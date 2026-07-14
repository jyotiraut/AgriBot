# ─────────────────────────────────────────────
# Plain Nepali language mappings for all output
# ─────────────────────────────────────────────

SEASON_NAMES = {
    'Garmi':  'गर्मी मौसम (वैशाख–असार)',
    'Barkhe': 'बर्खे मौसम (साउन–असोज)',
    'Hiude':  'हिउँदे मौसम (मंसिर–चैत)',
}

MONTH_NAMES = {
    'Baisakh':  'वैशाख',
    'Jestha':   'जेठ',
    'Ashadh':   'असार',
    'Shrawan':  'साउन',
    'Bhadra':   'भदौ',
    'Ashwin':   'असोज',
    'Kartik':   'कार्तिक',
    'Mangsir':  'मंसिर',
    'Poush':    'पुस',
    'Magh':     'माघ',
    'Falgun':   'फागुन',
    'Chaitra':  'चैत',
}

PLANTING_STATUS = {
    'plant_now':     '✅ अहिले रोप्नुस्',
    'coming_soon':   '⏳ छिट्टै रोप्न मिल्छ',
    'out_of_season': '❌ यो मौसममा नरोप्नुस्',
}

RISK_TIER = {
    'High':     '🔴 उच्च जोखिम',
    'Medium':   '🟡 मध्यम जोखिम',
    'Low':      '🟢 कम जोखिम',
}

DOMINANT_RISK_REASON = {
    'flood':      'यस मौसममा बाढी र पानीको खतरा बढी छ',
    'drought':    'यस मौसममा खडेरी र पानी अभावको खतरा छ',
    'frost':      'यस मौसममा हिमपात र चिसोले बाली नोक्सान गर्न सक्छ',
    'disease':    'यस मौसममा बिरामी र किरा फट्याङ्ग्राको खतरा बढी छ',
    'storage':    'यो बाली भण्डारण गर्न गाह्रो छ, चाँडै बेच्नुपर्छ',
    'volatility': 'यो बालीको बजार भाउ अचानक घटबढ हुन सक्छ',
}

HARVEST_CONFIDENCE = {
    'High': 'यो बाली तपाईंको क्षेत्रमा सामान्यतः यही समयमा उठ्छ',
    'Low':  'यो बालीको उठाइ समय अनुमानित हो, स्थानीय अवस्था हेर्नुस्',
}

WATER_REQUIREMENT = {
    'Medium':     'मध्यम सिँचाइ चाहिन्छ',
    'Low':        'कम सिँचाइ चाहिन्छ',
    'Low-Medium': 'कम देखि मध्यम सिँचाइ चाहिन्छ',
    'High':       'धेरै सिँचाइ चाहिन्छ',
}

SELLING_ADVICE = {
    'High': (
        'बजार भाउ अस्थिर छ — बाली उठेपछि सकेसम्म चाँडै '
        'नजिकको बजार वा कृषि सहकारीमा बेच्नुस्। '
        'भाउ राम्रो नभए सामूहिक बिक्री गर्नुस्।'
    ),
    'Medium': (
        'भाउ अलिकति घटबढ हुन सक्छ — बाली पाकेपछि '
        '१–२ हप्ता पर्खेर भाउ हेरी बेच्नुस्। '
        'भण्डारण सुविधा भए अलि ढिलो बेच्दा फाइदा हुन सक्छ।'
    ),
    'Low': (
        'भाउ तुलनात्मक रूपमा स्थिर छ — सहकारी वा '
        'स्थानीय बजारमा बेच्न सकिन्छ। '
        'राम्रो भण्डारण भए मौसम सकिएपछि बेच्दा बढी मूल्य पाइन्छ।'
    ),
}

STORAGE_ADVICE_TEMPLATE = (
    'भण्डारण अवधि: {shelf_life} — '
    'सुख्खा, छायाँदार र हावा चल्ने ठाउँमा राख्नुस्।'
)

OPPORTUNITY_LABEL = {
    (8, 10):  '⭐⭐⭐ उत्कृष्ट अवसर',
    (6, 8):   '⭐⭐ राम्रो अवसर',
    (4, 6):   '⭐ ठीकठाक अवसर',
    (0, 4):   '⚠️  सावधानीका साथ रोप्नुस्',
}

def get_opportunity_label(score):
    for (low, high), label in OPPORTUNITY_LABEL.items():
        if low <= score <= high:
            return label
    return '⚠️  सावधानीका साथ रोप्नुस्'

def translate_months(month_list):
    """Converts a list of English month names to Nepali."""
    return [MONTH_NAMES.get(m, m) for m in month_list]

def get_storage_advice(shelf_life):
    return STORAGE_ADVICE_TEMPLATE.format(shelf_life=shelf_life)

def get_selling_advice(risk_tier):
    return SELLING_ADVICE.get(risk_tier, SELLING_ADVICE['Medium'])

UI = {
    'page_title':        'नेपाली किसान बाली सल्लाह',
    'app_title':         'नेपाली किसान बाली सल्लाह प्रणाली',
    'today_label':       'आजको मिति',
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
    'no_results':        'यो फिल्टरमा कुनै बाली भेटिएन। फिल्टर परिवर्तन गर्नुस्।',
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
        'आफ्नो नजिकको कृषि सेवा केन्द्रमा थप जानकारीका लागि सम्पर्क गर्नुस्।',
        'कालीमाटी तरकारी बजार मूल्य सूचना:',
    ],
    'rank_label': 'क्रम',
}