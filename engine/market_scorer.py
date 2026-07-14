# import pandas as pd
# import os
# from engine.nepali_calendar import get_calendar_context
# from engine.planting_filter import get_filtered_crops, get_month_index, MONTH_ORDER

# def load_prices():
#     path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_prices.csv')
#     return pd.read_csv(path)

# def extract_harvest_months(harvest_str):
#     """
#     Parses entries like:
#     'Poush–Falgun (Hiude); Shrawan–Ashwin (Garmi)'
#     Returns a flat list of all harvest months across all seasons.
#     """
#     all_months = []
#     segments = harvest_str.split(';')

#     for seg in segments:
#         seg = seg.strip()

#         # remove anything in parentheses
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

# def get_projected_harvest_months(current_month_name, weeks_min, weeks_max):
#     """
#     Projects harvest window by adding growth duration to current month.
#     Returns list of months the crop would be ready in.
#     """
#     current_i    = get_month_index(current_month_name)
#     if current_i is None or weeks_min is None:
#         return []

#     # convert weeks to months (approximate)
#     months_min = round(weeks_min / 4)
#     months_max = round(weeks_max / 4)

#     projected = []
#     for offset in range(months_min, months_max + 1):
#         idx = (current_i + offset) % 12
#         projected.append(MONTH_ORDER[idx])

#     return list(set(projected))

# def score_market_opportunity(crop_key, harvest_months):
#     """
#     Scores market opportunity 0–10 based on:
#     - Price margin (max - min) / max  → upside potential
#     - Average price normalized across all crops
#     Returns score and price details.
#     """
#     prices = load_prices()
#     row    = prices[prices['crop_key'] == crop_key]

#     if row.empty:
#         return 5.0, None  # neutral score if no price data

#     row     = row.iloc[0]
#     avg     = float(row['average'])
#     maximum = float(row['maximum'])
#     minimum = float(row['minimum'])

#     # price margin score: how wide is the price swing? (0–10)
#     margin_score = ((maximum - minimum) / maximum) * 10

#     # average price score: normalize against max price in dataset
#     all_avgs  = prices['average'].astype(float)
#     price_score = (avg / all_avgs.max()) * 10

#     # combined market score
#     market_score = round((margin_score * 0.5) + (price_score * 0.5), 2)

#     return market_score, {
#         'average_price': avg,
#         'min_price':     minimum,
#         'max_price':     maximum,
#         'margin_score':  round(margin_score, 2),
#         'price_score':   round(price_score, 2),
#     }

# def get_market_scores():
#     crops   = get_filtered_crops()
#     ctx     = get_calendar_context()
#     current = ctx['month_name']

#     results = []
#     for crop in crops:
#         # get projected harvest from today
#         projected = get_projected_harvest_months(
#             current,
#             crop['growth_weeks_min'],
#             crop['growth_weeks_max']
#         )

#         # also parse the documented harvest months
#         documented = extract_harvest_months(crop['harvest_months'])

#         # overlap between projected and documented = stronger signal
#         overlap = [m for m in projected if m in documented]
#         harvest_confidence = 'High' if overlap else 'Low'

#         market_score, price_details = score_market_opportunity(
#             crop['crop_key'],
#             projected
#         )

#         results.append({
#             **crop,
#             'projected_harvest':    projected,
#             'documented_harvest':   documented,
#             'harvest_overlap':      overlap,
#             'harvest_confidence':   harvest_confidence,
#             'market_score':         market_score,
#             'price_details':        price_details,
#         })

#     return results

import pandas as pd
import os
from engine.nepali_calendar import get_calendar_context
from engine.planting_filter import get_filtered_crops, get_month_index, MONTH_ORDER

def load_prices():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_prices.csv')
    return pd.read_csv(path)

def extract_harvest_months(harvest_str):
    all_months = []
    segments   = harvest_str.split(';')

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

def get_projected_harvest_months(current_month_name, weeks_min, weeks_max):
    current_i = get_month_index(current_month_name)
    if current_i is None or weeks_min is None:
        return []

    months_min = round(weeks_min / 4)
    months_max = round(weeks_max / 4)

    projected = []
    for offset in range(months_min, months_max + 1):
        idx = (current_i + offset) % 12
        projected.append(MONTH_ORDER[idx])

    return list(set(projected))

def score_market_opportunity(crop_key, harvest_months):
    prices = load_prices()
    row    = prices[prices['crop_key'] == crop_key]

    if row.empty:
        return 5.0, None

    row     = row.iloc[0]
    avg     = float(row['average'])
    maximum = float(row['maximum'])
    minimum = float(row['minimum'])

    margin_score = ((maximum - minimum) / maximum) * 10

    all_avgs    = prices['average'].astype(float)
    price_score = (avg / all_avgs.max()) * 10

    market_score = round((margin_score * 0.5) + (price_score * 0.5), 2)

    return market_score, {
        'average_price': avg,
        'min_price':     minimum,
        'max_price':     maximum,
        'margin_score':  round(margin_score, 2),
        'price_score':   round(price_score, 2),
    }

def get_market_scores(month=None):           # ← month added
    crops   = get_filtered_crops(month=month)
    # ctx     = get_calendar_context(month=month)
    ctx     = get_calendar_context()
    current = ctx['month_name']

    results = []
    for crop in crops:
        projected = get_projected_harvest_months(
            current,
            crop['growth_weeks_min'],
            crop['growth_weeks_max']
        )

        documented = extract_harvest_months(crop['harvest_months'])
        overlap    = [m for m in projected if m in documented]
        harvest_confidence = 'High' if overlap else 'Low'

        market_score, price_details = score_market_opportunity(
            crop['crop_key'],
            projected
        )

        results.append({
            **crop,
            'projected_harvest':  projected,
            'documented_harvest': documented,
            'harvest_overlap':    overlap,
            'harvest_confidence': harvest_confidence,
            'market_score':       market_score,
            'price_details':      price_details,
        })

    return results