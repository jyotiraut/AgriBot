"""
Dialogue policy — the deterministic brain of the conversation.

Given the current profile, the classified intent of the farmer's message, and
whether we accepted a field value this turn, decide which LLM *task* to run.
This is pure Python (no DB, no LLM), so the whole conversation flow — including
disease detours and the return to profile collection — is unit-testable.

The LLM only renders the reply; it never decides the task.
"""
from typing import Optional

from rules.conversation_rules import get_next_field

# Confidence at/above which an extracted field value is trusted.
ACCEPT_CONFIDENCE = 0.65

# Tasks that represent a "detour" away from profile collection. When the NEXT
# turn returns to collection, we bridge back warmly (resume_ask) instead of a
# cold ack_ask.
DETOUR_TASKS = {"disease_answer", "answer_ask", "redirect"}


def select_task(
    profile: dict,
    intent: str,
    accepted: bool,
    confidence: float = 0.0,
    last_task: Optional[str] = None,
) -> str:
    """
    Decide the LLM task for this turn.

    Args:
        profile:    the farmer profile AFTER any accepted value has been saved.
        intent:     one of answer|question|disease|smalltalk|offtopic|correction.
        accepted:   True if a field value was saved this turn.
        confidence: extraction confidence for an "answer" intent.
        last_task:  the task used on the previous turn (for detour → resume).

    Returns one of:
        first, ack_ask, resume_ask, redirect, clarify, answer_ask,
        disease_answer, advise.
    """
    # Crop problems always take priority — help first, collect later.
    if intent == "disease":
        return "disease_answer"

    next_field = get_next_field(profile)
    is_complete = next_field is None

    # Profile fully collected → free-form advisory Q&A.
    if is_complete:
        return "advise"

    if intent == "question":
        return "answer_ask"

    if intent in ("smalltalk", "offtopic"):
        return "redirect"

    # An answer we could not accept: nudge for clarity if they tried, else redirect.
    if intent == "answer" and not accepted:
        return "clarify" if confidence and confidence > 0 else "redirect"

    # A value was accepted (answer) or a correction applied → acknowledge + ask next.
    # If we're coming back from a detour, bridge warmly instead of a cold ack.
    if last_task in DETOUR_TASKS:
        return "resume_ask"
    return "ack_ask"
