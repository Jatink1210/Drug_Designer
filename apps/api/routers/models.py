"""Endpoints for managing local and remote AI models."""

import json
import logging
import structlog
import os
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from config import settings
from services.runtime.selector import RuntimeSelector

router = APIRouter(prefix="/api/models", tags=["models"])
log = logging.getLogger(__name__)
slog = structlog.get_logger()


def _get_catalog_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "resources", "models_catalog.json")


class PullRequest(BaseModel):
    model_id: str


@router.post("/pull")
async def pull_model(req: PullRequest) -> Dict[str, Any]:
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
                return {"status": "success", "message": f"Pulled {req.model_id}"}
            return {
                "status": "error",
                "message": f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}",
            }
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama. Is it running?",
        )
    except Exception as e:
        log.error("Model pull failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pull/stream")
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


@router.get("/installed")
async def list_installed_models() -> List[Dict[str, Any]]:
    """List models installed in Ollama."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.ollama_host.rstrip('/')}/api/tags",
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {
                        "name": m.get("name", ""),
                        "size": m.get("size", 0),
                        "modified_at": m.get("modified_at", ""),
                    }
                    for m in data.get("models", [])
                ]
            slog.warning("models.installed_empty_response", detail="Ollama returned non-200 or no models")
            return []
    except Exception as e:
        slog.warning("models.installed_fetch_failed", error=str(e)[:100], hint="Is Ollama running?")
        return []


@router.delete("/{model_id:path}")
async def delete_model(model_id: str) -> Dict[str, Any]:
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
                return {"status": "success", "message": f"Deleted {model_id}"}
            return {"status": "error", "message": f"HTTP {resp.status_code}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog")
async def get_models_catalog() -> List[Dict[str, Any]]:
    """Get the list of officially supported biomedical LLMs."""
    path = _get_catalog_path()
    if not os.path.exists(path):
        slog.warning("models.catalog_missing", path=path, hint="Create resources/models_catalog.json")
        return []
    with open(path, "r") as f:
        return json.load(f)


@router.get("/compatibility/{model_name}")
async def check_compatibility(model_name: str) -> Dict[str, Any]:
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

    return {
        "model": model_name,
        "cpu_compatible": ram_ok,
        "gpu_compatible": vram_ok,
        "hardware": caps,
        "requirements": {"min_ram_gb": min_ram, "min_vram_gb": min_vram},
    }
