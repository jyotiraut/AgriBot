import streamlit as st
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../..')
))

from ui.utils import (
    render_css, render_footer,
    UI_EN, UI_NE,
    MONTH_OPTIONS_EN, RISK_TIER_EN, RISK_TIER_NE
)
from ui.api_client import get_general_dashboard


def render(selected_month: int, selected_lang: str):
    UI        = UI_EN        if selected_lang == 'en' else UI_NE
    RISK_TIER = RISK_TIER_EN if selected_lang == 'en' else RISK_TIER_NE

    if selected_lang == 'en':
        st.markdown("""
        <div class="tab-desc">
        📋 <strong>General seasonal crop status</strong> —
        all crops with planting window, risk level,
        and market price information.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="tab-desc">
        📋 <strong>सामान्य मौसमी बाली स्थिति</strong> —
        सबै बालीहरूको रोपाइ अवस्था र बजार मूल्य।
        </div>""", unsafe_allow_html=True)

    try:
        data  = get_general_dashboard(selected_month, selected_lang)
        cards = data.get('cards', [])
    except Exception as e:
        st.error(f'Error: {e}')
        cards = []

    plant_now     = [c for c in cards if '✅' in str(c.get('planting_status', ''))]
    coming_soon   = [c for c in cards if '⏳' in str(c.get('planting_status', ''))]
    out_of_season = [c for c in cards if '❌' in str(c.get('planting_status', ''))]

    st.markdown('<div class="summary-box">', unsafe_allow_html=True)
    st.markdown(f"### {UI['summary_title']}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(UI['plant_now_label'],   len(plant_now))
    with col2:
        st.metric(UI['coming_soon_label'], len(coming_soon))
    with col3:
        st.metric(UI['out_label'],         len(out_of_season))
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f"### {UI['filter_title']}")
    col_a, col_b = st.columns(2)
    with col_a:
        status_filter = st.selectbox(
            UI['filter_status'],
            [UI['filter_all'], UI['plant_now_label'],
             UI['coming_soon_label'], UI['out_label']],
            key="gen_status_filter"
        )
    with col_b:
        risk_filter = st.selectbox(
            UI['filter_risk'],
            [UI['filter_all']] + list(RISK_TIER.values()),
            key="gen_risk_filter"
        )

    filtered = cards
    if status_filter != UI['filter_all']:
        filtered = [c for c in filtered if status_filter in str(c.get('planting_status', ''))]
    if risk_filter != UI['filter_all']:
        filtered = [c for c in filtered if risk_filter in str(c.get('risk_level', ''))]

    st.markdown(f"**{len(filtered)} {UI['results_found']}**")
    st.markdown('---')

    if not filtered:
        st.warning(UI['no_results'])
    else:
        for card in filtered:
            risk_class = {
                '🔴 High Risk':    'card-high-risk',
                '🔴 उच्च जोखिम':  'card-high-risk',
                '🟡 Medium Risk':  'card-medium-risk',
                '🟡 मध्यम जोखिम': 'card-medium-risk',
                '🟢 Low Risk':     'card-low-risk',
                '🟢 कम जोखिम':    'card-low-risk',
            }.get(card.get('risk_level', ''), 'card')

            st.markdown(f'<div class="card {risk_class}">', unsafe_allow_html=True)

            col_rank, col_title, col_score = st.columns([1, 5, 2])
            with col_rank:
                st.markdown(
                    f'<div style="font-size:2rem;font-weight:bold;color:#2e7d32">'
                    f'#{card.get("rank", "")}</div>',
                    unsafe_allow_html=True
                )
            with col_title:
                st.markdown(f'### {card.get("crop_name", "")}')
                st.markdown(card.get('opportunity_label', ''))
            with col_score:
                st.markdown(
                    f'<div class="score-badge" style="margin-top:16px">'
                    f'{UI["score_label"]}: {card.get("opportunity_score", "")}/10</div>',
                    unsafe_allow_html=True
                )

            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f'<div class="section-label">{UI["planting_status"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-value">{card.get("planting_status", "")}</div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div class="section-label">{UI["season"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-value">{card.get("season", "")}</div>', unsafe_allow_html=True)

            col3, col4 = st.columns(2)
            with col3:
                st.markdown(f'<div class="section-label">{UI["risk_level"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-value">{card.get("risk_level", "")}</div>', unsafe_allow_html=True)
            with col4:
                st.markdown(f'<div class="section-label">{UI["risk_reason"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-value">{card.get("risk_reason", "")}</div>', unsafe_allow_html=True)

            col5, col6 = st.columns(2)
            with col5:
                st.markdown(f'<div class="section-label">{UI["harvest"]}</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="section-value">'
                    f'{", ".join(card.get("harvest_months", []))}</div>',
                    unsafe_allow_html=True
                )
            with col6:
                st.markdown(f'<div class="section-label">{UI["water"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-value">{card.get("water_requirement", "")}</div>', unsafe_allow_html=True)

            st.markdown(f'<div class="section-label">{UI["price"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="section-value">{card.get("price_info", "")}</div>', unsafe_allow_html=True)

            col7, col8 = st.columns(2)
            with col7:
                st.markdown(f'<div class="section-label">{UI["storage"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-value">{card.get("storage_advice", "")}</div>', unsafe_allow_html=True)
            with col8:
                st.markdown(f'<div class="section-label">{UI["selling"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-value">{card.get("selling_advice", "")}</div>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

    render_footer(UI)