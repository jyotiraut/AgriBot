# Chat Intent-Router — Implementation Plan

Wire the existing advisory engines into the conversational `/chat` flow so a
farmer can just *ask* — "अहिले के लगाउने?", "आलुको भाउ कति?", "पानी पर्छ?",
"कहिले काट्ने?" — and get an **accurate, engine-computed** answer, phrased in
Nepali by the LLM.

**Design principle (already how this codebase works):** Python decides the task
and supplies the facts; the LLM only *renders*. New intents dispatch to an
engine, and the engine's structured output is injected as an authoritative
`DATA:` block the model must not alter. This is what makes answers accurate and
non-hallucinated.

**No new LLM calls.** Intent already comes out of the existing multi-slot
extraction call, so classification is free. Only the single reply-render call
runs, exactly as today.

---

## 0. Scope & phasing

| Feature | Engine (ready?) | Phase |
|---|---|---|
| `planting` | `engine.crop_advisor.recommend_crops` ✅ ready | **1** |
| `weather`  | `rules.weather_integration.fetch_7_day_forecast` ✅ ready | **1** |
| `harvest`  | needs tiny `harvest_facts()` helper (spec §6) | **1** |
| `price`    | needs cached-forecast reader (spec §7) — do **not** call `get_full_price_analysis` per turn | **2** |

Ship Phase 1 first (planting → weather → harvest), each a vertical slice. Price
is Phase 2 because a per-turn Prophet run is too slow; it needs the cached
reader (and ideally the live market feed) first.

---

## 1. Understand — add intents (`rules/field_extractor.py`)

### 1a. Extend `VALID_INTENTS`
```python
VALID_INTENTS = (
    "answer", "question", "disease", "smalltalk", "offtopic", "correction",
    "planting", "price", "weather", "harvest",   # ← new advisory intents
)
```

### 1b. Add them to the multi-slot prompt
In `build_multislot_prompt`, extend the intent list and add few-shots
(Nepali / Romanized), e.g.:
```
  planting = asking WHICH crop to plant / what to grow now
  price    = asking a crop's price / rate / market value
  weather  = asking about weather, rain, frost, temperature
  harvest  = asking WHEN to harvest / cut / when a crop is ready
```
```
  "aile ke lagaune?"        -> {"intent":"planting","fields":{}}
  "alu ko bhau kati cha?"   -> {"intent":"price","fields":{"crop":{"value":"potato","confidence":1.0}}}
  "bholi pani parcha?"      -> {"intent":"weather","fields":{}}
  "tomato kahile tipne?"    -> {"intent":"harvest","fields":{"crop":{"value":"tomato","confidence":1.0}}}
```
> Note: fields still extract normally — "आलुको भाउ" yields both `intent=price`
> **and** `crop=potato`, so the router already knows the crop.

---

## 2. Detect deterministically — keyword fast-paths (`api/routes.py`)

LLM intent is good but not free of drift. Add cheap, reliable keyword detectors
mirroring the existing `_is_disease_question` / `_is_asking` (both already in
`routes.py`). These act as an **override** so detection never depends on the LLM
alone.

```python
_PLANTING_KW = ("ke lagaune", "k lagaune", "kun bali", "ke ropne", "के लगाउने",
                "के रोप्ने", "कुन बाली", "what to plant", "which crop")
_PRICE_KW    = ("bhau", "mulya", "rate", "price", "भाउ", "मूल्य", "दाम", "कति पर्छ")
_WEATHER_KW  = ("pani parcha", "mausam", "barsat", "hawa", "chiso", "पानी पर्छ",
                "मौसम", "वर्षा", "तुषारो", "गर्मी", "weather", "rain", "frost")
_HARVEST_KW  = ("kahile tipne", "kahile katne", "harvest", "कहिले टिप्ने",
                "कहिले काट्ने", "कहिले भित्र्याउने", "पाक्छ")

def _kw_intent(msg: str) -> str | None:
    m = msg.lower()
    # disease already wins earlier; order the rest by specificity
    if any(k in m for k in _HARVEST_KW):  return "harvest"
    if any(k in m for k in _PLANTING_KW): return "planting"
    if any(k in m for k in _PRICE_KW):    return "price"
    if any(k in m for k in _WEATHER_KW):  return "weather"
    return None
```

Apply it **after** the existing `if intent not in VALID_INTENTS:` fallback block
(around line 745), and let a confident keyword hit override a generic label —
but never override `disease` (crop problems keep priority):
```python
if intent != "disease":
    kw = _kw_intent(payload.message)
    if kw:
        intent = kw
```

---

## 3. Route (`rules/dialogue_policy.py`)

### 3a. New tasks, answered regardless of profile completeness
Add these branches at the **top** of `select_task`, right after the disease
check (so advisory questions are answered even mid-collection):
```python
if intent == "disease":  return "disease_answer"
if intent == "planting": return "plant_advice"
if intent == "price":    return "price_info"
if intent == "weather":  return "weather_info"
if intent == "harvest":  return "harvest_info"
```

### 3b. Make them detours so the next turn bridges back warmly
```python
DETOUR_TASKS = {
    "disease_answer", "answer_ask", "redirect",
    "plant_advice", "price_info", "weather_info", "harvest_info",   # ← add
}
```

### 3c. Tests (extend `tests/test_dialogue_flow.py`)
```python
def test_advisory_intents_route_directly():
    for intent, task in [("planting","plant_advice"), ("price","price_info"),
                         ("weather","weather_info"), ("harvest","harvest_info")]:
        # incomplete profile must NOT block an advisory answer
        assert select_task({"crop":"potato"}, intent=intent, accepted=False) == task

def test_disease_still_wins_over_advisory():
    assert select_task({}, intent="disease", accepted=False) == "disease_answer"
```

---

## 4. Dispatch to engines (`api/routes.py`, inside `chat()`)

Add **one** dispatch block right after `task = select_task(...)` and **before**
the RAG section. It computes an authoritative `data_facts` string; missing
required inputs degrade gracefully (ask, don't guess).

```python
from engine.crop_advisor import recommend_crops
from rules.zone_classifier import classify_zone   # month_to_season already imported

ADVISORY_TASKS = {"plant_advice", "price_info", "weather_info", "harvest_info"}
data_facts = ""

if task in ADVISORY_TASKS:
    district = profile.get("district")
    crop     = profile.get("crop") or normalise_crop(payload.message.lower())
    month    = profile.get("farming_month")            # int | None (None → current)

    if task == "plant_advice":
        if not district:
            # need location for an accurate answer — ask for it this turn
            data_facts = "ASK_DISTRICT"
        else:
            recs = recommend_crops(district, month=month,
                                   irrigation=profile.get("irrigation_type"), top_n=4)
            data_facts = _fmt_planting(recs, district)

    elif task == "weather_info":
        zone = classify_zone(district).value if district else "Hills"
        data_facts = _fmt_weather(_weather_cached(zone), zone)

    elif task == "harvest_info":
        data_facts = _fmt_harvest(harvest_facts(crop, sowing_month=month)) if crop \
                     else "ASK_CROP"

    elif task == "price_info":            # Phase 2
        data_facts = _fmt_price(price_snapshot(crop, month)) if crop else "ASK_CROP"
```

**Formatting helpers** (compact, model-friendly; keep to top 3–4 so the reply
stays short). Example for planting:
```python
def _fmt_planting(recs, district):
    if not recs:
        return f"NO_MATCH for {district}"
    lines = [f"District: {district}"]
    for i, c in enumerate(recs, 1):
        v = ", ".join(c["varieties"][:2]) or "—"
        lines.append(
            f"{i}. {c['crop_name']} | harvest: {c['harvest_months']} | "
            f"varieties: {v} | market: {c['market_value'] or '?'} | risk: {c['risk_tier'] or '?'}"
        )
    return "\n".join(lines)
```

**Suppress the profile question on advisory turns** (focus the reply), exactly
like disease does. Change line 957:
```python
SUPPRESS_Q = {"disease_answer"} | ADVISORY_TASKS
prompt_next_question = "" if task in SUPPRESS_Q else next_question
```

**Skip the redundant crop_tip RAG** for advisory tasks — guard the existing
`elif crop_for_rag:` branch with `and task not in ADVISORY_TASKS`.

**Pass the facts to the renderer** — extend the existing `build_user_message`
call (line 959):
```python
user_msg = build_user_message(
    task, prompt_next_question, known, payload.message, rag,
    crop_tip=crop_tip, data_facts=data_facts,   # ← new kwarg
)
```

---

## 5. Render (`rag/prompts.py`)

### 5a. Grounding rule — add to `KRISHIMITRA_SYSTEM`
```
- DATA दिइएको छ भने त्यहीँका तथ्य (बाली, मिति, भाउ, मौसम) हुबहु प्रयोग गर्नुस् —
  आफैँले अनुमान गरेर संख्या वा नाम कहिल्यै नबनाउनुस्। DATA मा ASK_DISTRICT/ASK_CROP
  भए, बरु त्यही जानकारी विनम्रतापूर्वक सोध्नुस्।
```

### 5b. New task instructions — add to `TASKS`
```python
"plant_advice":  "DATA मा दिइएका सिफारिस बालीहरू (क्रमैसँग) छोटो कारणसहित बताउनुस् — कुन बजार-मूल्य/जोखिमको आधारमा। ३-४ भन्दा बढी नभन्नुस्।",
"price_info":    "DATA मा दिइएको भाउ/प्रवृत्ति हुबहु नेपालीमा बताउनुस्, 'कालिमाटी अनुसार' उल्लेख गर्नुस्।",
"weather_info":  "DATA को मौसम जानकारी सरल नेपालीमा भन्नुस् र खेतीका लागि एउटा व्यावहारिक सुझाव दिनुस् (सिँचाइ/तुषारो/छहारी)।",
"harvest_info":  "DATA अनुसार काट्ने/टिप्ने उपयुक्त समय बताउनुस्; sowing मिति भए त्यसैबाट गणना गर्नुस्।",
```

### 5c. Extend `build_user_message` signature (append-only, non-breaking)
```python
def build_user_message(task, next_question, known_summary, farmer_said,
                       rag_context="", crop_tip="", data_facts=""):
    ...
    if data_facts:
        lines.append(f"DATA:\n{data_facts}")
    return "\n".join(lines)
```

---

## 6. `harvest_facts()` helper (Phase 1 — small, pure)

Add to `engine/crop_advisor.py` (reuses the calendar it already reads):
```python
def harvest_facts(crop: str, sowing_month: int | None = None) -> dict:
    """{crop, harvest_months, growth_weeks_min/max, expected_harvest_month?}.
    Reads the crop_calendar row; if sowing_month is known, projects the harvest
    month from growth weeks. Returns {} if the crop is unknown."""
    key = _norm(crop)
    df = load_calendar()               # lru_cache this — see §8
    row = df[df["crop_key"].map(_norm) == key]
    if row.empty:
        return {}
    r = row.iloc[0]
    wmin, wmax = parse_growth_weeks(r["Growth Duration (Weeks)"])
    out = {"crop": crop,
           "harvest_months": r["Typical Harvest Months (Nepali)"],
           "growth_weeks_min": wmin, "growth_weeks_max": wmax}
    if sowing_month and wmax:
        # BS month projection: sowing + ~weeks/4 months, wrapped 1-12
        months = round(((wmin + wmax) / 2) / 4.345)
        out["expected_harvest_month"] = ((sowing_month - 1 + months) % 12) + 1
    return out
```
(`load_calendar`, `parse_growth_weeks`, `_norm` already exist.)

---

## 7. `price_snapshot()` helper (Phase 2 — cached, never Prophet-per-turn)

Do **not** call `get_full_price_analysis()` in the request path (it trains
Prophet). Instead read the pre-computed cache `data/forecast_cache.csv`:
```python
@functools.lru_cache(maxsize=1)
def _forecast_cache():
    return pd.read_csv(os.path.join(HERE, "..", "data", "forecast_cache.csv"))

def price_snapshot(crop: str, month: int | None) -> dict:
    """{crop, current_price, trend_pct, peak_month} from the cached forecast.
    Returns {} if the crop isn't covered."""
    ...
```
Refresh the cache **out of band** via the existing `/forecast/retrain`
endpoint on a nightly schedule (see `notifications.py` scheduler). For genuinely
live prices, feed the daily Kalimati market data into `price_data` nightly and
re-run the cache — the answer then carries an "as of \<date\>" stamp.

---

## 8. Optimizations (do these — they matter per turn)

1. **Cache the calendar CSV.** `planting_filter.load_calendar()` does
   `pd.read_csv` on **every** call → runs each chat turn via `recommend_crops`.
   Wrap it: `@functools.lru_cache(maxsize=1)`. (Invalidate only on file change,
   which doesn't happen at runtime.) Biggest per-turn win.
2. **Cache weather per zone with a TTL** (~1–3 h) so Open-Meteo isn't hit every
   turn:
   ```python
   _wx: dict[str, tuple[float, dict]] = {}
   def _weather_cached(zone, ttl=3600):
       now = time.time(); hit = _wx.get(zone)
       if hit and now - hit[0] < ttl: return hit[1]
       data = fetch_7_day_forecast(zone); _wx[zone] = (now, data); return data
   ```
3. **Price uses the cached forecast**, never a per-turn Prophet run (§7).
4. **No extra LLM call** — intent is reused from the existing multi-slot call.
5. `_risk_lookup` in `crop_advisor` is already `lru_cache`d; keep it.
6. Keep `data_facts` to **top 3–4** items so the single render call stays cheap
   and the reply stays short/readable.

---

## 9. Edge cases / correctness checklist

- [ ] New intents added to **`VALID_INTENTS`** so a valid `planting` label isn't
      overwritten by the `intent not in VALID_INTENTS` fallback (line 745).
- [ ] Advisory branches placed **before** the completeness/`next_field` logic in
      `select_task` (answer even mid-collection).
- [ ] Every new task exists in **`TASKS`** (a missing key → `KeyError` in
      `build_user_message`). Verify all four.
- [ ] New tasks added to **`DETOUR_TASKS`** so the next turn resumes collection.
- [ ] `data_facts` sentinels **`ASK_DISTRICT` / `ASK_CROP` / `NO_MATCH`** handled
      by the grounding rule (§5a) — bot asks instead of inventing.
- [ ] `classify_zone` never returns None (falls back to Hills) — weather/plant
      dispatch is always safe even with an unknown district.
- [ ] Advisory tasks **suppress** `next_question` and **skip** `crop_tip` RAG.
- [ ] `month` is a **BS month int** everywhere (profile `farming_month`), matching
      `recommend_crops` / `get_calendar_context(bs_month=…)`.
- [ ] Disease keeps priority over the keyword fast-path.

---

## 10. Test plan

- `tests/test_dialogue_flow.py` — new routing + disease-priority tests (§3c).
- `tests/test_field_extractor` (or new) — `_kw_intent` returns the right label
  for Nepali/Romanized samples; disease not misrouted.
- `tests/test_crop_advisor.py` — add `harvest_facts` cases (known crop, unknown
  crop, sowing-month projection).
- **Manual/integration** (needs live LLM + MongoDB): drive `/chat` with
  "काभ्रेमा अहिले के लगाउने?" → expect engine crop list in the reply; then a
  profile answer next turn → expect `resume_ask` bridge-back.

---

## 11. Recommended execution order

1. §5c + §5a/§5b (render plumbing + grounding rule) — harmless foundation.
2. §1 + §2 (intents + fast-paths) and §3 (routing + tests) — provable offline.
3. §4 **planting only** + §8.1 (calendar cache) → first end-to-end slice.
4. §4 weather (+ §8.2 cache), then §6 harvest.
5. §7 price snapshot + nightly cache refresh (Phase 2).

Each step is independently shippable; nothing here is a big-bang change, and the
chat flow keeps working throughout because every addition is append-only.
