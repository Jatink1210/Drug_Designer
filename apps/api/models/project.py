"""Project & Memory models (Drug Designer §56, §A7).

Projects are the top-level organizational unit. Project Memory grows
after real use: queries, runs, evidence saves, reports, dossiers.
These Pydantic schemas complement the SQLAlchemy ORM in models/user.py.
"""

from __future__ import annotations

import uuid
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Project ────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    """Payload for creating a new project."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""


class ProjectUpdate(BaseModel):
    """Payload for updating an existing project."""

    title: Optional[str] = None
    description: Optional[str] = None


class ProjectSummary(BaseModel):
    """Project as returned in list views."""

    id: str
    title: str
    description: str = ""
    owner_id: str
    created_at: str
    last_active: str
    total_runs: int = 0
    total_evidence_items: int = 0
    total_dossiers: int = 0


# ── Project Member ─────────────────────────────────────────
class ProjectMember(BaseModel):
    """A user's membership and role in a project (§55.2 RBAC)."""

    project_id: str
    user_id: str
    role: str = Field(
        "collaborator",
        description="owner | collaborator | viewer (§55.2)",
    )


# ── Project Note ───────────────────────────────────────────
class ProjectNote(BaseModel):
    """Free-text note attached to a project."""

    note_id: str = Field(default_factory=_uuid)
    project_id: str
    user_id: str
    body: str
    created_at: str = Field(default_factory=_now_iso)


# ── Memory Object (§A7, §56.2) ─────────────────────────────
class MemoryObject(BaseModel):
    """A saved object in Project Memory — evidence bundles, disease runs,
    target rankings, graph snapshots, dossiers, etc.

    §A7: Scientists should never have to restart their context from scratch.
    """

    memory_id: str = Field(default_factory=_uuid)
    project_id: str
    object_type: str = Field(
        ..., description="evidence_bundle | disease_run | target_ranking | graph_snapshot | dossier"
    )
    object_id: str = Field(..., description="UUID of the referenced object")
    label: str = ""
    pinned: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)


# ── §A7.2 — Project Memory Summary ─────────────────────────
class ProjectMemorySummary(BaseModel):
    """Aggregated memory view for a project — displayed on Cockpit."""

    project_id: str
    created_at: str
    last_active: str
    disease_runs: List[Dict[str, Any]] = Field(default_factory=list)
    target_rankings: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_bundles: List[Dict[str, Any]] = Field(default_factory=list)
    graph_snapshots: List[Dict[str, Any]] = Field(default_factory=list)
    dossiers: List[Dict[str, Any]] = Field(default_factory=list)
    contradictions: List[Dict[str, Any]] = Field(default_factory=list)
    total_runs: int = 0
    total_evidence_items: int = 0
    total_exports: int = 0
