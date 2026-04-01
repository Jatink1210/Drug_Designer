/** Data Manager — API keys, connector toggles, cache, storage. */

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    Database, Upload, RefreshCw, Activity, HardDrive, Settings2,
    Key, Power, Trash2, Loader2, CheckCircle2, XCircle, Plus, Save, Eye, EyeOff
} from "lucide-react";
import {
    dataKeysAPI, dataSetKeyAPI, dataDeleteKeyAPI,
    dataConnectorsAPI, dataToggleConnectorAPI,
    dataCacheAPI, dataClearCacheAPI, dataStorageAPI,
    type ConnectorInfo,
} from "@/lib/api";

export default function DataPage() {
    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1200px] mx-auto px-6 py-5">
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">Data Manager</h1>
                <p className="text-xs text-[var(--text-muted)] mb-5">Manage API keys, connectors, caches, and storage</p>

                <div className="grid grid-cols-2 gap-5">
                    <APIKeysPanel />
                    <ConnectorsPanel />
                    <CachePanel />
                    <StoragePanel />
                </div>
            </div>
        </div>
    );
}

/* ─── API Keys ────────────────────────────────────────── */

function APIKeysPanel() {
    const qc = useQueryClient();
    const keysQ = useQuery({ queryKey: ["dataKeys"], queryFn: dataKeysAPI });
    const setKeyMut = useMutation({ mutationFn: ({ service, key }: { service: string; key: string }) => dataSetKeyAPI(service, key), onSuccess: () => qc.invalidateQueries({ queryKey: ["dataKeys"] }) });
    const delKeyMut = useMutation({ mutationFn: (service: string) => dataDeleteKeyAPI(service), onSuccess: () => qc.invalidateQueries({ queryKey: ["dataKeys"] }) });
    const [newService, setNewService] = useState("");
    const [newKey, setNewKey] = useState("");
    const [showKey, setShowKey] = useState(false);

    const keys = (keysQ.data as any)?.keys || {};

    return (
        <div className="glass-card rounded-xl p-4">
            <h2 className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-3"><Key size={14} /> API Keys</h2>
            <div className="space-y-1 mb-3">
                {Object.entries(keys).map(([service, masked]) => (
                    <div key={service} className="flex items-center justify-between py-1.5 border-b border-dashed" style={{ borderColor: "var(--border-light)" }}>
                        <div>
                            <span className="text-xs font-medium text-[var(--text-primary)]">{service}</span>
                            <span className="text-[10px] text-[var(--text-muted)] ml-2 font-mono">{String(masked)}</span>
                        </div>
                        <button onClick={() => delKeyMut.mutate(service)} className="text-red-400 hover:text-red-600"><Trash2 size={12} /></button>
                    </div>
                ))}
                {Object.keys(keys).length === 0 && <p className="text-xs text-[var(--text-muted)]">No API keys configured</p>}
            </div>
            <div className="flex gap-2">
                <select value={newService} onChange={e => setNewService(e.target.value)} className="flex-1 px-2 py-1.5 text-xs rounded border" style={{ borderColor: "var(--border)" }}>
                    <option value="">Select service…</option>
                    {["NCBI_API_KEY", "OPENAI_API_KEY", "SEMANTIC_SCHOLAR_KEY", "SURECHEBL_KEY"].map(k => <option key={k} value={k}>{k}</option>)}
                </select>
                <div className="relative flex-1">
                    <input type={showKey ? "text" : "password"} value={newKey} onChange={e => setNewKey(e.target.value)} placeholder="API Key"
                        className="w-full px-2 py-1.5 text-xs rounded border pr-7" style={{ borderColor: "var(--border)" }} />
                    <button onClick={() => setShowKey(!showKey)} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]">
                        {showKey ? <EyeOff size={10} /> : <Eye size={10} />}
                    </button>
                </div>
                <button onClick={() => { if (newService && newKey) { setKeyMut.mutate({ service: newService, key: newKey }); setNewKey(""); } }}
                    className="px-2 py-1.5 rounded text-xs text-white" style={{ background: "var(--accent)" }}>
                    <Save size={12} />
                </button>
            </div>
        </div>
    );
}

/* ─── Connectors ──────────────────────────────────────── */

function ConnectorsPanel() {
    const qc = useQueryClient();
    const connectorsQ = useQuery({ queryKey: ["dataConnectors"], queryFn: dataConnectorsAPI });
    const toggleMut = useMutation({
        mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => dataToggleConnectorAPI(id, enabled),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["dataConnectors"] }),
    });

    const connectors = connectorsQ.data || [];

    return (
        <div className="glass-card rounded-xl p-4">
            <h2 className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-3"><Power size={14} /> Connectors</h2>
            <div className="space-y-1">
                {connectors.map((c: ConnectorInfo) => (
                    <div key={c.id} className="flex items-center justify-between py-1.5 border-b border-dashed" style={{ borderColor: "var(--border-light)" }}>
                        <div className="flex items-center gap-2">
                            <span className={`w-1.5 h-1.5 rounded-full ${c.enabled ? "bg-green-500" : "bg-slate-300"}`} />
                            <span className="text-xs text-[var(--text-primary)]">{c.name}</span>
                            {c.required && <span className="text-[8px] px-1 py-0.5 rounded bg-slate-100 text-slate-500">core</span>}
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" checked={c.enabled} onChange={() => toggleMut.mutate({ id: c.id, enabled: !c.enabled })} className="sr-only peer" />
                            <div className="w-7 h-4 bg-gray-200 rounded-full peer peer-checked:bg-[var(--accent)] after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:after:translate-x-full"></div>
                        </label>
                    </div>
                ))}
            </div>
        </div>
    );
}

/* ─── Cache ───────────────────────────────────────────── */

function CachePanel() {
    const qc = useQueryClient();
    const cacheQ = useQuery({ queryKey: ["dataCache"], queryFn: dataCacheAPI });
    const clearMut = useMutation({ mutationFn: dataClearCacheAPI, onSuccess: () => qc.invalidateQueries({ queryKey: ["dataCache"] }) });

    const cache = cacheQ.data || {};
    const sqliteStats = (cache as any).sqlite || {};
    const memStats = (cache as any).memory || {};

    return (
        <div className="glass-card rounded-xl p-4">
            <h2 className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-3"><Database size={14} /> Cache</h2>
            <div className="grid grid-cols-2 gap-3 mb-3">
                <div className="rounded-lg border p-2.5" style={{ borderColor: "var(--border-light)" }}>
                    <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase">SQLite</div>
                    <div className="text-sm font-semibold text-[var(--text-primary)] mt-0.5">{sqliteStats.total_entries ?? "—"}</div>
                    <div className="text-[10px] text-[var(--text-muted)]">entries</div>
                </div>
                <div className="rounded-lg border p-2.5" style={{ borderColor: "var(--border-light)" }}>
                    <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase">Memory</div>
                    <div className="text-sm font-semibold text-[var(--text-primary)] mt-0.5">{memStats.size ?? "—"}</div>
                    <div className="text-[10px] text-[var(--text-muted)]">/ {memStats.max_size ?? 2000} max</div>
                </div>
            </div>
            <button onClick={() => clearMut.mutate()} disabled={clearMut.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border text-red-600 hover:bg-red-50" style={{ borderColor: "var(--border)" }}>
                {clearMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />} Clear All Caches
            </button>
        </div>
    );
}

/* ─── Storage ─────────────────────────────────────────── */

function StoragePanel() {
    const storageQ = useQuery({ queryKey: ["dataStorage"], queryFn: dataStorageAPI });
    const data = storageQ.data as any || {};
    const subs = data.subdirectories || {};

    const formatBytes = (b: number) => {
        if (!b) return "0 B";
        if (b < 1024) return b + " B";
        if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
        return (b / 1048576).toFixed(1) + " MB";
    };

    return (
        <div className="glass-card rounded-xl p-4">
            <h2 className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-3"><HardDrive size={14} /> Storage</h2>
            <div className="text-sm font-semibold text-[var(--text-primary)]">{formatBytes(data.total_bytes || 0)}</div>
            <div className="text-[10px] text-[var(--text-muted)] mb-3">Total local storage</div>
            <div className="space-y-1.5">
                {Object.entries(subs).map(([name, bytes]) => (
                    <div key={name} className="flex items-center justify-between">
                        <span className="text-xs text-[var(--text-secondary)]">{name.replace(/_/g, " ")}</span>
                        <span className="text-xs font-mono text-[var(--text-muted)]">{formatBytes(Number(bytes))}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
