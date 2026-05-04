import { useState, useEffect } from "react";
import { History, Search, Clock, ArrowRight, RefreshCw, Filter } from "lucide-react";
import { useNavigate } from "react-router-dom";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "../lib/types";
import { ensureApiBase } from "@/lib/api";

interface QueryRecord {
  id: string;
  query: string;
  run_type: string;
  state: string;
  created_at: string;
  result_count?: number;
  sources?: string[];
  duration_ms?: number;
}

export default function HistoricalQueries() {
  const navigate = useNavigate();
  const [queries, setQueries] = useState<QueryRecord[]>([]);
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [filterText, setFilterText] = useState("");

  const fetchQueries = () => {
    setViewState("loading");
    ensureApiBase().then((base) =>
      fetch(`${base}/runs?limit=100`, { credentials: "include" })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((env) => {
          const runs = env?.data?.runs ?? env?.data ?? [];
          const mapped: QueryRecord[] = (Array.isArray(runs) ? runs : []).map(
            (r: Record<string, unknown>) => ({
              id: String(r.id || r.run_id || ""),
              query: String(r.query || r.input_query || r.run_type || "Unknown"),
              run_type: String(r.run_type || "search"),
              state: String(r.state || r.status || "unknown"),
              created_at: String(r.created_at || ""),
              result_count: typeof r.result_count === "number" ? r.result_count : undefined,
              sources: Array.isArray(r.sources) ? r.sources.map(String) : undefined,
              duration_ms: typeof r.duration_ms === "number" ? r.duration_ms : undefined,
            }),
          );
          setQueries(mapped);
          setViewState(mapped.length === 0 ? "empty" : "success");
        })
        .catch(() => setViewState("error")),
    );
  };

  useEffect(() => { fetchQueries(); }, []);

  const filtered = queries.filter(
    (q) =>
      q.query.toLowerCase().includes(filterText.toLowerCase()) ||
      q.run_type.toLowerCase().includes(filterText.toLowerCase()),
  );

  const stateColor = (s: string) => {
    const up = s.toUpperCase();
    if (up === "COMPLETED" || up === "SUCCESS") return "var(--success, #10b981)";
    if (up === "RUNNING" || up === "PENDING" || up === "QUEUED") return "var(--accent)";
    if (up === "FAILED" || up === "ERROR") return "var(--error, #ef4444)";
    return "var(--text-muted)";
  };

  return (
    <StateWrapper
      state={viewState}
      moduleName="Query History"
      emptyTitle="No query history"
      emptyDescription="Run a search to populate the query log."
      onRetry={fetchQueries}
    >
      <div
        className="flex-1 overflow-y-auto"
        style={{ background: "var(--bg-app)" }}
      >
        <div className="max-w-[1100px] mx-auto px-6 py-5">
          {/* Header */}
          <div className="mb-5 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
            <div>
              <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
                Query History
              </h1>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                Historical log of all search, disease, and analysis queries across this project.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={fetchQueries}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-medium border transition-all hover:shadow-sm"
                style={{ borderColor: "var(--border)", color: "var(--text-secondary)", background: "var(--bg-surface)" }}
              >
                <RefreshCw size={12} /> Refresh
              </button>
            </div>
          </div>

          {/* Filter bar */}
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg border mb-4"
            style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
          >
            <Filter size={13} style={{ color: "var(--text-muted)" }} />
            <input
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              placeholder="Filter queries…"
              className="flex-1 text-[12px] bg-transparent outline-none"
              style={{ color: "var(--text-primary)" }}
            />
            <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
              {filtered.length} of {queries.length}
            </span>
          </div>

          {/* Query list */}
          <div className="space-y-2">
            {filtered.map((q) => (
              <div
                key={q.id}
                className="flex items-center gap-4 px-4 py-3 rounded-lg border transition-all hover:shadow-sm cursor-pointer group"
                style={{ borderColor: "var(--border)", background: "var(--bg-elevated)" }}
                onClick={() => navigate(`/runs/${q.id}`)}
              >
                {/* Icon */}
                <div
                  className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center"
                  style={{ background: "var(--bg-surface)" }}
                >
                  <Search size={14} style={{ color: "var(--accent)" }} />
                </div>

                {/* Query text + meta */}
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium truncate" style={{ color: "var(--text-primary)" }}>
                    {q.query}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ background: "var(--bg-surface)", color: "var(--text-muted)" }}>
                      {q.run_type}
                    </span>
                    {q.result_count !== undefined && (
                      <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                        {q.result_count} results
                      </span>
                    )}
                    {q.duration_ms !== undefined && (
                      <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                        {(q.duration_ms / 1000).toFixed(1)}s
                      </span>
                    )}
                  </div>
                </div>

                {/* State badge */}
                <span
                  className="shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full"
                  style={{ color: stateColor(q.state), background: `${stateColor(q.state)}15` }}
                >
                  {q.state.toLowerCase()}
                </span>

                {/* Timestamp */}
                <div className="shrink-0 flex items-center gap-1 text-[10px]" style={{ color: "var(--text-muted)" }}>
                  <Clock size={10} />
                  {q.created_at ? new Date(q.created_at).toLocaleString() : "—"}
                </div>

                {/* Arrow */}
                <ArrowRight size={13} className="shrink-0 opacity-0 group-hover:opacity-60 transition-opacity" style={{ color: "var(--text-muted)" }} />
              </div>
            ))}
          </div>

          {filtered.length === 0 && queries.length > 0 && (
            <div className="text-center py-12">
              <History size={28} className="mx-auto mb-3" style={{ color: "var(--text-muted)", opacity: 0.4 }} />
              <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
                No queries match "{filterText}"
              </p>
            </div>
          )}
        </div>
      </div>
    </StateWrapper>
  );
}
