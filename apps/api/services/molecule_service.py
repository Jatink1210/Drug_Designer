"""Molecule Design Studio service — scoring, ADMET, analogs, novelty."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import structlog

from config import settings

log = structlog.get_logger()


# ── Physicochemical Rules (Lipinski / Veber / Ghose) ──────

def compute_physichem(smiles: str) -> Dict[str, Any]:
    """Compute physicochemical properties from SMILES (rule-based approximation)."""
    # Approximate MW from SMILES string length (rough heuristic)
    mw_estimate = len(smiles.replace("[", "").replace("]", "")) * 12.0  # very rough
    # Count HBD/HBA from common patterns
    hbd = smiles.count("O") + smiles.count("N") - smiles.count("n")
    hba = smiles.count("O") + smiles.count("N") + smiles.count("F")
    rotatable = smiles.count("-") + max(0, smiles.count("C") - 6)
    rings = smiles.count("1") + smiles.count("2")  # ring closures

    return {
        "smiles": smiles,
        "mw_estimate": round(mw_estimate, 1),
        "hbd": max(hbd, 0),
        "hba": max(hba, 0),
        "rotatable_bonds": max(rotatable, 0),
        "rings": rings,
        "lipinski_violations": sum([
            mw_estimate > 500,
            hbd > 5,
            hba > 10,
            # logP can't be computed without RDKit
        ]),
        "druglikeness": "pass" if mw_estimate <= 500 and hbd <= 5 and hba <= 10 else "flag",
        "note": "Estimates without RDKit. Install rdkit for accurate values.",
    }


def compute_physichem_rdkit(smiles: str) -> Dict[str, Any]:
    """Compute physicochemical properties using RDKit (if available)."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"error": "Invalid SMILES", "smiles": smiles}

        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd = rdMolDescriptors.CalcNumHBD(mol)
        hba = rdMolDescriptors.CalcNumHBA(mol)
        tpsa = Descriptors.TPSA(mol)
        rotatable = rdMolDescriptors.CalcNumRotatableBonds(mol)
        rings = rdMolDescriptors.CalcNumRings(mol)
        aromatic_rings = rdMolDescriptors.CalcNumAromaticRings(mol)
        fsp3 = rdMolDescriptors.CalcFractionCSP3(mol)

        lipinski_violations = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
        veber_pass = rotatable <= 10 and tpsa <= 140

        return {
            "smiles": smiles,
            "mw": round(mw, 2),
            "logp": round(logp, 2),
            "hbd": hbd,
            "hba": hba,
            "tpsa": round(tpsa, 2),
            "rotatable_bonds": rotatable,
            "rings": rings,
            "aromatic_rings": aromatic_rings,
            "fsp3": round(fsp3, 3),
            "lipinski_violations": lipinski_violations,
            "lipinski_pass": lipinski_violations <= 1,
            "veber_pass": veber_pass,
            "druglikeness": "pass" if lipinski_violations <= 1 and veber_pass else "flag",
            "engine": "rdkit",
        }
    except ImportError:
        return compute_physichem(smiles)


# ── ADMET Prediction ──────────────────────────────────────

class ADMETPredictor:
    """ADMET prediction with rule-based defaults + plugin interface for learned models."""

    def predict(self, smiles: str) -> Dict[str, Any]:
        props = compute_physichem_rdkit(smiles)
        mw = props.get("mw", props.get("mw_estimate", 0))
        logp = props.get("logp", 0)
        tpsa = props.get("tpsa", 0)
        hbd = props.get("hbd", 0)

        return {
            "smiles": smiles,
            "absorption": {
                "hia": "high" if tpsa < 140 and mw < 500 else "low",
                "caco2_permeable": tpsa < 90,
                "pgp_substrate": mw > 400 and hbd > 2,
            },
            "distribution": {
                "bbb_penetrant": tpsa < 80 and mw < 450 and logp > 0 and logp < 4,
                "vd_estimate": "low" if logp < 1 else ("high" if logp > 3 else "moderate"),
                "ppb_estimate": "high" if logp > 3 else "moderate",
            },
            "metabolism": {
                "cyp3a4_substrate": mw > 300,
                "cyp2d6_substrate": logp > 2 and mw > 250,
                "cyp_inhibitor_risk": "high" if logp > 3.5 else "low",
            },
            "excretion": {
                "clearance_estimate": "hepatic" if mw > 400 else "renal",
                "half_life_class": "long" if logp > 3 else "short",
            },
            "toxicity": {
                "herg_risk": "high" if logp > 4 and mw > 400 else "low",
                "ames_risk": "unknown",
                "hepatotoxicity_risk": "moderate" if logp > 3 else "low",
            },
            "synthetic_accessibility": _estimate_sa(smiles),
            "method": "rule_based",
            "note": "Rule-based predictions. For ML models, configure ADMET plugin.",
        }


def _estimate_sa(smiles: str) -> Dict[str, Any]:
    """Estimate synthetic accessibility."""
    try:
        from rdkit import Chem
        from rdkit.Chem import RDConfig
        import sys
        sys.path.append(os.path.join(RDConfig.RDContribDir, "SA_Score"))
        import sascorer
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            score = sascorer.calculateScore(mol)
            return {"sa_score": round(score, 2), "feasibility": "easy" if score < 4 else ("moderate" if score < 6 else "hard")}
    except Exception:
        log.debug("SA score calculation unavailable")
    return {"sa_score": None, "feasibility": "unknown", "note": "RDKit SA_Score not available"}


# ── Analog Generation ─────────────────────────────────────

class AnalogGenerator:
    """Generate molecular analogs via similarity search and scaffold operations."""

    async def generate_analogs(
        self,
        smiles: str,
        method: str = "similarity",
        num_analogs: int = 10,
    ) -> List[Dict[str, Any]]:
        if method == "similarity":
            return await self._similarity_search(smiles, num_analogs)
        elif method == "scaffold_hop":
            return self._scaffold_hop(smiles, num_analogs)
        elif method == "enumeration":
            return self._enumerate_substituents(smiles, num_analogs)
        return []

    async def _similarity_search(self, smiles: str, limit: int) -> List[Dict[str, Any]]:
        """Search PubChem for similar compounds."""
        from core.http_client import ResilientClient
        client = ResilientClient()
        try:
            url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/fastsimilarity_2d/smiles/%s/property/CanonicalSMILES,MolecularWeight,XLogP,TPSA,IUPACName/JSON" % smiles
            body, _ = await client.get(url, params={"Threshold": 85, "MaxRecords": limit})
            if not body:
                return []
            props = body.get("PropertyTable", {}).get("Properties", [])
            return [
                {
                    "cid": p.get("CID"),
                    "smiles": p.get("CanonicalSMILES", ""),
                    "name": p.get("IUPACName", ""),
                    "mw": p.get("MolecularWeight"),
                    "logp": p.get("XLogP"),
                    "tpsa": p.get("TPSA"),
                    "source": "PubChem similarity",
                }
                for p in props
            ]
        finally:
            await client.close()

    def _scaffold_hop(self, smiles: str, limit: int) -> List[Dict[str, Any]]:
        """Scaffold hopping via Murcko decomposition (requires RDKit)."""
        try:
            from rdkit import Chem
            from rdkit.Chem.Scaffolds import MurckoScaffold
            mol = Chem.MolFromSmiles(smiles)
            if not mol:
                return []
            core = MurckoScaffold.GetScaffoldForMol(mol)
            framework = MurckoScaffold.MakeScaffoldGeneric(core)
            return [{
                "scaffold": Chem.MolToSmiles(core),
                "generic_scaffold": Chem.MolToSmiles(framework),
                "source": "Murcko decomposition",
                "note": "Use scaffold for substructure search in ChEMBL/PubChem",
            }]
        except ImportError:
            return [{"error": "RDKit required for scaffold hopping"}]

    def _enumerate_substituents(self, smiles: str, limit: int) -> List[Dict[str, Any]]:
        return [{"note": "R-group enumeration requires RDKit and predefined libraries"}]


# ── Novelty Validation ────────────────────────────────────

class NoveltyValidator:
    """Check novelty against publications and patents."""

    async def check_novelty(self, smiles: str) -> Dict[str, Any]:
        """Search PubMed and PatentsView for similar/identical molecules."""
        from connectors.pubmed import PubMedConnector
        from connectors.patents import PatentsViewConnector

        pubmed = PubMedConnector()
        patents = PatentsViewConnector()

        try:
            pub_results = await pubmed.search(smiles[:50], limit=5)
            pat_results = await patents.search(smiles[:50], limit=5)

            return {
                "smiles": smiles,
                "publication_hits": len(pub_results),
                "patent_hits": len(pat_results),
                "publications": pub_results[:3],
                "patents": pat_results[:3],
                "novelty_assessment": "potentially_novel" if len(pub_results) == 0 and len(pat_results) == 0 else "known",
            }
        finally:
            await pubmed.close()
            await patents.close()


# ── Iteration Manager ─────────────────────────────────────

class IterationManager:
    """Save and retrieve design iterations with reproducibility bundles."""

    def __init__(self) -> None:
        self._dir = os.path.join(settings.local_store_path, "design_iterations")
        os.makedirs(self._dir, exist_ok=True)

    def save_iteration(
        self, target: str, smiles_list: List[str], scores: List[Dict], params: Dict[str, Any]
    ) -> str:
        iteration_id = str(uuid.uuid4())[:8]
        bundle = {
            "iteration_id": iteration_id,
            "target": target,
            "smiles": smiles_list,
            "scores": scores,
            "parameters": params,
            "timestamp": time.time(),
            "checksum": hashlib.sha256(json.dumps(smiles_list, sort_keys=True).encode()).hexdigest()[:16],
        }
        path = os.path.join(self._dir, "%s.json" % iteration_id)
        with open(path, "w") as f:
            json.dump(bundle, f, indent=2, default=str)
        return iteration_id

    def get_iteration(self, iteration_id: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(self._dir, "%s.json" % iteration_id)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def list_iterations(self) -> List[Dict[str, Any]]:
        iters = []
        for fname in sorted(os.listdir(self._dir), reverse=True)[:50]:
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(self._dir, fname)) as f:
                        data = json.load(f)
                        iters.append({
                            "iteration_id": data.get("iteration_id"),
                            "target": data.get("target"),
                            "num_compounds": len(data.get("smiles", [])),
                            "timestamp": data.get("timestamp"),
                        })
                except Exception:
                    log.debug("Skipping malformed iteration file")
        return iters
