"""Docking API routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.docking_service import DockingService

router = APIRouter(prefix="/api/docking", tags=["docking"])

_svc = DockingService()


class DockingRequest(BaseModel):
    receptor_path: str
    ligand_path: str
    center: List[float] = Field(..., min_length=3, max_length=3)
    box_size: List[float] = Field(default=[20.0, 20.0, 20.0], min_length=3, max_length=3)
    engine: str = "vina"
    exhaustiveness: int = 8
    num_modes: int = 9
    energy_range: float = 3.0


class PocketRequest(BaseModel):
    receptor_path: str
    method: str = "fpocket"


@router.post("/run")
async def run_docking(req: DockingRequest) -> Dict[str, Any]:
    """Execute a docking calculation. Returns poses ranked by affinity."""
    if req.engine not in DockingService.SUPPORTED_ENGINES:
        raise HTTPException(status_code=400, detail="Unsupported engine: %s" % req.engine)
    return await _svc.run_docking(
        receptor_path=req.receptor_path,
        ligand_path=req.ligand_path,
        center=req.center,
        box_size=req.box_size,
        engine=req.engine,
        exhaustiveness=req.exhaustiveness,
        num_modes=req.num_modes,
        energy_range=req.energy_range,
    )


@router.post("/pockets")
async def detect_pockets(req: PocketRequest) -> Dict[str, Any]:
    """Detect binding pockets using fpocket or P2Rank."""
    pockets = await _svc.detect_pockets(req.receptor_path, req.method)
    return {"receptor": req.receptor_path, "method": req.method, "pockets": pockets}


@router.get("/runs")
async def list_runs() -> List[Dict[str, Any]]:
    """List saved docking runs."""
    return _svc.list_runs()


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> Dict[str, Any]:
    """Retrieve a saved docking run."""
    run = _svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
