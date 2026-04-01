"""
Security Router — API key management and runtime fabric control endpoints.
Provides the REST surface for Sections 16.2 and 14.1 of the specification.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

router = APIRouter(prefix="/api/security", tags=["security"])


class SetKeyRequest(BaseModel):
    service: str
    api_key: str

class RuntimeModeRequest(BaseModel):
    mode: str  # cpu, gpu, or auto

class ModelRoleRequest(BaseModel):
    role: str
    model: str


# ─── API Key Management ─────────────────────────
@router.get("/keys")
async def list_api_keys() -> List[Dict[str, str]]:
    from services.api_key_manager import get_key_manager
    return get_key_manager().list_services()

@router.post("/keys")
async def set_api_key(req: SetKeyRequest) -> Dict[str, str]:
    from services.api_key_manager import get_key_manager
    get_key_manager().set_key(req.service, req.api_key)
    return {"status": "saved", "service": req.service}

@router.delete("/keys/{service}")
async def delete_api_key(service: str) -> Dict[str, str]:
    from services.api_key_manager import get_key_manager
    if get_key_manager().delete_key(service):
        return {"status": "deleted", "service": service}
    raise HTTPException(404, "Service key not found")


# ─── Runtime Fabric Control ─────────────────────
@router.get("/runtime")
async def get_runtime_config() -> Dict[str, Any]:
    from services.runtime.fabric import get_runtime_fabric
    return get_runtime_fabric().get_config()

@router.post("/runtime/mode")
async def set_runtime_mode(req: RuntimeModeRequest) -> Dict[str, str]:
    from services.runtime.fabric import get_runtime_fabric
    try:
        get_runtime_fabric().set_mode(req.mode)
        return {"status": "updated", "mode": req.mode}
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/runtime/model-role")
async def set_model_role(req: ModelRoleRequest) -> Dict[str, str]:
    from services.runtime.fabric import get_runtime_fabric
    get_runtime_fabric().set_model_for_role(req.role, req.model)
    return {"status": "updated", "role": req.role, "model": req.model}


# ─── Vector Store ────────────────────────────────
@router.get("/vectors/stats")
async def vector_store_stats() -> Dict[str, Any]:
    from services.vector_store import get_vector_store
    store = get_vector_store()
    return {"count": store.count(), "dimension": store.dimension}

@router.post("/vectors/search")
async def vector_search(query: Dict[str, Any]) -> List[Dict[str, Any]]:
    from services.vector_store import get_vector_store
    results = get_vector_store().search(query.get("text", ""), top_k=query.get("top_k", 10))
    return [{"id": r[0], "score": r[1], "metadata": r[2]} for r in results]


# ─── Job Queue Stats ────────────────────────────
@router.get("/jobs/stats")
async def job_queue_stats() -> Dict[str, Any]:
    from services.job_queue import get_job_queue
    return get_job_queue().get_stats()

@router.get("/jobs")
async def list_queued_jobs() -> List[Dict[str, Any]]:
    from services.job_queue import get_job_queue
    return get_job_queue().list_jobs()
