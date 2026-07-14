# core/profile_extractor.py
import json
from datetime import datetime

from langchain_groq import ChatGroq  # type: ignore
from langchain_core.messages import SystemMessage, HumanMessage

from config import get_settings
settings = get_settings()

from db import crud

from rules.crop_normalizer   import normalize_crop
from rules.field_validator   import clean_and_type, merge_profiles, STRIP_FROM_LLM_INPUT, COMPUTED_FIELDS
from rules.income_calculator import calculate_income, can_estimate_income
from rules.zone_classifier   import classify_zone, month_to_season, month_to_name


# ══════════════════════════════════════════════════════════════
# LLM
# ══════════════════════════════════════════════════════════════

_llm = ChatGroq(
    model=settings.llm_model,
    temperature=0.0,
    api_key=settings.GROQ_API_KEY,
)

FULL_EXTRACTION_THRESHOLD = 10

# Approximate planting → harvest duration (months) per crop, for estimating the
# selling month used in price lookup. Falls back to DEFAULT_GROWING_MONTHS.
DEFAULT_GROWING_MONTHS = 4
CROP_GROWING_MONTHS = {
    "potato":      3,
    "tomato":      3,
    "cauliflower": 3,
    "cabbage":     3,
    "maize":       4,
    "paddy":       4,
    "wheat":       5,
    "mustard":     4,
    "onion":       5,
    "garlic":      6,
    "ginger":      8,
    "sugarcane":   12,
    "lentil":      4,
    "millet":      4,
    "soybean":     4,
    "cardamom":    10,
}


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _format_turns(turns: list[dict]) -> str:
    lines = []
    for t in turns:
        lines.append("Farmer: " + t["question"])
        lines.append("Advisor: " + t["answer"])
        lines.append("")
    return "\n".join(lines)


def _parse_json(raw: str) -> dict:
    import re
    clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError("LLM returned invalid JSON: " + str(e) + "\nRaw:\n" + raw)


def _derive_zone_and_season(profile: dict) -> dict:
    """
    Derive and return zone, season, and farming_month_name from profile data.
    Only sets a field if the source data is present and the field is not already set,
    so manually provided values are never overwritten.

    - zone             : derived from district (or location as fallback) via classify_zone()
    - season           : derived from farming_month integer via month_to_season()
    - farming_month_name: Nepali month name string derived from farming_month integer
    """
    updates = {}

    # ── Zone from district / location ────────────────────────────────────────
    if not profile.get("zone"):
        district = profile.get("district") or profile.get("location")
        if district:
            zone_enum = classify_zone(district)       # Zone enum (TERAI / HILLS / MOUNTAINS)
            updates["zone"] = zone_enum.value         # saves as "terai" / "hills" / "mountains"

    # ── Season + month name from farming_month integer ───────────────────────
    month = profile.get("farming_month")
    if month:
        if not profile.get("season"):
            season = month_to_season(month)
            if season:
                updates["season"] = season            # "Kharif" | "Rabi" | "Spring"

        if not profile.get("farming_month_name"):
            month_name = month_to_name(month)
            if month_name:
                updates["farming_month_name"] = month_name   # e.g. "Shrawan"

    return updates


# ══════════════════════════════════════════════════════════════
# INCOME ESTIMATION
# ══════════════════════════════════════════════════════════════

async def estimate_income(profile: dict) -> dict | None:
    can_estimate, missing = can_estimate_income(profile)
    if not can_estimate:
        print("⏭️  Income estimation skipped — missing: " + ", ".join(missing))
        return None

    crop_lower     = normalize_crop(profile["crop"])
    district_lower = (profile.get("district") or profile.get("location")).lower()
    # farming_month is the planting month. Different crops mature at different
    # rates, so the harvest/selling month = planting month + crop-specific
    # growing duration (falls back to 4 months for unknown crops).
    planting_month = profile["farming_month"]
    months_to_harvest = CROP_GROWING_MONTHS.get(crop_lower, DEFAULT_GROWING_MONTHS)
    harvest_month  = ((planting_month - 1 + months_to_harvest) % 12) + 1
    farming_month  = harvest_month
    land_size_ha   = profile["land_size_hectares"]

    try:
        yield_record = await crud.yield_data_get(district_lower)
        if not yield_record:
            print("⚠️  No yield_data for district: " + district_lower)
            return None

        yield_t_per_ha = yield_record.get(crop_lower)
        if yield_t_per_ha is None:
            print(
                "⚠️  No yield for crop '" + crop_lower
                + "' in '" + district_lower + "'"
                + " | available keys: "
                + str([k for k in yield_record if k not in ("_id", "district")])
            )
            return None

        price_record = await crud.price_data_get(crop_lower, farming_month)
        if not price_record:
            print("⚠️  No price_data for crop '" + crop_lower + "' month " + str(farming_month))
            return None

        avg_price_per_kg = price_record.get("avg")
        if avg_price_per_kg is None:
            print("⚠️  price_data has no 'avg' for crop '" + crop_lower + "' month " + str(farming_month))
            return None

        # ── Pure calculation from rules/ ──────────────────────
        result = calculate_income(yield_t_per_ha, land_size_ha, avg_price_per_kg)
        result["income_estimated_at"] = datetime.utcnow()

        print(
            "💰 Income estimate"
            + " | crop: "       + crop_lower
            + " | district: "   + district_lower
            + " | month: "      + str(farming_month)
            + " | land: "       + str(land_size_ha) + " ha"
            + " | harvest_month: " + str(farming_month)
            + " | yield: "      + str(result["estimated_yield_kg"]) + " kg"
            + " | income: NPR " + str(result["estimated_income_npr"])
        )

        return result

    except Exception as e:
        print("❌ Income estimation failed: " + str(e))
        return None


# ══════════════════════════════════════════════════════════════
# PUBLIC FUNCTIONS
# ══════════════════════════════════════════════════════════════

async def extract_full(user_id: str) -> dict:
    turns = await crud.chat_history_pairs(user_id, limit=500)

    if not turns:
        return {"message": "No conversation history found", "user_id": user_id}

    from rag.prompts import EXTRACTION_SYSTEM_PROMPT
    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(
            content="Extract farmer profile from this conversation:\n\n"
            + _format_turns(turns)
        ),
    ]

    response  = _llm.invoke(messages)
    extracted = _parse_json(response.content)
    cleaned   = clean_and_type(extracted)          # ← from rules/field_validator

    if not cleaned:
        return {"message": "Nothing extractable found yet", "user_id": user_id}

    # ── Auto-derive zone / season / farming_month_name ───────────────────────
    derived = _derive_zone_and_season(cleaned)
    if derived:
        cleaned.update(derived)
        print("🗺️  Derived fields: " + str(derived))
    # ─────────────────────────────────────────────────────────────────────────

    income_fields = await estimate_income(cleaned)
    if income_fields:
        cleaned.update(income_fields)

    cleaned["extracted_at"]       = datetime.utcnow()
    cleaned["extraction_version"] = 1

    saved = await crud.profile_upsert(user_id, cleaned)

    print(
        "✅ Full extraction"
        + " | user: "        + user_id
        + " | crop: "        + str(cleaned.get("crop"))
        + " | confidence: "  + str(cleaned.get("extraction_confidence", 0))
        + " | land: "        + str(cleaned.get("land_size_hectares")) + " ha"
        + " | district: "    + str(cleaned.get("district"))
        + " | zone: "        + str(cleaned.get("zone"))
        + " | season: "      + str(cleaned.get("season"))
        + " | month: "       + str(cleaned.get("farming_month"))
        + " | month_name: "  + str(cleaned.get("farming_month_name"))
        + " | income_npr: "  + str(cleaned.get("estimated_income_npr"))
    )

    return saved


async def extract_incremental(user_id: str, since: datetime) -> dict:
    new_turns = await crud.chat_history_pairs_since(user_id, since)

    if not new_turns:
        return await crud.profile_get(user_id) or {}

    existing_profile = await crud.profile_get(user_id) or {}

    existing_clean = {
        k: v for k, v in existing_profile.items()
        if k not in STRIP_FROM_LLM_INPUT          # ← from rules/field_validator
    }

    from rag.prompts import INCREMENTAL_SYSTEM_PROMPT
    messages = [
        SystemMessage(content=INCREMENTAL_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                "EXISTING PROFILE:\n"
                + json.dumps(existing_clean, default=str, indent=2)
                + "\n\nNEW TURNS:\n"
                + _format_turns(new_turns)
                + "\n\nReturn the updated profile JSON."
            )
        ),
    ]

    response  = _llm.invoke(messages)
    extracted = _parse_json(response.content)
    new_clean = clean_and_type(extracted)          # ← from rules/field_validator

    if not new_clean:
        return existing_profile

    merged = merge_profiles(existing_clean, new_clean)  # ← from rules/field_validator

    # ── Auto-derive zone / season / farming_month_name ───────────────────────
    derived = _derive_zone_and_season(merged)
    if derived:
        merged.update(derived)
        print("🗺️  Derived fields: " + str(derived))
    # ─────────────────────────────────────────────────────────────────────────

    income_fields = await estimate_income(merged)
    if income_fields:
        merged.update(income_fields)

    merged["extracted_at"] = datetime.utcnow()
    saved = await crud.profile_upsert(user_id, merged)

    print(
        "✅ Incremental extraction"
        + " | user: "       + user_id
        + " | crop: "       + str(merged.get("crop"))
        + " | district: "   + str(merged.get("district"))
        + " | zone: "       + str(merged.get("zone"))
        + " | season: "     + str(merged.get("season"))
        + " | month_name: " + str(merged.get("farming_month_name"))
        + " | new turns: "  + str(len(new_turns))
        + " | month: "      + str(merged.get("farming_month"))
        + " | income_npr: " + str(merged.get("estimated_income_npr"))
    )

    return saved


async def recalculate_income(user_id: str) -> dict:
    profile = await crud.profile_get(user_id)
    if not profile:
        return {"error": "Profile not found for user_id: " + user_id}

    updates = {}

    # ── Normalize crop name ───────────────────────────────────────────────────
    existing_crop = profile.get("crop")
    if existing_crop:
        normalized = normalize_crop(existing_crop)  # ← from rules/crop_normalizer
        if normalized != existing_crop:
            print("🔧 Normalizing crop: '" + existing_crop + "' → '" + normalized + "'")
            updates["crop"] = normalized
            profile["crop"] = normalized

    # ── Backfill district ↔ location ─────────────────────────────────────────
    if profile.get("location") and not profile.get("district"):
        updates["district"] = profile["location"].lower()
        profile["district"] = updates["district"]
        print("🔧 Backfilling district from location: " + updates["district"])
    elif profile.get("district") and not profile.get("location"):
        updates["location"] = profile["district"].lower()
        profile["location"] = updates["location"]
        print("🔧 Backfilling location from district: " + updates["location"])

    # ── Re-derive zone / season / month name ─────────────────────────────────
    # Run after district backfill so classify_zone() has the best possible input
    derived = _derive_zone_and_season(profile)
    if derived:
        updates.update(derived)
        profile.update(derived)
        print("🗺️  Derived fields: " + str(derived))
    # ─────────────────────────────────────────────────────────────────────────

    if updates:
        await crud.profile_upsert(user_id, updates)

    income_fields = await estimate_income(profile)
    if not income_fields:
        return {
            "error": (
                "Cannot estimate income — need crop, district, "
                "land_size_hectares, and farming_month to all be present."
            ),
            "profile_has": {
                "crop":               profile.get("crop"),
                "district":           profile.get("district"),
                "location":           profile.get("location"),
                "land_size_hectares": profile.get("land_size_hectares"),
                "farming_month":      profile.get("farming_month"),
                "zone":               profile.get("zone"),
                "season":             profile.get("season"),
                "farming_month_name": profile.get("farming_month_name"),
            },
        }

    income_fields["income_estimated_at"] = datetime.utcnow()
    saved = await crud.profile_upsert(user_id, income_fields)

    print(
        "💰 Income recalculated (backfill)"
        + " | user: "       + user_id
        + " | crop: "       + str(profile.get("crop"))
        + " | district: "   + str(profile.get("district"))
        + " | zone: "       + str(profile.get("zone"))
        + " | season: "     + str(profile.get("season"))
        + " | month_name: " + str(profile.get("farming_month_name"))
        + " | income_npr: " + str(income_fields.get("estimated_income_npr"))
    )

    return saved


async def trigger_on_login(user_id: str) -> None:
    try:
        existing          = await crud.profile_get(user_id)
        last_extracted_at = existing.get("extracted_at") if existing else None

        if not existing or not last_extracted_at:
            print("🔄 First extraction for " + user_id)
            await extract_full(user_id)
            return

        new_turns = await crud.chat_history_pairs_since(user_id, last_extracted_at)
        new_count = len(new_turns)

        if new_count == 0:
            if existing.get("estimated_income_npr") is None:
                print("💰 Backfilling income for up-to-date profile: " + user_id)
                await recalculate_income(user_id)
            elif any(
                existing.get(f) is None
                for f in ("zone", "season", "farming_month_name")
            ):
                # Profile is income-complete but missing derived geo/season fields
                print("🗺️  Backfilling zone/season for up-to-date profile: " + user_id)
                await recalculate_income(user_id)
            else:
                print("ℹ️  Profile up to date for " + user_id)
            return
        elif new_count >= FULL_EXTRACTION_THRESHOLD:
            print("🔄 " + str(new_count) + " new turns — full extraction for " + user_id)
            await extract_full(user_id)
        else:
            print("🔄 " + str(new_count) + " new turns — incremental for " + user_id)
            await extract_incremental(user_id, since=last_extracted_at)

    except Exception as e:
        print("❌ Extraction failed for " + user_id + ": " + str(e))