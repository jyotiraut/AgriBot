# rules/field_validator.py
"""
Cleans and validates raw LLM-extracted fields before saving to DB.
Pure functions — no DB calls, no LLM calls.
"""

from rules.crop_normalizer import normalize_crop
from rules.nepali_date_converter import nepali_to_english_date

# Fields that are computed — never sent to LLM, always recalculated
COMPUTED_FIELDS = {
    "estimated_yield_kg",
    "estimated_income_npr",
    "income_price_per_kg",
    "income_yield_t_per_ha",
    "income_estimated_at",
}

# Fields stripped before sending existing profile to LLM
STRIP_FROM_LLM_INPUT = COMPUTED_FIELDS | {
    "_id", "user_id", "extracted_at", "extraction_version",
    "stage_progress", "credit_score", "risk_level",
    "score_explanation", "scored_at",
}

# Fields that should always be overwritten when LLM returns a new value
ALWAYS_OVERWRITE = {
    "extraction_confidence",
    "raw_notes",
    "land_size_raw",
    "crop",
    "location",
    "district",
    "zone",
    "season",
    "farming_month_name",
    "land_size_hectares",
    "farming_month",
    "farming_type",
    "irrigation_type",
    "land_ownership",
    "has_loan",
    "loan_amount",
    "experience_years",
    "annual_income_estimate",
    "owns_equipment",
    "uses_inputs_on_credit",
    "farmer_type",
    "sowing_date",
}

FIELD_TYPES = {
    # ── Core profile ──────────────────────────────────────────
    "crop":                   str,
    "land_size_raw":          str,
    "location":               str,
    "district":               str,
    "zone":                   str,
    "season":                 str,
    "farming_month_name":     str,
    "irrigation_type":        str,
    "farming_type":           str,
    "land_ownership":         str,
    "raw_notes":              str,
    "farmer_type":            str,
    "sowing_date":            str,   # stored as "YYYY-MM-DD" (AD) after conversion
    # ── Numeric ───────────────────────────────────────────────
    "land_size_hectares":     float,
    "loan_amount":            float,
    "annual_income_estimate": float,
    "extraction_confidence":  float,
    "farming_month":          int,
    "experience_years":       int,
    # ── Boolean ───────────────────────────────────────────────
    "has_loan":               bool,
    "owns_equipment":         bool,
    "uses_inputs_on_credit":  bool,
}

# Maximum allowed experience years — anything above is capped
MAX_EXPERIENCE_YEARS = 25


# ── Functions ──────────────────────────────────────────────────

def _cap_experience(value: int) -> int:
    """Cap experience_years to MAX_EXPERIENCE_YEARS."""
    return min(int(value), MAX_EXPERIENCE_YEARS)


def clean_and_type(extracted: dict) -> dict:
    """
    Remove nulls, enforce correct types, validate ranges.
    Normalizes crop name, converts sowing_date to AD ISO format,
    and keeps location ↔ district in sync.
    """
    cleaned = {}

    for field, expected_type in FIELD_TYPES.items():
        val = extracted.get(field)
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        try:
            cleaned[field] = expected_type(val)
        except (ValueError, TypeError):
            continue

    # Normalize crop to singular lowercase
    if "crop" in cleaned:
        cleaned["crop"] = normalize_crop(cleaned["crop"])

    # Convert sowing_date from Nepali BS to English AD ISO string
    if "sowing_date" in cleaned:
        cleaned["sowing_date"] = nepali_to_english_date(cleaned["sowing_date"])

    # Keep location ↔ district in sync
    if "location" in cleaned:
        cleaned["location"] = cleaned["location"].lower()
        cleaned["district"]  = cleaned["location"]
    elif "district" in cleaned:
        cleaned["district"] = cleaned["district"].lower()
        cleaned["location"]  = cleaned["district"]

    # Validate farming_month range
    if "farming_month" in cleaned:
        if not (1 <= cleaned["farming_month"] <= 12):
            del cleaned["farming_month"]

    # Cap experience_years at MAX_EXPERIENCE_YEARS
    if "experience_years" in cleaned:
        cleaned["experience_years"] = _cap_experience(cleaned["experience_years"])

    return cleaned


def merge_profiles(existing: dict, new_fields: dict) -> dict:
    """
    Merge new extracted fields into existing profile.
    - ALWAYS_OVERWRITE fields → always replaced with new value
    - All other fields        → only filled if currently None
    - COMPUTED_FIELDS         → never touched here
    """
    merged = dict(existing)

    for field, new_val in new_fields.items():
        if new_val is None:
            continue
        if field in COMPUTED_FIELDS:
            continue
        if field in ALWAYS_OVERWRITE:
            merged[field] = new_val
        elif existing.get(field) is None:
            merged[field] = new_val

    # Cap experience_years at MAX_EXPERIENCE_YEARS after merge
    if "experience_years" in merged:
        merged["experience_years"] = _cap_experience(merged["experience_years"])

    # Keep location ↔ district in sync after merge
    if "location" in merged and "district" not in merged:
        merged["district"] = merged["location"]
    elif "district" in merged and "location" not in merged:
        merged["location"] = merged["district"]

    return merged