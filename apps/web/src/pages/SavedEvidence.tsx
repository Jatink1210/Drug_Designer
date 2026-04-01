import { Bookmark, Search } from "lucide-react";

export default function SavedEvidence() {
    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">Saved Evidence Sets</h1>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">Collections of curated scientific literature and extracted claims for project context.</p>
                </div>
                <div className="glass-card flex flex-col items-center justify-center p-12 text-center border-dashed border-[var(--border)]">
                    <Bookmark size={40} className="text-[var(--text-muted)] mb-4" />
                    <h3 className="text-sm font-medium text-[var(--text-primary)] mb-2">No Saved Evidence</h3>
                    <p className="text-xs text-[var(--text-muted)] max-w-sm mb-6">You haven't pinned any evidence sets to your Project Memory. Use the Evidence Search module to curate bundles.</p>
                    <button className="glass-button text-xs flex items-center gap-2 px-6 py-2">
                        <Search size={14} /> Go to Evidence Search
                    </button>
                </div>
            </div>
        </div>
    );
}
