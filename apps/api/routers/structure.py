"""Structure workbench API routes — RCSB-grade depth."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel

from services.structure_service import StructureService

router = APIRouter(prefix="/api/structure", tags=["structure"])

_svc = StructureService()


@router.get("/search")
async def search_structures(q: str = Query(...), limit: int = Query(25, le=100)) -> Dict[str, Any]:
    """Search RCSB PDB by text (protein name, disease, ligand, PDB ID)."""
    result = await _svc.search_structures(q, limit)
    return result


@router.get("/{pdb_id}")
async def get_structure(pdb_id: str) -> Dict[str, Any]:
    """Full structure summary: classification, organism, method, R-factors, assemblies, chains, ligands, downloads."""
    summary = await _svc.get_structure_summary(pdb_id)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@router.get("/{pdb_id}/annotations")
async def get_annotations(pdb_id: str) -> Dict[str, Any]:
    """Annotations: Pfam, InterPro, GO terms, EC numbers, PTMs."""
    return await _svc.get_annotations(pdb_id)


@router.get("/{pdb_id}/experiment")
async def get_experiment(pdb_id: str) -> Dict[str, Any]:
    """Experiment details: data collection, refinement, crystal parameters, software."""
    return await _svc.get_experiment(pdb_id)


@router.get("/{pdb_id}/sequence")
async def get_sequences(pdb_id: str) -> List[Dict[str, Any]]:
    """Per-chain sequences with feature tracks."""
    return await _svc.get_sequences(pdb_id)


@router.get("/alphafold/{uniprot_id}")
async def get_alphafold(uniprot_id: str) -> Dict[str, Any]:
    """AlphaFold predicted structure by UniProt ID."""
    result = await _svc.get_alphafold(uniprot_id)
    if not result:
        raise HTTPException(status_code=404, detail="AlphaFold prediction not found for %s" % uniprot_id)
    return result

class DockingRequest(BaseModel):
    protein_pdb: str
    ligand_smiles: str

@router.post("/mirofish_dock")
async def mirofish_docking(req: DockingRequest) -> Dict[str, Any]:
    """Execute combinatorial docking strictly matching 666ghj/MiroFish logical mapping."""
    from services.structure.mirofish_pipeline import MiroFishDockingOrchestrator
    orchestrator = MiroFishDockingOrchestrator()
    mol = orchestrator.parse_smiles_to_mol(req.ligand_smiles)
    res = orchestrator.execute_blind_docking(req.protein_pdb, mol)
    return res

class SequenceRequest(BaseModel):
    sequence: str

@router.post("/ssd_evaluate")
async def evaluate_sequence_ssd(req: SequenceRequest) -> Dict[str, Any]:
    """Execute state-space sequence modeling strictly matching tanishqkumar/ssd logic."""
    from services.models.ssd_state_space import StateSpaceSequenceModel
    ssd = StateSpaceSequenceModel()
    return ssd.process_protein_sequence(req.sequence)
