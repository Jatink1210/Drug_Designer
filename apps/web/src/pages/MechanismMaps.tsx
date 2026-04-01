import { GitMerge, Map } from "lucide-react";

export default function MechanismMaps() {
    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6 flex items-center justify-between">
                    <div>
                        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Mechanism Maps</h1>
                        <p className="text-xs text-[var(--text-muted)] mt-0.5">Trace the specific mechanistic cascade from molecular perturbation to phenotypic resolution.</p>
                    </div>
                </div>

                <div className="glass-card border border-border p-12 text-center rounded-xl flex flex-col items-center justify-center min-h-[500px]">
                    <GitMerge size={50} className="text-[#6060ff]/30 mb-6" />
                    <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Mechanistic Modeling Offline</h2>
                    <p className="text-xs text-[var(--text-muted)] max-w-lg mx-auto">
                        Inference of novel drug mechanisms requires activating a local LLM pathway annotator in the Runtime Center. Currently waiting for agentic directives from the Task Orchestrator.
                    </p>
                </div>
            </div>
        </div>
    );
}
