"""Cockpit dashboard endpoints (§9.3 Endpoint Catalog, §133).

GET  /api/v1/cockpit/summary         — aggregated dashboard view
GET  /api/v1/cockpit/open-actions    — pending actions for current user
GET  /api/v1/cockpit/recent-runs     — recent run list
GET  /api/v1/cockpit/runtime-health  — runtime health status
GET  /api/v1/cockpit/source-health   — source health list
POST /api/v1/cockpit/analyze         — agentic full-analysis (search + summary)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, List, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.db import AsyncSessionLocal, get_db
from models.envelope import build_envelope
from models.db_tables import CockpitRun
from routers.auth import get_current_user
from core.websocket_manager import get_ws_manager
from services.runtime.policy import get_runtime_policy

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/cockpit", tags=["Cockpit"])
_cockpit_background_tasks: set[asyncio.Task[Any]] = set()


COCKPIT_LATENCY_BUDGET = {
    "version": "2026-05-04.phase1",
    "ack_ms": 1500,
    "first_progress_ms": 5000,
    "sync_soft_timeout_ms": 60000,
    "poll_interval_ms": 2000,
    "default_ui_execution_mode": "background",
}

_TARGET_GUARD_QUERY_TYPES = {
    "target_prioritization", "target_discovery_lab", "knowledge_graph",
    "translation_research", "translational_pico", "disease_intelligence",
    "evidence_retrieval",
}
_PATHWAY_GUARD_QUERY_TYPES = {
    "knowledge_graph", "translation_research", "translational_pico",
    "target_prioritization", "disease_intelligence", "evidence_retrieval",
}


def _ensure_non_empty_llm_contradictions(
    papers: List[Dict[str, Any]],
    llm_contradictions: List[Dict[str, Any]],
    contradictions_detail: List[Dict[str, Any]],
    runtime_diagnostics: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], bool]:
    """Guard against silent empty contradiction sections when literature evidence exists."""
    if llm_contradictions or not papers:
        return llm_contradictions, False

    if contradictions_detail:
        first = contradictions_detail[0]
        return ([{
            "relationship": "Heuristic contradiction fallback",
            "claim_a": first.get("claim_a", ""),
            "claim_b": first.get("claim_b", ""),
            "source_a": first.get("source_a", {}),
            "source_b": first.get("source_b", {}),
            "reason": "LLM contradiction verification was unavailable or returned no verified pairs; using the strongest heuristic contradiction instead.",
            "severity": first.get("severity", "moderate"),
            "context_a": first.get("context_a", {}),
            "context_b": first.get("context_b", {}),
            "llm_verified": False,
            "fallback_mode": True,
            "runtime_diagnostics": runtime_diagnostics,
            "explanation": first.get("explanation", "Heuristic contradiction fallback was used."),
        }], True)

    return ([{
        "relationship": "No verified contradictions found",
        "claim_a": "",
        "claim_b": "",
        "source_a": {},
        "source_b": {},
        "reason": "Literature contradiction analysis completed, but no contradictory paper pairs met the verification threshold.",
        "severity": "low",
        "context_a": {},
        "context_b": {},
        "llm_verified": False,
        "fallback_mode": True,
        "runtime_diagnostics": runtime_diagnostics,
        "explanation": "Treat this as completed contradiction analysis with no verified pairs, not a missing section.",
    }], True)


def _build_quality_guards(
    query_type: str,
    target_ranking: List[Dict[str, Any]],
    pathways_data: List[Dict[str, Any]],
    llm_contradictions: List[Dict[str, Any]],
    contradiction_guard_applied: bool,
) -> Dict[str, Any]:
    """Surface minimum-output guards so thin results are explicit in diagnostics."""
    target_minimum = 3 if query_type in _TARGET_GUARD_QUERY_TYPES else 0
    pathway_minimum = 1 if query_type in _PATHWAY_GUARD_QUERY_TYPES else 0

    return {
        "targets": {
            "count": len(target_ranking),
            "minimum_expected": target_minimum,
            "status": "pass" if len(target_ranking) >= target_minimum else "degraded",
            "guard_applied": target_minimum > 0,
        },
        "pathways": {
            "count": len(pathways_data),
            "minimum_expected": pathway_minimum,
            "status": "pass" if len(pathways_data) >= pathway_minimum else "degraded",
            "guard_applied": pathway_minimum > 0,
        },
        "llm_contradictions": {
            "count": len(llm_contradictions),
            "minimum_expected": 1 if contradiction_guard_applied else 0,
            "status": "pass" if llm_contradictions else "degraded",
            "guard_applied": contradiction_guard_applied,
        },
    }


def _annotate_literature_llm_diagnostics(
    llm_contradictions: List[Dict[str, Any]],
    runtime_diagnostics: Dict[str, Any],
) -> Dict[str, Any]:
    """Mark heuristic-only contradiction results as explicit fallback mode."""
    if not llm_contradictions or any(item.get("llm_verified") for item in llm_contradictions):
        return runtime_diagnostics

    updated = dict(runtime_diagnostics or {})
    fallbacks = list(updated.get("fallbacks") or [])
    if "llm_contradictions_heuristic_only" not in fallbacks:
        fallbacks.append("llm_contradictions_heuristic_only")
    updated["fallbacks"] = fallbacks
    updated["contradictions_mode"] = "heuristic_fallback"
    return updated


# ── Response schemas ───────────────────────────────────────

class RunBrief(BaseModel):
    run_id: str
    module_name: str = ""
    state: str = "CREATED"
    created_at: str = ""


class CockpitQueuedRun(BaseModel):
    run_id: str
    status: str
    created_at: str = ""
    updated_at: str = ""
    stream_channel: str = ""
    poll_after_ms: int = COCKPIT_LATENCY_BUDGET["poll_interval_ms"]
    latency_budget: Dict[str, Any] = Field(default_factory=lambda: dict(COCKPIT_LATENCY_BUDGET))


class SourceHealthBrief(BaseModel):
    source_name: str
    status: str = "healthy"
    latency_ms: Optional[int] = None


class RuntimeHealthBrief(BaseModel):
    hosted_status: str = "ok"
    local_agent_connected: bool = False
    default_mode: str = "hosted"


class DossierBrief(BaseModel):
    dossier_id: str
    title: str = ""
    status: str = "draft"
    updated_at: str = ""


class CockpitSummary(BaseModel):
    """§9.3: Cockpit summary payload."""
    recent_runs: List[RunBrief] = Field(default_factory=list)
    open_exports: int = 0
    source_health: List[SourceHealthBrief] = Field(default_factory=list)
    runtime_health: RuntimeHealthBrief = Field(default_factory=RuntimeHealthBrief)
    recent_dossiers: List[DossierBrief] = Field(default_factory=list)
    recent_reports: int = 0
    dlq_count: int = 0  # A4: total dead-letter items across all queues


class ActionItem(BaseModel):
    action_type: str  # failed_run | degraded_source | dossier_review | agent_issue
    title: str
    detail: str = ""
    related_id: str = ""


class CockpitActions(BaseModel):
    """§9.3: Pending actions payload."""
    pending_actions: List[ActionItem] = Field(default_factory=list)
    failed_runs: List[RunBrief] = Field(default_factory=list)
    degraded_sources: List[SourceHealthBrief] = Field(default_factory=list)
    dossiers_needing_review: List[DossierBrief] = Field(default_factory=list)
    local_agent_issues: List[str] = Field(default_factory=list)


# ── Endpoints ──────────────────────────────────────────────

@router.get("/summary")
async def cockpit_summary(request: Request, user=Depends(get_current_user)) -> Dict[str, Any]:
    """Return aggregated cockpit summary (§9.3).

    Aggregates recent runs, open exports, source health, runtime health,
    recent dossiers/reports for the current project context.
    """
    from core.db import AsyncSessionLocal
    summary = CockpitSummary()

    try:
        from sqlalchemy import select, desc, func
        from models.db_tables import Run, Source, SourceHealthRecord, DossierRecord

        async with AsyncSessionLocal() as session:
            # Recent runs (last 10)
            result = await session.execute(
                select(Run).order_by(desc(Run.created_at)).limit(10)
            )
            runs = result.scalars().all()
            summary.recent_runs = [
                RunBrief(
                    run_id=r.id,
                    module_name=getattr(r, "module_name", "") or r.run_type or "",
                    state=r.state or "CREATED",
                    created_at=str(r.created_at) if r.created_at else "",
                )
                for r in runs
            ]

            # Source health (latest per source)
            result = await session.execute(
                select(Source).limit(20)
            )
            sources = result.scalars().all()
            summary.source_health = [
                SourceHealthBrief(
                    source_name=s.source_name,
                    status=s.status or "active",
                )
                for s in sources
            ]

            # Recent dossiers
            result = await session.execute(
                select(DossierRecord).order_by(desc(DossierRecord.created_at)).limit(5)
            )
            dossiers = result.scalars().all()
            summary.recent_dossiers = [
                DossierBrief(
                    dossier_id=d.id,
                    title=d.title or "",
                    status=getattr(d, "status", "draft") or "draft",
                    updated_at=str(getattr(d, "updated_at", d.created_at) or ""),
                )
                for d in dossiers
            ]

    except Exception:
        pass  # Return empty summary if DB not available

    # A4: DLQ count from Redis
    try:
        from redis import asyncio as aioredis
        from config import settings as _cfg
        _rc = await aioredis.from_url(_cfg.redis_url, decode_responses=True)
        keys = await _rc.keys("dlq:*")
        total = 0
        if keys:
            lengths = await _rc.execute_command("LLEN", keys[0]) if len(keys) == 1 else None
            if lengths is None:
                pipe = _rc.pipeline()
                for k in keys:
                    pipe.llen(k)
                lengths = await pipe.execute()
                total = sum(lengths)
            else:
                total = lengths
        await _rc.aclose()
        summary.dlq_count = total
    except Exception:
        pass  # Redis not available — dlq_count stays 0

    return build_envelope(request, summary.model_dump())


@router.get("/open-actions")
async def cockpit_open_actions(request: Request, user=Depends(get_current_user)) -> Dict[str, Any]:
    """Return pending actions for current user (§133).

    Surfaces failed runs, degraded source alerts, dossiers needing review,
    and local agent issues.
    """
    actions = CockpitActions()

    try:
        from sqlalchemy import select, desc
        from models.db_tables import Run, Source, DossierRecord
        from core.db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # Failed runs
            result = await session.execute(
                select(Run).where(Run.state == "FAILED").order_by(desc(Run.created_at)).limit(10)
            )
            failed = result.scalars().all()
            actions.failed_runs = [
                RunBrief(
                    run_id=r.id,
                    module_name=getattr(r, "module_name", "") or r.run_type or "",
                    state="FAILED",
                    created_at=str(r.created_at) if r.created_at else "",
                )
                for r in failed
            ]

            # Degraded sources
            result = await session.execute(
                select(Source).where(Source.status.in_(["degraded", "down"]))
            )
            degraded = result.scalars().all()
            actions.degraded_sources = [
                SourceHealthBrief(
                    source_name=s.source_name,
                    status=s.status,
                )
                for s in degraded
            ]

            # Dossiers needing review (status = 'draft' or 'review')
            result = await session.execute(
                select(DossierRecord).where(
                    DossierRecord.status.in_(["draft", "review"])
                ).order_by(desc(DossierRecord.created_at)).limit(5)
            )
            review_dossiers = result.scalars().all()
            actions.dossiers_needing_review = [
                DossierBrief(
                    dossier_id=d.id,
                    title=d.title or "",
                    status=getattr(d, "status", "draft") or "draft",
                )
                for d in review_dossiers
            ]

            # Build action items from above
            for r in actions.failed_runs:
                actions.pending_actions.append(ActionItem(
                    action_type="failed_run",
                    title=f"Run {r.run_id[:8]}… failed",
                    detail=r.module_name,
                    related_id=r.run_id,
                ))
            for s in actions.degraded_sources:
                actions.pending_actions.append(ActionItem(
                    action_type="degraded_source",
                    title=f"Source {s.source_name} is {s.status}",
                    related_id=s.source_name,
                ))
            for d in actions.dossiers_needing_review:
                actions.pending_actions.append(ActionItem(
                    action_type="dossier_review",
                    title=f"Dossier '{d.title}' needs review",
                    related_id=d.dossier_id,
                ))

    except Exception:
        pass

    return build_envelope(request, actions.model_dump())


# ── §133 Additional standalone endpoints ──────────────────

@router.get("/recent-runs")
async def cockpit_recent_runs(
    request: Request,
    user=Depends(get_current_user),
    limit: int = 10,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return recent cockpit analysis runs (§133, Task 1.4)."""
    runs: List[Dict[str, Any]] = []
    try:
        from sqlalchemy import desc, select

        result = await db.execute(
            select(CockpitRun)
            .order_by(desc(CockpitRun.created_at))
            .offset(offset)
            .limit(limit)
        )
        for r in result.scalars().all():
            runs.append({
                "run_id": r.id,
                "query": r.query or "",
                "status": r.status or "pending",
                "created_at": str(r.created_at) if r.created_at else "",
                "updated_at": str(r.updated_at) if r.updated_at else "",
                "result_summary": r.result_summary,
                "error_message": r.error_message,
                "provenance": r.provenance,
                "stream_channel": f"/ws/runs/{r.id}",
            })
    except Exception:
        try:
            from sqlalchemy import desc, select
            from models.db_tables import Run

            result = await db.execute(
                select(Run).order_by(desc(Run.created_at)).offset(offset).limit(limit)
            )
            for r in result.scalars().all():
                runs.append({
                    "run_id": r.id,
                    "query": getattr(r, "query", "") or "",
                    "status": r.state or "CREATED",
                    "created_at": str(r.created_at) if r.created_at else "",
                    "updated_at": str(getattr(r, "updated_at", r.created_at)) if r.created_at else "",
                    "result_summary": None,
                    "error_message": None,
                    "provenance": {},
                    "stream_channel": f"/ws/runs/{r.id}",
                })
        except Exception as ex:
            log.warning("cockpit_recent_runs_failed", error=str(ex)[:160])

    return build_envelope(request, {"recent_runs": runs, "count": len(runs), "limit": limit, "offset": offset})


@router.get("/runs/{run_id}")
async def cockpit_run_status(
    run_id: str,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return the persisted lifecycle state for a cockpit analysis run."""
    run = await db.get(CockpitRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Cockpit run not found")

    payload = {
        "run_id": run.id,
        "query": run.query,
        "status": run.status,
        "created_at": str(run.created_at) if run.created_at else "",
        "updated_at": str(run.updated_at) if run.updated_at else "",
        "result_summary": run.result_summary,
        "error_message": run.error_message,
        "provenance": run.provenance or {},
        "stream_channel": f"/ws/runs/{run.id}",
        "poll_after_ms": COCKPIT_LATENCY_BUDGET["poll_interval_ms"],
        "is_complete": run.status in {"completed", "failed"},
        "latency_budget": dict(COCKPIT_LATENCY_BUDGET),
    }
    return build_envelope(request, payload)


@router.get("/runtime-health")
async def cockpit_runtime_health(request: Request, user=Depends(get_current_user)) -> Dict[str, Any]:
    """Return runtime health status (§133)."""
    health = RuntimeHealthBrief()
    try:
        from services.runtime.selector import RuntimeSelector
        sel = RuntimeSelector.get_active()
        health.default_mode = sel.get("mode", "hosted")
        health.hosted_status = "ok"
        health.local_agent_connected = sel.get("local_connected", False)
    except Exception:
        pass
    return build_envelope(request, health.model_dump())


@router.get("/source-health")
async def cockpit_source_health(request: Request, user=Depends(get_current_user)) -> Dict[str, Any]:
    """Return comprehensive source health with rolling Redis stats (§133, Task 9.1).

    Returns health data for ALL registered connectors, not just those with recent activity.
    Includes circuit breaker state, latency metrics, and error counts.
    """
    from services.backend_hardening import ALL_CONNECTORS

    sources: List[Dict[str, Any]] = []
    db_sources: Dict[str, Dict[str, Any]] = {}

    # First, get DB-registered sources
    try:
        from sqlalchemy import select
        from models.db_tables import Source
        from core.db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Source).limit(200))
            for s in result.scalars().all():
                db_sources[s.source_name] = {
                    "name": s.source_name,
                    "status": s.status or "unknown",
                    "last_checked": str(getattr(s, "last_checked_at", "")) or "",
                }
    except Exception:
        pass

    # Build entries for ALL registered connectors
    for connector_name in ALL_CONNECTORS:
        if connector_name in db_sources:
            entry = db_sources.pop(connector_name)
        else:
            entry = {
                "name": connector_name,
                "status": "unknown",
                "last_checked": "",
            }
        entry.setdefault("avg_response_ms", None)
        entry.setdefault("p95_response_ms", None)
        entry.setdefault("errors_1h", 0)
        entry.setdefault("ratelimit_hits_1h", 0)
        entry.setdefault("circuit_breaker_state", "closed")
        sources.append(entry)

    # Add any DB sources not in ALL_CONNECTORS
    for name, entry in db_sources.items():
        entry.setdefault("avg_response_ms", None)
        entry.setdefault("p95_response_ms", None)
        entry.setdefault("errors_1h", 0)
        entry.setdefault("ratelimit_hits_1h", 0)
        entry.setdefault("circuit_breaker_state", "closed")
        sources.append(entry)

    # Enrich with circuit breaker state
    try:
        from core.circuit_breaker import CircuitBreakerRegistry
        registry = CircuitBreakerRegistry()
        for entry in sources:
            name = entry.get("name", "")
            cb = registry.get(name)
            if cb:
                entry["circuit_breaker_state"] = cb.state
                if cb.state == "open":
                    entry["status"] = "degraded"
                elif cb.state == "half_open":
                    entry["status"] = "degraded"
    except Exception:
        pass

    # Enrich with rolling health stats from Redis
    try:
        from core.redis_client import get_redis_client
        redis = await get_redis_client()
        for entry in sources:
            name = entry.get("name", "")
            if not name:
                continue
            try:
                latency_raw = await redis.lrange(f"source_health:{name}:latency", 0, -1)
                if latency_raw:
                    lats = [float(x) for x in latency_raw]
                    entry["avg_response_ms"] = round(sum(lats) / len(lats), 1)
                    sorted_lats = sorted(lats)
                    p95_idx = min(int(len(sorted_lats) * 0.95), len(sorted_lats) - 1)
                    entry["p95_response_ms"] = round(sorted_lats[p95_idx], 1)
                err_raw = await redis.get(f"source_health:{name}:errors")
                entry["errors_1h"] = int(err_raw) if err_raw else 0
                rl_raw = await redis.get(f"source_health:{name}:ratelimit_hits")
                entry["ratelimit_hits_1h"] = int(rl_raw) if rl_raw else 0
                # Derive status from error rate if not already set by circuit breaker
                if entry.get("status") not in ("degraded",) and entry.get("errors_1h", 0) >= 10:
                    entry["status"] = "error"
                elif entry.get("status") == "unknown" and entry.get("avg_response_ms") is not None:
                    entry["status"] = "healthy"
            except Exception:
                pass
    except Exception:
        pass

    # Compute summary
    summary = {"total": len(sources), "healthy": 0, "degraded": 0, "error": 0, "unknown": 0}
    for entry in sources:
        status = entry.get("status", "unknown")
        if status in ("healthy", "active", "ok"):
            summary["healthy"] += 1
        elif status == "degraded":
            summary["degraded"] += 1
        elif status == "error":
            summary["error"] += 1
        else:
            summary["unknown"] += 1

    return build_envelope(request, {"sources": sources, "summary": summary, "count": len(sources)})


@router.get("/nav-counts")
async def cockpit_nav_counts(request: Request, user=Depends(get_current_user)) -> Dict[str, Any]:
    """Return sidebar badge counts for the left navigation rail."""
    counts: Dict[str, int] = {}
    try:
        from sqlalchemy import select, func
        from models.db_tables import (
            Run, DiseaseQuery, Source, DossierRecord, TargetRanking,
            DiseaseCandidateGene, ReportRecord,
        )
        from core.db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            r = await session.execute(select(func.count()).select_from(Run))
            counts["runs"] = r.scalar() or 0

            r = await session.execute(select(func.count()).select_from(DiseaseQuery))
            counts["disease_queries"] = r.scalar() or 0

            r = await session.execute(select(func.count()).select_from(Source))
            counts["sources"] = r.scalar() or 0

            r = await session.execute(select(func.count()).select_from(DossierRecord))
            counts["dossiers"] = r.scalar() or 0

            r = await session.execute(select(func.count()).select_from(DiseaseCandidateGene))
            counts["genes"] = r.scalar() or 0

            r = await session.execute(
                select(func.count(func.distinct(TargetRanking.gene_symbol)))
                .select_from(TargetRanking)
            )
            counts["targets"] = r.scalar() or 0

            r = await session.execute(select(func.count()).select_from(ReportRecord))
            counts["reports"] = r.scalar() or 0

    except Exception:
        pass

    # Model catalog count (from static file, not DB)
    try:
        import json, os
        catalog_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "models_catalog.json")
        with open(catalog_path) as f:
            counts["models"] = len(json.load(f))
    except Exception:
        counts["models"] = 0

    return build_envelope(request, counts)


# ── Agentic full-analysis endpoint ────────────────────────

class AnalyzeRequest(BaseModel):
    query: str
    limit: int = 100
    execution_mode: Literal["sync", "background"] = "sync"


def _build_cockpit_run_provenance(
    *,
    query: str,
    execution_mode: str,
    status: str,
    payload: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    provenance: Dict[str, Any] = {
        "query": query,
        "execution_mode": execution_mode,
        "status": status,
        "latency_budget": dict(COCKPIT_LATENCY_BUDGET),
    }
    if payload is not None:
        provenance.update({
            "timings": payload.get("timings", {}),
            "latency_ms": payload.get("latency_ms", 0),
            "degraded_sources": payload.get("degraded_sources", []),
            "query_classification": payload.get("query_classification", {}),
            "search_provenance": payload.get("search_provenance", {}),
        })
    if error_message:
        provenance["error_message"] = error_message
    return provenance

async def _persist_cockpit_run(
    run_id: str,
    *,
    status: str,
    query: Optional[str] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    execution_mode: str,
    session_factory=None,
) -> None:
    factory = session_factory or AsyncSessionLocal
    async with factory() as session:
        run = await session.get(CockpitRun, run_id)
        if run is None:
            return
        run.status = status
        if result_summary is not None:
            run.result_summary = result_summary
        if error_message is not None:
            run.error_message = error_message
        run.provenance = _build_cockpit_run_provenance(
            query=query or run.query,
            execution_mode=execution_mode,
            status=status,
            payload=result_summary,
            error_message=error_message,
        )
        await session.commit()


async def _execute_cockpit_background_run(run_id: str, query: str, limit: int, session_factory=None) -> None:
    ws = get_ws_manager()
    await _persist_cockpit_run(
        run_id,
        status="running",
        query=query,
        execution_mode="background",
        session_factory=session_factory,
    )
    try:
        payload = await _run_cockpit_analysis_payload(
            AnalyzeRequest(query=query, limit=limit, execution_mode="background"),
            run_id=run_id,
            ws=ws,
        )
        await _persist_cockpit_run(
            run_id,
            status="completed",
            query=query,
            result_summary=payload,
            execution_mode="background",
            session_factory=session_factory,
        )
        await ws.emit_complete(run_id, "completed", ["cockpit.result_summary"])
    except Exception as exc:
        error_message = str(exc)
        await _persist_cockpit_run(
            run_id,
            status="failed",
            query=query,
            error_message=error_message,
            execution_mode="background",
            session_factory=session_factory,
        )
        await ws.emit_error(run_id, "cockpit_analysis", error_message, recoverable=True)


def _schedule_cockpit_background_run(run_id: str, query: str, limit: int, session_factory=None) -> None:
    task = asyncio.create_task(_execute_cockpit_background_run(run_id, query, limit, session_factory))
    _cockpit_background_tasks.add(task)
    task.add_done_callback(_cockpit_background_tasks.discard)


# ── Helper: safe parallel execution ──────────────────────

async def _safe(coro, label: str):
    """Run async coro, return (label, result) or (label, None) on error."""
    try:
        return label, await coro
    except Exception as ex:
        log.warning("cockpit_enrichment_failed", step=label, error=str(ex)[:200])
        return label, None


def _sync_safe(fn, label: str):
    """Run sync fn, return (label, result) or (label, None) on error."""
    try:
        return label, fn()
    except Exception as ex:
        log.warning("cockpit_enrichment_failed", step=label, error=str(ex)[:200])
        return label, None


# ── Entity extraction from search results ────────────────

def _extract_entities(categories, query: str = ""):
    """Pull typed entity lists from search category rows.

    Handles all known category names including 'phenotypes' → diseases,
    and extracts genes from targets with uniprot IDs. Filters out
    negative-control / assay-control compounds.
    """
    import re

    genes, proteins, diseases, drugs = [], [], [], []
    smiles_list, structures, trials_list = [], [], []
    pathways_list, publications_list = [], []

    _CONTROL_PAT = re.compile(r"(?i)(negative.?control|positive.?control|dmso|vehicle|blank|assay.?control)")

    for cat in (categories or []):
        cat_name = cat.get("category", "") if isinstance(cat, dict) else getattr(cat, "category", "")
        rows = cat.get("rows", []) if isinstance(cat, dict) else getattr(cat, "rows", [])

        for row in (rows or []):
            name = row.get("name") or row.get("title") or row.get("canonical_name") or row.get("symbol") or row.get("id", "")

            if cat_name in ("genes", "targets"):
                symbol = row.get("symbol") or row.get("gene_symbol") or ""
                cname = row.get("canonical_name") or str(name)
                # Prefer gene symbol; fall back to canonical_name only if it looks
                # like a short gene symbol (≤15 chars, no comma, mostly alnum).
                if not symbol:
                    if len(cname) <= 15 and "," not in cname and cname.replace("-", "").replace("_", "").isalnum():
                        symbol = cname
                    else:
                        # Long protein name → skip as target (not a useful gene symbol)
                        symbol = ""
                if symbol and symbol not in genes:
                    genes.append(symbol)
                # Also extract protein accession from targets
                uniprot = row.get("uniprot") or row.get("uniprot_id") or row.get("accession")
                if uniprot and str(uniprot) not in proteins:
                    proteins.append(str(uniprot))
            elif cat_name == "proteins":
                accession = row.get("accession") or row.get("uniprot_id") or str(name)
                if accession and accession not in proteins:
                    proteins.append(accession)
                # Also harvest gene symbol from protein entries
                gsym = row.get("gene_symbol") or row.get("symbol") or ""
                if gsym and gsym not in genes:
                    genes.append(gsym)
            elif cat_name in ("diseases", "phenotypes"):
                dname = row.get("canonical_name") or row.get("name") or str(name)
                if dname and str(dname) not in diseases:
                    diseases.append(str(dname))
            elif cat_name in ("drugs", "molecules", "compounds"):
                n = str(name)
                # Filter out negative-control / assay artifacts
                if _CONTROL_PAT.search(n):
                    continue
                if n and n not in drugs:
                    drugs.append(n)
                smi = row.get("smiles") or row.get("canonical_smiles")
                if smi and not _CONTROL_PAT.search(n):
                    smiles_list.append(str(smi))
            elif cat_name == "structures":
                pdb = row.get("pdb_id") or row.get("id")
                if pdb:
                    structures.append(str(pdb))
            elif cat_name == "clinical_trials":
                trials_list.append(row)
            elif cat_name == "interactions":
                # Extract gene symbols from interaction endpoints
                for field in ("source_entity", "target_entity"):
                    sym = row.get(field, "")
                    if sym and len(sym) <= 15 and sym.replace("-", "").replace("_", "").isalnum() and sym not in genes:
                        genes.append(sym)
            elif cat_name == "pathways":
                pathways_list.append(row)
            elif cat_name == "publications":
                publications_list.append(row)

    # Fallback: if no diseases extracted, infer from query
    # Only use the first phrase (before comma/period) and cap length
    if not diseases and query:
        fragment = query.split(",")[0].split(".")[0].strip()
        if len(fragment) > 60:
            fragment = " ".join(fragment.split()[:6])
        diseases.append(fragment)

    return {
        "genes": genes[:30],
        "proteins": proteins[:20],
        "diseases": diseases[:10],
        "drugs": drugs[:20],
        "smiles": smiles_list[:10],
        "structures": structures[:10],
        "trials": trials_list[:20],
        "pathways": pathways_list[:30],
        "publications": publications_list[:30],
    }


@router.post("/analyze")
async def cockpit_analyze(
    body: AnalyzeRequest,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    query = body.query.strip()
    if not query:
        return build_envelope(request, {"error": "Query is required"})

    run = CockpitRun(
        query=query,
        status="queued",
        user_id=getattr(user, "id", None),
        provenance=_build_cockpit_run_provenance(
            query=query,
            execution_mode=body.execution_mode,
            status="queued",
        ),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    session_factory = async_sessionmaker(bind=db.bind, expire_on_commit=False) if db.bind is not None else AsyncSessionLocal

    ws = get_ws_manager()
    await ws.emit_progress(run.id, "queued", 5, "Queued cockpit analysis")

    if body.execution_mode == "background":
        await _persist_cockpit_run(
            run.id,
            status="running",
            query=query,
            execution_mode="background",
            session_factory=session_factory,
        )
        _schedule_cockpit_background_run(run.id, query, body.limit, session_factory)
        accepted = CockpitQueuedRun(
            run_id=run.id,
            status="running",
            created_at=str(run.created_at) if run.created_at else "",
            updated_at=str(run.updated_at) if run.updated_at else "",
            stream_channel=f"/ws/runs/{run.id}",
        )
        return build_envelope(request, accepted.model_dump())

    await _persist_cockpit_run(
        run.id,
        status="running",
        query=query,
        execution_mode="sync",
        session_factory=session_factory,
    )
    try:
        payload = await _run_cockpit_analysis_payload(body, run_id=run.id, ws=ws)
        await _persist_cockpit_run(
            run.id,
            status="completed",
            query=query,
            result_summary=payload,
            execution_mode="sync",
            session_factory=session_factory,
        )
        await ws.emit_complete(run.id, "completed", ["cockpit.result_summary"])
        return build_envelope(request, payload)
    except Exception as exc:
        error_message = str(exc)
        await _persist_cockpit_run(
            run.id,
            status="failed",
            query=query,
            error_message=error_message,
            execution_mode="sync",
            session_factory=session_factory,
        )
        await ws.emit_error(run.id, "cockpit_analysis", error_message, recoverable=True)
        raise


async def _run_cockpit_analysis_payload(
    body: AnalyzeRequest,
    *,
    run_id: Optional[str] = None,
    ws=None,
) -> Dict[str, Any]:
    """Agentic cockpit analysis: 18-section canonical report.

    Returns everything the frontend needs to render a comprehensive
    drug-discovery intelligence report:
    §1  Executive header (run metadata)
    §2  Objective restatement
    §3  Agentic execution summary (pipeline steps + timings)
    §4  Entity normalization table
    §5  Evidence acquisition (sources, counts, quality)
    §6  Contradiction analysis (detailed)
    §7  Disease intelligence (disease profile + gene associations)
    §8  Target prioritization (7-signal scores + ranking)
    §9  Graph / pathway reasoning
    §10 Structure / pocket analysis
    §11 Molecule retrieval & ideation
    §12 ADMET / off-target screening
    §13 Retrosynthesis route planning
    §14 Translational / population context
    §15 Next-step program (recommendations)
    §16 Scenario comparison (SynthArena)
    §17 Final recommendation (AI conclusion)
    §18 Provenance appendix (sources, timestamps)
    """
    t0 = time.monotonic()
    run_id = run_id or uuid.uuid4().hex[:12]
    query = body.query.strip()
    if not query:
        return {"error": "Query is required", "run_id": run_id}

    enrichment_errors: List[str] = []
    if ws is not None:
        await ws.emit_progress(run_id, "classification", 10, "Classifying cockpit query")

    # ── Classify query intent ─────────────────────────────
    from services.query_classifier import classify_query, get_search_query, get_summary_prompt_context
    classification = classify_query(query)
    search_query = get_search_query(classification, query)
    log.info("cockpit_query_classified",
             query_type=classification.query_type,
             disease=classification.disease,
             genes=classification.genes,
             cohort=classification.cohort,
             search_query=search_query)
    if ws is not None:
        await ws.emit_progress(run_id, "search", 20, "Searching biomedical sources")

    # ── §1 Run the multi-source search first ──────────────
    from services.search_engine import execute_search
    envelope = await execute_search(search_query, mode="auto", limit=body.limit)

    # ── Gene-specific supplementary search ────────────────
    # For queries mentioning specific genes, run additional
    # gene-focused search if the primary search missed them.
    # Run in parallel for speed.
    gene_search_tasks = []
    if classification.genes and classification.query_type in (
        "uniprot_mapping", "target_prioritization", "structure_pocket",
        "design_studio", "admet", "population_genomics", "syntharena",
        "disease_intelligence", "dossier", "knowledge_graph",
        "target_discovery_lab", "evidence_retrieval", "e2e_program",
        "molecule_lab", "pocket_discovery",
    ):
        for gene in classification.genes[:3]:
            gene_search_tasks.append(_safe(execute_search(gene, mode="auto", limit=30), f"gene_{gene}"))

    if gene_search_tasks:
        gene_results = await asyncio.gather(*gene_search_tasks)
        for label, gene_envelope in gene_results:
            if gene_envelope is None:
                enrichment_errors.append(f"{label}: gene search failed")
                continue
            try:
                for cat_name, cat_result in (gene_envelope.categories or {}).items():
                    if cat_name not in (envelope.categories or {}):
                        envelope.categories[cat_name] = cat_result
                    else:
                        existing = envelope.categories[cat_name]
                        existing_ids = {r.get("id", r.get("name", "")) for r in (existing.rows or [])}
                        for row in (cat_result.rows or []):
                            rid = row.get("id", row.get("name", ""))
                            if rid not in existing_ids:
                                existing.rows.append(row)
                                existing_ids.add(rid)
            except Exception as ex:
                enrichment_errors.append(f"{label}_merge: {str(ex)[:100]}")

    t_search = round((time.monotonic() - t0) * 1000)
    if ws is not None:
        source_count = len((envelope.provenance or {}).get("sources_hit") or [])
        await ws.emit_progress(
            run_id,
            "search",
            35,
            f"Search completed across {source_count} sources",
            sources_completed=source_count,
            sources_total=source_count,
        )

    # ── Build category summaries ──────────────────────────
    category_summaries: List[Dict[str, Any]] = []
    all_entity_names: List[str] = []
    for cat_name, cat_result in (envelope.categories or {}).items():
        rows = cat_result.rows if hasattr(cat_result, "rows") else cat_result.get("rows", [])
        total = cat_result.total if hasattr(cat_result, "total") else cat_result.get("total", 0)
        cols = cat_result.columns if hasattr(cat_result, "columns") else cat_result.get("columns", [])
        top_names = []
        for r in (rows or [])[:5]:
            n = r.get("name") or r.get("title") or r.get("canonical_name") or r.get("id", "")
            top_names.append(str(n)[:80])
            all_entity_names.append(str(n)[:80])
        category_summaries.append({
            "category": cat_name,
            "count": total,
            "columns": cols,
            "rows": rows or [],
            "top_items": top_names,
        })
    category_summaries.sort(key=lambda c: c["count"], reverse=True)

    stats = envelope.summary_stats or {}
    evidence = envelope.evidence_summary or {}

    # ── Extract entities for enrichment ───────────────────
    entities = _extract_entities(category_summaries, query=query)

    # ── Merge classifier-detected entities into enrichment seeds ──
    # The classifier finds genes/disease/pathways from the query text
    # that may not appear in search results. Merge them so enrichment
    # steps always have seed data.
    if classification.genes:
        for g in classification.genes:
            if g not in entities["genes"]:
                entities["genes"].append(g)
    if classification.disease:
        canonical = classification.disease
        if canonical not in entities["diseases"]:
            entities["diseases"].insert(0, canonical)

    # ── Gene discovery for target-centric queries ────────
    # When query type needs gene targets, ensure we have RELEVANT
    # human disease-associated genes (not random search-extracted names).
    # For disease-centric queries without explicit gene mentions,
    # curated seeds replace/supplement search-extracted genes.
    _DISEASE_GENE_SEEDS = {
        "triple-negative breast cancer": ["BRCA1", "BRCA2", "EGFR", "TP53", "PIK3CA", "MYC", "PTEN", "AKT1", "KRAS", "ERBB2"],
        "Type 2 diabetes mellitus": ["PPARG", "KCNJ11", "TCF7L2", "SLC30A8", "MTOR", "INS", "GCK", "HNF1A", "ABCC8", "IRS1"],
        "Alzheimer's disease": ["APOE", "APP", "PSEN1", "PSEN2", "MAPT", "BACE1", "TREM2", "CLU", "BIN1", "SORL1"],
        "non-small cell lung cancer": ["EGFR", "KRAS", "ALK", "ROS1", "BRAF", "MET", "ERBB2", "PIK3CA", "STK11", "KEAP1"],
        "rheumatoid arthritis": ["TNF", "IL6", "JAK2", "IL6R", "CTLA4", "TNFRSF1A", "HLA-DRB1", "STAT3", "NFKB1", "CCL2", "PTPN22", "IL1B"],
        "glioblastoma": ["EGFR", "TP53", "PTEN", "IDH1", "IDH2", "PIK3CA", "PDGFRA", "MGMT", "CDKN2A", "NF1"],
        "ulcerative colitis": ["TNF", "IL23R", "JAK2", "STAT3", "IL10", "NOD2", "IL6", "NFKB1", "HLA-DRB1", "CARD9"],
        "hepatocellular carcinoma": ["TP53", "CTNNB1", "AXIN1", "ARID1A", "TERT", "VEGFA", "MYC", "KRAS", "PIK3CA", "MET"],
        "Parkinson's disease": ["SNCA", "LRRK2", "PARK7", "PINK1", "PRKN", "GBA1", "MAPT", "VPS35", "DNAJC13", "COMT"],
        "Parkinson disease": ["SNCA", "LRRK2", "PARK7", "PINK1", "PRKN", "GBA1", "MAPT", "VPS35", "DNAJC13", "COMT"],
        "melanoma": ["BRAF", "NRAS", "KIT", "CDKN2A", "TP53", "PTEN", "NF1", "MAP2K1", "CTLA4", "PDCD1"],
        "acute myeloid leukemia": ["FLT3", "NPM1", "DNMT3A", "IDH1", "IDH2", "TET2", "TP53", "RUNX1", "CEBPA", "KIT"],
        "breast cancer": ["BRCA1", "BRCA2", "ERBB2", "ESR1", "PIK3CA", "TP53", "CDH1", "PTEN", "AKT1", "GATA3"],
        "colorectal cancer": ["APC", "KRAS", "TP53", "SMAD4", "PIK3CA", "BRAF", "FBXW7", "MLH1", "MSH2", "CTNNB1"],
        "pancreatic cancer": ["KRAS", "TP53", "CDKN2A", "SMAD4", "BRCA2", "PALB2", "ATM", "ARID1A", "MYC", "TGFBR2"],
        "prostate cancer": ["AR", "PTEN", "TP53", "BRCA2", "ERG", "TMPRSS2", "SPOP", "FOXA1", "MYC", "CDK12"],
        "chronic kidney disease": ["PKD1", "PKD2", "UMOD", "APOL1", "ACE", "AGT", "NPHS1", "COL4A3", "WT1", "NPHP1"],
        "systemic lupus erythematosus": ["STAT4", "IRF5", "ITGAM", "BLK", "TNFAIP3", "PTPN22", "HLA-DRB1", "FCGR2A", "BANK1", "TNFSF4"],
        "asthma": ["IL4", "IL13", "IL33", "TSLP", "IL5", "ADAM33", "ORMDL3", "HLA-DRB1", "GSDMB", "ADRB2"],
        "Crohn's disease": ["NOD2", "ATG16L1", "IL23R", "IRGM", "TNF", "IL10", "CARD9", "LRRK2", "HLA-DRB1", "PTPN22"],
        "multiple sclerosis": ["HLA-DRB1", "IL7R", "IL2RA", "CD58", "CLEC16A", "IRF8", "TNFRSF1A", "TYK2", "EVI5", "CD6"],
        "psoriasis": ["IL23R", "IL12B", "TNF", "HLA-C", "STAT3", "TRAF3IP2", "IL17A", "CARD14", "NFKBIA", "LCE3B"],
        "ovarian cancer": ["BRCA1", "BRCA2", "TP53", "HRD", "KRAS", "PIK3CA", "PTEN", "ARID1A", "CCNE1", "MYC"],
        "Huntington's disease": ["HTT", "BDNF", "GRIA1", "GRIK2", "HAP1", "DCAF17", "MSH3", "FAN1", "PMS1", "MLH1"],
    }
    _TARGET_CENTRIC_TYPES = (
        "target_prioritization", "target_discovery_lab",
        "knowledge_graph", "structure_pocket",
        "translation_research",
    )
    # Types that benefit from gene context (for graph, contradictions, etc)
    _GENE_ENRICHABLE_TYPES = _TARGET_CENTRIC_TYPES + (
        "evidence_retrieval", "disease_intelligence", "cockpit_resume",
        "dossier", "research_loop", "population_genomics",
        "translational_pico", "design_studio", "admet",
        "e2e_program", "autopilot", "molecule_lab", "pocket_discovery",
        "vaccine_epitope", "metabolic_engineering", "translation_research",
        "retrosynthesis", "error_handling", "syntharena",
    )
    if classification.disease and not classification.genes and not entities["genes"]:
        # No genes from query or search → seed from curated map
        seeds = _DISEASE_GENE_SEEDS.get(classification.disease, [])
        if seeds and classification.query_type in _GENE_ENRICHABLE_TYPES:
            entities["genes"] = list(seeds)
    elif classification.query_type in _TARGET_CENTRIC_TYPES and classification.disease:
        seeds = _DISEASE_GENE_SEEDS.get(classification.disease, [])
        if seeds:
            if not classification.genes:
                # No explicit genes in query → use curated disease seeds
                # as PRIMARY list (replace search-extracted genes which
                # may be irrelevant bacterial/structural hits)
                entities["genes"] = list(seeds)
            else:
                # Query mentioned specific genes; supplement with seeds
                for s in seeds:
                    if s not in entities["genes"]:
                        entities["genes"].append(s)
    elif classification.query_type in _TARGET_CENTRIC_TYPES and not entities["genes"]:
        # No disease detected, no genes found — try OpenTargets
        try:
            from connectors.opentargets import OpenTargetsConnector
            ot = OpenTargetsConnector()
            disease_query = classification.disease or query
            ot_results = await ot.search(disease_query, limit=15)
            if ot_results and isinstance(ot_results, list):
                for r in ot_results:
                    sym = r.get("symbol") or r.get("gene_symbol") or r.get("name", "")
                    if sym and len(sym) <= 15 and sym.replace("-", "").replace("_", "").isalnum() and sym not in entities["genes"]:
                        entities["genes"].append(sym)
        except Exception as ex:
            enrichment_errors.append(f"gene_discovery: {str(ex)[:100]}")

    # Fallback gene discovery for non-target-centric types with no genes
    if not entities["genes"] and classification.query_type in _GENE_ENRICHABLE_TYPES:
        try:
            from connectors.opentargets import OpenTargetsConnector
            ot = OpenTargetsConnector()
            disease_query = classification.disease or query
            ot_results = await ot.search(disease_query, limit=15)
            if ot_results and isinstance(ot_results, list):
                for r in ot_results:
                    sym = r.get("symbol") or r.get("gene_symbol") or r.get("name", "")
                    if sym and len(sym) <= 15 and sym.replace("-", "").replace("_", "").isalnum() and sym not in entities["genes"]:
                        entities["genes"].append(sym)
        except Exception as ex:
            enrichment_errors.append(f"gene_discovery_fallback: {str(ex)[:100]}")

    # ── §3-§18 Parallel enrichment calls ──────────────────
    t_enrich_start = time.monotonic()
    tasks = []
    if ws is not None:
        await ws.emit_progress(run_id, "enrichment", 45, "Running enrichment modules")

    # Disease normalization (§7)
    if entities["diseases"]:
        async def _disease_norm():
            from services.disease.disease_normalizer import normalize_disease_name
            results = []
            for dname in entities["diseases"][:5]:
                try:
                    r = normalize_disease_name(dname)
                    results.append(r)
                except Exception:
                    results.append({"original_name": dname, "preferred_name": dname})
            return results
        tasks.append(_safe(_disease_norm(), "disease_normalization"))

    # Target scoring (§8)
    if entities["genes"]:
        async def _target_score():
            from services.target_scorer import TargetScorer
            scorer = TargetScorer(query_id=run_id, candidates=entities["genes"][:15])
            return await scorer.evaluate_candidates()
        tasks.append(_safe(_target_score(), "target_scoring"))

    # Contradiction detection (§6)
    async def _contradictions():
        from services.contradiction_detector import detect_contradictions
        raw_cats = {}
        for cs in category_summaries:
            if cs["rows"]:
                raw_cats[cs["category"]] = cs["rows"]
        return await detect_contradictions(raw_cats, query)
    tasks.append(_safe(_contradictions(), "contradiction_detection"))

    # Structure lookup (§10)
    _needs_structure = entities["structures"] or entities["proteins"] or classification.query_type in (
        "structure_pocket", "pocket_discovery", "design_studio",
        "molecule_lab", "target_prioritization", "knowledge_graph",
        "disease_intelligence", "dossier", "e2e_program", "autopilot",
        "vaccine_epitope", "admet", "retrosynthesis",
        "research_loop", "target_discovery_lab",
    )
    if _needs_structure:
        async def _structures():
            from services.structure_service import StructureService
            svc = StructureService()
            all_results: list[dict] = []
            try:
                # Prioritize classifier-detected genes for structure search
                search_terms: list[str] = []
                if classification.genes:
                    search_terms.extend(classification.genes[:5])
                if len(search_terms) < 3 and entities["genes"]:
                    # Filter to likely protein-coding genes (short symbols, alphanumeric)
                    _good = [g for g in entities["genes"] if len(g) <= 10 and g.isalnum() and not g.startswith("LINC")]
                    for g in _good:
                        if g not in search_terms:
                            search_terms.append(g)
                        if len(search_terms) >= 5:
                            break
                if not search_terms:
                    search_terms = entities["proteins"][:3]
                if not search_terms and classification.disease:
                    search_terms = [classification.disease]
                seen_ids: set[str] = set()
                for term in search_terms:
                    sr = await svc.search_structures(term, limit=5)
                    if sr and isinstance(sr, dict):
                        for hit in sr.get("result_set", []):
                            pid = hit.get("identifier", "")
                            if pid and pid not in seen_ids:
                                seen_ids.add(pid)
                                all_results.append(hit)
                # Fetch detailed summaries for top PDB IDs
                summaries = []
                for hit in all_results[:10]:
                    pid = hit.get("identifier", "")
                    if pid:
                        try:
                            s = await svc.get_structure_summary(pid)
                            if s and "error" not in s:
                                summaries.append(s)
                        except Exception:
                            summaries.append({"pdb_id": pid, "score": hit.get("score", 0)})
                return summaries if summaries else all_results[:10]
            finally:
                await svc.close()
        tasks.append(_safe(_structures(), "structure_analysis"))

    # ADMET predictions (§12)
    # Extract SMILES from query text if not found in search results
    if not entities["smiles"] and classification.query_type in ("admet", "design_studio", "retrosynthesis", "molecule_lab"):
        import re as _re
        # SMILES pattern: contains atoms (C,N,O,S,P,F,Cl,Br,I) + bonds/rings
        _smiles_pat = _re.compile(
            r"(?<![a-zA-Z])"
            r"([A-Z][A-Za-z0-9@+\-\[\]\(\)\\\/=#$:.%]{5,})"
            r"(?![a-zA-Z])"
        )
        for m in _smiles_pat.finditer(query):
            candidate = m.group(1)
            # Basic validate: must have at least one lowercase after uppercase
            if _re.search(r"[cnops]", candidate) or _re.search(r"[=\(\)\[\]#]", candidate):
                entities["smiles"].append(candidate)
    # Fallback: fetch SMILES from ChEMBL for drug entities when query type needs chemistry
    if not entities["smiles"] and classification.query_type in ("admet", "design_studio", "retrosynthesis", "molecule_lab"):
        # Try extracting SMILES from category rows (drugs/molecules)
        for cs in category_summaries:
            if cs["category"] in ("drugs", "molecules", "compounds"):
                for row in cs["rows"][:5]:
                    smi = row.get("smiles") or row.get("canonical_smiles")
                    if smi and str(smi).strip() and smi not in entities["smiles"]:
                        entities["smiles"].append(str(smi))
        # If still empty, try fetching from ChEMBL using drug names or target genes
        if not entities["smiles"]:
            try:
                from connectors.chembl import ChEMBLConnector
                chembl = ChEMBLConnector()
                # First try drug names (more specific → better SMILES)
                search_terms: list[str] = []
                if entities["drugs"]:
                    search_terms.extend(entities["drugs"][:5])
                if len(search_terms) < 3 and entities["genes"]:
                    search_terms.extend(f"{g} inhibitor" for g in entities["genes"][:3])
                for term in search_terms:
                    results = await chembl.search(term, limit=5)
                    if results and isinstance(results, list):
                        for r in results:
                            smi = r.get("smiles") or r.get("canonical_smiles")
                            if smi and str(smi).strip() and smi not in entities["smiles"]:
                                entities["smiles"].append(str(smi))
                            if len(entities["smiles"]) >= 5:
                                break
                    if len(entities["smiles"]) >= 5:
                        break
            except Exception:
                pass
    if entities["smiles"] or classification.query_type in ("admet",):
        async def _admet():
            from services.molecule_service import ADMETPredictor, compute_physichem
            predictor = ADMETPredictor()
            results = []
            for smi in entities["smiles"][:5]:
                try:
                    physchem = compute_physichem(smi)
                    admet = predictor.predict(smi)
                    results.append({"smiles": smi, "physichem": physchem, "admet": admet})
                except Exception:
                    results.append({"smiles": smi, "physichem": {}, "admet": {}})
            return results
        tasks.append(_safe(_admet(), "admet_prediction"))

    # Retrosynthesis (§13)
    if entities["smiles"] or classification.query_type in ("retrosynthesis",):
        async def _retro():
            from services.rl_optimizer import RLService
            results = []
            for smi in entities["smiles"][:3]:
                try:
                    r = RLService.analyze_retrosynthesis(smi)
                    results.append(r)
                except Exception:
                    results.append({"status": "failed", "target": smi, "steps": []})
            return results
        tasks.append(_safe(_retro(), "retrosynthesis"))

    # Graph neighborhood (§9)
    async def _graph():
        from services.graph_service import GraphService
        gsvc = GraphService()
        neighborhoods = []
        try:
            # Try to get neighborhood for top entities
            for eid in (entities["genes"][:3] + entities["proteins"][:2]):
                try:
                    nb = await gsvc.get_neighborhood(eid, depth=1)
                    if nb:
                        neighborhoods.append({"entity": eid, "neighborhood": nb})
                except Exception:
                    pass
        finally:
            await gsvc.close()
        return neighborhoods
    tasks.append(_safe(_graph(), "graph_reasoning"))

    # Protein-protein interaction enrichment (STRING) for graph-centric queries
    if classification.query_type in (
        "knowledge_graph", "target_discovery_lab", "disease_intelligence",
        "dossier", "e2e_program", "research_loop", "evidence_retrieval",
        "translation_research",
    ) and entities["genes"]:
        async def _string_interactions():
            from connectors.string_db import STRINGConnector
            interactions = []
            try:
                sdb = STRINGConnector()
                for gene in entities["genes"][:5]:
                    try:
                        results = await sdb.search(gene, limit=10)
                        if results and isinstance(results, list):
                            for r in results:
                                interactions.append(r)
                    except Exception:
                        pass
            except Exception as ex:
                log.warning("string_interactions_failed", error=str(ex))
            return interactions
        tasks.append(_safe(_string_interactions(), "string_interactions"))

    # Pathway enrichment (KEGG) for graph/pathway-centric queries
    if classification.query_type in (
        "knowledge_graph", "target_discovery_lab", "target_prioritization",
        "disease_intelligence", "dossier", "e2e_program", "research_loop",
        "evidence_retrieval", "translation_research",
    ) and entities["genes"]:
        async def _pathway_enrichment():
            from connectors.kegg import KEGGConnector
            pathways = []
            try:
                kegg = KEGGConnector()
                for gene in entities["genes"][:5]:
                    try:
                        results = await kegg.search(gene, limit=5)
                        if results and isinstance(results, list):
                            for r in results:
                                if r not in pathways:
                                    pathways.append(r)
                    except Exception:
                        pass
            except Exception as ex:
                log.warning("pathway_enrichment_failed", error=str(ex))
            return pathways
        tasks.append(_safe(_pathway_enrichment(), "pathway_enrichment"))

    # PICO extraction from first publication abstracts (§14)
    # First: harvest inline pico_data already embedded in publication rows
    inline_pico: List[Dict[str, Any]] = []
    if entities["publications"]:
        for pub in entities["publications"][:10]:
            pd = pub.get("pico_data")
            if pd and isinstance(pd, str):
                try:
                    import ast
                    pd = ast.literal_eval(pd)
                except Exception:
                    pd = None
            if pd and isinstance(pd, dict):
                has_content = any(pd.get(k) for k in ("population", "intervention", "comparator", "outcome"))
                if has_content:
                    inline_pico.append({"title": pub.get("title", ""), "pico": pd})

    # If inline PICO insufficient, try LLM extraction
    if len(inline_pico) < 2 and entities["publications"]:
        async def _pico():
            from services.pico_extractor import extract_pico_data
            results = list(inline_pico)  # start with what we have
            for pub in entities["publications"][:5]:
                abstract = pub.get("abstract") or pub.get("snippet") or pub.get("description") or pub.get("title", "")
                if abstract and len(str(abstract)) > 50:
                    try:
                        pico = await extract_pico_data(str(abstract)[:2000])
                        if pico and any(pico.get(k) for k in ("population", "intervention", "comparator", "outcome")):
                            results.append({"title": pub.get("title", ""), "pico": pico})
                    except Exception:
                        pass
                if len(results) >= 5:
                    break
            return results
        tasks.append(_safe(_pico(), "pico_extraction"))

    # Population genomics enrichment (§14 / population_genomics queries)
    _POP_GENOMICS_TYPES = {
        "population_genomics", "dossier", "research_loop", "e2e_program",
        "disease_intelligence", "target_prioritization", "target_discovery_lab",
        "vaccine_epitope", "autopilot",
    }
    if classification.cohort or classification.query_type in _POP_GENOMICS_TYPES:
        async def _population_genomics():
            pop_results = {"indigen": [], "gnomad": [], "genome_asia": []}
            search_genes = classification.genes or entities["genes"][:5]
            if not search_genes:
                search_genes = [classification.disease or query]

            # gnomAD — always available
            try:
                from connectors.gnomad import GnomadConnector
                gnomad = GnomadConnector()
                for gene in search_genes[:3]:
                    r = await gnomad.search(gene, limit=10)
                    if r:
                        pop_results["gnomad"].extend(r)
            except Exception as ex:
                enrichment_errors.append(f"gnomad: {str(ex)[:100]}")

            # IndiGen — Indian cohort
            if classification.cohort in ("Indian", "South Asian", None):
                try:
                    from connectors.indigen_loader import IndiGenLoader
                    indigen = IndiGenLoader()
                    for gene in search_genes[:3]:
                        r = await indigen.search(gene, limit=10)
                        if r:
                            pop_results["indigen"].extend(r)
                except Exception as ex:
                    enrichment_errors.append(f"indigen: {str(ex)[:100]}")

            # GenomeAsia
            try:
                from connectors.genomeasia_loader import GenomeAsiaLoader
                ga = GenomeAsiaLoader()
                for gene in search_genes[:3]:
                    r = await ga.search(gene, limit=10)
                    if r:
                        pop_results["genome_asia"].extend(r)
            except Exception as ex:
                enrichment_errors.append(f"genome_asia: {str(ex)[:100]}")

            return pop_results
        tasks.append(_safe(_population_genomics(), "population_genomics"))

    # Dedicated clinical trials enrichment (§14)
    _CT_TYPES = {
        "disease_intelligence", "target_prioritization", "evidence_retrieval",
        "translational_pico", "translation_research", "dossier", "research_loop",
        "e2e_program", "autopilot", "design_studio", "admet",
    }
    if not entities["trials"] and classification.query_type in _CT_TYPES:
        async def _clinical_trials():
            from connectors.clinicaltrials import ClinicalTrialsConnector
            ct = ClinicalTrialsConnector()
            try:
                disease = classification.disease or query
                results = await ct.search(disease, limit=20)
                return results or []
            except Exception as ex:
                enrichment_errors.append(f"clinical_trials: {str(ex)[:100]}")
                return []
            finally:
                await ct.close()
        tasks.append(_safe(_clinical_trials(), "clinical_trials_enrichment"))

    # SynthArena scenario comparison (§16 / syntharena queries)
    if classification.query_type == "syntharena" and classification.comparison_targets:
        async def _syntharena():
            from services.syntharena.engine import ScenarioEngine
            from models.scenario import Scenario, SynthArenaSession
            scenarios = []
            disease = classification.disease or query
            for target in classification.comparison_targets:
                scenarios.append(Scenario(
                    title=f"{target}-first strategy for {disease}",
                    assumptions=[f"{target}-first approach"],
                    seed_entities={"targets": [target], "pathways": [], "compounds": []},
                    population_context=classification.cohort or "global",
                ))
            session = SynthArenaSession(
                session_id=run_id,
                project_id=run_id,
                title=f"Cockpit comparison: {' vs '.join(classification.comparison_targets)} for {disease}",
                scenarios=scenarios,
            )
            engine = ScenarioEngine()
            return await engine.run_comparison(session)
        tasks.append(_safe(_syntharena(), "syntharena_comparison"))

    # ── Literature-specific enrichment (for evidence_retrieval queries) ──
    _LITERATURE_TYPES = ("evidence_retrieval", "cockpit_resume", "dossier",
                         "research_loop", "knowledge_graph", "disease_intelligence",
                         "target_prioritization", "e2e_program", "autopilot",
                         "translation_research", "translational_pico")
    is_literature_query = classification.query_type in _LITERATURE_TYPES

    if is_literature_query:
        async def _literature_deep():
            from services.literature_service import (
                fetch_literature, build_literature_table, build_filtered_table,
                extract_terms_map, detect_similarities, detect_nuanced_relationships,
                build_literature_kg, extract_user_specified_terms,
                extract_evidence_sentences, build_paper_sentences,
                extract_structures_from_literature, cross_reference_pathways,
                verify_contradictions_llm, build_traceable_summary,
                build_unified_pathways, cluster_by_mechanism,
            )
            from services.mesh_mapper import standardize_terms
            from services.paper_store import store_papers, get_paper_count
            from core.inference_engine import UniversalInferenceEngine

            # LLM engine for contradiction verification + traceable summary
            engine = UniversalInferenceEngine()
            llm_runtime_diagnostics = {
                "engine_status": engine.get_status(),
                "runtime_policy": get_runtime_policy(),
                "contradictions_mode": "llm",
                "traceable_summary_mode": "llm",
                "fallbacks": [],
            }

            # MeSH/GO term standardization
            term_std = standardize_terms(search_query)
            expanded = term_std.get("expanded_search_terms", search_query.split())

            # Deep literature fetch (includes full-text retrieval for OA papers)
            lit_data = await fetch_literature(search_query, expanded, limit=100)
            papers = lit_data.get("papers", [])

            # ── Persist papers to local SQLite DB ──
            newly_stored = 0
            total_in_db = 0
            try:
                newly_stored = await store_papers(papers, query)
                total_in_db = await get_paper_count()
            except Exception as e:
                log.warning("paper_store_failed", error=str(e))

            # Build tables
            lit_table = build_literature_table(papers)

            # User-specified filtering
            user_specs = extract_user_specified_terms(query)
            filtered_table = []
            if user_specs["filter_terms"]:
                filtered_table = build_filtered_table(
                    papers, user_specs["filter_terms"], user_specs["filter_type"]
                )

            # Terms map
            terms_map = extract_terms_map(papers, search_query)

            # Similarities
            similarities = detect_similarities(papers, threshold=0.12)

            # Nuanced relationships
            nuanced = detect_nuanced_relationships(papers)

            # Bidirectional traceability: sentence index + evidence linking
            paper_sentences = build_paper_sentences(papers)
            # Extract key claims from top papers for evidence mapping
            top_claims = []
            for p in papers[:10]:
                title = p.get("title", "")
                if title:
                    top_claims.append(title)
            evidence_links = extract_evidence_sentences(papers, top_claims, max_per_claim=3)

            # SMILES / protein sequence extraction from literature
            lit_structures = extract_structures_from_literature(papers)

            # Enrich with PubChem SMILES for drug names
            try:
                from services.literature_service import enrich_structures_from_pubchem
                lit_structures = enrich_structures_from_pubchem(terms_map, lit_structures)
            except Exception as exc:
                log.warning("pubchem_smiles_failed", error=str(exc)[:200])

            # ── LLM-verified contradiction detection (Gemma 4 26B) ──
            llm_contradictions = []
            try:
                llm_contradictions = await verify_contradictions_llm(
                    papers, query, engine=engine
                )
            except Exception as exc:
                llm_runtime_diagnostics["contradictions_mode"] = "error"
                llm_runtime_diagnostics["fallbacks"].append("llm_contradictions_error")
                log.warning("llm_contradiction_failed", error=str(exc)[:200])
            if not llm_contradictions and papers:
                llm_runtime_diagnostics["contradictions_mode"] = "fallback"
                llm_runtime_diagnostics["fallbacks"].append("llm_contradictions_empty")
            llm_runtime_diagnostics = _annotate_literature_llm_diagnostics(
                llm_contradictions,
                llm_runtime_diagnostics,
            )

            # ── Traceable AI Summary w/ [Ref N] citations ──
            traceable_summary = {}
            try:
                traceable_summary = await build_traceable_summary(
                    papers, query, llm_contradictions, terms_map, engine=engine
                )
            except Exception as exc:
                llm_runtime_diagnostics["traceable_summary_mode"] = "error"
                llm_runtime_diagnostics["fallbacks"].append("traceable_summary_error")
                log.warning("traceable_summary_failed", error=str(exc)[:200])
            if not traceable_summary and papers:
                llm_runtime_diagnostics["traceable_summary_mode"] = "fallback"
                llm_runtime_diagnostics["fallbacks"].append("traceable_summary_empty")

            # ── Unified Pathways Diagram ──
            unified_pathways = {}
            try:
                unified_pathways = build_unified_pathways(terms_map, papers)
            except Exception as exc:
                log.warning("unified_pathways_failed", error=str(exc)[:200])

            # ── Mechanism Clustering ──
            mechanism_clusters = {}
            try:
                mechanism_clusters = cluster_by_mechanism(papers)
            except Exception as exc:
                log.warning("mechanism_clustering_failed", error=str(exc)[:200])

            return {
                "papers": papers,
                "literature_table": lit_table,
                "filtered_table": filtered_table,
                "filter_info": user_specs,
                "terms_map": terms_map,
                "similarities": similarities,
                "nuanced_relationships": nuanced,
                "terminology": term_std,
                "fetch_stats": {
                    "total_fetched": lit_data.get("total_fetched", 0),
                    "total_unique": lit_data.get("total_unique", 0),
                    "sources": lit_data.get("sources_queried", []),
                    "timings": lit_data.get("fetch_timings", {}),
                    "newly_stored_in_db": newly_stored,
                    "total_papers_in_db": total_in_db,
                    "fulltext_papers": sum(1 for p in papers if p.get("full_text")),
                },
                "term_frequency": lit_data.get("term_frequency", {}),
                "paper_sentences": paper_sentences,
                "evidence_links": evidence_links,
                "lit_structures": lit_structures,
                "llm_contradictions": llm_contradictions,
                "traceable_summary": traceable_summary,
                "unified_pathways": unified_pathways,
                "mechanism_clusters": mechanism_clusters,
                "llm_runtime_diagnostics": llm_runtime_diagnostics,
            }
        tasks.append(_safe(_literature_deep(), "literature_analysis"))

    # Run all enrichment tasks in parallel (360s global timeout for 26B LLM)
    enrichment_results = {}
    if tasks:
        try:
            completed = await asyncio.wait_for(asyncio.gather(*tasks), timeout=600.0)
        except asyncio.TimeoutError:
            log.warning("cockpit_enrichment_global_timeout", timeout_s=600)
            completed = []
        for label, result in completed:
            enrichment_results[label] = result
            if result is None:
                enrichment_errors.append(f"{label}: enrichment failed (degraded)")

    # Add inline PICO if no LLM-PICO was tasked and inline data is available
    if inline_pico and "pico_extraction" not in enrichment_results:
        enrichment_results["pico_extraction"] = inline_pico

    t_enrich = round((time.monotonic() - t_enrich_start) * 1000)
    all_errors = (envelope.errors or []) + enrichment_errors
    degraded_sources = sorted({
        err.split(":")[0].strip()
        for err in all_errors
        if isinstance(err, str) and err.strip()
    })
    if ws is not None:
        await ws.emit_progress(
            run_id,
            "summary",
            78,
            "Composing cockpit report",
            degraded_sources=degraded_sources,
        )

    # ── Generate comprehensive AI summary (§17) ──────────
    # For literature queries, use traceable summary w/ [Ref N] citations
    # Extract early so traceable_summary can be used for AI summary
    _lit_early = enrichment_results.get("literature_analysis") or {}
    traceable_summary = _lit_early.get("traceable_summary", {})
    llm_contradictions = _lit_early.get("llm_contradictions", [])
    unified_pathways = _lit_early.get("unified_pathways", {})
    summary_text = ""
    if traceable_summary and traceable_summary.get("summary_text"):
        summary_text = traceable_summary["summary_text"]
    
    if not summary_text:
        try:
            from core.inference_engine import UniversalInferenceEngine
            engine = UniversalInferenceEngine()
            entities_text = "; ".join(all_entity_names[:30]) if all_entity_names else "no specific entities"
            cat_text = ", ".join(f"{c['category']}({c['count']})" for c in category_summaries if c["count"] > 0)

            # Build enrichment context for the LLM
            enrich_ctx_parts = []
            if enrichment_results.get("disease_normalization"):
                dn = enrichment_results["disease_normalization"]
                disease_names = ", ".join(d.get("preferred_name", d.get("original_name", "")) for d in dn)
                enrich_ctx_parts.append(f"Disease normalization: {disease_names}")
            if enrichment_results.get("target_scoring"):
                ts = enrichment_results["target_scoring"]
                top3 = sorted(ts, key=lambda x: x.get("composite_score", 0), reverse=True)[:3]
                target_strs = ", ".join(t.get("symbol", "?") + "(" + str(round(t.get("composite_score", 0), 2)) + ")" for t in top3)
                enrich_ctx_parts.append(f"Top targets: {target_strs}")
            if enrichment_results.get("contradiction_detection"):
                cd = enrichment_results["contradiction_detection"]
                enrich_ctx_parts.append(f"Contradictions found: {len(cd)}")
            if enrichment_results.get("population_genomics"):
                pg = enrichment_results["population_genomics"]
                gnomad_n = len(pg.get("gnomad", []))
                indigen_n = len(pg.get("indigen", []))
                ga_n = len(pg.get("genome_asia", []))
                if gnomad_n or indigen_n or ga_n:
                    enrich_ctx_parts.append(f"Population genomics: gnomAD={gnomad_n}, IndiGen={indigen_n}, GenomeAsia={ga_n}")
            if enrichment_results.get("syntharena_comparison"):
                sa = enrichment_results["syntharena_comparison"]
                if sa.get("winner"):
                    enrich_ctx_parts.append(f"SynthArena winner: {sa['winner']}")
            enrich_ctx = "\n".join(enrich_ctx_parts) if enrich_ctx_parts else "No enrichment data available."

            # Add query-type-specific focus from classifier
            classifier_ctx = get_summary_prompt_context(classification)
            if classifier_ctx:
                enrich_ctx = classifier_ctx + "\n\n" + enrich_ctx

            # Add literature-specific context when literature analysis is available
            lit_analysis_ctx = enrichment_results.get("literature_analysis") or {}
            if lit_analysis_ctx.get("papers"):
                lit_papers = lit_analysis_ctx["papers"]
                lit_ctx_parts = [f"Literature papers fetched: {len(lit_papers)}"]
                top5 = sorted(lit_papers, key=lambda p: p.get("_relevance_score", 0), reverse=True)[:5]
                for i, p in enumerate(top5, 1):
                    title = p.get("title", "")[:80]
                    year = p.get("year", "?")
                    source = (p.get("provenance", [{}])[0].get("source", "") if p.get("provenance") else "")
                    lit_ctx_parts.append(f"  {i}. {title} ({year}, {source})")
                sims = lit_analysis_ctx.get("similarities", [])
                if sims:
                    lit_ctx_parts.append(f"Paper similarities detected: {len(sims)} pairs")
                nuanced = lit_analysis_ctx.get("nuanced_relationships", [])
                if nuanced:
                    rel_types = {}
                    for r in nuanced:
                        rt = r.get("relationship", "unknown")
                        rel_types[rt] = rel_types.get(rt, 0) + 1
                    lit_ctx_parts.append(f"Nuanced relationships: {', '.join(f'{k}({v})' for k, v in rel_types.items())}")
                enrich_ctx += "\n\nLiterature Analysis:\n" + "\n".join(lit_ctx_parts)

            prompt = f"""You are an expert biomedical research analyst. Write a comprehensive executive summary for the query: "{query}".

Data found: {stats.get('total_results', 0)} results across {stats.get('categories_found', 0)} categories from {stats.get('sources_queried', 0)} databases.
Categories: {cat_text}
Key entities: {entities_text}
PubMed publications: {stats.get('pubmed_count', 'N/A')}
Clinical trials: {stats.get('clinical_trials_count', 'N/A')}
Evidence confidence: {evidence.get('overall_confidence', 0):.0%}
Enrichment context:
{enrich_ctx}

Write a clear, scientifically rigorous 15-20 line executive summary:
1. Restate the research objective and scope
2. Key disease biology and known etiology
3. Top target candidates with their druggability signals
4. Key compounds/drugs identified and their development stage
5. Structural and pathway insights
6. Evidence quality assessment—confidence, contradictions, gaps
7. Translational readiness (clinical trials, population data, biomarkers)
8. Critical risks and uncertainties
9. Concrete next steps and recommended experiments
10. Overall strategic recommendation for drug discovery program"""

            result = await engine.generate(
                prompt=prompt,
                max_tokens=1200,
                temperature=0.3,
                system_prompt="You are a senior biomedical research analyst providing expert drug discovery intelligence for a comprehensive canonical report.",
            )
            summary_text = result.get("text", "").strip()
        except Exception as ex:
            log.warning("cockpit_analyze_llm_failed", error=str(ex))

    # Fallback summary — 18-section canonical report format
    if not summary_text:
        total = stats.get("total_results", 0)
        sources = stats.get("sources_queried", 0)
        cats = stats.get("categories_found", 0)
        pubmed = stats.get("pubmed_count")
        trials = stats.get("clinical_trials_count")
        conf = evidence.get("overall_confidence", 0)

        # §1-2: Objective + execution context
        lines = [
            f'RESEARCH OBJECTIVE',
            f'Comprehensive multi-database analysis for "{query}" across {sources} authoritative databases returned {total} results in {cats} entity categories.',
            f'Query type: {classification.query_type}. Disease: {classification.disease or "not specified"}. '
            f'Genes: {", ".join(classification.genes[:5]) if classification.genes else "auto-seeded"}.',
            "",
        ]

        # §3: Agentic execution
        triggered = [k for k, v in enrichment_results.items() if v]
        lines.append(f"AGENTIC EXECUTION\nModules triggered: {', '.join(triggered) if triggered else 'search only'}. "
                      f"Total enrichment time: {t_enrich:,}ms.\n")

        # §4: Entity normalization
        lines.append(f"ENTITY NORMALIZATION\n"
                      f"Genes: {', '.join(entities['genes'][:10]) if entities['genes'] else 'none'}. "
                      f"Proteins: {', '.join(entities['proteins'][:5]) if entities['proteins'] else 'none'}. "
                      f"Diseases: {', '.join(entities['diseases'][:5]) if entities['diseases'] else 'none'}. "
                      f"Drugs: {', '.join(entities['drugs'][:5]) if entities['drugs'] else 'none'}.\n")

        # §5: Evidence acquisition
        if pubmed:
            lines.append(f"EVIDENCE ACQUISITION\nPubMed indexes {pubmed:,} related publications, "
                          f"indicating {'extensive' if pubmed > 10000 else 'moderate' if pubmed > 1000 else 'limited'} research activity.\n")

        # §6: Contradictions
        _contra_data = enrichment_results.get("contradiction_detection") or []
        n_contra = len(_contra_data)
        if n_contra > 0:
            lines.append(f"CONTRADICTIONS\n{n_contra} cross-source contradictions detected requiring manual review.")
            for c in _contra_data[:3]:
                if isinstance(c, dict) and c.get("claim_a"):
                    lines.append(f"  - {c.get('claim_a', '')[:80]} vs {c.get('claim_b', '')[:80]}")
            lines.append("")
        else:
            lines.append("EVIDENCE CONSISTENCY\nNo cross-source contradictions detected.\n")

        # §7: Disease intelligence
        di = enrichment_results.get("disease_normalization") or []
        if di:
            di_names = ", ".join(d.get("preferred_name", d.get("original_name", "")) for d in di[:5])
            lines.append(f"DISEASE INTELLIGENCE\n{len(di)} disease-gene associations identified. Diseases: {di_names}.\n")

        # §8: Target prioritization
        ts = enrichment_results.get("target_scoring") or []
        if ts:
            top5 = sorted(ts, key=lambda x: x.get("composite_score", 0), reverse=True)[:5]
            tlines = []
            for i, t in enumerate(top5, 1):
                sym = t.get("symbol", "?")
                score = round(t.get("composite_score", 0), 2)
                tlines.append(f"  {i}. {sym} (score={score})")
            lines.append(f"TARGET PRIORITIZATION\n{len(ts)} targets scored using composite signals (GWAS, druggability, pathways, expression, novelty, safety, literature).\n" + "\n".join(tlines) + "\n")
        elif entities["genes"]:
            lines.append(f"GENE TARGETS\nGene targets identified: {', '.join(entities['genes'][:10])}.\n")

        # §9: Graph & pathway reasoning
        _pg = envelope.preview_graph or {"nodes": [], "edges": []}
        if hasattr(_pg, "model_dump"): _pg = _pg.model_dump()
        elif hasattr(_pg, "dict"): _pg = _pg.dict()
        gn = len(_pg.get("nodes", []))
        ge = len(_pg.get("edges", []))
        if gn > 0:
            lines.append(f"GRAPH & PATHWAY REASONING\nKnowledge graph: {gn} nodes, {ge} edges. ")
            _pw_enr = enrichment_results.get("pathway_enrichment") or []
            _pw_names = [pw.get("name") or pw.get("title") or pw.get("id", "") for pw in (_pw_enr or entities["pathways"])]
            _pw_names = [n for n in _pw_names if n][:5]
            if _pw_names:
                lines.append(f"Key pathways: {', '.join(_pw_names)}.")
            lines.append("")

        # §10: Structure & pocket
        struct = enrichment_results.get("structure_analysis") or []
        if struct:
            lines.append(f"STRUCTURE & POCKET ANALYSIS\n{len(struct)} structures retrieved from RCSB PDB.\n")

        # §11-12: ADMET
        admet = enrichment_results.get("admet_prediction") or []
        if admet:
            lines.append(f"ADMET & OFF-TARGET\n{len(admet)} ADMET predictions generated.\n")

        # §13: Retrosynthesis
        retro = enrichment_results.get("retrosynthesis") or []
        if retro:
            lines.append(f"RETROSYNTHESIS\n{len(retro)} retrosynthetic routes analyzed.\n")

        # §14: Translational & population
        pico = enrichment_results.get("pico_extraction") or []
        pop = enrichment_results.get("population_genomics") or {}
        _ct_enr = enrichment_results.get("clinical_trials_enrichment") or []
        _n_trials = (trials or 0) + len(_ct_enr)
        txl_parts = []
        if _n_trials:
            txl_parts.append(f"{_n_trials:,} clinical trials registered")
        if pico:
            txl_parts.append(f"{len(pico)} PICO extractions")
        gnomad_n = len(pop.get("gnomad", []))
        indigen_n = len(pop.get("indigen", []))
        ga_n = len(pop.get("genome_asia", []))
        if gnomad_n or indigen_n or ga_n:
            txl_parts.append(f"population genomics: gnomAD={gnomad_n}, IndiGen={indigen_n}, GenomeAsia={ga_n}")
        if txl_parts:
            lines.append(f"TRANSLATIONAL & POPULATION\n{'. '.join(txl_parts)}.\n")

        # §16: SynthArena
        sa = enrichment_results.get("syntharena_comparison") or {}
        if sa and sa.get("winner"):
            lines.append(f"SYNTHARENA\nWinning scenario: {sa['winner']}.\n")

        # §17: Confidence & recommendation
        lines.append(f"EVIDENCE QUALITY\nOverall evidence confidence: {conf:.0%}. "
                      f"{'High confidence — strong cross-source agreement.' if conf >= 0.7 else 'Moderate confidence — additional validation recommended.'}\n")

        # §15 + §17: Next steps
        lines.append("RECOMMENDED NEXT STEPS\n"
                      "1. Deep-dive evidence search for top targets and compounds\n"
                      "2. Run disease workbench for detailed genetic association analysis\n"
                      "3. Explore knowledge graph for pathway-level mechanistic insights\n"
                      "4. Generate decision dossier for stakeholder review\n"
                      "5. Validate top candidates with in vitro target-engagement assays")

        # §18: Provenance
        _all_errs = (envelope.errors or []) + enrichment_errors
        degraded = [e.split(":")[0] for e in _all_errs if isinstance(e, str)]
        if degraded:
            lines.append(f"\nPROVENANCE\nDegraded sources: {', '.join(degraded[:10])}. Run ID: {run_id}")
        else:
            lines.append(f"\nPROVENANCE\nAll sources operational. Run ID: {run_id}")

        summary_text = "\n".join(lines)

    # ── Per-source breakdown ──────────────────────────────
    source_breakdown: Dict[str, int] = {}
    prov = envelope.provenance or {}
    for src in (prov.get("sources_hit") or []):
        source_breakdown[src] = source_breakdown.get(src, 0) + 1

    # ── Graph data ────────────────────────────────────────
    graph = envelope.preview_graph or {"nodes": [], "edges": []}
    if hasattr(graph, "model_dump"):
        graph = graph.model_dump()
    elif hasattr(graph, "dict"):
        graph = graph.dict()

    # Enrich graph edges from interaction / pathway search results
    # (The search returns nodes but the graph_store may have no edges
    #  pre-loaded; build them from actual search data.)
    existing_edge_ids = {e.get("id", "") for e in (graph.get("edges") or [])}
    existing_node_ids = {n.get("id", "") for n in (graph.get("nodes") or [])}
    for cat in category_summaries:
        cat_name = cat.get("category", "")
        if cat_name == "interactions":
            for row in (cat.get("rows") or [])[:60]:
                src = row.get("source_entity") or ""
                tgt = row.get("target_entity") or ""
                rel = row.get("interaction_type") or row.get("type") or "interacts_with"
                score = row.get("score") or row.get("combined_score") or 0
                if src and tgt:
                    eid = f"{src}-{rel}-{tgt}"
                    if eid not in existing_edge_ids:
                        graph.setdefault("edges", []).append({
                            "id": eid, "source": src, "target": tgt,
                            "type": rel, "properties": {"score": score},
                        })
                        existing_edge_ids.add(eid)
                    # Ensure both nodes exist
                    for nid in (src, tgt):
                        if nid not in existing_node_ids:
                            graph.setdefault("nodes", []).append({
                                "id": nid, "label": "Gene",
                                "properties": {"name": nid},
                            })
                            existing_node_ids.add(nid)
        elif cat_name == "pathways":
            for row in (cat.get("rows") or [])[:40]:
                pathway_name = row.get("name") or row.get("title") or ""
                pathway_genes = row.get("genes") or row.get("gene_symbols") or []
                if isinstance(pathway_genes, str):
                    pathway_genes = [g.strip() for g in pathway_genes.split(",") if g.strip()]
                if pathway_name and not pathway_genes:
                    # No gene list in pathway row; link pathway as node to known genes
                    for gene in entities["genes"][:5]:
                        eid = f"{gene}-in_pathway-{pathway_name}"
                        if eid not in existing_edge_ids:
                            graph.setdefault("edges", []).append({
                                "id": eid, "source": gene, "target": pathway_name,
                                "type": "in_pathway", "properties": {},
                            })
                            existing_edge_ids.add(eid)
                            if pathway_name not in existing_node_ids:
                                graph.setdefault("nodes", []).append({
                                    "id": pathway_name, "label": "Pathway",
                                    "properties": {"name": pathway_name},
                                })
                                existing_node_ids.add(pathway_name)
                elif pathway_name and pathway_genes:
                    # Link each gene to pathway
                    if pathway_name not in existing_node_ids:
                        graph.setdefault("nodes", []).append({
                            "id": pathway_name, "label": "Pathway",
                            "properties": {"name": pathway_name},
                        })
                        existing_node_ids.add(pathway_name)
                    for gene in pathway_genes[:10]:
                        eid = f"{gene}-in_pathway-{pathway_name}"
                        if eid not in existing_edge_ids:
                            graph.setdefault("edges", []).append({
                                "id": eid, "source": gene, "target": pathway_name,
                                "type": "in_pathway", "properties": {},
                            })
                            existing_edge_ids.add(eid)
                            if gene not in existing_node_ids:
                                graph.setdefault("nodes", []).append({
                                    "id": gene, "label": "Gene",
                                    "properties": {"name": gene},
                                })
                                existing_node_ids.add(gene)

    # Also merge graph_reasoning neighborhoods into the preview graph
    for nb in (enrichment_results.get("graph_reasoning") or []):
        nb_data = nb.get("neighborhood", {})
        for n in (nb_data.get("nodes") or []):
            nid = n.get("id", "")
            if nid and nid not in existing_node_ids:
                graph.setdefault("nodes", []).append(n)
                existing_node_ids.add(nid)
        for e in (nb_data.get("edges") or []):
            eid = e.get("id", "")
            if eid and eid not in existing_edge_ids:
                graph.setdefault("edges", []).append(e)
                existing_edge_ids.add(eid)

    # Add disease→gene edges when disease and genes are known
    if classification.disease and entities["genes"]:
        disease_id = classification.disease
        if disease_id not in existing_node_ids:
            graph.setdefault("nodes", []).append({
                "id": disease_id, "label": "Disease",
                "properties": {"name": disease_id},
            })
            existing_node_ids.add(disease_id)
        for gene in entities["genes"][:15]:
            eid = f"{disease_id}-associated_with-{gene}"
            if eid not in existing_edge_ids:
                graph.setdefault("edges", []).append({
                    "id": eid, "source": disease_id, "target": gene,
                    "type": "associated_with", "properties": {},
                })
                existing_edge_ids.add(eid)
                if gene not in existing_node_ids:
                    graph.setdefault("nodes", []).append({
                        "id": gene, "label": "Gene",
                        "properties": {"name": gene},
                    })
                    existing_node_ids.add(gene)

    # Merge STRING interactions into graph
    for interaction in (enrichment_results.get("string_interactions") or []):
        src = interaction.get("source_entity") or interaction.get("preferredName_A") or ""
        tgt = interaction.get("target_entity") or interaction.get("preferredName_B") or ""
        score = interaction.get("score") or interaction.get("combined_score") or 0
        if src and tgt:
            eid = f"{src}-interacts_with-{tgt}"
            if eid not in existing_edge_ids:
                graph.setdefault("edges", []).append({
                    "id": eid, "source": src, "target": tgt,
                    "type": "interacts_with",
                    "properties": {"score": score, "source_db": "STRING"},
                })
                existing_edge_ids.add(eid)
                for nid in (src, tgt):
                    if nid not in existing_node_ids:
                        graph.setdefault("nodes", []).append({
                            "id": nid, "label": "Gene",
                            "properties": {"name": nid},
                        })
                        existing_node_ids.add(nid)

    # Merge pathway enrichment into pathways and graph
    pathway_enriched = enrichment_results.get("pathway_enrichment") or []
    if pathway_enriched:
        for pw in pathway_enriched:
            pw_name = pw.get("name") or pw.get("title") or pw.get("id") or ""
            if pw_name and pw not in entities["pathways"]:
                entities["pathways"].append(pw)
            # Add pathway→gene edges
            pw_genes = pw.get("genes") or pw.get("gene_symbols") or []
            if isinstance(pw_genes, str):
                pw_genes = [g.strip() for g in pw_genes.split(",") if g.strip()]
            if pw_name:
                if pw_name not in existing_node_ids:
                    graph.setdefault("nodes", []).append({
                        "id": pw_name, "label": "Pathway",
                        "properties": {"name": pw_name},
                    })
                    existing_node_ids.add(pw_name)
                # Link known genes to this pathway
                link_genes = pw_genes if pw_genes else entities["genes"][:5]
                for gene in link_genes[:8]:
                    eid = f"{gene}-in_pathway-{pw_name}"
                    if eid not in existing_edge_ids:
                        graph.setdefault("edges", []).append({
                            "id": eid, "source": gene, "target": pw_name,
                            "type": "in_pathway", "properties": {},
                        })
                        existing_edge_ids.add(eid)

    # Drop orphan preview nodes after bridge-edge enrichment so the cockpit graph
    # stays focused on connected evidence neighborhoods.
    connected_node_ids = {
        node_id
        for edge in (graph.get("edges") or [])
        for node_id in (edge.get("source"), edge.get("target"))
        if node_id
    }
    graph["nodes"] = [
        node
        for node in (graph.get("nodes") or [])
        if not connected_node_ids or node.get("id") in connected_node_ids
    ]

    elapsed = round((time.monotonic() - t0) * 1000)

    # ── Build 18-section canonical report ─────────────────

    # §7: Disease intelligence
    disease_intel = enrichment_results.get("disease_normalization") or []

    # §8: Target prioritization
    target_ranking = enrichment_results.get("target_scoring") or []
    if target_ranking:
        target_ranking = sorted(target_ranking, key=lambda x: x.get("composite_score", 0), reverse=True)

    # §6: Contradiction analysis (detailed)
    contradictions_detail = enrichment_results.get("contradiction_detection") or []

    # §10: Structure analysis
    structure_data = enrichment_results.get("structure_analysis") or []

    # §12: ADMET predictions
    admet_data = enrichment_results.get("admet_prediction") or []

    # §13: Retrosynthesis
    retro_data = enrichment_results.get("retrosynthesis") or []

    # §9: Graph reasoning
    graph_reasoning = enrichment_results.get("graph_reasoning") or []

    # §14: PICO / translational
    pico_data = enrichment_results.get("pico_extraction") or []

    # §14: Clinical trials context (merge search results + dedicated enrichment)
    trials_data = entities["trials"][:20]
    ct_enriched = enrichment_results.get("clinical_trials_enrichment") or []
    if ct_enriched:
        seen_ids = {t.get("nct_id") or t.get("id") for t in trials_data if t.get("nct_id") or t.get("id")}
        for ct in ct_enriched:
            ct_id = ct.get("nct_id") or ct.get("id")
            if ct_id and ct_id not in seen_ids:
                trials_data.append(ct)
                seen_ids.add(ct_id)
        trials_data = trials_data[:30]

    # §9: Pathways
    pathways_data = entities["pathways"][:30]

    # §14: Population genomics
    population_data = enrichment_results.get("population_genomics") or {}

    # §16: SynthArena comparison
    syntharena_data = enrichment_results.get("syntharena_comparison") or {}

    # §17-§23: Literature analysis
    lit_analysis = enrichment_results.get("literature_analysis") or {}

    # Pathways fallback: if enrichment returned 0 pathways, build from literature terms_map
    if not pathways_data:
        _lit_tm = (lit_analysis or {}).get("terms_map", {})
        _lit_genes = _lit_tm.get("genes", {})
        _lit_drugs = _lit_tm.get("drugs", {})
        _lit_diseases = _lit_tm.get("diseases", {})
        _pw_items = []
        # Synthesize pathway-like entries from top gene terms
        for sym, cnt in sorted(_lit_genes.items(), key=lambda x: -x[1])[:15]:
            _pw_items.append({"name": f"{sym} signaling pathway", "source": "literature-derived",
                              "genes": [sym], "relevance": cnt})
        for drug, cnt in sorted(_lit_drugs.items(), key=lambda x: -x[1])[:5]:
            _pw_items.append({"name": f"{drug} mechanism", "source": "literature-derived",
                              "genes": [], "relevance": cnt})
        pathways_data = _pw_items[:20]

    # Targets fallback: if target_scoring returned <3, supplement from disease seeds
    if len(target_ranking) < 3 and classification.disease:
        _seeds = _DISEASE_GENE_SEEDS.get(classification.disease, [])
        _existing_syms = {t.get("symbol") or t.get("gene") for t in target_ranking}
        for _s in _seeds:
            if _s not in _existing_syms:
                target_ranking.append({
                    "symbol": _s, "gene": _s,
                    "composite_score": 0.3,
                    "signals": {"literature": 0.5, "druggability": 0.3, "pathways": 0.3,
                                "expression": 0.2, "novelty": 0.2, "safety": 0.4, "gwas": 0.1},
                    "source": "disease-seed-fallback",
                })
            if len(target_ranking) >= 10:
                break
        target_ranking = sorted(target_ranking, key=lambda x: x.get("composite_score", 0), reverse=True)

    literature_table = lit_analysis.get("literature_table", [])
    filtered_literature = lit_analysis.get("filtered_table", [])
    filter_info = lit_analysis.get("filter_info", {})
    terms_map = lit_analysis.get("terms_map", {})
    similarities = lit_analysis.get("similarities", [])
    nuanced_relationships = lit_analysis.get("nuanced_relationships", [])
    mesh_terminology = lit_analysis.get("terminology", {})
    lit_fetch_stats = lit_analysis.get("fetch_stats", {})
    term_frequency = lit_analysis.get("term_frequency", {})
    paper_sentences = lit_analysis.get("paper_sentences", [])
    evidence_links = lit_analysis.get("evidence_links", {})
    lit_structures = lit_analysis.get("lit_structures", [])
    llm_contradictions = lit_analysis.get("llm_contradictions", [])
    traceable_summary = lit_analysis.get("traceable_summary", {})
    unified_pathways = lit_analysis.get("unified_pathways", {})
    mechanism_clusters = lit_analysis.get("mechanism_clusters", {})
    llm_runtime_diagnostics = lit_analysis.get("llm_runtime_diagnostics", {})
    llm_contradictions, contradiction_guard_applied = _ensure_non_empty_llm_contradictions(
        lit_analysis.get("papers", []),
        llm_contradictions,
        contradictions_detail,
        llm_runtime_diagnostics,
    )
    # Build literature KG if papers present
    literature_kg = {}
    if lit_analysis.get("papers"):
        try:
            from services.literature_service import build_literature_kg
            # Use LLM-verified contradictions if available, fallback to general
            kg_contradictions = llm_contradictions if llm_contradictions else contradictions_detail
            literature_kg = build_literature_kg(
                lit_analysis["papers"], terms_map, kg_contradictions
            )
        except Exception:
            literature_kg = {}

    # Pathway-literature cross-reference
    pathways_with_lit = pathways_data
    if lit_analysis.get("papers") and pathways_data:
        try:
            from services.literature_service import cross_reference_pathways
            pathways_with_lit = cross_reference_pathways(
                lit_analysis["papers"], pathways_data
            )
        except Exception:
            pass

    quality_guards = _build_quality_guards(
        classification.query_type,
        target_ranking,
        pathways_with_lit,
        llm_contradictions,
        contradiction_guard_applied,
    )

    runtime_diagnostics = {
        "policy": get_runtime_policy(),
        "literature_llm": llm_runtime_diagnostics,
        "pico": pico_data.get("diagnostics", {}) if isinstance(pico_data, dict) else {},
        "fallback_modes": [
            mode
            for mode in [
                "llm_contradictions_guard" if contradiction_guard_applied else None,
                "pico_regex" if isinstance(pico_data, dict) and pico_data.get("method") == "regex" else None,
            ]
            if mode
        ],
    }

    all_timings = envelope.timings or {}
    all_timings["search_ms"] = t_search
    all_timings["enrichment_ms"] = t_enrich
    all_timings["total_ms"] = elapsed
    all_timings["budget.first_progress_ms"] = float(COCKPIT_LATENCY_BUDGET["first_progress_ms"])
    all_timings["budget.sync_soft_timeout_ms"] = float(COCKPIT_LATENCY_BUDGET["sync_soft_timeout_ms"])
    if ws is not None:
        await ws.emit_progress(
            run_id,
            "finalize",
            95,
            "Persisting cockpit analysis",
            degraded_sources=degraded_sources,
        )

    return {
        "query": query,
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "execution_mode": body.execution_mode,
        "latency_budget": dict(COCKPIT_LATENCY_BUDGET),

        # Query classification metadata (for frontend adaptive rendering)
        "query_classification": classification.to_dict(),

        # §2: AI Executive Summary / Final Recommendation
        "summary": summary_text,

        # §3: Categories (entity tables)
        "categories": category_summaries,

        # §4: Graph preview
        "graph": graph,

        # §5: Stats
        "stats": {
            "total_results": stats.get("total_results", 0),
            "categories_found": stats.get("categories_found", 0),
            "sources_queried": stats.get("sources_queried", 0),
            "pubmed_count": stats.get("pubmed_count"),
            "clinical_trials_count": len(trials_data) or stats.get("clinical_trials_count"),
            "overall_confidence": evidence.get("overall_confidence", 0),
            "contradictions_count": len(contradictions_detail) if contradictions_detail else (
                evidence.get("contradictions", {}).get("count", 0)
                if isinstance(evidence.get("contradictions"), dict)
                else len(evidence.get("contradictions", []))
            ),
        },

        # §5: Source breakdown
        "source_breakdown": source_breakdown,

        # §5: Evidence
        "evidence": {
            "top_citations": evidence.get("top_citations", []),
            "confidence": evidence.get("overall_confidence", 0),
        },

        # §6: Contradictions (detailed)
        "contradictions": contradictions_detail,

        # §7: Disease Intelligence
        "disease_intelligence": disease_intel,

        # §8: Target Prioritization
        "target_prioritization": target_ranking,

        # §9: Graph Reasoning (neighborhoods)
        "graph_reasoning": graph_reasoning,

        # §9: Pathways
        "pathways": pathways_with_lit,

        # §10: Structures
        "structures": structure_data,

        # §11-§12: ADMET / Molecule Data
        "admet": admet_data,

        # §13: Retrosynthesis
        "retrosynthesis": retro_data,

        # §14: Clinical Trials (translational)
        "clinical_trials": trials_data,

        # §14: PICO Extraction
        "pico": pico_data,

        # §14: Population Genomics
        "population_genomics": population_data,

        # §16: SynthArena Scenario Comparison
        "syntharena": syntharena_data,

        # §17: Literature Table (all papers, sorted by relevance)
        "literature_table": literature_table,

        # §18: User-Specified Literature (filtered by GWAS/mechanisms/etc.)
        "filtered_literature": filtered_literature,
        "filter_info": filter_info,

        # §19: Similarities (paper pairs with shared findings)
        "similarities": similarities,

        # §20: Nuanced Relationships (Refines, Fails to Replicate, etc.)
        "nuanced_relationships": nuanced_relationships,

        # §21: Terms Map (genes, drugs, diseases, methods with frequencies)
        "terms_map": terms_map,
        "term_frequency": term_frequency,

        # §22: Literature Knowledge Graph (category-colored nodes)
        "literature_kg": literature_kg,

        # §23: MeSH/GO Terminology Mapping
        "mesh_terminology": mesh_terminology,

        # Literature fetch stats
        "literature_stats": lit_fetch_stats,

        # §25: Bidirectional traceability (sentence index + evidence links)
        "paper_sentences": paper_sentences,
        "evidence_links": evidence_links,

        # §26: Literature structures (SMILES / protein sequences from papers)
        "lit_structures": lit_structures,

        # §27: LLM-verified contradictions (Gemma 4 — experimental context)
        "llm_contradictions": llm_contradictions,

        # §28: Traceable summary w/ [Ref N] citations
        "traceable_summary": traceable_summary,

        # §29: Unified Pathways Diagram (genes→drugs→diseases→methods)
        "unified_pathways": unified_pathways,

        # §30: Mechanism Clusters (papers grouped by biological mechanism)
        "mechanism_clusters": mechanism_clusters,

        # Timing & errors
        "timings": all_timings,
        "errors": all_errors,
        "latency_ms": elapsed,
        "degraded_sources": degraded_sources,
        "search_provenance": envelope.provenance or {},
        "quality_guards": quality_guards,
        "runtime_diagnostics": runtime_diagnostics,

        # §4: Entities extracted (for normalization display)
        "entities_extracted": {
            "genes": entities["genes"],
            "proteins": entities["proteins"],
            "diseases": entities["diseases"],
            "drugs": entities["drugs"],
            "structures": entities["structures"],
        },
    }


# ── Scientific export endpoints ────────────────────────────

class ExportRequest(BaseModel):
    papers: List[Dict[str, Any]] = Field(default_factory=list)
    query: str = ""


@router.post("/export/ris")
async def export_ris(body: ExportRequest, _user=Depends(get_current_user)):
    """Export literature results as RIS (Research Information Systems) format."""
    from fastapi.responses import Response
    from services.export_service import generate_ris

    ris_text = generate_ris(body.papers, body.query)
    return Response(
        content=ris_text,
        media_type="application/x-research-info-systems",
        headers={"Content-Disposition": "attachment; filename=literature_export.ris"},
    )


# ── A4: Dead-letter queue inspection ─────────────────────

class DLQItem(BaseModel):
    run_id: str = ""
    ts: str = ""
    function: str = ""
    error: str = ""
    raw: str = ""


@router.get("/dead-letters")
async def cockpit_dead_letters(
    request: Request,
    user=Depends(get_current_user),
    queue: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Return dead-letter queue items from Redis (A4).

    If `queue` is given, returns items from `dlq:{queue}` only.
    Otherwise aggregates all `dlq:*` keys up to `limit` items total.
    """
    import json as _json
    items: List[Dict[str, Any]] = []
    queues_found: List[str] = []
    try:
        from redis import asyncio as aioredis
        from config import settings as _cfg
        rc = await aioredis.from_url(_cfg.redis_url, decode_responses=True)
        if queue:
            keys = [f"dlq:{queue}"]
        else:
            keys = await rc.keys("dlq:*")
        queues_found = [k.removeprefix("dlq:") for k in keys]
        for key in keys:
            raw_entries = await rc.lrange(key, 0, limit - 1)
            for raw in raw_entries:
                try:
                    entry = _json.loads(raw)
                except Exception:
                    entry = {"raw": raw}
                entry["_queue"] = key.removeprefix("dlq:")
                items.append(entry)
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break
        await rc.aclose()
    except Exception as exc:
        log.warning("dead_letters_read_failed", error=str(exc))
    return build_envelope(request, {
        "items": items,
        "count": len(items),
        "queues": queues_found,
    })


@router.post("/export/bibtex")
async def export_bibtex(body: ExportRequest, _user=Depends(get_current_user)):
    """Export literature results as BibTeX format."""
    from fastapi.responses import Response
    from services.export_service import generate_bibtex

    bib_text = generate_bibtex(body.papers)
    return Response(
        content=bib_text,
        media_type="application/x-bibtex",
        headers={"Content-Disposition": "attachment; filename=literature_export.bib"},
    )


# ── Entity Detail Endpoint (§1.8) ─────────────────────────

class EntityDetailRequest(BaseModel):
    entity_id: str
    entity_type: str = ""
    entity_name: str = ""


@router.get("/entity/{entity_id}")
async def cockpit_entity_detail(
    entity_id: str,
    request: Request,
    entity_type: str = "",
    entity_name: str = "",
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Return entity detail page: AI overview, publications, patents,
    citations, clinical trials, related entities, and action buttons.

    Requirement 1.8: Entity Detail Page with AI overview, publications,
    patents, citations, clinical trials, related entities, action buttons.
    """
    t0 = time.monotonic()
    warnings: List[str] = []

    # Determine search query from entity info
    search_term = entity_name or entity_id

    # Parallel fetch: publications, clinical trials, related entities
    from services.search_engine import execute_search

    pub_task = _safe(execute_search(f"{search_term} publications", mode="auto", limit=20), "publications")
    trial_task = _safe(execute_search(f"{search_term} clinical trial", mode="auto", limit=10), "trials")
    related_task = _safe(execute_search(search_term, mode="auto", limit=30), "related")

    results = await asyncio.gather(pub_task, trial_task, related_task)

    publications = []
    clinical_trials = []
    related_entities = []
    patents = []

    for label, envelope_result in results:
        if envelope_result is None:
            warnings.append(f"{label}: fetch failed")
            continue
        try:
            cats = envelope_result.categories or {}
            if label == "publications":
                pub_cat = cats.get("publications", None)
                if pub_cat:
                    publications = (pub_cat.rows if hasattr(pub_cat, "rows") else pub_cat.get("rows", []))[:20]
            elif label == "trials":
                trial_cat = cats.get("clinical_trials", None)
                if trial_cat:
                    clinical_trials = (trial_cat.rows if hasattr(trial_cat, "rows") else trial_cat.get("rows", []))[:10]
            elif label == "related":
                for cat_name, cat_data in cats.items():
                    rows = cat_data.rows if hasattr(cat_data, "rows") else cat_data.get("rows", [])
                    for row in (rows or [])[:5]:
                        name = row.get("name") or row.get("title") or row.get("canonical_name") or ""
                        if name and name.lower() != search_term.lower():
                            related_entities.append({
                                "entityId": row.get("id") or row.get("entity_id") or name,
                                "entityType": cat_name.rstrip("s"),
                                "entityName": name,
                                "sourceCategory": cat_name,
                            })
                # Extract patents if available
                patent_cat = cats.get("patents", None)
                if patent_cat:
                    patents = (patent_cat.rows if hasattr(patent_cat, "rows") else patent_cat.get("rows", []))[:10]
        except Exception as ex:
            warnings.append(f"{label}_parse: {str(ex)[:100]}")

    # Deduplicate related entities
    seen_related = set()
    unique_related = []
    for ent in related_entities[:20]:
        key = f"{ent.get('entityType')}:{ent.get('entityId')}"
        if key not in seen_related:
            seen_related.add(key)
            unique_related.append(ent)

    # Generate AI overview (simple summary from available data)
    ai_overview = f"{entity_name or entity_id} is a {entity_type or 'biomedical entity'} "
    if publications:
        ai_overview += f"with {len(publications)} associated publications. "
    if clinical_trials:
        ai_overview += f"It appears in {len(clinical_trials)} clinical trials. "
    if unique_related:
        ai_overview += f"Related to {len(unique_related)} other entities across the knowledge base."

    # Build action buttons based on entity type
    actions = [
        {"action": "run_cockpit_search", "label": "Deep Search", "route": "/workspace"},
        {"action": "open_in_graph", "label": "View in Knowledge Graph", "route": "/graph"},
    ]
    if entity_type in ("protein", "gene"):
        actions.extend([
            {"action": "open_in_structure", "label": "View 3D Structure", "route": "/structure"},
            {"action": "run_entity_intelligence", "label": "Run Entity Intelligence", "route": "/entity-intelligence"},
        ])
    if entity_type in ("drug", "molecule", "compound"):
        actions.extend([
            {"action": "open_in_design", "label": "Open in Design Studio", "route": "/design"},
        ])
    if entity_type == "disease":
        actions.extend([
            {"action": "run_entity_intelligence", "label": "Run Disease Intelligence", "route": "/entity-intelligence"},
        ])

    elapsed_ms = round((time.monotonic() - t0) * 1000)

    return build_envelope(request, {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "entity_name": entity_name or entity_id,
        "ai_overview": ai_overview,
        "publications": publications,
        "patents": patents,
        "citations": [],  # Citations derived from publications
        "clinical_trials": clinical_trials,
        "related_entities": unique_related[:15],
        "actions": actions,
        "elapsed_ms": elapsed_ms,
    }, warnings=warnings if warnings else None)
