"""Run & Job models (Drug Designer §23, §41).

Every serious action in Drug Designer becomes a tracked Run with artifacts,
logs, diagnostics, and proof of completion. Runs are persistent, evented,
and replayable.

Lifecycle: CREATED → QUEUED → RUNNING → [PARTIAL_SUCCESS | SUCCESS | FAILED | CANCELLED | TIMED_OUT]
"""

from __future__ import annotations

import uuid
import time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── §23.3 — Run State Machine ──────────────────────────────
class RunState(str, Enum):
    """All possible run states. No other states are allowed."""

    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


# ── §23.2 — Run Types ──────────────────────────────────────
class RunType(str, Enum):
    """Enumeration of all run types supported by the platform."""

    RETRIEVAL_FAST = "retrieval.fast"
    RETRIEVAL_DEEP = "retrieval.deep"
    DISEASE_INTELLIGENCE = "disease.intelligence"
    TARGET_RANKING = "target.ranking"
    GRAPH_ENRICHMENT = "graph.enrichment"
    PICO_EXTRACTION = "pico.extraction"
    MOLECULE_GENERATION = "molecule.generation"
    ADMET_BATCH = "admet.batch"
    RETROSYNTHESIS_PLAN = "retrosynthesis.plan"
    DOSSIER_GENERATION = "dossier.generation"
    EXPORT_RENDER = "export.render"
    SCENARIO_SIMULATION = "scenario.simulation"
    RUNTIME_LOCAL_DISPATCH = "runtime.local_dispatch"


# ── §23.4 — Run Contract (every run stores these) ──────────
class RunTimingInfo(BaseModel):
    """Per-stage timing breakdown for a run."""

    total_ms: int = 0
    per_stage: Dict[str, int] = Field(default_factory=dict)


class DegradedInfo(BaseModel):
    """Tracks which sources failed and why."""

    reason: Optional[str] = None
    affected_sources: List[str] = Field(default_factory=list)


class RunProvenance(BaseModel):
    """Provenance metadata for a completed run (§A4.3)."""

    sources_attempted: int = 0
    sources_queried: int = 0
    sources_succeeded: int = 0
    contradictions_found: int = 0
    evidence_coverage: Optional[str] = Field(None, description="Percentage of target sources that returned data, e.g. '74%'")


class RunRecord(BaseModel):
    """The canonical Run object stored in PostgreSQL for every tracked operation.

    §23.5: Each run isolates runtime context, selected model, source footprint,
    timing, and errors. Runs are persistent, evented, and replayable.
    """

    run_id: str = Field(default_factory=_uuid)
    run_type: str = Field(..., description="e.g. 'disease.intelligence'")
    module_name: str = Field("", description="Spec §3.3 alias for run_type (e.g. 'disease_intelligence')")
    project_id: str = Field(..., description="Owning project UUID")
    state: RunState = Field(RunState.CREATED)
    status: str = Field("", description="Spec §3.3 status alias — mirrors state as lowercase")
    created_at: str = Field(default_factory=_now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    completed_at: Optional[str] = None
    summary: Optional[str] = Field(None, description="Spec §3.3 — human-readable run summary")
    runtime_context: Dict[str, Any] = Field(
        default_factory=lambda: {"mode": "hosted", "model_id": None, "hardware": None},
        description="Runtime mode, model, hardware used",
    )
    source_footprint: List[str] = Field(
        default_factory=list,
        description="List of source names queried during this run",
    )
    timing: RunTimingInfo = Field(default_factory=RunTimingInfo)
    input_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Frozen copy of input parameters for reproducibility",
    )
    output_artifacts: List[str] = Field(
        default_factory=list,
        description="UUIDs of artifacts produced by this run",
    )
    logs: List[str] = Field(
        default_factory=list,
        description="Log entry IDs associated with this run",
    )
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    degraded: DegradedInfo = Field(default_factory=DegradedInfo)
    provenance: RunProvenance = Field(default_factory=RunProvenance)


# ── Job (§92 — ARQ background job tracking) ────────────────
class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class JobRecord(BaseModel):
    """Tracks an ARQ background job linked to a run."""

    job_id: str = Field(default_factory=_uuid)
    run_id: str = Field(..., description="Parent run UUID")
    queue_name: str = Field(..., description="ARQ queue name, e.g. 'disease.intelligence'")
    status: JobState = Field(JobState.PENDING)
    payload: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None
    retries: int = 0
    created_at: str = Field(default_factory=_now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


# ── §57 — WebSocket Event (run progress) ───────────────────
class RunEvent(BaseModel):
    """WebSocket event sent from server to client during run execution.

    Event types (§57.3): run.progress, run.stage_complete, run.error,
    run.paused, run.complete
    """

    event: str = Field(
        ..., description="run.progress | run.stage_complete | run.error | run.paused | run.complete"
    )
    run_id: str
    timestamp: str = Field(default_factory=_now_iso)
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="stage, progress_pct, message, sources_completed, etc.",
    )
