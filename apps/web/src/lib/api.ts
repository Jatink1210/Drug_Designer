// ── API Base URL resolution ────────────────────────────
// In Tauri desktop mode the backend runs on a dynamic port discovered at
// startup.  In browser/dev mode the Vite proxy forwards /api → localhost:8000.

let _apiBase = "/api";
let _resolvePromise: Promise<string> | null = null;

export async function ensureApiBase(): Promise<string> {
    if (_resolvePromise) return _resolvePromise;

    _resolvePromise = (async () => {
        // Tauri v2 injects window.__TAURI__ when app.withGlobalTauri is true.
        // We call the raw IPC directly to avoid importing @tauri-apps/api (which
        // is not available in browser builds).
        if (typeof window !== "undefined" && (window as any).__TAURI__?.core?.invoke) {
            try {
                const port: number = await (window as any).__TAURI__.core.invoke("get_api_port");
                _apiBase = `http://localhost:${port}/api`;
            } catch { /* fallback to /api */ }
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
}

export interface CategoryResult {
    columns: string[];
    rows: Record<string, unknown>[];
    total: number;
}

export interface GraphNode { id: string; label: string; type: string }
export interface GraphEdge { source: string; target: string; label: string; weight: number }

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
}

export interface SearchResponse {
    query: string;
    intent: { intent: string; search_term: string; method: string };
    summary_stats: {
        total_results: number; categories_found: number;
        pubmed_count: number | null; clinical_trials_count: number | null; sources_queried: number;
    };
    categories: Record<string, CategoryResult>;
    preview_graph: { nodes: GraphNode[]; edges: GraphEdge[] };
    provenance: { sources_hit: string[]; timestamps: Record<string, number> };
    timings: Record<string, number>;
    errors: string[];
    evidence_summary?: EvidenceSummaryDTO;
}

export interface HealthResponse { status: string; service: string; version: string; check_ms?: number; issues?: string[] | null; ollama_ok?: boolean; connectors_active?: number; connectors_total?: number; connectors_degraded?: number }
export interface DiagnosticsResponse {
    status: string; version: string;
    components: Record<string, { status: string;[k: string]: unknown }>;
    connectors: Record<string, { status: string; latency_ms?: number; error?: string }>;
}

/* ─── Structure Types ─────────────────────────────────── */

export interface StructureSummary {
    pdb_id: string; title: string; classification: string;
    organism: string; expression_system: string;
    method: string; resolution: number | null; r_work: number | null; r_free: number | null;
    space_group: string; cell_dimensions: Record<string, number | null>;
    deposition_date: string; release_date: string; revision_date: string;
    primary_citation: { title: string; journal: string; year: number | null; doi: string; pmid: string };
    macromolecules: Array<{ entity_id: string; type: string; chains: string[]; length: number | null; sequence: string; organism: string; uniprot_ids: string[]; gene_names: string[]; description: string }>;
    ligands: Array<{ comp_id: string; name: string; formula: number | null; type: string }>;
    assemblies: Array<{ assembly_id: string; polymer_entity_count: number | null; oligomeric_state: string; kind: string }>;
    revision_count: number;
    revision_history: Array<{ version: number | null; date: string; type: string }>;
    downloads: Record<string, string>;
    url: string;
}

export interface StructureAnnotations { pfam: Array<{ id: string; name: string }>; interpro: Array<{ id: string; name: string }>; go: Array<{ id: string; name: string }>; ec: Array<{ id: string; name: string }>; ptms: unknown[] }
export interface ExperimentData { method: string; crystal_growth: Record<string, unknown>; data_collection: Record<string, unknown>; refinement: Record<string, unknown>; cell: Record<string, unknown>; software: Array<{ name: string; version: string; classification: string }> }
export interface SequenceData { entity_id: string; chains: string[]; length: number | null; sequence: string; type: string; features: Array<{ type: string; name: string; start: number | null; end: number | null }> }

/* ─── Docking Types ───────────────────────────────────── */

export interface DockingRequest {
    receptor_path: string; ligand_path: string; center: number[];
    box_size?: number[]; engine?: string; exhaustiveness?: number; num_modes?: number;
}
export interface DockingPose { rank: number; affinity_kcal: number; rmsd_lb: number | null; rmsd_ub: number | null }
export interface DockingResult { run_id: string; status: string; engine: string; elapsed_seconds: number; poses: DockingPose[]; error?: string }

/* ─── Molecule Types ──────────────────────────────────── */

export interface PhysiochemProps { smiles: string; mw?: number; logp?: number; hbd: number; hba: number; tpsa?: number; rotatable_bonds: number; lipinski_violations: number; druglikeness: string }
export interface ADMETResult { smiles: string; absorption: Record<string, unknown>; distribution: Record<string, unknown>; metabolism: Record<string, unknown>; excretion: Record<string, unknown>; toxicity: Record<string, unknown>; synthetic_accessibility: Record<string, unknown> }

/* ─── Evidence Types ──────────────────────────────────── */

export interface EvidenceSearchRequest { query: string; sources?: string[]; limit?: number; year_from?: number; year_to?: number }
export interface EvidenceResult { query: string; total: number; results: Record<string, Record<string, unknown>[]> }

/* ─── Report Types ────────────────────────────────────── */

export interface ReportRequest { title?: string; query?: string; sections?: string[]; search_data?: Record<string, unknown>; structure_data?: Record<string, unknown>; docking_data?: Record<string, unknown>; notes?: string }
export interface ReportResult { report_id: string; status: string; sections: string[]; html_path: string; json_path: string }

/* ─── Data Manager Types ──────────────────────────────── */

export interface ConnectorInfo { id: string; name: string; required: boolean; enabled: boolean }

/* ─── API Functions ───────────────────────────────────── */

async function post<T>(path: string, body: unknown): Promise<T> {
    const base = await ensureApiBase();
    const resp = await fetch(`${base}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!resp.ok) throw new Error(`${path} failed: ${resp.status}`);
    return resp.json();
}
async function get<T>(path: string): Promise<T> {
    const base = await ensureApiBase();
    const resp = await fetch(`${base}${path}`);
    if (!resp.ok) throw new Error(`${path} failed: ${resp.status}`);
    return resp.json();
}
async function httpDelete(path: string): Promise<void> {
    const base = await ensureApiBase();
    const resp = await fetch(`${base}${path}`, { method: "DELETE" });
    if (!resp.ok) throw new Error(`${path} failed: ${resp.status}`);
}

// Search
export const searchAPI = (req: SearchRequest) => post<SearchResponse>("/search", req);

// Health
export const healthAPI = () => get<HealthResponse>("/health");
export const diagnosticsAPI = () => get<DiagnosticsResponse>("/diagnostics");

// Structure
export const structureSearchAPI = (q: string) => get<Record<string, unknown>>(`/structure/search?q=${encodeURIComponent(q)}`);
export const structureSummaryAPI = (pdbId: string) => get<StructureSummary>(`/structure/${pdbId}`);
export const structureAnnotationsAPI = (pdbId: string) => get<StructureAnnotations>(`/structure/${pdbId}/annotations`);
export const structureExperimentAPI = (pdbId: string) => get<ExperimentData>(`/structure/${pdbId}/experiment`);
export const structureSequenceAPI = (pdbId: string) => get<SequenceData[]>(`/structure/${pdbId}/sequence`);
export const alphafoldAPI = (uniprotId: string) => get<Record<string, unknown>>(`/structure/alphafold/${uniprotId}`);

// Docking
export const dockingRunAPI = (req: DockingRequest) => post<DockingResult>("/docking/run", req);
export const dockingPocketsAPI = (receptor_path: string) => post<Record<string, unknown>>("/docking/pockets", { receptor_path });
export const dockingRunsAPI = () => get<Record<string, unknown>[]>("/docking/runs");

// Molecules
export const moleculeScoreAPI = (smiles: string[]) => post<PhysiochemProps[]>("/molecules/score", { smiles });
export const moleculeADMETAPI = (smiles: string[]) => post<ADMETResult[]>("/molecules/admet", { smiles });
export const moleculeAnalogsAPI = (smiles: string, method?: string) => post<Record<string, unknown>>("/molecules/analogs", { smiles, method: method || "similarity" });
export const moleculeNoveltyAPI = (smiles: string) => post<Record<string, unknown>>("/molecules/novelty", { smiles });
export const designIterationsAPI = () => get<Record<string, unknown>[]>("/molecules/iterations");

// Evidence
export const evidenceSearchAPI = (req: EvidenceSearchRequest) => post<EvidenceResult>("/evidence/search", req);
export const evidenceExportAPI = (query: string, format: string) => get<Record<string, unknown>>(`/evidence/export?query=${encodeURIComponent(query)}&format=${format}`);

// Reports
export const reportGenerateAPI = (req: ReportRequest) => post<ReportResult>("/reports/generate", req);
export const reportListAPI = () => get<Record<string, unknown>[]>("/reports/list");

// Data Manager
export const dataKeysAPI = () => get<Record<string, unknown>>("/data/keys");
export const dataSetKeyAPI = (service: string, key: string) => post<Record<string, string>>("/data/keys", { service, key });
export const dataDeleteKeyAPI = (service: string) => httpDelete(`/data/keys/${service}`);
export const dataConnectorsAPI = () => get<ConnectorInfo[]>("/data/connectors");
export const dataToggleConnectorAPI = (connector_id: string, enabled: boolean) => post<Record<string, string>>("/data/connectors/toggle", { connector_id, enabled });
export const dataCacheAPI = () => get<Record<string, unknown>>("/data/cache");
export const dataClearCacheAPI = () => httpDelete("/data/cache");
export const dataStorageAPI = () => get<Record<string, unknown>>("/data/storage");

// Pathways
export const pathwaysSearchAPI = (query: string, source: string = "reactome", limit: number = 20) =>
    post<Array<{ id: string; canonical_name: string; description: string; species: string; url: string; pathway_id: string }>>("/pathways/search", { query, source, limit });
export const pathwaysDetailAPI = (id: string) =>
    get<{ id: string; canonical_name: string; genes: string[]; gene_count: number; url: string }>(`/pathways/${encodeURIComponent(id)}`);

// Graph / KG
export interface GraphStats { nodes: Record<string, number>; edges: Record<string, number>; total_nodes: number; total_edges: number }
export interface GraphSample { nodes: Array<{ id: string; label: string; properties: Record<string, unknown> }>; edges: Array<{ source: string; target: string; type: string; properties: Record<string, unknown> }> }
export const graphStatsAPI = () => get<GraphStats>("/graph/stats");
export const graphSampleAPI = (limit: number = 50) => get<GraphSample>(`/graph/sample?limit=${limit}`);
export const graphNeighborhoodAPI = (entityId: string, depth: number = 1) =>
    post<Record<string, unknown>>("/graph/neighborhood", { entity_id: entityId, depth });

// Catalog
export interface CatalogStats { collections: Record<string, number>; total: number }
export interface CatalogSearchResult { items: Array<Record<string, unknown>>; total: number }
export const catalogStatsAPI = () => get<CatalogStats>("/catalog/stats");
export const catalogSearchAPI = (entityType: string, limit: number = 50) =>
    post<CatalogSearchResult>("/catalog/search", { entity_type: entityType, limit });

// Runtimes
export interface HardwareCapabilities {
    cpu_cores: number; ram_gb: number; gpu: string;
    gpu_name: string | null; vram_gb: number; airllm_installed: boolean;
}
export interface RuntimeInfo { id: string; name: string; status: string; capabilities: string[] }
export interface RuntimesResponse { capabilities: HardwareCapabilities; available: RuntimeInfo[]; active: string; compute_mode: string }
export interface ModelCatalogEntry {
    name: string; ollama_id: string; hf_repo_or_url: string; size_gb: number; parameters: string;
    min_ram_gb: number; min_vram_gb: number; compute_modes: string[];
    quantization_levels: string[]; default_quantization: string; context_window: number;
    runtimes_supported: string[]; tags: string[]; description: string;
}
export interface RecommendResponse {
    compute_mode: string; recommended_model: ModelCatalogEntry | null;
    compatible_models: ModelCatalogEntry[]; hardware: HardwareCapabilities;
}
export interface InstalledModel { name: string; size: number; modified_at: string }

export const runtimesListAPI = () => get<RuntimesResponse>("/runtimes");
export const runtimesSelectAPI = (runtime_id: string, model_name?: string, endpoint?: string, compute_mode?: string) =>
    post<Record<string, string>>("/runtimes/select", { runtime_id, model_name, endpoint, compute_mode });
export const runtimesHealthAPI = () => get<Record<string, unknown>>("/runtimes/health");
export const runtimesRecommendAPI = () => get<RecommendResponse>("/runtimes/recommend");

// Models
export const modelsCatalogAPI = () => get<ModelCatalogEntry[]>("/models/catalog");
export const modelsInstalledAPI = () => get<InstalledModel[]>("/models/installed");
export const modelsPullAPI = (model_id: string) => post<Record<string, string>>("/models/pull", { model_id });
export const modelsDeleteAPI = (model_id: string) => httpDelete(`/models/${model_id}`);
export const modelsCompatibilityAPI = (model_name: string) => get<Record<string, unknown>>(`/models/compatibility/${encodeURIComponent(model_name)}`);

// Settings
export const settingsGetAPI = () => get<Record<string, unknown>>("/settings");
export const settingsUpdateAPI = (s: Record<string, unknown>) => post<Record<string, unknown>>("/settings", s);

