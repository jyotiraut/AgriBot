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


import pandas as pd
import os
from engine.nepali_calendar import get_calendar_context

MONTH_ORDER = [
    "Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra",
    "Ashwin", "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"
]

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

def get_filtered_crops(month=None):
    """Crops from the calendar tagged plant_now / coming_soon / out_of_season.

    month: Bikram Sambat month number (1-12). When given, filtering is done for
    that month; when None, falls back to the UI override month, then today's
    real month (see get_calendar_context).
    """
    df      = load_calendar()
    ctx     = get_calendar_context(bs_month=month)
    current = ctx['month_name']

    results = []
    for _, row in df.iterrows():
        planting_str         = row['Planting Seasons (Nepali Months)']
        status               = get_planting_status(planting_str, current)
        weeks_min, weeks_max = parse_growth_weeks(row['Growth Duration (Weeks)'])

        results.append({
            'crop_key':           row['crop_key'],
            'crop_name':          row['Crop Name (Common/Nepali)'],
            'planting_status':    status,
            'planting_months':    planting_str,
            'growth_weeks_min':   weeks_min,
            'growth_weeks_max':   weeks_max,
            'harvest_months':     row['Typical Harvest Months (Nepali)'],
            'altitude_min':       row['Required Altitude Range (masl)'],
            'water_requirement':  row['Water Requirement'],
            'diseases':           row['Typical Disease Vulnerabilities'],
            'storage_shelf_life': row['Storage Shelf Life (Days)'],
        })

    return results