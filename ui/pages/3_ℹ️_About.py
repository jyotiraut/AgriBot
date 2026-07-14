import streamlit as st
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../..')
))

from ui.utils import render_css, render_language_toggle, UI_EN, UI_NE
from ui.api_client import check_api_health

st.set_page_config(
    page_title = 'About',
    page_icon  = 'ℹ️',
    layout     = 'centered'
)

render_css()
lang_code = render_language_toggle()

st.markdown(
    '## ℹ️ About this System'
    if lang_code == 'en'
    else '## ℹ️ यो प्रणालीको बारेमा'
)

ok, health = check_api_health()
if ok:
    st.success(
        f'✅ API is running — Current month: {health.get("month_name","")} | Season: {health.get("season","")}'
        if lang_code == 'en'
        else f'✅ API चलिरहेको छ — महिना: {health.get("month_name","")} | मौसम: {health.get("season","")}'
    )
else:
    st.error('❌ API not reachable' if lang_code == 'en' else '❌ API उपलब्ध छैन')

if lang_code == 'en':
    st.markdown("""
    ### How this system works

    This tool combines **4 data layers** to give Nepali
    farmers accurate, actionable crop recommendations:

    **1. Market Analysis**
    Kalimati price data for 89 crops analyzed using a
    demand opportunity score (price spike + volatility +
    trend) to identify which months have the highest
    demand for each crop.

    **2. Price Forecasting**
    Facebook Prophet AI models trained on 5+ years of
    daily price data forecast prices for the next 12
    Nepali months.

    **3. Agronomic Feasibility**
    The system checks which crops can actually be planted
    in the current month and harvested during high-demand
    periods based on growth duration and planting windows.

    **4. LLM Silent Correction**
    Grok AI validates every recommendation for agronomic
    correctness and silently fixes any mismatches before
    the farmer sees them.

    ### Data Sources
    - Kalimati Fruits and Vegetables Market price data
    - Nepal Department of Agriculture crop calendar
    - Nepal Agricultural Research Council disease data

    ### API Endpoints
    - Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)
    - ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
    """)
else:
    st.markdown("""
    ### यो प्रणाली कसरी काम गर्छ

    यो उपकरणले **४ तथ्याङ्क तहहरू** मिलाएर नेपाली
    किसानलाई सटीक बाली सिफारिस दिन्छ:

    **१. बजार विश्लेषण**
    ८९ बालीको कालीमाटी मूल्य तथ्याङ्क विश्लेषण।

    **२. मूल्य पूर्वानुमान**
    Prophet AI मोडेलले अर्को १२ महिनाको मूल्य
    अनुमान गर्छ।

    **३. कृषि सम्भाव्यता जाँच**
    हालको महिनामा कुन बाली रोप्न मिल्छ र उठाइ
    उच्च माग अवधिमा पर्छ कि पर्दैन जाँच गर्छ।

    **४. LLM मौन सुधार**
    Grok AI ले प्रत्येक सिफारिस जाँच र सुधार गर्छ।

    ### तथ्याङ्क स्रोत
    - कालीमाटी फलफूल तरकारी बजार मूल्य तथ्याङ्क
    - नेपाल कृषि विभागको बाली पात्रो
    - नेपाल कृषि अनुसन्धान परिषद्
    """)