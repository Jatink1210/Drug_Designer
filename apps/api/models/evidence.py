"""Evidence models (Drug Designer §94.2, §17 Evidence Behavior Rules).

Every evidence item must carry: source name, source type, retrieval
timestamp, source record ID, normalized internal ID, confidence hint,
contradiction state. Every generated conclusion must link to supporting
evidence items. No evidence item may be fabricated.
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


# ── §94.2 — Evidence Item ──────────────────────────────────
class EvidenceItem(BaseModel):
    """The standard evidence payload returned from RAG lookups.

    Every evidence item shown in the product must carry provenance,
    confidence, and contradiction state (§17 Evidence Behavior Rules).
    """

    evidence_id: str = Field(default_factory=_uuid)
    source_family: str = Field(
        ..., description="literature | disease | target | pathway | compound | genetics | clinical"
    )
    source_name: str = Field(..., description="e.g. PubMed, OpenTargets, DisGeNET")
    source_type: str = Field(..., description="e.g. api, database, scrape")
    external_record_id: str = Field("", description="e.g. PMID:123456")
    normalized_entity_id: str = Field("", description="e.g. UniProt:P38398")
    title: str = ""
    snippet: str = ""
    url: str = ""
    published_at: Optional[str] = None
    retrieved_at: str = Field(default_factory=_now_iso)
    content: Dict[str, Any] = Field(
        default_factory=dict,
        description="Full structured content from source",
    )
    confidence: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Confidence score — every visible score must be explainable (§107.7)",
    )
    contradiction_state: str = Field(
        "none",
        description="none | flagged | confirmed — conflicting evidence MUST be visible (§107.6)",
    )
    contradiction_pair_id: Optional[str] = Field(
        None, description="UUID of the paired contradicting evidence item"
    )
    contradiction_group_id: Optional[str] = None
    indian_population_relevant: bool = Field(
        False, description="Explicitly flagged when Indian population data is present (§15)"
    )
    freshness: str = Field("current", description="current | stale")
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="api_endpoint, response_time_ms, query_params",
    )


# ── Evidence Annotation ────────────────────────────────────
class EvidenceAnnotation(BaseModel):
    """User annotation on an evidence item."""

    annotation_id: str = Field(default_factory=_uuid)
    evidence_item_id: str
    user_id: str
    annotation_type: str = Field(
        ..., description="note | flag | contradiction | bookmark"
    )
    body: str = ""
    created_at: str = Field(default_factory=_now_iso)


# ── Evidence Bundle ────────────────────────────────────────
class EvidenceBundle(BaseModel):
    """A curated collection of evidence items saved to Project Memory."""

    bundle_id: str = Field(default_factory=_uuid)
    project_id: str
    title: str
    description: str = ""
    evidence_item_ids: List[str] = Field(default_factory=list)
    created_by: str = Field(..., description="User ID")
    created_at: str = Field(default_factory=_now_iso)


# ── §94.1 — Entity Reference ──────────────────────────────
class EntityReference(BaseModel):
    """Used whenever identifying a biological or chemical target."""

    entity_type: str = Field(
        ..., description="disease | gene | protein | pathway | compound | publication | variant"
    )
    entity_id: str
    label: str
    source_system: str = ""
    normalized: bool = False
