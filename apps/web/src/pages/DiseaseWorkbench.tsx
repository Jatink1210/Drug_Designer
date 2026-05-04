/** DiseaseWorkbench — Unified disease analysis: Disease Intelligence + Target Prioritization + UniProt Mapping.
 *  Three-tab interface with shared disease context.
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  Download,
  FileSpreadsheet,
  AlertTriangle,
  Shield,
  CheckCircle,
  BarChart2,
  Target,
  ExternalLink,
  ChevronRight,
  RefreshCw,
  Link2,
  AlertCircle,
  Activity,
  Dna,
  Loader2,
  ArrowRight,
  Send,
  Box,
} from "lucide-react";
import { ensureApiBase, diseaseSendToTargetAPI, targetSendToDossierAPI } from "@/lib/api";
import { useSetPageConfidence } from "@/lib/PageConfidenceContext";
import { useRunProgress } from "@/lib/hooks";
import StateWrapper from "@/components/ui/StateWrapper";
import { readCockpitHandoff } from "@/lib/canonicalProduct";
import type { ViewState } from "@/components/ui/StateWrapper";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

/* ── Types ─────────────────────────────────────────────── */

type DiseaseTarget = {
  target_id: string;
  symbol: string;
  name: string;
  overall_score: number;
  uniprot_id?: string;
};

type DiseaseInfo = {
  name: string;
  id: string;
  iri?: string;
  ontology?: string;
};

interface TargetEvidence {
  source: string;
  title: string;
  id: string;
  year: number;
  type: string;
}

interface RankedTarget {
  rank: number;
  gene: string;
  uniprotId: string;
  score: number;
  ucbScore: number;
  uncertainty: number;
  sourceCount: number;
  contradictions: number;
  contradictionFlag: boolean;
  gdaScore: number;
  evidence: TargetEvidence[];
  rationale: string;
}

interface MappedProtein {
  input: string;
  uniprotId: string;
  name: string;
  length: number;
  gene: string;
  organism: string;
  evidenceLevel: number;
  resolved: boolean;
}

const SOURCE_COLORS: Record<string, string> = {
  DisGeNET: "#8b5cf6",
  OpenTargets: "#ef4444",
  PubMed: "#3b82f6",
  ChEMBL: "#0891b2",
  ClinicalTrials: "#10b981",
  KEGG: "#22c55e",
  GWAS: "#f59e0b",
  STRING: "#6366f1",
};

type TabId = "disease" | "targets" | "mapping";

/* ── Main Component ──────────────────────────────────── */

export default function DiseaseWorkbench() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabId>("disease");
  const [query, setQuery] = useState("");

  // Disease Intel state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diseaseInfo, setDiseaseInfo] = useState<DiseaseInfo | null>(null);
  const [diseaseTargets, setDiseaseTargets] = useState<DiseaseTarget[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [degradedSources, setDegradedSources] = useState<string[]>([]);
  const wsProgress = useRunProgress(currentRunId);

  // Target Prioritization state
  const [rankedTargets, setRankedTargets] = useState<RankedTarget[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<RankedTarget | null>(null);
  const [targetsLoading, setTargetsLoading] = useState(false);
  const [targetsError, setTargetsError] = useState<string | null>(null);

  // UniProt Mapping state
  const [proteins, setProteins] = useState<MappedProtein[]>([]);
  const [mappingLoading, setMappingLoading] = useState(false);

  const setConfidence = useSetPageConfidence();
  useEffect(() => {
    if (diseaseInfo) {
      setConfidence({ freshness: "current", sourceCount: 3, sourcesQueried: ["OpenTargets", "DisGeNET", "ChEMBL"] });
    } else {
      setConfidence(null);
    }
    return () => setConfidence(null);
  }, [diseaseInfo, setConfidence]);

  useEffect(() => {
    if (wsProgress?.isComplete) {
      setCurrentRunId(null);
      setLoading(false);
    }
  }, [wsProgress?.isComplete]);

  useEffect(() => {
    const payload = readCockpitHandoff();
    if (!payload || payload.targetRoute !== "/entity-intelligence") return;
    const entity = payload.entities[0];
    const seededQuery = entity?.entityName || payload.query;
    if (!seededQuery) return;
    setQuery(seededQuery);
    if (entity && ["gene", "protein", "target"].includes(entity.entityType)) {
      setActiveTab("targets");
    }
  }, []);

  const analyzeDisease = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setDiseaseInfo(null);
    setDiseaseTargets([]);
    setCurrentRunId(null);
    setDegradedSources([]);

    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/disease/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
        cache: "no-store",
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to analyze disease");
      }

      const envelope = await res.json();
      const data = envelope?.data ?? envelope;
      if (data.run_id) setCurrentRunId(data.run_id);
      setDiseaseInfo(data.disease_info);
      setDiseaseTargets(data.candidate_genes || data.targets || []);
      if (data.degraded_sources?.length) setDegradedSources(data.degraded_sources);
      else if (data.errors?.length) setDegradedSources(data.errors);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [query]);

  const fetchTargetPrioritization = useCallback(async () => {
    if (!diseaseInfo) return;
    setTargetsLoading(true);
    setTargetsError(null);
    try {
      const base = await ensureApiBase();
      const genes = diseaseTargets.slice(0, 20).map((t) => t.symbol).filter(Boolean);
      if (genes.length === 0) return;
      const res = await fetch(`${base}/targets/prioritize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ disease: diseaseInfo.name, genes }),
        cache: "no-store",
      });
      if (res.ok) {
        const data = await res.json();
        const payload = data?.data ?? data;
        if (payload.targets?.length) {
          const mapped: RankedTarget[] = payload.targets.map((t: Record<string, unknown>, idx: number) => ({
            rank: (t.rank as number) || idx + 1,
            gene: (t.symbol as string) || (t.gene as string) || "",
            uniprotId: (t.uniprotId as string) || "",
            score: (t.composite_score as number) || (t.score as number) || 0,
            ucbScore: (t.ucb_score as number) || 0,
            uncertainty: (t.uncertainty as number) || 0,
            sourceCount: (t.evidence_count as number) || (t.sourceCount as number) || 0,
            contradictions: (t.contradictions as number) || 0,
            contradictionFlag: (t.contradiction_flag as boolean) || false,
            gdaScore: (t.gdaScore as number) || (t.composite_score as number) || 0,
            evidence: Array.isArray(t.evidence) ? t.evidence as TargetEvidence[] : ((t.sources as string[]) || []).map((s: string) => ({ source: s, score: ((t.signals as Record<string, number>) || {})[s] || 0, detail: "" })),
            rationale: (t.explanation as string) || (t.rationale as string) || "",
          }));
          setRankedTargets(mapped);
          setSelectedTarget(mapped[0]);
        }
      }
    } catch (err: unknown) {
      setTargetsError(err instanceof Error ? err.message : "Network error");
    } finally {
      setTargetsLoading(false);
    }
  }, [diseaseInfo, diseaseTargets]);

  const fetchUniProtMapping = useCallback(async () => {
    setMappingLoading(true);
    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/evidence/uniprot-map`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        const payload = data?.data ?? data;
        if (Array.isArray(payload) && payload.length) setProteins(payload);
      }
    } catch {
      /* silent */
    } finally {
      setMappingLoading(false);
    }
  }, []);

  // Auto-fetch targets/mapping when switching tabs
  useEffect(() => {
    if (activeTab === "targets" && rankedTargets.length === 0 && diseaseTargets.length > 0) {
      fetchTargetPrioritization();
    }
    if (activeTab === "mapping" && proteins.length === 0) {
      fetchUniProtMapping();
    }
  }, [activeTab, rankedTargets.length, diseaseTargets.length, proteins.length, fetchTargetPrioritization, fetchUniProtMapping]);

  const downloadExcel = async () => {
    if (!query) return;
    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/disease/export_excel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: diseaseInfo?.name || query }),
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${diseaseInfo?.id || "disease"}_dossier.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      // download failed — non-critical, silently ignore
    }
  };

  const diseaseViewState: ViewState = loading
    ? "loading"
    : error
      ? "error"
      : diseaseInfo
        ? diseaseTargets.length === 0
          ? "empty"
          : degradedSources.length > 0
            ? "degraded"
            : "success"
        : "initial";

  const tabs: { id: TabId; label: string; icon: React.ReactNode; badge?: string }[] = [
    { id: "disease", label: "Disease Intelligence", icon: <Activity size={14} />, badge: diseaseTargets.length > 0 ? String(diseaseTargets.length) : undefined },
    { id: "targets", label: "Target Prioritization", icon: <Target size={14} />, badge: rankedTargets.length > 0 ? String(rankedTargets.length) : undefined },
    { id: "mapping", label: "UniProt Mapping", icon: <Link2 size={14} />, badge: proteins.length > 0 ? String(proteins.length) : undefined },
  ];

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-[1440px] mx-auto px-6 py-5">
        {/* Header */}
        <div className="mb-5">
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">Disease Workbench</h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Integrated disease analysis: normalize, prioritize targets, and map UniProt identifiers
          </p>
        </div>

        {/* Search bar */}
        <div className="card rounded-xl p-4 mb-5">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && analyzeDisease()}
                placeholder="Enter a disease or indication (e.g. 'Alzheimers', 'Asthma', 'NSCLC')…"
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
                style={{ borderColor: "var(--border)" }}
              />
            </div>
            <button
              onClick={analyzeDisease}
              disabled={loading || !query.trim()}
              className="px-6 py-2.5 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-40 hover:opacity-90"
              style={{ background: "var(--accent)" }}
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : "Analyze Disease"}
            </button>
            {diseaseInfo && (
              <button
                onClick={downloadExcel}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm hover:bg-[var(--bg-surface)]"
                style={{ borderColor: "var(--border)" }}
              >
                <FileSpreadsheet size={14} className="text-green-500" /> Export
              </button>
            )}
          </div>
        </div>

        {/* Progress bar */}
        {wsProgress && !wsProgress.isComplete && (
          <div className="flex items-center gap-3 px-4 py-2 rounded-lg text-xs mb-4" style={{ background: "var(--bg-surface)" }}>
            <div className="w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
            <span className="font-medium" style={{ color: "var(--accent)" }}>{wsProgress.stage || "Processing…"}</span>
            <div className="flex-1 h-1.5 rounded-full bg-[var(--bg-inset)] overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${wsProgress.progressPercent}%`, background: "var(--accent)" }} />
            </div>
            <span style={{ color: "var(--text-muted)" }}>{wsProgress.progressPercent}%</span>
            {wsProgress.sourcesTotal > 0 && (
              <span style={{ color: "var(--text-muted)" }}>{wsProgress.sourcesCompleted}/{wsProgress.sourcesTotal} sources</span>
            )}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-5 border-b" style={{ borderColor: "var(--border)" }}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors -mb-px ${
                activeTab === tab.id
                  ? "text-[var(--accent)] border-[var(--accent)]"
                  : "text-[var(--text-muted)] border-transparent hover:text-[var(--text-secondary)]"
              }`}
            >
              {tab.icon} {tab.label}
              {tab.badge && (
                <span className="text-[9px] bg-[var(--bg-inset)] text-[var(--text-secondary)] px-1.5 rounded-full font-semibold">
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "disease" && (
          <DiseaseIntelligenceTab
            viewState={diseaseViewState}
            diseaseInfo={diseaseInfo}
            targets={diseaseTargets}
            error={error}
            degradedSources={degradedSources}
            onRetry={analyzeDisease}
            onSendToTargetRanking={async () => {
              if (!diseaseInfo || diseaseTargets.length === 0) return;
              try {
                const symbols = diseaseTargets.map(t => t.symbol).filter(Boolean);
                await diseaseSendToTargetAPI(diseaseInfo.id, symbols);
                setActiveTab("targets");
                fetchTargetPrioritization();
              } catch {
                /* silently fall through — tab switch still happens */
                setActiveTab("targets");
              }
            }}
          />
        )}
        {activeTab === "targets" && (
          <TargetPrioritizationTab
            targets={rankedTargets}
            selected={selectedTarget}
            onSelect={setSelectedTarget}
            loading={targetsLoading}
            error={targetsError}
            onRetry={fetchTargetPrioritization}
            hasDisease={!!diseaseInfo}
            onOpenFullView={() => {
              const genes = rankedTargets.map(t => t.gene).join(",");
              const disease = diseaseInfo?.name || query;
              navigate(`/targets?disease=${encodeURIComponent(disease)}&genes=${encodeURIComponent(genes)}`);
            }}
            onSendToDossier={async () => {
              if (rankedTargets.length === 0) return;
              try {
                const symbols = rankedTargets.slice(0, 10).map(t => t.gene);
                await targetSendToDossierAPI(symbols, "draft");
                navigate("/dossiers");
              } catch {
                navigate("/dossiers");
              }
            }}
            onViewStructure={(gene: string) => navigate(`/structure/${encodeURIComponent(gene)}`)}
            onViewInGraph={(gene: string) => navigate(`/graph?entity=${encodeURIComponent(gene)}`)}
          />
        )}
        {activeTab === "mapping" && (
          <UniProtMappingTab proteins={proteins} loading={mappingLoading} onRetry={fetchUniProtMapping} />
        )}
      </div>
    </div>
  );
}

/* ── Disease Intelligence Tab ────────────────────────── */

function DiseaseIntelligenceTab({
  viewState,
  diseaseInfo,
  targets,
  error,
  onRetry,
  onSendToTargetRanking,
  degradedSources,
}: {
  viewState: ViewState;
  diseaseInfo: DiseaseInfo | null;
  targets: DiseaseTarget[];
  error: string | null;
  onRetry: () => void;
  onSendToTargetRanking: () => void;
  degradedSources?: string[];
}) {
  return (
    <StateWrapper
      state={viewState}
      moduleName="Disease Intelligence"
      loadingMessage="Analyzing disease and querying targets…"
      emptyTitle="No targets found"
      emptyDescription="The disease was normalized but no associated targets were returned. Try a broader indication."
      errorInfo={error ? { code: "ANALYSIS_FAILED", message: error, recoverable: true } : undefined}
      degradedInfo={degradedSources?.length ? { reason: "Some data sources were unavailable. Results may be incomplete.", affectedSources: degradedSources } : undefined}
      onRetry={onRetry}
    >
      {diseaseInfo && (
        <div className="space-y-6">
          {/* Normalized ontology card */}
          <div className="card p-5 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10">
              <Shield size={80} />
            </div>
            <h2 className="text-xs font-semibold text-[var(--text-muted)] mb-1 uppercase tracking-wider">
              Normalized Ontology
            </h2>
            <div className="text-2xl font-bold text-[var(--text-primary)] mb-2">
              {diseaseInfo.name}
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-[var(--text-secondary)] mb-2">
              <CheckCircle size={14} className="text-[var(--success, #10b981)]" />
              {diseaseInfo.id}
            </div>
            {diseaseInfo.iri && (
              <p className="text-xs text-[var(--text-muted)] break-all max-w-[80%]">{diseaseInfo.iri}</p>
            )}
          </div>

          {/* Target chart + table */}
          {targets.length > 0 && (
            <div className="card overflow-hidden">
              <div className="px-5 py-3 border-b flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
                <div className="flex items-center gap-2">
                  <BarChart2 size={14} className="text-[var(--accent)]" />
                  <span className="text-sm font-semibold text-[var(--text-primary)]">
                    Prioritized Targets ({targets.length})
                  </span>
                </div>
                <button
                  onClick={onSendToTargetRanking}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-all hover:opacity-90"
                  style={{ background: "var(--accent)" }}
                >
                  <Send size={12} /> Send to Target Ranking <ArrowRight size={12} />
                </button>
              </div>

              <div className="p-5 h-[250px] w-full border-b" style={{ borderColor: "var(--border)" }}>
                <div role="img" aria-label="Top disease-associated target scores bar chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={targets.slice(0, 15)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="symbol" tick={{ fontSize: 10, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
                    <YAxis hide domain={[0, 1]} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "var(--surface)", borderColor: "var(--border)", borderRadius: "8px", fontSize: "12px" }}
                      itemStyle={{ color: "var(--text-primary)" }}
                    />
                    <Bar dataKey="overall_score" fill="var(--accent)" radius={[4, 4, 0, 0]} maxBarSize={40} />
                  </BarChart>
                </ResponsiveContainer>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr style={{ background: "var(--bg-surface)" }}>
                      <th className="px-5 py-3 font-medium text-[var(--text-muted)]">Target Identity</th>
                      <th className="px-5 py-3 font-medium text-[var(--text-muted)]">Symbol</th>
                      <th className="px-5 py-3 font-medium text-[var(--text-muted)] text-right">OT Score</th>
                      <th className="px-5 py-3 font-medium text-[var(--text-muted)]">UniProt Mapping</th>
                    </tr>
                  </thead>
                  <tbody>
                    {targets.map((t, i) => (
                      <tr key={i} className="border-b hover:bg-[var(--bg-surface)]/30 transition-colors" style={{ borderColor: "var(--border)" }}>
                        <td className="px-5 py-3">
                          <div className="font-medium text-[var(--text-primary)]">{t.name}</div>
                          <div className="text-[10px] text-[var(--text-muted)] font-mono">{t.target_id}</div>
                        </td>
                        <td className="px-5 py-3">
                          <span className="px-2 py-1 rounded bg-[var(--bg-surface)] border font-mono text-amber-600 text-[11px]" style={{ borderColor: "var(--border)" }}>
                            {t.symbol}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-right font-mono text-[var(--accent)]">
                          {(t.overall_score || 0).toFixed(4)}
                        </td>
                        <td className="px-5 py-3">
                          {t.uniprot_id ? (
                            <span className="flex items-center gap-1.5 text-blue-500">
                              <CheckCircle size={12} /> {t.uniprot_id}
                            </span>
                          ) : (
                            <span className="text-[var(--text-muted)]">Unmapped</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </StateWrapper>
  );
}

/* ── Target Prioritization Tab ───────────────────────── */

function TargetPrioritizationTab({
  targets,
  selected,
  onSelect,
  loading,
  error,
  onRetry,
  hasDisease,
  onSendToDossier,
  onOpenFullView,
  onViewStructure,
  onViewInGraph,
}: {
  targets: RankedTarget[];
  selected: RankedTarget | null;
  onSelect: (t: RankedTarget) => void;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  hasDisease: boolean;
  onSendToDossier: () => void;
  onOpenFullView: () => void;
  onViewStructure: (gene: string) => void;
  onViewInGraph: (gene: string) => void;
}) {
  const viewState: ViewState = loading
    ? "loading"
    : error
      ? "error"
      : targets.length > 0
        ? "success"
        : hasDisease
          ? "empty"
          : "initial";

  return (
    <StateWrapper
      state={viewState}
      moduleName="Target Prioritization"
      loadingMessage="Ranking targets with multi-source scoring…"
      emptyTitle="No targets ranked"
      emptyDescription="Run Disease Intelligence first to generate candidate genes for ranking."
      errorInfo={error ? { code: "FETCH_FAILED", message: error, recoverable: true } : undefined}
      onRetry={onRetry}
    >
      {/* Action bar */}
      {targets.length > 0 && (
        <div className="flex items-center justify-between px-4 py-3 mb-4 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <span className="text-xs text-[var(--text-muted)]">
            {targets.length} targets ranked — select targets to take action
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={onOpenFullView}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:bg-[var(--bg-surface)]"
              style={{ borderColor: "var(--border)", color: "var(--accent)" }}
            >
              <ExternalLink size={12} /> Open Full View <ArrowRight size={10} />
            </button>
            <button
              onClick={onSendToDossier}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-all hover:opacity-90"
              style={{ background: "var(--accent)" }}
            >
              <Send size={12} /> Send Top 10 to Dossier
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-0 overflow-hidden rounded-lg" style={{ border: "1px solid var(--border)" }}>
        {/* Left: ranked list */}
        <div className="flex-1 overflow-y-auto max-h-[600px]" style={{ borderRight: "1px solid var(--border)" }}>
          <div className="px-4 py-3 flex items-center justify-between" style={{ background: "var(--bg-surface)" }}>
            <span className="text-xs font-semibold text-[var(--text-primary)]">
              {targets.length} targets ranked
            </span>
            <button
              onClick={onRetry}
              className="flex items-center gap-1 px-2 py-1 text-[10px] rounded border hover:bg-[var(--bg-surface)]"
              style={{ borderColor: "var(--border)", color: "var(--accent)" }}
            >
              <RefreshCw size={10} /> Re-rank
            </button>
          </div>
          {targets.map((t) => (
            <div
              key={t.gene}
              className="flex items-center gap-3 py-3 px-4 cursor-pointer transition-colors hover:bg-[var(--bg-surface)]/50"
              style={{
                borderBottom: "1px solid var(--border)",
                background: selected?.gene === t.gene ? "var(--accent-subtle, rgba(59,130,246,0.05))" : "transparent",
                borderLeft: selected?.gene === t.gene ? "3px solid var(--accent)" : "3px solid transparent",
              }}
              onClick={() => onSelect(t)}
            >
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0"
                style={{ background: t.rank <= 3 ? "var(--accent)" : "var(--border)", color: t.rank <= 3 ? "#fff" : "var(--text-muted)" }}
              >
                {t.rank}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{t.gene}</span>
                  <span className="text-[9px] font-mono text-[var(--text-muted)]">{t.uniprotId}</span>
                </div>
                <div className="flex items-center gap-3 mt-0.5">
                  <span className="text-[10px] text-[var(--text-muted)]">{t.sourceCount} sources</span>
                  {t.contradictions > 0 && (
                    <span className="text-[10px] flex items-center gap-0.5 text-amber-600">
                      <AlertTriangle size={9} /> {t.contradictions}
                    </span>
                  )}
                  <span className="text-[10px] text-[var(--text-muted)]">GDA: {t.gdaScore.toFixed(2)}</span>
                </div>
              </div>
              <div className="w-20 shrink-0">
                <div className="flex items-center justify-between text-[10px] font-semibold mb-0.5">
                  <span>Score</span>
                  <span style={{ color: "var(--accent)" }}>{t.score.toFixed(2)}</span>
                </div>
                <div className="w-full h-1.5 rounded-full" style={{ background: "var(--border)" }}>
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${t.score * 100}%`,
                      background: t.score > 0.8 ? "#2D8B5F" : t.score > 0.6 ? "#C48820" : "#C43D2F",
                    }}
                  />
                </div>
              </div>
              <ChevronRight size={14} className="text-[var(--text-muted)] shrink-0" />
            </div>
          ))}
        </div>

        {/* Right: inspector */}
        {selected && (
          <div className="w-[380px] shrink-0 overflow-y-auto max-h-[600px] p-5" style={{ background: "var(--bg-surface)" }}>
            <div className="flex items-center gap-2 mb-1">
              <Target size={18} className="text-[var(--accent)]" />
              <h2 className="text-lg font-bold" style={{ fontFamily: "var(--font-display)" }}>{selected.gene}</h2>
              <span className="text-[10px] px-1.5 py-0.5 rounded font-medium text-white" style={{ background: "var(--accent)" }}>
                Rank #{selected.rank}
              </span>
            </div>
            <div className="text-[11px] font-mono text-[var(--text-muted)] mb-4">
              UniProt: {selected.uniprotId}
            </div>

            {/* Score breakdown */}
            <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Score Breakdown</div>
            <div className="flex items-center gap-3 mb-4">
              <div className="flex-1">
                <div className="text-[10px] text-[var(--text-muted)]">Overall</div>
                <div className="text-lg font-bold text-[var(--accent)]">{selected.score.toFixed(2)}</div>
              </div>
              <div className="flex-1">
                <div className="text-[10px]" style={{ color: "#a78bfa" }}>UCB</div>
                <div className="text-lg font-bold" style={{ color: "#a78bfa" }}>{(selected.ucbScore ?? 0).toFixed(2)}</div>
                {(selected.uncertainty ?? 0) > 0 && (
                  <div className="text-[9px] text-[var(--text-muted)]">±{selected.uncertainty.toFixed(3)}</div>
                )}
              </div>
              <div className="flex-1">
                <div className="text-[10px] text-[var(--text-muted)]">GDA</div>
                <div className="text-lg font-bold">{selected.gdaScore.toFixed(2)}</div>
              </div>
              <div className="flex-1">
                <div className="text-[10px] text-[var(--text-muted)]">Sources</div>
                <div className="text-lg font-bold">{selected.sourceCount}</div>
              </div>
            </div>

            {/* Contradiction warning */}
            {selected.contradictionFlag && (
              <div className="mb-4 p-3 rounded-lg" style={{ background: "rgba(251, 191, 36, 0.08)", border: "1px solid rgba(251, 191, 36, 0.2)" }}>
                <div className="flex items-center gap-2 text-xs font-semibold" style={{ color: "#fbbf24" }}>
                  <AlertTriangle size={12} /> Contradictory evidence
                </div>
                <p className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>
                  Conflicting signals detected — review before advancing to design.
                </p>
              </div>
            )}

            {/* Rationale */}
            <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Why This Rank?</div>
            <div className="text-[11px] p-3 mb-4 leading-relaxed" style={{ color: "var(--text-secondary)", background: "var(--bg-elevated, var(--bg-app))", border: "1px solid var(--border)" }}>
              {selected.rationale}
            </div>

            {/* Source distribution */}
            <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Source Distribution</div>
            <div className="flex gap-1 h-5 mb-2">
              {selected.evidence.map((ev, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-sm"
                  style={{ background: SOURCE_COLORS[ev.source] || "#6b7280" }}
                  title={`${ev.source}: ${ev.title}`}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 mb-4">
              {[...new Set(selected.evidence.map((e) => e.source))].map((src) => (
                <span key={src} className="flex items-center gap-1 text-[9px]">
                  <span className="w-2 h-2 rounded-sm" style={{ background: SOURCE_COLORS[src] || "#6b7280" }} />
                  {src}
                </span>
              ))}
            </div>

            {/* Handoff actions */}
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => onViewStructure(selected.gene)}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[11px] font-medium border transition-colors hover:bg-[var(--bg-surface)]"
                style={{ borderColor: "var(--border)", color: "var(--accent)" }}
              >
                <Box size={12} /> View Structure
              </button>
              <button
                onClick={() => onViewInGraph(selected.gene)}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[11px] font-medium border transition-colors hover:bg-[var(--bg-surface)]"
                style={{ borderColor: "var(--border)", color: "var(--accent)" }}
              >
                <ExternalLink size={12} /> View in Graph
              </button>
            </div>

            {/* Evidence */}
            <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Evidence ({selected.evidence.length})
            </div>
            <div className="space-y-0 max-h-[300px] overflow-y-auto">
              {selected.evidence.map((ev, i) => (
                <div key={i} className="py-2 text-[11px]" style={{ borderBottom: "1px solid var(--border)" }}>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[8px] font-bold px-1 py-0.5 rounded-sm text-white" style={{ background: SOURCE_COLORS[ev.source] || "#6b7280" }}>
                      {ev.source}
                    </span>
                    <span className="text-[var(--text-secondary)] truncate">{ev.title}</span>
                  </div>
                  <div className="text-[9px] text-[var(--text-muted)] mt-0.5">
                    {ev.type} · {ev.year} · {ev.id}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </StateWrapper>
  );
}

/* ── UniProt Mapping Tab ─────────────────────────────── */

function UniProtMappingTab({
  proteins,
  loading,
  onRetry,
}: {
  proteins: MappedProtein[];
  loading: boolean;
  onRetry: () => void;
}) {
  const resolved = proteins.filter((p) => p.resolved);
  const unresolved = proteins.filter((p) => !p.resolved);

  const viewState: ViewState = loading ? "loading" : proteins.length === 0 ? "empty" : "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="UniProt Mapping"
      emptyTitle="No mapping results"
      emptyDescription="Run Disease Intelligence first—UniProt mappings will auto-populate."
      onRetry={onRetry}
    >
      <div>
        {/* Summary bar */}
        <div className="flex items-center gap-4 py-2.5 px-4 mb-5 rounded-lg" style={{ borderLeft: "3px solid var(--accent)", background: "var(--bg-surface)" }}>
          <span className="text-sm font-semibold" style={{ color: "var(--accent)" }}>{resolved.length} resolved</span>
          {unresolved.length > 0 && (
            <span className="text-sm font-semibold" style={{ color: "#C43D2F" }}>{unresolved.length} unresolved</span>
          )}
          <span className="text-xs text-[var(--text-muted)]">{proteins.length} total queries</span>
        </div>

        {/* Table */}
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr style={{ background: "var(--bg-surface)" }}>
                  <th className="text-left py-2.5 px-3 font-semibold text-[var(--text-muted)]">Input</th>
                  <th className="text-left py-2.5 px-3 font-semibold text-[var(--text-muted)]">UniProt ID</th>
                  <th className="text-left py-2.5 px-3 font-semibold text-[var(--text-muted)]">Protein Name</th>
                  <th className="text-right py-2.5 px-3 font-semibold text-[var(--text-muted)]">Length</th>
                  <th className="text-left py-2.5 px-3 font-semibold text-[var(--text-muted)]">Gene</th>
                  <th className="text-left py-2.5 px-3 font-semibold text-[var(--text-muted)]">Organism</th>
                  <th className="text-center py-2.5 px-3 font-semibold text-[var(--text-muted)]">Evidence</th>
                  <th className="text-center py-2.5 px-3 font-semibold text-[var(--text-muted)]">Status</th>
                </tr>
              </thead>
              <tbody>
                {proteins.map((p) => (
                  <tr key={p.input} className="border-t" style={{ borderColor: "var(--border)" }}>
                    <td className="py-2.5 px-3 font-semibold">{p.input}</td>
                    <td className="py-2.5 px-3 font-mono" style={{ color: p.resolved ? "var(--accent)" : "var(--text-muted)" }}>
                      {p.uniprotId}
                    </td>
                    <td className="py-2.5 px-3 text-[var(--text-secondary)]">{p.name}</td>
                    <td className="py-2.5 px-3 text-right">{p.length > 0 ? `${p.length} aa` : "—"}</td>
                    <td className="py-2.5 px-3 text-[var(--text-secondary)]">{p.gene}</td>
                    <td className="py-2.5 px-3 text-[var(--text-muted)]">{p.organism}</td>
                    <td className="py-2.5 px-3 text-center">
                      {p.evidenceLevel > 0 ? (
                        <span className="text-[10px] font-bold" style={{ color: p.evidenceLevel >= 4 ? "#2D8B5F" : "#C48820" }}>
                          {"★".repeat(p.evidenceLevel)}{"☆".repeat(Math.max(0, 5 - p.evidenceLevel))}
                        </span>
                      ) : (
                        <span className="text-[var(--text-muted)]">—</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {p.resolved ? (
                        <span className="flex items-center justify-center gap-1 text-green-600">
                          <CheckCircle size={12} /> Resolved
                        </span>
                      ) : (
                        <span className="flex items-center justify-center gap-1 text-amber-600">
                          <AlertCircle size={12} /> Retry
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </StateWrapper>
  );
}
