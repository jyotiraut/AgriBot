import pandas as pd
import numpy as np
import os
import json
import warnings
from datetime import datetime, timezone
warnings.filterwarnings('ignore')

from prophet import Prophet
from nepali_datetime import date as nepali_date
from engine.market_analysis import (
    load_prices,
    compute_monthly_averages,
    compute_demand_opportunity_score,
    NEPALI_MONTHS
)

MIN_RECORDS   = 100
FORECAST_DAYS = 365
VALID_UNIT    = 'kg'
CACHE_PATH    = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'forecast_cache.csv'
)
CACHE_META_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'forecast_cache_meta.json'
)


def cache_generated_at() -> str | None:
    """ISO timestamp of the last successful run_all_forecasts(force_retrain=True),
    or None if the cache predates this tracking / meta file is missing. Lets
    callers (API responses, the Streamlit dashboard) show how stale the
    forecast is instead of presenting it as always-fresh."""
    try:
        with open(CACHE_META_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get('generated_at')
    except (FileNotFoundError, json.JSONDecodeError):
        return None

# ── nepali month tagger ───────────────────────────────────
def tag_nepali_month(date_series):
    bs_months = []
    for d in date_series:
        try:
            nd = nepali_date.from_datetime_date(d.date())
            bs_months.append(nd.month)
        except:
            bs_months.append(None)
    return bs_months

# ── single crop prophet model ─────────────────────────────
def train_and_forecast(crop_df, crop_key, forecast_days=FORECAST_DAYS):
    """
    Trains Prophet on one crop's daily price history.
    Returns daily forecast dataframe.
    """
    ts = crop_df[['date', 'average']].rename(
        columns={'date': 'ds', 'average': 'y'}
    ).copy()

    # remove outliers beyond 3 std devs
    mean = ts['y'].mean()
    std  = ts['y'].std()
    ts   = ts[
        (ts['y'] >= mean - 3 * std) &
        (ts['y'] <= mean + 3 * std)
    ].copy()

    model = Prophet(
        yearly_seasonality      = True,
        weekly_seasonality      = False,
        daily_seasonality       = False,
        seasonality_mode        = 'multiplicative',
        changepoint_prior_scale = 0.1,
        interval_width          = 0.80
    )
    model.fit(ts)

    future          = model.make_future_dataframe(periods=forecast_days)
    forecast        = model.predict(future)
    last_date       = ts['ds'].max()
    future_forecast = forecast[forecast['ds'] > last_date][[
        'ds', 'yhat', 'yhat_lower', 'yhat_upper'
    ]].copy()

    future_forecast['yhat']       = future_forecast['yhat'].clip(lower=0)
    future_forecast['yhat_lower'] = future_forecast['yhat_lower'].clip(lower=0)
    future_forecast['yhat_upper'] = future_forecast['yhat_upper'].clip(lower=0)
    future_forecast['crop_key']   = crop_key
    return future_forecast

# ── aggregate daily forecast → nepali monthly ─────────────
def aggregate_to_nepali_months(forecast_df):
    forecast_df             = forecast_df.copy()
    forecast_df['bs_month'] = tag_nepali_month(forecast_df['ds'])
    forecast_df             = forecast_df.dropna(subset=['bs_month'])
    forecast_df['bs_month'] = forecast_df['bs_month'].astype(int)

    monthly = forecast_df.groupby(
        ['crop_key', 'bs_month']
    ).agg(
        forecasted_avg   = ('yhat',       'mean'),
        forecasted_lower = ('yhat_lower', 'mean'),
        forecasted_upper = ('yhat_upper', 'mean'),
        forecast_days    = ('yhat',       'count')
    ).reset_index()

    monthly['nepali_month'] = monthly['bs_month'].apply(
        lambda m: NEPALI_MONTHS[m - 1]
    )
    return monthly.round(2)

# ── compute demand score on forecasted prices ─────────────
def compute_forecasted_demand_scores(forecast_monthly_df):
    """
    Applies the same demand opportunity scoring logic
    (spike + volatility + trend) but on forecasted prices
    instead of historical prices.
    """
    results = []

    for crop_key, group in forecast_monthly_df.groupby('crop_key'):
        group      = group.copy()
        annual_avg = group['forecasted_avg'].mean()
        annual_std = group['forecasted_avg'].std()
        annual_med = group['forecasted_avg'].median()

        if annual_avg == 0:
            continue

        for _, row in group.iterrows():
            spike_score = (row['forecasted_avg'] - annual_avg) / annual_avg
            cv_score    = (annual_std / annual_avg) if annual_avg > 0 else 0
            trend_score = (
                (row['forecasted_avg'] - annual_med) / (annual_med + 1)
            )

            demand_score = (
                spike_score * 0.40 +
                cv_score    * 0.35 +
                trend_score * 0.25
            )

            results.append({
                'crop_key':        crop_key,
                'bs_month':        int(row['bs_month']),
                'nepali_month':    row['nepali_month'],
                'forecasted_avg':  row['forecasted_avg'],
                'forecasted_lower': row['forecasted_lower'],
                'forecasted_upper': row['forecasted_upper'],
                'annual_avg':      round(annual_avg, 2),
                'spike_score':     round(spike_score,  4),
                'cv_score':        round(cv_score,     4),
                'trend_score':     round(trend_score,  4),
                'demand_score':    round(demand_score, 4),
            })

    return pd.DataFrame(results)

# ── rank crops by forecasted demand ──────────────────────
def rank_by_forecasted_demand(demand_df, top_n=5):
    """
    For each Nepali month ranks crops by forecasted
    demand_score descending.
    """
    rankings = {}
    for month_num in range(1, 13):
        month_data = demand_df[
            demand_df['bs_month'] == month_num
        ].copy()
        month_data = month_data.sort_values(
            'demand_score', ascending=False
        )
        month_data = month_data.head(top_n).reset_index(drop=True)
        month_data['rank'] = month_data.index + 1

        rankings[month_num] = month_data[[
            'rank', 'crop_key', 'nepali_month',
            'forecasted_avg', 'forecasted_lower',
            'forecasted_upper', 'demand_score'
        ]].to_dict(orient='records')

    return rankings

# ── batch all crops ───────────────────────────────────────
def run_all_forecasts(force_retrain=False):
    """
    Trains Prophet models for all eligible crops.
    Caches results to forecast_cache.csv.
    Set force_retrain=True to retrain from scratch.
    """
    if os.path.exists(CACHE_PATH) and not force_retrain:
        print('[ok] Loading forecasts from cache...')
        return pd.read_csv(CACHE_PATH)

    df    = load_prices()
    crops = df['crop_key'].unique()
    all_results = []

    print(f'Training Prophet models for {len(crops)} crops...')
    print('This will take a few minutes. Please wait.\n')

    for i, crop_key in enumerate(crops):
        crop_df = df[df['crop_key'] == crop_key].copy()
        try:
            print(f'  [{i+1}/{len(crops)}] Forecasting: {crop_key}')
            forecast = train_and_forecast(crop_df, crop_key)
            monthly  = aggregate_to_nepali_months(forecast)
            all_results.append(monthly)
        except Exception as e:
            print(f'  [skip] Skipped {crop_key}: {e}')
            continue

    if not all_results:
        raise ValueError('No forecasts generated. Check your data.')

    combined = pd.concat(all_results, ignore_index=True)
    combined.to_csv(CACHE_PATH, index=False)
    with open(CACHE_META_PATH, 'w', encoding='utf-8') as f:
        json.dump({'generated_at': datetime.now(timezone.utc).isoformat()}, f)
    print(f'\n[ok] Forecasts saved to {CACHE_PATH}')
    return combined

# ── full analysis entry point ─────────────────────────────
def get_full_price_analysis():
    """
    Returns:
      - historical_rankings : top 5 crops per month by historical demand
      - forecasted_rankings : top 5 crops per month by forecasted demand
      - forecast_df         : full forecast dataframe for feasibility checker
      - demand_scores_df    : forecasted demand scores per crop per month
    """
    # historical demand scores
    df             = load_prices()
    monthly_df     = compute_monthly_averages(df)
    hist_demand_df = compute_demand_opportunity_score(monthly_df)
    hist_rankings  = _rank_historical(hist_demand_df)

    # forecasted demand scores
    forecast_raw       = run_all_forecasts()
    forecast_demand_df = compute_forecasted_demand_scores(forecast_raw)
    fore_rankings      = rank_by_forecasted_demand(forecast_demand_df)

    return {
        'historical_rankings':  hist_rankings,
        'forecasted_rankings':  fore_rankings,
        'forecast_df':          forecast_raw,
        'demand_scores_df':     forecast_demand_df,
    }

def _rank_historical(demand_df, top_n=5):
    rankings = {}
    for month_num in range(1, 13):
        month_data = demand_df[
            demand_df['bs_month'] == month_num
        ].copy()
        month_data = month_data.sort_values(
            'demand_score', ascending=False
        )
        month_data = month_data.head(top_n).reset_index(drop=True)
        month_data['rank'] = month_data.index + 1
        rankings[month_num] = month_data.to_dict(orient='records')
    return rankings