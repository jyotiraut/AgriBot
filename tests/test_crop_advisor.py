"""Unit tests for engine.crop_advisor — the combined district crop recommender."""
from engine.crop_advisor import (
    recommend_crops,
    _risk_lookup,
    _curated_lookup,
    _norm,
    _rank_key,
)
from schemas.farmer import Zone, Season


EXPECTED_KEYS = {
    "crop_key", "crop_name", "planting_status", "harvest_months",
    "growth_weeks_min", "growth_weeks_max", "water_requirement",
    "storage_shelf_life", "altitude_suitable", "risk_tier", "risk_score",
    "price_volatility", "market_value", "varieties",
}


# ── shape ─────────────────────────────────────────────────────────────────────

def test_returns_list_of_fact_dicts():
    res = recommend_crops("chitwan", month=6, top_n=5)
    assert isinstance(res, list)
    assert res, "expected some recommendations for Chitwan"
    for c in res:
        assert EXPECTED_KEYS <= set(c.keys())


def test_top_n_is_respected():
    assert len(recommend_crops("kavre", month=6, top_n=3)) <= 3


# ── join normalisation (the fragile part) ─────────────────────────────────────

def test_norm_unifies_underscore_and_space():
    assert _norm("finger_millet") == _norm("Finger Millet")


def test_curated_lookup_joins_multiword_crop():
    # Finger Millet lives in the Hills/Kharif/Rainfed curated cell.
    curated = _curated_lookup(Zone.HILLS, Season.KHARIF, "rainfed")
    assert "finger millet" in curated
    assert curated["finger millet"].market_value  # has a market tier


def test_curated_lookup_empty_when_inputs_unknown():
    assert _curated_lookup(None, Season.KHARIF, "rainfed") == {}
    assert _curated_lookup(Zone.HILLS, None, "rainfed") == {}


# ── risk enrichment ───────────────────────────────────────────────────────────

def test_risk_sheet_has_core_crops():
    risks = _risk_lookup()
    assert "tomato" in risks and "potato" in risks
    assert risks["tomato"]["risk_tier"]            # non-empty tier
    assert isinstance(risks["tomato"]["risk_score"], float)


# ── geography ─────────────────────────────────────────────────────────────────

def test_zone_changes_recommendation():
    terai = {c["crop_key"] for c in recommend_crops("chitwan", month=1, top_n=50)}
    mtn   = {c["crop_key"] for c in recommend_crops("jumla", month=1, top_n=50)}
    assert terai != mtn


def test_unknown_district_falls_back_not_empty():
    # classify_zone falls back to Hills, so we still get a recommendation.
    assert recommend_crops("nowhereland", month=6)


# ── ranking ───────────────────────────────────────────────────────────────────

def test_results_are_ranked():
    res = recommend_crops("chitwan", month=9, irrigation="canal", top_n=20)
    keys = [_rank_key(c) for c in res]
    assert keys == sorted(keys, reverse=True)


def test_month_none_uses_current_month():
    # Should not raise and should return a list (current BS month resolved).
    assert isinstance(recommend_crops("kavre"), list)
