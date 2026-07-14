import streamlit as st
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')
))

NEPALI_MONTH_NAMES = {
    'Baisakh':'वैशाख', 'Jestha':'जेठ',    'Ashadh':'असार',
    'Shrawan':'साउन',  'Bhadra':'भदौ',    'Ashwin':'असोज',
    'Kartik':'कार्तिक','Mangsir':'मंसिर', 'Poush':'पुस',
    'Magh':'माघ',      'Falgun':'फागुन',  'Chaitra':'चैत'
}

MONTH_OPTIONS_EN = [
    'Baisakh', 'Jestha',  'Ashadh',  'Shrawan', 'Bhadra',
    'Ashwin',  'Kartik',  'Mangsir', 'Poush',   'Magh',
    'Falgun',  'Chaitra'
]
MONTH_OPTIONS_NE = [
    'वैशाख', 'जेठ',    'असार',   'साउन',   'भदौ',
    'असोज',  'कार्तिक','मंसिर',  'पुस',    'माघ',
    'फागुन', 'चैत'
]

UI_EN = {
    'app_title':         'Nepali Farmer Crop Advisory System',
    'today_label':       'Selected Month',
    'month_label':       '',
    'season_label':      'Season',
    'summary_title':     '📊 Quick Summary',
    'plant_now_label':   '✅ Plant Now',
    'coming_soon_label': '⏳ Plant Soon',
    'out_label':         '❌ Out of Season',
    'filter_title':      '🔍 Filter Crops',
    'filter_status':     'Planting Status',
    'filter_risk':       'Risk Level',
    'filter_all':        'All',
    'results_found':     'crops found',
    'no_results':        'No crops found. Try changing the filter.',
    'planting_status':   '🌱 Planting Status',
    'season':            '📅 Season',
    'risk_level':        '⚠️ Risk Level',
    'risk_reason':       '🔍 Main Reason',
    'harvest':           '🌾 Estimated Harvest',
    'water':             '💧 Irrigation',
    'price':             '💰 Market Price (Kalimati)',
    'storage':           '📦 Storage Advice',
    'selling':           '🛒 Selling Advice',
    'score_label':       'Score',
    'footer_title':      '📌 Important Notice',
    'footer_lines': [
        'This advice is based on data and is an estimate only.',
        'Always check local weather and soil conditions.',
        'Contact your nearest Agriculture Service Center.',
        'Kalimati market price information:',
    ],
}

UI_NE = {
    'app_title':         'नेपाली किसान बाली सल्लाह प्रणाली',
    'today_label':       'छानिएको महिना',
    'month_label':       'महिना',
    'season_label':      'मौसम',
    'summary_title':     '📊 संक्षिप्त सारांश',
    'plant_now_label':   '✅ अहिले रोप्नुस्',
    'coming_soon_label': '⏳ छिट्टै मिल्छ',
    'out_label':         '❌ नरोप्नुस्',
    'filter_title':      '🔍 फिल्टर गर्नुस्',
    'filter_status':     'रोपाइ स्थिति',
    'filter_risk':       'जोखिम स्तर',
    'filter_all':        'सबै',
    'results_found':     'बाली भेटियो',
    'no_results':        'कुनै बाली भेटिएन। फिल्टर परिवर्तन गर्नुस्।',
    'planting_status':   '🌱 रोपाइ स्थिति',
    'season':            '📅 मौसम',
    'risk_level':        '⚠️ जोखिम स्तर',
    'risk_reason':       '🔍 मुख्य कारण',
    'harvest':           '🌾 अनुमानित उठाइ',
    'water':             '💧 सिँचाइ',
    'price':             '💰 बजार मूल्य (कालीमाटी)',
    'storage':           '📦 भण्डारण सल्लाह',
    'selling':           '🛒 बिक्री सल्लाह',
    'score_label':       'अंक',
    'footer_title':      '📌 महत्त्वपूर्ण सूचना',
    'footer_lines': [
        'यो सल्लाह तथ्याङ्कमा आधारित अनुमान हो।',
        'स्थानीय मौसम र माटोको अवस्था पनि हेर्नुस्।',
        'नजिकको कृषि सेवा केन्द्रमा सम्पर्क गर्नुस्।',
        'कालीमाटी तरकारी बजार मूल्य सूचना:',
    ],
}

RISK_TIER_EN = {
    'High':   '🔴 High Risk',
    'Medium': '🟡 Medium Risk',
    'Low':    '🟢 Low Risk',
}

RISK_TIER_NE = {
    'High':   '🔴 उच्च जोखिम',
    'Medium': '🟡 मध्यम जोखिम',
    'Low':    '🟢 कम जोखिम',
}

CSS = """
<style>
    .header-box {
        background: linear-gradient(135deg, #2e7d32, #66bb6a);
        color: white; padding: 24px; border-radius: 14px;
        margin-bottom: 20px; text-align: center;
    }
    .card {
        background-color: white; border-radius: 12px;
        padding: 20px; margin-bottom: 20px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    .card-high-risk   { border-left: 6px solid #e53935; }
    .card-medium-risk { border-left: 6px solid #FB8C00; }
    .card-low-risk    { border-left: 6px solid #43A047; }
    .smart-card {
        background: white; border-radius: 12px;
        padding: 22px; margin-bottom: 22px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.10);
        border-top: 4px solid #1565c0;
    }
    .smart-card-rank {
        font-size: 2rem; font-weight: 800; color: #1565c0;
    }
    .score-badge {
        background-color: #e8f5e9; color: #2e7d32;
        padding: 4px 12px; border-radius: 20px;
        font-weight: bold; font-size: 0.95rem;
    }
    .smart-score-badge {
        background-color: #e3f2fd; color: #1565c0;
        padding: 4px 12px; border-radius: 20px;
        font-weight: bold; font-size: 0.95rem;
    }
    .section-label {
        color: #757575; font-size: 0.82rem;
        text-transform: uppercase; letter-spacing: 0.05em;
        margin-bottom: 2px;
    }
    .section-value {
        font-size: 1rem; color: #212121; margin-bottom: 12px;
    }
    .reason-box {
        background: #f0f4ff; border-left: 4px solid #1565c0;
        border-radius: 6px; padding: 10px 14px;
        font-size: 0.95rem; color: #1a237e; margin-top: 10px;
    }
    .summary-box {
        background-color: #f1f8e9; border-radius: 10px;
        padding: 16px 20px; margin-bottom: 24px;
        border: 1px solid #c5e1a5;
    }
    .smart-summary-box {
        background-color: #e3f2fd; border-radius: 10px;
        padding: 16px 20px; margin-bottom: 24px;
        border: 1px solid #90caf9;
    }
    .footer-box {
        background-color: #fff8e1; border-radius: 10px;
        padding: 16px 20px; margin-top: 32px;
        border: 1px solid #ffe082;
        font-size: 0.9rem; color: #5d4037;
    }
    .tab-desc {
        color: #555; font-size: 0.95rem; margin-bottom: 20px;
        padding: 10px 14px; background: #fafafa;
        border-radius: 8px; border-left: 4px solid #aaa;
    }
    .month-bar {
        background: #f9f9f9; border-radius: 10px;
        padding: 12px 16px; margin-bottom: 16px;
        border: 1px solid #e0e0e0;
    }
    .divider { border-top: 1px solid #f0f0f0; margin: 12px 0; }
    .api-error {
        background: #fff5f5; border-left: 4px solid #e53935;
        border-radius: 8px; padding: 12px 16px;
        color: #c62828; font-size: 0.9rem;
    }
</style>
"""

def render_css():
    st.markdown(CSS, unsafe_allow_html=True)

def render_footer(UI):
    footer_lines = ''.join(
        [f'• {line}<br>' for line in UI['footer_lines']]
    )
    st.markdown(f"""
    <div class="footer-box">
        <strong>{UI['footer_title']}</strong><br><br>
        {footer_lines}
        &nbsp;&nbsp;
        <a href="http://www.kalimatimarket.gov.np"
        target="_blank">www.kalimatimarket.gov.np</a>
    </div>
    """, unsafe_allow_html=True)

def render_month_selector(lang_code):
    """
    Renders month selector bar.
    Returns (selected_bs_month, season, season_label)
    """
    from ui.api_client import get_season
    try:
        from nepali_datetime import date as _npdate
        _current_bs = _npdate.today().month
    except Exception:
        _current_bs = 1

    st.markdown('<div class="month-bar">', unsafe_allow_html=True)
    col_m1, col_m2, col_m3 = st.columns([2, 2, 2])

    with col_m1:
        label         = (
            'Select Nepali Month' if lang_code == 'en'
            else 'नेपाली महिना छान्नुस्'
        )
        month_options = (
            MONTH_OPTIONS_EN if lang_code == 'en'
            else MONTH_OPTIONS_NE
        )
        selected_label = st.selectbox(
            label,
            options = month_options,
            index   = _current_bs - 1,
        )

    selected_bs_month = (
        MONTH_OPTIONS_EN.index(selected_label) + 1
        if lang_code == 'en'
        else MONTH_OPTIONS_NE.index(selected_label) + 1
    )

    with col_m2:
        season_data  = get_season(selected_bs_month)
        season       = season_data.get('season', '')
        season_label = {
            'Garmi':  'गर्मी 🌞'  if lang_code == 'ne' else 'Summer 🌞',
            'Barkhe': 'बर्खे 🌧️' if lang_code == 'ne' else 'Monsoon 🌧️',
            'Hiude':  'हिउँदे ❄️' if lang_code == 'ne' else 'Winter ❄️',
        }.get(season, season)
        st.markdown(
            f'<div style="padding-top:28px">'
            f'{"मौसम" if lang_code == "ne" else "Season"}: '
            f'<strong>{season_label}</strong></div>',
            unsafe_allow_html=True
        )

    with col_m3:
        actual_label = (
            MONTH_OPTIONS_NE[_current_bs - 1]
            if lang_code == 'ne'
            else MONTH_OPTIONS_EN[_current_bs - 1]
        )
        note = (
            f'📅 आजको महिना: {actual_label}'
            if lang_code == 'ne'
            else f'📅 Today: {actual_label}'
        )
        st.markdown(
            f'<div style="padding-top:28px;color:#888;'
            f'font-size:0.9rem">{note}</div>',
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)
    return selected_bs_month, season, season_label

def render_language_toggle():
    """Renders language toggle. Returns lang_code."""
    col_l1, col_l2, col_l3 = st.columns([4, 1, 1])
    with col_l2:
        st.markdown(
            '<div style="padding-top:8px;text-align:right">🌐</div>',
            unsafe_allow_html=True
        )
    with col_l3:
        lang = st.selectbox(
            '',
            options          = ['नेपाली', 'English'],
            label_visibility = 'collapsed',
            key              = 'lang_toggle'
        )
    return 'ne' if lang == 'नेपाली' else 'en'

def render_header(UI, selected_month_en, season_label):
    st.markdown(f"""
    <div class="header-box">
        <div style="font-size:2.2rem">🌾</div>
        <div style="font-size:1.6rem;font-weight:700;margin:6px 0">
            {UI['app_title']}
        </div>
        <div style="font-size:1rem;opacity:0.9">
            {UI['today_label']}:
            <strong>{selected_month_en} {UI['month_label']}</strong>
            &nbsp;|&nbsp;
            {UI['season_label']}: <strong>{season_label}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)

def check_api_or_stop(lang_code):
    """Checks API health. Stops app if API is down."""
    from ui.api_client import check_api_health
    ok, _ = check_api_health()
    if not ok:
        st.markdown("""
        <div class="api-error">
        ⚠️ <strong>API server not reachable.</strong>
        Please start the FastAPI backend first:<br><br>
        <code>uvicorn api.main:app --reload --port 8000</code>
        </div>
        """, unsafe_allow_html=True)
        st.stop()