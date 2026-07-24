# KrishiMitra — Technical Case Analysis

A detailed walkthrough of the three subsystems that make the product work: how
the knowledge base is built (ingestion), how a chat message becomes a reply
(extraction + routing + generation), and how a credit score is calculated. Written
from the actual implementation — every number, threshold, and formula below is
what the code does today, not an approximation.

---

## 1. Knowledge ingestion — how the bot learns to answer disease/farming questions

The chat's disease-and-general-knowledge answers aren't generated from the LLM's
own training data — they're retrieved from a purpose-built knowledge base and
handed to the LLM as grounding context (retrieval-augmented generation, RAG).
There are two separate ingestion paths, because the source documents aren't
uniform.

### 1a. Standard PDF ingestion (crop guides)

Plain-text PDFs — crop guides for potato, tomato, cauliflower — go through a
straightforward pipeline:

1. **Parse** — each PDF is opened with PyMuPDF and every page's text layer is
   extracted and concatenated.
2. **Chunk** — the full text is split into ~500-character chunks with 50
   characters of overlap (so a fact split across a chunk boundary still reads
   completely in at least one chunk).
3. **Tag metadata** — each chunk is tagged with its source filename, a chunk
   index, and a guessed crop (matched from the filename — "potato-guide.pdf" →
   `potato`), so answers can later be filtered or attributed by crop.
4. **Embed and store** — every chunk is turned into a vector embedding and
   upserted into a vector database, with a **deterministic ID** derived from
   `hash(filename + chunk index)`. Re-running ingestion on an unchanged file
   updates the same points instead of duplicating them — ingestion is safe to
   re-run any time.
5. The vector collection is auto-recreated if the embedding model's output
   dimension ever changes, so the ingest and retrieval sides can never
   silently disagree about vector size.

### 1b. Vision-based ingestion (the Krishi Diary — legacy Nepali fonts)

The *Krishi Diary 2082* is a much harder case: its PDF text layer is encoded in
old, non-Unicode Nepali fonts (FontasyHimali, Preeti, and others) mixed with
real Unicode. Extracting its "text" directly produces unreadable character
soup. Standard OCR doesn't help either, since the fonts don't map cleanly to
any encoding table. The fix: **render each page as an image and have a vision
model read it**, the same way a human would — since the visual glyphs are
legible even though the underlying byte encoding isn't.

This runs in two deliberately separate phases so that re-chunking the output
never re-pays for the (paid) vision calls:

**Phase 1 — transcribe** (paid, cached, resumable): each page is rendered to a
PNG and sent to Gemini flash vision with an instruction to transcribe it into
clean Markdown — prose and tables, in proper Devanagari Unicode, skipping
calendar grids and decorative elements. Three cost-control measures make this
cheap to run at book scale:
- A **free Python pre-filter** runs before any API call: pages that are mostly
  calendar grids (detected by counting English weekday names in the garbled
  text layer) or near-blank (character count below a threshold) are skipped
  without ever calling the model.
- Pages that pass the filter but the model decides hold no useful agricultural
  content return the single token `SKIP` instead of a full transcription —
  cheap on output tokens.
- Every result (transcription or `SKIP`) is **cached to disk per page**, with
  an atomic write (temp file + rename) so a process killed mid-write never
  leaves a corrupt cache entry. Re-running the command only processes pages
  that don't have a finished cache file yet — a multi-hour transcription job
  can be safely interrupted and resumed.

**Phase 2 — ingest** (free, re-runnable): the cached Markdown pages are chunked
**table-aware** — each Markdown table becomes its own chunk (prefixed with the
nearest heading, so a bare row like "urea | 120 kg" keeps its crop/section
context when retrieved on its own), while surrounding prose is split with the
same recursive splitter used for the crop-guide PDFs (600 characters here, since
diary prose tends to be denser). Crop is detected from Devanagari keywords
(आलु → potato, गोलभेडा → tomato, etc.) rather than filename, since the whole
diary is one file covering many crops. Chunks are embedded and upserted the
same way as the standard pipeline.

### 1c. Shared embedding/retrieval layer

Both pipelines funnel into the same embedding model and vector store, loaded
once per process and reused (not reloaded per chat turn):

| Setting | Value |
|---|---|
| Embedding model | `BAAI/bge-m3` — multilingual, 1024-dimensional, chosen specifically because it handles Nepali well |
| Vector store | Qdrant — either an embedded local folder (no server needed) or a remote/cloud instance, selected by whether the configured URL starts with `http` |
| Similarity metric | Cosine distance |
| Retrieval | top-3 nearest chunks per query by default; an optional minimum similarity score can filter out weak matches |

At chat time, a disease/knowledge question's retrieval query is built from the
farmer's own wording plus the crop name and district (if known), so the
vector search is as specific as possible; the top matches are stripped of
markdown formatting and handed to the LLM as grounding context — the LLM
paraphrases them into a warm, conversational Nepali reply rather than
hallucinating an answer from scratch.

---

## 2. Chat reply pipeline — how one message becomes one reply

Every incoming chat message goes through the same fixed pipeline, in order.
Nothing about *which* task runs is decided by the LLM — that's deliberate: a
plain Python router picks the task, and the LLM's only job is turning the
result into natural language.

### Step 1 — Fast, cheap extraction attempts first

Before ever calling an LLM, two free/cheap checks run:
- A **keyword classifier** checks whether the message is an obvious farmer-type
  statement ("I've already planted..." vs "I'm planning to...").
- A **regex extractor** tries to pull the exact field currently being asked
  about (a land size, a date, a yes/no loan answer) directly from the text
  pattern, with high confidence, no LLM call needed.

### Step 2 — Multi-slot LLM extraction (one call, not one-field-at-a-time)

A farmer rarely answers one question at a time — a message like *"Kavre ma 2
ropani alu cha"* states district, land size, and crop all at once, unprompted.
A single LLM call is given the message (plus which field was just asked, for
context on short replies) and returns **every profile field it can confidently
identify**, each with its own confidence score, plus an overall conversational
**intent** label (answer / question / disease / smalltalk / offtopic /
correction / planting / price / weather / harvest / market_trend).

### Step 3 — Deterministic acceptance rules

Extracted values aren't saved blindly:
- A value below the confidence threshold is discarded.
- A value for a field that's *already known* is only overwritten if it's the
  field currently being asked about, or the new value came in at very high
  confidence (treated as a correction).
- Accepted fields are normalised (crop-name aliases, unit conversions, Nepali
  digit conversion, date parsing) before being saved.

### Step 4 — Keyword override for advisory intents

Even after the LLM assigns an intent, a fast keyword check can override it for
the four "advisory" intents (planting / price / weather / harvest /
market_trend) — this guarantees a question like *"आलुको भाउ कति?"* always
routes to the price engine even if the LLM's own intent label were ever wrong
or inconsistent. Disease detection always takes priority over everything else,
since a sick crop is the most time-sensitive kind of question.

### Step 5 — Task selection (pure function, unit-tested)

Given the (possibly updated) profile, the classified intent, and whether a
value was just accepted, a single deterministic function decides the task for
this turn — e.g. `disease_answer`, `plant_advice`, `price_info`,
`harvest_info`, `market_trend_info`, `ack_ask` (acknowledge + ask the next
profile question), `resume_ask` (return warmly from an advisory detour), or
`advise` (profile complete, free-form Q&A). This function takes no LLM input at
all — it's pure logic over the current state, which is what makes it reliably
testable.

### Step 6 — Engines compute the facts; the LLM only phrases them

For every advisory task, a dedicated engine computes the actual answer from
real data — never from the LLM's own guess:

| Task | What computes the answer |
|---|---|
| `plant_advice` | Crop calendar (season + altitude fit for the farmer's district/zone) joined with a curated variety/market table and a risk sheet, plus live 7-day weather |
| `price_info` | A per-crop price forecasting model's cached output for the requested month, with trend into next month and the best-selling month |
| `harvest_info` | Crop calendar's harvest window, projected forward from the farmer's stated sowing month using average growth duration |
| `market_trend_info` | Crops whose harvest window includes the current/asked month, ranked by a demand-opportunity score (not just raw price — see §3 below) |
| `disease_answer` | The RAG retrieval described in §1, grounded in the farmer's own wording |

The result is rendered into a compact, plain-text "DATA" block — crop names,
numbers, dates, exactly as computed — and that block, along with a short
instruction for the current task, is the only thing the LLM receives for this
turn. The system prompt explicitly instructs the model to use DATA facts
verbatim and never invent a number, date, or crop name of its own; if a
required piece of context is missing (e.g. no district known yet), the DATA
block contains a sentinel value that tells the model to ask for it instead of
guessing.

### Step 7 — Reply generation

One final LLM call, given the task instruction, the DATA block (if any), the
farmer's known profile so far, and the last few turns of conversation for
continuity, produces the reply — always in Nepali, always as a single
question at a time when profile collection is still in progress, and skipping
the profile question entirely on advisory/disease turns so the reply stays
focused on what the farmer actually asked.

---

## 3. Market Analysis — the same "engines compute, don't guess" principle

The Market Analysis page and the chat's price/market_trend answers are backed
by the same underlying pipeline:

1. **Historical demand scoring** — years of real wholesale market price
   records are grouped by crop and Nepali calendar month, and each crop-month
   combination is scored on three signals: how much its price spikes above its
   own annual average that month (40% weight), how volatile the crop's price
   is across the year — a proxy for exploitable supply gaps (35% weight), and
   whether the price sits above the crop's own median, signalling sustained
   rather than one-off demand (25% weight). This keeps a crop that's simply
   *always* expensive (like an out-of-season imported fruit) from dominating
   every month's ranking — the score is about *this month being unusually good
   for this crop*, not absolute price level.
2. **Forecasting** — a time-series forecasting model is trained independently
   per crop on its own price history and projects a year ahead; outliers
   beyond 3 standard deviations are stripped before training. The daily
   forecast is aggregated into Nepali-calendar months and cached to disk, so
   the live chat/API never retrains a model inside a request — it only reads
   the pre-computed cache.
3. **Harvest calendar join** — for "what should I harvest and sell this
   month," the crop calendar's harvest-window data is joined against that
   month's forecast and demand score, so the answer only ever surfaces crops
   that are actually in season, ranked by opportunity rather than raw price.
4. **Planting recommendations** — the ranked "what to plant" cards run a
   fuller evaluation per candidate crop: is it plantable this month for the
   farmer's zone and altitude, what's its forecast price and demand score,
   what's its risk tier (flood/drought/frost/price-volatility), and what's its
   feasibility given the stated sowing month — combined into a single
   opportunity score used to rank the results.

---

## 4. Credit scoring — how the Admin Dashboard's numbers are calculated

The score is a transparent, rule-based 100-point model — not a black-box ML
prediction — built from five weighted components, computed once enough of the
farmer's profile (crop, land, irrigation, experience, estimated income) is
known from the conversation.

### The five components

| Component | Max points | What it measures | Scoring logic |
|---|---|---|---|
| **Debt-to-income (DTI)** | 35 | Can they actually repay this specific loan? | Monthly EMI ÷ monthly income. ≤25% → 35 pts (very comfortable), ≤40% → 27 pts (standard safe zone), ≤60% → 16 pts, ≤80% → 7 pts, ≤100% → 2 pts, over 100% → 0 pts. No loan requested → neutral 18 pts. |
| **Irrigation reliability** | 20 | How much does income depend on the monsoon? | Drip/borewell → 20 (most reliable), pump → 17, sprinkler → 15, canal → 12, rain-fed → 3 (highest risk — entirely monsoon-dependent), unknown → neutral 7. |
| **Land ownership** | 20 | Is there collateral if the loan defaults? | Owned → 20, partial → 11, leased → 8 (no collateral), unknown → 7. |
| **Farming experience** | 15 | Track record / reliability | 0 years → 1 pt (first-season farmers default at a measurably higher rate), 1 year → 5, 2 years → 8, 3–4 years → 12, 5+ years → 15. |
| **Crop price stability** | 10 | How volatile is the farmer's income likely to be? | Staples (paddy/wheat/maize) → 10 (most stable), potato → 8, cauliflower → 5, tomato → 1 (prices swing 3–4× per season in Nepal — highest risk), unknown crop → neutral 5. |

### EMI and DTI, calculated properly

The monthly EMI (equated monthly instalment) uses the standard amortization
formula over a 12-month tenure at 7% annual interest (Nepal's subsidised
agricultural loan rate):

```
EMI = P × [r(1+r)ⁿ] / [(1+r)ⁿ − 1]
```

where P is the loan amount, r is the monthly interest rate, and n is the
number of months. DTI is then `EMI ÷ (annual estimated income ÷ 12)`.

### From score to decision

| Score | Risk level | Default probability | Recommendation |
|---|---|---|---|
| 80–100 | Low | 4% | Approve |
| 65–79 | Medium | 9% | Review, conditions (e.g. crop insurance) |
| 50–64 | Medium | 15% | Review, conditions |
| 35–49 | High | 22% | Reduce loan amount or require collateral |
| 20–34 | High | 35% | Reduce loan amount or require collateral |
| Below 20 | Very high | 60% | Decline |

The default-probability estimate is further nudged upward if the DTI ratio
itself is high (up to an extra 20 percentage points for a DTI over 100%),
independent of which score bracket the farmer landed in — a high raw score
with an unusually high DTI still gets flagged.

**Three hard overrides** can downgrade a recommendation regardless of the
score bracket, because they represent bright-line lending rules rather than
graduated risk:
1. **EMI exceeds monthly income outright** → automatic decline, with the exact
   shortfall stated in the decision note.
2. **Requested loan exceeds the EMI-based safe limit** (the loan amount whose
   EMI would consume 40% of monthly income) → downgraded to "review" even if
   the component score alone would have approved it.
3. **Requested loan exceeds 65% of the farmer's estimated harvest income** (a
   standard agricultural-lending cap) → downgraded to "review."

### Watch points

Alongside the numeric score, the scorer generates plain-language flags for
anything a loan officer should specifically double-check: high repayment
burden, a first-season or one-year farmer, a price-volatile crop like tomato,
rain-fed irrigation, or leased land with no collateral. These are exactly what
renders under each expanded row in the Admin Dashboard.

### What the dashboard shows vs. what it computes

The Admin Dashboard **never recalculates anything** — it reads the score,
risk level, recommendation, full component breakdown, loan/EMI figures, and
watch points exactly as they were computed and saved at scoring time, joined
with the farmer's account email for identification. Scoring itself runs
whenever a profile has enough information (crop, district, land size, month)
to produce an income estimate — not on every dashboard page load.
