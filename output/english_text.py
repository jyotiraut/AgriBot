# ─────────────────────────────────────────────
# English language mappings for all output
# ─────────────────────────────────────────────

SEASON_NAMES = {
    'Garmi':  'Summer Season (Baisakh–Ashadh)',
    'Barkhe': 'Monsoon Season (Shrawan–Ashwin)',
    'Hiude':  'Winter Season (Mangsir–Chaitra)',
}

MONTH_NAMES = {
    'Baisakh':  'Baisakh',
    'Jestha':   'Jestha',
    'Ashadh':   'Ashadh',
    'Shrawan':  'Shrawan',
    'Bhadra':   'Bhadra',
    'Ashwin':   'Ashwin',
    'Kartik':   'Kartik',
    'Mangsir':  'Mangsir',
    'Poush':    'Poush',
    'Magh':     'Magh',
    'Falgun':   'Falgun',
    'Chaitra':  'Chaitra',
}

PLANTING_STATUS = {
    'plant_now':     '✅ Plant Now',
    'coming_soon':   '⏳ Plant Soon',
    'out_of_season': '❌ Out of Season',
}

RISK_TIER = {
    'High':   '🔴 High Risk',
    'Medium': '🟡 Medium Risk',
    'Low':    '🟢 Low Risk',
}

DOMINANT_RISK_REASON = {
    'flood':      'High flood and waterlogging risk this season',
    'drought':    'Risk of drought and water shortage this season',
    'frost':      'Frost and cold damage risk this season',
    'disease':    'High disease and pest pressure this season',
    'storage':    'This crop is difficult to store — sell quickly after harvest',
    'volatility': 'Market price for this crop can swing suddenly',
}

HARVEST_CONFIDENCE = {
    'High': 'This crop typically harvests in this window in your region',
    'Low':  'Harvest timing is estimated — check local conditions',
}

WATER_REQUIREMENT = {
    'Medium':     'Moderate irrigation needed',
    'Low':        'Low irrigation needed',
    'Low-Medium': 'Low to moderate irrigation needed',
    'High':       'High irrigation needed',
}

SELLING_ADVICE = {
    'High': (
        'Market price is unstable — sell as soon as possible '
        'after harvest at the nearest market or cooperative. '
        'Consider group selling if prices are low.'
    ),
    'Medium': (
        'Price can fluctuate slightly — wait 1–2 weeks after '
        'harvest to monitor prices before selling. '
        'Storage can help you get a better price.'
    ),
    'Low': (
        'Price is relatively stable — sell at local market '
        'or cooperative. Selling after peak season with good '
        'storage can fetch a higher price.'
    ),
}

STORAGE_ADVICE_TEMPLATE = (
    'Shelf life: {shelf_life} — '
    'Store in a cool, dry and well-ventilated place.'
)

OPPORTUNITY_LABEL = {
    (8, 10): '⭐⭐⭐ Excellent Opportunity',
    (6, 8):  '⭐⭐ Good Opportunity',
    (4, 6):  '⭐ Fair Opportunity',
    (0, 4):  '⚠️  Plant with Caution',
}

UI = {
    'page_title':        'Nepali Farmer Crop Advisor',
    'app_title':         'Nepali Farmer Crop Advisory System',
    'today_label':       'Today',
    'month_label':       'Month',
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
    'no_results':        'No crops found for this filter. Try changing the filter.',
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
        'Contact your nearest Agriculture Service Center for more information.',
        'Kalimati vegetable market price information:',
    ],
    'rank_label': 'Rank',
}

def get_opportunity_label(score):
    for (low, high), label in OPPORTUNITY_LABEL.items():
        if low <= score <= high:
            return label
    return '⚠️  Plant with Caution'

def translate_months(month_list):
    return [MONTH_NAMES.get(m, m) for m in month_list]

def get_storage_advice(shelf_life):
    return STORAGE_ADVICE_TEMPLATE.format(shelf_life=shelf_life)

def get_selling_advice(risk_tier):
    return SELLING_ADVICE.get(risk_tier, SELLING_ADVICE['Medium'])