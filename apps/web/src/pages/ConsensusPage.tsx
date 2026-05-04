/**
 * ConsensusPage — MAV Consensus Dashboard (B-7)
 *
 * Shows all consensus votes for a selected run with vote breakdown visualizations.
 * Route: /consensus
 */

import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Scale,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { ensureApiBase } from "@/lib/api";

interface VoteTrace {
  id: string;
  specialist_role: string;
  entity_id: string;
  verdict: "verified" | "contradicted" | "uncertain" | string;
  score: number;
  confidence: number;
  reasoning: string;
  key_evidence_cited?: string[];
  created_at: string | null;
}

interface ConsensusAgg {
  run_id: string;
  entity_id: string | null;
  vote_count: number;
  mean_score: number;
  mean_confidence: number;
  verdict: string;
  consensus_met: boolean;
  verdict_counts: Record<string, number>;
  minority_dissent: { specialist_role: string; vote: VoteTrace }[];
  full_trace: VoteTrace[];
}

const verdictIcon = (v: string) => {
  if (v === "verified") return <CheckCircle2 size={14} className="text-green-500" />;
  if (v === "contradicted") return <XCircle size={14} className="text-red-500" />;
  if (v === "conflict") return <AlertTriangle size={14} className="text-amber-500" />;
  return <HelpCircle size={14} className="text-slate-400" />;
};

const verdictBadge: Record<string, string> = {
  verified: "bg-green-100 text-green-700",
  contradicted: "bg-red-100 text-red-600",
  conflict: "bg-amber-100 text-amber-700",
  uncertain: "bg-slate-100 text-slate-600",
  no_votes: "bg-slate-100 text-slate-500",
};

export default function ConsensusPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [runId, setRunId] = useState(searchParams.get("run_id") ?? "");
  const [entityId, setEntityId] = useState(searchParams.get("entity_id") ?? "");
  const [data, setData] = useState<ConsensusAgg | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const fetch = async (rid: string, eid?: string) => {
    if (!rid.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const base = await ensureApiBase();
      const params = new URLSearchParams();
      if (eid?.trim()) params.set("entity_id", eid.trim());
      const res = await window.fetch(`${base}/consensus/${rid.trim()}?${params}`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setData(json.data ?? json);
    } catch (e: any) {
      setError(e.message ?? "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const rid = searchParams.get("run_id");
    const eid = searchParams.get("entity_id") ?? "";
    if (rid) {
      setRunId(rid);
      setEntityId(eid);
      fetch(rid, eid);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleQuery = () => {
    const params: Record<string, string> = {};
    if (runId.trim()) params.run_id = runId.trim();
    if (entityId.trim()) params.entity_id = entityId.trim();
    setSearchParams(params);
    fetch(runId, entityId);
  };

  const toggleExpand = (i: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
          <Scale size={20} className="text-violet-600" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">MAV Consensus Dashboard</h1>
          <p className="text-xs text-[var(--text-muted)]">Multi-Agent Voting vote trace per run / entity</p>
        </div>
      </div>

      {/* Query controls */}
      <div className="card p-4 rounded-xl space-y-3">
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="text-[10px] uppercase text-[var(--text-muted)] font-medium">Run ID</label>
            <input
              className="input w-full mt-0.5 font-mono text-xs"
              placeholder="uuid"
              value={runId}
              onChange={(e) => setRunId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleQuery()}
            />
          </div>
          <div className="flex-1">
            <label className="text-[10px] uppercase text-[var(--text-muted)] font-medium">
              Entity ID (optional)
            </label>
            <input
              className="input w-full mt-0.5 text-xs"
              placeholder="gene_symbol or target id"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleQuery()}
            />
          </div>
        </div>
        <button
          onClick={handleQuery}
          disabled={loading || !runId.trim()}
          className="btn btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50"
        >
          {loading ? <RefreshCw size={13} className="animate-spin" /> : <Scale size={13} />}
          {loading ? "Loading…" : "Fetch Votes"}
        </button>
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>

      {/* Results */}
      {data && (
        <div className="space-y-4">
          {/* Summary row */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Votes", value: data.vote_count },
              { label: "Mean Score", value: `${(data.mean_score * 100).toFixed(0)}%` },
              { label: "Mean Confidence", value: `${(data.mean_confidence * 100).toFixed(0)}%` },
              {
                label: "Verdict",
                value: (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${verdictBadge[data.verdict] ?? "bg-slate-100 text-slate-600"}`}>
                    {data.verdict?.toUpperCase()}
                  </span>
                ),
              },
            ].map((m, i) => (
              <div key={i} className="card p-3 rounded-xl text-center">
                <div className="text-lg font-bold text-[var(--text-primary)]">{m.value}</div>
                <div className="text-[9px] uppercase text-[var(--text-muted)]">{m.label}</div>
              </div>
            ))}
          </div>

          {/* Verdict breakdown bar */}
          {data.verdict_counts && (
            <div className="card p-4 rounded-xl">
              <div className="text-[10px] uppercase font-medium text-[var(--text-muted)] mb-2">Verdict Breakdown</div>
              <div className="flex rounded-full overflow-hidden h-4">
                {(["verified", "contradicted", "uncertain"] as const).map((v) => {
                  const count = data.verdict_counts?.[v] ?? 0;
                  const pct = data.vote_count > 0 ? (count / data.vote_count) * 100 : 0;
                  if (pct === 0) return null;
                  const colors: Record<string, string> = {
                    verified: "bg-green-400",
                    contradicted: "bg-red-400",
                    uncertain: "bg-slate-300",
                  };
                  return (
                    <div
                      key={v}
                      style={{ width: `${pct}%` }}
                      className={`${colors[v]} flex items-center justify-center`}
                      title={`${v}: ${count}`}
                    />
                  );
                })}
              </div>
              <div className="flex gap-4 mt-1.5 text-[10px]">
                {Object.entries(data.verdict_counts ?? {}).map(([v, c]) => (
                  <span key={v} className="flex items-center gap-1 text-[var(--text-muted)]">
                    {verdictIcon(v)} {v}: <strong>{c as number}</strong>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Minority dissent */}
          {data.minority_dissent?.length > 0 && (
            <div className="card p-4 rounded-xl border-l-4 border-amber-400">
              <div className="text-xs font-semibold text-amber-700 flex items-center gap-1.5 mb-2">
                <AlertTriangle size={13} /> Minority Dissent ({data.minority_dissent.length})
              </div>
              {data.minority_dissent.map((d, i) => (
                <div key={i} className="text-[11px] text-[var(--text-secondary)]">
                  {d.specialist_role}: {d.vote?.verdict} (score {(d.vote?.score * 100).toFixed(0)}%)
                </div>
              ))}
            </div>
          )}

          {/* Full trace */}
          {data.full_trace?.length > 0 && (
            <div className="card p-4 rounded-xl">
              <div className="text-[10px] uppercase font-medium text-[var(--text-muted)] mb-3">
                Full Vote Trace ({data.full_trace.length})
              </div>
              <div className="space-y-2">
                {data.full_trace.map((v, i) => (
                  <div key={i} className="rounded-lg border" style={{ borderColor: "var(--border)" }}>
                    <button
                      className="w-full flex items-center gap-3 p-3 text-left"
                      onClick={() => toggleExpand(i)}
                    >
                      <div className="w-7 h-7 rounded-full bg-violet-100 flex items-center justify-center text-[10px] font-bold text-violet-700 shrink-0">
                        {v.specialist_role?.[0]?.toUpperCase() ?? "?"}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-[var(--text-primary)]">
                            {v.specialist_role}
                          </span>
                          <div className="flex items-center gap-2">
                            {verdictIcon(v.verdict)}
                            <span className={`text-[10px] font-semibold ${verdictBadge[v.verdict] ? `px-1.5 py-0.5 rounded-full ${verdictBadge[v.verdict]}` : ""}`}>
                              {v.verdict}
                            </span>
                            <span className="text-[10px] font-mono text-[var(--text-muted)]">
                              {(v.score * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                        {!expanded.has(i) && v.reasoning && (
                          <p className="text-[10px] text-[var(--text-muted)] truncate mt-0.5">{v.reasoning}</p>
                        )}
                      </div>
                      {expanded.has(i) ? <ChevronUp size={13} className="shrink-0 text-[var(--text-muted)]" /> : <ChevronDown size={13} className="shrink-0 text-[var(--text-muted)]" />}
                    </button>
                    {expanded.has(i) && (
                      <div className="px-4 pb-3 space-y-1.5 border-t" style={{ borderColor: "var(--border)" }}>
                        <div className="text-[10px] text-[var(--text-muted)] pt-2 leading-relaxed">{v.reasoning}</div>
                        <div className="flex gap-4 text-[10px] text-[var(--text-muted)]">
                          <span>Confidence: <strong>{(v.confidence * 100).toFixed(0)}%</strong></span>
                          {v.entity_id && <span>Entity: <strong>{v.entity_id}</strong></span>}
                          {v.created_at && <span>At: <strong>{new Date(v.created_at).toLocaleString()}</strong></span>}
                        </div>
                        {v.key_evidence_cited && v.key_evidence_cited.length > 0 && (
                          <div className="text-[10px] text-[var(--text-muted)]">
                            Evidence: {v.key_evidence_cited.join(", ")}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
