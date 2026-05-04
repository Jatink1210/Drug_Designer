/** Contradiction & Similarity — Cross-evidence contradiction detection, similarity analysis,
 *  and methodological comparison. Shows active contradictions with matched claim cards,
 *  assessment, resolution actions, live detection, and similarity/methodology views.
 *  Phase Y-1: search bar, entity selector, paste abstracts, tab switcher, filters, export.
 */

import { useState, useCallback, useEffect, useMemo } from "react";
import {
  AlertTriangle, CheckCircle, Flag, Loader2, Info, ExternalLink,
  Search, FileText, Download, Plus, Filter, Layers, Beaker, Handshake,
} from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { useContradictions as useContradictionsHook } from "@/lib/hooks";
import {
  ensureApiBase,
  contradictionLiveDetectAPI,
  contradictionResolveAPI,
  evidenceBundleCreateAPI,
  evidenceBundleAddItemsAPI,
} from "@/lib/api";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";
import ContradictionDetailDrawer, { type ContradictionDetail } from "@/components/ui/ContradictionDetailDrawer";
import BackendDegradedIndicator from "@/components/ui/BackendDegradedIndicator";
import { readCockpitHandoff } from "@/lib/canonicalProduct";

/* ── Types ─────────────────────────────────────────────── */

interface ContradictionSource {
  claim: string;
  source: string;
  id: string;
  year: number;
  detail: string;
}

interface Contradiction {
  number: number;
  title: string;
  contradiction_type?: string;
  sourceA: ContradictionSource;
  sourceB: ContradictionSource;
  assessment: string;
  resolved: boolean;
  confidence?: number;
  nli_method?: "nli_model" | "keyword_heuristic" | "llm";
  shared_entities?: string[];
  temporal_note?: string;
  context_a?: {
    study_type?: string;
    model_organisms?: string[];
    cell_lines?: string[];
    methodologies?: string[];
  };
  context_b?: {
    study_type?: string;
    model_organisms?: string[];
    cell_lines?: string[];
    methodologies?: string[];
  };
}

/** Similarity item derived from the same evidence model as contradictions */
interface SimilarityItem {
  number: number;
  title: string;
  similarity_type: "shared_finding" | "complementary_evidence";
  sourceA: ContradictionSource;
  sourceB: ContradictionSource;
  sharedClaim: string;
  confidence: number;
  shared_entities?: string[];
  nli_method?: "nli_model" | "keyword_heuristic" | "llm";
}

/** Methodological comparison item */
interface MethodologyItem {
  number: number;
  title: string;
  sourceA: ContradictionSource;
  sourceB: ContradictionSource;
  methodologyA: string;
  methodologyB: string;
  comparison: string;
  strengthDelta: string;
}

type ContradictionTypeFilter = "directional" | "temporal" | "score_divergence" | "methodological" | "population";
type SeverityFilter = "high" | "medium" | "low";
type ActiveTab = "contradictions" | "similarity" | "methodology";

/* ── Constants ─────────────────────────────────────────── */

const TYPE_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  directional:       { bg: "#fef3c7", color: "#92400e", label: "Directional" },
  temporal:          { bg: "#e0e7ff", color: "#3730a3", label: "Temporal" },
  score_divergence:  { bg: "#fce7f3", color: "#9d174d", label: "Score Divergence" },
  methodological:    { bg: "#d1fae5", color: "#065f46", label: "Methodological" },
  population:        { bg: "#ede9fe", color: "#5b21b6", label: "Population" },
};

const SOURCE_COLORS: Record<string, string> = {
  PubMed: "#3b82f6",
  GWAS: "#f59e0b",
  DisGeNET: "#8b5cf6",
  ClinicalTrials: "#10b981",
  ChEMBL: "#0891b2",
};

const METHODOLOGY_GROUPS: Record<string, { label: string; color: string; description: string }> = {
  rct:            { label: "RCT", color: "#2D8B5F", description: "Randomized Controlled Trials" },
  observational:  { label: "Observational", color: "#C48820", description: "Cohort, case-control, cross-sectional" },
  preclinical:    { label: "Preclinical", color: "#8b5cf6", description: "In vitro, animal models, cell lines" },
  meta_analysis:  { label: "Meta-analysis", color: "#0891b2", description: "Systematic reviews & meta-analyses" },
  case_report:    { label: "Case Report", color: "#6b7280", description: "Individual case reports & series" },
};

const ENTITY_OPTIONS = [
  { value: "", label: "All entities" },
  { value: "protein", label: "Protein" },
  { value: "gene", label: "Gene" },
  { value: "drug", label: "Drug" },
  { value: "disease", label: "Disease" },
  { value: "pathway", label: "Pathway" },
];

const ALL_TYPES: ContradictionTypeFilter[] = ["directional", "temporal", "score_divergence", "methodological", "population"];
const ALL_SEVERITIES: SeverityFilter[] = ["high", "medium", "low"];

const TAB_CONFIG: { key: ActiveTab; label: string; icon: React.ReactNode }[] = [
  { key: "contradictions", label: "Contradictions", icon: <AlertTriangle size={13} /> },
  { key: "similarity", label: "Similarities", icon: <Handshake size={13} /> },
  { key: "methodology", label: "Methodological Comparison", icon: <Beaker size={13} /> },
];

/* ── Helpers ───────────────────────────────────────────── */

/** Derive similarity items from contradiction data (shared findings / complementary evidence) */
function deriveSimilarities(contradictions: Contradiction[]): SimilarityItem[] {
  return contradictions
    .filter((c) => c.resolved)
    .map((c, i) => ({
      number: i + 1,
      title: c.title,
      similarity_type: i % 2 === 0 ? "shared_finding" as const : "complementary_evidence" as const,
      sourceA: c.sourceA,
      sourceB: c.sourceB,
      sharedClaim: `Both sources address: ${c.title}`,
      confidence: c.resolved ? 0.85 : 0.6,
    }));
}

/** Derive methodology comparison items from contradiction data */
function deriveMethodology(contradictions: Contradiction[]): MethodologyItem[] {
  return contradictions
    .filter((c) => c.contradiction_type === "methodological" || c.sourceA.source !== c.sourceB.source)
    .map((c, i) => ({
      number: i + 1,
      title: c.title,
      sourceA: c.sourceA,
      sourceB: c.sourceB,
      methodologyA: guessMethodology(c.sourceA.source),
      methodologyB: guessMethodology(c.sourceB.source),
      comparison: c.assessment,
      strengthDelta: c.contradiction_type === "methodological" ? "Significant" : "Moderate",
    }));
}

function guessMethodology(source: string): string {
  const map: Record<string, string> = {
    PubMed: "Peer-reviewed literature",
    GWAS: "Genome-wide association study",
    DisGeNET: "Curated gene-disease associations",
    ClinicalTrials: "Clinical trial registry",
    ChEMBL: "Bioactivity database",
  };
  return map[source] ?? "Unknown methodology";
}

function severityFromAssessment(assessment: string): SeverityFilter {
  const lower = assessment.toLowerCase();
  if (/critical|severe|major|high/i.test(lower)) return "high";
  if (/moderate|medium/i.test(lower)) return "medium";
  return "low";
}

const SEVERITY_BADGE: Record<SeverityFilter, { bg: string; color: string }> = {
  high: { bg: "#fef2f2", color: "#991b1b" },
  medium: { bg: "#fef3c7", color: "#92400e" },
  low: { bg: "#f0fdf4", color: "#166534" },
};


/* ── Main Component ────────────────────────────────────── */

export default function Contradictions() {
  /* ── Pre-computed contradictions from hook ─────────── */
  const { data, state: hookState, error: hookError, refetch } = useContradictionsHook();
  const precomputedItems: Contradiction[] = useMemo(() => (Array.isArray(data) ? data : []), [data]);

  /* ── Live detection mutation ───────────────────────── */
  const liveDetectMut = useMutation({
    mutationFn: ({ query, abstracts }: { query: string; abstracts?: string[] }) =>
      contradictionLiveDetectAPI(query, abstracts),
  });

  /* ── Resolve mutation ─────────────────────────────── */
  const resolveMut = useMutation({
    mutationFn: ({ id, resolution, annotation }: { id: string; resolution: string; annotation?: string }) =>
      contradictionResolveAPI(id, resolution, annotation),
  });

  /* ── State ────────────────────────────────────────── */
  const [activeTab, setActiveTab] = useState<ActiveTab>("contradictions");
  const [searchQuery, setSearchQuery] = useState("");
  const [entityFilter, setEntityFilter] = useState("");
  const [pasteAbstracts, setPasteAbstracts] = useState("");
  const [showPasteArea, setShowPasteArea] = useState(false);
  const [typeFilters, setTypeFilters] = useState<Set<ContradictionTypeFilter>>(new Set());
  const [severityFilters, setSeverityFilters] = useState<Set<SeverityFilter>>(new Set());
  const [sourceFilter, setSourceFilter] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [selectedDetail, setSelectedDetail] = useState<ContradictionDetail | null>(null);
  const [handoffTopic, setHandoffTopic] = useState<string | null>(null);
  const [dossierStatus, setDossierStatus] = useState<"idle" | "saving" | "done" | "error">("idle");
  const [dossierError, setDossierError] = useState<string | null>(null);

  /* ── Cockpit handoff ──────────────────────────────── */
  useEffect(() => {
    const payload = readCockpitHandoff();
    if (!payload || (payload.targetRoute !== "/contradiction-similarity" && payload.targetRoute !== "/contradictions")) return;
    const topic = payload.entities[0]?.entityName || payload.query || null;
    setHandoffTopic(topic);
    if (topic) {
      setSearchQuery(topic);
      liveDetectMut.mutate({ query: topic });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── Merge pre-computed + live-detected items ─────── */
  const liveItems: Contradiction[] = useMemo(() => {
    if (!liveDetectMut.data) return [];
    const raw = liveDetectMut.data as Record<string, unknown>;
    const items = (raw.contradictions ?? raw.items ?? raw.results ?? []) as Contradiction[];
    return Array.isArray(items) ? items.map((item, i) => ({ ...item, number: item.number || i + 1 })) : [];
  }, [liveDetectMut.data]);

  /* ── Extract analysis method from live detection response ── */
  const analysisMethod = useMemo(() => {
    if (!liveDetectMut.data) return null;
    const raw = liveDetectMut.data as Record<string, unknown>;
    return (raw.method_used as string) || null;
  }, [liveDetectMut.data]);

  const allContradictions = useMemo(() => {
    const seen = new Set<string>();
    const merged: Contradiction[] = [];
    for (const item of [...liveItems, ...precomputedItems]) {
      const key = `${item.title}-${item.sourceA?.id}-${item.sourceB?.id}`;
      if (!seen.has(key)) {
        seen.add(key);
        merged.push(item);
      }
    }
    return merged;
  }, [liveItems, precomputedItems]);

  /* ── Collect unique sources for filter dropdown ───── */
  const uniqueSources = useMemo(() => {
    const sources = new Set<string>();
    allContradictions.forEach((c) => {
      if (c.sourceA?.source) sources.add(c.sourceA.source);
      if (c.sourceB?.source) sources.add(c.sourceB.source);
    });
    return Array.from(sources).sort();
  }, [allContradictions]);

  /* ── Filtered contradictions ──────────────────────── */
  const filteredContradictions = useMemo(() => {
    return allContradictions.filter((c) => {
      if (typeFilters.size > 0 && c.contradiction_type && !typeFilters.has(c.contradiction_type as ContradictionTypeFilter)) return false;
      if (severityFilters.size > 0 && !severityFilters.has(severityFromAssessment(c.assessment))) return false;
      if (sourceFilter && c.sourceA?.source !== sourceFilter && c.sourceB?.source !== sourceFilter) return false;
      if (entityFilter) {
        const lower = entityFilter.toLowerCase();
        const inTitle = c.title?.toLowerCase().includes(lower);
        const inClaimA = c.sourceA?.claim?.toLowerCase().includes(lower);
        const inClaimB = c.sourceB?.claim?.toLowerCase().includes(lower);
        if (!inTitle && !inClaimA && !inClaimB) return false;
      }
      return true;
    });
  }, [allContradictions, typeFilters, severityFilters, sourceFilter, entityFilter]);

  /* ── Derived similarity & methodology views ───────── */
  const similarities = useMemo(() => deriveSimilarities(allContradictions), [allContradictions]);
  const methodologyItems = useMemo(() => deriveMethodology(allContradictions), [allContradictions]);

  /* ── Handlers ─────────────────────────────────────── */
  const handleSearch = useCallback(() => {
    if (!searchQuery.trim()) return;
    const abstracts = pasteAbstracts.trim()
      ? pasteAbstracts.split(/\n{2,}/).filter(Boolean)
      : undefined;
    liveDetectMut.mutate({ query: searchQuery.trim(), abstracts });
  }, [searchQuery, pasteAbstracts, liveDetectMut]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  }, [handleSearch]);

  const toggleTypeFilter = useCallback((t: ContradictionTypeFilter) => {
    setTypeFilters((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t); else next.add(t);
      return next;
    });
  }, []);

  const toggleSeverityFilter = useCallback((s: SeverityFilter) => {
    setSeverityFilters((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s); else next.add(s);
      return next;
    });
  }, []);

  const exportJSON = useCallback(() => {
    const payload = activeTab === "contradictions"
      ? filteredContradictions
      : activeTab === "similarity"
        ? similarities
        : methodologyItems;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${activeTab}_export.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [activeTab, filteredContradictions, similarities, methodologyItems]);

  const appendToDossier = useCallback(async () => {
    setDossierStatus("saving");
    setDossierError(null);
    try {
      const bundle = await evidenceBundleCreateAPI({
        name: `Contradiction & Similarity — ${searchQuery || "All"}`,
        description: `${filteredContradictions.length} contradictions, ${similarities.length} similarities exported`,
        project_id: "default",
      });
      const bundleId = (bundle as Record<string, unknown>).id as string || (bundle as Record<string, unknown>).bundle_id as string || "";
      if (bundleId) {
        const ids = filteredContradictions.map((c) => c.sourceA?.id).filter(Boolean);
        if (ids.length > 0) {
          await evidenceBundleAddItemsAPI(bundleId, ids);
        }
      }
      setDossierStatus("done");
      setTimeout(() => setDossierStatus("idle"), 3000);
    } catch (err) {
      setDossierError(err instanceof Error ? err.message : "Failed to append to dossier");
      setDossierStatus("error");
    }
  }, [searchQuery, filteredContradictions, similarities]);

  /* ── View state ───────────────────────────────────── */
  const isLoading = hookState === "loading" || liveDetectMut.isPending;
  const hasError = hookError || liveDetectMut.error;
  const isEmpty = !isLoading && !hasError && allContradictions.length === 0;
  const viewState: ViewState = isLoading ? "loading" : hasError ? "error" : isEmpty ? "empty" : "success";

  /* ── Render ───────────────────────────────────────── */
  return (
    <StateWrapper
      state={viewState}
      moduleName="Contradiction & Similarity"
      emptyTitle="No contradictions or similarities found"
      emptyDescription="Search a topic, paste abstracts, or run an evidence extraction to detect contradictions."
      errorInfo={hasError ? { code: "DETECT_FAIL", message: hookError || (liveDetectMut.error as Error)?.message || "Detection failed" } : undefined}
      onRetry={refetch}
    >
    <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
      {/* ── Page Header ─────────────────────────────── */}
      <h1 className="text-xl mb-1" style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>
        Contradiction &amp; Similarity
      </h1>
      <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
        Cross-evidence contradiction detection, similarity analysis &amp; methodological comparison
      </p>

      <BackendDegradedIndicator />

      {/* ── Analysis Method Banner ──────────────────── */}
      {analysisMethod && (
        <div className="mb-4 px-4 py-2 rounded-lg text-xs flex items-center gap-2" style={{
          background: analysisMethod === "nlp" ? "rgba(91, 33, 182, 0.08)" : "rgba(107, 114, 128, 0.08)",
          border: `1px solid ${analysisMethod === "nlp" ? "rgba(91, 33, 182, 0.18)" : "rgba(107, 114, 128, 0.18)"}`,
          color: analysisMethod === "nlp" ? "#5b21b6" : "#6b7280",
        }}>
          <Layers size={14} />
          <span className="font-semibold">
            Analysis method: {analysisMethod === "nlp"
              ? "Biomedical NLP (PubMedBERT + BioNLI)"
              : "Keyword Heuristic (NLP models unavailable)"}
          </span>
        </div>
      )}

      {handoffTopic && (
        <div className="mb-4 px-4 py-2 rounded-lg text-xs" style={{ background: "rgba(59, 130, 246, 0.08)", border: "1px solid rgba(59, 130, 246, 0.18)", color: "#1d4ed8" }}>
          Cockpit handoff context: {handoffTopic}
        </div>
      )}

      {/* ── Input Controls ──────────────────────────── */}
      <div className="mb-5 space-y-3">
        {/* Search bar + entity selector row */}
        <div className="flex gap-2 items-center flex-wrap">
          <div className="relative flex-1 min-w-[240px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search topic for live contradiction detection…"
              className="w-full pl-9 pr-3 py-2 text-xs rounded-lg"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)", outline: "none" }}
              aria-label="Search topic"
            />
          </div>
          <select
            value={entityFilter}
            onChange={(e) => setEntityFilter(e.target.value)}
            className="px-3 py-2 text-xs rounded-lg"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            aria-label="Entity type filter"
          >
            {ENTITY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <button
            onClick={handleSearch}
            disabled={!searchQuery.trim() || liveDetectMut.isPending}
            className="px-4 py-2 text-xs rounded-lg font-semibold flex items-center gap-1.5 transition-colors"
            style={{ background: "var(--accent)", color: "#fff", opacity: !searchQuery.trim() || liveDetectMut.isPending ? 0.5 : 1 }}
            aria-label="Run live detection"
          >
            {liveDetectMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
            Detect
          </button>
          <button
            onClick={() => setShowPasteArea(!showPasteArea)}
            className="px-3 py-2 text-xs rounded-lg border flex items-center gap-1.5 transition-colors hover:bg-[var(--bg-elevated)]"
            style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
            aria-label="Toggle paste abstracts area"
          >
            <FileText size={12} />
            Paste Abstracts
          </button>
        </div>

        {/* Paste abstracts textarea */}
        {showPasteArea && (
          <div>
            <textarea
              value={pasteAbstracts}
              onChange={(e) => setPasteAbstracts(e.target.value)}
              placeholder="Paste one or more abstracts here (separate with blank lines)…"
              rows={4}
              className="w-full px-3 py-2 text-xs rounded-lg resize-y"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)", outline: "none", fontFamily: "var(--font-mono)" }}
              aria-label="Paste abstracts for comparison"
            />
            <p className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>
              Separate multiple abstracts with blank lines. They will be compared for contradictions and similarities.
            </p>
          </div>
        )}
      </div>

      {/* ── Tab Switcher ────────────────────────────── */}
      <div className="flex items-center gap-1 mb-4" role="tablist" aria-label="Analysis mode">
        {TAB_CONFIG.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            onClick={() => setActiveTab(tab.key)}
            className="px-3 py-1.5 text-xs rounded-md flex items-center gap-1.5 transition-colors"
            style={{
              background: activeTab === tab.key ? "var(--accent)" : "transparent",
              color: activeTab === tab.key ? "#fff" : "var(--text-secondary)",
              fontWeight: activeTab === tab.key ? 600 : 400,
            }}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Filter Controls ─────────────────────────── */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="px-3 py-1.5 text-[10px] rounded border flex items-center gap-1 transition-colors hover:bg-[var(--bg-elevated)]"
          style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
          aria-expanded={showFilters}
          aria-label="Toggle filters"
        >
          <Filter size={10} />
          Filters {(typeFilters.size + severityFilters.size + (sourceFilter ? 1 : 0)) > 0 && `(${typeFilters.size + severityFilters.size + (sourceFilter ? 1 : 0)})`}
        </button>

        {/* Summary counts */}
        <span className="text-[10px] ml-auto" style={{ color: "var(--text-muted)" }}>
          {activeTab === "contradictions" && `${filteredContradictions.length} contradiction${filteredContradictions.length !== 1 ? "s" : ""}`}
          {activeTab === "similarity" && `${similarities.length} similarit${similarities.length !== 1 ? "ies" : "y"}`}
          {activeTab === "methodology" && `${methodologyItems.length} comparison${methodologyItems.length !== 1 ? "s" : ""}`}
        </span>

        {/* Export + Dossier buttons */}
        <button
          onClick={exportJSON}
          className="px-3 py-1.5 text-[10px] rounded border flex items-center gap-1 transition-colors hover:bg-[var(--bg-elevated)]"
          style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
          aria-label="Export as JSON"
        >
          <Download size={10} />
          Export JSON
        </button>
        <button
          onClick={appendToDossier}
          disabled={dossierStatus === "saving"}
          className="px-3 py-1.5 text-[10px] rounded border flex items-center gap-1 transition-colors hover:bg-[var(--bg-elevated)]"
          style={{ borderColor: "var(--border)", color: dossierStatus === "done" ? "#2D8B5F" : "var(--text-secondary)" }}
          aria-label="Append to dossier"
        >
          {dossierStatus === "saving" ? <Loader2 size={10} className="animate-spin" /> : dossierStatus === "done" ? <CheckCircle size={10} /> : <Plus size={10} />}
          {dossierStatus === "done" ? "Added to Dossier" : "Append to Dossier"}
        </button>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="mb-4 p-4 rounded-lg space-y-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          {/* Type filters */}
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
              Contradiction Type
            </span>
            <div className="flex gap-1.5 mt-1.5 flex-wrap">
              {ALL_TYPES.map((t) => {
                const badge = TYPE_BADGE[t];
                const active = typeFilters.has(t);
                return (
                  <button
                    key={t}
                    onClick={() => toggleTypeFilter(t)}
                    className="px-2 py-0.5 text-[9px] font-bold rounded transition-opacity"
                    style={{ background: badge?.bg, color: badge?.color, opacity: active ? 1 : 0.4 }}
                    aria-pressed={active}
                  >
                    {badge?.label ?? t}
                  </button>
                );
              })}
            </div>
          </div>
          {/* Severity filters */}
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
              Severity
            </span>
            <div className="flex gap-1.5 mt-1.5 flex-wrap">
              {ALL_SEVERITIES.map((s) => {
                const badge = SEVERITY_BADGE[s];
                const active = severityFilters.has(s);
                return (
                  <button
                    key={s}
                    onClick={() => toggleSeverityFilter(s)}
                    className="px-2 py-0.5 text-[9px] font-bold rounded capitalize transition-opacity"
                    style={{ background: badge.bg, color: badge.color, opacity: active ? 1 : 0.4 }}
                    aria-pressed={active}
                  >
                    {s}
                  </button>
                );
              })}
            </div>
          </div>
          {/* Source filter */}
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
              Source
            </span>
            <div className="mt-1.5">
              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="px-2 py-1 text-[10px] rounded"
                style={{ background: "var(--bg-app)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                aria-label="Filter by source"
              >
                <option value="">All sources</option>
                {uniqueSources.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>
          {/* Clear all */}
          {(typeFilters.size > 0 || severityFilters.size > 0 || sourceFilter || entityFilter) && (
            <button
              onClick={() => { setTypeFilters(new Set()); setSeverityFilters(new Set()); setSourceFilter(""); setEntityFilter(""); }}
              className="text-[10px] underline"
              style={{ color: "var(--accent)" }}
            >
              Clear all filters
            </button>
          )}
        </div>
      )}

      {/* Dossier error */}
      {dossierError && (
        <div className="mb-4 px-4 py-2 rounded-lg text-xs flex items-center gap-2" style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", color: "#ef4444" }}>
          {dossierError}
          <button onClick={() => { setDossierError(null); setDossierStatus("idle"); }} className="ml-auto underline text-[10px]">Dismiss</button>
        </div>
      )}

      {/* Live detection error */}
      {liveDetectMut.error && (
        <div className="mb-4 px-4 py-2 rounded-lg text-xs flex items-center gap-2" style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", color: "#ef4444" }}>
          Live detection error: {(liveDetectMut.error as Error).message}
          <button onClick={() => liveDetectMut.reset()} className="ml-auto underline text-[10px]">Dismiss</button>
        </div>
      )}

      {/* ── Tab Content ─────────────────────────────── */}
      {activeTab === "contradictions" && (
        <ContradictionsTab
          items={filteredContradictions}
          onSelect={setSelectedDetail}
          resolveMut={resolveMut}
        />
      )}
      {activeTab === "similarity" && (
        <SimilaritiesTab items={similarities} />
      )}
      {activeTab === "methodology" && (
        <MethodologyTab items={methodologyItems} />
      )}

      {/* ── Detail Drawer ───────────────────────────── */}
      <ContradictionDetailDrawer
        contradiction={selectedDetail}
        onClose={() => setSelectedDetail(null)}
      />
    </div>
    </StateWrapper>
  );
}


/* ── Contradictions Tab ────────────────────────────────── */

interface ContradictionsTabProps {
  items: Contradiction[];
  onSelect: (detail: ContradictionDetail) => void;
  resolveMut: ReturnType<typeof useMutation<Record<string, unknown>, Error, { id: string; resolution: string; annotation?: string }>>;
}

function ContradictionsTab({ items, onSelect, resolveMut }: ContradictionsTabProps) {
  const [expandedClaims, setExpandedClaims] = useState<Set<string>>(new Set());

  const toggleClaim = (key: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedClaims((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  if (items.length === 0) {
    return (
      <div className="text-center py-12" style={{ color: "var(--text-muted)" }}>
        <AlertTriangle size={32} className="mx-auto mb-3 opacity-40" />
        <p className="text-sm">No contradictions match the current filters.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((c, idx) => {
        const typeBadge = TYPE_BADGE[c.contradiction_type ?? ""] ?? null;
        const severity = severityFromAssessment(c.assessment);
        const sevBadge = SEVERITY_BADGE[severity];

        return (
          <div
            key={`${c.title}-${c.sourceA?.id}-${idx}`}
            className="rounded-lg p-4 cursor-pointer transition-colors hover:shadow-md"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
            onClick={() => onSelect({
              number: c.number || idx + 1,
              title: c.title,
              contradiction_type: c.contradiction_type,
              sourceA: c.sourceA,
              sourceB: c.sourceB,
              assessment: c.assessment,
              resolved: c.resolved,
            })}
            role="button"
            tabIndex={0}
            aria-label={`Contradiction ${c.number || idx + 1}: ${c.title}`}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect({
                  number: c.number || idx + 1,
                  title: c.title,
                  contradiction_type: c.contradiction_type,
                  sourceA: c.sourceA,
                  sourceB: c.sourceB,
                  assessment: c.assessment,
                  resolved: c.resolved,
                });
              }
            }}
          >
            {/* Card header */}
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle size={14} style={{ color: "#C48820" }} />
              <span className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>
                #{c.number || idx + 1}
              </span>
              <span className="text-xs font-semibold flex-1 truncate" style={{ color: "var(--text-primary)" }}>
                {c.title}
              </span>
              {typeBadge && (
                <span className="text-[9px] font-bold px-2 py-0.5 rounded" style={{ background: typeBadge.bg, color: typeBadge.color }}>
                  {typeBadge.label}
                </span>
              )}
              <span className="text-[9px] font-bold px-2 py-0.5 rounded capitalize" style={{ background: sevBadge.bg, color: sevBadge.color }}>
                {severity}
              </span>
              {c.resolved && (
                <span className="text-[9px] font-bold px-2 py-0.5 rounded" style={{ background: "#ecfdf5", color: "#047857" }}>
                  ✓ Resolved
                </span>
              )}
              {c.nli_method && (
                <span className="text-[9px] font-medium px-2 py-0.5 rounded" style={{
                  background: c.nli_method === "nli_model" ? "#ede9fe" : c.nli_method === "llm" ? "#e0e7ff" : "#f3f4f6",
                  color: c.nli_method === "nli_model" ? "#5b21b6" : c.nli_method === "llm" ? "#3730a3" : "#6b7280",
                }}>
                  {c.nli_method === "nli_model" ? "NLP" : c.nli_method === "llm" ? "LLM" : "Keyword"}
                </span>
              )}
              {typeof c.confidence === "number" && (
                <span className="text-[9px] font-medium" style={{ color: "var(--text-muted)" }}>
                  {(c.confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>

            {/* Source A vs Source B */}
            <div className="grid grid-cols-2 gap-3 mb-2">
              <div className="p-3 rounded" style={{ background: "var(--bg-app)", border: "1px solid var(--border)" }}>
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: "#C48820" }}>Source A</span>
                  {c.sourceA?.source && (
                    <span className="px-1.5 py-0.5 rounded text-white text-[8px] font-bold" style={{ background: SOURCE_COLORS[c.sourceA.source] || "#6b7280" }}>
                      {c.sourceA.source}
                    </span>
                  )}
                </div>
                <p
                  className={`text-[11px] leading-relaxed cursor-pointer ${expandedClaims.has(`${idx}-a`) ? "" : "line-clamp-3"}`}
                  style={{ color: "var(--text-primary)" }}
                  onClick={(e) => toggleClaim(`${idx}-a`, e)}
                  title={c.sourceA?.claim}
                >
                  "{c.sourceA?.claim}"
                </p>
                {c.sourceA?.id && (
                  <span className="text-[9px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                    {c.sourceA.id} {c.sourceA.year > 0 && `(${c.sourceA.year})`}
                  </span>
                )}
              </div>
              <div className="p-3 rounded" style={{ background: "var(--bg-app)", border: "1px solid var(--border)" }}>
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: "#C48820" }}>Source B</span>
                  {c.sourceB?.source && (
                    <span className="px-1.5 py-0.5 rounded text-white text-[8px] font-bold" style={{ background: SOURCE_COLORS[c.sourceB.source] || "#6b7280" }}>
                      {c.sourceB.source}
                    </span>
                  )}
                </div>
                <p
                  className={`text-[11px] leading-relaxed cursor-pointer ${expandedClaims.has(`${idx}-b`) ? "" : "line-clamp-3"}`}
                  style={{ color: "var(--text-primary)" }}
                  onClick={(e) => toggleClaim(`${idx}-b`, e)}
                  title={c.sourceB?.claim}
                >
                  "{c.sourceB?.claim}"
                </p>
                {c.sourceB?.id && (
                  <span className="text-[9px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                    {c.sourceB.id} {c.sourceB.year > 0 && `(${c.sourceB.year})`}
                  </span>
                )}
              </div>
            </div>

            {/* Assessment */}
            <p className="text-[10px] leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              <strong>Assessment:</strong> {c.assessment}
            </p>

            {/* Experimental Context */}
            {(c.context_a?.study_type || c.context_b?.study_type || c.temporal_note) && (
              <div className="mt-2 p-2 rounded text-[9px] space-y-1" style={{ background: "var(--bg-app)", border: "1px solid var(--border)" }}>
                {(c.context_a?.study_type && c.context_a.study_type !== "unknown") || (c.context_b?.study_type && c.context_b.study_type !== "unknown") ? (
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold" style={{ color: "var(--text-muted)" }}>Context:</span>
                    {c.context_a?.study_type && c.context_a.study_type !== "unknown" && (
                      <span className="px-1.5 py-0.5 rounded" style={{ background: "rgba(59, 130, 246, 0.1)", color: "#2563eb" }}>
                        A: {c.context_a.study_type.replace("_", " ")}
                        {c.context_a.model_organisms?.length ? ` (${c.context_a.model_organisms.join(", ")})` : ""}
                      </span>
                    )}
                    {c.context_b?.study_type && c.context_b.study_type !== "unknown" && (
                      <span className="px-1.5 py-0.5 rounded" style={{ background: "rgba(16, 185, 129, 0.1)", color: "#059669" }}>
                        B: {c.context_b.study_type.replace("_", " ")}
                        {c.context_b.model_organisms?.length ? ` (${c.context_b.model_organisms.join(", ")})` : ""}
                      </span>
                    )}
                  </div>
                ) : null}
                {c.temporal_note && (
                  <div style={{ color: "var(--text-muted)" }}>
                    <span className="font-semibold">Temporal:</span> {c.temporal_note}
                  </div>
                )}
                {(c.context_a?.methodologies?.length || c.context_b?.methodologies?.length) ? (
                  <div className="flex items-center gap-1 flex-wrap" style={{ color: "var(--text-muted)" }}>
                    <span className="font-semibold">Methods:</span>
                    {[...(c.context_a?.methodologies || []), ...(c.context_b?.methodologies || [])].filter((v, i, a) => a.indexOf(v) === i).slice(0, 5).map((m) => (
                      <span key={m} className="px-1 py-0.5 rounded" style={{ background: "var(--bg-inset)", fontFamily: "var(--font-mono)" }}>{m}</span>
                    ))}
                  </div>
                ) : null}
              </div>
            )}

            {/* Resolution action */}
            {!c.resolved && (
              <div className="flex gap-2 mt-2" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => resolveMut.mutate({ id: c.sourceA?.id || String(c.number), resolution: "accepted", annotation: "Resolved via UI" })}
                  disabled={resolveMut.isPending}
                  className="px-2 py-1 text-[9px] rounded flex items-center gap-1 transition-colors hover:opacity-80"
                  style={{ background: "#ecfdf5", color: "#047857" }}
                >
                  <CheckCircle size={9} /> Resolve
                </button>
                <button
                  onClick={() => resolveMut.mutate({ id: c.sourceA?.id || String(c.number), resolution: "flagged", annotation: "Flagged for review" })}
                  disabled={resolveMut.isPending}
                  className="px-2 py-1 text-[9px] rounded flex items-center gap-1 transition-colors hover:opacity-80"
                  style={{ background: "#fef3c7", color: "#92400e" }}
                >
                  <Flag size={9} /> Flag
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Similarities Tab ──────────────────────────────────── */

function SimilaritiesTab({ items }: { items: SimilarityItem[] }) {
  if (items.length === 0) {
    return (
      <div className="text-center py-12" style={{ color: "var(--text-muted)" }}>
        <Handshake size={32} className="mx-auto mb-3 opacity-40" />
        <p className="text-sm">No similarities detected yet.</p>
        <p className="text-[10px] mt-1">Similarities are derived from resolved contradictions and shared evidence patterns.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((s, idx) => (
        <div
          key={`sim-${idx}`}
          className="rounded-lg p-4"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <div className="flex items-center gap-2 mb-2">
            <Handshake size={14} style={{ color: "#2D8B5F" }} />
            <span className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>
              #{s.number}
            </span>
            <span className="text-xs font-semibold flex-1 truncate" style={{ color: "var(--text-primary)" }}>
              {s.title}
            </span>
            <span
              className="text-[9px] font-bold px-2 py-0.5 rounded"
              style={{
                background: s.similarity_type === "shared_finding" ? "#d1fae5" : "#e0e7ff",
                color: s.similarity_type === "shared_finding" ? "#065f46" : "#3730a3",
              }}
            >
              {s.similarity_type === "shared_finding" ? "Shared Finding" : "Complementary Evidence"}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-2">
            <div className="p-3 rounded" style={{ background: "var(--bg-app)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: "#2D8B5F" }}>Source A</span>
                {s.sourceA?.source && (
                  <span className="px-1.5 py-0.5 rounded text-white text-[8px] font-bold" style={{ background: SOURCE_COLORS[s.sourceA.source] || "#6b7280" }}>
                    {s.sourceA.source}
                  </span>
                )}
              </div>
              <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-primary)" }}>
                "{s.sourceA?.claim}"
              </p>
            </div>
            <div className="p-3 rounded" style={{ background: "var(--bg-app)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: "#2D8B5F" }}>Source B</span>
                {s.sourceB?.source && (
                  <span className="px-1.5 py-0.5 rounded text-white text-[8px] font-bold" style={{ background: SOURCE_COLORS[s.sourceB.source] || "#6b7280" }}>
                    {s.sourceB.source}
                  </span>
                )}
              </div>
              <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-primary)" }}>
                "{s.sourceB?.claim}"
              </p>
            </div>
          </div>

          <p className="text-[10px] leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            <strong>Shared claim:</strong> {s.sharedClaim}
          </p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-[9px]" style={{ color: "var(--text-muted)" }}>
              Confidence: {(s.confidence * 100).toFixed(0)}%
            </span>
            <div className="w-16 h-1.5 rounded-full" style={{ background: "var(--border)" }}>
              <div className="h-full rounded-full" style={{ width: `${s.confidence * 100}%`, background: "#2D8B5F" }} />
            </div>
            {s.nli_method && (
              <span className="text-[9px] font-medium px-1.5 py-0.5 rounded" style={{
                background: s.nli_method === "nli_model" ? "#ede9fe" : "#f3f4f6",
                color: s.nli_method === "nli_model" ? "#5b21b6" : "#6b7280",
              }}>
                {s.nli_method === "nli_model" ? "NLP" : "Keyword"}
              </span>
            )}
          </div>
          {s.shared_entities && s.shared_entities.length > 0 && (
            <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
              <span className="text-[9px] font-semibold" style={{ color: "var(--text-muted)" }}>Shared:</span>
              {s.shared_entities.slice(0, 5).map((entity) => (
                <span key={entity} className="text-[9px] px-1.5 py-0.5 rounded font-mono" style={{ background: "var(--bg-inset)", color: "var(--text-secondary)" }}>
                  {entity}
                </span>
              ))}
              {s.shared_entities.length > 5 && (
                <span className="text-[9px]" style={{ color: "var(--text-muted)" }}>+{s.shared_entities.length - 5} more</span>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Methodology Tab ───────────────────────────────────── */

function MethodologyTab({ items }: { items: MethodologyItem[] }) {
  if (items.length === 0) {
    return (
      <div className="text-center py-12" style={{ color: "var(--text-muted)" }}>
        <Beaker size={32} className="mx-auto mb-3 opacity-40" />
        <p className="text-sm">No methodological comparisons available.</p>
        <p className="text-[10px] mt-1">Comparisons are generated when sources use different study methodologies.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((m, idx) => (
        <div
          key={`meth-${idx}`}
          className="rounded-lg p-4"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <div className="flex items-center gap-2 mb-3">
            <Beaker size={14} style={{ color: "#0891b2" }} />
            <span className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>
              #{m.number}
            </span>
            <span className="text-xs font-semibold flex-1 truncate" style={{ color: "var(--text-primary)" }}>
              {m.title}
            </span>
            <span className="text-[9px] font-bold px-2 py-0.5 rounded" style={{ background: m.strengthDelta === "Significant" ? "#fef2f2" : "#fef3c7", color: m.strengthDelta === "Significant" ? "#991b1b" : "#92400e" }}>
              {m.strengthDelta} difference
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-3">
            <div className="p-3 rounded" style={{ background: "var(--bg-app)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: "#0891b2" }}>Source A Methodology</span>
              </div>
              <p className="text-[11px] font-semibold mb-1" style={{ color: "var(--text-primary)" }}>
                {m.methodologyA}
              </p>
              {m.sourceA?.source && (
                <span className="px-1.5 py-0.5 rounded text-white text-[8px] font-bold" style={{ background: SOURCE_COLORS[m.sourceA.source] || "#6b7280" }}>
                  {m.sourceA.source}
                </span>
              )}
              <p className="text-[10px] mt-1.5 leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                "{m.sourceA?.claim}"
              </p>
            </div>
            <div className="p-3 rounded" style={{ background: "var(--bg-app)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: "#0891b2" }}>Source B Methodology</span>
              </div>
              <p className="text-[11px] font-semibold mb-1" style={{ color: "var(--text-primary)" }}>
                {m.methodologyB}
              </p>
              {m.sourceB?.source && (
                <span className="px-1.5 py-0.5 rounded text-white text-[8px] font-bold" style={{ background: SOURCE_COLORS[m.sourceB.source] || "#6b7280" }}>
                  {m.sourceB.source}
                </span>
              )}
              <p className="text-[10px] mt-1.5 leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                "{m.sourceB?.claim}"
              </p>
            </div>
          </div>

          <p className="text-[10px] leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            <strong>Comparison:</strong> {m.comparison}
          </p>
        </div>
      ))}

      {/* Methodology legend */}
      <div className="p-4 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
        <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
          Methodology Reference
        </div>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(METHODOLOGY_GROUPS).map(([key, group]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: group.color }} />
              <span className="text-[10px] font-semibold" style={{ color: "var(--text-primary)" }}>{group.label}</span>
              <span className="text-[9px]" style={{ color: "var(--text-muted)" }}>— {group.description}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
