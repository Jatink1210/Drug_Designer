"""SQLAlchemy ORM Models — Complete Data Plane (Drug Designer §56, §91).

35 tables across 6 migration waves, following the existing pattern
from user.py. All tables support the browser-native hosted persistence
layer — NO local DB on user machines (§2.4).

Wave 1: Core Identity (users, sessions, user_preferences, projects, project_members, project_notes)
Wave 2: Runs & Jobs (runs, jobs, run_events)
Wave 3: Sources & Evidence (sources, source_health, evidence_items, evidence_annotations, evidence_bundles, evidence_bundle_items)
Wave 4: Disease & Target (disease_queries, disease_source_hits, disease_candidate_genes, uniprot_mappings, target_rankings)
Wave 5: Graph & Pathways (graph_nodes, graph_edges, pathway_records, pathway_memberships, reports, dossiers, media_artifacts, exports, memory_objects)
Wave 6: Runtime & Agent (models, runtime_backends, local_agents, local_agent_events, runtime_selections, model_registry, audit_log)
"""

import uuid

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index, Enum as SAEnum,
)
from sqlalchemy.sql import func

from core.db import Base


def _uuid():
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════
# WAVE 1 — Core Identity
# ═══════════════════════════════════════════════════════════

# User and Project already exist in user.py — not redefined here.

class Session(Base):
    """User session tracking (Deep-Impl §2.1)."""
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    ip_hash = Column(String, nullable=True)  # §2.1: hashed IP (replaces plaintext)
    user_agent_hash = Column(String, nullable=True)  # §2.1: hashed user agent
    client_type = Column(String, default="browser")  # §2.1: browser | api | agent
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=True)  # §2.1: last activity timestamp
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)


class UserPreference(Base):
    """User-level preferences (runtime mode, theme, default project) — Deep-Impl §2.1."""
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    default_runtime_mode = Column(String, default="hosted")  # hosted | local | auto
    default_model_id = Column(String, nullable=True)
    default_project_id = Column(String, ForeignKey("projects.id"), nullable=True)  # §2.1: pinned project
    density_mode = Column(String, default="comfortable")  # §2.1: compact | comfortable | spacious
    theme = Column(String, default="dark")
    locale = Column(String, default="en")
    preferred_sources_json = Column(JSON, default=dict)  # §2.1: user's source whitelist/ranking
    accessibility_flags_json = Column(JSON, default=dict)  # §2.1: a11y settings
    preferences_json = Column(JSON, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProjectMember(Base):
    """Project membership and RBAC (§55.2)."""
    __tablename__ = "project_members"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    role = Column(String, default="collaborator")  # owner | collaborator | viewer
    joined_at = Column(DateTime(timezone=True), server_default=func.now())


class ProjectNote(Base):
    """Free-text notes attached to a project (Deep-Impl §2.2)."""
    __tablename__ = "project_notes"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)  # serves as body_md per §2.2
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # §2.2


# ═══════════════════════════════════════════════════════════
# WAVE 2 — Runs & Jobs
# ═══════════════════════════════════════════════════════════

class Run(Base):
    """Tracked scientific run (§23, §41, Deep-Impl §2.3).
    
    Lifecycle: CREATED → QUEUED → RUNNING → 
    [PARTIAL_SUCCESS | SUCCESS | FAILED | CANCELLED | TIMED_OUT]
    """
    __tablename__ = "runs"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=True)  # §2.3: who triggered
    run_type = Column(String, nullable=False)  # disease.intelligence, target.ranking, etc.
    module_name = Column(String, nullable=True)  # §2.3: module_name (disease_intelligence, target_ranking, etc.)
    trigger_type = Column(String, default="manual")  # §2.3: manual | api | event | scheduled
    state = Column(String, default="CREATED", index=True)
    query_text = Column(Text, nullable=True)  # §2.3: original user query
    normalized_query_json = Column(JSON, default=dict)  # §2.3: parsed query structure
    input_snapshot = Column(JSON, default=dict)
    runtime_mode = Column(String, default="hosted")  # §2.3: hosted | local | auto
    model_id = Column(String, nullable=True)  # §2.3: which model was used
    runtime_context = Column(JSON, default=dict)  # mode, model_id, hardware
    source_footprint = Column(JSON, default=list)  # sources queried
    timing = Column(JSON, default=dict)  # total_ms, per_stage
    output_artifacts = Column(JSON, default=list)  # artifact UUIDs
    errors = Column(JSON, default=list)
    degraded = Column(JSON, default=dict)  # §56.1: degraded (reason, affected_sources)
    degraded_reason_json = Column(JSON, default=dict)  # §2.3: structured degraded reason
    degraded_sources_json = Column(JSON, default=list)  # A-3: list of source names that were degraded
    provenance = Column(JSON, default=dict)  # sources_queried, sources_succeeded, contradictions_found
    summary = Column(Text, default="")  # §2.3: brief text summary of run
    elapsed_ms = Column(Integer, nullable=True)  # §2.3: duration in milliseconds
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)  # §2.3: explicit start time
    finished_at = Column(DateTime(timezone=True), nullable=True)  # §2.3: explicit finish time
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_runs_project_state", "project_id", "state"),
        Index("ix_runs_type", "run_type"),
        Index("ix_runs_user", "user_id"),
        Index("ix_runs_module", "module_name"),
    )


class Job(Base):
    """ARQ background job linked to a run (§92)."""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    queue_name = Column(String, nullable=False)  # ARQ queue name
    status = Column(String, default="pending")  # pending | running | success | failed | dead_letter
    payload = Column("payload_json", JSON, default=dict)  # §56.2: payload_json
    result = Column("result_json", JSON, default=dict)  # §56.2: result_json
    error = Column("error_json", JSON, nullable=True)  # §56.2: error_json
    retries = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)  # §5.3: spec retry_count field
    idempotency_key = Column(String, nullable=True, unique=True, index=True)  # §6.2: deduplication
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class RunEvent(Base):
    """WebSocket event record for run progress (§57)."""
    __tablename__ = "run_events"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    event_type = Column(String, nullable=False)  # run.progress, run.stage_complete, etc.
    payload = Column("event_payload_json", JSON, default=dict)  # §56.2: event_payload_json
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════
# WAVE 3 — Sources & Evidence
# ═══════════════════════════════════════════════════════════

class Source(Base):
    """Registered external data source (§17, §62)."""
    __tablename__ = "sources"

    id = Column(String, primary_key=True, default=_uuid)
    source_name = Column(String, unique=True, nullable=False, index=True)
    source_family = Column(String, nullable=False)  # literature, disease, target, etc.
    source_type = Column(String, nullable=False)  # api | database | scrape
    access_mode = Column(String, default="public")  # public | free_key | paid
    requires_key = Column(Boolean, default=False)
    homepage_url = Column(String, default="")
    status = Column(String, default="active")  # active | degraded | down | disabled
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SourceHealthRecord(Base):
    """Point-in-time source health check (§62, §A9)."""
    __tablename__ = "source_health"

    id = Column(String, primary_key=True, default=_uuid)
    source_id = Column(String, ForeignKey("sources.id"), index=True, nullable=False)
    status = Column(String, default="healthy")  # healthy | degraded | down
    latency_ms = Column(Integer, nullable=True)
    error_rate = Column(Float, default=0.0)
    degraded_reason = Column("degraded_reason_json", JSON, default=dict)  # §56.2: degraded_reason_json
    checked_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_source_health_checked_at", "checked_at"),
    )


class EvidenceItemRecord(Base):
    """Persisted evidence item (§94.2, §17, Deep-Impl §2.4)."""
    __tablename__ = "evidence_items"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    run_id = Column(String, ForeignKey("runs.id"), nullable=True, index=True)
    source_id = Column(String, ForeignKey("sources.id"), nullable=True, index=True)  # §2.4: FK to sources
    source_family = Column(String, nullable=False)
    source_name = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False)
    external_record_id = Column(String, default="", index=True)
    entity_type = Column(String, default="")  # §2.4: protein | gene | disease | compound | pathway | variant
    normalized_entity_id = Column(String, default="")
    title = Column(Text, default="")
    snippet = Column(Text, default="")
    url = Column(String, default="")
    published_at = Column(DateTime(timezone=True), nullable=True)
    content = Column(JSON, default=dict)
    confidence = Column(Float, default=0.5)
    quality_score = Column(Float, nullable=True)  # §2.4: explicit quality score
    contradiction_state = Column(String, default="none")  # none | flagged | confirmed
    contradiction_group_id = Column(String, nullable=True)  # §2.4: spec field name
    contradiction_pair_id = Column(String, nullable=True)  # kept for backward compat
    indian_population_relevant = Column(Boolean, default=False)
    contradiction_type = Column(String(50), nullable=True)  # A-2: directional | temporal | population | methodological | score_divergence
    freshness = Column(String, default="current")
    entities = Column(JSON, default=list)
    metadata_json = Column(JSON, default=dict)
    provenance = Column(JSON, default=dict)
    embedding_ref = Column(String, default="")  # §2.4: vector DB reference ID
    retrieved_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_evidence_project_source", "project_id", "source_name"),
        Index("ix_evidence_external_record", "external_record_id"),
        Index("ix_evidence_entity_type", "entity_type"),
    )


class EvidenceAnnotationRecord(Base):
    """User annotation on evidence (§7.2)."""
    __tablename__ = "evidence_annotations"

    id = Column(String, primary_key=True, default=_uuid)
    evidence_item_id = Column(String, ForeignKey("evidence_items.id"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    annotation_type = Column(String, nullable=False)  # note | flag | contradiction | bookmark
    body = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EvidenceBundleRecord(Base):
    """Curated evidence bundle (§7.2)."""
    __tablename__ = "evidence_bundles"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EvidenceBundleItem(Base):
    """Many-to-many link between bundles and evidence items."""
    __tablename__ = "evidence_bundle_items"

    id = Column(String, primary_key=True, default=_uuid)
    bundle_id = Column(String, ForeignKey("evidence_bundles.id"), index=True, nullable=False)
    evidence_item_id = Column(String, ForeignKey("evidence_items.id"), index=True, nullable=False)


# ═══════════════════════════════════════════════════════════
# WAVE 4 — Disease & Target
# ═══════════════════════════════════════════════════════════

class DiseaseQuery(Base):
    """Disease Intelligence query (§B1, §9)."""
    __tablename__ = "disease_queries"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    raw_input = Column(String, nullable=False)
    normalized_label = Column(String, default="")
    identifiers = Column("ontology_ids_json", JSON, default=dict)  # §56.2: ontology_ids_json
    synonyms = Column("synonyms_json", JSON, default=list)  # §56.2: synonyms_json
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DiseaseSourceHit(Base):
    """Individual source hit during disease aggregation (§56.2)."""
    __tablename__ = "disease_source_hits"

    id = Column(String, primary_key=True, default=_uuid)
    disease_query_id = Column(String, ForeignKey("disease_queries.id"), index=True, nullable=False)
    source_id = Column(String, ForeignKey("sources.id"), nullable=True, index=True)  # §56.2: source_id FK
    source_name = Column(String, nullable=False)  # kept for backward compat
    external_record_id = Column(String, default="")
    matched_label = Column(String, default="")
    match_score = Column(Float, default=0.0)
    metadata_json = Column(JSON, default=dict)


class DiseaseCandidateGene(Base):
    """Candidate gene aggregated from sources (§9.2)."""
    __tablename__ = "disease_candidate_genes"

    id = Column(String, primary_key=True, default=_uuid)
    disease_query_id = Column(String, ForeignKey("disease_queries.id"), index=True, nullable=False)
    gene_symbol = Column(String, nullable=False, index=True)
    source_count = Column(Integer, default=0)
    source_refs = Column("source_refs_json", JSON, default=list)  # §56.2: source_refs_json
    score = Column(Float, default=0.0)
    notes = Column(Text, default="")
    metadata_json = Column(JSON, default=dict)


class DiseaseResult(Base):
    """Normalized disease output (§56.1 disease_results)."""
    __tablename__ = "disease_results"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    normalized_label = Column(String, nullable=False)
    identifiers = Column(JSON, default=dict)  # {mondo, omim, mesh, do, hpo, efo, icd10}
    synonyms = Column(JSON, default=list)
    candidate_genes = Column(JSON, default=list)
    contradiction_count = Column(Integer, default=0)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UniProtMappingRecord(Base):
    """Gene-to-UniProt mapping result (§11).
    
    §B1 Step 4: Silent dropping of unmapped entities is forbidden.
    """
    __tablename__ = "uniprot_mappings"

    id = Column(String, primary_key=True, default=_uuid)
    disease_query_id = Column(String, ForeignKey("disease_queries.id"), index=True, nullable=False)
    gene_symbol = Column(String, nullable=False, index=True)
    uniprot_id = Column(String, nullable=True)
    mapping_method = Column(String, default="")  # direct | ensembl_xref | blast | manual
    mapping_confidence = Column(Float, default=0.0)
    status = Column(String, default="pending")  # pending | mapped | ambiguous | failed
    notes = Column(Text, default="")


class TargetRanking(Base):
    """Persisted target ranking result (§10, §56.1, §94.3)."""
    __tablename__ = "target_rankings"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    gene_symbol = Column(String, nullable=False, index=True)  # §56.1: gene_symbol
    target_symbol = Column(String, nullable=True)  # kept for backward compat
    uniprot_id = Column(String, default="")
    rank = Column(Integer, default=0)
    composite_score = Column(Float, default=0.0)
    # §56.1 individual score columns:
    gwas_score = Column(Float, default=0.0)
    druggability_score = Column(Float, default=0.0)
    pathway_centrality = Column(Float, default=0.0)
    expression_score = Column(Float, default=0.0)
    safety_score = Column(Float, default=0.0)
    novelty_score = Column(Float, default=0.0)
    literature_score = Column(Float, default=0.0)
    score_breakdown = Column(JSON, default=dict)  # kept for backward compat / extra detail
    evidence_breakdown = Column(JSON, default=dict)  # §56.1: evidence_breakdown
    per_source_evidence_json = Column(JSON, default=dict)  # A-5: evidence per source {source_name: [evidence_item_ids]}
    ucb_score = Column(Float, nullable=True)
    contradiction_flag = Column(Boolean, default=False)
    explanation = Column(Text, default="")
    evidence_item_ids = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_target_rankings_run_rank", "run_id", "rank"),
    )


# ═══════════════════════════════════════════════════════════
# WAVE 5 — Graph, Pathways, Reports, Dossiers, Memory
# ═══════════════════════════════════════════════════════════

class GraphNodeRecord(Base):
    """Knowledge Graph node (§12, §56.2, §82)."""
    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True, default=_uuid)
    graph_namespace = Column(String, nullable=False, default="default", index=True)  # §56.2: multi-tenant graph isolation
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(String, nullable=False, index=True)  # canonical ID
    label = Column(String, default="")
    metadata_json = Column(JSON, default=dict)  # §56.2: metadata_json
    properties = Column(JSON, default=dict)  # kept for backward compat
    source = Column(String, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_graph_nodes_ns_entity", "graph_namespace", "entity_type", "entity_id", unique=True),
    )


class GraphEdgeRecord(Base):
    """Knowledge Graph edge (§12, §56.2, §82)."""
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True, default=_uuid)
    graph_namespace = Column(String, nullable=False, default="default", index=True)  # §56.2: multi-tenant graph isolation
    source_node_id = Column(String, ForeignKey("graph_nodes.id"), index=True, nullable=False)
    target_node_id = Column(String, ForeignKey("graph_nodes.id"), index=True, nullable=False)
    relation_type = Column(String, nullable=False)  # §56.2: relation_type
    edge_type = Column(String, nullable=True)  # kept for backward compat
    confidence = Column(Float, default=1.0)  # §56.2: confidence (was weight)
    weight = Column(Float, default=1.0)  # kept for backward compat
    contradiction_flag = Column(Boolean, default=False)  # §56.2: contradiction_flag
    provenance_json = Column(JSON, default=dict)  # §56.2: provenance_json
    evidence_ids = Column(JSON, default=list)
    properties = Column(JSON, default=dict)
    source = Column(String, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_graph_edges_ns_composite", "graph_namespace", "source_node_id", "target_node_id", "relation_type"),
    )


class PathwayRecordDB(Base):
    """Biological pathway (§13, §56.2)."""
    __tablename__ = "pathway_records"

    id = Column(String, primary_key=True, default=_uuid)
    external_id = Column(String, nullable=False, unique=True, index=True)  # §56.2: pathway_id UNIQUE
    pathway_name = Column(String, nullable=False)
    source_db = Column(String, nullable=False)  # §56.2: source_system
    category = Column(String, default="")  # §56.2: category
    description = Column(Text, default="")  # §56.2: description
    species = Column(String, default="Homo sapiens")
    gene_count = Column(Integer, default=0)
    url = Column(String, default="")
    metadata_json = Column(JSON, default=dict)


class PathwayMembershipDB(Base):
    """Pathway membership (§13, §56.2)."""
    __tablename__ = "pathway_memberships"

    id = Column(String, primary_key=True, default=_uuid)
    pathway_id = Column(String, ForeignKey("pathway_records.id"), index=True, nullable=False)
    entity_id = Column(String, nullable=False, index=True)  # §56.2: entity_id (gene/protein/compound ID)
    entity_type = Column(String, nullable=False, default="gene")  # §56.2: entity_type
    gene_symbol = Column(String, nullable=True, index=True)  # kept for backward compat
    uniprot_id = Column(String, default="")
    role = Column(String, default="")
    membership_confidence = Column(Float, nullable=True)  # §56.2: membership_confidence
    provenance_json = Column(JSON, default=dict)  # §56.2: provenance_json
    evidence_ids = Column(JSON, default=list)

    __table_args__ = (
        Index("ix_pathway_memberships_entity", "pathway_id", "entity_id", "entity_type"),
    )


class ReportRecord(Base):
    """Generated report (§25)."""
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    report_type = Column(String, nullable=False)  # summary | detailed | custom
    title = Column(String, nullable=False)
    status = Column(String, default="draft")  # draft | generating | ready | failed
    body = Column(JSON, default=dict)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DossierRecord(Base):
    """Decision Dossier (§19, §A10, Deep-Impl §2.8)."""
    __tablename__ = "dossiers"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    title = Column(String, nullable=False)
    objective = Column(Text, default="")
    status = Column(String, default="draft")  # §2.8: draft | review | finalized | archived
    sections = Column(JSON, default=list)
    body_json = Column(JSON, default=dict)  # §2.8: structured JSON body
    body_md = Column(Text, default="")  # §2.8: markdown body
    mav_consensus_trace = Column(JSON, default=dict)
    provenance_appendix = Column(JSON, default=dict)
    body_s3_key = Column(String, default="")
    created_by = Column(String, ForeignKey("users.id"), nullable=True)  # §2.8: user FK
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # §2.8
    exported_at = Column(DateTime(timezone=True), nullable=True)


class MediaArtifactRecord(Base):
    """Media artifact (figure, chart, rendering) (§27)."""
    __tablename__ = "media_artifacts"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    run_id = Column(String, ForeignKey("runs.id"), nullable=True)
    artifact_type = Column(String, nullable=False)  # figure | chart | structure | graph_snapshot
    title = Column(String, default="")
    file_ref = Column(String, nullable=False)  # S3 key or local path
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExportRecord(Base):
    """Export job (§28, §71)."""
    __tablename__ = "exports"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    object_type = Column(String, nullable=False)
    object_id = Column(String, nullable=False)
    export_format = Column(String, nullable=False)  # pdf | docx | json | csv | sdf | pdb | png
    status = Column(String, default="pending")  # pending | rendering | ready | failed
    file_ref = Column(String, default="")
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MemoryObjectRecord(Base):
    """Project Memory object (§22, §A7, Deep-Impl §2.2)."""
    __tablename__ = "memory_objects"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=False)
    object_type = Column(String, nullable=False)  # evidence_bundle | disease_run | target_ranking | graph_snapshot | contradiction_review
    object_id = Column(String, nullable=False)
    label = Column(String, default="")
    summary = Column(Text, default="")  # §2.2: text summary of memory object
    source_run_id = Column(String, ForeignKey("runs.id"), nullable=True, index=True)  # §2.2: which run created it
    source_module = Column(String, nullable=True)  # §2.2: which module/stage created it
    object_ref = Column(String, default="")  # §2.2: canonical reference/path
    pinned = Column(Boolean, default=False)
    embedding_status = Column(String, default="pending")  # §2.2: pending | indexed | failed
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # §2.2


# ═══════════════════════════════════════════════════════════
# WAVE 6 — Runtime & Agent
# ═══════════════════════════════════════════════════════════

class ModelRegistryRecord(Base):
    """Model registry entry (§63)."""
    __tablename__ = "models"

    id = Column(String, primary_key=True, default=_uuid)
    model_name = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, default="")
    provider_type = Column(String, nullable=False)  # ollama | openai | huggingface | custom
    mode = Column(String, nullable=False)  # chat | embedding | classification
    family = Column(String, nullable=False)  # llm | gnn | dqn | admet | embedding
    capabilities = Column("capabilities_json", JSON, default=dict)  # §56.2: capabilities_json
    context_window = Column(Integer, nullable=True)
    embedding_dims = Column(Integer, nullable=True)
    recommended_for = Column("recommended_for_json", JSON, default=list)  # §56.2: recommended_for_json
    status = Column(String, default="available")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelVersionRecord(Base):
    """NN model version (§63.2).
    
    Lifecycle: TRAINING → VALIDATION → STAGING → ACTIVE → ARCHIVED
    Only ONE version per model can be is_active = true.
    """
    __tablename__ = "model_registry"
    __table_args__ = (
        Index("ix_model_registry_name_active", "model_name", "is_active"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    model_name = Column(String, ForeignKey("models.model_name"), nullable=False, index=True)
    version = Column(String, nullable=False)
    weights_s3_key = Column(String, default="")
    training_provenance = Column(JSON, default=dict)
    is_active = Column(Boolean, default=False)
    parent_version_id = Column(String, ForeignKey("model_registry.id"), nullable=True)  # A-6: lineage FK
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RuntimeBackendRecord(Base):
    """Registered runtime backend (§35)."""
    __tablename__ = "runtime_backends"

    id = Column(String, primary_key=True, default=_uuid)
    backend_name = Column(String, nullable=False, unique=True)
    backend_type = Column(String, nullable=False)  # ollama | openai | airllm | custom
    hosted_or_local = Column(String, nullable=False)  # hosted | local
    supports_gpu = Column(Boolean, default=False)
    supports_cpu = Column(Boolean, default=True)
    supports_embeddings = Column(Boolean, default=False)
    supports_generation = Column(Boolean, default=False)
    supports_vision = Column(Boolean, default=False)
    status = Column(String, default="online")  # online | offline | degraded
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LocalAgentRecord(Base):
    """Local Runtime Agent status (§15, §27)."""
    __tablename__ = "local_agents"
    __table_args__ = (
        Index("ix_local_agents_user_status", "user_id", "status"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    device_name = Column(String, default="")
    platform = Column(String, default="")  # windows | linux | macos
    agent_version = Column(String, default="")
    status = Column(String, default="disconnected")  # connected | disconnected | error
    hardware = Column("hardware_json", JSON, default=dict)  # §56.2: hardware_json
    runtime_inventory = Column("runtime_inventory_json", JSON, default=dict)  # §56.2
    model_inventory = Column("model_inventory_json", JSON, default=dict)  # §56.2
    connected_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)


class LocalAgentEvent(Base):
    """Event from local agent (connection, disconnection, heartbeat)."""
    __tablename__ = "local_agent_events"
    __table_args__ = (
        Index("ix_lae_agent_type_created", "local_agent_id", "event_type", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column("local_agent_id", String, ForeignKey("local_agents.id"), index=True, nullable=False)  # §56.2: local_agent_id
    event_type = Column(String, nullable=False)  # connect | disconnect | heartbeat | error
    payload = Column("payload_json", JSON, default=dict)  # §56.2: payload_json
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelInstallRequest(Base):
    """Tracks per-user model installation requests (§91 Wave 6)."""
    __tablename__ = "model_install_requests"
    __table_args__ = (
        Index("ix_mir_user_status", "user_id", "status"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    model_name = Column(String, nullable=False)
    model_version = Column(String, default="latest")
    status = Column(String, default="pending")  # pending | downloading | installed | failed | cancelled
    progress_pct = Column(Integer, default=0)
    error_message = Column(String, nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class RuntimeSelection(Base):
    """Runtime selection record — tracks which runtime was chosen for a run (§56.2)."""
    __tablename__ = "runtime_selections"
    __table_args__ = (
        Index("ix_rtsel_run_created", "run_id", "created_at"),
        Index("ix_rtsel_project_user", "project_id", "user_id"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), index=True, nullable=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=True)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=True)
    backend_id = Column("selected_backend_id", String, ForeignKey("runtime_backends.id"), nullable=True)  # §56.2
    model_id = Column("selected_model_id", String, ForeignKey("models.id"), nullable=True)  # §56.2
    preferred_mode = Column(String, nullable=False, default="hosted")  # hosted | local | auto
    fallback_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Audit log for security and compliance (§61.3)."""
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String, nullable=False)  # login | logout | project.create | run.create | export | etc.
    resource_type = Column(String, default="")  # project | run | evidence | dossier | etc.
    resource_id = Column(String, default="")
    details = Column(JSON, default=dict)
    ip_address = Column(String, default="")
    user_agent = Column(String, default="")  # §61.3 — browser user-agent for audit trail
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_audit_action", "action"),
        Index("ix_audit_user_action", "user_id", "action"),
    )


# ═══════════════════════════════════════════════════════════
# WAVE 7 — Literature Paper Storage (local DB persistence)
# ═══════════════════════════════════════════════════════════

class StoredPaper(Base):
    """Locally-persisted literature paper for zero-data-loss caching."""
    __tablename__ = "stored_papers"

    id = Column(String, primary_key=True, default=_uuid)
    query_hash = Column(String, nullable=False)
    doi = Column(String, nullable=True)
    pmid = Column(String, nullable=True)
    pmc_id = Column(String, nullable=True)
    title = Column(Text, default="")
    abstract = Column(Text, default="")
    full_text = Column(Text, default="")
    authors = Column(JSON, default=list)
    year = Column(Integer, nullable=True)
    journal = Column(String, default="")
    url = Column(String, default="")
    source_db = Column(String, default="")
    smiles_extracted = Column(JSON, default=list)
    protein_sequences = Column(JSON, default=list)
    experimental_context = Column(JSON, default=dict)
    provenance = Column(JSON, default=dict)
    citation_count = Column(Integer, default=0)
    relevance_score = Column(Float, default=0.0)
    raw_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_stored_papers_query", "query_hash"),
        Index("ix_stored_papers_doi", "doi"),
        Index("ix_stored_papers_pmid", "pmid"),
    )


# ═══════════════════════════════════════════════════════════
# WAVE 8 — Clinical Workflow Tables (10-Stage Pipeline)
# ═══════════════════════════════════════════════════════════

class ClinicalRecord(Base):
    """EHR data storage with PHI redaction (FR-DB-002, FR-CLIN-001)."""
    __tablename__ = "clinical_records"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    patient_id = Column(String, nullable=False, index=True)  # Hashed/anonymized
    record_type = Column(String, nullable=False)  # ehr | family_history | clinical_note
    raw_text = Column(Text, nullable=True)
    structured_data = Column(JSON, default=dict)
    phi_redacted = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PhenotypeCluster(Base):
    """HDBSCAN clustering results for phenotype analysis (FR-DB-002, FR-CLIN-002)."""
    __tablename__ = "phenotype_clusters"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=False)
    cluster_id = Column(Integer, nullable=False)
    phenotypes = Column(JSON, nullable=False)  # Array of {term, hpo_id, severity}
    size = Column(Integer, nullable=False)
    rarity_score = Column(Float, nullable=False)
    representative_terms = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TissueAnalysis(Base):
    """Histopathology image analysis results (FR-DB-002, FR-CLIN-003)."""
    __tablename__ = "tissue_analyses"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=False)
    image_ref = Column(String, nullable=False)  # S3 key for WSI
    anomalies_detected = Column(JSON, nullable=False)  # Array of {type, location, confidence}
    heatmap_ref = Column(String, nullable=True)  # S3 key for heatmap
    model_version = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BiomarkerProfile(Base):
    """Flow cytometry quantification results (FR-DB-002, FR-CLIN-004)."""
    __tablename__ = "biomarker_profiles"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=False)
    sample_id = Column(String, nullable=False)
    cell_populations = Column(JSON, nullable=False)  # Array of {population, count, percentage}
    abnormal_flags = Column(JSON, default=list)
    reference_comparison = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GenomicVariant(Base):
    """VCF parsing results for genomic variants (FR-DB-002, FR-CLIN-005)."""
    __tablename__ = "genomic_variants"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=False)
    chromosome = Column(String, nullable=False)
    position = Column(Integer, nullable=False)
    ref_allele = Column(String, nullable=False)
    alt_allele = Column(String, nullable=False)
    variant_type = Column(String, nullable=False)  # snv | indel | cnv
    gene_symbol = Column(String, nullable=True, index=True)
    quality_score = Column(Float, nullable=True)
    population_frequency = Column(Float, nullable=True)
    annotations = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PathogenicityPrediction(Base):
    """DL model pathogenicity predictions (FR-DB-002, FR-CLIN-006)."""
    __tablename__ = "pathogenicity_predictions"

    id = Column(String, primary_key=True, default=_uuid)
    variant_id = Column(String, ForeignKey("genomic_variants.id", ondelete="CASCADE"), index=True, nullable=False)
    score = Column(Float, nullable=False)  # 0-1
    classification = Column(String, nullable=False)  # pathogenic | likely_pathogenic | uncertain_significance | likely_benign | benign
    confidence_interval = Column(JSON, nullable=False)  # {lower, upper}
    features_used = Column(JSON, default=list)
    model_version = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DisruptionModel(Base):
    """Mutation effect simulation results (FR-DB-002, FR-CLIN-008)."""
    __tablename__ = "disruption_models"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=False)
    variant_id = Column(String, ForeignKey("genomic_variants.id", ondelete="SET NULL"), nullable=True)
    affected_pathways = Column(JSON, default=list)
    transcriptional_impacts = Column(JSON, default=dict)
    immune_dysregulation = Column(JSON, default=dict)
    disruption_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TherapyStratification(Base):
    """Patient therapy compatibility scores (FR-DB-002, FR-CLIN-010)."""
    __tablename__ = "therapy_stratifications"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=False)
    therapy_type = Column(String, nullable=False)  # stem_cell | bone_marrow | gene_therapy
    compatibility_score = Column(Float, nullable=False)
    risk_benefit_analysis = Column(JSON, nullable=False)
    eligibility_criteria = Column(JSON, nullable=False)
    timeline_estimate = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ConsensusVote(Base):
    """Individual specialist vote per run/entity for MAV consensus (A-7, FR-API-002)."""
    __tablename__ = "consensus_votes"

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=False)
    entity_id = Column(String, nullable=False, index=True)  # gene_symbol or target id
    specialist_role = Column(String(100), nullable=False)
    vote = Column(JSON, nullable=False)  # {score: float, confidence: float, reasoning: str, verdict: str}
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_consensus_votes_run_entity", "run_id", "entity_id"),
    )


class ConsensusResult(Base):
    """MAV consensus voting results (FR-API-002, FR-SUB-002)."""
    __tablename__ = "consensus_results"

    id = Column(String, primary_key=True, default=_uuid)
    claim = Column(Text, nullable=False)
    evidence_bundle_id = Column(String, ForeignKey("evidence_bundles.id", ondelete="SET NULL"), nullable=True)
    jury_size = Column(Integer, nullable=False)
    status = Column(String, nullable=False, index=True)  # verified | contradicted | conflict
    votes = Column(JSON, nullable=False)  # Array of {agent_id, verdict, confidence, reasoning}
    consensus_trace = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# WAVE 9 — Cockpit Run Tracking (Final Product Hardening)
# ═══════════════════════════════════════════════════════════

class CockpitRun(Base):
    """Tracked cockpit analysis run for query lifecycle persistence."""
    __tablename__ = "cockpit_runs"

    id = Column(String, primary_key=True, default=_uuid)
    query = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    result_summary = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    provenance = Column(JSON, nullable=True)
    user_id = Column(String, nullable=True)
    project_id = Column(String, nullable=True)
