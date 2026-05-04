/** PocketLabPage — Binding Pocket Prediction Lab (§20.5, §131 /labs/pocket). */

import { useState, useEffect } from "react";
import { Crosshair, Play, Loader2 } from "lucide-react";
import { labsPocketRunAPI } from "@/lib/api";
import { useRunProgress } from "@/lib/hooks";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

export default function PocketLabPage() {
  const [targetId, setTargetId] = useState("");
  const [viewState, setViewState] = useState<ViewState>("initial");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
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
    try {
      const res = await labsPocketRunAPI(targetId);
      if ((res as any).run_id) setCurrentRunId((res as any).run_id);
      setResult(res);
      setViewState("success");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Pocket prediction failed");
      setViewState("error");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <header className="flex items-center gap-3">
        <Crosshair size={28} style={{ color: "var(--accent)" }} />
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Binding Pocket Prediction Lab</h1>
      </header>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        Predict druggable binding pockets on protein targets using graph transformer models.
      </p>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded px-3 py-2 text-sm"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          placeholder="Enter target UniProt ID (e.g. P37231)…"
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runLab()}
        />
        <button
          onClick={runLab}
          disabled={viewState === "loading"}
          aria-disabled={viewState === "loading"}
          title={viewState === "loading" ? "unavailable: analysis in progress" : "Predict binding pockets"}
          className="flex items-center gap-1 px-4 py-2 text-sm text-white rounded disabled:opacity-50 transition-colors"
          style={{ background: "var(--accent)" }}
        >
          {viewState === "loading" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          Predict Pockets
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
        moduleName="Pocket Prediction"
        loadingMessage="Analyzing protein structure for binding sites…"
        emptyTitle="No pockets found"
        emptyDescription="Enter a target ID and run the prediction."
        onRetry={runLab}
      >
        {result && (
          <div className="rounded-lg p-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Predicted Pockets</h2>
            <pre className="text-xs overflow-x-auto whitespace-pre-wrap font-mono" style={{ color: "var(--text-secondary)" }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </StateWrapper>
    </div>
    </div>
  );
}
