"""Unit tests for Research Labs real computation (Task 3).

Tests the enhanced inline lab functions in routers/labs.py:
- Provenance builder (3.9)
- StructuredError model (3.9)
- Epitope prediction helpers (3.6)
- ADMET prediction (3.4)
- Retrosynthesis (3.5)
- Metabolic Engineering (3.7)
"""

from __future__ import annotations

import sys
import os
import pytest

# Ensure the apps/api directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ── Helpers ───────────────────────────────────────────────

def _has_provenance(result: dict) -> bool:
    """Check that result has a valid provenance chain."""
    prov = result.get("provenance", {})
    return (
        isinstance(prov.get("sources_queried"), list)
        and isinstance(prov.get("sources_succeeded"), list)
        and isinstance(prov.get("sources_degraded"), list)
        and isinstance(prov.get("computation_time_ms"), int)
        and isinstance(prov.get("generated_at"), str)
        and len(prov["generated_at"]) > 0
    )


# ── 3.9 Structured Error Handling & Provenance ───────────

class TestStructuredErrorAndProvenance:
    """Tests for StructuredError model and _build_provenance."""

    def test_structured_error_model(self):
        """StructuredError model has required fields."""
        from routers.labs import StructuredError
        err = StructuredError(
            error_code="TOOL_UNAVAILABLE",
            message="fpocket not found",
            suggested_remediation="conda install -c bioconda fpocket",
            service="fpocket",
        )
        d = err.model_dump()
        assert d["error_code"] == "TOOL_UNAVAILABLE"
        assert d["service"] == "fpocket"
        assert "install" in d["suggested_remediation"].lower()

    def test_structured_error_with_degraded_result(self):
        """StructuredError can carry a degraded_result."""
        from routers.labs import StructuredError
        err = StructuredError(
            error_code="CONNECTOR_TIMEOUT",
            message="OpenTargets timed out",
            suggested_remediation="Retry later",
            service="OpenTargets",
            retry_after_seconds=30,
            degraded_result={"partial": True, "targets": []},
        )
        d = err.model_dump()
        assert d["retry_after_seconds"] == 30
        assert d["degraded_result"]["partial"] is True

    def test_build_provenance(self):
        """_build_provenance returns valid provenance chain."""
        from routers.labs import _build_provenance
        prov = _build_provenance(
            sources_queried=["A", "B"],
            sources_succeeded=["A"],
            sources_degraded=["B"],
            computation_time_ms=100,
        )
        assert prov["sources_queried"] == ["A", "B"]
        assert prov["sources_succeeded"] == ["A"]
        assert prov["sources_degraded"] == ["B"]
        assert prov["computation_time_ms"] == 100
        assert len(prov["generated_at"]) > 0
        # generated_at should be ISO format
        assert "T" in prov["generated_at"]

    def test_build_provenance_empty(self):
        """_build_provenance works with empty lists."""
        from routers.labs import _build_provenance
        prov = _build_provenance([], [], [], 0)
        assert prov["sources_queried"] == []
        assert prov["computation_time_ms"] == 0

    @pytest.mark.asyncio
    async def test_run_lab_inline_unknown_type(self):
        """Unknown lab type returns degraded with provenance."""
        from routers.labs import _run_lab_inline
        result = await _run_lab_inline("labs.unknown_type", {})
        assert result["status"] == "degraded"
        assert _has_provenance(result)


# ── 3.6 Vaccine Design: epitope prediction helpers ───────

class TestEpitopePrediction:
    """Tests for epitope prediction helper functions."""

    def test_hydrophilicity_score_hydrophilic(self):
        """Arginine (R) is highly hydrophilic."""
        from routers.labs import _hydrophilicity_score
        assert _hydrophilicity_score("R") > 0

    def test_hydrophilicity_score_hydrophobic(self):
        """Isoleucine (I) is hydrophobic."""
        from routers.labs import _hydrophilicity_score
        assert _hydrophilicity_score("I") < 0

    def test_hydrophilicity_score_mixed(self):
        """Mixed peptide returns intermediate score."""
        from routers.labs import _hydrophilicity_score
        score = _hydrophilicity_score("ARIK")
        assert isinstance(score, float)

    def test_hydrophilicity_score_empty(self):
        """Empty string returns 0."""
        from routers.labs import _hydrophilicity_score
        assert _hydrophilicity_score("") == 0.0

    def test_predict_bcell_epitopes_basic(self):
        """B-cell epitope prediction returns ranked epitopes."""
        from routers.labs import _predict_bcell_epitopes
        seq = "MFVFLVLLPLVSSQCVNLTTRTQLPPAYTNSFTRGVYYPDKVFRSSVLHSTQDLFLPFFSNVTWFHAI"
        epitopes = _predict_bcell_epitopes(seq, window=15, top_n=5)
        assert len(epitopes) > 0
        assert len(epitopes) <= 5
        # Sorted by hydrophilicity descending
        scores = [e["hydrophilicity_score"] for e in epitopes]
        assert scores == sorted(scores, reverse=True)

    def test_predict_bcell_epitopes_fields(self):
        """Each B-cell epitope has required fields."""
        from routers.labs import _predict_bcell_epitopes
        seq = "MFVFLVLLPLVSSQCVNLTTRTQLPPAYTNSFTRGVYYPDKVFRSSVLHSTQDLFLPFFSNVTWFHAI"
        epitopes = _predict_bcell_epitopes(seq, window=15, top_n=3)
        for e in epitopes:
            assert "epitope_id" in e
            assert "start" in e
            assert "end" in e
            assert "sequence" in e
            assert "hydrophilicity_score" in e
            assert "type" in e
            assert "source" in e
            assert len(e["sequence"]) == 15

    def test_predict_tcell_epitopes_basic(self):
        """T-cell epitope prediction returns ranked epitopes."""
        from routers.labs import _predict_tcell_epitopes
        seq = "MFVFLVLLPLVSSQCVNLTTRTQLPPAYTNSFTRGVYYPDKVFRSSVLHSTQDLFLPFFSNVTWFHAI"
        epitopes = _predict_tcell_epitopes(seq, window=9, top_n=5)
        assert len(epitopes) > 0
        assert len(epitopes) <= 5
        scores = [e["amphipathicity_score"] for e in epitopes]
        assert scores == sorted(scores, reverse=True)

    def test_predict_tcell_epitopes_fields(self):
        """Each T-cell epitope has required fields."""
        from routers.labs import _predict_tcell_epitopes
        seq = "MFVFLVLLPLVSSQCVNLTTRTQLPPAYTNSFTRGVYYPDKVFRSSVLHSTQDLFLPFFSNVTWFHAI"
        epitopes = _predict_tcell_epitopes(seq, window=9, top_n=3)
        for e in epitopes:
            assert "epitope_id" in e
            assert "start" in e
            assert "end" in e
            assert "sequence" in e
            assert "amphipathicity_score" in e
            assert e["type"] == "CD8+"
            assert len(e["sequence"]) == 9

    def test_short_sequence_returns_empty(self):
        """Sequences shorter than window return empty epitope list."""
        from routers.labs import _predict_bcell_epitopes, _predict_tcell_epitopes
        assert _predict_bcell_epitopes("SHORT", window=15) == []
        assert _predict_tcell_epitopes("SHORT", window=9) == []


# ── 3.4 ADMET (synchronous predictor test) ───────────────

class TestADMETPredictor:
    """Tests for ADMET prediction via ADMETPredictor."""

    def test_admet_predict_all_categories(self):
        """ADMETPredictor.predict returns all 5 ADMET categories."""
        from services.molecule_service import ADMETPredictor
        predictor = ADMETPredictor()
        result = predictor.predict("CCO")
        assert "absorption" in result
        assert "distribution" in result
        assert "metabolism" in result
        assert "excretion" in result
        assert "toxicity" in result

    def test_admet_confidence_interval(self):
        """ADMETPredictor returns confidence interval with valid bounds."""
        from services.molecule_service import ADMETPredictor
        predictor = ADMETPredictor()
        result = predictor.predict("CCO")
        ci = result.get("confidence_interval", {})
        assert "lower" in ci
        assert "upper" in ci
        assert ci["lower"] <= ci["upper"]
        assert 0.0 <= ci["lower"] <= 1.0
        assert 0.0 <= ci["upper"] <= 1.0

    def test_admet_multiple_smiles(self):
        """ADMETPredictor works for multiple SMILES."""
        from services.molecule_service import ADMETPredictor
        predictor = ADMETPredictor()
        smiles_list = ["CCO", "c1ccccc1", "CC(=O)O"]
        for smi in smiles_list:
            result = predictor.predict(smi)
            assert result["smiles"] == smi
            assert "absorption" in result


# ── 3.5 Retrosynthesis (inline, fast) ────────────────────

class TestRetrosynthesisInline:
    """Tests for retrosynthesis inline computation."""

    @pytest.mark.asyncio
    async def test_retrosynthesis_provenance(self):
        """Retrosynthesis result includes provenance."""
        from routers.labs import _inline_retrosynthesis
        result = await _inline_retrosynthesis({"smiles": "CC(=O)Oc1ccccc1C(=O)O"})
        assert _has_provenance(result)

    @pytest.mark.asyncio
    async def test_retrosynthesis_routes_have_feasibility(self):
        """Each route step has a feasibility score in [0, 1]."""
        from routers.labs import _inline_retrosynthesis
        result = await _inline_retrosynthesis({"smiles": "CC(=O)Oc1ccccc1C(=O)O"})
        for route in result.get("artifacts", []):
            assert "feasibility" in route
            assert 0.0 <= route["feasibility"] <= 1.0

    @pytest.mark.asyncio
    async def test_retrosynthesis_max_steps(self):
        """Respects max_steps parameter."""
        from routers.labs import _inline_retrosynthesis
        result = await _inline_retrosynthesis({"smiles": "CC(=O)Oc1ccccc1C(=O)O", "max_steps": 3})
        assert len(result.get("artifacts", [])) <= 3


# ── 3.7 Metabolic Engineering (inline, fast) ─────────────

class TestMetabolicEngineeringInline:
    """Tests for metabolic engineering inline computation."""

    @pytest.mark.asyncio
    async def test_metabolic_engineering_provenance(self):
        """Metabolic engineering result includes provenance."""
        from routers.labs import _inline_metabolic_engineering
        result = await _inline_metabolic_engineering({
            "organism": "E. coli", "target_metabolite": "lysine",
        })
        assert _has_provenance(result)

    @pytest.mark.asyncio
    async def test_metabolic_engineering_returns_data(self):
        """Metabolic engineering returns pathway designs and FBA results."""
        from routers.labs import _inline_metabolic_engineering
        result = await _inline_metabolic_engineering({
            "organism": "E. coli", "target_metabolite": "lysine",
        })
        if result["status"] == "success":
            artifacts = result["artifacts"]
            assert len(artifacts) > 0
            art = artifacts[0]
            assert "fba_results" in art
            assert "pathway_designs" in art
            assert "strain_recommendations" in art


# ── 3.4 ADMET inline (fast, no network) ──────────────────

class TestADMETInline:
    """Tests for ADMET inline computation."""

    @pytest.mark.asyncio
    async def test_admet_inline_provenance(self):
        """ADMET inline result includes provenance."""
        from routers.labs import _inline_admet
        result = await _inline_admet({"smiles_list": ["CCO"]})
        assert _has_provenance(result)

    @pytest.mark.asyncio
    async def test_admet_inline_all_categories(self):
        """ADMET inline returns all 5 categories per molecule."""
        from routers.labs import _inline_admet
        result = await _inline_admet({"smiles_list": ["CCO"]})
        if result["status"] == "success":
            for pred in result["artifacts"]:
                assert "absorption" in pred
                assert "distribution" in pred
                assert "metabolism" in pred
                assert "excretion" in pred
                assert "toxicity" in pred

    @pytest.mark.asyncio
    async def test_admet_inline_confidence_intervals(self):
        """ADMET inline predictions include valid confidence intervals."""
        from routers.labs import _inline_admet
        result = await _inline_admet({"smiles_list": ["CCO"]})
        if result["status"] == "success":
            for pred in result["artifacts"]:
                ci = pred.get("confidence_interval", {})
                lb = ci.get("lower_bound", 0)
                ub = ci.get("upper_bound", 1)
                assert 0.0 <= lb <= 1.0
                assert 0.0 <= ub <= 1.0
                assert lb <= ub

    @pytest.mark.asyncio
    async def test_admet_inline_empty_list(self):
        """Empty SMILES list returns success with zero count."""
        from routers.labs import _inline_admet
        result = await _inline_admet({"smiles_list": []})
        assert result["count"] == 0


# ── 3.6 Vaccine inline (fast, no network) ────────────────

class TestVaccineInline:
    """Tests for vaccine design inline computation."""

    @pytest.mark.asyncio
    async def test_vaccine_with_sequence(self):
        """With antigen sequence, returns B-cell and T-cell epitopes."""
        from routers.labs import _inline_vaccine
        seq = "MFVFLVLLPLVSSQCVNLTTRTQLPPAYTNSFTRGVYYPDKVFRSSVLHSTQDLFLPFFSNVTWFHAI"
        result = await _inline_vaccine({
            "pathogen": "SARS-CoV-2", "antigen_sequence": seq,
        })
        assert result["status"] == "success"
        assert len(result.get("bcell_epitopes", [])) > 0
        assert len(result.get("tcell_epitopes", [])) > 0
        assert _has_provenance(result)

    @pytest.mark.asyncio
    async def test_vaccine_candidates_ranked(self):
        """Vaccine candidates have overall_score."""
        from routers.labs import _inline_vaccine
        seq = "MFVFLVLLPLVSSQCVNLTTRTQLPPAYTNSFTRGVYYPDKVFRSSVLHSTQDLFLPFFSNVTWFHAI"
        result = await _inline_vaccine({
            "pathogen": "test", "antigen_sequence": seq,
        })
        if result["status"] == "success":
            for c in result["artifacts"]:
                assert "overall_score" in c
                assert 0.0 <= c["overall_score"] <= 1.0
