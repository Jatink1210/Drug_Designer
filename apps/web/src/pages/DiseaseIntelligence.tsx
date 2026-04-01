/** Disease Intelligence Page */
import { useState } from "react";
import { Search, Download, FileSpreadsheet, AlertTriangle, Shield, CheckCircle, BarChart2 } from "lucide-react";
import { ensureApiBase } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

type Target = {
    target_id: string;
    symbol: string;
    name: string;
    overall_score: number;
    uniprot_id?: string;
};

type DiseaseInfo = {
    name: string;
    id: string;
    iri?: string;
    ontology?: string;
};

export default function DiseaseIntelligence() {
    const [query, setQuery] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [diseaseInfo, setDiseaseInfo] = useState<DiseaseInfo | null>(null);
    const [targets, setTargets] = useState<Target[]>([]);

    const analyzeDisease = async () => {
        if (!query.trim()) return;
        setLoading(true);
        setError(null);
        setDiseaseInfo(null);
        setTargets([]);

        try {
            const base = await ensureApiBase();
            const res = await fetch(`${base}/disease/analyze`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query })
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to analyze disease");
            }

            const data = await res.json();
            setDiseaseInfo(data.disease_info);
            setTargets(data.targets || []);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const downloadExcel = async () => {
        if (!query) return;
        const base = await ensureApiBase();
        fetch(`${base}/disease/export_excel`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: diseaseInfo?.name || query })
        })
        .then(res => res.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${diseaseInfo?.id || 'disease'}_dossier.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        });
    };

    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">Disease Intelligence</h1>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">Normalize disease queries, fetch OpenTargets associations, and map UniProt targets.</p>
                </div>

                <div className="flex gap-4 mb-6 relative">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" size={16} />
                        <input 
                            type="text" 
                            className="w-full glass-input text-sm py-2.5 pl-9 pr-4"
                            placeholder="Enter a disease or indication (e.g. 'Alzheimers', 'Asthma')..."
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && analyzeDisease()}
                        />
                    </div>
                    <button 
                        onClick={analyzeDisease}
                        disabled={loading}
                        className="glass-button text-sm px-6 font-medium"
                    >
                        {loading ? "Analyzing..." : "Analyze Disease"}
                    </button>
                </div>

                {error && (
                    <div className="mb-6 p-4 rounded-xl flex items-center gap-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                        <AlertTriangle size={16} /> {error}
                    </div>
                )}

                {diseaseInfo && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                        <div className="glass-card p-5 col-span-1 md:col-span-2 relative overflow-hidden">
                            <div className="absolute top-0 right-0 p-4 opacity-10">
                                <Shield size={100} />
                            </div>
                            <h2 className="text-xs font-semibold text-[var(--text-muted)] mb-1 uppercase tracking-wider">Normalized Ontology</h2>
                            <div className="text-2xl font-bold text-[var(--text-primary)] mb-2">{diseaseInfo.name}</div>
                            <div className="flex items-center gap-2 text-xs font-mono text-[var(--text-secondary)] mb-4">
                                <CheckCircle size={14} className="text-[var(--success, #10b981)]" /> {diseaseInfo.id}
                            </div>
                            <p className="text-xs text-[var(--text-muted)] break-all max-w-[80%]">{diseaseInfo.iri}</p>
                        </div>

                        <div className="glass-card p-5 flex flex-col items-center justify-center text-center">
                            <div className="text-sm font-semibold text-[var(--text-primary)] mb-2">Decision Dossier</div>
                            <p className="text-[10px] text-[var(--text-muted)] mb-4">Export prioritized targets and normalized disease metadata as a unified Excel report.</p>
                            <button onClick={downloadExcel} className="glass-button flex items-center gap-2 py-2 px-4 shadow-sm">
                                <FileSpreadsheet size={16} className="text-green-500" /> Export Dossier
                            </button>
                        </div>
                    </div>
                )}

                {targets.length > 0 && (
                    <div className="glass-card overflow-hidden">
                        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                            <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2"><BarChart2 size={16} className="text-[var(--accent)]"/> Prioritized Targets Array (Top {targets.length})</h2>
                        </div>
                        
                        <div className="p-5 border-b border-border/50 h-[250px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={targets.slice(0, 10)}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                                    <XAxis dataKey="symbol" tick={{fontSize: 10, fill: 'var(--text-muted)'}} axisLine={false} tickLine={false} />
                                    <YAxis hide domain={[0, 1]} />
                                    <Tooltip 
                                        contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', borderRadius: '8px', fontSize: '12px' }}
                                        itemStyle={{ color: 'var(--text-primary)' }}
                                    />
                                    <Bar dataKey="overall_score" fill="var(--accent)" radius={[4, 4, 0, 0]} maxBarSize={40} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-xs">
                                <thead>
                                    <tr className="border-b border-border bg-surface/50">
                                        <th className="px-5 py-3 font-medium text-[var(--text-muted)]">Target Identity</th>
                                        <th className="px-5 py-3 font-medium text-[var(--text-muted)]">Symbol</th>
                                        <th className="px-5 py-3 font-medium text-[var(--text-muted)] text-right">OT Score</th>
                                        <th className="px-5 py-3 font-medium text-[var(--text-muted)]">UniProt Mapping</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {targets.map((t, i) => (
                                        <tr key={i} className="border-b border-border/50 hover:bg-surface/30 transition-colors">
                                            <td className="px-5 py-3">
                                                <div className="font-medium text-[var(--text-primary)]">{t.name}</div>
                                                <div className="text-[10px] text-[var(--text-muted)] font-mono">{t.target_id}</div>
                                            </td>
                                            <td className="px-5 py-3">
                                                <span className="px-2 py-1 rounded bg-surface border border-border font-mono text-amber-500/80">{t.symbol}</span>
                                            </td>
                                            <td className="px-5 py-3 text-right">
                                                <div className="font-mono text-[var(--accent)]">{(t.overall_score || 0).toFixed(4)}</div>
                                            </td>
                                            <td className="px-5 py-3">
                                                {t.uniprot_id ? (
                                                    <span className="flex items-center gap-1.5 text-blue-400">
                                                        <CheckCircle size={12} /> {t.uniprot_id}
                                                    </span>
                                                ) : (
                                                    <span className="text-[var(--text-muted)]">Unmapped</span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
