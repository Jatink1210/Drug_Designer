/**
 * ModelsPage — First-class Model Center surface.
 *
 * Shows installed models, online catalog with hardware compatibility,
 * recommendations, pull progress, and runtime status.
 */

import { useState, useEffect, useCallback } from "react";
import { ensureApiBase } from "@/lib/api";

interface InstalledModel {
    name: string;
    size: number;
    modified_at: string;
}

interface CatalogModel {
    name: string;
    ollama_id: string;
    size_gb: number;
    parameters: string;
    min_ram_gb: number;
    min_vram_gb: number;
    context_window: number;
    compute_modes: string[];
    tags: string[];
    description: string;
    default_quantization: string;
}

interface HardwareInfo {
    cpu_cores: number;
    ram_gb: number;
    gpu: string;
    gpu_name: string | null;
    vram_gb: number;
}

interface RuntimeInfo {
    capabilities: HardwareInfo;
    available: { id: string; name: string; status: string; capabilities: string[] }[];
    active: string;
    compute_mode: string;
}

type PullStatus = "idle" | "pulling" | "done" | "error";

export default function ModelsPage() {
    const [installed, setInstalled] = useState<InstalledModel[]>([]);
    const [catalog, setCatalog] = useState<CatalogModel[]>([]);
    const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
    const [pullTarget, setPullTarget] = useState<string | null>(null);
    const [pullStatus, setPullStatus] = useState<PullStatus>("idle");
    const [pullProgress, setPullProgress] = useState("");
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<"installed" | "catalog" | "hardware">("catalog");

    const loadData = useCallback(async () => {
        try {
            const base = await ensureApiBase();
            const [instRes, catRes, rtRes] = await Promise.all([
                fetch(`${base}/models/installed`).then(r => r.json()).catch(() => []),
                fetch(`${base}/models/catalog`).then(r => r.json()).catch(() => []),
                fetch(`${base}/runtimes`).then(r => r.json()).catch(() => null),
            ]);
            setInstalled(instRes);
            setCatalog(catRes);
            setRuntime(rtRes);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadData(); }, [loadData]);

    const pullModel = async (ollamaId: string) => {
        setPullTarget(ollamaId);
        setPullStatus("pulling");
        setPullProgress("Starting pull…");
        try {
            const base = await ensureApiBase();
            const res = await fetch(`${base}/models/pull`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_id: ollamaId }),
            });
            const data = await res.json();
            if (data.status === "success") {
                setPullStatus("done");
                setPullProgress(data.message);
                loadData();
            } else {
                setPullStatus("error");
                setPullProgress(data.message || data.detail || "Pull failed");
            }
        } catch (e: any) {
            setPullStatus("error");
            setPullProgress(e.message || "Pull failed");
        }
    };

    const deleteModel = async (name: string) => {
        try {
            const base = await ensureApiBase();
            await fetch(`${base}/models/${encodeURIComponent(name)}`, { method: "DELETE" });
            loadData();
        } catch { /* ignore */ }
    };

    const isInstalled = (ollamaId: string) =>
        installed.some(m => m.name === ollamaId || m.name.startsWith(ollamaId.split(":")[0]));

    const canRunOnCPU = (model: CatalogModel) =>
        runtime && runtime.capabilities.ram_gb >= model.min_ram_gb;

    const canRunOnGPU = (model: CatalogModel) =>
        runtime && runtime.capabilities.vram_gb >= model.min_vram_gb;

    const formatSize = (bytes: number) => {
        if (bytes > 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
        return `${(bytes / 1e6).toFixed(0)} MB`;
    };

    if (loading) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-5xl mx-auto">
                {/* Header */}
                <div className="mb-6">
                    <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                        Model Center
                    </h1>
                    <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                        Manage local models, browse the biomedical catalog, and view hardware compatibility.
                    </p>
                </div>

                {/* Hardware Summary Bar */}
                {runtime && (
                    <div className="rounded-xl p-4 mb-6" style={{
                        background: "var(--bg-card)",
                        border: "1px solid var(--border)"
                    }}>
                        <div className="flex items-center gap-6 text-xs" style={{ color: "var(--text-secondary)" }}>
                            <div>
                                <span style={{ color: "var(--text-muted)" }}>CPU </span>
                                <strong>{runtime.capabilities.cpu_cores} cores</strong>
                            </div>
                            <div>
                                <span style={{ color: "var(--text-muted)" }}>RAM </span>
                                <strong>{runtime.capabilities.ram_gb} GB</strong>
                            </div>
                            <div>
                                <span style={{ color: "var(--text-muted)" }}>GPU </span>
                                <strong>{runtime.capabilities.gpu_name || runtime.capabilities.gpu}</strong>
                                {runtime.capabilities.vram_gb > 0 && (
                                    <span className="ml-1">({runtime.capabilities.vram_gb} GB VRAM)</span>
                                )}
                            </div>
                            <div>
                                <span style={{ color: "var(--text-muted)" }}>Runtime </span>
                                <strong>{runtime.active}</strong>
                            </div>
                            <div>
                                <span style={{ color: "var(--text-muted)" }}>Mode </span>
                                <strong>{runtime.compute_mode}</strong>
                            </div>
                        </div>
                    </div>
                )}

                {/* Tab Bar */}
                <div className="flex gap-1 mb-4">
                    {(["catalog", "installed", "hardware"] as const).map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className="px-4 py-1.5 rounded-lg text-xs font-semibold transition-colors"
                            style={{
                                background: activeTab === tab ? "var(--accent)" : "var(--bg-card)",
                                color: activeTab === tab ? "#fff" : "var(--text-muted)",
                                border: `1px solid ${activeTab === tab ? "var(--accent)" : "var(--border)"}`,
                            }}
                        >
                            {tab === "catalog" ? `Catalog (${catalog.length})` :
                             tab === "installed" ? `Installed (${installed.length})` :
                             "Hardware & Runtimes"}
                        </button>
                    ))}
                </div>

                {/* Pull Progress */}
                {pullStatus !== "idle" && (
                    <div className="rounded-lg p-3 mb-4 text-xs" style={{
                        background: pullStatus === "error" ? "rgba(255,80,80,0.08)" :
                                    pullStatus === "done" ? "rgba(80,200,80,0.08)" :
                                    "rgba(100,140,255,0.08)",
                        border: `1px solid ${pullStatus === "error" ? "rgba(255,80,80,0.2)" :
                                              pullStatus === "done" ? "rgba(80,200,80,0.2)" :
                                              "rgba(100,140,255,0.2)"}`,
                        color: "var(--text-secondary)",
                    }}>
                        <strong>{pullTarget}</strong>: {pullProgress}
                        {pullStatus !== "pulling" && (
                            <button
                                className="ml-3 underline"
                                onClick={() => { setPullStatus("idle"); setPullTarget(null); }}
                            >
                                Dismiss
                            </button>
                        )}
                    </div>
                )}

                {/* Catalog Tab */}
                {activeTab === "catalog" && (
                    <div className="grid gap-3">
                        {catalog.map(model => {
                            const cpuOk = canRunOnCPU(model);
                            const gpuOk = canRunOnGPU(model);
                            const alreadyInstalled = isInstalled(model.ollama_id);

                            return (
                                <div key={model.name} className="rounded-xl p-4" style={{
                                    background: "var(--bg-card)",
                                    border: "1px solid var(--border)",
                                }}>
                                    <div className="flex items-start justify-between">
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2">
                                                <h3 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                                                    {model.name}
                                                </h3>
                                                <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{
                                                    background: "rgba(100,140,255,0.1)",
                                                    color: "var(--accent)",
                                                }}>
                                                    {model.parameters}
                                                </span>
                                                {model.tags.includes("biomedical") && (
                                                    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{
                                                        background: "rgba(80,200,120,0.1)",
                                                        color: "#50c878",
                                                    }}>
                                                        Biomedical
                                                    </span>
                                                )}
                                                {alreadyInstalled && (
                                                    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{
                                                        background: "rgba(80,200,80,0.1)",
                                                        color: "#50c850",
                                                    }}>
                                                        Installed
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
                                                {model.description}
                                            </p>
                                            <div className="flex items-center gap-4 mt-2 text-[10px]" style={{ color: "var(--text-muted)" }}>
                                                <span>Size: {model.size_gb} GB</span>
                                                <span>Context: {model.context_window.toLocaleString()}</span>
                                                <span>Quant: {model.default_quantization}</span>
                                                <span>
                                                    CPU: <strong style={{ color: cpuOk ? "#50c878" : "#ff6060" }}>
                                                        {cpuOk ? "✓" : "✗"} {model.min_ram_gb}GB RAM
                                                    </strong>
                                                </span>
                                                <span>
                                                    GPU: <strong style={{ color: gpuOk ? "#50c878" : "#ff6060" }}>
                                                        {gpuOk ? "✓" : "✗"} {model.min_vram_gb}GB VRAM
                                                    </strong>
                                                </span>
                                            </div>
                                        </div>
                                        <div className="flex gap-2 ml-4">
                                            {!alreadyInstalled ? (
                                                <button
                                                    className="px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-colors"
                                                    style={{
                                                        background: "var(--accent)",
                                                        color: "#fff",
                                                        opacity: pullStatus === "pulling" ? 0.5 : 1,
                                                    }}
                                                    disabled={pullStatus === "pulling"}
                                                    onClick={() => pullModel(model.ollama_id)}
                                                >
                                                    Pull
                                                </button>
                                            ) : (
                                                <span className="px-3 py-1.5 rounded-lg text-[11px] font-medium" style={{
                                                    background: "rgba(80,200,80,0.1)",
                                                    color: "#50c850",
                                                }}>
                                                    Ready
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                        {catalog.length === 0 && (
                            <div className="text-center py-12 text-xs" style={{ color: "var(--text-muted)" }}>
                                No models in catalog. Check <code>resources/models_catalog.json</code>.
                            </div>
                        )}
                    </div>
                )}

                {/* Installed Tab */}
                {activeTab === "installed" && (
                    <div className="grid gap-3">
                        {installed.length === 0 ? (
                            <div className="text-center py-12 rounded-xl" style={{
                                background: "var(--bg-card)",
                                border: "1px solid var(--border)",
                                color: "var(--text-muted)",
                            }}>
                                <p className="text-xs">No models installed. Ensure Ollama is running and pull a model from the Catalog tab.</p>
                            </div>
                        ) : installed.map(model => (
                            <div key={model.name} className="rounded-xl p-4 flex items-center justify-between" style={{
                                background: "var(--bg-card)",
                                border: "1px solid var(--border)",
                            }}>
                                <div>
                                    <h3 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                                        {model.name}
                                    </h3>
                                    <div className="flex gap-4 mt-1 text-[10px]" style={{ color: "var(--text-muted)" }}>
                                        <span>{formatSize(model.size)}</span>
                                        <span>Modified: {new Date(model.modified_at).toLocaleDateString()}</span>
                                    </div>
                                </div>
                                <button
                                    className="px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors"
                                    style={{
                                        background: "rgba(255,80,80,0.08)",
                                        color: "#ff6060",
                                        border: "1px solid rgba(255,80,80,0.15)",
                                    }}
                                    onClick={() => deleteModel(model.name)}
                                >
                                    Remove
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Hardware & Runtimes Tab */}
                {activeTab === "hardware" && runtime && (
                    <div className="grid gap-4">
                        {/* Hardware Details */}
                        <div className="rounded-xl p-5" style={{
                            background: "var(--bg-card)",
                            border: "1px solid var(--border)",
                        }}>
                            <h3 className="text-xs font-bold mb-3" style={{ color: "var(--text-primary)" }}>
                                Detected Hardware
                            </h3>
                            <div className="grid grid-cols-2 gap-y-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                                <div>CPU Cores</div><div className="font-mono">{runtime.capabilities.cpu_cores}</div>
                                <div>System RAM</div><div className="font-mono">{runtime.capabilities.ram_gb} GB</div>
                                <div>GPU</div><div className="font-mono">{runtime.capabilities.gpu_name || runtime.capabilities.gpu}</div>
                                <div>VRAM</div><div className="font-mono">{runtime.capabilities.vram_gb > 0 ? `${runtime.capabilities.vram_gb} GB` : "N/A"}</div>
                                <div>Compute Mode</div><div className="font-mono">{runtime.compute_mode}</div>
                            </div>
                        </div>

                        {/* Available Runtimes */}
                        <div className="rounded-xl p-5" style={{
                            background: "var(--bg-card)",
                            border: "1px solid var(--border)",
                        }}>
                            <h3 className="text-xs font-bold mb-3" style={{ color: "var(--text-primary)" }}>
                                Available Runtimes
                            </h3>
                            <div className="grid gap-2">
                                {runtime.available.map(rt => (
                                    <div key={rt.id} className="flex items-center justify-between p-3 rounded-lg" style={{
                                        background: "var(--bg-app)",
                                        border: `1px solid ${rt.id === runtime.active ? "var(--accent)" : "var(--border)"}`,
                                    }}>
                                        <div>
                                            <div className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                                                {rt.name}
                                                {rt.id === runtime.active && (
                                                    <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full" style={{
                                                        background: "rgba(100,140,255,0.1)",
                                                        color: "var(--accent)",
                                                    }}>
                                                        Active
                                                    </span>
                                                )}
                                            </div>
                                            <div className="text-[10px] mt-0.5" style={{ color: "var(--text-muted)" }}>
                                                {rt.capabilities?.join(", ")}
                                            </div>
                                        </div>
                                        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full" style={{
                                            background: rt.status === "ready" ? "rgba(80,200,80,0.1)" :
                                                        rt.status === "not_installed" ? "rgba(255,160,40,0.1)" :
                                                        "rgba(255,80,80,0.1)",
                                            color: rt.status === "ready" ? "#50c850" :
                                                   rt.status === "not_installed" ? "#ffa040" :
                                                   "#ff6060",
                                        }}>
                                            {rt.status}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Task-Role Assignments */}
                        <div className="rounded-xl p-5" style={{
                            background: "var(--bg-card)",
                            border: "1px solid var(--border)",
                        }}>
                            <h3 className="text-xs font-bold mb-3" style={{ color: "var(--text-primary)" }}>
                                Task-Role Model Assignments
                            </h3>
                            <div className="grid gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                                {[
                                    { role: "Evidence Synthesis", desc: "Literature search and summarization", recommended: "BioMistral-7B" },
                                    { role: "Molecule Design", desc: "SMILES generation and property prediction", recommended: "Llama-3-8B-Instruct" },
                                    { role: "Embeddings", desc: "Biomedical text embedding", recommended: "PubMedBERT" },
                                    { role: "Clinical Reasoning", desc: "Guidelines interpretation, PICO analysis", recommended: "Meditron-70B" },
                                    { role: "General Reasoning", desc: "Chain-of-thought, planning, dossier drafting", recommended: "Gemma-2-9B-Instruct" },
                                    { role: "Lightweight Tasks", desc: "Quick classification, extraction, triage", recommended: "Phi-3-mini-4k" },
                                ].map(item => (
                                    <div key={item.role} className="flex items-center justify-between p-3 rounded-lg" style={{
                                        background: "var(--bg-app)",
                                        border: "1px solid var(--border)",
                                    }}>
                                        <div>
                                            <div className="font-semibold" style={{ color: "var(--text-primary)" }}>
                                                {item.role}
                                            </div>
                                            <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                                                {item.desc}
                                            </div>
                                        </div>
                                        <div className="text-[10px] font-mono px-2 py-0.5 rounded" style={{
                                            background: "rgba(100,140,255,0.08)",
                                            color: "var(--accent)",
                                        }}>
                                            {item.recommended}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
