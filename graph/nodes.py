"""
KrishiMitra - LangGraph Nodes (UNIFIED)
Merged from both team versions. Each function is a pure node: receives state,
returns a partial state update.

Node execution order (see workflow.py for the graph):
  extract_profile_node
    └─► normalise_profile_node        (alias/unit/district normalisation)
    └─► convert_date_node             (BS → AD)
    └─► convert_units_node            (ropani/bigha → hectares)
    └─► classify_zone_node            (district → Terai/Hills/Mountains)
    └─► calculate_income_node         (yield × price → estimated income)
    └─► resolve_conversation_mode_node (mode / next-question / crop-tip)
    └─► route_farmer
          ├─[Type A]──► calculate_das_gdd_node
          │               → apply_safety_guardrails_node
          │               → build_rule_output_node
          │               → retrieve_rag_context_node
          │               → synthesize_llm_node
          └─[Type B]──► check_crop_suitability_node
                          → build_rule_output_node
                          → retrieve_rag_context_node
                          → synthesize_llm_node
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_settings
from engine.crop_recommender import get_current_season, predict_crops_with_fallback
from graph.state import KrishiMitraState
from rag.prompts import (
    KRISHIMITRA_SYSTEM_PROMPT,
    KRISHIMITRA_USER_PROMPT,
    build_user_message,          # Doc-1 style — used in synthesize_llm_node
)
from rag.retriever import get_retriever
from rules.crop_suitability import CropOption, get_suitable_crops
from rules.das_gdd import (
    calculate_das,
    estimate_gdd,
    get_growth_stage,
    get_zone_temperature_defaults,
)
from rules.safety_guardrails import SafetyFlag, run_safety_checks
from rules.zone_classifier import classify_zone, get_zone_characteristics
from schemas.farmer import IrrigationAccess, Season, Zone

logger   = logging.getLogger(__name__)
settings = get_settings()


# ═════════════════════════════════════════════════════════════════════════════
# UTILITY NODE 1 — Convert Nepali (BS) sowing date → AD ISO string
# ═════════════════════════════════════════════════════════════════════════════

def convert_date_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Convert raw sowing_date from Bikram Sambat (BS) to an AD ISO string.

    Reads:  state["sowing_date"]          — any BS format or already-AD string
    Writes: state["sowing_date"]          — always "YYYY-MM-DD" (AD)
            state["sowing_date_original"] — original raw value, kept for display

    Python does the conversion; the LLM never sees raw BS strings.
    """
    from rules.nepali_date_converter import nepali_to_english_date

    raw = state.get("sowing_date")
    if not raw:
        return state

    converted = nepali_to_english_date(raw)
    logger.info("Date conversion: '%s' → '%s'", raw, converted)

    return {
        **state,
        "sowing_date":          converted,
        "sowing_date_original": raw,
    }


# ═════════════════════════════════════════════════════════════════════════════
# UTILITY NODE 2 — Convert land area → hectares
# ═════════════════════════════════════════════════════════════════════════════

def convert_units_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Convert land_size from any Nepali unit (ropani, bigha, kattha …) to hectares.

    Reads:  state["land_size"]           — numeric value
            state["land_size_unit"]      — unit string
    Writes: state["land_size_hectares"]  — float, land in hectares

    No-ops when land_size_hectares is already populated or land_size is absent.
    """
    from rules.unit_converter import convert_to_hectares

    if state.get("land_size_hectares"):
        return state

    land_size = state.get("land_size")
    if land_size is None:
        return state

    try:
        land_size = float(land_size)
    except (TypeError, ValueError):
        logger.warning("convert_units_node: cannot parse land_size='%s'", land_size)
        return state

    land_unit = state.get("land_size_unit", "hectare")
    hectares  = convert_to_hectares(land_size, land_unit)

    if hectares is None:
        logger.warning(
            "convert_units_node: unknown unit '%s', treating value as hectares", land_unit
        )
        hectares = land_size

    logger.info("Unit conversion: %.4f %s → %.4f ha", land_size, land_unit, hectares)
    return {**state, "land_size_hectares": hectares}


# ═════════════════════════════════════════════════════════════════════════════
# UTILITY NODE 3 — Classify zone + enrich characteristics
# ═════════════════════════════════════════════════════════════════════════════

def classify_zone_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Classify the farmer's district into Terai / Hills / Mountains and enrich
    state with zone agronomic characteristics.
    """
    district        = state.get("district", "")
    zone: Zone      = classify_zone(district)
    characteristics = get_zone_characteristics(zone)

    logger.info("Zone classified: district=%s → zone=%s", district, zone.value)
    return {
        **state,
        "zone":                 zone.value,
        "zone_characteristics": characteristics,
    }


# ═════════════════════════════════════════════════════════════════════════════
# UTILITY NODE 4 — Estimate farmer income
# ═════════════════════════════════════════════════════════════════════════════

def calculate_income_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Estimate income from crop × land size × yield tables × market price.
    All arithmetic stays in Python; the LLM only receives the finished numbers.

    Writes: state["income_estimate"] — dict with can_estimate, estimated values,
                                       or missing_fields when data is unavailable.
    """
    from rules.income_calculator import calculate_income, can_estimate_income

    profile = {
        "crop":               state.get("crop"),
        "land_size_hectares": state.get("land_size_hectares"),
        "district":           state.get("district"),
        "farming_month":      state.get("farming_month"),
    }

    can_estimate, missing = can_estimate_income(profile)
    if not can_estimate:
        logger.info("Income estimate skipped — missing fields: %s", missing)
        return {
            **state,
            "income_estimate": {"can_estimate": False, "missing_fields": missing},
        }

    yield_t_per_ha   = state.get("yield_t_per_ha")
    avg_price_per_kg = state.get("avg_price_per_kg")

    # Yield/price come from the async DB-backed estimator (core.profile_extractor
    # .estimate_income), which the /chat background task runs and persists onto
    # the profile. If they are not already in state we skip here rather than doing
    # a sync-over-async DB call inside this synchronous graph node.
    if not yield_t_per_ha or not avg_price_per_kg:
        logger.info("Income calc: yield/price not in state — skipping estimate.")
        return {
            **state,
            "income_estimate": {
                "can_estimate":   False,
                "missing_fields": ["yield_data", "price_data"],
            },
        }

    result = calculate_income(
        yield_t_per_ha=yield_t_per_ha,
        land_size_ha=profile["land_size_hectares"],
        avg_price_per_kg=avg_price_per_kg,
    )
    result.update({"can_estimate": True, "missing_fields": []})

    logger.info(
        "Income estimated: crop=%s land=%.4f ha yield=%.2f t/ha → NPR %.2f",
        profile["crop"],
        profile["land_size_hectares"],
        yield_t_per_ha,
        result["estimated_income_npr"],
    )

    return {
        **state,
        "income_estimate":  result,
        "yield_t_per_ha":   yield_t_per_ha,
        "avg_price_per_kg": avg_price_per_kg,
    }


# ═════════════════════════════════════════════════════════════════════════════
# UTILITY NODE 5 — Resolve conversation mode
# ═════════════════════════════════════════════════════════════════════════════

def resolve_conversation_mode_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Determine what the assistant should do next (collect info, answer a question,
    give an advisory, etc.) and pre-fetch a RAG crop tip if the crop is known.

    Python owns all these decisions; the LLM only uses the resulting fields.
    """
    from rag.retriever import get_retriever
    from rules.conversation_rules import (
        build_known_summary,
        build_remaining_fields_summary,
        get_conversation_mode,
        get_next_field,
        get_next_question,
    )
    from rules.rag_context_fetcher import get_crop_tip

    # Build a merged profile view from state
    profile: Dict[str, Any] = state.get("farmer_profile") or {}
    for key in (
        "farmer_type", "crop", "district", "sowing_date", "land_size_hectares",
        "land_ownership", "farming_month", "irrigation_access",
        "experience_years", "farming_type", "has_loan",
    ):
        if state.get(key) and not profile.get(key):
            profile[key] = state[key]

    is_first  = not state.get("conversation_started", False)
    farmer_q  = state.get("farmer_asked_question", False)

    mode          = get_conversation_mode(profile, is_first, farmer_q)
    next_field    = get_next_field(profile)
    next_question = get_next_question(profile)
    known_summary = build_known_summary(profile, state.get("user_name", ""))
    remaining     = build_remaining_fields_summary(profile)

    # Pre-fetch a crop tip from RAG (Python does this so LLM just weaves it in)
    crop_tip = ""
    if profile.get("crop"):
        try:
            crop_tip = get_crop_tip(
                retriever=get_retriever(),
                crop=profile.get("crop"),
                farmer_type=profile.get("farmer_type"),
                district=profile.get("district"),
                month=profile.get("farming_month"),
            )
        except Exception as exc:
            logger.warning("crop tip fetch failed: %s", exc)

    logger.info("Conversation mode: %s | next_field: %s", mode, next_field)
    logger.debug("crop_tip fetched for crop=%s: '%s'", profile.get("crop"), crop_tip)

    return {
        **state,
        "conversation_mode":    mode,
        "next_field":           next_field,
        "next_question":        next_question,
        "known_summary":        known_summary,
        "remaining_fields":     remaining,
        "conversation_started": True,
        "farmer_profile":       profile,
        "crop_tip":             crop_tip,
    }



# ═════════════════════════════════════════════════════════════════════════════
# NODE 0 — Extract / Update Farmer Profile
# ═════════════════════════════════════════════════════════════════════════════

async def extract_profile_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Wraps core/profile_extractor.py into a LangGraph node.

    • First message  → full extraction from scratch (extract_full)
    • Subsequent     → incremental extraction from new turns only (extract_incremental)

    Merges extracted fields into flat state so downstream nodes can read them
    directly. Never overwrites fields that are already explicitly set in state.
    """
    from core.profile_extractor import extract_full, extract_incremental

    user_id = state.get("user_id")
    if not user_id:
        logger.warning("extract_profile_node: no user_id in state, skipping.")
        return state

    last_extracted_at = state.get("last_extracted_at")

    try:
        if not last_extracted_at:
            logger.info("Profile extraction: full run for user=%s", user_id)
            profile = await extract_full(user_id)
        else:
            since = datetime.fromisoformat(last_extracted_at)
            logger.info(
                "Profile extraction: incremental for user=%s since=%s", user_id, last_extracted_at
            )
            profile = await extract_incremental(user_id, since=since)
    except Exception as exc:
        logger.error("Profile extraction failed for user=%s: %s", user_id, exc)
        return state

    if not profile:
        return state

    updates: Dict[str, Any] = {
        "farmer_profile":     profile,
        "last_extracted_at":  datetime.utcnow().isoformat(),
        "profile_confidence": profile.get("extraction_confidence", 0.0),
    }

    # Map extracted profile fields → flat state keys (fill gaps, never overwrite)
    field_map = {
        "district":        "district",
        "crop":            "crop",
        "irrigation_type": "irrigation_access",
        "farming_month":   "farming_month",
        "land_size":       "land_size",
        "land_size_unit":  "land_size_unit",
    }
    for profile_key, state_key in field_map.items():
        if not state.get(state_key) and profile.get(profile_key):
            updates[state_key] = profile[profile_key]

    # Infer farmer_type when not already set
    if not state.get("farmer_type"):
        if profile.get("crop") and profile.get("farming_month"):
            updates["farmer_type"] = "A"   # active crop → advisory mode
        elif profile.get("district"):
            updates["farmer_type"] = "B"   # location only → planning mode

    logger.info(
        "Profile merged: user=%s crop=%s district=%s confidence=%.2f",
        user_id,
        profile.get("crop"),
        profile.get("district"),
        profile.get("extraction_confidence", 0.0),
    )

    return {**state, **updates}


# ═════════════════════════════════════════════════════════════════════════════
# NODE — Normalise Extracted Profile
# ═════════════════════════════════════════════════════════════════════════════

def normalise_profile_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Run normalise_extracted_profile() on the raw LLM extraction result.

    Resolves crop aliases, district name variants, land units, irrigation
    strings, etc. Must run BEFORE convert_date_node / convert_units_node /
    classify_zone_node so those nodes receive already-normalised values.
    """
    from rules.conversation_rules import normalise_extracted_profile

    raw_extraction = state.get("llm_extracted_profile") or {}
    if not raw_extraction:
        return state

    cleaned = normalise_extracted_profile(raw_extraction)

    field_map = {
        "crop":               "crop",
        "farmer_type":        "farmer_type",
        "district":           "district",
        "land_size_hectares": "land_size_hectares",
        "land_size_raw":      "land_size",
        "land_size_unit":     "land_size_unit",
        "sowing_date":        "sowing_date",
        "irrigation_type":    "irrigation_access",
        "farming_month":      "farming_month",
        "experience_years":   "experience_years",
        "farming_type":       "farming_type",
        "has_loan":           "has_loan",
    }

    updates: Dict[str, Any] = {}
    for cleaned_key, state_key in field_map.items():
        if cleaned.get(cleaned_key) is not None and not state.get(state_key):
            updates[state_key] = cleaned[cleaned_key]

    logger.info("Profile normalised: updated keys = %s", list(updates.keys()))
    return {**state, **updates}


# ═════════════════════════════════════════════════════════════════════════════
# NODE 1 — Route Farmer (validation / sanity-check)
# ═════════════════════════════════════════════════════════════════════════════

def route_farmer(state: KrishiMitraState) -> KrishiMitraState:
    """
    Validate required fields and normalise farmer_type.
    Acts as the entry / sanity-check node after all utility nodes have run.
    Returns an error key (never raises) so the graph can route gracefully.
    """
    farmer_type = state.get("farmer_type", "").upper()

    if farmer_type not in ("A", "B"):
        return {**state, "error": f"Unknown farmer_type: '{farmer_type}'. Must be 'A' or 'B'."}

    if farmer_type == "A":
        if not state.get("crop"):
            return {**state, "error": "Type A farmer must provide 'crop'."}
        if not state.get("sowing_date"):
            return {**state, "error": "Type A farmer must provide 'sowing_date'."}

    if farmer_type == "B":
        if not state.get("season"):
            return {**state, "error": "Type B farmer must provide 'season'."}

    return {
        **state,
        "farmer_type":        farmer_type,
        "language":           state.get("language", "nepali"),
        "safety_flags":       state.get("safety_flags", []),
        "has_critical_flags": False,
        "error":              None,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 3A — Calculate DAS / GDD  (Type A only)
# ═════════════════════════════════════════════════════════════════════════════

def calculate_das_gdd_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    For active farmers (Type A):
    • Compute Days After Sowing (DAS) from sowing_date (always AD ISO after
      convert_date_node) to today.
    • Estimate Growing Degree Days (GDD) using zone climatological averages.
    • Resolve current growth stage and days-to-harvest.
    """
    sowing_date = state.get("sowing_date")
    crop        = state.get("crop", "")
    zone_name   = state.get("zone", "Hills")

    if isinstance(sowing_date, str):
        sowing_date = date.fromisoformat(sowing_date)

    das   = calculate_das(sowing_date)
    temps = get_zone_temperature_defaults(zone_name)
    gdd   = estimate_gdd(
        sowing_date,
        avg_tmax=temps["avg_tmax"],
        avg_tmin=temps["avg_tmin"],
        base_temp=settings.base_temp_celsius,
    )
    growth_stage    = get_growth_stage(crop, das, gdd)
    days_to_harvest = max(0, growth_stage.das_end - das)

    logger.info(
        "DAS/GDD: crop=%s das=%d gdd=%.1f stage=%s dth=%d",
        crop, das, gdd, growth_stage.name, days_to_harvest,
    )

    return {
        **state,
        "das":             das,
        "gdd":             gdd,
        "growth_stage":    growth_stage,
        "days_to_harvest": days_to_harvest,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 3B — Crop Suitability  (Type B only)
# ═════════════════════════════════════════════════════════════════════════════

def check_crop_suitability_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    For planning farmers (Type B):
    Retrieve ranked crop options from the ML model with a rule-based fallback.
    Auto-determines current season when the farmer hasn't specified one.
    """
    district      = state.get("district", "Unknown")
    zone_str      = state.get("zone", "Hills")
    season_str    = state.get("season") or get_current_season(zone=zone_str)
    irrigation_str = state.get("irrigation_access", "Rainfed")

    try:
        zone       = Zone(zone_str)
        season     = Season(season_str)
        irrigation = IrrigationAccess(irrigation_str)
    except ValueError as exc:
        return {**state, "error": str(exc)}

    ml_results = predict_crops_with_fallback(
        district=district,
        season=season_str,
        zone=zone_str,
        irrigation_access=irrigation_str,
        top_n=5,
    )

    crops: List[CropOption] = [
        CropOption(
            name=r["crop"],
            season=season,
            suitability_score=r["confidence"],
            input_cost="medium",
            market_value="medium",
            notes=f"Recommended via {r['source']}. Confidence: {r['confidence']}%",
            variety_suggestions=[],
        )
        for r in ml_results
    ]

    logger.info(
        "Crop suitability: district=%s zone=%s season=%s → %d options",
        district, zone_str, season_str, len(crops),
    )

    return {
        **state,
        "season":            season_str,
        "recommended_crops": crops,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 4 — Apply Safety Guardrails
# ═════════════════════════════════════════════════════════════════════════════

def apply_safety_guardrails_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Run all fertilizer and pesticide safety checks.
    Appends SafetyFlag entries to state; marks has_critical_flags when any
    CRITICAL flag is present.
    """
    crop            = state.get("crop", "")
    das             = state.get("das", 0)
    last_fertilizer = state.get("last_fertilizer") or {}
    last_pesticide  = state.get("last_pesticide") or {}

    flags: List[SafetyFlag] = run_safety_checks(
        crop=crop,
        das=das,
        fertilizer_name=last_fertilizer.get("name"),
        fertilizer_kg_per_ha=last_fertilizer.get("kg_per_ha"),
        pesticide_name=last_pesticide.get("name"),
        pesticide_ml_per_ha=last_pesticide.get("ml_per_ha"),
    )

    all_flags    = state.get("safety_flags", []) + flags
    has_critical = any(f.severity == "CRITICAL" for f in all_flags)

    logger.info(
        "Safety check: crop=%s das=%d flags=%d critical=%s",
        crop, das, len(all_flags), has_critical,
    )

    return {**state, "safety_flags": all_flags, "has_critical_flags": has_critical}


# ═════════════════════════════════════════════════════════════════════════════
# NODE 5 — Build Rule Output
# ═════════════════════════════════════════════════════════════════════════════

def build_rule_output_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Package all Python-computed values into a single rule_output dict that the
    LLM uses as grounding context.

    All numerics (DAS, GDD, hectares, income, zone) are already computed by
    upstream nodes. This node only assembles them — the LLM must NEVER
    re-derive these values; it only formats and explains them.
    """
    farmer_type = state.get("farmer_type")

    # ── Utility computation results (pre-computed by Python nodes) ────────────
    income_estimate      = state.get("income_estimate") or {}
    sowing_date_original = state.get("sowing_date_original")
    sowing_date_ad       = state.get("sowing_date")
    land_size_hectares   = state.get("land_size_hectares")

    utility_context: Dict[str, Any] = {
        "sowing_date_original": sowing_date_original,
        "sowing_date_ad":       sowing_date_ad,
        "land_size_raw":        state.get("land_size"),
        "land_size_unit":       state.get("land_size_unit"),
        "land_size_hectares":   land_size_hectares,
        "income_estimate":      income_estimate if income_estimate.get("can_estimate") else None,
        "income_missing_fields": income_estimate.get("missing_fields", []),
    }

    output: Dict[str, Any] = {
        "farmer_type": farmer_type,
        "zone":        state.get("zone"),
        "zone_notes":  (state.get("zone_characteristics") or {}).get("notes", ""),
        "utility":     utility_context,
    }

    if farmer_type == "A":
        growth_stage  = state.get("growth_stage")
        weather       = state.get("weather_data") or {}
        weather_alert = (
            "ALERT: Heavy rain expected in the next 3 days. "
            "Delay fertilizer application to avoid runoff."
            if weather.get("heavy_rain_upcoming")
            else ""
        )

        output.update({
            "crop":                   state.get("crop"),
            "variety":                state.get("variety"),
            "das":                    state.get("das"),
            "gdd":                    state.get("gdd"),
            "growth_stage_name":      growth_stage.name if growth_stage else "Unknown",
            "key_activities":         growth_stage.key_activities if growth_stage else [],
            "advisory_focus":         growth_stage.advisory_focus if growth_stage else "",
            "observed_issues":        state.get("observed_issues"),
            "weather_forecast_alert": weather_alert,
            "safety_flags": [
                {"severity": f.severity, "message": f.message}
                for f in state.get("safety_flags", [])
            ],
        })

    elif farmer_type == "B":
        rec_crops = state.get("recommended_crops") or []
        output.update({
            "season":            state.get("season"),
            "irrigation_access": state.get("irrigation_access"),
            "market_preference": state.get("market_preference"),
            "top_crops": [
                {
                    "name":         c.name,
                    "varieties":    c.variety_suggestions,
                    "market_value": c.market_value,
                    "input_cost":   c.input_cost,
                    "score":        c.suitability_score,
                    "notes":        c.notes,
                }
                for c in rec_crops
            ],
        })

    return {**state, "rule_output": output}


# ═════════════════════════════════════════════════════════════════════════════
# NODE 5.5 — Retrieve RAG Context
# ═════════════════════════════════════════════════════════════════════════════

def retrieve_rag_context_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Search Qdrant for context related to the crop, observed issues, or growth
    stage (Type A) or zone/season planting advice (Type B).
    """
    farmer_type = state.get("farmer_type")

    if farmer_type == "A":
        crop  = state.get("crop", "")
        stage = state.get("growth_stage").name if state.get("growth_stage") else ""
        issue = state.get("observed_issues", "")
        query = f"{crop} {stage} management." + (f" Problem: {issue}" if issue else "")
    elif farmer_type == "B":
        zone   = state.get("zone", "")
        season = state.get("season", "")
        query  = f"Best crops to plant in {zone} zone during {season} season."
    else:
        query = ""

    logger.info("RAG query: %s", query)

    rag_context = ""
    if query:
        try:
            retriever   = get_retriever()
            docs        = retriever.invoke(query)
            rag_context = "\n".join(d.page_content for d in docs)
            logger.info("RAG: retrieved %d documents", len(docs))
        except Exception as exc:
            logger.error("RAG retrieval failed: %s", exc)

    return {**state, "rag_context": rag_context}


# ═════════════════════════════════════════════════════════════════════════════
# NODE 6 — LLM Synthesis
# ═════════════════════════════════════════════════════════════════════════════

def synthesize_llm_node(state: KrishiMitraState) -> KrishiMitraState:
    """
    Generate the final advisory response.

    Strategy (conversation-mode aware):
    • Python builds the full prompt via build_user_message() — the LLM only
      writes the natural-language reply.
    • Falls back to _fallback_message() when the Gemini API is unavailable.
    """
    language   = state.get("language", "nepali")
    lang_label = "Nepali (नेपाली)" if language == "nepali" else "English"
    mode       = state.get("conversation_mode", "collect")
    rule_output = state.get("rule_output", {})
    rag_context = state.get("rag_context", "No external context found.")

    # ── Map conversation mode → prompt task ───────────────────────────────────
    MODE_TO_TASK = {
        "first_message":   "first",
        "classify":        "ack_ask",
        "collect":         "ack_ask",
        "farmer_question": "answer_ask",
        "advisory":        "advise",
        "returning":       "returning",
    }
    task = MODE_TO_TASK.get(mode, "ack_ask")

    # ── Build the user-facing message — Python packages everything ────────────
    # Uses the richer build_user_message() from Doc-1 when available,
    # falls back to a simple formatted prompt otherwise.
    try:
        user_msg = build_user_message(
            task=task,
            next_question=state.get("next_question", ""),
            known_summary=state.get("known_summary", ""),
            farmer_said=state.get("last_farmer_message", ""),
            rag_context=rag_context,
            crop_tip=state.get("crop_tip", ""),
        )
    except Exception:
        # Fallback: simple prompt used by Doc-2 style
        rule_output_str = json.dumps(rule_output, ensure_ascii=False, indent=2)
        user_msg = KRISHIMITRA_USER_PROMPT.format(language=lang_label)

    system = KRISHIMITRA_SYSTEM_PROMPT

    api_key = settings.google_api_key
    if api_key:
        try:
            llm = ChatGoogleGenerativeAI(
                model=settings.llm_model,
                temperature=0.3,
                google_api_key=api_key,
            )
            messages = [
                SystemMessage(content=system),
                HumanMessage(content=user_msg),
            ]
            response      = llm.invoke(messages)
            final_message = response.text.strip()
            logger.info("LLM synthesis completed (mode=%s task=%s)", mode, task)
        except Exception as exc:
            logger.error("LLM synthesis failed: %s", exc)
            final_message = _fallback_message(rule_output, language)
    else:
        logger.warning("No google_api_key — using rule-based fallback.")
        final_message = _fallback_message(rule_output, language)

    return {**state, "final_message": final_message}


# ═════════════════════════════════════════════════════════════════════════════
# HELPER — Rule-based fallback advisory (no LLM)
# ═════════════════════════════════════════════════════════════════════════════

def _fallback_message(rule_output: Dict[str, Any], language: str) -> str:
    """
    Plain-text advisory rendered entirely from rule_output when the LLM is
    unavailable. Ensures the system degrades gracefully.
    """
    farmer_type = rule_output.get("farmer_type", "?")
    zone        = rule_output.get("zone", "")

    if farmer_type == "A":
        crop       = rule_output.get("crop", "your crop")
        stage      = rule_output.get("growth_stage_name", "current stage")
        activities = rule_output.get("key_activities", [])
        flags      = rule_output.get("safety_flags", [])
        das        = rule_output.get("das", "?")

        critical = [f for f in flags if f.get("severity") == "CRITICAL"]
        warnings = [f for f in flags if f.get("severity") == "WARNING"]

        lines = [f"📋 KrishiMitra Advisory — {crop} (DAS {das}, {zone})"]
        lines.append(f"Growth Stage: {stage}")

        if critical:
            lines.append("\n🚨 CRITICAL ALERTS:")
            lines.extend(f"  {f['message']}" for f in critical)

        if warnings:
            lines.append("\n⚠️ Warnings:")
            lines.extend(f"  {f['message']}" for f in warnings)

        if activities:
            lines.append("\n✅ Recommended actions this week:")
            lines.extend(f"  • {a}" for a in activities)

        advisory_focus = rule_output.get("advisory_focus", "")
        if advisory_focus:
            lines.append(f"\n💡 Key focus: {advisory_focus}")

        # Surface income estimate if available
        utility = rule_output.get("utility") or {}
        income  = utility.get("income_estimate")
        if income:
            lines.append(
                f"\n💰 Estimated income: NPR {income.get('estimated_income_npr', 0):,.0f}"
                f" ({income.get('estimated_yield_kg', 0):,.0f} kg @ "
                f"NPR {income.get('income_price_per_kg', 0):.1f}/kg)"
            )

        return "\n".join(lines)

    if farmer_type == "B":
        season    = rule_output.get("season", "")
        top_crops = rule_output.get("top_crops", [])

        lines = [f"📋 KrishiMitra Crop Recommendation — {zone}, {season}"]
        if top_crops:
            lines.append("Top crop options for your land:")
            for i, c in enumerate(top_crops[:3], 1):
                varieties = ", ".join(c.get("varieties", [])[:2]) or "local variety"
                lines.append(
                    f"  {i}. {c['name']} (Score: {c['score']}/100) — "
                    f"Market: {c['market_value']} | Cost: {c['input_cost']}"
                )
                lines.append(f"     Varieties: {varieties}")
                if c.get("notes"):
                    lines.append(f"     Note: {c['notes']}")
        return "\n".join(lines)

    return (
        "KrishiMitra: Advisory generated. "
        "Please contact your local extension officer for further guidance."
    )