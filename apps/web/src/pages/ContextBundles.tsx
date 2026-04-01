import { Archive, Layers } from "lucide-react";

export default function ContextBundles() {
    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">Saved Context Bundles</h1>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">L0-L2 conversational memory architectures saved for swift context resurrection.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <div className="glass-card p-6 border border-dashed border-border flex flex-col items-center justify-center min-h-[200px] text-center hover:bg-surface/50 cursor-pointer transition-colors">
                        <Layers size={24} className="text-[var(--text-muted)] mb-3" />
                        <span className="text-xs text-[var(--text-primary)] font-medium">Capture Session Context</span>
                        <span className="text-[10px] text-[var(--text-secondary)] mt-1">Snapshot the active agentic workflow</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
