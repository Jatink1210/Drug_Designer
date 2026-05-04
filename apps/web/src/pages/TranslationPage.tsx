/** TranslationPage — Translation module (§77, §127). */

import { useState } from "react";
import {
  ArrowRightLeft,
  Save,
  Loader2,
  AlertTriangle,
  CheckCircle,
  Download,
  FileText,
} from "lucide-react";
import {
  translationTransformAPI,
  translationSaveAPI,
} from "../lib/api";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";

const FORMATS = [
  { value: "json", label: "JSON" },
  { value: "csv", label: "CSV" },
  { value: "tsv", label: "TSV" },
  { value: "fasta", label: "FASTA" },
  { value: "sdf", label: "SDF" },
  { value: "smiles", label: "SMILES" },
  { value: "xml", label: "XML" },
  { value: "pdb", label: "PDB" },
];

type Status = "idle" | "loading" | "success" | "error";

interface TransformResult {
  result_id: string;
  source_format: string;
  target_format: string;
  status: string;
  transformed: unknown;
}

export default function TranslationPage() {
  const [sourceFormat, setSourceFormat] = useState("json");
  const [targetFormat, setTargetFormat] = useState("csv");
  const [inputData, setInputData] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<TransformResult | null>(null);
  const [saveStatus, setSaveStatus] = useState<Status>("idle");
  const [saveLabel, setSaveLabel] = useState("");

  const handleTransform = async () => {
    if (!inputData.trim()) {
      setError("Please enter data to transform.");
      setStatus("error");
      return;
    }
    setStatus("loading");
    setError("");
    setResult(null);
    setSaveStatus("idle");
    try {
      let parsed: unknown = inputData;
      if (sourceFormat === "json") {
        try {
          parsed = JSON.parse(inputData);
        } catch {
          // Send as raw string if not valid JSON
        }
      }
      const res = (await translationTransformAPI(
        sourceFormat,
        targetFormat,
        parsed,
      )) as unknown as TransformResult;
      setResult(res);
      setStatus("success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Transform failed";
      setError(msg);
      setStatus("error");
    }
  };

  const handleSave = async () => {
    if (!result?.result_id) return;
    setSaveStatus("loading");
    try {
      await translationSaveAPI(result.result_id, saveLabel || undefined);
      setSaveStatus("success");
    } catch {
      setSaveStatus("error");
    }
  };

  const handleDownload = () => {
    if (!result?.transformed) return;
    const content =
      typeof result.transformed === "string"
        ? result.transformed
        : JSON.stringify(result.transformed, null, 2);
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `translation_${result.result_id}.${targetFormat}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const formatOutput = (data: unknown): string => {
    if (typeof data === "string") return data;
    return JSON.stringify(data, null, 2);
  };

  const viewState: ViewState =
    status === "loading" ? "loading" :
    status === "error" ? "error" :
    "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="Translation"
      errorInfo={error ? { code: "TRANSFORM_ERROR", message: error } : undefined}
      onRetry={error ? () => { setStatus("idle"); setError(""); } : undefined}
    >
    <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
      <h1 className="text-xl font-bold mb-1" style={{ color: "var(--text-primary)" }}>
        Translation
      </h1>
      <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
        Transform, review, and save translation results between data formats and ontologies.
      </p>

      {/* ── Configuration Panel ────────────────────── */}
      <div
        className="rounded-lg border p-5 mb-4"
        style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
      >
        <div className="flex items-center gap-2 mb-4">
          <FileText size={16} style={{ color: "var(--accent)" }} />
          <span className="text-xs uppercase tracking-widest font-bold" style={{ color: "var(--accent)" }}>
            Format Configuration
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-4 mb-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
              Source Format
            </label>
            <select
              value={sourceFormat}
              onChange={(e) => setSourceFormat(e.target.value)}
              className="rounded border px-3 py-1.5 text-sm"
              style={{
                borderColor: "var(--border)",
                background: "var(--bg-app)",
                color: "var(--text-primary)",
              }}
            >
              {FORMATS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>

          <ArrowRightLeft size={18} className="mt-4" style={{ color: "var(--text-muted)" }} />

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
              Target Format
            </label>
            <select
              value={targetFormat}
              onChange={(e) => setTargetFormat(e.target.value)}
              className="rounded border px-3 py-1.5 text-sm"
              style={{
                borderColor: "var(--border)",
                background: "var(--bg-app)",
                color: "var(--text-primary)",
              }}
            >
              {FORMATS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <label className="text-xs font-medium mb-1 block" style={{ color: "var(--text-muted)" }}>
          Input Data
        </label>
        <textarea
          value={inputData}
          onChange={(e) => setInputData(e.target.value)}
          rows={10}
          placeholder={`Paste your ${sourceFormat.toUpperCase()} data here…`}
          className="w-full rounded border p-3 text-sm font-mono resize-y"
          style={{
            borderColor: "var(--border)",
            background: "var(--bg-app)",
            color: "var(--text-primary)",
          }}
        />

        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={handleTransform}
            disabled={status === "loading"}
            className="flex items-center gap-2 rounded px-4 py-2 text-sm font-medium transition-colors"
            style={{
              background: "var(--accent)",
              color: "#fff",
              opacity: status === "loading" ? 0.6 : 1,
            }}
          >
            {status === "loading" ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <ArrowRightLeft size={14} />
            )}
            {status === "loading" ? "Transforming…" : "Transform"}
          </button>
        </div>
      </div>

      {/* ── Error ──────────────────────────────────── */}
      {status === "error" && (
        <div
          className="rounded-lg border p-4 mb-4 flex items-start gap-3"
          style={{ borderColor: "#ef4444", background: "rgba(239,68,68,0.08)" }}
        >
          <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: "#ef4444" }} />
          <p className="text-sm" style={{ color: "#ef4444" }}>
            {error}
          </p>
        </div>
      )}

      {/* ── Result Panel ──────────────────────────── */}
      {result && (
        <div
          className="rounded-lg border p-5"
          style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <CheckCircle size={16} style={{ color: "#22c55e" }} />
              <span className="text-xs uppercase tracking-widest font-bold" style={{ color: "#22c55e" }}>
                Transform Complete
              </span>
            </div>
            <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
              {result.source_format} → {result.target_format} · {result.result_id}
            </span>
          </div>

          <pre
            className="rounded border p-3 text-xs font-mono overflow-auto max-h-64 mb-4"
            style={{
              borderColor: "var(--border)",
              background: "var(--bg-app)",
              color: "var(--text-primary)",
            }}
          >
            {formatOutput(result.transformed)}
          </pre>

          {/* ── Save / Download Controls ────────── */}
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                Label (optional)
              </label>
              <input
                type="text"
                value={saveLabel}
                onChange={(e) => setSaveLabel(e.target.value)}
                placeholder="e.g. T2DM gene mapping"
                className="rounded border px-3 py-1.5 text-sm w-56"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-app)",
                  color: "var(--text-primary)",
                }}
              />
            </div>
            <button
              onClick={handleSave}
              disabled={saveStatus === "loading"}
              className="flex items-center gap-2 rounded px-4 py-2 text-sm font-medium border transition-colors"
              style={{
                borderColor: "var(--accent)",
                color: "var(--accent)",
                opacity: saveStatus === "loading" ? 0.6 : 1,
              }}
            >
              {saveStatus === "loading" ? (
                <Loader2 size={14} className="animate-spin" />
              ) : saveStatus === "success" ? (
                <CheckCircle size={14} />
              ) : (
                <Save size={14} />
              )}
              {saveStatus === "success" ? "Saved" : "Save to Project"}
            </button>
            <button
              onClick={handleDownload}
              className="flex items-center gap-2 rounded px-4 py-2 text-sm font-medium border transition-colors"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
            >
              <Download size={14} />
              Download
            </button>
          </div>

          {saveStatus === "error" && (
            <p className="text-xs mt-2" style={{ color: "#ef4444" }}>
              Failed to save. The result may have expired — try transforming again.
            </p>
          )}
        </div>
      )}
    </div>
    </StateWrapper>
  );
}
