# import pandas as pd
# import os
# from nepali_datetime import date as nepali_date
# from engine.nepali_calendar import get_calendar_context
# from engine.price_forecaster import get_full_price_analysis, NEPALI_MONTHS

# MONTH_ORDER = [
#     'Baisakh', 'Jestha',  'Ashadh',  'Shrawan', 'Bhadra',
#     'Ashwin',  'Kartik',  'Mangsir', 'Poush',   'Magh',
#     'Falgun',  'Chaitra'
# ]

# def get_month_index(month_name):
#     month_name = month_name.strip()
#     if month_name in MONTH_ORDER:
#         return MONTH_ORDER.index(month_name)
#     return None

# def months_ahead(from_idx, to_idx):
#     return (to_idx - from_idx) % 12

# def load_calendar():
#     path = os.path.join(
#         os.path.dirname(__file__), '..', 'data', 'crop_calendar.csv'
#     )
#     return pd.read_csv(path)

# def extract_all_months_from_str(range_str):
#     all_months = []
#     segments   = range_str.split(';')
#     for seg in segments:
#         seg = seg.strip()
#         if '(' in seg:
#             seg = seg[:seg.index('(')].strip()
#         seg = seg.replace('–', '-')
#         if '-' in seg:
#             parts   = seg.split('-')
#             start   = parts[0].strip()
#             end     = parts[1].strip()
#             start_i = get_month_index(start)
#             end_i   = get_month_index(end)
#             if start_i is None or end_i is None:
#                 continue
#             if start_i <= end_i:
#                 for i in range(start_i, end_i + 1):
#                     all_months.append(MONTH_ORDER[i])
#             else:
#                 for i in list(range(start_i, 12)) + list(range(0, end_i + 1)):
#                     all_months.append(MONTH_ORDER[i])
#         else:
#             if seg in MONTH_ORDER:
#                 all_months.append(seg)
#     return all_months

# def parse_growth_weeks(growth_str):
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

# def get_projected_harvest(plant_month_name, weeks_min, weeks_max):
#     """
#     Given a planting month and growth duration,
#     returns list of projected harvest months.
#     """
#     plant_idx   = get_month_index(plant_month_name)
#     months_min  = max(1, round(weeks_min / 4))
#     months_max  = max(1, round(weeks_max / 4))
#     projected   = []
#     for offset in range(months_min, months_max + 1):
#         idx = (plant_idx + offset) % 12
#         projected.append(MONTH_ORDER[idx])
#     return list(dict.fromkeys(projected))  # deduplicate, preserve order

# def get_demand_score_for_month(crop_key, bs_month, demand_scores_df):
#     """
#     Looks up the forecasted demand score for a crop
#     in a specific Nepali month.
#     """
#     row = demand_scores_df[
#         (demand_scores_df['crop_key']  == crop_key) &
#         (demand_scores_df['bs_month']  == bs_month)
#     ]
#     if row.empty:
#         return 0.0, 0.0
#     return (
#         float(row.iloc[0]['demand_score']),
#         float(row.iloc[0]['forecasted_avg'])
#     )

# def run_feasibility_check():
#     """
#     PLANT-FIRST LOGIC:
#     ─────────────────
#     1. Find all crops that can be planted THIS month
#     2. Project their harvest months (today + growth weeks)
#     3. Look up forecasted demand score at each harvest month
#     4. Pick the harvest month with highest demand per crop
#     5. Rank all plantable crops by that demand score
#     6. Return top 5

#     If fewer than 5 crops are plantable this month,
#     also check next month as a fallback and label them
#     as 'prepare to plant next month'.
#     """
#     ctx              = get_calendar_context()
#     current_bs_month = ctx['bs_month']
#     current_month    = MONTH_ORDER[current_bs_month - 1]
#     calendar_df      = load_calendar()

#     analysis         = get_full_price_analysis()
#     demand_scores_df = analysis['demand_scores_df']

#     results = []

#     # check current month + next month as fallback
#     months_to_check = [
#         (current_bs_month, current_month, 'now'),
#         ((current_bs_month % 12) + 1,
#          MONTH_ORDER[current_bs_month % 12], 'next'),
#     ]

#     seen_crops = set()

#     for bs_month, month_name, timing in months_to_check:
#         if len(results) >= 5:
#             break

#         for _, row in calendar_df.iterrows():
#             if len(results) >= 5:
#                 break

#             crop_key     = row['crop_key']
#             if crop_key in seen_crops:
#                 continue

#             planting_str = str(row['Planting Seasons (Nepali Months)'])
#             growth_str   = str(row['Growth Duration (Weeks)'])

#             planting_months = extract_all_months_from_str(planting_str)
#             weeks_min, weeks_max = parse_growth_weeks(growth_str)

#             if weeks_min is None:
#                 continue

#             # ── check if plantable this month ─────────────
#             if month_name not in planting_months:
#                 continue

#             # ── project harvest months ────────────────────
#             projected_harvest = get_projected_harvest(
#                 month_name, weeks_min, weeks_max
#             )

#             if not projected_harvest:
#                 continue

#             # ── find best harvest month by demand ─────────
#             # get demand scores for ALL 12 months for this crop
#             all_month_scores = []
#             for m_num in range(1, 13):
#                 d_score, f_price = get_demand_score_for_month(
#                     crop_key, m_num, demand_scores_df
#                 )
#                 all_month_scores.append((m_num, d_score, f_price))

#             # sort all months by demand score descending
#             all_month_scores.sort(key=lambda x: x[1], reverse=True)

#             # find the best demand month that is reachable
#             # i.e. within 2 months of projected harvest window
#             best_demand_score   = -999
#             best_harvest_month  = None
#             best_forecast_price = 0
#             best_bs_harvest     = None

#             harvest_indices = [
#                 get_month_index(h) for h in projected_harvest
#             ]

#             for m_num, d_score, f_price in all_month_scores:
#                 m_idx = m_num - 1
#                 # check if this demand month is within
#                 # 2 months of any projected harvest month
#                 reachable = any(
#                     (m_idx - h_idx) % 12 <= 2
#                     for h_idx in harvest_indices
#                 )
#                 if reachable:
#                     best_demand_score   = d_score
#                     best_harvest_month  = MONTH_ORDER[m_idx]
#                     best_forecast_price = f_price
#                     best_bs_harvest     = m_num
#                     break  # take the best reachable month

#             # fallback: if nothing reachable just use
#             # best score within projected harvest
#             if best_harvest_month is None:
#                 for h_month in projected_harvest:
#                     h_idx = get_month_index(h_month)
#                     h_bs  = h_idx + 1
#                     d_score, f_price = get_demand_score_for_month(
#                         crop_key, h_bs, demand_scores_df
#                     )
#                     if d_score > best_demand_score:
#                         best_demand_score   = d_score
#                         best_harvest_month  = h_month
#                         best_forecast_price = f_price
#                         best_bs_harvest     = h_bs


#             # ── check documented harvest overlap ──────────
#             harvest_str       = str(row['Typical Harvest Months (Nepali)'])
#             documented_harvest = extract_all_months_from_str(harvest_str)
#             overlap           = [
#                 m for m in projected_harvest
#                 if m in documented_harvest
#             ]
#             harvest_confidence = 'High' if overlap else 'Low'

#             results.append({
#                 'crop_key':          crop_key,
#                 'plant_month':       month_name,
#                 'plant_timing':      timing,  # 'now' or 'next'
#                 'harvest_months':    projected_harvest,
#                 'best_harvest_month': best_harvest_month,
#                 'best_bs_harvest':   best_bs_harvest,
#                 'documented_harvest': documented_harvest,
#                 'harvest_overlap':   overlap,
#                 'harvest_confidence': harvest_confidence,
#                 'demand_score':      round(best_demand_score, 4),
#                 'forecasted_price':  round(best_forecast_price, 2),
#                 'weeks_to_grow':     f'{weeks_min}–{weeks_max}',
#                 'feasibility_reason': (
#                     f'Plantable in {month_name}, '
#                     f'harvests in {", ".join(projected_harvest)}, '
#                     f'peak demand in {best_harvest_month}'
#                 ),
#             })
#             seen_crops.add(crop_key)

#     # sort by demand score
#     results.sort(key=lambda x: x['demand_score'], reverse=True)
#     return results[:5], ctx

import pandas as pd
import os
from nepali_datetime import date as nepali_date
from engine.nepali_calendar import get_calendar_context
from engine.price_forecaster import get_full_price_analysis, NEPALI_MONTHS

MONTH_ORDER = [
    'Baisakh', 'Jestha',  'Ashadh',  'Shrawan', 'Bhadra',
    'Ashwin',  'Kartik',  'Mangsir', 'Poush',   'Magh',
    'Falgun',  'Chaitra'
]

def get_month_index(month_name):
    month_name = month_name.strip()
    if month_name in MONTH_ORDER:
        return MONTH_ORDER.index(month_name)
    return None

def months_ahead(from_idx, to_idx):
    return (to_idx - from_idx) % 12

def load_calendar():
    path = os.path.join(
        os.path.dirname(__file__), '..', 'data', 'crop_calendar.csv'
    )
    return pd.read_csv(path)

def extract_all_months_from_str(range_str):
    all_months = []
    segments   = range_str.split(';')
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

def get_projected_harvest(plant_month_name, weeks_min, weeks_max):
    plant_idx  = get_month_index(plant_month_name)
    months_min = max(1, round(weeks_min / 4))
    months_max = max(1, round(weeks_max / 4))
    projected  = []
    for offset in range(months_min, months_max + 1):
        idx = (plant_idx + offset) % 12
        projected.append(MONTH_ORDER[idx])
    return list(dict.fromkeys(projected))

def get_demand_score_for_month(crop_key, bs_month, demand_scores_df):
    row = demand_scores_df[
        (demand_scores_df['crop_key'] == crop_key) &
        (demand_scores_df['bs_month'] == bs_month)
    ]
    if row.empty:
        return 0.0, 0.0
    return (
        float(row.iloc[0]['demand_score']),
        float(row.iloc[0]['forecasted_avg'])
    )

def run_feasibility_check(month=None):       # ← month added
    # ctx              = get_calendar_context(month=month)
    ctx = get_calendar_context()
    current_bs_month = ctx['bs_month']
    current_month    = MONTH_ORDER[current_bs_month - 1]
    calendar_df      = load_calendar()

    analysis         = get_full_price_analysis()
    demand_scores_df = analysis['demand_scores_df']

    results = []

    months_to_check = [
        (current_bs_month, current_month, 'now'),
        ((current_bs_month % 12) + 1,
         MONTH_ORDER[current_bs_month % 12], 'next'),
    ]

    seen_crops = set()

    for bs_month, month_name, timing in months_to_check:
        if len(results) >= 5:
            break

        for _, row in calendar_df.iterrows():
            if len(results) >= 5:
                break

            crop_key = row['crop_key']
            if crop_key in seen_crops:
                continue

            planting_str = str(row['Planting Seasons (Nepali Months)'])
            growth_str   = str(row['Growth Duration (Weeks)'])

            planting_months      = extract_all_months_from_str(planting_str)
            weeks_min, weeks_max = parse_growth_weeks(growth_str)

            if weeks_min is None:
                continue

            if month_name not in planting_months:
                continue

            projected_harvest = get_projected_harvest(
                month_name, weeks_min, weeks_max
            )

            if not projected_harvest:
                continue

            all_month_scores = []
            for m_num in range(1, 13):
                d_score, f_price = get_demand_score_for_month(
                    crop_key, m_num, demand_scores_df
                )
                all_month_scores.append((m_num, d_score, f_price))

            all_month_scores.sort(key=lambda x: x[1], reverse=True)

            best_demand_score   = -999
            best_harvest_month  = None
            best_forecast_price = 0
            best_bs_harvest     = None

            harvest_indices = [
                get_month_index(h) for h in projected_harvest
            ]

            for m_num, d_score, f_price in all_month_scores:
                m_idx = m_num - 1
                reachable = any(
                    (m_idx - h_idx) % 12 <= 2
                    for h_idx in harvest_indices
                )
                if reachable:
                    best_demand_score   = d_score
                    best_harvest_month  = MONTH_ORDER[m_idx]
                    best_forecast_price = f_price
                    best_bs_harvest     = m_num
                    break

            if best_harvest_month is None:
                for h_month in projected_harvest:
                    h_idx = get_month_index(h_month)
                    h_bs  = h_idx + 1
                    d_score, f_price = get_demand_score_for_month(
                        crop_key, h_bs, demand_scores_df
                    )
                    if d_score > best_demand_score:
                        best_demand_score   = d_score
                        best_harvest_month  = h_month
                        best_forecast_price = f_price
                        best_bs_harvest     = h_bs

            harvest_str        = str(row['Typical Harvest Months (Nepali)'])
            documented_harvest = extract_all_months_from_str(harvest_str)
            overlap            = [
                m for m in projected_harvest
                if m in documented_harvest
            ]
            harvest_confidence = 'High' if overlap else 'Low'

            results.append({
                'crop_key':           crop_key,
                'plant_month':        month_name,
                'plant_timing':       timing,
                'harvest_months':     projected_harvest,
                'best_harvest_month': best_harvest_month,
                'best_bs_harvest':    best_bs_harvest,
                'documented_harvest': documented_harvest,
                'harvest_overlap':    overlap,
                'harvest_confidence': harvest_confidence,
                'demand_score':       round(best_demand_score, 4),
                'forecasted_price':   round(best_forecast_price, 2),
                'weeks_to_grow':      f'{weeks_min}–{weeks_max}',
                'feasibility_reason': (
                    f'Plantable in {month_name}, '
                    f'harvests in {", ".join(projected_harvest)}, '
                    f'peak demand in {best_harvest_month}'
                ),
            })
            seen_crops.add(crop_key)

    results.sort(key=lambda x: x['demand_score'], reverse=True)
    return results[:5], ctx