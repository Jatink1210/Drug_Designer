/** SetupWizard — 3-step onboarding with auto-detect and model compatibility. */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Loader2, Cpu, HardDrive, CheckCircle2, Star, Wand2, XCircle } from "lucide-react";
import {
    runtimesListAPI, runtimesRecommendAPI, modelsCatalogAPI, settingsUpdateAPI,
    modelsPullAPI, settingsGetAPI,
    type RuntimesResponse, type RecommendResponse, type ModelCatalogEntry,
} from "@/lib/api";

export default function SetupWizard() {
    const navigate = useNavigate();
    const [step, setStep] = useState(1);
    const [compute, setCompute] = useState("auto");
    const [runtime, setRuntime] = useState("llama.cpp");
    const [modelId, setModelId] = useState("");
    const [rec, setRec] = useState<RecommendResponse | null>(null);
    const [autoLoading, setAutoLoading] = useState(false);

    const { data: runtimesInfo, isLoading: loadingRuntimes } = useQuery<RuntimesResponse>({
        queryKey: ["runtimes"], queryFn: runtimesListAPI,
    });
    const { data: catalog, isLoading: loadingCatalog } = useQuery<ModelCatalogEntry[]>({
        queryKey: ["catalog"], queryFn: modelsCatalogAPI,
    });

    const saveSettings = useMutation({
        mutationFn: (s: Record<string, unknown>) => settingsUpdateAPI(s),
        onSuccess: () => navigate("/search"),
    });

    const pullModel = useMutation({
        mutationFn: (id: string) => modelsPullAPI(id),
    });

    // Auto-redirect if already setup
    useEffect(() => {
        settingsGetAPI().then(data => {
            if (data && data.setup_complete) navigate("/search");
        }).catch(() => {});
    }, [navigate]);

    const handleAutoDetect = async () => {
        setAutoLoading(true);
        try {
            const result = await runtimesRecommendAPI();
            setRec(result);
            setCompute(result.compute_mode);
            if (result.recommended_model) setModelId(result.recommended_model.name);
        } catch { /* ignore */ }
        setAutoLoading(false);
    };

    if (loadingRuntimes || loadingCatalog) {
        return <div className="h-screen w-screen flex items-center justify-center"><Loader2 className="animate-spin text-gray-400" /></div>;
    }

    const caps = runtimesInfo?.capabilities;
    const hasGpu = caps ? caps.gpu !== "none" && caps.gpu !== "unknown" : false;
    const hasAirLlm = caps?.airllm_installed === true;

    const compatibleCatalog = catalog?.filter(m => {
        const mode = compute === "auto" ? (hasGpu ? "gpu" : "cpu") : compute;
        return m.compute_modes.includes(mode);
    }) || [];

    const handleComplete = async () => {
        const selectedModel = catalog?.find(m => m.name === modelId);
        if (runtime !== "remote" && selectedModel) {
            await pullModel.mutateAsync(selectedModel.ollama_id);
        }
        saveSettings.mutate({
            compute_mode: compute,
            runtime,
            model_id: modelId,
            setup_complete: true,
        });
    };

    return (
        <div className="h-screen w-screen flex flex-col items-center justify-center" style={{ backgroundColor: "var(--bg-app)" }}>
            <div className="w-full max-w-2xl glass-card rounded-xl p-8">
                <h1 className="text-2xl font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Welcome to Drug Designer</h1>
                <p className="mb-8" style={{ color: "var(--text-secondary)" }}>Let's configure your local AI workspace.</p>

                {/* Step 1: Compute */}
                {step === 1 && (
                    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4">
                        <h2 className="text-lg font-medium" style={{ color: "var(--text-primary)" }}>1. Select Compute Mode</h2>
                        <div className="grid grid-cols-3 gap-3">
                            <button onClick={() => { setCompute("auto"); handleAutoDetect(); }}
                                className={`p-4 border rounded-lg text-left transition-all ${compute === "auto" ? "ring-2 ring-[var(--accent)] border-transparent bg-[var(--bg-app)]" : ""}`}
                                style={{ borderColor: "var(--border)" }}>
                                <Wand2 className="mb-2 text-[var(--accent)]" size={20} />
                                <div className="font-medium text-sm">Auto-Detect</div>
                                <div className="text-xs text-[var(--accent)] mt-0.5">Recommended</div>
                                <div className="text-[10px] text-gray-500 mt-1">Best config for your hardware</div>
                            </button>
                            <button onClick={() => setCompute("cpu")}
                                className={`p-4 border rounded-lg text-left transition-all ${compute === "cpu" ? "ring-2 ring-[var(--accent)] border-transparent bg-[var(--bg-app)]" : ""}`}
                                style={{ borderColor: "var(--border)" }}>
                                <Cpu className="mb-2" size={20} />
                                <div className="font-medium text-sm">CPU</div>
                                <div className="text-xs text-gray-500">{caps?.cpu_cores} Cores / {caps?.ram_gb} GB RAM</div>
                            </button>
                            <button onClick={() => { if (hasGpu) setCompute("gpu"); }}
                                disabled={!hasGpu}
                                className={`p-4 border rounded-lg text-left transition-all ${compute === "gpu" ? "ring-2 ring-[var(--accent)] border-transparent bg-[var(--bg-app)]" : ""} ${!hasGpu ? "opacity-40 cursor-not-allowed" : ""}`}
                                style={{ borderColor: "var(--border)" }}>
                                <HardDrive className="mb-2" size={20} />
                                <div className="font-medium text-sm">GPU</div>
                                <div className="text-xs text-gray-500">{hasGpu ? caps?.gpu_name : "No compatible GPU"}</div>
                            </button>
                        </div>

                        {autoLoading && (
                            <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                                <Loader2 size={12} className="animate-spin" /> Analyzing hardware...
                            </div>
                        )}

                        {rec && rec.recommended_model && (
                            <div className="px-3 py-2 rounded-lg bg-green-50 border border-green-200 text-xs">
                                <span className="font-medium text-green-800">Detected:</span>{" "}
                                <span className="text-green-700">{rec.compute_mode.toUpperCase()}</span>{" "}
                                <span className="text-green-600">with {rec.recommended_model.name}</span>
                            </div>
                        )}

                        <div className="flex justify-end pt-4">
                            <button onClick={() => setStep(2)} className="px-5 py-2 text-sm font-medium text-white rounded-lg hover:opacity-90" style={{ background: "var(--accent)" }}>Next</button>
                        </div>
                    </div>
                )}

                {/* Step 2: Runtime */}
                {step === 2 && (
                    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4">
                        <h2 className="text-lg font-medium" style={{ color: "var(--text-primary)" }}>2. Select Engine Runtime</h2>
                        <div className="space-y-3">
                            {runtimesInfo?.available.map((r) => (
                                <button key={r.id} onClick={() => setRuntime(r.id)}
                                    disabled={r.id === "airllm" && !hasAirLlm}
                                    className={`w-full p-4 border rounded-lg text-left flex items-center justify-between transition-all ${runtime === r.id ? "ring-2 ring-[var(--accent)] border-transparent bg-[var(--bg-app)]" : ""} ${r.id === "airllm" && !hasAirLlm ? "opacity-40" : ""}`}
                                    style={{ borderColor: "var(--border)" }}>
                                    <div>
                                        <div className="font-medium text-sm">{r.name}</div>
                                        <div className="text-xs text-gray-500">Supports: {r.capabilities.join(", ")}</div>
                                    </div>
                                    {r.id === "airllm" && !hasAirLlm && <span className="text-[10px] bg-gray-100 px-2 py-1 rounded">Not Installed</span>}
                                </button>
                            ))}
                        </div>
                        <div className="flex justify-between pt-4">
                            <button onClick={() => setStep(1)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Back</button>
                            <button onClick={() => setStep(3)} className="px-5 py-2 text-sm font-medium text-white rounded-lg hover:opacity-90" style={{ background: "var(--accent)" }}>Next</button>
                        </div>
                    </div>
                )}

                {/* Step 3: Model */}
                {step === 3 && (
                    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4">
                        <h2 className="text-lg font-medium" style={{ color: "var(--text-primary)" }}>3. Select Biomedical Model</h2>
                        <div className="space-y-3 max-h-64 overflow-y-auto pr-2">
                            {compatibleCatalog.map((m) => {
                                const isRecommended = rec?.recommended_model?.name === m.name;
                                const ramOk = caps ? caps.ram_gb >= m.min_ram_gb : true;
                                return (
                                    <button key={m.name} onClick={() => setModelId(m.name)}
                                        className={`w-full p-4 border rounded-lg text-left transition-all ${modelId === m.name ? "ring-2 ring-[var(--accent)] border-transparent bg-[var(--bg-app)]" : ""}`}
                                        style={{ borderColor: "var(--border)" }}>
                                        <div className="flex items-center gap-2">
                                            {isRecommended && <Star size={12} className="text-amber-500 fill-amber-500 shrink-0" />}
                                            <span className="font-medium text-sm">{m.name}</span>
                                            <span className="text-[10px] text-gray-400 ml-auto">{m.parameters} / {m.size_gb} GB</span>
                                        </div>
                                        <p className="text-xs text-gray-500 mt-1">{m.description}</p>
                                        <div className="flex items-center gap-3 mt-2">
                                            <div className="flex gap-1">
                                                {m.tags.map(t => <span key={t} className="text-[9px] bg-gray-100 rounded px-1.5 py-0.5">{t}</span>)}
                                            </div>
                                            <div className="ml-auto flex items-center gap-1 text-[10px]">
                                                {ramOk
                                                    ? <><CheckCircle2 size={10} className="text-green-600" /><span className="text-green-700">Compatible</span></>
                                                    : <><XCircle size={10} className="text-red-500" /><span className="text-red-600">Needs {m.min_ram_gb} GB RAM</span></>
                                                }
                                            </div>
                                        </div>
                                    </button>
                                );
                            })}
                            {compatibleCatalog.length === 0 && (
                                <p className="text-xs text-[var(--text-muted)] py-4 text-center">No compatible models found for selected compute mode.</p>
                            )}
                        </div>

                        {pullModel.isPending && (
                            <div className="p-4 bg-gray-50 rounded-lg border flex items-center gap-3" style={{ borderColor: "var(--border)" }}>
                                <Loader2 className="animate-spin text-gray-500" size={18} />
                                <div className="flex-1">
                                    <div className="text-sm font-medium">Downloading {modelId}...</div>
                                    <p className="text-[10px] text-[var(--text-muted)] mt-1">This may take several minutes depending on model size and connection speed.</p>
                                    <div className="w-full bg-gray-200 h-1.5 rounded mt-2 overflow-hidden">
                                        <div className="bg-[var(--accent)] h-full animate-[indeterminate_1.5s_ease-in-out_infinite]"
                                             style={{ width: "40%", animation: "indeterminate 1.5s ease-in-out infinite" }} />
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="flex justify-between pt-4">
                            <button onClick={() => setStep(2)} disabled={pullModel.isPending || saveSettings.isPending}
                                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Back</button>
                            <button onClick={handleComplete} disabled={!modelId || pullModel.isPending || saveSettings.isPending}
                                className="px-5 py-2 text-sm font-medium text-white rounded-lg flex items-center gap-2 hover:opacity-90 disabled:opacity-40"
                                style={{ background: "var(--accent)" }}>
                                {(pullModel.isPending || saveSettings.isPending) ? <Loader2 className="animate-spin" size={14} /> : <CheckCircle2 size={14} />}
                                Complete Setup
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
