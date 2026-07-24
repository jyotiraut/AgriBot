"""
KrishiMitra — price facts from the pre-computed Prophet forecast cache.

Reads data/forecast_cache.csv (written by engine.price_forecaster's
run_all_forecasts, refreshed out-of-band via POST /forecast/retrain — never
trains Prophet in the request path). Pure pandas, no DB, fully unit-testable.

Prices are Kalimati wholesale forecasts; answers should say "as per Kalimati
market" (the price_info task instruction enforces this).
"""
from __future__ import annotations

import os
import functools
from typing import Optional

import pandas as pd

from engine.nepali_calendar import get_current_nepali_month
from rules.crop_normalizer import normalize_crop, fuzzy_match_crop

_CACHE_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "forecast_cache.csv")


def _norm(name) -> str:
    return normalize_crop(str(name).replace("_", " "))


@functools.lru_cache(maxsize=1)
def _forecast_df() -> pd.DataFrame:
    df = pd.read_csv(_CACHE_CSV)
    df["_key"] = df["crop_key"].map(_norm)
    return df


def refresh_cache() -> None:
    """Drop the in-memory frame so the next read picks up a retrained CSV.
    Call after POST /forecast/retrain rewrites forecast_cache.csv."""
    _forecast_df.cache_clear()


def price_snapshot(crop: str, month: Optional[int] = None) -> dict:
    """Forecast price facts for one crop.

    Returns {crop, month, month_name, price_avg, price_low, price_high,
             next_month_avg, trend_pct, peak_month_name, peak_avg}
    or {} when the crop isn't in the forecast cache.

    month: BS month 1-12 (None = current). trend_pct is the change from this
    month's forecast to next month's.
    """
    if month is None:
        month = get_current_nepali_month()
    month = int(month)

    df = _forecast_df()
    key = _norm(crop)
    rows = df[df["_key"] == key]
    if rows.empty:
        match = fuzzy_match_crop(crop, df["_key"].unique())
        if match:
            key = match
            rows = df[df["_key"] == key]
    if rows.empty:
        return {}

    def _month_row(m):
        r = rows[rows["bs_month"] == m]
        return r.iloc[0] if not r.empty else None

    cur = _month_row(month)
    if cur is None:
        return {}
    nxt = _month_row((month % 12) + 1)
    peak = rows.loc[rows["forecasted_avg"].idxmax()]

    facts = {
        "crop":            key,
        "month":           month,
        "month_name":      cur["nepali_month"],
        "price_avg":       round(float(cur["forecasted_avg"]), 1),
        "price_low":       round(float(cur["forecasted_lower"]), 1),
        "price_high":      round(float(cur["forecasted_upper"]), 1),
        "peak_month_name": peak["nepali_month"],
        "peak_avg":        round(float(peak["forecasted_avg"]), 1),
    }
    if nxt is not None and float(cur["forecasted_avg"]) > 0:
        nxt_avg = float(nxt["forecasted_avg"])
        facts["next_month_avg"] = round(nxt_avg, 1)
        facts["trend_pct"] = round(
            (nxt_avg - float(cur["forecasted_avg"])) / float(cur["forecasted_avg"]) * 100, 1
        )
    return facts


def format_price_facts(facts: dict) -> str:
    """Compact DATA-block rendering of price_snapshot for the chat LLM."""
    if not facts:
        return "NO_DATA (crop not in price forecast)"
    lines = [
        f"Crop: {facts['crop']} (Kalimati wholesale forecast, NPR/kg)",
        f"{facts['month_name']}: avg {facts['price_avg']} (range {facts['price_low']}-{facts['price_high']})",
    ]
    if facts.get("trend_pct") is not None:
        direction = "up" if facts["trend_pct"] > 0 else "down"
        lines.append(f"Next month: {facts['next_month_avg']} ({direction} {abs(facts['trend_pct'])}%)")
    lines.append(f"Best price month: {facts['peak_month_name']} (avg {facts['peak_avg']})")
    return "\n".join(lines)
