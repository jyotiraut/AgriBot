import re
from typing import Optional

from rules.unit_converter import (
    NEPALI_NUMBER_WORDS,
    NEPALI_MONTH_TO_INT,
    PLACE_TO_DISTRICT,
    ALL_DISTRICTS,
    DISTRICT_CANONICAL,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. CROP NAME NORMALISATION  (delegates to the single source of truth)
# ─────────────────────────────────────────────────────────────────────────────
# The canonical alias table lives in rules/crop_normalizer.py so the batch
# extractor and the live chat resolve crop names identically.

from rules.crop_normalizer import normalize_crop as _normalize_crop, is_valid_crop


def normalise_crop(raw: str) -> Optional[str]:
    """
    Map a raw crop string from the farmer (any language/spelling) to a
    canonical lowercase English crop name. Returns None if unrecognised
    (so the caller can keep the raw value and let the LLM handle it).
    """
    if not raw:
        return None
    resolved = _normalize_crop(raw)
    return resolved if is_valid_crop(resolved) else None


# ─────────────────────────────────────────────────────────────────────────────
# 2. FARMER TYPE CLASSIFICATION  (Python resolves from keyword signals)
# ─────────────────────────────────────────────────────────────────────────────

_TYPE_A_SIGNALS: set[str] = {
    # Romanised — single words matched against token set only
    "chha", "cha", "lagaeko", "lageako", "lagaisakyo", "lagaiskyo",
    "ropeko", "ropeako", "laaeko",
    "gardaichhu", "gardaichhau", "lagaisake", "ropi", "ropisake",
    # "planted" spelling variants farmers actually type
    "lagako", "lageko", "lagayeko", "lagayo", "lagaya", "lagaeko",
    "lagai", "ropya", "ropeko", "ropiyo", "ropeko",
    # Multi-word phrases (matched as substrings in full text)
    "chha ni", "xcha", "xa", "kheti gardaichhu", "bali chha",
    "chha hola", "lagaisake", "ropi sake", "lagako chhu", "lagako cha",
    # Devanagari
    "छ", "लगाइसकेको", "रोपेको", "खेती गर्दैछु", "लगाएको", "रोपिसकेको",
    "लगाको", "लगायो",
}

_TYPE_B_SIGNALS: set[str] = {
    # Romanised — single words
    "lagaune", "lagauncha", "socheko", "socheko",
    "lagauna", "bichar", "abhai",
    "banaudai",   # "yojana banaudai chhu"
    "yojana",     # strong planning signal
    "ropney",     # "ropney yojana chha"
    "sochnu",     # "sochnu vako"
    # Multi-word phrases (matched as substrings in full text)
    "plan chha", "plan xa", "sochda chhu", "lagaune bichar",
    "yo season ma lagaune", "lagauna lageako", "lagaune socheko",
    "lagaune plan", "ropney yojana", "yojana chha", "yojana banaudai",
    # Devanagari
    "लगाउने", "सोचेको", "योजना छ", "लगाउने विचार", "लगाउँछु",
    "लगाउने सोचेको", "रोप्ने योजना", "योजना",
}


def classify_farmer_type(farmer_reply: str) -> Optional[str]:
    """
    Classify farmer as Type A (planted) or Type B (planning) from their raw reply.
    Returns "A", "B", or None (ambiguous — needs clarification).

    FIX: Single-word signals are matched against the TOKEN SET only (not substrings),
    preventing "cha" from matching inside "banaudai chhu" etc.
    Multi-word signals are matched as substrings in the full lowercased text.

    Called in the route/extraction layer BEFORE the LLM prompt is built.
    """
    text = farmer_reply.strip().lower()
    words = set(re.split(r"[\s,।!?]+", text))

    a_score = 0
    b_score = 0

    for sig in _TYPE_A_SIGNALS:
        if " " in sig or any(c in sig for c in ["छ", "को", "गर्"]):
            # Multi-word or Devanagari phrase → substring match in full text
            if sig in text:
                a_score += 1
        else:
            # Single-word token → exact word match only
            if sig in words:
                a_score += 1

    for sig in _TYPE_B_SIGNALS:
        if " " in sig or any(c in sig for c in ["लग", "सो", "यो"]):
            # Multi-word or Devanagari phrase → substring match in full text
            if sig in text:
                b_score += 1
        else:
            # Single-word token → exact word match only
            if sig in words:
                b_score += 1

    if a_score > 0 and b_score == 0:
        return "A"
    if b_score > 0 and a_score == 0:
        return "B"
    # Both or neither → ambiguous
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. DISTRICT NORMALISATION  (Python resolves — LLM never sees the map)
# ─────────────────────────────────────────────────────────────────────────────

def normalise_district(raw: str) -> Optional[str]:
    """
    Map a raw place/district string to a canonical lowercase district name.
    Returns None if unrecognised (caller decides how to handle).
    """
    if not raw:
        return None
    key = raw.strip().lower()
    # City → district
    if key in PLACE_TO_DISTRICT:
        return PLACE_TO_DISTRICT[key]
    # Known district (exact)
    if key in ALL_DISTRICTS:
        return DISTRICT_CANONICAL.get(key, key.title())
    # Partial match against district list
    for d in ALL_DISTRICTS:
        if d in key or key in d:
            return DISTRICT_CANONICAL.get(d, d.title())
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 4. FIELD ORDER + STATE MACHINE  (Python owns — LLM never re-derives this)
# ─────────────────────────────────────────────────────────────────────────────

TYPE_A_FIELD_ORDER: list[str] = [
    "crop", "sowing_date", "district", "land_size",
    "land_ownership", "irrigation_type", "experience_years",
    "farming_type", "has_loan",
]

TYPE_B_FIELD_ORDER: list[str] = [
    "crop", "district", "land_size", "land_ownership",
    "farming_month", "irrigation_type", "experience_years",
    "farming_type", "has_loan",
]

# Human-readable Nepali question for each field — the single source of truth.
# Fields that need different phrasing per farmer type use a {"A": ..., "B": ...} dict.
FIELD_QUESTIONS: dict[str, str | dict] = {
    "crop": {
        "A": "राम्रो! कुन बाली लगाउनुभएको छ?",
        "B": "राम्रो! कुन बाली लगाउने सोच्दै हुनुहुन्छ?",
    },
    "sowing_date":         "कहिले रोप्नुभयो — महिना र मिति थाहा छ?",
    "district": {
        "A": "तपाईं कुन जिल्लामा खेती गर्नुहुन्छ?",
        "B": "तपाईं कुन जिल्लामा खेती गर्ने सोच्नुभएको छ?",
    },
    "land_size_hectares":  "तपाईंको खेत कति ठूलो छ — रोपनी, बिघा, वा हेक्टेयरमा बताउनुस्।",
    "land_ownership": {
        "A": "यो जग्गा आफ्नै हो कि भाडामा लिनुभएको?",
        "B": "रोप्ने जग्गा आफ्नै हो कि भाडामा लिने सोच्नुभएको छ?",
    },
    "farming_month": {
        "A": "कहिले रोप्नुभयो — महिना र मिति थाहा छ?",   # Type A shouldn't reach here
        "B": "कुन महिनामा लगाउने सोच्नुभएको छ?",
    },
    "irrigation_type": {
        "A": "खेतमा सिंचाइको के व्यवस्था छ — वर्षाको पानी, नहर, पम्प, वा थोपा सिंचाइ?",
        "B": "खेतमा सिंचाइको के व्यवस्था छ — वर्षाको पानी, नहर, पम्प, वा थोपा सिंचाइ?",
    },
    "experience_years": {
        "A": "खेतीमा तपाईंलाई कति वर्षको अनुभव छ?",
        "B": "खेतीमा तपाईंलाई कति वर्षको अनुभव छ?",
    },
    "farming_type": {
        "A": "तपाईं जैविक खेती गर्नुहुन्छ कि रासायनिक मल प्रयोग गर्नुहुन्छ?",
        "B": "जैविक खेती गर्ने सोच्नुभएको छ कि रासायनिक मल प्रयोग गर्ने?",
    },
    "has_loan": {
        "A": "के अहिले खेतीको लागि कुनै ऋण लिनुभएको छ?",
        "B": "के खेतीको लागि ऋण लिने सोच्नुभएको छ?",
    },
}


def get_next_field(profile: dict) -> Optional[str]:
    farmer_type = profile.get("farmer_type")
    if not farmer_type:
        return "farmer_type"

    order = TYPE_A_FIELD_ORDER if farmer_type == "A" else TYPE_B_FIELD_ORDER
    for field in order:
        if field == "land_size":
            # land_size is collected as raw, derived into land_size_hectares
            val = profile.get("land_size_hectares")  # skip if hectares already saved
        else:
            val = profile.get(field)
        if val is None or val == "":
            return field
    return None


def get_next_question(profile: dict) -> Optional[str]:
    """
    Return the exact Nepali question string for the next field.
    Returns None when the profile is complete (advisory mode).

    Always uses farmer_type to select the right phrasing from dict-valued fields.
    """
    field = get_next_field(profile)
    if field is None:
        return None
    if field == "farmer_type":
        return "के तपाईंको खेतमा हाल कुनै बाली छ, कि रोप्ने योजना बनाउँदै हुनुहुन्छ?"

    q = FIELD_QUESTIONS.get(field)
    farmer_type = profile.get("farmer_type", "A")

    if isinstance(q, dict):
        # Per-type phrasing — always resolve with actual farmer_type
        return q.get(farmer_type, list(q.values())[0])
    return q


def build_remaining_fields_summary(profile: dict) -> str:
    """
    Return a short comma-separated list of fields still needed AFTER the next one.
    Python builds this; the LLM receives only the resolved string.
    """
    farmer_type = profile.get("farmer_type")
    if not farmer_type:
        return ""

    order = TYPE_A_FIELD_ORDER if farmer_type == "A" else TYPE_B_FIELD_ORDER
    missing = [f for f in order if not profile.get(f)]
    # Skip the very next field (already in the question)
    remaining = missing[1:] if len(missing) > 1 else []
    return ", ".join(remaining) if remaining else ""


def build_known_summary(profile: dict, user_name: str = "") -> str:
    """
    Build a concise Nepali-labelled summary of what we already know.
    Python formats this; the LLM receives a ready-made string.
    """
    labels = {
        "farmer_type":         "किसान प्रकार",
        "crop":                "बाली",
        "sowing_date":         "रोपाइँ मिति",
        "district":            "जिल्ला",
        "land_size_hectares":  "जग्गा (ha)",
        "land_size_raw":       "जग्गा (मूल)",
        "land_ownership":      "जग्गा स्वामित्व",
        "farming_month":       "रोप्ने महिना",
        "irrigation_type":     "सिंचाइ",
        "experience_years":    "अनुभव (वर्ष)",
        "farming_type":        "खेती प्रकार",
        "has_loan":            "ऋण",
    }
    lines = []
    if user_name:
        lines.append(f"नाम: {user_name}")
    for key, label in labels.items():
        val = profile.get(key)
        if val is not None and val != "":
            lines.append(f"{label}: {val}")
    return "\n".join(lines) if lines else "— अझै जानकारी संकलन भएको छैन।"


# ─────────────────────────────────────────────────────────────────────────────
# 5. POST-EXTRACTION NORMALISATION  (run AFTER LLM extracts raw strings)
# ─────────────────────────────────────────────────────────────────────────────

def normalise_extracted_profile(raw: dict) -> dict:
    """
    Takes the raw JSON extracted by the LLM and resolves every field that
    Python can resolve deterministically. Returns the cleaned profile update.

    Run this immediately after parsing the LLM's JSON response.
    Never ask the LLM to do these lookups — it hallucinates on edge cases.
    """
    from rules.unit_converter import convert_to_hectares, nepali_word_to_number
    from rules.nepali_date_converter import nepali_to_english_date

    out = dict(raw)

    # ── Crop normalisation ───────────────────────────────────────────────────
    if raw.get("crop"):
        resolved = normalise_crop(raw["crop"])
        if resolved:
            out["crop"] = resolved
        # else keep raw — unknown crop, let advisory layer handle

    # ── Farmer type (ensure always uppercase if present) ─────────────────────
    if raw.get("farmer_type"):
        out["farmer_type"] = str(raw["farmer_type"]).upper()

    # ── District normalisation ───────────────────────────────────────────────
    if raw.get("district"):
        resolved = normalise_district(raw["district"])
        if resolved:
            out["district"] = resolved.lower()

    

    # ── Nepali word numbers for experience ───────────────────────────────────
    exp = raw.get("experience_years")
    if isinstance(exp, str):
        # Try word → int ("paanch barsa" → 5)
        for word, num in NEPALI_NUMBER_WORDS.items():
            if word in exp.lower():
                out["experience_years"] = num
                break
        else:
            # Try parsing digit string
            digits = re.sub(r"[^\d]", "", exp)
            if digits:
                out["experience_years"] = int(digits)

    # ── Farming month → int ─────────────────────────────────────────────────
    month = raw.get("farming_month")
    if isinstance(month, str):
        resolved_month = NEPALI_MONTH_TO_INT.get(month.lower().strip())
        if resolved_month:
            out["farming_month"] = resolved_month

    # ── Land ownership normalisation ─────────────────────────────────────────
    ownership = raw.get("land_ownership", "")
    if ownership:
        lo = ownership.lower()
        if any(w in lo for w in ["owned", "own", "aafno", "aafkai", "hamro"]):
            out["land_ownership"] = "owned"
        elif any(w in lo for w in ["leased", "lease", "bhada", "rented"]):
            out["land_ownership"] = "leased"

    # ── Irrigation normalisation ─────────────────────────────────────────────
    irr = raw.get("irrigation_type", "")
    if irr:
        il = irr.lower()
        if any(w in il for w in ["barshat", "varsha", "rain", "rainfed"]):
            out["irrigation_type"] = "rainfed"
        elif any(w in il for w in ["drip", "thopa"]):
            out["irrigation_type"] = "drip"
        elif any(w in il for w in ["canal", "nahr", "nali", "khola", "nadi"]):
            out["irrigation_type"] = "canal"
        elif any(w in il for w in ["pump", "paani pump"]):
            out["irrigation_type"] = "pump"
        elif any(w in il for w in ["sprinkler"]):
            out["irrigation_type"] = "sprinkler"

    # ── Farming type normalisation ───────────────────────────────────────────
    ft = raw.get("farming_type", "")
    if ft:
        fl = ft.lower()
        has_organic  = any(w in fl for w in ["jaivik", "gobar", "compost", "organic"])
        has_chemical = any(w in fl for w in ["dap", "urea", "rasaynik", "chemical"])
        if has_organic and has_chemical:
            out["farming_type"] = "mixed"
        elif has_organic:
            out["farming_type"] = "organic"
        elif has_chemical:
            out["farming_type"] = "chemical"

    # ── has_loan: only True on explicit confirmation ─────────────────────────
    loan = raw.get("has_loan")
    if isinstance(loan, str):
        out["has_loan"] = loan.lower() in ("true", "yes", "cha", "chha", "छ")

    return out


# ─────────────────────────────────────────────────────────────────────────────
# 6. CONVERSATION MODE RESOLVER  (Python decides mode — not the LLM)
# ─────────────────────────────────────────────────────────────────────────────

def get_conversation_mode(
    profile: dict,
    is_first_message: bool = False,
    farmer_asked_question: bool = False,
) -> str:
    """
    Resolve the current conversation mode. Returned as a simple string so
    prompts.py can select the right (short) prompt template.

    Modes:
      "first_message"   — very first turn, no data yet
      "classify"        — need farmer type (crop planted or planning?)
      "collect"         — actively gathering profile fields
      "farmer_question" — farmer asked something mid-collection
      "advisory"        — all fields done, free-form Q&A
      "returning"       — returning user, skip intro
    """
    if is_first_message:
        return "first_message"

    farmer_type = profile.get("farmer_type")
    next_field  = get_next_field(profile)

    if farmer_type is None:
        return "classify"

    if next_field is None:
        return "advisory"

    # Returning farmer check: has crop + district but session is fresh
    is_returning = bool(
        profile.get("crop") and profile.get("district") and
        not profile.get("_session_greeted")
    )
    if is_returning and next_field not in ("crop", "farmer_type"):
        return "returning"

    if farmer_asked_question:
        return "farmer_question"

    return "collect"


# ─────────────────────────────────────────────────────────────────────────────
# 7. LANGUAGE RULES (single source — imported into prompts.py)
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_RULES = """\
LANGUAGE (mandatory): Reply in Nepali Devanagari only.
Understand any input language (Nepali, English, Romanized, Hindi).
Use Devanagari numerals: १ २ ३. Address farmer warmly: हजुर, राम्रो।"""

REPLY_FORMAT_RULES = """\
REPLY FORMAT (every turn):
1. React to what the farmer just said (1 sentence, specific).
2. If crop is known and a farming fact is available — share ONE fact naturally.
3. Ask EXACTLY ONE question (the one provided in NEXT QUESTION). Never two."""


# ─────────────────────────────────────────────────────────────────────────────
# 8. EXTRACTOR HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_current_expected_field(profile: dict) -> Optional[str]:
    """
    What field are we currently waiting for the farmer to answer?
    This is what we pass to the extractor — extract ONLY this field.
    Same as get_next_field() but named clearly for the extractor layer.
    """
    return get_next_field(profile)


def should_reclassify(profile: dict, farmer_msg: str) -> bool:
    """
    If farmer_type is set but farmer's reply contradicts it — re-check.
    e.g. was classified A but now says 'lagaune socheko'.

    Uses the fixed classify_farmer_type which does token-level matching,
    so false positives from partial word matches are prevented.
    """
    if not profile.get("farmer_type"):
        return False
    detected = classify_farmer_type(farmer_msg)
    return detected is not None and detected != profile.get("farmer_type")