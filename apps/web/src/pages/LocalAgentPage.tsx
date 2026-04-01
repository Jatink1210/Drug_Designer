/** LocalAgentPage — Local Runtime Agent installation, connection status, and GPU tier guide. */

import { useState, useEffect } from "react";
import { Monitor, Download, Server, Shield, Cpu } from "lucide-react";

interface AgentStatus {
    connected: boolean;
    port: number;
    lastCheck: string;
    gpu?: { name: string; vram: string; driver: string };
}

export default function LocalAgentPage() {
    const [status, setStatus] = useState<AgentStatus>({
        connected: false,
        port: 4133,
        lastCheck: "2s ago",
    });

    useEffect(() => {
        const checkAgent = async () => {
            try {
                const res = await fetch("http://localhost:4133/health", {
                    signal: AbortSignal.timeout(2000),
                });
                if (res.ok) {
                    const data = await res.json();
                    setStatus({
                        connected: true,
                        port: 4133,
                        lastCheck: "just now",
                        gpu: data.gpu,
                    });
                }
            } catch {
                setStatus(s => ({ ...s, connected: false, lastCheck: "2s ago" }));
            }
        };
        checkAgent();
        const id = setInterval(checkAgent, 10_000);
        return () => clearInterval(id);
    }, []);

    const tiers = [
        { tier: "Minimal", gpu: "None (CPU only)", vram: "—", models: "ESM2-8M, PubMedBERT, ChemBERTa", perf: "Embedding only, 5-15s/query" },
        { tier: "Basic", gpu: "GTX 1660 / RTX 2060", vram: "6 GB", models: "+ Llama 3 8B (Q4)", perf: "Full RAG, 2-5s/query" },
        { tier: "Recommended", gpu: "RTX 3080 / 4070", vram: "10-12 GB", models: "+ Llama 3 8B (Q8), Mixtral", perf: "Full pipeline, 1-3s/query" },
        { tier: "Optimal", gpu: "RTX 4090 / A100", vram: "24+ GB", models: "+ Llama 3 70B (Q4), BioMistral", perf: "Multi-model, <1s/query" },
    ];

    return (
        <div className="flex-1 overflow-y-auto p-8" style={{ background: "var(--bg-app)" }}>
            <h1
                className="text-xl mb-1"
                style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
            >
                Local Runtime Agent
            </h1>
            <p className="text-xs mb-6" style={{ color: "var(--text-muted)" }}>
                Optional companion daemon for GPU telemetry, local model management, and secure hardware-aware execution
            </p>

            {/* Connection status */}
            <div
                className="p-5 mb-6"
                style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}
            >
                <div className="flex items-center gap-3 mb-3">
                    <Monitor size={28} style={{ color: status.connected ? "#2D8B5F" : "#C43D2F" }} />
                    <div>
                        <div className="text-sm font-semibold" style={{ color: status.connected ? "#2D8B5F" : "#C43D2F" }}>
                            {status.connected ? "Agent Connected" : "Agent Not Detected"}
                        </div>
                        <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                            Port {status.port} · {status.connected ? "Active" : "No response"} · Last check: {status.lastCheck}
                        </div>
                    </div>
                </div>
                {/* Progress bar */}
                <div className="w-full h-1.5 rounded-full" style={{ background: "var(--border)" }}>
                    <div
                        className="h-full rounded-full transition-all"
                        style={{
                            width: status.connected ? "100%" : "5%",
                            background: status.connected ? "#2D8B5F" : "#C43D2F",
                        }}
                    />
                </div>
                <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>
                    Connection: {status.connected ? "100%" : "0%"} · {status.connected ? "Healthy" : "Retrying every 10s"}
                </div>
            </div>

            {/* What the agent provides */}
            <div className="mb-6">
                <div className="section-label mb-3">What the Local Agent Provides</div>
                <div className="grid grid-cols-3 gap-4">
                    {[
                        { icon: <Cpu size={18} />, title: "GPU Detection", desc: "Automatic NVIDIA/AMD GPU detection via CUDA/ROCm. PCIe bandwidth, VRAM capacity, and utilization monitoring." },
                        { icon: <Server size={18} />, title: "Model Management", desc: "Download, install, and serve models locally. Ollama integration. Quantization-aware recommendations (Q4, Q5, Q8, FP16)." },
                        { icon: <Shield size={18} />, title: "Secure Handshake", desc: "Encrypted communication between browser app and local daemon. Trust boundary enforcement. No data leaves the machine." },
                    ].map(c => (
                        <div key={c.title} className="p-4" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
                            <div className="mb-2" style={{ color: "var(--accent)" }}>{c.icon}</div>
                            <div className="text-xs font-semibold mb-1">{c.title}</div>
                            <div className="text-[11px]" style={{ color: "var(--text-secondary)" }}>{c.desc}</div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Installation */}
            <div className="mb-6">
                <div className="section-label mb-3">Installation</div>
                <div className="text-xs" style={{ color: "var(--text-secondary)", lineHeight: 2 }}>
                    <strong>Step 1:</strong> Download the Local Runtime Agent for your platform
                    <div className="flex gap-2 my-2">
                        <button className="btn-primary px-3 py-1.5 text-[11px] flex items-center gap-1"><Download size={11} /> Windows (.msi)</button>
                        <button className="px-3 py-1.5 text-[11px] border rounded flex items-center gap-1" style={{ borderColor: "var(--border)" }}><Download size={11} /> macOS (.dmg)</button>
                        <button className="px-3 py-1.5 text-[11px] border rounded flex items-center gap-1" style={{ borderColor: "var(--border)" }}><Download size={11} /> Linux (.deb)</button>
                    </div>
                    <strong>Step 2:</strong> Run the installer and start the daemon
                    <div className="my-1">
                        <code className="text-[11px] px-2 py-1" style={{ background: "var(--bg-surface)", fontFamily: "var(--font-mono)" }}>
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
                        {tiers.map(t => (
                            <tr key={t.tier}>
                                <td className="py-2 px-3 font-semibold">{t.tier}</td>
                                <td className="py-2 px-3" style={{ color: "var(--text-secondary)" }}>{t.gpu}</td>
                                <td className="py-2 px-3">{t.vram}</td>
                                <td className="py-2 px-3" style={{ color: "var(--text-secondary)" }}>{t.models}</td>
                                <td className="py-2 px-3" style={{ color: "var(--text-muted)" }}>{t.perf}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
