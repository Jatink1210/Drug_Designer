"""Canonical entity schemas — unified data model for all biomedical entities."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> float:
    return time.time()


# ─── Cross-reference ─────────────────────────────────────
class XRef(BaseModel):
    source: str
    id: str
    url: str = ""


# ─── Base Entity ──────────────────────────────────────────
class EntityBase(BaseModel):
    id: str = Field(default_factory=_uuid)
    entity_type: str
    canonical_name: str
    description: str = ""
    synonyms: List[str] = Field(default_factory=list)
    xrefs: List[XRef] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=_now)
    updated_at: float = Field(default_factory=_now)
    properties: Dict[str, Any] = Field(default_factory=dict)
    provenance: List[Dict[str, Any]] = Field(default_factory=list)
    gwas_significance: Optional[float] = None
    indian_demographic_context: str = ""
    pico_data: Dict[str, Any] = Field(default_factory=dict)


# ─── Entity Types ─────────────────────────────────────────
class GeneEntity(EntityBase):
    entity_type: str = "gene"
    symbol: str = ""
    ensembl_id: str = ""
    organism: str = "Homo sapiens"
    chromosome: str = ""
    biotype: str = ""

class ProteinEntity(EntityBase):
    entity_type: str = "protein"
    gene_symbol: str = ""
    organism: str = "Homo sapiens"
    length: Optional[int] = None
    sequence: str = ""
    uniprot_id: str = ""
    pdb_ids: List[str] = Field(default_factory=list)
    function_description: str = ""

class DiseaseEntity(EntityBase):
    entity_type: str = "disease"
    ontology_ids: Dict[str, str] = Field(default_factory=dict)  # EFO, MONDO, DOID, MeSH
    therapeutic_area: str = ""

class DrugEntity(EntityBase):
    entity_type: str = "drug"
    mechanism_of_action: str = ""
    indication: str = ""
    max_clinical_phase: int = 0
    drug_type: str = ""  # small molecule, antibody, etc.
    targets: List[str] = Field(default_factory=list)

class MoleculeEntity(EntityBase):
    entity_type: str = "molecule"
    smiles: str = ""
    inchi: str = ""
    inchi_key: str = ""
    formula: str = ""
    molecular_weight: Optional[float] = None
    logp: Optional[float] = None
    tpsa: Optional[float] = None

class VariantFrequency(BaseModel):
    population: str
    allele_frequency: float
    allele_count: Optional[int] = None
    allele_number: Optional[int] = None
    homozygous_count: Optional[int] = None

class PopulationEvidence(BaseModel):
    dataset_name: str
    frequencies: List[VariantFrequency] = Field(default_factory=list)
    clinical_significance: str = ""
    notes: str = ""

class VariantEntity(EntityBase):
    entity_type: str = "variant"
    rs_id: str = ""
    gene: str = ""
    consequence: str = ""
    clinical_significance: str = ""
    population_frequencies: Dict[str, float] = Field(default_factory=dict)
    mapped_genes: List[Dict[str, Any]] = Field(default_factory=list)
    population_evidence: List[PopulationEvidence] = Field(default_factory=list)

class PathwayEntity(EntityBase):
    entity_type: str = "pathway"
    pathway_id: str = ""
    source_db: str = ""  # KEGG, Reactome
    species: str = "Homo sapiens"
    gene_count: int = 0
    genes: List[str] = Field(default_factory=list)
    url: str = ""

class StructureEntity(EntityBase):
    entity_type: str = "structure"
    pdb_id: str = ""
    method: str = ""
    resolution: Optional[float] = None
    deposition_date: str = ""
    release_date: str = ""
    chains: List[str] = Field(default_factory=list)
    ligands: List[str] = Field(default_factory=list)
    organism: str = ""
    title: str = ""
    r_free: Optional[float] = None

class PublicationEntity(EntityBase):
    entity_type: str = "publication"
    title: str = ""
    authors: List[str] = Field(default_factory=list)
    journal: str = ""
    year: Optional[int] = None
    pmid: str = ""
    doi: str = ""
    url: str = ""
    abstract: str = ""
    citation_count: Optional[int] = None

class ClinicalTrialEntity(EntityBase):
    entity_type: str = "clinical_trial"
    nct_id: str = ""
    phase: str = ""
    status: str = ""
    conditions: List[str] = Field(default_factory=list)
    interventions: List[str] = Field(default_factory=list)
    enrollment: Optional[int] = None
    start_date: str = ""
    primary_outcome: str = ""
    url: str = ""

class PatentEntity(EntityBase):
    entity_type: str = "patent"
    patent_id: str = ""
    title: str = ""
    assignee: str = ""
    filing_date: str = ""
    grant_date: str = ""
    abstract: str = ""

class AssayEntity(EntityBase):
    entity_type: str = "assay"
    assay_type: str = ""
    target: str = ""
    organism: str = ""
    bioactivity_type: str = ""
    value: Optional[float] = None
    unit: str = ""

class InteractionEntity(EntityBase):
    entity_type: str = "interaction"
    source_entity: str = ""
    target_entity: str = ""
    interaction_type: str = ""
    detection_method: str = ""
    score: Optional[float] = None


# ─── Citation & Contradiction Models ─────────────────────
class CitationRef(BaseModel):
    source: str          # "PubMed", "ClinicalTrials", "ChEMBL", etc.
    external_id: str     # "PMID:12345", "NCT00000000"
    title: str = ""
    year: Optional[int] = None
    url: str = ""
    snippet: str = ""
    confidence: float = 0.5
    evidence_type: str = ""  # "supporting", "contradicting", "neutral"

class Contradiction(BaseModel):
    claim_a: str
    claim_b: str
    source_a: CitationRef
    source_b: CitationRef
    severity: str = "moderate"  # "low", "moderate", "high"
    explanation: str = ""

class EvidenceSummary(BaseModel):
    citations: List[CitationRef] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    overall_confidence: float = 0.5
    evidence_count: int = 0


# ─── Evidence Record ──────────────────────────────────────
class EvidenceRecord(BaseModel):
    id: str = Field(default_factory=_uuid)
    entity_ids: List[str] = Field(default_factory=list)
    relationship: str = ""
    source: str = ""
    external_id: str = ""
    title: str = ""
    year: Optional[int] = None
    venue: str = ""
    authors: List[str] = Field(default_factory=list)
    url: str = ""
    snippet: str = ""
    retrieved_at: float = Field(default_factory=_now)
    weight: float = 1.0
    evidence_type: str = ""  # publication, trial, assay, database


# ─── Relationship Edge ───────────────────────────────────
class RelationshipEdge(BaseModel):
    id: str = Field(default_factory=_uuid)
    source_entity_id: str
    target_entity_id: str
    predicate: str  # e.g., "targets", "associated_with", "participates_in"
    evidence_ids: List[str] = Field(default_factory=list)
    weight: float = 1.0
    directionality: str = "directed"  # directed, undirected
    created_at: float = Field(default_factory=_now)
    properties: Dict[str, Any] = Field(default_factory=dict)


# ─── Search Result Format ─────────────────────────────────
class CategoryResult(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    total: int

class SearchResultEnvelope(BaseModel):
    query: str
    intent: Dict[str, Any]
    summary_stats: Dict[str, Any] = Field(default_factory=dict)
    categories: Dict[str, CategoryResult] = Field(default_factory=dict)
    preview_graph: Dict[str, Any] = Field(default_factory=lambda: {"nodes": [], "edges": []})
    provenance: Dict[str, Any] = Field(default_factory=dict)
    timings: Dict[str, float] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    evidence_summary: Dict[str, Any] = Field(default_factory=dict)
