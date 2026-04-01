"""Tests for the DossierBuilder decision-dossier assembler."""

from unittest.mock import patch

from services.dossier_builder import DossierBuilder


# ── Fixture data ──────────────────────────────────────────

MOCK_TRACE = {
    "job_id": "job_test_001",
    "name": "Find EGFR inhibitors for NSCLC",
    "status": "completed",
    "started_at": "2025-01-15T10:00:00Z",
    "duration_ms": 5000,
    "steps": [
        {
            "id": 1,
            "name": "Query Decomposition",
            "timestamp": "10:00:01",
            "duration_ms": 50,
            "status": "success",
            "details": {
                "action_type": "decomposition",
                "outputs_summary": "Decomposed into sub-queries",
            },
        },
        {
            "id": 2,
            "name": "Fetch PubMed",
            "timestamp": "10:00:02",
            "duration_ms": 1200,
            "status": "success",
            "details": {
                "action_type": "tool_call",
                "tool_name": "pubmed",
                "outputs_summary": "Found 12 articles",
                "evidence_refs": ["ref_pubmed_123", "ref_pubmed_456"],
            },
        },
        {
            "id": 3,
            "name": "Apply Filters",
            "timestamp": "10:00:03",
            "duration_ms": 30,
            "status": "success",
            "details": {
                "action_type": "filter",
                "outputs_summary": "Filtered to kinase inhibitors only",
            },
        },
        {
            "id": 4,
            "name": "Synthesize",
            "timestamp": "10:00:04",
            "duration_ms": 200,
            "status": "success",
            "details": {
                "action_type": "synthesis",
                "outputs_summary": "Ranked targets",
                "top_targets_ranked": [
                    {"name": "EGFR", "score": 0.91, "uncertainty": 0.05, "note": "Strong kinase inhibitor evidence"},
                    {"name": "MET", "score": 0.78, "uncertainty": 0.08, "note": "Co-amplification in NSCLC"},
                ],
            },
        },
        {
            "id": 5,
            "name": "Contradiction Check",
            "timestamp": "10:00:05",
            "duration_ms": 100,
            "status": "warning",
            "details": {
                "action_type": "contradiction_check",
                "outputs_summary": "Islet exhaustion concern flagged",
                "errors": "Conflicting evidence on long-term safety",
                "evidence_refs": ["ref_pubmed_789"],
            },
        },
    ],
}

MOCK_RECIPE = {
    "schema_version": "1.0",
    "job_id": "job_test_001",
    "name": "Find EGFR inhibitors for NSCLC",
}

MOCK_EVIDENCE = {
    "edges": [
        {
            "edge_id": "edge_001",
            "src_entity": "PMID:999",
            "dst_entity": "Query:test",
            "source": "pubmed",
            "source_locator": "PMID:999#page=1",
        }
    ],
    "entities": [],
}

MOCK_ARTIFACTS = [
    {
        "artifact_id": "art_001",
        "type": "chart",
        "title": "Ranking Plot",
        "description": "Bar chart of target scores",
    }
]


def _patch_all():
    """Return a stack of patches for all DossierBuilder data sources."""
    return (
        patch("services.dossier_builder.JobLogger.get_job_trace", return_value=MOCK_TRACE),
        patch("services.dossier_builder.JobLogger.get_job_recipe", return_value=MOCK_RECIPE),
        patch("services.dossier_builder.EvidenceStore.get_job_evidence", return_value=MOCK_EVIDENCE),
        patch("services.dossier_builder.JobLogger.get_job_artifacts", return_value=MOCK_ARTIFACTS),
    )


# ── Tests ─────────────────────────────────────────────────

def test_build_returns_none_for_missing_job():
    with patch("services.dossier_builder.JobLogger.get_job_trace", return_value=None):
        result = DossierBuilder.build("nonexistent")
    assert result is None


def test_build_returns_full_dossier():
    p1, p2, p3, p4 = _patch_all()
    with p1, p2, p3, p4:
        dossier = DossierBuilder.build("job_test_001")
    assert dossier is not None
    expected_keys = {
        "schema_version", "job_id", "generated_at", "question",
        "constraints", "evidence", "ranking_table", "contradictions",
        "assumptions_and_overrides", "recommended_next_experiments",
        "media_artifacts", "run_recipe", "trace_summary",
    }
    assert expected_keys.issubset(set(dossier.keys()))


def test_dossier_schema_version():
    p1, p2, p3, p4 = _patch_all()
    with p1, p2, p3, p4:
        dossier = DossierBuilder.build("job_test_001")
    assert dossier["schema_version"] == "1.0"


def test_dossier_question_from_trace_name():
    p1, p2, p3, p4 = _patch_all()
    with p1, p2, p3, p4:
        dossier = DossierBuilder.build("job_test_001")
    assert dossier["question"] == "Find EGFR inhibitors for NSCLC"


def test_extract_constraints_with_filter_step():
    constraints = DossierBuilder._extract_constraints(MOCK_TRACE["steps"])
    assert constraints["applied"] is True
    assert "kinase inhibitors" in constraints["summary"]


def test_extract_constraints_no_filter():
    steps_no_filter = [s for s in MOCK_TRACE["steps"] if s["details"].get("action_type") != "filter"]
    constraints = DossierBuilder._extract_constraints(steps_no_filter)
    assert constraints["applied"] is False


def test_build_evidence_table_deduplicates():
    p1, p2, p3, p4 = _patch_all()
    with p1, p2, p3, p4:
        dossier = DossierBuilder.build("job_test_001")
    refs = [row["ref"] for row in dossier["evidence"]]
    assert len(refs) == len(set(refs)), "Evidence table contains duplicate refs"


def test_ref_to_locator_pubmed():
    assert DossierBuilder._ref_to_locator("ref_pubmed_12345") == "PMID:12345"


def test_ref_to_locator_opentargets():
    assert DossierBuilder._ref_to_locator("ref_ot_ENSG00000146648") == "OpenTargets:ENSG00000146648"


def test_ref_to_locator_chembl():
    assert DossierBuilder._ref_to_locator("ref_chembl_CHEMBL941") == "ChEMBL:CHEMBL941"


def test_render_html_contains_doctype():
    p1, p2, p3, p4 = _patch_all()
    with p1, p2, p3, p4:
        dossier = DossierBuilder.build("job_test_001")
    html = DossierBuilder.render_html(dossier)
    assert html.startswith("<!DOCTYPE html>")


def test_render_html_escapes_xss():
    p1, p2, p3, p4 = _patch_all()
    with p1, p2, p3, p4:
        dossier = DossierBuilder.build("job_test_001")
    dossier["question"] = '<script>alert("xss")</script>'
    html = DossierBuilder.render_html(dossier)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_contradictions_extracted():
    p1, p2, p3, p4 = _patch_all()
    with p1, p2, p3, p4:
        dossier = DossierBuilder.build("job_test_001")
    assert len(dossier["contradictions"]) >= 1
    assert dossier["contradictions"][0]["step"] == "Contradiction Check"


def test_ranking_table_populated():
    p1, p2, p3, p4 = _patch_all()
    with p1, p2, p3, p4:
        dossier = DossierBuilder.build("job_test_001")
    assert len(dossier["ranking_table"]) >= 1
    assert dossier["ranking_table"][0]["rank"] == 1
