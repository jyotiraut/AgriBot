"""
Conversation eval harness.

Simulates full multi-turn dialogues against the *pure* dialogue policy
(rules.dialogue_policy.select_task) with no LLM / no DB. Each turn supplies the
intent and (for answers) the extracted value that the real system would produce,
and we assert the task the bot picks and that profile collection progresses and
completes correctly — including disease detours, tangents, and corrections.

This is the regression net for conversational behaviour: run it on every prompt
or policy change.
"""
from rules.dialogue_policy import select_task
from rules.conversation_rules import get_next_field, TYPE_A_FIELD_ORDER, TYPE_B_FIELD_ORDER


class DialogueSim:
    """A tiny turn-by-turn simulator over the pure policy + profile state."""

    def __init__(self, farmer_type: str):
        self.profile = {"farmer_type": farmer_type}
        self.last_task = None

    def turn(self, intent: str, value=None, field=None, confidence=1.0):
        """Play one farmer turn; return the task the bot chooses."""
        accepted = False
        if intent in ("answer", "correction") and value is not None and confidence >= 0.65:
            target = field or get_next_field(self.profile)
            # land_size is stored as hectares in the profile view
            key = "land_size_hectares" if target == "land_size" else target
            self.profile[key] = value
            accepted = True

        task = select_task(
            self.profile, intent=intent, accepted=accepted,
            confidence=confidence, last_task=self.last_task,
        )
        self.last_task = task
        return task

    @property
    def next_field(self):
        return get_next_field(self.profile)


def _answer_value(field):
    """A plausible accepted value for any field."""
    return 1.0 if field == "land_size" else "x"


class TestHappyPath:
    def test_type_b_collects_every_field_in_order(self):
        sim = DialogueSim("B")
        asked = []
        # Answer each field the policy points at, until the profile is complete.
        for _ in range(len(TYPE_B_FIELD_ORDER) + 2):
            field = sim.next_field
            if field is None:
                break
            asked.append(field)
            task = sim.turn("answer", value=_answer_value(field))
            assert task in ("ack_ask", "resume_ask", "advise")
        assert sim.next_field is None                 # profile complete
        assert asked == TYPE_B_FIELD_ORDER            # asked in the defined order

    def test_completion_switches_to_advise(self):
        sim = DialogueSim("A")
        while sim.next_field is not None:
            sim.turn("answer", value=_answer_value(sim.next_field))
        assert sim.turn("question") == "advise"


class TestDiseaseDetour:
    def test_disease_pauses_then_resumes(self):
        sim = DialogueSim("A")
        sim.turn("answer", value="potato")            # crop
        field_before = sim.next_field

        assert sim.turn("disease") == "disease_answer"  # detour: answer the problem
        assert sim.next_field == field_before           # collection did NOT advance

        # Next turn the farmer answers again → bridge back, then normal.
        assert sim.turn("answer", value="2024-01-01") == "resume_ask"
        assert sim.next_field != field_before           # now it advanced

    def test_repeated_disease_questions_never_advance(self):
        sim = DialogueSim("B")
        sim.turn("answer", value="tomato")
        pending = sim.next_field
        for _ in range(3):
            assert sim.turn("disease") == "disease_answer"
            assert sim.next_field == pending


class TestTangents:
    def test_general_question_is_answered_without_advancing(self):
        sim = DialogueSim("B")
        sim.turn("answer", value="maize")
        pending = sim.next_field
        assert sim.turn("question") == "answer_ask"
        assert sim.next_field == pending

    def test_smalltalk_and_offtopic_redirect(self):
        sim = DialogueSim("A")
        assert sim.turn("smalltalk") == "redirect"
        assert sim.turn("offtopic") == "redirect"

    def test_low_confidence_answer_asks_to_clarify(self):
        sim = DialogueSim("A")
        assert sim.turn("answer", value="???", confidence=0.4) == "clarify"


class TestCorrections:
    def test_correction_updates_named_field(self):
        sim = DialogueSim("A")
        sim.turn("answer", value="potato")            # crop = potato
        assert sim.profile["crop"] == "potato"
        # Later the farmer corrects the crop out of order.
        sim.turn("correction", value="maize", field="crop")
        assert sim.profile["crop"] == "maize"


class TestNeverStuck:
    def test_always_returns_a_valid_task(self):
        sim = DialogueSim("A")
        valid = {"ack_ask", "resume_ask", "redirect", "clarify",
                 "answer_ask", "disease_answer", "advise"}
        for intent in ("answer", "question", "disease", "smalltalk", "offtopic"):
            assert sim.turn(intent, value="x") in valid
