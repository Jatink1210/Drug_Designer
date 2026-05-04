/** ESM3DesignPanel — De Novo Protein Design via EvolutionaryScale Forge API.
 *  Extracted as a separate async chunk so it can be lazy-loaded (§O-6).
 *  §24.2: ESM-3 Large scaffold generation.
 */

import { useState, useEffect } from "react";
import { Loader2, Dna, Sparkles, ChevronDown, ChevronUp } from "lucide-react";
import { esm3ScaffoldAPI, esm3HealthAPI } from "@/lib/api";

interface ESM3ScaffoldResult {
  sequence?: string;
  confidence?: number;
  per_residue_confidence?: number[];
  model?: string;
  provenance?: Record<string, unknown>;
  error?: string;
}

export default function ESM3DesignPanel() {
  const [partialSeq, setPartialSeq] = useState("");
  const [targetDesc, setTargetDesc] = useState("");
  const [numSteps, setNumSteps] = useState(8);
  const [temperature, setTemperature] = useState(0.7);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ESM3ScaffoldResult | null>(null);
  const [forgeStatus, setForgeStatus] = useState<"unknown" | "ok" | "degraded">("unknown");
  const [expanded, setExpanded] = useState(false);

  // Check Forge API health on mount
  useEffect(() => {
    esm3HealthAPI()
      .then((r: any) => setForgeStatus(r?.status === "ok" ? "ok" : "degraded"))
      .catch(() => setForgeStatus("degraded"));
  }, []);

  const runScaffold = async () => {
    if (!partialSeq.trim() && !targetDesc.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res: any = await esm3ScaffoldAPI({
        partial_sequence: partialSeq.trim() || undefined,
        target_description: targetDesc.trim() || undefined,
        num_steps: numSteps,
        temperature,
      });
      setResult(res ?? null);
    } catch (err: unknown) {
      setResult({ error: err instanceof Error ? err.message : "Scaffold generation failed" });
    } finally {
      setLoading(false);
    }
  };

  const statusColor =
    forgeStatus === "ok"
      ? "var(--success)"
      : forgeStatus === "degraded"
        ? "var(--warning)"
        : "var(--text-muted)";
  const statusLabel =
    forgeStatus === "ok"
      ? "Forge API connected"
      : forgeStatus === "degraded"
        ? "Forge API unavailable (set ESM_FORGE_API_KEY)"
        : "Checking…";

  return (
    <div className="rounded-lg" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
      {/* Header */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <Dna size={18} style={{ color: "var(--accent)" }} />
          <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
            ESM-3 Large — De Novo Protein Design
          </span>
          <Sparkles size={13} style={{ color: "var(--accent)", opacity: 0.8 }} />
          <span
            className="text-xs px-1.5 py-0.5 rounded-full"
            style={{ background: "var(--bg-inset)", color: statusColor }}
          >
            {statusLabel}
          </span>
        </div>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t" style={{ borderColor: "var(--border)" }}>
          <p className="text-xs mt-3" style={{ color: "var(--text-secondary)" }}>
            Generate de-novo protein scaffolds for PPI inhibitors using ESM-3 Large (98B) via
            EvolutionaryScale Forge API. Use <code>_</code> as mask tokens for positions to be
            generated.
          </p>

          {/* Partial sequence */}
          <div className="space-y-1">
            <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              Partial Sequence{" "}
              <span className="opacity-50">(use _ for masked positions)</span>
            </label>
            <input
              className="w-full rounded px-3 py-2 text-xs font-mono"
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
              placeholder="e.g. MKTAY____QRQISFVK____WKRQTLG"
              value={partialSeq}
              onChange={(e) => setPartialSeq(e.target.value)}
            />
          </div>

          {/* Target description */}
          <div className="space-y-1">
            <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              Target / Function Description
            </label>
            <input
              className="w-full rounded px-3 py-2 text-xs"
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
              placeholder="e.g. PPI inhibitor targeting EGFR-KRAS interface"
              value={targetDesc}
              onChange={(e) => setTargetDesc(e.target.value)}
            />
          </div>

          {/* Parameters */}
          <div className="flex gap-4">
            <div className="space-y-1 flex-1">
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                Generation Steps <span className="opacity-50">(1–32)</span>
              </label>
              <input
                type="number"
                min={1}
                max={32}
                className="w-full rounded px-3 py-2 text-xs"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                }}
                value={numSteps}
                onChange={(e) => setNumSteps(Number(e.target.value))}
              />
            </div>
            <div className="space-y-1 flex-1">
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                Temperature <span className="opacity-50">(0–2)</span>
              </label>
              <input
                type="number"
                min={0}
                max={2}
                step={0.05}
                className="w-full rounded px-3 py-2 text-xs"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                }}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
              />
            </div>
          </div>

          <button
            onClick={runScaffold}
            disabled={loading || (!partialSeq.trim() && !targetDesc.trim())}
            className="flex items-center gap-2 px-4 py-2 text-sm text-white rounded disabled:opacity-50 transition-colors"
            style={{ background: "var(--accent)" }}
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Dna size={14} />}
            Generate Scaffold
          </button>

          {/* Result */}
          {result && (
            <div
              className="rounded p-3 text-xs"
              style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}
            >
              {result.error ? (
                <p style={{ color: "var(--error)" }}>{result.error}</p>
              ) : (
                <div className="space-y-2">
                  <div>
                    <span className="font-medium" style={{ color: "var(--text-secondary)" }}>
                      Generated Sequence:
                    </span>
                    <p className="font-mono mt-1 break-all" style={{ color: "var(--success)" }}>
                      {result.sequence}
                    </p>
                  </div>
                  {result.confidence !== undefined && (
                    <p style={{ color: "var(--text-muted)" }}>
                      Mean Confidence:{" "}
                      <span style={{ color: "var(--text-primary)" }}>
                        {(result.confidence * 100).toFixed(1)}%
                      </span>
                    </p>
                  )}
                  {result.model && (
                    <p style={{ color: "var(--text-muted)" }}>Model: {result.model}</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
