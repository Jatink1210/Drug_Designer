"""Disease Intelligence models (Drug Designer §B1, §56).

The disease pipeline: normalization → source search → candidate gene
aggregation → UniProt mapping is a single transactional unit with
provenance preserved at each stage (§112.4).
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


# ── Disease Normalization Result ───────────────────────────
class DiseaseNormalizationResult(BaseModel):
    """Output of Step 1 of the Disease Intelligence pipeline.

    Maps raw user text to canonical ontology identifiers.
    """

    query_id: str = Field(default_factory=_uuid)
    run_id: str
    input_text: str = Field(..., description="Original user input, e.g. 'Type 2 Diabetes'", alias="raw_input")
    normalized_label: str = Field("", description="Canonical disease name")
    identifiers: Dict[str, str] = Field(
        default_factory=dict,
        description="Ontology IDs: {mondo, omim, mesh, do, hpo, efo, icd10}",
    )
    synonyms: List[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    provenance: List[Dict[str, Any]] = Field(default_factory=list, description="Source lineage for normalization")
    unresolved_flag: bool = Field(False, description="True when normalization could not map to any ontology")
    created_at: str = Field(default_factory=_now_iso)


# ── Disease Source Hit ─────────────────────────────────────
class DiseaseSourceHit(BaseModel):
    """A single hit from one disease/ontology source during aggregation."""

    hit_id: str = Field(default_factory=_uuid)
    disease_query_id: str
    source_id: str
    source_name: str
    external_record_id: str = ""
    matched_label: str = ""
    match_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Candidate Gene ─────────────────────────────────────────
class CandidateGene(BaseModel):
    """A gene identified as potentially associated with the disease.

    Aggregated from multiple sources, deduplicated by HGNC symbol.
    """

    gene_id: str = Field(default_factory=_uuid)
    disease_query_id: str
    gene_symbol: str = Field(..., description="HGNC gene symbol")
    source_count: int = Field(0, description="Number of independent sources")
    source_refs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Per-source evidence references",
    )
    evidence_refs: List[str] = Field(default_factory=list, description="IDs of linked evidence items")
    ranking_features: Dict[str, float] = Field(default_factory=dict, description="Feature breakdown for explainable ranking")
    score: float = Field(
        0.0, description="source_count × evidence_strength × genetic_support"
    )
    notes: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── UniProt Mapping ────────────────────────────────────────
class UniProtMapping(BaseModel):
    """Gene symbol → UniProt accession mapping result.

    §B1 Step 4: Silent dropping of unmapped entities is forbidden.
    """

    mapping_id: str = Field(default_factory=_uuid)
    disease_query_id: str
    gene_symbol: str
    uniprot_id: Optional[str] = Field(
        None, description="UniProt accession if resolved"
    )
    mapping_method: str = Field(
        "", description="direct | ensembl_xref | blast | manual"
    )
    mapping_confidence: float = Field(0.0, ge=0.0, le=1.0)
    status: str = Field(
        "pending", description="pending | mapped | ambiguous | failed"
    )
    unresolved_flag: bool = Field(False, description="True when mapping could not resolve")
    provenance: List[Dict[str, Any]] = Field(default_factory=list, description="Mapping source lineage")
    notes: str = Field(
        "", description="Explanation for failed/ambiguous mappings — must never be silent"
    )


# ── Disease Intelligence Result (full pipeline output) ─────
class DiseaseIntelligenceResult(BaseModel):
    """Complete output of a disease.intelligence run (§B1)."""

    run_id: str
    project_id: str
    normalization: DiseaseNormalizationResult
    candidate_genes: List[CandidateGene] = Field(default_factory=list)
    uniprot_mappings: List[UniProtMapping] = Field(default_factory=list)
    contradiction_count: int = 0
    sources_queried: int = 0
    sources_succeeded: int = 0
    sources_degraded: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)
