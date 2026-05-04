/** PICOVerification — Enhanced PICO (Population, Intervention, Comparison, Outcome) page.
 *  Phase Y-2: search bar, paste abstract, select from evidence, live PICO extraction,
 *  P/I/C/O components with source attribution & confidence, include in dossier action.
 */

import { useEffect, useState, useCallback, useMemo } from "react";
import { useMutation } from "@tanstack/react-query";
import { usePICOItems } from "@/lib/hooks";
import { ensureApiBase, picoExtractAPI, evidenceBundleCreateAPI, evidenceBundleAddItemsAPI } from "@/lib/api";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "@/lib/types";
import { readCockpitHandoff } from "@/lib/canonicalProduct";
import { Loader2, Download, ArrowLeft, FileCheck, ChevronDown, Search, FileText, ClipboardList, Plus, Layers } from "lucide-react";

/* ── Types ─────────────────────────────────────────────── */

interface PICOItem {
  title: string;
  id: string;
  population: {
    text: string;
    status: "pass" | "partial" | "fail";
    detail: string;
  };
  intervention: {
    text: string;
    status: "pass" | "partial" | "fail";
    detail: string;
  };
  comparison: {
    text: string;
    status: "pass" | "partial" | "fail";
    detail: string;
  };
  outcome: {
    text: string;
    status: "pass" | "partial" | "fail";
    detail: string;
  };
  overall: "Strong" | "Moderate" | "Weak";
}

/** Extracted PICO component from live extraction */
interface ExtractedPICOComponent {
  label: string;
  text: string;
  confidence: number;
  source_attribution?: string;
  quality_signal?: "high" | "medium" | "low";
}

interface ExtractedPICOResult {
  population: ExtractedPICOComponent;
  intervention: ExtractedPICOComponent;
  comparison: ExtractedPICOComponent;
  outcome: ExtractedPICOComponent;
  raw_text?: string;
  model_used?: string;
}

/* ── Helpers ───────────────────────────────────────────── */

const statusIcon = (s: "pass" | "partial" | "fail") =>
  s === "pass" ? "✓" : s === "partial" ? "~" : "✗";

const statusColor = (s: "pass" | "partial" | "fail") =>
  s === "pass" ? "#2D8B5F" : s === "partial" ? "#C48820" : "#C43D2F";

const overallBar = (o: "Strong" | "Moderate" | "Weak") => ({
  width: o === "Strong" ? "100%" : o === "Moderate" ? "60%" : "30%",
  color: o === "Strong" ? "#2D8B5F" : o === "Moderate" ? "#C48820" : "#C43D2F",
});

const confidenceColor = (c: number) =>
  c >= 0.8 ? "#2D8B5F" : c >= 0.5 ? "#C48820" : "#C43D2F";

const qualityBadge = (q?: "high" | "medium" | "low") => {
  if (!q) return null;
  const map = {
    high: { bg: "#d1fae5", color: "#065f46", label: "High Quality" },
    medium: { bg: "#fef3c7", color: "#92400e", label: "Medium Quality" },
    low: { bg: "#fef2f2", color: "#991b1b", label: "Low Quality" },
  };
  return map[q];
};

/** Normalize raw API response into ExtractedPICOResult */
function normalizeExtraction(raw: Record<string, unknown>): ExtractedPICOResult | null {
  if (!raw) return null;
  const data = (raw.pico ?? raw.result ?? raw.data ?? raw) as Record<string, unknown>;

  const makeComponent = (key: string): ExtractedPICOComponent => {
    const val = data[key];
    if (typeof val === "string") {
      return { label: key, text: val, confidence: 0.7 };
    }
    if (val && typeof val === "object") {
      const obj = val as Record<string, unknown>;
      return {
        label: key,
        text: (obj.text ?? obj.value ?? obj.description ?? "") as string,
        confidence: (obj.confidence ?? obj.score ?? 0.7) as number,
        source_attribution: (obj.source ?? obj.source_attribution ?? obj.attribution) as string | undefined,
        quality_signal: (obj.quality ?? obj.quality_signal) as "high" | "medium" | "low" | undefined,
      };
    }
    return { label: key, text: "Not extracted", confidence: 0 };
  };

  return {
    population: makeComponent("population"),
    intervention: makeComponent("intervention"),
    comparison: makeComponent("comparison"),
    outcome: makeComponent("outcome"),
    raw_text: (data.raw_text ?? data.input_text) as string | undefined,
    model_used: (data.model_used ?? data.model) as string | undefined,
  };
}


/* ── Main Component ────────────────────────────────────── */

export default function PICOVerification() {
  /* ── Pre-computed PICO items from hook ─────────────── */
  const { data, state, error, refetch } = usePICOItems();
  const items: PICOItem[] = Array.isArray(data) ? data : [];

  /* ── Live extraction mutation ──────────────────────── */
  const extractMut = useMutation({
    mutationFn: (text: string) => picoExtractAPI(text, true),
  });

  /* ── State ────────────────────────────────────────── */
  const [searchQuery, setSearchQuery] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [showPasteArea, setShowPasteArea] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState("");
  const [exporting, setExporting] = useState(false);
  const [addingToDossier, setAddingToDossier] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [expandedCell, setExpandedCell] = useState<string | null>(null);
  const [handoffTopic, setHandoffTopic] = useState<string | null>(null);
  const [dossierSuccess, setDossierSuccess] = useState(false);

  /* ── Cockpit handoff ──────────────────────────────── */
  useEffect(() => {
    const payload = readCockpitHandoff();
    if (!payload || (payload.targetRoute !== "/pico" && payload.targetRoute !== "/pico-verification")) return;
    const topic = payload.entities[0]?.entityName || payload.query || null;
    setHandoffTopic(topic);
    if (topic) {
      setSearchQuery(topic);
    }
  }, []);

  /* ── Extracted result ─────────────────────────────── */
  const extractedResult: ExtractedPICOResult | null = useMemo(() => {
    if (!extractMut.data) return null;
    return normalizeExtraction(extractMut.data as Record<string, unknown>);
  }, [extractMut.data]);

  /* ── Handlers ─────────────────────────────────────── */
  const handleSearch = useCallback(() => {
    const text = pasteText.trim() || searchQuery.trim();
    if (!text) return;
    extractMut.mutate(text);
  }, [searchQuery, pasteText, extractMut]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  }, [handleSearch]);

  const exportPICO = useCallback(async () => {
    setExporting(true);
    const payload = {
      precomputed: items,
      extracted: extractedResult,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "pico_assessment.json";
    a.click();
    URL.revokeObjectURL(url);
    setExporting(false);
  }, [items, extractedResult]);

  const addVerifiedToDossier = useCallback(async () => {
    setAddingToDossier(true);
    setAddError(null);
    setDossierSuccess(false);
    try {
      const strong = items.filter(i => i.overall === "Strong" || i.overall === "Moderate");
      const bundle = await evidenceBundleCreateAPI({
        name: `PICO Verified Evidence — ${searchQuery || "All"}`,
        description: `${strong.length} items passed PICO verification`,
        project_id: "default",
      });
      const bundleId = (bundle as Record<string, unknown>).id as string || (bundle as Record<string, unknown>).bundle_id as string || "";
      if (bundleId && strong.length > 0) {
        await evidenceBundleAddItemsAPI(bundleId, strong.map(i => i.id));
      }
      setDossierSuccess(true);
      setTimeout(() => setDossierSuccess(false), 3000);
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to add to dossier");
    }
    setAddingToDossier(false);
  }, [items, searchQuery]);

  const includeExtractionInDossier = useCallback(async () => {
    if (!extractedResult) return;
    setAddingToDossier(true);
    setAddError(null);
    setDossierSuccess(false);
    try {
      await evidenceBundleCreateAPI({
        name: `PICO Extraction — ${searchQuery || "Live extraction"}`,
        description: `Live PICO extraction: P=${extractedResult.population.text.slice(0, 50)}, I=${extractedResult.intervention.text.slice(0, 50)}`,
        project_id: "default",
      });
      setDossierSuccess(true);
      setTimeout(() => setDossierSuccess(false), 3000);
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to include in dossier");
    }
    setAddingToDossier(false);
  }, [extractedResult, searchQuery]);

  /* ── View state ───────────────────────────────────── */
  const viewState: ViewState = state === "loading" ? "loading" : error ? "error" : items.length === 0 && !extractedResult ? "empty" : "success";

  /* ── Render ───────────────────────────────────────── */
  return (
    <StateWrapper state={viewState} moduleName="PICO Verification"
      emptyTitle="No PICO items"
      emptyDescription="Search a topic, paste an abstract, or run an evidence extraction to populate PICO assessments."
      errorInfo={error ? { code: "FETCH_FAIL", message: error } : undefined}
      onRetry={refetch}
    >
    <div
      className="flex-1 overflow-y-auto p-6"
      style={{ background: "var(--bg-app)" }}
    >
      <h1
        className="text-xl mb-1"
        style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
      >
        PICO Verification
      </h1>
      <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
        Population · Intervention · Comparison · Outcome — structured evidence
        quality assessment with live extraction
      </p>

      {handoffTopic && (
        <div className="mb-4 px-4 py-2 rounded-lg text-xs" style={{ background: "rgba(59, 130, 246, 0.08)", border: "1px solid rgba(59, 130, 246, 0.18)", color: "#1d4ed8" }}>
          Cockpit handoff context: {handoffTopic}
        </div>
      )}

      {/* ── Input Controls ──────────────────────────── */}
      <div className="mb-5 space-y-3">
        {/* Search bar row */}
        <div className="flex gap-2 items-center flex-wrap">
          <div className="relative flex-1 min-w-[240px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search topic for PICO extraction…"
              className="w-full pl-9 pr-3 py-2 text-xs rounded-lg"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)", outline: "none" }}
              aria-label="Search topic for PICO extraction"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={(!searchQuery.trim() && !pasteText.trim()) || extractMut.isPending}
            className="px-4 py-2 text-xs rounded-lg font-semibold flex items-center gap-1.5 transition-colors"
            style={{ background: "var(--accent)", color: "#fff", opacity: (!searchQuery.trim() && !pasteText.trim()) || extractMut.isPending ? 0.5 : 1 }}
            aria-label="Extract PICO components"
          >
            {extractMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Layers size={12} />}
            Extract PICO
          </button>
          <button
            onClick={() => setShowPasteArea(!showPasteArea)}
            className="px-3 py-2 text-xs rounded-lg border flex items-center gap-1.5 transition-colors hover:bg-[var(--bg-elevated)]"
            style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
            aria-label="Toggle paste abstract area"
          >
            <FileText size={12} />
            Paste Abstract
          </button>
          {/* Select from evidence */}
          <select
            value={selectedEvidence}
            onChange={(e) => {
              setSelectedEvidence(e.target.value);
              if (e.target.value) {
                const item = items.find((i) => i.id === e.target.value);
                if (item) {
                  setSearchQuery(item.title);
                }
              }
            }}
            className="px-3 py-2 text-xs rounded-lg"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            aria-label="Select from saved evidence"
          >
            <option value="">Select from evidence…</option>
            {items.map((item) => (
              <option key={item.id} value={item.id}>{item.title}</option>
            ))}
          </select>
        </div>

        {/* Paste abstract textarea */}
        {showPasteArea && (
          <div>
            <textarea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="Paste an abstract or full text here for live PICO extraction…"
              rows={5}
              className="w-full px-3 py-2 text-xs rounded-lg resize-y"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)", outline: "none", fontFamily: "var(--font-mono)" }}
              aria-label="Paste abstract for PICO extraction"
            />
            <p className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>
              Paste an abstract or full text. The PICO extractor will identify Population, Intervention, Comparison, and Outcome components.
            </p>
          </div>
        )}
      </div>

      {/* ── Live Extraction Results ─────────────────── */}
      {extractMut.isPending && (
        <div className="mb-5 p-4 rounded-lg flex items-center gap-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <Loader2 size={16} className="animate-spin" style={{ color: "var(--accent)" }} />
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>Extracting PICO components…</span>
        </div>
      )}

      {extractMut.error && (
        <div className="mb-5 px-4 py-2 rounded-lg text-xs flex items-center gap-2" style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", color: "#ef4444" }}>
          Extraction error: {(extractMut.error as Error).message}
          <button onClick={() => extractMut.reset()} className="ml-auto underline text-[10px]">Dismiss</button>
        </div>
      )}

      {extractedResult && (
        <div className="mb-5">
          <div className="flex items-center gap-2 mb-3">
            <ClipboardList size={14} style={{ color: "var(--accent)" }} />
            <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              Live PICO Extraction
            </h2>
            {extractedResult.model_used && (
              <span className="text-[9px] px-2 py-0.5 rounded" style={{ background: "var(--bg-surface)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                Model: {extractedResult.model_used}
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            {(["population", "intervention", "comparison", "outcome"] as const).map((key) => {
              const comp = extractedResult[key];
              const qBadge = qualityBadge(comp.quality_signal);
              return (
                <div
                  key={key}
                  className="p-4 rounded-lg"
                  style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--accent)" }}>
                      {key.charAt(0).toUpperCase()}{key.slice(1)}
                    </span>
                    {qBadge && (
                      <span className="text-[8px] font-bold px-1.5 py-0.5 rounded" style={{ background: qBadge.bg, color: qBadge.color }}>
                        {qBadge.label}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] leading-relaxed mb-2" style={{ color: "var(--text-primary)" }}>
                    {comp.text || "Not extracted"}
                  </p>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[9px]" style={{ color: "var(--text-muted)" }}>Confidence:</span>
                      <div className="w-12 h-1.5 rounded-full" style={{ background: "var(--border)" }}>
                        <div className="h-full rounded-full" style={{ width: `${comp.confidence * 100}%`, background: confidenceColor(comp.confidence) }} />
                      </div>
                      <span className="text-[9px] font-semibold" style={{ color: confidenceColor(comp.confidence) }}>
                        {(comp.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    {comp.source_attribution && (
                      <span className="text-[9px]" style={{ color: "var(--text-muted)" }}>
                        Source: {comp.source_attribution}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Include in Dossier button for extraction */}
          <div className="flex gap-2 mt-3">
            <button
              onClick={includeExtractionInDossier}
              disabled={addingToDossier}
              className="px-3 py-1.5 text-[10px] rounded flex items-center gap-1 transition-colors"
              style={{ background: dossierSuccess ? "#ecfdf5" : "var(--accent)", color: dossierSuccess ? "#047857" : "#fff" }}
            >
              {addingToDossier ? <Loader2 size={10} className="animate-spin" /> : dossierSuccess ? <FileCheck size={10} /> : <Plus size={10} />}
              {dossierSuccess ? "Included in Dossier" : "Include in Dossier"}
            </button>
          </div>
        </div>
      )}

      {/* ── Summary ─────────────────────────────────── */}
      <div
        className="flex items-center gap-4 py-2.5 px-4 mb-5"
        style={{
          borderLeft: "3px solid var(--accent)",
          background: "var(--bg-surface)",
        }}
      >
        <span
          className="text-sm font-semibold"
          style={{ color: "var(--accent)" }}
        >
          {items.length} evidence items under review
        </span>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          Framework: PICO (Sackett 1997)
        </span>
      </div>

      {/* ── PICO table ──────────────────────────────── */}
      {items.length > 0 && (
        <div
          className="overflow-x-auto"
          style={{ border: "1px solid var(--border)" }}
        >
          <table className="w-full text-xs" style={{ minWidth: 800 }}>
            <thead>
              <tr style={{ background: "var(--bg-surface)" }}>
                <th className="text-left py-2.5 px-3 font-semibold" style={{ width: 200, color: "var(--text-muted)" }}>
                  Evidence
                </th>
                <th className="text-center py-2.5 px-3 font-semibold" style={{ color: "var(--text-muted)" }}>
                  Population
                </th>
                <th className="text-center py-2.5 px-3 font-semibold" style={{ color: "var(--text-muted)" }}>
                  Intervention
                </th>
                <th className="text-center py-2.5 px-3 font-semibold" style={{ color: "var(--text-muted)" }}>
                  Comparison
                </th>
                <th className="text-center py-2.5 px-3 font-semibold" style={{ color: "var(--text-muted)" }}>
                  Outcome
                </th>
                <th className="text-center py-2.5 px-3 font-semibold" style={{ color: "var(--text-muted)" }}>
                  Overall
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const ob = overallBar(item.overall);
                return (
                  <tr key={item.id}>
                    <td className="py-3 px-3" style={{ borderBottom: "1px solid var(--border)" }}>
                      <div className="font-semibold">{item.title}</div>
                      <div style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)", fontSize: "9px" }}>
                        {item.id}
                      </div>
                    </td>
                    {(["population", "intervention", "comparison", "outcome"] as const).map((col) => {
                      const cell = item[col];
                      const cellKey = `${item.id}-${col}`;
                      const isExpanded = expandedCell === cellKey;
                      return (
                        <td
                          key={col}
                          className="py-3 px-3 text-center cursor-pointer"
                          style={{ borderBottom: "1px solid var(--border)" }}
                          onClick={() => setExpandedCell(isExpanded ? null : cellKey)}
                          title={cell.detail || "Click to expand"}
                        >
                          <span style={{ color: statusColor(cell.status), fontWeight: 600 }}>
                            {statusIcon(cell.status)} {cell.text.split("\n")[0]}
                          </span>
                          {cell.text.includes("\n") && (
                            <div style={{ color: "var(--accent)", fontSize: "10px" }}>
                              {cell.text.split("\n")[1]}
                            </div>
                          )}
                          {cell.detail && (
                            <div className="flex items-center justify-center gap-0.5 mt-1">
                              <ChevronDown size={9} className={`transition-transform ${isExpanded ? "rotate-180" : ""}`} style={{ color: "var(--text-muted)" }} />
                            </div>
                          )}
                          {isExpanded && cell.detail && (
                            <div className="mt-1.5 p-2 rounded text-[10px] text-left leading-relaxed" style={{ background: "var(--bg-app)", color: "var(--text-secondary)" }}>
                              {cell.detail}
                            </div>
                          )}
                        </td>
                      );
                    })}
                    <td className="py-3 px-3 text-center" style={{ borderBottom: "1px solid var(--border)" }}>
                      <div className="flex flex-col items-center gap-1">
                        <div className="w-16 h-2 rounded-full" style={{ background: "var(--border)" }}>
                          <div className="h-full rounded-full" style={{ width: ob.width, background: ob.color }} />
                        </div>
                        <span className="text-[9px] font-bold" style={{ color: ob.color }}>
                          {item.overall}
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Grading key ─────────────────────────────── */}
      <div
        className="mt-4 p-4"
        style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}
      >
        <div className="text-xs font-semibold mb-2">📋 PICO Grading Key</div>
        <div className="flex gap-6 text-[10px]">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ background: "#2D8B5F" }} />
            <strong>✓ Strong</strong> — Well-defined, large N, controlled
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ background: "#C48820" }} />
            <strong>~ Moderate</strong> — Partially defined, observational, or small N
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ background: "#C43D2F" }} />
            <strong>✗ Weak</strong> — Missing element, preclinical only, or no comparator
          </span>
        </div>
      </div>

      {/* ── Actions ─────────────────────────────────── */}
      {addError && (
        <div className="mt-4 px-4 py-2 rounded-lg text-xs flex items-center gap-2" style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", color: "#ef4444" }}>
          {addError}
          <button onClick={() => setAddError(null)} className="ml-auto underline text-[10px]">Dismiss</button>
        </div>
      )}
      <div className="flex gap-2 mt-4">
        <button
          className="btn-primary px-3 py-1.5 text-[10px] flex items-center gap-1"
          onClick={addVerifiedToDossier}
          disabled={addingToDossier || items.length === 0}
        >
          {addingToDossier ? <Loader2 size={10} className="animate-spin" /> : <FileCheck size={10} />}
          Add Verified to Dossier
        </button>
        <button
          className="px-3 py-1.5 text-[10px] border rounded flex items-center gap-1"
          style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
          onClick={() => window.history.back()}
        >
          <ArrowLeft size={10} /> Evidence Workspace
        </button>
        <button
          className="px-3 py-1.5 text-[10px] border rounded flex items-center gap-1"
          style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
          onClick={exportPICO}
          disabled={exporting || (items.length === 0 && !extractedResult)}
        >
          {exporting ? <Loader2 size={10} className="animate-spin" /> : <Download size={10} />}
          Export PICO Table
        </button>
      </div>
    </div>
    </StateWrapper>
  );
}
