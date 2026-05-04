"""Phase 1 cockpit run persistence + background execution regressions."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import models.db_tables  # noqa: F401
import models.user  # noqa: F401
from core.db import Base, get_db
from main import app
from models.db_tables import CockpitRun
from routers import cockpit


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path):
    db_path = tmp_path / "cockpit-runs.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield factory
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_background_cockpit_analysis_completes_and_persists_run(
    client: AsyncClient,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DRUGDESIGNER_AUTH_ENABLED", "false")

    async def fake_payload(body, *, run_id=None, ws=None):
        return {
            "query": body.query,
            "run_id": run_id,
            "timestamp": "2026-05-04T00:00:00Z",
            "summary": "queued cockpit summary",
            "categories": [],
            "graph": {"nodes": [], "edges": []},
            "stats": {
                "total_results": 0,
                "categories_found": 0,
                "sources_queried": 0,
                "pubmed_count": None,
                "clinical_trials_count": 0,
                "overall_confidence": 0.0,
                "contradictions_count": 0,
            },
            "source_breakdown": {},
            "evidence": {"top_citations": [], "confidence": 0.0},
            "contradictions": [],
            "disease_intelligence": [],
            "target_prioritization": [],
            "graph_reasoning": [],
            "pathways": [],
            "structures": [],
            "admet": [],
            "retrosynthesis": [],
            "clinical_trials": [],
            "pico": [],
            "population_genomics": {},
            "syntharena": {},
            "literature_table": [],
            "filtered_literature": [],
            "filter_info": {},
            "similarities": [],
            "nuanced_relationships": [],
            "terms_map": {},
            "term_frequency": {},
            "literature_kg": {},
            "mesh_terminology": {},
            "literature_stats": {},
            "paper_sentences": [],
            "evidence_links": {},
            "lit_structures": [],
            "llm_contradictions": [],
            "traceable_summary": {},
            "unified_pathways": {},
            "mechanism_clusters": {},
            "timings": {"search_ms": 12.0, "connector.pubmed.ms": 4.0, "total_ms": 30.0},
            "errors": [],
            "latency_ms": 30,
            "degraded_sources": [],
            "search_provenance": {"cache_summary": {"response_cache_hit": False}},
            "query_classification": {"query_type": "general", "genes": [], "disease": None},
            "entities_extracted": {"genes": [], "proteins": [], "diseases": [], "drugs": [], "structures": []},
            "execution_mode": body.execution_mode,
            "latency_budget": dict(cockpit.COCKPIT_LATENCY_BUDGET),
        }

    monkeypatch.setattr(cockpit, "_run_cockpit_analysis_payload", fake_payload)

    response = await client.post(
        "/api/v1/cockpit/analyze",
        json={"query": "aspirin", "limit": 5, "execution_mode": "background"},
    )
    assert response.status_code == 200
    accepted = response.json()["data"]
    assert accepted["status"] == "running"
    assert accepted["stream_channel"].endswith(accepted["run_id"])

    run_id = accepted["run_id"]

    for _ in range(10):
        status_response = await client.get(f"/api/v1/cockpit/runs/{run_id}")
        assert status_response.status_code == 200
        status_payload = status_response.json()["data"]
        if status_payload["status"] == "completed":
            break
        await asyncio.sleep(0.05)
    else:
        pytest.fail("cockpit background run did not complete in time")

    assert status_payload["result_summary"]["query"] == "aspirin"
    assert status_payload["provenance"]["execution_mode"] == "background"
    assert status_payload["latency_budget"]["first_progress_ms"] == cockpit.COCKPIT_LATENCY_BUDGET["first_progress_ms"]

    async with session_factory() as session:
        run = await session.get(CockpitRun, run_id)
        assert run is not None
        assert run.status == "completed"
        assert run.result_summary["run_id"] == run_id


@pytest.mark.asyncio
async def test_sync_cockpit_analysis_persists_run_result(
    client: AsyncClient,
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DRUGDESIGNER_AUTH_ENABLED", "false")

    async def fake_payload(body, *, run_id=None, ws=None):
        return {
            "query": body.query,
            "run_id": run_id,
            "timestamp": "2026-05-04T00:00:00Z",
            "summary": "sync cockpit summary",
            "categories": [],
            "graph": {"nodes": [], "edges": []},
            "stats": {
                "total_results": 0,
                "categories_found": 0,
                "sources_queried": 0,
                "pubmed_count": None,
                "clinical_trials_count": 0,
                "overall_confidence": 0.0,
                "contradictions_count": 0,
            },
            "source_breakdown": {},
            "evidence": {"top_citations": [], "confidence": 0.0},
            "contradictions": [],
            "disease_intelligence": [],
            "target_prioritization": [],
            "graph_reasoning": [],
            "pathways": [],
            "structures": [],
            "admet": [],
            "retrosynthesis": [],
            "clinical_trials": [],
            "pico": [],
            "population_genomics": {},
            "syntharena": {},
            "literature_table": [],
            "filtered_literature": [],
            "filter_info": {},
            "similarities": [],
            "nuanced_relationships": [],
            "terms_map": {},
            "term_frequency": {},
            "literature_kg": {},
            "mesh_terminology": {},
            "literature_stats": {},
            "paper_sentences": [],
            "evidence_links": {},
            "lit_structures": [],
            "llm_contradictions": [],
            "traceable_summary": {},
            "unified_pathways": {},
            "mechanism_clusters": {},
            "timings": {"search_ms": 8.0, "total_ms": 18.0},
            "errors": [],
            "latency_ms": 18,
            "degraded_sources": [],
            "search_provenance": {"cache_summary": {"response_cache_hit": False}},
            "query_classification": {"query_type": "general", "genes": [], "disease": None},
            "entities_extracted": {"genes": [], "proteins": [], "diseases": [], "drugs": [], "structures": []},
            "execution_mode": body.execution_mode,
            "latency_budget": dict(cockpit.COCKPIT_LATENCY_BUDGET),
        }

    monkeypatch.setattr(cockpit, "_run_cockpit_analysis_payload", fake_payload)

    response = await client.post(
        "/api/v1/cockpit/analyze",
        json={"query": "ibuprofen", "limit": 5, "execution_mode": "sync"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["query"] == "ibuprofen"

    recent = await client.get("/api/v1/cockpit/recent-runs?limit=1")
    assert recent.status_code == 200
    latest = recent.json()["data"]["recent_runs"][0]
    assert latest["query"] == "ibuprofen"
    assert latest["status"] == "completed"