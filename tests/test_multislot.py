from rules.field_extractor import build_multislot_prompt, MULTISLOT_FIELDS, MULTISLOT_SYSTEM
from rules.conversation_rules import get_next_field
from rules.dialogue_policy import select_task


class TestMultislotPrompt:
    def test_covers_all_profile_fields(self):
        for f in ("farmer_type", "crop", "district", "land_size", "has_loan"):
            assert f in MULTISLOT_FIELDS

    def test_prompt_mentions_fields_and_message(self):
        p = build_multislot_prompt("maile tomato lagako chhu")
        assert "farmer_type" in p
        assert "crop" in p
        assert "maile tomato lagako chhu" in p
        assert "intent" in p

    def test_prompt_notes_known_fields(self):
        p = build_multislot_prompt("2 ropani", {"farmer_type": "A", "crop": "potato"})
        assert "Already known" in p

    def test_system_prompt_is_nonempty(self):
        assert MULTISLOT_SYSTEM and "extract" in MULTISLOT_SYSTEM.lower()


class TestMultiFieldTurnAdvancesConversation:
    """The whole point: one message that states several facts fills them all,
    and the bot only asks for what's genuinely still missing."""

    def test_type_and_crop_in_one_turn(self):
        # Farmer said "maile tomato lagako chhu" → type A + crop tomato.
        profile = {"farmer_type": "A", "crop": "tomato"}
        # Next question should skip crop and go to sowing_date (Type A order).
        assert get_next_field(profile) == "sowing_date"
        # And the turn is a normal acknowledgment, not a re-ask/clarify.
        assert select_task(profile, "answer", accepted=True, confidence=1.0) == "ack_ask"

    def test_four_facts_in_one_turn(self):
        # "Kavre ma 2 ropani alu cha" → type + district + land + crop.
        profile = {
            "farmer_type": "A", "crop": "potato",
            "district": "kavre", "land_size_hectares": 0.1,
        }
        # Those four are done; next unfilled Type A field is sowing_date.
        assert get_next_field(profile) == "sowing_date"
        assert select_task(profile, "answer", accepted=True, confidence=1.0) == "ack_ask"
