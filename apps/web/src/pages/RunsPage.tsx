/** RunsPage.tsx — Job history and run management UI. */

import { useState, useEffect } from "react";
import { Clock, Play, CheckCircle, XCircle, AlertTriangle, Loader2, ChevronRight, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ensureApiBase } from "@/lib/api";

interface JobRun {
    job_id: string;
    name: string;
    status: string;
    started_at: string;
    duration_ms: number;
}

function getStatusIcon(status: string) {
    switch (status) {
        case "completed": return <CheckCircle size={14} className="text-green-600" />;
        case "failed": return <XCircle size={14} className="text-red-500" />;
        case "active": return <Loader2 size={14} className="text-[var(--accent)] animate-spin" />;
        default: return <AlertTriangle size={14} className="text-amber-500" />;
    }
}

function getStatusClass(status: string) {
    switch (status) {
        case "completed": return "bg-green-50 text-green-700 border-green-200";
        case "failed": return "bg-red-50 text-red-600 border-red-200";
        case "active": return "bg-[var(--accent-subtle)] text-[var(--accent)] border-[var(--accent)]";
        default: return "bg-amber-50 text-amber-700 border-amber-200";
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
            month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
        });
    } catch { return ts; }
}

export default function RunsPage() {
    const [runs, setRuns] = useState<JobRun[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const fetchRuns = async () => {
        setLoading(true);
        setError(null);
        try {
            const base = await ensureApiBase();
            const res = await fetch(`${base}/jobs/history`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setRuns(data);
        } catch (e: unknown) {
            setError((e as Error).message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchRuns(); }, []);

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
                        onClick={fetchRuns}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm text-secondary hover:bg-[var(--border-light)] transition-colors"
                    >
                        <RefreshCw size={14} /> Refresh
                    </button>
                </div>

                {/* Loading state */}
                {loading && (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 size={24} className="animate-spin text-[var(--accent)]" />
                    </div>
                )}

                {/* Error state */}
                {error && !loading && (
                    <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm">
                        <XCircle size={16} /> Failed to load runs: {error}
                    </div>
                )}

                {/* Empty state */}
                {!loading && !error && runs.length === 0 && (
                    <div className="empty-state">
                        <Play size={40} />
                        <p className="mt-3">No runs yet. Start a trace from the Cockpit to see your history here.</p>
                    </div>
                )}

                {/* Runs table */}
                {!loading && !error && runs.length > 0 && (
                    <div className="bg-surface rounded-xl border border-border overflow-hidden shadow-sm">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b-2 border-border">
                                    <th className="text-left px-4 py-3 text-muted font-semibold text-xs uppercase tracking-wider">Status</th>
                                    <th className="text-left px-4 py-3 text-muted font-semibold text-xs uppercase tracking-wider">Name</th>
                                    <th className="text-left px-4 py-3 text-muted font-semibold text-xs uppercase tracking-wider">Started</th>
                                    <th className="text-left px-4 py-3 text-muted font-semibold text-xs uppercase tracking-wider">Duration</th>
                                    <th className="w-8"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {runs.map((run) => (
                                    <tr
                                        key={run.job_id}
                                        onClick={() => navigate(`/jobs/${run.job_id}`)}
                                        className="border-b border-[var(--border-light)] cursor-pointer hover:bg-[var(--accent-subtle)]/30 transition-colors"
                                    >
                                        <td className="px-4 py-3">
                                            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${getStatusClass(run.status)}`}>
                                                {getStatusIcon(run.status)}
                                                {run.status}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 font-medium text-primary max-w-[300px] truncate">{run.name || run.job_id}</td>
                                        <td className="px-4 py-3 text-muted tabular-nums">{formatTimestamp(run.started_at)}</td>
                                        <td className="px-4 py-3 text-muted tabular-nums">{run.duration_ms ? formatDuration(run.duration_ms) : "—"}</td>
                                        <td className="px-2 py-3 text-muted"><ChevronRight size={14} /></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {/* Summary stats */}
                {!loading && runs.length > 0 && (
                    <div className="mt-6 flex gap-4">
                        <div className="metric-card flex-1">
                            <div className="metric-label">Total</div>
                            <div className="metric-value">{runs.length}</div>
                        </div>
                        <div className="metric-card flex-1">
                            <div className="metric-label">Completed</div>
                            <div className="metric-value text-green-600">{runs.filter(r => r.status === "completed").length}</div>
                        </div>
                        <div className="metric-card flex-1">
                            <div className="metric-label">Failed</div>
                            <div className="metric-value text-red-500">{runs.filter(r => r.status === "failed").length}</div>
                        </div>
                        <div className="metric-card flex-1">
                            <div className="metric-label">Active</div>
                            <div className="metric-value text-[var(--accent)]">{runs.filter(r => r.status === "active").length}</div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
