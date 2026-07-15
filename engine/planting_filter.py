# import pandas as pd
# import os
# from engine.nepali_calendar import get_calendar_context

# MONTH_ORDER = [
#     "Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra",
#     "Ashwin", "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"
# ]

# def load_calendar():
#     path = os.path.join(os.path.dirname(__file__), '..', 'data', 'crop_calendar.csv')
#     return pd.read_csv(path)

# def get_month_index(month_name):
#     month_name = month_name.strip()
#     if month_name in MONTH_ORDER:
#         return MONTH_ORDER.index(month_name)
#     return None

# def extract_all_planting_months(planting_str):
#     """
#     Handles entries like:
#     'Bhadra–Ashwin (nursery for Hiude); Chaitra–Baisakh (nursery for Garmi)'
#     Strips annotations in parentheses, splits by semicolon, then parses each range.
#     """
#     all_months = []

#     # split multiple seasons by semicolon
#     segments = planting_str.split(';')

#     for seg in segments:
#         seg = seg.strip()

#         # remove anything in parentheses e.g. "(nursery for Hiude)"
#         if '(' in seg:
#             seg = seg[:seg.index('(')].strip()

#         # now seg should be like "Bhadra–Ashwin" or "Chaitra–Baisakh"
#         # handle both dash types: – and -
#         seg = seg.replace('–', '-')

#         if '-' in seg:
#             parts = seg.split('-')
#             start = parts[0].strip()
#             end   = parts[1].strip()
#             start_i = get_month_index(start)
#             end_i   = get_month_index(end)
#             if start_i is None or end_i is None:
#                 continue
#             if start_i <= end_i:
#                 for i in range(start_i, end_i + 1):
#                     all_months.append(MONTH_ORDER[i])
#             else:
#                 # wraps around year e.g. Chaitra-Baisakh
#                 for i in list(range(start_i, 12)) + list(range(0, end_i + 1)):
#                     all_months.append(MONTH_ORDER[i])
#         else:
#             if seg in MONTH_ORDER:
#                 all_months.append(seg)

#     return all_months

# def parse_growth_weeks(growth_str):
#     """
#     Parses '10–14' into min=10, max=14.
#     Handles both dash types.
#     """
#     growth_str = str(growth_str).replace('–', '-')
#     if '-' in growth_str:
#         parts = growth_str.split('-')
#         try:
#             return int(parts[0].strip()), int(parts[1].strip())
#         except:
#             return None, None
#     else:
#         try:
#             v = int(growth_str.strip())
#             return v, v
#         except:
#             return None, None

# def get_planting_status(planting_str, current_month_name):
#     all_months = extract_all_planting_months(planting_str)
#     current_i  = get_month_index(current_month_name)

#     if current_month_name in all_months:
#         return 'plant_now'

#     # check if any planting month is within next 2 months
#     for m in all_months:
#         m_i = get_month_index(m)
#         if m_i is None:
#             continue
#         diff = (m_i - current_i) % 12
#         if 1 <= diff <= 2:
#             return 'coming_soon'

#     return 'out_of_season'

# def get_filtered_crops():
#     df  = load_calendar()
#     ctx = get_calendar_context()
#     current = ctx['month_name']

#     results = []
#     for _, row in df.iterrows():
#         planting_str = row['Planting Seasons (Nepali Months)']
#         status       = get_planting_status(planting_str, current)
#         weeks_min, weeks_max = parse_growth_weeks(row['Growth Duration (Weeks)'])

#         results.append({
#             'crop_key':        row['crop_key'],
#             'crop_name':       row['Crop Name (Common/Nepali)'],
#             'planting_status': status,
#             'planting_months': planting_str,
#             'growth_weeks_min': weeks_min,
#             'growth_weeks_max': weeks_max,
#             'harvest_months':  row['Typical Harvest Months (Nepali)'],
#             'altitude_min':    row['Required Altitude Range (masl)'],
#             'water_requirement': row['Water Requirement'],
#             'diseases':        row['Typical Disease Vulnerabilities'],
#             'storage_shelf_life': row['Storage Shelf Life (Days)'],
#         })

#     return results


import re
import pandas as pd
import os
from engine.nepali_calendar import get_calendar_context

MONTH_ORDER = [
    "Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra",
    "Ashwin", "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"
]

# ── Agro-ecological altitude bands (masl) ─────────────────────────────────────
# Nepal has no per-district elevation in this dataset — only district→zone. Each
# zone maps to the elevation band where its cultivation actually happens. A crop
# is altitude-suitable for a district if the crop's required altitude range
# OVERLAPS that district's zone band. Bands overlap deliberately (inner-Terai,
# mid-hills) so a crop is never wrongly excluded at a boundary.
ZONE_ALTITUDE_BANDS = {
    "terai":     (60, 900),
    "hills":     (300, 2500),
    "mountains": (1500, 4500),
}


def parse_altitude_range(altitude_str) -> tuple | None:
    """Parse a crop's 'Required Altitude Range (masl)' cell into (min, max).

    Handles '60–1500', '60-1500', '500 to 2500', trailing 'masl', and a lone
    number. Returns None when no number is present (unknown → treated as
    suitable, never excluded).
    """
    nums = [int(n) for n in re.findall(r"\d+", str(altitude_str))]
    if not nums:
        return None
    if len(nums) == 1:
        return (0, nums[0])          # open-ended low bound
    return (min(nums), max(nums))


def is_altitude_suitable(altitude_str, zone: str) -> bool | None:
    """True/False if the crop's altitude range overlaps the zone band; None when
    either the crop range or the zone is unknown (caller decides — we don't drop
    unknowns)."""
    band = ZONE_ALTITUDE_BANDS.get((zone or "").strip().lower())
    crop_range = parse_altitude_range(altitude_str)
    if band is None or crop_range is None:
        return None
    (c_lo, c_hi), (z_lo, z_hi) = crop_range, band
    return c_lo <= z_hi and c_hi >= z_lo


def load_calendar():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'crop_calendar.csv')
    return pd.read_csv(path)

def get_month_index(month_name):
    month_name = month_name.strip()
    if month_name in MONTH_ORDER:
        return MONTH_ORDER.index(month_name)
    return None

def extract_all_planting_months(planting_str):
    all_months = []
    segments = planting_str.split(';')

    for seg in segments:
        seg = seg.strip()
        if '(' in seg:
            seg = seg[:seg.index('(')].strip()
        seg = seg.replace('–', '-')

        if '-' in seg:
            parts   = seg.split('-')
            start   = parts[0].strip()
            end     = parts[1].strip()
            start_i = get_month_index(start)
            end_i   = get_month_index(end)
            if start_i is None or end_i is None:
                continue
            if start_i <= end_i:
                for i in range(start_i, end_i + 1):
                    all_months.append(MONTH_ORDER[i])
            else:
                for i in list(range(start_i, 12)) + list(range(0, end_i + 1)):
                    all_months.append(MONTH_ORDER[i])
        else:
            if seg in MONTH_ORDER:
                all_months.append(seg)

    return all_months

def parse_growth_weeks(growth_str):
    growth_str = str(growth_str).replace('–', '-')
    if '-' in growth_str:
        parts = growth_str.split('-')
        try:
            return int(parts[0].strip()), int(parts[1].strip())
        except:
            return None, None
    else:
        try:
            v = int(growth_str.strip())
            return v, v
        except:
            return None, None

def get_planting_status(planting_str, current_month_name):
    all_months = extract_all_planting_months(planting_str)
    current_i  = get_month_index(current_month_name)

    if current_month_name in all_months:
        return 'plant_now'

    for m in all_months:
        m_i = get_month_index(m)
        if m_i is None:
            continue
        diff = (m_i - current_i) % 12
        if 1 <= diff <= 2:
            return 'coming_soon'

    return 'out_of_season'

def get_filtered_crops(month=None, zone=None):
    """Crops from the calendar tagged plant_now / coming_soon / out_of_season.

    month: Bikram Sambat month number (1-12). When given, filtering is done for
    that month; when None, falls back to the UI override month, then today's
    real month (see get_calendar_context).

    zone: optional agro-ecological zone ('Terai' | 'Hills' | 'Mountains',
    case-insensitive) — usually derived from the farmer's district. When given,
    each crop gains 'altitude_suitable' (True/False/None). Crops are NOT dropped
    here (callers filter), so existing callers see identical behaviour plus the
    extra flag.
    """
    df      = load_calendar()
    ctx     = get_calendar_context(bs_month=month)
    current = ctx['month_name']

    results = []
    for _, row in df.iterrows():
        planting_str         = row['Planting Seasons (Nepali Months)']
        status               = get_planting_status(planting_str, current)
        weeks_min, weeks_max = parse_growth_weeks(row['Growth Duration (Weeks)'])
        altitude_range       = row['Required Altitude Range (masl)']

        results.append({
            'crop_key':           row['crop_key'],
            'crop_name':          row['Crop Name (Common/Nepali)'],
            'planting_status':    status,
            'planting_months':    planting_str,
            'growth_weeks_min':   weeks_min,
            'growth_weeks_max':   weeks_max,
            'harvest_months':     row['Typical Harvest Months (Nepali)'],
            'altitude_min':       altitude_range,
            'altitude_suitable':  is_altitude_suitable(altitude_range, zone) if zone else None,
            'water_requirement':  row['Water Requirement'],
            'diseases':           row['Typical Disease Vulnerabilities'],
            'storage_shelf_life': row['Storage Shelf Life (Days)'],
        })

    return results


def get_crops_for_location(zone, month=None, statuses=("plant_now",)):
    """District-accurate recommendation: crops whose season matches AND whose
    altitude range fits the zone. This is the function the chat intent-router
    should call for 'what can I plant in <district> now'.

    zone: 'Terai' | 'Hills' | 'Mountains' (derive from district via
    rules.zone_classifier.classify_zone). month: BS month (None = current).
    statuses: which planting statuses to keep (default only 'plant_now').

    Altitude-unknown crops (flag None) are kept — we never exclude on missing
    data, only on a confirmed mismatch (flag False).
    """
    crops = get_filtered_crops(month=month, zone=zone)
    return [
        c for c in crops
        if c['planting_status'] in statuses and c['altitude_suitable'] is not False
    ]