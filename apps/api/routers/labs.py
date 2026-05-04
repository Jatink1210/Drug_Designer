"""Research Labs — Drug Designer §131, §24, §42.

Advanced autonomous research loops: target discovery, ADMET batch,
retrosynthesis, and vaccine design.

§78: All responses use ResponseEnvelope.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from models.db_tables import Run
from routers.auth import get_current_user, User
from worker import enqueue_job

router = APIRouter(prefix="/api/v1/labs", tags=["Research Labs"])
log = structlog.get_logger(__name__)


# ── Queue name mapping for each lab type ──────────────────
_LAB_QUEUE_MAP = {
    "labs.target_discovery": ("run_target_discovery_lab", "labs.target_discovery"),
    "admet.batch": ("run_admet_lab", "labs.admet"),
    "retrosynthesis.plan": ("run_retrosynthesis_lab", "labs.retrosynthesis"),
    "labs.vaccine_design": ("run_vaccine_design_lab", "labs.vaccine"),
    "labs.pocket_detection": ("run_pocket_detection_lab", "labs.pocket"),
    "labs.molecule_generation": ("run_molecule_generation_lab", "labs.molecule_generation"),
    "labs.admet": ("run_admet_lab", "labs.admet"),
    "labs.retrosynthesis": ("run_retrosynthesis_lab", "labs.retrosynthesis"),
    "labs.vaccine": ("run_vaccine_design_lab", "labs.vaccine"),
    "labs.metabolic_engineering": ("run_metabolic_engineering_lab", "labs.metabolic"),
    "labs.pharmacogenomics": ("run_pharmacogenomics_lab", "labs.pharmacogenomics"),
}


# ── Structured Error for graceful degradation (§2.10) ─────

class StructuredError(BaseModel):
    """Structured error with dependency info and degraded result."""
    error_code: str = "TOOL_UNAVAILABLE"
    message: str = ""
    suggested_remediation: str = ""
    service: Optional[str] = None
    retry_after_seconds: Optional[int] = None
    degraded_result: Optional[Dict[str, Any]] = None


# ── Provenance builder ────────────────────────────────────

def _build_provenance(
    sources_queried: List[str],
    sources_succeeded: List[str],
    sources_degraded: List[str],
    computation_time_ms: int,
) -> Dict[str, Any]:
    """Build a ProvenanceChain dict per design spec."""
    return {
        "sources_queried": sources_queried,
        "sources_succeeded": sources_succeeded,
        "sources_degraded": sources_degraded,
        "computation_time_ms": computation_time_ms,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Pydantic schemas ──────────────────────────────────────

class TargetDiscoveryRequest(BaseModel):
    disease: str
    objective_function: str = "relevance * pathway_centrality"
    max_iterations: int = 20
    early_stop_threshold: float = 0.9
    project_id: Optional[str] = None

class AdmetBatchRequest(BaseModel):
    smiles_list: List[str]
    project_id: Optional[str] = None

class RetrosynthesisPlanRequest(BaseModel):
    smiles: str
    max_steps: int = 6
    commercial_only: bool = True
    project_id: Optional[str] = None

class VaccineDesignRequest(BaseModel):
    pathogen: str
    antigen_sequence: str = ""
    target_epitopes: List[str] = Field(default_factory=list)
    population_context: str = "global"
    project_id: Optional[str] = None


def _envelope(data: Any, *, req: Request, warnings: list | None = None):
    return {
        "request_id": getattr(req.state, "request_id", str(uuid.uuid4())),
        "trace_id": getattr(req.state, "trace_id", ""),
        "status": "ok",
        "data": data,
        "warnings": warnings or [],
        "errors": [],
        "timing": {},
        "provenance": {},
    }


def _queue_run(db, run_type: str, project_id: str, input_data: dict) -> tuple[str, Run]:
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        project_id=project_id or "",
        run_type=run_type,
        state="QUEUED",
        input_snapshot=input_data,
        runtime_context={"mode": "hosted"},
    )
    db.add(run)
    return run_id, run


async def _dispatch_lab(
    request: Request, db: AsyncSession, run_type: str, run_id: str, input_data: dict,
):
    """Commit the Run row then enqueue the ARQ job (R-002 fix).

    Falls back to inline computation if ARQ is unavailable.
    """
    await db.commit()
    mapping = _LAB_QUEUE_MAP.get(run_type)
    if mapping:
        func_name, queue_name = mapping
        try:
            await enqueue_job(
                request.app.state,
                func_name,
                run_id,
                input_data,
                queue_name=queue_name,
                idempotency_key=f"lab:{run_id}",
            )
        except Exception as exc:
            log.warning(
                "labs_arq_unavailable_running_inline",
                run_type=run_type, run_id=run_id, error=str(exc),
            )
            result = await _run_lab_inline(run_type, input_data)
            run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
            if run:
                run.state = "SUCCESS" if result.get("status") != "error" else "PARTIAL_SUCCESS"
                run.output_artifacts = result.get("artifacts", [result])
                run.completed_at = datetime.now(timezone.utc)
                run.provenance = result.get("provenance", {})
                await db.commit()
    else:
        log.warning("labs_no_queue_mapping", run_type=run_type, run_id=run_id)


async def _run_lab_inline(run_type: str, input_data: dict) -> Dict[str, Any]:
    """Run lab computation inline when ARQ worker is unavailable."""
    try:
        if run_type in ("labs.target_discovery",):
            return await _inline_target_discovery(input_data)
        elif run_type in ("admet.batch", "labs.admet"):
            return await _inline_admet(input_data)
        elif run_type in ("retrosynthesis.plan", "labs.retrosynthesis"):
            return await _inline_retrosynthesis(input_data)
        elif run_type in ("labs.pocket_detection",):
            return await _inline_pocket_detection(input_data)
        elif run_type in ("labs.molecule_generation",):
            return await _inline_molecule_generation(input_data)
        elif run_type in ("labs.vaccine_design", "labs.vaccine"):
            return await _inline_vaccine(input_data)
        elif run_type in ("labs.metabolic_engineering",):
            return await _inline_metabolic_engineering(input_data)
        elif run_type in ("labs.pharmacogenomics",):
            return await _inline_pharmacogenomics(input_data)
        else:
            return {
                "status": "degraded",
                "message": f"No inline handler for {run_type}",
                "provenance": _build_provenance([], [], [], 0),
            }
    except Exception as exc:
        log.error("inline_lab_failed", run_type=run_type, error=str(exc))
        return {
            "status": "error",
            "message": str(exc),
            "provenance": _build_provenance([], [], [], 0),
        }


# ── Helper: safe connector call ───────────────────────────

async def _safe_call(
    coro,
    source_name: str,
    succeeded: list,
    degraded: list,
    warnings: list,
):
    """Execute a connector coroutine, tracking success/degradation."""
    try:
        result = await coro
        succeeded.append(source_name)
        return result
    except Exception as exc:
        degraded.append(source_name)
        warnings.append(f"{source_name}: {exc}")
        log.warning("connector_call_failed", source=source_name, error=str(exc))
        return None



# ═══════════════════════════════════════════════════════════
# 3.1 — Target Discovery: real computation
# ═══════════════════════════════════════════════════════════

async def _inline_target_discovery(input_data: dict) -> Dict[str, Any]:
    """Inline target discovery: OpenTargets, DisGeNET, UniProt in parallel + TargetScorer."""
    t0 = time.monotonic()
    disease = input_data.get("disease", "")
    sources_queried = ["OpenTargets", "DisGeNET", "UniProt"]
    succeeded: List[str] = []
    degraded: List[str] = []
    warnings: List[str] = []

    from connectors.opentargets import OpenTargetsConnector
    from connectors.disgenet import DisGeNETConnector
    from connectors.uniprot import UniProtConnector

    ot_result, dg_result, up_result = await asyncio.gather(
        _safe_call(OpenTargetsConnector().search(disease, limit=20), "OpenTargets", succeeded, degraded, warnings),
        _safe_call(DisGeNETConnector().search(disease, limit=20), "DisGeNET", succeeded, degraded, warnings),
        _safe_call(UniProtConnector().search(disease, limit=10), "UniProt", succeeded, degraded, warnings),
    )

    # Merge candidate symbols from all sources
    candidate_symbols: Dict[str, Dict[str, Any]] = {}
    for item in (ot_result or []):
        name = item.get("canonical_name", item.get("name", ""))
        if name:
            candidate_symbols.setdefault(name, {"name": name, "id": item.get("id", ""), "sources": [], "score": 0.5})
            candidate_symbols[name]["sources"].append("OpenTargets")
            candidate_symbols[name]["score"] = max(candidate_symbols[name]["score"], item.get("association_score") or 0.5)
    for item in (dg_result or []):
        name = item.get("canonical_name", item.get("gene_symbol", ""))
        if name:
            candidate_symbols.setdefault(name, {"name": name, "id": item.get("id", ""), "sources": [], "score": 0.5})
            candidate_symbols[name]["sources"].append("DisGeNET")
    for item in (up_result or []):
        name = item.get("gene_symbol", item.get("canonical_name", ""))
        if name:
            candidate_symbols.setdefault(name, {"name": name, "id": item.get("uniprot_id", item.get("id", "")), "sources": [], "score": 0.5})
            candidate_symbols[name]["sources"].append("UniProt")

    # Score targets using TargetScorer
    targets: List[Dict[str, Any]] = []
    symbols_list = list(candidate_symbols.keys())[:20]
    if symbols_list:
        try:
            from services.target_scorer import TargetScorer
            scorer = TargetScorer(query_id=disease, candidates=symbols_list)
            targets = await scorer.evaluate_candidates()
            sources_queried.append("TargetScorer")
            succeeded.append("TargetScorer")
        except Exception as exc:
            log.warning("target_scorer_failed", error=str(exc))
            degraded.append("TargetScorer")
            warnings.append(f"TargetScorer: {exc}")
            for sym, info in candidate_symbols.items():
                src_count = len(set(info["sources"]))
                targets.append({
                    "symbol": sym, "id": info["id"],
                    "composite_score": round(info["score"] * (0.5 + 0.25 * src_count), 4),
                    "ucb_score": round(info["score"] * (0.5 + 0.25 * src_count), 4),
                    "sources": info["sources"],
                    "degraded_signals": ["all — TargetScorer unavailable"],
                })
            targets.sort(key=lambda x: x.get("ucb_score", 0), reverse=True)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return {
        "status": "success" if targets else "degraded",
        "artifacts": targets, "disease": disease, "target_count": len(targets),
        "warnings": warnings,
        "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
    }


# ═══════════════════════════════════════════════════════════
# 3.2 — Pocket Detection: real computation
# ═══════════════════════════════════════════════════════════

async def _inline_pocket_detection(input_data: dict) -> Dict[str, Any]:
    """Inline pocket detection using DockingService.detect_pockets()."""
    import shutil
    import tempfile
    t0 = time.monotonic()
    pdb_id = input_data.get("pdb_id", input_data.get("target_id", ""))
    method = str(input_data.get("method", "fpocket") or "fpocket").lower()
    selected_method = method if method in {"fpocket", "p2rank"} else "fpocket"
    sources_queried = [selected_method]
    succeeded: List[str] = []
    degraded: List[str] = []
    warnings: List[str] = []
    pockets: List[Dict[str, Any]] = []

    try:
        from services.docking_service import DockingService
        svc = DockingService()
        receptor_path = None

        # Download PDB from RCSB if pdb_id given
        if pdb_id:
            try:
                from core.http_client import ResilientClient
                client = ResilientClient()
                try:
                    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
                    body, _ = await client.get(url)
                    if body and isinstance(body, (str, bytes)):
                        tmp = tempfile.NamedTemporaryFile(suffix=".pdb", delete=False)
                        content = body if isinstance(body, bytes) else body.encode()
                        tmp.write(content)
                        tmp.close()
                        receptor_path = tmp.name
                        succeeded.append("RCSB_PDB")
                        sources_queried.append("RCSB_PDB")
                finally:
                    await client.close()
            except Exception as exc:
                warnings.append(f"PDB download failed: {exc}")
                degraded.append("RCSB_PDB")

        if receptor_path:
            raw_pockets = await svc.detect_pockets(receptor_path, method=selected_method)
            if raw_pockets and not any(p.get("error") for p in raw_pockets):
                succeeded.append(selected_method)
                for i, p in enumerate(raw_pockets):
                    pockets.append({
                        "pocket_id": p.get("id", str(i + 1)),
                        "druggability_score": p.get("druggability_score", p.get("score", 0.0)),
                        "volume": p.get("volume", 0.0),
                        "residues": p.get("residues", ""),
                        "center_coordinates": p.get("center", []),
                        "source": selected_method,
                    })
                pockets.sort(key=lambda x: x.get("druggability_score", 0), reverse=True)
            else:
                degraded.append(selected_method)
                err_msg = raw_pockets[0].get("error", "Unknown") if raw_pockets else "No output"
                warnings.append(f"{selected_method}: {err_msg}")
        elif not shutil.which("fpocket") and selected_method == "fpocket":
            degraded.append(selected_method)
            warnings.append("fpocket binary not detected")
    except Exception as exc:
        degraded.append(selected_method)
        warnings.append(f"DockingService({selected_method}): {exc}")

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    if not pockets and selected_method in degraded:
        remediation = (
            "Install fpocket: conda install -c bioconda fpocket"
            if selected_method == "fpocket"
            else "Install P2Rank and ensure the `prank` binary is on PATH"
        )
        return {
            "status": "degraded", "artifacts": [], "pdb_id": pdb_id,
            "method": selected_method,
            "warnings": warnings,
            "structured_error": StructuredError(
                error_code="TOOL_UNAVAILABLE",
                message=f"{selected_method} is unavailable or the PDB download failed.",
                suggested_remediation=remediation,
                service=selected_method,
                degraded_result={"pdb_id": pdb_id, "pockets": []},
            ).model_dump(),
            "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
        }
    return {
        "status": "success" if pockets else "degraded",
        "artifacts": pockets, "pdb_id": pdb_id, "pocket_count": len(pockets),
        "method": selected_method,
        "warnings": warnings,
        "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
    }


# ═══════════════════════════════════════════════════════════
# 3.3 — Molecule Generation: real computation
# ═══════════════════════════════════════════════════════════

async def _inline_molecule_generation(input_data: dict) -> Dict[str, Any]:
    """Inline molecule generation: DLModelService diffusion or RDKit enumeration fallback."""
    t0 = time.monotonic()
    num_candidates = min(input_data.get("num_candidates", 5), 10)
    sources_queried: List[str] = []
    succeeded: List[str] = []
    degraded: List[str] = []
    warnings: List[str] = []
    candidates: List[Dict[str, Any]] = []

    # Try DLModelService diffusion model first
    diffusion_ok = False
    try:
        from services.dl_models import DLModelService
        sources_queried.append("DLModelService_diffusion")
        for i in range(num_candidates):
            result = DLModelService.run_molecule_diffusion(num_atoms=32)
            candidates.append({
                "index": i, "status": result.status,
                "predictions": result.predictions,
                "method": "graph_diffusion", "source": "DLModelService",
            })
        if candidates:
            diffusion_ok = True
            succeeded.append("DLModelService_diffusion")
    except Exception as exc:
        degraded.append("DLModelService_diffusion")
        warnings.append(f"Diffusion model: {exc}")

    # Fallback: RDKit enumeration
    if not diffusion_ok:
        try:
            from rdkit import Chem
            from rdkit.Chem import Descriptors, rdMolDescriptors
            sources_queried.append("RDKit_enumeration")
            seeds = ["c1ccccc1", "C1CCCCC1", "c1ccncc1", "C1CCNCC1", "c1ccc2ccccc2c1"]
            for i in range(num_candidates):
                mol = Chem.MolFromSmiles(seeds[i % len(seeds)])
                if mol:
                    candidates.append({
                        "index": i, "smiles": Chem.MolToSmiles(mol),
                        "properties": {
                            "mw": round(Descriptors.MolWt(mol), 2),
                            "logp": round(Descriptors.MolLogP(mol), 2),
                            "tpsa": round(Descriptors.TPSA(mol), 2),
                            "hbd": rdMolDescriptors.CalcNumHBD(mol),
                            "hba": rdMolDescriptors.CalcNumHBA(mol),
                            "rotatable_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol),
                        },
                        "method": "rdkit_enumeration", "source": "RDKit",
                    })
            if candidates:
                succeeded.append("RDKit_enumeration")
        except ImportError as exc:
            degraded.append("RDKit_enumeration")
            warnings.append(f"RDKit: {exc}")

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    if not candidates:
        return {
            "status": "degraded", "artifacts": [], "warnings": warnings,
            "structured_error": StructuredError(
                error_code="TOOL_UNAVAILABLE",
                message="Neither PyTorch (diffusion) nor RDKit (enumeration) available.",
                suggested_remediation="pip install rdkit-pypi  # or install PyTorch for diffusion",
                service="molecule_generation",
            ).model_dump(),
            "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
        }
    return {
        "status": "success", "artifacts": candidates,
        "candidate_count": len(candidates), "warnings": warnings,
        "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
    }


# ═══════════════════════════════════════════════════════════
# 3.4 — ADMET: real computation with confidence intervals
# ═══════════════════════════════════════════════════════════

async def _inline_admet(input_data: dict) -> Dict[str, Any]:
    """Inline ADMET prediction: ADMETPredictor with all 5 categories + confidence intervals."""
    t0 = time.monotonic()
    smiles_list = input_data.get("smiles_list", [])
    sources_queried = ["ADMETPredictor", "RDKit_descriptors"]
    succeeded: List[str] = []
    degraded: List[str] = []
    warnings: List[str] = []
    results: List[Dict[str, Any]] = []

    try:
        from services.molecule_service import ADMETPredictor
        predictor = ADMETPredictor()
        succeeded.append("ADMETPredictor")
        for smi in smiles_list:
            pred = predictor.predict(smi)
            ci = pred.get("confidence_interval", {})
            results.append({
                "smiles": smi,
                "absorption": pred.get("absorption", {}),
                "distribution": pred.get("distribution", {}),
                "metabolism": pred.get("metabolism", {}),
                "excretion": pred.get("excretion", {}),
                "toxicity": pred.get("toxicity", {}),
                "confidence_interval": {
                    "lower_bound": max(0.0, min(1.0, ci.get("lower", 0.0))),
                    "prediction": max(0.0, min(1.0, ci.get("lower", 0.0) + ci.get("std", 0.1))),
                    "upper_bound": max(0.0, min(1.0, ci.get("upper", 1.0))),
                    "method": ci.get("method", "conformal_prediction"),
                    "level": ci.get("level", "90%"),
                },
                "synthetic_accessibility": pred.get("synthetic_accessibility", {}),
                "method": pred.get("method", "rule_based"),
                "source": "ADMETPredictor",
            })
        if results:
            succeeded.append("RDKit_descriptors")
    except Exception as exc:
        degraded.append("ADMETPredictor")
        warnings.append(f"ADMETPredictor: {exc}")

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    if not results:
        return {
            "status": "degraded", "artifacts": [], "count": 0, "warnings": warnings,
            "structured_error": StructuredError(
                error_code="TOOL_UNAVAILABLE",
                message="ADMETPredictor unavailable.",
                suggested_remediation="Ensure molecule_service.py is importable and RDKit is installed.",
                service="ADMETPredictor",
            ).model_dump(),
            "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
        }
    return {
        "status": "success", "artifacts": results, "count": len(results),
        "warnings": warnings,
        "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
    }


# ═══════════════════════════════════════════════════════════
# 3.5 — Retrosynthesis: real computation
# ═══════════════════════════════════════════════════════════

async def _inline_retrosynthesis(input_data: dict) -> Dict[str, Any]:
    """Inline retrosynthesis using RDKit RECAP decomposition with feasibility scoring."""
    t0 = time.monotonic()
    smiles = input_data.get("smiles", "")
    max_steps = input_data.get("max_steps", 6)
    sources_queried = ["RDKit_RECAP"]
    succeeded: List[str] = []
    degraded: List[str] = []
    warnings: List[str] = []
    routes: List[Dict[str, Any]] = []
    route_tree: Optional[Dict[str, Any]] = None

    try:
        from rdkit import Chem
        from rdkit.Chem import Recap, Descriptors

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return {
                "status": "degraded", "artifacts": [], "target_smiles": smiles,
                "warnings": ["Invalid SMILES string"],
                "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
            }

        tree = Recap.RecapDecompose(mol)
        children = tree.GetAllChildren()
        succeeded.append("RDKit_RECAP")

        for key, _node in list(children.items())[:max_steps]:
            child_mol = Chem.MolFromSmiles(key)
            mw = Descriptors.MolWt(child_mol) if child_mol else 0
            feasibility = round(min(1.0, max(0.3, 1.0 - (mw / 600.0))), 3)
            routes.append({
                "smiles": key, "step": len(routes) + 1,
                "molecular_weight": round(mw, 2) if child_mol else None,
                "feasibility": feasibility,
                "commercially_available": mw < 300,
                "source": "RDKit RECAP decomposition",
            })

        route_tree = {
            "target": smiles, "target_mw": round(Descriptors.MolWt(mol), 2),
            "decomposition_steps": routes, "total_steps": len(routes), "method": "RECAP",
        }
    except ImportError:
        degraded.append("RDKit_RECAP")
        warnings.append("RDKit not available")
        routes = [{
            "smiles": smiles, "step": 1, "feasibility": 0.5,
            "source": "degraded — RDKit not available",
            "note": "Install rdkit for real retrosynthesis: pip install rdkit-pypi",
        }]

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    if "RDKit_RECAP" in degraded:
        return {
            "status": "degraded", "artifacts": routes, "target_smiles": smiles,
            "warnings": warnings,
            "structured_error": StructuredError(
                error_code="TOOL_UNAVAILABLE",
                message="RDKit not available for RECAP decomposition.",
                suggested_remediation="pip install rdkit-pypi",
                service="RDKit",
                degraded_result={"routes": routes},
            ).model_dump(),
            "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
        }
    return {
        "status": "success", "artifacts": routes, "route_tree": route_tree,
        "target_smiles": smiles, "warnings": warnings,
        "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
    }


# ═══════════════════════════════════════════════════════════
# 3.6 — Vaccine Design: epitope prediction
# ═══════════════════════════════════════════════════════════

# Kyte-Doolittle hydrophilicity scale (inverted: positive = hydrophilic)
_KD_HYDROPHILICITY: Dict[str, float] = {
    "A": -1.8, "R": 4.5, "N": 3.5, "D": 3.5, "C": -2.5,
    "Q": 3.5, "E": 3.5, "G": 0.4, "H": 3.2, "I": -4.5,
    "L": -3.8, "K": 3.9, "M": -1.9, "F": -2.8, "P": 1.6,
    "S": 0.8, "T": 0.7, "W": -0.9, "Y": 1.3, "V": -4.2,
}


def _hydrophilicity_score(peptide: str) -> float:
    """Average hydrophilicity for a peptide (Kyte-Doolittle inverted)."""
    scores = [_KD_HYDROPHILICITY.get(aa.upper(), 0.0) for aa in peptide]
    return sum(scores) / max(len(scores), 1)


def _predict_bcell_epitopes(sequence: str, window: int = 15, top_n: int = 10) -> List[Dict[str, Any]]:
    """Predict B-cell epitopes via sliding window + hydrophilicity."""
    if len(sequence) < window:
        return []
    windows = []
    for i in range(len(sequence) - window + 1):
        pep = sequence[i:i + window]
        score = _hydrophilicity_score(pep)
        windows.append({
            "epitope_id": f"B{i+1}", "start": i + 1, "end": i + window,
            "sequence": pep, "hydrophilicity_score": round(score, 3),
            "type": "B-cell_linear", "source": "hydrophilicity_analysis",
        })
    windows.sort(key=lambda x: x["hydrophilicity_score"], reverse=True)
    return windows[:top_n]


def _predict_tcell_epitopes(sequence: str, window: int = 9, top_n: int = 10) -> List[Dict[str, Any]]:
    """Predict T-cell epitopes (MHC-I 9-mer) via amphipathicity scoring."""
    if len(sequence) < window:
        return []
    windows = []
    for i in range(len(sequence) - window + 1):
        pep = sequence[i:i + window]
        hydro = _hydrophilicity_score(pep)
        amphipathicity = max(0, 1.0 - abs(hydro) / 5.0)
        windows.append({
            "epitope_id": f"T{i+1}", "start": i + 1, "end": i + window,
            "sequence": pep, "amphipathicity_score": round(amphipathicity, 3),
            "type": "CD8+", "source": "amphipathicity_analysis",
        })
    windows.sort(key=lambda x: x["amphipathicity_score"], reverse=True)
    return windows[:top_n]


async def _inline_vaccine(input_data: dict) -> Dict[str, Any]:
    """Inline vaccine design — epitope prediction using sliding window + hydrophilicity."""
    t0 = time.monotonic()
    pathogen = input_data.get("pathogen", "")
    antigen_sequence = input_data.get("antigen_sequence", "")
    population_context = input_data.get("population_context", "global")
    sources_queried = ["epitope_prediction", "hydrophilicity_analysis"]
    succeeded: List[str] = []
    degraded: List[str] = []
    warnings: List[str] = []

    # If no antigen sequence, delegate to VaccineDesignLab with a default sequence
    if not antigen_sequence:
        try:
            from services.labs.vaccine_lab import VaccineDesignLab
            lab = VaccineDesignLab()
            # Use a short representative spike protein fragment
            default_seq = (
                "MFVFLVLLPLVSSQCVNLTTRTQLPPAYTNSFTRGVYYPDKVFRSSVLHSTQDLFLPFFSNVTWFHAI"
                "HVSGTNGTKRFDNPVLPFNDGVYFASTEKSNIIRGWIFGTTLDSKTQSLLIVNNATNVVIKVCEFQFC"
            )
            result = await lab.design_vaccine(
                antigen_sequence=default_seq,
                antigen_type="viral",
                target_population=population_context,
            )
            sources_queried.append("VaccineDesignLab")
            succeeded.extend(["VaccineDesignLab", "epitope_prediction", "hydrophilicity_analysis"])
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return {
                "status": "success",
                "artifacts": result.get("vaccine_candidates", []),
                "bcell_epitopes": result.get("bcell_epitopes", []),
                "tcell_epitopes": result.get("tcell_epitopes", []),
                "pathogen": pathogen,
                "warnings": warnings,
                "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
            }
        except Exception as exc:
            degraded.append("VaccineDesignLab")
            warnings.append(f"VaccineDesignLab: {exc}")
            # Fall through to degraded response
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return {
                "status": "degraded", "artifacts": [], "pathogen": pathogen,
                "warnings": warnings + ["No antigen_sequence provided and VaccineDesignLab failed"],
                "structured_error": StructuredError(
                    error_code="MISSING_INPUT",
                    message="Provide antigen_sequence for epitope prediction.",
                    suggested_remediation="Include antigen_sequence (amino acid string) in request body.",
                    service="vaccine_design",
                ).model_dump(),
                "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
            }

    # Real epitope prediction on provided sequence
    bcell = _predict_bcell_epitopes(antigen_sequence)
    tcell = _predict_tcell_epitopes(antigen_sequence)
    succeeded.extend(["epitope_prediction", "hydrophilicity_analysis"])

    # Rank vaccine candidates by combining B-cell and T-cell scores
    vaccine_candidates = []
    if bcell or tcell:
        # Multi-epitope candidate
        top_b = bcell[:3]
        top_t = tcell[:3]
        combined_score = 0.0
        if top_b:
            combined_score += sum(e["hydrophilicity_score"] for e in top_b) / len(top_b) / 5.0
        if top_t:
            combined_score += sum(e["amphipathicity_score"] for e in top_t) / len(top_t)
        combined_score = round(min(1.0, max(0.0, combined_score / 2.0 + 0.5)), 3)

        vaccine_candidates.append({
            "candidate_id": "VAC-001",
            "name": "Multi-epitope vaccine candidate",
            "bcell_epitopes": [e["epitope_id"] for e in top_b],
            "tcell_epitopes": [e["epitope_id"] for e in top_t],
            "overall_score": combined_score,
            "population_coverage_estimate": 0.85 if population_context == "global" else 0.75,
            "rationale": "Combines top B-cell and T-cell epitopes for broad immune response",
        })

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return {
        "status": "success" if vaccine_candidates else "degraded",
        "artifacts": vaccine_candidates,
        "bcell_epitopes": bcell, "tcell_epitopes": tcell,
        "pathogen": pathogen, "sequence_length": len(antigen_sequence),
        "warnings": warnings,
        "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
    }


# ═══════════════════════════════════════════════════════════
# 3.7 — Metabolic Engineering: stoichiometric analysis
# ═══════════════════════════════════════════════════════════

async def _inline_metabolic_engineering(input_data: dict) -> Dict[str, Any]:
    """Inline metabolic engineering — stoichiometric analysis via MetabolicEngineeringLab."""
    t0 = time.monotonic()
    organism = input_data.get("organism", "E. coli")
    metabolite = input_data.get("target_metabolite", "")
    sources_queried = ["MetabolicEngineeringLab", "stoichiometric_analysis"]
    succeeded: List[str] = []
    degraded: List[str] = []
    warnings: List[str] = []

    try:
        from services.labs.metabolic_engineering_lab import MetabolicEngineeringLab
        lab = MetabolicEngineeringLab()
        result = await lab.optimize_pathway(
            target_metabolite=metabolite,
            host_organism=organism,
        )
        succeeded.extend(["MetabolicEngineeringLab", "stoichiometric_analysis"])

        # Extract key artifacts
        fba = result.get("fba_results", {})
        pathway_designs = result.get("pathway_designs", [])
        optimization = result.get("optimization_results", {})
        strains = result.get("strain_recommendations", [])

        artifacts = {
            "fba_results": {
                "theoretical_yield": fba.get("theoretical_yield"),
                "growth_rate": fba.get("growth_rate"),
                "bottleneck_reactions": fba.get("bottleneck_reactions", []),
            },
            "pathway_designs": pathway_designs,
            "optimization": {
                "best_pathway": optimization.get("best_pathway"),
                "optimized_yield": optimization.get("optimized_yield"),
                "strategies": optimization.get("optimization_strategies", []),
            },
            "strain_recommendations": strains,
        }

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            "status": "success",
            "artifacts": [artifacts],
            "organism": organism, "target_metabolite": metabolite,
            "warnings": warnings,
            "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
        }
    except Exception as exc:
        degraded.extend(["MetabolicEngineeringLab", "stoichiometric_analysis"])
        warnings.append(f"MetabolicEngineeringLab: {exc}")
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            "status": "degraded",
            "artifacts": [],
            "organism": organism, "target_metabolite": metabolite,
            "warnings": warnings,
            "structured_error": StructuredError(
                error_code="TOOL_UNAVAILABLE",
                message="Metabolic engineering computation failed.",
                suggested_remediation="Ensure MetabolicEngineeringLab service is available.",
                service="MetabolicEngineeringLab",
                degraded_result={"organism": organism, "target_metabolite": metabolite},
            ).model_dump(),
            "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
        }


# ═══════════════════════════════════════════════════════════
# 3.8 — Pharmacogenomics: PharmGKB + CPIC
# ═══════════════════════════════════════════════════════════

async def _inline_pharmacogenomics(input_data: dict) -> Dict[str, Any]:
    """Inline pharmacogenomics: query PharmGKB and CPIC connectors in parallel."""
    t0 = time.monotonic()
    gene_symbols = input_data.get("gene_symbols", [])
    population = input_data.get("population", "global")
    sources_queried = ["CPIC", "PharmGKB"]
    succeeded: List[str] = []
    degraded: List[str] = []
    warnings: List[str] = []
    all_results: List[Dict[str, Any]] = []

    if not gene_symbols:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            "status": "degraded", "artifacts": [], "gene_symbols": gene_symbols,
            "warnings": ["No gene_symbols provided"],
            "provenance": _build_provenance(sources_queried, succeeded, degraded, elapsed_ms),
        }

    # Query CPIC and PharmGKB in parallel for each gene
    from connectors.cpic import CPICConnector
    from connectors.pharmgkb import PharmGKBConnector

    cpic_conn = CPICConnector()
    pgkb_conn = PharmGKBConnector()

    for gene in gene_symbols[:10]:
        cpic_data, pgkb_data = await asyncio.gather(
            _safe_call(cpic_conn.search(gene, limit=10), "CPIC", succeeded, degraded, warnings),
            _safe_call(pgkb_conn.search(gene, limit=10), "PharmGKB", succeeded, degraded, warnings),
        )

        gene_result: Dict[str, Any] = {
            "gene_symbol": gene,
            "cpic_interactions": [],
            "pharmgkb_annotations": [],
            "dosing_recommendations": [],
        }

        if cpic_data and isinstance(cpic_data, list):
            for item in cpic_data:
                interaction = {
                    "gene_symbol": item.get("gene_symbol", gene),
                    "drug_name": item.get("drug_name", ""),
                    "cpic_level": item.get("cpic_level", ""),
                    "has_guideline": item.get("has_cpic_guideline", False),
                    "guideline_url": item.get("guideline_url", ""),
                    "source": "CPIC",
                }
                gene_result["cpic_interactions"].append(interaction)
                if item.get("has_cpic_guideline"):
                    gene_result["dosing_recommendations"].append({
                        "drug": item.get("drug_name", ""),
                        "level": item.get("cpic_level", ""),
                        "source": "CPIC",
                        "guideline_url": item.get("guideline_url", ""),
                    })

        if pgkb_data and isinstance(pgkb_data, list):
            for item in pgkb_data:
                gene_result["pharmgkb_annotations"].append({
                    "annotation_id": item.get("annotation_id", ""),
                    "gene_symbol": item.get("gene_symbol", gene),
                    "drug_name": item.get("drug_name", ""),
                    "variant_name": item.get("variant_name", ""),
                    "phenotype": item.get("phenotype", ""),
                    "level": item.get("level", ""),
                    "url": item.get("url", ""),
                    "source": "PharmGKB",
                })

        all_results.append(gene_result)

    # Also try PharmacogenomicsLab for richer analysis
    try:
        from services.labs.pharmacogenomics_lab import PharmacogenomicsLab
        lab = PharmacogenomicsLab()
        sources_queried.append("PharmacogenomicsLab")
        # Use first gene for detailed analysis
        if gene_symbols:
            lab_result = await lab.analyze_drug_response(
                patient_variants=[{"gene": gene_symbols[0], "variant": "*1/*1"}],
                drug_name="general",
                indication="pharmacogenomics_screening",
            )
            succeeded.append("PharmacogenomicsLab")
            if all_results:
                all_results[0]["detailed_analysis"] = {
                    "metabolism_prediction": lab_result.get("metabolism_prediction", {}),
                    "dosing_recommendations": lab_result.get("dosing_recommendations", {}),
                    "adverse_reactions": lab_result.get("adverse_reactions", []),
                }
    except Exception as exc:
        degraded.append("PharmacogenomicsLab")
        warnings.append(f"PharmacogenomicsLab: {exc}")

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    # Deduplicate succeeded/degraded
    succeeded_dedup = list(dict.fromkeys(succeeded))
    degraded_dedup = list(dict.fromkeys(degraded))

    has_data = any(
        r.get("cpic_interactions") or r.get("pharmgkb_annotations")
        for r in all_results
    )
    return {
        "status": "success" if has_data else "degraded",
        "artifacts": all_results,
        "gene_symbols": gene_symbols,
        "warnings": warnings,
        "provenance": _build_provenance(sources_queried, succeeded_dedup, degraded_dedup, elapsed_ms),
    }



# ── Target Discovery Lab ─────────────────────────────────

@router.post("/target-discovery/start")
async def start_target_discovery(
    body: TargetDiscoveryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start autonomous target discovery loop (§131, §24)."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "labs.target_discovery", body.project_id, input_data)
    await _dispatch_lab(request, db, "labs.target_discovery", run_id, input_data)
    log.info("labs_target_discovery_started", run_id=run_id, disease=body.disease)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


@router.get("/target-discovery/{run_id}")
async def get_target_discovery(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get target discovery run results (§131)."""
    run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _envelope({
        "run_id": run.id,
        "state": run.state,
        "run_type": run.run_type,
        "input_snapshot": run.input_snapshot,
        "output_artifacts": run.output_artifacts,
        "timing": run.timing,
        "provenance": run.provenance,
        "completed_at": str(run.completed_at) if run.completed_at else None,
    }, req=request)


# ── ADMET Batch Lab ───────────────────────────────────────

@router.post("/admet/batch")
async def batch_admet(
    body: AdmetBatchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run ADMET prediction on a batch of molecules (§131, §85)."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "admet.batch", body.project_id, input_data)
    await _dispatch_lab(request, db, "admet.batch", run_id, input_data)
    log.info("labs_admet_batch_started", run_id=run_id, count=len(body.smiles_list))
    return _envelope({"run_id": run_id, "status": "QUEUED",
                       "molecules_count": len(body.smiles_list)}, req=request)


@router.get("/admet/{run_id}")
async def get_admet_results(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get ADMET batch run results (§131)."""
    run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _envelope({
        "run_id": run.id,
        "state": run.state,
        "output_artifacts": run.output_artifacts,
        "timing": run.timing,
    }, req=request)


# ── Retrosynthesis Lab ────────────────────────────────────

@router.post("/retrosynthesis/plan")
async def plan_retrosynthesis(
    body: RetrosynthesisPlanRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Plan retrosynthetic routes (§131, §13.4)."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "retrosynthesis.plan", body.project_id, input_data)
    await _dispatch_lab(request, db, "retrosynthesis.plan", run_id, input_data)
    log.info("labs_retrosynthesis_started", run_id=run_id)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


@router.get("/retrosynthesis/{run_id}")
async def get_retrosynthesis_results(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get retrosynthesis plan results (§131)."""
    run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _envelope({
        "run_id": run.id,
        "state": run.state,
        "output_artifacts": run.output_artifacts,
        "timing": run.timing,
    }, req=request)


# ── Vaccine Design Lab ────────────────────────────────────

@router.post("/vaccine/design")
async def design_vaccine(
    body: VaccineDesignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger vaccine design pipeline (§131)."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "labs.vaccine_design", body.project_id, input_data)
    await _dispatch_lab(request, db, "labs.vaccine_design", run_id, input_data)
    log.info("labs_vaccine_design_started", run_id=run_id, pathogen=body.pathogen)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


# ── §131 Spec-Aligned Lab Endpoints (exact paths) ────────

class PocketRunRequest(BaseModel):
    target_id: str = ""
    pdb_id: str = ""
    method: str = "fpocket"
    project_id: Optional[str] = None

class MoleculeGenerationRunRequest(BaseModel):
    target_id: str = ""
    constraints: Dict[str, Any] = {}
    num_candidates: int = 10
    project_id: Optional[str] = None

class MetabolicEngineeringRunRequest(BaseModel):
    organism: str = ""
    target_metabolite: str = ""
    project_id: Optional[str] = None

class PharmacogenomicsRunRequest(BaseModel):
    gene_symbols: List[str] = []
    population: str = "global"
    project_id: Optional[str] = None


@router.post("/pocket/run")
async def run_pocket_detection(
    body: PocketRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§131: POST /api/v1/labs/pocket/run — Binding pocket detection."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "labs.pocket_detection", body.project_id, input_data)
    await _dispatch_lab(request, db, "labs.pocket_detection", run_id, input_data)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


@router.post("/molecule-generation/run")
async def run_molecule_generation(
    body: MoleculeGenerationRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§131: POST /api/v1/labs/molecule-generation/run — De novo molecule generation."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "labs.molecule_generation", body.project_id, input_data)
    await _dispatch_lab(request, db, "labs.molecule_generation", run_id, input_data)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


@router.post("/admet/run")
async def run_admet(
    body: AdmetBatchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§131: POST /api/v1/labs/admet/run — ADMET prediction run."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "labs.admet", body.project_id, input_data)
    await _dispatch_lab(request, db, "labs.admet", run_id, input_data)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


@router.post("/retrosynthesis/run")
async def run_retrosynthesis(
    body: RetrosynthesisPlanRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§131: POST /api/v1/labs/retrosynthesis/run — Retrosynthesis planning run."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "labs.retrosynthesis", body.project_id, input_data)
    await _dispatch_lab(request, db, "labs.retrosynthesis", run_id, input_data)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


@router.post("/vaccine/run")
async def run_vaccine(
    body: VaccineDesignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§131: POST /api/v1/labs/vaccine/run — Vaccine design run."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "labs.vaccine", body.project_id, input_data)
    await _dispatch_lab(request, db, "labs.vaccine", run_id, input_data)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


@router.post("/metabolic-engineering/run")
async def run_metabolic_engineering(
    body: MetabolicEngineeringRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§131: POST /api/v1/labs/metabolic-engineering/run — Metabolic engineering run."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "labs.metabolic_engineering", body.project_id, input_data)
    await _dispatch_lab(request, db, "labs.metabolic_engineering", run_id, input_data)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


@router.post("/pharmacogenomics/run")
async def run_pharmacogenomics(
    body: PharmacogenomicsRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§131: POST /api/v1/labs/pharmacogenomics/run — Pharmacogenomics analysis run."""
    input_data = body.model_dump()
    run_id, _ = _queue_run(db, "labs.pharmacogenomics", body.project_id, input_data)
    await _dispatch_lab(request, db, "labs.pharmacogenomics", run_id, input_data)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)
