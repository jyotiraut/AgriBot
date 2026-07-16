import requests
import os
import streamlit as st

BASE_URL = os.environ.get('API_BASE_URL', 'http://127.0.0.1:8000/api/v1')

def check_api_health():
    try:
        r = requests.get(f'{BASE_URL}/health', timeout=5)
        return r.status_code == 200, r.json()
    except Exception:
        return False, {}

def get_season(bs_month: int):
    try:
        r = requests.get(
            f'{BASE_URL}/season',
            params  = {'month': bs_month},
            timeout = 5
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {'season': 'Garmi', 'error': str(e)}

@st.cache_data(ttl=3600)
def get_verified_recommendations(bs_month: int, lang: str):
    r = requests.get(
        f'{BASE_URL}/recommendations',
        params  = {'month': bs_month, 'lang': lang},
        timeout = 120
    )
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600)
def get_general_dashboard(bs_month: int, lang: str):
    r = requests.get(
        f'{BASE_URL}/dashboard',
        params  = {'month': bs_month, 'lang': lang},
        timeout = 30
    )
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600)
def get_market_forecast():
    r = requests.get(
        f'{BASE_URL}/market/forecast',
        timeout = 30
    )
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600)
def get_market_analysis():
    r = requests.get(
        f'{BASE_URL}/market/analysis',
        timeout = 30
    )
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600)
def get_all_months_summary():
    r = requests.get(
        f'{BASE_URL}/crops/summary/all-months',
        timeout = 120
    )
    r.raise_for_status()
    return r.json()