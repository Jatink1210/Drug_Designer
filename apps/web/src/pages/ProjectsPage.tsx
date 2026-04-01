import { useState, useEffect } from "react";
import { FolderArchive, Plus, Trash2, Pin, PinOff, Loader2, Notebook, Link } from "lucide-react";
import { ensureApiBase } from "@/lib/api";

type Project = {
    id: string;
    name: string;
    description: string;
    tags: string[];
    pinned: boolean;
    job_ids: string[];
    notes: { id: string; text: string; created_at: number }[];
    created_at: number;
    updated_at: number;
};

export default function ProjectsPage() {
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);
    const [newName, setNewName] = useState("");
    const [newDesc, setNewDesc] = useState("");

    const load = async () => {
        setLoading(true);
        try {
            const base = await ensureApiBase();
            const res = await fetch(`${base}/projects`);
            if (res.ok) setProjects(await res.json());
        } catch { /* */ }
        setLoading(false);
    };

    const create = async () => {
        if (!newName.trim()) return;
        const base = await ensureApiBase();
        await fetch(`${base}/projects`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: newName, description: newDesc })
        });
        setNewName(""); setNewDesc(""); setShowCreate(false);
        load();
    };

    const remove = async (id: string) => {
        const base = await ensureApiBase();
        await fetch(`${base}/projects/${id}`, { method: "DELETE" });
        load();
    };

    const togglePin = async (p: Project) => {
        const base = await ensureApiBase();
        await fetch(`${base}/projects/${p.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pinned: !p.pinned })
        });
        load();
    };

    useEffect(() => { load(); }, []);

    const fmt = (ts: number) => ts ? new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6 flex justify-between items-center">
                    <div>
                        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Project Dashboard</h1>
                        <p className="text-xs text-[var(--text-muted)] mt-0.5">Manage persistent project memory and continuity architectures.</p>
                    </div>
                    <button onClick={() => setShowCreate(!showCreate)} className="glass-button text-xs flex items-center gap-2 py-2 px-4 shadow-sm bg-blue-500/10 text-blue-400 border-blue-500/20">
                        <Plus size={14} /> New Project
                    </button>
                </div>

                {showCreate && (
                    <div className="glass-card p-5 mb-6 space-y-3">
                        <input type="text" value={newName} onChange={e => setNewName(e.target.value)} placeholder="Project name" className="w-full p-2.5 rounded-lg border border-border bg-[var(--bg-app)] text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]" />
                        <textarea value={newDesc} onChange={e => setNewDesc(e.target.value)} placeholder="Description (optional)" rows={2} className="w-full p-2.5 rounded-lg border border-border bg-[var(--bg-app)] text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]" />
                        <div className="flex justify-end gap-2">
                            <button onClick={() => setShowCreate(false)} className="px-4 py-1.5 text-sm rounded-lg border border-border text-[var(--text-secondary)]">Cancel</button>
                            <button onClick={create} disabled={!newName.trim()} className="px-4 py-1.5 text-sm rounded-lg bg-[var(--accent)] text-white disabled:opacity-40">Create</button>
                        </div>
                    </div>
                )}

                {loading && <div className="flex justify-center py-20"><Loader2 size={24} className="animate-spin text-[var(--accent)]" /></div>}

                {!loading && projects.length === 0 && (
                    <div className="glass-card border-dashed border-2 border-border/60 p-14 flex flex-col items-center justify-center text-center">
                        <FolderArchive size={48} className="text-[var(--text-muted)]/50 mb-4" />
                        <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-2">No Active Projects</h2>
                        <p className="text-xs text-[var(--text-secondary)] max-w-sm">Create a project to start organizing your research runs, evidence sets, and decision dossiers.</p>
                    </div>
                )}

                {!loading && projects.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {projects.map(p => (
                            <div key={p.id} className="glass-card p-5 group hover:border-[var(--accent)] transition-colors">
                                <div className="flex items-start justify-between mb-2">
                                    <div className="flex-1 min-w-0">
                                        <h3 className="font-semibold text-[var(--text-primary)] truncate">{p.name}</h3>
                                        {p.description && <p className="text-xs text-[var(--text-muted)] mt-0.5 line-clamp-2">{p.description}</p>}
                                    </div>
                                    <button onClick={() => togglePin(p)} className="text-[var(--text-muted)] hover:text-amber-500 ml-2">
                                        {p.pinned ? <Pin size={14} className="text-amber-500" /> : <PinOff size={14} />}
                                    </button>
                                </div>
                                <div className="flex items-center gap-3 text-[10px] text-[var(--text-muted)] mb-3">
                                    <span className="flex items-center gap-1"><Link size={10} /> {p.job_ids?.length || 0} runs</span>
                                    <span className="flex items-center gap-1"><Notebook size={10} /> {p.notes?.length || 0} notes</span>
                                    <span>Updated {fmt(p.updated_at)}</span>
                                </div>
                                {p.tags?.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mb-3">{p.tags.map(t => <span key={t} className="px-2 py-0.5 rounded-full text-[9px] bg-[var(--accent-subtle)] text-[var(--accent)]">{t}</span>)}</div>
                                )}
                                <div className="flex justify-end pt-2 border-t border-border/50">
                                    <button onClick={() => remove(p.id)} className="text-red-400 hover:text-red-600 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"><Trash2 size={14} /></button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
