/** Report Builder Wizard — create PDF/HTML reports from data. */

import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  FileText,
  Download,
  Loader2,
  CheckCircle2,
  Plus,
  Trash2,
} from "lucide-react";
import {
  reportGenerateAPI,
  reportListAPI,
  ensureApiBase,
  type ReportRequest,
  type ReportResult,
} from "@/lib/api";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";

const AVAILABLE_SECTIONS = [
  {
    id: "summary",
    label: "Query Summary",
    desc: "Search intent, totals, sources",
  },
  { id: "results", label: "Results Tables", desc: "Categorized entity tables" },
  {
    id: "evidence",
    label: "Evidence Citations",
    desc: "Top evidence with PMID/DOI links",
  },
  {
    id: "structures",
    label: "Structure Data",
    desc: "PDB summaries and screenshots",
  },
  {
    id: "docking",
    label: "Docking Results",
    desc: "Poses, affinities, interactions",
  },
  {
    id: "pathways",
    label: "Pathway Diagrams",
    desc: "Reactome/KEGG pathway maps",
  },
  { id: "graph", label: "Graph Snapshots", desc: "KG subgraph with metrics" },
  {
    id: "provenance",
    label: "Reproducibility Appendix",
    desc: "Configs, timestamps, sources",
  },
];

export default function ReportPage() {
  const [title, setTitle] = useState("Research Report");
  const [query, setQuery] = useState("");
  const [notes, setNotes] = useState("");
  const [sections, setSections] = useState([
    "summary",
    "results",
    "evidence",
    "provenance",
  ]);
  const [apiBase, setApiBase] = useState("/api");

  useEffect(() => {
    ensureApiBase().then(setApiBase);
  }, []);

  const generateMut = useMutation({
    mutationFn: (req: ReportRequest) => reportGenerateAPI(req),
  });
  const historyQ = useQuery({
    queryKey: ["reportList"],
    queryFn: reportListAPI,
  });

  const historyList = Array.isArray(historyQ.data) ? historyQ.data : [];

  const viewState: ViewState =
    historyQ.isLoading ? "loading" :
    historyQ.error ? "error" :
    "success";

  const handleGenerate = () => {
    generateMut.mutate({ title, query, sections, notes });
  };

  const toggleSection = (id: string) => {
    setSections((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  };

  return (
    <StateWrapper
      state={viewState}
      moduleName="Report Builder"
      errorInfo={historyQ.error ? { code: "FETCH_ERROR", message: String(historyQ.error) } : undefined}
      onRetry={historyQ.error ? () => historyQ.refetch() : undefined}
    >
    <div
      className="flex-1 overflow-y-auto"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-[900px] mx-auto px-6 py-5">
        <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
          Report Builder
        </h1>
        <p className="text-xs text-[var(--text-muted)] mb-5">
          Generate clean HTML reports from your research data
        </p>

        <div className="grid grid-cols-3 gap-5">
          {/* Configuration */}
          <div className="col-span-2 space-y-4">
            <div className="card rounded-xl p-4">
              <h2 className="text-xs font-semibold text-[var(--text-primary)] mb-3">
                Report Configuration
              </h2>
              <div className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-[var(--text-secondary)] mb-1 block">
                    Report Title
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-lg border"
                    style={{ borderColor: "var(--border)" }}
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-[var(--text-secondary)] mb-1 block">
                    Query / Topic
                  </label>
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g., EGFR inhibitors in NSCLC"
                    className="w-full px-3 py-2 text-xs rounded-lg border"
                    style={{ borderColor: "var(--border)" }}
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-[var(--text-secondary)] mb-1 block">
                    Notes
                  </label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Add analyst notes…"
                    className="w-full h-20 px-3 py-2 text-xs rounded-lg border resize-none"
                    style={{ borderColor: "var(--border)" }}
                  />
                </div>
              </div>
            </div>

            <div className="card rounded-xl p-4">
              <h2 className="text-xs font-semibold text-[var(--text-primary)] mb-3">
                Sections
              </h2>
              <div className="space-y-1">
                {AVAILABLE_SECTIONS.map((s) => (
                  <label
                    key={s.id}
                    className="flex items-center gap-3 py-2 px-2 rounded hover:bg-[var(--bg-surface)] cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={sections.includes(s.id)}
                      onChange={() => toggleSection(s.id)}
                      className="rounded"
                    />
                    <div>
                      <div className="text-xs font-medium text-[var(--text-primary)]">
                        {s.label}
                      </div>
                      <div className="text-[10px] text-[var(--text-muted)]">
                        {s.desc}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <button
              onClick={handleGenerate}
              disabled={generateMut.isPending}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium text-white"
              style={{ background: "var(--accent)" }}
            >
              {generateMut.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <FileText size={16} />
              )}
              Generate Report
            </button>

            {generateMut.isError && (
              <div
                className="rounded-xl border p-4 bg-red-50"
                style={{ borderColor: "#fecaca" }}
              >
                <div className="flex items-center gap-2 text-sm font-medium text-red-700">
                  Report generation failed:{" "}
                  {(generateMut.error as Error).message}
                </div>
              </div>
            )}

            {generateMut.data && (
              <div
                className="rounded-xl border p-4 bg-green-50"
                style={{ borderColor: "#bbf7d0" }}
              >
                <div className="flex items-center gap-2 text-sm font-medium text-green-700">
                  <CheckCircle2 size={16} /> Report Generated
                </div>
                <div className="text-xs text-green-600 mt-1">
                  ID: {generateMut.data.report_id} • Sections:{" "}
                  {generateMut.data.sections.join(", ")}
                </div>
                <div className="flex gap-2 mt-2">
                  <a
                    href={`${apiBase}/reports/${generateMut.data.report_id}`}
                    target="_blank"
                    className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-white border text-green-700 hover:bg-green-50"
                    style={{ borderColor: "#bbf7d0" }}
                  >
                    <Download size={12} /> Download HTML
                  </a>
                </div>
              </div>
            )}
          </div>

          {/* Sidebar — History */}
          <div>
            <div className="card rounded-xl p-4">
              <h2 className="text-xs font-semibold text-[var(--text-primary)] mb-3">
                Report History
              </h2>
              {historyQ.isLoading && (
                <Loader2
                  size={14}
                  className="animate-spin text-[var(--text-muted)]"
                />
              )}
              {historyQ.data && (historyQ.data as any[]).length > 0 ? (
                <div className="space-y-2">
                  {(historyQ.data as any[]).map((r: any) => (
                    <div
                      key={r.report_id}
                      className="rounded-lg border p-2"
                      style={{ borderColor: "var(--border-light)" }}
                    >
                      <div className="text-xs font-medium text-[var(--text-primary)]">
                        {r.title}
                      </div>
                      <div className="text-[10px] text-[var(--text-muted)]">
                        {r.generated_at}
                      </div>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(r.sections || []).map((s: string) => (
                          <span
                            key={s}
                            className="text-[8px] px-1 py-0.5 rounded bg-[var(--bg-inset)] text-[var(--text-muted)]"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[var(--text-muted)]">
                  No reports generated yet
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
    </StateWrapper>
  );
}
