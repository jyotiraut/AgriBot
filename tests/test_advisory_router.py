"""Tests for the chat advisory intent-router: intent detection, routing,
engine fact helpers, and the DATA render channel."""
import rules.weather_integration as wx

from rules.field_extractor import detect_advisory_intent, VALID_INTENTS
from rules.dialogue_policy import select_task, DETOUR_TASKS, ADVISORY_INTENT_TASKS
from engine.crop_advisor import (
    harvest_facts,
    format_harvest_facts,
    format_planting_facts,
    recommend_crops,
)
from engine.price_snapshot import price_snapshot, format_price_facts
from engine.market_calendar import crops_in_harvest_this_month, format_market_calendar_facts
from rag.prompts import TASKS, KRISHIMITRA_SYSTEM, build_user_message


# ── intent detection ──────────────────────────────────────────────────────────

def test_new_intents_registered():
    for i in ("planting", "price", "weather", "harvest", "market_trend"):
        assert i in VALID_INTENTS


def test_keyword_detection_nepali_and_romanized():
    assert detect_advisory_intent("aile ke lagaune hola") == "planting"
    assert detect_advisory_intent("के लगाउने होला यो महिना") == "planting"
    assert detect_advisory_intent("alu ko bhau kati cha") == "price"
    assert detect_advisory_intent("आलुको भाउ कति छ") == "price"
    assert detect_advisory_intent("bholi pani parcha ki") == "weather"
    assert detect_advisory_intent("मौसम कस्तो छ") == "weather"
    assert detect_advisory_intent("tomato kahile tipne") == "harvest"
    assert detect_advisory_intent("कहिले काट्ने धान") == "harvest"
    assert detect_advisory_intent("yo mahina k bechne") == "market_trend"
    assert detect_advisory_intent("यो महिना कुन बाली बेच्ने") == "market_trend"
    assert detect_advisory_intent("best crop to sell this month") == "market_trend"
    # natural variation not in the fixed phrase list — caught by the
    # (month-cue AND action-cue) combinator
    assert detect_advisory_intent("yo mahina k bechda ramro huncha?") == "market_trend"


def test_keyword_detection_negative():
    assert detect_advisory_intent("mero naam ram ho") is None
    assert detect_advisory_intent("2 ropani jagga cha") is None
    assert detect_advisory_intent("") is None
    assert detect_advisory_intent(None) is None


def test_harvest_beats_planting_when_both_present():
    # "kahile tipne" (harvest) + "lagaune" (planting) → harvest is more specific
    assert detect_advisory_intent("ke lagaune ra kahile tipne") == "harvest"


# ── routing ───────────────────────────────────────────────────────────────────

def test_advisory_intents_route_to_engine_tasks():
    for intent, task in ADVISORY_INTENT_TASKS.items():
        # incomplete profile must NOT block an advisory answer
        assert select_task({}, intent=intent, accepted=False) == task
        assert select_task({"crop": "potato"}, intent=intent, accepted=False) == task


def test_disease_still_wins_over_advisory():
    assert select_task({}, intent="disease", accepted=False) == "disease_answer"


def test_advisory_tasks_are_detours_that_bridge_back():
    for task in ADVISORY_INTENT_TASKS.values():
        assert task in DETOUR_TASKS
    # next turn: a value gets accepted → warm resume, not cold ack
    assert select_task(
        {"crop": "potato"}, intent="answer", accepted=True, last_task="plant_advice"
    ) == "resume_ask"


# ── harvest facts ─────────────────────────────────────────────────────────────

def test_harvest_facts_known_crop():
    facts = harvest_facts("potato")
    assert facts["crop"] == "potato"
    assert facts["growth_weeks_min"] and facts["growth_weeks_max"]
    assert facts["harvest_months"]


def test_harvest_facts_projects_from_sowing_month():
    facts = harvest_facts("potato", sowing_month=6)
    assert 1 <= facts["expected_harvest_month"] <= 12
    assert facts["expected_harvest_month_name"]


def test_harvest_facts_unknown_crop_and_sentinel():
    assert harvest_facts("zzz_not_a_crop") == {}
    assert format_harvest_facts({}) .startswith("NO_DATA")


# ── price facts ───────────────────────────────────────────────────────────────

def test_price_snapshot_known_crop():
    facts = price_snapshot("potato", month=4)
    assert facts["price_avg"] > 0
    assert facts["price_low"] <= facts["price_avg"] <= facts["price_high"]
    assert facts["peak_month_name"]
    assert "trend_pct" in facts


def test_price_snapshot_unknown_crop_and_sentinel():
    assert price_snapshot("zzz_not_a_crop") == {}
    assert format_price_facts({}).startswith("NO_DATA")


def test_price_format_mentions_kalimati():
    out = format_price_facts(price_snapshot("tomato", month=1))
    assert "Kalimati" in out


def test_price_snapshot_fuzzy_typo_still_resolves():
    # "poteto" isn't in CROP_NORMALIZE's alias table nor an exact forecast key —
    # fuzzy_match_crop should still land it on "potato".
    facts = price_snapshot("poteto", month=4)
    assert facts.get("crop") == "potato"


# ── market calendar (month -> crops to harvest & sell) ────────────────────────

def test_market_calendar_returns_ranked_crops():
    rows = crops_in_harvest_this_month(month=9, top_n=5)  # Poush — potato harvest
    assert rows
    for r in rows:
        assert r["price_avg"] > 0
        assert r["price_low"] <= r["price_avg"] <= r["price_high"]
    # ranked by demand_score descending (seasonal opportunity, not raw price —
    # a raw-price ranking would let rare high-value crops dominate every month)
    scores = [r["demand_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)


def test_market_calendar_format_and_sentinel():
    rows = crops_in_harvest_this_month(month=9, top_n=3)
    out = format_market_calendar_facts(rows)
    assert "avg" in out
    assert format_market_calendar_facts([]).startswith("NO_DATA")


# ── planting facts ────────────────────────────────────────────────────────────

def test_planting_facts_include_weather_note():
    recs = recommend_crops("kavre", month=4, top_n=3)
    out = format_planting_facts(recs, "kavre", weather_note="heavy rain expected")
    assert "kavre" in out
    assert "heavy rain expected" in out


def test_planting_facts_empty_is_no_data():
    assert format_planting_facts([], "kavre").startswith("NO_DATA")


# ── weather summary (network mocked) ─────────────────────────────────────────

def _fake_forecast(zone):
    return {
        "forecast_available": True,
        "heavy_rain_upcoming": True,
        "raw_daily": {
            "temperature_2m_max": [30, 36, 33, 31, 29, 28, 27],
            "temperature_2m_min": [1.5, 4, 5, 6, 5, 4, 3],
            "precipitation_sum":  [12.0, 8.0, 0.5, 0, 0, 0, 0],
        },
    }


def test_summarize_forecast_flags(monkeypatch):
    monkeypatch.setattr(wx, "fetch_7_day_forecast", _fake_forecast)
    wx._wx_cache.clear()
    s = wx.summarize_forecast("Hills")
    assert s["available"] and s["heavy_rain_upcoming"]
    assert s["frost_risk"] is True          # min 1.5 < 2
    assert s["heat_stress"] is True         # max 36 > 35
    assert s["rain_3day_mm"] == 20.5
    out = wx.format_weather_facts(s, "Hills")
    assert "frost" in out and "heavy rain" in out


def test_weather_unavailable_is_no_data(monkeypatch):
    monkeypatch.setattr(
        wx, "fetch_7_day_forecast",
        lambda z: {"forecast_available": False, "heavy_rain_upcoming": False},
    )
    wx._wx_cache.clear()
    s = wx.summarize_forecast("Hills")
    assert s == {"available": False}
    assert wx.format_weather_facts(s, "Hills").startswith("NO_DATA")


def test_weather_cache_serves_second_call(monkeypatch):
    calls = {"n": 0}

    def counting_fetch(zone):
        calls["n"] += 1
        return _fake_forecast(zone)

    monkeypatch.setattr(wx, "fetch_7_day_forecast", counting_fetch)
    wx._wx_cache.clear()
    wx.fetch_7_day_forecast_cached("Terai")
    wx.fetch_7_day_forecast_cached("Terai")
    assert calls["n"] == 1


# ── render channel ────────────────────────────────────────────────────────────

def test_all_advisory_tasks_have_instructions():
    # a missing TASKS key would KeyError inside build_user_message
    for task in ADVISORY_INTENT_TASKS.values():
        assert task in TASKS


def test_build_user_message_includes_data_block():
    msg = build_user_message(
        "plant_advice", "", "KNOWN: crop=potato", "ke lagaune?",
        data_facts="District: kavre\n1. Potato",
    )
    assert "DATA:\nDistrict: kavre" in msg


def test_build_user_message_backward_compatible():
    # old call shape (no data_facts) must still work and omit the DATA block
    msg = build_user_message("ack_ask", "q?", "KNOWN:", "hi", "", crop_tip="tip")
    assert "DATA:" not in msg


def test_system_prompt_has_grounding_rule():
    assert "DATA" in KRISHIMITRA_SYSTEM
    assert "ASK_DISTRICT" in KRISHIMITRA_SYSTEM
