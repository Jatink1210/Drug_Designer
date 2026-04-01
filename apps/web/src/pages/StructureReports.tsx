import { NotebookPen, Download } from "lucide-react";

export default function StructureReports() {
    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6 flex justify-between items-center">
                    <div>
                        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Structure-linked Reports</h1>
                        <p className="text-xs text-[var(--text-muted)] mt-0.5">Formal PDF reports detailing PDB resolution scores, AlphaFold confidences, and Pocket detection logs.</p>
                    </div>
                </div>

                <div className="glass-card flex flex-col items-center justify-center p-14 text-center border border-border">
                    <NotebookPen size={45} className="text-[#10b981]/50 mb-5" />
                    <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-2">No Structure Reports Accessible</h2>
                    <p className="text-xs text-[var(--text-secondary)] max-w-sm mb-6">
                        Reports are automatically compiled downstream of any docking execution or structural inference workflow. Ensure a project is loaded to view historical reports.
                    </p>
                    <button className="glass-button text-xs font-mono">Run Scaffold Parser</button>
                </div>
            </div>
        </div>
    );
}
