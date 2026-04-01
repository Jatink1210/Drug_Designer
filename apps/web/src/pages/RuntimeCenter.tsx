import { Cpu, Server, Laptop, ChevronRight, Activity } from "lucide-react";

export default function RuntimeCenter() {
    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">Runtime Center</h1>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">Manage execution flow paths across hosted endpoints, AirLLM optimization engines, and local Llama inference.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="glass-card p-6 border-l-[3px] border-l-[#10b981] relative overflow-hidden group hover:bg-surface/50 cursor-pointer transition-colors">
                        <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                            <Server size={64} />
                        </div>
                        <div className="flex justify-between items-center mb-4 relative z-10">
                            <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                                <Server size={18} className="text-[#10b981]" /> Hosted Execution Fabric
                            </h2>
                            <span className="text-[10px] bg-[#10b981]/10 text-[#10b981] px-2 py-1 rounded border border-[#10b981]/20">Active/Default</span>
                        </div>
                        <p className="text-xs text-[var(--text-secondary)] mb-4 relative z-10">
                            Fast API cloud inference pipeline. Connects to primary external APIs, handles huge graph queries via Neo4J, and proxies basic inference calls to commercial models.
                        </p>
                        <div className="flex items-center text-xs text-[#10b981] font-medium relative z-10">
                            <Activity size={14} className="mr-1.5" /> Checking 5 Nodes...
                        </div>
                    </div>

                    <div className="glass-card p-6 border-l-[3px] border-l-amber-500 relative overflow-hidden group hover:bg-surface/50 cursor-pointer transition-colors">
                        <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                            <Laptop size={64} />
                        </div>
                        <div className="flex justify-between items-center mb-4 relative z-10">
                            <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                                <Laptop size={18} className="text-amber-500" /> Local Runtime Agent
                            </h2>
                            <span className="text-[10px] bg-amber-500/10 text-amber-500 px-2 py-1 rounded border border-amber-500/20">Standby</span>
                        </div>
                        <p className="text-xs text-[var(--text-secondary)] mb-4 relative z-10">
                            Private, decoupled inference execution. Requires the Local Agent companion application running on port :11434 to host llama.cpp architectures securely on this machine.
                        </p>
                        <div className="flex items-center text-xs text-amber-500 font-medium relative z-10">
                            Configure Agent <ChevronRight size={14} />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
