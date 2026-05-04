import { useState } from "react";
import {
  SearchCheck,
  FlaskConical,
  Beaker,
  Loader2,
  ArrowRight,
  Atom,
} from "lucide-react";
import { ensureApiBase } from "@/lib/api";
import { useMoleculeLibrary } from "@/lib/hooks";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";

type Candidate = {
  smiles: string;
  name: string;
  score: number;
  properties: Record<string, any>;
};

export default function MoleculeCandidateReview() {
  const { data, state, error, refetch } = useMoleculeLibrary();
  const candidates: Candidate[] = Array.isArray(data) ? data : (data as any)?.molecules ?? [];
  const loading = state === "loading";
  const [smiles, setSmiles] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);

  const analyzeSMILES = async () => {
    if (!smiles.trim()) return;
    setAnalyzing(true);
    setAnalysis(null);
    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/molecules/properties`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ smiles }),
      });
      if (res.ok) setAnalysis(await res.json());
    } catch {
      /* */
    }
    setAnalyzing(false);
  };

  const viewState: ViewState =
    state === "loading" ? "loading" :
    error ? "error" :
    candidates.length === 0 ? "empty" :
    "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="Candidate Review"
      emptyTitle="No molecules"
      emptyDescription="Design or import molecules to start the candidate review."
      errorInfo={error ? { code: "FETCH_ERROR", message: error } : undefined}
      onRetry={error ? refetch : undefined}
    >
    <div
      className="flex-1 overflow-y-auto"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-[1100px] mx-auto px-6 py-5">
        <div className="mb-6">
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">
            Molecule Candidate Review
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Comparative ledger of synthetically designed molecules with live
            property analysis.
          </p>
        </div>

        {/* SMILES Analyzer */}
        <div className="card p-5 mb-6">
          <h3 className="text-xs font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <Atom size={14} className="text-[var(--accent)]" /> Quick SMILES
            Analysis
          </h3>
          <div className="flex gap-3">
            <input
              type="text"
              value={smiles}
              onChange={(e) => setSmiles(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && analyzeSMILES()}
              placeholder="Enter SMILES (e.g., CC(=O)Oc1ccccc1C(=O)O for Aspirin)"
              className="flex-1 p-2.5 rounded-lg border border-border bg-[var(--bg-app)] text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            />
            <button
              onClick={analyzeSMILES}
              disabled={analyzing || !smiles.trim()}
              className="glass-button flex items-center gap-2 text-xs px-5 py-2"
            >
              {analyzing ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <FlaskConical size={14} />
              )}{" "}
              Analyze
            </button>
          </div>
          {analysis && (
            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(analysis)
                .filter(([k]) => k !== "smiles" && k !== "error")
                .map(([k, v]) => (
                  <div
                    key={k}
                    className="p-3 rounded-lg bg-[var(--bg-app)] border border-border"
                  >
                    <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase">
                      {k.replace(/_/g, " ")}
                    </div>
                    <div className="text-sm font-medium text-[var(--text-primary)] mt-0.5">
                      {typeof v === "number"
                        ? (v as number).toFixed(2)
                        : String(v)}
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="md:col-span-1 card p-4 text-xs">
            <h3 className="font-semibold text-[var(--text-primary)] uppercase tracking-wider mb-4 border-b border-border/50 pb-2">
              Active Candidates
            </h3>
            {loading && (
              <Loader2
                size={16}
                className="animate-spin text-[var(--accent)]"
              />
            )}
            {!loading && candidates.length === 0 && (
              <p className="text-[var(--text-muted)] italic">
                No candidates queued in design space.
              </p>
            )}
            {!loading &&
              candidates.map((c, i) => (
                <div
                  key={i}
                  className="mb-2 p-2 rounded bg-[var(--bg-app)] border border-border/50 cursor-pointer hover:border-[var(--accent)] transition-colors"
                >
                  <div className="font-mono text-[var(--accent)] truncate">
                    {c.name || c.smiles?.slice(0, 20) || `Candidate ${i + 1}`}
                  </div>
                  <div className="text-[10px] text-[var(--text-muted)]">
                    Score: {c.score?.toFixed(2) || "N/A"}
                  </div>
                </div>
              ))}
          </div>

          <div className="md:col-span-3 card p-10 flex flex-col items-center justify-center border-dashed border-border border-2 min-h-[300px]">
            <Beaker
              size={50}
              className="text-[var(--text-muted)] opacity-50 mb-4"
            />
            <span className="text-sm font-medium text-[var(--text-primary)] mb-2">
              {candidates.length > 0
                ? "Select a candidate to inspect"
                : "Review Queue Empty"}
            </span>
            <span className="text-[11px] text-[var(--text-secondary)] text-center max-w-md leading-relaxed">
              Generate compounds via generative RL models in the{" "}
              <b>Design Studio</b> or use the SMILES analyzer above for quick
              property calculations.
            </span>
          </div>
        </div>
      </div>
    </div>
    </StateWrapper>
  );
}
