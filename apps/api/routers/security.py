"""
Security Router — API key management and runtime fabric control endpoints.
Provides the REST surface for Sections 16.2 and 14.1 of the specification.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from models.envelope import build_envelope

from core.rbac import require_role, Role

router = APIRouter(prefix="/api/v1/security", tags=["security"])


class SetKeyRequest(BaseModel):
    service: str
    api_key: str

class RuntimeModeRequest(BaseModel):
    mode: str  # cpu, gpu, or auto

class ModelRoleRequest(BaseModel):
    role: str
    model: str


# ─── API Key Management ─────────────────────────
@router.get("/keys", dependencies=[Depends(require_role(Role.ADMIN))])
async def list_api_keys(request: Request) -> Dict[str, Any]:
    from services.api_key_manager import get_key_manager
    return build_envelope(request, get_key_manager().list_services())

@router.post("/keys", dependencies=[Depends(require_role(Role.ADMIN))])
async def set_api_key(req: SetKeyRequest, request: Request) -> Dict[str, str]:
    from services.api_key_manager import get_key_manager
    get_key_manager().set_key(req.service, req.api_key)
    try:
        from core.audit import log_audit
        from core.db import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await log_audit(db, user_id="system", action="key.create", resource_type="api_key", resource_id=req.service, ip_address=request.client.host if request.client else None)
            await db.commit()
    except Exception:
        pass
    return build_envelope(request, {"status": "saved", "service": req.service})

@router.delete("/keys/{service}", dependencies=[Depends(require_role(Role.ADMIN))])
async def delete_api_key(service: str, request: Request) -> Dict[str, str]:
    from services.api_key_manager import get_key_manager
    if get_key_manager().delete_key(service):
        try:
            from core.audit import log_audit
            from core.db import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                await log_audit(db, user_id="system", action="key.delete", resource_type="api_key", resource_id=service, ip_address=request.client.host if request.client else None)
                await db.commit()
        except Exception:
            pass
        return build_envelope(request, {"status": "deleted", "service": service})
    raise HTTPException(404, "Service key not found")


# ─── Runtime Fabric Control ─────────────────────
@router.get("/runtime", dependencies=[Depends(require_role(Role.ADMIN))])
async def get_runtime_config(request: Request) -> Dict[str, Any]:
    from services.runtime.fabric import get_runtime_fabric
    return build_envelope(request, get_runtime_fabric().get_config())

@router.post("/runtime/mode", dependencies=[Depends(require_role(Role.ADMIN))])
async def set_runtime_mode(req: RuntimeModeRequest, request: Request) -> Dict[str, Any]:
    from services.runtime.fabric import get_runtime_fabric
    try:
        get_runtime_fabric().set_mode(req.mode)
        return build_envelope(request, {"status": "updated", "mode": req.mode})
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/runtime/model-role", dependencies=[Depends(require_role(Role.ADMIN))])
async def set_model_role(req: ModelRoleRequest, request: Request) -> Dict[str, Any]:
    from services.runtime.fabric import get_runtime_fabric
    get_runtime_fabric().set_model_for_role(req.role, req.model)
    return build_envelope(request, {"status": "updated", "role": req.role, "model": req.model})


# ─── Vector Store ────────────────────────────────
@router.get("/vectors/stats", dependencies=[Depends(require_role(Role.ADMIN))])
async def vector_store_stats(request: Request) -> Dict[str, Any]:
    from services.vector_store import get_vector_store
    store = get_vector_store()
    return build_envelope(request, {"count": store.count(), "dimension": store.dimension})

@router.post("/vectors/search", dependencies=[Depends(require_role(Role.ADMIN))])
async def vector_search(query: Dict[str, Any], request: Request) -> Dict[str, Any]:
    from services.vector_store import get_vector_store
    results = get_vector_store().search(query.get("text", ""), top_k=query.get("top_k", 10))
    return build_envelope(request, [{"id": r[0], "score": r[1], "metadata": r[2]} for r in results])


# ─── Job Queue Stats ────────────────────────────
@router.get("/jobs/stats", dependencies=[Depends(require_role(Role.ADMIN))])
async def job_queue_stats(request: Request) -> Dict[str, Any]:
    from services.job_queue import get_job_queue
    return build_envelope(request, get_job_queue().get_stats())

@router.get("/jobs", dependencies=[Depends(require_role(Role.ADMIN))])
async def list_queued_jobs(request: Request) -> Dict[str, Any]:
    from services.job_queue import get_job_queue
    return build_envelope(request, get_job_queue().list_jobs())


# ─── Audit Log (§65) ────────────────────────────

@router.get("/audit-log", dependencies=[Depends(require_role(Role.ADMIN))])
async def get_audit_log(
    request: Request,
    limit: int = 50,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
) -> Dict[str, Any]:
    """§65: GET /api/v1/security/audit-log — View audit log entries."""
    try:
        from sqlalchemy import select, desc
        from core.db import AsyncSessionLocal
        from models.db_tables import AuditLog

        async with AsyncSessionLocal() as db:
            q = select(AuditLog).order_by(desc(AuditLog.created_at))
            if user_id:
                q = q.where(AuditLog.user_id == user_id)
            if action:
                q = q.where(AuditLog.action == action)
            q = q.limit(limit)
            result = await db.execute(q)
            entries = result.scalars().all()
            return build_envelope(request, {
                "entries": [
                    {
                        "id": e.id,
                        "user_id": e.user_id,
                        "action": e.action,
                        "resource_type": e.resource_type,
                        "resource_id": e.resource_id,
                        "details": e.details or {},
                        "ip_address": e.ip_address,
                        "created_at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in entries
                ],
                "total": len(entries),
            })
    except Exception:
        return build_envelope(request, {"entries": [], "total": 0})


# ─── Session Management (§22) ───────────────────

@router.get("/sessions", dependencies=[Depends(require_role(Role.ADMIN))])
async def list_sessions(request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
    """§22: GET /api/v1/security/sessions — List active user sessions."""
    try:
        from sqlalchemy import select
        from core.db import AsyncSessionLocal
        from models.db_tables import Session

        async with AsyncSessionLocal() as db:
            q = select(Session).where(Session.is_active == True)
            if user_id:
                q = q.where(Session.user_id == user_id)
            result = await db.execute(q)
            sessions = result.scalars().all()
            return build_envelope(request, {
                "sessions": [
                    {
                        "id": s.id,
                        "user_id": s.user_id,
                        "ip_address": s.ip_address,
                        "user_agent": s.user_agent,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                    }
                    for s in sessions
                ],
                "total": len(sessions),
            })
    except Exception:
        return build_envelope(request, {"sessions": [], "total": 0})


@router.delete("/sessions/{session_id}", dependencies=[Depends(require_role(Role.ADMIN))])
async def revoke_session(session_id: str, request: Request) -> Dict[str, Any]:
    """§22: DELETE /api/v1/security/sessions/{id} — Revoke an active session."""
    try:
        from sqlalchemy import select
        from core.db import AsyncSessionLocal
        from models.db_tables import Session

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Session).where(Session.id == session_id))
            session = result.scalars().first()
            if not session:
                raise HTTPException(404, "Session not found")
            session.is_active = False
            await db.commit()
            return build_envelope(request, {"status": "revoked", "session_id": session_id})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
