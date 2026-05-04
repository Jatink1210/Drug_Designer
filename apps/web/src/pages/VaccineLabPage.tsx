/** VaccineLabPage — Vaccine Design Lab (§20, §131 /labs/vaccine). */

import { useState, useEffect } from "react";
import { Shield, Play, Loader2 } from "lucide-react";
import { labsVaccineRunAPI } from "@/lib/api";
import { useRunProgress } from "@/lib/hooks";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

export default function VaccineLabPage() {
  const [antigenId, setAntigenId] = useState("");
  const [viewState, setViewState] = useState<ViewState>("initial");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [degradedSources, setDegradedSources] = useState<string[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const wsProgress = useRunProgress(currentRunId);

  useEffect(() => {
    if (wsProgress?.isComplete) {
      setCurrentRunId(null);
      setViewState("success");
    }
  }, [wsProgress?.isComplete]);

  const runLab = async () => {
    if (!antigenId.trim()) return;
    setViewState("loading");
    setCurrentRunId(null);
    setDegradedSources([]);
    try {
      const res = await labsVaccineRunAPI(antigenId);
      if ((res as any).run_id) setCurrentRunId((res as any).run_id);
      setResult(res);
      const degraded = (res as any).degraded_sources || (res as any).warnings || [];
      if (Array.isArray(degraded) && degraded.length > 0) {
        setDegradedSources(degraded);
        setViewState("degraded");
      } else {
        setViewState("success");
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Vaccine analysis failed");
      setViewState("error");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <header className="flex items-center gap-3">
        <Shield size={28} style={{ color: "var(--info)" }} />
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Vaccine Design Lab</h1>
      </header>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        Epitope prediction, immunogenicity scoring, and vaccine candidate selection.
      </p>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded px-3 py-2 text-sm"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          placeholder="Enter antigen / pathogen ID…"
          value={antigenId}
          onChange={(e) => setAntigenId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runLab()}
        />
        <button
          onClick={runLab}
          disabled={viewState === "loading"}
          aria-disabled={viewState === "loading"}
          title={viewState === "loading" ? "unavailable: analysis in progress" : "Run vaccine analysis"}
          className="flex items-center gap-1 px-4 py-2 text-sm text-white rounded disabled:opacity-50 transition-colors"
          style={{ background: "var(--accent)" }}
        >
          {viewState === "loading" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          Run Analysis
        </button>
      </div>

      {wsProgress && !wsProgress.isComplete && (
        <div className="flex items-center gap-3 px-4 py-2 rounded-lg text-xs" style={{ background: "var(--bg-surface)" }}>
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

      <StateWrapper
        state={viewState}
        moduleName="Vaccine Design"
        loadingMessage="Analyzing epitopes and immunogenicity…"
        emptyTitle="No candidates"
        emptyDescription="Enter an antigen ID and run the analysis."
        errorInfo={{ code: "VACCINE_ERROR", message: errorMsg, recoverable: true }}
        degradedInfo={degradedSources.length > 0 ? { reason: "Some analysis sources were unavailable. Results may be partial.", affectedSources: degradedSources } : undefined}
        onRetry={runLab}
      >
        {result && (
          <pre className="rounded-lg p-4 text-xs overflow-auto max-h-96 font-mono" style={{ background: "var(--bg-surface)", color: "var(--text-primary)", border: "1px solid var(--border)" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </StateWrapper>
    </div>
    </div>
  );
}
