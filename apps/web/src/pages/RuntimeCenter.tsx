import { useState, useEffect, useCallback } from "react";
import { Cpu, Server, Laptop, ChevronRight, Activity, Zap, CheckCircle, AlertTriangle, RefreshCw } from "lucide-react";
import { ensureApiBase } from "@/lib/api";

interface RuntimeStatus {
  active_mode: string;
  active_engine: string;
  selected_model: string;
  capabilities: {
    cpu_cores: number;
    ram_gb: number;
    gpu: string;
    gpu_name: string | null;
    vram_gb: number;
    airllm_installed: boolean;
  };
}

export default function RuntimeCenter() {
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    setFetchError(null);
    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/runtime/status`, { cache: "no-store" });
      if (res.ok) {
        const json = await res.json();
        setStatus(json.data || json);
      } else {
        setFetchError(`Server returned ${res.status}`);
      }
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : "Failed to reach backend");
    }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const switchMode = async (mode: string, engine: string) => {
    setSwitching(true);
    setSwitchError(null);
    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/runtime/select-mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, target_engine: engine }),
      });
      if (!res.ok) setSwitchError(`Failed to switch: ${res.status}`);
      await loadStatus();
    } catch (err) {
      setSwitchError(err instanceof Error ? err.message : "Switch failed");
    }
    finally { setSwitching(false); }
  };

  const caps = status?.capabilities;
  const hasGPU = caps?.gpu === "cuda" || caps?.gpu === "mps";

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-[1100px] mx-auto px-6 py-5">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
              Runtime Center
            </h1>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
              Manage execution paths — hosted endpoints, AirLLM optimization, and local Llama inference.
            </p>
          </div>
          <button
            onClick={() => { setLoading(true); loadStatus(); }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-medium"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        {/* Error states */}
        {fetchError && (
          <div className="rounded-xl p-4 mb-6 flex items-center gap-3" style={{ background: "rgba(239, 68, 68, 0.06)", border: "1px solid rgba(239, 68, 68, 0.2)" }}>
            <AlertTriangle size={16} style={{ color: "#ef4444" }} />
            <div className="flex-1">
              <div className="text-xs font-semibold" style={{ color: "#ef4444" }}>Failed to load runtime status</div>
              <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{fetchError}</div>
            </div>
            <button onClick={() => { setLoading(true); loadStatus(); }} className="text-xs underline" style={{ color: "#ef4444" }}>Retry</button>
          </div>
        )}
        {switchError && (
          <div className="rounded-xl p-3 mb-4 flex items-center gap-2 text-xs" style={{ background: "rgba(245, 158, 11, 0.06)", border: "1px solid rgba(245, 158, 11, 0.2)", color: "#f59e0b" }}>
            <AlertTriangle size={13} /> {switchError}
            <button onClick={() => setSwitchError(null)} className="ml-auto underline text-[10px]">Dismiss</button>
          </div>
        )}

        {/* Active Configuration Banner */}
        {status && (
          <div className="rounded-xl p-4 mb-6" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="flex items-center gap-6 text-xs" style={{ color: "var(--text-secondary)" }}>
              <div className="flex items-center gap-1.5">
                <Zap size={13} style={{ color: "var(--accent)" }} />
                <span style={{ color: "var(--text-muted)" }}>Engine</span>
                <strong>{status.active_engine}</strong>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>Mode </span>
                <strong>{status.active_mode}</strong>
              </div>
              {status.selected_model && (
                <div>
                  <span style={{ color: "var(--text-muted)" }}>Model </span>
                  <strong style={{ color: "var(--accent)" }}>{status.selected_model}</strong>
                </div>
              )}
              <div>
                <span style={{ color: "var(--text-muted)" }}>CPU </span>
                <strong>{caps?.cpu_cores} cores</strong>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>RAM </span>
                <strong>{caps?.ram_gb} GB</strong>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>GPU </span>
                <strong>{caps?.gpu_name || caps?.gpu || "none"}</strong>
              </div>
              {caps?.airllm_installed && (
                <div className="flex items-center gap-1">
                  <CheckCircle size={11} style={{ color: "#10b981" }} />
                  <span style={{ color: "#10b981", fontWeight: 600 }}>AirLLM</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Runtime Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {/* Hosted / Ollama */}
          <div
            className="card p-5 relative overflow-hidden group cursor-pointer transition-colors"
            style={{
              borderLeft: `3px solid ${status?.active_engine === "llama.cpp" ? "#10b981" : "var(--border)"}`,
              opacity: switching ? 0.6 : 1,
            }}
            onClick={() => !switching && switchMode("cpu", "llama.cpp")}
          >
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-sm font-semibold flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
                <Server size={16} className="text-[#10b981]" /> Ollama / Llama.cpp
              </h2>
              {status?.active_engine === "llama.cpp" && (
                <span className="text-[9px] bg-[#10b981]/10 text-[#10b981] px-2 py-0.5 rounded font-semibold">Active</span>
              )}
            </div>
            <p className="text-[11px] mb-3" style={{ color: "var(--text-muted)" }}>
              Local Ollama server on port 11434. Fast, private, runs quantized models. Ideal for 7B–13B models.
            </p>
            <div className="text-[10px] font-medium" style={{ color: "#10b981" }}>
              <Activity size={11} className="inline mr-1" /> Ready for CPU inference
            </div>
          </div>

          {/* AirLLM */}
          <div
            className="card p-5 relative overflow-hidden group cursor-pointer transition-colors"
            style={{
              borderLeft: `3px solid ${status?.active_engine === "airllm" ? "#8b5cf6" : "var(--border)"}`,
              opacity: switching ? 0.6 : 1,
            }}
            onClick={() => !switching && switchMode("cpu", "airllm")}
          >
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-sm font-semibold flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
                <Zap size={16} className="text-[#8b5cf6]" /> AirLLM
              </h2>
              {status?.active_engine === "airllm" && (
                <span className="text-[9px] bg-[#8b5cf6]/10 text-[#8b5cf6] px-2 py-0.5 rounded font-semibold">Active</span>
              )}
            </div>
            <p className="text-[11px] mb-3" style={{ color: "var(--text-muted)" }}>
              Split-layer inference for massive models (26B–70B). Runs on 4GB VRAM via layer-wise CPU offloading.
            </p>
            <div className="text-[10px] font-medium" style={{ color: caps?.airllm_installed ? "#8b5cf6" : "#f59e0b" }}>
              {caps?.airllm_installed ? (
                <><CheckCircle size={11} className="inline mr-1" /> Package installed</>
              ) : (
                <><AlertTriangle size={11} className="inline mr-1" /> Requires: pip install airllm</>
              )}
            </div>
          </div>

          {/* Remote / OpenAI */}
          <div
            className="card p-5 relative overflow-hidden group cursor-pointer transition-colors"
            style={{
              borderLeft: `3px solid ${status?.active_engine === "remote" ? "#3b82f6" : "var(--border)"}`,
              opacity: switching ? 0.6 : 1,
            }}
            onClick={() => !switching && switchMode("cpu", "remote")}
          >
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-sm font-semibold flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
                <Cpu size={16} className="text-[#3b82f6]" /> Remote API
              </h2>
              {status?.active_engine === "remote" && (
                <span className="text-[9px] bg-[#3b82f6]/10 text-[#3b82f6] px-2 py-0.5 rounded font-semibold">Active</span>
              )}
            </div>
            <p className="text-[11px] mb-3" style={{ color: "var(--text-muted)" }}>
              OpenAI-compatible API endpoint. Use with GPT-4, Claude, LM Studio, or any compatible server.
            </p>
            <div className="text-[10px] font-medium" style={{ color: "#3b82f6" }}>
              <Server size={11} className="inline mr-1" /> Requires API key in Settings
            </div>
          </div>
        </div>

        {/* Hardware capability details */}
        {caps && (
          <div className="rounded-xl p-5" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <h3 className="text-xs font-bold mb-3" style={{ color: "var(--text-primary)" }}>
              Hardware Capabilities
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-3 rounded-lg" style={{ background: "var(--bg-app)" }}>
                <div className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{caps.cpu_cores}</div>
                <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>CPU Cores</div>
              </div>
              <div className="text-center p-3 rounded-lg" style={{ background: "var(--bg-app)" }}>
                <div className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{caps.ram_gb} GB</div>
                <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>System RAM</div>
              </div>
              <div className="text-center p-3 rounded-lg" style={{ background: "var(--bg-app)" }}>
                <div className="text-lg font-bold" style={{ color: hasGPU ? "#10b981" : "var(--text-muted)" }}>
                  {caps.gpu_name || caps.gpu}
                </div>
                <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>GPU</div>
              </div>
              <div className="text-center p-3 rounded-lg" style={{ background: "var(--bg-app)" }}>
                <div className="text-lg font-bold" style={{ color: caps.vram_gb > 0 ? "#10b981" : "var(--text-muted)" }}>
                  {caps.vram_gb > 0 ? `${caps.vram_gb} GB` : "N/A"}
                </div>
                <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>VRAM</div>
              </div>
            </div>

            {/* Model compatibility guidance */}
            <div className="mt-4 p-3 rounded-lg text-[11px]" style={{ background: "rgba(139,92,246,0.05)", border: "1px solid rgba(139,92,246,0.1)" }}>
              <div className="font-semibold mb-1" style={{ color: "#8b5cf6" }}>Hardware → Model Guidance</div>
              <div style={{ color: "var(--text-secondary)" }}>
                {caps.ram_gb >= 32 ? "✓ Can run 26B+ models via AirLLM split-layer inference" :
                 caps.ram_gb >= 16 ? "✓ Can run 7B–13B models locally, 26B via AirLLM with disk offloading" :
                 caps.ram_gb >= 8 ? "✓ Can run 7B quantized models (Q4_K_M)" :
                 "⚠ Limited RAM — use remote API or lightweight models"}
                {hasGPU && caps.vram_gb >= 8 && " | GPU acceleration available for faster inference"}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
