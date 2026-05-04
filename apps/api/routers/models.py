"""Endpoints for managing local and remote AI models."""

import json
import logging
import structlog
import os
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from core.rbac import require_role, Role

from config import settings
from models.envelope import build_envelope as _shared_envelope
from services.runtime.selector import RuntimeSelector

router = APIRouter(prefix="/api/v1/models", tags=["models"])
log = logging.getLogger(__name__)
slog = structlog.get_logger()


def _get_catalog_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "resources", "models_catalog.json")


class PullRequest(BaseModel):
    model_id: str


@router.post("/pull", response_model=Dict[str, Any], dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def pull_model(req: PullRequest, request: Request) -> Dict[str, Any]:
    """Pull a model via Ollama's /api/pull endpoint."""
    ollama_url = f"{settings.ollama_host.rstrip('/')}/api/pull"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                ollama_url,
                json={"name": req.model_id, "stream": False},
                timeout=600.0,
            )
            if resp.status_code == 200:
                return _build_envelope(request, {"status": "success", "message": f"Pulled {req.model_id}"})
            return _build_envelope(request, {
                "status": "error",
                "message": f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}",
            })
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama. Is it running?",
        )
    except Exception as e:
        log.error("Model pull failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pull/stream", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def pull_model_stream(req: PullRequest):
    """Pull a model with SSE progress updates."""
    ollama_url = f"{settings.ollama_host.rstrip('/')}/api/pull"

    async def event_generator():
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    ollama_url,
                    json={"name": req.model_id, "stream": True},
                    timeout=httpx.Timeout(600.0),
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.strip():
                            yield f"data: {line}\n\n"
            yield "event: done\ndata: {}\n\n"
        except httpx.ConnectError:
            yield f"event: error\ndata: {json.dumps({'error': 'Cannot connect to Ollama'})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/installed", response_model=Dict[str, Any], dependencies=[Depends(require_role(Role.VIEWER))])
async def list_installed_models(request: Request) -> Dict[str, Any]:
    """List models installed in Ollama."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.ollama_host.rstrip('/')}/api/tags",
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                models = [
                    {
                        "name": m.get("name", ""),
                        "size": m.get("size", 0),
                        "modified_at": m.get("modified_at", ""),
                    }
                    for m in data.get("models", [])
                ]
                return _build_envelope(request, models)
            slog.warning("models.installed_empty_response", detail="Ollama returned non-200 or no models")
            return _build_envelope(request, [])
    except Exception as e:
        slog.warning("models.installed_fetch_failed", error=str(e)[:100], hint="Is Ollama running?")
        return _build_envelope(request, [])


@router.delete("/{model_id:path}", response_model=Dict[str, Any], dependencies=[Depends(require_role(Role.OWNER))])
async def delete_model(model_id: str, request: Request) -> Dict[str, Any]:
    """Delete a model from Ollama."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                "DELETE",
                f"{settings.ollama_host.rstrip('/')}/api/delete",
                json={"name": model_id},
                timeout=30.0,
            )
            if resp.status_code == 200:
                return _build_envelope(request, {"status": "success", "message": f"Deleted {model_id}"})
            return _build_envelope(request, {"status": "error", "message": f"HTTP {resp.status_code}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog", response_model=Dict[str, Any], dependencies=[Depends(require_role(Role.VIEWER))])
async def get_models_catalog(request: Request) -> Dict[str, Any]:
    """Get the list of officially supported biomedical LLMs."""
    path = _get_catalog_path()
    if not os.path.exists(path):
        slog.warning("models.catalog_missing", path=path, hint="Create resources/models_catalog.json")
        return _build_envelope(request, [])
    with open(path, "r") as f:
        return _build_envelope(request, json.load(f))


@router.get("/compatibility/{model_name}", response_model=Dict[str, Any], dependencies=[Depends(require_role(Role.VIEWER))])
async def check_compatibility(model_name: str, request: Request) -> Dict[str, Any]:
    """Check if hardware can run a given model."""
    caps = RuntimeSelector.detect_capabilities()
    catalog = RuntimeSelector._load_catalog()
    model = next((m for m in catalog if m["name"] == model_name), None)
    if not model:
        raise HTTPException(status_code=404, detail="Model not in catalog")

    ram_gb = caps.get("ram_gb", 0)
    vram_gb = caps.get("vram_gb", 0)
    min_ram = model.get("min_ram_gb", 999)
    min_vram = model.get("min_vram_gb", 999)

    ram_ok = isinstance(ram_gb, (int, float)) and ram_gb >= min_ram
    vram_ok = isinstance(vram_gb, (int, float)) and vram_gb >= min_vram

    return _build_envelope(request, {
        "model": model_name,
        "cpu_compatible": ram_ok,
        "gpu_compatible": vram_ok,
        "hardware": caps,
        "requirements": {"min_ram_gb": min_ram, "min_vram_gb": min_vram},
    })
    
def _build_envelope(req: Request, data: Any) -> Dict[str, Any]:
    return _shared_envelope(req, data)


# ── §128 Spec-Aligned Additional Endpoints ───────────────

@router.get("", dependencies=[Depends(require_role(Role.VIEWER))])
async def list_models(request: Request) -> Dict[str, Any]:
    """§128: GET /api/v1/models — List all available models (installed + catalog)."""
    installed = []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_host.rstrip('/')}/api/tags", timeout=10.0)
            if resp.status_code == 200:
                installed = [
                    {"name": m.get("name", ""), "size": m.get("size", 0), "source": "installed"}
                    for m in resp.json().get("models", [])
                ]
    except Exception:
        pass

    catalog = []
    path = _get_catalog_path()
    if os.path.exists(path):
        with open(path) as f:
            catalog = json.load(f)

    return _build_envelope(request, {"installed": installed, "catalog": catalog})


class ModelRecommendation(BaseModel):
    task: str = "target_ranking"


@router.get("/recommendations", dependencies=[Depends(require_role(Role.VIEWER))])
async def get_recommendations(request: Request, task: str = "target_ranking") -> Dict[str, Any]:
    """§128: GET /api/v1/models/recommendations — Get model recommendations for a task."""
    caps = RuntimeSelector.detect_capabilities()
    catalog = RuntimeSelector._load_catalog() if hasattr(RuntimeSelector, '_load_catalog') else []
    recommendations = []
    for model in catalog:
        score = 0
        ram_gb = caps.get("ram_gb", 0)
        min_ram = model.get("min_ram_gb", 999)
        if isinstance(ram_gb, (int, float)) and ram_gb >= min_ram:
            score += 1
        if task in model.get("tasks", []) or task in model.get("name", "").lower():
            score += 2
        recommendations.append({"model": model.get("name", ""), "score": score, "compatible": score > 0})
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    return _build_envelope(request, {"task": task, "recommendations": recommendations[:5]})


class ModelSelectRequest(BaseModel):
    model_name: str
    task: str = ""


@router.post("/select", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def select_model(req: ModelSelectRequest, request: Request) -> Dict[str, Any]:
    """§128: POST /api/v1/models/select — Select a model for inference."""
    RuntimeSelector.set_active_runtime(
        runtime_id="ollama",
        compute_mode="auto",
        model_name=req.model_name,
        endpoint=settings.ollama_host,
        api_key="",
    )
    return _build_envelope(request, {"status": "selected", "model": req.model_name, "task": req.task})


class LocalInstallRequest(BaseModel):
    model_id: str


@router.post("/local/install", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def install_local_model(req: LocalInstallRequest, request: Request) -> Dict[str, Any]:
    """§128: POST /api/v1/models/local/install — Install a model locally via Ollama."""
    ollama_url = f"{settings.ollama_host.rstrip('/')}/api/pull"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(ollama_url, json={"name": req.model_id, "stream": False}, timeout=600.0)
            if resp.status_code == 200:
                return _build_envelope(request, {"status": "installed", "model_id": req.model_id})
            return _build_envelope(request, {"status": "error", "message": f"HTTP {resp.status_code}"})
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot connect to Ollama")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{model_name}/versions")
async def list_model_versions(model_name: str, request: Request) -> Dict[str, Any]:
    """§63.2: GET /api/v1/models/{model_name}/versions — List all versions with lineage (M-4)."""
    from sqlalchemy import select
    from core.db import AsyncSessionLocal
    from models.db_tables import ModelVersionRecord

    async with AsyncSessionLocal() as db:
        stmt = (
            select(ModelVersionRecord)
            .where(ModelVersionRecord.model_name == model_name)
            .order_by(ModelVersionRecord.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

    versions = [
        {
            "id": r.id,
            "version": r.version,
            "is_active": r.is_active,
            "parent_version_id": r.parent_version_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return _build_envelope(request, {"model": model_name, "versions": versions})


class RollbackRequest(BaseModel):
    to_version: str


@router.post("/{model_name}/rollback", dependencies=[Depends(require_role(Role.OWNER))])
async def rollback_model(model_name: str, req: RollbackRequest, request: Request) -> Dict[str, Any]:
    """§63.3: POST /api/v1/models/{model_name}/rollback — Rollback model to a previous version."""
    from sqlalchemy import select, update
    from core.db import AsyncSessionLocal
    from models.db_tables import ModelRegistryRecord

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(ModelRegistryRecord)
                .where(ModelRegistryRecord.model_name == model_name, ModelRegistryRecord.is_active == True)
                .values(is_active=False)
            )
            stmt = select(ModelRegistryRecord).where(
                ModelRegistryRecord.model_name == model_name,
                ModelRegistryRecord.version == req.to_version,
            )
            result = await db.execute(stmt)
            target = result.scalar_one_or_none()
            if not target:
                raise HTTPException(status_code=404, detail=f"Version {req.to_version} not found for {model_name}")
            target.is_active = True
            await db.commit()
        return _build_envelope(request, {
            "status": "rolled_back",
            "model": model_name,
            "active_version": req.to_version,
        })
    except HTTPException:
        raise
    except Exception as exc:
        slog.error("model_rollback_failed", model=model_name, version=req.to_version, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
