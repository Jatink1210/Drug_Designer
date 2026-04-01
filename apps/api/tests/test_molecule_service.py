"""Tests for molecule_service.py — physicochemical properties, ADMET, iteration manager."""
from __future__ import annotations

from services.molecule_service import (
    compute_physichem,
    compute_physichem_rdkit,
    ADMETPredictor,
    IterationManager,
)

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
ETHANOL = "CCO"


def test_compute_physichem_returns_expected_keys():
    result = compute_physichem(ASPIRIN)
    assert "smiles" in result
    assert "mw_estimate" in result
    assert "hbd" in result
    assert "hba" in result
    assert "lipinski_violations" in result
    assert "druglikeness" in result


def test_compute_physichem_lipinski_pass():
    result = compute_physichem(ETHANOL)
    assert result["druglikeness"] == "pass"


def test_compute_physichem_lipinski_flag():
    # Very long SMILES to push MW estimate > 500
    long_smiles = "C" * 50
    result = compute_physichem(long_smiles)
    assert result["mw_estimate"] > 500
    assert result["druglikeness"] == "flag"


def test_compute_physichem_rdkit_aspirin():
    result = compute_physichem_rdkit(ASPIRIN)
    # RDKit is available in this env
    assert "mw" in result or "mw_estimate" in result
    if result.get("engine") == "rdkit":
        assert result["mw"] > 170  # aspirin MW ~180
        assert "logp" in result
        assert "tpsa" in result


def test_compute_physichem_rdkit_invalid():
    result = compute_physichem_rdkit("NOT_A_SMILES")
    # Should return error or fall back to heuristic
    if "error" in result:
        assert result["error"] == "Invalid SMILES"
    else:
        # Fell back to heuristic compute_physichem
        assert "mw_estimate" in result


def test_admet_predict_aspirin():
    predictor = ADMETPredictor()
    result = predictor.predict(ASPIRIN)
    assert "absorption" in result
    assert "distribution" in result
    assert "metabolism" in result
    assert "excretion" in result
    assert "toxicity" in result
    assert result["method"] == "rule_based"


def test_iteration_manager_save_load(tmp_store):
    mgr = IterationManager()
    iid = mgr.save_iteration(
        target="EGFR",
        smiles_list=["CCO", "CC(=O)O"],
        scores=[{"score": 0.8}, {"score": 0.6}],
        params={"method": "bioisosteric"},
    )
    loaded = mgr.get_iteration(iid)
    assert loaded is not None
    assert loaded["target"] == "EGFR"
    assert len(loaded["smiles"]) == 2


def test_iteration_manager_list(tmp_store):
    mgr = IterationManager()
    mgr.save_iteration("T1", ["CCO"], [{"s": 1}], {})
    mgr.save_iteration("T2", ["CC"], [{"s": 2}], {})
    items = mgr.list_iterations()
    assert len(items) >= 2
    targets = [i["target"] for i in items]
    assert "T1" in targets
    assert "T2" in targets
