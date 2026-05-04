"""Endpoints for detecting and selecting LLM runtime layers."""

import os
import logging
from typing import Dict, Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import settings
from models.envelope import build_envelope as _shared_envelope
from services.runtime.selector import RuntimeSelector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])

# ── Local Agent proxy ───────────────────────────────────────
_agent_url: Optional[str] = (
    getattr(settings, "local_agent_url", None)
    or os.environ.get("LOCAL_AGENT_URL")
)


async def _agent_proxy(
    path: str, method: str = "GET", json_body: Optional[dict] = None,
) -> Optional[dict]:
    """Proxy request to local agent. Returns None if not configured/reachable."""
    if not _agent_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if method == "POST":
                resp = await client.post(f"{_agent_url}{path}", json=json_body)
            else:
                resp = await client.get(f"{_agent_url}{path}")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


class RuntimeSelectionRequest(BaseModel):
    mode: str
    target_engine: str = "llama.cpp"


class AgentPairRequest(BaseModel):
    agent_url: str
    pair_code: str = ""


@router.get("/status")
async def get_runtime_status(request: Request) -> Dict[str, Any]:
    """§128: GET /api/v1/runtime/status"""
    config = RuntimeSelector._load_config()
    data = {
        "active_mode": RuntimeSelector.get_compute_mode(),
        "active_engine": RuntimeSelector.get_active_runtime_id(),
        "selected_model": config.get("model_name", ""),
        "capabilities": RuntimeSelector.detect_capabilities()
    }
    return _build_envelope(request, data)


@router.post("/select-mode")
async def select_mode(req: RuntimeSelectionRequest, request: Request) -> Dict[str, Any]:
    """§128: POST /api/v1/runtime/select-mode"""
    RuntimeSelector.set_active_runtime(
        runtime_id=req.target_engine,
        compute_mode=req.mode,
        model_name="",
        endpoint="",
        api_key=""
    )
    try:
        from core.audit import log_audit
        from core.db import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await log_audit(db, user_id="system", action="runtime.mode_change", resource_type="runtime", resource_id=req.mode, details={"engine": req.target_engine}, ip_address=request.client.host if request.client else None)
            await db.commit()
    except Exception:
        pass
    return _build_envelope(request, {"status": "success", "mode": req.mode})


@router.get("/diagnostics")
async def get_diagnostics(request: Request) -> Dict[str, Any]:
    """§128: GET /api/v1/runtime/diagnostics"""
    try:
        runtime = RuntimeSelector.get_active_runtime()
        import asyncio
        data = runtime.health_check()
        if asyncio.iscoroutine(data):
            data = await data
    except Exception as exc:
        data = {"status": "error", "error": str(exc)}
    return _build_envelope(request, data)


# ── J-2: Runtime Inventory endpoint (receives agent sync) ─

_runtime_inventory: Optional[Dict[str, Any]] = None


@router.post("/inventory")
async def receive_runtime_inventory(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """J-2: Accept runtime_inventory_json from local agent POST /runtime/sync."""
    global _runtime_inventory
    _runtime_inventory = payload
    logger.info("runtime_inventory_received", ts=payload.get("timestamp"))
    return _build_envelope(request, {"status": "accepted"})


@router.get("/inventory")
async def get_runtime_inventory(request: Request) -> Dict[str, Any]:
    """J-2: Return the last received runtime inventory snapshot."""
    if _runtime_inventory is None:
        return _build_envelope(request, {"status": "empty", "inventory": None})
    return _build_envelope(request, _runtime_inventory)


@router.get("/fallback-plan")
async def get_fallback_plan(request: Request) -> Dict[str, Any]:
    """§128: GET /api/v1/runtime/fallback-plan"""
    data = RuntimeSelector.recommend_model()
    return _build_envelope(request, data)


@router.get("/local-agent/status")
async def get_local_agent_status(request: Request) -> Dict[str, Any]:
    """§128: GET /api/v1/runtime/local-agent/status"""
    health = await _agent_proxy("/health")
    if health is not None:
        data = {"paired": True, "agent_ip": _agent_url, **health}
    else:
        data = {"paired": bool(_agent_url), "agent_ip": _agent_url, "last_ping": None}
    return _build_envelope(request, data)


@router.post("/local-agent/pair")
async def pair_local_agent(req: AgentPairRequest, request: Request) -> Dict[str, Any]:
    """§128: POST /api/v1/runtime/local-agent/pair"""
    global _agent_url
    url = req.agent_url.rstrip("/")
    # Verify connectivity before storing
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{url}/health")
            resp.raise_for_status()
            health = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Cannot reach agent at the provided URL")
    _agent_url = url
    return _build_envelope(request, {"status": "paired", "agent_url": _agent_url, "health": health})


@router.post("/local-agent/unpair")
async def unpair_local_agent(request: Request) -> Dict[str, Any]:
    """§128: POST /api/v1/runtime/local-agent/unpair"""
    global _agent_url
    _agent_url = None
    return _build_envelope(request, {"status": "unpaired"})


@router.get("/local-agent/hardware")
async def get_local_agent_hardware(request: Request) -> Dict[str, Any]:
    """§20: GET /api/v1/runtime/local-agent/hardware"""
    hw = await _agent_proxy("/hardware")
    if hw is not None:
        return _build_envelope(request, hw)
    return _build_envelope(request, {
        "cpu": "unknown", "ram_gb": 0, "gpu_name": "unknown",
        "vram_gb": 0, "disk_free_gb": 0,
        "note": "Connect a Local Runtime Agent to populate hardware details",
    })


@router.get("/local-agent/runtimes")
async def get_local_agent_runtimes(request: Request) -> Dict[str, Any]:
    """§20: GET /api/v1/runtime/local-agent/runtimes — installed runtime list"""
    data = await _agent_proxy("/runtimes")
    if data is not None:
        return _build_envelope(request, data)
    return _build_envelope(request, {"runtimes": [], "note": "No agent connected"})


@router.get("/local-agent/models")
async def get_local_agent_models(request: Request) -> Dict[str, Any]:
    """§20: GET /api/v1/runtime/local-agent/models — locally installed models"""
    data = await _agent_proxy("/models")
    if data is not None:
        return _build_envelope(request, data)
    return _build_envelope(request, {"models": [], "note": "No agent connected"})


@router.get("/local-agent/diagnostics")
async def get_local_agent_diagnostics(request: Request) -> Dict[str, Any]:
    """§20: GET /api/v1/runtime/local-agent/diagnostics"""
    diag = await _agent_proxy("/diagnostics") or await _agent_proxy("/health")
    if diag is not None:
        return _build_envelope(request, {"installed": True, "connected": True, "diagnostics": diag})
    return _build_envelope(request, {
        "installed": False, "connected": False,
        "diagnostics": [{"check": "agent_connectivity", "status": "no_agent"}],
    })


# ── Endpoint Probing — connect to existing local LLM servers ──


class ProbeEndpointRequest(BaseModel):
    url: str


@router.post("/probe-endpoint")
async def probe_endpoint(req: ProbeEndpointRequest, request: Request) -> Dict[str, Any]:
    """Probe an OpenAI-compatible or Ollama endpoint for connectivity and available models.

    Supports: Ollama (/api/tags), OpenAI-compatible (/v1/models), LM Studio, vLLM, text-generation-webui.
    The user provides a URL; we detect what's running and list available models — no downloads needed.
    """
    url = req.url.rstrip("/")
    result: Dict[str, Any] = {
        "reachable": False,
        "server_type": "unknown",
        "models": [],
        "endpoint": url,
    }

    async with httpx.AsyncClient(timeout=8.0) as client:
        # Try Ollama /api/tags first
        try:
            resp = await client.get(f"{url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [
                    {"name": m.get("name", ""), "size": m.get("size", 0)}
                    for m in data.get("models", [])
                ]
                result.update(reachable=True, server_type="ollama", models=models)
                return _build_envelope(request, result)
        except Exception:
            pass

        # Try OpenAI-compatible /v1/models
        try:
            resp = await client.get(f"{url}/v1/models")
            if resp.status_code == 200:
                data = resp.json()
                models = [
                    {"name": m.get("id", ""), "size": 0}
                    for m in data.get("data", [])
                ]
                result.update(reachable=True, server_type="openai_compat", models=models)
                return _build_envelope(request, result)
        except Exception:
            pass

        # Try plain /models (some servers use this)
        try:
            resp = await client.get(f"{url}/models")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    models = [{"name": m if isinstance(m, str) else m.get("id", ""), "size": 0} for m in data]
                elif isinstance(data, dict) and "data" in data:
                    models = [{"name": m.get("id", ""), "size": 0} for m in data["data"]]
                else:
                    models = []
                result.update(reachable=True, server_type="openai_compat", models=models)
                return _build_envelope(request, result)
        except Exception:
            pass

        # Try a basic health/root check
        try:
            resp = await client.get(url)
            if resp.status_code < 500:
                result.update(reachable=True, server_type="unknown")
                return _build_envelope(request, result)
        except Exception:
            pass

    return _build_envelope(request, result)


def _build_envelope(req: Request, data: Any) -> Dict[str, Any]:
    return _shared_envelope(req, data)
