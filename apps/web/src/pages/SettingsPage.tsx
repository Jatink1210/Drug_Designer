/** Settings — hardware dashboard, compute/runtime selection, model management. */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useRef, useCallback } from "react";
import { Loader2, Save, Cpu, HardDrive, Trash2, Download, CheckCircle2, XCircle, Wand2 } from "lucide-react";
import {
    runtimesListAPI, runtimesRecommendAPI, modelsCatalogAPI, modelsInstalledAPI,
    modelsDeleteAPI, settingsGetAPI, settingsUpdateAPI, ensureApiBase,
    type RuntimesResponse, type RecommendResponse, type ModelCatalogEntry, type InstalledModel,
} from "@/lib/api";

export default function SettingsPage() {
    const qc = useQueryClient();
    const [formData, setFormData] = useState<Record<string, unknown>>({});
    const [pullModel, setPullModel] = useState("");
    const [pullProgress, setPullProgress] = useState<string | null>(null);
    const [isPulling, setIsPulling] = useState(false);
    const abortRef = useRef<AbortController | null>(null);

    const { data: settings, isLoading: loadingSettings } = useQuery({ queryKey: ["settings"], queryFn: settingsGetAPI });
    const { data: runtimes } = useQuery<RuntimesResponse>({ queryKey: ["runtimes"], queryFn: runtimesListAPI });
    const { data: catalog } = useQuery<ModelCatalogEntry[]>({ queryKey: ["catalog"], queryFn: modelsCatalogAPI });
    const { data: installed, refetch: refetchInstalled } = useQuery<InstalledModel[]>({ queryKey: ["installed"], queryFn: modelsInstalledAPI });

    useEffect(() => { if (settings) setFormData(settings); }, [settings]);

    const saveMut = useMutation({
        mutationFn: (s: Record<string, unknown>) => settingsUpdateAPI(s),
        onSuccess: () => { qc.invalidateQueries({ queryKey: ["settings"] }); qc.invalidateQueries({ queryKey: ["runtimes"] }); },
    });

    const deleteMut = useMutation({
        mutationFn: (id: string) => modelsDeleteAPI(id),
        onSuccess: () => refetchInstalled(),
    });

    const handlePull = useCallback(async () => {
        if (!pullModel) return;
        setIsPulling(true);
        setPullProgress("Starting download...");
        const ctrl = new AbortController();
        abortRef.current = ctrl;
        try {
            const base = await ensureApiBase();
            const resp = await fetch(`${base}/models/pull/stream`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_id: pullModel }),
                signal: ctrl.signal,
            });
            const reader = resp.body?.getReader();
            const decoder = new TextDecoder();
            if (reader) {
                let buf = "";
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buf += decoder.decode(value, { stream: true });
                    const lines = buf.split("\n");
                    buf = lines.pop() || "";
                    for (const line of lines) {
                        if (line.startsWith("data: ")) {
                            try {
                                const d = JSON.parse(line.slice(6));
                                if (d.status) setPullProgress(d.status + (d.completed && d.total ? ` (${Math.round(d.completed / d.total * 100)}%)` : ""));
                            } catch { /* skip */ }
                        }
                    }
                }
            }
            setPullProgress("Done!");
            refetchInstalled();
        } catch (e) {
            if ((e as Error).name !== "AbortError") setPullProgress(`Error: ${(e as Error).message}`);
        } finally {
            setIsPulling(false);
            abortRef.current = null;
        }
    }, [pullModel, refetchInstalled]);

    const handleChange = (k: string, v: unknown) => setFormData(prev => ({ ...prev, [k]: v }));

    if (loadingSettings) return <div className="p-8"><Loader2 className="animate-spin text-gray-400" /></div>;

    const caps = runtimes?.capabilities;
    const hasGpu = caps ? caps.gpu !== "none" && caps.gpu !== "unknown" : false;
    const computeMode = String(formData.compute_mode || "auto");
    const selectedModel = catalog?.find(m => m.name === formData.model_id);

    return (
        <div className="flex-1 overflow-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-3xl mx-auto px-6 py-5 space-y-5">
                <div>
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">Settings</h1>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">Manage compute, runtime, and model configurations.</p>
                </div>

                {/* Hardware Dashboard */}
                {caps && <HardwareCard caps={caps} />}

                {/* Compute & Runtime */}
                <div className="glass-card rounded-xl p-5 space-y-4">
                    <h2 className="text-sm font-semibold text-[var(--text-primary)]">Compute & Runtime</h2>

                    <div>
                        <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Compute Mode</label>
                        <div className="grid grid-cols-3 gap-2">
                            {([["auto", "Auto", Wand2], ["cpu", "CPU", Cpu], ["gpu", "GPU", HardDrive]] as const).map(([val, lbl, Icon]) => (
                                <button key={val} onClick={() => handleChange("compute_mode", val)}
                                    disabled={val === "gpu" && !hasGpu}
                                    className={`p-3 rounded-lg border text-left text-xs transition-all ${computeMode === val ? "ring-2 ring-[var(--accent)] border-transparent bg-[var(--bg-app)]" : "hover:bg-gray-50"} ${val === "gpu" && !hasGpu ? "opacity-40 cursor-not-allowed" : ""}`}
                                    style={{ borderColor: "var(--border)" }}>
                                    <Icon size={14} className="mb-1 text-[var(--text-muted)]" />
                                    <div className="font-medium text-[var(--text-primary)]">{lbl}</div>
                                    {val === "auto" && <span className="text-[9px] text-[var(--accent)]">Recommended</span>}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Inference Runtime</label>
                        <select value={String(formData.runtime || "llama.cpp")} onChange={e => handleChange("runtime", e.target.value)}
                            className="w-full border rounded-lg text-sm p-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                            style={{ borderColor: "var(--border)" }}>
                            {runtimes?.available.map(r => (
                                <option key={r.id} value={r.id} disabled={r.status === "not_installed"}>{r.name}{r.status === "not_installed" ? " (Not Installed)" : ""}</option>
                            ))}
                        </select>
                    </div>

                    {formData.runtime === "remote" && (
                        <div>
                            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Remote Endpoint URL</label>
                            <input type="text" value={String(formData.remote_base_url || "")} onChange={e => handleChange("remote_base_url", e.target.value)}
                                placeholder="https://api.openai.com/v1"
                                className="w-full border rounded-lg text-sm p-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                                style={{ borderColor: "var(--border)" }} />
                        </div>
                    )}
                </div>

                {/* Active Model */}
                <div className="glass-card rounded-xl p-5 space-y-4">
                    <h2 className="text-sm font-semibold text-[var(--text-primary)]">Active Model</h2>
                    <select value={String(formData.model_id || "")} onChange={e => handleChange("model_id", e.target.value)}
                        className="w-full border rounded-lg text-sm p-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                        style={{ borderColor: "var(--border)" }}>
                        <option value="">Select a model...</option>
                        {catalog?.map(m => (
                            <option key={m.name} value={m.name}>{m.name} ({m.parameters}, {m.size_gb} GB)</option>
                        ))}
                    </select>
                    {selectedModel && <ModelInfoCard model={selectedModel} caps={caps} />}
                </div>

                {/* Installed Models */}
                <div className="glass-card rounded-xl p-5 space-y-4">
                    <h2 className="text-sm font-semibold text-[var(--text-primary)]">Installed Models</h2>
                    {installed && installed.length > 0 ? (
                        <div className="space-y-2">
                            {installed.map(m => (
                                <div key={m.name} className="flex items-center justify-between px-3 py-2 rounded-lg border text-xs" style={{ borderColor: "var(--border)" }}>
                                    <div>
                                        <span className="font-medium text-[var(--text-primary)]">{m.name}</span>
                                        <span className="ml-2 text-[var(--text-muted)]">{(m.size / 1e9).toFixed(1)} GB</span>
                                    </div>
                                    <button onClick={() => deleteMut.mutate(m.name)} disabled={deleteMut.isPending}
                                        className="text-red-500 hover:text-red-700 p-1"><Trash2 size={12} /></button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-xs text-[var(--text-muted)]">No models installed in Ollama.</p>
                    )}

                    <div className="pt-2 border-t" style={{ borderColor: "var(--border)" }}>
                        <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Pull New Model</label>
                        <div className="flex gap-2">
                            <select value={pullModel} onChange={e => setPullModel(e.target.value)}
                                className="flex-1 border rounded-lg text-sm p-2 bg-white" style={{ borderColor: "var(--border)" }}>
                                <option value="">Select model to pull...</option>
                                {catalog?.map(m => <option key={m.name} value={m.ollama_id}>{m.name} ({m.size_gb} GB)</option>)}
                            </select>
                            <button onClick={handlePull} disabled={!pullModel || isPulling}
                                className="px-4 py-2 rounded-lg text-xs font-medium text-white disabled:opacity-40"
                                style={{ background: "var(--accent)" }}>
                                {isPulling ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                            </button>
                        </div>
                        {pullProgress && (
                            <div className="mt-2 px-3 py-2 rounded bg-slate-50 text-xs text-[var(--text-muted)]">{pullProgress}</div>
                        )}
                    </div>
                </div>

                {/* Privacy */}
                <div className="glass-card rounded-xl p-5 space-y-3">
                    <h2 className="text-sm font-semibold text-[var(--text-primary)]">Privacy</h2>
                    <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer">
                        <input type="checkbox" checked={!!formData.privacy_mode} onChange={e => handleChange("privacy_mode", e.target.checked)}
                            className="rounded border-gray-300" />
                        Privacy mode — keep all data local
                    </label>
                </div>

                {/* Save */}
                <div className="flex justify-end pb-8">
                    <button onClick={() => saveMut.mutate(formData)} disabled={saveMut.isPending}
                        className="px-6 py-2.5 rounded-lg text-sm font-medium text-white flex items-center gap-2 hover:opacity-90 disabled:opacity-40"
                        style={{ background: "var(--accent)" }}>
                        {saveMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                        Save Changes
                    </button>
                </div>
            </div>
        </div>
    );
}

/* ─── Sub-components ──────────────────────────────────── */

function HardwareCard({ caps }: { caps: NonNullable<RuntimesResponse["capabilities"]> }) {
    const [rec, setRec] = useState<RecommendResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const handleRecommend = async () => {
        setLoading(true);
        try { setRec(await runtimesRecommendAPI()); } catch { /* ignore */ }
        setLoading(false);
    };

    return (
        <div className="glass-card rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-[var(--text-primary)]">Hardware</h2>
                <button onClick={handleRecommend} disabled={loading}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-medium text-white hover:opacity-90"
                    style={{ background: "var(--accent)" }}>
                    {loading ? <Loader2 size={10} className="animate-spin" /> : <Wand2 size={10} />}
                    Auto-Detect
                </button>
            </div>
            <div className="grid grid-cols-4 gap-3 text-xs">
                <StatCell label="CPU Cores" value={String(caps.cpu_cores)} />
                <StatCell label="RAM" value={`${caps.ram_gb} GB`} />
                <StatCell label="GPU" value={caps.gpu_name || caps.gpu} />
                <StatCell label="VRAM" value={caps.vram_gb ? `${caps.vram_gb} GB` : "N/A"} />
            </div>
            {rec && rec.recommended_model && (
                <div className="mt-3 px-3 py-2 rounded-lg bg-green-50 border border-green-200 text-xs">
                    <span className="font-medium text-green-800">Recommended:</span>{" "}
                    <span className="text-green-700">{rec.recommended_model.name}</span>{" "}
                    <span className="text-green-600">on {rec.compute_mode.toUpperCase()}</span>
                    <span className="text-green-500 ml-1">({rec.compatible_models.length} compatible models)</span>
                </div>
            )}
        </div>
    );
}

function StatCell({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <div className="text-[var(--text-muted)] text-[10px] uppercase tracking-wider">{label}</div>
            <div className="font-medium text-[var(--text-primary)] mt-0.5">{value}</div>
        </div>
    );
}

function ModelInfoCard({ model, caps }: { model: ModelCatalogEntry; caps?: RuntimesResponse["capabilities"] }) {
    const ramOk = caps ? (caps.ram_gb >= model.min_ram_gb) : true;
    const vramOk = caps ? (caps.vram_gb >= model.min_vram_gb) : true;

    return (
        <div className="rounded-lg border p-3 text-xs space-y-2" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-center justify-between">
                <span className="font-medium text-[var(--text-primary)]">{model.name}</span>
                <div className="flex gap-1">
                    {model.tags.map(t => <span key={t} className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 text-[9px]">{t}</span>)}
                </div>
            </div>
            <p className="text-[var(--text-muted)]">{model.description}</p>
            <div className="grid grid-cols-4 gap-2">
                <StatCell label="Size" value={`${model.size_gb} GB`} />
                <StatCell label="Params" value={model.parameters} />
                <StatCell label="Context" value={`${model.context_window}`} />
                <StatCell label="Quant" value={model.default_quantization} />
            </div>
            <div className="flex gap-3 pt-1">
                <CompatBadge label="CPU" ok={ramOk} detail={`Needs ${model.min_ram_gb} GB RAM`} />
                <CompatBadge label="GPU" ok={vramOk} detail={`Needs ${model.min_vram_gb} GB VRAM`} />
            </div>
        </div>
    );
}

function CompatBadge({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
    return (
        <div className="flex items-center gap-1 text-[10px]" title={detail}>
            {ok ? <CheckCircle2 size={10} className="text-green-600" /> : <XCircle size={10} className="text-red-500" />}
            <span className={ok ? "text-green-700" : "text-red-600"}>{label}: {ok ? "Compatible" : "Insufficient"}</span>
        </div>
    );
}
