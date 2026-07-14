# rules/income_calculator.py
"""
Pure income calculation logic.
No DB calls here — yield_record and price_record are passed in
from the caller (profile_extractor.py fetches them from DB).
"""


def calculate_income(
    yield_t_per_ha:    float,
    land_size_ha:      float,
    avg_price_per_kg:  float,
) -> dict:
    """
    Calculate estimated income from yield and price data.

    Args:
        yield_t_per_ha:   tonnes per hectare for this crop+district
        land_size_ha:     farmer's land size in hectares
        avg_price_per_kg: average market price per kg for this crop+month

    Returns:
        dict with estimated_yield_kg and estimated_income_npr
    """
    estimated_yield_kg   = round(yield_t_per_ha * land_size_ha * 1000, 2)
    estimated_income_npr = round(estimated_yield_kg * avg_price_per_kg, 2)

    return {
        "estimated_yield_kg":    estimated_yield_kg,
        "estimated_income_npr":  estimated_income_npr,
        "income_price_per_kg":   avg_price_per_kg,
        "income_yield_t_per_ha": yield_t_per_ha,
    }


def can_estimate_income(profile: dict) -> tuple[bool, list[str]]:
    """
    Check if a profile has all required fields for income estimation.
    Returns (can_estimate: bool, missing_fields: list)
    """
    required = {
        "crop":               profile.get("crop"),
        "land_size_hectares": profile.get("land_size_hectares"),
        "district":           profile.get("district") or profile.get("location"),
        "farming_month":      profile.get("farming_month"),
    }
    missing = [field for field, value in required.items() if not value]
    return (len(missing) == 0, missing)