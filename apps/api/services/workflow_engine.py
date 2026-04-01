"""Translational Workflow Engine — state machine for end-to-end research pipelines."""

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
import time
from pydantic import BaseModel, Field

PROJECTS_DIR = Path("data/projects")
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
log = logging.getLogger(__name__)


class ProjectStage(str, Enum):
    INITIALIZATION = "initialization"
    LITERATURE_REVIEW = "literature_review"
    TARGET_VALIDATION = "target_validation"
    MOLECULE_SCREENING = "molecule_screening"
    CLINICAL_TRIAL_EVAL = "clinical_trial_eval"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"

STAGE_ORDER = list(ProjectStage)

def _uuid() -> str:
    return str(uuid.uuid4())

def _now() -> float:
    return time.time()


class ResearchArtifact(BaseModel):
    id: str = Field(default_factory=_uuid)
    artifact_type: str  # "pico_claim", "target_score", "molecule", "trial_summary"
    content: Dict[str, Any]
    created_at: float = Field(default_factory=_now)


class TranslationalProject(BaseModel):
    id: str = Field(default_factory=_uuid)
    name: str
    description: str = ""
    current_stage: ProjectStage = ProjectStage.INITIALIZATION
    created_at: float = Field(default_factory=_now)
    updated_at: float = Field(default_factory=_now)
    artifacts: List[ResearchArtifact] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    def next_stage(self) -> None:
        idx = STAGE_ORDER.index(self.current_stage)
        if idx < len(STAGE_ORDER) - 1:
            self.current_stage = STAGE_ORDER[idx + 1]
            self.updated_at = _now()


class WorkflowEngine:
    """Manages persistence and progression of translational projects."""

    @staticmethod
    def _project_path(project_id: str) -> Path:
        return PROJECTS_DIR / f"{project_id}.json"

    @classmethod
    def create_project(cls, name: str, description: str = "") -> TranslationalProject:
        project = TranslationalProject(name=name, description=description)
        cls.save_project(project)
        return project

    @classmethod
    def load_project(cls, project_id: str) -> Optional[TranslationalProject]:
        path = cls._project_path(project_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return TranslationalProject(**json.load(f))

    @classmethod
    def save_project(cls, project: TranslationalProject) -> None:
        project.updated_at = _now()
        path = cls._project_path(project.id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(project.model_dump_json(indent=2))

    @classmethod
    def list_projects(cls) -> List[TranslationalProject]:
        projects = []
        for path in PROJECTS_DIR.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    projects.append(TranslationalProject(**json.load(f)))
            except Exception:
                log.debug("Skipping malformed project file: %s", path)
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)

    @classmethod
    def add_artifact(cls, project_id: str, artifact_type: str, content: Dict[str, Any]) -> Optional[TranslationalProject]:
        project = cls.load_project(project_id)
        if not project:
            return None
        project.artifacts.append(ResearchArtifact(artifact_type=artifact_type, content=content))
        cls.save_project(project)
        return project

    @classmethod
    def advance_project(cls, project_id: str) -> Optional[TranslationalProject]:
        project = cls.load_project(project_id)
        if not project:
            return None
        project.next_stage()
        cls.save_project(project)
        return project
