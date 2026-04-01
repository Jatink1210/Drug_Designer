import { History, Target } from "lucide-react";

export default function HistoricalQueries() {
    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6 flex justify-between items-start">
                    <div>
                        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Historical Queries</h1>
                        <p className="text-xs text-[var(--text-muted)] mt-0.5">Log traces of executed Search payloads across semantic and lexical indices.</p>
                    </div>
                </div>

                <div className="glass-card p-6 border border-border/50 bg-black/20">
                    <div className="flex items-center justify-center py-20 opacity-50">
                        <History size={30} className="text-[var(--text-muted)] mr-3" />
                        <span className="text-sm font-mono text-[var(--text-secondary)]">Query vector cache perfectly empty.</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
