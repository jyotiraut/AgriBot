#to show options for selecting months.
from nepali_datetime import date as nepali_date
import json
import os

# override for manual month selection from UI
_OVERRIDE_MONTH = None

def load_month_map():
    path = os.path.join(
        os.path.dirname(__file__), '..', 'data', 'nepali_months_map.json'
    )
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_current_nepali_month():
    today = nepali_date.today()
    return today.month

def get_month_name(bs_month):
    data = load_month_map()
    for m in data['months']:
        if m['bs_month'] == bs_month:
            return m['name']
    return None

def get_season_for_month(bs_month):
    data = load_month_map()
    for season, months in data['seasons'].items():
        if bs_month in months:
            return season
    return None

def get_risk_multipliers_for_season(season):
    data = load_month_map()
    return data['season_risks'][season]

def get_calendar_context(bs_month=None):
    """
    Returns calendar context for a given BS month.
    Priority: explicit bs_month arg > _OVERRIDE_MONTH > today's date
    """
    global _OVERRIDE_MONTH

    if bs_month is None:
        bs_month = _OVERRIDE_MONTH

    if bs_month is None:
        bs_month = get_current_nepali_month()

    month_name  = get_month_name(bs_month)
    season      = get_season_for_month(bs_month)
    multipliers = get_risk_multipliers_for_season(season)

    return {
        'bs_month':         bs_month,
        'month_name':       month_name,
        'season':           season,
        'risk_multipliers': multipliers,
        'is_manual':        True,
    }

def set_override_month(bs_month):
    """Call this once from UI or main.py to set the active month."""
    global _OVERRIDE_MONTH
    _OVERRIDE_MONTH = bs_month