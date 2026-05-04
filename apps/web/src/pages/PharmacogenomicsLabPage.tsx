/** PharmacogenomicsLabPage — Indian Population Pharmacogenomics Lab (§7, §131 /labs/pharmacogenomics). */

import { useState, useEffect } from "react";
import { Dna, Play, Loader2 } from "lucide-react";
import { labsPharmacogenomicsRunAPI } from "@/lib/api";
import { useRunProgress } from "@/lib/hooks";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

export default function PharmacogenomicsLabPage() {
  const [geneQuery, setGeneQuery] = useState("");
  const [drugId, setDrugId] = useState("");
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
    if (!geneQuery.trim()) return;
    setViewState("loading");
    setCurrentRunId(null);
    try {
      const res = await labsPharmacogenomicsRunAPI(geneQuery, drugId || "metformin");
      if ((res as any).run_id) setCurrentRunId((res as any).run_id);
      setResult(res);
      setViewState("success");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Pharmacogenomic analysis failed");
      setViewState("error");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <header className="flex items-center gap-3">
        <Dna size={28} style={{ color: "var(--error)" }} />
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Pharmacogenomics Lab</h1>
      </header>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        Indian population-specific allele frequencies, pharmacogenomic variant analysis, and drug-response prediction.
      </p>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded px-3 py-2 text-sm"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          placeholder="Gene symbol (e.g. CYP2D6)…"
          value={geneQuery}
          onChange={(e) => setGeneQuery(e.target.value)}
        />
        <input
          className="flex-1 rounded px-3 py-2 text-sm"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          placeholder="Drug ID (e.g. metformin)…"
          value={drugId}
          onChange={(e) => setDrugId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runLab()}
        />
        <button
          onClick={runLab}
          disabled={viewState === "loading"}
          aria-disabled={viewState === "loading"}
          title={viewState === "loading" ? "unavailable: analysis in progress" : "Analyze pharmacogenomics variants"}
          className="flex items-center gap-1 px-4 py-2 text-sm text-white rounded disabled:opacity-50 transition-colors"
          style={{ background: "var(--accent)" }}
        >
          {viewState === "loading" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          Analyze Variants
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
        moduleName="Pharmacogenomics"
        loadingMessage="Querying Indian population databases and computing allele frequencies…"
        emptyTitle="No variants found"
        emptyDescription="Enter a gene or variant ID to analyze."
        onRetry={runLab}
      >
        {result && (
          <div className="rounded-lg p-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Pharmacogenomic Results</h2>
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
