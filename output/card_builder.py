# from engine.ranker import get_ranked_crops

# def get_lang_module(lang='ne'):
#     if lang == 'en':
#         from output import english_text as L
#     else:
#         from output import nepali_text as L
#     return L

# def build_cards(lang='ne'):
#     L      = get_lang_module(lang)
#     crops  = get_ranked_crops()
#     cards  = []

#     for crop in crops:
#         season_np       = L.SEASON_NAMES.get(crop['season'], crop['season'])
#         status_np       = L.PLANTING_STATUS.get(crop['planting_status'])
#         risk_np         = L.RISK_TIER.get(crop['risk_tier'])
#         risk_reason_np  = L.DOMINANT_RISK_REASON.get(crop['dominant_risk'])
#         harvest_conf_np = L.HARVEST_CONFIDENCE.get(crop['harvest_confidence'])
#         water_np        = L.WATER_REQUIREMENT.get(
#                               crop['water_requirement'],
#                               crop['water_requirement']
#                           )
#         opportunity_np  = L.get_opportunity_label(crop['opportunity_score'])
#         harvest_np      = L.translate_months(crop['projected_harvest'])
#         selling_np      = L.get_selling_advice(crop['risk_tier'])
#         storage_np      = L.get_storage_advice(crop['storage_shelf_life'])

#         if crop['price_details']:
#             pd = crop['price_details']
#             price_info = (
#                 f"Min: Rs.{pd['min_price']}/kg | "
#                 f"Max: Rs.{pd['max_price']}/kg | "
#                 f"Avg: Rs.{pd['average_price']}/kg"
#             ) if lang == 'en' else (
#                 f"न्यूनतम: रु.{pd['min_price']}/के.जी. | "
#                 f"अधिकतम: रु.{pd['max_price']}/के.जी. | "
#                 f"औसत: रु.{pd['average_price']}/के.जी."
#             )
#         else:
#             price_info = 'Price data not available' if lang == 'en' else 'मूल्य तथ्याङ्क उपलब्ध छैन'

#         card = {
#             'rank':              crop['rank'],
#             'crop_key':          crop['crop_key'],
#             'crop_name':         crop['crop_name'],
#             'opportunity_label': opportunity_np,
#             'opportunity_score': crop['opportunity_score'],
#             'planting_status':   status_np,
#             'season':            season_np,
#             'risk_level':        risk_np,
#             'risk_reason':       risk_reason_np,
#             'harvest_note':      harvest_conf_np,
#             'harvest_months':    harvest_np,
#             'price_info':        price_info,
#             'selling_advice':    selling_np,
#             'storage_advice':    storage_np,
#             'water_requirement': water_np,
#             'scoring_notes':     crop['scoring_notes'],
#         }
#         cards.append(card)

#     return cards

# def print_cards(lang='ne'):
#     cards = build_cards(lang=lang)
#     L     = get_lang_module(lang)

#     for card in cards:
#         print('=' * 60)
#         print(f"#{card['rank']}  {card['crop_name']}")
#         print(f"    {card['opportunity_label']}  |  {L.UI['score_label']}: {card['opportunity_score']}/10")
#         print()
#         print(f"🌱 {L.UI['planting_status']:<20} : {card['planting_status']}")
#         print(f"📅 {L.UI['season']:<20} : {card['season']}")
#         print()
#         print(f"⚠️  {L.UI['risk_level']:<20} : {card['risk_level']}")
#         print(f"   {L.UI['risk_reason']:<20} : {card['risk_reason']}")
#         print()
#         print(f"🌾 {L.UI['harvest']:<20} : {', '.join(card['harvest_months'])}")
#         print(f"💧 {L.UI['water']:<20} : {card['water_requirement']}")
#         print()
#         print(f"💰 {L.UI['price']:<20} : {card['price_info']}")
#         print(f"📦 {L.UI['storage']:<20} : {card['storage_advice']}")
#         print()
#         print(f"🛒 {L.UI['selling']} :")
#         print(f"   {card['selling_advice']}")
#         print('=' * 60)
#         print()

from engine.ranker import get_ranked_crops

def get_lang_module(lang='ne'):
    if lang == 'en':
        from output import english_text as L
    else:
        from output import nepali_text as L
    return L

def build_cards(lang='ne', month=None):      # ← month added
    L     = get_lang_module(lang)
    crops = get_ranked_crops()
    # crops = get_ranked_crops(month=month)    # ← passed down
    cards = []

    for crop in crops:
        season_np       = L.SEASON_NAMES.get(crop['season'], crop['season'])
        status_np       = L.PLANTING_STATUS.get(crop['planting_status'])
        risk_np         = L.RISK_TIER.get(crop['risk_tier'])
        risk_reason_np  = L.DOMINANT_RISK_REASON.get(crop['dominant_risk'])
        harvest_conf_np = L.HARVEST_CONFIDENCE.get(crop['harvest_confidence'])
        water_np        = L.WATER_REQUIREMENT.get(
                              crop['water_requirement'],
                              crop['water_requirement']
                          )
        opportunity_np  = L.get_opportunity_label(crop['opportunity_score'])
        harvest_np      = L.translate_months(crop['projected_harvest'])
        selling_np      = L.get_selling_advice(crop['risk_tier'])
        storage_np      = L.get_storage_advice(crop['storage_shelf_life'])

        if crop['price_details']:
            pd = crop['price_details']
            price_info = (
                f"Min: Rs.{pd['min_price']}/kg | "
                f"Max: Rs.{pd['max_price']}/kg | "
                f"Avg: Rs.{pd['average_price']}/kg"
            ) if lang == 'en' else (
                f"न्यूनतम: रु.{pd['min_price']}/के.जी. | "
                f"अधिकतम: रु.{pd['max_price']}/के.जी. | "
                f"औसत: रु.{pd['average_price']}/के.जी."
            )
        else:
            price_info = (
                'Price data not available' if lang == 'en'
                else 'मूल्य तथ्याङ्क उपलब्ध छैन'
            )

        card = {
            'rank':              crop['rank'],
            'crop_key':          crop['crop_key'],
            'crop_name':         crop['crop_name'],
            'opportunity_label': opportunity_np,
            'opportunity_score': crop['opportunity_score'],
            'planting_status':   status_np,
            'season':            season_np,
            'risk_level':        risk_np,
            'risk_reason':       risk_reason_np,
            'harvest_note':      harvest_conf_np,
            'harvest_months':    harvest_np,
            'price_info':        price_info,
            'selling_advice':    selling_np,
            'storage_advice':    storage_np,
            'water_requirement': water_np,
            'scoring_notes':     crop['scoring_notes'],
        }
        cards.append(card)

    return cards

def print_cards(lang='ne', month=None):      # ← month added
    # cards = build_cards(lang=lang, month=month)
    cards = build_cards(lang=lang)
    L     = get_lang_module(lang)

    for card in cards:
        print('=' * 60)
        print(f"#{card['rank']}  {card['crop_name']}")
        print(f"    {card['opportunity_label']}  |  {L.UI['score_label']}: {card['opportunity_score']}/10")
        print()
        print(f"🌱 {L.UI['planting_status']:<20} : {card['planting_status']}")
        print(f"📅 {L.UI['season']:<20} : {card['season']}")
        print()
        print(f"⚠️  {L.UI['risk_level']:<20} : {card['risk_level']}")
        print(f"   {L.UI['risk_reason']:<20} : {card['risk_reason']}")
        print()
        print(f"🌾 {L.UI['harvest']:<20} : {', '.join(card['harvest_months'])}")
        print(f"💧 {L.UI['water']:<20} : {card['water_requirement']}")
        print()
        print(f"💰 {L.UI['price']:<20} : {card['price_info']}")
        print(f"📦 {L.UI['storage']:<20} : {card['storage_advice']}")
        print()
        print(f"🛒 {L.UI['selling']} :")
        print(f"   {card['selling_advice']}")
        print('=' * 60)
        print()