// ── API Base URL resolution ────────────────────────────
// In Tauri desktop mode the backend runs on a dynamic port discovered at
// startup.  In browser/dev mode the Vite proxy forwards /api → localhost:8000.

let _apiBase = "/api/v1";
let _resolvePromise: Promise<string> | null = null;

export async function ensureApiBase(): Promise<string> {
  if (_resolvePromise) return _resolvePromise;

  _resolvePromise = (async () => {
    // Tauri v2 injects window.__TAURI__ when app.withGlobalTauri is true.
    // We call the raw IPC directly to avoid importing @tauri-apps/api (which
    // is not available in browser builds).
    if (
      typeof window !== "undefined" &&
      (window as any).__TAURI__?.core?.invoke
    ) {
      try {
        const port: number = await (window as any).__TAURI__.core.invoke(
          "get_api_port",
        );
        _apiBase = `http://localhost:${port}/api/v1`;
      } catch {
        /* fallback to /api */
      }
    }
    return _apiBase;
  })();

  return _resolvePromise;
}

/* ─── Search Types ────────────────────────────────────── */

export interface SearchRequest {
  query: string;
  mode?: string;
  filters?: Record<string, unknown>;
  limit?: number;
  strict_evidence?: boolean;
  sources?: string[];
  year_from?: number | null;
  year_to?: number | null;
}

export interface SummaryRequest {
  query: string;
  context: Record<string, unknown>;
}

export interface SummaryResponse {
  query: string;
  summary: string;
  model_used: string;
  latency_ms: number;
}

export interface EntityDetailRequest {
  entity_id: string;
  entity_type: string;
  entity_name?: string;
}

export interface EntityDetail {
  entity_id: string;
  entity_type: string;
  entity_name: string;
  description: string;
  publications: Record<string, unknown>[];
  patents: Record<string, unknown>[];
  clinical_trials: Record<string, unknown>[];
  chembl_data: Record<string, unknown>[];
}

export interface CategoryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  total: number;
}

export type EntityIntelligenceSlotType = "drug" | "disease" | "molecule" | "gene" | "protein" | "blank" | "variant";

export interface EntityIntelligenceEntity {
  entityId: string;
  entityType: string;
  entityName: string;
  sourceCategory?: string;
  identifiers?: Record<string, string>;
  attributes?: Record<string, unknown>;
}

export interface EntityIntelligenceProvenance {
  source: string;
  sourceRecordId?: string;
  retrievedAt?: string;
  confidence?: number | null;
  contradictionState?: string | null;
  evidenceCount?: number | null;
  requestId?: string;
  traceId?: string;
  runId?: string;
}

export interface EntityIntelligenceResolvedSlot {
  slotIndex: number;
  declaredType: EntityIntelligenceSlotType;
  resolvedType: EntityIntelligenceSlotType;
  queryValues: string[];
  results: EntityIntelligenceEntity[];
  alternatives: string[];
  conflicts: string[];
  provenance: EntityIntelligenceProvenance[];
  degradedSources: string[];
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties?: Record<string, unknown>;
}
export interface GraphEdge {
  source: string;
  target: string;
  label: string;
  weight: number;
  type?: string;
  /** Populated only when type === "contradiction" */
  contradiction_detail?: {
    claim: string;
    agents: string[];
    verdict: string;
  };
}

export interface EntityIntelligenceGraphEdge extends GraphEdge {
  id?: string;
  properties?: Record<string, unknown>;
}

export interface EntityIntelligenceTarget {
  symbol: string;
  rank: number;
  composite_score: number;
  ucb_score: number;
  uncertainty: number;
  contradiction_flag: boolean;
  signals: Record<string, number>;
  explanation: string;
  evidence_count: number;
  sources: string[];
}

export interface EntityIntelligencePathway {
  pathway_id: string;
  name: string;
  genes: string[];
  hit_count: number;
  source: string;
}

export interface EntityIntelligenceGOTerm {
  go_id: string;
  name: string;
  aspect: string;
  genes: string[];
  hit_count: number;
}

export interface EntityIntelligenceStructureCandidate {
  entityName: string;
  geneSymbol: string;
  uniprotId: string;
  pdbId: string;
  alphafoldId: string;
}

export interface EntityIntelligenceAnalyzeRequest {
  slots: Array<{
    slot_index: number;
    declared_type: EntityIntelligenceSlotType;
    value?: string;
    values?: string[];
  }>;
  graph_max_nodes?: number;
  graph_depth?: number;
}

export interface EntityIntelligenceAnalyzeResult {
  run_id: string;
  resolvedSlots: EntityIntelligenceResolvedSlot[];
  entities: EntityIntelligenceEntity[];
  provenance: EntityIntelligenceProvenance[];
  diseaseIntelligence: {
    queries: Array<{
      query: string;
      normalized: string;
      identifiers: Record<string, string>;
      candidateGenes: Array<Record<string, unknown>>;
    }>;
    candidateGenes: Array<Record<string, unknown>>;
    degradedSources: string[];
  };
  targetPrioritization: {
    targets: EntityIntelligenceTarget[];
    degradedSources: string[];
  };
  graph: GraphBuildResult & { edges: EntityIntelligenceGraphEdge[] };
  ppi: {
    nodes: GraphNode[];
    edges: EntityIntelligenceGraphEdge[];
    queryGenes: string[];
  };
  pathways: {
    enrichedPathways: EntityIntelligencePathway[];
    goTerms: EntityIntelligenceGOTerm[];
  };
  structures: EntityIntelligenceStructureCandidate[];
  enrichment: {
    communities: Record<string, unknown>;
    centrality: Record<string, unknown>;
    goTerms: EntityIntelligenceGOTerm[];
  };
  summary: {
    slotCount: number;
    entityCount: number;
    geneCount: number;
    diseaseCount: number;
    graphQuery: string;
    elapsed_ms: number;
  };
  degraded_sources?: string[];
}

export interface CitationRefDTO {
  source: string;
  external_id: string;
  title: string;
  year?: number | null;
  url: string;
  confidence: number;
  evidence_type: string;
}

export interface ContradictionDTO {
  claim_a: string;
  claim_b: string;
  source_a: CitationRefDTO;
  source_b: CitationRefDTO;
  severity: string;
  explanation: string;
}

export interface EvidenceSummaryDTO {
  contradictions: ContradictionDTO[];
  overall_confidence: number;
  evidence_count: number;
  top_citations: CitationRefDTO[];
  source_breakdown?: Record<string, number>;
}

export interface SearchResponse {
  query: string;
  intent: { intent: string; search_term: string; method: string };
  summary_stats: {
    total_results: number;
    categories_found: number;
    pubmed_count: number | null;
    clinical_trials_count: number | null;
    sources_queried: number;
  };
  categories: Record<string, CategoryResult>;
  preview_graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  provenance: { sources_hit: string[]; timestamps: Record<string, number> };
  timings: Record<string, number>;
  errors: string[];
  evidence_summary?: EvidenceSummaryDTO;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  check_ms?: number;
  issues?: string[] | null;
  ollama_ok?: boolean;
  connectors_active?: number;
  connectors_total?: number;
  connectors_degraded?: number;
  runtime_mode?: string;
  active_model?: string;
  active_runs?: number;
  active_project_name?: string;
  last_run_at?: string;
}
export interface DiagnosticsResponse {
  status: string;
  version: string;
  components: Record<string, { status: string; [k: string]: unknown }>;
  connectors: Record<
    string,
    { status: string; latency_ms?: number; error?: string }
  >;
}

/* ─── Structure Types ─────────────────────────────────── */

export interface StructureSummary {
  pdb_id: string;
  title: string;
  classification: string;
  organism: string;
  expression_system: string;
  method: string;
  resolution: number | null;
  r_work: number | null;
  r_free: number | null;
  space_group: string;
  cell_dimensions: Record<string, number | null>;
  deposition_date: string;
  release_date: string;
  revision_date: string;
  primary_citation: {
    title: string;
    journal: string;
    year: number | null;
    doi: string;
    pmid: string;
  };
  macromolecules: Array<{
    entity_id: string;
    type: string;
    chains: string[];
    length: number | null;
    sequence: string;
    organism: string;
    uniprot_ids: string[];
    gene_names: string[];
    description: string;
  }>;
  ligands: Array<{
    comp_id: string;
    name: string;
    formula: number | null;
    type: string;
  }>;
  assemblies: Array<{
    assembly_id: string;
    polymer_entity_count: number | null;
    oligomeric_state: string;
    kind: string;
  }>;
  revision_count: number;
  revision_history: Array<{
    version: number | null;
    date: string;
    type: string;
  }>;
  downloads: Record<string, string>;
  url: string;
}

export interface StructureAnnotations {
  pfam: Array<{ id: string; name: string }>;
  interpro: Array<{ id: string; name: string }>;
  go: Array<{ id: string; name: string }>;
  ec: Array<{ id: string; name: string }>;
  ptms: unknown[];
}
export interface ExperimentData {
  method: string;
  crystal_growth: Record<string, unknown>;
  data_collection: Record<string, unknown>;
  refinement: Record<string, unknown>;
  cell: Record<string, unknown>;
  software: Array<{ name: string; version: string; classification: string }>;
}
export interface SequenceData {
  entity_id: string;
  chains: string[];
  length: number | null;
  sequence: string;
  type: string;
  residue_confidence?: number[];
  features: Array<{
    type: string;
    name: string;
    start: number | null;
    end: number | null;
  }>;
}

export interface StructureCompareRequest {
  left_pdb_id?: string;
  right_pdb_id?: string;
  left_pdb_text?: string;
  right_pdb_text?: string;
  left_structure_url?: string;
  right_structure_url?: string;
  left_chain?: string;
  right_chain?: string;
}

export interface StructureCompareResult {
  left_label: string;
  right_label: string;
  left_chain: string;
  right_chain: string;
  left_selection: string;
  right_selection: string;
  aligned_residues: number;
  matching_residues: number;
  sequence_identity: number;
  coverage_left: number;
  coverage_right: number;
  left_chain_length: number;
  right_chain_length: number;
  left_residue_range: string;
  right_residue_range: string;
  rmsd: number;
  rotation: number[][];
  translation: number[];
}

/* ─── Docking Types ───────────────────────────────────── */

export interface DockingRequest {
  receptor_path: string;
  ligand_path: string;
  center: number[];
  box_size?: number[];
  engine?: string;
  exhaustiveness?: number;
  num_modes?: number;
}
export interface DockingPose {
  rank: number;
  affinity_kcal: number;
  rmsd_lb: number | null;
  rmsd_ub: number | null;
}
export interface DockingResult {
  run_id: string;
  status: string;
  engine: string;
  elapsed_seconds: number;
  poses: DockingPose[];
  error?: string;
}

/* ─── Molecule Types ──────────────────────────────────── */

export interface PhysiochemProps {
  smiles: string;
  mw?: number;
  logp?: number;
  hbd: number;
  hba: number;
  tpsa?: number;
  rotatable_bonds: number;
  lipinski_violations: number;
  druglikeness: string;
}
export interface ADMETConformalInterval {
  point: number | number[];
  interval?: [number, number];
  prediction_set?: number[];
  alpha?: number;
  quantile?: number;
  calibrated: boolean;
}

export interface ADMETResult {
  smiles: string;
  absorption: Record<string, unknown>;
  distribution: Record<string, unknown>;
  metabolism: Record<string, unknown>;
  excretion: Record<string, unknown>;
  toxicity: Record<string, unknown>;
  synthetic_accessibility: Record<string, unknown>;
  /** I-2: per-property conformal prediction intervals (90% coverage) */
  conformal_intervals?: Record<string, ADMETConformalInterval>;
  confidence_interval?: {
    lower: number;
    upper: number;
    std: number;
    method: string;
    level: string;
    note: string;
  };
}

/* ─── Evidence Types ──────────────────────────────────── */

export interface EvidenceSearchRequest {
  query: string;
  sources?: string[];
  limit?: number;
  year_from?: number;
  year_to?: number;
}
export interface EvidenceResult {
  query: string;
  total: number;
  results: Record<string, Record<string, unknown>[]>;
}

/* ─── Report Types ────────────────────────────────────── */

export interface ReportRequest {
  title?: string;
  query?: string;
  sections?: string[];
  search_data?: Record<string, unknown>;
  structure_data?: Record<string, unknown>;
  docking_data?: Record<string, unknown>;
  notes?: string;
}
export interface ReportResult {
  report_id: string;
  status: string;
  sections: string[];
  html_path: string;
  json_path: string;
}

/* ─── Data Manager Types ──────────────────────────────── */

export interface ConnectorInfo {
  id: string;
  name: string;
  required: boolean;
  enabled: boolean;
}

/* ─── API Functions ───────────────────────────────────── */

async function post<T>(path: string, body: unknown): Promise<T> {
  const base = await ensureApiBase();
  const resp = await fetch(`${base}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
  });
  if (!resp.ok) throw new Error(`${path} failed: ${resp.status}`);
  const json = await resp.json();
  // Automatically unwrap the universal ResponseEnvelope if present.
  if (json && json.data !== undefined && json.request_id !== undefined) {
    return json.data as T;
  }
  return json as T;
}
async function get<T>(path: string): Promise<T> {
  const base = await ensureApiBase();
  const resp = await fetch(`${base}${path}`, { credentials: "include", cache: "no-store" });
  if (!resp.ok) throw new Error(`${path} failed: ${resp.status}`);
  const json = await resp.json();
  if (json && json.data !== undefined && json.request_id !== undefined) {
    return json.data as T;
  }
  return json as T;
}
async function httpDelete(path: string): Promise<void> {
  const base = await ensureApiBase();
  const resp = await fetch(`${base}${path}`, { method: "DELETE", credentials: "include" });
  if (!resp.ok) throw new Error(`${path} failed: ${resp.status}`);
}

// Search
export const searchAPI = (req: SearchRequest) =>
  post<SearchResponse>("/search", req);
export const searchSummaryAPI = (req: SummaryRequest) =>
  post<SummaryResponse>("/search/summary", req);
export const entityDetailAPI = (req: EntityDetailRequest) =>
  post<EntityDetail>("/search/entity-detail", req);
export const entityIntelligenceAnalyzeAPI = (req: EntityIntelligenceAnalyzeRequest) =>
  post<EntityIntelligenceAnalyzeResult>("/entity-intelligence/analyze", req);

// Health
export const healthAPI = () => get<HealthResponse>("/health");
export const diagnosticsAPI = () => get<DiagnosticsResponse>("/diagnostics");

// Structure
export const structureSearchAPI = (q: string) =>
  get<Record<string, unknown>>(`/structure/search?q=${encodeURIComponent(q)}`);
export const structureSummaryAPI = (pdbId: string) =>
  get<StructureSummary>(`/structure/${pdbId}`);
export const structureAnnotationsAPI = (pdbId: string) =>
  get<StructureAnnotations>(`/structure/${pdbId}/annotations`);
export const structureExperimentAPI = (pdbId: string) =>
  get<ExperimentData>(`/structure/${pdbId}/experiment`);
export const structureSequenceAPI = (pdbId: string) =>
  get<SequenceData[]>(`/structure/${pdbId}/sequence`);
export const structureBindingSitesAPI = (targetId: string) =>
  get<Record<string, unknown>>(`/structure/${targetId}/pockets`);
export const structureByTargetAPI = (targetId: string) =>
  get<Record<string, unknown>>(`/structure/by-target/${targetId}`);
export const structurePredictAPI = (targetId: string) =>
  get<Record<string, unknown>>(`/structure/predict/${encodeURIComponent(targetId)}`);
export const structureCompareAPI = (req: StructureCompareRequest) =>
  post<StructureCompareResult>("/structure/compare", req);
export const alphafoldAPI = (uniprotId: string) =>
  get<Record<string, unknown>>(`/structure/alphafold/${uniprotId}`);

// Docking
export const dockingRunAPI = (req: DockingRequest) =>
  post<DockingResult>("/docking/run", req);
export const dockingPocketsAPI = (receptor_path: string) =>
  post<Record<string, unknown>>("/docking/pockets", { receptor_path });
export const dockingRunsAPI = () =>
  get<Record<string, unknown>[]>("/docking/runs");

// Molecules
export const moleculeScoreAPI = (smiles: string[]) =>
  post<PhysiochemProps[]>("/molecules/score", { smiles });
export const moleculeADMETAPI = (smiles: string[]) =>
  post<ADMETResult[]>("/molecules/admet", { smiles });
export const moleculeAnalogsAPI = (smiles: string, method?: string) =>
  post<Record<string, unknown>>("/molecules/analogs", {
    smiles,
    method: method || "similarity",
  });
export const moleculeNoveltyAPI = (smiles: string) =>
  post<Record<string, unknown>>("/molecules/novelty", { smiles });
export const designIterationsAPI = () =>
  get<Record<string, unknown>[]>("/molecules/iterations");

// Evidence
export const evidenceSearchAPI = (req: EvidenceSearchRequest) =>
  post<EvidenceResult>("/evidence/search", req);
export const evidenceExportAPI = (query: string, format: string) =>
  get<Record<string, unknown>>(
    `/evidence/export?query=${encodeURIComponent(query)}&format=${format}`,
  );

// Reports
export const reportGenerateAPI = (req: ReportRequest) =>
  post<ReportResult>("/reports/generate", req);
export const reportListAPI = () =>
  get<Record<string, unknown>[]>("/reports/list");

// Data Manager
export const dataKeysAPI = () => get<Record<string, unknown>>("/data/keys");
export const dataSetKeyAPI = (service: string, key: string) =>
  post<Record<string, string>>("/data/keys", { service, key });
export const dataDeleteKeyAPI = (service: string) =>
  httpDelete(`/data/keys/${service}`);
export const dataConnectorsAPI = () => get<ConnectorInfo[]>("/data/connectors");
export const dataToggleConnectorAPI = (
  connector_id: string,
  enabled: boolean,
) =>
  post<Record<string, string>>("/data/connectors/toggle", {
    connector_id,
    enabled,
  });
export const dataCacheAPI = () => get<Record<string, unknown>>("/data/cache");
export const dataClearCacheAPI = () => httpDelete("/data/cache");
export const dataStorageAPI = () =>
  get<Record<string, unknown>>("/data/storage");

// Pathways
export const pathwaysSearchAPI = (
  query: string,
  source: string = "reactome",
  limit: number = 20,
) =>
  post<
    Array<{
      id: string;
      canonical_name: string;
      description: string;
      species: string;
      url: string;
      pathway_id: string;
    }>
  >("/pathways/search", { query, source, limit });
export const pathwaysDetailAPI = (id: string) =>
  get<{
    id: string;
    canonical_name: string;
    genes: string[];
    gene_count: number;
    url: string;
  }>(`/pathways/${encodeURIComponent(id)}`);

// Graph / KG
export interface GraphStats {
  nodes: Record<string, number>;
  edges: Record<string, number>;
  total_nodes: number;
  total_edges: number;
}
export interface GraphSample {
  nodes: Array<{
    id: string;
    label: string;
    properties: Record<string, unknown>;
  }>;
  edges: Array<{
    source: string;
    target: string;
    type: string;
    properties: Record<string, unknown>;
  }>;
}
export const graphStatsAPI = () => get<GraphStats>("/graph/stats");
export const graphSampleAPI = (limit: number = 50) =>
  get<GraphSample>(`/graph/sample?limit=${limit}`);
export const graphNeighborhoodAPI = (entityId: string, depth: number = 1) =>
  post<Record<string, unknown>>("/graph/neighborhood", {
    entity_id: entityId,
    depth,
  });

// Graph Build — multi-source search to KG
export interface GraphBuildResult {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    total_nodes: number;
    total_edges: number;
    entity_types: Record<string, number>;
    query: string;
    depth: number;
    latency_ms: number;
  };
  degraded_sources?: string[];
}
export const graphBuildAPI = (query: string, maxNodes: number = 2000): Promise<GraphBuildResult> =>
  post<GraphBuildResult>("/graph/build", { query, max_nodes: maxNodes, depth: 3 });

// Catalog
export interface CatalogStats {
  collections: Record<string, number>;
  total: number;
}
export interface CatalogSearchResult {
  items: Array<Record<string, unknown>>;
  total: number;
}
export const catalogStatsAPI = () => get<CatalogStats>("/catalog/stats");
export const catalogSearchAPI = (entityType: string, limit: number = 50) =>
  post<CatalogSearchResult>("/catalog/search", {
    entity_type: entityType,
    limit,
  });

// Runtimes
export interface HardwareCapabilities {
  cpu_cores: number;
  ram_gb: number;
  gpu: string;
  gpu_name: string | null;
  vram_gb: number;
  airllm_installed: boolean;
}
export interface RuntimeInfo {
  id: string;
  name: string;
  status: string;
  capabilities: string[];
}
export interface RuntimesResponse {
  capabilities: HardwareCapabilities;
  available: RuntimeInfo[];
  active: string;
  compute_mode: string;
}
export interface ModelCatalogEntry {
  name: string;
  ollama_id: string;
  hf_repo_or_url: string;
  size_gb: number;
  parameters: string;
  min_ram_gb: number;
  min_vram_gb: number;
  compute_modes: string[];
  quantization_levels: string[];
  default_quantization: string;
  context_window: number;
  runtimes_supported: string[];
  tags: string[];
  description: string;
}
export interface RecommendResponse {
  compute_mode: string;
  recommended_model: ModelCatalogEntry | null;
  compatible_models: ModelCatalogEntry[];
  hardware: HardwareCapabilities;
}
export interface InstalledModel {
  name: string;
  size: number;
  modified_at: string;
}

export const runtimesListAPI = () => get<RuntimesResponse>("/runtime/status");
export const runtimesSelectAPI = (
  runtime_id: string,
  model_name?: string,
  endpoint?: string,
  compute_mode?: string,
) =>
  post<Record<string, string>>("/runtime/select", {
    runtime_id,
    model_name,
    endpoint,
    compute_mode,
  });
export const runtimesHealthAPI = () =>
  get<Record<string, unknown>>("/runtime/status");
export const runtimesRecommendAPI = () =>
  get<RecommendResponse>("/runtime/status");

// Models
export const modelsCatalogAPI = () =>
  get<ModelCatalogEntry[]>("/models/catalog");
export const modelsInstalledAPI = () =>
  get<InstalledModel[]>("/models/installed");
export const modelsPullAPI = (model_id: string) =>
  post<Record<string, string>>("/models/pull", { model_id });
export const modelsDeleteAPI = (model_id: string) =>
  httpDelete(`/models/${model_id}`);
export const modelsCompatibilityAPI = (model_name: string) =>
  get<Record<string, unknown>>(
    `/models/compatibility/${encodeURIComponent(model_name)}`,
  );

// Endpoint probing — connect to existing local LLM servers without downloading
export interface ProbeResult {
  reachable: boolean;
  server_type: "ollama" | "openai_compat" | "unknown";
  models: Array<{ name: string; size: number }>;
  endpoint: string;
}
export const probeEndpointAPI = (url: string) =>
  post<ProbeResult>("/runtime/probe-endpoint", { url });

// Settings
export const settingsGetAPI = () => get<Record<string, unknown>>("/settings");
export const settingsUpdateAPI = (s: Record<string, unknown>) =>
  post<Record<string, unknown>>("/settings", s);

// ── Runs (§23, §41, §92) ────────────────────────────────
export interface RunCreateRequest {
  run_type: string;
  input: Record<string, unknown>;
  project_id?: string;
}
export interface RunListParams {
  cursor?: string;
  limit?: number;
  state?: string;
  project_id?: string;
}
export const runsCreateAPI = (req: RunCreateRequest) =>
  post<Record<string, unknown>>("/runs", req);
export const runsListAPI = (params?: RunListParams) => {
  const qs = new URLSearchParams();
  if (params?.cursor) qs.set("cursor", params.cursor);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.state) qs.set("state", params.state);
  if (params?.project_id) qs.set("project_id", params.project_id);
  const q = qs.toString();
  return get<Record<string, unknown>[]>(`/runs${q ? `?${q}` : ""}`);
};
export const runGetAPI = (runId: string) =>
  get<Record<string, unknown>>(`/runs/${runId}`);
export const runCancelAPI = (runId: string) =>
  post<Record<string, unknown>>(`/runs/${runId}/cancel`, {});
export const runRetryAPI = (runId: string) =>
  post<Record<string, unknown>>(`/runs/${runId}/retry`, {});
export const runEventsAPI = (runId: string) =>
  get<Record<string, unknown>[]>(`/runs/${runId}/events`);
export const runArtifactsAPI = (runId: string) =>
  get<Record<string, unknown>[]>(`/runs/${runId}/artifacts`);
export const runJobsAPI = (runId: string) =>
  get<Record<string, unknown>[]>(`/runs/${runId}/jobs`);

// ── Exports (§28, §71) ──────────────────────────────────
export interface ExportCreateRequest {
  format: "json" | "csv" | "pdf" | "docx" | "sdf" | "pdb" | "png";
  scope: Record<string, unknown>;
  title?: string;
}
export const exportCreateAPI = (req: ExportCreateRequest) =>
  post<Record<string, unknown>>("/exports", req);
export const exportsListAPI = () =>
  get<Record<string, unknown>[]>("/exports");
export const exportGetAPI = (exportId: string) =>
  get<Record<string, unknown>>(`/exports/${exportId}`);
export const exportDownloadAPI = async (exportId: string) => {
  const base = await ensureApiBase();
  window.open(`${base}/exports/${exportId}/download`, "_blank");
};

// ── Sources (§17, §62) ──────────────────────────────────
export const sourcesListAPI = () =>
  get<Record<string, unknown>[]>("/sources");
export const sourcesHealthAPI = () =>
  get<Record<string, unknown>[]>("/sources/health");
export const sourceToggleAPI = (sourceId: string, enabled: boolean) =>
  post<Record<string, unknown>>("/sources/toggle", { source_id: sourceId, enabled });
export const sourceRefreshAPI = (sourceId: string) =>
  post<Record<string, unknown>>("/sources/refresh", { source_id: sourceId });

// ── Auth (§22) ───────────────────────────────────────────
export const authRefreshAPI = () =>
  post<{ access_token: string }>("/auth/refresh", {});
export const authLogoutAPI = () =>
  post<Record<string, string>>("/auth/logout", {});
export const authChangePasswordAPI = (currentPassword: string, newPassword: string) =>
  post<Record<string, string>>("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });

// ── Evidence: Annotate & Bundles (§7.2) ─────────────────
export interface AnnotationRequest {
  evidence_id: string;
  annotation_type: "note" | "flag" | "contradiction" | "bookmark";
  content: string;
  project_id?: string;
}
export const evidenceAnnotateAPI = (req: AnnotationRequest) =>
  post<Record<string, unknown>>("/evidence/annotate", req);
export interface BundleCreateRequest {
  name: string;
  description?: string;
  project_id?: string;
}
export const evidenceBundleCreateAPI = (req: BundleCreateRequest) =>
  post<Record<string, unknown>>("/evidence/bundles", req);
export const evidenceBundlesListAPI = (projectId?: string) =>
  get<Record<string, unknown>[]>(
    `/evidence/bundles${projectId ? `?project_id=${projectId}` : ""}`,
  );
export const evidenceBundleAddItemsAPI = (
  bundleId: string,
  evidenceIds: string[],
) =>
  post<Record<string, unknown>>(`/evidence/bundles/${bundleId}/items`, {
    evidence_ids: evidenceIds,
  });

// ── Y-1: Live Contradiction & Similarity Detection ──────
export const contradictionLiveDetectAPI = (query: string, abstracts?: string[]) =>
  post<Record<string, unknown>>("/contradictions/analyze", {
    query,
    max_contradictions: 50,
    max_similarities: 20,
  });
export const contradictionBatchDetectAPI = (projectId?: string, items?: string[]) =>
  post<Record<string, unknown>>("/evidence/contradictions/batch-detect", {
    project_id: projectId ?? "",
    items: items ?? [],
  });
export const contradictionDetailAPI = (contradictionId: string) =>
  get<Record<string, unknown>>(`/evidence/contradictions/${contradictionId}`);
export const contradictionResolveAPI = (contradictionId: string, resolution: string, annotation?: string) =>
  post<Record<string, unknown>>(`/evidence/contradictions/${contradictionId}/resolve`, {
    resolution,
    annotation: annotation ?? "",
  });

// ── Y-2: PICO Extraction ────────────────────────────────
export const picoExtractAPI = (text: string, useLlm?: boolean) =>
  post<Record<string, unknown>>("/pico/extract", {
    query: text,
    texts: [text],
    max_publications: 10,
  });
export const picoTranslationalExtractAPI = (text: string) =>
  post<Record<string, unknown>>("/translational/pico/extract", { text });

// ── Disease (§B1) ────────────────────────────────────────
export const diseaseNormalizeAPI = (rawInput: string) =>
  post<Record<string, unknown>>("/disease/normalize", { raw_input: rawInput });
export const diseaseGenesAPI = (diseaseId: string, limit?: number) =>
  post<Record<string, unknown>>("/disease/genes", { disease_id: diseaseId, limit });
export const diseaseUniprotMapAPI = (geneSymbols: string[]) =>
  post<Record<string, unknown>>("/disease/uniprot-map", { gene_symbols: geneSymbols });

// ── Targets (§10, §122) ────────────────────────────────────
export const targetDruggabilityAPI = (symbol: string) =>
  get<Record<string, unknown>>(`/targets/${encodeURIComponent(symbol)}/druggability`);

// ── Targets Ranking (§122) ──────────────────────────────
/** Canonical target ranking endpoint */
export const targetRankAPI = (queryId: string, candidates: string[]) =>
  post<Record<string, unknown>>("/targets/rank", {
    query_id: queryId,
    candidates,
  });

/** @deprecated Use targetRankAPI instead. Forwards to /targets/rank. */
export const targetPrioritizeAPI = (disease: string, genes: string[]) =>
  post<PrioritizeResult>("/targets/prioritize", { disease, genes });

// ── Pathways (§13) ───────────────────────────────────────
export const pathwaysEnrichmentAPI = (geneList: string[], organism?: string) =>
  post<Record<string, unknown>>("/pathways/enrichment", {
    gene_list: geneList,
    organism: organism ?? "Homo sapiens",
  });

// ── Dossiers (§A10) ──────────────────────────────────────
export const dossiersListAPI = (projectId?: string) =>
  get<Record<string, unknown>[]>(
    `/dossiers${projectId ? `?project_id=${projectId}` : ""}`,
  );
export const dossierExportAPI = (
  dossierId: string,
  format: "json" | "html" | "pdf" = "json",
) => post<Record<string, unknown>>(`/dossiers/${dossierId}/export`, { format });

// ── Reports (§25) ────────────────────────────────────────
export const reportGetAPI = (reportId: string) =>
  get<Record<string, unknown>>(`/reports/${reportId}`);

// ── Graph (§82) ──────────────────────────────────────────
export interface GraphExportRequest {
  format: "json" | "graphml" | "cytoscape";
  node_ids?: string[];
  max_nodes?: number;
}
export const graphExportAPI = (req: GraphExportRequest) =>
  post<Record<string, unknown>>("/graph/export", req);

// ── Security (§61.3) ────────────────────────────────────
export interface AuditLogParams {
  user_id?: string;
  action?: string;
  limit?: number;
  offset?: number;
}
export const securityAuditLogAPI = (params?: AuditLogParams) => {
  const qs = new URLSearchParams();
  if (params?.user_id) qs.set("user_id", params.user_id);
  if (params?.action) qs.set("action", params.action);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const q = qs.toString();
  return get<Record<string, unknown>[]>(`/security/audit-log${q ? `?${q}` : ""}`);
};
export const securitySessionsAPI = () =>
  get<Record<string, unknown>[]>("/security/sessions");
export const securityRevokeSessionAPI = (sessionId: string) =>
  httpDelete(`/security/sessions/${sessionId}`);

// ── Disease Intelligence (§121) ──────────────────────────
export const diseaseStartAPI = (rawInput: string) =>
  post<Record<string, unknown>>("/disease/start", { raw_input: rawInput });
export const diseaseRunAPI = (rawInput: string) =>
  post<Record<string, unknown>>("/disease/run", { raw_input: rawInput });
export const diseaseRunResultAPI = (runId: string) =>
  get<Record<string, unknown>>(`/disease/run/${runId}`);
export const diseaseQueryGenesAPI = (queryId: string) =>
  get<Record<string, unknown>>(`/disease/query/${queryId}/genes`);
export const diseaseQueryMappingsAPI = (queryId: string) =>
  get<Record<string, unknown>>(`/disease/query/${queryId}/mappings`);
export const diseaseCandidatesAPI = (queryId: string) =>
  get<Record<string, unknown>>(`/disease/candidates/${queryId}`);
export const diseaseContradictionsAPI = (queryId: string) =>
  get<Record<string, unknown>>(`/disease/contradictions/${queryId}`);
export const diseaseQueriesAPI = () =>
  get<Record<string, unknown>[]>("/disease/queries");
export const diseaseDeleteAPI = (queryId: string) =>
  httpDelete(`/disease/${queryId}`);
export const diseaseExportAPI = (format: string = "json") =>
  post<Record<string, unknown>>("/disease/export", { format });
export const diseaseSendToTargetAPI = (queryId: string, symbols: string[]) =>
  post<Record<string, unknown>>("/disease/send-to-target-ranking", {
    query_id: queryId,
    gene_symbols: symbols,
  });

// ── Targets (§122) ──────────────────────────────────────
export interface TargetSignals {
  gwas: number;
  druggability: number;
  pathways: number;
  expression: number;
  novelty: number;
  safety: number;
  literature: number;
  [key: string]: number;
}
export interface PrioritizedTarget {
  symbol: string;
  rank: number;
  composite_score: number;
  ucb_score: number;
  uncertainty: number;
  contradiction_flag: boolean;
  signals: TargetSignals;
  explanation: string;
  evidence_count: number;
  sources: string[];
  /** Set when Indian population boost was applied (§D1) */
  indian_population_boost_applied?: boolean;
  indian_context_score?: number;
  /** Optional GAT attention weights per signal (keyed by signal name) */
  gat_attention_weights?: Record<string, number>;
}
export interface PrioritizeResult {
  targets: PrioritizedTarget[];
  run_id: string | null;
  degraded_sources?: string[];
}
// targetPrioritizeAPI and targetRankAPI are defined above in the Targets section
export const targetRankResultAPI = (runId: string) =>
  get<Record<string, unknown>>(`/targets/rank/${runId}`);
export const targetGetAPI = (symbol: string) =>
  get<Record<string, unknown>>(`/targets/${encodeURIComponent(symbol)}`);
export const targetScoresAPI = (runId: string) =>
  get<Record<string, unknown>>(`/targets/${runId}/scores`);
export const targetCompareAPI = (symbols: string[]) =>
  get<Record<string, unknown>>(`/targets/compare?symbols=${symbols.join(",")}`);
export const targetExportAPI = (runId?: string, symbols?: string[], format: string = "csv") =>
  post<Record<string, unknown>>("/targets/export", { run_id: runId, symbols, format });
export const targetSendToDossierAPI = (targetSymbols: string[], dossierId: string) =>
  post<Record<string, unknown>>("/targets/send-to-dossier", {
    target_symbols: targetSymbols,
    dossier_id: dossierId,
  });

// ── UniProt Mapping (§123) ──────────────────────────────
export const mappingStartAPI = (queryId: string, geneSymbols: string[]) =>
  post<Record<string, unknown>>("/mapping/uniprot/start", {
    query_id: queryId,
    gene_symbols: geneSymbols,
  });
export const mappingStatusAPI = (queryId: string) =>
  get<Record<string, unknown>>(`/mapping/uniprot/${queryId}`);
export const mappingResultsAPI = (queryId: string) =>
  get<Record<string, unknown>>(`/mapping/uniprot/${queryId}`);
export const mappingRetryAPI = (mappingId: string) =>
  post<Record<string, unknown>>("/mapping/uniprot/retry", { mapping_id: mappingId });
export const mappingAcceptAPI = (mappingId: string, uniprotId: string) =>
  post<Record<string, unknown>>("/mapping/uniprot/accept", {
    mapping_id: mappingId,
    accepted_uniprot_id: uniprotId,
  });

// ── Graph (§124) ─────────────────────────────────────────
export const graphEdgeAPI = (edgeId: string) =>
  get<Record<string, unknown>>(`/graph/edge/${edgeId}`);
export const graphExportSnapshotAPI = (format: string = "json", nodeIds?: string[]) =>
  post<Record<string, unknown>>("/graph/export-snapshot", { format, node_ids: nodeIds });

// ── Pathways (§125) ──────────────────────────────────────
export const pathwayMembersAPI = (pathwayId: string) =>
  get<Record<string, unknown>>(`/pathways/${encodeURIComponent(pathwayId)}/members`);
export const pathwayDiseaseContextAPI = (pathwayId: string, diseaseQueryId: string) =>
  get<Record<string, unknown>>(
    `/pathways/${encodeURIComponent(pathwayId)}/disease-context?disease_query_id=${diseaseQueryId}`,
  );
export const pathwayExportAPI = (pathwayIds: string[], format: string = "json") =>
  post<Record<string, unknown>>("/pathways/export", { pathway_ids: pathwayIds, format });

// ── Structure (§126) ────────────────────────────────────
export const structurePocketsAPI = (targetId: string) =>
  get<Record<string, unknown>>(`/structure/${targetId}/pockets`);

// ── Design Studio (§126) ────────────────────────────────
export const designStartSessionAPI = (
  targetId: string,
  projectId?: string,
  bindingSite?: Record<string, unknown>,
  sourceContext?: Record<string, unknown>,
) =>
  post<Record<string, unknown>>("/design/session/start", {
    target_id: targetId,
    project_id: projectId,
    binding_site: bindingSite,
    source_context: sourceContext,
  });
export const designRetrieveCandidatesAPI = (sessionId: string, targetId: string) =>
  post<Record<string, unknown>>("/design/retrieve-candidates", {
    session_id: sessionId,
    target_id: targetId,
  });
export const designEvaluateAdmetAPI = (sessionId: string, smilesList: string[]) =>
  post<Record<string, unknown>>("/design/evaluate-admet", {
    session_id: sessionId,
    smiles_list: smilesList,
  });
export const designSaveCandidateAPI = (sessionId: string, smiles: string, label?: string) =>
  post<Record<string, unknown>>("/design/save-candidate", {
    session_id: sessionId,
    smiles,
    label,
  });
export const designExportAPI = (sessionId: string, format: string = "json") =>
  post<Record<string, unknown>>("/design/export", {
    session_id: sessionId,
    format,
  });

// H-3/H-5: PPO molecule optimization
export const ppoOptimizeAPI = (
  targetId: string,
  seedSmiles?: string,
  constraints?: Record<string, unknown>,
  nSteps?: number,
) =>
  post<{ run_id: string; status: string }>("/design/optimize", {
    target_id: targetId,
    seed_smiles: seedSmiles,
    constraints: constraints ?? {},
    n_steps: nSteps ?? 50,
  });

// U-2.5: Diffusion-based molecule generation
export const designDiffusionGenerateAPI = (
  numAtoms?: number,
  pocketEmbed?: number[],
  targetId?: string,
  projectId?: string,
  numCandidates?: number,
) =>
  post<{
    run_id: string;
    candidates: Array<Record<string, unknown>>;
    total: number;
    model: string;
    status: string;
  }>("/design/generate-diffusion", {
    num_atoms: numAtoms ?? 32,
    pocket_embed: pocketEmbed ?? null,
    target_id: targetId ?? "",
    project_id: projectId ?? null,
    num_candidates: numCandidates ?? 5,
  });

// U-4.5: Send molecule context from Design Studio to a Research Lab
export const designSendToLabAPI = (
  labType: string,
  smiles?: string,
  targetId?: string,
  projectId?: string,
  bindingSite?: Record<string, unknown>,
  properties?: Record<string, unknown>,
  designSessionId?: string,
  notes?: string,
) =>
  post<{
    run_id: string;
    lab_type: string;
    status: string;
    stream_channel: string;
    message: string;
  }>("/design/send-to-lab", {
    lab_type: labType,
    smiles: smiles ?? "",
    target_id: targetId ?? "",
    project_id: projectId ?? "",
    binding_site: bindingSite ?? {},
    properties: properties ?? {},
    design_session_id: designSessionId ?? "",
    notes: notes ?? "",
  });

// ── Translation (§127) ──────────────────────────────────
export const translationTransformAPI = (sourceFormat: string, targetFormat: string, data: unknown) =>
  post<Record<string, unknown>>("/translation/transform", {
    source_format: sourceFormat,
    target_format: targetFormat,
    data,
  });
export const translationResultAPI = (resultId: string) =>
  get<Record<string, unknown>>(`/translation/result/${resultId}`);
export const translationSaveAPI = (resultId: string, label?: string) =>
  post<Record<string, unknown>>("/translation/save", { result_id: resultId, label });

// ── Translational Research (§127) ───────────────────────
export const translationalAnalyzeAPI = (targetSymbol: string, indicationId: string) =>
  post<Record<string, unknown>>("/translational/analyze", {
    target_symbol: targetSymbol,
    indication_id: indicationId,
  });
export const translationalRunResultAPI = (runId: string) =>
  get<Record<string, unknown>>(`/translational/run/${runId}`);
export const translationalExportAPI = (runId: string, format: string = "json") =>
  post<Record<string, unknown>>("/translational/export", { run_id: runId, format });

// ── Models (§128) ────────────────────────────────────────
export const modelsListAPI = () =>
  get<Record<string, unknown>[]>("/models");
export const modelsRecommendationsAPI = (task?: string) =>
  get<Record<string, unknown>>(`/models/recommendations${task ? `?task=${task}` : ""}`);
export const modelsSelectAPI = (modelId: string, backend?: string) =>
  post<Record<string, unknown>>("/models/select", { model_id: modelId, backend });
export const modelsLocalInstallAPI = (modelId: string, quantization?: string) =>
  post<Record<string, unknown>>("/models/local/install", {
    model_id: modelId,
    quantization,
  });

// ── Runtime (§128) ───────────────────────────────────────
export const runtimeStatusAPI = () =>
  get<Record<string, unknown>>("/runtime/status");
export const runtimeSelectModeAPI = (mode: string) =>
  post<Record<string, unknown>>("/runtime/select-mode", { mode });
export const runtimeDiagnosticsAPI = () =>
  get<Record<string, unknown>>("/settings/diagnostics");
export const runtimeFallbackPlanAPI = () =>
  get<Record<string, unknown>>("/runtime/fallback-plan");
export const runtimeLocalAgentStatusAPI = () =>
  get<Record<string, unknown>>("/runtime/local-agent/status");
export const runtimeLocalAgentPairAPI = (deviceName: string) =>
  post<Record<string, unknown>>("/runtime/local-agent/pair", { device_name: deviceName });
export const runtimeLocalAgentUnpairAPI = () =>
  post<Record<string, unknown>>("/runtime/local-agent/unpair", {});

// ── Dossier (§129) ──────────────────────────────────────
export const dossierCreateAPI = (projectId: string, title?: string) =>
  post<Record<string, unknown>>("/dossiers", { project_id: projectId, title });
export const dossierUpdateAPI = (dossierId: string, update: Record<string, unknown>) =>
  fetch(`${_apiBase}/dossiers/${dossierId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
    credentials: "include",
  }).then((r) => r.json());
export const dossierInsertEvidenceAPI = (dossierId: string, evidenceIds: string[]) =>
  post<Record<string, unknown>>(`/dossiers/${dossierId}/insert-evidence`, {
    evidence_ids: evidenceIds,
  });

// ── Cockpit Dashboard (§9.3, §133) ──────────────────────
export const cockpitSummaryAPI = () =>
  get<Record<string, unknown>>("/cockpit/summary");
export const cockpitOpenActionsAPI = () =>
  get<Record<string, unknown>>("/cockpit/open-actions");
export const cockpitRecentRunsAPI = (limit = 10) =>
  get<Record<string, unknown>>(`/cockpit/recent-runs?limit=${limit}`);
export const cockpitSourceHealthAPI = () =>
  get<Record<string, unknown>>("/cockpit/source-health");

// Cockpit agentic full-analysis
export interface CockpitAnalysisResult {
  query: string;
  run_id: string;
  timestamp: string;
  execution_mode?: "sync" | "background";
  latency_budget?: Record<string, unknown>;
  search_provenance?: Record<string, unknown>;
  summary: string;
  categories: Array<{
    category: string;
    count: number;
    columns: string[];
    rows: Array<Record<string, unknown>>;
    top_items: string[];
  }>;
  graph: { nodes: Array<Record<string, unknown>>; edges: Array<Record<string, unknown>> };
  stats: {
    total_results: number;
    categories_found: number;
    sources_queried: number;
    pubmed_count: number | null;
    clinical_trials_count: number | null;
    overall_confidence: number;
    contradictions_count: number;
  };
  source_breakdown: Record<string, number>;
  evidence: { top_citations: Array<Record<string, unknown>>; confidence: number };
  // §6: Detailed contradictions
  contradictions: Array<Record<string, unknown>>;
  // §7: Disease intelligence
  disease_intelligence: Array<Record<string, unknown>>;
  // §8: Target prioritization
  target_prioritization: Array<Record<string, unknown>>;
  // §9: Graph reasoning neighborhoods
  graph_reasoning: Array<Record<string, unknown>>;
  // §9: Pathways
  pathways: Array<Record<string, unknown>>;
  // §10: Structures
  structures: Array<Record<string, unknown>>;
  // §12: ADMET
  admet: Array<Record<string, unknown>>;
  // §13: Retrosynthesis
  retrosynthesis: Array<Record<string, unknown>>;
  // §14: Clinical trials
  clinical_trials: Array<Record<string, unknown>>;
  // §14: PICO extraction
  pico: Array<Record<string, unknown>>;
  // §14: Population genomics
  population_genomics: Record<string, Array<Record<string, unknown>>>;
  // §16: SynthArena scenario comparison
  syntharena: Record<string, unknown>;
  // §17: Literature table (all papers sorted by relevance)
  literature_table: Array<Record<string, unknown>>;
  // §18: Filtered literature (user-specified GWAS/mechanisms/etc.)
  filtered_literature: Array<Record<string, unknown>>;
  filter_info: Record<string, unknown>;
  // §19: Similarities (paper pairs with shared findings)
  similarities: Array<Record<string, unknown>>;
  // §20: Nuanced relationships (Refines, Fails to Replicate, etc.)
  nuanced_relationships: Array<Record<string, unknown>>;
  // §21: Terms map (genes, drugs, diseases, methods with frequencies)
  terms_map: Record<string, Array<Record<string, unknown>>>;
  term_frequency: Record<string, number>;
  // §22: Literature knowledge graph (category-colored nodes)
  literature_kg: Record<string, unknown>;
  // §23: MeSH/GO terminology mapping
  mesh_terminology: Record<string, unknown>;
  // Literature fetch stats
  literature_stats: Record<string, unknown>;
  // §25: Bidirectional traceability — sentence index per paper
  paper_sentences: Array<{
    paper_id: string;
    title: string;
    doi: string;
    year: number | null;
    sentences: Array<{
      idx: number;
      text: string;
      offset: number;
      length: number;
    }>;
  }>;
  // §25: Evidence links — claim → supporting sentences
  evidence_links: Record<string, Array<{
    paper_id: string;
    paper_title: string;
    doi: string;
    sentence: string;
    offset: number;
    score: number;
    year: number | null;
    source: string;
  }>>;
  // §26: Literature structures — SMILES / protein sequences from papers
  lit_structures: Array<{
    type: string;
    value: string;
    paper_id: string;
    paper_title: string;
    doi: string;
    context: string;
  }>;
  // §27: LLM-verified contradictions (Gemma 4 — experimental context)
  llm_contradictions: Array<{
    claim_a: string;
    claim_b: string;
    source_a: { title: string; id: string; doi: string; year: number | null; url: string };
    source_b: { title: string; id: string; doi: string; year: number | null; url: string };
    reason: string;
    reliability_judgment?: string;
    severity: string;
    context_a: { study_type: string; model_organisms: string[]; cell_lines: string[]; methodologies: string[] };
    context_b: { study_type: string; model_organisms: string[]; cell_lines: string[]; methodologies: string[] };
    llm_verified: boolean;
    explanation: string;
  }>;
  // §28: Traceable summary w/ [Ref N] citations
  traceable_summary: {
    summary_text: string;
    references: Array<{
      ref_num: number;
      paper_id: string;
      title: string;
      doi: string;
      year: number | null;
      key_finding: string;
      authors: string[];
      methodology: string | Record<string, unknown>;
    }>;
    supporting_findings: Array<{
      ref_num: number;
      title: string;
      doi: string;
      year: number | null;
      finding: string;
      methodology: string | Record<string, unknown>;
      contradiction_note?: string;
      should_influence: string[];
      should_not_influence: string[];
    }>;
    dissenting_findings: Array<{
      ref_num: number;
      title: string;
      doi: string;
      year: number | null;
      finding: string;
      methodology: string | Record<string, unknown>;
      contradiction_note?: string;
      should_influence: string[];
      should_not_influence: string[];
    }>;
  };
  // §29: Unified Pathways Diagram (genes→drugs→diseases→methods)
  unified_pathways: {
    nodes: Array<{
      id: string;
      label: string;
      type: string;
      color: string;
      layer: number;
      frequency: number;
      size: number;
    }>;
    edges: Array<{
      source: string;
      target: string;
      type: string;
      weight: number;
      papers: string[];
      label: string;
    }>;
    pathway_layers: Array<{
      layer: number;
      label: string;
      color: string;
      node_count: number;
    }>;
    total_nodes: number;
    total_edges: number;
  };
  // §30: Mechanism Clusters (papers grouped by biological mechanism)
  mechanism_clusters: {
    clusters: Array<{
      name: string;
      papers: Array<{
        title: string;
        id: string;
        doi: string;
        year: number | null;
        relevance_score: number;
      }>;
      count: number;
    }>;
    unclustered: Array<{
      title: string;
      id: string;
      doi: string;
      year: number | null;
    }>;
    total_clustered: number;
  };
  // Query classification metadata
  query_classification: {
    query_type: string;
    disease: string | null;
    genes: string[];
    pathways: string[];
    cohort: string | null;
    chemistry_type: string | null;
    comparison_targets: string[];
    runtime_mode: string | null;
    emphasis: string[];
    search_terms: string[];
  };
  // §4: Entity normalization summary
  entities_extracted: {
    genes: string[];
    proteins: string[];
    diseases: string[];
    drugs: string[];
    structures: string[];
  };
  latency_ms: number;
  errors: string[];
  timings: Record<string, unknown>;
  degraded_sources?: string[];
}

export const cockpitAnalyzeAPI = (query: string, limit = 100) =>
  post<CockpitAnalysisResult>("/cockpit/analyze", { query, limit });

export interface CockpitQueuedRun {
  run_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  stream_channel: string;
  poll_after_ms: number;
  latency_budget: Record<string, unknown>;
}

export interface CockpitRunStatus {
  run_id: string;
  query: string;
  status: string;
  created_at: string;
  updated_at: string;
  result_summary: CockpitAnalysisResult | null;
  error_message: string | null;
  provenance: Record<string, unknown>;
  stream_channel: string;
  poll_after_ms: number;
  is_complete: boolean;
  latency_budget: Record<string, unknown>;
}

export const cockpitStartAnalysisAPI = (query: string, limit = 100) =>
  post<CockpitQueuedRun>("/cockpit/analyze", { query, limit, execution_mode: "background" });

export const cockpitRunStatusAPI = (runId: string) =>
  get<CockpitRunStatus>(`/cockpit/runs/${encodeURIComponent(runId)}`);

export const cockpitEntityDetailAPI = (entityId: string) =>
  get<Record<string, unknown>>(`/cockpit/entity/${encodeURIComponent(entityId)}`);

// ── Agentic Auto-Pilot / DAG Planner (§50, §58) ─────────
export interface DAGPlanResult {
  dag_id: string;
  run_id?: string;
  execution_status?: string;
  nodes: Array<{
    node_id: string;
    module: string;
    action: string;
    params: Record<string, unknown>;
    depends_on: string[];
  }>;
  execution_order: string[];
  estimated_duration_seconds?: number;
  clarification_needed?: string;
  error?: string;
}

export const dagExecuteAPI = (prompt: string, projectId?: string, autoExecute = true) =>
  post<DAGPlanResult>("/dag", {
    prompt,
    project_id: projectId ?? "",
    auto_execute: autoExecute,
  });

export const dagStatusAPI = (runId: string) =>
  get<Record<string, unknown>>(`/dag/${runId}`);

// ── Reports (§129) ──────────────────────────────────────
export const reportsListAPI = (projectId?: string) =>
  get<Record<string, unknown>[]>(`/reports${projectId ? `?project_id=${projectId}` : ""}`);
export const reportCreateAPI = (req: ReportRequest) =>
  post<Record<string, unknown>>("/reports", req);
export const reportExportByIdAPI = (reportId: string, format: string = "pdf") =>
  post<Record<string, unknown>>(`/reports/${reportId}/export`, { format });

// ── Logs (§129) ──────────────────────────────────────────
export const logsListAPI = (projectId?: string) =>
  get<Record<string, unknown>[]>(`/logs${projectId ? `?project_id=${projectId}` : ""}`);
export const logsByRunAPI = (runId: string) =>
  get<Record<string, unknown>[]>(`/logs/by-run/${runId}`);
export const logsExportAPI = (format: string = "json", runId?: string) =>
  post<Record<string, unknown>>("/logs/export", { format, run_id: runId });

// ── Media (§129) ─────────────────────────────────────────
export const mediaListAPI = (projectId?: string) =>
  get<Record<string, unknown>[]>(`/media${projectId ? `?project_id=${projectId}` : ""}`);
export const mediaGetAPI = (artifactId: string) =>
  get<Record<string, unknown>>(`/media/${artifactId}`);
export const mediaExportAPI = (artifactIds: string[], format: string = "zip") =>
  post<Record<string, unknown>>("/media/export", { artifact_ids: artifactIds, format });

// ── SynthArena (§130) ────────────────────────────────────
export const synthArenaCreateSessionAPI = (projectId?: string) =>
  post<Record<string, unknown>>("/syntharena/sessions", { project_id: projectId });
export const synthArenaListSessionsAPI = () =>
  get<Record<string, unknown>[]>("/syntharena/sessions");
export const synthArenaGetSessionAPI = (sessionId: string) =>
  get<Record<string, unknown>>(`/syntharena/sessions/${sessionId}`);
export const synthArenaAddScenarioAPI = (sessionId: string, scenario: Record<string, unknown>) =>
  post<Record<string, unknown>>(`/syntharena/sessions/${sessionId}/add-scenario`, scenario);
export const synthArenaExportSessionAPI = (sessionId: string, format: string = "json") =>
  post<Record<string, unknown>>(`/syntharena/sessions/${sessionId}/export`, { format });

// ── Labs (§131) ──────────────────────────────────────────
export const labsPocketRunAPI = (targetId: string, params?: Record<string, unknown>) =>
  post<Record<string, unknown>>("/labs/pocket/run", { target_id: targetId, ...params });
export const labsMoleculeGenerationRunAPI = (targetId: string, params?: Record<string, unknown>) =>
  post<Record<string, unknown>>("/labs/molecule-generation/run", { target_id: targetId, ...params });
export const labsAdmetRunAPI = (smilesList: string[]) =>
  post<Record<string, unknown>>("/labs/admet/run", { smiles_list: smilesList });
export const labsRetrosynthesisRunAPI = (smiles: string) =>
  post<Record<string, unknown>>("/labs/retrosynthesis/run", { smiles });
export const labsVaccineRunAPI = (proteinSequence: string, params?: Record<string, unknown>) =>
  post<Record<string, unknown>>("/labs/vaccine/run", { protein_sequence: proteinSequence, ...params });
export const labsMetabolicEngineeringRunAPI = (organismId: string, targetCompound: string) =>
  post<Record<string, unknown>>("/labs/metabolic-engineering/run", {
    organism: organismId,
    target_metabolite: targetCompound,
  });
export const labsPharmacogenomicsRunAPI = (geneSymbol: string, drugId: string) =>
  post<Record<string, unknown>>("/labs/pharmacogenomics/run", {
    gene_symbols: [geneSymbol],
    population: drugId || "global",
  });

// ── ESM-3 Large Protein Design (§24.2, Forge API) ───────
export const esm3ScaffoldAPI = (params: {
  partial_sequence?: string;
  target_description?: string;
  motif_sequences?: string[];
  num_steps?: number;
  temperature?: number;
  project_id?: string;
  run_id?: string;
}) => post<Record<string, unknown>>("/esm3/scaffold", params);

export const esm3EmbedAPI = (sequence: string, proteinId?: string) =>
  post<Record<string, unknown>>("/esm3/embed", { sequence, protein_id: proteinId });

export const esm3FoldAPI = (sequence: string, proteinId?: string) =>
  post<Record<string, unknown>>("/esm3/fold", { sequence, protein_id: proteinId });

export const esm3HealthAPI = () =>
  get<Record<string, unknown>>("/esm3/health");

// ── Projects (§119) ─────────────────────────────────────
export const projectsListAPI = () =>
  get<Record<string, unknown>[]>("/projects");
export const projectCreateAPI = (name: string, description?: string) =>
  post<Record<string, unknown>>("/projects", { name, description });
export const projectGetAPI = (projectId: string) =>
  get<Record<string, unknown>>(`/projects/${projectId}`);
export const projectMemoryAPI = (projectId: string) =>
  get<Record<string, unknown>>(`/projects/${projectId}/memory`);
