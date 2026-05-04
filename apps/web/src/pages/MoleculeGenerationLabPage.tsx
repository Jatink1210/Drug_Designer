/** MoleculeGenerationLabPage — Molecule Design Lab (§19, §131 /labs/molecule-generation).
 *  Includes ESM-3 Large De Novo Protein Design panel (§24.2, Forge API).
 */

import { useState, useEffect, lazy, Suspense } from "react";
import { Atom, Play, Loader2 } from "lucide-react";
import { labsMoleculeGenerationRunAPI } from "@/lib/api";
import { useRunProgress } from "@/lib/hooks";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

// §O-6: ESM-3 panel loaded as a separate async chunk — only fetched when the
// Molecule Lab page is first visited, reducing initial bundle size.
const ESM3DesignPanel = lazy(
  () => import("@/components/esm3/ESM3DesignPanel"),
);

export default function MoleculeGenerationLabPage() {
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
      const res = await labsMoleculeGenerationRunAPI(targetId);
      if ((res as any).run_id) setCurrentRunId((res as any).run_id);
      setResult(res);
      setViewState("success");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Molecule generation failed");
      setViewState("error");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <header className="flex items-center gap-3">
        <Atom size={28} style={{ color: "var(--success)" }} />
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Molecule Generation Lab</h1>
      </header>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        Generate novel drug candidates using graph diffusion models and RL-based optimization.
      </p>

      {/* ESM-3 De Novo Protein Design panel — lazy-loaded (§O-6) */}
      <Suspense fallback={<div className="text-xs" style={{ color: "var(--text-muted)" }}>Loading ESM-3 panel…</div>}>
        <ESM3DesignPanel />
      </Suspense>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded px-3 py-2 text-sm"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          placeholder="Enter target protein ID or SMILES seed…"
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runLab()}
        />
        <button
          onClick={runLab}
          disabled={viewState === "loading"}
          className="flex items-center gap-1 px-4 py-2 text-sm text-white rounded disabled:opacity-50 transition-colors"
          style={{ background: "var(--accent)" }}
        >
          {viewState === "loading" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          Generate Molecules
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
        moduleName="Molecule Generation"
        loadingMessage="Running diffusion model and RL optimization…"
        emptyTitle="No candidates"
        emptyDescription="Enter a target ID and run molecule generation."
        onRetry={runLab}
      >
        {result && (
          <div className="rounded-lg p-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Generated Candidates</h2>
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
