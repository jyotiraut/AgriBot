# rules/crop_normalizer.py
"""
Single source of truth for crop-name normalisation across the whole app.
Both the batch extractor (core/profile_extractor.py, rules/field_validator.py)
and the live chat (rules/conversation_rules.normalise_crop) resolve crops here.
"""

CROP_NORMALIZE = {
    # Potato
    "tomatoes":     "tomato",
    "potatoes":     "potato",
    "cauliflowers": "cauliflower",
    "cabbages":     "cabbage",
    "paddies":      "paddy",
    "rice":         "paddy",
    "corns":        "maize",
    "corn":         "maize",
    "wheats":       "wheat",
    "aloo":         "potato",
    "alu":          "potato",
    "aalu":         "potato",
    "alu bari":     "potato",
    "golbheda":     "tomato",
    "tamatar":      "tomato",
    "tamater":      "tomato",
    "kauli":        "cauliflower",
    "cauli":        "cauliflower",
    "phool gobhi":  "cauliflower",
    "phool kobhi":  "cauliflower",
    "band gobhi":   "cabbage",
    "band kobhi":   "cabbage",
    "bandakopi":    "cabbage",
    "banda":        "cabbage",
    "makai":        "maize",
    "makkai":       "maize",
    "dhan":         "paddy",
    "dhaan":        "paddy",
    "chamal":       "paddy",
    "gahu":         "wheat",
    "gahun":        "wheat",
    "gehun":        "wheat",
    "tarkari":      "vegetables",
    "sabji":        "vegetables",
    "adu":          "ginger",
    "adua":         "ginger",
    "aduwa":        "ginger",
    "aduwaa":       "ginger",
    "lasun":        "garlic",
    "lahsun":       "garlic",
    "pyaj":         "onion",
    "pyaz":         "onion",
    "piaj":         "onion",
    "tori":         "mustard",
    "sarson":       "mustard",
    "ukhu":         "sugarcane",
    "ukh":          "sugarcane",
    "aalaichi":     "cardamom",
    "alaichi":      "cardamom",
    "elaichi":      "cardamom",
    "chiya":        "tea",
    "syau":         "apple",
    "syaau":        "apple",
    "kera":         "banana",
    "kella":        "banana",
    # Pulses / grains / vegetables previously only in conversation_rules
    "masuro":       "lentil",
    "masur":        "lentil",
    "dal":          "lentil",
    "kakro":        "cucumber",
    "karela":       "bitter gourd",
    "farsi":        "pumpkin",
    "simi":         "bean",
    "bodi":         "bean",
    "kodo":         "millet",
    "junelo":       "millet",
    "bhatmas":      "soybean",
    "fapar":        "buckwheat",
}

# Valid singular lowercase crop names the system recognises
VALID_CROPS = {
    "tomato", "potato", "cauliflower", "cabbage", "paddy", "maize",
    "wheat", "ginger", "garlic", "onion", "mustard", "sugarcane",
    "cardamom", "tea", "apple", "banana", "vegetables",
    "lentil", "cucumber", "bitter gourd", "pumpkin", "bean",
    "millet", "soybean", "buckwheat",
}


def normalize_crop(crop: str) -> str:
    """
    Normalize any crop name variant to singular lowercase English.
    Exact alias match first, then substring match (e.g. 'alu ko bali' → potato),
    otherwise the lowercased input is returned unchanged.
    """
    if not crop:
        return ""
    key = crop.lower().strip()
    if key in CROP_NORMALIZE:
        return CROP_NORMALIZE[key]
    if key in VALID_CROPS:
        return key
    for alias, canonical in CROP_NORMALIZE.items():
        if alias in key:
            return canonical
    return key


def is_valid_crop(crop: str) -> bool:
    """Check if a normalized crop name is in the known valid set."""
    return normalize_crop(crop) in VALID_CROPS