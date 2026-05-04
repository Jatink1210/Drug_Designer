"""Run State Machine schemas for Subsystem 3 (Symphony Orchestrator)."""

from enum import Enum
from typing import List, Dict, Any
from pydantic import BaseModel

class RunState(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class RunRecord(BaseModel):
    """Immutable trace record for all background workflows (§41)."""
    run_id: str
    run_type: str
    state: RunState
    runtime_context: Dict[str, Any]
    logs: List[str]
    artifacts: List[str]
    provenance: Dict[str, Any]
