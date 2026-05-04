"""Runtime & Local Agent models (Drug Designer §27, §34, §44).

The user gets the option to choose runtime:
  - Hosted (Cloud): Immediate use, no installation burden
  - Local Machine: Via Local Runtime Agent — privacy, lower cost
  - Auto/Fallback: System picks best available

§112.5: Model selection must always go through the Runtime Selection layer.
No module may hardcode a model ID.
"""

from __future__ import annotations

import uuid
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Runtime Mode ───────────────────────────────────────────
class RuntimeMode(BaseModel):
    """Current runtime configuration."""

    mode: str = Field("hosted", description="hosted | local | auto")
    selected_backend_id: Optional[str] = None
    selected_model_id: Optional[str] = None


# ── Runtime Status (§4 contract) ───────────────────────────
class RuntimeStatus(BaseModel):
    """Full runtime status snapshot as required by §4 runtime contracts."""

    mode: str = Field("hosted", description="hosted | local | auto")
    availability: str = Field("available", description="available | degraded | unavailable")
    reason_if_unavailable: Optional[str] = Field(None, description="Why the runtime is not available")
    hardware_summary: Dict[str, Any] = Field(default_factory=dict, description="cpu, ram_gb, gpu, vram_gb")
    supported_model_classes: List[str] = Field(default_factory=list, description="llm, gnn, embedding, etc.")
    diagnostics: List[Dict[str, Any]] = Field(default_factory=list, description="Runtime diagnostic messages")
    timestamp: str = Field(default_factory=_now_iso)


# ── Model Record (§63) ─────────────────────────────────────
class ModelRecord(BaseModel):
    """A model in the platform's model registry."""

    model_id: str = Field(default_factory=_uuid)
    model_name: str = Field(..., description="e.g. llama3.1:8b, admet_deep_classifier")
    display_name: str = ""
    provider_type: str = Field(
        ..., description="ollama | openai | huggingface | custom"
    )
    mode: str = Field(..., description="chat | embedding | classification")
    family: str = Field(..., description="llm | gnn | dqn | admet | embedding")
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    context_window: Optional[int] = None
    embedding_dims: Optional[int] = None
    recommended_for: List[str] = Field(default_factory=list)
    origin: str = Field("hosted", description="hosted | local")
    installed_flag: bool = Field(False, description="Whether the model is installed locally")
    runtime_requirements: Dict[str, Any] = Field(default_factory=dict, description="min_vram_gb, min_ram_gb, etc.")
    recommendation_score: float = Field(0.0, description="0-1 recommendation strength")
    role_tags: List[str] = Field(default_factory=list, description="e.g. chat, reasoning, embedding, admet")
    status: str = Field("available", description="available | downloading | unavailable")


# ── Model Version (§63.2) ──────────────────────────────────
class ModelVersion(BaseModel):
    """Neural network model version tracking.

    §63.1 Lifecycle: TRAINING → VALIDATION → STAGING → ACTIVE → ARCHIVED
    Only ONE version per model can be is_active = true.
    """

    version_id: str = Field(default_factory=_uuid)
    model_name: str
    version: str = Field(..., description="e.g. v2.3.1")
    weights_s3_key: str = ""
    training_provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="training_data_hash, training_config, validation_metrics, trained_at, parent_version",
    )
    is_active: bool = False
    created_at: str = Field(default_factory=_now_iso)


# ── Runtime Backend ────────────────────────────────────────
class RuntimeBackend(BaseModel):
    """A registered runtime backend (hosted server or local agent)."""

    backend_id: str = Field(default_factory=_uuid)
    backend_name: str
    backend_type: str = Field(..., description="ollama | openai | airllm | custom")
    hosted_or_local: str = Field(..., description="hosted | local")
    supports_gpu: bool = False
    supports_cpu: bool = True
    supports_embeddings: bool = False
    supports_generation: bool = False
    supports_vision: bool = False
    status: str = Field("online", description="online | offline | degraded")


# ── Local Agent (§27.4) ────────────────────────────────────
class LocalAgentStatus(BaseModel):
    """Status of a user's Local Runtime Agent."""

    agent_id: str = Field(default_factory=_uuid)
    user_id: str
    device_name: str = ""
    platform: str = Field("", description="windows | linux | macos")
    agent_version: str = ""
    connected_at: Optional[str] = None
    status: str = Field("disconnected", description="connected | disconnected | error")
    installed: bool = Field(False, description="Whether the agent is installed")
    hardware: Dict[str, Any] = Field(
        default_factory=dict,
        description="cpu, ram_gb, gpu_name, vram_gb, disk_free_gb",
    )
    runtime_inventory: Dict[str, Any] = Field(
        default_factory=dict, description="Installed runtimes"
    )
    model_inventory: Dict[str, Any] = Field(
        default_factory=dict, description="Installed models"
    )
    diagnostics: List[Dict[str, Any]] = Field(default_factory=list, description="Agent diagnostic messages")


# ── §27.5 — Runtime Provenance ─────────────────────────────
class RuntimeProvenance(BaseModel):
    """Written back with every locally-executed run."""

    runtime_mode: str = Field("hosted", description="hosted | local")
    local_agent_version: Optional[str] = None
    hardware_used: Dict[str, Any] = Field(default_factory=dict)
    model_used: str = ""
    inference_method: str = Field(
        "", description="standard | airllm_layer_wise | speculative_decoding"
    )
    fallback_occurred: bool = False
