"""
KrishiMitra — Market Calendar: "what to harvest & sell this month", by month.

The chat router already answers ONE crop at a time — engine.crop_advisor.
harvest_facts() (crop -> harvest window) and engine.price_snapshot.
price_snapshot() (crop -> price). Neither answers the reverse question a
farmer actually asks: "given the month, which crops should I be harvesting
and selling for the best price?"

This module joins crop_calendar.csv's harvest-month windows with the Prophet
forecast cache (data/forecast_cache.csv) to build that reverse index: for a
BS month, every crop typically harvested THEN, ranked by that month's
forecasted DEMAND OPPORTUNITY SCORE (engine.market_analysis's spike/
volatility/trend formula) — not raw price. Ranking by raw price would let
rare high-value crops (avocado, asparagus) dominate every single month
regardless of season, exactly the trap that formula's own docstring warns
against; demand_score instead asks "is THIS month unusually good for THIS
crop", which is what "what should I harvest now" actually means.

Pure pandas, no DB, no LLM — the chat router only phrases these facts.
"""
from __future__ import annotations

import os
import functools
from typing import Optional

import pandas as pd

from engine.nepali_calendar import get_current_nepali_month
from engine.planting_filter import load_calendar, extract_all_planting_months, MONTH_ORDER
from engine.price_forecaster import run_all_forecasts, compute_forecasted_demand_scores
from rules.crop_normalizer import normalize_crop

_CACHE_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "forecast_cache.csv")


def _norm(name) -> str:
    return normalize_crop(str(name).replace("_", " "))


@functools.lru_cache(maxsize=1)
def _forecast_df() -> pd.DataFrame:
    """Forecast cache enriched with demand_score (per crop, per BS month) and
    the normalized join key. Reads run_all_forecasts()'s on-disk cache (never
    retrains here) then applies the same demand-score formula market_analysis/
    price_forecaster use for their own month rankings."""
    raw = run_all_forecasts()  # reads CACHE_PATH from disk; no-op if cached
    df = compute_forecasted_demand_scores(raw)
    df["_key"] = df["crop_key"].map(_norm)
    return df


@functools.lru_cache(maxsize=1)
def _harvest_month_index() -> dict[int, list[str]]:
    """BS month (1-12) -> normalized crop_keys typically harvested that month."""
    df = load_calendar()
    index: dict[int, list[str]] = {m: [] for m in range(1, 13)}
    for _, row in df.iterrows():
        key = _norm(row["crop_key"])
        for month_name in extract_all_planting_months(row["Typical Harvest Months (Nepali)"]):
            m = MONTH_ORDER.index(month_name) + 1
            index[m].append(key)
    return index


def refresh_cache() -> None:
    """Drop in-memory frames so the next read picks up a retrained forecast
    or an edited crop_calendar.csv. Call after POST /forecast/retrain."""
    _forecast_df.cache_clear()
    _harvest_month_index.cache_clear()


def crops_in_harvest_this_month(month: Optional[int] = None, top_n: int = 5) -> list[dict]:
    """Crops typically harvested in `month` (BS 1-12; current month if None),
    ranked by demand_score descending — how unusually good THIS month is for
    THAT crop's own price, not raw price level (see module docstring).

    Returns a list of {crop, month, month_name, price_avg, price_low,
    price_high, demand_score, trend_pct} — trend_pct is the forecast change
    into next month (None when the crop has no forecast row for it). Empty
    list when no calendar crop is harvested that month or the forecast cache
    lacks it.
    """
    if month is None:
        month = get_current_nepali_month()
    month = int(month)

    harvest_keys = set(_harvest_month_index().get(month, []))
    if not harvest_keys:
        return []

    fdf = _forecast_df()
    cur = fdf[(fdf["bs_month"] == month) & (fdf["_key"].isin(harvest_keys))].copy()
    if cur.empty:
        return []

    next_month = (month % 12) + 1
    nxt = fdf.loc[fdf["bs_month"] == next_month, ["_key", "forecasted_avg"]]
    nxt = nxt.rename(columns={"forecasted_avg": "next_avg"})
    cur = cur.merge(nxt, on="_key", how="left")
    cur["trend_pct"] = (
        (cur["next_avg"] - cur["forecasted_avg"]) / cur["forecasted_avg"] * 100
    ).round(1)

    cur = cur.sort_values("demand_score", ascending=False).head(top_n)

    rows = []
    for _, r in cur.iterrows():
        rows.append({
            "crop":         r["_key"],
            "month":        month,
            "month_name":   r["nepali_month"],
            "price_avg":    round(float(r["forecasted_avg"]), 1),
            "price_low":    round(float(r["forecasted_lower"]), 1),
            "price_high":   round(float(r["forecasted_upper"]), 1),
            "demand_score": round(float(r["demand_score"]), 4),
            "trend_pct":    None if pd.isna(r["trend_pct"]) else float(r["trend_pct"]),
        })
    return rows


def full_market_calendar(top_n: int = 5) -> dict[int, list[dict]]:
    """crops_in_harvest_this_month() for all 12 BS months — the Streamlit
    Market Analysis calendar view and any bulk API caller."""
    return {m: crops_in_harvest_this_month(month=m, top_n=top_n) for m in range(1, 13)}


def format_market_calendar_facts(rows: list[dict], month_name: str = "") -> str:
    """Compact DATA-block rendering for the chat LLM."""
    if not rows:
        return f"NO_DATA (no crops in harvest season for {month_name or 'this month'})"
    lines = [
        f"Crops ready to harvest & sell — {rows[0]['month_name']} "
        f"(Kalimati wholesale forecast, NPR/kg):"
    ]
    for i, r in enumerate(rows, 1):
        trend = ""
        if r["trend_pct"] is not None:
            direction = "up" if r["trend_pct"] > 0 else "down"
            trend = f", next month {direction} {abs(r['trend_pct'])}%"
        lines.append(
            f"{i}. {r['crop']}: avg {r['price_avg']} (range {r['price_low']}-{r['price_high']}){trend}"
        )
    return "\n".join(lines)
