import { useState, useEffect } from 'react';
import { FlaskConical, Plus, ChevronRight, Download, Loader2, AlertCircle } from 'lucide-react';
import { ensureApiBase } from "@/lib/api";

interface Project {
    id: string;
    name: string;
    description: string;
    current_stage: string;
}

export default function TranslationalResearch() {
    const [apiBase, setApiBase] = useState("/api");
    const [projects, setProjects] = useState<Project[]>([]);
    const [newProjectName, setNewProjectName] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);

    useEffect(() => { ensureApiBase().then(setApiBase); }, []);

    useEffect(() => {
        if (apiBase) fetchProjects();
    }, [apiBase]);

    const fetchProjects = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${apiBase}/translational/projects`);
            if (res.ok) {
                setProjects(await res.json());
            } else {
                setError("Failed to load projects.");
            }
        } catch {
            setError("Unable to reach API — check that the backend is running.");
        }
        setLoading(false);
    };

    const createProject = async () => {
        if (!newProjectName) return;
        setActionError(null);
        try {
            const res = await fetch(`${apiBase}/translational/projects`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newProjectName, description: 'Created via web UI' })
            });
            if (res.ok) {
                setNewProjectName('');
                fetchProjects();
            } else {
                setActionError("Failed to create project.");
            }
        } catch {
            setActionError("Network error — could not create project.");
        }
    };

    const advanceStage = async (id: string) => {
        setActionError(null);
        try {
            const res = await fetch(`${apiBase}/translational/projects/${id}/advance`, { method: 'POST' });
            if (res.ok) fetchProjects();
            else setActionError("Failed to advance stage.");
        } catch {
            setActionError("Network error — could not advance stage.");
        }
    };

    const exportReport = async (id: string) => {
        setActionError(null);
        try {
            const res = await fetch(`${apiBase}/translational/projects/${id}/export`);
            if (res.ok) {
                const data = await res.json();
                const markdown = data.markdown_report || "# No report data available";
                const blob = new Blob([markdown], { type: "text/markdown" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `evidence_bundle_${id}.md`;
                a.click();
                URL.revokeObjectURL(url);
            } else {
                setActionError("Failed to export report.");
            }
        } catch {
            setActionError("Network error — could not export report.");
        }
    };

    return (
        <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[900px] mx-auto">
                <div className="flex items-center gap-3 mb-6">
                    <FlaskConical size={20} className="text-[var(--accent)]" />
                    <div>
                        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Translational Research Workflow</h2>
                        <p className="text-xs text-[var(--text-muted)]">Manage translational research projects through structured pipeline stages</p>
                    </div>
                </div>

                {(error || actionError) && (
                    <div className="mb-4 px-4 py-3 rounded-xl border bg-red-50 text-red-700 text-xs flex items-center gap-2" style={{ borderColor: "#fecaca" }}>
                        <AlertCircle size={14} /> {error || actionError}
                    </div>
                )}

                <div className="glass-card rounded-xl p-5 mb-6">
                    <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Initialize New Project</h3>
                    <div className="flex gap-3">
                        <input
                            type="text"
                            value={newProjectName}
                            onChange={(e) => setNewProjectName(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && createProject()}
                            placeholder="Project Name..."
                            className="flex-1 px-3 py-2 text-sm rounded-lg border bg-[var(--bg-app)] text-[var(--text-primary)]"
                            style={{ borderColor: "var(--border)" }}
                        />
                        <button
                            onClick={createProject}
                            className="px-4 py-2 rounded-lg text-white text-sm font-medium flex items-center gap-1.5 transition-opacity hover:opacity-90"
                            style={{ background: "var(--accent)" }}
                        >
                            <Plus size={14} /> Create Project
                        </button>
                    </div>
                </div>

                {loading ? (
                    <div className="flex items-center justify-center py-16 text-[var(--text-muted)]">
                        <Loader2 size={20} className="animate-spin" />
                    </div>
                ) : (
                <div className="space-y-4">
                    {projects.map(p => (
                        <div key={p.id} className="glass-card rounded-xl p-5 border-l-4" style={{ borderLeftColor: "var(--accent)" }}>
                            <div className="flex items-start justify-between mb-3">
                                <div>
                                    <h3 className="text-base font-semibold text-[var(--text-primary)]">{p.name}</h3>
                                    <p className="text-xs text-[var(--text-muted)] mt-0.5">{p.description}</p>
                                </div>
                                <span
                                    className="px-2.5 py-1 text-[10px] font-semibold rounded-full uppercase tracking-wider"
                                    style={{ background: "var(--accent)", color: "white", opacity: 0.9 }}
                                >
                                    {p.current_stage}
                                </span>
                            </div>

                            <div className="flex gap-3 mt-4">
                                <button
                                    onClick={() => advanceStage(p.id)}
                                    disabled={p.current_stage === 'completed'}
                                    className="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors hover:bg-slate-50 disabled:opacity-40 flex items-center gap-1.5 text-[var(--text-primary)]"
                                    style={{ borderColor: "var(--border)" }}
                                >
                                    <ChevronRight size={12} /> Advance Stage
                                </button>

                                <button
                                    onClick={() => exportReport(p.id)}
                                    className="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors hover:bg-slate-50 flex items-center gap-1.5 text-[var(--text-primary)]"
                                    style={{ borderColor: "var(--border)" }}
                                >
                                    <Download size={12} /> Export Evidence Bundle
                                </button>
                            </div>
                        </div>
                    ))}
                    {projects.length === 0 && (
                        <div className="text-center py-12">
                            <FlaskConical size={32} className="mx-auto mb-3 text-slate-300" />
                            <p className="text-sm text-[var(--text-muted)]">No active translational projects. Create one above to get started.</p>
                        </div>
                    )}
                </div>
                )}
            </div>
        </div>
    );
}
