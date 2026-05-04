/** SetupWizard — 3-step onboarding: mode → connect → confirm model.
 *
 * Key design decisions:
 * - Local mode probes existing servers (Ollama, LM Studio) — no forced download.
 * - Remote mode lets user enter any OpenAI-compatible endpoint.
 * - Cross-tab sync via localStorage so other tabs don't re-trigger setup.
 * - AirLLM fallback for local hardware without a running server.
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Loader2,
  Cpu,
  Globe,
  Server,
  CheckCircle2,
  Star,
  Wand2,
  XCircle,
  Wifi,
  WifiOff,
  RefreshCw,
  ArrowRight,
  ArrowLeft,
  Zap,
} from "lucide-react";
import {
  runtimesListAPI,
  runtimesRecommendAPI,
  modelsCatalogAPI,
  settingsUpdateAPI,
  settingsGetAPI,
  probeEndpointAPI,
  type RuntimesResponse,
  type RecommendResponse,
  type ModelCatalogEntry,
  type ProbeResult,
} from "@/lib/api";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";

/** Default endpoints for well-known local LLM servers. */
const LOCAL_ENDPOINTS = [
  { name: "Ollama", url: "http://localhost:11434", icon: "🦙" },
  { name: "LM Studio", url: "http://localhost:1234", icon: "🔬" },
  { name: "text-generation-webui", url: "http://localhost:5000", icon: "🌐" },
  { name: "vLLM", url: "http://localhost:8000", icon: "⚡" },
  { name: "LocalAI", url: "http://localhost:8080", icon: "🤖" },
];

type RunMode = "local" | "remote" | "hosted";

export default function SetupWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState<RunMode>("local");
  const [endpointUrl, setEndpointUrl] = useState("http://localhost:11434");
  const [apiKey, setApiKey] = useState("");
  const [probeResult, setProbeResult] = useState<ProbeResult | null>(null);
  const [probing, setProbing] = useState(false);
  const [selectedModel, setSelectedModel] = useState("");
  const [autoProbed, setAutoProbed] = useState(false);

  const { data: runtimesInfo, isLoading: loadingRuntimes } =
    useQuery<RuntimesResponse>({
      queryKey: ["runtimes"],
      queryFn: runtimesListAPI,
    });
  const { data: catalog } = useQuery<ModelCatalogEntry[]>({
    queryKey: ["catalog"],
    queryFn: modelsCatalogAPI,
  });

  const saveSettings = useMutation({
    mutationFn: (s: Record<string, unknown>) => settingsUpdateAPI(s),
    onSuccess: () => {
      // Broadcast to all tabs via localStorage
      localStorage.setItem("dss_setup_complete", "true");
      navigate("/search");
    },
  });

  // Auto-redirect if already set up
  useEffect(() => {
    if (localStorage.getItem("dss_setup_complete") === "true") {
      navigate("/search");
      return;
    }
    settingsGetAPI()
      .then((data) => {
        if (data && data.setup_complete) {
          localStorage.setItem("dss_setup_complete", "true");
          navigate("/search");
        }
      })
      .catch(() => {});
  }, [navigate]);

  // Auto-probe local endpoints when user selects "local" mode and advances to step 2
  const probeEndpoint = useCallback(async (url: string) => {
    setProbing(true);
    setProbeResult(null);
    try {
      const result = await probeEndpointAPI(url);
      setProbeResult(result);
      if (result.reachable && result.models.length > 0) {
        setSelectedModel(result.models[0].name);
      }
    } catch {
      setProbeResult({ reachable: false, server_type: "unknown", models: [], endpoint: url });
    }
    setProbing(false);
  }, []);

  // Auto-probe all local endpoints when entering step 2 in local mode
  useEffect(() => {
    if (step === 2 && mode === "local" && !autoProbed) {
      setAutoProbed(true);
      probeEndpoint(endpointUrl);
    }
  }, [step, mode, autoProbed, endpointUrl, probeEndpoint]);

  const caps = runtimesInfo?.capabilities;
  const hasGpu = caps ? caps.gpu !== "none" && caps.gpu !== "unknown" : false;

  const handleComplete = () => {
    const runtimeId = mode === "hosted" ? "remote" :
      probeResult?.server_type === "ollama" ? "llama.cpp" :
      probeResult?.server_type === "openai_compat" ? "remote" :
      "llama.cpp";

    saveSettings.mutate({
      compute_mode: mode === "hosted" ? "remote" : hasGpu ? "gpu" : "cpu",
      runtime: runtimeId,
      model_id: selectedModel || "BioMistral-7B",
      remote_base_url: mode === "hosted" ? endpointUrl : (probeResult?.endpoint || endpointUrl),
      setup_complete: true,
    });
  };

  const viewState: ViewState = loadingRuntimes ? "loading" : "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="Setup"
      emptyTitle="No runtimes detected"
      emptyDescription="Could not detect available runtimes."
      onRetry={() => window.location.reload()}
    >
      <div
        className="min-h-screen w-full flex flex-col items-center justify-center p-4 overflow-y-auto"
        style={{ backgroundColor: "var(--bg-app)" }}
      >
        <div className="w-full max-w-2xl card rounded-xl p-8">
          {/* Header */}
          <h1
            className="text-2xl font-semibold mb-1"
            style={{ color: "var(--text-primary)" }}
          >
            Welcome to Drug Designer
          </h1>
          <p className="mb-6 text-sm" style={{ color: "var(--text-secondary)" }}>
            Connect your AI engine in 3 steps — no downloads required.
          </p>

          {/* Progress bar */}
          <div className="flex items-center gap-2 mb-8">
            {[1, 2, 3].map((s) => (
              <div key={s} className="flex-1 flex items-center gap-2">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                    s <= step
                      ? "text-white"
                      : "text-[var(--text-muted)] border border-[var(--border)]"
                  }`}
                  style={s <= step ? { background: "var(--accent)" } : {}}
                >
                  {s < step ? <CheckCircle2 size={14} /> : s}
                </div>
                {s < 3 && (
                  <div
                    className="flex-1 h-0.5 rounded"
                    style={{
                      background: s < step ? "var(--accent)" : "var(--border)",
                    }}
                  />
                )}
              </div>
            ))}
          </div>

          {/* ── Step 1: Choose Mode ── */}
          {step === 1 && (
            <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4">
              <h2 className="text-lg font-medium" style={{ color: "var(--text-primary)" }}>
                Where should AI run?
              </h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Choose how to connect to an LLM. You can change this later in Settings.
              </p>

              <div className="grid grid-cols-3 gap-3">
                {/* Local */}
                <button
                  onClick={() => { setMode("local"); setEndpointUrl("http://localhost:11434"); }}
                  className={`p-4 border rounded-lg text-left transition-all ${
                    mode === "local" ? "ring-2 ring-[var(--accent)] border-transparent" : ""
                  }`}
                  style={{ borderColor: "var(--border)", background: mode === "local" ? "var(--bg-app)" : undefined }}
                >
                  <Cpu className="mb-2 text-[var(--accent)]" size={20} />
                  <div className="font-medium text-sm">Local Server</div>
                  <div className="text-[10px] text-green-600 mt-0.5">No downloads needed</div>
                  <div className="text-[10px] text-[var(--text-muted)] mt-1">
                    Connect to Ollama, LM Studio, or any local LLM server already running on your machine.
                  </div>
                </button>

                {/* Remote Server */}
                <button
                  onClick={() => { setMode("remote"); setEndpointUrl(""); }}
                  className={`p-4 border rounded-lg text-left transition-all ${
                    mode === "remote" ? "ring-2 ring-[var(--accent)] border-transparent" : ""
                  }`}
                  style={{ borderColor: "var(--border)", background: mode === "remote" ? "var(--bg-app)" : undefined }}
                >
                  <Server className="mb-2" size={20} />
                  <div className="font-medium text-sm">Remote Server</div>
                  <div className="text-[10px] text-blue-600 mt-0.5">Self-hosted or LAN</div>
                  <div className="text-[10px] text-[var(--text-muted)] mt-1">
                    Connect to a remote OpenAI-compatible server on your network or cloud.
                  </div>
                </button>

                {/* Hosted API */}
                <button
                  onClick={() => { setMode("hosted"); setEndpointUrl("https://api.openai.com/v1"); }}
                  className={`p-4 border rounded-lg text-left transition-all ${
                    mode === "hosted" ? "ring-2 ring-[var(--accent)] border-transparent" : ""
                  }`}
                  style={{ borderColor: "var(--border)", background: mode === "hosted" ? "var(--bg-app)" : undefined }}
                >
                  <Globe className="mb-2" size={20} />
                  <div className="font-medium text-sm">Cloud API</div>
                  <div className="text-[10px] text-purple-600 mt-0.5">OpenAI, Anthropic, etc.</div>
                  <div className="text-[10px] text-[var(--text-muted)] mt-1">
                    Use a hosted API with your API key. Works with any OpenAI-compatible provider.
                  </div>
                </button>
              </div>

              {/* Hardware info */}
              {caps && (
                <div className="px-3 py-2 rounded-lg border text-xs" style={{ borderColor: "var(--border)" }}>
                  <span className="font-medium" style={{ color: "var(--text-primary)" }}>Your Hardware: </span>
                  <span style={{ color: "var(--text-secondary)" }}>
                    {caps.cpu_cores} CPU cores, {caps.ram_gb} GB RAM
                    {hasGpu ? `, ${caps.gpu_name} (${caps.vram_gb} GB VRAM)` : ", no GPU detected"}
                  </span>
                </div>
              )}

              <div className="flex justify-end pt-2">
                <button
                  onClick={() => { setStep(2); setAutoProbed(false); }}
                  className="px-5 py-2 text-sm font-medium text-white rounded-lg hover:opacity-90 flex items-center gap-2"
                  style={{ background: "var(--accent)" }}
                >
                  Next <ArrowRight size={14} />
                </button>
              </div>
            </div>
          )}

          {/* ── Step 2: Connect to Server ── */}
          {step === 2 && (
            <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4">
              <h2 className="text-lg font-medium" style={{ color: "var(--text-primary)" }}>
                {mode === "local" ? "Connect to Local Server" :
                 mode === "remote" ? "Connect to Remote Server" :
                 "Configure Cloud API"}
              </h2>

              {/* Local mode — quick-connect buttons */}
              {mode === "local" && (
                <div className="space-y-3">
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Select a running local server or enter a custom endpoint. We'll detect available models automatically.
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    {LOCAL_ENDPOINTS.map((ep) => (
                      <button
                        key={ep.url}
                        onClick={() => { setEndpointUrl(ep.url); probeEndpoint(ep.url); }}
                        className={`px-3 py-2 border rounded-lg text-left text-xs transition-all flex items-center gap-2 ${
                          endpointUrl === ep.url ? "ring-2 ring-[var(--accent)] border-transparent" : ""
                        }`}
                        style={{ borderColor: "var(--border)" }}
                      >
                        <span className="text-base">{ep.icon}</span>
                        <div>
                          <div className="font-medium">{ep.name}</div>
                          <div className="text-[10px] text-[var(--text-muted)]">{ep.url}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Endpoint URL input (all modes) */}
              <div className="space-y-2">
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                  {mode === "hosted" ? "API Base URL" : "Server Endpoint"}
                </label>
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={endpointUrl}
                    onChange={(e) => setEndpointUrl(e.target.value)}
                    placeholder={mode === "hosted" ? "https://api.openai.com/v1" : "http://localhost:11434"}
                    className="flex-1 px-3 py-2 text-sm border rounded-lg"
                    style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
                  />
                  <button
                    onClick={() => probeEndpoint(endpointUrl)}
                    disabled={probing || !endpointUrl}
                    className="px-4 py-2 text-sm font-medium text-white rounded-lg hover:opacity-90 disabled:opacity-40 flex items-center gap-2"
                    style={{ background: "var(--accent)" }}
                  >
                    {probing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                    Test
                  </button>
                </div>
              </div>

              {/* API Key (hosted/remote only) */}
              {(mode === "hosted" || mode === "remote") && (
                <div className="space-y-2">
                  <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                    API Key <span className="text-[var(--text-muted)]">(optional for local servers)</span>
                  </label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-..."
                    className="w-full px-3 py-2 text-sm border rounded-lg"
                    style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
                  />
                </div>
              )}

              {/* Probe result */}
              {probeResult && (
                <div
                  className={`p-3 rounded-lg border text-xs ${
                    probeResult.reachable
                      ? "bg-green-50 border-green-200"
                      : "bg-red-50 border-red-200"
                  }`}
                >
                  {probeResult.reachable ? (
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Wifi size={12} className="text-green-600" />
                        <span className="font-medium text-green-800">
                          Connected — {probeResult.server_type === "ollama" ? "Ollama" :
                            probeResult.server_type === "openai_compat" ? "OpenAI-compatible" : "Server"} detected
                        </span>
                      </div>
                      {probeResult.models.length > 0 && (
                        <div className="text-green-700">
                          {probeResult.models.length} model{probeResult.models.length > 1 ? "s" : ""} available
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <WifiOff size={12} className="text-red-500" />
                      <span className="text-red-700">
                        Cannot reach server at {endpointUrl}. Make sure it's running.
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* AirLLM fallback hint for local */}
              {mode === "local" && probeResult && !probeResult.reachable && (
                <div className="p-3 rounded-lg border border-amber-200 bg-amber-50 text-xs">
                  <div className="flex items-center gap-2 mb-1">
                    <Zap size={12} className="text-amber-600" />
                    <span className="font-medium text-amber-800">No local server detected</span>
                  </div>
                  <p className="text-amber-700">
                    Start <strong>Ollama</strong> ({`"`}ollama serve{`"`}) or <strong>LM Studio</strong> on your machine,
                    then click Test again. You can also use AirLLM for direct hardware inference — configure it in Settings after setup.
                  </p>
                </div>
              )}

              <div className="flex justify-between pt-2">
                <button
                  onClick={() => setStep(1)}
                  className="px-4 py-2 text-sm flex items-center gap-1"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <ArrowLeft size={14} /> Back
                </button>
                <button
                  onClick={() => setStep(3)}
                  disabled={mode !== "hosted" && !probeResult?.reachable && !endpointUrl}
                  className="px-5 py-2 text-sm font-medium text-white rounded-lg hover:opacity-90 disabled:opacity-40 flex items-center gap-2"
                  style={{ background: "var(--accent)" }}
                >
                  Next <ArrowRight size={14} />
                </button>
              </div>
            </div>
          )}

          {/* ── Step 3: Select Model ── */}
          {step === 3 && (
            <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4">
              <h2 className="text-lg font-medium" style={{ color: "var(--text-primary)" }}>
                Select Your Model
              </h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {probeResult?.reachable && probeResult.models.length > 0
                  ? "These models are already available on your server — no download needed."
                  : "Choose a model from our biomedical catalog. You can install models later in Settings."}
              </p>

              <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
                {/* Models from probed server */}
                {probeResult?.reachable && probeResult.models.length > 0 && (
                  <>
                    <div className="text-xs font-medium px-1 pt-1" style={{ color: "var(--text-secondary)" }}>
                      Available on {probeResult.server_type === "ollama" ? "Ollama" : "server"}:
                    </div>
                    {probeResult.models.map((m) => (
                      <button
                        key={m.name}
                        onClick={() => setSelectedModel(m.name)}
                        className={`w-full p-3 border rounded-lg text-left transition-all ${
                          selectedModel === m.name ? "ring-2 ring-[var(--accent)] border-transparent" : ""
                        }`}
                        style={{ borderColor: "var(--border)", background: selectedModel === m.name ? "var(--bg-app)" : undefined }}
                      >
                        <div className="flex items-center gap-2">
                          <CheckCircle2
                            size={12}
                            className={selectedModel === m.name ? "text-[var(--accent)]" : "text-green-500"}
                          />
                          <span className="font-medium text-sm">{m.name}</span>
                          <span className="text-[10px] text-green-600 ml-auto flex items-center gap-1">
                            <Wifi size={8} /> Ready
                          </span>
                        </div>
                        {m.size > 0 && (
                          <div className="text-[10px] text-[var(--text-muted)] mt-1 ml-5">
                            {(m.size / 1e9).toFixed(1)} GB
                          </div>
                        )}
                      </button>
                    ))}
                  </>
                )}

                {/* Catalog models (shown if no probed models or for reference) */}
                {(catalog && catalog.length > 0) && (
                  <>
                    {probeResult?.reachable && probeResult.models.length > 0 && (
                      <div className="text-xs font-medium px-1 pt-3" style={{ color: "var(--text-secondary)" }}>
                        From catalog (may need to install):
                      </div>
                    )}
                    {catalog
                      .filter((m) => {
                        // If we have server models, don't duplicate them
                        if (probeResult?.models.some((pm) => pm.name.includes(m.name) || m.name.includes(pm.name))) {
                          return false;
                        }
                        return true;
                      })
                      .slice(0, 6)
                      .map((m) => (
                        <button
                          key={m.name}
                          onClick={() => setSelectedModel(m.name)}
                          className={`w-full p-3 border rounded-lg text-left transition-all ${
                            selectedModel === m.name ? "ring-2 ring-[var(--accent)] border-transparent" : ""
                          }`}
                          style={{ borderColor: "var(--border)", background: selectedModel === m.name ? "var(--bg-app)" : undefined }}
                        >
                          <div className="flex items-center gap-2">
                            <Star size={10} className="text-amber-400" />
                            <span className="font-medium text-sm">{m.name}</span>
                            <span className="text-[10px] text-[var(--text-muted)] ml-auto">
                              {m.parameters} / {m.size_gb} GB
                            </span>
                          </div>
                          <p className="text-[10px] text-[var(--text-muted)] mt-1 ml-5">
                            {m.description}
                          </p>
                          <div className="flex gap-1 mt-1.5 ml-5">
                            {(m.tags ?? []).slice(0, 3).map((t) => (
                              <span
                                key={t}
                                className="text-[9px] bg-[var(--bg-inset)] rounded px-1.5 py-0.5"
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        </button>
                      ))}
                  </>
                )}

                {(!probeResult?.models?.length && (!catalog || catalog.length === 0)) && (
                  <p className="text-xs text-center py-4" style={{ color: "var(--text-muted)" }}>
                    No models detected. You can configure models later in Settings.
                  </p>
                )}
              </div>

              <div className="flex justify-between pt-2">
                <button
                  onClick={() => setStep(2)}
                  disabled={saveSettings.isPending}
                  className="px-4 py-2 text-sm flex items-center gap-1"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <ArrowLeft size={14} /> Back
                </button>
                <button
                  onClick={handleComplete}
                  disabled={saveSettings.isPending}
                  className="px-5 py-2 text-sm font-medium text-white rounded-lg flex items-center gap-2 hover:opacity-90 disabled:opacity-40"
                  style={{ background: "var(--accent)" }}
                >
                  {saveSettings.isPending ? (
                    <Loader2 className="animate-spin" size={14} />
                  ) : (
                    <CheckCircle2 size={14} />
                  )}
                  {selectedModel ? "Launch Drug Designer" : "Skip & Launch"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </StateWrapper>
  );
}
