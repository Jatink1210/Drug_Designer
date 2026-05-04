export type CanonicalNavSectionKey = "discovery" | "analysis" | "workflows" | "system";

export type CanonicalModuleKey =
  | "cockpit"
  | "evidence-search"
  | "entity-intelligence"
  | "knowledge-graph"
  | "pathways"
  | "structure"
  | "design"
  | "clinical-design"
  | "syntharena"
  | "research-labs"
  | "contradiction-similarity"
  | "pico-verification"
  | "settings";

export type LegacyRouteAction = "keep" | "adapt" | "merge" | "hide" | "delete";

export type CockpitEntityType =
  | "protein"
  | "gene"
  | "drug"
  | "disease"
  | "molecule"
  | "pathway"
  | "variant"
  | "publication"
  | "clinical_trial"
  | "target"
  | "compound"
  | "unknown";

export type CockpitHandoffAction =
  | "run_cockpit_search"
  | "open_in_structure"
  | "open_in_design"
  | "open_in_labs"
  | "open_in_clinical"
  | "open_in_contradiction_similarity"
  | "open_in_pico_verification"
  | "append_to_dossier"
  | "run_entity_intelligence"
  | "open_in_graph"
  | "open_in_pathways"
  | "compare_entities";

export interface CanonicalModuleRoute {
  key: CanonicalModuleKey;
  label: string;
  path: string;
  section: CanonicalNavSectionKey;
  backendEndpoints: string[];
  legacyPaths?: string[];
}

export interface LegacyRouteDecision {
  legacyPath: string;
  action: LegacyRouteAction;
  canonicalPath?: string;
  note: string;
}

export interface SharedEntitySchema {
  entityId: string;
  entityType: CockpitEntityType;
  entityName: string;
  sourceCategory?: string;
  identifiers?: Record<string, string>;
  attributes?: Record<string, unknown>;
}

export interface SharedProvenancePayload {
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

export interface SharedHandoffPayload {
  version: "phase0.v1";
  sourceModule: CanonicalModuleKey;
  action: CockpitHandoffAction;
  targetRoute: string;
  query: string;
  createdAt: string;
  runId?: string;
  traceId?: string;
  entities: SharedEntitySchema[];
  provenance: SharedProvenancePayload[];
  metadata?: Record<string, unknown>;
}

export interface SlashCommandDefinition {
  command: string;
  module: CanonicalModuleKey;
  label: string;
  description: string;
  route: string;
}

export interface EndpointDriftMatrixEntry {
  module: CanonicalModuleKey;
  frontendClients: string[];
  backendRouters: string[];
  livePages: string[];
  driftStatus: "aligned" | "adapt" | "merge" | "investigate";
  notes: string;
}

export const CANONICAL_NAV_SECTIONS: Array<{ key: CanonicalNavSectionKey; title: string }> = [
  { key: "discovery", title: "Discovery" },
  { key: "analysis", title: "Analysis" },
  { key: "workflows", title: "Workflows" },
  { key: "system", title: "System" },
];

export const CANONICAL_MODULE_ROUTES: CanonicalModuleRoute[] = [
  {
    key: "cockpit",
    label: "Cockpit",
    path: "/workspace",
    section: "discovery",
    backendEndpoints: ["POST /api/v1/cockpit/analyze", "GET /api/v1/cockpit/summary"],
    legacyPaths: ["/home", "/cockpit"],
  },
  {
    key: "evidence-search",
    label: "Evidence Search",
    path: "/evidence/search",
    section: "discovery",
    backendEndpoints: ["POST /api/v1/evidence/search", "GET /api/v1/evidence/export"],
    legacyPaths: ["/evidence", "/search"],
  },
  {
    key: "entity-intelligence",
    label: "Entity Intelligence",
    path: "/entity-intelligence",
    section: "discovery",
    backendEndpoints: [
      "POST /api/v1/search/entity-detail",
      "POST /api/v1/disease/start",
      "POST /api/v1/targets/prioritize",
    ],
    legacyPaths: ["/disease", "/targets", "/gene-explorer", "/ppi"],
  },
  {
    key: "knowledge-graph",
    label: "Knowledge Graph",
    path: "/graph",
    section: "analysis",
    backendEndpoints: ["POST /api/v1/graph/build", "POST /api/v1/graph/neighborhood"],
    legacyPaths: ["/kg", "/interaction-maps"],
  },
  {
    key: "pathways",
    label: "Pathways",
    path: "/pathways",
    section: "analysis",
    backendEndpoints: ["POST /api/v1/pathways/search", "GET /api/v1/pathways/:id"],
  },
  {
    key: "structure",
    label: "3D Structure",
    path: "/structure",
    section: "analysis",
    backendEndpoints: ["GET /api/v1/structure/search", "GET /api/v1/structure/:id"],
  },
  {
    key: "design",
    label: "Design Studio",
    path: "/design",
    section: "analysis",
    backendEndpoints: ["POST /api/v1/design/session/start", "POST /api/v1/design/retrieve-candidates"],
  },
  {
    key: "clinical-design",
    label: "Clinical Design",
    path: "/clinical-design",
    section: "workflows",
    backendEndpoints: ["POST /api/v1/translational/analyze", "GET /api/v1/translational/run/:runId"],
    legacyPaths: ["/translational", "/translation"],
  },
  {
    key: "syntharena",
    label: "SynthArena",
    path: "/syntharena",
    section: "workflows",
    backendEndpoints: ["POST /api/v1/syntharena/sessions", "POST /api/v1/syntharena/sessions/:id/export"],
    legacyPaths: ["/scenario-arena"],
  },
  {
    key: "research-labs",
    label: "Research Labs",
    path: "/labs",
    section: "workflows",
    backendEndpoints: [
      "POST /api/v1/labs/pocket/run",
      "POST /api/v1/labs/molecule-generation/run",
      "POST /api/v1/labs/admet/run",
      "POST /api/v1/labs/retrosynthesis/run",
    ],
  },
  {
    key: "contradiction-similarity",
    label: "Contradiction & Similarity",
    path: "/contradiction-similarity",
    section: "workflows",
    backendEndpoints: ["POST /api/v1/cockpit/analyze", "POST /api/v1/search/cross-modal"],
    legacyPaths: ["/contradictions", "/evidence/contradictions"],
  },
  {
    key: "pico-verification",
    label: "PICO Verification",
    path: "/pico",
    section: "workflows",
    backendEndpoints: ["POST /api/v1/cockpit/analyze"],
    legacyPaths: ["/pico-verification"],
  },
  {
    key: "settings",
    label: "Settings",
    path: "/settings",
    section: "system",
    backendEndpoints: ["GET /api/v1/settings", "POST /api/v1/runtime/select-mode", "GET /api/v1/runtime/diagnostics"],
  },
];

export const LEGACY_ROUTE_DECISIONS: LegacyRouteDecision[] = [
  { legacyPath: "/home", action: "adapt", canonicalPath: "/workspace", note: "Legacy cockpit alias redirects to canonical cockpit." },
  { legacyPath: "/cockpit", action: "adapt", canonicalPath: "/workspace", note: "Legacy cockpit alias redirects to canonical cockpit." },
  { legacyPath: "/evidence", action: "adapt", canonicalPath: "/evidence/search", note: "Evidence search uses canonical discovery route." },
  { legacyPath: "/disease", action: "merge", canonicalPath: "/entity-intelligence", note: "Disease workflow becomes one mode inside Entity Intelligence." },
  { legacyPath: "/targets", action: "merge", canonicalPath: "/entity-intelligence", note: "Target ranking becomes one mode inside Entity Intelligence." },
  { legacyPath: "/gene-explorer", action: "merge", canonicalPath: "/entity-intelligence", note: "Gene/protein exploration merges into Entity Intelligence." },
  { legacyPath: "/ppi", action: "merge", canonicalPath: "/entity-intelligence", note: "Standalone PPI route exits primary nav and maps to merged entity workflow." },
  { legacyPath: "/kg", action: "adapt", canonicalPath: "/graph", note: "Short alias retained but canonical graph path is /graph." },
  { legacyPath: "/interaction-maps", action: "merge", canonicalPath: "/graph", note: "Interaction maps merge into Knowledge Graph." },
  { legacyPath: "/translational", action: "adapt", canonicalPath: "/clinical-design", note: "Clinical design becomes canonical workflow label/route." },
  { legacyPath: "/translation", action: "adapt", canonicalPath: "/clinical-design", note: "Legacy translation route redirects to clinical design." },
  { legacyPath: "/scenario-arena", action: "adapt", canonicalPath: "/syntharena", note: "Scenario arena is canonical SynthArena." },
  { legacyPath: "/contradictions", action: "adapt", canonicalPath: "/contradiction-similarity", note: "Contradiction analysis becomes contradiction + similarity workflow." },
  { legacyPath: "/evidence/contradictions", action: "adapt", canonicalPath: "/contradiction-similarity", note: "Evidence contradiction shortcut redirects to canonical workflow." },
  { legacyPath: "/reports", action: "hide", note: "Reports stay contextual, not primary nav." },
  { legacyPath: "/exports", action: "hide", note: "Export center stays contextual, not primary nav." },
  { legacyPath: "/export", action: "hide", note: "Export center stays contextual, not primary nav." },
  { legacyPath: "/notes", action: "hide", note: "Notes remain internal/contextual, not primary nav." },
  { legacyPath: "/memory", action: "hide", note: "Memory remains internal/contextual, not primary nav." },
  { legacyPath: "/operations", action: "hide", note: "Operations leaves primary nav." },
];

export const SLASH_COMMANDS: SlashCommandDefinition[] = [
  { command: "/disease", module: "entity-intelligence", label: "Disease", description: "Open Entity Intelligence with a disease-focused query.", route: "/entity-intelligence" },
  { command: "/drug", module: "cockpit", label: "Drug", description: "Run a cockpit analysis focused on a drug or therapy.", route: "/workspace" },
  { command: "/molecule", module: "design", label: "Molecule", description: "Open Design Studio with a molecule or SMILES query.", route: "/design" },
  { command: "/gene", module: "entity-intelligence", label: "Gene", description: "Open Entity Intelligence with a gene-focused query.", route: "/entity-intelligence" },
  { command: "/protein", module: "structure", label: "Protein", description: "Open 3D Structure with a protein-focused query.", route: "/structure" },
  { command: "/blank", module: "cockpit", label: "Blank", description: "Start a blank cockpit research session.", route: "/workspace" },
  { command: "/targets", module: "entity-intelligence", label: "Targets", description: "Open Entity Intelligence in target ranking mode.", route: "/entity-intelligence" },
  { command: "/kg", module: "knowledge-graph", label: "Knowledge Graph", description: "Open Knowledge Graph with the current query.", route: "/graph" },
  { command: "/pathways", module: "pathways", label: "Pathways", description: "Open Pathways with the current query.", route: "/pathways" },
  { command: "/structure", module: "structure", label: "3D Structure", description: "Open the structure workbench with the current query.", route: "/structure" },
  { command: "/design", module: "design", label: "Design", description: "Open Design Studio with the current query.", route: "/design" },
  { command: "/clinical", module: "clinical-design", label: "Clinical", description: "Open Clinical Design with the current query.", route: "/clinical-design" },
  { command: "/labs", module: "research-labs", label: "Labs", description: "Open Research Labs with the current query.", route: "/labs" },
  { command: "/compare", module: "cockpit", label: "Compare", description: "Compare selected entities from the cockpit.", route: "/workspace" },
  { command: "/contradictions", module: "contradiction-similarity", label: "Contradictions", description: "Open Contradiction & Similarity for the current topic.", route: "/contradiction-similarity" },
  { command: "/pico", module: "pico-verification", label: "PICO", description: "Open PICO Verification with the current topic.", route: "/pico" },
];

export const CANONICAL_ENDPOINT_DRIFT_MATRIX: EndpointDriftMatrixEntry[] = [
  {
    module: "cockpit",
    frontendClients: ["cockpitAnalyzeAPI"],
    backendRouters: ["POST /api/v1/cockpit/analyze"],
    livePages: ["WorkspacePage"],
    driftStatus: "aligned",
    notes: "Canonical cockpit entrypoint and report contract are now the primary search surface.",
  },
  {
    module: "evidence-search",
    frontendClients: ["searchAPI", "evidence APIs"],
    backendRouters: ["POST /api/v1/evidence/search", "GET /api/v1/evidence/export"],
    livePages: ["SearchPage", "EvidencePage"],
    driftStatus: "adapt",
    notes: "Evidence search remains live but canonical nav points to a merged evidence/search route.",
  },
  {
    module: "entity-intelligence",
    frontendClients: ["entityDetailAPI", "targetCompareAPI", "disease APIs"],
    backendRouters: ["POST /api/v1/search/entity-detail", "POST /api/v1/disease/analyze", "POST /api/v1/targets/prioritize"],
    livePages: ["DiseaseWorkbench"],
    driftStatus: "merge",
    notes: "Legacy disease, target, and gene flows are merged into Entity Intelligence.",
  },
  {
    module: "knowledge-graph",
    frontendClients: ["graphBuildAPI", "graphNeighborhoodAPI", "graphStatsAPI"],
    backendRouters: ["POST /api/v1/graph/build", "POST /api/v1/graph/neighborhood", "GET /api/v1/graph/stats"],
    livePages: ["KGPage"],
    driftStatus: "aligned",
    notes: "Cockpit now hands run context into the dedicated graph explorer.",
  },
  {
    module: "pathways",
    frontendClients: ["pathwaysSearchAPI", "pathwaysDetailAPI", "pathwaysEnrichmentAPI"],
    backendRouters: ["POST /api/v1/pathways/search", "GET /api/v1/pathways/:id", "POST /api/v1/pathways/enrichment"],
    livePages: ["PathwaysPage"],
    driftStatus: "aligned",
    notes: "Unified pathway handoff preloads query context and pathway identifiers.",
  },
  {
    module: "structure",
    frontendClients: ["structureSummaryAPI", "structureSearchAPI", "structureByTargetAPI"],
    backendRouters: ["GET /api/v1/structure/search", "GET /api/v1/structure/:id", "GET /api/v1/structure/by-target"],
    livePages: ["StructurePage"],
    driftStatus: "aligned",
    notes: "Cockpit handoff now seeds PDB or UniProt context before structure search.",
  },
  {
    module: "design",
    frontendClients: ["dockingRunAPI", "moleculeScoreAPI", "labsRetrosynthesisRunAPI"],
    backendRouters: ["POST /api/v1/design/session/start", "POST /api/v1/design/retrieve-candidates", "POST /api/v1/docking/run"],
    livePages: ["DesignPage"],
    driftStatus: "adapt",
    notes: "Design Studio now accepts cockpit target and SMILES handoff; broader contract cleanup continues in design-specific phases.",
  },
  {
    module: "clinical-design",
    frontendClients: ["translational project fetches"],
    backendRouters: ["GET /api/v1/translational/projects", "POST /api/v1/translational/projects", "GET /api/v1/clinical/india-trials/:disease"],
    livePages: ["TranslationalResearch"],
    driftStatus: "adapt",
    notes: "Canonical clinical workflow uses the translational page while the 10-step backend contract remains the target shape.",
  },
  {
    module: "syntharena",
    frontendClients: ["SynthArena page fetches"],
    backendRouters: ["POST /api/v1/syntharena/sessions", "POST /api/v1/syntharena/sessions/:id/export"],
    livePages: ["SynthArenaPage"],
    driftStatus: "investigate",
    notes: "Route is canonical, but deeper FE↔BE parity remains outside Phase P scope.",
  },
  {
    module: "research-labs",
    frontendClients: ["labsPocketRunAPI", "labsAdmetRunAPI", "labsRetrosynthesisRunAPI", "labsMoleculeGenerationRunAPI"],
    backendRouters: ["POST /api/v1/labs/pocket/run", "POST /api/v1/labs/admet/run", "POST /api/v1/labs/retrosynthesis/run", "POST /api/v1/labs/molecule-generation/run"],
    livePages: ["LabsPage"],
    driftStatus: "aligned",
    notes: "Cockpit handoff now lands on labs with a recommended module when entity type is known.",
  },
  {
    module: "contradiction-similarity",
    frontendClients: ["useContradictions hook"],
    backendRouters: ["GET /api/v1/evidence/contradictions", "POST /api/v1/evidence/contradictions/resolve"],
    livePages: ["Contradictions"],
    driftStatus: "adapt",
    notes: "Canonical route exists and now accepts cockpit context, but fresh-input UX remains a separate phase.",
  },
  {
    module: "pico-verification",
    frontendClients: ["usePICOItems hook"],
    backendRouters: ["GET /api/v1/pico/items", "POST /api/v1/evidence/bundles"],
    livePages: ["PICOVerification"],
    driftStatus: "adapt",
    notes: "Canonical route exists and now accepts cockpit context, while full live-input authoring remains separate work.",
  },
  {
    module: "settings",
    frontendClients: ["settings fetches", "runtime diagnostics fetches"],
    backendRouters: ["GET /api/v1/settings", "POST /api/v1/runtime/select-mode", "GET /api/v1/runtime/diagnostics"],
    livePages: ["SettingsPage"],
    driftStatus: "aligned",
    notes: "Settings remains the secure surface for runtime and connector configuration.",
  },
];

export const CREDENTIAL_HANDLING_RULE = {
  allowedSources: ["environment variables", "secure settings", "server-side secret managers"],
  forbiddenSources: ["source code constants", "page-local variables", "checked-in markdown examples with live tokens"],
  runtimePolicy: [
    "External model or API credentials must be injected at runtime, never bundled into the frontend.",
    "Frontend pages may only reference masked connector health or setting presence, not raw credential values.",
    "Exports, logs, and persisted handoff payloads must exclude raw secrets and local file-system credential paths.",
  ],
} as const;

export const COCKPIT_HANDOFF_STORAGE_KEY = "drug-designer:cockpit-handoff";
export const COCKPIT_RECENT_COMMANDS_KEY = "drug-designer:recent-commands";
export const COCKPIT_PROJECT_MEMORY_KEY = "drug-designer:project-memory";

export interface CockpitArtifactMemoryRecord {
  runId?: string;
  query: string;
  queryMode: ReturnType<typeof classifyCockpitQueryMode>;
  createdAt: string;
  entityCount: number;
  targetRoute?: string;
}

export function normalizeCockpitQuery(input: string): string {
  const greekMap: Record<string, string> = {
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "κ": "kappa",
  };

  let normalized = input.normalize("NFKC")
    .replace(/[–—]/g, "-")
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'");

  for (const [glyph, token] of Object.entries(greekMap)) {
    normalized = normalized.replaceAll(glyph, token);
  }

  normalized = normalized.replace(/\b([OPQ][0-9][A-Z0-9]{3,8}[0-9])\b/gi, (match) => match.toUpperCase());
  normalized = normalized.replace(/\b(\d[A-Z0-9]{3})\b/gi, (match) => match.toUpperCase());
  return normalized.replace(/\s+/g, " ").trim();
}

export function parseSlashCommand(input: string): { command: SlashCommandDefinition | null; argument: string; normalizedQuery: string } {
  // Delegate to inline parser for backward compatibility
  const result = parseInlineSlashCommand(input);
  return {
    command: result.command,
    argument: result.argument,
    normalizedQuery: result.normalizedQuery,
  };
}

/* ── Inline Slash Command Parser ─────────────────────────── */

export interface InlineSlashParseResult {
  command: SlashCommandDefinition | null;
  argument: string;
  additionalInstructions: string;
  pendingCommands: SlashCommandDefinition[];
  originalQuery: string;
  normalizedQuery: string;
}

/**
 * Parse slash commands at ANY position in the input string.
 * Supports leading ("/disease BRCA1"), inline ("Run /disease intelligence on BRCA1"),
 * and multi-command ("Run /disease then /targets") patterns.
 *
 * Algorithm:
 * 1. Normalize input
 * 2. Scan for all /word tokens using regex
 * 3. Match each against SLASH_COMMANDS
 * 4. First valid match → primary command; subsequent → pendingCommands
 * 5. Text surrounding the command → additionalInstructions
 * 6. No valid command → passthrough as general query
 */
export function parseInlineSlashCommand(input: string): InlineSlashParseResult {
  const originalQuery = input;
  const normalizedQuery = normalizeCockpitQuery(input);

  if (!normalizedQuery) {
    return {
      command: null,
      argument: normalizedQuery,
      additionalInstructions: "",
      pendingCommands: [],
      originalQuery,
      normalizedQuery,
    };
  }

  // Scan for all /command tokens at any position
  const commandRegex = /(?:^|\s)(\/[a-z]+)(?:\s|$)/gi;
  const matches: Array<{ token: string; index: number; endIndex: number }> = [];
  let match: RegExpExecArray | null;

  while ((match = commandRegex.exec(normalizedQuery)) !== null) {
    const token = match[1].toLowerCase();
    const tokenStart = match.index + (match[0].startsWith(" ") ? 1 : 0);
    const tokenEnd = tokenStart + token.length;
    matches.push({ token, index: tokenStart, endIndex: tokenEnd });
    // Reset lastIndex to avoid skipping overlapping matches
    commandRegex.lastIndex = tokenEnd;
  }

  // Resolve each token against SLASH_COMMANDS
  const validMatches: Array<{ def: SlashCommandDefinition; index: number; endIndex: number }> = [];
  for (const m of matches) {
    const def = SLASH_COMMANDS.find((cmd) => cmd.command === m.token);
    if (def) {
      validMatches.push({ def, index: m.index, endIndex: m.endIndex });
    }
  }

  if (validMatches.length === 0) {
    return {
      command: null,
      argument: normalizedQuery,
      additionalInstructions: "",
      pendingCommands: [],
      originalQuery,
      normalizedQuery,
    };
  }

  const primary = validMatches[0];
  const pendingCommands = validMatches.slice(1).map((m) => m.def);

  // Extract argument: text after the primary command token until the next command or end
  const afterCommand = normalizedQuery.slice(primary.endIndex).trim();
  let argument: string;
  if (validMatches.length > 1) {
    // Argument is text between primary command and next command
    const nextCommandStart = validMatches[1].index;
    argument = normalizedQuery.slice(primary.endIndex, nextCommandStart).trim();
  } else {
    argument = afterCommand;
  }

  // Additional instructions: text before the primary command + text after argument/pending commands
  const beforeCommand = normalizedQuery.slice(0, primary.index).trim();
  let afterAllCommands = "";
  if (validMatches.length > 1) {
    const lastMatch = validMatches[validMatches.length - 1];
    afterAllCommands = normalizedQuery.slice(lastMatch.endIndex).trim();
  }
  const additionalInstructions = [beforeCommand, afterAllCommands].filter(Boolean).join(" ").trim();

  return {
    command: primary.def,
    argument,
    additionalInstructions,
    pendingCommands,
    originalQuery,
    normalizedQuery,
  };
}

/* ── Health Computation Pure Functions ────────────────────── */

export interface SourceHealthEntry {
  name: string;
  status: "healthy" | "degraded" | "error" | "unknown";
  avg_response_ms: number | null;
  p95_response_ms: number | null;
  errors_1h: number;
  ratelimit_hits_1h: number;
  last_checked: string;
  circuit_breaker_state: "closed" | "open" | "half_open";
}

export interface HealthSummary {
  total: number;
  healthy: number;
  degraded: number;
  error: number;
  unknown: number;
}

export type HealthBadgeColor = "green" | "yellow" | "red";

/** Pure function: compute badge color from health summary */
export function computeHealthBadgeColor(summary: HealthSummary): HealthBadgeColor {
  if (summary.total === 0) return "red";
  const ratio = summary.healthy / summary.total;
  if (ratio > 0.8) return "green";
  if (ratio >= 0.5) return "yellow";
  return "red";
}

/** Pure function: aggregate health summary from source entries */
export function computeHealthSummary(sources: SourceHealthEntry[]): HealthSummary {
  const summary: HealthSummary = { total: sources.length, healthy: 0, degraded: 0, error: 0, unknown: 0 };
  for (const s of sources) {
    switch (s.status) {
      case "healthy": summary.healthy++; break;
      case "degraded": summary.degraded++; break;
      case "error": summary.error++; break;
      default: summary.unknown++; break;
    }
  }
  return summary;
}

/** Pure function: derive connector status from circuit breaker state and error count */
export function deriveConnectorStatus(
  circuitBreakerState: string,
  errors1h: number,
  errorThreshold = 10,
): "healthy" | "degraded" | "error" {
  if (circuitBreakerState === "open") return "degraded";
  if (circuitBreakerState === "half_open") return "degraded";
  if (errors1h >= errorThreshold) return "error";
  return "healthy";
}

/** Pure function: compute health stats from response time samples */
export function computeHealthStats(samples: number[]): { avg_response_ms: number; p95_response_ms: number } {
  if (samples.length === 0) return { avg_response_ms: 0, p95_response_ms: 0 };
  const avg = samples.reduce((a, b) => a + b, 0) / samples.length;
  const sorted = [...samples].sort((a, b) => a - b);
  const p95Index = Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1);
  return {
    avg_response_ms: avg,
    p95_response_ms: sorted[p95Index],
  };
}

export function classifyCockpitQueryMode(input: string):
  | "evidence"
  | "disease"
  | "target"
  | "graph"
  | "pathway"
  | "structure"
  | "design"
  | "clinical"
  | "lab"
  | "compare" {
  const { command, normalizedQuery } = parseSlashCommand(input);
  if (command) {
    if (["/disease"].includes(command.command)) return "disease";
    if (["/targets", "/gene"].includes(command.command)) return "target";
    if (["/kg"].includes(command.command)) return "graph";
    if (["/pathways"].includes(command.command)) return "pathway";
    if (["/structure", "/protein"].includes(command.command)) return "structure";
    if (["/design", "/molecule"].includes(command.command)) return "design";
    if (["/clinical"].includes(command.command)) return "clinical";
    if (["/labs"].includes(command.command)) return "lab";
    if (["/compare"].includes(command.command)) return "compare";
  }

  if (/pathway|reactome|kegg/i.test(normalizedQuery)) return "pathway";
  if (/structure|pdb|alphafold|protein/i.test(normalizedQuery)) return "structure";
  if (/design|smiles|molecule|ligand|dock/i.test(normalizedQuery)) return "design";
  if (/clinical|phase\s+[1-4]|trial|pico/i.test(normalizedQuery)) return "clinical";
  if (/graph|network|interaction/i.test(normalizedQuery)) return "graph";
  if (/target|gene/i.test(normalizedQuery)) return "target";
  if (/disease|syndrome|cancer/i.test(normalizedQuery)) return "disease";
  return "evidence";
}

export function persistCockpitHandoff(payload: SharedHandoffPayload): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(COCKPIT_HANDOFF_STORAGE_KEY, JSON.stringify(payload));
}

export function readCockpitHandoff(): SharedHandoffPayload | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(COCKPIT_HANDOFF_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SharedHandoffPayload;
  } catch {
    return null;
  }
}

export function rememberSlashCommand(command: string): void {
  if (typeof window === "undefined") return;
  const current = JSON.parse(window.localStorage.getItem(COCKPIT_RECENT_COMMANDS_KEY) || "[]") as string[];
  const next = [command, ...current.filter((item) => item !== command)].slice(0, 8);
  window.localStorage.setItem(COCKPIT_RECENT_COMMANDS_KEY, JSON.stringify(next));
}

export function readRecentSlashCommands(): string[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(COCKPIT_RECENT_COMMANDS_KEY) || "[]") as string[];
  } catch {
    return [];
  }
}

export function persistCockpitArtifactRecord(record: CockpitArtifactMemoryRecord): void {
  if (typeof window === "undefined") return;
  const current = readCockpitArtifactMemory();
  const next = [record, ...current.filter((item) => !(item.runId && item.runId === record.runId))].slice(0, 20);
  window.localStorage.setItem(COCKPIT_PROJECT_MEMORY_KEY, JSON.stringify(next));
}

export function readCockpitArtifactMemory(): CockpitArtifactMemoryRecord[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(COCKPIT_PROJECT_MEMORY_KEY) || "[]") as CockpitArtifactMemoryRecord[];
  } catch {
    return [];
  }
}
