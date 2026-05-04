/** TargetPrioritization — Dynamic multi-signal target ranking (§74, §83, §122).
 *
 *  - Search bar: enter disease + genes (or pick from presets)
 *  - Ranked list: sorted by composite score, 7-signal breakdown bars
 *  - Inspector panel: signal radar, explanation, actions (→ Dossier, → Design Studio, → KG)
 *  - Wires to POST /api/v1/targets/prioritize (real backend scoring)
 */

import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Target,
  ExternalLink,
  ChevronRight,
  RefreshCw,
  Search,
  Loader2,
  Dna,
  Network,
  FileText,
  FlaskConical,
  Download,
  BarChart3,
  Zap,
  Info,
  AlertTriangle,
  Brain,
  Sparkles,
} from "lucide-react";
import { targetPrioritizeAPI, ensureApiBase } from "@/lib/api";
import type { PrioritizedTarget, TargetSignals } from "@/lib/api";
import { useSetPageConfidence } from "@/lib/PageConfidenceContext";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";

/* ── Signal display config ───────────── */
const SIGNAL_META: Record<string, { label: string; color: string; weight: number; description: string }> = {
  gwas:         { label: "GWAS",         color: "#f59e0b", weight: 0.25, description: "Genetic association strength from GWAS Catalog" },
  druggability: { label: "Druggability", color: "#8b5cf6", weight: 0.20, description: "Structural pocket quality & protein class" },
  pathways:     { label: "Pathways",     color: "#10b981", weight: 0.15, description: "Pathway centrality (KEGG, Reactome)" },
  expression:   { label: "Expression",   color: "#3b82f6", weight: 0.10, description: "Disease-tissue expression specificity" },
  novelty:      { label: "Novelty",      color: "#ec4899", weight: 0.10, description: "Less-explored = higher novelty bonus" },
  safety:       { label: "Safety",       color: "#22c55e", weight: 0.10, description: "Off-target risk & selectivity penalty" },
  literature:   { label: "Literature",   color: "#6366f1", weight: 0.10, description: "Publication evidence linking gene to disease" },
};

/* ── Presets ───────────── */
const PRESETS: { label: string; disease: string; genes: string[] }[] = [
  { label: "NSCLC", disease: "NSCLC", genes: ["EGFR", "ALK", "KRAS", "MET", "ROS1", "BRAF", "RET", "NTRK1"] },
  { label: "Alzheimer's", disease: "Alzheimer", genes: ["APP", "PSEN1", "PSEN2", "APOE", "MAPT", "BACE1", "TREM2", "BIN1"] },
  { label: "Breast Cancer", disease: "Breast Cancer", genes: ["BRCA1", "BRCA2", "HER2", "ESR1", "PIK3CA", "TP53", "CDK4", "PTEN"] },
  { label: "Type 2 Diabetes", disease: "Type 2 Diabetes", genes: ["TCF7L2", "PPARG", "KCNJ11", "SLC30A8", "GLP1R", "DPP4", "SGLT2", "INSR"] },
  { label: "Parkinson's", disease: "Parkinson", genes: ["SNCA", "LRRK2", "PARK7", "PINK1", "GBA", "PRKN", "VPS35", "MAPT"] },
];

export default function TargetPrioritization() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [disease, setDisease] = useState(searchParams.get("disease") || "");
  const [genesInput, setGenesInput] = useState(searchParams.get("genes") || "");
  const [targets, setTargets] = useState<PrioritizedTarget[]>([]);
  const [selected, setSelected] = useState<PrioritizedTarget | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [viewState, setViewState] = useState<ViewState>("initial");
  const [runId, setRunId] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [llmInsight, setLlmInsight] = useState<string | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [degradedSources, setDegradedSources] = useState<string[]>([]);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const fetchTargetLLM = useCallback(async (t: PrioritizedTarget, d: string) => {
    setLlmLoading(true);
    setLlmInsight(null);
    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/disease/llm-summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          disease_name: d,
          synonyms: [],
          identifiers: {},
          top_targets: [{ symbol: t.symbol, name: t.symbol, overall_score: t.composite_score }],
        }),
      });
      if (res.ok) {
        const envelope = await res.json();
        setLlmInsight((envelope?.data ?? envelope)?.summary || null);
      }
    } catch { /* non-critical */ }
    setLlmLoading(false);
  }, []);

  const setConfidence = useSetPageConfidence();
  useEffect(() => {
    if (targets.length > 0) {
      setConfidence({ freshness: "current", sourceCount: targets[0]?.sources.length ?? 0, sourcesQueried: targets[0]?.sources ?? [] });
    } else {
      setConfidence(null);
    }
    return () => setConfidence(null);
  }, [targets, setConfidence]);

  const runPrioritize = useCallback(async (d: string, g: string[]) => {
    if (!d.trim() || g.length === 0) return;
    setLoading(true);
    setFetchError(null);
    setViewState("loading");
    setSelected(null);
    setDegradedSources([]);
    const t0 = performance.now();
    try {
      const result = await targetPrioritizeAPI(d.trim(), g);
      setElapsedMs(Math.round(performance.now() - t0));
      if (result.targets?.length) {
        setTargets(result.targets);
        setSelected(result.targets[0]);
        setRunId(result.run_id);
        if (result.degraded_sources && result.degraded_sources.length > 0) {
          setDegradedSources(result.degraded_sources);
          setViewState("degraded");
        } else {
          setViewState("success");
        }
      } else {
        setTargets([]);
        setViewState("empty");
      }
    } catch (err: unknown) {
      setFetchError(err instanceof Error ? err.message : "Network error");
      setViewState("error");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSubmit = useCallback(() => {
    const genes = genesInput.split(/[,;\s]+/).map((g) => g.trim().toUpperCase()).filter(Boolean);
    if (!disease.trim() || genes.length === 0) return;
    setSearchParams({ disease: disease.trim(), genes: genes.join(",") });
    runPrioritize(disease.trim(), genes);
  }, [disease, genesInput, runPrioritize, setSearchParams]);

  const applyPreset = useCallback((preset: typeof PRESETS[0]) => {
    setDisease(preset.disease);
    setGenesInput(preset.genes.join(", "));
    setSearchParams({ disease: preset.disease, genes: preset.genes.join(",") });
    runPrioritize(preset.disease, preset.genes);
  }, [runPrioritize, setSearchParams]);

  // Auto-run from URL params
  useEffect(() => {
    const d = searchParams.get("disease");
    const g = searchParams.get("genes");
    if (d && g) {
      const genes = g.split(",").filter(Boolean);
      if (genes.length > 0 && targets.length === 0 && !loading) {
        setDisease(d);
        setGenesInput(genes.join(", "));
        runPrioritize(d, genes);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleExport = useCallback(() => {
    if (targets.length === 0) return;
    const header = "rank,symbol,composite_score,ucb_score,uncertainty,gwas,druggability,pathways,expression,novelty,safety,literature,evidence_count,contradiction\n";
    const rows = targets.map((t) =>
      `${t.rank},${t.symbol},${t.composite_score},${t.ucb_score ?? 0},${t.uncertainty ?? 0},${t.signals.gwas ?? 0},${t.signals.druggability ?? 0},${t.signals.pathways ?? 0},${t.signals.expression ?? 0},${t.signals.novelty ?? 0},${t.signals.safety ?? 0},${t.signals.literature ?? 0},${t.evidence_count},${t.contradiction_flag ? "YES" : "no"}`
    ).join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `targets_${disease.replace(/\s+/g, "_")}.csv`; a.click();
    URL.revokeObjectURL(url);
  }, [targets, disease]);

  const scoreColor = (s: number) => s > 0.6 ? "#2D8B5F" : s > 0.3 ? "#C48820" : "#C43D2F";

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ background: "var(--bg-app)" }}>
      {/* Search bar */}
      <div className="shrink-0 px-6 pt-5 pb-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2 mb-2">
          <Target size={18} style={{ color: "var(--accent)" }} />
          <h1 className="text-lg" style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>
            Target Prioritization
          </h1>
          <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "rgba(139,92,246,0.1)", color: "#8b5cf6", fontWeight: 600 }}>
            §83 Composite Score
          </span>
        </div>

        <div className="flex gap-2 items-end">
          <div className="flex-shrink-0" style={{ width: 200 }}>
            <label className="text-[9px] font-bold uppercase tracking-wider block mb-1" style={{ color: "var(--text-muted)" }}>Disease</label>
            <input
              value={disease}
              onChange={(e) => setDisease(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder="e.g. NSCLC, Alzheimer"
              className="w-full text-[12px] px-2.5 py-1.5 rounded"
              style={{ border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-primary)", outline: "none" }}
            />
          </div>
          <div className="flex-1">
            <label className="text-[9px] font-bold uppercase tracking-wider block mb-1" style={{ color: "var(--text-muted)" }}>
              Candidate Genes (comma-separated)
            </label>
            <input
              value={genesInput}
              onChange={(e) => setGenesInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder="e.g. EGFR, ALK, KRAS, MET, BRAF"
              className="w-full text-[12px] px-2.5 py-1.5 rounded"
              style={{ border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-primary)", outline: "none" }}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={loading || !disease.trim() || !genesInput.trim()}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded text-[11px] font-semibold shrink-0"
            style={{
              background: loading ? "var(--bg-surface)" : "var(--accent)",
              color: loading ? "var(--text-muted)" : "#fff",
              border: "none",
              cursor: loading || !disease.trim() || !genesInput.trim() ? "not-allowed" : "pointer",
              opacity: loading || !disease.trim() || !genesInput.trim() ? 0.6 : 1,
            }}
          >
            {loading ? <><Loader2 size={11} className="animate-spin" /> Scoring…</> : <><Zap size={11} /> Prioritize</>}
          </button>
        </div>

        {/* Presets */}
        <div className="flex items-center gap-1.5 mt-2">
          <span className="text-[9px] font-medium" style={{ color: "var(--text-muted)" }}>Presets:</span>
          {PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => applyPreset(p)}
              disabled={loading}
              className="text-[10px] px-2 py-0.5 rounded-full font-medium transition-colors"
              style={{ background: "var(--bg-surface)", color: "var(--accent)", border: "1px solid var(--border)", cursor: loading ? "not-allowed" : "pointer" }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main content */}
      <StateWrapper
        state={viewState}
        moduleName="Target Prioritization"
        emptyTitle="No targets ranked"
        emptyDescription="Enter a disease and candidate genes above, or select a preset to get started."
        errorInfo={fetchError ? { code: "FETCH_FAILED", message: fetchError, recoverable: true, suggestedAction: "Check network and retry" } : undefined}
        degradedInfo={degradedSources.length > 0 ? { reason: "Some scoring sources were unavailable. Results are partial.", affectedSources: degradedSources } : undefined}
        onRetry={handleSubmit}
      >
      <div className="flex-1 flex overflow-hidden">
        {/* Left — ranked list */}
        <div className="flex-1 overflow-y-auto p-4" style={{ borderRight: "1px solid var(--border)" }}>
          {/* Stats bar */}
          <div className="flex flex-wrap gap-2 mb-3">
            {[
              { label: "Targets", value: targets.length, color: "#8b5cf6" },
              { label: "Disease", value: disease, color: "#3b82f6" },
              { label: "Signals", value: "7-dim", color: "#10b981" },
              { label: "Time", value: `${(elapsedMs / 1000).toFixed(1)}s`, color: "#6b7280" },
              ...(runId ? [{ label: "Run", value: runId.slice(0, 8), color: "#f59e0b" }] : []),
            ].map((s) => (
              <span key={s.label} className="flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded"
                style={{ background: `${s.color}10`, color: s.color, border: `1px solid ${s.color}20` }}>
                <BarChart3 size={9} /> {s.label}: {s.value}
              </span>
            ))}
            {targets.length > 0 && (
              <button onClick={handleExport} className="flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded ml-auto"
                style={{ border: "1px solid var(--border)", color: "var(--text-muted)" }}>
                <Download size={9} /> CSV
              </button>
            )}
          </div>

          {/* Ranked target rows */}
          {targets.map((t) => {
            const isActive = selected?.symbol === t.symbol;
            const isExpanded = expandedRows.has(t.symbol);
            return (
              <div key={t.symbol} style={{ borderBottom: "1px solid var(--border)" }}>
                <div
                  className="flex items-center gap-3 py-3 px-3 cursor-pointer transition-colors"
                  style={{
                    background: isActive ? "var(--accent-subtle)" : "transparent",
                    borderLeft: isActive ? "3px solid var(--accent)" : "3px solid transparent",
                  }}
                  onClick={() => { setSelected(t); setLlmInsight(null); }}
                >
                  {/* Rank */}
                  <div className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0"
                    style={{ background: t.rank <= 3 ? "var(--accent)" : "var(--border)", color: t.rank <= 3 ? "#fff" : "var(--text-muted)" }}>
                    {t.rank}
                  </div>

                  {/* Gene info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Dna size={12} style={{ color: "#8b5cf6" }} />
                      <span className="text-sm font-semibold">{t.symbol}</span>
                      <span className="text-[9px] font-medium px-1.5 py-0.5 rounded"
                        style={{ background: "rgba(99,102,241,0.08)", color: "#6366f1" }}>
                        {t.evidence_count} signals
                      </span>
                      {t.indian_population_boost_applied && (
                        <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded" style={{ background: "#ff6b0015", color: "#ea580c" }}>
                          🇮🇳 India+
                        </span>
                      )}
                    </div>
                    {/* Mini signal bars */}
                    <div className="flex gap-0.5 mt-1.5 h-1.5">
                      {Object.entries(SIGNAL_META).map(([key, meta]) => {
                        const v = (t.signals as Record<string, number>)[key] ?? 0;
                        return (
                          <div key={key} className="flex-1 rounded-sm overflow-hidden" style={{ background: "var(--border)" }} title={`${meta.label}: ${(v * 100).toFixed(0)}%`}>
                            <div className="h-full rounded-sm" style={{ width: `${v * 100}%`, background: meta.color }} />
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Composite score + UCB */}
                  <div className="w-24 shrink-0 text-right">
                    <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>Score</div>
                    <div className="text-base font-bold" style={{ color: scoreColor(t.composite_score), fontFamily: "var(--font-mono)" }}>
                      {t.composite_score.toFixed(3)}
                    </div>
                    {(t.ucb_score ?? 0) > 0 && (
                      <div className="text-[9px] font-mono" style={{ color: "#a78bfa" }}>
                        UCB {(t.ucb_score ?? 0).toFixed(3)}
                      </div>
                    )}
                    {t.contradiction_flag && (
                      <div className="text-[9px] text-amber-400 font-semibold">⚠ conflict</div>
                    )}
                  </div>

                  {/* Expand toggle */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setExpandedRows((prev) => {
                        const next = new Set(prev);
                        if (next.has(t.symbol)) next.delete(t.symbol);
                        else next.add(t.symbol);
                        return next;
                      });
                    }}
                    className="ml-1 p-1 rounded hover:bg-[var(--bg-inset)] shrink-0"
                    title={isExpanded ? "Collapse breakdown" : "Expand signal breakdown"}
                  >
                    <ChevronRight
                      size={13}
                      style={{
                        color: "var(--text-muted)",
                        transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                        transition: "transform 0.2s",
                      }}
                    />
                  </button>
                </div>

                {/* §E5: Expanded score breakdown */}
                {isExpanded && (
                  <div className="px-4 pb-4 pt-2" style={{ background: "var(--bg-surface)" }}>
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                      7-Signal Score Breakdown
                    </div>
                    {/* Bar chart */}
                    <div className="space-y-1.5">
                      {Object.entries(SIGNAL_META).map(([key, meta]) => {
                        const v = (t.signals as Record<string, number>)[key] ?? 0;
                        const isIndiaSignal = key === "gwas" && t.indian_population_boost_applied;
                        const gatWeight = t.gat_attention_weights?.[key];
                        return (
                          <div key={key} className="flex items-center gap-2 text-xs">
                            <span className="w-20 text-[10px] shrink-0" style={{ color: "var(--text-muted)" }}>{meta.label}</span>
                            <div className="flex-1 h-4 bg-[var(--bg-inset)] rounded-sm overflow-hidden relative" title={`Weight: ${(meta.weight * 100).toFixed(0)}%`}>
                              <div
                                className="h-full rounded-sm transition-all duration-500"
                                style={{
                                  width: `${v * 100}%`,
                                  background: isIndiaSignal
                                    ? "linear-gradient(90deg, #ea580c, #f97316)"
                                    : meta.color,
                                  opacity: 0.85,
                                }}
                              />
                              {isIndiaSignal && (
                                <span className="absolute right-1 top-0 text-[9px] text-orange-700 font-bold leading-4">🇮🇳</span>
                              )}
                            </div>
                            <span className="w-10 text-right font-mono text-[10px]" style={{ color: meta.color }}>
                              {(v * 100).toFixed(0)}%
                            </span>
                            {gatWeight !== undefined && (
                              <span className="text-[9px] text-purple-500 font-mono w-12 text-right" title="GAT attention weight">
                                α={gatWeight.toFixed(2)}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {/* Indian context boost note */}
                    {t.indian_population_boost_applied && (
                      <div className="mt-3 p-2 rounded text-[10px]" style={{ background: "#ff6b0010", border: "1px solid #ea580c30", color: "#ea580c" }}>
                        🇮🇳 Indian population weight (+{t.indian_context_score !== undefined ? (t.indian_context_score * 100).toFixed(1) + "%" : "15%"}) applied to GWAS signal (§D1 India population weighting)
                      </div>
                    )}

                    {/* GAT attention heatmap */}
                    {t.gat_attention_weights ? (
                      <div className="mt-3">
                        <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1.5">GAT Attention Weights</div>
                        <div className="flex gap-1 h-6">
                          {Object.entries(SIGNAL_META).map(([key, meta]) => {
                            const w = t.gat_attention_weights![key] ?? 0;
                            return (
                              <div
                                key={key}
                                className="flex-1 rounded-sm flex items-end justify-center text-[7px] font-bold overflow-hidden"
                                style={{ background: `${meta.color}${Math.round(w * 255).toString(16).padStart(2, "0")}`, color: w > 0.5 ? "#fff" : meta.color }}
                                title={`${meta.label} attention: ${(w * 100).toFixed(0)}%`}
                              >
                                {(w * 100).toFixed(0)}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : (
                      <div className="mt-3 text-[9px] text-[var(--text-muted)] italic">
                        GAT attention weights not available (model not loaded)
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Right — inspector */}
        {selected && (
          <div className="w-[400px] shrink-0 overflow-y-auto p-5" style={{ background: "var(--bg-surface)" }}>
            <div className="flex items-center gap-2 mb-1">
              <Target size={18} style={{ color: "var(--accent)" }} />
              <h2 className="text-lg font-bold" style={{ fontFamily: "var(--font-display)" }}>{selected.symbol}</h2>
              <span className="text-[10px] px-1.5 py-0.5 rounded font-semibold"
                style={{ background: "var(--accent)", color: "#fff" }}>
                #{selected.rank}
              </span>
            </div>
            <p className="text-[10px] mb-4" style={{ color: "var(--text-muted)" }}>
              Composite score computed from 7 weighted signals (§83).
              {selected.sources.length > 0 && <> Active signals: {selected.sources.join(", ")}.</>}
            </p>

            {/* Overall score — hero display */}
            <div className="mb-5 p-4 rounded-xl text-center relative overflow-hidden"
              style={{ background: `linear-gradient(135deg, ${scoreColor(selected.composite_score)}15, ${scoreColor(selected.composite_score)}05)`, border: `2px solid ${scoreColor(selected.composite_score)}30` }}>
              <div className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>Overall Priority Score</div>
              <div className="text-4xl font-black" style={{ color: scoreColor(selected.composite_score), fontFamily: "var(--font-mono)" }}>
                {selected.composite_score.toFixed(3)}
              </div>
              <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>
                {selected.composite_score > 0.7 ? "🟢 High priority target" : selected.composite_score > 0.4 ? "🟡 Moderate priority" : "🔴 Low priority — needs more evidence"}
              </div>
            </div>

            <div className="flex items-center gap-3 mb-5">
              <div className="flex-1 text-center p-3 rounded-lg" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                <div className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: "#a78bfa" }}>UCB Score</div>
                <div className="text-xl font-bold" style={{ color: "#a78bfa", fontFamily: "var(--font-mono)" }}>
                  {(selected.ucb_score ?? 0).toFixed(3)}
                </div>
                {(selected.uncertainty ?? 0) > 0 && (
                  <div className="text-[9px]" style={{ color: "var(--text-muted)" }}>
                    ±{(selected.uncertainty ?? 0).toFixed(3)} explore
                  </div>
                )}
              </div>
              <div className="flex-1 text-center p-3 rounded-lg" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                <div className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>Evidence</div>
                <div className="text-xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>{selected.evidence_count}</div>
              </div>
              <div className="flex-1 text-center p-3 rounded-lg" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                <div className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>Rank</div>
                <div className="text-xl font-bold" style={{ color: "var(--accent)", fontFamily: "var(--font-mono)" }}>#{selected.rank}</div>
              </div>
            </div>

            {/* Radar Chart — signal visualization */}
            <div className="section-label mb-2">Signal Radar</div>
            <div className="mb-5 rounded-xl p-2" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
              <div role="img" aria-label={`Signal radar chart for ${selected?.gene || selected?.symbol || 'target'}`}>
              <ResponsiveContainer width="100%" height={220}>
                <RadarChart data={Object.entries(SIGNAL_META).map(([key, meta]) => ({
                  signal: meta.label,
                  value: ((selected.signals as Record<string, number>)[key] ?? 0) * 100,
                  fullMark: 100,
                }))}>
                  <PolarGrid stroke="var(--border)" />
                  <PolarAngleAxis dataKey="signal" tick={{ fontSize: 9, fill: "var(--text-muted)" }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 8 }} />
                  <Radar name={selected.symbol} dataKey="value" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.25} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
              </div>
            </div>

            {/* Contradiction warning */}
            {selected.contradiction_flag && (
              <div className="mb-4 p-3 rounded-lg" style={{ background: "rgba(251, 191, 36, 0.08)", border: "1px solid rgba(251, 191, 36, 0.2)" }}>
                <div className="flex items-center gap-2 text-xs font-semibold" style={{ color: "#fbbf24" }}>
                  <AlertTriangle size={13} />
                  Contradictory evidence detected for this target
                </div>
                <p className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>
                  Some sources provide conflicting signals. Review the evidence in detail before advancing.
                </p>
              </div>
            )}

            {/* 7-signal breakdown bars */}
            <div className="section-label mb-2 flex items-center gap-1">
              Signal Breakdown
              <Info size={10} style={{ color: "var(--text-muted)" }} />
            </div>
            <div className="space-y-2 mb-5">
              {Object.entries(SIGNAL_META).map(([key, meta]) => {
                const v = (selected.signals as Record<string, number>)[key] ?? 0;
                return (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-0.5">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ background: meta.color }} />
                        <span className="text-[10px] font-semibold">{meta.label}</span>
                        <span className="text-[8px]" style={{ color: "var(--text-muted)" }}>(w={meta.weight})</span>
                      </div>
                      <span className="text-[10px] font-bold" style={{ color: meta.color, fontFamily: "var(--font-mono)" }}>
                        {(v * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="w-full h-2 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                      <div className="h-full rounded-full transition-all" style={{ width: `${v * 100}%`, background: meta.color }} />
                    </div>
                    <div className="text-[8px] mt-0.5" style={{ color: "var(--text-muted)" }}>{meta.description}</div>
                  </div>
                );
              })}
            </div>

            {/* Weighted contribution */}
            <div className="section-label mb-2">Weighted Contribution</div>
            <div className="flex gap-0.5 h-6 rounded-lg overflow-hidden mb-1">
              {Object.entries(SIGNAL_META).map(([key, meta]) => {
                const v = (selected.signals as Record<string, number>)[key] ?? 0;
                const contribution = v * meta.weight;
                const pct = selected.composite_score > 0 ? (contribution / selected.composite_score) * 100 : 0;
                return pct > 0 ? (
                  <div key={key} style={{ width: `${pct}%`, background: meta.color, minWidth: pct > 3 ? 0 : 4 }}
                    title={`${meta.label}: ${(contribution * 100).toFixed(1)}% contribution`} />
                ) : null;
              })}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 mb-5">
              {Object.entries(SIGNAL_META).map(([key, meta]) => {
                const v = (selected.signals as Record<string, number>)[key] ?? 0;
                if (v === 0) return null;
                return (
                  <span key={key} className="flex items-center gap-1 text-[9px]">
                    <span className="w-2 h-2 rounded-sm" style={{ background: meta.color }} />
                    {meta.label}
                  </span>
                );
              })}
            </div>

            {/* Explanation */}
            {selected.explanation && (
              <>
                <div className="section-label mb-2">Explanation</div>
                <div className="text-[11px] p-3 mb-4 rounded"
                  style={{ color: "var(--text-secondary)", background: "var(--bg-elevated)", border: "1px solid var(--border)", lineHeight: 1.6 }}>
                  {selected.explanation}
                </div>
              </>
            )}

            {/* LLM-powered Target Insight */}
            <div className="section-label mb-2 flex items-center gap-1.5">
              <Brain size={11} className="text-purple-500" /> AI Target Insight
            </div>
            <div className="mb-4 p-3 rounded-lg" style={{ background: "linear-gradient(135deg, rgba(139,92,246,0.05), rgba(168,85,247,0.02))", border: "1px solid rgba(139,92,246,0.15)" }}>
              {llmInsight && !llmLoading && (
                <div className="text-[10px] leading-relaxed whitespace-pre-line" style={{ color: "var(--text-secondary)" }}>
                  <Sparkles size={10} className="inline text-amber-400 mr-1" />{llmInsight}
                </div>
              )}
              {llmLoading && (
                <div className="flex items-center gap-2 text-[10px] py-2" style={{ color: "var(--text-muted)" }}>
                  <Loader2 size={12} className="animate-spin text-purple-400" /> Analyzing target with AI...
                </div>
              )}
              {!llmInsight && !llmLoading && (
                <button
                  onClick={() => fetchTargetLLM(selected, disease)}
                  className="text-[10px] px-3 py-1.5 rounded-lg flex items-center gap-1.5 font-medium"
                  style={{ border: "1px solid rgba(139,92,246,0.3)", color: "#8b5cf6", background: "transparent", cursor: "pointer" }}>
                  <Brain size={10} /> Generate AI Analysis
                </button>
              )}
            </div>

            {/* Actions */}
            <div className="section-label mb-2">Actions</div>
            <div className="flex flex-wrap gap-2">
              <button className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold"
                style={{ background: "var(--accent)", color: "#fff", border: "none", cursor: "pointer" }}
                onClick={() => navigate(`/graph?q=${encodeURIComponent(selected.symbol)}`)}>
                <Network size={10} /> View in KG
              </button>
              <button className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold"
                style={{ background: "#10b981", color: "#fff", border: "none", cursor: "pointer" }}
                onClick={() => navigate(`/structure?q=${encodeURIComponent(selected.symbol)}`)}>
                <FlaskConical size={10} /> 3D Structure
              </button>
              <button className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold"
                style={{ border: "1px solid var(--border)", color: "var(--accent)", background: "transparent", cursor: "pointer" }}
                onClick={() => navigate("/dossiers")}>
                <FileText size={10} /> → Dossier
              </button>
              <button className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold"
                style={{ border: "1px solid var(--border)", color: "var(--text-muted)", background: "transparent", cursor: "pointer" }}
                onClick={() => navigate(`/design?target=${encodeURIComponent(selected.symbol)}`)}>
                <ExternalLink size={10} /> Design Studio
              </button>
            </div>
          </div>
        )}
      </div>
      </StateWrapper>
    </div>
  );
}
