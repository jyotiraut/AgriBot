"""
KrishiMitra — Combined district-accurate crop recommender.

Merges three data sources into one ranked recommendation:
  1. 90-crop seasonal calendar  → season + altitude fit  (engine.planting_filter)
  2. curated agronomic table     → varieties + market tier (rules.crop_suitability)
  3. crop risk sheet             → risk tier + price volatility (data/crop_risks.csv)

This is the single function the chat intent-router should call for
"what should I plant in <district> now". It returns STRUCTURED FACTS the LLM
only phrases — it never invents numbers.

Pure and synchronous (reads CSVs, no DB, no LLM), so it is fully unit-testable
offline. Live market PRICE is intentionally left as an extension point: those
come from the market feed / price_forecaster and are joined by the router at
answer time, with an "as of <date>" stamp.
"""
from __future__ import annotations

import os
import re
import functools
from typing import Optional

import pandas as pd

from engine.planting_filter import get_crops_for_location
from engine.nepali_calendar import get_current_nepali_month
from rules.crop_normalizer import normalize_crop
from rules.zone_classifier import classify_zone, month_to_season
from rules.crop_suitability import get_suitable_crops
from schemas.farmer import Zone, Season, IrrigationAccess


_RISK_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "crop_risks.csv")

# Farmer-reported irrigation string → curated table's IrrigationAccess enum.
_IRR_MAP = {
    "rainfed":   IrrigationAccess.RAINFED,
    "canal":     IrrigationAccess.FULL,
    "pump":      IrrigationAccess.FULL,
    "drip":      IrrigationAccess.FULL,
    "sprinkler": IrrigationAccess.PARTIAL,
}

_MARKET_RANK = {"premium": 3, "high": 2, "medium": 1, "low": 0}


# ── small helpers ─────────────────────────────────────────────────────────────

def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm(name) -> str:
    """Normalise a crop identifier for joining: underscores→spaces, lowercased.
    Makes calendar keys ('finger_millet') match curated names ('Finger Millet')."""
    return normalize_crop(str(name).replace("_", " "))


def _first_int(v) -> int:
    """First integer in a messy cell, e.g. '30–60 (fresh); 180+' → 30."""
    nums = re.findall(r"\d+", str(v))
    return int(nums[0]) if nums else 0


@functools.lru_cache(maxsize=1)
def _risk_lookup() -> dict:
    """crop_key → {risk_tier, risk_score, price_volatility} from crop_risks.csv."""
    df = pd.read_csv(_RISK_CSV)
    out = {}
    for _, r in df.iterrows():
        out[str(r["crop_key"]).strip().lower()] = {
            "risk_tier":        r.get("risk_tier"),
            "risk_score":       _to_float(r.get("composite_risk_score_1to5")),
            "price_volatility": _to_float(r.get("market_price_volatility_1to5")),
        }
    return out


def _zone_enum(value) -> Optional[Zone]:
    """Accept a Zone, or a zone NAME ('Terai'/'hills'/...). Returns None if the
    value is not a zone name (e.g. it's a district) so the caller can classify."""
    if isinstance(value, Zone):
        return value
    try:
        return Zone(str(value).strip().capitalize())
    except ValueError:
        return None


def _curated_lookup(zone_enum, season_enum, irrigation) -> dict:
    """_norm(name) → CropOption from the curated suitability table. Best-effort:
    returns {} when the (zone, season, irrigation) cell is empty or inputs are
    unknown — enrichment is optional, never fatal."""
    if zone_enum is None or season_enum is None:
        return {}
    irr = _IRR_MAP.get((irrigation or "").strip().lower(), IrrigationAccess.PARTIAL)
    try:
        opts = get_suitable_crops(zone_enum, season_enum, irr, top_n=50)
    except Exception:
        return {}
    return {_norm(o.name): o for o in opts}


def _rank_key(c: dict):
    """Transparent, tunable ranking: higher market value first, then LOWER risk,
    then longer storage life. Unknown values sort to the neutral middle."""
    market = _MARKET_RANK.get((c.get("market_value") or "").lower(), 0)
    risk = c.get("risk_score")
    risk_inv = (6 - risk) if isinstance(risk, (int, float)) else 3   # lower risk → higher rank
    return (market, risk_inv, _first_int(c.get("storage_shelf_life")))


# ── public API ────────────────────────────────────────────────────────────────

def recommend_crops(
    district: str,
    month: Optional[int] = None,
    irrigation: Optional[str] = None,
    top_n: int = 8,
) -> list[dict]:
    """District-accurate, ranked planting recommendation.

    Args:
        district:   farmer district (mapped to zone), OR a zone name directly.
        month:      Bikram Sambat month 1-12 (None = current month).
        irrigation: 'rainfed|canal|pump|drip|sprinkler' — optional; improves the
                    curated variety/market match.
        top_n:      max crops to return.

    Returns a list of fact dicts for crops that are IN SEASON and ALTITUDE-FIT
    for the district, each enriched with harvest window, growth weeks, water
    need, storage life, risk tier + score, price volatility, and (when the
    curated table covers it) recommended varieties + market value. Ranked by
    _rank_key. Empty list if the zone/month yields nothing.
    """
    if month is None:
        month = get_current_nepali_month()

    zone_enum = _zone_enum(district) or classify_zone(district)
    zone_name = zone_enum.value if zone_enum else None

    season_str  = month_to_season(month)
    season_enum = Season(season_str) if season_str else None

    candidates = get_crops_for_location(zone_name, month=month) if zone_name else []
    risks   = _risk_lookup()
    curated = _curated_lookup(zone_enum, season_enum, irrigation)

    enriched = []
    for c in candidates:
        key  = str(c["crop_key"]).strip().lower()
        risk = risks.get(key, {})
        opt  = curated.get(_norm(key))
        enriched.append({
            "crop_key":           c["crop_key"],
            "crop_name":          c["crop_name"],
            "planting_status":    c["planting_status"],
            "harvest_months":     c["harvest_months"],
            "growth_weeks_min":   c["growth_weeks_min"],
            "growth_weeks_max":   c["growth_weeks_max"],
            "water_requirement":  c["water_requirement"],
            "storage_shelf_life": c["storage_shelf_life"],
            "altitude_suitable":  c["altitude_suitable"],
            "risk_tier":          risk.get("risk_tier"),
            "risk_score":         risk.get("risk_score"),
            "price_volatility":   risk.get("price_volatility"),
            "market_value":       opt.market_value if opt else None,
            "varieties":          list(opt.variety_suggestions) if opt else [],
        })

    enriched.sort(key=_rank_key, reverse=True)
    return enriched[:top_n]
