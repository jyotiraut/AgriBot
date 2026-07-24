"""
KrishiMitra - Pydantic schemas
Request bodies and response models for the REST API and MongoDB.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
import enum
import regex as re


class FarmerType(str, enum.Enum):
    A = "A"
    B = "B"


class Zone(str, enum.Enum):
    TERAI     = "Terai"
    HILLS     = "Hills"
    MOUNTAINS = "Mountains"


class Season(str, enum.Enum):
    KHARIF = "Kharif"
    RABI   = "Rabi"
    SPRING = "Spring"


class IrrigationAccess(str, enum.Enum):
    RAINFED = "Rainfed"
    PARTIAL = "Partial"
    FULL    = "Full"


class TypeADetailIn(BaseModel):
    crop:                    str            = Field(..., example="Rice")
    variety:                 Optional[str]  = Field(None, example="Sabitri")
    sowing_date:             date           = Field(..., example="2025-06-15")
    observed_issues:         Optional[str]  = Field(None, example="Yellow leaves on lower stem")
    last_fertilizer_applied: Optional[dict] = None
    last_pesticide_applied:  Optional[dict] = None


class TypeBDetailIn(BaseModel):
    season:             Season            = Field(..., example="Kharif")
    irrigation_access:  IrrigationAccess  = Field(IrrigationAccess.RAINFED)
    market_preference:  Optional[str]     = Field(None, example="local market, vegetables")
    budget_npr:         Optional[float]   = Field(None, example=15000.0)


class FarmerProfileCreate(BaseModel):
    phone_number: str           = Field(..., example="+9779800000000")
    name:         Optional[str] = None
    farmer_type:  FarmerType
    district:     str           = Field(..., example="Chitwan")
    village:      Optional[str] = None
    soil_type:    Optional[str] = Field(None, example="loamy")
    land_area_ha: Optional[float] = Field(None, example=0.5)
    language:     str           = Field("nepali", example="nepali")

    type_a: Optional[TypeADetailIn] = None
    type_b: Optional[TypeBDetailIn] = None

    @field_validator("type_a")
    @classmethod
    def a_requires_type(cls, v, info):
        if v and info.data.get("farmer_type") == FarmerType.B:
            raise ValueError("type_a detail provided for a Type B farmer")
        return v


class FarmerProfileOut(BaseModel):
    id:           str
    phone_number: str
    name:         Optional[str] = None
    farmer_type:  FarmerType
    district:     str
    zone:         Optional[Zone] = None
    language:     str

    model_config = {"from_attributes": True}


class AdvisoryRequest(BaseModel):
    profile_id:      str
    observed_issues: Optional[str]    = None
    season_override: Optional[Season] = None
    language:        Optional[str]    = None


class AdvisoryResponse(BaseModel):
    profile_id:        str
    farmer_type:       str
    zone:              str
    crop:              Optional[str]        = None
    das:               Optional[int]        = None
    gdd:               Optional[float]      = None
    growth_stage:      Optional[str]        = None
    safety_flags:      List[str]            = []
    recommended_crops: Optional[List[str]]  = None
    message:           str
    log_id:            Optional[str]        = None


class SafetyCheckIn(BaseModel):
    crop:                   str
    das:                    int
    fertilizer_name:        str
    fertilizer_kg_per_ha:   float
    pesticide_name:         Optional[str]   = None
    pesticide_ml_per_ha:    Optional[float] = None


class SafetyCheckOut(BaseModel):
    safe:                           bool
    flags:                          List[str]
    adjusted_fertilizer_kg_per_ha:  Optional[float] = None


class ChatMessage(BaseModel):
    message:    str
    language:   Optional[str] = None
    session_id: Optional[str] = None   # omit to use/create the farmer's latest session


class ChatResponse(BaseModel):
    user_id: str
    session_id: str
    reply: str
    disease_detected: Optional[bool] = False
    disease_info: Optional[Dict[str, Any]] = None


class ChatSessionOut(BaseModel):
    id:         str
    title:      str
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(BaseModel):
    role:      str
    message:   str
    timestamp: datetime

class FarmerProfilePublic(BaseModel):
    id:      str
    user_id: str

    # ── Core fields ───────────────────────────────────────────────────────────
    crop:               str
    land_size_hectares: float
    land_size_raw:      str
    farming_month:      int
    farming_month_name: Optional[str]   = None   # ← NEW: "Baisakh" … "Chaitra"
    land_ownership:     str
    irrigation_type:    str
    experience_years:   int
    location:           str
    district:           Optional[str]   = None
    zone:               Optional[str]   = None   # ← NEW: "Terai" | "Hills" | "Mountains"
    season:             Optional[str]   = None   # ← NEW: "Kharif" | "Rabi" | "Spring"

    # ── Farmer classification ─────────────────────────────────────────────────
    farmer_type:        Optional[str]   = None   # ← NEW: "A" | "B"
    sowing_date:        Optional[str]   = None   # ← NEW

    # ── Financial / optional ──────────────────────────────────────────────────
    farming_type:           Optional[str]   = None
    has_loan:               Optional[bool]  = None
    loan_amount:            Optional[float] = None
    annual_income_estimate: Optional[float] = None
    owns_equipment:         Optional[bool]  = None
    uses_inputs_on_credit:  Optional[bool]  = None

    # ── Income projections ────────────────────────────────────────────────────
    estimated_yield_kg:    Optional[float]    = None
    estimated_income_npr:  Optional[float]    = None
    income_price_per_kg:   Optional[float]    = None
    income_yield_t_per_ha: Optional[float]    = None
    income_estimated_at:   Optional[datetime] = None

    # ── Credit scoring ────────────────────────────────────────────────────────
    credit_score:      Optional[int]      = None
    risk_level:        Optional[str]      = None
    score_explanation: Optional[str]      = None
    scored_at:         Optional[datetime] = None

    # ── RAG / LLM extraction ─────────────────────────────────────────────────
    extraction_confidence: Optional[float]    = None
    extracted_at:          Optional[datetime] = None
    raw_notes:             Optional[str]      = None


class ConversationalFarmerProfileUpdate(BaseModel):
    """Used for the LLM to patch data into a profile during the onboarding chat."""

    ai_reply_to_user: str = Field(
        ...,
        description="Your direct conversational reply to the user. MUST BE PROVIDED."
    )

    # ── Core crop / land ──────────────────────────────────────────────────────
    crop:               Optional[str]   = None
    land_size_hectares: Optional[float] = None
    land_size_raw:      Optional[str]   = None

    # ── Time / season ─────────────────────────────────────────────────────────
    farming_month:      Optional[int]   = None   # integer 1–12 (Nepali calendar)
    farming_month_name: Optional[str]   = None   # ← NEW: "Baisakh" … "Chaitra"
    season:             Optional[str]   = None   # ← NEW: "Kharif" | "Rabi" | "Spring"
    sowing_date:        Optional[str]   = None   # "2081-02-15" or "Baisakh 15"

    # ── Location / zone ───────────────────────────────────────────────────────
    location:           Optional[str]   = None
    zone:               Optional[str]   = None   # ← NEW: "Terai" | "Hills" | "Mountains"

    # ── Farm details ──────────────────────────────────────────────────────────
    land_ownership:     Optional[str]   = None
    irrigation_type:    Optional[str]   = None
    experience_years:   Optional[int]   = None
    farming_type:       Optional[str]   = None

    # ── Financial ─────────────────────────────────────────────────────────────
    has_loan:               Optional[bool]  = None
    loan_amount:            Optional[float] = None
    annual_income_estimate: Optional[float] = None
    owns_equipment:         Optional[bool]  = None
    uses_inputs_on_credit:  Optional[bool]  = None

    # ── Farmer classification ─────────────────────────────────────────────────
    farmer_type:        Optional[str]   = None   # "A" or "B"

    @field_validator("land_size_hectares", mode="before")
    @classmethod
    def parse_land_size(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            if re.match(r'^[\d\s\.\+\-\*\/]+$', v.strip()):
                try:
                    return round(float(eval(v)), 4)
                except Exception:
                    return None
            try:
                return float(v)
            except Exception:
                return None
        return None

    @field_validator("farming_month", mode="before")
    @classmethod
    def validate_farming_month(cls, v):
        if v is None:
            return None
        try:
            month = int(v)
            return month if 1 <= month <= 12 else None
        except (ValueError, TypeError):
            return None

    @field_validator("zone", mode="before")
    @classmethod
    def normalise_zone(cls, v):
        """Accept any capitalisation — store as title case to match Zone enum."""
        if v is None:
            return None
        mapping = {
            "terai":     "Terai",
            "hills":     "Hills",
            "mountains": "Mountains",
            "mountain":  "Mountains",
        }
        return mapping.get(str(v).strip().lower(), str(v).strip().title())

    @field_validator("season", mode="before")
    @classmethod
    def normalise_season(cls, v):
        """Accept any capitalisation — store as title case to match Season enum."""
        if v is None:
            return None
        mapping = {
            "kharif": "Kharif",
            "rabi":   "Rabi",
            "spring": "Spring",
        }
        return mapping.get(str(v).strip().lower(), str(v).strip().title())