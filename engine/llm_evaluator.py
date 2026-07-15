import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from config import get_settings
from engine.nepali_calendar import get_calendar_context
from engine.smart_recommender import build_recommendations

load_dotenv()
_settings = get_settings()

MONTH_ORDER = [
    'Baisakh', 'Jestha',  'Ashadh',  'Shrawan', 'Bhadra',
    'Ashwin',  'Kartik',  'Mangsir', 'Poush',   'Magh',
    'Falgun',  'Chaitra'
]

NEPALI_MONTH_NAMES = {
    'Baisakh':'वैशाख', 'Jestha':'जेठ',    'Ashadh':'असार',
    'Shrawan':'साउन',  'Bhadra':'भदौ',    'Ashwin':'असोज',
    'Kartik':'कार्तिक','Mangsir':'मंसिर', 'Poush':'पुस',
    'Magh':'माघ',      'Falgun':'फागुन',  'Chaitra':'चैत'
}


# ── Gemini client (via OpenAI-compatible endpoint) ────────
def get_client():
    api_key = _settings.google_api_key or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError(
            'google_api_key not found. '
            'Set GOOGLE_API_KEY in your .env file or environment variables.'
        )
    return OpenAI(api_key=api_key, base_url=_settings.gemini_base_url)

# ── system prompt ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are a senior agronomist and agricultural economist 
specializing in Nepal's farming calendar, Kalimati market 
price dynamics, and Nepali Bikram Sambat (BS) seasonal cycles.

You receive crop recommendations from an AI system.
Your job is NOT just to validate — you are a SILENT CORRECTOR.

For each crop you must:
1. CHECK if the recommendation is agronomically correct
2. If correct → keep it and enhance with expert notes
3. If incorrect or suspicious → FIX IT silently:
   - Correct the planting month
   - Correct the harvest months
   - Adjust unrealistic prices
   - Replace with a better alternative crop if needed
4. NEVER return an empty list — always return 5 crops
5. If fewer than 5 valid crops exist in the input,
   ADD new crops from your agronomic knowledge that
   are suitable for the given BS month and season

Every crop in your output must be READY TO SHOW to a farmer.
No flags, no warnings to the farmer — just clean, correct,
actionable recommendations.

Return ONLY a valid JSON array of exactly 5 crops.
Each item must have these exact fields:
{
  "rank": 1,
  "crop_key": "string (snake_case)",
  "crop_name_en": "English common name",
  "crop_name_ne": "नेपाली नाम",
  "plant_month": "Nepali month name in English",
  "plant_timing": "now" or "next",
  "harvest_months": ["Month1", "Month2"],
  "best_harvest_month": "MonthName",
  "forecasted_price": 85.0,
  "weeks_to_grow": "10-14",
  "risk_tier": "High" or "Medium" or "Low",
  "dominant_risk": "flood" or "drought" or "frost" or "disease" or "storage" or "volatility",
  "water_req": "Medium" or "Low" or "High" or "Low-Medium",
  "shelf_life": "shelf life description",
  "opportunity_score": 7.5,
  "was_corrected": false,
  "correction_note": null,
  "expert_note_en": "1-2 sentence expert farming advice in English",
  "expert_note_ne": "१-२ वाक्य विज्ञ कृषि सल्लाह नेपालीमा",
  "selling_tip_en": "specific selling advice for this crop in English",
  "selling_tip_ne": "यो बालीको बिक्री सल्लाह नेपालीमा"
}

Important rules:
- plant_month must be a valid Nepali month for planting this crop
- harvest_months must logically follow from plant_month + weeks_to_grow
- forecasted_price must be realistic for Kalimati market
- opportunity_score must be between 0 and 10
- was_corrected = true if you changed anything from the input
- correction_note = brief internal note of what you fixed (not shown to farmer)
- Return ONLY the JSON array, no other text
"""

# ── build prompt ──────────────────────────────────────────
def build_correction_prompt(recommendations, ctx):
    lines = [
        f"Current BS Month : {ctx['month_name']} (Month {ctx['bs_month']})",
        f"Current Season   : {ctx['season']}",
        f"Total crops from recommender: {len(recommendations)}",
        "",
        "Crops to validate, correct and enhance:",
        ""
    ]

    for i, crop in enumerate(recommendations):
        lines.append(f"Crop {i+1}:")
        lines.append(f"  crop_key          : {crop['crop_key']}")
        lines.append(f"  crop_name         : {crop['crop_name']}")
        lines.append(f"  plant_month       : {crop['plant_month']}")
        lines.append(f"  plant_timing      : {crop['plant_timing']}")
        lines.append(
            f"  harvest_months    : {', '.join(crop['harvest_months'])}"
        )
        lines.append(
            f"  best_harvest_month: {crop['best_harvest_month']}"
        )
        lines.append(
            f"  forecasted_price  : Rs.{crop['forecasted_price']}/kg"
        )
        lines.append(f"  demand_score      : {crop['demand_score']}")
        lines.append(f"  risk_tier         : {crop['risk_tier']}")
        lines.append(
            f"  dominant_risk     : {crop['dominant_risk']}"
        )
        lines.append(f"  weeks_to_grow     : {crop['weeks_to_grow']}")
        lines.append(
            f"  harvest_confidence: {crop['harvest_confidence']}"
        )
        lines.append(f"  water_req         : {crop['water_req']}")
        lines.append(f"  shelf_life        : {crop['shelf_life']}")
        lines.append(
            f"  opportunity_score : {crop['opportunity_score']}"
        )
        lines.append("")

    lines.append(
        "Validate, silently correct any issues, enhance with "
        "expert notes, and return exactly 5 crops as JSON array."
    )
    return "\n".join(lines)

# ── call Grok ─────────────────────────────────────────────
def call_grok(prompt, system_prompt=SYSTEM_PROMPT):
    client   = get_client()
    response = client.chat.completions.create(
        model       = _settings.llm_model,
        messages    = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': prompt},
        ],
        temperature = 0.2,
        max_tokens  = 4000,
    )
    return response.choices[0].message.content.strip()

# ── parse response ────────────────────────────────────────
def parse_llm_response(raw_response):
    try:
        clean = raw_response
        if '```json' in clean:
            clean = clean.split('```json')[1].split('```')[0].strip()
        elif '```' in clean:
            clean = clean.split('```')[1].split('```')[0].strip()

        parsed = json.loads(clean)

        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict) and 'crops' in parsed:
            return parsed['crops']
        elif isinstance(parsed, dict) and 'recommendations' in parsed:
            return parsed['recommendations']
        return parsed

    except json.JSONDecodeError as e:
        print(f'⚠️  JSON parse error: {e}')
        print(f'Raw response snippet: {raw_response[:300]}')
        return []

# ── enrich with display fields ────────────────────────────
def enrich_crop(crop, lang='ne'):
    """
    Adds translated display fields to each LLM-verified crop.
    """
    risk_tier = crop.get('risk_tier', 'Medium')
    dominant  = crop.get('dominant_risk', 'disease')
    score     = crop.get('opportunity_score', 5.0)
    plant_m   = crop.get('plant_month', '')
    timing    = crop.get('plant_timing', 'now')

    # opportunity label
    if score >= 8:
        opp_en = '⭐⭐⭐ Excellent Opportunity'
        opp_ne = '⭐⭐⭐ उत्कृष्ट अवसर'
    elif score >= 6:
        opp_en = '⭐⭐ Good Opportunity'
        opp_ne = '⭐⭐ राम्रो अवसर'
    elif score >= 4:
        opp_en = '⭐ Fair Opportunity'
        opp_ne = '⭐ ठीकठाक अवसर'
    else:
        opp_en = '⚠️ Plant with Caution'
        opp_ne = '⚠️ सावधानीका साथ रोप्नुस्'

    # planting urgency
    if timing == 'now':
        urg_en = '✅ Plant this month'
        urg_ne = '✅ अहिले रोप्नुस्'
    else:
        m_ne   = NEPALI_MONTH_NAMES.get(plant_m, plant_m)
        urg_en = f'⏳ Prepare to plant in {plant_m}'
        urg_ne = f'⏳ {m_ne} मा रोप्न तयारी गर्नुस्'

    # risk tier display
    risk_display = {
        'High':   {'en': '🔴 High Risk',   'ne': '🔴 उच्च जोखिम'},
        'Medium': {'en': '🟡 Medium Risk', 'ne': '🟡 मध्यम जोखिम'},
        'Low':    {'en': '🟢 Low Risk',    'ne': '🟢 कम जोखिम'},
    }.get(risk_tier, {'en': '🟡 Medium Risk', 'ne': '🟡 मध्यम जोखिम'})

    # dominant risk reason
    risk_reasons = {
        'flood':      {'en': 'High flood risk this season',
                       'ne': 'बाढीको खतरा बढी छ'},
        'drought':    {'en': 'Risk of drought and water shortage',
                       'ne': 'खडेरी र पानी अभावको खतरा छ'},
        'frost':      {'en': 'Frost damage risk this season',
                       'ne': 'हिमपातले बाली नोक्सान गर्न सक्छ'},
        'disease':    {'en': 'High disease and pest pressure',
                       'ne': 'किरा र रोगको खतरा बढी छ'},
        'storage':    {'en': 'Hard to store — sell quickly',
                       'ne': 'भण्डारण गाह्रो — चाँडै बेच्नुस्'},
        'volatility': {'en': 'Market price can be volatile',
                       'ne': 'बजार भाउ अस्थिर हुन सक्छ'},
    }
    risk_reason = risk_reasons.get(
        dominant, {'en': dominant, 'ne': dominant}
    )

    # water label
    water_labels = {
        'Medium':     {'en': 'Moderate irrigation', 'ne': 'मध्यम सिँचाइ'},
        'Low':        {'en': 'Low irrigation',      'ne': 'कम सिँचाइ'},
        'Low-Medium': {'en': 'Low to moderate',     'ne': 'कम–मध्यम सिँचाइ'},
        'High':       {'en': 'High irrigation',     'ne': 'धेरै सिँचाइ'},
    }
    water = water_labels.get(
        crop.get('water_req', 'Medium'),
        {'en': 'Moderate irrigation', 'ne': 'मध्यम सिँचाइ'}
    )

    # storage advice
    shelf = crop.get('shelf_life', 'N/A')
    storage_en = (
        f'Shelf life: {shelf} — '
        f'Store in cool, dry, ventilated place.'
    )
    storage_ne = (
        f'भण्डारण अवधि: {shelf} — '
        f'सुख्खा, छायाँदार ठाउँमा राख्नुस्।'
    )

    # harvest months in nepali
    harvest_ne = [
        NEPALI_MONTH_NAMES.get(m, m)
        for m in crop.get('harvest_months', [])
    ]

    crop['opportunity_label_en'] = opp_en
    crop['opportunity_label_ne'] = opp_ne
    crop['planting_urgency_en']  = urg_en
    crop['planting_urgency_ne']  = urg_ne
    crop['risk_display_en']      = risk_display['en']
    crop['risk_display_ne']      = risk_display['ne']
    crop['risk_reason_en']       = risk_reason['en']
    crop['risk_reason_ne']       = risk_reason['ne']
    crop['water_label_en']       = water['en']
    crop['water_label_ne']       = water['ne']
    crop['storage_advice_en']    = storage_en
    crop['storage_advice_ne']    = storage_ne
    crop['harvest_months_ne']    = harvest_ne

    return crop

# ── main entry point ──────────────────────────────────────
def run_llm_evaluation(lang='en'):
    """
    Full silent correction pipeline:
    1. Get smart recommendations
    2. Send to Grok for silent correction
    3. Parse and enrich corrected output
    4. Return final clean list ready for dashboard
    """
    print('🔄 Getting smart recommendations...')
    recommendations, ctx = build_recommendations()

    if not recommendations:
        print('⚠️  No recommendations — asking LLM to generate from scratch...')
        recommendations = []

    print(
        f'📤 Sending {len(recommendations)} crops to Grok '
        f'for silent correction...'
    )
    prompt       = build_correction_prompt(recommendations, ctx)
    raw_response = call_grok(prompt)

    print('📥 Parsing corrected output...')
    corrected = parse_llm_response(raw_response)

    if not corrected:
        print('⚠️  LLM returned empty response — returning raw recommendations')
        return recommendations, ctx

    # enrich each crop with display fields
    enriched = []
    for i, crop in enumerate(corrected):
        crop['rank'] = i + 1
        crop         = enrich_crop(crop, lang)
        enriched.append(crop)

    print(f'✅ {len(enriched)} verified crops ready for dashboard')
    return enriched, ctx

# ── comparison entry point (kept for internal use) ────────
def run_comparison(lang='en'):
    """
    Returns both raw recommender output and LLM corrected
    output side by side — for internal analysis only,
    not shown to farmers.
    """
    raw_recommendations, ctx = build_recommendations()
    corrected, _             = run_llm_evaluation(lang)

    return {
        'raw':       raw_recommendations,
        'corrected': corrected,
        'ctx':       ctx,
    }