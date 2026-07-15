"""
KrishiMitra - API Routes (Phase 1)
REST endpoints for farmer profile management and advisory generation.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from rules.zone_classifier import classify_zone
from rules.weather_integration import fetch_7_day_forecast, format_weather_for_disease_prompt
from fastapi import File, UploadFile, Form

import asyncio
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=2)

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query
from bson import ObjectId
from api.auth_routes import get_current_user

import json
import re as _re 
from bson import ObjectId

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import nepali_datetime
import nepali_datetime as _npdt
 

from config import get_settings
from db.mongo import get_db
from rules.conversation_rules import (
    build_known_summary,
    build_remaining_fields_summary,
    classify_farmer_type,
    get_conversation_mode,
    get_next_field,
    get_next_question,
    normalise_extracted_profile,
    normalise_crop,
)
from rules.nepali_date_converter import nepali_to_english_date, bs_month_from_raw
from rules.unit_converter import convert_to_hectares, NEPALI_MONTH_TO_INT
from rules.zone_classifier import classify_zone, month_to_season, month_to_name
from schemas.farmer import ChatMessage, ChatResponse

from rules.field_extractor import (
    build_multislot_prompt,
    try_regex_extract,
    MULTISLOT_SYSTEM,
    MULTISLOT_FIELDS,
    VALID_INTENTS,
)
from rules.dialogue_policy import select_task, ACCEPT_CONFIDENCE
 

from db.mongo import get_db
from schemas.farmer import (
    FarmerProfileCreate,
    FarmerProfileOut,
    AdvisoryRequest,
    AdvisoryResponse,
    SafetyCheckIn,
    SafetyCheckOut,
    ChatMessage,
    ChatResponse,
)

from rules.safety_guardrails import run_safety_checks

from graph.workflow import get_advisory_graph
from rag.prompts import (
    build_user_message,
    KRISHIMITRA_SYSTEM
)


import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import traceback
from fastapi import Query

import engine.nepali_calendar as _cal
from engine.nepali_calendar   import get_calendar_context
from engine.market_analysis   import run_market_analysis, NEPALI_MONTHS
from engine.price_forecaster  import get_full_price_analysis
from engine.planting_filter   import get_filtered_crops
from engine.risk_scorer       import get_risk_scores
from engine.ranker            import get_ranked_crops
from engine.smart_recommender import build_recommendations
from engine.llm_evaluator     import run_llm_evaluation
from output.card_builder      import build_cards





settings = get_settings()
logger   = logging.getLogger(__name__)
router   = APIRouter()



# Add this helper at the top of routes.py (outside the chat function)

_DEVANAGARI_TABLE = str.maketrans("०१२३४५६७८९", "0123456789")

def _to_ascii_number(value):
    """Convert Devanagari digits to ASCII. Returns int or float or original."""
    if isinstance(value, str):
        cleaned = value.translate(_DEVANAGARI_TABLE).strip()
        try:
            return float(cleaned) if "." in cleaned else int(cleaned)
        except ValueError:
            return value
    return value


def set_month(bs_month: int):
    if not 1 <= bs_month <= 12:
        raise HTTPException(
            status_code=400,
            detail='bs_month must be between 1 and 12'
        )
    _cal.set_override_month(bs_month)

def handle_error(e: Exception):
    raise HTTPException(
        status_code=500,
        detail={
            'error': str(e),
            'trace': traceback.format_exc()
        }
    )
# ─────────────────────────────────────────────────────────────────────────────
# Farmer Profile Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/farmers",
    response_model=FarmerProfileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new farmer profile",
)
async def create_farmer(payload: FarmerProfileCreate):
    db = get_db()
    collection = db["farmer_profiles"]
    
    existing = await collection.find_one({"phone_number": payload.phone_number})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Farmer with phone {payload.phone_number} already exists.",
        )

    zone = classify_zone(payload.district)

    profile_data = {
        "phone_number": payload.phone_number,
        "name":         payload.name,
        "farmer_type":  payload.farmer_type.value,
        "district":     payload.district,
        "zone":         zone.value if zone else None,
        "village":      payload.village,
        "soil_type":    payload.soil_type,
        "land_area_ha": payload.land_area_ha,
        "language":     payload.language,
        "created_at":   datetime.utcnow(),
        "is_active":    True,
    }

    if payload.farmer_type.value == "A" and payload.type_a:
        profile_data["type_a_detail"] = payload.type_a.model_dump(mode="json")
    elif payload.farmer_type.value == "B" and payload.type_b:
        profile_data["type_b_detail"] = payload.type_b.model_dump(mode="json")

    result = await collection.insert_one(profile_data)
    profile_data["id"] = str(result.inserted_id)
    return profile_data


@router.get("/farmers/{profile_id}", response_model=FarmerProfileOut)
async def get_farmer(profile_id: str):
    db = get_db()
    collection = db["farmer_profiles"]
    if not ObjectId.is_valid(profile_id):
        raise HTTPException(status_code=400, detail="Invalid profile ID format.")
    profile = await collection.find_one({"_id": ObjectId(profile_id)})
    if not profile:
        raise HTTPException(status_code=404, detail="Farmer not found.")
    profile["id"] = str(profile["_id"])
    return profile


@router.get("/farmers", response_model=List[FarmerProfileOut])
async def list_farmers(skip: int = 0, limit: int = 50):
    db = get_db()
    collection = db["farmer_profiles"]
    cursor = collection.find({"is_active": True}).skip(skip).limit(limit)
    profiles = await cursor.to_list(length=limit)
    for p in profiles:
        p["id"] = str(p["_id"])
    return profiles


# ─────────────────────────────────────────────────────────────────────────────
# Advisory Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/advisory", response_model=AdvisoryResponse)
async def generate_advisory(payload: AdvisoryRequest):

    """
    Run the full LangGraph advisory pipeline for a farmer.
    Type A (active farmer):   route → zone → DAS/GDD → safety → rules → RAG → LLM
    Type B (planning farmer): route → zone → suitability → rules → RAG → LLM
    """
    db = get_db()
    collection = db["farmer_profiles"]
    if not ObjectId.is_valid(payload.profile_id):
        raise HTTPException(status_code=400, detail="Invalid profile ID.")
    profile = await collection.find_one({"_id": ObjectId(payload.profile_id)})
    if not profile:
        raise HTTPException(status_code=404, detail="Farmer not found.")

    farmer_type = profile.get("farmer_type", "").upper()
    type_a      = profile.get("type_a_detail", {}) or {}
    type_b      = profile.get("type_b_detail", {}) or {}

    initial_state = {
        "profile_id":         str(profile["_id"]),
        "farmer_type":        profile.get("farmer_type"),
        "district":           profile.get("district"),
        "language":           payload.language or profile.get("language", "nepali"),
        "soil_type":          profile.get("soil_type"),
        "land_area_ha":       profile.get("land_area_ha"),
        "safety_flags":       [],
        "has_critical_flags": False,
    }

    if farmer_type == "A":
        initial_state.update({
            "crop":              type_a.get("crop") or payload.crop,
            "variety":           type_a.get("variety"),
            "sowing_date":       type_a.get("sowing_date") or payload.sowing_date,
            "observed_issues":   payload.observed_issues or type_a.get("observed_issues"),
            "last_fertilizer":   payload.last_fertilizer or type_a.get("last_fertilizer"),
            "last_pesticide":    payload.last_pesticide or type_a.get("last_pesticide"),
        })
    if farmer_type == "B":
        initial_state.update({
            "season":            type_b.get("season") or payload.season_override,
            "irrigation_access": type_b.get("irrigation_access"),
            "market_preference": type_b.get("market_preference"),
            "budget_npr":        type_b.get("budget_npr"),
        })

    try:
        logger.info("Running advisory graph — profile=%s type=%s", str(profile["_id"]), farmer_type)
        final_state = get_advisory_graph().invoke(initial_state)
    except Exception as exc:
        logger.exception("advisory_graph.invoke() failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Advisory pipeline failed: {str(exc)}")

    if final_state.get("error"):
        raise HTTPException(status_code=422, detail=final_state["error"])

    growth_stage = final_state.get("growth_stage")
    safety_flags = final_state.get("safety_flags", [])

    log_doc = {
        "profile_id":         str(profile["_id"]),
        "farmer_type":        farmer_type,
        "crop":               final_state.get("crop"),
        "das":                final_state.get("das"),
        "gdd":                final_state.get("gdd"),
        "zone":               final_state.get("zone"),
        "growth_stage":       growth_stage.name if growth_stage else None,
        "rule_output":        final_state.get("rule_output"),
        "final_message":      final_state.get("final_message"),
        "safety_flags":       [{"severity": f.severity, "message": f.message} for f in safety_flags],
        "has_critical_flags": final_state.get("has_critical_flags", False),
        "created_at":         datetime.utcnow(),
    }
    log_result = db["advisory_logs"].insert_one(log_doc)


     # ── 7. Return response 
    return AdvisoryResponse(
        profile_id=str(profile["_id"]),
        farmer_type=farmer_type,
        zone=final_state.get("zone", ""),
        crop=final_state.get("crop"),
        das=final_state.get("das"),
        growth_stage=growth_stage.name if growth_stage else None,
        has_critical_flags=final_state.get("has_critical_flags", False),
        safety_flags=[{"severity": f.severity, "message": f.message} for f in safety_flags],
        recommended_crops=[
            {
                "name":         c.name,
                "score":        c.suitability_score,
                "varieties":    c.variety_suggestions,
                "market_value": c.market_value,
                "input_cost":   c.input_cost,
                "notes":        c.notes,
            }
            for c in (final_state.get("recommended_crops") or [])
        ],
        message=final_state.get("final_message", ""),
        log_id=str(log_result.inserted_id),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Safety Check Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/safety-check", response_model=SafetyCheckOut)
def safety_check(payload: SafetyCheckIn):
    flags   = run_safety_checks(
        crop=payload.crop,
        das=payload.das,
        fertilizer_name=payload.fertilizer_name,
        fertilizer_kg_per_ha=payload.fertilizer_kg_per_ha,
        pesticide_name=payload.pesticide_name,
        pesticide_ml_per_ha=payload.pesticide_ml_per_ha,
    )
    is_safe = not any(f.severity == "CRITICAL" for f in flags)
    return SafetyCheckOut(
        safe=is_safe,
        flags=[f.message for f in flags],
    )

 
# ─────────────────────────────────────────────────────────────────────────────
# Notification Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/notifications", summary="List notifications saved by the scheduler")
async def list_notifications(
    farmer_id: Optional[str] = Query(None),
    crop: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    skip: int = Query(0),
):
    db = get_db()
    query: dict = {}
    if farmer_id:
        query["profile_id"]      = farmer_id
    if crop:
        query["crop"]            = crop.lower()
    if status:
        query["delivery_status"] = status
 
    cursor = (
        db["notifications"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


@router.get("/notifications/stats", summary="Notification summary stats")
async def notification_stats():
    db = get_db()
    col = db["notifications"]
    total  = await col.count_documents({})
    sent   = await col.count_documents({"delivery_status": "sent"})
    failed = await col.count_documents({"delivery_status": "failed"})
 
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_sent = await col.count_documents({
        "delivery_status": "sent",
        "created_at":      {"$gte": datetime.fromisoformat(today_str)},
    })
    pipeline = [
        {"$group": {"_id": "$crop", "count": {"$sum": 1}}},
        {"$sort":  {"count": -1}},
    ]
    by_crop = {d["_id"]: d["count"] async for d in col.aggregate(pipeline)}
 
    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "today_sent": today_sent,
        "by_crop": by_crop,
    }
 
 
@router.post("/notifications/trigger", summary="Manually trigger the notification scheduler (demo)")
async def trigger_notifications():
    """
    Run the notification job right now — useful for demos.
    Calls the same function the scheduler calls daily.
    """
    from notifications import run_notification_job
    try:
        result = await run_notification_job()
        return {
            "message": "Notification job completed",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except Exception as e:
        logger.exception("Manual notification trigger failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))








# ─────────────────────────────────────────────────────────────────────────────
# CHAT ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

# settings = get_settings()
# logger   = logging.getLogger(__name__)
# router   = APIRouter()
 
# ── Module-level singletons — NOT recreated per request ──────────────────────
_llm_reply = ChatGoogleGenerativeAI(
    model=settings.llm_model_fast,   # fast chat loop — flash
    temperature=0.3,
    google_api_key=settings.google_api_key,
)
_llm_extract = ChatGoogleGenerativeAI(
    model=settings.llm_model_fast,   # fast chat loop — flash
    temperature=0.0,          # deterministic for extraction
    google_api_key=settings.google_api_key,
)
 
# ── Question signals — detect when farmer is asking something ─────────────────
_QUESTION_SIGNALS = [
    "?","ke","k ","kasto","kasari","kina","kaha","kahile","kati","kun",
    "how","what","which","why","when","where","tell me","bhannus",
    "bhannuhos","explain","hunchha","garchan","hudaina",
    "के","कसरी","किन","कहाँ","कहिले","कति","कुन",
]
 
NEPALI_MONTH_NAMES = {
    1:"Baisakh",2:"Jestha",3:"Ashadh",4:"Shrawan",
    5:"Bhadra",6:"Ashwin",7:"Kartik",8:"Mangsir",
    9:"Poush",10:"Magh",11:"Falgun",12:"Chaitra",
}
 
 
# ── Background task — runs after reply is sent ────────────────────────────────
async def _run_income_calc(profile_id: str, profile: dict) -> None:
    """Triggered when crop+district+land+month all present. Never blocks reply."""
    try:
        from core.profile_extractor import estimate_income
        result = await estimate_income(profile)
        if result:
            db = get_db()
            await db["farmer_profiles"].update_one(
                {"_id": ObjectId(profile_id)},
                {"$set": result},
            )
            logger.info(
                "BG income | profile=%s | npr=%s",
                profile_id, result.get("estimated_income_npr"),
            )
    except Exception as e:
        logger.warning("BG income failed | profile=%s: %s", profile_id, e)
 
 
def _is_asking(message: str) -> bool:
    lower = message.strip().lower()
    return any(s in lower for s in _QUESTION_SIGNALS)


# ── Disease/pest intent signals — detect when farmer describes a crop problem ──
_DISEASE_SIGNALS = [
    # Devanagari
    "रोग", "बिरामी", "कीरा", "किरा", "धमिरा", "ढुसी", "फंगस", "संक्रमण",
    "दाग", "धब्बा", "टाटो", "ओइला", "ओइलि", "कुहि", "कुहिन", "सडे", "सडेको",
    "पहेँलो", "पहेंलो", "पहेली", "कालो भयो", "कालो भइरहेको", "पात खा",
    "पात कुहि", "पात झर", "ब्लाइट", "उपचार", "औषधि", "लाग्यो", "लागेको",
    "मर्न", "मरे", "सुक्न", "सुकेको", "गल्न", "गलेको",
    # Romanized
    "rog", "birami", "kira", "keera", "dhamira", "dhusi", "fungus",
    "sankraman", "daag", "dhabba", "tato", "oilai", "kuhi", "sade",
    "pahelo", "kalo bhayo", "pat khai", "blight", "upchar", "aushadhi",
    "lagyo", "mareko", "sukyo", "galeko",
    # English
    "disease", "pest", "insect", "infection", "fungus", "blight",
    "rot", "wilt", "spot", "yellowing", "dying", "symptom", "leaf spot",
]


def _is_disease_question(message: str) -> bool:
    """True when the farmer is describing a crop disease / pest / problem."""
    lower = message.strip().lower()
    return any(s in lower for s in _DISEASE_SIGNALS)
 
 
def _parse_llm_json(raw: str) -> dict:
    """Safely parse LLM JSON response, strip markdown fences."""
    if not raw:
        return {}
    
    clean = _re.sub(r"```(?:json)?|```", "", raw).strip()
    
    # Try full JSON parse
    try:
        return json.loads(clean)
    except Exception:
        pass
    
    # Try extracting {"reply": "..."} pattern
    try:
        match = _re.search(r'\{"reply"\s*:\s*"(.+?)"\s*\}', clean, _re.DOTALL)
        if match:
            return {"reply": match.group(1)}
    except Exception:
        pass
    
    # LLM returned plain text instead of JSON — use it directly
    if not clean.startswith("{"):
        return {"reply": clean}
    
    return {}
 
 
# ── The single derive function — batches all rule-based derivations ───────────
def _derive_fields(current_field: str, value, unit: str, profile: dict) -> dict:
    derived = {}

    if current_field == "land_size":
        if value and unit:
            ha = convert_to_hectares(float(value), unit)
            if ha:
                derived["land_size_value"]    = value
                derived["land_size_unit"]     = unit
                derived["land_size_hectares"] = ha
                derived["land_size_raw"]      = f"{value} {unit}"

    elif current_field == "sowing_date":
        derived["sowing_date_original"] = value
        ad_date = nepali_to_english_date(value)
        if ad_date:
            derived["sowing_date"] = ad_date

        bs_month = bs_month_from_raw(value)
        if bs_month:
            derived["farming_month"]      = bs_month
            derived["farming_month_name"] = NEPALI_MONTH_NAMES.get(bs_month, "")
            season = month_to_season(bs_month)
            if season:
                derived["season"] = season
        else:
            # Fallback: bs_month_from_raw couldn't parse the string,
            # so convert the AD date back to BS to get the month
            if ad_date:
                try:
                    import nepali_datetime
                    from datetime import date as _date
                    ad = _date.fromisoformat(ad_date)
                    bs = nepali_datetime.date.from_datetime_date(ad)
                    derived["farming_month"]      = bs.month
                    derived["farming_month_name"] = NEPALI_MONTH_NAMES.get(bs.month, "")
                    season = month_to_season(bs.month)
                    if season:
                        derived["season"] = season
                except Exception as e:
                    logger.warning("BS month fallback from AD date failed: %s", e)

    elif current_field == "farming_month":
        # Type B farmer gives month directly e.g. "Ashadh" or "असार"
        bs_month = bs_month_from_raw(value)
        if bs_month:
            derived["farming_month"]      = bs_month
            derived["farming_month_name"] = NEPALI_MONTH_NAMES.get(bs_month, "")
            season = month_to_season(bs_month)
            if season:
                derived["season"] = season

    elif current_field == "district":
        zone = classify_zone(value)
        if zone:
            derived["zone"] = zone.value

    return derived


def _state_key(field_name: str) -> str:
    """Map an extractor field name to the profile key that stores its result."""
    return "land_size_hectares" if field_name == "land_size" else field_name


def _build_updates_from_fields(accepted_fields: list, profile: dict) -> dict:
    """
    Turn a list of accepted (field_name, value, unit) tuples into one db_updates
    dict — running each through the same Python derivation + normalisation rules
    the single-field path used. Returns the merged updates ready for one DB write.
    """
    db_updates: dict = {}
    all_derived: dict = {}
    for field_name, value, unit in accepted_fields:
        if field_name == "land_size":
            db_updates["land_size_value"] = value
            db_updates["land_size_unit"]  = unit or ""
        else:
            db_updates[field_name] = value
        # derive against the profile view including everything accepted so far
        derived = _derive_fields(field_name, value, unit or "", {**profile, **db_updates})
        db_updates.update(derived)
        all_derived.update(derived)

    db_updates = normalise_extracted_profile(db_updates)
    db_updates.update(all_derived)   # derivations win over generic normalisation
    return db_updates


# =============================================================================
# /chat endpoint
# =============================================================================
 
@router.post("/chat", response_model=ChatResponse, summary="KrishiMitra Chat")
async def chat(
    payload: ChatMessage,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    db         = get_db()
    col        = db["farmer_profiles"]
    hist       = db["conversation_history"]
    user_id    = str(current_user["_id"])
    user_name  = current_user.get("name", "")

    # ── 1. Single profile read ─────────────────────────────────────────────────
    profile = await col.find_one({"user_id": user_id})
    if not profile:
        res     = await col.insert_one({"user_id": user_id, "name": user_name})
        profile = {"_id": res.inserted_id, "user_id": user_id, "name": user_name}

    # ── 1a. One-time migration: location → district ────────────────────────────
    if not profile.get("district") and profile.get("location"):
        await col.update_one(
            {"_id": profile["_id"]},
            {"$set": {"district": profile["location"]}, "$unset": {"location": ""}},
        )
        profile["district"] = profile["location"]

    # ── 2. Turn bookkeeping ────────────────────────────────────────────────────
    # The user message is NOT persisted here. It is saved together with the
    # assistant reply at each exit point via _persist_turn(), so a mid-turn crash
    # writes both or neither — never an orphaned user message without an answer.
    prior_user_msgs = await hist.count_documents({"user_id": user_id, "role": "user"})
    turn_count = prior_user_msgs + 1
    is_first   = turn_count <= 1 and not profile.get("greeted")

    async def _persist_turn(reply_text: str) -> None:
        """Save this turn's user message + assistant reply as one atomic pair.
        The assistant timestamp is nudged 1ms ahead so history always pairs
        user→assistant in order regardless of clock resolution."""
        now = datetime.utcnow()
        await hist.insert_many([
            {"user_id": user_id, "role": "user",
             "message": payload.message, "timestamp": now},
            {"user_id": user_id, "role": "assistant",
             "message": reply_text, "timestamp": now + timedelta(milliseconds=1)},
        ])

    # ── 3. FIRST MESSAGE — fixed reply, zero LLM ──────────────────────────────
    if is_first:
        await col.update_one({"_id": profile["_id"]}, {"$set": {"greeted": True}})
        reply = (
            "नमस्ते! म कृषिमित्र हुँ — तपाईंको खेतीको साथी। "
            "के तपाईंको खेतमा हाल कुनै बाली छ, कि रोप्ने योजना बनाउँदै हुनुहुन्छ?"
        )
        await _persist_turn(reply)
        return ChatResponse(user_id=user_id, reply=reply)

    # ── 4. MULTI-SLOT extraction — intent + EVERY field stated, in one call ────
    # A farmer volunteers facts non-linearly ("Kavre ma 2 ropani alu cha" = type
    # + district + land + crop). We extract them all at once. Rules then
    # normalise/validate; only high-confidence, still-empty fields are saved.
    current_field  = get_next_field(profile)   # what we're currently waiting on
    intent         = "answer"
    cur_field_conf = 0.0
    accepted       = False
    accepted_names: set[str] = set()

    if not is_first:
        candidates: dict = {}   # field_name -> (value, unit, confidence)

        # Cheap deterministic fast-paths first (no hallucination) ──────────────
        kw_type = classify_farmer_type(payload.message) if not profile.get("farmer_type") else None
        if kw_type:
            candidates["farmer_type"] = (kw_type, None, 1.0)

        if current_field:
            regex_result = try_regex_extract(current_field, payload.message)
            if regex_result and regex_result.get("value") is not None:
                candidates[current_field] = (
                    regex_result["value"], regex_result.get("unit"),
                    float(regex_result.get("confidence", 0)),
                )

        # Multi-slot LLM extraction ────────────────────────────────────────────
        fields: dict = {}
        try:
            raw_resp = await _llm_extract.ainvoke([
                SystemMessage(content=MULTISLOT_SYSTEM),
                HumanMessage(content=build_multislot_prompt(payload.message, profile, current_field)),
            ])
            parsed = _parse_llm_json(raw_resp.text)
            if parsed:
                intent = parsed.get("intent") or "answer"
                fields = parsed.get("fields") or {}
                if not isinstance(fields, dict):
                    fields = {}
        except Exception as e:
            logger.warning("Multi-slot extraction failed: %s", e)

        for fname, fdata in fields.items():
            if fname not in MULTISLOT_FIELDS or not isinstance(fdata, dict):
                continue
            fval  = fdata.get("value")
            fconf = float(fdata.get("confidence", 0) or 0)
            if fname == current_field:
                cur_field_conf = max(cur_field_conf, fconf)
            if fval is None:
                continue
            # Don't clobber a fast-path result already captured for this field.
            if fname not in candidates:
                candidates[fname] = (fval, fdata.get("unit"), fconf)

        # Intent fallback when the model didn't give a usable label ────────────
        if intent not in VALID_INTENTS:
            if _is_disease_question(payload.message):
                intent = "disease"
            elif _is_asking(payload.message):
                intent = "question"
            else:
                intent = "answer" if current_field else "question"

        # Decide which candidates to accept ────────────────────────────────────
        # Fill empty fields freely; overwrite a KNOWN field only when it's the one
        # we're asking now or a very high-confidence restatement (correction).
        accepted_fields: list = []
        for fname, (fval, funit, fconf) in candidates.items():
            if fconf < ACCEPT_CONFIDENCE:
                continue
            already = profile.get(_state_key(fname)) not in (None, "")
            if already and fname != current_field and fname != "farmer_type" and fconf < 0.9:
                continue
            accepted_fields.append((fname, fval, funit))

        # Persist all accepted fields through the rule pipeline in one write ────
        if accepted_fields:
            db_updates = _build_updates_from_fields(accepted_fields, profile)
            if db_updates:
                await col.update_one({"_id": profile["_id"]}, {"$set": db_updates})
                profile.update(db_updates)
                accepted = True
                accepted_names = {f[0] for f in accepted_fields}
                logger.info(
                    "Multi-slot saved | user=%s | fields=%s | intent=%s",
                    user_id, sorted(accepted_names), intent,
                )

        # Type A fallback — auto-set farming_month if a crop is planted but no month
        if (
            accepted
            and profile.get("farmer_type") == "A"
            and not profile.get("farming_month")
            and profile.get("crop")
        ):
            current_bs_month = _npdt.date.today().month
            month_fallback = {
                "farming_month":        current_bs_month,
                "farming_month_name":   NEPALI_MONTH_NAMES.get(current_bs_month, ""),
                "farming_month_source": "auto_current_month",
            }
            season = month_to_season(current_bs_month)
            if season:
                month_fallback["season"] = season
            await col.update_one({"_id": profile["_id"]}, {"$set": month_fallback})
            profile.update(month_fallback)

        # Trigger income calc in background if all 4 inputs are present ─────────
        if accepted:
            has_income = all([
                profile.get("crop"),
                profile.get("district"),
                profile.get("land_size_hectares"),
                profile.get("farming_month"),
            ])
            income_stale = (
                not profile.get("estimated_income_npr")
                or bool(accepted_names & {"crop", "district", "land_size", "farming_month", "sowing_date"})
            )
            if has_income and income_stale:
                background_tasks.add_task(
                    _run_income_calc,
                    str(profile["_id"]),
                    dict(profile),
                )

    # If the farmer type is STILL unknown and nothing usable came in, ask for it.
    if not profile.get("farmer_type") and not is_first and intent in ("answer", "smalltalk", "offtopic"):
        reply = (
            "राम्रो! बाली अहिले खेतमा छ भने 'छ' भन्नुस्, "
            "रोप्ने योजना छ भने 'योजना छ' भन्नुस्।"
        )
        await _persist_turn(reply)
        await col.update_one({"_id": profile["_id"]}, {"$set": {"last_task": "classify"}})
        return ChatResponse(user_id=user_id, reply=reply)

    # ── 6. Pure dialogue policy picks the task for this turn ──────────────────
    # rules/dialogue_policy.select_task owns all routing (unit-tested); the LLM
    # only renders the reply. last_task lets us bridge back after a detour.
    next_field    = get_next_field(profile)
    next_question = get_next_question(profile) or ""
    is_complete   = next_field is None
    last_task     = profile.get("last_task")

    task = select_task(
        profile,
        intent=intent,
        accepted=accepted,
        confidence=cur_field_conf,
        last_task=last_task,
    )
    logger.info(
        "Turn routed | intent=%s | accepted=%s | conf=%.2f | last_task=%s | task=%s",
        intent, accepted, cur_field_conf, last_task, task,
    )

    # ── Handle returning farmer ────────────────────────────────────────────────
    is_returning = (
        profile.get("crop") and profile.get("district")
        and not profile.get("_session_greeted")
        and turn_count == 2
    )
    if is_returning and task in ("ack_ask", "resume_ask"):
        task = "returning"
        await col.update_one({"_id": profile["_id"]},
                              {"$set": {"_session_greeted": True}})

    # ── 7. RAG fetch ───────────────────────────────────────────────────────────
    import re as _re

    rag          = ""
    crop_tip     = ""
    crop_for_rag = profile.get("crop") or normalise_crop(payload.message.lower())

    logger.info("RAG DEBUG | crop_for_rag=%s | task=%s | farmer_type=%s",
                crop_for_rag, task, profile.get("farmer_type"))

    # ── 7a. Disease/problem question — retrieve using the farmer's OWN words ────
    # Runs even when crop is not yet known. No crop_tip stapled on this turn.
    if task == "disease_answer":
        try:
            from rag.retriever import get_retriever
            retriever = get_retriever()
            query = " ".join(filter(None, [
                crop_for_rag or "",
                payload.message,
                "disease symptom cause treatment prevention Nepal",
                profile.get("district", ""),
            ])).strip()
            logger.info("RAG disease | query=%s", query)
            docs = retriever.invoke(query)
            if docs:
                raw_rag = " ".join(d.page_content for d in docs[:2])[:600].strip()
                rag     = _re.sub(r"[#*_`>\-]+", " ", raw_rag)
                rag     = _re.sub(r"\s+", " ", rag).strip()
            logger.info("RAG disease | docs=%d | context_len=%d", len(docs), len(rag))
        except Exception as e:
            logger.warning("Disease RAG failed: %s", e)

    elif crop_for_rag:
        try:
            from rag.retriever import get_retriever
            retriever = get_retriever()

            # General RAG — only for direct farmer questions and advisory
            if task in ("answer_ask", "advise", "open_advisory"):
                docs = retriever.invoke(
                    f"{crop_for_rag} Nepal farming advice {profile.get('district', '')}"
                )
                if docs:
                    raw_rag = docs[0].page_content[:400].strip()
                    rag     = _re.sub(r"[#*_`]", "", raw_rag).strip()
                logger.info("RAG general | docs=%d", len(docs))

            # Crop tip — fetched on EVERY turn once crop is known
            # Type B (planning) → opportunity/benefits
            # Type A (planted)  → disease/pest warnings
            farmer_type = profile.get("farmer_type", "B")


            fields_done = sum(1 for f in[
                "crop","district","land_size_hectares","land_ownership",
                "irrigation_type","experience_years","farming_type",
            ] if profile.get(f))

            if farmer_type == "B":
                tip_queries = [
                    f"{crop_for_rag} farming benefits Nepal",
                    f"{crop_for_rag} best variety Nepal yield",
                    f"{crop_for_rag} market price Nepal profit",
                    f"{crop_for_rag} sowing season Nepal climate",
                    f"{crop_for_rag} fertilizer irrigation Nepal",

                ]
            else:
                tip_queries = [
                    f"{crop_for_rag} disease early warning Nepal",
                    f"{crop_for_rag} pest management Nepal",
                    f"{crop_for_rag} fertilizer schedule Nepal",
                    f"{crop_for_rag} irrigation water management Nepal",
                    f"{crop_for_rag} harvest post harvest Nepal",
                ]

            tip_query = tip_queries[fields_done % len(tip_queries)] 

            if profile.get("district"):
                tip_query += f" {profile['district']}"

            logger.info("crop_tip query | fields_done=%d | query=%s", fields_done, tip_query)   

            tip_docs = retriever.invoke(tip_query)
            if tip_docs:
                # Strip markdown so LLM gets clean plain text to translate into Nepali
                raw_tip  = tip_docs[0].page_content[:250].strip()
                crop_tip = _re.sub(r"[#*_`>\-]+", " ", raw_tip)   # remove # * _ ` > -
                crop_tip = _re.sub(r"\s+", " ", crop_tip).strip()  # collapse whitespace
                logger.info("crop_tip fetched | crop=%s | clean_preview=%s",
                            crop_for_rag, crop_tip[:100])
            else:
                logger.info("crop_tip | no docs returned | query=%s", tip_query)

        except Exception as e:
            logger.warning("RAG failed: %s", e)

    # ── 8. Build prompt — one system prompt, dynamic user message ─────────────
    # On a disease turn, suppress the profile question so the bot answers the
    # problem fully; collection resumes automatically on the next turn.
    prompt_next_question = "" if task == "disease_answer" else next_question
    known    = build_known_summary(profile, user_name)
    user_msg = build_user_message(
        task,
        prompt_next_question,
        known,
        payload.message,
        rag,
        crop_tip=crop_tip,
    )

    logger.info("user_msg to LLM:\n%s", user_msg)

    # ── Fetch last 6 turns for conversation context ───────────────────────────
    recent = await hist.find({"user_id": user_id}).sort("timestamp", -1).limit(6).to_list(6)
    recent.reverse()

    messages = [SystemMessage(content=KRISHIMITRA_SYSTEM)]
    for doc in recent:
        if doc["role"] == "user":
            messages.append(HumanMessage(content=doc["message"]))
        elif doc["role"] == "assistant":
            messages.append(AIMessage(content=doc["message"]))
    messages.append(HumanMessage(content=user_msg))

    # ── 9. Single LLM call — reply generation only ────────────────────────────
    reply = ""
    try:
        resp   = await _llm_reply.ainvoke(messages)
        logger.info("RAW LLM response: %s", resp.text[:300])
        parsed = _parse_llm_json(resp.text)
        reply  = parsed.get("reply", "").strip()

        logger.info("parsed reply: '%s'", reply) 
    except Exception as e:
        logger.error("Reply LLM failed | user=%s: %s", user_id, e)

    # ── 10. Fallback if LLM returned empty ────────────────────────────────────
    if not reply:
        fallback_map = {
            "advise":         "तपाईंको प्रोफाइल पूरा भयो! कुनै प्रश्न छ भने सोध्नुहोस्।",
            "redirect":       f"हजुर! {next_question}",
            "clarify":        f"अलि स्पष्ट गर्नुस् — {next_question}",
            "disease_answer": "तपाईंको बालीमा देखिएको समस्या बुझ्न, कृपया लक्षण अलि विस्तारमा बताउनुहोस् वा स्थानीय कृषि विशेषज्ञसँग एकपटक सम्पर्क गर्नुहोस्।",
        }
        reply = fallback_map.get(task, next_question or "राम्रो! अगाडि बढौं।")

    # ── 11. Save the turn + remember this turn's task (for bridge-back next turn) ──
    await _persist_turn(reply)
    await col.update_one({"_id": profile["_id"]}, {"$set": {"last_task": task}})

    logger.info(
        "Chat done | user=%s | turn=%d | task=%s | field=%s | reply_len=%d",
        user_id, turn_count, task, current_field, len(reply),
    )

    return ChatResponse(user_id=user_id, reply=reply)



# ── CALENDAR ──────────────────────────────────────────────────────────────────

@router.get("/calendar/{bs_month}", tags=["Calendar"], summary="Get Nepali calendar context")
def get_calendar(bs_month: int):
    try:
        ctx = get_calendar_context(bs_month=bs_month)
        return {
            'bs_month':         ctx['bs_month'],
            'month_name':       ctx['month_name'],
            'season':           ctx['season'],
            'risk_multipliers': ctx['risk_multipliers'],
        }
    except Exception as e:
        handle_error(e)


@router.get("/season", tags=["Calendar"], summary="Get season name for a given BS month")
def get_season(month: int = Query(..., ge=1, le=12)):
    try:
        from engine.nepali_calendar import get_season_for_month
        season = get_season_for_month(month)
        return {
            'bs_month':   month,
            'month_name': NEPALI_MONTHS[month - 1],
            'season':     season,
        }
    except Exception as e:
        handle_error(e)


# ── MARKET ────────────────────────────────────────────────────────────────────

@router.get("/market/analysis", tags=["Market"], summary="Historical demand analysis")
def market_analysis(top_n: int = Query(5, ge=1, le=20)):
    try:
        _, demand_df, rankings, _ = run_market_analysis()
        return {
            'source':   'historical',
            'top_n':    top_n,
            'rankings': {
                NEPALI_MONTHS[m-1]: crops[:top_n]
                for m, crops in rankings.items()
            },
            'total_crops_analyzed': int(demand_df['crop_key'].nunique()),
        }
    except Exception as e:
        handle_error(e)


@router.get("/market/forecast", tags=["Market"], summary="Prophet price forecasts")
def market_forecast(top_n: int = Query(5, ge=1, le=20)):
    try:
        analysis = get_full_price_analysis()
        return {
            'source':              'prophet_forecast',
            'top_n':               top_n,
            'historical_rankings': {
                NEPALI_MONTHS[m-1]: crops[:top_n]
                for m, crops in analysis['historical_rankings'].items()
            },
            'forecasted_rankings': {
                NEPALI_MONTHS[m-1]: crops[:top_n]
                for m, crops in analysis['forecasted_rankings'].items()
            },
            'forecast_months': int(analysis['forecast_df']['bs_month'].nunique()),
        }
    except Exception as e:
        handle_error(e)


# ── CROPS ─────────────────────────────────────────────────────────────────────

@router.get("/crops/filtered/{bs_month}", tags=["Crops"], summary="Crops plantable in a given month")
def crops_filtered(bs_month: int):
    try:
        set_month(bs_month)
        crops = get_filtered_crops()
        return {
            'bs_month':      bs_month,
            'month_name':    NEPALI_MONTHS[bs_month - 1],
            'total':         len(crops),
            'plant_now':     [c for c in crops if c['planting_status'] == 'plant_now'],
            'coming_soon':   [c for c in crops if c['planting_status'] == 'coming_soon'],
            'out_of_season': [c for c in crops if c['planting_status'] == 'out_of_season'],
        }
    except HTTPException:
        raise
    except Exception as e:
        handle_error(e)


@router.get("/crops/risks/{bs_month}", tags=["Crops"], summary="Season-adjusted risk scores")
def crops_risks(bs_month: int):
    try:
        set_month(bs_month)
        scores = get_risk_scores()
        return {
            'bs_month':   bs_month,
            'month_name': NEPALI_MONTHS[bs_month - 1],
            'total':      len(scores),
            'risks':      scores,
        }
    except HTTPException:
        raise
    except Exception as e:
        handle_error(e)


@router.get("/crops/ranked/{bs_month}", tags=["Crops"], summary="Crops ranked by opportunity score")
def crops_ranked(
    bs_month: int,
    lang: str = Query('en', regex='^(en|ne)$')
):
    try:
        set_month(bs_month)
        cards = build_cards(lang=lang)
        return {
            'bs_month':   bs_month,
            'month_name': NEPALI_MONTHS[bs_month - 1],
            'lang':       lang,
            'total':      len(cards),
            'crops':      cards,
        }
    except HTTPException:
        raise
    except Exception as e:
        handle_error(e)


@router.get("/crops/smart/{bs_month}", tags=["Crops"], summary="Smart recommendations")
def crops_smart(bs_month: int):
    try:
        set_month(bs_month)
        recommendations, ctx = build_recommendations()
        return {
            'bs_month':        bs_month,
            'month_name':      ctx['month_name'],
            'season':          ctx['season'],
            'total':           len(recommendations),
            'recommendations': recommendations,
        }
    except HTTPException:
        raise
    except Exception as e:
        handle_error(e)


@router.get("/crops/verified/{bs_month}", tags=["Crops"], summary="LLM-verified recommendations")
def crops_verified(
    bs_month: int,
    lang: str = Query('en', regex='^(en|ne)$')
):
    try:
        set_month(bs_month)
        verified, ctx = run_llm_evaluation(lang=lang)
        corrected = [c for c in verified if c.get('was_corrected', False)]
        return {
            'bs_month':         bs_month,
            'month_name':       ctx['month_name'],
            'season':           ctx['season'],
            'lang':             lang,
            'total':            len(verified),
            'corrections_made': len(corrected),
            'crops':            verified,
        }
    except HTTPException:
        raise
    except Exception as e:
        handle_error(e)


@router.get("/crops/summary/all-months", tags=["Crops"], summary="Smart recommendations for all 12 months")
def all_months_summary():
    try:
        result = {}
        for month_num in range(1, 13):
            _cal.set_override_month(month_num)
            try:
                recommendations, _ = build_recommendations()
                result[NEPALI_MONTHS[month_num - 1]] = [
                    {
                        'rank':             r['rank'],
                        'crop_key':         r['crop_key'],
                        'crop_name':        r['crop_name'],
                        'plant_month':      r['plant_month'],
                        'best_harvest':     r['best_harvest_month'],
                        'opportunity_score': r['opportunity_score'],
                        'forecasted_price': r['forecasted_price'],
                    }
                    for r in recommendations[:3]
                ]
            except Exception:
                result[NEPALI_MONTHS[month_num - 1]] = []
        return {'source': 'smart_recommender', 'months': result}
    except Exception as e:
        handle_error(e)


# ── RECOMMENDATIONS & DASHBOARD (main dashboard endpoints) ───────────────────

@router.get("/recommendations", tags=["Crops"], summary="LLM verified recommendations — main dashboard")
def get_recommendations(
    month: int = Query(..., ge=1, le=12),
    lang:  str = Query('en', regex='^(en|ne)$')
):
    try:
        set_month(month)
        verified, ctx = run_llm_evaluation(lang=lang)
        corrected = [c for c in verified if c.get('was_corrected', False)]
        return {
            'context': {
                'bs_month':   ctx['bs_month'],
                'month_name': ctx['month_name'],
                'season':     ctx['season'],
            },
            'total':            len(verified),
            'corrections_made': len(corrected),
            'recommendations':  verified,
        }
    except HTTPException:
        raise
    except Exception as e:
        handle_error(e)


@router.get("/dashboard", tags=["Crops"], summary="General crop status cards — Tab 2")
def get_dashboard(
    month: int = Query(..., ge=1, le=12),
    lang:  str = Query('en', regex='^(en|ne)$')
):
    try:
        set_month(month)
        ctx   = get_calendar_context()
        cards = build_cards(lang=lang)
        return {
            'context': {
                'bs_month':   ctx['bs_month'],
                'month_name': ctx['month_name'],
                'season':     ctx['season'],
            },
            'total': len(cards),
            'cards': cards,
        }
    except HTTPException:
        raise
    except Exception as e:
        handle_error(e)


# ── FORECAST RETRAIN ──────────────────────────────────────────────────────────

@router.post("/forecast/retrain", tags=["Forecast"], summary="Force retrain all Prophet models")
def retrain_forecast():
    try:
        from engine.price_forecaster import run_all_forecasts, CACHE_PATH
        if os.path.exists(CACHE_PATH):
            os.remove(CACHE_PATH)
        forecasts = run_all_forecasts(force_retrain=True)
        return {
            'status':  'retrained',
            'message': 'All Prophet models retrained successfully',
            'rows':    len(forecasts),
        }
    except Exception as e:
        handle_error(e)


@router.get("/admin/farmers", summary="Admin — all farmer profiles with scores")
async def admin_get_all_farmers(
    current_user=Depends(get_current_user),
):
    if current_user.get("email") != "admin@gmail.com":
        raise HTTPException(status_code=403, detail="Access denied.")

    db = get_db()
    col = db["farmer_profiles"]

    cursor = col.find({}).sort("scored_at", -1)
    farmers = await cursor.to_list(length=None)

    for f in farmers:
        f["_id"] = str(f["_id"])

    return farmers