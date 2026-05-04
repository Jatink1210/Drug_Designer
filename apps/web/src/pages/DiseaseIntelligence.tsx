/** Disease Intelligence Page */
import { useState, useEffect } from "react";
import {
  Search,
  Download,
  FileSpreadsheet,
  AlertTriangle,
  Shield,
  CheckCircle,
  BarChart2,
  Brain,
  Loader2,
  Tag,
  Hash,
  Sparkles,
} from "lucide-react";
import { ensureApiBase } from "@/lib/api";
import { useSetPageConfidence } from "@/lib/PageConfidenceContext";
import { useRunProgress } from "@/lib/hooks";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "@/components/ui/StateWrapper";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from "recharts";

type Target = {
  target_id: string;
  symbol: string;
  name: string;
  overall_score: number;
  uniprot_id?: string;
  source_count?: number;
  sources?: string[];
};

type DiseaseInfo = {
  name: string;
  id?: string;
  iri?: string;
  ontology?: string;
  identifiers?: Record<string, string>;
  synonyms?: string[];
  confidence?: number;
};

export default function DiseaseIntelligence() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diseaseInfo, setDiseaseInfo] = useState<DiseaseInfo | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [llmSummary, setLlmSummary] = useState<string | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const wsProgress = useRunProgress(currentRunId);

  // §115: Derive 6-state ViewState for StateWrapper
  const viewState: ViewState = loading
    ? "loading"
    : error
      ? "error"
      : diseaseInfo
        ? targets.length === 0
          ? "empty"
          : "success"
        : "initial";

  const setConfidence = useSetPageConfidence();
  useEffect(() => {
    if (diseaseInfo) {
      setConfidence({ freshness: "current", sourceCount: 2, sourcesQueried: ["OpenTargets", "DisGeNET"] });
    } else {
      setConfidence(null);
    }
    return () => setConfidence(null);
  }, [diseaseInfo, setConfidence]);

  // When WS reports completion, clear run tracking and stop loading
  useEffect(() => {
    if (wsProgress?.isComplete) {
      setCurrentRunId(null);
      setLoading(false);
    }
  }, [wsProgress?.isComplete]);

  const analyzeDisease = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setDiseaseInfo(null);
    setTargets([]);
    setCurrentRunId(null);

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
      const di = data.disease_info;
      setDiseaseInfo({
        name: di?.name || query,
        id: di?.identifiers?.mondo_id || di?.identifiers?.mesh_id || di?.id || "",
        iri: di?.iri,
        ontology: di?.ontology,
        identifiers: di?.identifiers || {},
        synonyms: di?.synonyms || [],
        confidence: di?.confidence || 0,
      });
      const tgts = data.candidate_genes || data.targets || [];
      setTargets(tgts);

      // Fire LLM summary request in background
      fetchLLMSummary(di, tgts);
    } catch (e: any) {
      setError(e.message);
    } finally {
      if (!currentRunId) setLoading(false);
    }
  };

  const fetchLLMSummary = async (di: any, tgts: Target[]) => {
    if (!di?.name) return;
    setLlmLoading(true);
    setLlmSummary(null);
    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/disease/llm-summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          disease_name: di.name,
          synonyms: di.synonyms || [],
          identifiers: di.identifiers || {},
          top_targets: tgts.slice(0, 15).map((t) => ({
            symbol: t.symbol,
            name: t.name,
            overall_score: t.overall_score,
          })),
        }),
      });
      if (res.ok) {
        const envelope = await res.json();
        const summaryData = envelope?.data ?? envelope;
        setLlmSummary(summaryData.summary || null);
      }
    } catch {
      // Non-critical — LLM summary is optional
    }
    setLlmLoading(false);
  };

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
      // download failed — non-critical
    }
  };

  return (
    <div
      className="flex-1 overflow-y-auto"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-[1100px] mx-auto px-6 py-5">
        <div className="mb-6">
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">
            Disease Intelligence
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Normalize disease queries, fetch OpenTargets associations, and map
            UniProt targets.
          </p>
        </div>

        <div className="flex gap-4 mb-6 relative">
          <div className="relative flex-1">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
              size={16}
            />
            <input
              type="text"
              className="w-full glass-input text-sm py-2.5 pl-9 pr-4"
              placeholder="Enter a disease or indication (e.g. 'Alzheimers', 'Asthma')..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && analyzeDisease()}
            />
          </div>
          <button
            onClick={analyzeDisease}
            disabled={loading}
            className="glass-button text-sm px-6 font-medium"
          >
            {loading ? "Analyzing..." : "Analyze Disease"}
          </button>
        </div>

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

        {/* §115 StateWrapper: handles initial/loading/empty/error/success states */}
        <StateWrapper
          state={viewState}
          moduleName="Disease Intelligence"
          loadingMessage="Analyzing disease and querying targets…"
          emptyTitle="No targets found"
          emptyDescription="The disease was normalized but no associated targets were returned. Try a broader indication."
          errorInfo={error ? { code: "ANALYSIS_FAILED", message: error, recoverable: true } : undefined}
          onRetry={analyzeDisease}
        >
          {diseaseInfo && (
          <div className="space-y-6 mb-8">
            {/* Row 1: Normalized Ontology + Identifiers + Confidence */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="card p-5 col-span-1 md:col-span-2 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10">
                  <Shield size={100} />
                </div>
                <div className="flex items-center gap-2 mb-1">
                  <h2 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                    Normalized Ontology
                  </h2>
                  {diseaseInfo.confidence != null && diseaseInfo.confidence > 0 && (
                    <span className={`text-[9px] font-semibold px-2 py-0.5 rounded-full ${
                      diseaseInfo.confidence > 0.8 ? "bg-green-100 text-green-700" :
                      diseaseInfo.confidence > 0.5 ? "bg-amber-100 text-amber-700" :
                      "bg-red-100 text-red-700"
                    }`}>
                      {(diseaseInfo.confidence * 100).toFixed(0)}% confidence
                    </span>
                  )}
                </div>
                <div className="text-2xl font-bold text-[var(--text-primary)] mb-3">
                  {diseaseInfo.name}
                </div>

                {/* Identifiers grid */}
                {diseaseInfo.identifiers && Object.keys(diseaseInfo.identifiers).length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {Object.entries(diseaseInfo.identifiers).map(([key, val]) =>
                      val ? (
                        <span key={key} className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-[var(--bg-app)] border border-[var(--border)] text-[10px] font-mono">
                          <Hash size={9} className="text-[var(--accent)]" />
                          <span className="text-[var(--text-muted)] uppercase">{key.replace(/_/g, " ")}:</span>
                          <span className="text-[var(--text-primary)]">{val}</span>
                        </span>
                      ) : null
                    )}
                  </div>
                )}

                {/* Synonyms / alternative names */}
                {diseaseInfo.synonyms && diseaseInfo.synonyms.length > 1 && (
                  <div className="mt-2">
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-1.5 flex items-center gap-1">
                      <Tag size={10} /> Also Known As
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {diseaseInfo.synonyms.filter(s => s.toLowerCase() !== diseaseInfo.name.toLowerCase()).slice(0, 12).map((syn, i) => (
                        <span key={i} className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-[10px] border border-blue-200">
                          {syn}
                        </span>
                      ))}
                      {diseaseInfo.synonyms.length > 13 && (
                        <span className="px-2 py-0.5 rounded-full bg-[var(--bg-inset)] text-[var(--text-muted)] text-[10px]">
                          +{diseaseInfo.synonyms.length - 13} more
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {diseaseInfo.iri && (
                  <p className="text-[10px] text-[var(--text-muted)] break-all max-w-[80%] mt-2">
                    {diseaseInfo.iri}
                  </p>
                )}
              </div>

              <div className="card p-5 flex flex-col items-center justify-center text-center">
                <div className="text-sm font-semibold text-[var(--text-primary)] mb-2">
                  Decision Dossier
                </div>
                <p className="text-[10px] text-[var(--text-muted)] mb-4">
                  Export prioritized targets and normalized disease metadata as a
                  unified Excel report.
                </p>
                <button
                  onClick={downloadExcel}
                  className="glass-button flex items-center gap-2 py-2 px-4 shadow-sm"
                >
                  <FileSpreadsheet size={16} className="text-green-500" /> Export
                  Dossier
                </button>
              </div>
            </div>

            {/* Row 2: LLM Intelligence Summary */}
            <div className="card p-5 relative">
              <div className="flex items-center gap-2 mb-3">
                <Brain size={16} className="text-purple-500" />
                <h2 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                  AI Intelligence Briefing
                </h2>
                {llmLoading && <Loader2 size={14} className="animate-spin text-purple-400" />}
                {llmSummary && !llmLoading && (
                  <Sparkles size={12} className="text-amber-400" />
                )}
              </div>
              {llmLoading && !llmSummary && (
                <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] py-4">
                  <Loader2 size={14} className="animate-spin" />
                  Generating AI-powered disease intelligence briefing...
                </div>
              )}
              {llmSummary && (
                <div className="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-line">
                  {llmSummary}
                </div>
              )}
              {!llmLoading && !llmSummary && diseaseInfo && (
                <button
                  onClick={() => fetchLLMSummary(diseaseInfo, targets)}
                  className="text-xs px-3 py-1.5 rounded-lg border hover:bg-[var(--bg-surface)] flex items-center gap-1.5"
                  style={{ borderColor: "var(--border)" }}
                >
                  <Brain size={12} /> Generate AI Summary
                </button>
              )}
            </div>
          </div>
        )}

        {targets.length > 0 && (
          <div className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                <BarChart2 size={16} className="text-[var(--accent)]" />{" "}
                Prioritized Targets Array (Top {targets.length})
              </h2>
            </div>

            <div className="p-5 border-b border-border/50 h-[250px] w-full">
              <div role="img" aria-label="Target evidence score bar chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={targets.slice(0, 10)}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="symbol"
                    tick={{ fontSize: 10, fill: "var(--text-muted)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis hide domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--surface)",
                      borderColor: "var(--border)",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    itemStyle={{ color: "var(--text-primary)" }}
                  />
                  <Bar
                    dataKey="overall_score"
                    fill="var(--accent)"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={40}
                  />
                </BarChart>
              </ResponsiveContainer>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border bg-surface/50">
                    <th className="px-5 py-3 font-medium text-[var(--text-muted)]">
                      Target Identity
                    </th>
                    <th className="px-5 py-3 font-medium text-[var(--text-muted)]">
                      Symbol
                    </th>
                    <th className="px-5 py-3 font-medium text-[var(--text-muted)] text-right">
                      OT Score
                    </th>
                    <th className="px-5 py-3 font-medium text-[var(--text-muted)] text-center">
                      Sources
                    </th>
                    <th className="px-5 py-3 font-medium text-[var(--text-muted)]">
                      Database Evidence
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {targets.map((t, i) => (
                    <tr
                      key={i}
                      className="border-b border-border/50 hover:bg-surface/30 transition-colors"
                    >
                      <td className="px-5 py-3">
                        <div className="font-medium text-[var(--text-primary)]">
                          {t.name}
                        </div>
                        <div className="text-[10px] text-[var(--text-muted)] font-mono">
                          {t.target_id}
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <span className="px-2 py-1 rounded bg-surface border border-border font-mono text-amber-500/80">
                          {t.symbol}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <div className="font-mono text-[var(--accent)]">
                          {(t.overall_score || 0).toFixed(4)}
                        </div>
                        <div className="w-full h-1 rounded-full bg-gray-200 mt-1">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${(t.overall_score || 0) * 100}%`,
                              background: `linear-gradient(90deg, var(--accent), ${(t.overall_score || 0) > 0.7 ? "#10b981" : (t.overall_score || 0) > 0.4 ? "#f59e0b" : "#ef4444"})`,
                            }}
                          />
                        </div>
                      </td>
                      <td className="px-5 py-3 text-center">
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-50 text-blue-600 text-[10px] font-bold">
                          {t.source_count || 0}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex flex-wrap gap-1">
                          {(t.sources || []).map((src, si) => (
                            <span key={si} className="px-1.5 py-0.5 rounded text-[9px] bg-[var(--bg-app)] border border-[var(--border)] text-[var(--text-muted)]">
                              {src}
                            </span>
                          ))}
                          {(!t.sources || t.sources.length === 0) && (
                            <span className="text-[var(--text-muted)]">—</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        </StateWrapper>
      </div>
    </div>
  );
}
