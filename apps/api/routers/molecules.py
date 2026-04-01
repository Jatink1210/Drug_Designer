"""Molecule Design Studio API routes."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.molecule_service import (
    compute_physichem_rdkit, ADMETPredictor, AnalogGenerator,
    NoveltyValidator, IterationManager,
)

router = APIRouter(prefix="/api/molecules", tags=["molecules"])

_admet = ADMETPredictor()
_analogs = AnalogGenerator()
_novelty = NoveltyValidator()
_iterations = IterationManager()


class ScoreRequest(BaseModel):
    smiles: List[str]


class AnalogRequest(BaseModel):
    smiles: str
    method: str = "similarity"
    num_analogs: int = 10


class NoveltyRequest(BaseModel):
    smiles: str


class IterationSaveRequest(BaseModel):
    target: str
    smiles: List[str]
    scores: List[Dict[str, Any]] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


@router.post("/score")
async def score_molecules(req: ScoreRequest) -> List[Dict[str, Any]]:
    """Compute physicochemical properties for a list of SMILES."""
    return [compute_physichem_rdkit(s) for s in req.smiles]


@router.post("/admet")
async def predict_admet(req: ScoreRequest) -> List[Dict[str, Any]]:
    """Predict ADMET properties for a list of SMILES."""
    return [_admet.predict(s) for s in req.smiles]


@router.post("/analogs")
async def generate_analogs(req: AnalogRequest) -> Dict[str, Any]:
    """Generate molecular analogs via similarity search or scaffold hopping."""
    analogs = await _analogs.generate_analogs(req.smiles, req.method, req.num_analogs)
    return {"query_smiles": req.smiles, "method": req.method, "analogs": analogs}


@router.post("/novelty")
async def check_novelty(req: NoveltyRequest) -> Dict[str, Any]:
    """Check novelty of a molecule against publications and patents."""
    return await _novelty.check_novelty(req.smiles)


@router.get("/iterations")
async def list_iterations() -> List[Dict[str, Any]]:
    """List saved design iterations."""
    return _iterations.list_iterations()


@router.get("/iterations/{iteration_id}")
async def get_iteration(iteration_id: str) -> Dict[str, Any]:
    """Get a saved design iteration."""
    result = _iterations.get_iteration(iteration_id)
    if not result:
        raise HTTPException(status_code=404, detail="Iteration not found")
    return result


@router.post("/iterations")
async def save_iteration(req: IterationSaveRequest) -> Dict[str, Any]:
    """Save a design iteration with reproducibility bundle."""
    iteration_id = _iterations.save_iteration(req.target, req.smiles, req.scores, req.parameters)
    return {"iteration_id": iteration_id, "status": "saved"}
