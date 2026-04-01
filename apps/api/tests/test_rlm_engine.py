"""Tests for the RLM engine — real LLM integration with fallbacks."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.rlm_engine import RLMEngine


# ── init ──────────────────────────────────────────────────────

def test_rlm_engine_init():
    engine = RLMEngine(query="test query", constraints={"exclude": ["toxicity"]})
    assert engine.query == "test query"
    assert engine.constraints == {"exclude": ["toxicity"]}
    assert engine.max_steps == 10
    assert engine.current_step == 0
    assert engine.memory == []
    assert engine.evidence_refs == []


def test_rlm_engine_init_with_project_id():
    engine = RLMEngine(query="q", constraints={}, project_id="proj_123")
    assert engine.project_id == "proj_123"


# ── _plan_subtasks ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_plan_subtasks_no_llm():
    """Without LLM, falls back to keyword split."""
    engine = RLMEngine(query="diabetes and hypertension", constraints={})
    with patch.object(RLMEngine, "_get_runtime", return_value=None):
        subtasks = await engine._plan_subtasks()
    assert len(subtasks) >= 2
    assert any("diabetes" in s.lower() for s in subtasks)
    assert any("hypertension" in s.lower() for s in subtasks)


@pytest.mark.asyncio
async def test_plan_subtasks_simple_query_no_llm():
    """Simple query without conjunctions returns the query itself."""
    engine = RLMEngine(query="GLP1R", constraints={})
    with patch.object(RLMEngine, "_get_runtime", return_value=None):
        subtasks = await engine._plan_subtasks()
    assert subtasks == ["GLP1R"]


@pytest.mark.asyncio
async def test_plan_subtasks_with_mock_llm():
    """LLM response is parsed into subtask list."""
    mock_runtime = MagicMock()
    mock_runtime.health_check.return_value = {"status": "PASS"}
    mock_runtime.chat = AsyncMock(
        return_value='["Search for GLP1R targets", "Find diabetes drugs"]'
    )

    engine = RLMEngine(query="T2D targets", constraints={})
    with patch.object(RLMEngine, "_get_runtime", return_value=mock_runtime):
        subtasks = await engine._plan_subtasks()
    assert subtasks == ["Search for GLP1R targets", "Find diabetes drugs"]


@pytest.mark.asyncio
async def test_plan_subtasks_llm_bad_json_falls_back():
    """If LLM returns bad JSON, falls back to keyword split."""
    mock_runtime = MagicMock()
    mock_runtime.health_check.return_value = {"status": "PASS"}
    mock_runtime.chat = AsyncMock(return_value="I don't know")

    engine = RLMEngine(query="cancer and inflammation", constraints={})
    with patch.object(RLMEngine, "_get_runtime", return_value=mock_runtime):
        subtasks = await engine._plan_subtasks()
    # Falls back to keyword split
    assert len(subtasks) >= 2


# ── _apply_constraints ────────────────────────────────────────

def test_apply_constraints_exclude():
    engine = RLMEngine(query="q", constraints={"exclude": ["toxicity"]})
    entities = {
        "protein": [
            {"name": "GLP1R", "description": "Receptor"},
            {"name": "Bad Target", "description": "High toxicity risk"},
        ]
    }
    result = engine._apply_constraints(entities)
    assert len(result["protein"]) == 1
    assert result["protein"][0]["name"] == "GLP1R"


def test_apply_constraints_require():
    engine = RLMEngine(query="q", constraints={"require": ["kinase"]})
    entities = {
        "protein": [
            {"name": "EGFR kinase", "description": "Tyrosine receptor"},
            {"name": "GLP1R", "description": "G-protein coupled receptor"},
        ]
    }
    result = engine._apply_constraints(entities)
    assert len(result["protein"]) == 1
    assert result["protein"][0]["name"] == "EGFR kinase"


def test_apply_constraints_no_constraints():
    engine = RLMEngine(query="q", constraints={})
    entities = {"protein": [{"name": "A"}, {"name": "B"}]}
    result = engine._apply_constraints(entities)
    assert len(result["protein"]) == 2


def test_apply_constraints_empty_after_filter():
    engine = RLMEngine(query="q", constraints={"exclude": ["everything"]})
    entities = {"protein": [{"name": "everything is bad", "description": ""}]}
    result = engine._apply_constraints(entities)
    assert "protein" not in result


# ── _check_contradictions ─────────────────────────────────────

@pytest.mark.asyncio
async def test_check_contradictions_integration():
    """Calls detect_contradictions with the correct structure."""
    engine = RLMEngine(query="test", constraints={})
    entities = {
        "protein": [
            {"name": "A", "description": "inhibits growth", "id": "p1"},
            {"name": "B", "description": "activates growth", "id": "p2"},
        ]
    }
    # Run real contradiction detector (keyword heuristic)
    result = await engine._check_contradictions(entities)
    assert isinstance(result, list)
    # Should find "inhibits" vs "activates" contradiction
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_check_contradictions_empty():
    engine = RLMEngine(query="test", constraints={})
    result = await engine._check_contradictions({})
    assert result == []


# ── _search_documents ─────────────────────────────────────────

def test_search_documents_empty(tmp_store):
    """Gracefully returns [] when no documents are indexed."""
    engine = RLMEngine(query="test query", constraints={})
    result = engine._search_documents()
    assert result == []


# ── _synthesize ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_synthesize_no_llm():
    """Rule-based synthesis returns sorted targets."""
    engine = RLMEngine(query="diabetes targets", constraints={})
    entities = {
        "protein": [
            {"name": "GLP1R", "_confidence": 0.9},
            {"name": "INSR", "_confidence": 0.7},
        ]
    }
    with patch.object(RLMEngine, "_get_runtime", return_value=None):
        result = await engine._synthesize(entities, [], [])
    assert "GLP1R" in result["top_targets"]
    assert "INSR" in result["top_targets"]
    assert "diabetes targets" in result["synthesis"]
    assert result["warnings"] == []


@pytest.mark.asyncio
async def test_synthesize_with_contradictions():
    engine = RLMEngine(query="test", constraints={})
    entities = {"protein": [{"name": "A", "_confidence": 0.5}]}
    contras = [{"severity": "high", "explanation": "Opposing claims"}]
    with patch.object(RLMEngine, "_get_runtime", return_value=None):
        result = await engine._synthesize(entities, contras, [])
    assert len(result["warnings"]) == 1
    assert "Opposing claims" in result["warnings"][0]


@pytest.mark.asyncio
async def test_synthesize_no_results():
    engine = RLMEngine(query="nonexistent", constraints={})
    with patch.object(RLMEngine, "_get_runtime", return_value=None):
        result = await engine._synthesize({}, [], [])
    assert result["top_targets"] == []
    assert "No results found" in result["synthesis"]


# ── full run ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_run_no_llm(tmp_store):
    """Full run() completes without LLM and returns real structure."""
    from services.job_logger import JobLogger

    engine = RLMEngine(query="GLP1R", constraints={})

    # Mock _gather_evidence to avoid real network calls
    mock_entities = {
        "protein": [
            {"id": "p1", "name": "GLP1R", "_confidence": 0.8, "description": "Receptor"},
        ]
    }

    with patch.object(RLMEngine, "_get_runtime", return_value=None):
        with patch.object(
            RLMEngine, "_gather_evidence",
            new_callable=AsyncMock, return_value=mock_entities,
        ):
            with patch("services.figure_generator.FigureGenerator.generate_job_artifacts"):
                job_logger = JobLogger(job_name="test_run")
                with job_logger:
                    result = await engine.run(job_logger=job_logger)

    assert result["status"] == "completed"
    assert result["llm_available"] is False
    assert "GLP1R" in result["result"]["top_targets"]
    assert isinstance(result["result"]["evidence_count"], int)
    assert isinstance(result["result"]["synthesis"], str)


@pytest.mark.asyncio
async def test_full_run_result_structure(tmp_store):
    """Validates return dict has all required keys."""
    from services.job_logger import JobLogger

    engine = RLMEngine(query="test", constraints={})

    with patch.object(RLMEngine, "_get_runtime", return_value=None):
        with patch.object(
            RLMEngine, "_gather_evidence",
            new_callable=AsyncMock, return_value={},
        ):
            with patch("services.figure_generator.FigureGenerator.generate_job_artifacts"):
                job_logger = JobLogger(job_name="test_structure")
                with job_logger:
                    result = await engine.run(job_logger=job_logger)

    assert "query" in result
    assert "status" in result
    assert "steps_taken" in result
    assert "llm_available" in result
    assert "result" in result
    inner = result["result"]
    assert "top_targets" in inner
    assert "warnings" in inner
    assert "evidence_count" in inner
    assert "contradictions_found" in inner
    assert "documents_searched" in inner
    assert "synthesis" in inner


@pytest.mark.asyncio
async def test_step_queue_events(tmp_store):
    """Verifies step events are pushed to asyncio.Queue."""
    from services.job_logger import JobLogger

    engine = RLMEngine(query="test", constraints={})
    queue: asyncio.Queue = asyncio.Queue()

    with patch.object(RLMEngine, "_get_runtime", return_value=None):
        with patch.object(
            RLMEngine, "_gather_evidence",
            new_callable=AsyncMock, return_value={},
        ):
            with patch("services.figure_generator.FigureGenerator.generate_job_artifacts"):
                job_logger = JobLogger(job_name="test_queue")
                with job_logger:
                    await engine.run(job_logger=job_logger, step_queue=queue)

    # Should have 6 step events + 1 done event = 7 total
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    step_events = [e for e in events if e.get("type") == "step"]
    done_events = [e for e in events if e.get("type") == "done"]

    assert len(step_events) == 6  # plan, evidence, filter, contradictions, docs, synthesis
    assert len(done_events) == 1
    assert done_events[0]["type"] == "done"

    # Verify step names
    names = [e["name"] for e in step_events]
    assert "Query Decomposition & Planning" in names
    assert "Evidence Retrieval" in names
    assert "Constraint Filtering" in names
    assert "Counter-Evidence Analysis" in names
    assert "Document Intelligence (Doc-Tree)" in names
    assert "Final Synthesis" in names


# ── _llm_call ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_call_returns_fallback_when_no_runtime():
    engine = RLMEngine(query="q", constraints={})
    with patch.object(RLMEngine, "_get_runtime", return_value=None):
        result = await engine._llm_call([{"role": "user", "content": "hi"}], fallback="nope")
    assert result == "nope"


@pytest.mark.asyncio
async def test_llm_call_returns_response():
    mock_runtime = MagicMock()
    mock_runtime.health_check.return_value = {"status": "PASS"}
    mock_runtime.chat = AsyncMock(return_value="hello world")

    engine = RLMEngine(query="q", constraints={})
    with patch.object(RLMEngine, "_get_runtime", return_value=mock_runtime):
        result = await engine._llm_call([{"role": "user", "content": "hi"}])
    assert result == "hello world"


@pytest.mark.asyncio
async def test_llm_call_handles_exception():
    mock_runtime = MagicMock()
    mock_runtime.health_check.return_value = {"status": "PASS"}
    mock_runtime.chat = AsyncMock(side_effect=Exception("boom"))

    engine = RLMEngine(query="q", constraints={})
    with patch.object(RLMEngine, "_get_runtime", return_value=mock_runtime):
        result = await engine._llm_call(
            [{"role": "user", "content": "hi"}], fallback="safe"
        )
    assert result == "safe"
