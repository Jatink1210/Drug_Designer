from routers.cockpit import (
    _annotate_literature_llm_diagnostics,
    _build_quality_guards,
    _ensure_non_empty_llm_contradictions,
)


def test_ensure_non_empty_llm_contradictions_builds_fallback_entry():
    contradictions, applied = _ensure_non_empty_llm_contradictions(
        papers=[{"id": "paper-1"}],
        llm_contradictions=[],
        contradictions_detail=[{"claim_a": "supports response", "claim_b": "shows no effect", "severity": "moderate"}],
        runtime_diagnostics={"mode": "hosted"},
    )

    assert applied is True
    assert len(contradictions) == 1
    assert contradictions[0]["fallback_mode"] is True
    assert contradictions[0]["relationship"] == "Heuristic contradiction fallback"


def test_build_quality_guards_flags_low_targets_and_pathways():
    guards = _build_quality_guards(
        query_type="target_prioritization",
        target_ranking=[{"symbol": "EGFR"}, {"symbol": "KRAS"}],
        pathways_data=[],
        llm_contradictions=[{"relationship": "No verified contradictions found"}],
        contradiction_guard_applied=True,
    )

    assert guards["targets"]["status"] == "degraded"
    assert guards["pathways"]["status"] == "degraded"
    assert guards["llm_contradictions"]["status"] == "pass"


def test_build_quality_guards_applies_to_evidence_retrieval():
    guards = _build_quality_guards(
        query_type="evidence_retrieval",
        target_ranking=[{"symbol": "EGFR"}],
        pathways_data=[],
        llm_contradictions=[],
        contradiction_guard_applied=False,
    )

    assert guards["targets"]["minimum_expected"] == 3
    assert guards["pathways"]["minimum_expected"] == 1


def test_annotate_literature_llm_diagnostics_marks_heuristic_fallback():
    diagnostics = _annotate_literature_llm_diagnostics(
        llm_contradictions=[{"llm_verified": False}],
        runtime_diagnostics={"contradictions_mode": "llm", "fallbacks": []},
    )

    assert diagnostics["contradictions_mode"] == "heuristic_fallback"
    assert "llm_contradictions_heuristic_only" in diagnostics["fallbacks"]