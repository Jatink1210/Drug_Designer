"""Project memory — CRUD for persistent research projects."""

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.paths import get_data_dir

router = APIRouter(prefix="/api/projects", tags=["projects"])
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

@router.get("")
async def list_projects(current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
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
    return projects

@router.post("")
async def create_project(req: CreateProjectRequest, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
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
    return project

@router.get("/{project_id}")
async def get_project(project_id: str, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    path = _project_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(path) as f:
        proj = json.load(f)
    if proj.get("user_id", "local_desktop") != current_user.id and current_user.id != "local_desktop":
        raise HTTPException(status_code=403, detail="Not authorized to view this project")
    return proj

@router.patch("/{project_id}")
async def update_project(project_id: str, req: UpdateProjectRequest, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
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
    return project

@router.delete("/{project_id}")
async def delete_project(project_id: str, current_user: User = Depends(get_current_user)) -> Dict[str, str]:
    path = _project_path(project_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(path) as f:
        project = json.load(f)
    if project.get("user_id", "local_desktop") != current_user.id and current_user.id != "local_desktop":
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")
        
    os.remove(path)
    return {"status": "deleted", "id": project_id}


@router.post("/{project_id}/jobs/{job_id}")
async def link_job_to_project(project_id: str, job_id: str) -> Dict[str, Any]:
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
    return project


@router.post("/{project_id}/notes")
async def add_note(project_id: str, note: Dict[str, str]) -> Dict[str, Any]:
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
    return project
