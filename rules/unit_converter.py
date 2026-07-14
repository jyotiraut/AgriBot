# rules/unit_converter.py

UNIT_TO_HECTARE = {
    "ropani":  0.0509,
    "ro":      0.0509,
    "bigha":   0.6773,
    "biga":    0.6773,
    "kattha":  0.0338,
    "katha":   0.0338,
    "dhur":    0.00169,
    "acre":    0.4047,
    "hectare": 1.0,
    "ha":      1.0,
}

NEPALI_NUMBER_WORDS = {
    "ek":     1, "dui":   2, "teen":  3, "char":  4,
    "paanch": 5, "chha":  6, "saat":  7, "aath":  8,
    "nau":    9, "das":  10,
}

NEPALI_MONTH_TO_INT = {
    "baishakh": 1,  "jestha":   2,  "ashadh":  3,
    "shrawan":  4,  "bhadra":   5,  "ashwin":  6,
    "kartik":  7,  "mangsir": 8,  "poush":  9,
    "magh":     10,  "falgun":   11,  "chaitra":  12,
}

# ── District data (used by rag/chain.py) ───────────────────────

ALL_DISTRICTS = [
    "taplejung", "panchthar", "ilam", "jhapa", "morang", "sunsari",
    "dhankuta", "terhathum", "sankhuwasabha", "bhojpur", "solukhumbu",
    "okhaldhunga", "khotang", "udayapur", "saptari", "siraha", "dhanusha",
    "mahottari", "sarlahi", "rautahat", "bara", "parsa", "sindhuli",
    "ramechhap", "dolakha", "sindhupalchok", "kavrepalanchok", "lalitpur",
    "bhaktapur", "kathmandu", "nuwakot", "rasuwa", "dhading", "makwanpur",
    "chitwan", "gorkha", "lamjung", "tanahu", "syangja", "kaski", "manang",
    "mustang", "myagdi", "parbat", "baglung", "nawalpur", "palpa",
    "arghakhanchi", "gulmi", "rupandehi", "kapilvastu", "dang", "banke",
    "bardiya", "rolpa", "pyuthan", "dolpa", "mugu", "humla", "jumla",
    "kalikot", "dailekh", "jajarkot", "salyan", "surkhet", "bajura",
    "bajhang", "achham", "doti", "kailali", "kanchanpur", "dadeldhura",
    "baitadi", "darchula", "sinduli", "kavre", "bhaktpur", "ktm", "chitawan",
]

PLACE_TO_DISTRICT = {
    "pokhara":       "kaski",
    "butwal":        "rupandehi",
    "nepalgunj":     "banke",
    "nepalganj":     "banke",
    "dharan":        "sunsari",
    "biratnagar":    "morang",
    "hetauda":       "makwanpur",
    "bharatpur":     "chitwan",
    "chitawan":      "chitwan",
    "banepa":        "kavrepalanchok",
    "kavre":         "kavrepalanchok",
    "sinduli":       "sindhuli",
    "kamalamai":     "sindhuli",
    "ktm":           "kathmandu",
    "tansen":        "palpa",
    "baglung":       "baglung",
    "ilam":          "ilam",
    "dhankuta":      "dhankuta",
    "janakpur":      "dhanusha",
    "birgunj":       "parsa",
    "narayanghat":   "chitwan",
    "damauli":       "tanahu",
    "waling":        "syangja",
    "gorkha":        "gorkha",
    "besisahar":     "lamjung",
    "dumre":         "tanahu",
    "tulsipur":      "dang",
    "kohalpur":      "banke",
    "tikapur":       "kailali",
    "dhangadhi":     "kailali",
    "mahendranagar": "kanchanpur",
    "dadeldhura":    "dadeldhura",
    "baitadi":       "baitadi",
    "darchula":      "darchula",
    "jumla":         "jumla",
    "surkhet":       "surkhet",
    "birendranagar": "surkhet",
}

DISTRICT_CANONICAL = {
    "sinduli":  "Sindhuli",
    "kavre":    "Kavrepalanchok",
    "bhaktpur": "Bhaktapur",
    "ktm":      "Kathmandu",
    "chitawan": "Chitwan",
}


# ── Functions ──────────────────────────────────────────────────

def convert_to_hectares(value: float, unit: str) -> float | None:
    """Convert any Nepali land unit to hectares."""
    unit   = unit.lower().strip()
    factor = UNIT_TO_HECTARE.get(unit)
    if factor is None:
        return None
    return round(value * factor, 4)


def nepali_word_to_number(word: str) -> int | None:
    """Convert Nepali number words to integers. e.g. 'paanch' → 5"""
    return NEPALI_NUMBER_WORDS.get(word.lower().strip())


def nepali_month_to_int(month: str) -> int | None:
    """Convert Nepali month name to integer 1-12. e.g. 'Shrawan' → 7"""
    return NEPALI_MONTH_TO_INT.get(month.lower().strip())