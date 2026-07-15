"""Unit tests for engine.planting_filter — month filtering + altitude/zone fit."""
from engine.planting_filter import (
    get_filtered_crops,
    get_crops_for_location,
    parse_altitude_range,
    is_altitude_suitable,
)


# ── parse_altitude_range ──────────────────────────────────────────────────────

def test_parse_altitude_en_dash():
    assert parse_altitude_range("60–1500") == (60, 1500)


def test_parse_altitude_hyphen_and_masl():
    assert parse_altitude_range("500-3500 masl") == (500, 3500)


def test_parse_altitude_single_number_is_open_low():
    assert parse_altitude_range("2000") == (0, 2000)


def test_parse_altitude_unknown_is_none():
    assert parse_altitude_range("N/A") is None
    assert parse_altitude_range("") is None


# ── is_altitude_suitable (overlap of crop range vs. zone band) ────────────────

def test_high_altitude_crop_excluded_from_terai():
    assert is_altitude_suitable("2500–4000", "Terai") is False


def test_high_altitude_crop_fits_mountains():
    assert is_altitude_suitable("2500–4000", "Mountains") is True


def test_broad_range_crop_fits_terai():
    assert is_altitude_suitable("60–1500", "Terai") is True


def test_zone_is_case_insensitive():
    assert is_altitude_suitable("60–1500", "TERAI") is True


def test_unknown_zone_returns_none():
    assert is_altitude_suitable("60–1500", "Xanadu") is None


def test_unknown_crop_altitude_returns_none():
    assert is_altitude_suitable("N/A", "Terai") is None


# ── month argument actually filters ───────────────────────────────────────────

def test_month_argument_changes_results():
    baisakh = {c["crop_key"] for c in get_filtered_crops(month=1)
               if c["planting_status"] == "plant_now"}
    mangsir = {c["crop_key"] for c in get_filtered_crops(month=8)
               if c["planting_status"] == "plant_now"}
    assert baisakh != mangsir
    assert baisakh, "expected some crops plantable in Baisakh"


# ── zone narrows the recommendation ───────────────────────────────────────────

def test_zone_narrows_and_never_widens():
    all_in_season = {c["crop_key"] for c in get_filtered_crops(month=1)
                     if c["planting_status"] == "plant_now"}
    mountains = {c["crop_key"] for c in get_crops_for_location("Mountains", month=1)}
    # zone-filtered set is always a subset of the unfiltered in-season set
    assert mountains <= all_in_season
    # and mountains excludes at least one low-altitude-only crop
    assert len(mountains) < len(all_in_season)


def test_location_keeps_altitude_unknown_crops():
    # crops with unparseable altitude (flag None) must never be dropped
    crops = get_crops_for_location("Terai", month=1)
    assert all(c["altitude_suitable"] is not False for c in crops)


def test_no_zone_leaves_flag_none():
    crops = get_filtered_crops(month=1)
    assert all(c["altitude_suitable"] is None for c in crops)
