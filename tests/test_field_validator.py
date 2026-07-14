from rules.field_validator import clean_and_type, merge_profiles, MAX_EXPERIENCE_YEARS


class TestCleanAndType:
    def test_normalizes_crop(self):
        assert clean_and_type({"crop": "aloo"})["crop"] == "potato"

    def test_drops_out_of_range_month(self):
        assert "farming_month" not in clean_and_type({"farming_month": 13})
        assert clean_and_type({"farming_month": 3})["farming_month"] == 3

    def test_caps_experience(self):
        assert clean_and_type({"experience_years": 40})["experience_years"] == MAX_EXPERIENCE_YEARS

    def test_drops_none_and_empty(self):
        out = clean_and_type({"crop": None, "district": "  "})
        assert out == {}

    def test_syncs_location_and_district(self):
        out = clean_and_type({"district": "Kavre"})
        assert out["district"] == "kavre"
        assert out["location"] == "kavre"


class TestMergeProfiles:
    def test_always_overwrite_fields_replaced(self):
        merged = merge_profiles({"crop": "potato"}, {"crop": "tomato"})
        assert merged["crop"] == "tomato"

    def test_keeps_existing_for_non_overwrite_field(self):
        # A field NOT in ALWAYS_OVERWRITE keeps its existing value.
        merged = merge_profiles({"custom_note": "old"}, {"custom_note": "new"})
        assert merged["custom_note"] == "old"

    def test_overwrite_field_is_replaced(self):
        # experience_years IS in ALWAYS_OVERWRITE, so the new value wins.
        merged = merge_profiles({"experience_years": 5}, {"experience_years": 9})
        assert merged["experience_years"] == 9

    def test_fills_when_existing_none(self):
        merged = merge_profiles({"district": None}, {"district": "kavre"})
        assert merged["district"] == "kavre"

    def test_ignores_new_nulls(self):
        merged = merge_profiles({"crop": "potato"}, {"crop": None})
        assert merged["crop"] == "potato"
