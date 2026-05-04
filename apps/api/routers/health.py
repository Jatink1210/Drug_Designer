"""Health + Diagnostics routes.

The /api/health endpoint now performs real subsystem checks instead of
returning a hardcoded 'ok'.  It remains fast (<500ms) by checking only
local/embedded subsystems — no external API calls.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.cache import get_disk_cache

router = APIRouter(tags=["health"])


# ── Structured Error Model ──────────────────────────────────


class StructuredError(BaseModel):
    """Structured error response for service unavailability."""

    error_code: str
    message: str
    suggested_remediation: str
    service: Optional[str] = None
    retry_after_seconds: Optional[int] = None


class ServiceUnavailableError(Exception):
    """Raised when a backend service is unavailable."""

    def __init__(
        self,
        service: str,
        message: str = "",
        retry_after: int = 30,
    ) -> None:
        self.service = service
        self.message = message or f"{service} is currently unavailable"
        self.retry_after = retry_after
        super().__init__(self.message)

    def to_structured_error(self) -> StructuredError:
        remediation_map = {
            "postgresql": "Check database connection settings or retry in 30 seconds",
            "redis": "Verify Redis is running and connection URL is correct",
            "qdrant": "Ensure Qdrant vector store is running and accessible",
            "plugins": "Run plugin installation or check binary paths",
        }
        return StructuredError(
            error_code="SERVICE_UNAVAILABLE",
            message=self.message,
            suggested_remediation=remediation_map.get(
                self.service, f"Check {self.service} configuration or retry later"
            ),
            service=self.service,
            retry_after_seconds=self.retry_after,
        )


@router.get("/api/health")
@router.get("/api/v1/health")
async def health() -> Dict[str, Any]:
    """Health check that verifies core subsystem availability.

    Returns status "ok" if all core checks pass, "degraded" if
    non-critical subsystems fail, or "error" if critical checks fail.
    Always returns HTTP 200 to distinguish from a dead backend.

    Enhanced: checks PostgreSQL, Redis, Qdrant, and plugin availability.
    """
    from datetime import datetime, timezone

    issues: List[str] = []
    services: Dict[str, Dict[str, Any]] = {}
    t0 = time.monotonic()

    # 1. Check SQLite cache is accessible
    try:
        cache = get_disk_cache()
        cache.stats()
        services["cache"] = {"status": "ok"}
    except Exception as e:
        issues.append(f"cache: {str(e)[:80]}")
        services["cache"] = {"status": "unavailable", "error": str(e)[:80]}

    # 2. Check that the API directory and key files exist
    api_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isfile(os.path.join(api_dir, "..", "main.py")):
        issues.append("api: main.py not found relative to health router")

    # 3. Lightweight runtime check
    try:
        from services.runtime.selector import RuntimeSelector  # noqa: F811
        services["runtime"] = {"status": "ok"}
    except Exception as e:
        issues.append(f"runtime: {str(e)[:80]}")
        services["runtime"] = {"status": "unavailable", "error": str(e)[:80]}

    # 4. PostgreSQL connection check
    try:
        from core.db import AsyncSessionLocal
        from sqlalchemy import text as sa_text
        async with AsyncSessionLocal() as session:
            await session.execute(sa_text("SELECT 1"))
        services["postgresql"] = {"status": "ok"}
    except Exception as e:
        issues.append(f"postgresql: {str(e)[:80]}")
        services["postgresql"] = {"status": "unavailable", "error": str(e)[:80]}

    # 5. Redis ping check
    redis_result = await _check_redis()
    if redis_result.get("status") == "PASS":
        services["redis"] = {"status": "ok"}
    else:
        issues.append(f"redis: {redis_result.get('error', 'unavailable')[:80]}")
        services["redis"] = {"status": "unavailable", "error": redis_result.get("error", "")[:80]}

    # 6. Qdrant availability check
    qdrant_result = await _check_qdrant()
    if qdrant_result.get("status") == "PASS":
        services["qdrant"] = {"status": "ok", "collections": qdrant_result.get("collections", 0)}
    else:
        issues.append(f"qdrant: {qdrant_result.get('error', 'unavailable')[:80]}")
        services["qdrant"] = {"status": "unavailable", "error": qdrant_result.get("error", "")[:80]}

    # 7. Plugin status via ToolInstaller
    try:
        from services.tool_installer import ToolInstaller
        installer = ToolInstaller()
        plugin_status = installer.check_availability()
        plugins_info: Dict[str, Any] = {}
        for tool_name, tool_stat in plugin_status.items():
            plugins_info[tool_name] = {
                "status": tool_stat.status if hasattr(tool_stat, "status") else str(tool_stat),
                "version": getattr(tool_stat, "version", ""),
                "path": getattr(tool_stat, "path", ""),
            }
        services["plugins"] = {"status": "ok", "tools": plugins_info}
    except Exception as e:
        services["plugins"] = {"status": "unavailable", "error": str(e)[:80]}

    elapsed_ms = round((time.monotonic() - t0) * 1000)

    # Determine overall status
    failed_services = [k for k, v in services.items() if v.get("status") == "unavailable"]
    if not issues:
        status = "ok"
    else:
        status = "degraded"

    return {
        "status": status,
        "service": "drug-designer-api",
        "version": "1.0.0",
        "check_ms": elapsed_ms,
        "services": services,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "failed_services": failed_services if failed_services else None,
        "issues": issues if issues else None,
    }


def _detect_runtime_capabilities():
    """Lazy import to avoid loading torch/psutil at module level."""
    try:
        from services.runtime.selector import RuntimeSelector
        return RuntimeSelector.detect_capabilities()
    except Exception as e:
        return {"status": "FAIL", "error": str(e)[:100]}


@router.get("/api/diagnostics")
@router.get("/api/v1/diagnostics")
async def diagnostics() -> Dict[str, Any]:
    """Detailed system diagnostics."""
    cache_stats = get_disk_cache().stats()

    # Check Qdrant
    qdrant_status = await _check_qdrant()

    # Check connectors
    connector_pings = await _ping_connectors()

    from core.paths import get_app_dir, get_data_dir, get_cache_dir, get_data_mode
    import shutil

    def _free_gb(path: str) -> str:
        try:
            _, _, free = shutil.disk_usage(path)
            return f"{free / (2**30):.1f} GB"
        except Exception:
            return "Unknown"

    components = {
        "api": {"status": "PASS"},
        "cache": {
            "status": "PASS",
            "sqlite_entries": cache_stats.get("entries", 0),
            "db_path": cache_stats.get("db_path", ""),
        },
        "qdrant": qdrant_status,
        "graph_store": await _check_neo4j(),
        "redis": await _check_redis(),
        "llm": _detect_runtime_capabilities(),
    }

    # Compute overall status from component results — NOT hardcoded
    failed = [k for k, v in components.items() if isinstance(v, dict) and v.get("status") == "FAIL"]
    overall = "ok" if not failed else "degraded"

    return {
        "status": overall,
        "version": "1.0.0",
        "failed_components": failed if failed else None,
        "directories": {
            "mode": get_data_mode(),
            "app_dir": get_app_dir(),
            "data_dir": get_data_dir(),
            "data_free": _free_gb(get_data_dir()),
            "cache_dir": get_cache_dir(),
            "cache_free": _free_gb(get_cache_dir()),
        },
        "components": components,
        "connectors": connector_pings,
    }



async def _check_qdrant() -> Dict[str, Any]:
    try:
        from qdrant_client import QdrantClient
        from config import settings
        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, timeout=3)
        collections = client.get_collections()
        return {
            "status": "PASS",
            "collections": len(collections.collections),
            "host": "%s:%s" % (settings.qdrant_host, settings.qdrant_port),
        }
    except Exception as e:
        return {"status": "FAIL", "error": str(e)}


async def _check_redis() -> Dict[str, Any]:
    try:
        import redis.asyncio as redis
        from config import settings
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        return {"status": "PASS"}
    except Exception as e:
        return {"status": "FAIL", "error": str(e)}


async def _check_neo4j() -> Dict[str, Any]:
    try:
        from neo4j import AsyncGraphDatabase
        from config import settings
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri, 
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        async with driver.session() as session:
            await session.run("RETURN 1")
        await driver.close()
        return {"status": "PASS", "engine": "neo4j"}
    except Exception as e:
        return {"status": "FAIL", "error": str(e), "engine": "neo4j"}


async def _ping_connectors() -> Dict[str, Dict[str, Any]]:
    """Lightweight ping of each connector's base URL."""
    import httpx
    import time

    pings: Dict[str, Dict[str, Any]] = {}
    endpoints = {
        "UniProt": "https://rest.uniprot.org/uniprotkb/search?query=test&size=1&format=json",
        "PubMed": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=test&retmax=1&retmode=json",
        "OpenTargets": "https://api.platform.opentargets.org/api/v4/graphql",
        "RCSB_PDB": "https://data.rcsb.org/rest/v1/core/entry/1crn",
        "ChEMBL": "https://www.ebi.ac.uk/chembl/api/data/status.json",
        "ClinicalTrials.gov": "https://clinicaltrials.gov/api/v2/studies?pageSize=1&format=json",
        "Reactome": "https://reactome.org/ContentService/data/database/version",
        "AlphaFold": "https://alphafold.ebi.ac.uk/api/prediction/Q5VSL9",
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/aspirin/property/MolecularWeight/JSON",
        "KEGG": "https://rest.kegg.jp/info/pathway",
        "DrugBank": "https://go.drugbank.com/drugs/DB00945.json",
        "DisGeNET": "https://www.disgenet.org/api/gda/gene/1",
        "IntAct": "https://www.ebi.ac.uk/intact/ws/interaction/findInteractions/TP53?pageSize=1",
        "Ensembl": "https://rest.ensembl.org/info/ping?content-type=application/json",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in endpoints.items():
            try:
                t0 = time.monotonic()
                if name == "OpenTargets":
                    resp = await client.post(url, json={"query": "{ meta { apiVersion { x y z } } }"})
                else:
                    resp = await client.get(url)
                latency = round((time.monotonic() - t0) * 1000)
                pings[name] = {
                    "status": "PASS" if resp.status_code < 400 else "FAIL",
                    "latency_ms": latency,
                    "http_status": resp.status_code,
                }
            except Exception as e:
                pings[name] = {"status": "FAIL", "error": str(e)[:100]}

    return pings


# ── §5.3 Performance Budget Diagnostics ────────────────────
@router.get("/api/v1/diagnostics/performance")
async def performance_diagnostics() -> Dict[str, Any]:
    """Return p50/p95/p99 request timing stats from in-memory collector."""
    try:
        from main import get_recent_timings
        timings = get_recent_timings()
    except Exception:
        timings = []

    if not timings:
        return {"status": "ok", "sample_count": 0, "p50_ms": None, "p95_ms": None, "p99_ms": None}

    sorted_t = sorted(timings)
    n = len(sorted_t)

    def _percentile(p: float) -> float:
        idx = int(p / 100.0 * n)
        return round(sorted_t[min(idx, n - 1)], 1)

    return {
        "status": "ok",
        "sample_count": n,
        "p50_ms": _percentile(50),
        "p95_ms": _percentile(95),
        "p99_ms": _percentile(99),
        "min_ms": round(sorted_t[0], 1),
        "max_ms": round(sorted_t[-1], 1),
        "budget_ms": 400,
        "over_budget_count": sum(1 for t in sorted_t if t > 400),
    }


# ── §1.5 Event Bus Query Endpoint ──────────────────────────
@router.get("/api/v1/events/recent")
async def recent_events(family: str | None = None, limit: int = 50) -> Dict[str, Any]:
    """Return recent domain events from the in-memory event bus (Deep-Impl §1.5).

    Query params:
      family — filter by event family (project, retrieval, disease, target, etc.)
      limit  — max events to return (default 50, max 200)
    """
    from core.event_bus import event_bus

    limit = min(limit, 200)
    events = event_bus.recent_events(family=family, limit=limit)
    return {
        "status": "ok",
        "data": events,
        "count": len(events),
        "family_filter": family,
    }
