import streamlit as st
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')
))

from ui.utils import (
    render_css, render_footer, render_month_selector,
    render_language_toggle, render_header,
    check_api_or_stop, UI_EN, UI_NE,
    MONTH_OPTIONS_EN, NEPALI_MONTH_NAMES
)
from ui.api_client import get_verified_recommendations

st.set_page_config(
    page_title = ' Crop Advisor',
    page_icon  = '🌾',
    layout     = 'centered'
)

render_css()
check_api_or_stop('en')

lang_code = render_language_toggle()
UI        = UI_EN if lang_code == 'en' else UI_NE

selected_bs_month, season, season_label = render_month_selector(lang_code)
selected_month_en = MONTH_OPTIONS_EN[selected_bs_month - 1]
render_header(UI, selected_month_en, season_label)

# ── page content ──────────────────────────────────────────
if lang_code == 'en':
    st.markdown("""
    <div class="tab-desc">
    🌾 <strong>Expert-verified crop recommendations</strong>
    — validated and silently corrected by an agronomic AI.
    Each crop is checked for planting window, harvest timing,
    price realism, and seasonal fit.
    </div>""", unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="tab-desc">
    🌾 <strong>विज्ञ-प्रमाणित बाली सिफारिस</strong> —
    तपाईंसम्म पुग्नु अघि कृषि AI ले जाँच र सुधार गरेको।
    </div>""", unsafe_allow_html=True)

with st.spinner(
    '🔄 Fetching verified recommendations...'
    if lang_code == 'en'
    else '🔄 सिफारिस ल्याउँदै...'
):
    try:
        data     = get_verified_recommendations(
            selected_bs_month, lang_code
        )
        verified = data.get('recommendations', [])
    except Exception as e:
        st.error(f'Error: {e}')
        verified = []

if not verified:
    st.warning(
        'No recommendations available for this month.'
        if lang_code == 'en'
        else 'यस महिनाका लागि सिफारिस उपलब्ध छैन।'
    )
else:
    # summary
    st.markdown('<div class="smart-summary-box">', unsafe_allow_html=True)
    st.markdown(
        '### 📊 ' + (
            'Verified Recommendations' if lang_code == 'en'
            else 'प्रमाणित सिफारिसहरू'
        )
    )
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            '✅ Plant Now' if lang_code == 'en' else '✅ अहिले',
            len([c for c in verified if c.get('plant_timing') == 'now'])
        )
    with col2:
        st.metric(
            '🔧 Corrected' if lang_code == 'en' else '🔧 सुधार',
            len([c for c in verified if c.get('was_corrected')])
        )
    with col3:
        st.metric(
            '⭐ High Opp.' if lang_code == 'en' else '⭐ उच्च',
            len([c for c in verified
                 if float(c.get('opportunity_score', 0)) >= 6])
        )
    with col4:
        st.metric(
            '🌾 Total' if lang_code == 'en' else '🌾 जम्मा',
            len(verified)
        )
    st.markdown('</div>', unsafe_allow_html=True)

    for crop in verified:
        risk_class = {
            'High':   'card-high-risk',
            'Medium': 'card-medium-risk',
            'Low':    'card-low-risk',
        }.get(crop.get('risk_tier', 'Medium'), '')

        st.markdown(
            f'<div class="smart-card {risk_class}">',
            unsafe_allow_html=True
        )

        col_rank, col_title, col_score = st.columns([1, 5, 2])
        with col_rank:
            st.markdown(
                f'<div class="smart-card-rank">#{crop["rank"]}</div>',
                unsafe_allow_html=True
            )
        with col_title:
            name = (
                crop.get('crop_name_ne', crop.get('crop_key',''))
                if lang_code == 'ne'
                else crop.get('crop_name_en', crop.get('crop_key',''))
            )
            st.markdown(f'### {name}')
            st.markdown(
                crop.get('opportunity_label_ne','')
                if lang_code == 'ne'
                else crop.get('opportunity_label_en','')
            )
        with col_score:
            score = crop.get('opportunity_score', 0)
            label = 'Score' if lang_code == 'en' else 'अंक'
            st.markdown(
                f'<div class="smart-score-badge"'
                f' style="margin-top:16px">'
                f'{label}: {score}/10</div>',
                unsafe_allow_html=True
            )

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                f'<div class="section-label">'
                f'{"🌱 Planting" if lang_code == "en" else "🌱 रोपाइ"}'
                f'</div>', unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="section-value">'
                f'{crop.get("planting_urgency_en","") if lang_code == "en" else crop.get("planting_urgency_ne","")}'
                f'</div>', unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                f'<div class="section-label">'
                f'{"🌾 Harvest" if lang_code == "en" else "🌾 उठाइ"}'
                f'</div>', unsafe_allow_html=True
            )
            harvest = (
                ', '.join(crop.get('harvest_months', []))
                if lang_code == 'en'
                else ', '.join(crop.get('harvest_months_ne', []))
            )
            st.markdown(
                f'<div class="section-value">{harvest}</div>',
                unsafe_allow_html=True
            )

        col3, col4 = st.columns(2)
        with col3:
            st.markdown(
                f'<div class="section-label">'
                f'{"📈 Peak Demand" if lang_code == "en" else "📈 उच्च माग"}'
                f'</div>', unsafe_allow_html=True
            )
            peak = crop.get('best_harvest_month','')
            if lang_code == 'ne':
                peak = NEPALI_MONTH_NAMES.get(peak, peak)
            st.markdown(
                f'<div class="section-value">{peak}</div>',
                unsafe_allow_html=True
            )
        with col4:
            st.markdown(
                f'<div class="section-label">'
                f'{"💰 Forecast Price" if lang_code == "en" else "💰 अनुमानित भाउ"}'
                f'</div>', unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="section-value">'
                f'Rs.{crop.get("forecasted_price",0)}/kg</div>',
                unsafe_allow_html=True
            )

        col5, col6 = st.columns(2)
        with col5:
            st.markdown(
                f'<div class="section-label">'
                f'{"⏱️ Growth" if lang_code == "en" else "⏱️ बढ्ने समय"}'
                f'</div>', unsafe_allow_html=True
            )
            suffix = ' weeks' if lang_code == 'en' else ' हप्ता'
            st.markdown(
                f'<div class="section-value">'
                f'{crop.get("weeks_to_grow","N/A")}{suffix}</div>',
                unsafe_allow_html=True
            )
        with col6:
            st.markdown(
                f'<div class="section-label">'
                f'{"⚠️ Risk" if lang_code == "en" else "⚠️ जोखिम"}'
                f'</div>', unsafe_allow_html=True
            )
            risk   = crop.get('risk_display_en','') if lang_code == 'en' else crop.get('risk_display_ne','')
            reason = crop.get('risk_reason_en','')  if lang_code == 'en' else crop.get('risk_reason_ne','')
            st.markdown(
                f'<div class="section-value">{risk} — {reason}</div>',
                unsafe_allow_html=True
            )

        col7, col8 = st.columns(2)
        with col7:
            st.markdown(
                f'<div class="section-label">'
                f'{"💧 Irrigation" if lang_code == "en" else "💧 सिँचाइ"}'
                f'</div>', unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="section-value">'
                f'{crop.get("water_label_en","") if lang_code == "en" else crop.get("water_label_ne","")}'
                f'</div>', unsafe_allow_html=True
            )
        with col8:
            st.markdown(
                f'<div class="section-label">'
                f'{"📦 Storage" if lang_code == "en" else "📦 भण्डारण"}'
                f'</div>', unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="section-value">'
                f'{crop.get("storage_advice_en","") if lang_code == "en" else crop.get("storage_advice_ne","")}'
                f'</div>', unsafe_allow_html=True
            )

        st.markdown(
            f'<div class="section-label">'
            f'{"🛒 Selling" if lang_code == "en" else "🛒 बिक्री"}'
            f'</div>', unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="section-value">'
            f'{crop.get("selling_tip_en","") if lang_code == "en" else crop.get("selling_tip_ne","")}'
            f'</div>', unsafe_allow_html=True
        )

        note = (
            crop.get('expert_note_en','') if lang_code == 'en'
            else crop.get('expert_note_ne','')
        )
        if note:
            st.markdown(
                f'<div class="reason-box">'
                f'<strong>{"💡 Expert Note" if lang_code == "en" else "💡 विज्ञ सल्लाह"}:</strong> {note}'
                f'</div>', unsafe_allow_html=True
            )

        st.markdown('</div>', unsafe_allow_html=True)

render_footer(UI)