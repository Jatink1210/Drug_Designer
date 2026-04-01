import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    Terminal,
    CheckCircle2,
    Download,
    XCircle,
    Search,
    Filter,
    FileJson,
    AlertTriangle,
    Info,
    Clock,
} from "lucide-react";
import { ensureApiBase } from "@/lib/api";

interface LogEntry {
    level: string;
    event: string;
    ts: string;
    name?: string;
    status?: string;
    duration_ms?: number;
    step_num?: number;
    details?: Record<string, unknown>;
    [key: string]: unknown;
}

interface Job {
    job_id: string;
    name: string;
    status: string;
    duration_ms: number;
    started_at: string;
}

function levelIcon(level: string) {
    if (level === "error") return <XCircle size={14} className="text-red-500" />;
    if (level === "warning") return <AlertTriangle size={14} className="text-amber-500" />;
    return <Info size={14} className="text-sky-500" />;
}

function statusBadge(status: string) {
    const map: Record<string, string> = {
        completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
        failed: "bg-red-50 text-red-700 border-red-200",
        active: "bg-blue-50 text-blue-700 border-blue-200",
        warning: "bg-amber-50 text-amber-700 border-amber-200",
    };
    return map[status] || "bg-gray-50 text-gray-700 border-gray-200";
}

export default function LogsPage() {
    const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
    const [searchText, setSearchText] = useState("");
    const [toolFilter, setToolFilter] = useState("");
    const [activeTab, setActiveTab] = useState<"logs" | "trace" | "recipe">("logs");

    // ── Queries ──────────────────────────────────────────────
    const { data: jobs, isLoading: isJobsLoading } = useQuery<Job[]>({
        queryKey: ["log-jobs"],
        queryFn: async () => {
            const base = await ensureApiBase();
            const res = await fetch(`${base}/logs/jobs`);
            if (!res.ok) throw new Error("Failed to fetch jobs");
            return res.json();
        },
    });

    const activeJobId = selectedJobId || (jobs && jobs.length > 0 ? jobs[0].job_id : null);

    const { data: logsData, isLoading: isLogsLoading } = useQuery({
        queryKey: ["job-logs", activeJobId, searchText, toolFilter],
        queryFn: async () => {
            if (!activeJobId) return null;
            const base = await ensureApiBase();
            const params = new URLSearchParams({ limit: "500" });
            if (searchText) params.set("search", searchText);
            if (toolFilter) params.set("tool", toolFilter);
            const res = await fetch(`${base}/logs/job/${activeJobId}/logs?${params}`);
            if (!res.ok) return null;
            return res.json();
        },
        enabled: !!activeJobId && activeTab === "logs",
    });

    const { data: trace, isLoading: isTraceLoading } = useQuery({
        queryKey: ["log-trace", activeJobId],
        queryFn: async () => {
            if (!activeJobId) return null;
            const base = await ensureApiBase();
            const res = await fetch(`${base}/logs/job/${activeJobId}`);
            if (!res.ok) return null;
            return res.json();
        },
        enabled: !!activeJobId && activeTab === "trace",
    });

    const { data: recipe } = useQuery({
        queryKey: ["job-recipe", activeJobId],
        queryFn: async () => {
            if (!activeJobId) return null;
            const base = await ensureApiBase();
            const res = await fetch(`${base}/logs/job/${activeJobId}/recipe`);
            if (!res.ok) return null;
            return res.json();
        },
        enabled: !!activeJobId && activeTab === "recipe",
    });

    // ── Derived: unique tool names for the filter dropdown ───
    const toolNames = useMemo(() => {
        const entries: LogEntry[] = logsData?.entries ?? [];
        const names = new Set<string>();
        for (const e of entries) {
            const tn = (e.details as Record<string, unknown> | undefined)?.tool_name;
            if (typeof tn === "string" && tn) names.add(tn);
        }
        return Array.from(names).sort();
    }, [logsData]);

    // ── Helpers ──────────────────────────────────────────────
    function downloadRecipe() {
        if (!recipe) return;
        const blob = new Blob([JSON.stringify(recipe, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `recipe_${activeJobId}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    function downloadLogs() {
        if (!logsData?.entries?.length) return;
        const lines = logsData.entries.map((e: LogEntry) => JSON.stringify(e)).join("\n");
        const blob = new Blob([lines], { type: "application/x-ndjson" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `logs_${activeJobId}.jsonl`;
        a.click();
        URL.revokeObjectURL(url);
    }

    // ── Render ───────────────────────────────────────────────
    return (
        <div className="flex-1 flex h-full bg-[var(--bg-app)] overflow-hidden">
            {/* ──── Left sidebar: Job list ──── */}
            <div className="w-72 border-r border-[var(--border)] bg-[var(--bg-surface)] flex flex-col shrink-0">
                <div className="h-14 border-b border-[var(--border)] flex items-center px-4 shrink-0 justify-between">
                    <h2 className="font-semibold text-[var(--text-primary)]">Execution Logs</h2>
                    <span className="text-xs bg-[var(--border-light)] text-[var(--text-secondary)] px-2 py-1 rounded border border-[var(--border)] font-mono">
                        {jobs?.length ?? 0} jobs
                    </span>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2">
                    {isJobsLoading ? (
                        <div className="text-sm text-[var(--text-muted)] p-2">Loading jobs...</div>
                    ) : (
                        jobs?.map((job) => {
                            const isActive = job.job_id === activeJobId;
                            return (
                                <button
                                    key={job.job_id}
                                    onClick={() => { setSelectedJobId(job.job_id); setActiveTab("logs"); }}
                                    className={`w-full text-left p-3 rounded-lg border transition-colors ${
                                        isActive
                                            ? "bg-[var(--accent-subtle)] border-transparent text-[var(--accent)]"
                                            : "bg-transparent border-[var(--border-light)] hover:bg-[var(--border-light)] text-[var(--text-secondary)]"
                                    }`}
                                >
                                    <div className="flex justify-between items-center mb-1 line-clamp-1">
                                        <span className="font-semibold text-sm text-[var(--text-primary)]">
                                            {job.name || "Untitled Job"}
                                        </span>
                                    </div>
                                    <div className="flex justify-between items-center text-xs text-[var(--text-muted)]">
                                        <span className="font-mono">{job.job_id}</span>
                                        <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold border ${statusBadge(job.status)}`}>
                                            {job.status}
                                        </span>
                                    </div>
                                    {job.duration_ms > 0 && (
                                        <div className="flex items-center gap-1 text-[10px] text-[var(--text-muted)] mt-1">
                                            <Clock size={10} />
                                            {(job.duration_ms / 1000).toFixed(1)}s
                                        </div>
                                    )}
                                </button>
                            );
                        })
                    )}
                </div>
            </div>

            {/* ──── Main area ──── */}
            <div className="flex-1 flex flex-col bg-[var(--bg-app)]">
                {/* Header + tabs */}
                <div className="shrink-0 border-b border-[var(--border)] bg-[var(--bg-surface)]">
                    <div className="h-14 flex items-center px-6 justify-between">
                        <div className="flex items-center gap-3">
                            <Terminal size={18} className="text-[var(--text-secondary)]" />
                            <h1 className="text-lg font-semibold text-[var(--text-primary)]">
                                <span className="font-mono text-[var(--text-secondary)]">{activeJobId || "—"}</span>
                            </h1>
                        </div>
                        <div className="flex items-center gap-2">
                            {activeTab === "logs" && (
                                <button
                                    onClick={downloadLogs}
                                    className="flex items-center gap-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--border-light)] px-3 py-1.5 rounded-md text-sm font-medium transition-colors border border-transparent hover:border-[var(--border)]"
                                >
                                    <Download size={14} /> JSONL
                                </button>
                            )}
                            <button
                                onClick={downloadRecipe}
                                className="flex items-center gap-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--border-light)] px-3 py-1.5 rounded-md text-sm font-medium transition-colors border border-transparent hover:border-[var(--border)]"
                            >
                                <FileJson size={14} /> Recipe
                            </button>
                        </div>
                    </div>
                    {/* Tab bar */}
                    <div className="flex gap-0 px-6">
                        {(["logs", "trace", "recipe"] as const).map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`px-4 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
                                    activeTab === tab
                                        ? "border-[var(--accent)] text-[var(--accent)]"
                                        : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                                }`}
                            >
                                {tab}
                            </button>
                        ))}
                    </div>
                </div>

                {/* ── Tab: Logs ──────────────────────────────── */}
                {activeTab === "logs" && (
                    <div className="flex-1 flex flex-col overflow-hidden">
                        {/* Search + filter bar */}
                        <div className="shrink-0 flex items-center gap-3 px-6 py-3 border-b border-[var(--border-light)] bg-[var(--bg-surface)]">
                            <div className="flex items-center gap-2 flex-1 bg-[var(--bg-app)] border border-[var(--border)] rounded-md px-3 py-1.5">
                                <Search size={14} className="text-[var(--text-muted)]" />
                                <input
                                    type="text"
                                    placeholder="Search logs..."
                                    value={searchText}
                                    onChange={(e) => setSearchText(e.target.value)}
                                    className="flex-1 bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
                                />
                            </div>
                            <div className="flex items-center gap-2 bg-[var(--bg-app)] border border-[var(--border)] rounded-md px-3 py-1.5">
                                <Filter size={14} className="text-[var(--text-muted)]" />
                                <select
                                    value={toolFilter}
                                    onChange={(e) => setToolFilter(e.target.value)}
                                    className="bg-transparent text-sm text-[var(--text-primary)] outline-none"
                                >
                                    <option value="">All tools</option>
                                    {toolNames.map((t) => (
                                        <option key={t} value={t}>{t}</option>
                                    ))}
                                </select>
                            </div>
                            <span className="text-xs text-[var(--text-muted)] tabular-nums">
                                {logsData?.total ?? 0} entries
                            </span>
                        </div>

                        {/* Log entries */}
                        <div className="flex-1 overflow-y-auto p-4 font-mono text-sm">
                            {isLogsLoading ? (
                                <div className="text-center text-[var(--text-muted)] py-12">Loading logs...</div>
                            ) : !logsData?.entries?.length ? (
                                <div className="flex flex-col items-center justify-center py-20 text-[var(--text-muted)] border border-dashed border-[var(--border)] rounded-lg">
                                    <Terminal size={32} className="mb-4 opacity-50" />
                                    <p>No log entries found.</p>
                                </div>
                            ) : (
                                <div className="max-w-5xl mx-auto space-y-1">
                                    {logsData.entries.map((entry: LogEntry, idx: number) => (
                                        <div
                                            key={idx}
                                            className="flex items-start gap-3 px-3 py-2 rounded hover:bg-[var(--bg-surface)] group transition-colors"
                                        >
                                            <span className="shrink-0 mt-0.5">{levelIcon(entry.level)}</span>
                                            <span className="shrink-0 w-20 text-[11px] text-[var(--text-muted)] tabular-nums">
                                                {entry.ts ? new Date(entry.ts).toLocaleTimeString() : "—"}
                                            </span>
                                            <span className="shrink-0 w-16 text-right text-[11px] text-[var(--text-muted)] tabular-nums">
                                                {entry.duration_ms != null ? `${entry.duration_ms}ms` : ""}
                                            </span>
                                            <span className="flex-1 text-[var(--text-primary)] break-words">
                                                <span className="font-semibold">
                                                    {entry.event === "step" ? entry.name : entry.event}
                                                </span>
                                                {entry.status && entry.event === "step" && (
                                                    <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded border uppercase font-bold ${statusBadge(entry.status)}`}>
                                                        {entry.status}
                                                    </span>
                                                )}
                                                {entry.details && (
                                                    <span className="block mt-1 text-xs text-[var(--text-secondary)] font-normal">
                                                        {(entry.details as Record<string, unknown>).outputs_summary as string || ""}
                                                        {(entry.details as Record<string, unknown>).tool_name ? (
                                                            <span className="ml-2 bg-[var(--border-light)] text-[var(--text-muted)] px-1.5 py-0.5 rounded text-[10px]">
                                                                {(entry.details as Record<string, unknown>).tool_name as string}
                                                            </span>
                                                        ) : null}
                                                    </span>
                                                )}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* ── Tab: Trace (existing timeline view) ──── */}
                {activeTab === "trace" && (
                    <div className="flex-1 overflow-y-auto p-6 font-mono text-sm">
                        {isTraceLoading || !trace ? (
                            <div className="text-center text-[var(--text-muted)] py-12">Loading trace...</div>
                        ) : !trace.steps?.length ? (
                            <div className="flex flex-col items-center justify-center py-20 text-[var(--text-muted)] border border-dashed border-[var(--border)] rounded-lg">
                                <Terminal size={32} className="mb-4 opacity-50" />
                                <p>No execution steps recorded yet.</p>
                            </div>
                        ) : (
                            <div className="max-w-4xl mx-auto space-y-6 relative pb-12">
                                <div className="absolute left-[23px] top-6 bottom-0 w-px bg-[var(--border)] -z-10" />
                                {trace.steps.map((step: Record<string, unknown>, idx: number) => (
                                    <div key={(step.id as number) || idx} className="flex gap-4 group">
                                        <div className="shrink-0 w-12 h-12 flex items-center justify-center bg-[var(--bg-app)] relative z-10">
                                            <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                                                step.status === "success" ? "border-emerald-500 bg-emerald-50" :
                                                step.status === "failed" ? "border-red-500 bg-red-50" :
                                                "border-[var(--accent)] bg-[var(--accent-subtle)]"
                                            }`}>
                                                {step.status === "success" && <CheckCircle2 size={12} className="text-emerald-600" />}
                                                {step.status === "failed" && <XCircle size={12} className="text-red-600" />}
                                                {step.status !== "success" && step.status !== "failed" && <div className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" />}
                                            </div>
                                        </div>
                                        <div className="flex-1 bg-[var(--bg-surface)] border border-[var(--border)] rounded-[var(--radius-lg)] shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)] transition-all">
                                            <div className="p-4 flex justify-between items-start">
                                                <div className="flex items-center gap-3">
                                                    <h3 className="font-semibold text-base text-[var(--text-primary)] font-sans">{step.name as string}</h3>
                                                    <span className="text-xs text-[var(--text-muted)] bg-[var(--border-light)] px-1.5 py-0.5 rounded">{step.timestamp as string}</span>
                                                </div>
                                                <span className="text-xs font-medium text-[var(--text-secondary)]">{step.duration_ms as number}ms</span>
                                            </div>
                                            {Boolean(step.details) && Object.keys(step.details as Record<string, unknown>).length > 0 && (
                                                <div className="px-4 pb-4 border-t border-[var(--border-light)] mt-2 pt-3">
                                                    <div className="text-xs text-[var(--text-secondary)] space-y-2">
                                                        {Object.entries(step.details as Record<string, unknown>).map(([key, val]) => (
                                                            key === "prov_hash" ? (
                                                                <div key={key} className="flex items-baseline gap-2 mt-3 pt-3 border-t border-[var(--border-light)]/50">
                                                                    <span className="shrink-0 text-[var(--text-muted)] uppercase tracking-wider text-[10px] font-bold w-20">Prov Hash</span>
                                                                    <span className="bg-[var(--bg-app)] text-[var(--text-primary)] px-2 py-0.5 rounded border border-[var(--border)] font-mono text-[11px] select-all tracking-wider">
                                                                        {String(val)}
                                                                    </span>
                                                                </div>
                                                            ) : (
                                                                <div key={key} className="flex gap-2">
                                                                    <span className="shrink-0 text-[var(--text-muted)] capitalize w-20">{key}:</span>
                                                                    <span className="text-[var(--text-primary)] break-words whitespace-pre-wrap">{String(val)}</span>
                                                                </div>
                                                            )
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* ── Tab: Recipe ───────────────────────────── */}
                {activeTab === "recipe" && (
                    <div className="flex-1 overflow-y-auto p-6">
                        {!recipe ? (
                            <div className="text-center text-[var(--text-muted)] py-12">Loading recipe...</div>
                        ) : (
                            <div className="max-w-3xl mx-auto space-y-6">
                                <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-6 shadow-[var(--shadow-sm)]">
                                    <div className="flex items-center justify-between mb-4">
                                        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Run Recipe</h2>
                                        <button
                                            onClick={downloadRecipe}
                                            className="flex items-center gap-1.5 text-sm text-[var(--accent)] hover:underline"
                                        >
                                            <Download size={14} /> Download JSON
                                        </button>
                                    </div>

                                    {/* Key-value grid */}
                                    <div className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
                                        {recipe.schema_version && (
                                            <>
                                                <span className="text-[var(--text-muted)] font-medium">Schema</span>
                                                <span className="text-[var(--text-primary)] font-mono">{recipe.schema_version}</span>
                                            </>
                                        )}
                                        <span className="text-[var(--text-muted)] font-medium">Job ID</span>
                                        <span className="text-[var(--text-primary)] font-mono">{recipe.job_id}</span>
                                        <span className="text-[var(--text-muted)] font-medium">Name</span>
                                        <span className="text-[var(--text-primary)]">{recipe.name}</span>
                                        <span className="text-[var(--text-muted)] font-medium">Status</span>
                                        <span className={`px-2 py-0.5 rounded text-xs uppercase font-bold border w-fit ${statusBadge(recipe.status)}`}>{recipe.status}</span>
                                        <span className="text-[var(--text-muted)] font-medium">Started</span>
                                        <span className="text-[var(--text-primary)] font-mono text-xs">{recipe.started_at}</span>
                                        <span className="text-[var(--text-muted)] font-medium">Duration</span>
                                        <span className="text-[var(--text-primary)]">{((recipe.duration_ms || 0) / 1000).toFixed(1)}s</span>
                                        <span className="text-[var(--text-muted)] font-medium">Steps</span>
                                        <span className="text-[var(--text-primary)]">{recipe.steps_total}</span>
                                    </div>
                                </div>

                                {/* Environment */}
                                {recipe.environment && (
                                    <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-6 shadow-[var(--shadow-sm)]">
                                        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">Environment</h3>
                                        <div className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
                                            {Object.entries(recipe.environment as Record<string, string>).map(([k, v]) => (
                                                <div key={k} className="contents">
                                                    <span className="text-[var(--text-muted)] font-medium capitalize">{k}</span>
                                                    <span className="text-[var(--text-primary)] font-mono text-xs">{v}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Settings */}
                                {recipe.settings && (
                                    <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-6 shadow-[var(--shadow-sm)]">
                                        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">Settings</h3>
                                        <div className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
                                            {Object.entries(recipe.settings as Record<string, unknown>).map(([k, v]) => (
                                                <div key={k} className="contents">
                                                    <span className="text-[var(--text-muted)] font-medium capitalize">{k.replace(/_/g, " ")}</span>
                                                    <span className="text-[var(--text-primary)] font-mono text-xs">{String(v)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Connector calls */}
                                {recipe.connector_calls?.length > 0 && (
                                    <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-[var(--radius-lg)] p-6 shadow-[var(--shadow-sm)]">
                                        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">Connector Calls</h3>
                                        <div className="space-y-2">
                                            {(recipe.connector_calls as Array<Record<string, unknown>>).map((c, i: number) => (
                                                <div key={i} className="flex items-center gap-4 text-sm">
                                                    <span className="w-6 text-right font-mono text-[var(--text-muted)]">{c.step as number}</span>
                                                    <span className="bg-[var(--border-light)] text-[var(--text-primary)] px-2 py-0.5 rounded font-mono text-xs">{c.tool as string}</span>
                                                    <span className="text-[var(--text-muted)] text-xs">{c.duration_ms as number}ms</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {recipe.note && (
                                    <div className="bg-amber-50 border border-amber-200 rounded-[var(--radius-lg)] p-4 text-sm text-amber-800">
                                        {recipe.note}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
