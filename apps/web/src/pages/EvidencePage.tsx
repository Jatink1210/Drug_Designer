/** Evidence & Patents Workbench — unified table + citation export. */

import { useState, useMemo } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search, BookOpen, Download, Filter, SlidersHorizontal, Loader2, AlertCircle, FileText, Calendar, ExternalLink } from "lucide-react";
import { evidenceSearchAPI, evidenceExportAPI, type EvidenceSearchRequest, type EvidenceResult } from "@/lib/api";
import EvidenceBadge from "@/components/ui/EvidenceBadge";

export default function EvidencePage() {
    const [query, setQuery] = useState("");
    const [sources, setSources] = useState<string[]>(["pubmed", "clinicaltrials"]);
    const [yearFrom, setYearFrom] = useState(0);
    const [yearTo, setYearTo] = useState(9999);
    const [exportFmt, setExportFmt] = useState("json");

    const searchMut = useMutation({ mutationFn: (req: EvidenceSearchRequest) => evidenceSearchAPI(req) });
    const exportMut = useMutation({ mutationFn: ({ q, f }: { q: string; f: string }) => evidenceExportAPI(q, f) });

    const handleSearch = () => {
        if (!query.trim()) return;
        searchMut.mutate({ query: query.trim(), sources, limit: 50, year_from: yearFrom, year_to: yearTo });
    };

    const data = searchMut.data;

    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1440px] mx-auto px-6 py-5">
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">Evidence & Literature</h1>
                <p className="text-xs text-[var(--text-muted)] mb-5">Unified search across PubMed, Europe PMC, ClinicalTrials, and PatentsView with citation export</p>

                {/* Query bar */}
                <div className="glass-card rounded-xl p-4 mb-5">
                    <div className="flex gap-3">
                        <div className="flex-1 relative">
                            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                            <input type="text" value={query} onChange={e => setQuery(e.target.value)}
                                onKeyDown={e => e.key === "Enter" && handleSearch()}
                                placeholder="Search publications, trials, patents…"
                                className="w-full pl-10 pr-4 py-2.5 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                                style={{ borderColor: "var(--border)" }} />
                        </div>
                        <button onClick={handleSearch} disabled={searchMut.isPending || !query.trim()}
                            className="px-5 py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-40" style={{ background: "var(--accent)" }}>
                            {searchMut.isPending ? <Loader2 size={16} className="animate-spin" /> : "Search"}
                        </button>
                    </div>
                    {/* Source + filter bar */}
                    <div className="flex items-center gap-3 mt-3 flex-wrap">
                        {[
                            { id: "pubmed", label: "PubMed" }, { id: "europepmc", label: "Europe PMC" },
                            { id: "clinicaltrials", label: "ClinicalTrials" }, { id: "patents", label: "Patents" },
                        ].map(s => (
                            <label key={s.id} className="flex items-center gap-1.5 text-xs cursor-pointer">
                                <input type="checkbox" checked={sources.includes(s.id)}
                                    onChange={e => setSources(e.target.checked ? [...sources, s.id] : sources.filter(x => x !== s.id))}
                                    className="rounded" /> {s.label}
                            </label>
                        ))}
                        <div className="ml-auto flex items-center gap-2">
                            <Calendar size={12} className="text-[var(--text-muted)]" />
                            <input type="number" placeholder="From" value={yearFrom || ""} onChange={e => setYearFrom(+e.target.value)}
                                className="w-16 px-2 py-1 text-xs rounded border" style={{ borderColor: "var(--border)" }} />
                            <span className="text-xs text-[var(--text-muted)]">–</span>
                            <input type="number" placeholder="To" value={yearTo === 9999 ? "" : yearTo} onChange={e => setYearTo(+e.target.value || 9999)}
                                className="w-16 px-2 py-1 text-xs rounded border" style={{ borderColor: "var(--border)" }} />
                        </div>
                    </div>
                </div>

                {/* Error */}
                {searchMut.isError && (
                    <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm mb-4">
                        <AlertCircle size={16} /> {(searchMut.error as Error).message}
                    </div>
                )}

                {/* Results */}
                {data && <ResultsView data={data} query={query} exportFmt={exportFmt} setExportFmt={setExportFmt} exportMut={exportMut} />}

                {/* Empty */}
                {!data && !searchMut.isPending && (
                    <div className="glass-card rounded-xl p-12 text-center">
                        <BookOpen size={40} className="text-slate-200 mx-auto mb-3" />
                        <p className="text-sm text-slate-400 font-medium">Search for evidence</p>
                        <p className="text-xs text-slate-400 mt-1">Results will appear as sortable tables with citation tools</p>
                    </div>
                )}
            </div>
        </div>
    );
}

function ResultsView({ data, query, exportFmt, setExportFmt, exportMut }: {
    data: EvidenceResult; query: string; exportFmt: string;
    setExportFmt: (f: string) => void; exportMut: any;
}) {
    const categories = Object.keys(data.results);
    const [activeTab, setActiveTab] = useState(categories[0] || "");

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div className="text-xs text-[var(--text-muted)]">{data.total} results across {categories.length} sources</div>
                <div className="flex items-center gap-2">
                    <select value={exportFmt} onChange={e => setExportFmt(e.target.value)} className="text-xs border rounded px-2 py-1" style={{ borderColor: "var(--border)" }}>
                        <option value="json">JSON</option><option value="csv">CSV</option><option value="bibtex">BibTeX</option><option value="ris">RIS</option>
                    </select>
                    <button onClick={() => exportMut.mutate({ q: query, f: exportFmt })}
                        disabled={exportMut.isPending}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border hover:bg-gray-50" style={{ borderColor: "var(--border)" }}>
                        {exportMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />} Export
                    </button>
                </div>
            </div>

            {exportMut.data && (
                <div className="rounded-lg border p-3 bg-green-50" style={{ borderColor: "#bbf7d0" }}>
                    <div className="text-xs font-medium text-green-700">✓ Exported {(exportMut.data as any).count} citations as {(exportMut.data as any).format}</div>
                </div>
            )}

            {/* Category tabs */}
            <div className="flex gap-1">
                {categories.map(c => (
                    <button key={c} onClick={() => setActiveTab(c)}
                        className={`px-3 py-2 text-xs font-medium rounded-t-lg ${activeTab === c ? "bg-white text-[var(--accent)] border border-b-0" : "text-[var(--text-muted)] hover:bg-gray-50"}`}
                        style={activeTab === c ? { borderColor: "var(--border)" } : undefined}>
                        {c} ({data.results[c]?.length || 0})
                    </button>
                ))}
            </div>

            {/* Results table */}
            {data.results[activeTab] && (
                <div className="glass-card rounded-lg overflow-hidden">
                    <table className="w-full text-xs">
                        <thead>
                            <tr className="bg-[var(--bg-app)]">
                                {["Title / Name", "Year", "ID", "Source", "Details"].map(h => (
                                    <th key={h} className="px-3 py-2 text-left text-[9px] font-semibold text-[var(--text-muted)] uppercase">{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {data.results[activeTab].map((r: any, i: number) => (
                                <tr key={i} className="border-t hover:bg-gray-50" style={{ borderColor: "var(--border-light)" }}>
                                    <td className="px-3 py-2 max-w-[400px]">
                                        <div className="font-medium text-[var(--text-primary)] truncate">{r.title || r.canonical_name || r.name || "—"}</div>
                                        {r.journal && <div className="text-[10px] text-[var(--text-muted)]">{r.journal}</div>}
                                    </td>
                                    <td className="px-3 py-2 text-[var(--text-muted)]">{r.year || "—"}</td>
                                    <td className="px-3 py-2">
                                        {r.pmid && <EvidenceBadge type="pmid" value={r.pmid} />}
                                        {r.nct_id && <EvidenceBadge type="nct" value={r.nct_id} />}
                                        {r.doi && <EvidenceBadge type="doi" value={r.doi} />}
                                        {!r.pmid && !r.nct_id && !r.doi && <span className="text-[var(--text-muted)]">{r.id || "—"}</span>}
                                    </td>
                                    <td className="px-3 py-2 text-[var(--text-muted)]">{r.entity_type || activeTab}</td>
                                    <td className="px-3 py-2">
                                        {r.url && <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] flex items-center gap-1">View <ExternalLink size={9} /></a>}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
