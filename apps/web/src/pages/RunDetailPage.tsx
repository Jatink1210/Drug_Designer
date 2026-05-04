/** RunDetailPage — Run detail view (§20, §77 /runs/:runId). */

import { useState, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Activity, Clock, CheckCircle, XCircle, AlertTriangle, Loader2 } from "lucide-react";
import { ensureApiBase } from "@/lib/api";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

interface RunDetail {
  id: string;
  run_type: string;
  state: string;
  project_id: string;
  progress_pct: number;
  created_at: string;
  updated_at: string;
  runtime_context: { mode: string; selected_runtime: string; selected_model: string; fallback_used: boolean };
  logs: string[];
  artifacts: string[];
  provenance: Record<string, unknown>;
}

const STATE_ICON: Record<string, typeof CheckCircle> = {
  SUCCESS: CheckCircle,
  FAILED: XCircle,
  PARTIAL_SUCCESS: AlertTriangle,
  RUNNING: Loader2,
};
const STATE_COLOR: Record<string, string> = {
  SUCCESS: "text-green-500",
  FAILED: "text-red-500",
  PARTIAL_SUCCESS: "text-yellow-500",
  RUNNING: "text-blue-500",
  CREATED: "text-gray-400",
  QUEUED: "text-gray-400",
  CANCELLED: "text-gray-400",
};

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId) return;
    (async () => {
      setViewState("loading");
      try {
        const base = await ensureApiBase();
        const res = await fetch(`${base}/runs/${runId}`);
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        const envelope = await res.json();
        const data = envelope.data ?? envelope;
        setRun(data);
        setViewState("success");

        // WebSocket for live updates if run is active
        if (["CREATED", "QUEUED", "RUNNING"].includes(data.state)) {
          const wsBase = base.replace(/^http/, "ws");
          const ws = new WebSocket(`${wsBase.replace("/api/v1", "")}/ws/runs/${runId}`);
          ws.onmessage = (evt) => {
            try {
              const event = JSON.parse(evt.data);
              if (event.event === "run.progress") {
                setRun((prev) => prev ? { ...prev, progress_pct: event.payload.progress_pct, state: "RUNNING" } : prev);
              } else if (event.event === "run.completed") {
                setRun((prev) => prev ? { ...prev, state: event.payload.state || "SUCCESS" } : prev);
              } else if (event.event === "run.failed") {
                setRun((prev) => prev ? { ...prev, state: "FAILED" } : prev);
              }
            } catch { /* ignore parse errors */ }
          };
          wsRef.current = ws;
        }
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : "Failed to load run");
        setViewState("error");
      }
    })();
    return () => { wsRef.current?.close(); };
  }, [runId]);

  const Icon = run ? (STATE_ICON[run.state] || Activity) : Activity;
  const color = run ? (STATE_COLOR[run.state] || "text-gray-400") : "text-gray-400";

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <Link to="/runs" className="inline-flex items-center gap-1 text-sm hover:underline" style={{ color: "var(--accent)" }}>
        <ArrowLeft size={14} /> Back to Runs
      </Link>

      <StateWrapper
        state={viewState}
        moduleName="Run Detail"
        emptyTitle="Run not found"
        emptyDescription="The requested run could not be located."
        errorInfo={{ code: "RUN_LOAD_ERROR", message: errorMsg, recoverable: true }}
        onRetry={() => window.location.reload()}
      >
        {run && (
          <>
            <header className="flex items-center gap-3">
              <Icon size={28} className={color} />
              <div>
                <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{run.run_type}</h1>
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>Run ID: {run.id}</p>
              </div>
              <span className={`ml-auto px-3 py-1 rounded-lg text-sm font-medium ${color}`} style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                {run.state}
              </span>
            </header>

            {run.state === "RUNNING" && (
              <div className="w-full rounded-full h-2" style={{ background: "var(--bg-surface)" }}>
                <div
                  className="h-2 rounded-full transition-all"
                  style={{ width: `${run.progress_pct}%`, background: "var(--accent)" }}
                />
              </div>
            )}

            <div className="grid grid-cols-3 gap-4 text-sm">
              <div className="rounded-lg p-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                <Clock size={14} className="inline mr-1" style={{ color: "var(--text-muted)" }} />
                Started: {new Date(run.created_at).toLocaleString()}
              </div>
              <div className="rounded-lg p-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                <Activity size={14} className="inline mr-1" style={{ color: "var(--accent)" }} />
                Runtime: {run.runtime_context?.mode ?? "hosted"}
              </div>
              <div className="rounded-lg p-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                Model: {run.runtime_context?.selected_model ?? "default"}
                {run.runtime_context?.fallback_used && (
                  <span className="ml-1 text-xs" style={{ color: "var(--warning)" }}>(fallback)</span>
                )}
              </div>
            </div>

            {/* Provenance */}
            {run.provenance && Object.keys(run.provenance).length > 0 && (
              <section>
                <h2 className="text-lg font-semibold mb-2">Provenance</h2>
                <pre className="rounded-lg p-3 text-xs overflow-auto max-h-48 font-mono" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                  {JSON.stringify(run.provenance, null, 2)}
                </pre>
              </section>
            )}

            {/* Artifacts */}
            <section>
              <h2 className="text-lg font-semibold mb-2">Artifacts ({run.artifacts?.length ?? 0})</h2>
              {(run.artifacts?.length ?? 0) === 0 ? (
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>No artifacts generated yet.</p>
              ) : (
                <ul className="space-y-1">
                  {run.artifacts.map((a, i) => (
                    <li key={i} className="rounded-lg p-2 text-sm" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>{a}</li>
                  ))}
                </ul>
              )}
            </section>

            {/* Logs */}
            <section>
              <h2 className="text-lg font-semibold mb-2">Run Logs</h2>
              <div className="rounded-lg p-3 max-h-64 overflow-auto font-mono text-xs" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                {(run.logs?.length ?? 0) === 0 ? (
                  <p style={{ color: "var(--text-muted)" }}>No log entries.</p>
                ) : (
                  run.logs.map((l, i) => <div key={i} style={{ color: "var(--text-secondary)" }}>{l}</div>)
                )}
              </div>
            </section>
          </>
        )}
      </StateWrapper>
    </div>
    </div>
  );
}
