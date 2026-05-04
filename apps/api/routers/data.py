"""Data Manager API — keys, toggles, cache, storage."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from models.envelope import build_envelope

from core.rbac import require_role, Role

from config import settings
from core.cache import get_disk_cache, get_memory_cache
from services.api_key_manager import get_key_manager

router = APIRouter(prefix="/api/v1/data", tags=["data"])

# ── API Key Management (Fernet-encrypted via APIKeyManager) ──


class APIKeyUpdate(BaseModel):
    service: str
    key: str


@router.get("/keys", dependencies=[Depends(require_role(Role.VIEWER))])
async def list_keys(request: Request) -> Dict[str, Any]:
    """List configured API keys (masked)."""
    mgr = get_key_manager()
    services = mgr.list_services()
    return build_envelope(request, {"keys": {s["service"]: s["masked_key"] for s in services}, "count": len(services)})


@router.post("/keys", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def set_key(req: APIKeyUpdate, request: Request) -> Dict[str, Any]:
    """Set or update an API key."""
    mgr = get_key_manager()
    mgr.set_key(req.service, req.key)
    return build_envelope(request, {"status": "updated", "service": req.service})


@router.delete("/keys/{service}", dependencies=[Depends(require_role(Role.OWNER))])
async def delete_key(service: str, request: Request) -> Dict[str, Any]:
    mgr = get_key_manager()
    mgr.delete_key(service)
    return build_envelope(request, {"status": "deleted", "service": service})


# ── Connector Toggle ──────────────────────────────────────

TOGGLES_FILE = os.path.join(settings.local_store_path, "connector_toggles.json")

AVAILABLE_CONNECTORS = [
    {"id": "uniprot", "name": "UniProt", "required": True},
    {"id": "pubmed", "name": "PubMed", "required": True},
    {"id": "opentargets", "name": "OpenTargets", "required": True},
    {"id": "rcsb", "name": "RCSB PDB", "required": True},
    {"id": "chembl", "name": "ChEMBL", "required": True},
    {"id": "clinicaltrials", "name": "ClinicalTrials.gov", "required": True},
    {"id": "reactome", "name": "Reactome", "required": False},
    {"id": "alphafold", "name": "AlphaFold", "required": False},
    {"id": "pubchem", "name": "PubChem", "required": False},
    {"id": "europepmc", "name": "Europe PMC", "required": False},
    {"id": "string", "name": "STRING", "required": False},
    {"id": "patentsview", "name": "PatentsView", "required": False},
    {"id": "surechebl", "name": "SureChEMBL", "required": False},
]


def _load_toggles() -> Dict[str, bool]:
    if os.path.exists(TOGGLES_FILE):
        with open(TOGGLES_FILE) as f:
            return json.load(f)
    return {c["id"]: True for c in AVAILABLE_CONNECTORS}


def _save_toggles(toggles: Dict[str, bool]) -> None:
    os.makedirs(os.path.dirname(TOGGLES_FILE), exist_ok=True)
    with open(TOGGLES_FILE, "w") as f:
        json.dump(toggles, f, indent=2)


class ToggleRequest(BaseModel):
    connector_id: str
    enabled: bool


@router.get("/connectors", dependencies=[Depends(require_role(Role.VIEWER))])
async def list_connectors(request: Request) -> Dict[str, Any]:
    """List all connectors with enabled/disabled status."""
    toggles = _load_toggles()
    return build_envelope(request, [{**c, "enabled": toggles.get(c["id"], True)} for c in AVAILABLE_CONNECTORS])


@router.post("/connectors/toggle", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def toggle_connector(req: ToggleRequest, request: Request) -> Dict[str, Any]:
    """Enable or disable a connector."""
    toggles = _load_toggles()
    toggles[req.connector_id] = req.enabled
    _save_toggles(toggles)
    return build_envelope(request, {"status": "updated", "connector": req.connector_id, "enabled": str(req.enabled)})


# ── Cache Management ──────────────────────────────────────

@router.get("/cache", dependencies=[Depends(require_role(Role.VIEWER))])
async def cache_status(request: Request) -> Dict[str, Any]:
    """Get cache statistics."""
    disk = get_disk_cache()
    mem = get_memory_cache()
    return build_envelope(request, {
        "sqlite": disk.stats(),
        "memory": {"size": len(mem._cache) if hasattr(mem, "_cache") else 0, "max_size": getattr(mem, "_max_size", 2000)},
    })


@router.delete("/cache", dependencies=[Depends(require_role(Role.OWNER))])
async def clear_cache(request: Request) -> Dict[str, Any]:
    """Clear all caches."""
    disk = get_disk_cache()
    disk.clear()
    mem = get_memory_cache()
    if hasattr(mem, "clear"):
        mem.clear()
    return build_envelope(request, {"status": "cleared"})


# ── Storage ───────────────────────────────────────────────

@router.get("/storage", dependencies=[Depends(require_role(Role.VIEWER))])
async def storage_stats(request: Request) -> Dict[str, Any]:
    """Get storage usage statistics."""
    store_path = settings.local_store_path

    def dir_size(path: str) -> int:
        total = 0
        if os.path.exists(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    try:
                        total += os.path.getsize(os.path.join(dirpath, f))
                    except OSError:
                        pass
        return total

    return build_envelope(request, {
        "local_store_path": store_path,
        "total_bytes": dir_size(store_path),
        "subdirectories": {
            "docking_runs": dir_size(os.path.join(store_path, "docking_runs")),
            "design_iterations": dir_size(os.path.join(store_path, "design_iterations")),
            "reports": dir_size(os.path.join(store_path, "reports")),
            "cache_db": os.path.getsize(settings.sqlite_db_path) if os.path.exists(settings.sqlite_db_path) else 0,
        },
    })
