import streamlit as st
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../..')
))

from ui.utils import render_css, render_footer, UI_EN, UI_NE
from ui.api_client import get_market_forecast, get_market_analysis


def render(selected_month: int, selected_lang: str):
    UI = UI_EN if selected_lang == 'en' else UI_NE

    title = (
        '📈 Market Forecast — Top Demand Crops by Month'
        if selected_lang == 'en'
        else '📈 बजार पूर्वानुमान — महिनाअनुसार उच्च माग बाली'
    )
    st.markdown(f'## {title}')

    if selected_lang == 'en':
        st.markdown("""
        <div class="tab-desc">
        Prophet AI price forecasting model trained on 5+ years
        of Kalimati market data. Shows which crops have the
        highest demand opportunity in each Nepali month.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="tab-desc">
        Prophet AI मूल्य पूर्वानुमान मोडेल — कालीमाटी बजारको
        ५+ वर्षको तथ्याङ्कमा आधारित। प्रत्येक महिनामा कुन
        बालीको माग बढी हुन्छ देखाउँछ।
        </div>""", unsafe_allow_html=True)

    tab_hist, tab_fore = st.tabs([
        '📊 Historical Demand' if selected_lang == 'en' else '📊 ऐतिहासिक माग',
        '🔮 Forecasted Demand' if selected_lang == 'en' else '🔮 पूर्वानुमानित माग',
    ])

    with tab_hist:
        with st.spinner('Loading historical analysis...' if selected_lang == 'en' else 'लोड हुँदैछ...'):
            try:
                hist_data = get_market_analysis()
                rankings  = hist_data.get('rankings', {})
            except Exception as e:
                st.error(f'Error: {e}')
                rankings = {}

        for month_name, crops in rankings.items():
            if not crops:
                continue
            with st.expander(f'📅 {month_name}', expanded=False):
                for crop in crops:
                    col1, col2, col3 = st.columns([1, 4, 2])
                    with col1:
                        st.markdown(f"**#{crop.get('rank', '')}**")
                    with col2:
                        st.markdown(crop.get('crop_key', '').replace('_', ' ').title())
                    with col3:
                        st.markdown(f"Rs.{crop.get('avg_price', '')}/kg")

    with tab_fore:
        with st.spinner('Loading forecast...' if selected_lang == 'en' else 'लोड हुँदैछ...'):
            try:
                fore_data     = get_market_forecast()
                fore_rankings = fore_data.get('forecasted_rankings', {})
            except Exception as e:
                st.error(f'Error: {e}')
                fore_rankings = {}

        for month_name, crops in fore_rankings.items():
            if not crops:
                continue
            with st.expander(f'📅 {month_name}', expanded=False):
                for crop in crops:
                    col1, col2, col3 = st.columns([1, 4, 2])
                    with col1:
                        st.markdown(f"**#{crop.get('rank', '')}**")
                    with col2:
                        st.markdown(crop.get('crop_key', '').replace('_', ' ').title())
                    with col3:
                        st.markdown(f"Rs.{crop.get('forecasted_avg', '')}/kg")

    render_footer(UI)