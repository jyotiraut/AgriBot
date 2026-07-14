from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ── Step 1: User ──────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserInDB(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    created_at: datetime
    is_active: bool = True


class UserPublic(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInDB


# ── Step 2: Conversation ───────────────────────────────────────────────────────

class ConversationTurn(BaseModel):
    """A single Q&A exchange saved to MongoDB."""
    user_id: str
    session_id: str                     # groups turns in one sitting
    stage: Optional[str] = None         # which guided stage this belongs to
    question: str                       # what the farmer asked / said
    answer: str                         # what the bot replied
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationTurnPublic(ConversationTurn):
    id: str


class ConversationHistory(BaseModel):
    turns: List[ConversationTurnPublic]
    total: int


# ── Step 3: Stage tracking ────────────────────────────────────────────────────

class StageEnum(str, Enum):
    WELCOME    = "welcome"
    CROP       = "crop"
    FARM_SIZE  = "farm_size"
    EXPERIENCE = "experience"
    FINANCIAL  = "financial"
    COMPLETE   = "complete"


class StageProgress(BaseModel):
    """Persisted per-user stage state inside farmer_profiles collection."""
    current_stage:    StageEnum       = StageEnum.WELCOME
    stages_completed: List[StageEnum] = []
    stage_updated_at: datetime        = Field(default_factory=datetime.utcnow)
    agronomic_done:   bool            = False
    financial_done:   bool            = False
    scored:           bool            = False


# ── Step 4: Farmer Profile ────────────────────────────────────────────────────

class FarmerProfile(BaseModel):
    """Structured profile extracted from conversation history."""
    user_id: str

    # ── Agronomic ─────────────────────────────────────────────
    crop:               Optional[str]   = None
    land_size_hectares: Optional[float] = None   # canonical — always in hectares
    land_size_raw:      Optional[str]   = None   # what farmer said e.g. "3 ropani"
    farming_month:      Optional[int]   = None   # 1-12 integer (month to start farming)
    land_ownership:     Optional[str]   = None   # "owned" or "leased"
    irrigation_type:    Optional[str]   = None
    experience_years:   Optional[int]   = None
    location:           Optional[str]   = None   # district name (lowercase for DB lookup)
    farming_type:       Optional[str]   = None   # "organic", "conventional", "mixed"

    # ── Financial signals ──────────────────────────────────────
    has_loan:               Optional[bool]  = None   # True ONLY if farmer explicitly confirmed
    loan_amount:            Optional[float] = None
    annual_income_estimate: Optional[float] = None   # self-reported by farmer
    owns_equipment:         Optional[bool]  = None
    uses_inputs_on_credit:  Optional[bool]  = None

    # ── Estimated income (computed from yield_data + price_data) ──
    estimated_yield_kg:    Optional[float]    = None   # kg for their land size
    estimated_income_npr:  Optional[float]    = None   # NPR revenue for the season
    income_price_per_kg:   Optional[float]    = None   # avg market price used (NPR/kg)
    income_yield_t_per_ha: Optional[float]    = None   # district yield factor used (t/ha)
    income_estimated_at:   Optional[datetime] = None   # when estimate was last calculated

    # ── Meta ───────────────────────────────────────────────────
    extraction_confidence: float             = 0.0
    extracted_at:          Optional[datetime] = None
    extraction_version:    int               = 1
    raw_notes:             Optional[str]     = None

    # ── Stage progress ─────────────────────────────────────────
    stage_progress: StageProgress = Field(default_factory=StageProgress)


class FarmerProfilePublic(FarmerProfile):
    id:                str
    credit_score:      Optional[int]      = None
    risk_level:        Optional[str]      = None
    score_explanation: Optional[str]      = None
    scored_at:         Optional[datetime] = None


# ── Step 5: Credit Score ───────────────────────────────────────────────────────

class CreditScore(BaseModel):
    credit_score:      int  = Field(..., ge=0, le=850)
    risk_level:        str                    # "low" | "medium" | "high"
    score_breakdown:   dict = {}              # component → points
    score_explanation: str  = ""
    scored_at:         datetime = Field(default_factory=datetime.utcnow)


class AdminProfileView(BaseModel):
    """Admin endpoint response — full profile + score side by side."""
    id:      str
    user_id: str
    name:    Optional[str] = None
    email:   Optional[str] = None

    # Agronomic
    crop:               Optional[str]   = None
    land_size_hectares: Optional[float] = None   # was land_size_acres — now hectares
    land_size_raw:      Optional[str]   = None
    farming_month:      Optional[int]   = None
    land_ownership:     Optional[str]   = None
    location:           Optional[str]   = None
    irrigation_type:    Optional[str]   = None
    experience_years:   Optional[int]   = None
    farming_type:       Optional[str]   = None

    # Financial signals
    has_loan:               Optional[bool]  = None
    loan_amount:            Optional[float] = None
    annual_income_estimate: Optional[float] = None
    owns_equipment:         Optional[bool]  = None
    uses_inputs_on_credit:  Optional[bool]  = None

    # Estimated income
    estimated_yield_kg:    Optional[float]    = None
    estimated_income_npr:  Optional[float]    = None
    income_price_per_kg:   Optional[float]    = None
    income_yield_t_per_ha: Optional[float]    = None
    income_estimated_at:   Optional[datetime] = None

    # Credit score
    credit_score:      Optional[int]      = None
    risk_level:        Optional[str]      = None
    score_explanation: Optional[str]      = None
    scored_at:         Optional[datetime] = None

    # Meta
    extraction_confidence: Optional[float]    = None
    extracted_at:          Optional[datetime] = None
    raw_notes:             Optional[str]      = None