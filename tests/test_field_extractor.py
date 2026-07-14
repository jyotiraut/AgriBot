from rules.field_extractor import try_regex_extract


class TestLandSize:
    def test_bigha(self):
        r = try_regex_extract("land_size", "2 bigha jamin chha")
        assert r["value"] == 2.0
        assert r["unit"] == "bigha"

    def test_ropani_devanagari(self):
        r = try_regex_extract("land_size", "५ रोपनी")
        assert r["value"] == 5.0
        assert r["unit"] == "ropani"


class TestExperience:
    def test_years(self):
        assert try_regex_extract("experience_years", "5 barsa")["value"] == 5


class TestOwnership:
    def test_owned(self):
        assert try_regex_extract("land_ownership", "aafno jagga")["value"] == "owned"

    def test_leased(self):
        assert try_regex_extract("land_ownership", "bhada ma liyeko")["value"] == "leased"


class TestIrrigation:
    def test_canal(self):
        assert try_regex_extract("irrigation_type", "canal bata paani")["value"] == "canal"

    def test_rainfed(self):
        assert try_regex_extract("irrigation_type", "barshat ko paani")["value"] == "rainfed"


class TestHasLoan:
    def test_positive(self):
        assert try_regex_extract("has_loan", "rin cha")["value"] is True

    def test_negative(self):
        # Regression: "loan chaina" (no loan) must not be read as a loan.
        assert try_regex_extract("has_loan", "loan chaina")["value"] is False
        assert try_regex_extract("has_loan", "rin chaina")["value"] is False


class TestNoMatch:
    def test_returns_none(self):
        assert try_regex_extract("land_size", "thaha chaina") is None
