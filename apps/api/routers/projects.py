"""Project memory — CRUD for persistent research projects."""

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from core.paths import get_data_dir
from core.rbac import require_role, Role
from core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from models.envelope import build_envelope as _shared_envelope

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
log = logging.getLogger(__name__)


def _projects_dir() -> str:
    d = os.path.join(get_data_dir(), "projects")
    os.makedirs(d, exist_ok=True)
    return d


def _project_path(project_id: str) -> str:
    return os.path.join(_projects_dir(), f"{project_id}.json")


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    tags: List[str] = []


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    pinned: Optional[bool] = None


from routers.auth import get_current_user, User

@router.get("", dependencies=[Depends(require_role(Role.VIEWER))])
async def list_projects(request: Request, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """List all projects for the authenticated tenant."""
    projects = []
    for fname in os.listdir(_projects_dir()):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(_projects_dir(), fname)) as f:
                proj = json.load(f)
                if proj.get("user_id", "local_desktop") == current_user.id or current_user.id == "local_desktop":
                    projects.append(proj)
        except Exception:
            continue
    projects.sort(key=lambda p: p.get("updated_at", 0), reverse=True)
    return _build_envelope(request, projects)

@router.post("", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def create_project(req: CreateProjectRequest, request: Request, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Create a new research project isolated to the tenant."""
    project = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "name": req.name,
        "description": req.description,
        "tags": req.tags,
        "pinned": False,
        "job_ids": [],
        "notes": [],
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    with open(_project_path(project["id"]), "w") as f:
        json.dump(project, f, indent=2)
    return _build_envelope(request, project)

@router.get("/{project_id}", dependencies=[Depends(require_role(Role.VIEWER))])
async def get_project(project_id: str, request: Request, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    path = _project_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(path) as f:
        proj = json.load(f)
    if proj.get("user_id", "local_desktop") != current_user.id and current_user.id != "local_desktop":
        raise HTTPException(status_code=403, detail="Not authorized to view this project")
    return _build_envelope(request, proj)

@router.patch("/{project_id}", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def update_project(project_id: str, req: UpdateProjectRequest, request: Request, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    path = _project_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(path) as f:
        project = json.load(f)
    if project.get("user_id", "local_desktop") != current_user.id and current_user.id != "local_desktop":
        raise HTTPException(status_code=403, detail="Not authorized to edit this project")
        
    if req.name is not None:
        project["name"] = req.name
    if req.description is not None:
        project["description"] = req.description
    if req.tags is not None:
        project["tags"] = req.tags
    if req.pinned is not None:
        project["pinned"] = req.pinned
    project["updated_at"] = time.time()
    with open(path, "w") as f:
        json.dump(project, f, indent=2)
    return _build_envelope(request, project)

@router.delete("/{project_id}", dependencies=[Depends(require_role(Role.OWNER))])
async def delete_project(project_id: str, request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    path = _project_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(path) as f:
        project = json.load(f)
    if project.get("user_id", "local_desktop") != current_user.id and current_user.id != "local_desktop":
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")
        
    os.remove(path)
    from core.audit import log_audit
    await log_audit(db, user_id=current_user.id, action="project.delete", resource_type="project", resource_id=project_id, ip_address=request.client.host if request.client else None)
    await db.commit()
    return _build_envelope(request, {"status": "deleted", "id": project_id})


@router.post("/{project_id}/jobs/{job_id}", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def link_job_to_project(project_id: str, job_id: str, request: Request) -> Dict[str, Any]:
    """Link a completed job to a project."""
    path = _project_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(path) as f:
        project = json.load(f)
    if job_id not in project.get("job_ids", []):
        project.setdefault("job_ids", []).append(job_id)
        project["updated_at"] = time.time()
        with open(path, "w") as f:
            json.dump(project, f, indent=2)
    return _build_envelope(request, project)


@router.post("/{project_id}/notes", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def add_note(project_id: str, note: Dict[str, str], request: Request) -> Dict[str, Any]:
    """Add a text note to a project."""
    path = _project_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(path) as f:
        project = json.load(f)
    project.setdefault("notes", []).append({
        "id": str(uuid.uuid4()),
        "text": note.get("text", ""),
        "created_at": time.time(),
    })
    project["updated_at"] = time.time()
    with open(path, "w") as f:
        json.dump(project, f, indent=2)
    return _build_envelope(request, project)


@router.get("/{project_id}/memory", dependencies=[Depends(require_role(Role.VIEWER))])
async def get_project_memory(project_id: str, request: Request, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """§119: GET /api/v1/projects/{projectId}/memory — Get project memory (accumulated context)."""
    path = _project_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(path) as f:
        proj = json.load(f)
    if proj.get("user_id", "local_desktop") != current_user.id and current_user.id != "local_desktop":
        raise HTTPException(status_code=403, detail="Not authorized")
    memory = {
        "project_id": project_id,
        "notes": proj.get("notes", []),
        "job_ids": proj.get("job_ids", []),
        "tags": proj.get("tags", []),
        "created_at": proj.get("created_at"),
        "updated_at": proj.get("updated_at"),
    }
    return _build_envelope(request, memory)


# ── K-3 + K-4: Semantic memory search with structlog trace ───────────────

@router.get("/{project_id}/memory/search", dependencies=[Depends(require_role(Role.VIEWER))])
async def search_project_memory(
    project_id: str,
    request: Request,
    q: str,
    limit: int = 10,
    tiers: str = "1,2",
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """K-3: GET /api/v1/projects/{id}/memory/search?q=<text> — Semantic search over project memory.

    K-4: Emits structlog trace with retrieval timing.
    """
    import structlog, time
    slog = structlog.get_logger(__name__)

    path = _project_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Project not found")

    tier_filter = [int(t) for t in tiers.split(",") if t.strip().isdigit()]
    t0 = time.monotonic()

    try:
        from services.context_fabric.manager import ContextFabric
        fabric = ContextFabric()  # no deps — uses local fallback
        result = await fabric.retrieve(project_id, query=q, tier_filter=tier_filter, limit=limit)
    except Exception as exc:
        log.error("memory_search_failed", project_id=project_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Memory search failed: {exc}")

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # K-4: structlog retrieval trace
    slog.info(
        "memory_search_trace",
        project_id=project_id,
        query=q,
        tier_filter=tier_filter,
        results_count=result.get("total", 0),
        retrieval_ms=elapsed_ms,
        latency_trace=result.get("latency_trace"),
    )

    return _build_envelope(request, {
        "project_id": project_id,
        "query": q,
        "results": result.get("query_results", []),
        "total": result.get("total", 0),
        "retrieval_ms": elapsed_ms,
        "latency_trace": result.get("latency_trace"),
    })


# ── K-5: Cross-project memory linkage ────────────────────────────────────

class MemoryLinkRequest(BaseModel):
    source_object_id: str
    target_project_id: str
    target_object_id: str
    relation: str = "related"


@router.post("/{project_id}/memory/link", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def link_project_memory(
    project_id: str,
    body: MemoryLinkRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """K-5: POST /api/v1/projects/{id}/memory/link — Create cross-project memory linkage."""
    import structlog
    slog = structlog.get_logger(__name__)

    try:
        from services.context_fabric.manager import ContextFabric
        fabric = ContextFabric()
        link = await fabric.link_memory_objects(
            source_project_id=project_id,
            source_object_id=body.source_object_id,
            target_project_id=body.target_project_id,
            target_object_id=body.target_object_id,
            relation=body.relation,
        )
    except Exception as exc:
        log.error("memory_link_failed", project_id=project_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Memory link failed: {exc}")

    slog.info(
        "cross_project_link_created",
        source=f"{project_id}/{body.source_object_id}",
        target=f"{body.target_project_id}/{body.target_object_id}",
        relation=body.relation,
    )
    return _build_envelope(request, {"status": "linked", "link": link})


@router.get("/{project_id}/memory/links", dependencies=[Depends(require_role(Role.VIEWER))])
async def get_project_memory_links(
    project_id: str,
    request: Request,
    object_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """K-5: GET /api/v1/projects/{id}/memory/links — List cross-project memory links."""
    try:
        from services.context_fabric.manager import ContextFabric
        fabric = ContextFabric()
        links = await fabric.get_cross_project_links(project_id, object_id=object_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return _build_envelope(request, {"project_id": project_id, "links": links, "total": len(links)})


def _build_envelope(req: Request, data: Any) -> Dict[str, Any]:
    return _shared_envelope(req, data)
