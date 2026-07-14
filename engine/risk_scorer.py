import pandas as pd
import os
from engine.nepali_calendar import get_calendar_context

def load_risks():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'crop_risks.csv')
    return pd.read_csv(path)

def get_risk_scores():
    df  = load_risks()
    ctx = get_calendar_context()
    multipliers = ctx['risk_multipliers']

    results = []
    for _, row in df.iterrows():

        # apply season multipliers to each individual risk
        flood_adjusted   = round(row['flood_risk_1to5']             * multipliers['flood'],   2)
        drought_adjusted = round(row['drought_risk_1to5']           * multipliers['drought'], 2)
        frost_adjusted   = round(row['frost_risk_1to5']             * multipliers['frost'],   2)
        disease_adjusted = round(row['disease_frequency_nepal_1to5'] * multipliers['disease'], 2)

        # also factor in storage difficulty and price volatility
        storage_risk    = float(row['storage_difficulty_1to5'])
        volatility_risk = float(row['market_price_volatility_1to5'])

        # weighted composite:
        # disease and flood weighted most (0.25 each)
        # drought, frost, storage, volatility weighted equally (0.125 each)
        seasonal_composite = round(
            (flood_adjusted   * 0.25) +
            (disease_adjusted * 0.25) +
            (drought_adjusted * 0.125) +
            (frost_adjusted   * 0.125) +
            (storage_risk     * 0.125) +
            (volatility_risk  * 0.125),
            2
        )

        # normalize to 0–10 scale
        max_possible = 5 * max(multipliers.values())
        risk_score   = round((seasonal_composite / max_possible) * 10, 2)

        # risk penalty is what gets subtracted from market score (0.0 to 1.0)
        risk_penalty = round(risk_score / 10, 2)

        # human readable tier
        if risk_score >= 7:
            tier = 'High'
        elif risk_score >= 4:
            tier = 'Medium'
        else:
            tier = 'Low'

        results.append({
            'crop_key':              row['crop_key'],
            'risk_tier':             tier,
            'risk_score':            risk_score,
            'risk_penalty':          risk_penalty,
            'flood_adjusted':        flood_adjusted,
            'drought_adjusted':      drought_adjusted,
            'frost_adjusted':        frost_adjusted,
            'disease_adjusted':      disease_adjusted,
            'storage_risk':          storage_risk,
            'volatility_risk':       volatility_risk,
            'seasonal_composite':    seasonal_composite,
            'season':                ctx['season'],
            'original_risk_tier':    row['risk_tier'],
            'scoring_notes':         row['scoring_notes'],
            'dominant_risk':         get_dominant_risk(
                                        flood_adjusted,
                                        drought_adjusted,
                                        frost_adjusted,
                                        disease_adjusted,
                                        storage_risk,
                                        volatility_risk
                                     ),
        })

    return results

def get_dominant_risk(flood, drought, frost, disease, storage, volatility):
    """
    Returns the name of the highest risk factor this season.
    Used to explain risk to the farmer in plain language.
    """
    risks = {
        'flood':      flood,
        'drought':    drought,
        'frost':      frost,
        'disease':    disease,
        'storage':    storage,
        'volatility': volatility,
    }
    return max(risks, key=risks.get)

def get_risk_lookup():
    """
    Returns a dict keyed by crop_key for easy lookup in ranker.
    """
    scores = get_risk_scores()
    return {r['crop_key']: r for r in scores}