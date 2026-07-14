from rules.conversation_rules import (
    classify_farmer_type,
    get_next_field,
    get_next_question,
    get_conversation_mode,
    FIELD_QUESTIONS,
    TYPE_A_FIELD_ORDER,
)


class TestClassifyFarmerType:
    def test_active_farmer(self):
        assert classify_farmer_type("mero khet ma bali chha") == "A"

    def test_planning_farmer(self):
        assert classify_farmer_type("ropne yojana banaudai chhu") == "B"
        assert classify_farmer_type("lagaune socheko") == "B"

    def test_ambiguous_returns_none(self):
        assert classify_farmer_type("namaste") is None

    def test_planted_spelling_variants(self):
        # Regression: farmers type "lagako"/"lageko", not just "lagaeko".
        assert classify_farmer_type("maile tomato lagako chhu") == "A"
        assert classify_farmer_type("alu lagako cha") == "A"
        assert classify_farmer_type("tomato lageko chhu") == "A"


class TestNextField:
    def test_no_type_asks_type_first(self):
        assert get_next_field({}) == "farmer_type"

    def test_type_a_starts_with_crop(self):
        assert get_next_field({"farmer_type": "A"}) == "crop"

    def test_skips_filled_fields(self):
        profile = {"farmer_type": "A", "crop": "potato", "sowing_date": "2024-01-01"}
        assert get_next_field(profile) == "district"

    def test_complete_profile_returns_none(self):
        profile = {"farmer_type": "A"}
        for f in TYPE_A_FIELD_ORDER:
            profile[f] = "x"
        profile["land_size_hectares"] = 1.0  # land_size resolves via hectares
        assert get_next_field(profile) is None


class TestNextQuestion:
    def test_uses_type_a_phrasing(self):
        q = get_next_question({"farmer_type": "A"})
        assert q == FIELD_QUESTIONS["crop"]["A"]

    def test_uses_type_b_phrasing(self):
        q = get_next_question({"farmer_type": "B"})
        assert q == FIELD_QUESTIONS["crop"]["B"]


class TestConversationMode:
    def test_first_message(self):
        assert get_conversation_mode({}, is_first_message=True) == "first_message"

    def test_classify_when_no_type(self):
        assert get_conversation_mode({}) == "classify"

    def test_collect_when_gathering(self):
        assert get_conversation_mode({"farmer_type": "A", "crop": "potato"}) == "collect"

    def test_farmer_question_mid_collection(self):
        mode = get_conversation_mode(
            {"farmer_type": "A", "crop": "potato"}, farmer_asked_question=True
        )
        assert mode == "farmer_question"
