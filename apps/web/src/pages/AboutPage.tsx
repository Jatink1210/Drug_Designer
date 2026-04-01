/** About / Trust / Diagnostics page. */

import { useState, useEffect } from "react";
import { Shield, Activity, Server, Database, Cpu, Globe, RefreshCw, CheckCircle2, XCircle, AlertCircle, Clock } from "lucide-react";
import { diagnosticsAPI, type DiagnosticsResponse } from "@/lib/api";

export default function AboutPage() {
    const [diag, setDiag] = useState<DiagnosticsResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const refresh = async () => {
        setLoading(true);
        setError(null);
        try { setDiag(await diagnosticsAPI()); }
        catch { setError("Unable to reach API — check that the backend is running."); }
        setLoading(false);
    };

    useEffect(() => { refresh(); }, []);

    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="flex items-center justify-between mb-5">
                    <div>
                        <h1 className="text-lg font-semibold text-[var(--text-primary)]">About & Diagnostics</h1>
                        <p className="text-xs text-[var(--text-muted)] mt-0.5">System transparency, API health, model cards, and disclaimers</p>
                    </div>
                    <button onClick={refresh} disabled={loading}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border hover:bg-white transition-colors" style={{ borderColor: "var(--border)" }}>
                        <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
                    </button>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-6">
                    {/* System components */}
                    <div className="glass-card rounded-xl p-4">
                        <h2 className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-3"><Server size={14} /> System Components</h2>
                        <div className="space-y-2">
                            {error ? (
                                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-50 text-red-700 text-xs">
                                    <XCircle size={14} /> {error}
                                </div>
                            ) : diag ? Object.entries(diag.components).map(([name, comp]) => (
                                <div key={name} className="flex items-center justify-between py-1.5 border-b border-dashed" style={{ borderColor: "var(--border-light)" }}>
                                    <span className="text-xs text-[var(--text-secondary)]">{name}</span>
                                    <StatusBadge status={comp.status} />
                                </div>
                            )) : <Skeleton count={5} />}
                        </div>
                    </div>

                    {/* Architecture */}
                    <div className="glass-card rounded-xl p-4">
                        <h2 className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-3"><Cpu size={14} /> Architecture</h2>
                        <pre className="text-[10px] text-[var(--text-muted)] font-mono leading-relaxed whitespace-pre">{`Browser (React + TS)
  │  Vite proxy /api
  ▼
FastAPI (:8000)
  ├── 16 Connectors (async)
  ├── Circuit breaker + Rate limiter
  ├── Two-tier cache (LRU + SQLite)
  └── Provenance tracking
  │
  ├── Qdrant (vectors)
  ├── Redis (jobs, cache)
  └── SQLite (sessions, cache)`}</pre>
                    </div>
                </div>

                {/* Connector health */}
                <div className="glass-card rounded-xl p-4 mb-6">
                    <h2 className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-3"><Globe size={14} /> External API Health</h2>
                    <div className="grid grid-cols-3 gap-3">
                        {diag ? Object.entries(diag.connectors).map(([name, conn]) => (
                            <div key={name} className="flex items-center justify-between p-2.5 rounded-lg border" style={{ borderColor: "var(--border-light)" }}>
                                <div>
                                    <div className="text-xs font-medium text-[var(--text-primary)]">{name}</div>
                                    {conn.latency_ms != null && (
                                        <div className="flex items-center gap-1 mt-0.5"><Clock size={9} className="text-[var(--text-muted)]" /><span className="text-[10px] text-[var(--text-muted)]">{conn.latency_ms}ms</span></div>
                                    )}
                                </div>
                                <StatusBadge status={conn.status} />
                            </div>
                        )) : <Skeleton count={9} />}
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-6">
                    {/* Version & Build Info */}
                    <div className="glass-card rounded-xl p-4">
                        <h2 className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-3"><Activity size={14} /> Version Info</h2>
                        <div className="space-y-2 text-xs">
                            <div className="flex justify-between py-1 border-b border-dashed" style={{ borderColor: "var(--border-light)" }}>
                                <span className="text-[var(--text-muted)]">Product</span>
                                <span className="text-[var(--text-primary)] font-medium">Drug Designer</span>
                            </div>
                            <div className="flex justify-between py-1 border-b border-dashed" style={{ borderColor: "var(--border-light)" }}>
                                <span className="text-[var(--text-muted)]">Version</span>
                                <span className="text-[var(--text-primary)] font-medium">{diag?.version || "1.0.0"}</span>
                            </div>
                            <div className="flex justify-between py-1 border-b border-dashed" style={{ borderColor: "var(--border-light)" }}>
                                <span className="text-[var(--text-muted)]">Connectors</span>
                                <span className="text-[var(--text-primary)] font-medium">{diag ? Object.keys(diag.connectors).length : "—"}</span>
                            </div>
                            <div className="flex justify-between py-1">
                                <span className="text-[var(--text-muted)]">Runtime Mode</span>
                                <span className="text-[var(--text-primary)] font-medium">Embedded / Local</span>
                            </div>
                        </div>
                    </div>

                    {/* Disclaimer */}
                    <div className="glass-card rounded-xl p-4">
                        <h2 className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-3"><Shield size={14} /> Disclaimers</h2>
                        <div className="space-y-2 text-xs text-[var(--text-muted)] leading-relaxed">
                            <p><strong className="text-[var(--text-secondary)]">Research Tool Only.</strong> Drug Designer is a research aid. It is not a medical device, diagnostic tool, or substitute for professional medical advice.</p>
                            <p><strong className="text-[var(--text-secondary)]">AI Outputs.</strong> AI-generated summaries are approximate and may contain errors. Always verify claims against primary sources.</p>
                            <p><strong className="text-[var(--text-secondary)]">Data Sources.</strong> Data is fetched from public APIs (UniProt, PubMed, RCSB, etc.) and may have different licensing terms.</p>
                            <p><strong className="text-[var(--text-secondary)]">No Medical Advice.</strong> Do not make clinical decisions based solely on this software.</p>
                        </div>
                    </div>
                </div>

                {/* Version */}
                <div className="text-center py-4 text-[10px] text-[var(--text-muted)]">
                    Drug Designer v{diag?.version || "1.0.0"}
                </div>
            </div>
        </div>
    );
}

function StatusBadge({ status }: { status: string }) {
    const config: Record<string, { icon: React.ReactNode; cls: string }> = {
        ok: { icon: <CheckCircle2 size={12} />, cls: "text-green-600" },
        degraded: { icon: <AlertCircle size={12} />, cls: "text-amber-500" },
        unavailable: { icon: <XCircle size={12} />, cls: "text-red-500" },
        not_configured: { icon: <AlertCircle size={12} />, cls: "text-slate-400" },
    };
    const c = config[status] || config.not_configured;
    return <span className={`flex items-center gap-1 text-[10px] font-medium ${c.cls}`}>{c.icon} {status}</span>;
}

function Skeleton({ count }: { count: number }) {
    return <>{Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-6 bg-slate-100 rounded animate-pulse" />
    ))}</>;
}
