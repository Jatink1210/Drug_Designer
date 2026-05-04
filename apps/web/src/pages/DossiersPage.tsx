import { useState, useEffect, lazy, Suspense } from "react";
import {
  FileSpreadsheet,
  PlusCircle,
  Download,
  Loader2,
  Trash2,
  Eye,
  ClipboardList,
  FileText,
  Package,
} from "lucide-react";
import { ensureApiBase } from "@/lib/api";
import { useSetPageConfidence } from "@/lib/PageConfidenceContext";
import { useRunProgress } from "@/lib/hooks";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

type DossierMeta = {
  job_id: string;
  title: string;
  created_at: string;
  status: string;
  section_count: number;
  sections: string[];
};

export default function DossiersPage() {
  const [dossiers, setDossiers] = useState<DossierMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const wsProgress = useRunProgress(currentRunId);

  const setConfidence = useSetPageConfidence();
  useEffect(() => {
    if (dossiers.length > 0) {
      setConfidence({ freshness: "current", sourceCount: dossiers.length, sourcesQueried: ["Dossier Engine"] });
    } else {
      setConfidence(null);
    }
    return () => setConfidence(null);
  }, [dossiers, setConfidence]);

  // Clear run tracking on WS completion and refresh list
  useEffect(() => {
    if (wsProgress?.isComplete) {
      setCurrentRunId(null);
      load();
    }
  }, [wsProgress?.isComplete]);

  const load = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const base = await ensureApiBase();
      // Load dossiers from dossier list endpoint
      const dossiersRes = await fetch(`${base}/dossiers`, { cache: "no-store" });
      if (dossiersRes.ok) {
        const envelope: any = await dossiersRes.json();
        const raw = envelope?.data ?? envelope ?? [];
        const items: any[] = Array.isArray(raw) ? raw : (raw?.dossiers ?? []);
        const dList: DossierMeta[] = items.slice(0, 20).map((d: any) => ({
          job_id: d.id || d.dossier_id || d.job_id || "",
          title: d.title || "Untitled",
          created_at: d.created_at || "",
          status: d.status || "draft",
          section_count: d.section_count ?? (d.sections?.length ?? 0),
          sections: d.sections || [],
        }));
        setDossiers(dList);
      } else {
        setFetchError(`Server returned ${dossiersRes.status}`);
      }
    } catch (err: unknown) {
      setFetchError(err instanceof Error ? err.message : "Network error");
    }
    setLoading(false);
  };

  const viewDossier = async (jobId: string) => {
    const base = await ensureApiBase();
    const res = await fetch(`${base}/dossiers/${jobId}?format=json`, { cache: "no-store" });
    if (res.ok) setPreview(await res.json());
  };

  const downloadHTML = async (jobId: string) => {
    const base = await ensureApiBase();
    const res = await fetch(`${base}/dossiers/${jobId}?format=html`, { cache: "no-store" });
    if (res.ok) {
      const html = await res.text();
      const blob = new Blob([html], { type: "text/html" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `dossier_${jobId}.html`;
      a.click();
    }
  };

  const createDossier = async () => {
    if (!createTitle.trim()) return;
    setCreating(true);
    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/dossiers/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: "default",
          title: createTitle.trim(),
          include_sections: ["objective", "evidence_summary", "ranked_options", "contradictions", "recommendations", "provenance"],
        }),
      });
      if (res.ok) {
        const envelope: any = await res.json();
        const runId = envelope?.data?.run_id || envelope?.run_id;
        if (runId) setCurrentRunId(runId);
        setShowCreate(false);
        setCreateTitle("");
        load();
      }
    } catch (err) {
      console.error("Dossier creation failed:", err);
    }
    setCreating(false);
  };

  const deleteDossier = async (jobId: string) => {
    const base = await ensureApiBase();
    try {
      await fetch(`${base}/dossiers/${jobId}`, { method: "DELETE" });
      setDossiers(prev => prev.filter(d => d.job_id !== jobId));
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const viewState: ViewState = loading
    ? "loading"
    : fetchError
      ? "error"
      : preview
        ? "success"
        : dossiers.length === 0
          ? "empty"
          : "success";

  return (
    <div
      className="flex-1 overflow-y-auto"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-[1100px] mx-auto px-6 py-5">
        <div className="mb-6 flex justify-between items-center">
          <div>
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">
              Reports & Export
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Compiled dossiers, generated reports, and data export center.
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="btn-primary px-3 py-1.5 text-xs flex items-center gap-1.5"
          >
            <PlusCircle size={14} /> New Dossier
          </button>
        </div>

        {/* Create dossier dialog */}
        {showCreate && (
          <div className="card p-4 mb-5 border-l-2" style={{ borderColor: "var(--accent)" }}>
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">Generate New Dossier</h3>
            <input
              type="text"
              value={createTitle}
              onChange={(e) => setCreateTitle(e.target.value)}
              placeholder="Dossier title (e.g. BRCA1 Target Assessment)"
              className="w-full px-3 py-2 rounded text-sm mb-3"
              style={{ background: "var(--bg-app)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              onKeyDown={(e) => e.key === "Enter" && createDossier()}
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={createDossier}
                disabled={creating || !createTitle.trim()}
                className="btn-primary px-3 py-1.5 text-xs flex items-center gap-1"
              >
                {creating ? <Loader2 size={12} className="animate-spin" /> : <FileSpreadsheet size={12} />}
                Generate
              </button>
              <button
                onClick={() => { setShowCreate(false); setCreateTitle(""); }}
                className="px-3 py-1.5 text-xs border rounded"
                style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <StateWrapper
          state={viewState}
          moduleName="Decision Dossiers"
          emptyTitle="Dossier Repository Empty"
          emptyDescription="Run an Evidence Search or Disease Intelligence workflow to auto-generate dossiers from completed jobs."
          errorInfo={fetchError ? { code: "LOAD_FAILED", message: fetchError, recoverable: true } : undefined}
          onRetry={load}
        >

        {wsProgress && !wsProgress.isComplete && (
          <div className="flex items-center gap-3 px-4 py-2 rounded-lg text-xs mb-4" style={{ background: "var(--bg-surface)" }}>
            <div className="w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
            <span className="font-medium" style={{ color: "var(--accent)" }}>{wsProgress.stage || "Generating dossier…"}</span>
            <div className="flex-1 h-1.5 rounded-full bg-[var(--bg-inset)] overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${wsProgress.progressPercent}%`, background: "var(--accent)" }} />
            </div>
            <span style={{ color: "var(--text-muted)" }}>{wsProgress.progressPercent}%</span>
            {wsProgress.sourcesTotal > 0 && (
              <span style={{ color: "var(--text-muted)" }}>{wsProgress.sourcesCompleted}/{wsProgress.sourcesTotal} sources</span>
            )}
          </div>
        )}

        {!preview && dossiers.length > 0 && (
          <div className="space-y-3">
            {dossiers.map((d) => (
              <div
                key={d.job_id}
                className="card p-4 flex items-center justify-between group hover:border-[var(--accent)] transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">
                    {d.title}
                  </h3>
                  <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                    Job: {d.job_id} • {d.section_count} section{d.section_count !== 1 ? "s" : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${d.status === "finalized" ? "bg-green-100 text-green-700" : d.status === "review" ? "bg-amber-100 text-amber-700" : "bg-[var(--bg-inset)] text-[var(--text-secondary)]"}`}>
                    {d.status?.toUpperCase() || "DRAFT"}
                  </span>
                  <button
                    onClick={() => viewDossier(d.job_id)}
                    className="glass-button text-xs px-3 py-1 flex items-center gap-1"
                  >
                    <Eye size={12} /> View
                  </button>
                  <button
                    onClick={() => downloadHTML(d.job_id)}
                    className="glass-button text-xs px-3 py-1 flex items-center gap-1"
                  >
                    <Download size={12} /> HTML
                  </button>
                  <button
                    onClick={() => { if (confirm(`Delete dossier "${d.title}"?`)) deleteDossier(d.job_id); }}
                    className="glass-button text-xs px-2 py-1 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ color: "#ef4444" }}
                    title="Delete dossier"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {preview && (() => {
          const d = preview?.data ?? preview;
          const rankings: any[] = d?.ranked_options ?? d?.ranking_table ?? [];
          const recs: string[] = d?.recommendations ?? [];
          const assumptions: string[] = d?.assumptions_and_overrides ?? [];
          const contradictions: any[] = d?.contradictions ?? [];
          const evidence: any[] = d?.evidence ?? d?.evidence_summary ?? [];
          const footprint: any[] = d?.source_footprint ?? d?.provenance?.source_footprint ?? [];
          const maxScore = rankings.length > 0 ? Math.max(...rankings.map((r: any) => r.score || 0), 0.01) : 1;

          const handlePrint = () => {
            window.print();
          };

          return (
          <div className="space-y-5 print:space-y-3" id="dossier-report">
            {/* Hero Header */}
            <div className="rounded-xl overflow-hidden" style={{ background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%)" }}>
              <div className="p-6 text-white">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-[10px] uppercase tracking-widest opacity-70 mb-1">Drug Discovery Decision Dossier</div>
                    <h2 className="text-xl font-bold mb-2">{d?.title || "Decision Dossier"}</h2>
                    <p className="text-sm opacity-80 max-w-2xl">{d?.objective_text || d?.objective || ""}</p>
                  </div>
                  <div className="flex gap-2 print:hidden">
                    <button onClick={handlePrint} className="px-3 py-1.5 text-xs rounded bg-white/20 hover:bg-white/30 flex items-center gap-1 backdrop-blur-sm">
                      <FileText size={12} /> Print / PDF
                    </button>
                    <button onClick={() => setPreview(null)} className="px-3 py-1.5 text-xs rounded bg-white/20 hover:bg-white/30">
                      ← Back
                    </button>
                  </div>
                </div>
                <div className="flex gap-6 mt-4 text-[10px] opacity-70">
                  <span>Project: <strong className="opacity-100">{d?.project_id || "—"}</strong></span>
                  <span>Generated: <strong className="opacity-100">{d?.generated_at ? new Date(d.generated_at.replace("Z+00:00Z","Z").replace("+00:00Z","Z")).toLocaleString() : "—"}</strong></span>
                  <span>Version: <strong className="opacity-100">{d?.schema_version || "—"}</strong></span>
                </div>
              </div>
              {/* Key metrics strip */}
              <div className="grid grid-cols-4 bg-white/10 backdrop-blur-sm">
                {[
                  { label: "Targets Ranked", value: rankings.length },
                  { label: "Evidence Items", value: evidence.length },
                  { label: "Contradictions", value: contradictions.length },
                  { label: "Sources", value: footprint.length },
                ].map((m) => (
                  <div key={m.label} className="px-4 py-2.5 text-center border-r border-white/10 last:border-r-0">
                    <div className="text-xl font-bold text-white">{m.value}</div>
                    <div className="text-[9px] text-white/60 uppercase">{m.label}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Disease Summary */}
            {d?.disease_summary && (
              <div className="card p-5 rounded-xl">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2 flex items-center gap-2">
                  <div className="w-5 h-5 rounded bg-blue-100 flex items-center justify-center"><ClipboardList size={12} className="text-blue-600" /></div>
                  Disease Summary
                </h3>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{d.disease_summary}</p>
              </div>
            )}

            {/* Ranked Targets — visual cards */}
            {rankings.length > 0 && (
              <div className="card p-5 rounded-xl">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
                  <div className="w-5 h-5 rounded bg-indigo-100 flex items-center justify-center"><Package size={12} className="text-indigo-600" /></div>
                  Ranked Targets
                </h3>
                <div className="space-y-2.5">
                  {rankings.map((r: any, i: number) => {
                    const pct = maxScore > 0 ? ((r.score || 0) / maxScore) * 100 : 0;
                    const rank = r.rank || i + 1;
                    return (
                      <div key={i} className="rounded-lg border p-3 hover:shadow-sm transition-shadow" style={{ borderColor: "var(--border)" }}>
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm ${rank <= 3 ? "bg-gradient-to-br from-indigo-500 to-purple-600 text-white" : "bg-[var(--bg-inset)] text-[var(--text-muted)]"}`}>
                            {rank}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm font-semibold text-[var(--text-primary)]">{r.target}</span>
                              <div className="flex items-center gap-3">
                                <span className="text-xs font-mono font-bold text-[var(--accent)]">{r.score?.toFixed(3)}</span>
                                {r.ucb_score != null && (
                                  <span className="text-[10px] text-green-600 font-mono">UCB: {r.ucb_score.toFixed(3)}</span>
                                )}
                                {r.uncertainty != null && (
                                  <span className={`text-[10px] font-mono ${r.uncertainty > 0.3 ? "text-red-500" : r.uncertainty > 0.15 ? "text-amber-500" : "text-green-500"}`}>
                                    ±{r.uncertainty.toFixed(3)}
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className="w-full h-2 bg-[var(--bg-inset)] rounded-full overflow-hidden">
                              <div
                                className="h-full rounded-full transition-all duration-500"
                                style={{
                                  width: `${pct}%`,
                                  background: rank <= 3 ? "linear-gradient(90deg, #6366f1, #8b5cf6)" : "#94a3b8",
                                }}
                              />
                            </div>
                            {r.note && <p className="text-[10px] text-[var(--text-muted)] mt-1">{r.note}</p>}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Evidence */}
            {evidence.length > 0 && (
              <div className="card p-5 rounded-xl">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
                  <div className="w-5 h-5 rounded bg-emerald-100 flex items-center justify-center"><FileText size={12} className="text-emerald-600" /></div>
                  Evidence Summary ({evidence.length})
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {evidence.map((e: any, i: number) => (
                    <div key={i} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                      <div className="flex items-start gap-2">
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600 font-medium shrink-0">{i + 1}</span>
                        <div>
                          <span className="text-xs font-medium text-[var(--text-primary)]">{e.source || e.title || `Evidence ${i + 1}`}</span>
                          {e.summary && <p className="text-[10px] text-[var(--text-muted)] mt-0.5 leading-relaxed">{e.summary}</p>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Contradictions */}
            {contradictions.length > 0 && (
              <div className="card p-5 rounded-xl border-l-4 border-amber-400">
                <h3 className="text-sm font-semibold text-amber-600 mb-3 flex items-center gap-2">
                  ⚠ Contradictions ({contradictions.length})
                </h3>
                <div className="space-y-2">
                  {contradictions.map((c: any, i: number) => (
                    <div key={i} className="flex items-start gap-2 p-2 rounded bg-amber-50/50">
                      <span className="text-amber-500 text-xs">▸</span>
                      <p className="text-xs text-[var(--text-secondary)]">{typeof c === "string" ? c : c.description || c.title || JSON.stringify(c)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {recs.length > 0 && (
              <div className="card p-5 rounded-xl border-l-4 border-green-400">
                <h3 className="text-sm font-semibold text-green-700 mb-3">✓ Recommendations</h3>
                <ol className="space-y-2">
                  {recs.map((r, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-green-100 text-green-700 text-[10px] font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                      <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{r}</p>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Assumptions */}
            {assumptions.length > 0 && (
              <div className="card p-5 rounded-xl">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">Assumptions & Overrides</h3>
                <ul className="space-y-1">
                  {assumptions.map((a, i) => (
                    <li key={i} className="text-xs text-[var(--text-muted)] flex items-start gap-1.5">
                      <span className="text-slate-400 mt-0.5">—</span> {a}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Provenance footer */}
            <div className="card p-4 rounded-xl text-[10px] text-[var(--text-muted)] flex items-center justify-between">
              <div className="flex gap-6">
                <span>Runs: <strong>{d?.provenance?.run_count ?? "—"}</strong></span>
                <span>Sources: <strong>{footprint.length > 0 ? footprint.join(", ") : "None recorded"}</strong></span>
              </div>
              <div className="flex gap-2 print:hidden">
                <button onClick={() => downloadHTML(d?.job_id || d?.id || "")} className="px-3 py-1 text-xs rounded border flex items-center gap-1 hover:bg-[var(--bg-surface)]" style={{ borderColor: "var(--border)" }}>
                  <Download size={11} /> Download HTML
                </button>
                <button onClick={handlePrint} className="px-3 py-1 text-xs rounded border flex items-center gap-1 hover:bg-[var(--bg-surface)]" style={{ borderColor: "var(--border)" }}>
                  <FileText size={11} /> Print / PDF
                </button>
              </div>
            </div>

            {/* B-8: MAV Consensus Trace section */}
            {(() => {
              const trace = preview?.provenance?.runtime_context?.consensus
                ?? d?.mav_consensus_trace ?? null;
              if (!trace || trace.vote_count === 0) return null;
              const verdictColor: Record<string, string> = {
                verified: "text-green-600",
                contradicted: "text-red-500",
                conflict: "text-amber-500",
                uncertain: "text-slate-500",
              };
              return (
                <div className="card p-5 rounded-xl border-l-4 border-violet-400">
                  <h3 className="text-sm font-semibold text-violet-700 mb-3 flex items-center gap-2">
                    ⚖ MAV Consensus Trace
                    <span className={`text-xs font-mono font-bold ${verdictColor[trace.verdict] ?? "text-slate-600"}`}>
                      {trace.verdict?.toUpperCase()}
                    </span>
                    {trace.consensus_met && (
                      <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">CONSENSUS MET</span>
                    )}
                  </h3>
                  <div className="grid grid-cols-3 gap-3 mb-4 text-[11px]">
                    <div className="rounded-lg bg-violet-50 p-3 text-center">
                      <div className="text-xl font-bold text-violet-700">{trace.vote_count}</div>
                      <div className="text-[9px] uppercase text-violet-400">Total Votes</div>
                    </div>
                    <div className="rounded-lg bg-violet-50 p-3 text-center">
                      <div className="text-xl font-bold text-violet-700">{(trace.mean_score * 100).toFixed(0)}%</div>
                      <div className="text-[9px] uppercase text-violet-400">Mean Score</div>
                    </div>
                    <div className="rounded-lg bg-violet-50 p-3 text-center">
                      <div className="text-xl font-bold text-violet-700">{(trace.mean_confidence * 100).toFixed(0)}%</div>
                      <div className="text-[9px] uppercase text-violet-400">Mean Confidence</div>
                    </div>
                  </div>
                  {trace.full_trace?.length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-1">Individual Votes</div>
                      {trace.full_trace.map((v: any, i: number) => (
                        <div key={i} className="rounded-lg border p-2.5 flex items-start gap-2.5 text-xs" style={{ borderColor: "var(--border)" }}>
                          <div className="w-7 h-7 rounded-full bg-violet-100 flex items-center justify-center text-[10px] font-bold text-violet-700 shrink-0">
                            {v.specialist_role?.[0]?.toUpperCase() ?? "?"}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-0.5">
                              <span className="font-medium text-[var(--text-primary)]">{v.specialist_role}</span>
                              <span className={`font-mono text-[10px] font-bold ${verdictColor[v.verdict] ?? "text-slate-500"}`}>
                                {v.verdict} · {(v.score * 100).toFixed(0)}%
                              </span>
                            </div>
                            {v.reasoning && <p className="text-[10px] text-[var(--text-muted)] line-clamp-2">{v.reasoning}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {trace.minority_dissent?.length > 0 && (
                    <div className="mt-2 text-[10px] text-amber-600 flex items-center gap-1">
                      ⚠ {trace.minority_dissent.length} dissenting vote{trace.minority_dissent.length > 1 ? "s" : ""}
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
          );
        })()}
        </StateWrapper>
      </div>
    </div>
  );
}
