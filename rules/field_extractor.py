# extraction/field_extractor.py
import re
from typing import Optional

# ── Regex extractors — run before LLM, free and instant ──────────────────────

_DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")

LAND_PATTERN = re.compile(
    r"(\d+\.?\d*|[०-९]+\.?[०-९]*)\s*"
    r"(बिघा|bigha|रोपनी|ropani|कट्ठा|kattha|hectare|हेक्टेयर)",
    re.IGNORECASE
)
EXPERIENCE_PATTERN = re.compile(
    r"(\d+|[०-९]+)\s*(वर्ष|barsa|year|sal|साल)", re.IGNORECASE
)
LOAN_POSITIVE = re.compile(
    r"(ऋण\s*छ|loan\s*cha|rin\s*cha|chha\s*rin|yes.*loan|छ\s*ऋण|leko\s*chha)", re.IGNORECASE
)
LOAN_NEGATIVE = re.compile(
    r"(ऋण\s*छैन|loan\s*chaina|rin\s*chaina|no.*loan|छैन\s*ऋण)", re.IGNORECASE
)
MONTH_PATTERN = re.compile(
    r"(बैशाख|जेठ|असार|साउन|भदौ|असोज|कार्तिक|मङ्सिर|पुस|माघ|फागुन|चैत|"
    r"baisakh|jestha|ashadh|shrawan|bhadra|ashwin|kartik|mangsir|poush|magh|falgun|chaitra)",
    re.IGNORECASE
)
SOWING_DATE_PATTERN = re.compile(
    r"(बैशाख|जेठ|असार|साउन|भदौ|असोज|कार्तिक|मङ्सिर|पुस|माघ|फागुन|चैत|"
    r"baisakh|jestha|ashadh|shrawan|bhadra|ashwin|kartik|mangsir|poush|magh|falgun|chaitra)"
    r"\s*(\d{1,2}|[०-९]{1,2})?",
    re.IGNORECASE
)
OWNERSHIP_OWNED = re.compile(
    r"(aafno|आफ्नै|hamro|हाम्रो|owned|niji|निजी)", re.IGNORECASE
)
OWNERSHIP_LEASED = re.compile(
    r"(bhada|भाडा|leased|rented|thekka|ठेक्का)", re.IGNORECASE
)
IRRIGATION_MAP = {
    # "barsha" as a stem catches barsha / barshat / barshako / barshaako etc.
    "rainfed":   r"(barsha|barkha|varsha|aakashe|aakase|rain|वर्षा|आकाशे|बर्खा)",
    "drip":      r"(drip|thopa|थोपा)",
    "canal":     r"(canal|nahar|nahr|नहर|nali|नाली|kulo|कुलो)",
    "pump":      r"(pump|पम्प|boring|बोरिङ)",
    "sprinkler": r"(sprinkler|फव्वारा|fohara)",
}
FARMING_TYPE_MAP = {
    "organic":  r"(jaivik|जैविक|gobar|गोबर|compost|organic)",
    "chemical": r"(rasaynik|रासायनिक|dap|urea|chemical)",
}


def _ascii(val: str) -> str:
    return val.translate(_DEVANAGARI)


def try_regex_extract(field: str, message: str) -> Optional[dict]:
    """
    Try to extract `field` from message using regex.
    Returns {"value": ..., "confidence": 0.95, "raw": "..."} or None.
    """
    msg = message.strip()

    if field == "land_size":
        m = LAND_PATTERN.search(msg)
        if m:
            num_str = _ascii(m.group(1))
            unit    = m.group(2).lower()
            # normalise unit
            unit_map = {
                "बिघा": "bigha", "रोपनी": "ropani",
                "कट्ठा": "kattha", "हेक्टेयर": "hectare"
            }
            unit = unit_map.get(unit, unit)
            return {"value": float(num_str), "unit": unit,
                    "confidence": 0.95, "raw": m.group(0)}

    elif field == "experience_years":
        m = EXPERIENCE_PATTERN.search(msg)
        if m:
            return {"value": int(_ascii(m.group(1))),
                    "confidence": 0.95, "raw": m.group(0)}

    elif field == "has_loan":
        # Check NEGATIVE first: "loan chaina" (no loan) contains "loan cha",
        # which would otherwise match LOAN_POSITIVE and flip the meaning.
        if LOAN_NEGATIVE.search(msg):
            return {"value": False, "confidence": 0.95, "raw": msg}
        if LOAN_POSITIVE.search(msg):
            return {"value": True,  "confidence": 0.95, "raw": msg}

    elif field == "sowing_date":
        m = SOWING_DATE_PATTERN.search(msg)
        if m:
            return {"value": m.group(0).strip(),
                    "confidence": 0.90, "raw": m.group(0)}

    elif field == "farming_month":
        m = MONTH_PATTERN.search(msg)
        if m:
            return {"value": m.group(0).strip(),
                    "confidence": 0.90, "raw": m.group(0)}

    elif field == "land_ownership":
        if OWNERSHIP_OWNED.search(msg):
            return {"value": "owned",  "confidence": 0.95, "raw": msg}
        if OWNERSHIP_LEASED.search(msg):
            return {"value": "leased", "confidence": 0.95, "raw": msg}

    elif field == "irrigation_type":
        for itype, pattern in IRRIGATION_MAP.items():
            if re.search(pattern, msg, re.IGNORECASE):
                return {"value": itype, "confidence": 0.95, "raw": msg}

    elif field == "farming_type":
        has_org  = bool(re.search(FARMING_TYPE_MAP["organic"],  msg, re.IGNORECASE))
        has_chem = bool(re.search(FARMING_TYPE_MAP["chemical"], msg, re.IGNORECASE))
        if has_org and has_chem:
            return {"value": "mixed",    "confidence": 0.90, "raw": msg}
        if has_org:
            return {"value": "organic",  "confidence": 0.95, "raw": msg}
        if has_chem:
            return {"value": "chemical", "confidence": 0.95, "raw": msg}

    return None


# ── LLM fallback — called only when regex returns None ───────────────────────

FEW_SHOTS = {
    "land_size": [
        ("२ बिघा जमिन छ",          '{"value": 2.0, "unit": "bigha", "confidence": 1.0}'),
        ("paanch ropani xa",        '{"value": 5.0, "unit": "ropani", "confidence": 1.0}'),
        ("teen kattha",             '{"value": 3.0, "unit": "kattha", "confidence": 1.0}'),
        ("thaha chaina",            '{"value": null, "unit": null, "confidence": 0.0}'),
    ],
    "crop": [
        ("मकै लगाएको छु",           '{"value": "maize", "confidence": 1.0}'),
        ("alu kheti gardaichhu",    '{"value": "potato", "confidence": 1.0}'),
        ("golbheda ropeko",         '{"value": "tomato", "confidence": 1.0}'),
        ("thaha chaina",            '{"value": null, "confidence": 0.0}'),
    ],
    "district": [
        ("Baitadi ma basto garchhu", '{"value": "baitadi", "confidence": 1.0}'),
        ("म काठमाडौंमा छु",          '{"value": "kathmandu", "confidence": 1.0}'),
        ("thaha chaina",             '{"value": null, "confidence": 0.0}'),
    ],
    "sowing_date": [
        ("Baisakh 15 ma ropeko",    '{"value": "Baisakh 15", "confidence": 1.0}'),
        ("२ महिना अगाडि",           '{"value": "2 mahina agadi", "confidence": 0.8}'),
        ("thaha chaina",            '{"value": null, "confidence": 0.0}'),
    ],
    "farming_month": [
        ("Ashadh ma lagaune",       '{"value": "Ashadh", "confidence": 1.0}'),
        ("अर्को साउनमा",             '{"value": "Shrawan", "confidence": 1.0}'),
    ],
}

EXTRACT_SYSTEM = (
    "You extract one specific field from a Nepali farmer's message. "
    "Return JSON only. No explanation. null if not mentioned."
)

def build_extract_prompt(field: str, message: str) -> str:
    shots = FEW_SHOTS.get(field, [])
    examples = "\n".join(
        f'  Farmer: "{f}" → {o}' for f, o in shots
    )
    schema = {
        "land_size":        '{"value": float|null, "unit": string|null, "confidence": 0-1}',
        "crop":             '{"value": "english_name"|null, "confidence": 0-1}',
        "district":         '{"value": "lowercase_name"|null, "confidence": 0-1}',
        "sowing_date":      '{"value": "raw string"|null, "confidence": 0-1}',
        "farming_month":    '{"value": "month_name"|null, "confidence": 0-1}',
        "experience_years": '{"value": int|null, "confidence": 0-1}',
        "irrigation_type":  '{"value": "rainfed|canal|pump|drip|sprinkler"|null, "confidence": 0-1}',
        "farming_type":     '{"value": "organic|chemical|mixed"|null, "confidence": 0-1}',
        "has_loan":         '{"value": true|false|null, "confidence": 0-1}',
        "land_ownership":   '{"value": "owned|leased"|null, "confidence": 0-1}',
    }.get(field, '{"value": null, "confidence": 0.0}')

    return (
        f"Extract field: {field}\n"
        f"Schema: {schema}\n"
        + (f"Examples:\n{examples}\n" if examples else "")
        + f"Farmer said: \"{message}\"\n"
        "Return JSON only:"
    )


# ── Combined intent classification + field extraction (one LLM call) ──────────
# Replaces scattered keyword heuristics (_is_asking / _is_disease_question) with
# a single structured decision, and also captures out-of-order corrections.

VALID_INTENTS = ("answer", "question", "disease", "smalltalk", "offtopic", "correction")

_VALUE_SCHEMA = {
    "land_size":        '"value": float|null, "unit": "bigha|ropani|kattha|hectare"|null',
    "crop":             '"value": "english_crop_name"|null',
    "district":         '"value": "lowercase_district"|null',
    "sowing_date":      '"value": "raw date string"|null',
    "farming_month":    '"value": "month_name"|null',
    "experience_years": '"value": int|null',
    "irrigation_type":  '"value": "rainfed|canal|pump|drip|sprinkler"|null',
    "farming_type":     '"value": "organic|chemical|mixed"|null',
    "has_loan":         '"value": true|false|null',
    "land_ownership":   '"value": "owned|leased"|null',
    "farmer_type":      '"value": "A|B"|null',
}

CLASSIFY_EXTRACT_SYSTEM = (
    "You are the turn router for a Nepali farming assistant that is collecting a "
    "farmer's profile one field at a time. For each message decide the INTENT and, "
    "if it answers the current field, extract the value. Understand Nepali, "
    "Romanized Nepali, Hindi and English. Return JSON only — no commentary."
)

_INTENT_GUIDE = """\
intent meanings:
- "answer"     : the farmer is answering the CURRENT field being asked.
- "question"   : the farmer asks a general farming question (not a crop problem).
- "disease"    : the farmer describes a crop disease/pest/symptom or asks about one.
- "smalltalk"  : greeting, thanks, or casual chit-chat.
- "offtopic"   : unrelated to farming.
- "correction" : the farmer revises a detail they gave earlier — set corrected_field."""

_CLASSIFY_SHOTS = {
    "crop": [
        ("alu lagaeko chu", '{"intent":"answer","value":"potato","confidence":1.0,"corrected_field":null}'),
        ("mero tomato ma pat kalo bhayo k garne", '{"intent":"disease","value":null,"confidence":0.9,"corrected_field":null}'),
        ("kahile mal halne ho", '{"intent":"question","value":null,"confidence":0.9,"corrected_field":null}'),
        ("namaste sathi", '{"intent":"smalltalk","value":null,"confidence":0.9,"corrected_field":null}'),
    ],
    "land_size": [
        ("2 ropani", '{"intent":"answer","value":2.0,"unit":"ropani","confidence":1.0,"corrected_field":null}'),
        ("aile jaggabare hoina, kira lagyo teslai k garne", '{"intent":"disease","value":null,"confidence":0.9,"corrected_field":null}'),
        ("mero bali ta alu hoina makai ho", '{"intent":"correction","value":"maize","confidence":0.9,"corrected_field":"crop"}'),
    ],
}


# ── Multi-slot extraction — pull EVERY field the farmer stated in one call ────
# This is the primary understanding step. A farmer volunteers facts non-linearly
# ("Kavre ma 2 ropani alu cha" = type + district + land + crop); we extract them
# all at once instead of one keyword/field at a time. Rules then normalise +
# validate; only high-confidence values are saved.

MULTISLOT_FIELDS = (
    "farmer_type", "crop", "district", "land_size", "sowing_date",
    "farming_month", "land_ownership", "irrigation_type",
    "experience_years", "farming_type", "has_loan",
)

MULTISLOT_SYSTEM = (
    "You read ONE message from a Nepali farmer chatting with a farming assistant "
    "and extract EVERY profile detail the farmer stated in it — not just one. "
    "Understand Nepali, Romanized Nepali, Hindi and English. Only include a field "
    "if the farmer actually stated it; never guess. Return JSON only."
)


def build_multislot_prompt(
    message: str,
    profile: dict | None = None,
    current_field: str | None = None,
) -> str:
    """
    Build a prompt that returns the farmer's intent plus every profile field
    present in the message, each with a confidence:

      {"intent": "answer|question|disease|smalltalk|offtopic",
       "fields": {"<field>": {"value": ..., "confidence": 0-1}, ...}}

    Only stated fields are returned. land_size additionally carries "unit".

    current_field is the field the assistant just asked about — critical context
    so a terse reply like "barshako pani" is confidently mapped to irrigation_type.
    """
    asked = ""
    if current_field and current_field != "farmer_type":
        asked = (
            f"IMPORTANT: the assistant just asked the farmer about '{current_field}'. "
            f"A short reply most likely ANSWERS this field — map it to '{current_field}'.\n"
        )

    known = ""
    if profile:
        have = [k for k in ("farmer_type", "crop", "district") if profile.get(k)]
        if have:
            known = "Already known: " + ", ".join(have) + " (extract only new info or clear corrections)\n"

    return (
        "Extract any of these fields the farmer stated:\n"
        '- farmer_type: "A" if the crop is ALREADY planted/growing, "B" if only planning\n'
        "- crop: english crop name (potato, tomato, maize, ...)\n"
        "- district: nepali district, lowercase english\n"
        "- land_size: number, with unit bigha|ropani|kattha|hectare\n"
        "- sowing_date: raw date string exactly as said\n"
        "- farming_month: nepali month name (planting month, for planners)\n"
        "- land_ownership: owned | leased\n"
        "- irrigation_type: rainfed | canal | pump | drip | sprinkler\n"
        "- experience_years: integer\n"
        "- farming_type: organic | chemical | mixed\n"
        "- has_loan: true | false\n"
        "\nAlso classify intent:\n"
        "  disease = describing/asking about a crop disease, pest, or problem\n"
        "  question = a general farming question\n"
        "  smalltalk = greeting/thanks/chit-chat, offtopic = unrelated\n"
        "  answer = giving profile information\n\n"
        + asked
        + known +
        'Return JSON: {"intent":"...","fields":{"<field>":{"value":...,"confidence":0-1}, ...}}\n'
        'For land_size include a "unit" key.\n'
        "Examples:\n"
        '  "maile tomato lagako chhu" -> {"intent":"answer","fields":{"farmer_type":{"value":"A","confidence":1.0},"crop":{"value":"tomato","confidence":1.0}}}\n'
        '  "Kavre ma 2 ropani alu cha" -> {"intent":"answer","fields":{"farmer_type":{"value":"A","confidence":0.9},"district":{"value":"kavre","confidence":1.0},"land_size":{"value":2,"unit":"ropani","confidence":1.0},"crop":{"value":"potato","confidence":1.0}}}\n'
        '  (asked about irrigation_type) "barshako pani nai ho" -> {"intent":"answer","fields":{"irrigation_type":{"value":"rainfed","confidence":1.0}}}\n'
        '  "mero tomato ma pat kalo bhayo" -> {"intent":"disease","fields":{}}\n'
        '  "kahile mal halne ho" -> {"intent":"question","fields":{}}\n'
        f'Farmer said: "{message}"\n'
        "Return JSON only:"
    )


FARMER_TYPE_SYSTEM = (
    "Decide whether a Nepali farmer ALREADY has a crop planted or is only "
    "PLANNING to plant. Understand Nepali, Romanized Nepali, Hindi and English. "
    "Return JSON only."
)


def build_farmer_type_prompt(message: str) -> str:
    """
    LLM fallback for farmer-type classification when keyword matching is unsure.
    Returns {"farmer_type": "A"|"B"|null, "confidence": 0-1}.
      A = crop already planted / currently in the field.
      B = planning / thinking of planting, not yet planted.
    """
    return (
        "Has the farmer ALREADY planted a crop (A), or are they PLANNING to plant (B)?\n"
        "A = already planted / crop currently growing in the field.\n"
        "B = planning, thinking, or intending to plant — not yet planted.\n"
        'Return JSON: {"farmer_type": "A|B"|null, "confidence": 0-1}\n'
        "Examples:\n"
        '  "maile tomato lagako chhu" -> {"farmer_type":"A","confidence":1.0}\n'
        '  "alu ropisake" -> {"farmer_type":"A","confidence":1.0}\n'
        '  "makai lagaune socheko chu" -> {"farmer_type":"B","confidence":1.0}\n'
        '  "ropne yojana banaudai" -> {"farmer_type":"B","confidence":1.0}\n'
        '  "namaste" -> {"farmer_type":null,"confidence":0.0}\n'
        f'Farmer said: "{message}"\n'
        "Return JSON only:"
    )


def build_classify_extract_prompt(field: str, message: str) -> str:
    """
    Build a single prompt that returns intent + (optional) extracted value for
    the current field. Output schema:
      {"intent": <one of VALID_INTENTS>,
       <field value schema>,
       "corrected_field": "<field name>"|null,
       "confidence": 0-1}
    """
    value_schema = _VALUE_SCHEMA.get(field, '"value": null')
    shots = _CLASSIFY_SHOTS.get(field) or _CLASSIFY_SHOTS["crop"]
    examples = "\n".join(f'  Farmer: "{f}" -> {o}' for f, o in shots)

    return (
        f"Current field being collected: {field}\n"
        f"{_INTENT_GUIDE}\n"
        f'Return JSON: {{"intent": "answer|question|disease|smalltalk|offtopic|correction", '
        f'{value_schema}, "corrected_field": "field_name"|null, "confidence": 0-1}}\n'
        f"Examples:\n{examples}\n"
        f'Farmer said: "{message}"\n'
        "Return JSON only:"
    )