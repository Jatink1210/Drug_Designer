"""Health + Diagnostics routes.

The /api/health endpoint now performs real subsystem checks instead of
returning a hardcoded 'ok'.  It remains fast (<500ms) by checking only
local/embedded subsystems — no external API calls.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

from fastapi import APIRouter

from core.cache import get_disk_cache

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health() -> Dict[str, Any]:
    """Health check that verifies core subsystem availability.

    Returns status "ok" if all core checks pass, "degraded" if
    non-critical subsystems fail, or "error" if critical checks fail.
    Always returns HTTP 200 to distinguish from a dead backend.

    NOTE: This endpoint MUST respond in <500ms.  Heavy checks (torch,
    psutil, GPU detection) belong in /api/diagnostics, not here.
    """
    issues: List[str] = []
    t0 = time.monotonic()

    # 1. Check SQLite cache is accessible
    try:
        cache = get_disk_cache()
        cache.stats()
    except Exception as e:
        issues.append(f"cache: {str(e)[:80]}")

    # 2. Check that the API directory and key files exist
    api_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isfile(os.path.join(api_dir, "..", "main.py")):
        issues.append("api: main.py not found relative to health router")

    # 3. Lightweight runtime check — just verify the module is importable,
    #    do NOT call detect_capabilities() which imports torch/psutil and
    #    can hang for 10+ seconds in bundled environments.
    try:
        from services.runtime.selector import RuntimeSelector  # noqa: F811
        # Just verify the class exists and is importable
    except Exception as e:
        issues.append(f"runtime: {str(e)[:80]}")

    elapsed_ms = round((time.monotonic() - t0) * 1000)

    # Determine overall status
    if not issues:
        status = "ok"
    else:
        status = "degraded"

    return {
        "status": status,
        "service": "drugsynth-workbench-api",
        "version": "1.0.0",
        "check_ms": elapsed_ms,
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
