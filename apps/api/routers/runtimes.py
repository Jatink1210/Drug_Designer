"""Endpoints for detecting and selecting LLM runtime layers."""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.runtime.selector import RuntimeSelector

router = APIRouter(prefix="/api/runtimes", tags=["runtimes"])


class RuntimeSelectionRequest(BaseModel):
    runtime_id: str
    model_name: str = ""
    endpoint: str = ""
    api_key: str = ""
    compute_mode: str = "auto"


@router.get("")
async def list_runtimes() -> Dict[str, Any]:
    """List available runtimes and the detected host hardware capabilities."""
    return {
        "capabilities": RuntimeSelector.detect_capabilities(),
        "available": RuntimeSelector.get_available_runtimes(),
        "active": RuntimeSelector.get_active_runtime_id(),
        "compute_mode": RuntimeSelector.get_compute_mode(),
    }


@router.post("/select")
async def select_runtime(req: RuntimeSelectionRequest) -> Dict[str, Any]:
    """Select a runtime and persist it to the active configuration."""
    available = RuntimeSelector.get_available_runtimes()
    available_ids = [r["id"] for r in available]
    if req.runtime_id not in available_ids:
        raise HTTPException(status_code=400, detail="Invalid runtime_id")

    runtime_info = next((r for r in available if r["id"] == req.runtime_id), None)
    if runtime_info and runtime_info.get("status") == "not_implemented":
        raise HTTPException(
            status_code=400,
            detail=f"Runtime '{req.runtime_id}' is not yet fully integrated. "
                   f"Use 'llama.cpp' or 'remote' instead.",
        )

    RuntimeSelector.set_active_runtime(
        runtime_id=req.runtime_id,
        model_name=req.model_name,
        endpoint=req.endpoint,
        api_key=req.api_key,
        compute_mode=req.compute_mode,
    )

    return {
        "status": "success",
        "selected": req.runtime_id,
        "model": req.model_name,
        "compute_mode": req.compute_mode,
    }


@router.get("/health")
async def get_runtime_health() -> Dict[str, Any]:
    """Execute a runtime-specific health check."""
    runtime = RuntimeSelector.get_active_runtime()
    return runtime.health_check()


@router.get("/recommend")
async def recommend_configuration() -> Dict[str, Any]:
    """Auto-detect hardware and recommend compute mode + model."""
    return RuntimeSelector.recommend_model()
