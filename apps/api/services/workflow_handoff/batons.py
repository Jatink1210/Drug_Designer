"""Workflow Handoff Batons (§41, FR-SUB-006).

Typed Pydantic transfer objects ("batons") passed between pipeline modules.
Each baton encodes: what data is being handed, from where, to where, and
a full provenance + timing trail so any module can audit its input.

Usage::

    baton = TargetBaton(
        run_id="abc123",
        project_id="proj1",
        source_module="research_engine",
        target_module="target_scorer",
        payload={"gene_symbols": ["BRCA1", "TP53"]},
        provenance={"query_id": "q1", "sources": ["opentargets"]},
        timing={"started_at": "2024-01-01T00:00:00Z"},
        trace_id="trace-xyz",
    )
    await log_baton_transfer(baton)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field, field_validator

log = structlog.get_logger(__name__)


# ── Base baton ────────────────────────────────────────────────────────────────

class WorkflowBaton(BaseModel):
    """Base class for all pipeline baton transfers (§41.2)."""

    run_id: str = Field(..., description="Unique run identifier")
    project_id: str = Field(..., description="Project context")
    source_module: str = Field(..., description="Emitting module name")
    target_module: str = Field(..., description="Receiving module name")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Module-specific data")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Data lineage / sources used")
    timing: Dict[str, Any] = Field(default_factory=dict, description="Timestamps and durations")
    trace_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Distributed trace ID for correlation",
    )
    baton_type: str = Field(default="base", description="Discriminator for baton subtype")
    schema_version: str = Field(default="1.0")

    @field_validator("run_id", "project_id", "source_module", "target_module")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field must be a non-empty string")
        return v.strip()

    def with_elapsed(self) -> "WorkflowBaton":
        """Stamp timing.elapsed_ms based on started_at if present."""
        started = self.timing.get("started_at")
        if started:
            try:
                t0 = datetime.fromisoformat(started.replace("Z", "+00:00"))
                elapsed = (datetime.now(tz=timezone.utc) - t0).total_seconds() * 1000
                self.timing["elapsed_ms"] = round(elapsed, 1)
            except Exception:
                pass
        return self


# ── Specialised batons ────────────────────────────────────────────────────────

class ResearchBaton(WorkflowBaton):
    """Baton from initial research phase → downstream modules (§41.3)."""

    baton_type: str = "research"

    # payload fields (typed for clarity; can also be accessed via .payload)
    disease_query: str = Field(default="", description="Original disease / query string")
    literature_items: List[Dict[str, Any]] = Field(default_factory=list)
    gwas_hits: List[Dict[str, Any]] = Field(default_factory=list)
    search_strategies_used: List[str] = Field(default_factory=list)
    degraded_sources: List[str] = Field(default_factory=list)


class TargetBaton(WorkflowBaton):
    """Baton from target discovery / ranking → downstream modules (§41.4)."""

    baton_type: str = "target"

    gene_symbols: List[str] = Field(default_factory=list, description="Ranked gene symbols")
    composite_scores: Dict[str, float] = Field(
        default_factory=dict, description="symbol → composite UCB score"
    )
    signal_breakdown: Dict[str, Dict[str, float]] = Field(
        default_factory=dict, description="symbol → {signal_name: value}"
    )
    indian_population_relevant: bool = Field(
        default=False, description="Whether Indian-population boost was applied"
    )


class EvidenceBaton(WorkflowBaton):
    """Baton from evidence retrieval → dossier / analysis (§41.5)."""

    baton_type: str = "evidence"

    bundle_id: Optional[str] = Field(default=None)
    evidence_items: List[Dict[str, Any]] = Field(default_factory=list)
    source_footprint: List[str] = Field(default_factory=list)
    confidence_distribution: Dict[str, float] = Field(default_factory=dict)
    contradictions: List[Dict[str, Any]] = Field(default_factory=list)


class DesignBaton(WorkflowBaton):
    """Baton from molecule design (PPO) → validation / dossier (§41.6)."""

    baton_type: str = "design"

    seed_smiles: str = Field(default="")
    top_candidates: List[Dict[str, Any]] = Field(
        default_factory=list, description="Top-K molecules [{smiles, reward, admet, ...}]"
    )
    target_id: str = Field(default="")
    episodes_completed: int = Field(default=0)
    ppo_metrics: List[Dict[str, float]] = Field(default_factory=list)


class TranslationalBaton(WorkflowBaton):
    """Baton from translational analysis → clinical reporting (§41.7)."""

    baton_type: str = "translational"

    clinical_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    admet_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    population_context: str = Field(default="global")
    trial_eligibility_score: Optional[float] = Field(default=None)
    regulatory_flags: List[str] = Field(default_factory=list)


class DossierBaton(WorkflowBaton):
    """Baton to dossier builder — final assembly stage (§41.8)."""

    baton_type: str = "dossier"

    dossier_id: Optional[str] = Field(default=None)
    sections_requested: List[str] = Field(default_factory=list)
    output_format: str = Field(default="json")  # "json" | "html" | "pdf"
    include_provenance: bool = Field(default=True)
    research_baton_id: Optional[str] = Field(default=None)
    target_baton_id: Optional[str] = Field(default=None)
    evidence_baton_id: Optional[str] = Field(default=None)
    design_baton_id: Optional[str] = Field(default=None)


# ── Validation and transfer logging ──────────────────────────────────────────

def validate_baton(baton: WorkflowBaton) -> WorkflowBaton:
    """Validate baton schema and enrich timing (§41.9).

    Raises ``ValueError`` if required fields are missing or invalid.
    Returns the baton (possibly mutated with elapsed_ms).
    """
    if not baton.run_id:
        raise ValueError("Baton missing run_id")
    if not baton.project_id:
        raise ValueError("Baton missing project_id")
    if baton.source_module == baton.target_module:
        raise ValueError(
            f"source_module and target_module are identical: {baton.source_module!r}"
        )
    return baton.with_elapsed()


async def log_baton_transfer(baton: WorkflowBaton) -> None:
    """Log baton transfer with structured fields including trace_id (§41.9).

    Emits at INFO level. Also persists to Redis trace store when available.
    """
    log.info(
        "baton_transfer",
        baton_type=baton.baton_type,
        run_id=baton.run_id,
        project_id=baton.project_id,
        source_module=baton.source_module,
        target_module=baton.target_module,
        trace_id=baton.trace_id,
        elapsed_ms=baton.timing.get("elapsed_ms"),
        payload_keys=list(baton.payload.keys()),
        schema_version=baton.schema_version,
    )

    # Best-effort trace persistence in Redis (TTL 24h)
    try:
        from core.redis_client import get_redis_client
        import json as _json

        redis = await get_redis_client()
        key = f"baton_trace:{baton.trace_id}"
        await redis.setex(
            key,
            86400,  # 24h TTL
            _json.dumps({
                "baton_type": baton.baton_type,
                "run_id": baton.run_id,
                "project_id": baton.project_id,
                "source_module": baton.source_module,
                "target_module": baton.target_module,
                "trace_id": baton.trace_id,
                "timing": baton.timing,
                "schema_version": baton.schema_version,
            }),
        )
    except Exception:
        pass  # Redis unavailable; logging already captured above
