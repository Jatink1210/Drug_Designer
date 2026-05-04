"""Dossier & Report models (Drug Designer §A10, §94.4).

The Decision Dossier is the canonical final output of the platform.
It must be evidence-backed, contradiction-aware, and fully provenanced.
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


# ── §A10.1 — Dossier Section ──────────────────────────────
class DossierSection(BaseModel):
    """A single section within a Decision Dossier."""

    section_id: str = Field(default_factory=_uuid, description="Unique section identifier (§3.5)")
    section_type: str = Field(
        ...,
        description="objective | constraints | evidence_summary | ranked_findings | "
                    "contradictions | assumptions | recommendations | provenance_appendix | export_metadata",
    )
    title: str = ""
    body_markdown: str = ""
    body_md: str = Field("", description="Spec §3.5 alias for body_markdown")
    linked_evidence_ids: List[str] = Field(default_factory=list)
    linked_run_ids: List[str] = Field(default_factory=list)


# ── Dossier ────────────────────────────────────────────────
class Dossier(BaseModel):
    """The canonical Decision Dossier — the primary output artifact.

    §A10: Must contain Objective, Constraints, Evidence Summary,
    Ranked Options, Contradictions, Assumptions, Recommendations,
    Provenance Appendix, and Export Metadata.
    """

    dossier_id: str = Field(default_factory=_uuid)
    project_id: str
    title: str
    objective: str = ""
    sections: List[DossierSection] = Field(default_factory=list)
    mav_consensus_trace: Dict[str, Any] = Field(
        default_factory=dict,
        description="MAV voting results for every claim (§22.5)",
    )
    provenance_appendix: Dict[str, Any] = Field(
        default_factory=dict,
        description="Complete source list, retrieval timestamps, API responses",
    )
    body_s3_key: str = Field("", description="L3 archive reference for heavy body")
    created_at: str = Field(default_factory=_now_iso)
    exported_at: Optional[str] = None


class DossierCreate(BaseModel):
    """Payload for creating a new dossier."""

    project_id: str
    title: str
    objective: str = ""


# ── Report ─────────────────────────────────────────────────
class Report(BaseModel):
    """A generated report (PDF/DOCX/JSON)."""

    report_id: str = Field(default_factory=_uuid)
    project_id: str
    report_type: str = Field(..., description="summary | detailed | custom")
    title: str
    status: str = Field("draft", description="draft | generating | ready | failed")
    body: Dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: str = Field(default_factory=_now_iso)


# ── Export Job (§71) ───────────────────────────────────────
class ExportJob(BaseModel):
    """An export request for any project artifact."""

    export_id: str = Field(default_factory=_uuid)
    project_id: str
    object_type: str = Field(..., description="dossier | report | evidence | ranking | graph")
    object_id: str
    export_format: str = Field(
        ..., description="pdf | docx | json | csv | sdf | pdb | png | svg | fasta"
    )
    status: str = Field("pending", description="pending | rendering | ready | failed")
    file_ref: str = Field("", description="S3 key or local path to generated file")
    created_by: str
    created_at: str = Field(default_factory=_now_iso)


# ── Media Artifact ─────────────────────────────────────────
class MediaArtifact(BaseModel):
    """A media artifact (figure, chart, structure rendering)."""

    artifact_id: str = Field(default_factory=_uuid)
    project_id: str
    run_id: Optional[str] = None
    artifact_type: str = Field(..., description="figure | chart | structure | graph_snapshot")
    title: str
    file_ref: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)
