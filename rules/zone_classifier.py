"""
KrishiMitra - Zone Classifier
Maps every Nepal district to Terai / Hills / Mountains.

Source: Nepal's agro-ecological zone classification (MOALD / FAO Nepal).
"""
from typing import Dict, Optional
from schemas.farmer import Zone


# ── Nepal district → agro-ecological zone mapping ──────────────────────────
# 77 districts of Nepal (post-2015 restructuring)

DISTRICT_ZONE_MAP: Dict[str, Zone] = {
    # ── TERAI / MADHESH ──────────────────────────────────────────────────
    "Jhapa":             Zone.TERAI,
    "Morang":            Zone.TERAI,
    "Sunsari":           Zone.TERAI,
    "Saptari":           Zone.TERAI,
    "Siraha":            Zone.TERAI,
    "Dhanusha":          Zone.TERAI,
    "Mahottari":         Zone.TERAI,
    "Sarlahi":           Zone.TERAI,
    "Rautahat":          Zone.TERAI,
    "Bara":              Zone.TERAI,
    "Parsa":             Zone.TERAI,
    "Chitwan":           Zone.TERAI,
    "Nawalpur":          Zone.TERAI,
    "Rupandehi":         Zone.TERAI,
    "Kapilvastu":        Zone.TERAI,
    "Arghakhanchi":      Zone.HILLS,   # transition but classified Hills
    "Nawalparasi East":  Zone.TERAI,
    "Nawalparasi West":  Zone.TERAI,
    "Dang":              Zone.TERAI,
    "Banke":             Zone.TERAI,
    "Bardiya":           Zone.TERAI,
    "Surkhet":           Zone.HILLS,   # Surkhet valley – classified Hills
    "Kailali":           Zone.TERAI,
    "Kanchanpur":        Zone.TERAI,

    # ── HILLS ────────────────────────────────────────────────────────────
    "Ilam":              Zone.HILLS,
    "Taplejung":         Zone.HILLS,
    "Panchthar":         Zone.HILLS,
    "Terhathum":         Zone.HILLS,
    "Dhankuta":          Zone.HILLS,
    "Bhojpur":           Zone.HILLS,
    "Sankhuwasabha":     Zone.HILLS,
    "Khotang":           Zone.HILLS,
    "Okhaldhunga":       Zone.HILLS,
    "Solukhumbu":        Zone.MOUNTAINS,
    "Udayapur":          Zone.HILLS,
    "Sindhuli":          Zone.HILLS,
    "Ramechhap":         Zone.HILLS,
    "Dolakha":           Zone.HILLS,
    "Sindhupalchok":     Zone.HILLS,
    "Kavrepalanchok":    Zone.HILLS,
    "Bhaktapur":         Zone.HILLS,
    "Kathmandu":         Zone.HILLS,
    "Lalitpur":          Zone.HILLS,
    "Makwanpur":         Zone.HILLS,
    "Nuwakot":           Zone.HILLS,
    "Rasuwa":            Zone.MOUNTAINS,
    "Dhading":           Zone.HILLS,
    "Gorkha":            Zone.HILLS,
    "Lamjung":           Zone.HILLS,
    "Tanahun":           Zone.HILLS,
    "Syangja":           Zone.HILLS,
    "Kaski":             Zone.HILLS,
    "Parbat":            Zone.HILLS,
    "Myagdi":            Zone.HILLS,
    "Baglung":           Zone.HILLS,
    "Gulmi":             Zone.HILLS,
    "Palpa":             Zone.HILLS,
    "Pyuthan":           Zone.HILLS,
    "Rolpa":             Zone.HILLS,
    "Rukum East":        Zone.HILLS,
    "Salyan":            Zone.HILLS,
    "Jajarkot":          Zone.HILLS,
    "Dailekh":           Zone.HILLS,
    "Achham":            Zone.HILLS,
    "Doti":              Zone.HILLS,
    "Baitadi":           Zone.HILLS,
    "Dadeldhura":        Zone.HILLS,
    "Bajhang":           Zone.HILLS,
    "Bajura":            Zone.HILLS,

    # ── MOUNTAINS (High Himal) ────────────────────────────────────────────
    "Manang":            Zone.MOUNTAINS,
    "Mustang":           Zone.MOUNTAINS,
    "Rukum West":        Zone.MOUNTAINS,
    "Dolpa":             Zone.MOUNTAINS,
    "Humla":             Zone.MOUNTAINS,
    "Jumla":             Zone.MOUNTAINS,
    "Kalikot":           Zone.MOUNTAINS,
    "Mugu":              Zone.MOUNTAINS,
    "Taplejung High":    Zone.MOUNTAINS,  # upper belts only
}


# ── Nepali month number → name ───────────────────────────────────────────────
# Nepali calendar: 1 = Baisakh … 12 = Chaitra

NEPALI_MONTH_NAMES: Dict[int, str] = {
    1:  "Baisakh",
    2:  "Jestha",
    3:  "Ashadh",
    4:  "Shrawan",
    5:  "Bhadra",
    6:  "Ashwin",
    7:  "Kartik",
    8:  "Mangsir",
    9:  "Poush",
    10: "Magh",
    11: "Falgun",
    12: "Chaitra",
}

# ── Season boundaries (Nepali month numbers) ──────────────────────────────────
_KHARIF = {3, 4, 5, 6, 7}      # Ashadh–Kartik   (monsoon / summer crop)
_RABI   = {8, 9, 10, 11, 12}   # Mangsir–Chaitra (winter crop)
_SPRING = {1, 2}               # Baisakh–Jestha  (spring crop)


# ── Public functions ─────────────────────────────────────────────────────────

def classify_zone(district: str) -> Zone:
    """
    Return the agro-ecological zone for the given district name.
    Falls back to Hills if district is not in the lookup table.

    Args:
        district: District name as entered by the farmer (case-insensitive).

    Returns:
        Zone enum value  (Zone.TERAI / Zone.HILLS / Zone.MOUNTAINS)
        whose .value is  "Terai"   / "Hills"   / "Mountains"
    """
    district_clean = district.strip().title()
    zone = DISTRICT_ZONE_MAP.get(district_clean)
    if zone is None:
        # Soft fallback — Hills is the modal zone in Nepal
        return Zone.HILLS
    return zone


def month_to_name(month: int) -> Optional[str]:
    """
    Return the Nepali month name for a given month number (1–12).
    Returns None if out of range.
    """
    return NEPALI_MONTH_NAMES.get(month)


def month_to_season(month: int) -> Optional[str]:
    """
    Map a Nepali calendar month number to an agro-season string.

    Args:
        month: Integer 1–12 (1 = Baisakh, 12 = Chaitra).

    Returns:
        "Kharif" | "Rabi" | "Spring" | None if out of range.
    """
    if month in _KHARIF:
        return "Kharif"
    if month in _RABI:
        return "Rabi"
    if month in _SPRING:
        return "Spring"
    return None


def get_zone_characteristics(zone: Zone) -> dict:
    """
    Return agronomic characteristics relevant to crop advice for the zone.
    Used by the rule engine and LLM context builder.
    """
    characteristics = {
        Zone.TERAI: {
            "altitude_m":        "60–300",
            "avg_temp_celsius":  "20–35",
            "annual_rainfall_mm": "1200–2000",
            "suitable_seasons":  ["Kharif", "Rabi", "Spring"],
            "main_crops":        ["Rice", "Maize", "Wheat", "Lentil", "Mustard",
                                  "Sugarcane", "Jute", "Vegetables"],
            "notes": (
                "High humidity in monsoon; irrigation often available; "
                "flood risk in low-lying areas."
            ),
        },
        Zone.HILLS: {
            "altitude_m":        "300–2000",
            "avg_temp_celsius":  "10–25",
            "annual_rainfall_mm": "1000–2500",
            "suitable_seasons":  ["Kharif", "Rabi"],
            "main_crops":        ["Maize", "Millet", "Rice (irrigated valleys)",
                                  "Potato", "Wheat", "Barley", "Vegetables",
                                  "Tea", "Coffee"],
            "notes": (
                "Terrace farming predominant; mixed crops; rainfall varies "
                "greatly by aspect."
            ),
        },
        Zone.MOUNTAINS: {
            "altitude_m":        "2000–4000+",
            "avg_temp_celsius":  "2–15",
            "annual_rainfall_mm": "400–800",
            "suitable_seasons":  ["Spring", "Rabi (limited)"],
            "main_crops":        ["Potato", "Buckwheat", "Barley", "Peas",
                                  "Medicinal herbs", "Pseudo-cereals"],
            "notes": (
                "Short growing season; frost risk; limited irrigation; "
                "high-value medicinal plants viable."
            ),
        },
    }
    return characteristics[zone]