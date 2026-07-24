// Mirrors backend Pydantic schemas (schemas/farmer.py) and the JSON shapes
// returned by api/routes.py — keep field names identical to the API, not
// paraphrased, so payloads pass through untouched.

export interface AuthToken {
  access_token: string
  token_type: string
  user_id: string
}

export interface ChatSession {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ChatMessageOut {
  role: 'user' | 'assistant'
  message: string
  timestamp: string
}

export interface ChatResponse {
  user_id: string
  session_id: string
  reply: string
  disease_detected?: boolean
  disease_info?: Record<string, unknown> | null
}

// ── Market ────────────────────────────────────────────────────────────────

export interface MarketCalendarRow {
  crop: string
  month: number
  month_name: string
  price_avg: number
  price_low: number
  price_high: number
  demand_score: number
  trend_pct: number | null
}

export interface MarketCalendarMonthResponse {
  bs_month: number
  month_name: string
  generated_at: string | null
  crops: MarketCalendarRow[]
}

export interface MarketCalendarAllResponse {
  source: string
  top_n: number
  generated_at: string | null
  calendar: Record<string, MarketCalendarRow[]>
}

export interface ForecastRankingRow {
  rank: number
  crop_key: string
  nepali_month: string
  forecasted_avg: number
  forecasted_lower: number
  forecasted_upper: number
  demand_score: number
}

export interface MarketForecastResponse {
  source: string
  top_n: number
  generated_at: string | null
  historical_rankings: Record<string, unknown[]>
  forecasted_rankings: Record<string, ForecastRankingRow[]>
  forecast_months: number
}

// ── Recommendations (GET /recommendations) ───────────────────────────────
// English-only regardless of ?lang= (verified live — no bilingual _en/_ne
// split at this endpoint, unlike /crops/verified/{bs_month}).

export interface CropRecommendation {
  rank: number
  crop_key: string
  crop_name: string
  plant_month: string
  plant_timing: string
  harvest_months: string[]
  best_harvest_month: string
  weeks_to_grow: string // e.g. "10–14"
  forecasted_price: number
  demand_score: number
  feasibility_reason: string
  risk_score: number
  risk_tier: string
  dominant_risk: string
  scoring_notes: string
  water_req: string
  shelf_life: string
  diseases: string
  altitude: string
  opportunity_score: number
}

export interface RecommendationsResponse {
  context: { bs_month: number; month_name: string; season: string }
  total: number
  corrections_made: number
  recommendations: CropRecommendation[]
}

// ── Admin (GET /admin/farmers) ────────────────────────────────────────────
// Raw farmer_profiles documents enriched with the linked user's name/email/
// phone (db/crud.py admin_get_all_profiles). credit_score/risk_level/etc. are
// only present once core/credit_scorer.py has run for that farmer — most
// profiles won't have them yet, so every scoring field is optional. Verified
// live against real data — field names and shapes are exact, not paraphrased.

export interface ScoreBreakdown {
  dti_score: number
  irrigation_score: number
  land_score: number
  experience_score: number
  crop_score: number
  total: number
  max_possible: number
}

export interface AdminFarmerProfile {
  id: string
  user_id: string
  name: string | null
  email: string | null
  phone: string | null
  crop?: string
  district?: string
  zone?: string
  farmer_type?: 'A' | 'B'
  land_size_hectares?: number
  land_ownership?: string
  irrigation_type?: string
  experience_years?: number
  farming_type?: string
  has_loan?: boolean
  loan_amount?: number

  // Present only once scored:
  credit_score?: number
  risk_level?: 'low' | 'medium' | 'high'
  recommendation?: 'approve' | 'review' | 'decline'
  decision_note?: string
  default_probability?: number
  dti_ratio?: number
  loan_utilisation_pct?: number
  max_safe_loan_npr?: number
  headroom_npr?: number
  crop_loan_limit_npr?: number
  emi_monthly_npr?: number
  monthly_income_npr?: number
  monthly_burden_pct?: number
  monthly_remaining_npr?: number
  score_breakdown?: ScoreBreakdown
  scored_at?: string
  watch_points?: string[]

  estimated_income_npr?: number
  estimated_yield_kg?: number
}

export interface AdminFarmersResponse {
  total: number
  skip: number
  limit: number
  farmers: AdminFarmerProfile[]
}

export const NEPALI_MONTHS = [
  'Baisakh', 'Jestha', 'Ashadh', 'Shrawan', 'Bhadra', 'Ashwin',
  'Kartik', 'Mangsir', 'Poush', 'Magh', 'Falgun', 'Chaitra',
] as const
