"""Universal Response Envelope & Error Model (Drug Designer §78, §93).

Every REST API response MUST wrap its payload in this envelope to guarantee
provenance, runtime context, timing, and truthful error visibility.

No endpoint may return bare `data`. No endpoint may return `status: ok`
when it has not performed real scientific work.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _request_id() -> str:
    return f"req_{uuid.uuid4().hex[:16]}"


def _trace_id() -> str:
    return f"trace_{uuid.uuid4().hex[:16]}"


# ── §93.3 — Universal Error Model ──────────────────────────
class APIError(BaseModel):
    """Structured error — backend must NEVER throw raw 500 tracebacks to UI."""

    code: str = Field(
        ..., description="Machine-readable error code, e.g. SOURCE_TIMEOUT"
    )
    message: str = Field(
        ..., description="Scientific description of failure"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured details (source, timeout_ms, etc.)",
    )
    recoverable: bool = Field(
        True, description="Whether the user can retry or work around"
    )
    suggested_action: str = Field(
        "", description="Human-readable remediation guidance"
    )


# ── §78.1 — Provenance Sub-Object ──────────────────────────
class ProvenanceInfo(BaseModel):
    """Source lineage for every response."""

    sources: List[str] = Field(
        default_factory=list,
        description="List of external sources queried",
    )
    generated_at: str = Field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        description="ISO 8601 timestamp of generation",
    )
    model_id: Optional[str] = Field(
        None, description="Model used for inference, if any"
    )
    runtime_mode: str = Field(
        "hosted", description="hosted | local"
    )
    run_id: Optional[str] = Field(
        None, description="Associated run ID, if part of a tracked run"
    )


# ── §78.1 — Runtime Context Sub-Object ─────────────────────
class RuntimeContext(BaseModel):
    """Always tells the user what runtime executed the work."""

    mode: str = Field("hosted", description="hosted | local | auto")
    selected_runtime: str = Field("", description="Backend/runtime name")
    selected_model: str = Field("", description="Model ID or name")
    fallback_used: bool = Field(
        False, description="True if system fell back from local to hosted"
    )


# ── §78.1 — Timing Sub-Object ──────────────────────────────
class TimingInfo(BaseModel):
    """Response timing — aids performance monitoring and SLA enforcement."""

    started_at: str = Field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    finished_at: str = Field("")
    elapsed_ms: int = Field(0)


# ── §78.1 — Universal Response Envelope ────────────────────
class ResponseEnvelope(BaseModel):
    """The standard wrapper for ALL REST API responses in Drug Designer.

    Usage in routers:
        return ResponseEnvelope(
            status="ok",
            data={"targets": ranked_list},
            provenance=ProvenanceInfo(sources=["pubmed", "opentargets"]),
        )
    """

    request_id: str = Field(default_factory=_request_id)
    trace_id: str = Field(default_factory=_trace_id)
    status: str = Field(
        "ok",
        description="ok | partial | degraded | blocked | error",
    )
    data: Any = Field(
        None, description="Primary response payload"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal warnings (degraded sources, stale data, etc.)",
    )
    errors: List[APIError] = Field(
        default_factory=list,
        description="Structured errors if status is 'error'",
    )
    provenance: ProvenanceInfo = Field(
        default_factory=ProvenanceInfo,
        description="Source lineage and generation metadata",
    )
    runtime_context: RuntimeContext = Field(
        default_factory=RuntimeContext,
        description="Which runtime executed this request",
    )
    timing: TimingInfo = Field(
        default_factory=TimingInfo,
        description="Request timing for SLA monitoring",
    )


# ── §70 — Pagination Sub-Object ────────────────────────────
class PaginationInfo(BaseModel):
    """Cursor-based pagination for all list endpoints.

    Default page_size: 50, max: 200.
    Cursor is opaque base64-encoded token (not a page number).
    """

    cursor: Optional[str] = Field(None, description="Opaque cursor token")
    has_more: bool = Field(False)
    total_count: Optional[int] = Field(None)
    page_size: int = Field(50)


class PaginatedEnvelope(ResponseEnvelope):
    """ResponseEnvelope extended with pagination for list endpoints."""

    pagination: PaginationInfo = Field(default_factory=PaginationInfo)


# ── Shared Envelope Builder ─────────────────────────────────
# All routers SHOULD import this instead of writing ad-hoc _build_envelope helpers.

def build_envelope(
    request,  # fastapi.Request
    data: Any,
    *,
    status: str = "ok",
    warnings: List[str] | None = None,
    errors: List[Dict[str, Any]] | None = None,
    provenance: Dict[str, Any] | None = None,
    runtime_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a spec-compliant response envelope (§78.1).

    Includes request_id, trace_id, runtime_context, provenance, and timing
    — fields that ad-hoc router helpers often omit.
    """
    return {
        "request_id": request.headers.get("X-Request-ID", _request_id()),
        "trace_id": request.headers.get("X-Request-ID", _trace_id()),
        "status": status,
        "data": data,
        "warnings": warnings or [],
        "errors": errors or [],
        "provenance": provenance or {
            "sources": [],
            "sources_queried": [],
            "sources_succeeded": [],
            "sources_degraded": [],
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "runtime_mode": "hosted",
        },
        "runtime_context": runtime_context or {"mode": "hosted", "selected_runtime": "", "selected_model": "", "fallback_used": False},
        "timing": {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "elapsed_ms": 0},
    }
