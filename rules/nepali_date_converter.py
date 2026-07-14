# rules/nepali_date_converter.py
"""
Converts Nepali (Bikram Sambat) date strings to English (AD) ISO date strings.

Uses the `nepali-datetime` library for accurate BS→AD conversion.
Install: pip install nepali-datetime

Supported input formats
-----------------------
  "बैशाख ३"     →  "2026-04-16"   (Devanagari month + Devanagari day)
  "जेठ १५"      →  "2026-05-29"   (any Nepali month name + Nepali digits)
  "Baisakh 3"   →  "2026-04-16"   (romanised month + ASCII day)
  "Shrawan 15"  →  "2026-07-31"
  "2082-01-03"  →  "2026-04-16"   (BS ISO string — year >= 2040 treated as BS)
  "2083-01-03"  →  "2026-04-16"
  "2026-04-16"  →  "2026-04-16"   (already AD — returned unchanged)
  ""  / None    →  same value      (safe no-op)
  unparseable   →  original string (never silently drops data)
"""

import re
import nepali_datetime  # pip install nepali-datetime

# ── Month name lookup tables ──────────────────────────────────────────────────

_NP_MONTHS_DEVANAGARI: dict[str, int] = {
    "बैशाख": 1, "बाइसाख": 1,
    "जेठ":   2,
    "असार":  3, "असाढ":   3,
    "श्रावण": 4, "साउन":  4, "श्राबण": 4,
    "भाद्र": 5, "भदौ":    5,
    "आश्विन": 6, "असोज":  6,
    "कार्तिक": 7,
    "मंसिर":  8, "मङसिर": 8,
    "पुष":    9, "पुस":    9,
    "माघ":   10,
    "फाल्गुन": 11, "फागुन": 11,
    "चैत्र": 12, "चैत":   12,
}

_NP_MONTHS_ROMAN: dict[str, int] = {
    "baisakh": 1, "baishakh": 1, "vaisakh": 1,
    "jestha":  2, "jeth":     2,
    "ashadh":  3, "asar":     3, "asarh":   3,
    "shrawan": 4, "shravan":  4, "saun":    4,
    "bhadra":  5, "bhadau":   5,
    "ashwin":  6, "asoj":     6, "ashoj":   6,
    "kartik":  7,
    "mangsir": 8, "mansir":   8,
    "poush":   9, "push":     9, "pus":     9,
    "magh":   10,
    "falgun": 11, "phagun":  11, "fagun":  11,
    "chaitra": 12, "chait":  12,
}

# Devanagari digit → ASCII digit
_NP_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Years >= this threshold are treated as BS (Bikram Sambat), not AD
_BS_YEAR_THRESHOLD = 2040


# ── Internal helpers ──────────────────────────────────────────────────────────

def _to_ascii_digits(s: str) -> str:
    """Replace Devanagari digits with ASCII equivalents."""
    return s.translate(_NP_DIGITS)


def _parse_month_name(token: str, ascii_token: str) -> int | None:
    """
    Try to resolve a month token (Devanagari or Roman) to a BS month number (1–12).
    Returns None if unrecognised.
    """
    # Devanagari first (use original token before digit-translation)
    if token in _NP_MONTHS_DEVANAGARI:
        return _NP_MONTHS_DEVANAGARI[token]
    # Roman (case-insensitive, strip trailing punctuation)
    key = ascii_token.lower().rstrip(".")
    return _NP_MONTHS_ROMAN.get(key)


def _parse_bs_parts(raw: str) -> tuple[int | None, int, int] | None:
    s       = raw.strip()
    ascii_s = _to_ascii_digits(s)

    # Format A: ISO-style "YYYY-MM-DD"
    m = re.fullmatch(r"(20\d\d)[/-](\d{1,2})[/-](\d{1,2})", ascii_s)
    if m:
        year = int(m.group(1))
        if year >= _BS_YEAR_THRESHOLD:
            return year, int(m.group(2)), int(m.group(3))
        else:
            return None  # already AD

    # Format B: "MonthName Day [गते]" — any order of non-month tokens
    parts       = s.split()
    ascii_parts = ascii_s.split()

    if len(parts) >= 2:
        month_num = _parse_month_name(parts[0], ascii_parts[0])

        # ✅ FIX: scan all tokens after the month for the first numeric one
        day_str = ""
        for token in ascii_parts[1:]:
            candidate = re.sub(r"\D", "", token)
            if candidate:
                day_str = candidate
                break

        if month_num and day_str:
            return None, month_num, int(day_str)

    return None



# ── Public API ────────────────────────────────────────────────────────────────

def nepali_to_english_date(raw: str | None) -> str | None:
    """
    Convert a Nepali (BS) date string to an English (AD) ISO 8601 date string.

    - Returns the original value unchanged if it is None, empty, already an AD
      ISO date, or cannot be parsed — data is never silently lost.
    - When no BS year is present (month-name formats), the current BS year is
      used, so sowing dates entered this season automatically map to 2026 AD.

    Parameters
    ----------
    raw : str | None
        The raw sowing_date value from the LLM or the database.

    Returns
    -------
    str | None
        ISO 8601 AD date string ("YYYY-MM-DD"), or the original value if
        conversion is not possible.
    """
    if not raw:
        return raw

    stripped = raw.strip()
    if not stripped:
        return raw

    # ── Fast-path: already a valid AD ISO date ────────────────────────────────
    if re.fullmatch(r"20[012]\d-\d{2}-\d{2}", stripped):
        return stripped

    # ── Parse ─────────────────────────────────────────────────────────────────
    result = _parse_bs_parts(stripped)

    if result is None:
        # _parse_bs_parts returns None for two cases:
        #   1. AD ISO string that passed the fast-path (shouldn't happen, but safe)
        #   2. Genuinely unparseable input
        return raw

    bs_year, bs_month, bs_day = result

    # Resolve year: use current BS year when no year was present in the string
    if bs_year is None:
        bs_year = nepali_datetime.date.today().year

    # ── Convert using nepali-datetime ─────────────────────────────────────────
    try:
        ad_date = nepali_datetime.date(bs_year, bs_month, bs_day).to_datetime_date()
        return ad_date.strftime("%Y-%m-%d")
    except Exception:
        # Invalid day for that month, or other library error — return original
        return raw
    

    # ── Public helper for extracting BS month number from raw strings ─────────────

NEPALI_MONTH_NAMES = {
    1: "Baisakh", 2: "Jestha",  3: "Ashadh",  4: "Shrawan",
    5: "Bhadra",  6: "Ashwin",  7: "Kartik",  8: "Mangsir",
    9: "Poush",  10: "Magh",   11: "Falgun",  12: "Chaitra",
}

def bs_month_from_raw(raw: str) -> int | None:
    """
    Extract BS month number from any raw string like:
      "baisakh 9", "Baisakh 15 ma ropeko", "बैशाख ४", "Shrawan"
    Scans token by token — handles extra words gracefully.
    Returns 1-12 or None.
    """
    if not raw:
        return None
    for token in raw.strip().split():
        ascii_token = _to_ascii_digits(token)
        result = _parse_month_name(token, ascii_token)
        if result:
            return result
    return None