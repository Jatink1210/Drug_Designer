"""Pydantic models for Search request and response contracts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    mode: str = "auto"
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 20


class IntentResult(BaseModel):
    intent: str
    search_term: str
    confidence: float = 1.0
    method: str = "heuristic"


class EnrichmentCounts(BaseModel):
    pubmed: Optional[int] = None
    clinical_trials: Optional[int] = None
    local_kg: Optional[int] = None


class Citation(BaseModel):
    text: str
    source: str
    url: str = ""
    entity_id: str = ""


class AISummary(BaseModel):
    text: str
    citations: List[Citation] = Field(default_factory=list)
    model: str = ""
    available: bool = True


class SearchResponse(BaseModel):
    query: str
    intent: IntentResult
    counts: EnrichmentCounts = Field(default_factory=EnrichmentCounts)
    ai_summary: Optional[AISummary] = None
    entities_by_type: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    timings: Dict[str, float] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
