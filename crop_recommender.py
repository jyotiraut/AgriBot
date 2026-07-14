"""
KrishiMitra - Crop Recommendation Model Wrapper
================================================
Wraps the trained XGBoost model (crop_recommendation_model.pkl) for use by:
  - check_crop_suitability_node  (Type B advisory graph)
  - run_notification_job         (Type B seasonal nudges)
  - /recommendations endpoint    (direct API call)

The model was trained on D1 (UCI crop dataset with NPK in mg/kg).
Nepal district data (D2) uses different units/scales, so we apply
CDF matching via two QuantileTransformers before inference.

Fallback: if the model or district data is not found, falls back to
the rule-based crop_suitability.py table. This means the system
always returns something useful.
"""
from __future__ import annotations

import logging
import pickle
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import xgboost  # Ensure xgboost is available for unpickling

logger = logging.getLogger(__name__)

# ── File paths ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
MODEL_PATH   = BASE_DIR / "models" / "crop_recommendation_model.pkl"
SCALER_PATH  = BASE_DIR / "crop_recommendation_scaler.pkl"

# ── Season → months mapping ───────────────────────────────────────────────
SEASONS: dict[str, list[int]] = {
    "Kharif": [6, 7, 8, 9, 10],
    "Rabi":   [11, 12, 1, 2, 3],
    "Spring": [3, 4, 5],
}

FEATURES = ["N", "P", "K", "ph", "temperature", "humidity", "rainfall"]

# ── Module-level cache (loaded once on first call) ────────────────────────
_model        = None
_label_encoder = None
_qt_d1        = None
_qt_d2        = None
_district_tables: dict[str, any] = {}   # season → DataFrame
_loaded       = False
_load_error   = None


def _load_artifacts() -> bool:
    """
    Load model, scalers, and district tables once.
    Returns True if successful, False if any artifact is missing.
    Sets _load_error with reason on failure.
    """
    global _model, _label_encoder, _qt_d1, _qt_d2, _district_tables, _loaded, _load_error

    if _loaded:
        return _load_error is None

    try:
        # Load model bundle
        if not MODEL_PATH.exists():
            _load_error = f"Model file not found: {MODEL_PATH}"
            logger.warning(_load_error)
            _loaded = True
            return False

        with open(MODEL_PATH, "rb") as f:
            bundle = pickle.load(f)

        # Support two save formats:
        # Format A: single dict with all components
        # Format B: just the XGBClassifier (scaler loaded separately)
        if isinstance(bundle, dict):
            _model         = bundle.get("model")
            _label_encoder = bundle.get("label_encoder")
            _qt_d1         = bundle.get("qt_d1")
            _qt_d2         = bundle.get("qt_d2")
            _district_tables = bundle.get("district_tables", {})
        else:
            # Format B — model only
            _model = bundle

        # Load scaler separately if not in bundle
        if _qt_d1 is None and SCALER_PATH.exists():
            with open(SCALER_PATH, "rb") as f:
                scaler_bundle = pickle.load(f)
            if isinstance(scaler_bundle, dict):
                _label_encoder   = scaler_bundle.get("label_encoder", _label_encoder)
                _qt_d1           = scaler_bundle.get("qt_d1")
                _qt_d2           = scaler_bundle.get("qt_d2")
                _district_tables = scaler_bundle.get("district_tables", _district_tables)
            else:
                # Plain scaler
                _qt_d1 = scaler_bundle

        if _model is None:
            _load_error = "Model object is None after loading"
            logger.error(_load_error)
            _loaded = True
            return False

        # Build district tables from CSV if not bundled
        if not _district_tables:
            _district_tables = _build_district_tables_from_csv()

        logger.info("Crop recommendation model loaded successfully")
        _loaded = True
        _load_error = None
        return True

    except Exception as e:
        _load_error = str(e)
        logger.exception("Failed to load crop recommendation model: %s", e)
        _loaded = True
        return False


def _build_district_tables_from_csv() -> dict:
    """
    Build district feature tables from the merged CSV if not bundled in pickle.
    Mirrors the logic from crop.ipynb.
    """
    import pandas as pd

    csv_path = BASE_DIR / "api" / "data" / "merged_all_districts_weather_soil.csv"
    if not csv_path.exists():
        logger.warning("District CSV not found at %s", csv_path)
        return {}

    try:
        df = pd.read_csv(csv_path, parse_dates=["Date"])
        df["month"] = df["Date"].dt.month

        def make_features(df_in, months):
            return (
                df_in[df_in["month"].isin(months)]
                .groupby("district")
                .agg(
                    N=("soil_nitrogen",   "first"),
                    P=("soil_phosphorus", "first"),
                    K=("soil_potassium",  "first"),
                    ph=("soil_ph",        "first"),
                    temperature=("T2M",       "mean"),
                    humidity=("RH2M",         "mean"),
                    rainfall=("PRECTOTCORR",  lambda x: x.mean() * len(months) * 30),
                )
                .reset_index()
            )

        tables = {s: make_features(df, m) for s, m in SEASONS.items()}
        logger.info("Built district tables from CSV: %d seasons", len(tables))
        return tables

    except Exception as e:
        logger.error("Failed to build district tables from CSV: %s", e)
        return {}


# ── Current season helper ─────────────────────────────────────────────────

def get_current_season(ref_date: Optional[date] = None, zone: str = "Terai") -> str:
    """Return the current growing season based on month and zone."""
    d = ref_date or date.today()
    m = d.month

    # Terai transitions slightly earlier than Hills
    kharif = [6, 7, 8, 9, 10]
    rabi   = [11, 12, 1, 2, 3]

    if zone == "Terai":
        # Terai Rabi starts October
        rabi = [10, 11, 12, 1, 2, 3]
        kharif = [6, 7, 8, 9]

    if m in kharif:
        return "Kharif"
    elif m in rabi:
        return "Rabi"
    else:
        return "Spring"


# ── Main prediction function ───────────────────────────────────────────────

def predict_crops(
    district: str,
    season: str,
    top_n: int = 5,
) -> list[dict]:
    """
    Predict best crops for a district and season using the trained XGBoost model.

    Args:
        district:  District name (case-insensitive, e.g. "chitwan")
        season:    "Kharif" | "Rabi" | "Spring"
        top_n:     Number of top crops to return

    Returns:
        List of dicts: [{"crop": str, "confidence": float, "source": "ml"}]
        Returns empty list if model not available — caller should use fallback.
    """
    # Normalise season capitalisation
    season = season.strip().title()
    if season not in SEASONS:
        # Try common aliases
        aliases = {
            "Monsoon": "Kharif", "Barkhe": "Kharif",
            "Winter": "Rabi", "Hiunde": "Rabi",
            "Summer": "Spring", "Grishma": "Spring",
        }
        season = aliases.get(season.title(), "Kharif")

    if not _load_artifacts():
        logger.warning("Model not available — returning empty (caller uses fallback)")
        return []

    # Get district feature row
    district_df = _district_tables.get(season)
    if district_df is None or district_df.empty:
        logger.warning("No district table for season=%s", season)
        return []

    row = district_df[district_df["district"].str.lower() == district.lower()]
    if row.empty:
        logger.warning("District '%s' not found in season table '%s'", district, season)
        return []

    try:
        X_raw = row[FEATURES].values  # D2 scale

        # CDF matching: D2 percentile → D1 equivalent
        if _qt_d1 is not None and _qt_d2 is not None:
            percentiles = _qt_d2.transform(X_raw)      # → [0,1]
            X_input = _qt_d1.inverse_transform(percentiles)  # → D1 space
        else:
            # No transformers — use raw (less accurate but won't crash)
            logger.warning("QuantileTransformers not loaded — using raw features")
            X_input = X_raw

        proba = _model.predict_proba(X_input)[0]
        top_idx = np.argsort(proba)[::-1][:top_n]

        if _label_encoder is not None:
            crop_names = [_label_encoder.inverse_transform([i])[0] for i in top_idx]
        else:
            crop_names = [str(i) for i in top_idx]

        return [
            {
                "crop":       crop_names[rank],
                "confidence": round(float(proba[top_idx[rank]]) * 100, 1),
                "source":     "ml",
                "district":   district,
                "season":     season,
            }
            for rank in range(len(top_idx))
        ]

    except Exception as e:
        logger.exception("predict_crops failed for district=%s season=%s: %s", district, season, e)
        return []


def predict_crops_with_fallback(
    district: str,
    season: str,
    zone: str,
    irrigation_access: str = "Rainfed",
    top_n: int = 5,
) -> list[dict]:
    """
    Try ML model first; fall back to rule-based suitability table if model unavailable
    or district not found.

    This is the function that should be called from LangGraph nodes and the
    notification scheduler — it always returns something.
    """
    results = predict_crops(district, season, top_n=top_n)

    if results:
        logger.info(
            "ML recommendation: district=%s season=%s → %s",
            district, season,
            [f"{r['crop']}({r['confidence']}%)" for r in results],
        )
        return results

    # Fallback to rule engine
    logger.info("ML fallback → using rule-based suitability for zone=%s season=%s", zone, season)
    try:
        from schemas.farmer import Zone, Season, IrrigationAccess
        from rules.crop_suitability import get_suitable_crops

        zone_enum     = Zone(zone)
        season_enum   = Season(season)
        irr_enum      = IrrigationAccess(irrigation_access)
        rule_crops    = get_suitable_crops(zone_enum, season_enum, irr_enum, top_n=top_n)

        return [
            {
                "crop":       c.name,
                "confidence": c.suitability_score,
                "source":     "rules",
                "district":   district,
                "season":     season,
            }
            for c in rule_crops
        ]
    except Exception as e:
        logger.error("Rule-based fallback also failed: %s", e)
        return []