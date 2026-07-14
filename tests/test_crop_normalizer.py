from rules.crop_normalizer import normalize_crop, is_valid_crop
from rules.conversation_rules import normalise_crop


class TestNormalizeCrop:
    def test_romanized_aliases(self):
        assert normalize_crop("alu") == "potato"
        assert normalize_crop("golbheda") == "tomato"
        assert normalize_crop("makkai") == "maize"
        assert normalize_crop("bhatmas") == "soybean"
        assert normalize_crop("dal") == "lentil"

    def test_case_and_whitespace_insensitive(self):
        assert normalize_crop("  Kera ") == "banana"

    def test_plurals(self):
        assert normalize_crop("tomatoes") == "tomato"

    def test_substring_fallback(self):
        assert normalize_crop("alu ko bali") == "potato"

    def test_unknown_returns_lowercased_input(self):
        assert normalize_crop("dragonfruit") == "dragonfruit"

    def test_empty(self):
        assert normalize_crop("") == ""


class TestIsValidCrop:
    def test_known(self):
        assert is_valid_crop("alu") is True
        assert is_valid_crop("soybean") is True

    def test_unknown(self):
        assert is_valid_crop("dragonfruit") is False


class TestNormaliseCropChatContract:
    """conversation_rules.normalise_crop returns None for unknown crops."""

    def test_known(self):
        assert normalise_crop("alu") == "potato"

    def test_unknown_is_none(self):
        assert normalise_crop("dragonfruit") is None

    def test_empty_is_none(self):
        assert normalise_crop("") is None
