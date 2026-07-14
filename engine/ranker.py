# from engine.market_scorer import get_market_scores
# from engine.risk_scorer import get_risk_lookup

# def get_ranked_crops():
#     market_results = get_market_scores()
#     risk_lookup    = get_risk_lookup()

#     ranked = []
#     for crop in market_results:
#         crop_key = crop['crop_key']

#         # get risk data for this crop
#         risk = risk_lookup.get(crop_key)
#         if risk is None:
#             continue

#         market_score = crop['market_score']
#         risk_penalty = risk['risk_penalty']

#         # opportunity score formula:
#         # market score scaled down by risk penalty
#         # plant_now crops get a 20% bonus over coming_soon
#         # out_of_season crops get a 40% penalty
#         status = crop['planting_status']
#         if status == 'plant_now':
#             timing_multiplier = 1.20
#         elif status == 'coming_soon':
#             timing_multiplier = 1.00
#         else:
#             timing_multiplier = 0.60

#         opportunity_score = round(
#             market_score * (1 - risk_penalty) * timing_multiplier,
#             2
#         )

#         ranked.append({
#             # identity
#             'crop_key':           crop_key,
#             'crop_name':          crop['crop_name'],

#             # scores
#             'opportunity_score':  opportunity_score,
#             'market_score':       market_score,
#             'risk_score':         risk['risk_score'],
#             'risk_penalty':       risk_penalty,
#             'timing_multiplier':  timing_multiplier,

#             # planting info
#             'planting_status':    status,
#             'planting_months':    crop['planting_months'],
#             'growth_weeks_min':   crop['growth_weeks_min'],
#             'growth_weeks_max':   crop['growth_weeks_max'],

#             # harvest info
#             'projected_harvest':  crop['projected_harvest'],
#             'documented_harvest': crop['documented_harvest'],
#             'harvest_confidence': crop['harvest_confidence'],

#             # risk details
#             'risk_tier':          risk['risk_tier'],
#             'dominant_risk':      risk['dominant_risk'],
#             'scoring_notes':      risk['scoring_notes'],

#             # market details
#             'price_details':      crop['price_details'],

#             # crop details
#             'storage_shelf_life': crop['storage_shelf_life'],
#             'diseases':           crop['diseases'],
#             'water_requirement':  crop['water_requirement'],
#             'altitude_min':       crop['altitude_min'],

#             # season context
#             'season':             risk['season'],
#         })

#     # sort by opportunity score highest first
#     ranked.sort(key=lambda x: x['opportunity_score'], reverse=True)

#     # assign rank numbers
#     for i, crop in enumerate(ranked):
#         crop['rank'] = i + 1

#     return ranked

from engine.market_scorer import get_market_scores
from engine.risk_scorer import get_risk_lookup

def get_ranked_crops(month=None):            # ← month added
    # market_results = get_market_scores(month=month)
    market_results = get_market_scores()
    risk_lookup    = get_risk_lookup()

    ranked = []
    for crop in market_results:
        crop_key = crop['crop_key']

        risk = risk_lookup.get(crop_key)
        if risk is None:
            continue

        market_score = crop['market_score']
        risk_penalty = risk['risk_penalty']

        status = crop['planting_status']
        if status == 'plant_now':
            timing_multiplier = 1.20
        elif status == 'coming_soon':
            timing_multiplier = 1.00
        else:
            timing_multiplier = 0.60

        opportunity_score = round(
            market_score * (1 - risk_penalty) * timing_multiplier,
            2
        )

        ranked.append({
            'crop_key':           crop_key,
            'crop_name':          crop['crop_name'],
            'opportunity_score':  opportunity_score,
            'market_score':       market_score,
            'risk_score':         risk['risk_score'],
            'risk_penalty':       risk_penalty,
            'timing_multiplier':  timing_multiplier,
            'planting_status':    status,
            'planting_months':    crop['planting_months'],
            'growth_weeks_min':   crop['growth_weeks_min'],
            'growth_weeks_max':   crop['growth_weeks_max'],
            'projected_harvest':  crop['projected_harvest'],
            'documented_harvest': crop['documented_harvest'],
            'harvest_confidence': crop['harvest_confidence'],
            'risk_tier':          risk['risk_tier'],
            'dominant_risk':      risk['dominant_risk'],
            'scoring_notes':      risk['scoring_notes'],
            'price_details':      crop['price_details'],
            'storage_shelf_life': crop['storage_shelf_life'],
            'diseases':           crop['diseases'],
            'water_requirement':  crop['water_requirement'],
            'altitude_min':       crop['altitude_min'],
            'season':             risk['season'],
        })

    ranked.sort(key=lambda x: x['opportunity_score'], reverse=True)

    for i, crop in enumerate(ranked):
        crop['rank'] = i + 1

    return ranked