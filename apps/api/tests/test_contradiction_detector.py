"""Tests for contradiction_detector service."""

import pytest

from services.contradiction_detector import (
    compute_confidence,
    build_citation_refs,
    detect_contradictions,
    _keyword_heuristic,
    _extract_texts,
)


# ── compute_confidence ──────────────────────────────────────


def test_compute_confidence_basic():
    """Entity with no provenance gets base score."""
    entity = {"id": "test-1", "name": "Test Entity"}
    score = compute_confidence(entity, source_count=0)
    assert score == pytest.approx(0.3, abs=0.01)


def test_compute_confidence_with_sources():
    """More sources → higher score."""
    entity = {"id": "test-2", "name": "Test Entity"}
    score_1 = compute_confidence(entity, source_count=1)
    score_3 = compute_confidence(entity, source_count=3)
    assert score_1 > 0.3
    assert score_3 > score_1
    assert score_3 == pytest.approx(0.6, abs=0.01)  # 0.3 + 3*0.1


def test_compute_confidence_rich():
    """Entity with PMID, recent year, GWAS gets high score."""
    entity = {
        "id": "test-3",
        "name": "Rich Entity",
        "pmid": "12345678",
        "year": 2024,
        "gwas_significance": 0.95,
        "nct_id": "NCT000001",
        "uniprot_id": "P00000",
    }
    score = compute_confidence(entity, source_count=3)
    # 0.3 base + 0.3 sources + 0.1 pmid + 0.1 recent + 0.1 gwas + 0.1 multi-type = 1.0
    assert score == pytest.approx(1.0, abs=0.01)


def test_compute_confidence_caps_at_one():
    """Score never exceeds 1.0."""
    entity = {
        "id": "test-4",
        "pmid": "X",
        "doi": "10/Y",
        "year": 2025,
        "gwas_significance": 1.0,
        "nct_id": "NCT1",
        "uniprot_id": "UNI",
    }
    score = compute_confidence(entity, source_count=10)
    assert score <= 1.0


# ── build_citation_refs ─────────────────────────────────────


def test_build_citation_refs_pmid():
    """Entity with PMID produces a PubMed citation ref."""
    entity = {
        "id": "e-1",
        "pmid": "12345",
        "title": "A Study",
        "year": 2023,
    }
    refs = build_citation_refs(entity, ["PubMed"])
    assert len(refs) >= 1
    pubmed_refs = [r for r in refs if r["source"] == "PubMed"]
    assert len(pubmed_refs) == 1
    assert "12345" in pubmed_refs[0]["external_id"]
    assert pubmed_refs[0]["url"].startswith("https://pubmed")


def test_build_citation_refs_empty():
    """Entity with no IDs still gets a generic ref."""
    entity = {"id": "e-2", "canonical_name": "Some Entity"}
    refs = build_citation_refs(entity, ["UniProt"])
    assert len(refs) >= 1
    assert refs[0]["source"] == "UniProt"


def test_build_citation_refs_multiple():
    """Entity with both PMID and NCT produces multiple refs."""
    entity = {
        "id": "e-3",
        "pmid": "999",
        "nct_id": "NCT001",
        "title": "Multi",
    }
    refs = build_citation_refs(entity, [])
    sources = {r["source"] for r in refs}
    assert "PubMed" in sources
    assert "ClinicalTrials" in sources


# ── _keyword_heuristic ──────────────────────────────────────


def test_keyword_heuristic_finds_contradiction():
    """Opposing signal words are detected."""
    texts = [
        ("Drug X inhibits target A effectively in vitro", {"id": "a", "_confidence": 0.5}),
        ("Drug X activates target A leading to increased expression", {"id": "b", "_confidence": 0.6}),
    ]
    results = _keyword_heuristic(texts)
    assert len(results) >= 1
    assert results[0]["severity"] == "moderate"
    assert "inhibits" in results[0]["explanation"] or "activates" in results[0]["explanation"]


def test_keyword_heuristic_no_contradiction():
    """Consistent claims return empty."""
    texts = [
        ("Protein X is expressed in the liver", {"id": "a", "_confidence": 0.5}),
        ("Protein X is found abundantly in hepatocytes", {"id": "b", "_confidence": 0.6}),
    ]
    results = _keyword_heuristic(texts)
    assert len(results) == 0


def test_keyword_heuristic_risk_vs_protective():
    """Risk factor vs protective detected."""
    texts = [
        ("Gene Y is a risk factor for diabetes", {"id": "a", "_confidence": 0.7}),
        ("Gene Y has a protective role against diabetes", {"id": "b", "_confidence": 0.8}),
    ]
    results = _keyword_heuristic(texts)
    assert len(results) >= 1


# ── detect_contradictions (async) ───────────────────────────


@pytest.mark.asyncio
async def test_detect_contradictions_graceful_fallback():
    """Works without LLM — returns keyword heuristic results only."""
    entities = {
        "protein": [
            {"id": "p1", "name": "Protein A", "description": "This protein inhibits kinase X"},
            {"id": "p2", "name": "Protein B", "description": "This protein activates kinase X"},
        ],
    }
    results = await detect_contradictions(entities, "kinase X")
    assert isinstance(results, list)
    # Should find at least the keyword heuristic contradiction
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_detect_contradictions_empty_input():
    """Empty or single entity returns no contradictions."""
    entities = {"protein": [{"id": "p1", "description": "A protein"}]}
    results = await detect_contradictions(entities, "test")
    assert results == []


@pytest.mark.asyncio
async def test_detect_contradictions_deduplicates():
    """Duplicate contradictions by entity pair are removed."""
    entities = {
        "drug": [
            {"id": "d1", "name": "Drug1", "description": "Upregulated expression in trials"},
            {"id": "d2", "name": "Drug2", "description": "Downregulated expression observed"},
        ],
    }
    results = await detect_contradictions(entities, "expression")
    # Should be deduplicated — at most 1 per pair
    pairs = [(r["source_a"]["external_id"], r["source_b"]["external_id"]) for r in results]
    assert len(pairs) == len(set(pairs))


# ── _extract_texts ──────────────────────────────────────────


def test_extract_texts():
    """Extracts descriptive text from entities."""
    entities = {
        "protein": [
            {"id": "p1", "description": "A kinase enzyme", "canonical_name": "PKA"},
            {"id": "p2"},  # no text
        ],
        "drug": [
            {"id": "d1", "mechanism_of_action": "Inhibits serotonin reuptake"},
        ],
    }
    texts = _extract_texts(entities)
    assert len(texts) == 2  # p2 has no text, so excluded
    assert any("kinase" in t for t, _ in texts)
    assert any("serotonin" in t for t, _ in texts)
