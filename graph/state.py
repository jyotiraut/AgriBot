
from __future__ import annotations
from typing import Any, Dict, List, Optional, TypedDict
from rules.das_gdd import GrowthStage
from rules.crop_suitability import CropOption
from rules.safety_guardrails import SafetyFlag


class KrishiMitraState(TypedDict, total=False):
    # ── Input ─────────────────────────────────────────────────────
    profile_id: int
    farmer_type: str                    # "A" | "B"
    district: str
    soil_type: Optional[str]
    land_area_ha: Optional[float]
    language: str                       # "nepali" | "english"

    # Type A specific inputs
    crop: Optional[str]
    variety: Optional[str]
    sowing_date: Optional[Any]          # AD ISO string after convert_date_node
    sowing_date_original: Optional[str] # original BS string for display
    observed_issues: Optional[str]
    last_fertilizer: Optional[Dict]     # {name, kg_per_ha}
    last_pesticide: Optional[Dict]      # {name, ml_per_ha}

    # Type B specific inputs
    season: Optional[str]
    irrigation_access: Optional[str]
    market_preference: Optional[str]
    budget_npr: Optional[float]

    # ── Land size (raw + converted) ────────────────────────────────
    land_size: Optional[float]          # raw numeric value from farmer
    land_size_unit: Optional[str]       # raw unit string (ropani, bigha, etc.)
    land_size_hectares: Optional[float] # converted by convert_units_node

    # ── Income estimate ────────────────────────────────────────────
    income_estimate: Optional[Dict]     # {estimated_yield_kg, estimated_income_npr,
                                        #  income_price_per_kg, income_yield_t_per_ha,
                                        #  can_estimate, missing_fields}
    yield_t_per_ha: Optional[float]
    avg_price_per_kg: Optional[float]
    farming_month: Optional[int]        # month as int (1–12)

    # ── Derived by graph nodes ─────────────────────────────────────
    zone: Optional[str]                 # Terai | Hills | Mountains
    zone_characteristics: Optional[Dict]

    # Type A derived
    das: Optional[int]
    gdd: Optional[float]
    growth_stage: Optional[GrowthStage]
    days_to_harvest: Optional[int]

    # Type B derived
    recommended_crops: Optional[List[CropOption]]

    # Safety
    safety_flags: List[SafetyFlag]
    has_critical_flags: bool

    # Rule engine output
    rule_output: Optional[Dict]         # structured advice from rule nodes

    # RAG Context
    rag_context: Optional[str]          # retrieved textbook/agricultural document context

    # Weather Context
    weather_data: Optional[Dict]

    # LLM synthesis
    final_message: str                  # primary output (Nepali by default)
    final_message_english: Optional[str]

    # Metadata
    error: Optional[str]
    log_id: Optional[int]


    # ── Disease Detection (Image Upload) ────────────────────────────
    image_bytes: Optional[bytes]           # raw image from Streamlit upload
    disease_detected: bool                 # True if image was processed
    disease_info: Optional[Dict]           # {disease_raw, disease_readable, crop_type,#  confidence, confidence_level, top3, 
    disease_raw: Optional[str]              # e.g. "Tomato___Late_blight"
    disease_recommendation: Optional[str]   # LLM response for disease
    disease_rag_context: Optional[str]      # RAG context specific to disease
    conversation_history: Optional[List]    # for followup memory
    user_id: Optional[str]                  # needed for fetching history
    user_message: Optional[str]             # current user message                                   
                                           

    # ── Farmer Profile (incremental extraction) ───────────────────
    farmer_profile: Optional[Dict]      # incrementally built farmer profile
    last_extracted_at: Optional[str]    # ISO datetime of last extraction
    profile_confidence: Optional[float] # extraction_confidence from last run
    llm_extracted_profile: Optional[Dict]  # raw LLM extraction before normalise_profile_node

    # ── Flat profile fields (synced from farmer_profile) ─────────
    experience_years: Optional[int]
    farming_type: Optional[str]         # organic | chemical | mixed
    has_loan: Optional[bool]
    land_ownership: Optional[str]       # owned | leased

    # ── Conversation state machine ────────────────────────────────
    conversation_mode: Optional[str]    # first_message | classify | collect |
                                        # advisory | returning | farmer_question
    conversation_started: Optional[bool]
    next_field: Optional[str]           # field name to collect next
    next_question: Optional[str]        # resolved Nepali question string
    known_summary: Optional[str]        # formatted summary of what we know
    remaining_fields: Optional[str]     # comma-separated list of fields after next
    farmer_asked_question: Optional[bool]
    user_name: Optional[str]
    session_greeted: Optional[bool]     # True once returning-farmer greeting is shown
    user_id: Optional[str]              # user identifier for profile lookup