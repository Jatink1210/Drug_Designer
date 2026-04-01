/** SynthArenaPage — Drug candidate comparison arena with session list + comparison matrix.
 *  Session list view: cards showing name, target, compound count, status.
 *  Detail view: 10-criteria × N candidates comparison matrix with score bars.
 */

import { useState, useEffect } from "react";
import {
    FlaskConical, Plus, Trophy, Loader2, RefreshCw, Trash2, ArrowLeft, Star, Download
} from "lucide-react";
import { ensureApiBase } from "@/lib/api";

interface ArenaSession {
    id: string;
    name: string;
    target: string;
    compound_count: number;
    created_at: number;
    status: string;
}

interface Candidate {
    name: string;
    smiles: string;
    chemblId: string;
    scores: Record<string, number>;
    overall: number;
    winner: boolean;
}

const CRITERIA = [
    "Binding Affinity", "Selectivity", "ADMET Score",
    "Synthetic Accessibility", "Solubility", "Metabolic Stability",
    "hERG Liability", "Novelty", "Patent Freedom", "Evidence Support"
];

const DEMO_CANDIDATES: Candidate[] = [
    {
        name: "Osimertinib",
        smiles: "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1NC(=O)C=C",
        chemblId: "CHEMBL3353410",
        overall: 0.91,
        winner: true,
        scores: {
            "Binding Affinity": 0.95, "Selectivity": 0.88, "ADMET Score": 0.92,
            "Synthetic Accessibility": 0.78, "Solubility": 0.72, "Metabolic Stability": 0.85,
            "hERG Liability": 0.90, "Novelty": 0.45, "Patent Freedom": 0.40, "Evidence Support": 0.97,
        },
    },
    {
        name: "Lazertinib",
        smiles: "Nc1ncnc2cc3c(cc12)N(CC(=O)Nc1ccc(F)c(Cl)c1)C3",
        chemblId: "CHEMBL4594298",
        overall: 0.84,
        winner: false,
        scores: {
            "Binding Affinity": 0.92, "Selectivity": 0.90, "ADMET Score": 0.85,
            "Synthetic Accessibility": 0.82, "Solubility": 0.68, "Metabolic Stability": 0.80,
            "hERG Liability": 0.88, "Novelty": 0.75, "Patent Freedom": 0.55, "Evidence Support": 0.72,
        },
    },
    {
        name: "DSR-0410",
        smiles: "c1cc(NC(=O)C=CC2CC2)ccc1Nc1ncnc2ccc(OC)cc12",
        chemblId: "—",
        overall: 0.77,
        winner: false,
        scores: {
            "Binding Affinity": 0.87, "Selectivity": 0.82, "ADMET Score": 0.74,
            "Synthetic Accessibility": 0.91, "Solubility": 0.80, "Metabolic Stability": 0.70,
            "hERG Liability": 0.65, "Novelty": 0.92, "Patent Freedom": 0.95, "Evidence Support": 0.35,
        },
    },
];

function formatTime(ts: number) {
    if (!ts) return "—";
    return new Date(ts * 1000).toLocaleDateString(undefined, {
        month: "short", day: "numeric",
    });
}

function scoreColor(v: number) {
    if (v >= 0.85) return "#2D8B5F";
    if (v >= 0.65) return "#C48820";
    return "#C43D2F";
}

export default function SynthArenaPage() {
    const [sessions, setSessions] = useState<ArenaSession[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedSession, setSelectedSession] = useState<ArenaSession | null>(null);
    const [candidates, setCandidates] = useState<Candidate[]>(DEMO_CANDIDATES);
    const [showCreate, setShowCreate] = useState(false);
    const [newName, setNewName] = useState("");
    const [newTarget, setNewTarget] = useState("");
    const [creating, setCreating] = useState(false);

    const fetchSessions = async () => {
        setLoading(true);
        try {
            const base = await ensureApiBase();
            const res = await fetch(`${base}/syntharena/sessions`);
            if (res.ok) {
                const data = await res.json();
                setSessions(data);
            }
        } catch { /* empty */ }
        setLoading(false);
    };

    const createSession = async () => {
        if (!newName.trim()) return;
        setCreating(true);
        try {
            const base = await ensureApiBase();
            await fetch(`${base}/syntharena/sessions`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: newName, target: newTarget }),
            });
            setNewName("");
            setNewTarget("");
            setShowCreate(false);
            fetchSessions();
        } catch { /* empty */ }
        setCreating(false);
    };

    const deleteSession = async (id: string) => {
        try {
            const base = await ensureApiBase();
            await fetch(`${base}/syntharena/sessions/${id}`, { method: "DELETE" });
            fetchSessions();
        } catch { /* empty */ }
    };

    const openSession = (s: ArenaSession) => {
        setSelectedSession(s);
        // In production, would fetch candidates for this session
    };

    useEffect(() => { fetchSessions(); }, []);

    // --- Detail view (comparison matrix) ---
    if (selectedSession) {
        return (
            <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
                {/* Back + header */}
                <button
                    onClick={() => setSelectedSession(null)}
                    className="flex items-center gap-1 text-[11px] font-medium mb-3 transition-colors"
                    style={{ color: "var(--accent)" }}
                >
                    <ArrowLeft size={12} /> All Sessions
                </button>
                <div className="flex items-center justify-between mb-1">
                    <h1 className="text-xl" style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>
                        {selectedSession.name}
                    </h1>
                    <div className="flex gap-2">
                        <button className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded border" style={{ borderColor: "var(--border)", color: "var(--accent)" }}>
                            <Plus size={10} /> Add Candidate
                        </button>
                        <button className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded border" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
                            <Download size={10} /> Export
                        </button>
                    </div>
                </div>
                <p className="text-xs mb-5" style={{ color: "var(--text-muted)" }}>
                    Target: {selectedSession.target || "EGFR T790M"} · {candidates.length} candidates · {CRITERIA.length} criteria
                </p>

                {/* Comparison matrix table */}
                <div className="overflow-x-auto" style={{ border: "1px solid var(--border)" }}>
                    <table className="w-full text-xs" style={{ minWidth: 700 }}>
                        <thead>
                            <tr style={{ background: "var(--bg-surface)" }}>
                                <th className="text-left py-2.5 px-3 font-semibold" style={{ width: 180 }}>Criterion</th>
                                {candidates.map(c => (
                                    <th key={c.name} className="text-center py-2.5 px-3 font-semibold" style={{ minWidth: 140 }}>
                                        <div>{c.name}</div>
                                        {c.winner && (
                                            <span className="text-[8px] font-bold px-1 py-0.5 rounded" style={{ background: "#2D8B5F", color: "#fff" }}>
                                                🏆 WINNER
                                            </span>
                                        )}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {CRITERIA.map(criterion => {
                                const maxVal = Math.max(...candidates.map(c => c.scores[criterion] || 0));
                                return (
                                    <tr key={criterion}>
                                        <td className="py-2 px-3 font-medium" style={{ borderBottom: "1px solid var(--border)" }}>
                                            {criterion}
                                        </td>
                                        {candidates.map(c => {
                                            const val = c.scores[criterion] || 0;
                                            const isBest = val === maxVal && val > 0;
                                            return (
                                                <td
                                                    key={c.name}
                                                    className="py-2 px-3 text-center"
                                                    style={{
                                                        borderBottom: "1px solid var(--border)",
                                                        fontWeight: isBest ? 700 : 400,
                                                    }}
                                                >
                                                    <div className="flex flex-col items-center gap-1">
                                                        <span style={{ color: scoreColor(val) }}>
                                                            {(val * 100).toFixed(0)}%
                                                        </span>
                                                        <div className="w-16 h-1.5 rounded-full" style={{ background: "var(--border)" }}>
                                                            <div
                                                                className="h-full rounded-full"
                                                                style={{ width: `${val * 100}%`, background: scoreColor(val) }}
                                                            />
                                                        </div>
                                                    </div>
                                                </td>
                                            );
                                        })}
                                    </tr>
                                );
                            })}
                            {/* Overall row */}
                            <tr style={{ background: "var(--bg-surface)" }}>
                                <td className="py-2.5 px-3 font-bold">Overall Score</td>
                                {candidates.map(c => (
                                    <td key={c.name} className="py-2.5 px-3 text-center font-bold text-sm" style={{ color: "var(--accent)" }}>
                                        {c.overall.toFixed(2)}
                                    </td>
                                ))}
                            </tr>
                        </tbody>
                    </table>
                </div>

                {/* Candidate detail cards */}
                <div className="grid grid-cols-3 gap-4 mt-6">
                    {candidates.map(c => (
                        <div key={c.name} className="p-4" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
                            <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-semibold">{c.name}</span>
                                {c.winner && <Star size={12} style={{ color: "#C48820" }} />}
                            </div>
                            <div className="text-[9px] mb-2" style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                                {c.chemblId}
                            </div>
                            <div className="text-[9px] p-1.5 rounded overflow-x-auto" style={{ background: "var(--bg-elevated)", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
                                {c.smiles.length > 40 ? c.smiles.slice(0, 40) + "…" : c.smiles}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    // --- Session list view ---
    return (
        <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-4xl mx-auto">
                <div className="flex items-center justify-between mb-1">
                    <h1 className="text-xl" style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>
                        SynthArena
                    </h1>
                    <div className="flex gap-2">
                        <button
                            onClick={fetchSessions}
                            className="flex items-center gap-1 px-2 py-1 text-[10px] rounded border transition-colors"
                            style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
                        >
                            <RefreshCw size={10} /> Refresh
                        </button>
                        <button
                            onClick={() => setShowCreate(!showCreate)}
                            className="btn-primary flex items-center gap-1 px-3 py-1.5 text-[10px]"
                        >
                            <Plus size={10} /> New Session
                        </button>
                    </div>
                </div>
                <p className="text-xs mb-5" style={{ color: "var(--text-muted)" }}>
                    Compare and rank drug candidates against customizable evidence-backed criteria
                </p>

                {/* Create form */}
                {showCreate && (
                    <div className="p-4 mb-5" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
                        <div className="flex gap-3 mb-3">
                            <input
                                type="text" value={newName} onChange={e => setNewName(e.target.value)}
                                placeholder="Session name (e.g. EGFR Inhibitor Comparison)"
                                className="flex-1 px-2.5 py-1.5 text-xs rounded border" style={{ borderColor: "var(--border)" }}
                            />
                            <input
                                type="text" value={newTarget} onChange={e => setNewTarget(e.target.value)}
                                placeholder="Target protein (optional)"
                                className="flex-1 px-2.5 py-1.5 text-xs rounded border" style={{ borderColor: "var(--border)" }}
                            />
                        </div>
                        <div className="flex justify-end gap-2">
                            <button onClick={() => setShowCreate(false)} className="px-3 py-1 text-[10px] rounded border" style={{ borderColor: "var(--border)" }}>Cancel</button>
                            <button onClick={createSession} disabled={creating || !newName.trim()} className="btn-primary px-3 py-1 text-[10px]">
                                {creating ? <Loader2 size={10} className="animate-spin" /> : "Create"}
                            </button>
                        </div>
                    </div>
                )}

                {/* Loading */}
                {loading && (
                    <div className="flex items-center justify-center py-16">
                        <Loader2 size={20} className="animate-spin" style={{ color: "var(--accent)" }} />
                    </div>
                )}

                {/* Empty state */}
                {!loading && sessions.length === 0 && (
                    <div className="empty-state">
                        <Trophy size={36} />
                        <p className="mt-3">No arena sessions. Create one to compare drug candidates.</p>
                    </div>
                )}

                {/* Sessions */}
                {!loading && sessions.length > 0 && (
                    <div className="space-y-2">
                        {sessions.map(s => (
                            <div
                                key={s.id}
                                className="flex items-center gap-4 p-4 cursor-pointer transition-colors hover:border-[var(--text-muted)]"
                                style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}
                                onClick={() => openSession(s)}
                            >
                                <FlaskConical size={18} style={{ color: "var(--accent)" }} />
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm font-semibold">{s.name}</div>
                                    <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                                        {s.target && `Target: ${s.target} · `}{s.compound_count} compounds · {formatTime(s.created_at)}
                                    </div>
                                </div>
                                <span
                                    className="text-[9px] font-bold px-1.5 py-0.5 rounded-sm uppercase"
                                    style={{
                                        background: s.status === "ranked" ? "#ecfdf5" : "#fffbeb",
                                        color: s.status === "ranked" ? "#047857" : "#b45309",
                                    }}
                                >
                                    {s.status}
                                </span>
                                <button
                                    onClick={e => { e.stopPropagation(); deleteSession(s.id); }}
                                    className="p-1 rounded text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100"
                                >
                                    <Trash2 size={13} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Criteria info */}
                <div className="mt-6 p-4" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
                    <div className="section-label mb-2">Default Scoring Criteria</div>
                    <div className="flex flex-wrap gap-2">
                        {CRITERIA.map(c => (
                            <span
                                key={c}
                                className="text-[10px] font-medium px-2 py-1 rounded"
                                style={{ background: "var(--accent-subtle)", color: "var(--accent)" }}
                            >
                                {c}
                            </span>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
