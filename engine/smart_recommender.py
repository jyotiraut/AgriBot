# import pandas as pd
# import os
# from engine.nepali_calendar import get_calendar_context
# from engine.feasibility_checker import run_feasibility_check, load_calendar
# from engine.risk_scorer import get_risk_lookup
# from engine.market_analysis import NEPALI_MONTHS

# MONTH_ORDER = [
#     'Baisakh', 'Jestha',  'Ashadh',  'Shrawan', 'Bhadra',
#     'Ashwin',  'Kartik',  'Mangsir', 'Poush',   'Magh',
#     'Falgun',  'Chaitra'
# ]

# NEPALI_MONTH_NAMES = {
#     'Baisakh':'वैशाख', 'Jestha':'जेठ',    'Ashadh':'असार',
#     'Shrawan':'साउन',  'Bhadra':'भदौ',    'Ashwin':'असोज',
#     'Kartik':'कार्तिक','Mangsir':'मंसिर', 'Poush':'पुस',
#     'Magh':'माघ',      'Falgun':'फागुन',  'Chaitra':'चैत'
# }

# # ── scoring weights ───────────────────────────────────────
# W_FORECAST_PRICE = 0.35
# W_DEMAND_SCORE   = 0.30
# W_FEASIBILITY    = 0.20
# W_RISK_PENALTY   = 0.15

# # ── normalize helper ──────────────────────────────────────
# def normalize(series):
#     mn = series.min()
#     mx = series.max()
#     if mx == mn:
#         return pd.Series([0.5] * len(series), index=series.index)
#     return (series - mn) / (mx - mn)

# # ── main recommendation builder ───────────────────────────
# def build_recommendations():
#     ctx              = get_calendar_context()
#     feasible_crops, _ = run_feasibility_check()
#     risk_lookup      = get_risk_lookup()
#     calendar_df      = load_calendar()

#     if not feasible_crops:
#         return [], ctx

#     rows = []
#     for crop in feasible_crops:
#         crop_key = crop['crop_key']

#         # ── risk data ─────────────────────────────────────
#         risk = risk_lookup.get(crop_key)
#         if risk:
#             risk_score    = risk['risk_score']
#             risk_penalty  = risk['risk_penalty']
#             risk_tier     = risk['risk_tier']
#             dominant_risk = risk['dominant_risk']
#             scoring_notes = risk['scoring_notes']
#         else:
#             risk_score    = 3.0
#             risk_penalty  = 0.30
#             risk_tier     = 'Medium'
#             dominant_risk = 'disease'
#             scoring_notes = 'Risk data not available — treat as medium risk'

#         # ── calendar data ─────────────────────────────────
#         cal_row = calendar_df[calendar_df['crop_key'] == crop_key]
#         if not cal_row.empty:
#             cal_row    = cal_row.iloc[0]
#             crop_name  = cal_row['Crop Name (Common/Nepali)']
#             water_req  = cal_row['Water Requirement']
#             shelf_life = cal_row['Storage Shelf Life (Days)']
#             diseases   = cal_row['Typical Disease Vulnerabilities']
#             altitude   = cal_row['Required Altitude Range (masl)']
#         else:
#             crop_name  = crop_key
#             water_req  = 'Medium'
#             shelf_life = 'N/A'
#             diseases   = 'N/A'
#             altitude   = 'N/A'

#         # harvest confidence score
#         harvest_conf_score = (
#             1.0 if crop.get('harvest_confidence') == 'High' else 0.5
#         )

#         rows.append({
#             'crop_key':           crop_key,
#             'crop_name':          crop_name,
#             'plant_month':        crop['plant_month'],
#             'plant_timing':       crop['plant_timing'],
#             'harvest_months':     crop['harvest_months'],
#             'best_harvest_month': crop['best_harvest_month'],
#             'documented_harvest': crop['documented_harvest'],
#             'harvest_overlap':    crop['harvest_overlap'],
#             'harvest_confidence': crop['harvest_confidence'],
#             'harvest_conf_score': harvest_conf_score,
#             'weeks_to_grow':      crop['weeks_to_grow'],
#             'forecasted_price':   crop['forecasted_price'],
#             'demand_score':       crop['demand_score'],
#             'feasibility_reason': crop['feasibility_reason'],
#             'risk_score':         risk_score,
#             'risk_penalty':       risk_penalty,
#             'risk_tier':          risk_tier,
#             'dominant_risk':      dominant_risk,
#             'scoring_notes':      scoring_notes,
#             'water_req':          water_req,
#             'shelf_life':         shelf_life,
#             'diseases':           diseases,
#             'altitude':           altitude,
#         })

#     df = pd.DataFrame(rows)

#     if df.empty:
#         return [], ctx

#     # ── normalize and score ───────────────────────────────
#     df['price_norm']  = normalize(df['forecasted_price'])
#     df['demand_norm'] = normalize(df['demand_score'])
#     df['conf_norm']   = df['harvest_conf_score']
#     df['risk_norm']   = normalize(df['risk_score'])

#     df['opportunity_score'] = (
#         df['price_norm']  * W_FORECAST_PRICE +
#         df['demand_norm'] * W_DEMAND_SCORE   +
#         df['conf_norm']   * W_FEASIBILITY    -
#         df['risk_norm']   * W_RISK_PENALTY
#     )
#     df['opportunity_score'] = (df['opportunity_score'] * 10).round(2)

#     # ── rank ──────────────────────────────────────────────
#     df = df.sort_values(
#         'opportunity_score', ascending=False
#     ).reset_index(drop=True)
#     df['rank'] = df.index + 1

#     return df.to_dict(orient='records'), ctx

# # ── label helpers ─────────────────────────────────────────
# def get_opportunity_label(score, lang='ne'):
#     if lang == 'en':
#         if score >= 8:   return '⭐⭐⭐ Excellent Opportunity'
#         elif score >= 6: return '⭐⭐ Good Opportunity'
#         elif score >= 4: return '⭐ Fair Opportunity'
#         else:            return '⚠️  Plant with Caution'
#     else:
#         if score >= 8:   return '⭐⭐⭐ उत्कृष्ट अवसर'
#         elif score >= 6: return '⭐⭐ राम्रो अवसर'
#         elif score >= 4: return '⭐ ठीकठाक अवसर'
#         else:            return '⚠️  सावधानीका साथ रोप्नुस्'

# def get_planting_urgency(plant_timing, plant_month, lang='ne'):
#     if plant_timing == 'now':
#         return {
#             'ne': '✅ अहिले रोप्नुस्',
#             'en': '✅ Plant this month'
#         }.get(lang)
#     else:
#         m = NEPALI_MONTH_NAMES.get(plant_month, plant_month)
#         return {
#             'ne': f'⏳ {m} मा रोप्न तयारी गर्नुस्',
#             'en': f'⏳ Prepare to plant in {plant_month}'
#         }.get(lang)

# def get_risk_reason(dominant_risk, lang='ne'):
#     reasons = {
#         'flood':      {'ne': 'बाढीको खतरा बढी छ',
#                        'en': 'High flood risk this season'},
#         'drought':    {'ne': 'खडेरी र पानी अभावको खतरा छ',
#                        'en': 'Risk of drought and water shortage'},
#         'frost':      {'ne': 'हिमपातले बाली नोक्सान गर्न सक्छ',
#                        'en': 'Frost damage risk this season'},
#         'disease':    {'ne': 'किरा र रोगको खतरा बढी छ',
#                        'en': 'High disease and pest pressure'},
#         'storage':    {'ne': 'भण्डारण गाह्रो — चाँडै बेच्नुस्',
#                        'en': 'Hard to store — sell quickly'},
#         'volatility': {'ne': 'बजार भाउ अस्थिर हुन सक्छ',
#                        'en': 'Market price can be volatile'},
#     }
#     return reasons.get(dominant_risk, {}).get(lang, dominant_risk)

# def get_selling_advice(risk_tier, lang='ne'):
#     advice = {
#         'High': {
#             'ne': (
#                 'बजार भाउ अस्थिर छ — बाली उठेपछि '
#                 'सकेसम्म चाँडै नजिकको बजार वा '
#                 'कृषि सहकारीमा बेच्नुस्।'
#             ),
#             'en': (
#                 'Price is volatile — sell as soon as '
#                 'possible after harvest at nearest '
#                 'market or cooperative.'
#             ),
#         },
#         'Medium': {
#             'ne': (
#                 'भाउ अलिकति घटबढ हुन सक्छ — '
#                 '१–२ हप्ता पर्खेर भाउ हेरी बेच्नुस्।'
#             ),
#             'en': (
#                 'Price may fluctuate — wait 1–2 weeks '
#                 'after harvest to monitor prices.'
#             ),
#         },
#         'Low': {
#             'ne': (
#                 'भाउ स्थिर छ — सहकारी वा '
#                 'स्थानीय बजारमा बेच्न सकिन्छ।'
#             ),
#             'en': (
#                 'Price is stable — sell at local '
#                 'market or cooperative.'
#             ),
#         },
#     }
#     return advice.get(risk_tier, advice['Medium']).get(lang, '')

# def get_water_label(water_req, lang='ne'):
#     labels = {
#         'Medium':     {'ne': 'मध्यम सिँचाइ',    'en': 'Moderate irrigation'},
#         'Low':        {'ne': 'कम सिँचाइ',        'en': 'Low irrigation'},
#         'Low-Medium': {'ne': 'कम–मध्यम सिँचाइ', 'en': 'Low to moderate'},
#         'High':       {'ne': 'धेरै सिँचाइ',      'en': 'High irrigation'},
#     }
#     return labels.get(water_req, {}).get(lang, water_req)

# def get_storage_advice(shelf_life, lang='ne'):
#     if lang == 'ne':
#         return (
#             f'भण्डारण अवधि: {shelf_life} — '
#             f'सुख्खा, छायाँदार ठाउँमा राख्नुस्।'
#         )
#     return (
#         f'Shelf life: {shelf_life} — '
#         f'Store in a cool, dry, ventilated place.'
#     )

# def build_recommendation_reason(crop, lang='ne'):
#     plant   = crop['plant_month']
#     harvest = ', '.join(crop['harvest_months'])
#     peak    = crop['best_harvest_month']
#     price   = crop['forecasted_price']
#     weeks   = crop['weeks_to_grow']

#     if lang == 'ne':
#         p  = NEPALI_MONTH_NAMES.get(plant,  plant)
#         h  = ', '.join([
#             NEPALI_MONTH_NAMES.get(m, m)
#             for m in crop['harvest_months']
#         ])
#         pk = NEPALI_MONTH_NAMES.get(peak, peak)
#         return (
#             f'{p} महिनामा रोप्नुस् — {h} मा उठाउन मिल्छ। '
#             f'{pk} महिनामा माग उच्च हुने अनुमान छ। '
#             f'अनुमानित भाउ: रु.{price}/के.जी. '
#             f'({weeks} हप्तामा तयार हुन्छ)।'
#         )
#     return (
#         f'Plant in {plant} — harvest in {harvest}. '
#         f'Peak demand expected in {peak}. '
#         f'Estimated price: Rs.{price}/kg '
#         f'(ready in {weeks} weeks).'
#     )


import pandas as pd
import os
from engine.nepali_calendar import get_calendar_context
from engine.feasibility_checker import run_feasibility_check, load_calendar
from engine.risk_scorer import get_risk_lookup
from engine.market_analysis import NEPALI_MONTHS

MONTH_ORDER = [
    'Baisakh', 'Jestha',  'Ashadh',  'Shrawan', 'Bhadra',
    'Ashwin',  'Kartik',  'Mangsir', 'Poush',   'Magh',
    'Falgun',  'Chaitra'
]

NEPALI_MONTH_NAMES = {
    'Baisakh':'वैशाख', 'Jestha':'जेठ',    'Ashadh':'असार',
    'Shrawan':'साउन',  'Bhadra':'भदौ',    'Ashwin':'असोज',
    'Kartik':'कार्तिक','Mangsir':'मंसिर', 'Poush':'पुस',
    'Magh':'माघ',      'Falgun':'फागुन',  'Chaitra':'चैत'
}

# ── scoring weights ───────────────────────────────────────
W_FORECAST_PRICE = 0.35
W_DEMAND_SCORE   = 0.30
W_FEASIBILITY    = 0.20
W_RISK_PENALTY   = 0.15

# ── normalize helper ──────────────────────────────────────
def normalize(series):
    mn = series.min()
    mx = series.max()
    if mx == mn:
        return pd.Series([0.5] * len(series), index=series.index)
    return (series - mn) / (mx - mn)

# ── main recommendation builder ───────────────────────────
def build_recommendations(month=None):               # ← month added
    # ctx               = get_calendar_context(month=month)
    ctx = get_calendar_context()
    feasible_crops, _ = run_feasibility_check(month=month)
    risk_lookup       = get_risk_lookup()
    calendar_df       = load_calendar()

    if not feasible_crops:
        return [], ctx

    rows = []
    for crop in feasible_crops:
        crop_key = crop['crop_key']

        # ── risk data ─────────────────────────────────────
        risk = risk_lookup.get(crop_key)
        if risk:
            risk_score    = risk['risk_score']
            risk_penalty  = risk['risk_penalty']
            risk_tier     = risk['risk_tier']
            dominant_risk = risk['dominant_risk']
            scoring_notes = risk['scoring_notes']
        else:
            risk_score    = 3.0
            risk_penalty  = 0.30
            risk_tier     = 'Medium'
            dominant_risk = 'disease'
            scoring_notes = 'Risk data not available — treat as medium risk'

        # ── calendar data ─────────────────────────────────
        cal_row = calendar_df[calendar_df['crop_key'] == crop_key]
        if not cal_row.empty:
            cal_row    = cal_row.iloc[0]
            crop_name  = cal_row['Crop Name (Common/Nepali)']
            water_req  = cal_row['Water Requirement']
            shelf_life = cal_row['Storage Shelf Life (Days)']
            diseases   = cal_row['Typical Disease Vulnerabilities']
            altitude   = cal_row['Required Altitude Range (masl)']
        else:
            crop_name  = crop_key
            water_req  = 'Medium'
            shelf_life = 'N/A'
            diseases   = 'N/A'
            altitude   = 'N/A'

        harvest_conf_score = (
            1.0 if crop.get('harvest_confidence') == 'High' else 0.5
        )

        rows.append({
            'crop_key':           crop_key,
            'crop_name':          crop_name,
            'plant_month':        crop['plant_month'],
            'plant_timing':       crop['plant_timing'],
            'harvest_months':     crop['harvest_months'],
            'best_harvest_month': crop['best_harvest_month'],
            'documented_harvest': crop['documented_harvest'],
            'harvest_overlap':    crop['harvest_overlap'],
            'harvest_confidence': crop['harvest_confidence'],
            'harvest_conf_score': harvest_conf_score,
            'weeks_to_grow':      crop['weeks_to_grow'],
            'forecasted_price':   crop['forecasted_price'],
            'demand_score':       crop['demand_score'],
            'feasibility_reason': crop['feasibility_reason'],
            'risk_score':         risk_score,
            'risk_penalty':       risk_penalty,
            'risk_tier':          risk_tier,
            'dominant_risk':      dominant_risk,
            'scoring_notes':      scoring_notes,
            'water_req':          water_req,
            'shelf_life':         shelf_life,
            'diseases':           diseases,
            'altitude':           altitude,
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return [], ctx

    # ── normalize and score ───────────────────────────────
    df['price_norm']  = normalize(df['forecasted_price'])
    df['demand_norm'] = normalize(df['demand_score'])
    df['conf_norm']   = df['harvest_conf_score']
    df['risk_norm']   = normalize(df['risk_score'])

    df['opportunity_score'] = (
        df['price_norm']  * W_FORECAST_PRICE +
        df['demand_norm'] * W_DEMAND_SCORE   +
        df['conf_norm']   * W_FEASIBILITY    -
        df['risk_norm']   * W_RISK_PENALTY
    )
    df['opportunity_score'] = (df['opportunity_score'] * 10).round(2)

    # ── rank ──────────────────────────────────────────────
    df = df.sort_values(
        'opportunity_score', ascending=False
    ).reset_index(drop=True)
    df['rank'] = df.index + 1

    return df.to_dict(orient='records'), ctx

# ── label helpers ─────────────────────────────────────────
def get_opportunity_label(score, lang='ne'):
    if lang == 'en':
        if score >= 8:   return '⭐⭐⭐ Excellent Opportunity'
        elif score >= 6: return '⭐⭐ Good Opportunity'
        elif score >= 4: return '⭐ Fair Opportunity'
        else:            return '⚠️  Plant with Caution'
    else:
        if score >= 8:   return '⭐⭐⭐ उत्कृष्ट अवसर'
        elif score >= 6: return '⭐⭐ राम्रो अवसर'
        elif score >= 4: return '⭐ ठीकठाक अवसर'
        else:            return '⚠️  सावधानीका साथ रोप्नुस्'

def get_planting_urgency(plant_timing, plant_month, lang='ne'):
    if plant_timing == 'now':
        return {
            'ne': '✅ अहिले रोप्नुस्',
            'en': '✅ Plant this month'
        }.get(lang)
    else:
        m = NEPALI_MONTH_NAMES.get(plant_month, plant_month)
        return {
            'ne': f'⏳ {m} मा रोप्न तयारी गर्नुस्',
            'en': f'⏳ Prepare to plant in {plant_month}'
        }.get(lang)

def get_risk_reason(dominant_risk, lang='ne'):
    reasons = {
        'flood':      {'ne': 'बाढीको खतरा बढी छ',
                       'en': 'High flood risk this season'},
        'drought':    {'ne': 'खडेरी र पानी अभावको खतरा छ',
                       'en': 'Risk of drought and water shortage'},
        'frost':      {'ne': 'हिमपातले बाली नोक्सान गर्न सक्छ',
                       'en': 'Frost damage risk this season'},
        'disease':    {'ne': 'किरा र रोगको खतरा बढी छ',
                       'en': 'High disease and pest pressure'},
        'storage':    {'ne': 'भण्डारण गाह्रो — चाँडै बेच्नुस्',
                       'en': 'Hard to store — sell quickly'},
        'volatility': {'ne': 'बजार भाउ अस्थिर हुन सक्छ',
                       'en': 'Market price can be volatile'},
    }
    return reasons.get(dominant_risk, {}).get(lang, dominant_risk)

def get_selling_advice(risk_tier, lang='ne'):
    advice = {
        'High': {
            'ne': (
                'बजार भाउ अस्थिर छ — बाली उठेपछि '
                'सकेसम्म चाँडै नजिकको बजार वा '
                'कृषि सहकारीमा बेच्नुस्।'
            ),
            'en': (
                'Price is volatile — sell as soon as '
                'possible after harvest at nearest '
                'market or cooperative.'
            ),
        },
        'Medium': {
            'ne': (
                'भाउ अलिकति घटबढ हुन सक्छ — '
                '१–२ हप्ता पर्खेर भाउ हेरी बेच्नुस्।'
            ),
            'en': (
                'Price may fluctuate — wait 1–2 weeks '
                'after harvest to monitor prices.'
            ),
        },
        'Low': {
            'ne': (
                'भाउ स्थिर छ — सहकारी वा '
                'स्थानीय बजारमा बेच्न सकिन्छ।'
            ),
            'en': (
                'Price is stable — sell at local '
                'market or cooperative.'
            ),
        },
    }
    return advice.get(risk_tier, advice['Medium']).get(lang, '')

def get_water_label(water_req, lang='ne'):
    labels = {
        'Medium':     {'ne': 'मध्यम सिँचाइ',    'en': 'Moderate irrigation'},
        'Low':        {'ne': 'कम सिँचाइ',        'en': 'Low irrigation'},
        'Low-Medium': {'ne': 'कम–मध्यम सिँचाइ', 'en': 'Low to moderate'},
        'High':       {'ne': 'धेरै सिँचाइ',      'en': 'High irrigation'},
    }
    return labels.get(water_req, {}).get(lang, water_req)

def get_storage_advice(shelf_life, lang='ne'):
    if lang == 'ne':
        return (
            f'भण्डारण अवधि: {shelf_life} — '
            f'सुख्खा, छायाँदार ठाउँमा राख्नुस्।'
        )
    return (
        f'Shelf life: {shelf_life} — '
        f'Store in a cool, dry, ventilated place.'
    )

def build_recommendation_reason(crop, lang='ne'):
    plant   = crop['plant_month']
    harvest = ', '.join(crop['harvest_months'])
    peak    = crop['best_harvest_month']
    price   = crop['forecasted_price']
    weeks   = crop['weeks_to_grow']

    if lang == 'ne':
        p  = NEPALI_MONTH_NAMES.get(plant,  plant)
        h  = ', '.join([
            NEPALI_MONTH_NAMES.get(m, m)
            for m in crop['harvest_months']
        ])
        pk = NEPALI_MONTH_NAMES.get(peak, peak)
        return (
            f'{p} महिनामा रोप्नुस् — {h} मा उठाउन मिल्छ। '
            f'{pk} महिनामा माग उच्च हुने अनुमान छ। '
            f'अनुमानित भाउ: रु.{price}/के.जी. '
            f'({weeks} हप्तामा तयार हुन्छ)।'
        )
    return (
        f'Plant in {plant} — harvest in {harvest}. '
        f'Peak demand expected in {peak}. '
        f'Estimated price: Rs.{price}/kg '
        f'(ready in {weeks} weeks).'
    )