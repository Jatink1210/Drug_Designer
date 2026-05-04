"""Graph & Pathway models (Drug Designer §82, §56).

The Knowledge Graph unifies: genes, proteins, diseases, pathways,
compounds, variants, phenotypes, and publications as nodes.
Every visible edge or cluster must tie back to evidence or structured
reasoning (§107.5).
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


# ── Graph Node ─────────────────────────────────────────────
class GraphNode(BaseModel):
    """A node in the Knowledge Graph (Neo4j)."""

    node_id: str = Field(default_factory=_uuid)
    entity_type: str = Field(
        ..., description="gene | protein | disease | pathway | compound | variant | phenotype | publication"
    )
    entity_id: str = Field(..., description="Canonical ID (UniProt, MONDO, ChEMBL, etc.)")
    label: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    created_at: str = Field(default_factory=_now_iso)


# ── Graph Edge ─────────────────────────────────────────────
class GraphEdge(BaseModel):
    """An edge in the Knowledge Graph.

    Edge types: ppi, pathway_member, gene_disease, drug_target,
    variant_gene, phenotype_disease, evidence_link
    """

    edge_id: str = Field(default_factory=_uuid)
    source_node_id: str
    target_node_id: str
    edge_type: str = Field(
        ..., description="ppi | pathway_member | gene_disease | drug_target | variant_gene | evidence_link"
    )
    weight: float = Field(1.0, description="Evidence-based weight")
    evidence_ids: List[str] = Field(
        default_factory=list, description="Evidence items backing this edge"
    )
    properties: Dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    created_at: str = Field(default_factory=_now_iso)


# ── Graph Neighborhood Response ────────────────────────────
class GraphNeighborhood(BaseModel):
    """Response from a neighborhood/expansion query."""

    center_entity_id: str
    depth: int = 2
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0


# ── Pathway Record ─────────────────────────────────────────
class PathwayRecord(BaseModel):
    """A biological pathway reference."""

    pathway_id: str = Field(default_factory=_uuid)
    external_id: str = Field(..., description="e.g. KEGG:hsa05010, Reactome:R-HSA-123")
    pathway_name: str
    source_db: str = Field(..., description="KEGG | Reactome | WikiPathways | BioCyc")
    species: str = "Homo sapiens"
    gene_count: int = 0
    url: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Pathway Membership ─────────────────────────────────────
class PathwayMembership(BaseModel):
    """Gene/protein membership in a pathway."""

    membership_id: str = Field(default_factory=_uuid)
    pathway_id: str
    gene_symbol: str
    uniprot_id: str = ""
    role: str = Field("", description="enzyme | receptor | transporter | regulator | unknown")
    evidence_ids: List[str] = Field(default_factory=list)


# ── Disease-Specific Pathway Context ──────────────────────
class PathwayDiseaseContext(BaseModel):
    """Disease-specific pathway rewiring and perturbation data.

    Supports differential network analysis (§82.3).
    """

    pathway_id: str
    disease_query_id: str
    perturbation_genes: List[str] = Field(default_factory=list)
    differential_expression: Dict[str, float] = Field(default_factory=dict)
    rewiring_score: float = 0.0
    evidence_ids: List[str] = Field(default_factory=list)
