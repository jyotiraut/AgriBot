"""
KrishiMitra - DAS / GDD Growth Stage Calculator

DAS  = Days After Sowing  (simple calendar arithmetic)
GDD  = Growing Degree Days (accumulated heat units above base temperature)

GDD  = Σ max(0,  (T_max + T_min) / 2 - T_base)

Growth stage thresholds sourced from MOALD Package of Practices Nepal
and FAO Nepal crop calendars.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Dict, Optional


@dataclass
class GrowthStage:
    name: str
    das_start: int
    das_end: int
    gdd_start: float
    gdd_end: float
    key_activities: List[str]
    advisory_focus: str


# ── Per-crop growth stage tables ─────────────────────────────────────────────

CROP_STAGES: Dict[str, List[GrowthStage]] = {

    "Rice": [
        GrowthStage("Germination / Emergence", 0, 10, 0, 80,
                    ["Ensure standing water 2–5 cm", "Check seedling uniformity"],
                    "Maintain water level; watch for damping off."),
        GrowthStage("Seedling / Tillering", 10, 45, 80, 400,
                    ["Apply basal fertilizer (DAP + MOP)", "First weeding",
                     "Transplant if direct-seeded skipped"],
                    "Tillering is critical for yield formation; avoid water stress."),
        GrowthStage("Panicle Initiation", 45, 65, 400, 600,
                    ["Top-dress Urea (split)", "Monitor for stem borer",
                     "Blast disease scouting"],
                    "Most sensitive stage; protect from neck blast and stem borer."),
        GrowthStage("Heading / Flowering", 65, 80, 600, 750,
                    ["Maintain water", "Scout for BPH and sheath blight",
                     "Avoid pesticide during anthesis"],
                    "Protect grain filling; do not apply pesticides during flowering."),
        GrowthStage("Grain Filling / Ripening", 80, 115, 750, 1100,
                    ["Allow field to dry 10 days before harvest",
                     "Scout for false smut", "Arrange thresher"],
                    "Monitor moisture; target 20–22% grain moisture at harvest."),
        GrowthStage("Harvest", 115, 135, 1100, 1300,
                    ["Harvest at golden-yellow stage", "Thresh within 48 h",
                     "Dry to <14% moisture for storage"],
                    "Timely harvest prevents shattering losses."),
    ],

    "Maize": [
        GrowthStage("Germination", 0, 7, 0, 60,
                    ["Ensure 5–7 cm planting depth", "Pre-emergence weed control"],
                    "Soil temperature > 12°C needed; avoid waterlogging."),
        GrowthStage("Seedling (V1–V6)", 7, 30, 60, 350,
                    ["Thin to 1 plant per hill", "First fertilizer application (N+P)",
                     "Scout for cutworm"],
                    "Establish plant population; control early weeds."),
        GrowthStage("Vegetative (V6–V12)", 30, 55, 350, 700,
                    ["Side-dress Urea", "Earthing-up", "Monitor for FAW"],
                    "Fall Army Worm is the key threat; scout whorls daily."),
        GrowthStage("Tasseling / Silking (VT–R1)", 55, 70, 700, 900,
                    ["Ensure adequate moisture", "Do not spray during pollen shed",
                     "Last Urea split"],
                    "Pollination window — avoid stress and foliar sprays."),
        GrowthStage("Grain Fill (R2–R6)", 70, 110, 900, 1400,
                    ["Maintain moisture", "Scout for ear rot", "Monitor ear development"],
                    "Protect kernel weight; brace root lodging watch."),
        GrowthStage("Maturity / Harvest", 110, 125, 1400, 1600,
                    ["Harvest at black-layer stage (32–35% moisture for wet)",
                     "Or dry-harvest at 14% moisture"],
                    "Avoid late harvest; aflatoxin risk rises with wet weather."),
    ],

    "Wheat": [
        GrowthStage("Germination", 0, 7, 0, 80,
                    ["Ensure 5 cm seed depth", "Irrigation if dry"],
                    "Adequate moisture critical for uniform germination."),
        GrowthStage("Tillering (Zadoks 2x)", 7, 35, 80, 450,
                    ["Crown root irrigation", "Apply DAP + half Urea",
                     "Broadleaf weed control"],
                    "Tillering determines final ear count."),
        GrowthStage("Stem Extension / Jointing (Zadoks 3x)", 35, 60, 450, 750,
                    ["Second Urea split", "Scout for yellow rust",
                     "Aphid monitoring starts"],
                    "Yellow rust is the biggest biotic threat in Nepal hills."),
        GrowthStage("Heading / Anthesis (Zadoks 5x–6x)", 60, 75, 750, 950,
                    ["Flag leaf protection spray if rust evident",
                     "Maintain soil moisture"],
                    "Protect flag leaf — it contributes ~40% to grain weight."),
        GrowthStage("Grain Filling (Zadoks 7x–8x)", 75, 100, 950, 1250,
                    ["Terminal irrigation if dry", "Monitor Karnal bunt"],
                    "Avoid lodging; monitor for heat or drought stress."),
        GrowthStage("Ripening / Harvest", 100, 115, 1250, 1450,
                    ["Harvest when grain is hard (< 14% moisture)",
                     "Avoid wet harvest — fusarium risk"],
                    "Timely harvest critical in hills before late rains."),
    ],

    "Potato": [
        GrowthStage("Sprouting / Emergence", 0, 20, 0, 100,
                    ["Ensure 8–10 cm hilling", "Pre-emergence herbicide optional"],
                    "Cool soil (10–20°C) promotes uniform emergence."),
        GrowthStage("Vegetative Growth", 20, 50, 100, 400,
                    ["First earthing-up", "Apply NPK fertilizer",
                     "Scout for early blight"],
                    "Establish canopy quickly; earthing prevents greening."),
        GrowthStage("Tuber Initiation", 50, 70, 400, 650,
                    ["Critical irrigation", "Scout for late blight (Phytophthora)",
                     "Second earthing-up"],
                    "Late blight is the #1 risk; spray preventively in humid weather."),
        GrowthStage("Tuber Bulking", 70, 100, 650, 900,
                    ["Maintain steady moisture", "Late blight management continues",
                     "Avoid excess nitrogen"],
                    "Consistent water drives yield; assess bulking by test dig."),
        GrowthStage("Maturation", 100, 120, 900, 1100,
                    ["Stop irrigation 2 weeks before harvest", "Desiccate haulm",
                     "Allow skin set"],
                    "Skin set reduces bruising and storage losses."),
        GrowthStage("Harvest", 120, 130, 1100, 1200,
                    ["Harvest on a dry day", "Cure in shade for 5–7 days",
                     "Store at 4–10°C if possible"],
                    "Handle tubers gently; bruising causes storage rot."),
    ],

    "Mustard": [
        GrowthStage("Germination", 0, 7, 0, 60,
                    ["Shallow 1–2 cm sowing", "Ensure firm seedbed"],
                    "Rapid germination expected; thin to 15 cm within 10 days."),
        GrowthStage("Rosette / Vegetative", 7, 30, 60, 250,
                    ["Thinning", "Urea top-dress", "Aphid monitoring"],
                    "Mustard aphid peaks during cool, dry weather."),
        GrowthStage("Flowering", 30, 55, 250, 550,
                    ["Ensure pollinator access", "Avoid insecticide during bloom",
                     "Powdery mildew scouting"],
                    "Bees are critical pollinators; no insecticides in flower."),
        GrowthStage("Pod Fill / Ripening", 55, 90, 550, 850,
                    ["Scout for Alternaria pod disease",
                     "Allow pods to turn yellow-brown"],
                    "Harvest before shattering; early morning harvest reduces losses."),
    ],

    "Lentil": [
        GrowthStage("Germination", 0, 10, 0, 70,
                    ["Rhizobium seed treatment", "Light irrigation if dry"],
                    "Inoculation boosts N-fixation by 30%."),
        GrowthStage("Vegetative", 10, 40, 70, 300,
                    ["Weed control (critical window)", "Phosphorus top-dress"],
                    "Lentil is highly weed-sensitive in early vegetative stage."),
        GrowthStage("Flowering / Podding", 40, 70, 300, 600,
                    ["Aphid and thrip monitoring", "Avoid waterlogging"],
                    "Cool temperatures favour pod set."),
        GrowthStage("Maturity", 70, 95, 600, 850,
                    ["Harvest when 70% pods brown", "Early morning harvest"],
                    "Over-ripening causes shattering; harvest promptly."),
    ],
}

# Default fallback for unrecognized crops
_DEFAULT_STAGES = [
    GrowthStage("Early Growth", 0, 30, 0, 300,
                ["Apply basal fertilizer", "Weed control"],
                "Establish crop; manage weeds early."),
    GrowthStage("Mid Season", 30, 75, 300, 700,
                ["Top-dress nitrogen", "Scout for pests"],
                "Peak growth period; protect from major pests."),
    GrowthStage("Late Season / Harvest", 75, 120, 700, 1100,
                ["Reduce irrigation", "Prepare for harvest"],
                "Allow maturity; plan harvest logistics."),
]


def calculate_das(sowing_date: date, reference_date: Optional[date] = None) -> int:
    """Days After Sowing as of reference_date (default: today)."""
    ref = reference_date or date.today()
    das = (ref - sowing_date).days
    return max(0, das)


def estimate_gdd(
    sowing_date: date,
    avg_tmax: float,
    avg_tmin: float,
    base_temp: float = 10.0,
    reference_date: Optional[date] = None,
) -> float:
    """
    Estimate cumulative GDD using a constant average T_max / T_min
    (a simplified version; Phase 2 will pull real daily temps from Open-Meteo).

    Formula: GDD_daily = max(0, (T_max + T_min) / 2 - T_base)
    """
    das = calculate_das(sowing_date, reference_date)
    gdd_per_day = max(0.0, (avg_tmax + avg_tmin) / 2.0 - base_temp)
    return round(gdd_per_day * das, 1)


def get_growth_stage(
    crop: str,
    das: int,
    gdd: Optional[float] = None,
) -> GrowthStage:
    """
    Return the current growth stage for a crop given DAS (and optionally GDD).
    GDD is preferred when available; DAS is the fallback.
    """
    crop_title = crop.strip().title()
    stages = CROP_STAGES.get(crop_title, _DEFAULT_STAGES)

    if gdd is not None:
        # GDD-based lookup
        for stage in stages:
            if stage.gdd_start <= gdd < stage.gdd_end:
                return stage
        # GDD past all stages → last stage
        return stages[-1]

    # DAS-based lookup
    for stage in stages:
        if stage.das_start <= das < stage.das_end:
            return stage
    return stages[-1]


def get_zone_temperature_defaults(zone_name: str) -> Dict[str, float]:
    """
    Return climatological average T_max and T_min for GDD estimation
    when real weather data is not available (Phase 1 fallback).
    Phase 2 will replace this with Open-Meteo API values.
    """
    defaults = {
        "Terai":     {"avg_tmax": 32.0, "avg_tmin": 22.0},
        "Hills":     {"avg_tmax": 25.0, "avg_tmin": 14.0},
        "Mountains": {"avg_tmax": 15.0, "avg_tmin": 5.0},
    }
    return defaults.get(zone_name, {"avg_tmax": 28.0, "avg_tmin": 18.0})