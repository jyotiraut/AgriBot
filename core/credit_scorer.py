from datetime import datetime
from typing import Optional
import re
from db.mongo import get_db


# ── Constants ──────────────────────────────────────────────────
INTEREST_RATE      = 0.07   # 7% Nepal govt subsidised agri loan
LOAN_TENURE_MONTHS = 12     # standard 1 crop cycle
INCOME_SAFE_PCT    = 0.40   # 40% of monthly income — max safe EMI


# ══════════════════════════════════════════════════════════════
# EMI CALCULATOR
# ══════════════════════════════════════════════════════════════

def _calc_emi(principal: float, annual_rate: float = 0.07, months: int = 12) -> float:
    """
    Standard EMI formula — principal + interest monthly payment.
    EMI = P × [r(1+r)^n] / [(1+r)^n - 1]
    """
    if principal <= 0:
        return 0.0
    r = annual_rate / 12
    return principal * (r * (1 + r)**months) / ((1 + r)**months - 1)


# ══════════════════════════════════════════════════════════════
# SCORING COMPONENTS — total 100 points
#
# DTI          35 pts — can they repay? (EMI / monthly income)
# Irrigation   20 pts — how reliable is the income?
# Land         20 pts — collateral if they default
# Experience   15 pts — farmer reliability
# Crop         10 pts — price volatility risk
# ══════════════════════════════════════════════════════════════

def _score_dti(dti: float) -> int:
    """
    DTI = Monthly EMI / Monthly Income — 35 points
    Core repayment question.
    dti == 0   → no loan requested, neutral score (18)
    dti > 1.0  → EMI exceeds income, cannot repay (0)
    """
    if   dti == 0:    return 18   # no loan — neutral not maximum
    elif dti <= 0.25: return 35   # EMI is 25% of income — very comfortable
    elif dti <= 0.40: return 27   # standard safe zone
    elif dti <= 0.60: return 16   # getting stretched
    elif dti <= 0.80: return 7    # high burden
    elif dti <= 1.00: return 2    # barely affordable
    else:             return 0    # EMI exceeds income — cannot repay


def _score_irrigation(irrigation: Optional[str]) -> int:
    """
    Irrigation reliability — 20 points
    Rain-fed = income depends entirely on monsoon = highest risk
    Drip/borewell = reliable water year round = lowest risk

    Nepali inputs accepted:
      वर्षाको पानी / वर्षा  → rain-fed
      नहर                  → canal
      पम्प                 → pump
      थोपा / थोपा सिंचाइ  → drip
    """
    if not irrigation:
        return 7   # unknown — neutral
    i = irrigation.lower().strip()
    if   i in ("drip", "borewell", "थोपा", "थोपा सिंचाइ"):         return 20
    elif i in ("pump", "pipe", "पम्प"):                             return 17
    elif i == "sprinkler":                                          return 15
    elif i in ("canal", "नहर"):                                     return 12
    elif i in ("rain-fed", "rainfed", "monsoon", "rain",
               "वर्षाको पानी", "वर्षा"):                           return 3
    else:                                                           return 7


def _score_land_ownership(ownership: Optional[str]) -> int:
    """
    Land ownership — 20 points
    Owned land = collateral exists = lender can recover if default
    Leased land = zero collateral = total loss if default
    """
    if not ownership:
        return 7   # unknown — neutral
    o = ownership.lower().strip()
    if   o == "owned":   return 20
    elif o == "partial": return 11
    elif o == "leased":  return 8
    else:                return 7


def _score_experience(experience) -> int:
    """
    Farming experience — 15 points
    First year farmers default at ~12% higher rate in Nepal MFI data.
    Handles both int and string inputs.
    """
    if experience is None:
        return 7   # unknown — neutral

    if isinstance(experience, str):
        exp_lower = experience.lower()
        if any(w in exp_lower for w in ["first", "beginner", "new", "0"]):
            return 1
        if any(w in exp_lower for w in ["experienced", "many", "long"]):
            return 15
        match = re.search(r"(\d+)", experience)
        if match:
            experience = int(match.group(1))
        else:
            return 7

    try:
        exp = int(experience)
    except (ValueError, TypeError):
        return 7

    if   exp == 0:  return 1
    elif exp == 1:  return 5
    elif exp <= 2:  return 8
    elif exp <= 4:  return 12
    elif exp >= 5:  return 15


def _score_crop(crop: Optional[str]) -> int:
    """
    Crop price stability — 10 points
    Tomato price swings 3-4x per season in Nepal — highest risk
    Staple crops (paddy, wheat, maize) most stable
    Potato stable, cauliflower moderate
    """
    if not crop:
        return 5   # unknown — neutral
    c = crop.lower().strip()
    if   c in ("paddy", "rice", "wheat", "maize"):    return 10
    elif c in ("potato", "aloo"):                      return 8
    elif c in ("cauliflower", "cauli", "kauli"):       return 5
    elif c in ("tomato", "tomatoes", "golbheda"):      return 1
    else:                                              return 5


# ══════════════════════════════════════════════════════════════
# MAIN SCORER
# ══════════════════════════════════════════════════════════════

def calculate_score(profile: dict) -> dict:
    """
    Calculate credit score for a single farmer profile.

    Scoring — 100 points total:
      DTI        35 pts  (Monthly EMI / Monthly Income)
      Irrigation 20 pts  (water reliability)
      Land       20 pts  (collateral)
      Experience 15 pts  (farmer reliability)
      Crop       10 pts  (price volatility)

    DTI uses full EMI formula over 12 months standard tenure.
    Crop-linked loan limit = 65% of estimated harvest income (ADBL standard).

    Risk thresholds:
      80–100 → Low        (PD 4%)
      65–79  → Medium     (PD 9%)
      50–64  → Medium     (PD 15%)
      35–49  → High       (PD 22%)
      20–34  → High       (PD 35%)
      Below 20 → Very High (PD 60%)
    """

    # ── Extract fields ─────────────────────────────────────────
    income      = float(profile.get("estimated_income_npr") or 0)
    loan_amount = float(profile.get("loan_amount") or 0)

    # Handle leading space bugs in field names
    irrigation = (
        profile.get("irrigation_type")
        or profile.get("irrigation_method")
        or profile.get(" irrigation_type")
    )
    land_ownership = (
        profile.get("land_ownership")
        or profile.get(" land_ownership")
    )
    experience = (
        profile.get("experience_years")
        or profile.get(" experience_years")
    )
    crop = profile.get("crop") or profile.get("crop_type")

    # ── EMI and DTI ────────────────────────────────────────────
    monthly_income   = income / 12 if income > 0 else 0
    emi              = _calc_emi(loan_amount, INTEREST_RATE, LOAN_TENURE_MONTHS)
    annual_loan_cost = emi * LOAN_TENURE_MONTHS

    if   loan_amount == 0:   dti = 0.0
    elif monthly_income > 0: dti = round(emi / monthly_income, 4)
    else:                    dti = 1.0   # no income — worst case

    # ── Score each component ───────────────────────────────────
    dti_score        = _score_dti(dti)
    irrigation_score = _score_irrigation(irrigation)
    land_score       = _score_land_ownership(land_ownership)
    experience_score = _score_experience(experience)
    crop_score       = _score_crop(crop)

    total_score = (
        dti_score +
        irrigation_score +
        land_score +
        experience_score +
        crop_score
    )

    # ── Risk level ─────────────────────────────────────────────
    # Updated thresholds to match validated farmer scoring examples
    if   total_score >= 80: risk_level = "low"
    elif total_score >= 65: risk_level = "medium"
    elif total_score >= 50: risk_level = "medium"
    elif total_score >= 35: risk_level = "high"
    elif total_score >= 20: risk_level = "high"
    else:                   risk_level = "very_high"

    # ── Default probability ────────────────────────────────────
    # Calibrated to Nepal MFI NPL rate ~12-18%
    # Updated: Below 20 → 60% (was 70%)
    if   total_score >= 80: default_prob = 0.04
    elif total_score >= 65: default_prob = 0.09
    elif total_score >= 50: default_prob = 0.15
    elif total_score >= 35: default_prob = 0.22
    elif total_score >= 20: default_prob = 0.35
    else:                   default_prob = 0.60   # updated from 0.70

    # Adjust upward for high DTI
    if   dti > 1.0: default_prob = min(0.95, default_prob + 0.20)
    elif dti > 0.8: default_prob = min(0.95, default_prob + 0.15)
    elif dti > 0.6: default_prob = min(0.95, default_prob + 0.08)
    elif dti > 0.4: default_prob = min(0.95, default_prob + 0.04)

    # ── Max safe loan (reverse EMI formula) ────────────────────
    # Max EMI farmer can afford = 40% of monthly income
    # Back-calculate the principal from that EMI
    if income > 0:
        max_monthly_emi = monthly_income * INCOME_SAFE_PCT
        r               = INTEREST_RATE / 12
        n               = LOAN_TENURE_MONTHS
        max_safe_loan   = round(
            max_monthly_emi * ((1 + r)**n - 1) / (r * (1 + r)**n)
        )
    else:
        max_safe_loan = 0

    # ── Crop-linked loan limit (ADBL standard) ─────────────────
    # Maximum loan = 65% of expected harvest income
    crop_loan_limit     = round(income * 0.65) if income > 0 else 0
    crop_limit_breached = loan_amount > crop_loan_limit and crop_loan_limit > 0

    # ── Loan utilisation ───────────────────────────────────────
    if max_safe_loan > 0 and loan_amount > 0:
        loan_utilisation_pct = round((loan_amount / max_safe_loan) * 100, 1)
    else:
        loan_utilisation_pct = 0.0

    # ── Monthly burden ─────────────────────────────────────────
    monthly_remaining  = round(monthly_income - emi, 2)
    monthly_burden_pct = (
        round((emi / monthly_income) * 100, 1)
        if monthly_income > 0 else 0.0
    )

    # ── Recommendation ─────────────────────────────────────────
    if risk_level == "low":
        recommendation = "approve"
        decision_note  = "Low risk. Loan is well within safe repayment limits."
    elif risk_level == "medium":
        recommendation = "review"
        decision_note  = "Medium risk. Review with conditions — crop insurance recommended."
    elif risk_level == "high":
        recommendation = "reduce_or_decline"
        decision_note  = "High risk. Reduce loan amount or require collateral/group guarantee."
    else:
        recommendation = "decline"
        decision_note  = "Very high risk. Do not approve without significant collateral."

    # Hard override 1 — EMI exceeds monthly income
    if dti > 1.0:
        recommendation = "decline"
        decision_note  = (
            f"Monthly EMI (NPR {emi:,.0f}) exceeds monthly income "
            f"(NPR {monthly_income:,.0f}). "
            f"Farmer is short NPR {abs(monthly_remaining):,.0f} every month."
        )

    # Hard override 2 — loan exceeds EMI-based safe limit
    elif loan_amount > max_safe_loan and max_safe_loan > 0 and recommendation == "approve":
        recommendation = "review"
        decision_note  = (
            f"Loan exceeds EMI-based safe limit. "
            f"Maximum safe loan at 40% income rule: NPR {max_safe_loan:,}."
        )

    # Hard override 3 — crop-linked limit breached
    elif crop_limit_breached and recommendation == "approve":
        recommendation = "review"
        decision_note  = (
            f"Loan exceeds 65% of expected crop value. "
            f"Crop-linked limit (ADBL standard): NPR {crop_loan_limit:,}."
        )

    # ── Watch points ───────────────────────────────────────────
    watch_points = []

    if dti > 1.0:
        watch_points.append(
            f"CRITICAL: EMI NPR {emi:,.0f}/month exceeds income NPR {monthly_income:,.0f}/month "
            f"— short by NPR {abs(monthly_remaining):,.0f}"
        )
    elif dti > 0.6:
        watch_points.append(
            f"High EMI burden — {monthly_burden_pct}% of monthly income goes to repayment"
        )
    elif dti > 0.4:
        watch_points.append(
            f"DTI {round(dti*100)}% — approaching safe threshold of 40%"
        )

    if crop_limit_breached:
        watch_points.append(
            f"Loan NPR {loan_amount:,.0f} exceeds crop-linked limit NPR {crop_loan_limit:,}"
        )

    if loan_amount > max_safe_loan and max_safe_loan > 0:
        watch_points.append(
            f"Loan exceeds EMI-based safe limit by NPR {round(loan_amount - max_safe_loan):,}"
        )

    if isinstance(experience, (int, float)) and int(experience) == 0:
        watch_points.append("First season farmer — higher default risk")

    if isinstance(experience, (int, float)) and int(experience) == 1:
        watch_points.append("Only 1 year experience — limited track record")

    if crop and crop.lower() in ("tomato", "tomatoes", "golbheda"):
        watch_points.append("Tomato price volatile — recommend crop insurance")

    if irrigation and any(w in str(irrigation).lower() for w in ["rain", "वर्षा"]):
        watch_points.append("Rain-fed irrigation — yield depends on monsoon")

    if land_ownership and "lease" in str(land_ownership).lower():
        watch_points.append("Leased land — no collateral available for recovery")

    return {
        # ── Core output ────────────────────────────────────────
        "credit_score":          total_score,
        "risk_level":            risk_level,
        "default_probability":   round(default_prob, 3),
        "recommendation":        recommendation,
        "decision_note":         decision_note,

        # ── EMI and DTI ────────────────────────────────────────
        "dti_ratio":             dti,
        "emi_monthly_npr":       round(emi, 2),
        "monthly_income_npr":    round(monthly_income, 2),
        "monthly_remaining_npr": monthly_remaining,
        "monthly_burden_pct":    monthly_burden_pct,
        "annual_loan_cost_npr":  round(annual_loan_cost, 2),

        # ── Loan capacity ──────────────────────────────────────
        "max_safe_loan_npr":     max_safe_loan,
        "crop_loan_limit_npr":   crop_loan_limit,
        "loan_utilisation_pct":  loan_utilisation_pct,
        "headroom_npr":          max(0, max_safe_loan - loan_amount),

        # ── Score breakdown ────────────────────────────────────
        "score_breakdown": {
            "dti_score":         dti_score,
            "irrigation_score":  irrigation_score,
            "land_score":        land_score,
            "experience_score":  experience_score,
            "crop_score":        crop_score,
            "total":             total_score,
            "max_possible":      100,
        },

        # ── Watch points ───────────────────────────────────────
        "watch_points": watch_points,

        # ── Metadata ───────────────────────────────────────────
        "interest_rate_used":    INTEREST_RATE,
        "loan_tenure_months":    LOAN_TENURE_MONTHS,
        "scored_at":             datetime.utcnow(),
    }


# ══════════════════════════════════════════════════════════════
# DATABASE FUNCTIONS
# ══════════════════════════════════════════════════════════════

async def score_farmer(user_id: str) -> dict:
    """
    Score a single farmer by user_id.
    Reads from farmer_profiles, calculates score,
    saves result back to the same document.
    """
    db = get_db()

    profile = await db.farmer_profiles.find_one({"user_id": user_id})
    if not profile:
        return {"error": "Profile not found", "user_id": user_id}

    if not profile.get("estimated_income_npr"):
        return {
            "error": "Cannot score — estimated_income_npr missing. Run income calculator first.",
            "user_id": user_id,
        }

    result = calculate_score(profile)

    await db.farmer_profiles.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "credit_score":          result["credit_score"],
                "risk_level":            result["risk_level"],
                "default_probability":   result["default_probability"],
                "recommendation":        result["recommendation"],
                "decision_note":         result["decision_note"],
                "dti_ratio":             result["dti_ratio"],
                "emi_monthly_npr":       result["emi_monthly_npr"],
                "monthly_income_npr":    result["monthly_income_npr"],
                "monthly_remaining_npr": result["monthly_remaining_npr"],
                "monthly_burden_pct":    result["monthly_burden_pct"],
                "max_safe_loan_npr":     result["max_safe_loan_npr"],
                "crop_loan_limit_npr":   result["crop_loan_limit_npr"],
                "loan_utilisation_pct":  result["loan_utilisation_pct"],
                "headroom_npr":          result["headroom_npr"],
                "score_breakdown":       result["score_breakdown"],
                "watch_points":          result["watch_points"],
                "scored_at":             result["scored_at"],
            }
        }
    )

    result["user_id"] = user_id
    print(
        "✅ Scored | user=" + user_id +
        " | score="    + str(result["credit_score"]) + "/100" +
        " | risk="     + result["risk_level"] +
        " | EMI=NPR "  + str(result["emi_monthly_npr"]) +
        " | DTI="      + str(round(result["dti_ratio"] * 100, 1)) + "%" +
        " | PD="       + str(round(result["default_probability"] * 100, 1)) + "%"
    )

    return result


async def score_all_farmers() -> list[dict]:
    """
    Score every farmer in the farmer_profiles collection.
    Called from: POST /admin/score-all
    Skips profiles with no income data.
    """
    db = get_db()

    cursor   = db.farmer_profiles.find(
        {"estimated_income_npr": {"$exists": True, "$ne": None}}
    )
    profiles = await cursor.to_list(length=None)

    if not profiles:
        print("ℹ️  No profiles with income data found")
        return []

    print("🔄 Scoring " + str(len(profiles)) + " farmer profiles...")

    results = []
    scored  = 0
    skipped = 0

    for profile in profiles:
        user_id = profile.get("user_id")
        if not user_id:
            skipped += 1
            continue
        try:
            result = await score_farmer(user_id)
            if "error" not in result:
                results.append(result)
                scored += 1
            else:
                skipped += 1
        except Exception as e:
            print("❌ Failed | user=" + str(user_id) + " | " + str(e))
            skipped += 1

    print(
        "\n✅ Complete — "
        + str(scored) + " scored, "
        + str(skipped) + " skipped"
    )

    if results:
        low       = sum(1 for r in results if r["risk_level"] == "low")
        medium    = sum(1 for r in results if r["risk_level"] == "medium")
        high      = sum(1 for r in results if r["risk_level"] == "high")
        very_high = sum(1 for r in results if r["risk_level"] == "very_high")
        avg_score = sum(r["credit_score"] for r in results) / len(results)
        avg_dti   = sum(r["dti_ratio"] for r in results) / len(results)

        print("\n── Risk Distribution ──────────────────────")
        print("  Low risk      : " + str(low))
        print("  Medium risk   : " + str(medium))
        print("  High risk     : " + str(high))
        print("  Very high     : " + str(very_high))
        print("  Avg score     : " + str(round(avg_score, 1)) + " / 100")
        print("  Avg DTI       : " + str(round(avg_dti * 100, 1)) + "%")

    return results


async def get_all_scored_profiles(skip: int = 0, limit: int = 50) -> list[dict]:
    """
    Fetch all scored profiles for admin dashboard.
    Sorted by credit_score descending.
    Enriches with email and name from users collection.
    """
    db = get_db()

    cursor = (
        db.farmer_profiles
        .find({"credit_score": {"$exists": True}})
        .sort("credit_score", -1)
        .skip(skip)
        .limit(limit)
    )
    profiles = await cursor.to_list(length=None)

    results = []
    for p in profiles:
        if "_id" in p:
            p["id"] = str(p.pop("_id"))

        user = await db.users.find_one({"_id": p.get("user_id")})
        if not user:
            user = await db.users.find_one({"user_id": p.get("user_id")})

        p["email"] = user.get("email", "unknown") if user else "unknown"
        p["name"]  = user.get("name",  "unknown") if user else "unknown"

        results.append(p)

    return results