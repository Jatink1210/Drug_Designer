"""Docking API routes — with real-time WebSocket progress (§57, U-3.3)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from routers.auth import get_current_user
from pydantic import BaseModel, Field

from services.docking_service import DockingService
from models.envelope import build_envelope
from core.websocket_manager import get_ws_manager

router = APIRouter(prefix="/api/v1/docking", tags=["docking"], dependencies=[Depends(get_current_user)])

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
async def run_docking(req: DockingRequest, request: Request) -> Dict[str, Any]:
    """Execute a docking calculation with real-time WebSocket progress streaming.

    Returns poses ranked by affinity. Emits progress events on the
    WebSocket channel /ws/runs/{run_id} so the frontend can show live updates.
    """
    if req.engine not in DockingService.SUPPORTED_ENGINES:
        raise HTTPException(status_code=400, detail="Unsupported engine: %s" % req.engine)

    run_id = str(uuid.uuid4())[:12]
    ws = get_ws_manager()

    # Emit initial progress
    await ws.emit(run_id, "run.progress", {
        "stage": "docking",
        "progress_pct": 0,
        "message": f"Preparing docking with {req.engine}...",
        "state": "RUNNING",
    })

    # Emit setup stage
    await ws.emit(run_id, "run.progress", {
        "stage": "docking",
        "progress_pct": 10,
        "message": "Validating receptor and ligand inputs...",
        "state": "RUNNING",
    })

    # Run the actual docking (this is the long-running part)
    await ws.emit(run_id, "run.progress", {
        "stage": "docking",
        "progress_pct": 20,
        "message": f"Running {req.engine} docking (exhaustiveness={req.exhaustiveness})...",
        "state": "RUNNING",
    })

    result = await _svc.run_docking(
        receptor_path=req.receptor_path,
        ligand_path=req.ligand_path,
        center=req.center,
        box_size=req.box_size,
        engine=req.engine,
        exhaustiveness=req.exhaustiveness,
        num_modes=req.num_modes,
        energy_range=req.energy_range,
    )

    # Inject run_id into result for WS tracking
    result["ws_run_id"] = run_id

    # Emit completion or error
    if result.get("status") == "completed":
        num_poses = len(result.get("poses", []))
        await ws.emit(run_id, "run.progress", {
            "stage": "docking",
            "progress_pct": 90,
            "message": f"Parsing {num_poses} docking poses...",
            "state": "RUNNING",
        })
        await ws.emit(run_id, "run.completed", {
            "stage": "docking",
            "progress_pct": 100,
            "message": f"Docking complete: {num_poses} poses found",
            "state": "COMPLETE",
            "num_poses": num_poses,
            "best_affinity": result["poses"][0]["affinity_kcal"] if result["poses"] else None,
        })
    elif result.get("status") == "timeout":
        await ws.emit(run_id, "run.failed", {
            "stage": "docking",
            "progress_pct": 0,
            "message": "Docking timed out",
            "state": "FAILED",
            "error": result.get("error", "Timeout"),
        })
    else:
        await ws.emit(run_id, "run.failed", {
            "stage": "docking",
            "progress_pct": 0,
            "message": result.get("error", "Docking failed"),
            "state": "FAILED",
            "error": result.get("error", "Unknown error"),
        })

    return build_envelope(request, result)


@router.post("/pockets")
async def detect_pockets(req: PocketRequest, request: Request) -> Dict[str, Any]:
    """Detect binding pockets using fpocket or P2Rank."""
    pockets = await _svc.detect_pockets(req.receptor_path, req.method)
    return build_envelope(request, {"receptor": req.receptor_path, "method": req.method, "pockets": pockets})


@router.get("/runs")
async def list_runs(request: Request) -> Dict[str, Any]:
    """List saved docking runs."""
    return build_envelope(request, _svc.list_runs())


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> Dict[str, Any]:
    """Retrieve a saved docking run."""
    run = _svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return build_envelope(request, run)
