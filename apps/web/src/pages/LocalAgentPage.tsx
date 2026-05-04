/** LocalAgentPage — Local Runtime Agent installation, connection status, and GPU tier guide. */

import { useState, useEffect } from "react";
import { Monitor, Download, Server, Shield, Cpu, HardDrive, MemoryStick } from "lucide-react";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";

interface AgentStatus {
  connected: boolean;
  port: number;
  lastCheck: string;
  gpu?: { name: string; vram: string; driver: string };
}

// J-6: Real hardware capability types from /hardware/capabilities (pynvml)
interface GPUInfo {
  available: boolean;
  count: number;
  name: string;
  vram_gb: number;
  vram_free_gb: number;
  source: string;
  devices?: Array<{ index: number; name: string; vram_total_gb: number; vram_free_gb: number; vram_used_gb: number }>;
}

interface HardwareCapabilities {
  cpu: { count: number; name: string; freq_mhz?: number };
  ram: { total_gb: number; available_gb: number; used_pct: number };
  gpu: GPUInfo;
  disk: { total_gb: number; free_gb: number; used_pct: number };
  model_cache: Array<{ name: string; source: string; size_gb: number }>;
  dispatch_recommendations: Record<string, string>;
}

export default function LocalAgentPage() {
  const [status, setStatus] = useState<AgentStatus>({
    connected: false,
    port: 4133,
    lastCheck: "2s ago",
  });
  const [hw, setHw] = useState<HardwareCapabilities | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);

  useEffect(() => {
    const checkAgent = async () => {
      try {
        const res = await fetch("http://localhost:4133/health", {
          signal: AbortSignal.timeout(2000),
        });
        if (res.ok) {
          const data = await res.json();
          setStatus({ connected: true, port: 4133, lastCheck: "just now", gpu: data.gpu });
          // J-6: Fetch real hardware capabilities after connection confirmed
          try {
            const hwRes = await fetch("http://localhost:4133/hardware/capabilities", {
              signal: AbortSignal.timeout(5000),
            });
            if (hwRes.ok) setHw(await hwRes.json());
          } catch { /* hw fetch optional */ }
        }
      } catch {
        setStatus((s) => ({ ...s, connected: false, lastCheck: "2s ago" }));
      } finally {
        setInitialLoading(false);
      }
    };
    checkAgent();
    const id = setInterval(checkAgent, 10_000);
    return () => clearInterval(id);
  }, []);

  const tiers = [
    {
      tier: "Minimal",
      gpu: "None (CPU only)",
      vram: "—",
      models: "ESM-C 600M, PubMedBERT, ChemBERTa",
      perf: "Embedding only, 5-15s/query",
    },
    {
      tier: "Basic",
      gpu: "GTX 1660 / RTX 2060",
      vram: "6 GB",
      models: "+ Llama 3 8B (Q4)",
      perf: "Full RAG, 2-5s/query",
    },
    {
      tier: "Recommended",
      gpu: "RTX 3080 / 4070",
      vram: "10-12 GB",
      models: "+ Llama 3 8B (Q8), Mixtral",
      perf: "Full pipeline, 1-3s/query",
    },
    {
      tier: "Optimal",
      gpu: "RTX 4090 / A100",
      vram: "24+ GB",
      models: "+ Llama 3 70B (Q4), BioMistral",
      perf: "Multi-model, <1s/query",
    },
  ];

  const viewState: ViewState = initialLoading ? "loading" : "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="Local Agent"
      loadingMessage="Checking local agent status…"
    >
    <div
      className="flex-1 overflow-y-auto p-8"
      style={{ background: "var(--bg-app)" }}
    >
      <h1
        className="text-xl mb-1"
        style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
      >
        Local Runtime Agent
      </h1>
      <p className="text-xs mb-6" style={{ color: "var(--text-muted)" }}>
        Optional companion daemon for GPU telemetry, local model management, and
        secure hardware-aware execution
      </p>

      {/* Connection status */}
      <div
        className="p-5 mb-6"
        style={{
          border: "1px solid var(--border)",
          background: "var(--bg-surface)",
        }}
      >
        <div className="flex items-center gap-3 mb-3">
          <Monitor
            size={28}
            style={{ color: status.connected ? "#2D8B5F" : "#C43D2F" }}
          />
          <div>
            <div
              className="text-sm font-semibold"
              style={{ color: status.connected ? "#2D8B5F" : "#C43D2F" }}
            >
              {status.connected ? "Agent Connected" : "Agent Not Detected"}
            </div>
            <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>
              Port {status.port} · {status.connected ? "Active" : "No response"}{" "}
              · Last check: {status.lastCheck}
            </div>
          </div>
        </div>
        {/* Progress bar */}
        <div
          className="w-full h-1.5 rounded-full"
          style={{ background: "var(--border)" }}
        >
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: status.connected ? "100%" : "5%",
              background: status.connected ? "#2D8B5F" : "#C43D2F",
            }}
          />
        </div>
        <div
          className="text-[10px] mt-1"
          style={{ color: "var(--text-muted)" }}
        >
          Connection: {status.connected ? "100%" : "0%"} ·{" "}
          {status.connected ? "Healthy" : "Retrying every 10s"}
        </div>
      </div>

      {/* J-6: Real hardware metrics panel (visible when connected + hw data available) */}
      {status.connected && hw && (
        <div className="mb-6 p-5" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
          <div className="section-label mb-4">Hardware Capabilities</div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            {/* GPU VRAM */}
            <div className="p-3" style={{ border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-2 mb-2">
                <Cpu size={14} style={{ color: "var(--accent)" }} />
                <span className="text-[11px] font-semibold">{hw.gpu.name || "No GPU"}</span>
              </div>
              {hw.gpu.available ? (
                <>
                  <div className="flex justify-between text-[10px] mb-1" style={{ color: "var(--text-secondary)" }}>
                    <span>VRAM</span>
                    <span>{hw.gpu.vram_free_gb.toFixed(1)} / {hw.gpu.vram_gb.toFixed(1)} GB free</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full" style={{ background: "var(--border)" }}>
                    <div className="h-full rounded-full transition-all" style={{
                      width: `${Math.round(((hw.gpu.vram_gb - hw.gpu.vram_free_gb) / hw.gpu.vram_gb) * 100)}%`,
                      background: hw.gpu.vram_free_gb / hw.gpu.vram_gb > 0.4 ? "#2D8B5F" : "#E5A91A",
                    }} />
                  </div>
                  <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>
                    source: {hw.gpu.source}
                  </div>
                </>
              ) : (
                <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>CPU-only mode</div>
              )}
            </div>
            {/* RAM */}
            <div className="p-3" style={{ border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-2 mb-2">
                <MemoryStick size={14} style={{ color: "var(--accent)" }} />
                <span className="text-[11px] font-semibold">System RAM</span>
              </div>
              <div className="flex justify-between text-[10px] mb-1" style={{ color: "var(--text-secondary)" }}>
                <span>RAM</span>
                <span>{hw.ram.available_gb.toFixed(1)} / {hw.ram.total_gb.toFixed(1)} GB free</span>
              </div>
              <div className="h-1.5 w-full rounded-full" style={{ background: "var(--border)" }}>
                <div className="h-full rounded-full transition-all" style={{
                  width: `${hw.ram.used_pct}%`,
                  background: hw.ram.used_pct < 70 ? "#2D8B5F" : hw.ram.used_pct < 85 ? "#E5A91A" : "#C43D2F",
                }} />
              </div>
              <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>{hw.ram.used_pct}% used</div>
            </div>
            {/* CPU */}
            <div className="p-3" style={{ border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-2 mb-2">
                <Server size={14} style={{ color: "var(--accent)" }} />
                <span className="text-[11px] font-semibold">CPU</span>
              </div>
              <div className="text-[11px]" style={{ color: "var(--text-secondary)" }}>
                {hw.cpu.count} cores{hw.cpu.freq_mhz ? ` · ${(hw.cpu.freq_mhz / 1000).toFixed(1)} GHz` : ""}
              </div>
              <div className="text-[10px] mt-1 truncate" style={{ color: "var(--text-muted)" }}>{hw.cpu.name}</div>
            </div>
            {/* Disk */}
            <div className="p-3" style={{ border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-2 mb-2">
                <HardDrive size={14} style={{ color: "var(--accent)" }} />
                <span className="text-[11px] font-semibold">Disk</span>
              </div>
              <div className="flex justify-between text-[10px] mb-1" style={{ color: "var(--text-secondary)" }}>
                <span>Free</span>
                <span>{hw.disk.free_gb.toFixed(0)} / {hw.disk.total_gb.toFixed(0)} GB</span>
              </div>
              <div className="h-1.5 w-full rounded-full" style={{ background: "var(--border)" }}>
                <div className="h-full rounded-full" style={{
                  width: `${hw.disk.used_pct}%`,
                  background: hw.disk.used_pct < 80 ? "#2D8B5F" : "#E5A91A",
                }} />
              </div>
              <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>{hw.disk.used_pct}% used</div>
            </div>
          </div>
          {/* Model cache */}
          {hw.model_cache.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                Model Cache ({hw.model_cache.length} models · {hw.model_cache.reduce((s, m) => s + m.size_gb, 0).toFixed(1)} GB)
              </div>
              <div className="flex flex-wrap gap-2">
                {hw.model_cache.slice(0, 8).map((m) => (
                  <span key={m.name} className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--border)", color: "var(--text-secondary)" }}>
                    {m.name} · {m.size_gb.toFixed(1)} GB
                  </span>
                ))}
                {hw.model_cache.length > 8 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--border)", color: "var(--text-muted)" }}>
                    +{hw.model_cache.length - 8} more
                  </span>
                )}
              </div>
            </div>
          )}
          {/* Dispatch recommendations */}
          <div className="mt-3">
            <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>Dispatch Routing</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(hw.dispatch_recommendations).map(([model, route]) => (
                <span key={model} className="text-[10px] px-2 py-0.5 font-mono" style={{
                  border: "1px solid var(--border)",
                  color: route.startsWith("local") ? "#2D8B5F" : route === "hosted_api" ? "var(--text-muted)" : "var(--text-secondary)",
                }}>
                  {model}: {route}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* What the agent provides */}
      <div className="mb-6">
        <div className="section-label mb-3">What the Local Agent Provides</div>
        <div className="grid grid-cols-3 gap-4">
          {[
            {
              icon: <Cpu size={18} />,
              title: "GPU Detection",
              desc: "Automatic NVIDIA/AMD GPU detection via CUDA/ROCm. PCIe bandwidth, VRAM capacity, and utilization monitoring.",
            },
            {
              icon: <Server size={18} />,
              title: "Model Management",
              desc: "Download, install, and serve models locally. Ollama integration. Quantization-aware recommendations (Q4, Q5, Q8, FP16).",
            },
            {
              icon: <Shield size={18} />,
              title: "Secure Handshake",
              desc: "Encrypted communication between browser app and local daemon. Trust boundary enforcement. No data leaves the machine.",
            },
          ].map((c) => (
            <div
              key={c.title}
              className="p-4"
              style={{
                border: "1px solid var(--border)",
                background: "var(--bg-surface)",
              }}
            >
              <div className="mb-2" style={{ color: "var(--accent)" }}>
                {c.icon}
              </div>
              <div className="text-xs font-semibold mb-1">{c.title}</div>
              <div
                className="text-[11px]"
                style={{ color: "var(--text-secondary)" }}
              >
                {c.desc}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Installation */}
      <div className="mb-6">
        <div className="section-label mb-3">Installation</div>
        <div
          className="text-xs"
          style={{ color: "var(--text-secondary)", lineHeight: 2 }}
        >
          <strong>Step 1:</strong> Download the Local Runtime Agent for your
          platform
          <div className="flex gap-2 my-2">
            <button className="btn-primary px-3 py-1.5 text-[11px] flex items-center gap-1">
              <Download size={11} /> Windows (.msi)
            </button>
            <button
              className="px-3 py-1.5 text-[11px] border rounded flex items-center gap-1"
              style={{ borderColor: "var(--border)" }}
            >
              <Download size={11} /> macOS (.dmg)
            </button>
            <button
              className="px-3 py-1.5 text-[11px] border rounded flex items-center gap-1"
              style={{ borderColor: "var(--border)" }}
            >
              <Download size={11} /> Linux (.deb)
            </button>
          </div>
          <strong>Step 2:</strong> Run the installer and start the daemon
          <div className="my-1">
            <code
              className="text-[11px] px-2 py-1"
              style={{
                background: "var(--bg-surface)",
                fontFamily: "var(--font-mono)",
              }}
            >
              drug-designer-agent serve --port 4133
            </code>
          </div>
          <strong>Step 3:</strong> Return here — the agent will be auto-detected
        </div>
      </div>

      {/* GPU tier table */}
      <div className="mb-6">
        <div className="section-label mb-3">System Requirements</div>
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-left py-2 px-3">Tier</th>
              <th className="text-left py-2 px-3">GPU</th>
              <th className="text-left py-2 px-3">VRAM</th>
              <th className="text-left py-2 px-3">Capable Models</th>
              <th className="text-left py-2 px-3">Performance</th>
            </tr>
          </thead>
          <tbody>
            {tiers.map((t) => (
              <tr key={t.tier}>
                <td className="py-2 px-3 font-semibold">{t.tier}</td>
                <td
                  className="py-2 px-3"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {t.gpu}
                </td>
                <td className="py-2 px-3">{t.vram}</td>
                <td
                  className="py-2 px-3"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {t.models}
                </td>
                <td
                  className="py-2 px-3"
                  style={{ color: "var(--text-muted)" }}
                >
                  {t.perf}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
    </StateWrapper>
  );
}
