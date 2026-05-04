import { useState, useCallback } from "react";
import { Activity, FlaskConical, Plus, Trash2, Play, AlertTriangle, CheckCircle, XCircle, Info } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";
import { moleculeADMETAPI, type ADMETResult, type ADMETConformalInterval } from "@/lib/api";

const PANEL_META: { key: keyof Omit<ADMETResult, "smiles" | "confidence_interval">; label: string; color: string; icon: string }[] = [
  { key: "absorption", label: "Absorption", color: "#60a5fa", icon: "A" },
  { key: "distribution", label: "Distribution", color: "#a78bfa", icon: "D" },
  { key: "metabolism", label: "Metabolism", color: "#34d399", icon: "M" },
  { key: "excretion", label: "Excretion", color: "#fbbf24", icon: "E" },
  { key: "toxicity", label: "Toxicity", color: "#f87171", icon: "T" },
  { key: "synthetic_accessibility", label: "Synthetic Accessibility", color: "#818cf8", icon: "SA" },
];

function scoreToVerdict(val: unknown): { label: string; color: string; icon: typeof CheckCircle } {
  if (typeof val === "number") {
    if (val >= 0.7) return { label: "Favorable", color: "#34d399", icon: CheckCircle };
    if (val >= 0.4) return { label: "Moderate", color: "#fbbf24", icon: AlertTriangle };
    return { label: "Unfavorable", color: "#f87171", icon: XCircle };
  }
  if (typeof val === "string") {
    const low = val.toLowerCase();
    if (low === "high" || low === "good" || low === "yes") return { label: val, color: "#34d399", icon: CheckCircle };
    if (low === "moderate" || low === "medium") return { label: val, color: "#fbbf24", icon: AlertTriangle };
    return { label: val, color: "#f87171", icon: XCircle };
  }
  return { label: "—", color: "var(--text-muted)", icon: AlertTriangle };
}

/** I-3: Confidence interval band component (90% coverage via conformal prediction). */
function CIBand({ ci, color }: { ci?: ADMETConformalInterval; color: string }) {
  if (!ci || !ci.calibrated || !ci.interval) return null;
  const [lo, hi] = ci.interval;
  const width = hi - lo;
  const ciColor = width < 0.2 ? "#34d399" : width < 0.4 ? "#fbbf24" : "#f87171";
  return (
    <div
      className="mt-2 pt-2 border-t"
      style={{ borderColor: "var(--border)" }}
      title={`90% conformal prediction interval: [${lo.toFixed(3)}, ${hi.toFixed(3)}]`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9px] flex items-center gap-0.5" style={{ color: "var(--text-muted)" }}>
          <Info size={9} /> 90% CI
        </span>
        <span className="text-[9px] font-mono" style={{ color: ciColor }}>
          [{lo.toFixed(3)}, {hi.toFixed(3)}]
        </span>
      </div>
      <div className="relative h-1.5 rounded-full overflow-hidden" style={{ background: "var(--bg-surface)" }}>
        <div
          className="absolute h-full rounded-full"
          style={{
            left: `${Math.max(0, Math.min(lo * 100, 100))}%`,
            width: `${Math.max(2, Math.min(width * 100, 100))}%`,
            background: ciColor,
            opacity: 0.75,
          }}
        />
      </div>
    </div>
  );
}

export default function AdmetPanels() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const initialSmiles = params.get("smiles") ?? "";

  const [smilesInputs, setSmilesInputs] = useState<string[]>(initialSmiles ? [initialSmiles] : [""]);
  const [results, setResults] = useState<ADMETResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [degradedSources, setDegradedSources] = useState<string[]>([]);

  const onAddRow = useCallback(() => setSmilesInputs((prev) => [...prev, ""]), []);
  const onRemoveRow = useCallback(
    (idx: number) => setSmilesInputs((prev) => prev.filter((_, i) => i !== idx)),
    []
  );
  const onChangeRow = useCallback(
    (idx: number, val: string) =>
      setSmilesInputs((prev) => prev.map((s, i) => (i === idx ? val : s))),
    []
  );

  const onRun = useCallback(async () => {
    const valid = smilesInputs.filter((s) => s.trim());
    if (valid.length === 0) return;
    setLoading(true);
    setError("");
    setDegradedSources([]);
    try {
      const res = await moleculeADMETAPI(valid);
      const arr = Array.isArray(res) ? res : [res];
      setResults(arr);
      setSelectedIdx(0);
      // Detect partial/degraded results: panels with no entries
      if (arr.length > 0) {
        const panelKeys = PANEL_META.map((p) => p.key);
        const missing = panelKeys.filter((k) => {
          const v = arr[0][k] as Record<string, unknown> | undefined;
          return !v || Object.keys(v).length === 0;
        });
        if (missing.length > 0) {
          setDegradedSources(missing as string[]);
        }
      }
    } catch (err: any) {
      setError(err?.message ?? "ADMET prediction failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [smilesInputs]);

  const viewState: ViewState = loading
    ? "loading"
    : error
    ? "error"
    : results.length > 0 && degradedSources.length > 0
    ? "degraded"
    : results.length > 0
    ? "success"
    : "empty";
  const current = results[selectedIdx] ?? null;

  return (
    <StateWrapper
      state={viewState}
      moduleName="ADMET Panels"
      emptyTitle="No ADMET results"
      emptyDescription="Enter one or more SMILES strings and run the prediction."
      degradedInfo={
        degradedSources.length > 0
          ? { reason: "Some ADMET panels returned no data.", affectedSources: degradedSources }
          : undefined
      }
      onRetry={onRun}
    >
      <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
        <div className="max-w-[1200px] mx-auto px-6 py-5">
          {/* Header */}
          <div className="mb-6">
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">
              Property / ADMET Panels
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Deep inspection of physicochemical properties and ADMETox profiles for candidate molecules.
            </p>
          </div>

          {/* SMILES Input */}
          <div className="card border border-border rounded-xl p-4 mb-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                Molecules
              </h2>
              <div className="flex gap-2">
                <button onClick={onAddRow} className="glass-button flex items-center gap-1 px-3 py-1.5 text-xs">
                  <Plus size={12} /> Add
                </button>
                <button
                  onClick={onRun}
                  disabled={loading || smilesInputs.every((s) => !s.trim())}
                  className="glass-button flex items-center gap-1.5 px-4 py-1.5 text-xs bg-[var(--accent)]/10 text-[var(--accent)] disabled:opacity-50"
                >
                  {loading ? (
                    <Activity size={12} className="animate-spin" />
                  ) : (
                    <Play size={12} />
                  )}
                  Run ADMET
                </button>
              </div>
            </div>
            <div className="space-y-2">
              {smilesInputs.map((s, i) => (
                <div key={i} className="flex gap-2 items-center">
                  <span className="text-[10px] text-[var(--text-muted)] font-mono w-6 text-right">{i + 1}</span>
                  <input
                    className="flex-1 bg-[var(--bg-surface)] border border-border rounded-lg px-3 py-2 text-sm font-mono text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                    placeholder="Enter SMILES (e.g. CC(=O)OC1=CC=CC=C1C(=O)O)"
                    value={s}
                    onChange={(e) => onChangeRow(i, e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && onRun()}
                  />
                  {smilesInputs.length > 1 && (
                    <button onClick={() => onRemoveRow(i)} className="text-[var(--text-muted)] hover:text-red-400 transition-colors">
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
            {error && (
              <div className="mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
                {error}
              </div>
            )}
          </div>

          {/* Results */}
          {results.length > 0 && (
            <>
              {/* Compound selector (if multiple) */}
              {results.length > 1 && (
                <div className="flex gap-2 mb-4 flex-wrap">
                  {results.map((r, i) => (
                    <button
                      key={i}
                      onClick={() => setSelectedIdx(i)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-mono border transition-colors ${
                        selectedIdx === i
                          ? "border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)]"
                          : "border-border text-[var(--text-muted)] hover:border-[var(--accent)]/50"
                      }`}
                    >
                      {r.smiles?.length > 20 ? r.smiles.slice(0, 20) + "…" : r.smiles || `Compound ${i + 1}`}
                    </button>
                  ))}
                </div>
              )}

              {/* 6 ADMET panels */}
              {current && (
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                  {PANEL_META.map((panel) => {
                    const data = current[panel.key] as Record<string, unknown> | undefined;
                    const entries = data ? Object.entries(data) : [];
                    return (
                      <div
                        key={panel.key}
                        className="card p-5 border border-border flex flex-col rounded-xl transition-all hover:-translate-y-0.5"
                      >
                        <div className="flex justify-between items-start mb-4">
                          <div className="flex items-center gap-2">
                            <div
                              className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold"
                              style={{ background: `${panel.color}20`, color: panel.color }}
                            >
                              {panel.icon}
                            </div>
                            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{panel.label}</h3>
                          </div>
                          <Activity size={14} style={{ color: panel.color }} />
                        </div>

                        {entries.length > 0 ? (
                          <div className="space-y-2 flex-1">
                            {entries.map(([key, val]) => {
                              const v = scoreToVerdict(val);
                              const Icon = v.icon;
                              return (
                                <div key={key} className="flex items-center justify-between text-xs">
                                  <span className="text-[var(--text-muted)] truncate mr-2">
                                    {key.replace(/_/g, " ")}
                                  </span>
                                  <span className="flex items-center gap-1 shrink-0" style={{ color: v.color }}>
                                    <Icon size={11} />
                                    {typeof val === "number" ? val.toFixed(3) : v.label}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="flex-1 flex items-center justify-center">
                            <span className="text-[10px] text-[var(--text-muted)] italic">No data returned</span>
                          </div>
                        )}

                        {/* Summary bar */}
                        <div className="mt-3">
                          <div className="h-1 w-full bg-surface rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{
                                width: entries.length > 0 ? "100%" : "0%",
                                background: panel.color,
                                opacity: 0.6,
                              }}
                            />
                          </div>
                          <span className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] font-mono mt-1 block">
                            {entries.length} properties
                          </span>
                        </div>

                        {/* I-3: per-panel conformal interval band */}
                        <CIBand
                          ci={current?.conformal_intervals?.[panel.key] as ADMETConformalInterval | undefined}
                          color={panel.color}
                        />
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Action bar */}
              {current?.confidence_interval && (() => {
                const ci = current.confidence_interval;
                const width = ci.upper - ci.lower;
                const ciColor = width < 0.2 ? "#34d399" : width < 0.4 ? "#fbbf24" : "#f87171";
                const ciLabel = width < 0.2 ? "Narrow (high confidence)" : width < 0.4 ? "Moderate" : "Wide (low confidence)";
                return (
                  <div
                    className="mt-4 p-4 border rounded-xl flex flex-col gap-2"
                    style={{ borderColor: `${ciColor}40`, background: `${ciColor}08` }}
                    title="90% prediction interval via conformal prediction"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold" style={{ color: ciColor }}>
                        90% Conformal Prediction Interval
                      </span>
                      <span className="text-[10px] font-mono" style={{ color: ciColor }}>
                        [{ci.lower.toFixed(3)}, {ci.upper.toFixed(3)}]
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-2 bg-[var(--bg-surface)] rounded-full overflow-hidden relative">
                        <div
                          className="absolute h-full rounded-full transition-all duration-500"
                          style={{
                            left: `${ci.lower * 100}%`,
                            width: `${(ci.upper - ci.lower) * 100}%`,
                            background: ciColor,
                            opacity: 0.7,
                          }}
                        />
                      </div>
                      <span className="text-[10px] text-[var(--text-muted)] shrink-0">±{ci.std.toFixed(3)} σ</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-[var(--text-muted)]">Interval width: {ciLabel}</span>
                      <span className="text-[10px] text-[var(--text-muted)] italic">
                        Calibrate with held-out dataset for tighter intervals
                      </span>
                    </div>
                  </div>
                );
              })()}

              <div className="mt-5 flex gap-3 justify-end">
                <button
                  onClick={() => navigate(`/design?smiles=${encodeURIComponent(current?.smiles ?? "")}`)}
                  className="glass-button flex items-center gap-1.5 px-4 py-2 text-xs"
                >
                  <FlaskConical size={12} /> Open in Design Studio
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </StateWrapper>
  );
}
