/** Source Explorer Page */
import { Database, Link2, CheckCircle, Activity, Globe } from "lucide-react";

export default function SourceExplorer() {
    const sources = [
        { name: "OpenTargets", type: "Genetics / Targets", status: "online", ping: "45ms", records: "Millions" },
        { name: "UniProt", type: "Proteomics", status: "online", ping: "80ms", records: "250M+" },
        { name: "PubMed Central", type: "Literature", status: "online", ping: "120ms", records: "36M+" },
        { name: "ChEMBL", type: "Chemical Biology", status: "online", ping: "55ms", records: "2M+" },
        { name: "KEGG", type: "Pathways", status: "degraded", ping: "400ms", records: "Standardized" },
        { name: "String-DB", type: "Protein Interactions", status: "online", ping: "110ms", records: "Dense" }
    ];

    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6 flex items-center justify-between">
                    <div>
                        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Source Explorer</h1>
                        <p className="text-xs text-[var(--text-muted)] mt-0.5">Inspect the active scientific databases powering the inference engines.</p>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)] px-3 py-1.5 rounded-full border border-border bg-surface shadow-sm">
                        <Activity size={14} className="text-green-500" /> Evidence Pipeline Active
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {sources.map((s, idx) => (
                        <div key={idx} className="glass-card p-5 hover:-translate-y-1 transition-transform cursor-pointer relative overflow-hidden group">
                            <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                                <Database size={64} />
                            </div>
                            <div className="flex items-center justify-between mb-4 relative z-10">
                                <div className="text-sm font-semibold text-[var(--text-primary)]">{s.name}</div>
                                {s.status === "online" ? (
                                    <span className="flex items-center gap-1 text-[10px] bg-green-500/10 text-green-500 px-2 py-0.5 rounded-full border border-green-500/20">
                                        <CheckCircle size={10} /> Online
                                    </span>
                                ) : (
                                    <span className="flex items-center gap-1 text-[10px] bg-amber-500/10 text-amber-500 px-2 py-0.5 rounded-full border border-amber-500/20">
                                        <Activity size={10} /> Degraded
                                    </span>
                                )}
                            </div>
                            <div className="space-y-2 relative z-10">
                                <div className="flex items-center justify-between text-xs text-[var(--text-secondary)] border-b border-border/50 pb-1">
                                    <span className="flex items-center gap-1.5"><Globe size={12}/> Domain</span>
                                    <span>{s.type}</span>
                                </div>
                                <div className="flex items-center justify-between text-xs text-[var(--text-secondary)] border-b border-border/50 pb-1">
                                    <span className="flex items-center gap-1.5"><Activity size={12}/> Latency</span>
                                    <span className="font-mono">{s.ping}</span>
                                </div>
                                <div className="flex items-center justify-between text-xs text-[var(--text-secondary)] pb-1">
                                    <span className="flex items-center gap-1.5"><Link2 size={12}/> Est. Volume</span>
                                    <span>{s.records}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
