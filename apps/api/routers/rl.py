"""Reinforcement Learning (RL) API Routes."""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request
from models.envelope import build_envelope
from routers.auth import get_current_user

from services.rl_optimizer import RLService, RLStatusResult, OptimizationConstraints

router = APIRouter(prefix="/api/v1/rl", tags=["Reinforcement Learning"], dependencies=[Depends(get_current_user)])

@router.get("/status")
async def rl_infrastructure_status(request: Request) -> Dict[str, Any]:
    """Returns readiness status of RL subsystems (molecule optimization, retrosynthesis, ontology design)."""
    return build_envelope(request, RLService.get_status())

class GenerationRequest(OptimizationConstraints):
    base_smiles: str

@router.post("/generate_molecules")
async def generate_optimized_molecules(req: GenerationRequest, request: Request) -> Dict[str, Any]:
    """
    Generates optimized molecule candidates via bioisosteric replacement,
    substituent addition, and tautomer enumeration with ADMET scoring.
    """
    return build_envelope(request, RLService.generate_molecules(
        base_smiles=req.base_smiles,
        constraints=OptimizationConstraints(
            max_steps=req.max_steps,
            enforce_drug_likeness=req.enforce_drug_likeness,
            forbid_illicit_targets=req.forbid_illicit_targets
        )
    ))

@router.post("/retrosynthesis")
async def formulate_retrosynthetic_routes(target_smiles: str, request: Request) -> Dict[str, Any]:
    """Analyzes retrosynthetic routes via reaction template disconnection."""
    return build_envelope(request, RLService.analyze_retrosynthesis(target_smiles))

@router.post("/ontology_design")
async def design_taxonomy_branches(phenotype: str, request: Request) -> Dict[str, Any]:
    """Designs ontology branches using graph centrality analysis on the knowledge graph."""
    return build_envelope(request, RLService.design_ontology({"phenotype_seed": phenotype}))
