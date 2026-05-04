/** Evidence Search — Unified search with LLM summary, real filters, inline entity expansion, pagination. */

import { useState, useCallback, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  Search,
  Loader2,
  AlertCircle,
  SlidersHorizontal,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  ChevronUp,
  BarChart3,
  FileText,
  BookOpen,
  Download,
  ExternalLink,
  Calendar,
  Sparkles,
  Database,
  Shield,
  Activity,
  Microscope,
  Pill,
  Dna,
  FlaskConical,
  Network,
  Send,
  Target,
  ArrowRight,
  Save,
} from "lucide-react";
import {
  searchAPI,
  searchSummaryAPI,
  entityDetailAPI,
  evidenceExportAPI,
  evidenceBundleCreateAPI,
  ensureApiBase,
  type SearchRequest,
  type SearchResponse,
  type SummaryResponse,
  type EntityDetail,
  type CategoryResult,
} from "@/lib/api";
import ForceGraph from "@/components/ui/ForceGraph";
import ContradictionBanner from "@/components/ui/ContradictionBanner";
import { TYPE_COLORS } from "@/components/ui/EntityPill";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

/* ─── Constants ─────────────────────────────────────────── */
const ALL_SOURCES = [
  { id: "uniprot", label: "UniProt" },
  { id: "opentargets", label: "OpenTargets" },
  { id: "chembl", label: "ChEMBL" },
  { id: "pubmed", label: "PubMed" },
  { id: "europepmc", label: "Europe PMC" },
  { id: "clinicaltrials", label: "ClinicalTrials" },
  { id: "patents", label: "Patents" },
  { id: "rcsb", label: "PDB/RCSB" },
  { id: "alphafold", label: "AlphaFold" },
  { id: "pubchem", label: "PubChem" },
  { id: "reactome", label: "Reactome" },
  { id: "string", label: "STRING" },
  { id: "gwas", label: "GWAS Catalog" },
  { id: "kegg", label: "KEGG" },
  { id: "wikipathways", label: "WikiPathways" },
  { id: "interpro", label: "InterPro" },
  { id: "intact", label: "IntAct" },
  { id: "ensembl", label: "Ensembl" },
  { id: "disease_ontology", label: "Disease Ontology" },
  { id: "chebi", label: "ChEBI" },
  { id: "crossref", label: "CrossRef" },
  { id: "openalex", label: "OpenAlex" },
  { id: "clinvar", label: "ClinVar" },
  { id: "gnomad", label: "gnomAD" },
  { id: "hpo", label: "HPO" },
  { id: "pharos", label: "Pharos" },
  { id: "drugbank", label: "DrugBank" },
  { id: "disgenet", label: "DisGeNET" },
  { id: "semantic_scholar", label: "Semantic Scholar" },
  { id: "biogrid", label: "BioGRID" },
  { id: "omim", label: "OMIM" },
];

const ENTITY_ICONS: Record<string, React.ReactNode> = {
  proteins: <Dna size={13} />,
  genes: <Dna size={13} />,
  drugs: <Pill size={13} />,
  molecules: <FlaskConical size={13} />,
  diseases: <Activity size={13} />,
  publications: <BookOpen size={13} />,
  clinical_trials: <Microscope size={13} />,
  patents: <FileText size={13} />,
  pathways: <Network size={13} />,
  structures: <Database size={13} />,
  interactions: <Network size={13} />,
  variants: <Dna size={13} />,
};

const ITEMS_PER_PAGE = 20;

const HIDDEN_COLS = new Set([
  "properties", "entity_type", "canonical_name",
  "created_at", "updated_at", "xrefs", "tags", "synonyms",
  "sequence", "abstract", "_evidence_refs",
]);

/* ─── Main Component ─────────────────────────────────── */
interface SearchPageProps {
  onEntityClick: (entity: Record<string, unknown>) => void;
}

export default function SearchPage({ onEntityClick }: SearchPageProps) {
  const [query, setQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [yearFrom, setYearFrom] = useState<number | null>(null);
  const [yearTo, setYearTo] = useState<number | null>(null);
  const [minConfidence, setMinConfidence] = useState<number>(0);
  const [exportFmt, setExportFmt] = useState("json");

  const mutation = useMutation({
    mutationFn: (req: SearchRequest) => searchAPI(req),
  });

  const summaryMutation = useMutation({
    mutationFn: (params: { query: string; context: Record<string, unknown> }) =>
      searchSummaryAPI(params),
  });

  const exportMut = useMutation({
    mutationFn: ({ q, f }: { q: string; f: string }) => evidenceExportAPI(q, f),
  });

  const handleSearch = useCallback(() => {
    if (!query.trim()) return;
    summaryMutation.reset();
    const req: SearchRequest = {
      query: query.trim(),
      limit: 200,
    };
    if (selectedSources.length > 0) req.sources = selectedSources;
    if (yearFrom) req.year_from = yearFrom;
    if (yearTo) req.year_to = yearTo;
    mutation.mutate(req);
  }, [query, selectedSources, yearFrom, yearTo, mutation, summaryMutation]);

  // Auto-fetch LLM summary when results arrive
  useEffect(() => {
    if (mutation.data && !summaryMutation.data && !summaryMutation.isPending) {
      const d = mutation.data;
      const topEntities: string[] = [];
      for (const cat of Object.values(d.categories)) {
        for (const row of (cat.rows || []).slice(0, 3)) {
          topEntities.push(String(row.name || row.canonical_name || row.id || ""));
        }
      }
      summaryMutation.mutate({
        query: d.query,
        context: {
          total_results: d.summary_stats.total_results,
          categories_found: d.summary_stats.categories_found,
          sources_queried: d.summary_stats.sources_queried,
          pubmed_count: d.summary_stats.pubmed_count,
          clinical_trials_count: d.summary_stats.clinical_trials_count,
          overall_confidence: d.evidence_summary?.overall_confidence ?? 0,
          contradictions_count: d.evidence_summary?.contradictions?.length ?? 0,
          top_entities: topEntities,
        },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mutation.data]);

  const data = mutation.data;

  const searchState: ViewState = mutation.isPending
    ? "loading"
    : mutation.isError
      ? "error"
      : data && data.summary_stats?.total_results === 0
        ? "empty"
        : data && data.errors?.length
          ? "degraded"
          : data
            ? "success"
            : "initial";

  const toggleSource = (src: string) => {
    setSelectedSources((prev) =>
      prev.includes(src) ? prev.filter((s) => s !== src) : [...prev, src],
    );
  };

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-[1440px] mx-auto px-6 py-5">
        {/* Page header */}
        <div className="mb-5">
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">
            Evidence Search
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Unified multi-source search across 13+ biomedical databases with AI-powered summaries
          </p>
        </div>

        {/* Query bar + Filters */}
        <div className="card rounded-xl p-4 mb-5">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="Search proteins, genes, drugs, diseases, structures, trials, pathways, patents…"
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
                style={{ borderColor: "var(--border)" }}
              />
            </div>
            <button
              onClick={handleSearch}
              disabled={mutation.isPending || !query.trim()}
              className="px-6 py-2.5 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-40 hover:opacity-90"
              style={{ background: "var(--accent)" }}
            >
              {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : "Search"}
            </button>
          </div>

          {/* Filter toggle + export */}
          <div className="flex items-center gap-4 mt-3">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-1.5 text-xs hover:text-[var(--text-secondary)] transition-colors ${showFilters ? "text-[var(--accent)]" : "text-[var(--text-muted)]"}`}
            >
              <SlidersHorizontal size={13} />
              Filters {selectedSources.length > 0 && `(${selectedSources.length})`}
              {showFilters ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {data && (
              <div className="ml-auto flex items-center gap-2">
                <select
                  value={exportFmt}
                  onChange={(e) => setExportFmt(e.target.value)}
                  className="text-xs border rounded px-2 py-1"
                  style={{ borderColor: "var(--border)" }}
                >
                  <option value="json">JSON</option>
                  <option value="csv">CSV</option>
                  <option value="bibtex">BibTeX</option>
                  <option value="ris">RIS</option>
                </select>
                <button
                  onClick={() => exportMut.mutate({ q: query, f: exportFmt })}
                  disabled={exportMut.isPending}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border hover:bg-[var(--bg-surface)]"
                  style={{ borderColor: "var(--border)" }}
                >
                  {exportMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                  Export
                </button>
              </div>
            )}
          </div>

          {/* Expanded filters */}
          {showFilters && (
            <div className="mt-3 pt-3 border-t" style={{ borderColor: "var(--border)" }}>
              <div className="mb-3">
                <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                  Data Sources
                </div>
                <div className="flex flex-wrap gap-2">
                  {ALL_SOURCES.map((s) => (
                    <label key={s.id} className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={selectedSources.length === 0 || selectedSources.includes(s.id)}
                        onChange={() => toggleSource(s.id)}
                        className="rounded"
                      />
                      {s.label}
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                  Year Range
                </div>
                <Calendar size={12} className="text-[var(--text-muted)]" />
                <input
                  type="number"
                  placeholder="From"
                  value={yearFrom ?? ""}
                  onChange={(e) => setYearFrom(e.target.value ? +e.target.value : null)}
                  className="w-20 px-2 py-1 text-xs rounded border"
                  style={{ borderColor: "var(--border)" }}
                />
                <span className="text-xs text-[var(--text-muted)]">–</span>
                <input
                  type="number"
                  placeholder="To"
                  value={yearTo ?? ""}
                  onChange={(e) => setYearTo(e.target.value ? +e.target.value : null)}
                  className="w-20 px-2 py-1 text-xs rounded border"
                  style={{ borderColor: "var(--border)" }}
                />
                {(selectedSources.length > 0 || yearFrom || yearTo || minConfidence > 0) && (
                  <button
                    onClick={() => { setSelectedSources([]); setYearFrom(null); setYearTo(null); setMinConfidence(0); }}
                    className="text-xs text-[var(--accent)] hover:underline ml-2"
                  >
                    Clear all
                  </button>
                )}
              </div>
              <div className="flex items-center gap-3 mt-2">
                <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                  Min Confidence
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={minConfidence}
                  onChange={(e) => setMinConfidence(+e.target.value)}
                  className="w-32 h-1 accent-[var(--accent)]"
                />
                <span className="text-xs font-mono" style={{ color: minConfidence > 0 ? "var(--accent)" : "var(--text-muted)" }}>
                  {minConfidence > 0 ? `≥${minConfidence}%` : "Any"}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Export success */}
        {exportMut.data && (
          <div className="rounded-lg border p-3 bg-green-50 mb-4" style={{ borderColor: "#bbf7d0" }}>
            <div className="text-xs font-medium text-green-700">
              ✓ Exported citations as {exportFmt.toUpperCase()}
            </div>
          </div>
        )}

        {/* 6-state wrapper for results */}
        <StateWrapper
          state={searchState}
          moduleName="Evidence Search"
          loadingMessage="Querying 13+ biomedical databases…"
          emptyTitle="No results found"
          emptyDescription="Try different search terms or broaden your criteria."
          emptyAction={{ label: "Clear search", onClick: () => setQuery("") }}
          degradedInfo={data?.errors?.length ? { reason: "Some sources encountered errors", affectedSources: data.errors } : undefined}
          degradedChildren={data ? <SearchResults data={data} summary={summaryMutation.data ?? null} summaryLoading={summaryMutation.isPending} minConfidence={minConfidence} /> : undefined}
          errorInfo={mutation.isError ? { code: "SEARCH_FAILED", message: (mutation.error as Error).message, recoverable: true, suggestedAction: "Check network and retry" } : undefined}
          onRetry={handleSearch}
        >
          {data && <SearchResults data={data} summary={summaryMutation.data ?? null} summaryLoading={summaryMutation.isPending} minConfidence={minConfidence} />}
        </StateWrapper>
      </div>
    </div>
  );
}

/* ─── Results ─────────────────────────────────────────── */

function SearchResults({
  data,
  summary,
  summaryLoading,
  minConfidence,
}: {
  data: SearchResponse;
  summary: SummaryResponse | null;
  summaryLoading: boolean;
  minConfidence: number;
}) {
  const navigate = useNavigate();
  const catKeys = Object.keys(data.categories);
  const stats = data.summary_stats;
  const evidence = data.evidence_summary;
  const contradictions = evidence?.contradictions || [];

  /* Apply confidence filter at the row level */
  const filteredCategories = useMemo(() => {
    if (minConfidence <= 0) return data.categories;
    const threshold = minConfidence / 100;
    const out: Record<string, CategoryResult> = {};
    for (const [type, cat] of Object.entries(data.categories)) {
      const rows = cat.rows.filter((r: Record<string, unknown>) => {
        const conf = r._confidence;
        if (typeof conf !== "number") return true; // keep rows without confidence
        return conf >= threshold;
      });
      if (rows.length > 0) {
        out[type] = { ...cat, rows, total: rows.length };
      }
    }
    return out;
  }, [data.categories, minConfidence]);

  /* Derive primary entities for cross-page handoffs */
  const geneSymbols = useMemo(() => {
    const genes = data.categories["genes"]?.rows ?? data.categories["proteins"]?.rows ?? [];
    return genes.slice(0, 10).map((g: Record<string, unknown>) => String(g.name || g.symbol || g.canonical_name || "")).filter(Boolean);
  }, [data.categories]);

  const primaryQuery = data.intent?.search_term || "";

  const [dossierCreating, setDossierCreating] = useState(false);
  const [bundleSaving, setBundleSaving] = useState(false);
  const [bundleSaved, setBundleSaved] = useState(false);

  const handleSaveToProject = async () => {
    setBundleSaving(true);
    try {
      await evidenceBundleCreateAPI({
        name: `Search: ${data.query || "untitled"}`,
        description: `Evidence bundle from search "${data.query}" — ${stats.total_results} results across ${stats.categories_found} categories`,
      });
      setBundleSaved(true);
      setTimeout(() => setBundleSaved(false), 3000);
    } catch {
      // silent — could show toast
    }
    setBundleSaving(false);
  };

  const handleCreateDossier = async () => {
    setDossierCreating(true);
    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/dossiers/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: primaryQuery || data.intent?.search_term, sources: data.provenance?.sources_hit }),
      });
      if (res.ok) {
        const env = await res.json();
        const jobId = env?.data?.job_id || env?.job_id;
        if (jobId) navigate(`/dossiers`);
        else navigate("/dossiers");
      } else {
        navigate("/dossiers");
      }
    } catch {
      navigate("/dossiers");
    }
    setDossierCreating(false);
  };

  return (
    <div className="space-y-5">
      {/* LLM Summary */}
      <LLMSummary summary={summary} loading={summaryLoading} />

      {/* Stats Panel — merged Summary + Evidence Quality */}
      <StatsPanel stats={stats} evidence={evidence} data={data} />

      {/* Quick Actions — cross-page workflows (§74, §20.2) */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mr-1">Actions</span>
        {primaryQuery && (
          <button
            onClick={() => navigate(`/graph?entity=${encodeURIComponent(primaryQuery)}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium border transition-colors hover:bg-[var(--bg-surface)]"
            style={{ borderColor: "var(--border)", color: "var(--accent)" }}
          >
            <Network size={12} /> Explore in KG
          </button>
        )}
        {geneSymbols.length > 0 && (
          <button
            onClick={() => navigate(`/targets?disease=${encodeURIComponent(primaryQuery)}&genes=${encodeURIComponent(geneSymbols.join(","))}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium border transition-colors hover:bg-[var(--bg-surface)]"
            style={{ borderColor: "var(--border)", color: "var(--accent)" }}
          >
            <Target size={12} /> Rank Targets ({geneSymbols.length})
          </button>
        )}
        <button
          onClick={handleCreateDossier}
          disabled={dossierCreating}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium text-white transition-all hover:opacity-90 disabled:opacity-50"
          style={{ background: "var(--accent)" }}
        >
          {dossierCreating ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
          Generate Dossier <ArrowRight size={10} />
        </button>
        {primaryQuery && (
          <button
            onClick={() => navigate(`/disease?query=${encodeURIComponent(primaryQuery)}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium border transition-colors hover:bg-[var(--bg-surface)]"
            style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
          >
            <Activity size={12} /> Disease Intelligence
          </button>
        )}
        <button
          onClick={handleSaveToProject}
          disabled={bundleSaving || bundleSaved}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium border transition-colors hover:bg-[var(--bg-surface)] disabled:opacity-60"
          style={{ borderColor: bundleSaved ? "#22c55e" : "var(--border)", color: bundleSaved ? "#22c55e" : "var(--text-secondary)" }}
        >
          {bundleSaving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
          {bundleSaved ? "Saved ✓" : "Save to Project"}
        </button>
      </div>

      {/* Entity Relationship Graph */}
      {data.preview_graph.nodes.length > 0 && (
        <ForceGraph
          nodes={data.preview_graph.nodes}
          edges={data.preview_graph.edges}
          height={380}
        />
      )}

      {/* Contradictions */}
      {contradictions.length > 0 && (
        <div className="space-y-2">
          {contradictions.slice(0, 3).map((c, i) => (
            <ContradictionBanner key={i} contradiction={c} />
          ))}
          {contradictions.length > 3 && (
            <p className="text-[10px] text-[var(--text-muted)] text-center">
              +{contradictions.length - 3} more contradictions found
            </p>
          )}
        </div>
      )}

      {/* Errors */}
      {data.errors.length > 0 && (
        <div className="px-4 py-2 rounded-lg bg-amber-50 text-amber-800 text-xs">
          ⚠ {data.errors.join("; ")}
        </div>
      )}

      {/* Categorized Entity Groups with Pagination + Inline Expansion */}
      {catKeys.length === 0 ? (
        <div className="text-center py-12 text-[var(--text-muted)] text-sm">
          No results found.
        </div>
      ) : (
        <EntityCategoryGroups categories={filteredCategories} />
      )}
    </div>
  );
}

/* ─── LLM Summary ─────────────────────────────────────── */

function LLMSummary({ summary, loading }: { summary: SummaryResponse | null; loading: boolean }) {
  if (!loading && !summary) return null;

  return (
    <div className="card rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b flex items-center gap-2" style={{ borderColor: "var(--border)" }}>
        <Sparkles size={14} className="text-[var(--accent)]" />
        <span className="text-xs font-semibold text-[var(--text-primary)]">AI Research Summary</span>
        {summary?.model_used && (
          <span className="text-[9px] text-[var(--text-muted)] ml-auto">
            {summary.model_used} · {summary.latency_ms}ms
          </span>
        )}
      </div>
      <div className="px-4 py-3">
        {loading ? (
          <div className="flex items-center gap-2">
            <Loader2 size={14} className="animate-spin text-[var(--accent)]" />
            <span className="text-xs text-[var(--text-muted)]">Generating AI summary…</span>
          </div>
        ) : summary ? (
          <div className="text-xs leading-relaxed text-[var(--text-secondary)] whitespace-pre-line">
            {summary.summary}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/* ─── Stats Panel ─────────────────────────────────────── */

function StatsPanel({
  stats,
  evidence,
  data,
}: {
  stats: SearchResponse["summary_stats"];
  evidence: SearchResponse["evidence_summary"];
  data: SearchResponse;
}) {
  const confidencePct = evidence ? Math.round(evidence.overall_confidence * 100) : null;
  const contradictions = evidence?.contradictions || [];

  return (
    <div className="card rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b flex items-center gap-2" style={{ borderColor: "var(--border)" }}>
        <BarChart3 size={14} className="text-[var(--accent)]" />
        <span className="text-xs font-semibold text-[var(--text-primary)]">Stats & Evidence Quality</span>
      </div>
      <div className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <StatCard label="Total Results" value={stats.total_results.toLocaleString()} />
          <StatCard label="Categories" value={String(stats.categories_found)} />
          <StatCard label="Sources Queried" value={String(stats.sources_queried)} />
          {stats.pubmed_count != null && (
            <StatCard label="PubMed Articles" value={stats.pubmed_count.toLocaleString()} />
          )}
          {stats.clinical_trials_count != null && (
            <StatCard label="Clinical Trials" value={stats.clinical_trials_count.toLocaleString()} />
          )}
          {confidencePct != null && (
            <div className="group relative p-2.5 rounded-lg cursor-help" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
              <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1">
                Evidence Confidence
              </div>
              <div className="flex items-center gap-2">
                <Shield size={13} className="text-[var(--text-muted)]" />
                <div className="flex-1 h-2 rounded-full bg-[var(--bg-inset)] overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${confidencePct}%`,
                      backgroundColor: confidencePct >= 70 ? "#16a34a" : confidencePct >= 40 ? "#d97706" : "#dc2626",
                    }}
                  />
                </div>
                <span className="text-sm font-bold" style={{ color: confidencePct >= 70 ? "#16a34a" : confidencePct >= 40 ? "#d97706" : "#dc2626" }}>
                  {confidencePct}%
                </span>
              </div>
              {/* Confidence tooltip */}
              <div className="absolute bottom-full left-0 mb-2 w-60 p-3 bg-slate-800 text-white text-[10px] rounded-lg shadow-xl hidden group-hover:block z-50 pointer-events-none">
                <div className="font-semibold mb-1.5 text-[11px]">Evidence Confidence Breakdown</div>
                <div className="flex justify-between mb-0.5"><span className="opacity-70">Overall</span><span className="font-medium">{confidencePct}%</span></div>
                {evidence && (
                  <>
                    <div className="flex justify-between mb-0.5"><span className="opacity-70">Evidence items</span><span className="font-medium">{evidence.evidence_count}</span></div>
                    <div className="flex justify-between mb-0.5"><span className="opacity-70">Contradictions</span><span className={contradictions.length > 0 ? "font-medium text-amber-400" : "font-medium"}>{contradictions.length}</span></div>
                  </>
                )}
                {evidence?.source_breakdown && Object.keys(evidence.source_breakdown).length > 0 && (
                  <div className="mt-1.5 pt-1.5 border-t border-white/20">
                    <div className="opacity-70 mb-0.5">By source:</div>
                    {Object.entries(evidence.source_breakdown).map(([src, conf]) => (
                      <div key={src} className="flex justify-between"><span className="opacity-60">{src}</span><span>{Math.round((conf as number) * 100)}%</span></div>
                    ))}
                  </div>
                )}
                {evidence?.top_citations && evidence.top_citations.length > 0 && (
                  <div className="mt-1.5 pt-1.5 border-t border-white/20 opacity-60">
                    Top: {evidence.top_citations[0].source} ({evidence.top_citations[0].external_id})
                  </div>
                )}
              </div>
            </div>
          )}
          {evidence && (
            <>
              <StatCard label="Citations" value={String(evidence.evidence_count)} />
              <StatCard label="Contradictions" value={String(contradictions.length)} warn={contradictions.length > 0} />
            </>
          )}
          <div className="p-2.5 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1">
              Search Intent
            </div>
            <span
              className="px-2 py-0.5 rounded-full text-[10px] font-semibold text-white"
              style={{ background: TYPE_COLORS[data.intent.intent] || "#6b7280" }}
            >
              {data.intent.intent}
            </span>
            <div className="text-[9px] text-[var(--text-muted)] mt-1">{data.intent.method}</div>
          </div>
          {data.timings.total != null && (
            <StatCard label="Query Time" value={`${data.timings.total.toFixed(2)}s`} />
          )}
        </div>
        {/* Sources hit */}
        <div className="flex flex-wrap gap-1 mt-3 pt-3 border-t" style={{ borderColor: "var(--border)" }}>
          <span className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mr-2 self-center">
            Sources:
          </span>
          {data.provenance.sources_hit.map((s) => (
            <span key={s} className="px-1.5 py-0.5 text-[9px] rounded bg-[var(--bg-inset)] text-[var(--text-secondary)] font-medium">
              {s}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="p-2.5 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
      <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1">
        {label}
      </div>
      <div className={`text-lg font-bold ${warn ? "text-amber-600" : ""}`} style={warn ? {} : { fontFamily: "var(--font-display)" }}>
        {value}
      </div>
    </div>
  );
}

/* ─── Entity Category Groups with Pagination + Inline Expansion ── */

function EntityCategoryGroups({ categories }: { categories: Record<string, CategoryResult> }) {
  const types = Object.keys(categories);
  return (
    <div className="space-y-6">
      {types.map((type) => (
        <EntityGroup key={type} type={type} category={categories[type]} />
      ))}
    </div>
  );
}

function EntityGroup({ type, category }: { type: string; category: CategoryResult }) {
  const [page, setPage] = useState(0);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [entityDetail, setEntityDetail] = useState<EntityDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const totalPages = Math.ceil(category.rows.length / ITEMS_PER_PAGE);
  const pagedRows = category.rows.slice(page * ITEMS_PER_PAGE, (page + 1) * ITEMS_PER_PAGE);
  const visibleCols = category.columns.filter((c) => !HIDDEN_COLS.has(c));

  const handleExpand = async (idx: number, row: Record<string, unknown>) => {
    const globalIdx = page * ITEMS_PER_PAGE + idx;
    if (expandedRow === globalIdx) {
      setExpandedRow(null);
      setEntityDetail(null);
      return;
    }
    setExpandedRow(globalIdx);
    setEntityDetail(null);
    setDetailLoading(true);
    try {
      const detail = await entityDetailAPI({
        entity_id: String(row.id || ""),
        entity_type: type.replace(/s$/, ""),
        entity_name: String(row.name || row.canonical_name || row.id || ""),
      });
      setEntityDetail(detail);
    } catch {
      setEntityDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="card rounded-lg overflow-hidden">
      {/* Group header */}
      <div className="px-4 py-3 border-b flex items-center gap-2" style={{ borderColor: "var(--border)" }}>
        <span className="text-[var(--accent)]">{ENTITY_ICONS[type] || <Database size={13} />}</span>
        <span className="text-sm font-semibold text-[var(--text-primary)] capitalize">
          {type.replace(/_/g, " ")}
        </span>
        <span className="text-[10px] text-[var(--text-muted)] ml-1">
          ({category.total} total{category.rows.length !== category.total ? `, ${category.rows.length} loaded` : ""})
        </span>
        {totalPages > 1 && (
          <span className="text-[10px] text-[var(--text-muted)] ml-auto">
            Page {page + 1} of {totalPages}
          </span>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr style={{ background: "var(--bg-surface)" }}>
              <th className="px-3 py-2 text-left w-8" />
              {visibleCols.map((col) => (
                <th key={col} className="px-3 py-2 text-left text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                  {col.replace(/_/g, " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pagedRows.map((row, idx) => {
              const globalIdx = page * ITEMS_PER_PAGE + idx;
              const isExpanded = expandedRow === globalIdx;
              return (
                <EntityRow
                  key={globalIdx}
                  row={row}
                  cols={visibleCols}
                  type={type}
                  isExpanded={isExpanded}
                  onToggle={() => handleExpand(idx, row)}
                  detail={isExpanded ? entityDetail : null}
                  detailLoading={isExpanded && detailLoading}
                />
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-4 py-3 border-t flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
          <button
            onClick={() => { setPage(Math.max(0, page - 1)); setExpandedRow(null); }}
            disabled={page === 0}
            className="flex items-center gap-1 px-3 py-1.5 text-xs rounded border disabled:opacity-30 hover:bg-[var(--bg-surface)]"
            style={{ borderColor: "var(--border)" }}
          >
            <ChevronLeft size={12} /> Previous
          </button>
          <div className="flex gap-1">
            {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 10) {
                pageNum = i;
              } else if (page < 5) {
                pageNum = i;
              } else if (page >= totalPages - 5) {
                pageNum = totalPages - 10 + i;
              } else {
                pageNum = page - 5 + i;
              }
              return (
                <button
                  key={pageNum}
                  onClick={() => { setPage(pageNum); setExpandedRow(null); }}
                  className={`w-7 h-7 text-xs rounded ${page === pageNum ? "text-white font-bold" : "hover:bg-[var(--bg-inset)]"}`}
                  style={page === pageNum ? { background: "var(--accent)" } : {}}
                >
                  {pageNum + 1}
                </button>
              );
            })}
          </div>
          <button
            onClick={() => { setPage(Math.min(totalPages - 1, page + 1)); setExpandedRow(null); }}
            disabled={page >= totalPages - 1}
            className="flex items-center gap-1 px-3 py-1.5 text-xs rounded border disabled:opacity-30 hover:bg-[var(--bg-surface)]"
            style={{ borderColor: "var(--border)" }}
          >
            Next <ChevronRight size={12} />
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── Entity Row with Inline Expansion ──────────────── */

function EntityRow({
  row,
  cols,
  type,
  isExpanded,
  onToggle,
  detail,
  detailLoading,
}: {
  row: Record<string, unknown>;
  cols: string[];
  type: string;
  isExpanded: boolean;
  onToggle: () => void;
  detail: EntityDetail | null;
  detailLoading: boolean;
}) {
  return (
    <>
      <tr
        className="border-t hover:bg-[var(--bg-surface)]/50 cursor-pointer transition-colors"
        style={{ borderColor: "var(--border-light, var(--border))" }}
        onClick={onToggle}
      >
        <td className="px-3 py-2.5 text-center">
          {isExpanded ? (
            <ChevronDown size={14} className="text-[var(--accent)]" />
          ) : (
            <ChevronRight size={14} className="text-[var(--text-muted)]" />
          )}
        </td>
        {cols.map((col) => (
          <td key={col} className="px-3 py-2.5 max-w-[250px]">
            <CellValue value={row[col]} col={col} />
          </td>
        ))}
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={cols.length + 1} className="p-0">
            <EntityDetailPanel detail={detail} loading={detailLoading} row={row} type={type} />
          </td>
        </tr>
      )}
    </>
  );
}

function CellValue({ value, col }: { value: unknown; col: string }) {
  if (value == null || value === "") return <span className="text-[var(--text-muted)]">—</span>;
  if (col === "_confidence" && typeof value === "number") {
    const pct = Math.round(value * 100);
    const color = pct >= 70 ? "#2D8B5F" : pct >= 40 ? "#C48820" : "#C43D2F";
    return (
      <div className="flex items-center gap-1.5">
        <div className="w-10 h-1.5 rounded-full" style={{ background: "var(--border)" }}>
          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
        </div>
        <span className="font-mono text-[10px]" style={{ color }}>{pct}%</span>
      </div>
    );
  }
  if (col === "provenance" && Array.isArray(value)) {
    const sources = value.map((p: any) => p?.source_name || "").filter(Boolean);
    if (sources.length === 0) return <span className="text-[var(--text-muted)]">—</span>;
    return (
      <div className="flex flex-wrap gap-0.5">
        {sources.slice(0, 3).map((s: string, i: number) => (
          <span key={i} className="text-[8px] px-1 py-0.5 rounded-sm font-semibold text-white" style={{ background: "#6b7280" }}>{s}</span>
        ))}
        {sources.length > 3 && <span className="text-[8px] text-[var(--text-muted)]">+{sources.length - 3}</span>}
      </div>
    );
  }
  if (col === "provenance" && typeof value === "string") {
    return <span className="text-[9px] px-1.5 py-0.5 rounded-sm font-semibold text-white" style={{ background: "#6b7280" }}>{value}</span>;
  }
  if (col === "url" && typeof value === "string") {
    return (
      <a
        href={value}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[var(--accent)] flex items-center gap-1 hover:underline"
        onClick={(e) => e.stopPropagation()}
      >
        View <ExternalLink size={9} />
      </a>
    );
  }
  if (typeof value === "number") {
    return <span className="font-mono">{col.includes("score") ? value.toFixed(4) : value.toLocaleString()}</span>;
  }
  if (Array.isArray(value)) {
    return <span className="text-[var(--text-secondary)]">{value.slice(0, 3).join(", ")}{value.length > 3 ? ` +${value.length - 3}` : ""}</span>;
  }
  const str = String(value);
  return <span className="text-[var(--text-secondary)] truncate block" title={str}>{str.length > 80 ? str.slice(0, 80) + "…" : str}</span>;
}

/* ─── Entity Detail Panel (Inline Expansion) ─────────── */

function EntityDetailPanel({
  detail,
  loading,
  row,
  type,
}: {
  detail: EntityDetail | null;
  loading: boolean;
  row: Record<string, unknown>;
  type: string;
}) {
  const [activeTab, setActiveTab] = useState<"overview" | "publications" | "trials" | "patents" | "chembl">("overview");

  return (
    <div className="border-t px-6 py-4" style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}>
      {loading ? (
        <div className="flex items-center gap-2 py-4">
          <Loader2 size={16} className="animate-spin text-[var(--accent)]" />
          <span className="text-xs text-[var(--text-muted)]">Loading comprehensive entity data…</span>
        </div>
      ) : (
        <>
          {/* Detail tabs */}
          <div className="flex gap-1 mb-4 border-b" style={{ borderColor: "var(--border)" }}>
            {([
              { id: "overview" as const, label: "Overview", icon: <FileText size={12} /> },
              { id: "publications" as const, label: "Publications", icon: <BookOpen size={12} /> },
              { id: "trials" as const, label: "Clinical Trials", icon: <Microscope size={12} /> },
              { id: "patents" as const, label: "Patents", icon: <FileText size={12} /> },
              { id: "chembl" as const, label: "Drug Data", icon: <Pill size={12} /> },
            ]).map((tab) => (
              <button
                key={tab.id}
                onClick={(e) => { e.stopPropagation(); setActiveTab(tab.id); }}
                className={`flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium border-b-2 transition-colors -mb-px ${
                  activeTab === tab.id
                    ? "text-[var(--accent)] border-[var(--accent)]"
                    : "text-[var(--text-muted)] border-transparent hover:text-[var(--text-secondary)]"
                }`}
              >
                {tab.icon} {tab.label}
                {detail && tab.id === "publications" && detail.publications.length > 0 && (
                  <span className="text-[9px] bg-[var(--bg-inset)] px-1 rounded">{detail.publications.length}</span>
                )}
                {detail && tab.id === "trials" && detail.clinical_trials.length > 0 && (
                  <span className="text-[9px] bg-[var(--bg-inset)] px-1 rounded">{detail.clinical_trials.length}</span>
                )}
                {detail && tab.id === "patents" && detail.patents.length > 0 && (
                  <span className="text-[9px] bg-[var(--bg-inset)] px-1 rounded">{detail.patents.length}</span>
                )}
                {detail && tab.id === "chembl" && detail.chembl_data.length > 0 && (
                  <span className="text-[9px] bg-[var(--bg-inset)] px-1 rounded">{detail.chembl_data.length}</span>
                )}
              </button>
            ))}
          </div>

          {activeTab === "overview" && <OverviewTab detail={detail} row={row} type={type} />}
          {activeTab === "publications" && <RelatedItemsList items={detail?.publications || []} type="publication" />}
          {activeTab === "trials" && <RelatedItemsList items={detail?.clinical_trials || []} type="trial" />}
          {activeTab === "patents" && <RelatedItemsList items={detail?.patents || []} type="patent" />}
          {activeTab === "chembl" && <ChEMBLDataTab items={detail?.chembl_data || []} />}
        </>
      )}
    </div>
  );
}

function OverviewTab({ detail, row }: { detail: EntityDetail | null; row: Record<string, unknown>; type: string }) {
  const allProps = Object.entries(row).filter(([k]) => !HIDDEN_COLS.has(k) && k !== "id");

  return (
    <div className="space-y-4" onClick={(e) => e.stopPropagation()}>
      {detail?.description && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Sparkles size={12} className="text-[var(--accent)]" />
            <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
              AI Description
            </span>
          </div>
          <div className="text-xs leading-relaxed text-[var(--text-secondary)] p-3 rounded-lg" style={{ background: "var(--bg-elevated, var(--bg-app))", border: "1px solid var(--border)" }}>
            {detail.description}
          </div>
        </div>
      )}

      <div>
        <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
          Properties
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2">
          {allProps.map(([key, val]) => (
            <div key={key} className="text-xs">
              <span className="text-[var(--text-muted)] font-medium">{key.replace(/_/g, " ")}:</span>{" "}
              <span className="text-[var(--text-primary)]">
                {val == null ? "—" : Array.isArray(val) ? val.join(", ") : typeof val === "object" ? JSON.stringify(val) : String(val)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {!!row.url && (
        <div>
          <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
            External Resources
          </div>
          <div className="flex gap-2">
            <a
              href={String(row.url)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border hover:bg-[var(--bg-surface)] text-[var(--accent)]"
              style={{ borderColor: "var(--border)" }}
            >
              <ExternalLink size={11} /> Source Database
            </a>
            {!!row.pmid && (
              <a
                href={`https://pubmed.ncbi.nlm.nih.gov/${row.pmid}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border hover:bg-[var(--bg-surface)] text-[var(--accent)]"
                style={{ borderColor: "var(--border)" }}
              >
                <ExternalLink size={11} /> PubMed
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function RelatedItemsList({ items, type }: { items: Record<string, unknown>[]; type: string }) {
  if (items.length === 0) {
    return (
      <div className="text-xs text-[var(--text-muted)] py-4 text-center" onClick={(e) => e.stopPropagation()}>
        No {type}s found for this entity.
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-[400px] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
      {items.map((item, i) => (
        <div key={i} className="p-3 rounded-lg border text-xs hover:bg-[var(--bg-surface)]/50 transition-colors" style={{ borderColor: "var(--border)" }}>
          <div className="font-medium text-[var(--text-primary)] mb-1">
            {String(item.title || item.name || item.canonical_name || "Untitled")}
          </div>
          <div className="flex flex-wrap gap-3 text-[var(--text-muted)]">
            {!!item.year && <span>{String(item.year)}</span>}
            {!!item.journal && <span>{String(item.journal)}</span>}
            {!!item.authors && <span>{String(item.authors)}</span>}
            {!!item.phase && <span>Phase: {String(item.phase)}</span>}
            {!!item.status && <span>Status: {String(item.status)}</span>}
            {!!item.conditions && <span>Conditions: {String(item.conditions)}</span>}
            {!!item.patent_id && <span>{String(item.patent_id)}</span>}
            {!!item.assignee && <span>{String(item.assignee)}</span>}
            {!!item.filing_date && <span>{String(item.filing_date)}</span>}
            {!!item.nct_id && <span>{String(item.nct_id)}</span>}
            {!!item.pmid && <span>PMID: {String(item.pmid)}</span>}
          </div>
          {!!item.url && (
            <a href={String(item.url)} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] flex items-center gap-1 mt-1.5 hover:underline">
              View source <ExternalLink size={9} />
            </a>
          )}
        </div>
      ))}
    </div>
  );
}

function ChEMBLDataTab({ items }: { items: Record<string, unknown>[] }) {
  if (items.length === 0) {
    return (
      <div className="text-xs text-[var(--text-muted)] py-4 text-center" onClick={(e) => e.stopPropagation()}>
        No ChEMBL/drug data found for this entity.
      </div>
    );
  }

  return (
    <div className="space-y-3" onClick={(e) => e.stopPropagation()}>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="p-3 rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
            Drug Indications
          </div>
          {items.filter((i) => i.mechanism_of_action || i.drug_type).map((item, idx) => (
            <div key={idx} className="text-xs text-[var(--text-secondary)] mb-1">
              {!!item.mechanism_of_action && <div>{String(item.mechanism_of_action)}</div>}
              {!!item.drug_type && <div className="text-[var(--text-muted)]">Type: {String(item.drug_type)}</div>}
              {!!item.clinical_phase && <div className="text-[var(--text-muted)]">Phase: {String(item.clinical_phase)}</div>}
            </div>
          ))}
          {items.filter((i) => i.mechanism_of_action || i.drug_type).length === 0 && (
            <div className="text-xs text-[var(--text-muted)]">No indication data</div>
          )}
        </div>

        <div className="p-3 rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
            Molecule Features
          </div>
          {items.filter((i) => i.molecular_weight || i.logp || i.smiles).slice(0, 3).map((item, idx) => (
            <div key={idx} className="text-xs text-[var(--text-secondary)] mb-1">
              {!!item.molecular_weight && <div>MW: {String(item.molecular_weight)}</div>}
              {!!item.logp && <div>LogP: {String(item.logp)}</div>}
              {!!item.formula && <div>Formula: {String(item.formula)}</div>}
              {!!item.smiles && (
                <div className="font-mono text-[10px] text-[var(--text-muted)] truncate" title={String(item.smiles)}>
                  {String(item.smiles).slice(0, 60)}{String(item.smiles).length > 60 ? "…" : ""}
                </div>
              )}
            </div>
          ))}
          {items.filter((i) => i.molecular_weight || i.logp || i.smiles).length === 0 && (
            <div className="text-xs text-[var(--text-muted)]">No molecule data</div>
          )}
        </div>

        <div className="p-3 rounded-lg border" style={{ borderColor: "var(--border)" }}>
          <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
            Sources
          </div>
          <div className="space-y-1">
            {items.slice(0, 5).map((item, idx) => (
              <div key={idx} className="flex items-center justify-between text-xs">
                <span className="text-[var(--text-secondary)]">{String(item.name || item.id || `Entry ${idx + 1}`)}</span>
                {!!item.url && (
                  <a href={String(item.url)} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)]">
                    <ExternalLink size={10} />
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
