import pandas as pd
import numpy as np
import os
from nepali_datetime import date as nepali_date

NEPALI_MONTHS = [
    'Baisakh', 'Jestha',  'Ashadh',  'Shrawan', 'Bhadra',
    'Ashwin',  'Kartik',  'Mangsir', 'Poush',   'Magh',
    'Falgun',  'Chaitra'
]

MIN_RECORDS = 100
TOP_N       = 5
VALID_UNIT  = 'kg'

def load_prices():
    path = os.path.join(
        os.path.dirname(__file__), '..', 'data', 'market_prices.csv'
    )
    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'], format='%m/%d/%Y')
    df = df[df['unit'] == VALID_UNIT].copy()
    counts      = df['crop_key'].value_counts()
    valid_crops = counts[counts >= MIN_RECORDS].index
    df          = df[df['crop_key'].isin(valid_crops)].copy()
    return df

def tag_nepali_month(date_series):
    bs_months = []
    for d in date_series:
        try:
            nd = nepali_date.from_datetime_date(d.date())
            bs_months.append(nd.month)
        except:
            bs_months.append(None)
    return bs_months

def compute_monthly_averages(df):
    df = df.copy()
    df['bs_month'] = tag_nepali_month(df['date'])
    df = df.dropna(subset=['bs_month'])
    df['bs_month'] = df['bs_month'].astype(int)

    monthly = df.groupby(['crop_key', 'bs_month']).agg(
        avg_price    = ('average', 'mean'),
        max_price    = ('maximum', 'mean'),
        min_price    = ('minimum', 'mean'),
        record_count = ('average', 'count')
    ).reset_index()

    monthly['nepali_month'] = monthly['bs_month'].apply(
        lambda m: NEPALI_MONTHS[m - 1]
    )
    return monthly.round(2)

def compute_demand_opportunity_score(monthly_df):
    """
    Scores each crop-month combination using 3 signals:

    1. Relative Price Spike (40%)
       How much higher is this month's price vs the crop's
       own annual average? High spike = seasonal scarcity.

    2. Price Volatility (35%)
       Std deviation of monthly prices across the year,
       normalized per crop. High volatility = supply gaps
       that farmers can exploit.

    3. Price Trend Score (25%)
       Is the price above the crop's median? Signals
       sustained demand not just a one-off spike.

    This keeps expensive-but-rare crops (asparagus, kiwi)
    from dominating — they score low on volatility since
    their price is consistently high regardless of season.
    """
    results = []

    for crop_key, group in monthly_df.groupby('crop_key'):
        group      = group.copy()
        annual_avg = group['avg_price'].mean()
        annual_std = group['avg_price'].std()
        annual_med = group['avg_price'].median()

        # avoid division by zero for crops with flat prices
        if annual_avg == 0:
            continue

        for _, row in group.iterrows():
            # signal 1: relative spike vs own annual average
            spike_score = (row['avg_price'] - annual_avg) / annual_avg

            # signal 2: how volatile is this crop overall
            # normalized 0-1 using coefficient of variation
            cv_score = (annual_std / annual_avg) if annual_avg > 0 else 0

            # signal 3: is this month above the crop's median
            trend_score = (row['avg_price'] - annual_med) / (annual_med + 1)

            # combined demand opportunity score
            demand_score = (
                spike_score * 0.40 +
                cv_score    * 0.35 +
                trend_score * 0.25
            )

            results.append({
                'crop_key':     crop_key,
                'bs_month':     int(row['bs_month']),
                'nepali_month': row['nepali_month'],
                'avg_price':    row['avg_price'],
                'annual_avg':   round(annual_avg, 2),
                'spike_score':  round(spike_score,  4),
                'cv_score':     round(cv_score,     4),
                'trend_score':  round(trend_score,  4),
                'demand_score': round(demand_score, 4),
            })

    return pd.DataFrame(results)

def rank_crops_by_demand(demand_df, top_n=TOP_N):
    """
    For each Nepali month ranks crops by demand_score descending.
    Returns dict: { bs_month: [ {rank, crop_key, ...}, ... ] }
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
            'avg_price', 'annual_avg',
            'spike_score', 'cv_score',
            'trend_score', 'demand_score'
        ]].to_dict(orient='records')

    return rankings

def get_demand_matrix():
    """
    Pivot table of demand_score per crop per month.
    Used by price forecaster.
    """
    df         = load_prices()
    monthly_df = compute_monthly_averages(df)
    demand_df  = compute_demand_opportunity_score(monthly_df)

    matrix = demand_df.pivot_table(
        index   = 'crop_key',
        columns = 'bs_month',
        values  = 'demand_score'
    )
    matrix = matrix.fillna(0)
    return matrix

def run_market_analysis():
    df         = load_prices()
    monthly_df = compute_monthly_averages(df)
    demand_df  = compute_demand_opportunity_score(monthly_df)
    rankings   = rank_crops_by_demand(demand_df)
    matrix     = get_demand_matrix()
    return monthly_df, demand_df, rankings, matrix