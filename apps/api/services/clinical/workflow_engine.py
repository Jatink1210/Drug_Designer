"""Clinical Workflow Engine — 10-step sequential clinical design workflow.

Enforces step ordering, evidence requirements, justification for skips,
Go/No-Go summary generation, and state persistence.

Requirements 7.1-7.6: Clinical Design Workflow Enforcement.
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

WORKFLOW_DIR = Path("data/files/workflows")
WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


CLINICAL_STEPS = [
    "EHR Data Ingestion",
    "AI Phenotype Clustering",
    "DL Tissue Analysis",
    "Neural Network Biomarker Quantification",
    "Genomic Sequencing",
    "DL Pathogenicity Prediction",
    "Knowledge Graph Cross-Referencing",
    "AI Disruption Modeling",
    "AI Targeted Drug Matching",
    "Advanced Therapy Stratification",
]


class WorkflowStep(BaseModel):
    step_number: int
    step_name: str
    status: StepStatus = StepStatus.PENDING
    evidence_ids: List[str] = Field(default_factory=list)
    skip_justification: Optional[str] = None
    outputs: Dict[str, Any] = Field(default_factory=dict)
    completed_at: Optional[str] = None


class GoNoGoSummary(BaseModel):
    workflow_id: str
    decision: str = "pending"  # "go", "no_go", "pending"
    rationale: str = ""
    steps_completed: int = 0
    steps_skipped: int = 0
    total_evidence_items: int = 0
    step_summaries: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: str = ""


class ClinicalWorkflow(BaseModel):
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    steps: List[WorkflowStep] = Field(default_factory=list)
    current_step: int = 1
    go_nogo_summary: Optional[GoNoGoSummary] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StepResult(BaseModel):
    success: bool
    message: str
    step_number: int
    status: StepStatus
    workflow_id: str


class ClinicalWorkflowEngine:
    """Manages 10-step clinical workflow with enforcement rules.

    - Step ordering: step N requires steps 1..N-1 completed or skipped
    - Evidence requirement: completion requires non-empty evidence_ids
    - Skip justification: skipping requires non-empty justification
    - Go/No-Go: aggregates all step data into decision summary
    - Persistence: saves/loads workflow state to disk (or DB)
    """

    @staticmethod
    def _workflow_path(workflow_id: str) -> Path:
        return WORKFLOW_DIR / f"{workflow_id}.json"

    @classmethod
    def create_workflow(cls, project_id: str = "") -> ClinicalWorkflow:
        """Create a new 10-step clinical workflow."""
        workflow = ClinicalWorkflow(project_id=project_id)
        workflow.steps = [
            WorkflowStep(step_number=i + 1, step_name=name)
            for i, name in enumerate(CLINICAL_STEPS)
        ]
        cls.save_workflow(workflow)
        return workflow

    @classmethod
    def load_workflow(cls, workflow_id: str) -> Optional[ClinicalWorkflow]:
        """Load workflow from persistence."""
        path = cls._workflow_path(workflow_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return ClinicalWorkflow(**json.load(f))
        except Exception as e:
            log.error("Failed to load workflow %s: %s", workflow_id, e)
            return None

    @classmethod
    def save_workflow(cls, workflow: ClinicalWorkflow) -> None:
        """Persist workflow state."""
        workflow.updated_at = datetime.now(timezone.utc).isoformat()
        path = cls._workflow_path(workflow.workflow_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(workflow.model_dump_json(indent=2))

    @classmethod
    def list_workflows(cls) -> List[ClinicalWorkflow]:
        """List all workflows."""
        workflows = []
        for path in WORKFLOW_DIR.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    workflows.append(ClinicalWorkflow(**json.load(f)))
            except Exception:
                pass
        return sorted(workflows, key=lambda w: w.updated_at, reverse=True)

    @classmethod
    def attempt_step(
        cls,
        workflow_id: str,
        step_number: int,
        action: str = "complete",  # "complete" or "skip"
        evidence_ids: Optional[List[str]] = None,
        skip_justification: Optional[str] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ) -> StepResult:
        """Attempt to complete or skip a workflow step.

        Validates:
        - Steps 1..N-1 are completed or skipped before step N
        - Evidence_ids is non-empty for completion
        - Skip_justification is non-empty and non-whitespace for skip
        """
        workflow = cls.load_workflow(workflow_id)
        if not workflow:
            return StepResult(
                success=False, message=f"Workflow {workflow_id} not found",
                step_number=step_number, status=StepStatus.PENDING, workflow_id=workflow_id,
            )

        if step_number < 1 or step_number > 10:
            return StepResult(
                success=False, message=f"Step number must be between 1 and 10, got {step_number}",
                step_number=step_number, status=StepStatus.PENDING, workflow_id=workflow_id,
            )

        step = workflow.steps[step_number - 1]

        # Validate step ordering: all prior steps must be completed or skipped
        for prior in workflow.steps[:step_number - 1]:
            if prior.status == StepStatus.PENDING or prior.status == StepStatus.IN_PROGRESS:
                return StepResult(
                    success=False,
                    message=f"Cannot attempt step {step_number}: step {prior.step_number} ({prior.step_name}) is still {prior.status.value}",
                    step_number=step_number, status=step.status, workflow_id=workflow_id,
                )

        if action == "complete":
            # Validate evidence requirement
            if not evidence_ids or len(evidence_ids) == 0:
                return StepResult(
                    success=False,
                    message=f"Step {step_number} completion requires at least one evidence item",
                    step_number=step_number, status=step.status, workflow_id=workflow_id,
                )
            step.status = StepStatus.COMPLETED
            step.evidence_ids = evidence_ids
            step.outputs = outputs or {}
            step.completed_at = datetime.now(timezone.utc).isoformat()

        elif action == "skip":
            # Validate justification requirement
            if not skip_justification or not skip_justification.strip():
                return StepResult(
                    success=False,
                    message=f"Step {step_number} skip requires a non-empty justification",
                    step_number=step_number, status=step.status, workflow_id=workflow_id,
                )
            step.status = StepStatus.SKIPPED
            step.skip_justification = skip_justification.strip()
            step.completed_at = datetime.now(timezone.utc).isoformat()

        else:
            return StepResult(
                success=False, message=f"Unknown action: {action}",
                step_number=step_number, status=step.status, workflow_id=workflow_id,
            )

        # Update current step pointer
        for s in workflow.steps:
            if s.status == StepStatus.PENDING:
                workflow.current_step = s.step_number
                break
        else:
            workflow.current_step = 10  # All done

        cls.save_workflow(workflow)

        return StepResult(
            success=True,
            message=f"Step {step_number} ({step.step_name}) {action}d successfully",
            step_number=step_number, status=step.status, workflow_id=workflow_id,
        )

    @classmethod
    def generate_go_nogo(cls, workflow_id: str) -> Optional[GoNoGoSummary]:
        """Generate Go/No-Go summary from all step data."""
        workflow = cls.load_workflow(workflow_id)
        if not workflow:
            return None

        completed = sum(1 for s in workflow.steps if s.status == StepStatus.COMPLETED)
        skipped = sum(1 for s in workflow.steps if s.status == StepStatus.SKIPPED)
        total_evidence = sum(len(s.evidence_ids) for s in workflow.steps)

        step_summaries = []
        for s in workflow.steps:
            step_summaries.append({
                "step_number": s.step_number,
                "step_name": s.step_name,
                "status": s.status.value,
                "evidence_count": len(s.evidence_ids),
                "skip_justification": s.skip_justification,
                "completed_at": s.completed_at,
            })

        # Decision logic
        if completed + skipped < 10:
            decision = "pending"
            rationale = f"Workflow incomplete: {completed} completed, {skipped} skipped, {10 - completed - skipped} pending"
        elif skipped > 3:
            decision = "no_go"
            rationale = f"Too many steps skipped ({skipped}/10). Insufficient evidence for clinical advancement."
        elif total_evidence < 5:
            decision = "no_go"
            rationale = f"Insufficient evidence ({total_evidence} items). Minimum 5 evidence items recommended."
        else:
            decision = "go"
            rationale = f"All steps addressed ({completed} completed, {skipped} skipped) with {total_evidence} evidence items."

        summary = GoNoGoSummary(
            workflow_id=workflow_id,
            decision=decision,
            rationale=rationale,
            steps_completed=completed,
            steps_skipped=skipped,
            total_evidence_items=total_evidence,
            step_summaries=step_summaries,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        workflow.go_nogo_summary = summary
        cls.save_workflow(workflow)

        return summary
