"""Tests for Phase 11 — RL/DL Model Enhancement.

Covers: bioisosteric molecule generation, retrosynthesis templates,
ADMET prediction, graph-based ontology completion, evidence-weighted
target prioritization, and guardrail checks.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest

from config import settings
from services.dl_models import DLModelService, RDKIT_AVAILABLE
from services.rl_optimizer import RLService, OptimizationConstraints


@pytest.fixture(autouse=True)
def _force_embedded(monkeypatch):
    """Force embedded storage backend so graph store picks NetworkX."""
    monkeypatch.setattr(settings, "dss_storage_backend", "embedded")


# ── Molecule generation ──────────────────────────────────

@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit not installed")
def test_generate_molecules_produces_valid_smiles():
    """All candidates must parse as valid SMILES with RDKit."""
    from rdkit import Chem

    result = RLService.generate_molecules(
        base_smiles="CC(=O)Oc1ccccc1C(=O)O",  # Aspirin
        constraints=OptimizationConstraints(max_steps=10),
    )
    assert result["status"] == "success"
    assert len(result["candidates"]) > 0

    for cand in result["candidates"]:
        mol = Chem.MolFromSmiles(cand["smiles"])
        assert mol is not None, f"Invalid SMILES: {cand['smiles']}"
        assert cand["reward_score"] > 0
        assert "origin" in cand


@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit not installed")
def test_generate_molecules_guardrails():
    """Guardrails must reject molecules containing restricted substructures."""
    # Amphetamine core: NC(C)CC1=CC=CC=C1
    result = RLService.generate_molecules(
        base_smiles="NC(C)CC1=CC=CC=C1",
        constraints=OptimizationConstraints(forbid_illicit_targets=True),
    )
    assert result["status"] == "rejected"
    assert "Guardrail" in result.get("reason", "")


@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit not installed")
def test_generate_molecules_admet_scores():
    """Each candidate must have ADMET predictions attached."""
    result = RLService.generate_molecules(
        base_smiles="c1ccccc1O",  # Phenol — has OH for bioisosteric swap
        constraints=OptimizationConstraints(max_steps=5),
    )
    assert result["status"] == "success"
    for cand in result["candidates"]:
        assert "admet" in cand
        # If ADMET ran, should have molecular_weight
        if cand["admet"] is not None:
            assert "molecular_weight" in cand["admet"] or cand["admet"] is None


# ── Retrosynthesis ───────────────────────────────────────

@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit not installed")
def test_retrosynthesis_returns_steps():
    """Template matching on acetaminophen must produce disconnection steps."""
    # Acetaminophen: CC(=O)Nc1ccc(O)cc1  (has amide bond → should match)
    result = RLService.analyze_retrosynthesis("CC(=O)Nc1ccc(O)cc1")
    assert result["status"] == "success"
    assert len(result["steps"]) > 0

    for step in result["steps"]:
        assert "reaction" in step
        assert "precursors" in step
        assert len(step["precursors"]) > 0
        assert 0 < step["confidence"] <= 1.0
        assert "step_id" in step


@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit not installed")
def test_retrosynthesis_no_match():
    """Simple molecule with no matching templates returns gracefully."""
    # Methane — extremely simple, no functional groups for retro templates
    result = RLService.analyze_retrosynthesis("C")
    assert result["status"] == "no_templates_matched"
    assert result["steps"] == []
    assert result["metadata"]["templates_checked"] > 0


# ── Ontology completion (graph-based) ────────────────────

def test_ontology_completion_with_graph(tmp_store):
    """Returns predicted edges when graph has data."""
    from services.graph_store import get_graph_store

    store = get_graph_store()
    loop = asyncio.new_event_loop()

    # Build a small test graph: Disease → Gene → Protein
    loop.run_until_complete(store.create_node("Disease", "D001", {"name": "Diabetes"}))
    loop.run_until_complete(store.create_node("Gene", "G001", {"name": "PPARG"}))
    loop.run_until_complete(store.create_node("Gene", "G002", {"name": "INS"}))
    loop.run_until_complete(store.create_node("Protein", "P001", {"name": "Insulin"}))
    loop.run_until_complete(store.create_edge("Disease", "D001", "associated", "Gene", "G001"))
    loop.run_until_complete(store.create_edge("Disease", "D001", "associated", "Gene", "G002"))
    loop.run_until_complete(store.create_edge("Gene", "G001", "encodes", "Protein", "P001"))
    loop.run_until_complete(store.create_edge("Gene", "G002", "encodes", "Protein", "P001"))
    loop.close()

    result = DLModelService.run_ontology_completion(["D001", "G001"])
    assert result.status in ("graph_analysis_success", "fallback")
    assert result.model_type == "rgcn_ontology"
    assert result.metadata.get("graph_nodes", 0) >= 4


def test_ontology_completion_empty_graph(tmp_store):
    """Returns fallback when graph store is empty."""
    result = DLModelService.run_ontology_completion(["BRCA1", "TP53"])
    assert result.status == "fallback"
    assert result.predictions == []
    assert "reason" in result.metadata


# ── Target prioritization ────────────────────────────────

def test_target_prioritization_returns_scores(tmp_store):
    """Genes connected to the disease must have positive scores."""
    from services.graph_store import get_graph_store

    store = get_graph_store()
    loop = asyncio.new_event_loop()

    loop.run_until_complete(store.create_node("Disease", "cancer", {"name": "Cancer"}))
    loop.run_until_complete(store.create_node("Gene", "EGFR", {"name": "EGFR"}))
    loop.run_until_complete(store.create_node("Gene", "BRAF", {"name": "BRAF"}))
    loop.run_until_complete(store.create_node("Gene", "TP53", {"name": "TP53"}))
    loop.run_until_complete(store.create_edge("Disease", "cancer", "associated", "Gene", "EGFR"))
    loop.run_until_complete(store.create_edge("Disease", "cancer", "associated", "Gene", "BRAF"))
    loop.run_until_complete(store.create_edge("Gene", "EGFR", "interacts", "Gene", "TP53"))
    loop.close()

    result = DLModelService.run_target_prioritization("cancer")
    assert result.status == "graph_analysis_success"
    assert result.model_type == "gat_prioritization"
    assert len(result.predictions) > 0

    for gene_id, info in result.predictions.items():
        assert info["score"] > 0
        assert "details" in info


def test_target_prioritization_empty(tmp_store):
    """Returns fallback when disease is not in graph."""
    result = DLModelService.run_target_prioritization("nonexistent_disease_xyz")
    assert result.status == "fallback"
    assert result.predictions == {}
    assert "reason" in result.metadata


# ── ADMET (existing functionality) ───────────────────────

@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit not installed")
def test_admet_aspirin():
    """Real ADMET for aspirin SMILES produces valid Lipinski properties."""
    result = DLModelService.run_admet_prediction("CC(=O)Oc1ccccc1C(=O)O")
    assert result.status == "baseline_success"
    assert result.model_type == "admet_prediction"

    pred = result.predictions
    assert pred["molecular_weight"] > 0
    assert "logp" in pred
    assert "h_bond_acceptors" in pred
    assert "h_bond_donors" in pred
    assert "tpsa" in pred
    assert pred["lipinski_violations"] >= 0
    assert isinstance(pred["drug_like"], bool)
    # Aspirin MW ~180, should be drug-like
    assert pred["drug_like"] is True
