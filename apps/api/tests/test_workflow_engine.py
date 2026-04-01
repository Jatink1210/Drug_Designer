"""Tests for workflow_engine.py — project state machine and persistence."""
from __future__ import annotations

import pytest

from services.workflow_engine import (
    ProjectStage,
    TranslationalProject,
    WorkflowEngine,
    PROJECTS_DIR,
)


@pytest.fixture(autouse=True)
def _redirect_projects_dir(tmp_path, monkeypatch):
    """Redirect PROJECTS_DIR to a temp directory."""
    monkeypatch.setattr("services.workflow_engine.PROJECTS_DIR", tmp_path)


def test_project_stage_enum():
    stages = list(ProjectStage)
    assert len(stages) == 7
    assert stages[0] == ProjectStage.INITIALIZATION
    assert stages[-1] == ProjectStage.COMPLETED


def test_create_project():
    project = WorkflowEngine.create_project("Test Project", "A test")
    assert project.name == "Test Project"
    assert project.description == "A test"
    assert project.current_stage == ProjectStage.INITIALIZATION


def test_load_project():
    project = WorkflowEngine.create_project("Round-trip")
    loaded = WorkflowEngine.load_project(project.id)
    assert loaded is not None
    assert loaded.name == "Round-trip"
    assert loaded.id == project.id


def test_load_nonexistent_project():
    result = WorkflowEngine.load_project("nonexistent-id-00000")
    assert result is None


def test_advance_project():
    project = WorkflowEngine.create_project("Advance Test")
    assert project.current_stage == ProjectStage.INITIALIZATION

    WorkflowEngine.advance_project(project.id)
    loaded = WorkflowEngine.load_project(project.id)
    assert loaded is not None
    assert loaded.current_stage == ProjectStage.LITERATURE_REVIEW


def test_add_artifact():
    project = WorkflowEngine.create_project("Artifact Test")
    updated = WorkflowEngine.add_artifact(
        project.id,
        artifact_type="pico_claim",
        content={"claim": "Drug X reduces inflammation"},
    )
    assert updated is not None
    assert len(updated.artifacts) == 1
    assert updated.artifacts[0].artifact_type == "pico_claim"


def test_list_projects():
    WorkflowEngine.create_project("Project A")
    WorkflowEngine.create_project("Project B")
    projects = WorkflowEngine.list_projects()
    names = [p.name for p in projects]
    assert "Project A" in names
    assert "Project B" in names
