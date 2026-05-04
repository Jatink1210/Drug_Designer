"""Source & Connector models (Drug Designer §17, §62).

The application uses 140+ free API connectors. Each source must track
health, last successful request, error rate, and rate limit status.
Circuit breaker pattern is per-connector (§62).
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


# ── Source Registry ────────────────────────────────────────
class Source(BaseModel):
    """A registered external data source in the platform."""

    source_id: str = Field(default_factory=_uuid)
    source_name: str = Field(..., description="e.g. PubMed, OpenTargets")
    source_family: str = Field(
        ..., description="literature | disease | target | pathway | compound | genetics | clinical"
    )
    source_type: str = Field(..., description="api | database | scrape")
    access_mode: str = Field("public", description="public | free_key | paid")
    requires_key: bool = False
    homepage_url: str = ""
    status: str = Field("active", description="active | degraded | down | disabled")
    notes: str = ""


# ── Source Health (§62, §A9) ───────────────────────────────
class SourceHealth(BaseModel):
    """Point-in-time health check for a source connector."""

    source_id: str
    checked_at: str = Field(default_factory=_now_iso)
    status: str = Field("healthy", description="healthy | degraded | down")
    latency_ms: Optional[int] = None
    error_rate: float = 0.0
    degraded_reason: Dict[str, Any] = Field(default_factory=dict)


# ── §62.1 — Circuit Breaker State ──────────────────────────
class CircuitBreakerState(BaseModel):
    """Per-connector circuit breaker tracking."""

    connector_name: str
    state: str = Field("closed", description="closed | open | half_open")
    failure_count: int = 0
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 300
    last_failure_time: Optional[float] = None


# ── Connector Result (§33 contract) ────────────────────────
class ConnectorResult(BaseModel):
    """Standardized result envelope returned by any connector query.

    §33: Every connector must return a ConnectorResult that preserves
    source identity, provenance, normalization schema, and health semantics.
    """

    result_id: str = Field(default_factory=_uuid)
    source_id: str = Field(..., description="Source that produced this result")
    source_name: str = ""
    query: str = Field("", description="The query that was executed")
    status: str = Field("success", description="success | partial | error | rate_limited")
    record_count: int = 0
    records: List[Dict[str, Any]] = Field(default_factory=list, description="Normalized result records")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="timestamp, query_params, api_version")
    rate_limit_info: Optional[Dict[str, Any]] = Field(None, description="Remaining quota, retry-after")
    latency_ms: Optional[int] = None
    error_detail: Optional[str] = None
    retrieved_at: str = Field(default_factory=_now_iso)


# ── §A9.1 — Rate Limit Config ──────────────────────────────
class RateLimitConfig(BaseModel):
    """Rate limit configuration for a connector."""

    connector_name: str
    requests_per_second: int = 5
    burst: int = 10
