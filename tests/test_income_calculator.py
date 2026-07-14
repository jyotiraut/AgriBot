from rules.income_calculator import calculate_income, can_estimate_income


class TestCalculateIncome:
    def test_basic(self):
        r = calculate_income(yield_t_per_ha=10, land_size_ha=2, avg_price_per_kg=50)
        assert r["estimated_yield_kg"] == 20000     # 10 t/ha * 2 ha * 1000
        assert r["estimated_income_npr"] == 1000000  # 20000 kg * 50
        assert r["income_price_per_kg"] == 50
        assert r["income_yield_t_per_ha"] == 10

    def test_fractional_land(self):
        r = calculate_income(yield_t_per_ha=15.7, land_size_ha=0.5, avg_price_per_kg=30)
        assert r["estimated_yield_kg"] == 7850.0
        assert r["estimated_income_npr"] == 235500.0


class TestCanEstimateIncome:
    def test_complete(self):
        profile = {
            "crop": "potato",
            "land_size_hectares": 1.0,
            "district": "kavre",
            "farming_month": 3,
        }
        ok, missing = can_estimate_income(profile)
        assert ok is True
        assert missing == []

    def test_location_stands_in_for_district(self):
        profile = {
            "crop": "potato",
            "land_size_hectares": 1.0,
            "location": "kavre",
            "farming_month": 3,
        }
        ok, _ = can_estimate_income(profile)
        assert ok is True

    def test_missing_fields_reported(self):
        ok, missing = can_estimate_income({"crop": "potato"})
        assert ok is False
        assert "land_size_hectares" in missing
        assert "farming_month" in missing
