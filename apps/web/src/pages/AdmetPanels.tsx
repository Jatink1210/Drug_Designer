import { Pill, Activity, BarChart4 } from "lucide-react";

export default function AdmetPanels() {
    const panels = ["Absorption", "Distribution", "Metabolism", "Excretion", "Toxicity", "Synthesis (SA)"];

    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">Property / ADMET Panels</h1>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">Deep inspection of calculated physicochemical properties and ADMETox profiles.</p>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                    {panels.map((p, i) => (
                        <div key={i} className="glass-card p-5 border border-border flex flex-col transition-all hover:-translate-y-1 cursor-not-allowed opacity-70">
                            <div className="flex justify-between items-start mb-4">
                                <h3 className="text-sm font-semibold text-[var(--text-primary)]">{p}</h3>
                                <Activity size={14} className="text-[var(--text-muted)]" />
                            </div>
                            <div className="h-1 w-full bg-surface rounded-full overflow-hidden mb-3">
                                <div className="h-full bg-border" style={{ width: "20%" }}></div>
                            </div>
                            <span className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] font-mono">No Active Target</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
