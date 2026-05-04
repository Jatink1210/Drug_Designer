/** Pathways Explorer — Multi-source pathway browser with enrichment, reconstruction & scientific features. */

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Search,
  GitBranch,
  ExternalLink,
  Layers,
  Loader2,
  Dna,
  Download,
  BarChart3,
  Filter,
  ChevronRight,
  ChevronDown,
  Network,
  Sparkles,
  RefreshCw,
  Beaker,
  Database,
  ArrowRight,
  List,
  LayoutGrid,
  Copy,
  Eye,
} from "lucide-react";
import { pathwaysSearchAPI, pathwaysDetailAPI, pathwaysEnrichmentAPI, pathwayExportAPI, pathwayDiseaseContextAPI } from "@/lib/api";
import { useSetPageConfidence } from "@/lib/PageConfidenceContext";
import StateWrapper from "@/components/ui/StateWrapper";
import BiologicalPathwayWorkbench from "@/components/pathways/BiologicalPathwayWorkbench";
import { readCockpitHandoff } from "@/lib/canonicalProduct";
import type { ViewState } from "@/lib/types";

type SourceKey = "all" | "reactome" | "kegg" | "wikipathways";
type TabMode = "search" | "enrichment";
type ViewMode = "diagram" | "compare" | "genes" | "stats";

interface PathwayResult {
  id: string;
  canonical_name: string;
  name?: string;
  description: string;
  species: string;
  url: string;
  pathway_id: string;
  source_db?: string;
}

const SOURCE_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  reactome:     { bg: "bg-indigo-50",  text: "text-indigo-600",  label: "Reactome" },
  kegg:         { bg: "bg-emerald-50", text: "text-emerald-600", label: "KEGG" },
  wikipathways: { bg: "bg-purple-50",  text: "text-purple-600",  label: "WikiPathways" },
};

export default function PathwaysPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [source, setSource] = useState<SourceKey>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<string>("reactome");
  const [tabMode, setTabMode] = useState<TabMode>("search");
  const [viewMode, setViewMode] = useState<ViewMode>("diagram");
  const [geneInput, setGeneInput] = useState("");
  const [filterSource, setFilterSource] = useState<string | null>(null);
  const [expandedGenes, setExpandedGenes] = useState(false);
  const [handoffBanner, setHandoffBanner] = useState<{ query: string; pathwayIds: string[]; entityCount: number } | null>(null);
  const [handoffEntities, setHandoffEntities] = useState<Array<Record<string, unknown>>>([]);
  const [compareId, setCompareId] = useState<string>("");
  const [compareSource, setCompareSource] = useState<string>("reactome");

  // ── Pagination state ─────────────────────────────────
  const [paginationState, setPaginationState] = useState<Record<string, { page: number; pageSize: number }>>({
    reactome: { page: 1, pageSize: 25 },
    kegg: { page: 1, pageSize: 25 },
    wikipathways: { page: 1, pageSize: 25 },
  });
  const [enrichmentResultId, setEnrichmentResultId] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<"svg" | "png" | "json">("json");

  useEffect(() => {
    const payload = readCockpitHandoff();
    if (!payload || payload.targetRoute !== "/pathways") return;
    const seededQuery = payload.entities[0]?.entityName || payload.query;
    if (seededQuery) setQuery(seededQuery);
    setHandoffEntities(payload.entities as unknown as Array<Record<string, unknown>>);
    setHandoffBanner({
      query: seededQuery || payload.query,
      pathwayIds: Array.isArray(payload.metadata?.pathwayIds) ? (payload.metadata?.pathwayIds as string[]) : [],
      entityCount: payload.entities.length,
    });
  }, []);

  // ── Debounce search input (300ms) ────────────────────
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [query]);

  // ── Multi-source search ──────────────────────────────
  const reactomeQ = useQuery({
    queryKey: ["pathwaySearch", debouncedQuery, "reactome"],
    queryFn: () => pathwaysSearchAPI(debouncedQuery, "reactome", 25),
    enabled: debouncedQuery.length >= 2 && (source === "all" || source === "reactome"),
  });
  const keggQ = useQuery({
    queryKey: ["pathwaySearch", debouncedQuery, "kegg"],
    queryFn: () => pathwaysSearchAPI(debouncedQuery, "kegg", 25),
    enabled: debouncedQuery.length >= 2 && (source === "all" || source === "kegg"),
  });
  const wikiQ = useQuery({
    queryKey: ["pathwaySearch", debouncedQuery, "wikipathways"],
    queryFn: () => pathwaysSearchAPI(debouncedQuery, "wikipathways", 25),
    enabled: debouncedQuery.length >= 2 && (source === "all" || source === "wikipathways"),
  });

  const isSearching = reactomeQ.isLoading || keggQ.isLoading || wikiQ.isLoading;

  // Tag each result with its source_db
  const allResults = useMemo(() => {
    const tagged = (arr: PathwayResult[] | undefined, src: string) =>
      (arr ?? []).map((r) => ({ ...r, source_db: (r.source_db || src).toLowerCase() }));
    let combined = [
      ...tagged(reactomeQ.data as PathwayResult[] | undefined, "reactome"),
      ...tagged(keggQ.data as PathwayResult[] | undefined, "kegg"),
      ...tagged(wikiQ.data as PathwayResult[] | undefined, "wikipathways"),
    ];
    if (filterSource) combined = combined.filter((r) => r.source_db === filterSource);
    return combined;
  }, [reactomeQ.data, keggQ.data, wikiQ.data, filterSource]);

  // Source counts for badges
  const sourceCounts = useMemo(() => ({
    reactome: (reactomeQ.data ?? []).length,
    kegg: (keggQ.data ?? []).length,
    wikipathways: (wikiQ.data ?? []).length,
    total: (reactomeQ.data ?? []).length + (keggQ.data ?? []).length + (wikiQ.data ?? []).length,
  }), [reactomeQ.data, keggQ.data, wikiQ.data]);

  // ── Detail for selected pathway ──────────────────────
  const detailQ = useQuery({
    queryKey: ["pathwayDetail", selectedId],
    queryFn: () => pathwaysDetailAPI(selectedId!),
    enabled: !!selectedId,
  });
  const detail = detailQ.data;
  const compareDetailQ = useQuery({
    queryKey: ["pathwayCompareDetail", compareId],
    queryFn: () => pathwaysDetailAPI(compareId),
    enabled: !!compareId,
  });
  const diseaseContextQ = useQuery({
    queryKey: ["pathwayDiseaseContext", selectedId, handoffBanner?.query || query],
    queryFn: () => pathwayDiseaseContextAPI(selectedId!, handoffBanner?.query || query),
    enabled: !!selectedId && !!(handoffBanner?.query || query),
  });

  // ── Enrichment mutation ──────────────────────────────
  const enrichMut = useMutation({
    mutationFn: (genes: string[]) => pathwaysEnrichmentAPI(genes),
  });

  // ── Export mutation ──────────────────────────────────
  const exportMut = useMutation({
    mutationFn: () => pathwayExportAPI(allResults.map((r) => r.pathway_id || r.id), "json"),
  });

  const setConfidence = useSetPageConfidence();
  useEffect(() => {
    const queried: string[] = [];
    if (reactomeQ.data) queried.push("Reactome");
    if (keggQ.data) queried.push("KEGG");
    if (wikiQ.data) queried.push("WikiPathways");
    if (queried.length > 0) {
      setConfidence({ freshness: "current", sourceCount: queried.length, sourcesQueried: queried });
    } else {
      setConfidence(null);
    }
    return () => setConfidence(null);
  }, [reactomeQ.data, keggQ.data, wikiQ.data, setConfidence]);

  const handleSelect = useCallback((pw: PathwayResult) => {
    setSelectedId(pw.pathway_id || pw.id);
    setSelectedSource((pw.source_db || "reactome").toLowerCase());
    if (compareId === pw.pathway_id || compareId === pw.id) {
      setCompareId("");
    }
  }, []);

  const handleEnrich = useCallback(() => {
    const genes = geneInput.split(/[\s,;]+/).filter(Boolean);
    if (genes.length > 0) enrichMut.mutate(genes);
  }, [geneInput, enrichMut]);

  const copyGenes = useCallback(() => {
    if (detail?.genes) navigator.clipboard.writeText(detail.genes.join(", "));
  }, [detail]);

  const primarySnapshot = useMemo(() => {
    if (!selectedId || !detail) return null;
    return {
      id: selectedId,
      name: detail.canonical_name || (detail as Record<string, unknown>).name as string || selectedId,
      source: SOURCE_STYLE[selectedSource]?.label || selectedSource,
      genes: Array.isArray(detail.genes) ? detail.genes : [],
      pathwayType: detail.canonical_name ? detail.canonical_name.toLowerCase() : selectedId.toLowerCase(),
    };
  }, [detail, selectedId, selectedSource]);

  const secondarySnapshot = useMemo(() => {
    if (!compareId || !compareDetailQ.data) return null;
    const compareDetail = compareDetailQ.data as Record<string, unknown> & { genes?: string[]; canonical_name?: string };
    return {
      id: compareId,
      name: compareDetail.canonical_name || String(compareDetail.name || compareId),
      source: SOURCE_STYLE[compareSource]?.label || compareSource,
      genes: Array.isArray(compareDetail.genes) ? compareDetail.genes : [],
      pathwayType: String(compareDetail.canonical_name || compareDetail.name || compareId).toLowerCase(),
    };
  }, [compareDetailQ.data, compareId, compareSource]);

  const viewState: ViewState = "success";

  return (
    <StateWrapper state={viewState} moduleName="Pathways">
    <div className="flex-1 flex overflow-hidden" style={{ background: "var(--bg-app)" }}>

      {/* ── Left — Search + Results ──────────────────── */}
      <div className="w-[320px] glass-sidebar border-r flex flex-col">
        {/* Tab switcher */}
        <div className="flex border-b" style={{ borderColor: "var(--border)" }}>
          {(["search", "enrichment"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTabMode(t)}
              className={`flex-1 px-3 py-2 text-[11px] font-semibold transition-colors ${
                tabMode === t
                  ? "text-[var(--accent)] border-b-2 border-[var(--accent)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              }`}
            >
              {t === "search" ? (
                <span className="flex items-center justify-center gap-1"><Search size={11} /> Search</span>
              ) : (
                <span className="flex items-center justify-center gap-1"><Beaker size={11} /> Enrichment</span>
              )}
            </button>
          ))}
        </div>

        {tabMode === "search" ? (
          <>
            {/* Search input & source tabs */}
            <div className="p-3 border-b" style={{ borderColor: "var(--border)" }}>
              {handoffBanner && (
                <div className="mb-3 px-3 py-2 rounded-lg text-[10px]" style={{ background: "rgba(8, 145, 178, 0.08)", border: "1px solid rgba(8, 145, 178, 0.18)", color: "#0f766e" }}>
                  Cockpit handoff: {handoffBanner.query || "Pathway context"}
                  {handoffBanner.pathwayIds.length > 0 ? ` • ${handoffBanner.pathwayIds.slice(0, 4).join(", ")}` : ""}
                  {handoffBanner.entityCount > 0 ? ` • ${handoffBanner.entityCount} carried entities` : ""}
                </div>
              )}
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search pathways (e.g., BRCA1, apoptosis)..."
                  className="w-full pl-8 pr-3 py-1.5 text-xs rounded border bg-[var(--bg-app)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                  style={{ borderColor: "var(--border)" }}
                />
              </div>
              {/* Source selector with count badges */}
              <div className="flex gap-1 mt-2">
                {(["all", "reactome", "kegg", "wikipathways"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => { setSource(s); setFilterSource(s === "all" ? null : s); setSelectedId(null); }}
                    className={`flex-1 px-1.5 py-1 rounded text-[10px] font-medium transition-colors flex items-center justify-center gap-1 ${
                      source === s
                        ? "bg-[var(--accent)] text-white"
                        : "text-[var(--text-muted)] hover:bg-[var(--bg-surface)]"
                    }`}
                  >
                    {s === "all" ? "All" : SOURCE_STYLE[s].label}
                    {debouncedQuery.length >= 2 && (
                      <span className={`text-[9px] px-1 rounded-full ${
                        source === s ? "bg-white/20" : "bg-[var(--bg-inset)]"
                      }`}>
                        {s === "all" ? sourceCounts.total : sourceCounts[s]}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Results list */}
            <div className="flex-1 overflow-y-auto p-2">
              {isSearching && debouncedQuery.length >= 2 && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 size={16} className="animate-spin text-[var(--text-muted)]" />
                  <span className="ml-2 text-xs text-[var(--text-muted)]">Querying {source === "all" ? "3 databases" : SOURCE_STYLE[source]?.label}...</span>
                </div>
              )}

              {!isSearching && allResults.length === 0 && debouncedQuery.length >= 2 && (
                <p className="text-xs text-[var(--text-muted)] p-2">No pathways found across selected sources.</p>
              )}

              {debouncedQuery.length < 2 && (
                <div className="text-center py-8">
                  <Layers size={32} className="text-slate-400 mx-auto mb-2" />
                  <p className="text-xs text-[var(--text-muted)]">Search across Reactome, KEGG & WikiPathways</p>
                  <p className="text-[10px] text-[var(--text-muted)] mt-1">Type at least 2 characters</p>
                </div>
              )}

              {allResults.map((pw) => {
                const srcStyle = SOURCE_STYLE[pw.source_db || "reactome"] ?? SOURCE_STYLE.reactome;
                const isActive = selectedId === (pw.pathway_id || pw.id);
                return (
                  <button
                    key={`${pw.source_db}-${pw.pathway_id || pw.id}`}
                    onClick={() => handleSelect(pw)}
                    className={`w-full text-left px-3 py-2.5 text-xs rounded mb-0.5 transition-colors ${
                      isActive ? "bg-indigo-50 text-[var(--accent)]" : "text-[var(--text-secondary)] hover:bg-[var(--bg-surface)]"
                    }`}
                  >
                    <div className="flex items-start gap-1.5">
                      <GitBranch size={12} className="mt-0.5 shrink-0 opacity-50" />
                      <div className="min-w-0 flex-1">
                        <div className="font-medium leading-tight truncate" title={(pw.canonical_name || pw.name || pw.id || "").replace(/<[^>]*>/g, "")}>
                          {(pw.canonical_name || pw.name || pw.id || "").replace(/<[^>]*>/g, "")}
                        </div>
                        <div className="flex items-center gap-1.5 mt-1">
                          <span className={`inline-block px-1.5 py-0.5 text-[9px] rounded font-medium ${srcStyle.bg} ${srcStyle.text}`}>
                            {srcStyle.label}
                          </span>
                          {pw.species && (
                            <span className="text-[9px] text-[var(--text-muted)]">{pw.species}</span>
                          )}
                        </div>
                        {pw.description && (
                          <div className="text-[10px] text-[var(--text-muted)] mt-0.5 line-clamp-2">
                            {pw.description.length > 80 ? pw.description.slice(0, 80) + "..." : pw.description}
                          </div>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Results footer with pagination */}
            {allResults.length > 0 && (
              <div className="p-2 border-t flex flex-col gap-2" style={{ borderColor: "var(--border)" }}>
                {/* Pagination controls per source */}
                {(["reactome", "kegg", "wikipathways"] as const).map((s) => {
                  const count = sourceCounts[s];
                  if (count <= 25 || (source !== "all" && source !== s)) return null;
                  const pg = paginationState[s] || { page: 1, pageSize: 25 };
                  const totalPages = Math.ceil(count / pg.pageSize);
                  if (totalPages <= 1) return null;
                  return (
                    <div key={s} className="flex items-center justify-between text-[10px]" style={{ color: "var(--text-muted)" }}>
                      <span className={`font-medium ${SOURCE_STYLE[s].text}`}>{SOURCE_STYLE[s].label}</span>
                      <div className="flex items-center gap-1">
                        <button
                          disabled={pg.page <= 1}
                          onClick={() => setPaginationState((prev) => ({ ...prev, [s]: { ...prev[s], page: prev[s].page - 1 } }))}
                          className="px-1.5 py-0.5 rounded border disabled:opacity-30"
                          style={{ borderColor: "var(--border)" }}
                        >
                          ←
                        </button>
                        <span>{pg.page}/{totalPages}</span>
                        <button
                          disabled={pg.page >= totalPages}
                          onClick={() => setPaginationState((prev) => ({ ...prev, [s]: { ...prev[s], page: prev[s].page + 1 } }))}
                          className="px-1.5 py-0.5 rounded border disabled:opacity-30"
                          style={{ borderColor: "var(--border)" }}
                        >
                          →
                        </button>
                      </div>
                    </div>
                  );
                })}
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-[var(--text-muted)]">
                    {allResults.length} pathway{allResults.length !== 1 ? "s" : ""}
                  </span>
                  <button
                    onClick={() => exportMut.mutate()}
                    disabled={exportMut.isPending}
                    className="flex items-center gap-1 text-[10px] text-[var(--accent)] hover:underline"
                  >
                    <Download size={10} /> Export All
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          /* ── Enrichment Tab ──────────────────────────── */
          <div className="flex-1 flex flex-col p-3">
            <p className="text-xs text-[var(--text-secondary)] mb-2">
              Paste a gene list to find enriched pathways across all databases.
            </p>
            <textarea
              value={geneInput}
              onChange={(e) => setGeneInput(e.target.value)}
              placeholder="BRCA1, TP53, EGFR, KRAS, PIK3CA..."
              className="w-full h-32 text-xs font-mono p-2 border rounded resize-none bg-[var(--bg-app)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              style={{ borderColor: "var(--border)" }}
            />
            <button
              onClick={handleEnrich}
              disabled={enrichMut.isPending || !geneInput.trim()}
              className="mt-2 w-full py-2 rounded text-xs font-semibold bg-[var(--accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              {enrichMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
              Run Enrichment Analysis
            </button>

            {/* Enrichment results */}
            {enrichMut.data && (
              <div className="mt-3 flex-1 overflow-y-auto space-y-1.5">
                <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">Enriched Pathways</div>
                {(enrichMut.data as Record<string, unknown>).id && (
                  <div className="text-[9px] text-[var(--text-muted)] mb-1">
                    Result ID: {String((enrichMut.data as Record<string, unknown>).id).slice(0, 8)}…
                  </div>
                )}
                {Object.entries(enrichMut.data as Record<string, unknown>).filter(([key]) => key !== "id" && key !== "input_genes" && key !== "total_pathways").map(([key, val]) => (
                  <div key={key} className="px-2 py-1.5 text-xs rounded bg-[var(--bg-surface)] border" style={{ borderColor: "var(--border)" }}>
                    <span className="font-medium text-[var(--text-primary)]">{key}</span>
                    <span className="ml-2 text-[var(--text-muted)]">{String(val)}</span>
                  </div>
                ))}
              </div>
            )}

            {enrichMut.isError && (
              <p className="mt-2 text-xs text-red-500">Enrichment failed. Check your gene list.</p>
            )}
          </div>
        )}
      </div>

      {/* ── Center — Pathway Viewer ─────────────────── */}
      <div className="flex-1 flex flex-col">
        {/* Viewer toolbar */}
        <div className="glass-panel border-b px-4 py-2 flex items-center gap-3">
          <GitBranch size={14} className="text-[var(--text-muted)]" />
          <span className="text-xs font-medium text-[var(--text-primary)]">
            {selectedId && detail ? (detail.canonical_name || detail.id) : "Pathway Viewer"}
          </span>
          {selectedId && (
            <span className={`px-1.5 py-0.5 text-[9px] rounded font-medium ${SOURCE_STYLE[selectedSource]?.bg || ""} ${SOURCE_STYLE[selectedSource]?.text || ""}`}>
              {SOURCE_STYLE[selectedSource]?.label || selectedSource}
            </span>
          )}
          <div className="ml-auto flex items-center gap-1">
            {(["diagram", "compare", "genes", "stats"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setViewMode(v)}
                className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                  viewMode === v
                    ? "bg-[var(--accent)] text-white"
                    : "text-[var(--text-muted)] hover:bg-[var(--bg-inset)]"
                }`}
              >
                {v === "diagram" ? <><LayoutGrid size={10} className="inline mr-1" />Synthesis</> :
                 v === "compare" ? <><Layers size={10} className="inline mr-1" />Compare</> :
                 v === "genes" ? <><Dna size={10} className="inline mr-1" />Genes</> :
                 <><BarChart3 size={10} className="inline mr-1" />Stats</>}
              </button>
            ))}
          </div>
        </div>

        {/* Main viewer area */}
        {!selectedId && (
          <div className="flex-1 flex items-center justify-center" style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.03) 0%, rgba(168,85,247,0.04) 50%, rgba(34,197,94,0.03) 100%)" }}>
            <div className="text-center max-w-lg">
              <div className="w-24 h-24 rounded-2xl mx-auto mb-6 flex items-center justify-center"
                   style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.12), rgba(168,85,247,0.12))" }}>
                <Network size={40} className="text-indigo-300" />
              </div>
              <h2 className="text-base font-semibold text-[var(--text-primary)] mb-2">Multi-Source Pathway Explorer</h2>
              <p className="text-sm text-[var(--text-muted)] mb-4 leading-relaxed">
                Search across Reactome, KEGG & WikiPathways to explore biological pathways,
                view interactive diagrams, and analyze pathway gene sets.
              </p>
              <div className="flex items-center justify-center gap-3 mb-6">
                {Object.entries(SOURCE_STYLE).map(([k, s]) => (
                  <div key={k} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg ${s.bg}`}>
                    <Database size={11} className={s.text} />
                    <span className={`text-[11px] font-semibold ${s.text}`}>{s.label}</span>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 justify-center flex-wrap">
                {["apoptosis", "MAPK signaling", "Wnt pathway", "cell cycle"].map((ex) => (
                  <button
                    key={ex}
                    onClick={() => setQuery(ex)}
                    className="px-3 py-1.5 text-xs rounded-full border hover:bg-indigo-50 hover:border-indigo-200 transition-colors"
                    style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {selectedId && viewMode === "diagram" && (
          <div className="flex-1 relative overflow-auto"
               style={{ background: "linear-gradient(180deg, rgba(99,102,241,0.02) 0%, rgba(255,255,255,0) 30%)" }}>
            {/* Disease context annotations */}
            {diseaseContextQ.data && Array.isArray((diseaseContextQ.data as Record<string, unknown>).rewired_genes) &&
              ((diseaseContextQ.data as Record<string, unknown>).rewired_genes as string[]).length > 0 && (
              <div className="absolute top-3 right-3 z-10 rounded-lg border p-3 max-w-[220px] shadow-sm"
                   style={{ background: "rgba(255,255,255,0.95)", borderColor: "var(--border)" }}>
                <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "#dc2626" }}>
                  Disease Context
                </div>
                <div className="flex flex-wrap gap-1">
                  {((diseaseContextQ.data as Record<string, unknown>).rewired_genes as string[]).slice(0, 10).map((gene) => (
                    <span key={gene} className="px-1.5 py-0.5 text-[9px] font-mono rounded" style={{ background: "#fef2f2", color: "#991b1b", border: "1px solid #fecaca" }}>
                      {gene}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {/* Export controls */}
            <div className="absolute top-3 left-3 z-10 flex items-center gap-1">
              <select
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value as "svg" | "png" | "json")}
                className="px-2 py-1 text-[10px] rounded border"
                style={{ borderColor: "var(--border)", background: "rgba(255,255,255,0.9)" }}
              >
                <option value="json">JSON</option>
                <option value="svg">SVG</option>
                <option value="png">PNG</option>
              </select>
              <button
                onClick={() => exportMut.mutate()}
                disabled={exportMut.isPending}
                className="px-2 py-1 text-[10px] rounded border flex items-center gap-1 hover:bg-[var(--bg-elevated)]"
                style={{ borderColor: "var(--border)", background: "rgba(255,255,255,0.9)", color: "var(--text-secondary)" }}
              >
                <Download size={10} /> Export
              </button>
            </div>
            <BiologicalPathwayWorkbench
              primary={primarySnapshot}
              carriedEntities={handoffEntities as Array<{ entityId: string; entityType: string; entityName: string; identifiers?: Record<string, string>; attributes?: Record<string, unknown>; sourceCategory?: string }>}
              diseaseContext={(diseaseContextQ.data as { rewired_genes?: string[]; context?: Record<string, unknown> } | undefined) || null}
              query={handoffBanner?.query || query}
            />
          </div>
        )}

        {selectedId && viewMode === "compare" && (
          <div className="flex-1 overflow-auto">
            <div className="px-4 pt-4 flex items-center gap-3 flex-wrap">
              <select
                value={compareId}
                onChange={(event) => {
                  const next = event.target.value;
                  setCompareId(next);
                  const nextResult = allResults.find((result) => (result.pathway_id || result.id) === next);
                  setCompareSource((nextResult?.source_db || "reactome").toLowerCase());
                }}
                className="px-3 py-2 rounded-lg border text-xs"
                style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
              >
                <option value="">Select pathway to compare</option>
                {allResults.filter((result) => (result.pathway_id || result.id) !== selectedId).slice(0, 20).map((result) => (
                  <option key={`${result.source_db}-${result.pathway_id || result.id}`} value={result.pathway_id || result.id}>
                    {result.canonical_name || result.name || result.pathway_id || result.id}
                  </option>
                ))}
              </select>
              {compareId && compareDetailQ.isLoading && <span className="text-xs text-[var(--text-muted)]">Loading comparison pathway…</span>}
            </div>

            {/* Side-by-side diff view */}
            {compareId && primarySnapshot && secondarySnapshot && (
              <div className="px-4 py-3">
                <div className="grid grid-cols-3 gap-3 mb-4">
                  {/* Shared genes */}
                  <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                    <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#2D8B5F" }}>
                      Shared Genes ({primarySnapshot.genes.filter((g: string) => secondarySnapshot.genes.includes(g)).length})
                    </div>
                    <div className="flex flex-wrap gap-1 max-h-40 overflow-y-auto">
                      {primarySnapshot.genes.filter((g: string) => secondarySnapshot.genes.includes(g)).map((gene: string) => (
                        <span key={gene} className="px-1.5 py-0.5 text-[9px] font-mono rounded" style={{ background: "#d1fae5", color: "#065f46" }}>
                          {gene}
                        </span>
                      ))}
                    </div>
                  </div>
                  {/* Unique to A */}
                  <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                    <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#6366f1" }}>
                      Unique to {primarySnapshot.name.slice(0, 20)} ({primarySnapshot.genes.filter((g: string) => !secondarySnapshot.genes.includes(g)).length})
                    </div>
                    <div className="flex flex-wrap gap-1 max-h-40 overflow-y-auto">
                      {primarySnapshot.genes.filter((g: string) => !secondarySnapshot.genes.includes(g)).slice(0, 50).map((gene: string) => (
                        <span key={gene} className="px-1.5 py-0.5 text-[9px] font-mono rounded" style={{ background: "#e0e7ff", color: "#3730a3" }}>
                          {gene}
                        </span>
                      ))}
                    </div>
                  </div>
                  {/* Unique to B */}
                  <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                    <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#a855f7" }}>
                      Unique to {secondarySnapshot.name.slice(0, 20)} ({secondarySnapshot.genes.filter((g: string) => !primarySnapshot.genes.includes(g)).length})
                    </div>
                    <div className="flex flex-wrap gap-1 max-h-40 overflow-y-auto">
                      {secondarySnapshot.genes.filter((g: string) => !primarySnapshot.genes.includes(g)).slice(0, 50).map((gene: string) => (
                        <span key={gene} className="px-1.5 py-0.5 text-[9px] font-mono rounded" style={{ background: "#f3e8ff", color: "#7c3aed" }}>
                          {gene}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <BiologicalPathwayWorkbench
              primary={primarySnapshot}
              secondary={secondarySnapshot || undefined}
              carriedEntities={handoffEntities as Array<{ entityId: string; entityType: string; entityName: string; identifiers?: Record<string, string>; attributes?: Record<string, unknown>; sourceCategory?: string }>}
              diseaseContext={(diseaseContextQ.data as { rewired_genes?: string[]; context?: Record<string, unknown> } | undefined) || null}
              query={handoffBanner?.query || query}
            />
          </div>
        )}

        {selectedId && viewMode === "genes" && (
          <div className="flex-1 overflow-y-auto p-6" style={{ background: "linear-gradient(180deg, rgba(99,102,241,0.02) 0%, rgba(255,255,255,0) 40%)" }}>
            {detailQ.isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 size={20} className="animate-spin text-[var(--text-muted)]" />
              </div>
            ) : detail?.genes && detail.genes.length > 0 ? (
              <div className="max-w-3xl mx-auto">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Dna size={15} className="text-[var(--accent)]" />
                    <span className="text-sm font-semibold text-[var(--text-primary)]">
                      {detail.gene_count} Gene{detail.gene_count !== 1 ? "s" : ""} in Pathway
                    </span>
                  </div>
                  <div className="flex gap-3">
                    <button onClick={copyGenes} className="flex items-center gap-1.5 text-[11px] text-[var(--accent)] hover:underline font-medium">
                      <Copy size={11} /> Copy List
                    </button>
                    <button
                      onClick={() => { setGeneInput(detail.genes.join(", ")); setTabMode("enrichment"); }}
                      className="flex items-center gap-1.5 text-[11px] text-[var(--accent)] hover:underline font-medium"
                    >
                      <Beaker size={11} /> Run Enrichment
                    </button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(expandedGenes ? detail.genes : detail.genes.slice(0, 60)).map((gene) => (
                    <span
                      key={gene}
                      className="px-2.5 py-1.5 text-[11px] font-mono rounded-lg bg-gradient-to-b from-white to-indigo-50 text-indigo-700 border border-indigo-100 shadow-sm hover:shadow hover:border-indigo-200 transition-all cursor-default"
                    >
                      {gene}
                    </span>
                  ))}
                </div>
                {detail.genes.length > 60 && (
                  <button
                    onClick={() => setExpandedGenes(!expandedGenes)}
                    className="mt-2 text-[10px] text-[var(--accent)] hover:underline flex items-center gap-1"
                  >
                    {expandedGenes ? "Show less" : `Show all ${detail.genes.length} genes`}
                    <ChevronDown size={10} className={expandedGenes ? "rotate-180" : ""} />
                  </button>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-xs text-[var(--text-muted)]">
                No gene data available for this pathway.
              </div>
            )}
          </div>
        )}

        {selectedId && viewMode === "stats" && (
          <div className="flex-1 overflow-y-auto p-6" style={{ background: "linear-gradient(180deg, rgba(99,102,241,0.02) 0%, rgba(255,255,255,0) 40%)" }}>
            {detailQ.isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 size={20} className="animate-spin text-[var(--text-muted)]" />
              </div>
            ) : (
              <div className="space-y-6 max-w-3xl mx-auto">
                <div className="flex items-center gap-2">
                  <BarChart3 size={16} className="text-[var(--accent)]" />
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">Pathway Statistics</h3>
                </div>

                {/* Stat cards */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="relative overflow-hidden p-4 rounded-xl bg-gradient-to-br from-indigo-50 to-indigo-100/50 border border-indigo-100 shadow-sm">
                    <div className="absolute -top-3 -right-3 w-16 h-16 rounded-full bg-indigo-200/30" />
                    <Dna size={14} className="text-indigo-400 mb-2" />
                    <div className="text-2xl font-bold text-indigo-600">{detail?.gene_count ?? 0}</div>
                    <div className="text-[11px] text-indigo-500 font-medium mt-0.5">Gene Count</div>
                  </div>
                  <div className="relative overflow-hidden p-4 rounded-xl bg-gradient-to-br from-emerald-50 to-emerald-100/50 border border-emerald-100 shadow-sm">
                    <div className="absolute -top-3 -right-3 w-16 h-16 rounded-full bg-emerald-200/30" />
                    <Layers size={14} className="text-emerald-400 mb-2" />
                    <div className="text-2xl font-bold text-emerald-600">{detail?.genes?.length ?? 0}</div>
                    <div className="text-[11px] text-emerald-500 font-medium mt-0.5">Unique Genes</div>
                  </div>
                  <div className="relative overflow-hidden p-4 rounded-xl bg-gradient-to-br from-purple-50 to-purple-100/50 border border-purple-100 shadow-sm">
                    <div className="absolute -top-3 -right-3 w-16 h-16 rounded-full bg-purple-200/30" />
                    <Database size={14} className="text-purple-400 mb-2" />
                    <div className="text-lg font-bold text-purple-600">
                      {SOURCE_STYLE[selectedSource]?.label ?? selectedSource}
                    </div>
                    <div className="text-[11px] text-purple-500 font-medium mt-0.5">Source Database</div>
                  </div>
                </div>

                {/* Source comparison chart */}
                {debouncedQuery.length >= 2 && (
                  <div className="rounded-xl border bg-white p-4 shadow-sm" style={{ borderColor: "var(--border)" }}>
                    <h4 className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wide mb-3">
                      Cross-Source Comparison — "{debouncedQuery}"
                    </h4>
                    <div className="space-y-3">
                      {(["reactome", "kegg", "wikipathways"] as const).map((s) => {
                        const count = sourceCounts[s];
                        const max = Math.max(sourceCounts.reactome, sourceCounts.kegg, sourceCounts.wikipathways, 1);
                        const pct = Math.round((count / max) * 100);
                        const style = SOURCE_STYLE[s];
                        const barColors: Record<string, string> = {
                          reactome: "bg-indigo-400",
                          kegg: "bg-emerald-400",
                          wikipathways: "bg-purple-400",
                        };
                        return (
                          <div key={s} className="flex items-center gap-3">
                            <span className={`w-24 text-[11px] font-semibold ${style.text}`}>{style.label}</span>
                            <div className="flex-1 h-7 rounded-lg bg-[var(--bg-surface)] relative overflow-hidden border border-slate-100">
                              <div
                                className={`h-full rounded-lg transition-all duration-700 ease-out ${barColors[s]}`}
                                style={{ width: `${Math.max(pct, 4)}%`, opacity: 0.85 }}
                              />
                              <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-slate-700">
                                {count} pathway{count !== 1 ? "s" : ""}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Detail info */}
                {detail && (
                  <div className="rounded-xl border bg-white p-4 shadow-sm space-y-2.5" style={{ borderColor: "var(--border)" }}>
                    <h4 className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wide mb-1">Pathway Info</h4>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="font-medium text-[var(--text-secondary)] w-14">ID</span>
                      <span className="font-mono text-[var(--text-muted)] px-2 py-0.5 rounded bg-[var(--bg-surface)] border border-slate-100">{detail.id}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="font-medium text-[var(--text-secondary)] w-14">Name</span>
                      <span className="text-[var(--text-primary)]">{detail.canonical_name || (detail as any).name || detail.id}</span>
                    </div>
                    {detail.url && (
                      <a
                        href={detail.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-xs text-[var(--accent)] hover:underline mt-1"
                      >
                        <ExternalLink size={11} /> View on {SOURCE_STYLE[selectedSource]?.label}
                      </a>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Participants bar */}
        {selectedId && detail?.genes && detail.genes.length > 0 && viewMode === "diagram" && (
          <div className="h-[100px] border-t px-4 py-2 flex flex-col" style={{ borderColor: "var(--border)", background: "linear-gradient(180deg, rgba(99,102,241,0.03), transparent)" }}>
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase flex items-center gap-1.5 tracking-wide">
                <Dna size={11} className="text-indigo-400" /> Participants · {detail.gene_count} genes
              </div>
              <button onClick={copyGenes} className="flex items-center gap-1 text-[9px] font-medium text-[var(--accent)] hover:underline">
                <Copy size={9} /> Copy All
              </button>
            </div>
            <div className="flex-1 overflow-x-auto overflow-y-hidden">
              <div className="flex gap-1.5 flex-nowrap pb-1">
                {detail.genes.slice(0, 40).map((gene) => (
                  <span
                    key={gene}
                    className="shrink-0 px-2.5 py-1 text-[10px] font-mono rounded-md bg-gradient-to-b from-white to-indigo-50 text-indigo-700 border border-indigo-100 shadow-sm"
                  >
                    {gene}
                  </span>
                ))}
                {detail.genes.length > 40 && (
                  <span className="shrink-0 px-2.5 py-1 text-[10px] font-medium text-[var(--text-muted)] rounded-md bg-[var(--bg-surface)] border border-slate-100">
                    +{detail.genes.length - 40} more
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Right — Pathway Details ──────────────────── */}
      <div className="w-[260px] glass-panel border-l flex flex-col">
        <div className="p-3 border-b" style={{ borderColor: "var(--border)" }}>
          <h3 className="text-xs font-semibold text-[var(--text-primary)]">Pathway Details</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          {!selectedId && (
            <div className="text-center py-6">
              <GitBranch size={24} className="text-slate-400 mx-auto mb-2" />
              <p className="text-xs text-[var(--text-muted)]">Select a pathway to see details</p>
            </div>
          )}

          {selectedId && detailQ.isLoading && (
            <div className="flex items-center justify-center py-6">
              <Loader2 size={16} className="animate-spin text-[var(--text-muted)]" />
            </div>
          )}

          {selectedId && detailQ.isError && (
            <p className="text-xs text-red-500">Failed to load pathway details.</p>
          )}

          {selectedId && detail && (
            <div className="space-y-3">
              {/* Info fields */}
              <div className="space-y-2 text-xs">
                <div>
                  <span className="font-medium text-[var(--text-secondary)]">ID:</span>
                  <span className="ml-1.5 text-[var(--text-muted)] font-mono">{detail.id}</span>
                </div>
                <div>
                  <span className="font-medium text-[var(--text-secondary)]">Source:</span>
                  <span className="ml-1.5">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${SOURCE_STYLE[selectedSource]?.bg} ${SOURCE_STYLE[selectedSource]?.text}`}>
                      {SOURCE_STYLE[selectedSource]?.label}
                    </span>
                  </span>
                </div>
                <div>
                  <span className="font-medium text-[var(--text-secondary)]">Name:</span>
                  <span className="ml-1.5 text-[var(--text-primary)]">{detail.canonical_name || (detail as any).name || detail.id}</span>
                </div>
                <div>
                  <span className="font-medium text-[var(--text-secondary)]">Gene Count:</span>
                  <span className="ml-1.5 text-[var(--text-primary)] font-bold">{detail.gene_count ?? 0}</span>
                </div>
              </div>

              {/* Actions */}
              <div className="pt-2 border-t space-y-1.5" style={{ borderColor: "var(--border)" }}>
                {detail.url && (
                  <a
                    href={detail.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-xs text-[var(--accent)] hover:underline"
                  >
                    <ExternalLink size={11} /> View on {SOURCE_STYLE[selectedSource]?.label}
                  </a>
                )}
                <button
                  onClick={() => setViewMode("compare")}
                  className="flex items-center gap-1.5 text-xs text-[var(--accent)] hover:underline"
                >
                  <Layers size={11} /> Compare against another pathway
                </button>
                <button
                  onClick={() => setViewMode("diagram")}
                  className="flex items-center gap-1.5 text-xs text-[var(--accent)] hover:underline"
                >
                  <LayoutGrid size={11} /> Open biological synthesis renderer
                </button>
                {diseaseContextQ.data && (
                  <div className="mt-2 rounded-lg border px-2 py-2 text-[10px]" style={{ borderColor: "var(--border)", background: "var(--bg-app)" }}>
                    <div className="font-semibold text-[var(--text-secondary)] mb-1">Disease context</div>
                    <div className="text-[var(--text-muted)]">
                      {Array.isArray((diseaseContextQ.data as Record<string, unknown>).rewired_genes) && ((diseaseContextQ.data as Record<string, unknown>).rewired_genes as string[]).length > 0
                        ? `${((diseaseContextQ.data as Record<string, unknown>).rewired_genes as string[]).length} rewired genes flagged`
                        : "No rewired genes returned. Canonical pathway membership shown."}
                    </div>
                  </div>
                )}
                <button onClick={copyGenes} className="flex items-center gap-1.5 text-xs text-[var(--accent)] hover:underline">
                  <Copy size={11} /> Copy Gene List
                </button>
                <button
                  onClick={() => { setGeneInput((detail.genes || []).join(", ")); setTabMode("enrichment"); }}
                  className="flex items-center gap-1.5 text-xs text-[var(--accent)] hover:underline"
                >
                  <Beaker size={11} /> Enrich from Genes
                </button>
              </div>

              {/* Gene chips */}
              {detail.genes && detail.genes.length > 0 && (
                <div className="pt-2 border-t" style={{ borderColor: "var(--border)" }}>
                  <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-1.5">
                    Top Genes
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {detail.genes.slice(0, 20).map((gene) => (
                      <span
                        key={gene}
                        className="px-1.5 py-0.5 text-[9px] rounded bg-[var(--bg-inset)] text-[var(--text-secondary)] font-mono"
                      >
                        {gene}
                      </span>
                    ))}
                    {detail.genes.length > 20 && (
                      <span className="px-1.5 py-0.5 text-[9px] text-[var(--text-muted)]">
                        +{detail.genes.length - 20} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Source comparison mini */}
              {debouncedQuery.length >= 2 && (
                <div className="pt-2 border-t" style={{ borderColor: "var(--border)" }}>
                  <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-1.5">
                    Results by Source
                  </div>
                  {(["reactome", "kegg", "wikipathways"] as const).map((s) => {
                    const st = SOURCE_STYLE[s];
                    return (
                      <div key={s} className="flex items-center justify-between py-0.5">
                        <span className={`text-[10px] ${st.text}`}>{st.label}</span>
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${st.bg} ${st.text}`}>
                          {sourceCounts[s]}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

    </div>
    </StateWrapper>
  );
}
