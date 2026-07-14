# graph/workflow.py
from langgraph.graph import StateGraph, END

from graph.nodes import (
    extract_profile_node,
    normalise_profile_node,
    resolve_conversation_mode_node,
    route_farmer,
    classify_zone_node,
    calculate_das_gdd_node,
    check_crop_suitability_node,
    apply_safety_guardrails_node,
    build_rule_output_node,
    retrieve_rag_context_node,
    synthesize_llm_node,
    convert_date_node,
    calculate_income_node,
    convert_units_node,
)
from graph.state import KrishiMitraState


# ── Routing functions ────────────────────────────────────────────────────────

def _route_after_validation(state: KrishiMitraState) -> str:
    """After route_farmer: handle error OR branch by farmer type."""
    if state.get("error"):
        return "error"
    return "type_a" if state.get("farmer_type") == "A" else "type_b"


# ── Graph builder ────────────────────────────────────────────────────────────

def build_advisory_graph() -> StateGraph:
    graph = StateGraph(KrishiMitraState)

    # ── Register nodes ───────────────────────────────────────────────────────
    graph.add_node("extract_profile",          extract_profile_node)
    graph.add_node("normalise_profile",        normalise_profile_node)
    graph.add_node("convert_date",             convert_date_node)
    graph.add_node("convert_units",            convert_units_node)
    graph.add_node("classify_zone",            classify_zone_node)
    graph.add_node("calculate_income",         calculate_income_node)
    graph.add_node("route_farmer",             route_farmer)
    graph.add_node("resolve_conversation",     resolve_conversation_mode_node)  # ← ADDED
    graph.add_node("calculate_das_gdd",        calculate_das_gdd_node)
    graph.add_node("check_crop_suitability",   check_crop_suitability_node)
    graph.add_node("apply_safety_guardrails",  apply_safety_guardrails_node)
    graph.add_node("build_rule_output",        build_rule_output_node)
    graph.add_node("retrieve_rag_context",     retrieve_rag_context_node)
    graph.add_node("synthesize_llm",           synthesize_llm_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    graph.set_entry_point("extract_profile")

    # ── Chat path pipeline ────────────────────────────────────────────────────
    # step 1: extract raw fields from farmer message
    graph.add_edge("extract_profile",   "normalise_profile")

    # step 2: clean crop aliases, district names, etc.
    graph.add_edge("normalise_profile", "convert_date")

    # step 3: BS → AD date
    graph.add_edge("convert_date",      "convert_units")

    # step 4: ropani/bigha → hectares
    graph.add_edge("convert_units",     "classify_zone")

    # step 5: district → Terai/Hills/Mountains
    graph.add_edge("classify_zone",     "calculate_income")

    # step 6: yield × price → NPR estimate
    graph.add_edge("calculate_income",  "resolve_conversation")  # ← resolve BEFORE route_farmer

    # step 7: resolve mode + next question + fetch crop tip from RAG
    graph.add_edge("resolve_conversation", "route_farmer")

    # step 8: validate fields + branch by farmer type
    graph.add_conditional_edges(
        "route_farmer",
        _route_after_validation,
        {
            "error":  "synthesize_llm",       # still reply gracefully, don't just END
            "type_a": "calculate_das_gdd",
            "type_b": "check_crop_suitability",
        },
    )

    # ── Type A path ───────────────────────────────────────────────────────────
    graph.add_edge("calculate_das_gdd",       "apply_safety_guardrails")
    graph.add_edge("apply_safety_guardrails", "build_rule_output")

    # ── Type B path ───────────────────────────────────────────────────────────
    graph.add_edge("check_crop_suitability",  "build_rule_output")

    # ── Shared tail (both paths meet here) ────────────────────────────────────
    # retrieve_rag_context here is for rule_output grounding (growth stage / zone docs)
    # crop_tip was already fetched in resolve_conversation above
    graph.add_edge("build_rule_output",    "retrieve_rag_context")
    graph.add_edge("retrieve_rag_context", "synthesize_llm")
    graph.add_edge("synthesize_llm",       END)

    return graph.compile()


# ── Singleton ─────────────────────────────────────────────────────────────────
_advisory_graph = None

def get_advisory_graph():
    global _advisory_graph
    if _advisory_graph is None:
        _advisory_graph = build_advisory_graph()
    return _advisory_graph