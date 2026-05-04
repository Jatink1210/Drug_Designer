/** WorkspacePage — Biomedical Intelligence Search Hub
 *  Clean search → comprehensive 18-section canonical analysis report.
 *  Queries 30+ databases, applies AI analysis + enrichment (target scoring,
 *  disease intelligence, contradictions, ADMET, retrosynthesis, etc.).
 */

import { useState, useCallback, useRef, useEffect, useReducer } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search, Zap, Sparkles, Loader2, XCircle, BarChart3,
  Download, FileJson, FileSpreadsheet,
  Database, Network, Target, FlaskConical, FileText,
  BookOpen, Pill, Dna, Activity,
  ChevronDown, ChevronUp, ExternalLink,
  Clock, Shield, AlertTriangle, CheckCircle2,
  RefreshCw, Copy, Printer, Hash, Beaker, Microscope,
  TrendingUp, Layers, Atom, Syringe, Globe,
  FileSearch, GitBranch, ListChecks, Award,
} from "lucide-react";
import React from "react";
import { cockpitRunStatusAPI, cockpitStartAnalysisAPI } from "@/lib/api";
import type { CockpitAnalysisResult } from "@/lib/api";
import { useRunProgress } from "@/lib/hooks";
import ForceGraph from "@/components/ui/ForceGraph";
import SmilesRenderer from "@/components/ui/SmilesRenderer";
import CockpitEntityExplorer from "@/components/cockpit/CockpitEntityExplorer";
import EntityDetailDrawer from "@/components/entity/EntityDetailDrawer";
import { useToast } from "@/lib/ToastContext";
import {
  classifyCockpitQueryMode,
  normalizeCockpitQuery,
  parseSlashCommand,
  parseInlineSlashCommand,
  persistCockpitHandoff,
  persistCockpitArtifactRecord,
  readRecentSlashCommands,
  rememberSlashCommand,
  SLASH_COMMANDS,
  type SharedHandoffPayload,
  type SlashCommandDefinition,
  type InlineSlashParseResult,
} from "@/lib/canonicalProduct";

/* ── Download utilities ───────────────────────────────────── */

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function downloadJSON(data: CockpitAnalysisResult) {
  const ts = new Date().toISOString().slice(0, 10);
  const slug = data.query.replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 40);
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  downloadBlob(blob, `drug_designer_${slug}_${ts}.json`);
}

function downloadCSV(data: CockpitAnalysisResult) {
  const ts = new Date().toISOString().slice(0, 10);
  const slug = data.query.replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 40);
  let csv = `# Drug Designer Analysis Report\n# Query: ${data.query}\n# Date: ${new Date().toISOString()}\n# Total Results: ${data.stats.total_results}\n# Sources Queried: ${data.stats.sources_queried}\n# Confidence: ${Math.round(data.stats.overall_confidence * 100)}%\n\n`;

  for (const cat of data.categories) {
    if (!cat.rows.length) continue;
    csv += `\n## ${cat.category.toUpperCase()} (${cat.count} results)\n`;
    const cols = cat.columns.length > 0 ? cat.columns : Object.keys(cat.rows[0]);
    const safeCols = cols.filter((c) => !c.startsWith("_"));
    csv += safeCols.join(",") + "\n";
    for (const row of cat.rows) {
      csv += safeCols.map((c) => {
        const v = row[c];
        const str = v == null ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
        return str.includes(",") || str.includes('"') || str.includes("\n")
          ? `"${str.replace(/"/g, '""')}"` : str;
      }).join(",") + "\n";
    }
  }
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  downloadBlob(blob, `drug_designer_${slug}_${ts}.csv`);
}

async function downloadRIS(data: CockpitAnalysisResult) {
  const papers = data.literature_table || [];
  if (!papers.length) { alert("No literature data for RIS export."); return; }
  try {
    const resp = await fetch("/api/v1/cockpit/export/ris", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ papers, query: data.query }),
    });
    if (!resp.ok) throw new Error("Export failed");
    const text = await resp.text();
    const blob = new Blob([text], { type: "application/x-research-info-systems" });
    downloadBlob(blob, `literature_${data.query.replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 30)}.ris`);
  } catch {
    // Fallback: client-side RIS generation
    let ris = "";
    for (const p of papers) {
      ris += "TY  - JOUR\n";
      if (p.title) ris += `TI  - ${p.title}\n`;
      if (p.authors) ris += `AU  - ${p.authors}\n`;
      if (p.year) ris += `PY  - ${p.year}\n`;
      if (p.journal) ris += `JO  - ${p.journal}\n`;
      if (p.doi) ris += `DO  - ${p.doi}\n`;
      if (p.pmid) ris += `AN  - PMID:${p.pmid}\n`;
      if (p.url) ris += `UR  - ${p.url}\n`;
      if (p.summary) ris += `AB  - ${p.summary}\n`;
      ris += "ER  - \n\n";
    }
    const blob = new Blob([ris], { type: "application/x-research-info-systems" });
    downloadBlob(blob, `literature_${data.query.replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 30)}.ris`);
  }
}

async function downloadBibTeX(data: CockpitAnalysisResult) {
  const papers = data.literature_table || [];
  if (!papers.length) { alert("No literature data for BibTeX export."); return; }
  try {
    const resp = await fetch("/api/v1/cockpit/export/bibtex", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ papers, query: data.query }),
    });
    if (!resp.ok) throw new Error("Export failed");
    const text = await resp.text();
    const blob = new Blob([text], { type: "application/x-bibtex" });
    downloadBlob(blob, `literature_${data.query.replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 30)}.bib`);
  } catch {
    // Fallback: client-side BibTeX generation
    let bib = "";
    for (let i = 0; i < papers.length; i++) {
      const p = papers[i];
      const key = `paper${i + 1}_${String(p.year || "nd")}`;
      bib += `@article{${key},\n`;
      if (p.title) bib += `  title = {${p.title}},\n`;
      if (p.authors) bib += `  author = {${p.authors}},\n`;
      if (p.year) bib += `  year = {${p.year}},\n`;
      if (p.journal) bib += `  journal = {${p.journal}},\n`;
      if (p.doi) bib += `  doi = {${p.doi}},\n`;
      bib += "}\n\n";
    }
    const blob = new Blob([bib], { type: "application/x-bibtex" });
    downloadBlob(blob, `literature_${data.query.replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 30)}.bib`);
  }
}

/* ── Category meta ────────────────────────────────────────── */

const CATEGORY_META: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  proteins: { icon: <Dna size={14} />, color: "#7c3aed", label: "Proteins" },
  genes: { icon: <Dna size={14} />, color: "#6366f1", label: "Genes" },
  drugs: { icon: <Pill size={14} />, color: "#e11d48", label: "Drugs" },
  molecules: { icon: <FlaskConical size={14} />, color: "#d97706", label: "Molecules" },
  diseases: { icon: <Activity size={14} />, color: "#dc2626", label: "Diseases" },
  publications: { icon: <BookOpen size={14} />, color: "#3b82f6", label: "Publications" },
  clinical_trials: { icon: <FileText size={14} />, color: "#059669", label: "Clinical Trials" },
  pathways: { icon: <Network size={14} />, color: "#0891b2", label: "Pathways" },
  structures: { icon: <Database size={14} />, color: "#7c3aed", label: "Structures" },
  interactions: { icon: <Network size={14} />, color: "#0d9488", label: "Interactions" },
  patents: { icon: <FileText size={14} />, color: "#8b5cf6", label: "Patents" },
  variants: { icon: <Dna size={14} />, color: "#ea580c", label: "Variants" },
  targets: { icon: <Target size={14} />, color: "#8b5cf6", label: "Targets" },
  compounds: { icon: <FlaskConical size={14} />, color: "#f59e0b", label: "Compounds" },
  assays: { icon: <FlaskConical size={14} />, color: "#10b981", label: "Assays" },
};

/* ── Example queries ──────────────────────────────────────── */

const EXAMPLE_QUERIES = [
  "BRCA1 breast cancer",
  "GLP-1 receptor agonists",
  "KRAS G12C inhibitors",
  "Alzheimer's disease tau protein",
  "CAR-T cell therapy lymphoma",
  "EGFR non-small cell lung cancer",
];

/* ── Progress messages ────────────────────────────────────── */

const PROGRESS_STEPS = [
  "Initializing multi-source search engine…",
  "Querying PubMed, Europe PMC, Semantic Scholar…",
  "Searching ChEMBL, PubChem, DrugBank…",
  "Fetching UniProt, Ensembl, STRING…",
  "Querying ClinicalTrials.gov, GWAS Catalog…",
  "Analyzing OpenTargets, DisGeNET, KEGG…",
  "Building knowledge graph relationships…",
  "Scoring evidence confidence…",
  "Detecting contradictions across sources…",
  "Generating AI expert summary…",
];

const COCKPIT_LAST_RUN_KEY = "drug-designer:cockpit-last-run";
const COCKPIT_PENDING_RUN_KEY = "drug-designer:cockpit-pending-run";

/* ── ETA estimation per query intent ─────────────────────── */

const QUERY_INTENT_KEYWORDS: Array<{ pattern: RegExp; intent: string; eta: number; label: string }> = [
  { pattern: /literature|evidence|papers?|publications?|pubmed|search\s+for/i, intent: "Literature & Evidence", eta: 90, label: "Deep literature search across 6+ databases" },
  { pattern: /gwas|genome[- ]wide|snp|variant|allele/i, intent: "Genomics / GWAS", eta: 120, label: "Genomic variant analysis + population data" },
  { pattern: /clinical\s+trial|phase\s+[1-4I]/i, intent: "Clinical Trials", eta: 75, label: "Clinical trial registry search + PICO extraction" },
  { pattern: /drug\s+design|admet|pharmacokinetic|smiles|molecule/i, intent: "Drug Design / ADMET", eta: 100, label: "Molecular property prediction + retrosynthesis" },
  { pattern: /target|prioriti[sz]|druggab/i, intent: "Target Prioritization", eta: 85, label: "Multi-factor target scoring + network analysis" },
  { pattern: /pathway|signaling|cascade|kegg|reactome/i, intent: "Pathway Analysis", eta: 80, label: "Pathway enrichment + cross-reference" },
  { pattern: /structure|crystal|binding|pocket|pdb|alphafold/i, intent: "Structure Analysis", eta: 95, label: "3D structure retrieval + pocket analysis" },
  { pattern: /disease|epidemiology|prevalence|incidence/i, intent: "Disease Intelligence", eta: 90, label: "Disease profiling + genetic associations" },
  { pattern: /contradiction|replicate|compare/i, intent: "Comparative Analysis", eta: 110, label: "Cross-source contradiction + similarity detection" },
  { pattern: /knowledge\s+graph|network|interaction/i, intent: "Knowledge Graph", eta: 85, label: "Entity relationship mapping + graph construction" },
];

function detectQueryIntent(q: string): { intent: string; eta: number; label: string } {
  const lower = q.toLowerCase();
  for (const entry of QUERY_INTENT_KEYWORDS) {
    if (entry.pattern.test(lower)) return entry;
  }
  // Word count heuristic: longer queries → more complex
  const words = q.split(/\s+/).length;
  const eta = words > 10 ? 100 : words > 5 ? 80 : 60;
  return { intent: "General Biomedical", eta, label: "Multi-database search + AI analysis" };
}

function actionForSlashCommand(command: SlashCommandDefinition): SharedHandoffPayload["action"] {
  switch (command.command) {
    case "/kg":
      return "open_in_graph";
    case "/pathways":
      return "open_in_pathways";
    case "/structure":
    case "/protein":
      return "open_in_structure";
    case "/design":
    case "/molecule":
      return "open_in_design";
    case "/labs":
      return "open_in_labs";
    case "/clinical":
      return "open_in_clinical";
    case "/contradictions":
      return "open_in_contradiction_similarity";
    case "/pico":
      return "open_in_pico_verification";
    case "/disease":
    case "/gene":
    case "/targets":
      return "run_entity_intelligence";
    case "/compare":
      return "compare_entities";
    default:
      return "run_cockpit_search";
  }
}

function buildSlashCommandPayload(
  command: SlashCommandDefinition,
  query: string,
  runId?: string,
  entities: SharedHandoffPayload["entities"] = [],
  metadata?: Record<string, unknown>,
  traceId?: string,
): SharedHandoffPayload {
  return {
    version: "phase0.v1",
    sourceModule: "cockpit",
    action: actionForSlashCommand(command),
    targetRoute: command.route,
    query,
    createdAt: new Date().toISOString(),
    runId,
    traceId,
    entities,
    provenance: entities.length > 0
      ? entities.map((entity) => ({ source: entity.sourceCategory || "cockpit-command", retrievedAt: new Date().toISOString(), runId }))
      : [{ source: "cockpit-command", retrievedAt: new Date().toISOString(), runId }],
    metadata: {
      command: command.command,
      label: command.label,
      mode: classifyCockpitQueryMode(`${command.command} ${query}`),
      ...metadata,
    },
  };
}

function collectCommandEntities(result: CockpitAnalysisResult | null): SharedHandoffPayload["entities"] {
  if (!result) return [];

  const typeMap: Record<string, SharedHandoffPayload["entities"][number]["entityType"]> = {
    proteins: "protein",
    genes: "gene",
    drugs: "drug",
    diseases: "disease",
    pathways: "pathway",
    publications: "publication",
    clinical_trials: "clinical_trial",
    compounds: "compound",
    molecules: "molecule",
    variants: "variant",
    interactions: "target",
  };

  const readString = (row: Record<string, unknown>, keys: string[]) => {
    for (const key of keys) {
      const value = row[key];
      if (typeof value === "string" && value.trim()) return value.trim();
    }
    return undefined;
  };

  return (result.categories || [])
    .filter((category) => category.count > 0)
    .flatMap((category) =>
      category.rows.slice(0, 2).map((row, index) => ({
        entityId: readString(row, ["entity_id", "id", "uniprot_id", "ensembl_id", "drugbank_id", "chembl_id", "pathway_id", "pmid", "doi", "nct_id", "name", "symbol", "title"]) || `${category.category}-${index + 1}`,
        entityType: typeMap[category.category] || "unknown",
        entityName: readString(row, ["entity_name", "name", "title", "drug_name", "disease_name", "pathway_name", "protein_name", "compound_name", "symbol", "gene", "variant"]) || `${category.category}-${index + 1}`,
        sourceCategory: category.category,
        identifiers: Object.fromEntries(
          Object.entries(row)
            .filter(([key, value]) => /id$|_id$|symbol|gene|smiles|doi|pmid|nct/i.test(key) && typeof value === "string" && value.trim())
            .map(([key, value]) => [key, value as string]),
        ),
        attributes: row,
      })),
    )
    .slice(0, 24);
}

/* ── Section wrapper ───────────────────────────────────────── */

function ReportSection({
  num, title, icon, children, defaultOpen = true, color = "var(--accent)",
}: {
  num: number; title: string; icon: React.ReactNode; children: React.ReactNode;
  defaultOpen?: boolean; color?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)" }}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2.5 px-5 py-3.5 text-left hover:opacity-90 transition-opacity"
        style={{ background: `${color}06` }}
      >
        <span
          className="flex items-center justify-center w-6 h-6 rounded-full text-[10px] font-black"
          style={{ background: `${color}15`, color }}
        >
          {num}
        </span>
        <span style={{ color }}>{icon}</span>
        <span className="text-[13px] font-bold" style={{ color: "var(--text-primary)" }}>{title}</span>
        <span className="flex-1" />
        {open ? <ChevronUp size={14} style={{ color: "var(--text-muted)" }} /> : <ChevronDown size={14} style={{ color: "var(--text-muted)" }} />}
      </button>
      {open && <div className="px-5 py-4" style={{ borderTop: "1px solid var(--border)" }}>{children}</div>}
    </div>
  );
}

/* ── Mini data table ──────────────────────────────────────── */

function MiniTable({ columns, rows, maxRows = 20 }: { columns: string[]; rows: Array<Record<string, unknown>>; maxRows?: number }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? rows : rows.slice(0, maxRows);
  if (!rows.length) return <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>No data available.</div>;
  return (
    <div className="overflow-x-auto table-scroll-container">
      <table className="w-full text-[11px]" style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--bg-app)" }}>
            <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)", borderBottom: "2px solid var(--border)", width: 32 }}>#</th>
            {columns.map((c) => (
              <th key={c} className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)", borderBottom: "2px solid var(--border)" }}>
                {c.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visible.map((row, ri) => (
            <tr key={ri} className="hover:bg-[var(--bg-app)]" style={{ borderBottom: "1px solid var(--border)" }}>
              <td className="px-3 py-2 text-[10px]" style={{ color: "var(--text-muted)" }}>{ri + 1}</td>
              {columns.map((col) => {
                const val = row[col];
                const isUrl = (col === "url" || col === "link" || col === "source_url") && typeof val === "string" && val.startsWith("http");
                const isScore = (col.includes("score") || col.includes("confidence") || col === "pvalue") && typeof val === "number";
                const display = val == null ? "—" : typeof val === "object" ? JSON.stringify(val).slice(0, 80) : String(val).length > 120 ? String(val).slice(0, 117) + "…" : String(val);
                return (
                  <td key={col} className="px-3 py-2" style={{ color: "var(--text-primary)", maxWidth: 280 }}>
                    {isUrl ? <a href={val as string} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 hover:underline" style={{ color: "#3b82f6" }}><ExternalLink size={10} /> Link</a>
                     : isScore ? <span className="font-mono font-semibold" style={{ color: (val as number) >= 0.7 ? "#10b981" : (val as number) >= 0.4 ? "#f59e0b" : "#ef4444" }}>{(val as number).toFixed(3)}</span>
                     : <span className="break-words">{display}</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > maxRows && (
        <div className="text-center py-2" style={{ borderTop: "1px solid var(--border)" }}>
          <button onClick={() => setShowAll(!showAll)} className="text-[11px] font-semibold px-4 py-1.5 rounded" style={{ color: "#3b82f6", background: "#3b82f608", border: "1px solid #3b82f620" }}>
            {showAll ? `Show fewer (${maxRows})` : `Show all ${rows.length} rows`}
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Score bar ────────────────────────────────────────────── */

function ScoreBar({ value, label, color }: { value: number; label?: string; color?: string }) {
  const c = color || (value >= 0.7 ? "#10b981" : value >= 0.4 ? "#f59e0b" : "#ef4444");
  return (
    <div className="flex items-center gap-2 text-[11px]">
      {label && <span className="w-20 truncate font-medium" style={{ color: "var(--text-muted)" }}>{label}</span>}
      <div className="flex-1 h-2 rounded-full" style={{ background: "var(--border)" }}>
        <div className="h-2 rounded-full transition-all" style={{ width: `${Math.round(value * 100)}%`, background: c }} />
      </div>
      <span className="font-mono font-semibold w-10 text-right" style={{ color: c }}>{(value * 100).toFixed(0)}%</span>
    </div>
  );
}

/* ── Tag chips ────────────────────────────────────────────── */

function TagChips({ items, color = "#6366f1" }: { items: string[]; color?: string }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item, i) => (
        <span key={i} className="px-2.5 py-1 rounded-full text-[10px] font-medium" style={{ background: `${color}10`, color, border: `1px solid ${color}20` }}>
          {item}
        </span>
      ))}
    </div>
  );
}

/* ── KV Row ───────────────────────────────────────────────── */

function KVRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 py-1 text-[11px]">
      <span className="font-bold w-32 shrink-0 uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{label}</span>
      <span style={{ color: "var(--text-primary)" }}>{value || "—"}</span>
    </div>
  );
}

/* ── Error Boundary ────────────────────────────────────────── */

class ReportErrorBoundary extends React.Component<
  { children: React.ReactNode; onReset: () => void },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode; onReset: () => void }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-lg border p-6 text-center" style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
          <AlertTriangle size={32} className="mx-auto mb-3" style={{ color: "#ef4444" }} />
          <h3 className="text-sm font-bold mb-1" style={{ color: "var(--text-primary)" }}>Report Rendering Error</h3>
          <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>
            {this.state.error?.message || "An unexpected error occurred while rendering."}
          </p>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); this.props.onReset(); }}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium"
            style={{ background: "var(--accent)", color: "#fff" }}
          >
            <RefreshCw size={12} /> Try New Search
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ── Analysis Report ──────────────────────────────────────── */

function AnalysisReport({ data, onNewSearch }: { data: CockpitAnalysisResult; onNewSearch: () => void }) {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [copiedSummary, setCopiedSummary] = useState(false);
  const [tracePanel, setTracePanel] = useState<{ claim: string; evidence: Array<Record<string, unknown>> } | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<Record<string, unknown> | null>(null);
  const [selectedGraphEdge, setSelectedGraphEdge] = useState<Record<string, unknown> | null>(null);
  const [selectedPathwayNode, setSelectedPathwayNode] = useState<Record<string, unknown> | null>(null);
  const [refSelected, setRefSelected] = useState<number | null>(null);

  const handleCopySummary = async () => {
    if (data.summary) { await navigator.clipboard.writeText(data.summary); setCopiedSummary(true); setTimeout(() => setCopiedSummary(false), 2000); }
  };

  const { stats, categories, summary, graph, evidence, timings } = data;
  const nonEmpty = categories.filter((c) => c.count > 0);
  const totalRows = nonEmpty.reduce((s, c) => s + (c.rows?.length || 0), 0);

  const contradictions = data.contradictions || [];
  const diseaseIntel = data.disease_intelligence || [];
  const targetRanking = data.target_prioritization || [];
  const graphReasoning = data.graph_reasoning || [];
  const pathwaysData = data.pathways || [];
  const structureData = data.structures || [];
  const admetData = data.admet || [];
  const retroData = data.retrosynthesis || [];
  const trialsData = data.clinical_trials || [];
  const picoData = data.pico || [];
  const entitiesExtracted = data.entities_extracted || { genes: [], proteins: [], diseases: [], drugs: [], structures: [] };
  const populationData = data.population_genomics || {};
  const syntharenaData = data.syntharena || {};
  const queryClassification = data.query_classification || { query_type: "general", emphasis: [], genes: [], pathways: [], search_terms: [], comparison_targets: [] };

  // Literature-specific data
  const literatureTable = data.literature_table || [];
  const filteredLiterature = data.filtered_literature || [];
  const filterInfo = data.filter_info || {};
  const similarities = data.similarities || [];
  const nuancedRelationships = data.nuanced_relationships || [];
  const termsMap = data.terms_map || {};
  const termFrequency = data.term_frequency || {};
  const literatureKG = data.literature_kg || {};
  const meshTerminology = data.mesh_terminology || {};
  const literatureStats = data.literature_stats || {};
  const hasLiteratureData = literatureTable.length > 0;
  const paperSentences = data.paper_sentences || [];
  const evidenceLinks = data.evidence_links || {};
  const litStructures = data.lit_structures || [];
  const llmContradictions = data.llm_contradictions || [];
  const traceableSummary = data.traceable_summary || { summary_text: "", references: [], supporting_findings: [], dissenting_findings: [] };
  const unifiedPathways = data.unified_pathways || { nodes: [], edges: [], pathway_layers: [], total_nodes: 0, total_edges: 0 };
  const mechanismClusters = data.mechanism_clusters || { clusters: [], unclustered: [], total_clustered: 0 };

  // Determine if a section should be highlighted based on query classification
  const emphasizedSections = new Set(queryClassification.emphasis || []);

  // ── Intent-specific section visibility ────────────────
  // Literature-focused query types show literature sections prominently
  const LITERATURE_QUERY_TYPES = new Set([
    "evidence_retrieval", "cockpit_resume", "dossier", "research_loop",
    "knowledge_graph", "disease_intelligence", "target_prioritization",
    "e2e_program", "autopilot", "translation_research", "translational_pico",
    "general",
  ]);
  const DRUG_DESIGN_TYPES = new Set([
    "design_studio", "molecule_lab", "pocket_discovery", "retrosynthesis", "admet",
  ]);
  const STRUCTURE_TYPES = new Set([
    "structure_pocket", "pocket_discovery", "design_studio",
  ]);

  const qType = queryClassification.query_type || "general";
  const isLiteratureQuery = LITERATURE_QUERY_TYPES.has(qType) || hasLiteratureData;
  const isDrugDesignQuery = DRUG_DESIGN_TYPES.has(qType);
  const isStructureQuery = STRUCTURE_TYPES.has(qType);

  // Sections that only show when relevant data exists AND query intent matches
  const showDrugSections = isDrugDesignQuery || structureData.length > 0 || admetData.length > 0;
  const showRetro = isDrugDesignQuery || retroData.length > 0;
  const showSynthArena = qType === "syntharena" || Object.keys(syntharenaData).length > 0;
  const showPopGenomics = qType === "population_genomics" || (populationData.gnomad?.length > 0 || populationData.indigen?.length > 0 || populationData.genome_asia?.length > 0);
  const showClinical = ["translational_pico", "translation_research"].includes(qType) || trialsData.length > 0 || picoData.length > 0;

  const collectReportEntities = (): SharedHandoffPayload["entities"] => {
    const typeMap: Record<string, SharedHandoffPayload["entities"][number]["entityType"]> = {
      proteins: "protein",
      genes: "gene",
      drugs: "drug",
      diseases: "disease",
      publications: "publication",
      pathways: "pathway",
      clinical_trials: "clinical_trial",
      interactions: "target",
      compounds: "compound",
      molecules: "molecule",
      variants: "variant",
      structures: "protein",
    };

    const readString = (row: Record<string, unknown>, keys: string[]) => {
      for (const key of keys) {
        const value = row[key];
        if (typeof value === "string" && value.trim()) return value.trim();
      }
      return undefined;
    };

    return nonEmpty.flatMap((category) =>
      category.rows.slice(0, 3).map((row, index) => {
        const entityId = readString(row, ["entity_id", "id", "uniprot_id", "ensembl_id", "drugbank_id", "chembl_id", "pathway_id", "pmid", "doi", "nct_id", "name", "symbol", "title"]) || `${category.category}-${index + 1}`;
        const entityName = readString(row, ["entity_name", "name", "title", "drug_name", "disease_name", "pathway_name", "protein_name", "compound_name", "symbol", "gene", "variant"]) || entityId;
        return {
          entityId,
          entityType: typeMap[category.category] || "unknown",
          entityName,
          sourceCategory: category.category,
          identifiers: Object.fromEntries(
            Object.entries(row)
              .filter(([key, value]) => /id$|_id$|symbol|gene|smiles|doi|pmid|nct/i.test(key) && typeof value === "string" && value.trim())
              .map(([key, value]) => [key, value as string]),
          ),
          attributes: row,
        };
      }),
    ).slice(0, 24);
  };

  const navigateWithReportHandoff = (route: string, action: SharedHandoffPayload["action"], metadata?: Record<string, unknown>) => {
    const entities = collectReportEntities();
    const payload: SharedHandoffPayload = {
      version: "phase0.v1",
      sourceModule: "cockpit",
      action,
      targetRoute: route,
      query: data.query,
      createdAt: new Date().toISOString(),
      runId: data.run_id,
      traceId: typeof (data as unknown as Record<string, unknown>).trace_id === "string" ? ((data as unknown as Record<string, unknown>).trace_id as string) : undefined,
      entities,
      provenance: entities.map((entity) => ({
        source: entity.sourceCategory || "cockpit-report",
        retrievedAt: new Date().toISOString(),
        runId: data.run_id,
      })),
      metadata: {
        degradedSources: data.degraded_sources || [],
        ...metadata,
      },
    };
    persistCockpitHandoff(payload);
    addToast({ type: "success", title: "Cockpit handoff ready", message: `Context sent to ${route}.` });
    navigate(route);
  };

  return (
    <div className="flex flex-col gap-4">

      {/* ═══════════════════════════════════════════════════
          §1 — EXECUTIVE HEADER
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={1} title="Executive Header" icon={<Award size={14} />} color="#6366f1">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <KVRow label="Run ID" value={<span className="font-mono text-[10px]">{data.run_id || "—"}</span>} />
            <KVRow label="Timestamp" value={data.timestamp || new Date().toISOString()} />
          </div>
          <div>
            <KVRow label="Query" value={<span className="font-semibold">{data.query}</span>} />
            <KVRow label="Latency" value={`${(data.latency_ms / 1000).toFixed(1)}s`} />
          </div>
          <div>
            <KVRow label="Total Results" value={stats.total_results.toLocaleString()} />
            <KVRow label="Sources" value={stats.sources_queried} />
          </div>
          <div>
            <KVRow label="Confidence" value={<span style={{ color: stats.overall_confidence >= 0.7 ? "#10b981" : "#f59e0b" }}>{Math.round(stats.overall_confidence * 100)}%</span>} />
            <KVRow label="Contradictions" value={<span style={{ color: stats.contradictions_count > 0 ? "#ef4444" : "#10b981" }}>{stats.contradictions_count}</span>} />
          </div>
        </div>

        {/* Query classification badge */}
        {queryClassification.query_type !== "general" && (
          <div className="flex flex-wrap items-center gap-2 mt-3 p-2.5 rounded-lg" style={{ background: "var(--accent)08", border: "1px solid var(--accent)20" }}>
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--accent)" }}>Query Intent:</span>
            <span className="px-2.5 py-1 rounded-full text-[10px] font-bold" style={{ background: "var(--accent)15", color: "var(--accent)" }}>
              {queryClassification.query_type.replace(/_/g, " ").toUpperCase()}
            </span>
            {queryClassification.disease && <span className="px-2 py-0.5 rounded-full text-[10px]" style={{ background: "#dc262610", color: "#dc2626", border: "1px solid #dc262620" }}>{queryClassification.disease}</span>}
            {queryClassification.genes?.length > 0 && queryClassification.genes.map((g: string) => (
              <span key={g} className="px-2 py-0.5 rounded-full text-[10px]" style={{ background: "#6366f110", color: "#6366f1", border: "1px solid #6366f120" }}>{g}</span>
            ))}
            {queryClassification.cohort && <span className="px-2 py-0.5 rounded-full text-[10px]" style={{ background: "#0891b210", color: "#0891b2", border: "1px solid #0891b220" }}>{queryClassification.cohort} cohort</span>}
            {queryClassification.pathways?.length > 0 && queryClassification.pathways.map((p: string) => (
              <span key={p} className="px-2 py-0.5 rounded-full text-[10px]" style={{ background: "#059669 10", color: "#059669", border: "1px solid #05966920" }}>{p}</span>
            ))}
          </div>
        )}

        {/* Stats strip */}
        <div className="flex flex-wrap gap-2 mt-4">
          {[
            { label: "Results", value: stats.total_results.toLocaleString(), color: "#3b82f6", icon: <BarChart3 size={11} /> },
            { label: "Categories", value: stats.categories_found, color: "#8b5cf6", icon: <Database size={11} /> },
            { label: "Sources", value: stats.sources_queried, color: "#10b981", icon: <Shield size={11} /> },
            { label: "PubMed", value: stats.pubmed_count ?? "—", color: "#f59e0b", icon: <BookOpen size={11} /> },
            { label: "Trials", value: stats.clinical_trials_count ?? "—", color: "#ec4899", icon: <FileText size={11} /> },
            { label: "Confidence", value: `${Math.round(stats.overall_confidence * 100)}%`, color: stats.overall_confidence >= 0.7 ? "#10b981" : "#f59e0b", icon: <CheckCircle2 size={11} /> },
            { label: "Genes", value: entitiesExtracted.genes.length, color: "#6366f1", icon: <Dna size={11} /> },
            { label: "Proteins", value: entitiesExtracted.proteins.length, color: "#7c3aed", icon: <Dna size={11} /> },
            { label: "Drugs", value: entitiesExtracted.drugs.length, color: "#e11d48", icon: <Pill size={11} /> },
            { label: "Structures", value: entitiesExtracted.structures.length, color: "#0891b2", icon: <Database size={11} /> },
            { label: "Latency", value: `${(data.latency_ms / 1000).toFixed(1)}s`, color: "#6b7280", icon: <Clock size={11} /> },
          ].map((s) => (
            <div key={s.label} className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-[11px] font-semibold" style={{ background: `${s.color}08`, color: s.color, border: `1px solid ${s.color}20` }}>
              {s.icon} <span className="opacity-70">{s.label}:</span> {s.value}
            </div>
          ))}
        </div>

        {/* Export bar */}
        <div className="flex items-center gap-2 mt-4 p-3 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <span className="text-[11px] font-semibold mr-2" style={{ color: "var(--text-muted)" }}><Download size={12} className="inline mr-1" />Export:</span>
          <button onClick={() => downloadJSON(data)} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold hover:shadow-sm transition-all" style={{ background: "#3b82f610", color: "#3b82f6", border: "1px solid #3b82f620" }}><FileJson size={11} /> JSON</button>
          <button onClick={() => downloadCSV(data)} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold hover:shadow-sm transition-all" style={{ background: "#10b98110", color: "#10b981", border: "1px solid #10b98120" }}><FileSpreadsheet size={11} /> CSV</button>
          {hasLiteratureData && (
            <>
              <button onClick={() => downloadRIS(data)} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold hover:shadow-sm transition-all" style={{ background: "#8b5cf610", color: "#8b5cf6", border: "1px solid #8b5cf620" }}><BookOpen size={11} /> RIS</button>
              <button onClick={() => downloadBibTeX(data)} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold hover:shadow-sm transition-all" style={{ background: "#d9770610", color: "#d97706", border: "1px solid #d9770620" }}><FileText size={11} /> BibTeX</button>
            </>
          )}
          <button onClick={() => window.print()} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold hover:shadow-sm transition-all" style={{ background: "#6b728010", color: "#6b7280", border: "1px solid #6b728020" }}><Printer size={11} /> Print</button>
          <span className="flex-1" />
          <button onClick={onNewSearch} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold hover:shadow-sm transition-all" style={{ background: "var(--accent)", color: "#fff", border: "none" }}><RefreshCw size={11} /> New Search</button>
        </div>
      </ReportSection>

      {/* ═══════════════════════════════════════════════════
          §2 — AI EXECUTIVE SUMMARY
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={2} title="AI Executive Summary & Final Recommendation" icon={<Sparkles size={14} />} color="#8b5cf6">
        {(() => {
          // Build ref lookup from traceable summary
          const refMap: Record<number, Record<string, unknown>> = {};
          (traceableSummary.references || []).forEach((r: Record<string, unknown>) => {
            if (r.ref_num != null) refMap[Number(r.ref_num)] = r;
          });
          const hasTraceableSummary = !!(traceableSummary.summary_text);
          const displayText = hasTraceableSummary ? traceableSummary.summary_text : summary;

          // Helper: render text with [Ref N] as clickable badges
          const renderTraceableText = (text: string) => {
            const parts = text.split(/\[Ref\s*(\d+)(?:[^\]]*)?\]/g);
            return parts.map((part, idx) => {
              if (idx % 2 === 1) {
                // Odd parts are captured groups (the ref number)
                const refNum = Number(part);
                const ref = refMap[refNum];
                return (
                  <button
                    key={idx}
                    className="inline mx-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold cursor-pointer transition-all hover:shadow-sm"
                    style={{ background: refSelected === refNum ? "#8b5cf6" : "#8b5cf615", color: refSelected === refNum ? "#fff" : "#8b5cf6", border: "1px solid #8b5cf630" }}
                    onClick={() => setRefSelected(refSelected === refNum ? null : refNum)}
                    title={ref ? String(ref.title || "") : `Reference ${refNum}`}
                  >
                    [Ref {refNum}]
                  </button>
                );
              }
              // Even parts are regular text — render with section formatting
              return part.split("\n").map((line, li) => {
                const trimmed = line.trim();
                if (!trimmed) return <span key={`${idx}-${li}`} className="block h-2" />;
                if (/^[A-Z][A-Z &]{3,}$/.test(trimmed)) {
                  return <span key={`${idx}-${li}`} className="block text-[11px] font-bold uppercase tracking-wider mt-4 mb-1" style={{ color: "var(--accent, #6366f1)" }}>{trimmed}</span>;
                }
                if (/^\d+\.\s/.test(trimmed)) {
                  return <span key={`${idx}-${li}`} className="block pl-4 text-[12px]">{trimmed}</span>;
                }
                return <span key={`${idx}-${li}`} className="inline">{trimmed} </span>;
              });
            });
          };

          return displayText ? (
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#8b5cf6" }}>AI-Generated Expert Analysis</span>
                  {hasTraceableSummary && (
                    <span className="px-2 py-0.5 rounded-full text-[9px] font-bold" style={{ background: "#8b5cf615", color: "#8b5cf6", border: "1px solid #8b5cf625" }}>Gemma 4 26B · Traceable</span>
                  )}
                </div>
                <button onClick={handleCopySummary} className="flex items-center gap-1 px-2 py-1 rounded text-[10px] hover:shadow-sm transition-all" style={{ background: "var(--bg-surface)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                  <Copy size={10} /> {copiedSummary ? "Copied!" : "Copy"}
                </button>
              </div>
              {hasTraceableSummary && (
                <div className="text-[10px] mb-3" style={{ color: "var(--text-muted)" }}>
                  Click any <span className="px-1 rounded font-bold" style={{ background: "#8b5cf615", color: "#8b5cf6" }}>[Ref N]</span> citation to see the source paper.
                </div>
              )}
              <div className="text-[13px] leading-[1.8]" style={{ color: "var(--text-primary)" }}>
                {renderTraceableText(displayText)}
              </div>
              {/* Ref detail card */}
              {refSelected != null && refMap[refSelected] && (
                <div className="mt-3 p-3 rounded-lg relative" style={{ background: "var(--bg-surface)", border: "1px solid #8b5cf625", boxShadow: "0 4px 16px rgba(139,92,246,0.08)" }}>
                  <button className="absolute top-2 right-2 text-[10px]" style={{ color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer" }} onClick={() => setRefSelected(null)}>✕</button>
                  <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#8b5cf6" }}>[Ref {refSelected}]</div>
                  <div className="text-[12px] font-semibold mb-1" style={{ color: "var(--text-primary)" }}>{String(refMap[refSelected].title || "—")}</div>
                  <div className="text-[10px] mb-2" style={{ color: "var(--text-muted)" }}>
                    {String(refMap[refSelected].authors || "")}
                    {refMap[refSelected].year ? ` (${refMap[refSelected].year})` : ""}
                    {refMap[refSelected].journal ? ` · ${refMap[refSelected].journal}` : ""}
                  </div>
                  {Boolean(refMap[refSelected].key_finding) && (
                    <div className="text-[11px] italic mb-2" style={{ color: "var(--text-primary)" }}>"{String(refMap[refSelected].key_finding)}"</div>
                  )}
                  {Boolean(refMap[refSelected].doi) && (
                    <a href={`https://doi.org/${refMap[refSelected].doi}`} target="_blank" rel="noopener noreferrer" className="text-[9px] underline" style={{ color: "#3b82f6" }}>
                      DOI: {String(refMap[refSelected].doi)}
                    </a>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>AI summary unavailable — LLM not connected.</div>
          );
        })()}
      </ReportSection>

      <div className="flex flex-col gap-4" style={{ order: isLiteratureQuery ? 2 : 1 }}>
      {/* ═══════════════════════════════════════════════════
          §3 — AGENTIC EXECUTION SUMMARY
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={3} title="Agentic Execution Summary" icon={<ListChecks size={14} />} color="#0891b2">
        <div className="text-[10px] font-bold uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>Pipeline Steps Executed</div>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {[
            { label: "Multi-Source Search", detail: `${stats.sources_queried} databases, ${stats.total_results} results`, done: true },
            { label: "Entity Extraction", detail: `${stats.categories_found} categories across ${totalRows} rows`, done: true },
            { label: "Knowledge Graph", detail: `${graph.nodes.length} nodes, ${graph.edges.length} edges`, done: graph.nodes.length > 0 },
            { label: "Evidence Scoring", detail: `${Math.round(stats.overall_confidence * 100)}% confidence`, done: true },
            { label: "Disease Intelligence", detail: diseaseIntel.length > 0 ? `${diseaseIntel.length} diseases normalized` : "No diseases found", done: diseaseIntel.length > 0 },
            { label: "Target Prioritization", detail: targetRanking.length > 0 ? `${targetRanking.length} targets scored (7-signal)` : "No gene targets", done: targetRanking.length > 0 },
            { label: "Contradiction Detection", detail: `${contradictions.length} contradictions identified`, done: true },
            { label: "Structure Analysis", detail: structureData.length > 0 ? `${structureData.length} structures found` : "No structures", done: structureData.length > 0 },
            { label: "ADMET Prediction", detail: admetData.length > 0 ? `${admetData.length} molecules profiled` : "No SMILES found", done: admetData.length > 0 },
            { label: "Retrosynthesis", detail: retroData.length > 0 ? `${retroData.length} routes planned` : "No SMILES for retro", done: retroData.length > 0 },
            { label: "PICO Extraction", detail: picoData.length > 0 ? `${picoData.length} extractions` : "No suitable abstracts", done: picoData.length > 0 },
            { label: "Graph Reasoning", detail: graphReasoning.length > 0 ? `${graphReasoning.length} neighborhoods` : "No graph data", done: graphReasoning.length > 0 },
            { label: "Literature Analysis", detail: hasLiteratureData ? `${literatureTable.length} papers, ${similarities.length} similarities` : "No literature query", done: hasLiteratureData },
            { label: "AI Summary Generation", detail: summary ? "Generated" : "Skipped (no LLM)", done: !!summary },
          ].map((step) => (
            <div key={step.label} className="flex items-center gap-1.5 text-[11px]">
              {step.done ? <CheckCircle2 size={12} style={{ color: "#10b981" }} /> : <XCircle size={12} style={{ color: "#6b7280" }} />}
              <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{step.label}</span>
              <span style={{ color: "var(--text-muted)" }}>— {step.detail}</span>
            </div>
          ))}
        </div>

        {/* Timing breakdown */}
        {timings && Object.keys(timings).length > 0 && (
          <div className="mt-4">
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>Timing Breakdown</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(timings as Record<string, number>).map(([key, ms]) => (
                <div key={key} className="px-3 py-1.5 rounded text-[10px]" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                  <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{key.replace(/_/g, " ")}: </span>
                  <span className="font-mono" style={{ color: "var(--text-muted)" }}>{typeof ms === "number" ? `${ms.toFixed(0)}ms` : String(ms)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </ReportSection>

      {/* ═══════════════════════════════════════════════════
          §4 — ENTITY NORMALIZATION
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={4} title="Entity Normalization & Extraction" icon={<Hash size={14} />} color="#d97706">
        <div className="space-y-3">
          {[
            { label: "Genes / Gene Targets", items: entitiesExtracted.genes, color: "#6366f1" },
            { label: "Proteins", items: entitiesExtracted.proteins, color: "#7c3aed" },
            { label: "Diseases", items: entitiesExtracted.diseases, color: "#dc2626" },
            { label: "Drugs / Compounds", items: entitiesExtracted.drugs, color: "#e11d48" },
            { label: "Structures (PDB)", items: entitiesExtracted.structures, color: "#0891b2" },
          ].map((group) => (
            <div key={group.label}>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--text-muted)" }}>
                {group.label} ({group.items.length})
              </div>
              {group.items.length > 0 ? <TagChips items={group.items} color={group.color} /> : <span className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>None extracted</span>}
            </div>
          ))}
        </div>

        {/* Category tables (collapsible) */}
        <div className="mt-6">
          <CockpitEntityExplorer
            query={data.query}
            runId={data.run_id}
            categories={nonEmpty}
            graph={graph}
            onNavigateWithPayload={(route, payload) => {
              persistCockpitHandoff(payload);
              addToast({
                type: "success",
                title: "Cockpit handoff ready",
                message: `Context sent to ${route}.`,
              });
              navigate(route);
            }}
          />
        </div>
      </ReportSection>

      {/* ═══════════════════════════════════════════════════
          §5 — EVIDENCE ACQUISITION & QUALITY
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={5} title="Evidence Acquisition & Quality Assessment" icon={<Shield size={14} />} color="#10b981">
        <div className="card-grid">
          <div className="p-3 rounded" style={{ background: "var(--bg-surface)" }}>
            <div className="text-[10px] font-bold uppercase truncate" style={{ color: "var(--text-muted)" }}>Overall Confidence</div>
            <div className="text-2xl font-bold mt-1 truncate" style={{ color: stats.overall_confidence >= 0.7 ? "#10b981" : stats.overall_confidence >= 0.4 ? "#f59e0b" : "#ef4444" }}>
              {Math.round(stats.overall_confidence * 100)}%
            </div>
            <div className="w-full h-2 rounded-full mt-2" style={{ background: "var(--border)" }}>
              <div className="h-2 rounded-full transition-all" style={{ width: `${Math.round(stats.overall_confidence * 100)}%`, background: stats.overall_confidence >= 0.7 ? "#10b981" : stats.overall_confidence >= 0.4 ? "#f59e0b" : "#ef4444" }} />
            </div>
          </div>
          <div className="p-3 rounded" style={{ background: "var(--bg-surface)" }}>
            <div className="text-[10px] font-bold uppercase truncate" style={{ color: "var(--text-muted)" }}>Cross-Source Validation</div>
            <div className="text-2xl font-bold mt-1 truncate" style={{ color: "var(--text-primary)" }}>{stats.sources_queried}</div>
            <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>databases corroborated findings</div>
          </div>
          <div className="p-3 rounded" style={{ background: "var(--bg-surface)" }}>
            <div className="text-[10px] font-bold uppercase truncate" style={{ color: "var(--text-muted)" }}>Contradictions</div>
            <div className="text-2xl font-bold mt-1 truncate" style={{ color: stats.contradictions_count > 0 ? "#ef4444" : "#10b981" }}>{stats.contradictions_count}</div>
            <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>{stats.contradictions_count > 0 ? "cross-source conflicts" : "no conflicts detected"}</div>
          </div>
        </div>

        {/* Top citations */}
        {evidence.top_citations && evidence.top_citations.length > 0 && (
          <div className="mt-4">
            <div className="text-[10px] font-bold uppercase mb-2" style={{ color: "var(--text-muted)" }}>Top Evidence Citations</div>
            <div className="space-y-1.5">
              {evidence.top_citations.slice(0, 10).map((cit, i) => (
                <div key={i} className="flex items-start gap-2 text-[11px]" style={{ color: "var(--text-primary)" }}>
                  <span className="text-[9px] font-bold px-1.5 rounded" style={{ background: "#3b82f610", color: "#3b82f6", marginTop: 2 }}>{i + 1}</span>
                  <span className="flex-1">{(cit.title as string) || (cit.source as string) || JSON.stringify(cit).slice(0, 120)}</span>
                  {cit.url && <a href={cit.url as string} target="_blank" rel="noopener noreferrer" style={{ color: "#3b82f6" }}><ExternalLink size={10} /></a>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Source breakdown */}
        {data.source_breakdown && Object.keys(data.source_breakdown).length > 0 && (
          <div className="mt-4">
            <div className="text-[10px] font-bold uppercase mb-2" style={{ color: "var(--text-muted)" }}>Sources Breakdown</div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(data.source_breakdown).sort(([, a], [, b]) => b - a).map(([src, count]) => (
                <span key={src} className="px-2 py-1 rounded text-[10px] font-medium" style={{ background: "#10b98108", color: "#10b981", border: "1px solid #10b98120" }}>{src}: {count}</span>
              ))}
            </div>
          </div>
        )}
      </ReportSection>

      {/* ═══════════════════════════════════════════════════
          §6 — CONTRADICTION ANALYSIS
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={6} title="Contradiction & Conflict Analysis" icon={<AlertTriangle size={14} />} color="#ef4444" defaultOpen={contradictions.length > 0}>
        {contradictions.length > 0 ? (
          <div className="space-y-3">
            {contradictions.map((c, i) => {
              const srcA = (c.source_a || {}) as Record<string, unknown>;
              const srcB = (c.source_b || {}) as Record<string, unknown>;
              const sevColor = c.severity === "high" ? "#dc2626" : c.severity === "moderate" ? "#f59e0b" : "#6b7280";
              return (
                <div key={i} className="p-3 rounded-lg" style={{ background: "rgba(239, 68, 68, 0.04)", border: "1px solid rgba(239, 68, 68, 0.15)" }}>
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle size={12} style={{ color: "#ef4444" }} />
                    <span className="text-[11px] font-bold" style={{ color: "#ef4444" }}>Contradiction #{i + 1}</span>
                    {c.severity && <span className="text-[10px] px-1.5 py-0.5 rounded font-semibold" style={{ background: `${sevColor}15`, color: sevColor }}>{String(c.severity).toUpperCase()}</span>}
                  </div>
                  {c.claim_a && (
                    <div className="mb-2 p-2 rounded text-[11px]" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                      <div className="text-[10px] font-bold uppercase mb-0.5" style={{ color: "#ef4444" }}>Claim A {srcA.source ? `(${String(srcA.source)})` : ""}</div>
                      <div style={{ color: "var(--text-primary)" }}>{String(c.claim_a)}</div>
                      {srcA.title && <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>— {String(srcA.title)}{srcA.year ? ` (${String(srcA.year)})` : ""}</div>}
                    </div>
                  )}
                  {c.claim_b && (
                    <div className="mb-2 p-2 rounded text-[11px]" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                      <div className="text-[10px] font-bold uppercase mb-0.5" style={{ color: "#ef4444" }}>Claim B {srcB.source ? `(${String(srcB.source)})` : ""}</div>
                      <div style={{ color: "var(--text-primary)" }}>{String(c.claim_b)}</div>
                      {srcB.title && <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>— {String(srcB.title)}{srcB.year ? ` (${String(srcB.year)})` : ""}</div>}
                    </div>
                  )}
                  {c.explanation && <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>{String(c.explanation)}</div>}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-[11px] flex items-center gap-2" style={{ color: "#10b981" }}>
            <CheckCircle2 size={14} /> No cross-source contradictions detected. Evidence is internally consistent.
          </div>
        )}
      </ReportSection>

      {/* ═══════════════════════════════════════════════════
          §7 — DISEASE INTELLIGENCE
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={7} title="Disease Intelligence & Ontology Normalization" icon={<Activity size={14} />} color="#dc2626" defaultOpen={diseaseIntel.length > 0}>
        {diseaseIntel.length > 0 ? (
          <div className="space-y-3">
            {diseaseIntel.map((d, i) => (
              <div key={i} className="p-3 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                <div className="text-[12px] font-bold mb-2" style={{ color: "var(--text-primary)" }}>
                  {(d.preferred_name as string) || (d.original_name as string) || "Unknown Disease"}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-1">
                  <KVRow label="Original" value={String(d.original_name || "—")} />
                  <KVRow label="Preferred" value={String(d.preferred_name || "—")} />
                  <KVRow label="MeSH ID" value={String(d.mesh_id || "—")} />
                  <KVRow label="OMIM ID" value={String(d.omim_id || "—")} />
                  <KVRow label="ICD Code" value={String(d.icd_code || "—")} />
                  <KVRow label="MONDO ID" value={String(d.mondo_id || "—")} />
                </div>
                {d.synonyms && Array.isArray(d.synonyms) && (d.synonyms as string[]).length > 0 && (
                  <div className="mt-2">
                    <span className="text-[10px] font-bold uppercase" style={{ color: "var(--text-muted)" }}>Synonyms: </span>
                    <TagChips items={(d.synonyms as string[]).slice(0, 8)} color="#dc2626" />
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>No disease entities found in search results for normalization.</div>
        )}
      </ReportSection>

      {/* ═══════════════════════════════════════════════════
          §8 — TARGET PRIORITIZATION
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={8} title="Target Prioritization — 7-Signal Ranking" icon={<Target size={14} />} color="#8b5cf6" defaultOpen={targetRanking.length > 0}>
        {targetRanking.length > 0 ? (
          <div className="space-y-4">
            {targetRanking.map((t, i) => {
              const signals = (t.signals || {}) as Record<string, number>;
              const degraded = (t.degraded_signals || []) as string[];
              return (
                <div key={i} className="p-3 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                  <div className="flex items-center gap-3 mb-3">
                    <span className="flex items-center justify-center w-7 h-7 rounded-full text-[11px] font-black" style={{ background: "#8b5cf615", color: "#8b5cf6" }}>
                      {i + 1}
                    </span>
                    <span className="text-[13px] font-bold" style={{ color: "var(--text-primary)" }}>{String(t.symbol || "Unknown")}</span>
                    <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded" style={{ background: "#8b5cf610", color: "#8b5cf6" }}>
                      Score: {Number(t.composite_score || 0).toFixed(3)}
                    </span>
                    {t.ucb_score && <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>UCB: {Number(t.ucb_score).toFixed(3)}</span>}
                    {degraded.length > 0 && (
                      <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: "#f59e0b10", color: "#f59e0b", border: "1px solid #f59e0b20" }}>
                        {degraded.length} degraded signal{degraded.length > 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                  <div className="space-y-1.5">
                    {["gwas", "druggability", "pathways", "expression", "novelty", "safety", "literature"].map((sig) => (
                      <ScoreBar key={sig} label={sig} value={signals[sig] ?? 0} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>No gene/protein targets found for prioritization. Try a query mentioning specific genes or disease targets.</div>
        )}
      </ReportSection>

      {/* ═══════════════════════════════════════════════════
          §9 — KNOWLEDGE GRAPH & PATHWAY REASONING
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={9} title="Knowledge Graph & Pathway Reasoning" icon={<Network size={14} />} color="#0d9488">
        {/* Interactive force-directed graph */}
        {graph.nodes.length > 0 && (
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Interactive Graph ({graph.nodes.length} nodes, {graph.edges.length} edges)</span>
              <button
                className="text-[10px] px-3 py-1 rounded font-semibold"
                style={{ background: "var(--accent)", color: "#fff", border: "none" }}
                onClick={() => navigateWithReportHandoff("/graph", "open_in_graph", { graphNodes: graph.nodes.length, graphEdges: graph.edges.length })}
              >
                Open Full Graph →
              </button>
            </div>
            <ForceGraph
              nodes={graph.nodes}
              edges={graph.edges}
              height={350}
              onEdgeClick={(edge) => {
                const raw = (graph.edges as Array<Record<string, unknown>>).find(
                  (candidate) => String(candidate.source) === edge.source
                    && String(candidate.target) === edge.target
                    && String(candidate.label || candidate.type || "related_to") === edge.label,
                );
                setSelectedGraphEdge(raw ?? { source: edge.source, target: edge.target, label: edge.label, weight: edge.weight });
              }}
            />
            {selectedGraphEdge && (
              <div className="mt-3 p-3 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid #0d948820" }}>
                <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#0d9488" }}>Graph Edge Detail</div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  <KVRow label="Source" value={String(selectedGraphEdge.source || "—")} />
                  <KVRow label="Target" value={String(selectedGraphEdge.target || "—")} />
                  <KVRow label="Relation" value={String(selectedGraphEdge.label || selectedGraphEdge.relation || selectedGraphEdge.type || "—")} />
                  <KVRow label="Confidence" value={selectedGraphEdge.confidence ? Number(selectedGraphEdge.confidence).toFixed(3) : "—"} />
                  {selectedGraphEdge.source_db && <KVRow label="Source DB" value={String(selectedGraphEdge.source_db)} />}
                  {selectedGraphEdge.citation && <KVRow label="Citation" value={String(selectedGraphEdge.citation)} />}
                  {selectedGraphEdge.contradiction_state && <KVRow label="Contradiction" value={String(selectedGraphEdge.contradiction_state)} />}
                </div>
                {(selectedGraphEdge.provenance_sentence || selectedGraphEdge.evidence || selectedGraphEdge.summary) && (
                  <div className="mt-2 text-[11px]" style={{ color: "var(--text-primary)" }}>
                    {String(selectedGraphEdge.provenance_sentence || selectedGraphEdge.evidence || selectedGraphEdge.summary)}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Graph reasoning neighborhoods */}
        {graphReasoning.length > 0 && (
          <div className="mb-4">
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>Graph Neighborhoods Explored</div>
            {graphReasoning.map((gr, i) => (
              <div key={i} className="p-2 mb-2 rounded" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                <span className="text-[11px] font-bold" style={{ color: "var(--text-primary)" }}>{String((gr as Record<string, unknown>).entity || `Entity ${i + 1}`)}</span>
                <span className="text-[10px] ml-2" style={{ color: "var(--text-muted)" }}>
                  {JSON.stringify((gr as Record<string, unknown>).neighborhood || {}).slice(0, 200)}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Pathways */}
        {pathwaysData.length > 0 && (
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>Pathways ({pathwaysData.length})</div>
            <MiniTable
              columns={Object.keys(pathwaysData[0] || {}).filter((c) => !c.startsWith("_")).slice(0, 8)}
              rows={pathwaysData}
              maxRows={15}
            />
          </div>
        )}

        {graph.nodes.length === 0 && graphReasoning.length === 0 && pathwaysData.length === 0 && (
          <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>No graph or pathway data available for this query.</div>
        )}
      </ReportSection>

      {/* ═══════════════════════════════════════════════════
          §10 — STRUCTURE & POCKET ANALYSIS
          ═══════════════════════════════════════════════════ */}
      {(showDrugSections || isStructureQuery) && (
      <ReportSection num={10} title="Structure & Pocket Analysis" icon={<Layers size={14} />} color="#7c3aed" defaultOpen={structureData.length > 0}>
        {structureData.length > 0 ? (
          <MiniTable
            columns={Object.keys(structureData[0] || {}).filter((c) => !c.startsWith("_")).slice(0, 10)}
            rows={structureData}
            maxRows={10}
          />
        ) : (
          <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>No 3D structures found. Query structural targets (e.g., "EGFR kinase domain structure") for PDB results.</div>
        )}
      </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §11 — MOLECULE RETRIEVAL & IDEATION
          ═══════════════════════════════════════════════════ */}
      {showDrugSections && (
      <ReportSection num={11} title="Molecule Retrieval & Design Ideation" icon={<FlaskConical size={14} />} color="#d97706" defaultOpen={false}>
        {(() => {
          const molCats = nonEmpty.filter((c) => ["drugs", "molecules", "compounds"].includes(c.category));
          if (molCats.length === 0) return <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>No molecules or compounds retrieved. Search for specific drugs or compounds.</div>;
          return molCats.map((cat) => {
            const cols = (cat.columns.length > 0 ? cat.columns : Object.keys(cat.rows[0] || {})).filter((c) => !c.startsWith("_")).slice(0, 10);
            return (
              <div key={cat.category} className="mb-3">
                <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>{cat.category} ({cat.count})</div>
                <MiniTable columns={cols} rows={cat.rows} maxRows={15} />
              </div>
            );
          });
        })()}
      </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §12 — ADMET & OFF-TARGET SCREENING
          ═══════════════════════════════════════════════════ */}
      {showDrugSections && (
      <ReportSection num={12} title="ADMET & Off-Target Screening" icon={<Beaker size={14} />} color="#059669" defaultOpen={admetData.length > 0}>
        {admetData.length > 0 ? (
          <div className="space-y-4">
            {admetData.map((entry, i) => {
              const phys = (entry.physichem || {}) as Record<string, unknown>;
              const admet = (entry.admet || {}) as Record<string, unknown>;
              return (
                <div key={i} className="p-3 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                  <div className="text-[11px] font-mono font-bold mb-2" style={{ color: "#059669" }}>
                    {String(entry.smiles || `Molecule ${i + 1}`).slice(0, 60)}
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-[10px] font-bold uppercase mb-1" style={{ color: "var(--text-muted)" }}>Physicochemical</div>
                      {Object.entries(phys).map(([k, v]) => (
                        <KVRow key={k} label={k} value={v == null ? "—" : typeof v === "number" ? v.toFixed(2) : String(v)} />
                      ))}
                    </div>
                    <div>
                      <div className="text-[10px] font-bold uppercase mb-1" style={{ color: "var(--text-muted)" }}>ADMET Prediction</div>
                      {Object.entries(admet).map(([k, v]) => (
                        <KVRow key={k} label={k} value={v == null ? "—" : typeof v === "object" ? JSON.stringify(v).slice(0, 60) : String(v)} />
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>No molecules with SMILES found for ADMET prediction. Results are available when compounds with structural data are present.</div>
        )}
      </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §13 — RETROSYNTHESIS
          ═══════════════════════════════════════════════════ */}
      {showRetro && (
      <ReportSection num={13} title="Retrosynthesis Route Planning" icon={<GitBranch size={14} />} color="#0891b2" defaultOpen={retroData.length > 0}>
        {retroData.length > 0 ? (
          <div className="space-y-3">
            {retroData.map((route, i) => {
              const steps = ((route as Record<string, unknown>).steps || []) as Array<Record<string, unknown>>;
              const status = String((route as Record<string, unknown>).status || "unknown");
              return (
                <div key={i} className="p-3 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[11px] font-bold" style={{ color: "var(--text-primary)" }}>
                      Target: {String((route as Record<string, unknown>).target || `Molecule ${i + 1}`).slice(0, 60)}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: status === "success" ? "#10b98110" : "#f59e0b10", color: status === "success" ? "#10b981" : "#f59e0b", border: `1px solid ${status === "success" ? "#10b98120" : "#f59e0b20"}` }}>
                      {status}
                    </span>
                    <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>{steps.length} step{steps.length !== 1 ? "s" : ""}</span>
                  </div>
                  {steps.length > 0 && (
                    <div className="space-y-1">
                      {steps.map((step, si) => (
                        <div key={si} className="flex items-center gap-2 text-[10px] pl-4" style={{ color: "var(--text-primary)" }}>
                          <span className="font-bold" style={{ color: "#0891b2" }}>Step {si + 1}:</span>
                          <span>{String(step.name || step.reaction_name || "")}</span>
                          {step.confidence && <span className="font-mono" style={{ color: "var(--text-muted)" }}>({Number(step.confidence).toFixed(2)})</span>}
                          {step.precursors && <span className="font-mono text-[9px]" style={{ color: "var(--text-muted)" }}>→ {Array.isArray(step.precursors) ? (step.precursors as string[]).join(" + ") : String(step.precursors)}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>No SMILES available for retrosynthesis analysis. Requires molecules with structural data.</div>
        )}
      </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §14 — TRANSLATIONAL & POPULATION CONTEXT
          ═══════════════════════════════════════════════════ */}
      {showClinical && (
      <ReportSection num={14} title="Translational & Clinical Context" icon={<Syringe size={14} />} color="#ec4899">
        {/* Clinical trials */}
        {trialsData.length > 0 && (
          <div className="mb-4">
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>Clinical Trials ({trialsData.length})</div>
            <MiniTable
              columns={Object.keys(trialsData[0] || {}).filter((c) => !c.startsWith("_")).slice(0, 8)}
              rows={trialsData}
              maxRows={10}
            />
          </div>
        )}

        {/* PICO extractions */}
        {picoData.length > 0 && (
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>PICO Extraction from Literature</div>
            {picoData.map((p, i) => {
              const pico = ((p as Record<string, unknown>).pico || {}) as Record<string, string>;
              return (
                <div key={i} className="p-3 mb-2 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                  <div className="text-[11px] font-bold mb-2" style={{ color: "var(--text-primary)" }}>{String((p as Record<string, unknown>).title || `Abstract ${i + 1}`)}</div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                    <KVRow label="Population" value={pico.population || "—"} />
                    <KVRow label="Intervention" value={pico.intervention || "—"} />
                    <KVRow label="Comparator" value={pico.comparator || "—"} />
                    <KVRow label="Outcome" value={pico.outcome || "—"} />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {trialsData.length === 0 && picoData.length === 0 && (
          <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>No clinical trials or PICO data available for this query.</div>
        )}

        {/* Population genomics */}
        {(populationData.gnomad?.length > 0 || populationData.indigen?.length > 0 || populationData.genome_asia?.length > 0) && (
          <div className="mt-4">
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#0891b2" }}>
              <Globe size={12} className="inline mr-1" /> Population Genomics
              {queryClassification.cohort && <span className="ml-2 px-2 py-0.5 rounded-full text-[9px]" style={{ background: "#0891b210", border: "1px solid #0891b220" }}>{queryClassification.cohort} cohort emphasis</span>}
            </div>
            {populationData.gnomad?.length > 0 && (
              <div className="mb-3">
                <div className="text-[10px] font-semibold mb-1" style={{ color: "var(--text-muted)" }}>gnomAD Constraint ({populationData.gnomad.length})</div>
                <MiniTable
                  columns={Object.keys((populationData.gnomad[0] as Record<string, unknown>) || {}).filter((c) => !c.startsWith("_")).slice(0, 8)}
                  rows={populationData.gnomad as Array<Record<string, unknown>>}
                  maxRows={5}
                />
              </div>
            )}
            {populationData.indigen?.length > 0 && (
              <div className="mb-3">
                <div className="text-[10px] font-semibold mb-1" style={{ color: "var(--text-muted)" }}>IndiGen Indian Variants ({populationData.indigen.length})</div>
                <MiniTable
                  columns={Object.keys((populationData.indigen[0] as Record<string, unknown>) || {}).filter((c) => !c.startsWith("_")).slice(0, 8)}
                  rows={populationData.indigen as Array<Record<string, unknown>>}
                  maxRows={5}
                />
              </div>
            )}
            {populationData.genome_asia?.length > 0 && (
              <div className="mb-3">
                <div className="text-[10px] font-semibold mb-1" style={{ color: "var(--text-muted)" }}>GenomeAsia ({populationData.genome_asia.length})</div>
                <MiniTable
                  columns={Object.keys((populationData.genome_asia[0] as Record<string, unknown>) || {}).filter((c) => !c.startsWith("_")).slice(0, 8)}
                  rows={populationData.genome_asia as Array<Record<string, unknown>>}
                  maxRows={5}
                />
              </div>
            )}
          </div>
        )}
      </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §15 — NEXT-STEP PROGRAM
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={15} title="Recommended Next Steps" icon={<TrendingUp size={14} />} color="#f59e0b" defaultOpen={false}>
        <div className="space-y-2">
          {[
            targetRanking.length > 0 && { step: "Validate top-ranked targets", detail: `Run disease workbench for ${String((targetRanking[0] as Record<string, unknown>).symbol || "top targets")} with genetic and functional assays.`, action: () => navigate(`/targets?q=${encodeURIComponent(data.query)}`) },
            admetData.length > 0 && { step: "Optimize lead compounds", detail: "Run analog generation and scaffold hopping on ADMET-profiled molecules in Design Studio.", action: () => navigate(`/design?q=${encodeURIComponent(data.query)}`) },
            structureData.length > 0 && { step: "Structure-based drug design", detail: "Perform molecular docking against identified PDB structures.", action: () => navigate(`/structure?q=${encodeURIComponent(data.query)}`) },
            { step: "Build decision dossier", detail: "Compile all findings into a reproducible dossier for team review.", action: () => navigate(`/dossier?q=${encodeURIComponent(data.query)}`) },
            { step: "Deep evidence search", detail: "Explore full literature and evidence with advanced filters.", action: () => navigate(`/search?q=${encodeURIComponent(data.query)}`) },
            graph.nodes.length > 0 && { step: "Explore knowledge graph", detail: "Navigate entity relationships and pathway connections.", action: () => navigate(`/graph?q=${encodeURIComponent(data.query)}`) },
          ].filter(Boolean).map((item, i) => {
            const it = item as { step: string; detail: string; action: () => void };
            return (
              <div key={i} className="flex items-center gap-3 p-3 rounded-lg hover:shadow-sm transition-all cursor-pointer" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }} onClick={it.action}>
                <span className="flex items-center justify-center w-6 h-6 rounded-full text-[10px] font-black shrink-0" style={{ background: "#f59e0b15", color: "#f59e0b" }}>{i + 1}</span>
                <div className="flex-1">
                  <div className="text-[12px] font-bold" style={{ color: "var(--text-primary)" }}>{it.step}</div>
                  <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{it.detail}</div>
                </div>
                <ExternalLink size={12} style={{ color: "var(--text-muted)" }} />
              </div>
            );
          })}
        </div>
      </ReportSection>

      {/* ═══════════════════════════════════════════════════
          §16 — SCENARIO COMPARISON (SynthArena)
          ═══════════════════════════════════════════════════ */}
      {showSynthArena && (
      <ReportSection num={16} title="Scenario Comparison (SynthArena)" icon={<Microscope size={14} />} color="#0d9488" defaultOpen={Object.keys(syntharenaData).length > 0}>
        {/* Inline SynthArena comparison results */}
        {Object.keys(syntharenaData).length > 0 && (
          <div className="mb-4">
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#0d9488" }}>Scenario Comparison Results</div>
            {syntharenaData.scorecard && Array.isArray((syntharenaData.scorecard as Record<string, unknown>[]) || []) && (
              <MiniTable
                columns={Object.keys(((syntharenaData.scorecard as Record<string, unknown>[])[0]) || {}).filter((c) => !c.startsWith("_")).slice(0, 10)}
                rows={syntharenaData.scorecard as Record<string, unknown>[]}
                maxRows={10}
              />
            )}
            {syntharenaData.winner && (
              <div className="mt-2 p-2 rounded" style={{ background: "#0d948810", border: "1px solid #0d948820" }}>
                <span className="text-[11px] font-bold" style={{ color: "#0d9488" }}>Winner: </span>
                <span className="text-[11px]" style={{ color: "var(--text-primary)" }}>{String(syntharenaData.winner)}</span>
              </div>
            )}
            {syntharenaData.rationale && (
              <div className="mt-1 text-[11px]" style={{ color: "var(--text-primary)" }}>{String(syntharenaData.rationale)}</div>
            )}
          </div>
        )}
        {targetRanking.length >= 2 ? (
          <div>
            <div className="text-[11px] mb-3" style={{ color: "var(--text-primary)" }}>
              Compare top-ranked targets in SynthArena for multi-dimensional scenario evaluation (genetic support, druggability, pathway coherence, ADMET, literature, population context).
            </div>
            <button
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[11px] font-semibold"
              style={{ background: "#0d9488", color: "#fff", border: "none", cursor: "pointer" }}
              onClick={() => {
                const targets = targetRanking.slice(0, 3).map((t) => String((t as Record<string, unknown>).symbol || "")).filter(Boolean).join(",");
                navigate(`/syntharena?targets=${encodeURIComponent(targets)}&q=${encodeURIComponent(data.query)}`);
              }}
            >
              <Microscope size={12} /> Launch SynthArena Comparison →
            </button>
          </div>
        ) : (
          <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>Need ≥2 ranked targets for scenario comparison. Run a query yielding gene/protein targets.</div>
        )}
      </ReportSection>
      )}
      </div>

      <div className="flex flex-col gap-4" style={{ order: isLiteratureQuery ? 1 : 2 }}>
      {/* ═══════════════════════════════════════════════════
          §17 — LITERATURE TABLE (All Papers)
          ═══════════════════════════════════════════════════ */}
      {hasLiteratureData && (
        <ReportSection num={17} title={`Literature Table (${literatureTable.length} papers)`} icon={<BookOpen size={14} />} color="#3b82f6" defaultOpen={true}>
          {/* Literature stats banner */}
          {Object.keys(literatureStats).length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {literatureStats.total_fetched && <span className="px-2.5 py-1 rounded text-[10px] font-medium" style={{ background: "#3b82f608", color: "#3b82f6", border: "1px solid #3b82f620" }}>Fetched: {String(literatureStats.total_fetched)}</span>}
              {literatureStats.total_unique && <span className="px-2.5 py-1 rounded text-[10px] font-medium" style={{ background: "#10b98108", color: "#10b981", border: "1px solid #10b98120" }}>Unique: {String(literatureStats.total_unique)}</span>}
              {Array.isArray(literatureStats.sources) && (literatureStats.sources as string[]).map((s: string) => (
                <span key={s} className="px-2 py-1 rounded text-[10px]" style={{ background: "#6b728008", color: "#6b7280", border: "1px solid #6b728020" }}>{s}</span>
              ))}
            </div>
          )}
          <MiniTable
            columns={["sno", "id", "title", "authors", "year", "journal", "summary", "citation_count", "relevance_score", "methodology_context", "source", "doi_url"]}
            rows={literatureTable}
            maxRows={30}
          />
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §18 — USER-SPECIFIED LITERATURE
          ═══════════════════════════════════════════════════ */}
      {filteredLiterature.length > 0 && (
        <ReportSection num={18} title={`User-Specified Literature — ${String(filterInfo.filter_type || "Filtered")} (${filteredLiterature.length})`} icon={<FileSearch size={14} />} color="#8b5cf6" defaultOpen={true}>
          <div className="mb-2">
            {filterInfo.filter_terms && Array.isArray(filterInfo.filter_terms) && <TagChips items={filterInfo.filter_terms as string[]} color="#8b5cf6" />}
          </div>
          <MiniTable
            columns={["sno", "id", "title", "authors", "year", "specific_data", "citation_count", "relevance_score", "source"]}
            rows={filteredLiterature}
            maxRows={20}
          />
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §3 — LLM-VERIFIED CONTRADICTIONS (Gemma 4)
          ═══════════════════════════════════════════════════ */}
      {llmContradictions.length > 0 && (
        <ReportSection num={3} title={`⚡ Contradictions — Paper A vs Paper B (${llmContradictions.length})`} icon={<AlertTriangle size={14} />} color="#dc2626" defaultOpen={true}>
          <div className="space-y-3">
            {llmContradictions.map((c, i) => {
              const sevColor = c.severity === "high" ? "#dc2626" : c.severity === "moderate" ? "#f59e0b" : "#6b7280";
              return (
                <div key={i} className="p-3 rounded-lg" style={{ background: "rgba(220, 38, 38, 0.04)", border: "1px solid rgba(220, 38, 38, 0.15)" }}>
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <AlertTriangle size={12} style={{ color: "#dc2626" }} />
                    <span className="text-[11px] font-bold" style={{ color: "#dc2626" }}>⚡</span>
                    <span className="text-[11px] font-semibold" style={{ color: "var(--text-primary)" }}>
                      {String(c.source_a?.title || c.paper_a?.title || `Paper A`).slice(0, 60)}{String(c.source_a?.title || c.paper_a?.title || "").length > 60 ? "…" : ""}
                    </span>
                    <span className="text-[11px] font-bold mx-1" style={{ color: "#dc2626" }}>VS</span>
                    <span className="text-[11px] font-semibold" style={{ color: "var(--text-primary)" }}>
                      {String(c.source_b?.title || c.paper_b?.title || `Paper B`).slice(0, 60)}{String(c.source_b?.title || c.paper_b?.title || "").length > 60 ? "…" : ""}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded font-semibold ml-auto" style={{ background: `${sevColor}15`, color: sevColor }}>{String(c.severity).toUpperCase()}</span>
                    {c.llm_verified && <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "#6b728015", color: "#6b7280" }}>🤖 LLM-Verified</span>}
                  </div>
                  {/* Experimental context per spec */}
                  {(c.context_a || c.context_b) && (
                    <div className="mb-2 text-[10px] px-2 py-1.5 rounded" style={{ background: "#dc262608", border: "1px solid #dc262615", color: "var(--text-muted)" }}>
                      <span className="font-bold" style={{ color: "#dc2626" }}>Experimental Context: </span>
                      {c.context_a?.study_type && <>Paper A: {c.context_a.study_type}{c.context_a?.model_organisms?.length ? ` (${(c.context_a.model_organisms as string[]).join(", ")})` : ""}</>}
                      {c.context_b?.study_type && <>{c.context_a?.study_type ? " · " : ""}Paper B: {c.context_b.study_type}{c.context_b?.model_organisms?.length ? ` (${(c.context_b.model_organisms as string[]).join(", ")})` : ""}</>}
                    </div>
                  )}

                  {/* Paper A claim */}
                  <div className="mb-2 p-2 rounded text-[11px]" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                    <div className="text-[10px] font-bold uppercase mb-0.5" style={{ color: "#ef4444" }}>
                      Paper A — {c.context_a?.study_type || "unknown"} {c.context_a?.model_organisms?.length ? `(${c.context_a.model_organisms.join(", ")})` : ""}
                    </div>
                    <div style={{ color: "var(--text-primary)" }}>{c.claim_a}</div>
                    {c.source_a?.title && <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>— {c.source_a.title}{c.source_a.year ? ` (${c.source_a.year})` : ""}</div>}
                    {c.context_a?.methodologies?.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {c.context_a.methodologies.map((m: string, mi: number) => (
                          <span key={mi} className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "#10b98110", color: "#10b981", border: "1px solid #10b98120" }}>{m}</span>
                        ))}
                      </div>
                    )}
                    {c.context_a?.cell_lines?.length > 0 && (
                      <div className="text-[9px] mt-0.5" style={{ color: "var(--text-muted)" }}>Cell lines: {c.context_a.cell_lines.join(", ")}</div>
                    )}
                  </div>

                  {/* Paper B claim */}
                  <div className="mb-2 p-2 rounded text-[11px]" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                    <div className="text-[10px] font-bold uppercase mb-0.5" style={{ color: "#ef4444" }}>
                      Paper B — {c.context_b?.study_type || "unknown"} {c.context_b?.model_organisms?.length ? `(${c.context_b.model_organisms.join(", ")})` : ""}
                    </div>
                    <div style={{ color: "var(--text-primary)" }}>{c.claim_b}</div>
                    {c.source_b?.title && <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>— {c.source_b.title}{c.source_b.year ? ` (${c.source_b.year})` : ""}</div>}
                    {c.context_b?.methodologies?.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {c.context_b.methodologies.map((m: string, mi: number) => (
                          <span key={mi} className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "#10b98110", color: "#10b981", border: "1px solid #10b98120" }}>{m}</span>
                        ))}
                      </div>
                    )}
                    {c.context_b?.cell_lines?.length > 0 && (
                      <div className="text-[9px] mt-0.5" style={{ color: "var(--text-muted)" }}>Cell lines: {c.context_b.cell_lines.join(", ")}</div>
                    )}
                  </div>

                  {/* Why they differ */}
                  <div className="text-[11px] p-2 rounded" style={{ background: "#f59e0b08", border: "1px solid #f59e0b20" }}>
                    <div className="font-bold text-[10px] uppercase mb-0.5" style={{ color: "#f59e0b" }}>Why They Differ</div>
                    <div style={{ color: "var(--text-primary)" }}>{c.reason || c.explanation}</div>
                    {c.reliability_judgment && (
                      <div className="mt-1.5 text-[10px]" style={{ color: "var(--text-muted)" }}>
                        <span className="font-bold uppercase">Reliability: </span>{c.reliability_judgment}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §4 — SIMILARITIES (Paper A ~ Paper B)
          ═══════════════════════════════════════════════════ */}
      {similarities.length > 0 && (
        <ReportSection num={4} title={`🤝 Similarities — Paper A ~ Paper B (${similarities.length} pairs)`} icon={<Layers size={14} />} color="#0891b2" defaultOpen={true}>
          <div className="space-y-2">
            {similarities.slice(0, 20).map((sim, i) => {
              const pA = (sim.paper_a || {}) as Record<string, unknown>;
              const pB = (sim.paper_b || {}) as Record<string, unknown>;
              const score = (sim.similarity_score ?? sim.similarity ?? 0) as number;
              return (
                <div key={i} className="p-3 rounded-lg" style={{ background: "#0891b204", border: "1px solid #0891b215" }}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-[10px] font-bold px-1.5 rounded" style={{ background: "#0891b215", color: "#0891b2" }}>~ {(score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-[11px]">
                    <div className="p-2 rounded" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                      <div className="font-bold text-[10px] uppercase mb-0.5" style={{ color: "#0891b2" }}>Paper A</div>
                      <div style={{ color: "var(--text-primary)" }}>{String(pA.title || sim.paper_a_title || "—")}</div>
                      <div className="text-[10px] mt-0.5" style={{ color: "var(--text-muted)" }}>
                        {Array.isArray(pA.authors) ? (pA.authors as string[]).join(", ") : String(sim.paper_a_source || "")}
                        {(pA.year || sim.paper_a_year) ? ` (${pA.year || sim.paper_a_year})` : ""}
                      </div>
                    </div>
                    <div className="p-2 rounded" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                      <div className="font-bold text-[10px] uppercase mb-0.5" style={{ color: "#0891b2" }}>Paper B</div>
                      <div style={{ color: "var(--text-primary)" }}>{String(pB.title || sim.paper_b_title || "—")}</div>
                      <div className="text-[10px] mt-0.5" style={{ color: "var(--text-muted)" }}>
                        {Array.isArray(pB.authors) ? (pB.authors as string[]).join(", ") : String(sim.paper_b_source || "")}
                        {(pB.year || sim.paper_b_year) ? ` (${pB.year || sim.paper_b_year})` : ""}
                      </div>
                    </div>
                  </div>
                  {sim.shared_terms && Array.isArray(sim.shared_terms) && (
                    <div className="mt-1.5"><TagChips items={(sim.shared_terms as string[]).slice(0, 10)} color="#0891b2" /></div>
                  )}
                </div>
              );
            })}
          </div>
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §5 — NUANCED RELATIONSHIPS
          ═══════════════════════════════════════════════════ */}
      {nuancedRelationships.length > 0 && (
        <ReportSection num={5} title={`Nuanced Relationships (${nuancedRelationships.length})`} icon={<GitBranch size={14} />} color="#d97706" defaultOpen={true}>
          <div className="space-y-2">
            {nuancedRelationships.map((rel, i) => {
              const typeIcons: Record<string, string> = {
                refines: "🔬",
                fails_to_replicate: "❌",
                uses_methodology_from: "🧪",
                expands_to_new_model: "🌐",
                complementary_evidence: "🔄",
                shared_topic: "🧬",
                similar: "🤝",
                contradict: "⚡",
              };
              const typeColors: Record<string, string> = {
                refines: "#10b981",
                fails_to_replicate: "#ef4444",
                uses_methodology_from: "#3b82f6",
                expands_to_new_model: "#8b5cf6",
                complementary_evidence: "#0d9488",
                shared_topic: "#6366f1",
                similar: "#f59e0b",
                contradict: "#dc2626",
              };
              const rType = String(rel.relationship_type || "unknown");
              const icon = typeIcons[rType] || String(rel.icon || "🔗");
              const color = typeColors[rType] || "#6b7280";
              const pA = (rel.paper_a || {}) as Record<string, unknown>;
              const pB = (rel.paper_b || {}) as Record<string, unknown>;
              return (
                <div key={i} className="p-3 rounded-lg" style={{ background: `${color}04`, border: `1px solid ${color}15` }}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">{icon}</span>
                    <span className="text-[11px] font-bold uppercase" style={{ color }}>{rType.replace(/_/g, " ")}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-[11px]">
                    <div className="p-2 rounded" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                      <div className="font-bold" style={{ color: "var(--text-primary)" }}>{String(pA.title || rel.paper_a_title || "Paper A")}</div>
                      <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{String(pA.year || rel.paper_a_year || "")}</div>
                    </div>
                    <div className="p-2 rounded" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                      <div className="font-bold" style={{ color: "var(--text-primary)" }}>{String(pB.title || rel.paper_b_title || "Paper B")}</div>
                      <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{String(pB.year || rel.paper_b_year || "")}</div>
                    </div>
                  </div>
                  {(rel.explanation || rel.evidence) && <div className="text-[10px] mt-1.5 italic" style={{ color: "var(--text-muted)" }}>{String(rel.explanation || rel.evidence)}</div>}
                </div>
              );
            })}
          </div>
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §6 — TERMS MAP
          ═══════════════════════════════════════════════════ */}
      {Object.keys(termsMap).length > 0 && (
        <ReportSection num={6} title="Terms Map" icon={<Hash size={14} />} color="#059669" defaultOpen={true}>
          <div className="space-y-3">
            {Object.entries(termsMap).map(([category, terms]) => {
              // Backend returns dict {term: count} OR array — handle both
              let termItems: Array<{ term: string; count: number }> = [];
              if (Array.isArray(terms)) {
                termItems = (terms as Array<Record<string, unknown>>).map(t =>
                  typeof t === "string" ? { term: t, count: 0 } : { term: String(t.term || t), count: Number(t.count || 0) }
                );
              } else if (terms && typeof terms === "object") {
                termItems = Object.entries(terms as Record<string, number>).map(([term, count]) => ({ term, count: Number(count) || 0 }));
              }
              if (termItems.length === 0 || category === "total_papers_analyzed" || category === "top_terms") return null;
              // Sort by count descending
              termItems.sort((a, b) => b.count - a.count);
              const catColors: Record<string, string> = { genes: "#6366f1", drugs: "#e11d48", diseases: "#dc2626", methods: "#10b981", pathways: "#0891b2" };
              const color = catColors[category] || "#6b7280";
              return (
                <div key={category}>
                  <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color }}>{category} ({termItems.length})</div>
                  <div className="flex flex-wrap gap-1.5">
                    {termItems.slice(0, 30).map((t, ti) => (
                      <span key={ti} className="px-2.5 py-1 rounded-full text-[10px] font-medium" style={{ background: `${color}10`, color, border: `1px solid ${color}20` }}>
                        {t.term} {t.count > 0 ? <span className="opacity-60">×{t.count}</span> : ""}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          {/* Term frequency top items */}
          {Object.keys(termFrequency).length > 0 && (
            <div className="mt-4">
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>Top Term Frequencies</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(termFrequency).sort(([, a], [, b]) => b - a).slice(0, 20).map(([term, freq]) => (
                  <span key={term} className="px-2 py-1 rounded text-[10px] font-mono" style={{ background: "#05966908", color: "#059669", border: "1px solid #05966920" }}>{term}: {freq}</span>
                ))}
              </div>
            </div>
          )}
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §7 — LITERATURE KNOWLEDGE GRAPH
          ═══════════════════════════════════════════════════ */}
      {literatureKG && (literatureKG.nodes as Array<Record<string, unknown>> || []).length > 0 && (
        <ReportSection num={7} title="Literature Knowledge Graph" icon={<Network size={14} />} color="#6366f1" defaultOpen={true}>
          <div className="mb-3">
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
              Graph: {(literatureKG.nodes as Array<Record<string, unknown>>).length} nodes, {(literatureKG.edges as Array<Record<string, unknown>> || []).length} edges
            </div>
            {/* Category legend */}
            <div className="flex flex-wrap gap-2 mb-3">
              {[
                { label: "Gene", color: "#6366f1" },
                { label: "Drug", color: "#e11d48" },
                { label: "Disease", color: "#dc2626" },
                { label: "Method", color: "#10b981" },
                { label: "Pathway", color: "#0891b2" },
                { label: "Paper", color: "#f59e0b" },
              ].map((cat) => (
                <span key={cat.label} className="flex items-center gap-1 text-[10px]">
                  <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: cat.color }} />
                  <span style={{ color: "var(--text-muted)" }}>{cat.label}</span>
                </span>
              ))}
            </div>
            {/* Interactive force-directed literature KG */}
            <ForceGraph
              nodes={(literatureKG.nodes as Array<Record<string, unknown>>).map((n) => ({
                id: String(n.id || ""),
                label: String(n.label || n.id || ""),
                type: String(n.type || "unknown"),
              }))}
              edges={(literatureKG.edges as Array<Record<string, unknown>> || []).map((e) => ({
                source: String(e.source || ""),
                target: String(e.target || ""),
                label: String(e.relation || e.type || ""),
                weight: Number(e.weight || 1),
              }))}
              height={400}
              onEdgeClick={(edge) => {
                const raw = (literatureKG.edges as Array<Record<string, unknown>> || []).find(
                  (re) => String(re.source) === edge.source && String(re.target) === edge.target
                );
                setSelectedEdge(selectedEdge === raw ? null : raw ?? null);
              }}
            />
          </div>
          {/* Edges summary — clickable for detail popover */}
          {(literatureKG.edges as Array<Record<string, unknown>> || []).length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--text-muted)" }}>Key Connections (click for detail)</div>
              <div className="space-y-1">
                {(literatureKG.edges as Array<Record<string, unknown>>).slice(0, 20).map((edge, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-[10px] cursor-pointer rounded px-1.5 py-1 transition-all hover:shadow-sm"
                    style={{ color: "var(--text-primary)", background: selectedEdge === edge ? "#6366f108" : "transparent", border: selectedEdge === edge ? "1px solid #6366f125" : "1px solid transparent" }}
                    onClick={() => setSelectedEdge(selectedEdge === edge ? null : edge)}
                  >
                    <span className="font-semibold" style={{ color: "#6366f1" }}>{String(edge.source)}</span>
                    <span style={{ color: "var(--text-muted)" }}>→</span>
                    <span className="px-1.5 py-0.5 rounded text-[9px]" style={{ background: "var(--bg-surface)", color: "var(--text-muted)" }}>{String(edge.relation || edge.type || "—")}</span>
                    <span style={{ color: "var(--text-muted)" }}>→</span>
                    <span className="font-semibold" style={{ color: "#6366f1" }}>{String(edge.target)}</span>
                    {edge.weight && <span className="text-[9px] font-mono" style={{ color: "var(--text-muted)" }}>({Number(edge.weight).toFixed(1)})</span>}
                  </div>
                ))}
              </div>
              {/* Edge detail popover */}
              {selectedEdge && (
                <div className="mt-2 p-3 rounded-lg relative" style={{ background: "var(--bg-surface)", border: "1px solid #6366f125", boxShadow: "0 4px 16px rgba(99,102,241,0.08)" }}>
                  <button className="absolute top-2 right-2 text-[10px]" style={{ color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer" }} onClick={() => setSelectedEdge(null)}>✕</button>
                  <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#6366f1" }}>Edge Detail</div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                    <KVRow label="Source" value={String(selectedEdge.source || "—")} />
                    <KVRow label="Target" value={String(selectedEdge.target || "—")} />
                    <KVRow label="Relation" value={String(selectedEdge.relation || selectedEdge.type || "—")} />
                    <KVRow label="Weight" value={selectedEdge.weight ? Number(selectedEdge.weight).toFixed(3) : "—"} />
                    {selectedEdge.paper_title && <KVRow label="Paper" value={String(selectedEdge.paper_title)} />}
                    {selectedEdge.doi && <KVRow label="DOI" value={<a href={`https://doi.org/${selectedEdge.doi}`} target="_blank" rel="noopener noreferrer" className="underline" style={{ color: "#3b82f6" }}>{String(selectedEdge.doi)}</a>} />}
                    {selectedEdge.evidence && <KVRow label="Evidence" value={String(selectedEdge.evidence)} />}
                  </div>
                </div>
              )}
            </div>
          )}
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §8 — STRUCTURES GRID (SMILES / Protein Sequences)
          ═══════════════════════════════════════════════════ */}
      {(litStructures as Array<Record<string, unknown>>).length > 0 && (
        <ReportSection num={26} title={`Structures Grid (${(litStructures as Array<Record<string, unknown>>).length})`} icon={<Beaker size={14} />} color="#e11d48" defaultOpen={true}>
          <div className="card-grid">
            {(litStructures as Array<Record<string, unknown>>).map((struct, si) => {
              const isSmiles = struct.type === "smiles";
              const color = isSmiles ? "#e11d48" : "#8b5cf6";
              return (
                <div key={si} className="p-3 rounded-lg" style={{ background: `${color}04`, border: `1px solid ${color}15` }}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase" style={{ background: `${color}12`, color }}>
                      {isSmiles ? "SMILES" : "Protein Seq"}
                    </span>
                    {struct.drug_name && (
                      <span className="text-[11px] font-bold" style={{ color: "var(--text-primary)" }}>{String(struct.drug_name)}</span>
                    )}
                    {struct.source === "pubchem" && (
                      <span className="px-1.5 py-0.5 rounded text-[8px] font-medium" style={{ background: "#22c55e12", color: "#22c55e" }}>PubChem</span>
                    )}
                  </div>
                  {/* Structure value — 2D rendering for SMILES, monospace for protein */}
                  {isSmiles ? (
                    <div className="p-2 rounded flex flex-col items-center" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                      <SmilesRenderer smiles={String(struct.value || "")} width={220} height={160} theme="dark" />
                      <div className="font-mono text-[9px] mt-1 break-all text-center" style={{ color: "var(--text-muted)" }}>
                        {String(struct.value || "—").slice(0, 80)}{String(struct.value || "").length > 80 ? "…" : ""}
                      </div>
                    </div>
                  ) : (
                    <div className="font-mono text-[10px] p-2 rounded break-all leading-relaxed max-h-24 overflow-y-auto" style={{ background: "var(--bg-surface)", color: "var(--text-primary)", border: "1px solid var(--border)" }}>
                      {String(struct.value || "—")}
                    </div>
                  )}
                  {/* Paper source */}
                  <div className="mt-2 text-[10px]" style={{ color: "var(--text-muted)" }}>
                    {struct.paper_title && <div className="font-semibold" style={{ color: "var(--text-primary)" }}>{String(struct.paper_title)}</div>}
                    {struct.doi && (
                      <a href={`https://doi.org/${struct.doi}`} target="_blank" rel="noopener noreferrer" className="underline text-[9px]" style={{ color: "#3b82f6" }}>
                        {String(struct.doi)}
                      </a>
                    )}
                  </div>
                  {/* Context sentence */}
                  {struct.context && (
                    <div className="mt-1.5 text-[10px] italic" style={{ color: "var(--text-muted)" }}>
                      "{String(struct.context).slice(0, 200)}{String(struct.context).length > 200 ? "…" : ""}"
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §9 — UNIFIED PATHWAYS DIAGRAM (ForceGraph)
          ═══════════════════════════════════════════════════ */}
      {unifiedPathways.nodes?.length > 0 && (
        <ReportSection num={9} title={`Unified Pathways (${unifiedPathways.total_nodes} terms, ${unifiedPathways.total_edges} connections)`} icon={<GitBranch size={14} />} color="#0891b2" defaultOpen={true}>
          <div className="flex justify-end mb-3">
            <button
              className="text-[10px] px-3 py-1 rounded font-semibold"
              style={{ background: "#0891b2", color: "#fff", border: "none" }}
              onClick={() => navigateWithReportHandoff("/pathways", "open_in_pathways", {
                pathwayIds: unifiedPathways.nodes.map((node: any) => String(node.id || node.label)).slice(0, 24),
                pathwayLayers: unifiedPathways.pathway_layers?.map((layer: any) => layer.label) || [],
              })}
            >
              Open Pathways →
            </button>
          </div>
          {/* Layer legend */}
          {unifiedPathways.pathway_layers?.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {unifiedPathways.pathway_layers.map((layer: any, i: number) => (
                <span key={i} className="px-2.5 py-1 rounded-full text-[10px] font-medium" style={{ background: `${layer.color}10`, color: layer.color, border: `1px solid ${layer.color}20` }}>
                  ● {layer.label} ({layer.node_count})
                </span>
              ))}
            </div>
          )}
          {/* Force-directed pathway diagram */}
          {(() => {
            const pathwayGraphNodes = unifiedPathways.nodes.map((n: any) => ({
              id: n.id || `${n.layer}:${n.label}`,
              label: n.label,
              type: n.layer || "pathway",
            }));
            const pathwayGraphEdges = (unifiedPathways.edges || []).map((e: any) => ({
              source: e.source,
              target: e.target,
              label: e.weight ? `${e.weight} papers` : "",
            }));
            return (
              <ForceGraph
                nodes={pathwayGraphNodes}
                edges={pathwayGraphEdges}
                height={420}
                onNodeClick={(node) => {
                  const raw = unifiedPathways.nodes.find((candidate: any) => String(candidate.id || `${candidate.layer}:${candidate.label}`) === node.id || String(candidate.label) === node.label);
                  setSelectedPathwayNode(raw ?? { id: node.id, label: node.label, layer: node.type });
                }}
              />
            );
          })()}
          {selectedPathwayNode && (
            <div className="mt-3 p-3 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid #0891b220" }}>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#0891b2" }}>Pathway Node Detail</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                <KVRow label="Node" value={String(selectedPathwayNode.label || selectedPathwayNode.id || "—")} />
                <KVRow label="Layer" value={String(selectedPathwayNode.layer || selectedPathwayNode.source || "pathway")} />
                {selectedPathwayNode.source_db && <KVRow label="Source DB" value={String(selectedPathwayNode.source_db)} />}
                {selectedPathwayNode.description && <KVRow label="Description" value={String(selectedPathwayNode.description)} />}
              </div>
              <div className="mt-2 text-[11px]" style={{ color: "var(--text-primary)" }}>
                {String(selectedPathwayNode.label || selectedPathwayNode.id)} is part of the unified pathway view and highlights cross-database overlap around this cockpit query.
              </div>
              <div className="mt-2 space-y-1">
                {(unifiedPathways.edges || [])
                  .filter((edge: any) => {
                    const nodeId = String(selectedPathwayNode.id || `${selectedPathwayNode.layer}:${selectedPathwayNode.label}`);
                    return String(edge.source) === nodeId || String(edge.target) === nodeId;
                  })
                  .slice(0, 6)
                  .map((edge: any, index: number) => (
                    <div key={index} className="text-[10px] px-2 py-1 rounded" style={{ background: "rgba(8, 145, 178, 0.06)", color: "var(--text-primary)" }}>
                      {(String(edge.source).split(":").pop() || edge.source)} → {(String(edge.target).split(":").pop() || edge.target)}
                      {edge.weight ? ` • ${edge.weight} papers` : ""}
                    </div>
                  ))}
              </div>
            </div>
          )}
          {/* Top connections table below graph */}
          {unifiedPathways.edges?.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--text-muted)" }}>Top Connections</div>
              <div className="space-y-1">
                {unifiedPathways.edges.slice(0, 10).map((edge: any, ei: number) => {
                  const srcLabel = edge.source.split(":").pop() || edge.source;
                  const tgtLabel = edge.target.split(":").pop() || edge.target;
                  return (
                    <div key={ei} className="flex items-center gap-2 text-[10px] p-1.5 rounded" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                      <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{srcLabel}</span>
                      <span style={{ color: "var(--text-muted)" }}>→</span>
                      <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{tgtLabel}</span>
                      <span className="ml-auto text-[9px] px-1.5 rounded" style={{ background: "#0891b210", color: "#0891b2" }}>{edge.weight} papers</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §10 — EVIDENCE ASSESSMENT (Supporting vs Dissenting)
          ═══════════════════════════════════════════════════ */}
      {(traceableSummary.supporting_findings?.length > 0 || traceableSummary.dissenting_findings?.length > 0) && (
        <ReportSection num={10} title="Evidence Assessment — Supporting vs Dissenting" icon={<BarChart3 size={14} />} color="#059669" defaultOpen={true}>
          {traceableSummary.supporting_findings?.length > 0 && (
            <div className="mb-4">
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#10b981" }}>Top 5 Supporting Findings</div>
              <div className="space-y-2">
                {traceableSummary.supporting_findings.map((f, i) => (
                  <div key={i} className="p-2.5 rounded-lg text-[11px]" style={{ background: "#10b98108", border: "1px solid #10b98120" }}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-bold" style={{ color: "#10b981" }}>[Ref {f.ref_num}]</span>
                      <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{f.title?.slice(0, 120)}</span>
                      {f.year && <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>({f.year})</span>}
                    </div>
                    <div style={{ color: "var(--text-primary)" }}>{f.finding?.slice(0, 300)}</div>
                    {f.doi && (
                      <a href={`https://doi.org/${f.doi}`} target="_blank" rel="noopener noreferrer" className="text-[9px] underline mt-1 block" style={{ color: "#3b82f6" }}>
                        DOI: {f.doi}
                      </a>
                    )}
                    {(f as Record<string, unknown>).should_influence && Array.isArray((f as Record<string, unknown>).should_influence) && ((f as Record<string, unknown>).should_influence as string[]).length > 0 && (
                      <div className="mt-1.5 text-[10px]" style={{ color: "#10b981" }}>
                        <span className="font-bold uppercase">✓ Should Influence: </span>
                        {((f as Record<string, unknown>).should_influence as string[]).join("; ")}
                      </div>
                    )}
                    {(f as Record<string, unknown>).should_not_influence && Array.isArray((f as Record<string, unknown>).should_not_influence) && ((f as Record<string, unknown>).should_not_influence as string[]).length > 0 && (
                      <div className="mt-1 text-[10px]" style={{ color: "#f59e0b" }}>
                        <span className="font-bold uppercase">⚠ Should Not Influence: </span>
                        {((f as Record<string, unknown>).should_not_influence as string[]).join("; ")}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {traceableSummary.dissenting_findings?.length > 0 && (
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#ef4444" }}>Top 5 Dissenting Findings</div>
              <div className="space-y-2">
                {traceableSummary.dissenting_findings.map((f, i) => (
                  <div key={i} className="p-2.5 rounded-lg text-[11px]" style={{ background: "#ef444408", border: "1px solid #ef444420" }}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-bold" style={{ color: "#ef4444" }}>[Ref {f.ref_num}]</span>
                      <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{f.title?.slice(0, 120)}</span>
                      {f.year && <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>({f.year})</span>}
                    </div>
                    <div style={{ color: "var(--text-primary)" }}>{f.finding?.slice(0, 300)}</div>
                    {f.contradiction_note && (
                      <div className="mt-1 text-[10px] italic" style={{ color: "#f59e0b" }}>⚠ {f.contradiction_note}</div>
                    )}
                    {f.doi && (
                      <a href={`https://doi.org/${f.doi}`} target="_blank" rel="noopener noreferrer" className="text-[9px] underline mt-1 block" style={{ color: "#3b82f6" }}>
                        DOI: {f.doi}
                      </a>
                    )}
                    {(f as Record<string, unknown>).should_influence && Array.isArray((f as Record<string, unknown>).should_influence) && ((f as Record<string, unknown>).should_influence as string[]).length > 0 && (
                      <div className="mt-1.5 text-[10px]" style={{ color: "#10b981" }}>
                        <span className="font-bold uppercase">✓ Should Influence: </span>
                        {((f as Record<string, unknown>).should_influence as string[]).join("; ")}
                      </div>
                    )}
                    {(f as Record<string, unknown>).should_not_influence && Array.isArray((f as Record<string, unknown>).should_not_influence) && ((f as Record<string, unknown>).should_not_influence as string[]).length > 0 && (
                      <div className="mt-1 text-[10px]" style={{ color: "#f59e0b" }}>
                        <span className="font-bold uppercase">⚠ Should Not Influence: </span>
                        {((f as Record<string, unknown>).should_not_influence as string[]).join("; ")}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* Reference Index */}
          {traceableSummary.references?.length > 0 && (
            <div className="mt-4">
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>Reference Index</div>
              <div className="space-y-1">
                {traceableSummary.references.map((r, i) => (
                  <div key={i} className="flex items-center gap-2 text-[10px]" style={{ color: "var(--text-muted)" }}>
                    <span className="font-bold" style={{ color: "#3b82f6" }}>[{r.ref_num}]</span>
                    <span>{r.title?.slice(0, 100)}</span>
                    {r.year && <span>({r.year})</span>}
                    {r.doi && <a href={`https://doi.org/${r.doi}`} target="_blank" rel="noopener noreferrer" className="underline" style={{ color: "#3b82f6" }}>{r.doi}</a>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §11 — BIDIRECTIONAL TRACEABILITY
          ═══════════════════════════════════════════════════ */}
      {Object.keys(evidenceLinks).length > 0 && (
        <ReportSection num={11} title={`Bidirectional Traceability (${Object.keys(evidenceLinks).length} claims)`} icon={<FileSearch size={14} />} color="#0d9488" defaultOpen={false}>
          <div className="text-[10px] mb-3" style={{ color: "var(--text-muted)" }}>
            Click any claim below to see the exact source sentences from the literature that support it.
          </div>
          <div className="space-y-1.5">
            {Object.entries(evidenceLinks).map(([claim, evidenceArr]) => {
              const evArr = evidenceArr as Array<Record<string, unknown>>;
              const isOpen = tracePanel?.claim === claim;
              return (
                <div key={claim}>
                  <div
                    className="flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all hover:shadow-sm"
                    style={{ background: isOpen ? "#0d948808" : "var(--bg-surface)", border: isOpen ? "1px solid #0d948825" : "1px solid var(--border)" }}
                    onClick={() => setTracePanel(isOpen ? null : { claim, evidence: evArr })}
                  >
                    <Shield size={12} style={{ color: "#0d9488", flexShrink: 0 }} />
                    <span className="text-[11px] font-medium flex-1" style={{ color: "var(--text-primary)" }}>{claim}</span>
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded" style={{ background: "#0d948810", color: "#0d9488" }}>{evArr.length} source{evArr.length !== 1 ? "s" : ""}</span>
                    {isOpen ? <ChevronUp size={12} style={{ color: "var(--text-muted)" }} /> : <ChevronDown size={12} style={{ color: "var(--text-muted)" }} />}
                  </div>
                  {isOpen && (
                    <div className="ml-4 mt-1 space-y-1.5 border-l-2 pl-3" style={{ borderColor: "#0d948830" }}>
                      {evArr.map((ev, ei) => (
                        <div key={ei} className="p-2.5 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                          <div className="flex items-center gap-2 mb-1.5">
                            <span className="text-[10px] font-bold" style={{ color: "var(--text-primary)" }}>{String(ev.paper_title || "Unknown Paper")}</span>
                            {ev.year && <span className="text-[9px] font-mono" style={{ color: "var(--text-muted)" }}>({String(ev.year)})</span>}
                            {ev.score && (
                              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded" style={{ background: Number(ev.score) > 0.5 ? "#10b98110" : "#f59e0b10", color: Number(ev.score) > 0.5 ? "#10b981" : "#f59e0b" }}>
                                match: {(Number(ev.score) * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] italic leading-relaxed" style={{ color: "var(--text-primary)" }}>
                            "{String(ev.sentence || "—")}"
                          </div>
                          {ev.doi && (
                            <a href={`https://doi.org/${ev.doi}`} target="_blank" rel="noopener noreferrer" className="text-[9px] mt-1 inline-block underline" style={{ color: "#3b82f6" }}>
                              DOI: {String(ev.doi)}
                            </a>
                          )}
                          {ev.source && <span className="text-[9px] ml-2" style={{ color: "var(--text-muted)" }}>via {String(ev.source)}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {paperSentences.length > 0 && (
            <div className="mt-4">
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                Paper Sentence Index ({paperSentences.length} papers)
              </div>
              <div className="space-y-2">
                {(paperSentences as Array<Record<string, unknown>>).slice(0, 10).map((ps, pi) => (
                  <details key={pi} className="rounded-lg overflow-hidden" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                    <summary className="px-3 py-2 cursor-pointer text-[11px] font-semibold" style={{ color: "var(--text-primary)" }}>
                      {String(ps.title || `Paper ${pi + 1}`)}
                      {ps.year && <span className="text-[10px] font-mono ml-2" style={{ color: "var(--text-muted)" }}>({String(ps.year)})</span>}
                      <span className="text-[9px] ml-2 font-mono" style={{ color: "var(--text-muted)" }}>{(ps.sentences as Array<Record<string, unknown>>)?.length || 0} sentences</span>
                    </summary>
                    <div className="px-3 pb-2 space-y-1">
                      {(ps.sentences as Array<Record<string, unknown>> || []).slice(0, 15).map((sent, si) => (
                        <div key={si} className="text-[10px] flex gap-2" style={{ color: "var(--text-primary)" }}>
                          <span className="font-mono text-[9px] shrink-0" style={{ color: "var(--text-muted)" }}>S{Number(sent.idx) + 1}</span>
                          <span>{String(sent.text)}</span>
                        </div>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            </div>
          )}
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §12 — MECHANISM CLUSTERS
          ═══════════════════════════════════════════════════ */}
      {hasLiteratureData && mechanismClusters.clusters?.length > 0 && (
        <ReportSection num={12} title={`Mechanism Clusters (${mechanismClusters.total_clustered} papers in ${mechanismClusters.clusters.length} clusters)`} icon={<Layers size={14} />} color="#7c3aed" defaultOpen={false}>
          <div className="space-y-3">
            {mechanismClusters.clusters.map((cluster, ci) => {
              const clusterColors: Record<string, string> = {
                "Inflammation & Immunity": "#ef4444",
                "Oxidative Stress": "#f59e0b",
                "Cell Signaling & Pathways": "#8b5cf6",
                "Apoptosis & Cell Death": "#dc2626",
                "Gene Regulation & Expression": "#6366f1",
                "Genetic Variants & Polymorphisms": "#0891b2",
                "Drug Action & Pharmacology": "#e11d48",
                "Structural & Molecular Biology": "#059669",
              };
              const color = clusterColors[cluster.name] || "#6b7280";
              return (
                <div key={ci} className="rounded-lg overflow-hidden" style={{ border: `1px solid ${color}20`, background: `${color}04` }}>
                  <div className="flex items-center gap-2 px-4 py-2.5" style={{ borderBottom: `1px solid ${color}15` }}>
                    <span className="w-3 h-3 rounded-full" style={{ background: color }} />
                    <span className="text-[12px] font-bold" style={{ color }}>{cluster.name}</span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: `${color}12`, color }}>{cluster.count}</span>
                  </div>
                  <div className="px-4 py-2 space-y-1">
                    {cluster.papers.slice(0, 10).map((p, pi) => (
                      <div key={pi} className="flex items-center gap-2 text-[11px]">
                        <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>{pi + 1}.</span>
                        <span className="flex-1" style={{ color: "var(--text-primary)" }}>{p.title?.slice(0, 120)}{(p.title?.length || 0) > 120 ? "…" : ""}</span>
                        {p.year && <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>({p.year})</span>}
                        {p.relevance_score > 0 && <span className="text-[9px] font-mono px-1.5 rounded" style={{ background: "#10b98110", color: "#10b981" }}>{(p.relevance_score * 100).toFixed(0)}%</span>}
                        {p.doi && <a href={`https://doi.org/${p.doi}`} target="_blank" rel="noopener noreferrer" className="text-[9px] underline" style={{ color: "#3b82f6" }}>DOI</a>}
                      </div>
                    ))}
                    {cluster.count > 10 && <div className="text-[10px] italic" style={{ color: "var(--text-muted)" }}>…and {cluster.count - 10} more</div>}
                  </div>
                </div>
              );
            })}
          </div>
          {mechanismClusters.unclustered?.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--text-muted)" }}>Unclustered ({mechanismClusters.unclustered.length})</div>
              <div className="space-y-1">
                {mechanismClusters.unclustered.slice(0, 5).map((p, i) => (
                  <div key={i} className="text-[11px]" style={{ color: "var(--text-muted)" }}>{p.title?.slice(0, 100)}</div>
                ))}
              </div>
            </div>
          )}
        </ReportSection>
      )}

      {/* ═══════════════════════════════════════════════════
          §13 — MeSH/GO TERMINOLOGY
          ═══════════════════════════════════════════════════ */}
      {Object.keys(meshTerminology).length > 0 && (meshTerminology.mesh_mappings || meshTerminology.gene_mappings) && (
        <ReportSection num={13} title="MeSH/GO Terminology Mapping" icon={<Atom size={14} />} color="#7c3aed" defaultOpen={false}>
          {meshTerminology.mesh_mappings && Array.isArray(meshTerminology.mesh_mappings) && (meshTerminology.mesh_mappings as Array<Record<string, unknown>>).length > 0 && (
            <div className="mb-3">
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "#dc2626" }}>MeSH Disease Mappings</div>
              <div className="space-y-1">
                {(meshTerminology.mesh_mappings as Array<Record<string, unknown>>).map((m, i) => (
                  <div key={i} className="flex items-center gap-2 text-[11px]">
                    <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{String(m.term || "—")}</span>
                    <span style={{ color: "var(--text-muted)" }}>→</span>
                    <span className="font-mono text-[10px] px-1.5 rounded" style={{ background: "#dc262608", color: "#dc2626", border: "1px solid #dc262620" }}>{String(m.mesh_id || "—")}</span>
                    {m.synonyms && Array.isArray(m.synonyms) && <TagChips items={(m.synonyms as string[]).slice(0, 5)} color="#7c3aed" />}
                  </div>
                ))}
              </div>
            </div>
          )}
          {meshTerminology.gene_mappings && Array.isArray(meshTerminology.gene_mappings) && (meshTerminology.gene_mappings as Array<Record<string, unknown>>).length > 0 && (
            <div className="mb-3">
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "#6366f1" }}>Gene Alias Mappings</div>
              <div className="space-y-1">
                {(meshTerminology.gene_mappings as Array<Record<string, unknown>>).map((m, i) => (
                  <div key={i} className="flex items-center gap-2 text-[11px]">
                    <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{String(m.gene || "—")}</span>
                    <span style={{ color: "var(--text-muted)" }}>→</span>
                    {m.aliases && Array.isArray(m.aliases) && <TagChips items={(m.aliases as string[]).slice(0, 5)} color="#6366f1" />}
                  </div>
                ))}
              </div>
            </div>
          )}
          {meshTerminology.expanded_search_terms && Array.isArray(meshTerminology.expanded_search_terms) && (
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--text-muted)" }}>Expanded Search Terms</div>
              <TagChips items={meshTerminology.expanded_search_terms as string[]} color="#7c3aed" />
            </div>
          )}
        </ReportSection>
      )}
      </div>

      <div className="flex flex-col gap-4" style={{ order: 3 }}>
      {/* ═══════════════════════════════════════════════════
          §24 — PROVENANCE APPENDIX
          ═══════════════════════════════════════════════════ */}
      <ReportSection num={24} title="Provenance Appendix" icon={<FileSearch size={14} />} color="#6b7280" defaultOpen={false}>
        <div className="space-y-3">
          <div>
            <div className="text-[10px] font-bold uppercase mb-1" style={{ color: "var(--text-muted)" }}>Run Metadata</div>
            <KVRow label="Run ID" value={<span className="font-mono text-[10px]">{data.run_id || "—"}</span>} />
            <KVRow label="Generated At" value={data.timestamp || new Date().toISOString()} />
            <KVRow label="Query" value={data.query} />
            <KVRow label="Result Limit" value="100" />
            <KVRow label="Total Latency" value={`${data.latency_ms}ms`} />
          </div>
          {data.source_breakdown && Object.keys(data.source_breakdown).length > 0 && (
            <div>
              <div className="text-[10px] font-bold uppercase mb-1" style={{ color: "var(--text-muted)" }}>Databases Queried ({Object.keys(data.source_breakdown).length})</div>
              <TagChips items={Object.keys(data.source_breakdown).sort()} color="#6b7280" />
            </div>
          )}
          {data.errors && data.errors.length > 0 && (
            <div>
              <div className="text-[10px] font-bold uppercase mb-1" style={{ color: "#ef4444" }}>Errors & Degraded Sources ({data.errors.length})</div>
              <div className="space-y-1">
                {data.errors.map((err, i) => (
                  <div key={i} className="text-[10px] font-mono px-2 py-1 rounded" style={{ background: "rgba(239, 68, 68, 0.05)", color: "#ef4444" }}>{err}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      </ReportSection>

      {/* ── Navigation actions ─────────────────── */}
      <div className="flex flex-wrap gap-2 pt-2 pb-8">
        <button className="flex items-center gap-1.5 px-5 py-2.5 rounded-lg text-[12px] font-semibold transition-all hover:shadow-md" style={{ background: "var(--accent)", color: "#fff", border: "none", cursor: "pointer" }} onClick={() => navigate(`/search?q=${encodeURIComponent(data.query)}`)}>
          <Search size={13} /> Deep Evidence Search
        </button>
        <button className="flex items-center gap-1.5 px-5 py-2.5 rounded-lg text-[12px] font-semibold transition-all hover:shadow-md" style={{ background: "#8b5cf6", color: "#fff", border: "none", cursor: "pointer" }} onClick={() => navigate(`/graph?q=${encodeURIComponent(data.query)}`)}>
          <Network size={13} /> Knowledge Graph
        </button>
        <button className="flex items-center gap-1.5 px-5 py-2.5 rounded-lg text-[12px] font-semibold transition-all hover:shadow-md" style={{ background: "#10b981", color: "#fff", border: "none", cursor: "pointer" }} onClick={() => navigate(`/disease?q=${encodeURIComponent(data.query)}`)}>
          <Target size={13} /> Disease Workbench
        </button>
        <button className="flex items-center gap-1.5 px-5 py-2.5 rounded-lg text-[12px] font-semibold transition-all hover:shadow-md" style={{ background: "#f59e0b", color: "#fff", border: "none", cursor: "pointer" }} onClick={() => navigate(`/targets?q=${encodeURIComponent(data.query)}`)}>
          <Target size={13} /> Target Prioritization
        </button>
      </div>
      </div>
    </div>
  );
}

/* ── Cockpit Query Lifecycle State Machine ─────────────────── */

interface CockpitQueryState {
  query: string;
  isAnalyzing: boolean;
  result: CockpitAnalysisResult | null;
  error: string | null;
  runId: string | null;
  progressStage: string | null;
  progressPercent: number;
  timeoutWarning: boolean;
}

type CockpitAction =
  | { type: "START_ANALYSIS"; query: string; runId?: string }
  | { type: "PROGRESS"; stage: string; percent: number }
  | { type: "COMPLETE"; result: CockpitAnalysisResult }
  | { type: "ERROR"; error: string }
  | { type: "TIMEOUT" }
  | { type: "RESET" }
  | { type: "RESTORE"; result: CockpitAnalysisResult }
  | { type: "SET_QUERY"; query: string };

const initialCockpitState: CockpitQueryState = {
  query: "",
  isAnalyzing: false,
  result: null,
  error: null,
  runId: null,
  progressStage: null,
  progressPercent: 0,
  timeoutWarning: false,
};

/**
 * cockpitReducer — State machine for cockpit query lifecycle.
 * Key invariant: only RESET clears `result` to null.
 */
export function cockpitReducer(state: CockpitQueryState, action: CockpitAction): CockpitQueryState {
  switch (action.type) {
    case "START_ANALYSIS":
      return {
        ...state,
        query: action.query,
        isAnalyzing: true,
        error: null,
        runId: action.runId ?? null,
        progressStage: "classification",
        progressPercent: 0,
        timeoutWarning: false,
        // NOTE: result is NOT cleared here — only RESET clears it
      };
    case "PROGRESS":
      return {
        ...state,
        progressStage: action.stage,
        progressPercent: action.percent,
        timeoutWarning: false,
      };
    case "COMPLETE":
      return {
        ...state,
        isAnalyzing: false,
        result: action.result,
        error: null,
        runId: action.result.run_id ?? state.runId,
        progressStage: null,
        progressPercent: 100,
        timeoutWarning: false,
      };
    case "ERROR":
      return {
        ...state,
        isAnalyzing: false,
        error: action.error,
        progressStage: null,
        progressPercent: 0,
        timeoutWarning: false,
        // result is preserved for retry context
      };
    case "TIMEOUT":
      return {
        ...state,
        timeoutWarning: true,
        // result is preserved, isAnalyzing stays true until user acts
      };
    case "RESET":
      return {
        ...initialCockpitState,
      };
    case "RESTORE":
      return {
        ...state,
        result: action.result,
        query: action.result.query,
        isAnalyzing: false,
        error: null,
        runId: action.result.run_id ?? null,
        timeoutWarning: false,
      };
    case "SET_QUERY":
      return {
        ...state,
        query: action.query,
      };
    default:
      return state;
  }
}

/* ── Main Cockpit ─────────────────────────────────────────── */

export default function WorkspacePage() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);

  // Stabilized state machine — result only cleared by explicit RESET
  const [state, dispatch] = useReducer(cockpitReducer, initialCockpitState);
  const { query, isAnalyzing, result, error } = state;
  const wsProgress = useRunProgress(state.runId);

  const setQuery = useCallback((q: string) => dispatch({ type: "SET_QUERY", query: q }), []);
  const [progressIdx, setProgressIdx] = useState(0);
  const progressTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const elapsedTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const [queryIntent, setQueryIntent] = useState<{ intent: string; eta: number; label: string } | null>(null);
  const [recentCommands, setRecentCommands] = useState<string[]>([]);
  const [drawerEntity, setDrawerEntity] = useState<{ id: string; type: string; name: string } | null>(null);
  const parsedCommand = parseInlineSlashCommand(query);
  const commandToken = parsedCommand.normalizedQuery.startsWith("/")
    ? parsedCommand.normalizedQuery.split(" ")[0].toLowerCase()
    : "";
  // Also detect inline / for autocomplete
  const lastSlashIdx = query.lastIndexOf("/");
  const inlineSlashToken = lastSlashIdx >= 0 ? query.slice(lastSlashIdx).split(/\s/)[0].toLowerCase() : "";
  const queryMode = classifyCockpitQueryMode(query);
  const recentCommandDefs = recentCommands
    .map((command) => SLASH_COMMANDS.find((item) => item.command === command))
    .filter((item): item is SlashCommandDefinition => Boolean(item) && (!commandToken || item.command.startsWith(commandToken)));
  const matchingCommandDefs = commandToken
    ? SLASH_COMMANDS.filter((item) => item.command.startsWith(commandToken))
    : SLASH_COMMANDS;
  const showCommandAutocomplete = (parsedCommand.normalizedQuery.startsWith("/") && !parsedCommand.argument) ||
    (inlineSlashToken.startsWith("/") && inlineSlashToken.length > 1 && !parsedCommand.command);
  const matchingForInline = inlineSlashToken.startsWith("/")
    ? SLASH_COMMANDS.filter((item) => item.command.startsWith(inlineSlashToken))
    : matchingCommandDefs;
  const commandSuggestions = showCommandAutocomplete
    ? [
        ...recentCommandDefs,
        ...(inlineSlashToken.startsWith("/") ? matchingForInline : matchingCommandDefs).filter((item) => !recentCommandDefs.some((recent) => recent.command === item.command)),
      ]
    : [];

  // Auto-focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    setRecentCommands(readRecentSlashCommands());
  }, []);

  const persistCompletedRun = useCallback((analysisResult: CockpitAnalysisResult, rawQuery: string, modeQuery?: string) => {
    dispatch({ type: "COMPLETE", result: analysisResult });
    persistCockpitArtifactRecord({
      query: rawQuery,
      runId: analysisResult.run_id,
      queryMode: classifyCockpitQueryMode(modeQuery ?? rawQuery),
      createdAt: new Date().toISOString(),
      entityCount: collectCommandEntities(analysisResult).length,
    });
    window.sessionStorage.setItem(COCKPIT_LAST_RUN_KEY, JSON.stringify({
      query: rawQuery,
      runId: analysisResult.run_id,
      timestamp: analysisResult.timestamp,
      mode: classifyCockpitQueryMode(modeQuery ?? rawQuery),
    }));
    window.sessionStorage.removeItem(COCKPIT_PENDING_RUN_KEY);
  }, []);

  useEffect(() => {
    if (!isAnalyzing || !wsProgress) return;
    if (wsProgress.stage || wsProgress.progressPercent > 0) {
      dispatch({
        type: "PROGRESS",
        stage: wsProgress.stage || state.progressStage || "queued",
        percent: wsProgress.progressPercent,
      });
    }
    if (wsProgress.error) {
      window.sessionStorage.removeItem(COCKPIT_PENDING_RUN_KEY);
      dispatch({ type: "ERROR", error: wsProgress.error });
    }
  }, [isAnalyzing, state.progressStage, wsProgress]);

  useEffect(() => {
    if (!isAnalyzing || !state.runId) return;

    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    const pollStatus = async () => {
      try {
        const runStatus = await cockpitRunStatusAPI(state.runId!);
        if (cancelled) return;

        if (runStatus.status === "completed" && runStatus.result_summary) {
          persistCompletedRun(runStatus.result_summary, runStatus.query || query, runStatus.query || query);
          return;
        }

        if (runStatus.status === "failed") {
          window.sessionStorage.removeItem(COCKPIT_PENDING_RUN_KEY);
          dispatch({ type: "ERROR", error: runStatus.error_message || "Analysis failed. Check backend connection." });
          return;
        }

        pollTimer = setTimeout(pollStatus, runStatus.poll_after_ms || 2000);
      } catch {
        if (cancelled) return;
        pollTimer = setTimeout(pollStatus, 2000);
      }
    };

    void pollStatus();

    return () => {
      cancelled = true;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [isAnalyzing, persistCompletedRun, query, state.runId]);

  useEffect(() => {
    if (isAnalyzing || result) return;

    const rawPending = window.sessionStorage.getItem(COCKPIT_PENDING_RUN_KEY);
    if (!rawPending) return;

    let cancelled = false;

    const restorePendingRun = async () => {
      try {
        const pending = JSON.parse(rawPending) as { query?: string; runId?: string; modeQuery?: string };
        if (!pending.runId || !pending.query) {
          window.sessionStorage.removeItem(COCKPIT_PENDING_RUN_KEY);
          return;
        }

        const runStatus = await cockpitRunStatusAPI(pending.runId);
        if (cancelled) return;

        if (runStatus.status === "completed" && runStatus.result_summary) {
          setQuery(pending.query);
          setQueryIntent(detectQueryIntent(pending.query));
          persistCompletedRun(runStatus.result_summary, pending.query, pending.modeQuery ?? pending.query);
          return;
        }

        if (runStatus.status === "failed") {
          window.sessionStorage.removeItem(COCKPIT_PENDING_RUN_KEY);
          return;
        }

        setQuery(pending.query);
        setQueryIntent(detectQueryIntent(pending.query));
        dispatch({ type: "START_ANALYSIS", query: pending.query, runId: pending.runId });
        dispatch({ type: "PROGRESS", stage: runStatus.status || "queued", percent: 5 });
      } catch {
        window.sessionStorage.removeItem(COCKPIT_PENDING_RUN_KEY);
      }
    };

    void restorePendingRun();

    return () => {
      cancelled = true;
    };
  }, [isAnalyzing, persistCompletedRun, result, setQuery]);

  // Progress ticker + elapsed timer + 120s timeout
  useEffect(() => {
    if (isAnalyzing) {
      setProgressIdx(0);
      setElapsedSec(0);
      progressTimer.current = setInterval(() => {
        setProgressIdx((prev) => (prev + 1) % PROGRESS_STEPS.length);
      }, 2200);
      elapsedTimer.current = setInterval(() => {
        setElapsedSec((prev) => {
          const next = prev + 1;
          // 120s timeout: dispatch TIMEOUT if no progress
          if (next >= 120) {
            dispatch({ type: "TIMEOUT" });
          }
          return next;
        });
      }, 1000);
    } else {
      if (progressTimer.current) clearInterval(progressTimer.current);
      if (elapsedTimer.current) clearInterval(elapsedTimer.current);
    }
    return () => {
      if (progressTimer.current) clearInterval(progressTimer.current);
      if (elapsedTimer.current) clearInterval(elapsedTimer.current);
    };
  }, [isAnalyzing]);

  const resetSearch = useCallback(() => {
    dispatch({ type: "RESET" });
    setTimeout(() => inputRef.current?.focus(), 100);
  }, []);

  const applyCommandSuggestion = useCallback((command: SlashCommandDefinition) => {
    setQuery(`${command.command} `);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const handleAnalyze = useCallback(async (searchQuery?: string) => {
    const rawInput = normalizeCockpitQuery(searchQuery ?? query);
    if (!rawInput || isAnalyzing) return;

    const parsed = parseInlineSlashCommand(rawInput);

    if (parsed.command) {
      rememberSlashCommand(parsed.command.command);
      setRecentCommands(readRecentSlashCommands());

      if (parsed.command.command === "/blank") {
        dispatch({ type: "RESET" });
        addToast({ type: "success", title: "Blank cockpit session", message: "Cleared the current research context." });
        return;
      }

      const handoffQuery = normalizeCockpitQuery(parsed.argument || result?.query || "");
      if (parsed.command.route !== "/workspace") {
        if (!handoffQuery) {
          addToast({
            type: "info",
            title: "Query needed",
            message: `Add a topic after ${parsed.command.command} or run a cockpit search first.`,
          });
          return;
        }
        const carriedEntities = collectCommandEntities(result);
        const payload = buildSlashCommandPayload(
          parsed.command,
          handoffQuery,
          result?.run_id,
          carriedEntities,
          {
            degradedSources: result?.degraded_sources || [],
            additionalInstructions: parsed.additionalInstructions || undefined,
            pendingCommands: parsed.pendingCommands.map((cmd) => ({
              command: cmd.command,
              argument: "",
            })),
          },
          typeof (result as unknown as Record<string, unknown> | null)?.trace_id === "string" ? ((result as unknown as Record<string, unknown>).trace_id as string) : undefined,
        );
        persistCockpitHandoff(payload);
        persistCockpitArtifactRecord({
          query: handoffQuery,
          runId: result?.run_id,
          queryMode: classifyCockpitQueryMode(`${parsed.command.command} ${handoffQuery}`),
          createdAt: new Date().toISOString(),
          entityCount: carriedEntities.length,
          targetRoute: parsed.command.route,
        });
        addToast({
          type: "success",
          title: `Opening ${parsed.command.label}`,
          message: `Sent cockpit context to ${parsed.command.route}.`,
        });
        navigate(parsed.command.route);
        return;
      }

      if (!handoffQuery) {
        addToast({
          type: "info",
          title: "Query needed",
          message: `Add a topic after ${parsed.command.command} to run it inside the cockpit.`,
        });
        return;
      }

      setQuery(handoffQuery);
      setQueryIntent(detectQueryIntent(handoffQuery));
    }

    const q = parsed.command ? normalizeCockpitQuery(parsed.argument || result?.query || "") : rawInput;
    if (!q) return;
    const modeQuery = parsed.command ? `${parsed.command.command} ${q}` : q;

    setQuery(q);
    dispatch({ type: "START_ANALYSIS", query: q });
    dispatch({ type: "PROGRESS", stage: "queued", percent: 5 });
    setQueryIntent(detectQueryIntent(q));

    try {
      const queued = await cockpitStartAnalysisAPI(q, 100);
      dispatch({ type: "START_ANALYSIS", query: q, runId: queued.run_id });
      dispatch({ type: "PROGRESS", stage: "queued", percent: 5 });
      window.sessionStorage.setItem(COCKPIT_PENDING_RUN_KEY, JSON.stringify({
        query: q,
        runId: queued.run_id,
        modeQuery,
      }));
    } catch (err: unknown) {
      window.sessionStorage.removeItem(COCKPIT_PENDING_RUN_KEY);
      dispatch({ type: "ERROR", error: err instanceof Error ? err.message : "Analysis failed. Check backend connection." });
    }
  }, [query, isAnalyzing, result, addToast, navigate, setQuery]);

  const handleInputKeyDown = useCallback((event: React.KeyboardEvent<HTMLInputElement>) => {
    if ((event.key === "Tab" || event.key === "Enter") && showCommandAutocomplete && commandSuggestions.length > 0 && !parsedCommand.command) {
      event.preventDefault();
      applyCommandSuggestion(commandSuggestions[0]);
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      handleAnalyze();
    }
  }, [showCommandAutocomplete, commandSuggestions, parsedCommand.command, applyCommandSuggestion, handleAnalyze]);

  const handleNewSearch = () => {
    resetSearch();
  };

  // ─── Hero state (no results yet) ───────────
  if (!result && !isAnalyzing && !error) {
    return (
      <div
        className="flex-1 flex flex-col items-center justify-center p-8"
        style={{ background: "var(--bg-app)", minHeight: "100%" }}
      >
        <div className="text-center max-w-2xl w-full">
          {/* Logo & title */}
          <div className="mb-8">
            <div
              className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
              style={{ background: "linear-gradient(135deg, var(--accent), #8b5cf6)", boxShadow: "0 8px 32px rgba(99, 102, 241, 0.25)" }}
            >
              <Zap size={28} color="#fff" />
            </div>
            <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
              Drug Designer
            </h1>
            <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
              Biomedical Intelligence Engine — Search any topic across 30+ databases
            </p>
          </div>

          {/* Search bar */}
          <div className="mb-6">
            <div
              className="flex gap-2 p-2 rounded-xl"
              style={{
                background: "var(--bg-elevated)",
                border: parsedCommand.normalizedQuery.startsWith("/") ? "2px solid rgba(99, 102, 241, 0.38)" : "2px solid var(--border)",
                boxShadow: "0 4px 24px rgba(0,0,0,0.06)",
              }}
            >
              <div className="flex items-center pl-3">
                <Search size={18} style={{ color: parsedCommand.normalizedQuery.startsWith("/") ? "var(--accent)" : "var(--text-muted)" }} />
              </div>
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder="Search any biomedical topic — or use /disease, /protein, /pathways, /design…"
                className="flex-1 text-[15px] py-3 px-2 bg-transparent outline-none"
                style={{ color: "var(--text-primary)", fontFamily: "var(--font-body)" }}
              />
              <button
                onClick={() => handleAnalyze()}
                disabled={!query.trim()}
                className="flex items-center gap-2 px-6 py-3 rounded-lg text-[13px] font-bold transition-all"
                style={{
                  background: query.trim() ? "var(--accent)" : "var(--bg-surface)",
                  color: query.trim() ? "#fff" : "var(--text-muted)",
                  border: "none",
                  cursor: query.trim() ? "pointer" : "not-allowed",
                  opacity: query.trim() ? 1 : 0.5,
                }}
              >
                <Zap size={14} /> Analyze
              </button>
            </div>

            <div className="flex items-center gap-2 flex-wrap mt-3">
              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider" style={{ background: "rgba(99, 102, 241, 0.1)", color: "var(--accent)", border: "1px solid rgba(99, 102, 241, 0.18)" }}>
                Mode: {queryMode}
              </span>
              {parsedCommand.command ? (
                <span className="px-2.5 py-1 rounded-full text-[10px]" style={{ background: "var(--bg-surface)", color: "var(--text-primary)", border: "1px solid var(--border)" }}>
                  {parsedCommand.command.command} → {parsedCommand.command.label}
                </span>
              ) : recentCommands.length > 0 ? (
                <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                  Recent: {recentCommands.slice(0, 4).join(" · ")}
                </span>
              ) : null}
            </div>

            {showCommandAutocomplete && commandSuggestions.length > 0 && (
              <div className="mt-3 rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)", boxShadow: "0 16px 40px rgba(15, 23, 42, 0.08)" }}>
                <div className="px-4 py-2 text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
                  Slash Commands
                </div>
                {commandSuggestions.slice(0, 8).map((command, index) => (
                  <button
                    key={command.command}
                    onClick={() => applyCommandSuggestion(command)}
                    className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-[var(--bg-surface)]"
                    style={{ borderTop: index === 0 ? "none" : "1px solid var(--border)" }}
                  >
                    <span className="px-2 py-1 rounded text-[10px] font-bold" style={{ background: "rgba(99, 102, 241, 0.1)", color: "var(--accent)" }}>
                      {command.command}
                    </span>
                    <div className="min-w-0">
                      <div className="text-[12px] font-semibold" style={{ color: "var(--text-primary)" }}>{command.label}</div>
                      <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{command.description}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Example queries */}
          <div>
            <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
              Try:
            </span>
            <div className="flex flex-wrap justify-center gap-2 mt-2">
              {EXAMPLE_QUERIES.map((eq) => (
                <button
                  key={eq}
                  onClick={() => { setQuery(eq); handleAnalyze(eq); }}
                  className="px-3 py-1.5 rounded-full text-[11px] font-medium transition-all hover:shadow-sm"
                  style={{ background: "var(--bg-surface)", color: "var(--accent)", border: "1px solid var(--border)", cursor: "pointer" }}
                >
                  {eq}
                </button>
              ))}
            </div>
          </div>

          {/* What happens */}
          <div className="mt-12 card-grid text-left">
            {[
              { icon: <Database size={16} />, title: "30+ Databases", desc: "PubMed, ChEMBL, UniProt, OpenTargets, ClinicalTrials.gov, KEGG, Reactome, and more" },
              { icon: <Sparkles size={16} />, title: "AI Analysis", desc: "Expert biomedical summary with entity extraction, evidence scoring, and contradiction detection" },
              { icon: <Download size={16} />, title: "Full Export", desc: "Download complete results as JSON or CSV for further analysis in your tools" },
            ].map((item) => (
              <div
                key={item.title}
                className="p-4 rounded-lg"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
              >
                <div className="mb-2" style={{ color: "var(--accent)" }}>{item.icon}</div>
                <div className="text-[12px] font-bold mb-1" style={{ color: "var(--text-primary)" }}>{item.title}</div>
                <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>{item.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ─── Results / Loading / Error state ───────
  return (
    <>
    <div
      className="flex-1 flex flex-col overflow-hidden"
      style={{ background: "var(--bg-app)" }}
    >
      {/* Top search bar (compact) */}
      <div
        className="shrink-0 px-6 py-3"
        style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-elevated)" }}
      >
        <div className="max-w-4xl">
          <div className="flex gap-2">
            <div className="flex items-center">
              <Search size={16} style={{ color: parsedCommand.normalizedQuery.startsWith("/") ? "var(--accent)" : "var(--text-muted)" }} />
            </div>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder="Search any biomedical topic or route with /commands…"
              disabled={isAnalyzing}
              className="flex-1 text-[13px] py-2 px-2 bg-transparent outline-none"
              style={{ color: "var(--text-primary)", fontFamily: "var(--font-body)" }}
            />
            <button
              onClick={() => handleAnalyze()}
              disabled={isAnalyzing || !query.trim()}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[11px] font-bold"
              style={{
                background: isAnalyzing ? "var(--bg-surface)" : "var(--accent)",
                color: isAnalyzing ? "var(--text-muted)" : "#fff",
                border: "none",
                cursor: isAnalyzing || !query.trim() ? "not-allowed" : "pointer",
                opacity: isAnalyzing || !query.trim() ? 0.5 : 1,
              }}
            >
              {isAnalyzing ? <><Loader2 size={12} className="animate-spin" /> Analyzing…</> : <><Zap size={12} /> Analyze</>}
            </button>
          </div>

          <div className="mt-2 flex items-center gap-2 flex-wrap">
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold" style={{ background: "rgba(99, 102, 241, 0.1)", color: "var(--accent)" }}>
              {parsedCommand.command ? `Slash → ${parsedCommand.command.label}` : `Mode: ${queryMode}`}
            </span>
            {parsedCommand.command ? (
              <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>{parsedCommand.command.description}</span>
            ) : recentCommands.length > 0 ? (
              <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>Recent: {recentCommands.slice(0, 3).join(" · ")}</span>
            ) : null}
          </div>

          {showCommandAutocomplete && commandSuggestions.length > 0 && (
            <div className="mt-2 rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--bg-app)" }}>
              {commandSuggestions.slice(0, 6).map((command, index) => (
                <button
                  key={command.command}
                  onClick={() => applyCommandSuggestion(command)}
                  className="w-full flex items-start gap-3 px-4 py-2.5 text-left hover:bg-[var(--bg-surface)]"
                  style={{ borderTop: index === 0 ? "none" : "1px solid var(--border)" }}
                >
                  <span className="text-[10px] font-bold" style={{ color: "var(--accent)" }}>{command.command}</span>
                  <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>{command.description}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Scrollable results area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {/* Loading state */}
        {isAnalyzing && (
          <div className="flex flex-col items-center justify-center py-20">
            {state.timeoutWarning ? (
              <>
                <AlertTriangle size={48} style={{ color: "#f59e0b" }} />
                <div className="text-[14px] font-semibold mt-4 mb-2" style={{ color: "#f59e0b" }}>
                  Analysis Taking Longer Than Expected
                </div>
                <div className="text-[12px] mb-4" style={{ color: "var(--text-muted)" }}>
                  No progress received for over 120 seconds. The backend may be overloaded.
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => { dispatch({ type: "RESET" }); handleAnalyze(); }}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[12px] font-semibold"
                    style={{ background: "var(--accent)", color: "#fff", border: "none", cursor: "pointer" }}
                  >
                    <RefreshCw size={12} /> Retry
                  </button>
                  <button
                    onClick={() => dispatch({ type: "RESET" })}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[12px] font-semibold"
                    style={{ background: "var(--bg-surface)", color: "var(--text-primary)", border: "1px solid var(--border)", cursor: "pointer" }}
                  >
                    <XCircle size={12} /> Cancel
                  </button>
                </div>
              </>
            ) : (
            <>
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6"
              style={{ background: "linear-gradient(135deg, var(--accent), #8b5cf6)", boxShadow: "0 8px 32px rgba(99, 102, 241, 0.25)" }}
            >
              <Loader2 size={28} color="#fff" className="animate-spin" />
            </div>
            <div className="text-[14px] font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
              Analyzing: "{query}"
            </div>
            {/* ETA + Intent badge */}
            {queryIntent && (
              <div className="flex flex-col items-center gap-2 mb-4">
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-bold" style={{ background: "var(--accent)12", color: "var(--accent)", border: "1px solid var(--accent)25" }}>
                    {queryIntent.intent}
                  </span>
                  <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
                    ETA ~{queryIntent.eta}s
                  </span>
                </div>
                <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                  {queryIntent.label}
                </div>
              </div>
            )}
            {/* Elapsed / ETA progress bar */}
            {queryIntent && (
              <div className="w-64 mb-4">
                <div className="flex justify-between text-[10px] mb-1">
                  <span style={{ color: "var(--text-muted)" }}>Elapsed: {elapsedSec}s</span>
                  <span style={{ color: elapsedSec > queryIntent.eta ? "#f59e0b" : "var(--text-muted)" }}>
                    {elapsedSec < queryIntent.eta ? `~${queryIntent.eta - elapsedSec}s remaining` : "Taking longer than expected…"}
                  </span>
                </div>
                <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                  <div
                    className="h-full rounded-full transition-all duration-1000"
                    style={{
                      width: `${Math.min((elapsedSec / queryIntent.eta) * 100, 100)}%`,
                      background: elapsedSec > queryIntent.eta ? "#f59e0b" : "var(--accent)",
                    }}
                  />
                </div>
              </div>
            )}
            <div className="text-[12px] flex items-center gap-2" style={{ color: "var(--accent)" }}>
              <Loader2 size={12} className="animate-spin" />
              {state.progressStage
                ? `${state.progressStage.replace(/_/g, " ")} · ${Math.round(state.progressPercent)}%`
                : PROGRESS_STEPS[progressIdx]}
            </div>
            <div className="w-64 mt-3">
              <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.max(state.progressPercent, 5)}%`,
                    background: "var(--accent)",
                  }}
                />
              </div>
              {wsProgress?.message && (
                <div className="text-[11px] mt-2 text-center" style={{ color: "var(--text-muted)" }}>
                  {wsProgress.message}
                </div>
              )}
            </div>
            <div className="flex gap-1 mt-6">
              {PROGRESS_STEPS.map((_, i) => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full transition-all"
                  style={{ background: i <= progressIdx ? "var(--accent)" : "var(--border)" }}
                />
              ))}
            </div>
            </>
            )}
          </div>
        )}

        {/* Error state */}
        {error && !isAnalyzing && (
          <div className="flex flex-col items-center justify-center py-20">
            <XCircle size={48} style={{ color: "#ef4444" }} />
            <div className="text-[14px] font-semibold mt-4 mb-2" style={{ color: "#ef4444" }}>
              Analysis Failed
            </div>
            <div className="text-[12px] mb-4" style={{ color: "var(--text-muted)" }}>
              {error}
            </div>
            <button
              onClick={() => handleAnalyze()}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[12px] font-semibold"
              style={{ background: "var(--accent)", color: "#fff", border: "none", cursor: "pointer" }}
            >
              <RefreshCw size={12} /> Retry
            </button>
          </div>
        )}

        {/* Results */}
        {result && !isAnalyzing && (
          <div className="max-w-6xl">
            <div className="mb-4">
              <h2 className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
                Analysis: "{result.query}"
              </h2>
              <p className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
                Completed at {new Date().toLocaleTimeString()} · {(result.latency_ms / 1000).toFixed(1)}s · {result.stats.total_results.toLocaleString()} results across {result.stats.categories_found} categories from {result.stats.sources_queried} databases
              </p>
            </div>
            <ReportErrorBoundary onReset={handleNewSearch}>
              <AnalysisReport data={result} onNewSearch={handleNewSearch} />
            </ReportErrorBoundary>
          </div>
        )}
      </div>
    </div>
    {drawerEntity && (
      <EntityDetailDrawer
        entityId={drawerEntity.id}
        entityType={drawerEntity.type}
        entityName={drawerEntity.name}
        onClose={() => setDrawerEntity(null)}
      />
    )}
    </>
  );
}
