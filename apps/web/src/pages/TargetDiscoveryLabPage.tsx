/** TargetDiscoveryLabPage — Target Discovery Lab (§20, §131 /labs/target-discovery). */

import { useState, useEffect } from "react";
import { Target, Play, Loader2, CheckCircle, AlertTriangle } from "lucide-react";
import { labsPocketRunAPI } from "@/lib/api";
import { useRunProgress } from "@/lib/hooks";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

export default function TargetDiscoveryLabPage() {
  const [targetId, setTargetId] = useState("");
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
    if (!targetId.trim()) return;
    setViewState("loading");
    setCurrentRunId(null);
    setDegradedSources([]);
    try {
      const res = await labsPocketRunAPI(targetId);
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
      setErrorMsg(err instanceof Error ? err.message : "Lab run failed");
      setViewState("error");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <header className="flex items-center gap-3">
        <Target size={28} style={{ color: "var(--accent)" }} />
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Target Discovery Lab</h1>
      </header>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        Deep pocket detection, binding-site analysis, and druggability assessment.
      </p>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded px-3 py-2 text-sm"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          placeholder="Enter target ID (e.g., P04637)…"
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runLab()}
        />
        <button
          onClick={runLab}
          disabled={viewState === "loading"}
          aria-disabled={viewState === "loading"}
          title={viewState === "loading" ? "unavailable: analysis in progress" : "Run pocket detection analysis"}
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
        moduleName="Target Discovery"
        loadingMessage="Running pocket detection and druggability assessment…"
        emptyTitle="No results"
        emptyDescription="Enter a target ID and run an analysis."
        errorInfo={{ code: "LAB_ERROR", message: errorMsg, recoverable: true }}
        degradedInfo={degradedSources.length > 0 ? { reason: "Some analysis modules were unavailable. Results may be partial.", affectedSources: degradedSources } : undefined}
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
