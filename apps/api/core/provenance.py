"""Provenance tracking for all facts and entities."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProvenanceRecord(BaseModel):
    """Tracks the origin and quality of every piece of data."""
    source_name: str
    source_url: str = ""
    retrieval_timestamp: float = Field(default_factory=time.time)
    raw_payload_hash: str = ""
    normalization_version: str = "1.0"
    confidence_score: float = 1.0
    confidence_reasoning: str = ""
    external_id: str = ""
    canonical_link: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.dict()

    @classmethod
    def from_connector(
        cls,
        source: str,
        url: str = "",
        payload_hash: str = "",
        confidence: float = 1.0,
        reasoning: str = "",
        external_id: str = "",
    ) -> "ProvenanceRecord":
        return cls(
            source_name=source,
            source_url=url,
            raw_payload_hash=payload_hash,
            confidence_score=confidence,
            confidence_reasoning=reasoning,
            external_id=external_id,
            canonical_link=url,
        )


class ProvenanceBundle(BaseModel):
    """Collection of provenance records for a search or operation."""
    sources_hit: List[str] = Field(default_factory=list)
    timestamps: Dict[str, float] = Field(default_factory=dict)
    records: List[ProvenanceRecord] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    def add(self, record: ProvenanceRecord) -> None:
        self.records.append(record)
        if record.source_name not in self.sources_hit:
            self.sources_hit.append(record.source_name)
        self.timestamps[record.source_name] = record.retrieval_timestamp
