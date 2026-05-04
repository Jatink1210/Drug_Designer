"""Symphony background worker execution logic (§41.2).

Implements the real ARQ-based pipeline that:
1. Transitions run → RUNNING
2. Invokes specialist agents in sequence (normalise → aggregate → map)
3. Streams progress via WebSocket
4. Persists artifacts to Context Fabric
5. Handles timeouts / degraded sources → PARTIAL_SUCCESS
"""

from __future__ import annotations

import asyncio
import time
import traceback
from typing import Any, Dict, List

import structlog

try:
    import arq
    ARQ_AVAILABLE = True
except ImportError:
    ARQ_AVAILABLE = False

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Pipeline stages for disease intelligence (§41.2)
# ---------------------------------------------------------------------------
DISEASE_PIPELINE_STAGES: List[Dict[str, Any]] = [
    {"name": "normalisation", "agent": "disease_normalizer", "weight": 15},
    {"name": "target_identification", "agent": "target_expert", "weight": 20},
    {"name": "evidence_aggregation", "agent": "evidence_aggregator", "weight": 25},
    {"name": "scoring", "agent": "scorer", "weight": 15},
    {"name": "knowledge_graph", "agent": "kg_builder", "weight": 15},
    {"name": "report_generation", "agent": "report_writer", "weight": 10},
]


async def execute_disease_run(
    ctx: Dict[Any, Any], run_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Background ARQ execution pipeline for disease intelligence."""

    from services.orchestration.run_manager import RunManager
    from models.run import RunState

    rm = RunManager(db=ctx.get("db"), event_bus=ctx.get("event_bus"))

    # 1. Transition → RUNNING
    await rm.transition(run_id, RunState.RUNNING)
    log.info("symphony_run_started", run_id=run_id, type="disease_intelligence")

    degraded_sources: List[str] = []
    artifacts: List[str] = []
    cumulative_pct = 0
    start = time.time()

    # 2. Execute pipeline stages sequentially
    for stage in DISEASE_PIPELINE_STAGES:
        stage_name = stage["name"]
        agent_name = stage["agent"]
        weight = stage["weight"]

        try:
            await rm.emit_progress(
                run_id,
                stage=stage_name,
                progress_pct=cumulative_pct,
                message=f"Running {stage_name}…",
            )

            # Invoke specialist engine if available
            result = await _invoke_stage(ctx, stage_name, agent_name, payload)
            if result.get("artifact_id"):
                artifacts.append(result["artifact_id"])

            cumulative_pct += weight
            log.info(
                "stage_complete",
                run_id=run_id,
                stage=stage_name,
                elapsed=round(time.time() - start, 2),
            )
        except asyncio.TimeoutError:
            degraded_sources.append(stage_name)
            cumulative_pct += weight
            log.warning("stage_timeout", run_id=run_id, stage=stage_name)
        except Exception as exc:
            degraded_sources.append(stage_name)
            cumulative_pct += weight
            log.error(
                "stage_error",
                run_id=run_id,
                stage=stage_name,
                error=str(exc),
            )

    # 3. Save to Context Fabric
    try:
        from services.context_fabric.manager import ContextFabricManager

        cfm = ContextFabricManager()
        artifact_id = await cfm.store(
            context_type="run_result",
            data={
                "run_id": run_id,
                "artifacts": artifacts,
                "degraded_sources": degraded_sources,
                "elapsed_s": round(time.time() - start, 2),
            },
            session_id=run_id,
        )
        artifacts.append(artifact_id)
    except Exception as exc:
        log.debug("context_fabric_store_failed", error=str(exc))

    # 4. Final progress + complete
    await rm.emit_progress(run_id, stage="finalising", progress_pct=100, message="Done")
    await rm.complete(run_id, artifacts=artifacts, degraded_sources=degraded_sources)

    status = "PARTIAL_SUCCESS" if degraded_sources else "SUCCESS"
    log.info(
        "symphony_run_completed",
        run_id=run_id,
        status=status,
        elapsed=round(time.time() - start, 2),
    )
    return {"status": status, "run_id": run_id, "artifacts": artifacts}


async def _invoke_stage(
    ctx: Dict[str, Any],
    stage_name: str,
    agent_name: str,
    payload: Dict[str, Any],
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """Invoke a specialist engine for a pipeline stage with timeout."""
    try:
        from services.specialists.engine import SpecialistEngine
        from services.specialists.agent_profiles import AGENT_PROFILES

        profile = AGENT_PROFILES.get(agent_name)
        if profile is None:
            log.debug("no_agent_profile", agent=agent_name)
            return {"stage": stage_name, "status": "skipped"}

        engine = SpecialistEngine()
        result = await asyncio.wait_for(
            engine.invoke(role=profile, context=payload),
            timeout=timeout,
        )
        return {"stage": stage_name, "status": "ok", "result": result, "artifact_id": f"art_{stage_name}_{payload.get('run_id', '')}"}
    except ImportError:
        log.debug("specialist_engine_unavailable")
        return {"stage": stage_name, "status": "fallback"}
    except asyncio.TimeoutError:
        raise
    except Exception as exc:
        log.warning("stage_invoke_error", stage=stage_name, error=str(exc))
        return {"stage": stage_name, "status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# ARQ Worker Settings
# ---------------------------------------------------------------------------
if ARQ_AVAILABLE:
    class WorkerSettings:
        """Arq Worker Configuration (§41.2)."""
        functions = [execute_disease_run]
        redis_settings = arq.connections.RedisSettings()
else:
    class WorkerSettings:
        functions = [execute_disease_run]
        redis_settings = None
