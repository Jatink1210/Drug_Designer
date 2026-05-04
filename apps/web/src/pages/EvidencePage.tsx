/** Evidence & Patents Workbench — unified table + citation export. */

import { useState, useMemo, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Search,
  BookOpen,
  Download,
  Filter,
  SlidersHorizontal,
  Loader2,
  AlertCircle,
  FileText,
  Calendar,
  ExternalLink,
} from "lucide-react";
import {
  evidenceSearchAPI,
  evidenceExportAPI,
  type EvidenceSearchRequest,
  type EvidenceResult,
} from "@/lib/api";
import EvidenceBadge from "@/components/ui/EvidenceBadge";
import { useSetPageConfidence } from "@/lib/PageConfidenceContext";
import { useRunProgress } from "@/lib/hooks";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "@/lib/types";

export default function EvidencePage() {
  const [query, setQuery] = useState("");
  const [sources, setSources] = useState<string[]>([
    "pubmed",
    "clinicaltrials",
  ]);
  const [yearFrom, setYearFrom] = useState(0);
  const [yearTo, setYearTo] = useState(9999);
  const [exportFmt, setExportFmt] = useState("json");
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const wsProgress = useRunProgress(currentRunId);

  const searchMut = useMutation({
    mutationFn: (req: EvidenceSearchRequest) => evidenceSearchAPI(req),
  });
  const exportMut = useMutation({
    mutationFn: ({ q, f }: { q: string; f: string }) => evidenceExportAPI(q, f),
  });

  const handleSearch = () => {
    if (!query.trim()) return;
    setCurrentRunId(null);
    searchMut.mutate(
      {
        query: query.trim(),
        sources,
        limit: 50,
        year_from: yearFrom,
        year_to: yearTo,
      },
      {
        onSuccess: (result: any) => {
          if (result?.run_id) setCurrentRunId(result.run_id);
        },
      },
    );
  };

  const data = searchMut.data;

  const setConfidence = useSetPageConfidence();
  useEffect(() => {
    if (data) {
      setConfidence({ freshness: "current", sourceCount: sources.length, sourcesQueried: sources });
    } else {
      setConfidence(null);
    }
    return () => setConfidence(null);
  }, [data, sources, setConfidence]);

  // Clear run tracking on WS completion
  useEffect(() => {
    if (wsProgress?.isComplete) setCurrentRunId(null);
  }, [wsProgress?.isComplete]);

  /* §A3.1: Compute view state from mutation status */
  const viewState: ViewState = searchMut.isPending
    ? "loading"
    : searchMut.isError
      ? "error"
      : "success";

  return (
    <StateWrapper state={viewState} moduleName="Evidence">
    <div
      className="flex-1 overflow-y-auto"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-[1440px] mx-auto px-6 py-6">
        <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1" style={{ letterSpacing: "-0.01em" }}>
          Evidence & Literature
        </h1>
        <p className="text-[12px] text-[var(--text-muted)] mb-6">
          Unified search across PubMed, Europe PMC, ClinicalTrials, and
          PatentsView with citation export
        </p>

        {/* Query bar */}
        <div className="card rounded-xl p-5 mb-6" style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)", boxShadow: "var(--shadow-xs)" }}>
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search
                size={15}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="Search publications, trials, patents…"
              className="w-full pl-10 pr-4 py-2.5 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
                style={{ borderColor: "var(--border)", background: "var(--bg-app)" }}
              />
            </div>
            <button
              onClick={handleSearch}
              disabled={searchMut.isPending || !query.trim()}
              className="px-5 py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-40 transition-all hover:shadow-sm"
              style={{ background: "var(--accent)" }}
            >
              {searchMut.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                "Search"
              )}
            </button>
          </div>
          {/* Source + filter bar */}
          <div className="flex items-center gap-3 mt-3 flex-wrap">
            {[
              { id: "pubmed", label: "PubMed" },
              { id: "europepmc", label: "Europe PMC" },
              { id: "clinicaltrials", label: "ClinicalTrials" },
              { id: "patents", label: "Patents" },
            ].map((s) => (
              <label
                key={s.id}
                className="flex items-center gap-1.5 text-xs cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={sources.includes(s.id)}
                  onChange={(e) =>
                    setSources(
                      e.target.checked
                        ? [...sources, s.id]
                        : sources.filter((x) => x !== s.id),
                    )
                  }
                  className="rounded"
                />{" "}
                {s.label}
              </label>
            ))}
            <div className="ml-auto flex items-center gap-2">
              <Calendar size={12} className="text-[var(--text-muted)]" />
              <input
                type="number"
                placeholder="From"
                value={yearFrom || ""}
                onChange={(e) => setYearFrom(+e.target.value)}
                className="w-16 px-2 py-1 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
              <span className="text-xs text-[var(--text-muted)]">–</span>
              <input
                type="number"
                placeholder="To"
                value={yearTo === 9999 ? "" : yearTo}
                onChange={(e) => setYearTo(+e.target.value || 9999)}
                className="w-16 px-2 py-1 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
            </div>
          </div>
        </div>

        {/* Error */}
        {searchMut.isError && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm mb-4">
            <AlertCircle size={16} /> {(searchMut.error as Error).message}
          </div>
        )}

        {wsProgress && !wsProgress.isComplete && (
          <div className="flex items-center gap-3 px-4 py-2 rounded-lg text-xs mb-4" style={{ background: "var(--bg-surface)" }}>
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

        {/* Results */}
        {data && (
          <ResultsView
            data={data}
            query={query}
            exportFmt={exportFmt}
            setExportFmt={setExportFmt}
            exportMut={exportMut}
          />
        )}

        {/* Empty */}
        {!data && !searchMut.isPending && (
          <div className="card rounded-xl p-14 text-center" style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)" }}>
            <BookOpen size={36} className="mx-auto mb-4" style={{ color: "var(--border-strong)" }} />
            <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
              Search for evidence
            </p>
            <p className="text-[12px] mt-1" style={{ color: "var(--text-muted)" }}>
              Results will appear as sortable tables with citation tools
            </p>
          </div>
        )}
      </div>
    </div>
    </StateWrapper>
  );
}

function ResultsView({
  data,
  query,
  exportFmt,
  setExportFmt,
  exportMut,
}: {
  data: EvidenceResult;
  query: string;
  exportFmt: string;
  setExportFmt: (f: string) => void;
  exportMut: any;
}) {
  const categories = Object.keys(data.results);
  const [activeTab, setActiveTab] = useState(categories[0] || "");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs text-[var(--text-muted)]">
          {data.total} results across {categories.length} sources
        </div>
        <div className="flex items-center gap-2">
          <select
            value={exportFmt}
            onChange={(e) => setExportFmt(e.target.value)}
            className="text-xs border rounded px-2 py-1"
            style={{ borderColor: "var(--border)" }}
          >
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
            <option value="bibtex">BibTeX</option>
            <option value="ris">RIS</option>
          </select>
          <button
            onClick={() => exportMut.mutate({ q: query, f: exportFmt })}
            disabled={exportMut.isPending}
            className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border hover:bg-[var(--bg-surface)]"
            style={{ borderColor: "var(--border)" }}
          >
            {exportMut.isPending ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Download size={12} />
            )}{" "}
            Export
          </button>
        </div>
      </div>

      {exportMut.data && (
        <div
          className="rounded-lg border p-3 bg-green-50"
          style={{ borderColor: "#bbf7d0" }}
        >
          <div className="text-xs font-medium text-green-700">
            ✓ Exported {(exportMut.data as any).count} citations as{" "}
            {(exportMut.data as any).format}
          </div>
        </div>
      )}

      {/* Category tabs */}
      <div className="flex gap-1">
        {categories.map((c) => (
          <button
            key={c}
            onClick={() => setActiveTab(c)}
            className={`px-3 py-2 text-xs font-medium rounded-t-lg transition-all ${activeTab === c ? "text-[var(--accent)] border border-b-0" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-surface)]"}`}
            style={
              activeTab === c ? { borderColor: "var(--border)", background: "var(--bg-elevated)" } : undefined
            }
          >
            {c} ({data.results[c]?.length || 0})
          </button>
        ))}
      </div>

      {/* Results table */}
      {data.results[activeTab] && (
        <div className="card rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)" }}>
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-[var(--bg-app)]">
                {["Title / Name", "Year", "ID", "Source", "Details"].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-3 py-2 text-left text-[9px] font-semibold text-[var(--text-muted)] uppercase"
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {data.results[activeTab].map((r: any, i: number) => (
                <tr
                  key={i}
                  className="border-t transition-colors hover:bg-[var(--bg-surface)]"
                  style={{ borderColor: "var(--border-light)" }}
                >
                  <td className="px-3 py-2 max-w-[400px]">
                    <div className="font-medium text-[var(--text-primary)] truncate">
                      {r.title || r.canonical_name || r.name || "—"}
                    </div>
                    {r.journal && (
                      <div className="text-[10px] text-[var(--text-muted)]">
                        {r.journal}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[var(--text-muted)]">
                    {r.year || "—"}
                  </td>
                  <td className="px-3 py-2">
                    {r.pmid && <EvidenceBadge type="pmid" value={r.pmid} />}
                    {r.nct_id && <EvidenceBadge type="nct" value={r.nct_id} />}
                    {r.doi && <EvidenceBadge type="doi" value={r.doi} />}
                    {!r.pmid && !r.nct_id && !r.doi && (
                      <span className="text-[var(--text-muted)]">
                        {r.id || "—"}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[var(--text-muted)]">
                    {r.entity_type || activeTab}
                  </td>
                  <td className="px-3 py-2">
                    {r.url && (
                      <a
                        href={r.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[var(--accent)] flex items-center gap-1"
                      >
                        View <ExternalLink size={9} />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
