"""
KrishiMitra - Crop Suitability Engine
Encodes Nepal MOALD Package of Practices + FAO Nepal crop calendars.

Lookup: (zone, season, irrigation_access) → list[CropOption]
Each CropOption carries market value tier, input cost, and suitability score.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from schemas.farmer import Zone, Season, IrrigationAccess


@dataclass
class CropOption:
    name: str
    variety_suggestions: List[str] = field(default_factory=list)
    market_value: str = "medium"          # low | medium | high | premium
    input_cost: str = "medium"            # low | medium | high
    water_requirement: str = "medium"     # low | medium | high
    suitability_score: int = 70   
    season: str = ""        # 0-100 rule-based score
    notes: str = ""
    


# ── Master suitability table ──────────────────────────────────────────────────
# Key: (Zone, Season, IrrigationAccess)
# Value: list of CropOption ordered by suitability_score desc

_TABLE: Dict[Tuple[Zone, Season, IrrigationAccess], List[CropOption]] = {

    # ═══════════════════════════════════════════════════════════════
    #  TERAI
    # ═══════════════════════════════════════════════════════════════
    (Zone.TERAI, Season.KHARIF, IrrigationAccess.RAINFED): [
        CropOption("Rice", ["Sabitri", "Hardinath-1", "Radha-4"],
                   market_value="medium", water_requirement="high",
                   suitability_score=90,
                   notes="Main Kharif crop for Terai rainfed; monsoon rains sufficient."),
        CropOption("Maize", ["Gaurav", "Rajkumar", "Pool-2"],
                   market_value="medium", input_cost="low",
                   water_requirement="medium", suitability_score=80),
        CropOption("Jute", ["JRO-524"], market_value="medium",
                   water_requirement="high", suitability_score=70),
        CropOption("Black-eyed Pea", [],
                   market_value="medium", input_cost="low",
                   water_requirement="low", suitability_score=65,
                   notes="Good fallback legume; improves soil nitrogen."),
    ],
    (Zone.TERAI, Season.KHARIF, IrrigationAccess.PARTIAL): [
        CropOption("Rice", ["Sabitri", "Radha-4", "Sukha Dhan 3"],
                   market_value="medium", suitability_score=92),
        CropOption("Maize", ["Pool-2", "Rajkumar"], suitability_score=85),
        CropOption("Sugarcane", ["Co-0238"], market_value="medium",
                   input_cost="high", water_requirement="high",
                   suitability_score=78),
        CropOption("Cucumber", ["Malini"], market_value="high",
                   suitability_score=75,
                   notes="High value; needs trellis and regular irrigation."),
    ],
    (Zone.TERAI, Season.KHARIF, IrrigationAccess.FULL): [
        CropOption("Rice", ["Super Basmati", "Samba Masuri"],
                   market_value="high", suitability_score=95),
        CropOption("Sugarcane", [], market_value="medium",
                   input_cost="high", suitability_score=88),
        CropOption("Okra", ["Arka Anamika"], market_value="high",
                   suitability_score=82),
        CropOption("Bitter Gourd", [], market_value="high",
                   suitability_score=80),
        CropOption("Maize Hybrid", ["P3401", "DK9108"],
                   market_value="medium", suitability_score=78),
    ],
    (Zone.TERAI, Season.RABI, IrrigationAccess.RAINFED): [
        CropOption("Lentil", ["Simal", "Khajura-2"], market_value="high",
                   input_cost="low", water_requirement="low",
                   suitability_score=88,
                   notes="Good for residual soil moisture after rice."),
        CropOption("Mustard", ["Pusa Bold"], market_value="medium",
                   input_cost="low", water_requirement="low",
                   suitability_score=84),
        CropOption("Chickpea", ["Avarodhi", "ICCC-37"],
                   market_value="high", input_cost="low",
                   water_requirement="low", suitability_score=78),
    ],
    (Zone.TERAI, Season.RABI, IrrigationAccess.PARTIAL): [
        CropOption("Wheat", ["NL-297", "Gautam", "Bhrikuti"],
                   market_value="medium", suitability_score=92),
        CropOption("Lentil", ["Simal"], market_value="high",
                   suitability_score=85),
        CropOption("Mustard", ["Pusa Bold"], suitability_score=82),
        CropOption("Potato", ["Kufri Sinduri", "Desiree"],
                   market_value="medium", input_cost="high",
                   suitability_score=78),
    ],
    (Zone.TERAI, Season.RABI, IrrigationAccess.FULL): [
        CropOption("Wheat", ["WK-1204", "Bhrikuti"], suitability_score=95),
        CropOption("Potato", ["Desiree", "Atlantic"],
                   market_value="high", suitability_score=90),
        CropOption("Tomato", ["Lapsigede", "Moneymaker"],
                   market_value="high", input_cost="high",
                   suitability_score=88),
        CropOption("Onion", ["Nasik Red", "Arka Kalyan"],
                   market_value="high", suitability_score=85),
        CropOption("Garlic", ["Janak"],
                   market_value="premium", suitability_score=82),
    ],
    (Zone.TERAI, Season.SPRING, IrrigationAccess.FULL): [
        CropOption("Maize Hybrid", ["DK9108", "P3401"],
                   market_value="medium", suitability_score=88),
        CropOption("Summer Vegetables", ["Bitter Gourd", "Ridge Gourd", "Sponge Gourd"],
                   market_value="high", suitability_score=85),
        CropOption("Mung Bean", ["Pratiksha"],
                   market_value="high", input_cost="low",
                   suitability_score=80),
    ],

    # ═══════════════════════════════════════════════════════════════
    #  HILLS
    # ═══════════════════════════════════════════════════════════════
    (Zone.HILLS, Season.KHARIF, IrrigationAccess.RAINFED): [
        CropOption("Maize", ["Deuti", "Across 8528"],
                   market_value="medium", input_cost="low",
                   suitability_score=90,
                   notes="Primary Hills kharif staple; intercrop with legumes."),
        CropOption("Finger Millet", ["Kabre Kodo-2"],
                   market_value="medium", input_cost="low",
                   water_requirement="low", suitability_score=85,
                   notes="Drought-tolerant; high nutritional value."),
        CropOption("Soybean", ["Puja", "Harit Soybean"],
                   market_value="high", input_cost="low",
                   suitability_score=78),
        CropOption("Upland Rice", ["Chhomrong Dhan"],
                   market_value="medium", suitability_score=72),
    ],
    (Zone.HILLS, Season.KHARIF, IrrigationAccess.PARTIAL): [
        CropOption("Maize", ["Pool-2", "Deuti"], suitability_score=88),
        CropOption("Vegetable Beans", ["Dhapase Simi"], market_value="high",
                   suitability_score=82),
        CropOption("Tomato", ["Lapsigede"],
                   market_value="high", input_cost="high",
                   suitability_score=78),
        CropOption("Cucumber", [], market_value="high", suitability_score=75),
    ],
    (Zone.HILLS, Season.RABI, IrrigationAccess.RAINFED): [
        CropOption("Wheat", ["NL-297", "Bhirkuti"],
                   market_value="medium", suitability_score=85),
        CropOption("Barley", ["Solu Uwa"],
                   market_value="medium", input_cost="low",
                   water_requirement="low", suitability_score=80),
        CropOption("Pea", ["Arkel", "Bonville"],
                   market_value="high", suitability_score=78),
        CropOption("Mustard", ["Pusa Bold"],
                   market_value="medium", suitability_score=75),
    ],
    (Zone.HILLS, Season.RABI, IrrigationAccess.FULL): [
        CropOption("Potato", ["Kufri Jyoti", "Desiree"],
                   market_value="medium", suitability_score=92,
                   notes="Most profitable Hills rabi crop with irrigation."),
        CropOption("Cauliflower", ["Snow Ball-16"],
                   market_value="high", suitability_score=88),
        CropOption("Cabbage", ["Green Corona"],
                   market_value="high", suitability_score=85),
        CropOption("Garlic", ["Janak"],
                   market_value="premium", suitability_score=82),
        CropOption("Wheat", ["NL-297"], suitability_score=80),
    ],
    (Zone.HILLS, Season.SPRING, IrrigationAccess.PARTIAL): [
        CropOption("Maize", ["Pool-2"], suitability_score=82),
        CropOption("Summer Vegetables", ["Bottle Gourd", "Pumpkin"],
                   market_value="high", suitability_score=78),
        CropOption("Soybean", ["Harit"], suitability_score=75),
    ],

    # ═══════════════════════════════════════════════════════════════
    #  MOUNTAINS
    # ═══════════════════════════════════════════════════════════════
    (Zone.MOUNTAINS, Season.SPRING, IrrigationAccess.RAINFED): [
        CropOption("Potato", ["Kufri Himalini", "Cardinal"],
                   market_value="medium", suitability_score=92,
                   notes="Primary mountain spring staple."),
        CropOption("Buckwheat", ["FB-9"],
                   market_value="medium", input_cost="low",
                   water_requirement="low", suitability_score=85),
        CropOption("Peas", ["Arkel"],
                   market_value="high", suitability_score=80),
    ],
    (Zone.MOUNTAINS, Season.SPRING, IrrigationAccess.PARTIAL): [
        CropOption("Potato", ["Kufri Himalini"],
                   suitability_score=95),
        CropOption("Barley", ["Solu Uwa"],
                   suitability_score=85),
        CropOption("Medicinal Herbs", ["Yarshagumba, Timur, Jatamansi"],
                   market_value="premium", input_cost="low",
                   suitability_score=80,
                   notes="High value but requires technical knowledge."),
    ],
    (Zone.MOUNTAINS, Season.RABI, IrrigationAccess.RAINFED): [
        CropOption("Barley", ["Solu Uwa", "NB-1141"],
                   market_value="medium", input_cost="low",
                   suitability_score=82),
        CropOption("Buckwheat", [], suitability_score=75),
    ],
}


def get_suitable_crops(
    zone: Zone,
    season: Season,
    irrigation: IrrigationAccess,
    market_preference: str | None = None,
    top_n: int = 5,
) -> List[CropOption]:
    """
    Return ranked crop options for given agronomic context.

    Fallback cascade:
      (zone, season, irrigation) → (zone, season, RAINFED) → top generic zone crops
    """
    key = (zone, season, irrigation)
    crops = _TABLE.get(key)

    if not crops:
        # Cascade down to rainfed
        fallback_key = (zone, season, IrrigationAccess.RAINFED)
        crops = _TABLE.get(fallback_key, [])

    # Filter by market preference keyword if provided
    if market_preference:
        pref_lower = market_preference.lower()
        high_value_terms = {"high value", "premium", "vegetable", "export"}
        prefer_high = any(t in pref_lower for t in high_value_terms)
        if prefer_high:
            # Boost score for high/premium market value crops
            crops = sorted(
                crops,
                key=lambda c: (
                    c.suitability_score + (20 if c.market_value in ("high", "premium") else 0)
                ),
                reverse=True,
            )

    return sorted(crops, key=lambda c: c.suitability_score, reverse=True)[:top_n]


def crop_is_suitable_for_zone(crop_name: str, zone: Zone) -> bool:
    """Quick check: is a given crop known for a zone at all?"""
    for (z, _s, _i), options in _TABLE.items():
        if z == zone:
            for opt in options:
                if opt.name.lower() == crop_name.lower():
                    return True
    return False