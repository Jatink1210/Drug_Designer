import { useState, useEffect } from "react";
import { FileSpreadsheet, PlusCircle, Download, Loader2, Trash2, Eye } from "lucide-react";
import { ensureApiBase } from "@/lib/api";

type DossierMeta = { job_id: string; title: string; created_at: string; sections: string[] };

export default function DossiersPage() {
    const [dossiers, setDossiers] = useState<DossierMeta[]>([]);
    const [loading, setLoading] = useState(true);
    const [preview, setPreview] = useState<any>(null);

    const load = async () => {
        setLoading(true);
        try {
            const base = await ensureApiBase();
            // Load dossiers from job list
            const jobsRes = await fetch(`${base}/jobs`);
            if (jobsRes.ok) {
                const jobs: any[] = await jobsRes.json();
                const dList: DossierMeta[] = [];
                for (const j of jobs.slice(0, 20)) {
                    try {
                        const dr = await fetch(`${base}/jobs/${j.id || j.job_id}/dossier?format=json`);
                        if (dr.ok) {
                            const d = await dr.json();
                            dList.push({ job_id: j.id || j.job_id, title: d.title || j.query || "Untitled", created_at: d.meta?.created_at || "", sections: Object.keys(d).filter(k => k !== "meta") });
                        }
                    } catch { /* skip */ }
                }
                setDossiers(dList);
            }
        } catch { /* */ }
        setLoading(false);
    };

    const viewDossier = async (jobId: string) => {
        const base = await ensureApiBase();
        const res = await fetch(`${base}/jobs/${jobId}/dossier?format=json`);
        if (res.ok) setPreview(await res.json());
    };

    const downloadHTML = async (jobId: string) => {
        const base = await ensureApiBase();
        const res = await fetch(`${base}/jobs/${jobId}/dossier?format=html`);
        if (res.ok) {
            const html = await res.text();
            const blob = new Blob([html], { type: "text/html" });
            const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `dossier_${jobId}.html`; a.click();
        }
    };

    useEffect(() => { load(); }, []);

    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6 flex justify-between items-center">
                    <div>
                        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Decision Dossiers</h1>
                        <p className="text-xs text-[var(--text-muted)] mt-0.5">The canonical compiled output object housing project hypotheses, target rankings, and evidence links.</p>
                    </div>
                </div>

                {loading && <div className="flex justify-center py-20"><Loader2 size={24} className="animate-spin text-[var(--accent)]" /></div>}

                {!loading && dossiers.length === 0 && !preview && (
                    <div className="glass-card w-full h-[500px] flex flex-col items-center justify-center border-dashed border-2 border-border/60">
                        <FileSpreadsheet className="text-[var(--border)] mb-4" size={56} />
                        <span className="text-sm text-[var(--text-primary)] mt-2">Dossier Repository Empty</span>
                        <span className="text-xs text-[var(--text-muted)] mt-1 max-w-sm text-center">Run an Evidence Search or Disease Intelligence workflow to auto-generate dossiers from completed jobs.</span>
                    </div>
                )}

                {!loading && dossiers.length > 0 && !preview && (
                    <div className="space-y-3">
                        {dossiers.map(d => (
                            <div key={d.job_id} className="glass-card p-4 flex items-center justify-between group hover:border-[var(--accent)] transition-colors">
                                <div className="flex-1 min-w-0">
                                    <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">{d.title}</h3>
                                    <p className="text-[10px] text-[var(--text-muted)] mt-0.5">Job: {d.job_id} • {d.sections.length} sections</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button onClick={() => viewDossier(d.job_id)} className="glass-button text-xs px-3 py-1 flex items-center gap-1"><Eye size={12} /> View</button>
                                    <button onClick={() => downloadHTML(d.job_id)} className="glass-button text-xs px-3 py-1 flex items-center gap-1"><Download size={12} /> HTML</button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {preview && (
                    <div className="glass-card p-6">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-base font-semibold text-[var(--text-primary)]">Dossier Preview</h2>
                            <button onClick={() => setPreview(null)} className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]">← Back to list</button>
                        </div>
                        <pre className="text-xs text-[var(--text-secondary)] bg-[var(--bg-app)] p-4 rounded-lg overflow-auto max-h-[600px] font-mono whitespace-pre-wrap">{JSON.stringify(preview, null, 2)}</pre>
                    </div>
                )}
            </div>
        </div>
    );
}
