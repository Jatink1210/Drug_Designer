"""Data Manager API — keys, toggles, cache, storage."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import settings
from core.cache import get_disk_cache, get_memory_cache

router = APIRouter(prefix="/api/data", tags=["data"])

# ── API Key Management ────────────────────────────────────

KEYS_FILE = os.path.join(settings.local_store_path, "api_keys.json")


def _load_keys() -> Dict[str, str]:
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE) as f:
            return json.load(f)
    return {}


def _save_keys(keys: Dict[str, str]) -> None:
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)


class APIKeyUpdate(BaseModel):
    service: str
    key: str


@router.get("/keys")
async def list_keys() -> Dict[str, Any]:
    """List configured API keys (masked)."""
    keys = _load_keys()
    masked = {k: v[:4] + "***" + v[-4:] if len(v) > 8 else "***" for k, v in keys.items()}
    return {"keys": masked, "count": len(keys)}


@router.post("/keys")
async def set_key(req: APIKeyUpdate) -> Dict[str, str]:
    """Set or update an API key."""
    keys = _load_keys()
    keys[req.service] = req.key
    _save_keys(keys)
    return {"status": "updated", "service": req.service}


@router.delete("/keys/{service}")
async def delete_key(service: str) -> Dict[str, str]:
    keys = _load_keys()
    if service in keys:
        del keys[service]
        _save_keys(keys)
    return {"status": "deleted", "service": service}


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


@router.get("/connectors")
async def list_connectors() -> List[Dict[str, Any]]:
    """List all connectors with enabled/disabled status."""
    toggles = _load_toggles()
    return [{**c, "enabled": toggles.get(c["id"], True)} for c in AVAILABLE_CONNECTORS]


@router.post("/connectors/toggle")
async def toggle_connector(req: ToggleRequest) -> Dict[str, str]:
    """Enable or disable a connector."""
    toggles = _load_toggles()
    toggles[req.connector_id] = req.enabled
    _save_toggles(toggles)
    return {"status": "updated", "connector": req.connector_id, "enabled": str(req.enabled)}


# ── Cache Management ──────────────────────────────────────

@router.get("/cache")
async def cache_status() -> Dict[str, Any]:
    """Get cache statistics."""
    disk = get_disk_cache()
    mem = get_memory_cache()
    return {
        "sqlite": disk.stats(),
        "memory": {"size": len(mem._cache) if hasattr(mem, "_cache") else 0, "max_size": getattr(mem, "_max_size", 2000)},
    }


@router.delete("/cache")
async def clear_cache() -> Dict[str, str]:
    """Clear all caches."""
    disk = get_disk_cache()
    disk.clear()
    mem = get_memory_cache()
    if hasattr(mem, "clear"):
        mem.clear()
    return {"status": "cleared"}


# ── Storage ───────────────────────────────────────────────

@router.get("/storage")
async def storage_stats() -> Dict[str, Any]:
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

    return {
        "local_store_path": store_path,
        "total_bytes": dir_size(store_path),
        "subdirectories": {
            "docking_runs": dir_size(os.path.join(store_path, "docking_runs")),
            "design_iterations": dir_size(os.path.join(store_path, "design_iterations")),
            "reports": dir_size(os.path.join(store_path, "reports")),
            "cache_db": os.path.getsize(settings.sqlite_db_path) if os.path.exists(settings.sqlite_db_path) else 0,
        },
    }
