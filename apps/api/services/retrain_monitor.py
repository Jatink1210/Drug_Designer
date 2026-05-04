"""Auto-Retrain Triggers (§63.4) — Periodic model drift detection.

Monitors operational signals and enqueues retraining jobs when thresholds
are exceeded.  Designed to run as a periodic ARQ cron task.
"""

from __future__ import annotations

import structlog
from datetime import datetime, timezone, timedelta

log = structlog.get_logger()

# ── Thresholds ──────────────────────────────────────────────
ADMET_FAILURE_THRESHOLD = 100      # Queue ADMET retrain after N failures
GRAPH_EDGE_DELTA_THRESHOLD = 50    # Queue GNN finetune after N new edges
CHECK_WINDOW_HOURS = 24            # Look-back window for counters


async def _count_recent_admet_failures(window: timedelta) -> int:
    """Count ADMET prediction failures in the recent time window."""
    from core.db import AsyncSessionLocal
    from models.db_tables import Run
    from sqlalchemy import select, func

    cutoff = datetime.now(timezone.utc) - window
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(Run.id))
                .where(Run.module == "admet")
                .where(Run.state == "FAILED")
                .where(Run.completed_at >= cutoff)
            )
            return result.scalar_one_or_none() or 0
    except Exception as exc:
        log.warning("retrain_monitor_admet_count_failed", error=str(exc))
        return 0


async def _count_recent_graph_edges(window: timedelta) -> int:
    """Count new graph edges added in the recent time window."""
    from core.db import AsyncSessionLocal
    from models.db_tables import Run
    from sqlalchemy import select, func

    cutoff = datetime.now(timezone.utc) - window
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(Run.id))
                .where(Run.module == "graph_ingest")
                .where(Run.state == "SUCCESS")
                .where(Run.completed_at >= cutoff)
            )
            return result.scalar_one_or_none() or 0
    except Exception as exc:
        log.warning("retrain_monitor_graph_count_failed", error=str(exc))
        return 0


async def check_retrain_triggers(ctx: dict) -> dict:
    """ARQ cron function — checks drift signals and enqueues retrains.

    Register in WorkerSettings.cron_jobs:
        cron_jobs = [cron(check_retrain_triggers, hour={0, 6, 12, 18})]
    """
    window = timedelta(hours=CHECK_WINDOW_HOURS)
    actions: list[str] = []

    # ── ADMET failure check ─────────────────────────────────
    admet_failures = await _count_recent_admet_failures(window)
    if admet_failures >= ADMET_FAILURE_THRESHOLD:
        log.warning("retrain_trigger_admet",
                     failures=admet_failures,
                     threshold=ADMET_FAILURE_THRESHOLD)
        try:
            from arq import create_pool
            from arq.connections import RedisSettings
            from config import settings
            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await pool.enqueue_job("retrain_admet_model", _queue_name="ml:retrain")
            actions.append("admet_retrain_enqueued")
        except Exception as exc:
            log.error("retrain_trigger_admet_enqueue_failed", error=str(exc))
            actions.append(f"admet_retrain_failed: {exc}")
    else:
        log.info("retrain_check_admet_ok",
                 failures=admet_failures,
                 threshold=ADMET_FAILURE_THRESHOLD)

    # ── Graph edge delta check ──────────────────────────────
    new_edges = await _count_recent_graph_edges(window)
    if new_edges >= GRAPH_EDGE_DELTA_THRESHOLD:
        log.warning("retrain_trigger_gnn",
                     new_edges=new_edges,
                     threshold=GRAPH_EDGE_DELTA_THRESHOLD)
        try:
            from arq import create_pool
            from arq.connections import RedisSettings
            from config import settings
            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await pool.enqueue_job("finetune_gnn_model", _queue_name="ml:retrain")
            actions.append("gnn_finetune_enqueued")
        except Exception as exc:
            log.error("retrain_trigger_gnn_enqueue_failed", error=str(exc))
            actions.append(f"gnn_finetune_failed: {exc}")
    else:
        log.info("retrain_check_gnn_ok",
                 new_edges=new_edges,
                 threshold=GRAPH_EDGE_DELTA_THRESHOLD)

    return {"actions": actions, "admet_failures": admet_failures, "new_edges": new_edges}
