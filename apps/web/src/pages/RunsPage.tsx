/** RunsPage.tsx — Job history and run management UI. */

import { useState, useEffect } from "react";
import {
  Clock,
  Play,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  ChevronRight,
  RefreshCw,
  StopCircle,
  RotateCw,
  Filter,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useRunProgress, useJobsHistory } from "@/lib/hooks";
import { runCancelAPI, runRetryAPI } from "@/lib/api";
import RunProgressTracker from "@/components/ui/RunProgressTracker";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

interface JobRun {
  job_id: string;
  name: string;
  status: string;
  started_at: string;
  duration_ms: number;
}

function getStatusIcon(status: string) {
  switch (status) {
    case "completed":
      return <CheckCircle size={14} className="text-green-600" />;
    case "failed":
      return <XCircle size={14} className="text-red-500" />;
    case "active":
      return (
        <Loader2 size={14} className="text-[var(--accent)] animate-spin" />
      );
    default:
      return <AlertTriangle size={14} className="text-amber-500" />;
  }
}

function getStatusClass(status: string) {
  switch (status) {
    case "completed":
      return "bg-green-50 text-green-700 border-green-200";
    case "failed":
      return "bg-red-50 text-red-600 border-red-200";
    case "active":
      return "bg-[var(--accent-subtle)] text-[var(--accent)] border-[var(--accent)]";
    default:
      return "bg-amber-50 text-amber-700 border-amber-200";
  }
}

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

function formatTimestamp(ts: string) {
  try {
    const d = new Date(ts);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

export default function RunsPage() {
  const { data, state, error, refetch } = useJobsHistory();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [actionError, setActionError] = useState<string | null>(null);
  // Map API run fields to JobRun interface
  const runs: JobRun[] = (Array.isArray(data) ? data : []).map((r: any) => ({
    job_id: r.job_id ?? r.run_id ?? r.id ?? "",
    name: r.name ?? r.run_type ?? r.module_name ?? "Run",
    status: r.status ?? (r.state?.toLowerCase() === "partial_success" ? "completed" : r.state?.toLowerCase()) ?? "unknown",
    started_at: r.started_at ?? r.created_at ?? "",
    duration_ms: r.duration_ms ?? r.timing?.total_ms ?? 0,
  }));

  // Auto-refresh every 10s when there are active runs
  const hasActive = runs.some(r => r.status === "active");
  useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(() => refetch(), 10_000);
    return () => clearInterval(timer);
  }, [hasActive, refetch]);

  const filteredRuns = statusFilter === "all" ? runs : runs.filter(r => r.status === statusFilter);
  const navigate = useNavigate();
  const { runId } = useParams<{ runId?: string }>();

  // §57: Real-time WebSocket progress for the selected run
  const activeRunId = runId || runs.find((r) => r.status === "active")?.job_id || null;
  const progress = useRunProgress(activeRunId);

  const handleCancel = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setActionError(null);
    try {
      await runCancelAPI(jobId);
      refetch();
    } catch (err: unknown) {
      setActionError(`Cancel failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
  };

  const handleRetry = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setActionError(null);
    try {
      await runRetryAPI(jobId);
      refetch();
    } catch (err: unknown) {
      setActionError(`Retry failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
  };

  const viewState: ViewState = state === "loading"
    ? "loading"
    : error
      ? "error"
      : runs.length === 0
        ? "empty"
        : "success";

  return (
    <div className="flex-1 overflow-y-auto bg-app p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-primary flex items-center gap-2">
              <Clock size={22} /> Runs History
            </h1>
            <p className="text-sm text-muted mt-1">
              Past reasoning traces, experiments, and job runs.
            </p>
          </div>
          <button
            onClick={refetch}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm text-secondary hover:bg-[var(--border-light)] transition-colors"
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {/* Status filter bar */}
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <Filter size={12} className="text-[var(--text-muted)]" />
          {["all", "active", "completed", "failed"].map(f => (
            <button
              key={f}
              onClick={() => setStatusFilter(f)}
              className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider rounded-full border transition-colors"
              style={{
                borderColor: statusFilter === f ? "var(--accent)" : "var(--border)",
                background: statusFilter === f ? "var(--accent-subtle)" : "transparent",
                color: statusFilter === f ? "var(--accent)" : "var(--text-muted)",
              }}
            >
              {f} {f !== "all" ? `(${runs.filter(r => r.status === f).length})` : `(${runs.length})`}
            </button>
          ))}
          {hasActive && (
            <span className="ml-auto text-[10px] text-[var(--text-muted)] flex items-center gap-1">
              <Loader2 size={10} className="animate-spin" /> Auto-refreshing
            </span>
          )}
        </div>

        {/* Action error toast */}
        {actionError && (
          <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 text-red-700 text-xs flex items-center gap-2">
            <AlertTriangle size={12} /> {actionError}
            <button onClick={() => setActionError(null)} className="ml-auto text-red-500 hover:text-red-700">×</button>
          </div>
        )}

        {/* §57 Real-time progress for active run */}
        {progress && (
          <div className="mb-6">
            <RunProgressTracker
              progress={{
                runId: progress.runId,
                runType: "Run",
                state: progress.state,
                stage: progress.stage,
                progressPercent: progress.progressPercent,
                message: progress.message,
                sourcesCompleted: progress.sourcesCompleted,
                sourcesTotal: progress.sourcesTotal,
                elapsedMs: progress.elapsedMs,
                degradedSources: progress.degradedSources,
                error: progress.error,
              }}
              onInspect={(id) => navigate(`/jobs/${id}`)}
            />
          </div>
        )}

        <StateWrapper
          state={viewState}
          moduleName="Runs History"
          emptyTitle="No runs yet"
          emptyDescription="Start a trace from the Cockpit to see your history here."
          errorInfo={error ? { code: "LOAD_FAILED", message: error, recoverable: true } : undefined}
          onRetry={refetch}
        >
        {/* Runs table */}
        {filteredRuns.length > 0 && (
          <div className="bg-surface rounded-xl border border-border overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b-2 border-border">
                  <th className="text-left px-4 py-3 text-muted font-semibold text-xs uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-left px-4 py-3 text-muted font-semibold text-xs uppercase tracking-wider">
                    Name
                  </th>
                  <th className="text-left px-4 py-3 text-muted font-semibold text-xs uppercase tracking-wider">
                    Started
                  </th>
                  <th className="text-left px-4 py-3 text-muted font-semibold text-xs uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="text-left px-4 py-3 text-muted font-semibold text-xs uppercase tracking-wider">
                    Actions
                  </th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody>
                {filteredRuns.map((run) => (
                  <tr
                    key={run.job_id}
                    onClick={() => navigate(`/jobs/${run.job_id}`)}
                    className="border-b border-[var(--border-light)] cursor-pointer hover:bg-[var(--accent-subtle)]/30 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${getStatusClass(run.status)}`}
                      >
                        {getStatusIcon(run.status)}
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-medium text-primary max-w-[300px] truncate">
                      {run.name || run.job_id}
                    </td>
                    <td className="px-4 py-3 text-muted tabular-nums">
                      {formatTimestamp(run.started_at)}
                    </td>
                    <td className="px-4 py-3 text-muted tabular-nums">
                      {run.duration_ms ? formatDuration(run.duration_ms) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        {run.status === "active" && (
                          <button
                            onClick={(e) => handleCancel(run.job_id, e)}
                            className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
                            title="Cancel run"
                          >
                            <StopCircle size={10} /> Cancel
                          </button>
                        )}
                        {run.status === "failed" && (
                          <button
                            onClick={(e) => handleRetry(run.job_id, e)}
                            className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-600 hover:bg-amber-100 transition-colors"
                            title="Retry run"
                          >
                            <RotateCw size={10} /> Retry
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-3 text-muted">
                      <ChevronRight size={14} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Summary stats */}
        {runs.length > 0 && (
          <div className="mt-6 flex gap-4">
            <div className="metric-card flex-1">
              <div className="metric-label">Total</div>
              <div className="metric-value">{runs.length}</div>
            </div>
            <div className="metric-card flex-1">
              <div className="metric-label">Completed</div>
              <div className="metric-value text-green-600">
                {runs.filter((r) => r.status === "completed").length}
              </div>
            </div>
            <div className="metric-card flex-1">
              <div className="metric-label">Failed</div>
              <div className="metric-value text-red-500">
                {runs.filter((r) => r.status === "failed").length}
              </div>
            </div>
            <div className="metric-card flex-1">
              <div className="metric-label">Active</div>
              <div className="metric-value text-[var(--accent)]">
                {runs.filter((r) => r.status === "active").length}
              </div>
            </div>
          </div>
        )}
        </StateWrapper>
      </div>
    </div>
  );
}
