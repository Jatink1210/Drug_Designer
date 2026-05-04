/**
 * TypeScript Type Definitions (Drug Designer §94, §78)
 *
 * Mirrors the Pydantic models on the backend. Every API response
 * uses ResponseEnvelope<T>, and all domain types are defined here.
 */

// ── View State (§115, §Rule 2) ─────────────────────────────
export type ViewState =
  | "initial"
  | "loading"
  | "empty"
  | "degraded"
  | "error"
  | "success";

// ── Universal Response Envelope (§78) ──────────────────────
export interface APIError {
  code: string;
  message: string;
  details: Record<string, unknown>;
  recoverable: boolean;
  suggested_action: string;
}

export interface ProvenanceInfo {
  sources: string[];
  generated_at: string;
  model_id?: string;
  runtime_mode: "hosted" | "local";
  run_id?: string;
}

export interface RuntimeContext {
  mode: "hosted" | "local" | "auto";
  selected_runtime: string;
  selected_model: string;
  fallback_used: boolean;
}

export interface TimingInfo {
  started_at: string;
  finished_at: string;
  elapsed_ms: number;
}

export interface PaginationInfo {
  cursor?: string;
  has_more: boolean;
  total_count?: number;
  page_size: number;
}

export interface ResponseEnvelope<T = unknown> {
  request_id: string;
  trace_id: string;
  status: "ok" | "partial" | "degraded" | "error";
  data: T;
  warnings: string[];
  errors: APIError[];
  provenance: ProvenanceInfo;
  runtime_context: RuntimeContext;
  timing: TimingInfo;
}

export interface PaginatedEnvelope<T = unknown> extends ResponseEnvelope<T> {
  pagination: PaginationInfo;
}

// ── Run (§41) ──────────────────────────────────────────────
export type RunState =
  | "CREATED"
  | "QUEUED"
  | "RUNNING"
  | "PARTIAL_SUCCESS"
  | "SUCCESS"
  | "FAILED"
  | "CANCELLED"
  | "TIMED_OUT";

export interface RunRecord {
  run_id: string;
  run_type: string;
  project_id: string;
  state: RunState;
  created_at: string;
  completed_at?: string;
  runtime_context: Record<string, unknown>;
  source_footprint: string[];
  timing: { total_ms: number; per_stage: Record<string, number> };
  input_snapshot: Record<string, unknown>;
  output_artifacts: string[];
  errors: Array<Record<string, unknown>>;
  degraded: { reason?: string; affected_sources: string[] };
  provenance: {
    sources_queried: number;
    sources_succeeded: number;
    contradictions_found: number;
  };
}

// ── Run WebSocket Event (§57) ──────────────────────────────
export interface RunEvent {
  event:
    | "run.progress"
    | "run.stage_complete"
    | "run.error"
    | "run.failed"
    | "run.paused"
    | "run.complete"
    | "run.completed";
  run_id: string;
  timestamp: string;
  payload: {
    stage?: string;
    progress_pct?: number;
    message?: string;
    error?: string;
    sources_completed?: number;
    sources_total?: number;
    degraded_sources?: string[];
    state?: RunState;
  };
}

// ── Evidence (§94.2) ───────────────────────────────────────
export interface EvidenceItem {
  evidence_id: string;
  source_family: string;
  source_name: string;
  source_type: string;
  external_record_id: string;
  normalized_entity_id: string;
  title: string;
  snippet: string;
  url: string;
  published_at?: string;
  retrieved_at: string;
  confidence: number;
  contradiction_state: "none" | "flagged" | "confirmed";
  contradiction_pair_id?: string;
  indian_population_relevant: boolean;
  freshness: "current" | "stale";
  entities: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
}

// ── Target Ranking (§94.3) ────────────────────────────────
export interface TargetScoreBreakdown {
  gwas: number;
  druggability: number;
  pathway_centrality: number;
  expression: number;
  safety: number;
  novelty: number;
  literature: number;
}

export interface TargetRankingItem {
  target_id: string;
  target_symbol: string;
  uniprot_id: string;
  rank: number;
  composite_score: number;
  score_breakdown: TargetScoreBreakdown;
  ucb_score?: number;
  contradiction_flag: boolean;
  explanation: string;
  evidence_item_ids: string[];
}

// ── Disease (§B1) ──────────────────────────────────────────
export interface DiseaseNormalizationResult {
  query_id: string;
  run_id: string;
  raw_input: string;
  normalized_label: string;
  identifiers: Record<string, string>;
  synonyms: string[];
  confidence: number;
}

export interface CandidateGene {
  gene_id: string;
  gene_symbol: string;
  source_count: number;
  score: number;
}

// ── Project (§A7) ──────────────────────────────────────────
export interface ProjectSummary {
  id: string;
  title: string;
  description: string;
  owner_id: string;
  created_at: string;
  last_active: string;
  total_runs: number;
  total_evidence_items: number;
  total_dossiers: number;
}

// ── Source Health (§62) ────────────────────────────────────
export interface SourceHealth {
  source_id: string;
  source_name: string;
  status: "healthy" | "degraded" | "down";
  latency_ms?: number;
  error_rate: number;
}

// ── MAV Consensus (§22.5) ─────────────────────────────────
export interface ConsensusVote {
  agent_id: string;
  verdict: "support" | "refute" | "uncertain";
  confidence: number;
  rationale: string;
}

export interface ConsensusResult {
  claim_id: string;
  claim_text: string;
  status: "verified" | "canonical" | "conflict";
  votes: ConsensusVote[];
  consensus_met: boolean;
  requires_human_arbitration: boolean;
}

// ── Runtime (§34) ──────────────────────────────────────────
export interface ModelRecord {
  model_id: string;
  model_name: string;
  display_name: string;
  provider_type: string;
  mode: string;
  family: string;
  status: string;
}

export interface LocalAgentStatus {
  agent_id: string;
  status: "connected" | "disconnected" | "error";
  platform: string;
  hardware: Record<string, unknown>;
  model_inventory: Record<string, unknown>;
}
