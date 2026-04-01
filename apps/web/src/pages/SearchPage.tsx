/** Search Workbench — table-first with Insight Strip. */

import { useState, useCallback, useMemo } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search, Loader2, AlertCircle, Beaker, ToggleLeft, ToggleRight, SlidersHorizontal, Shield } from "lucide-react";
import { searchAPI, type SearchRequest, type SearchResponse } from "@/lib/api";
import DataGrid from "@/components/ui/DataGrid";
import MiniGraphPreview from "@/components/ui/MiniGraphPreview";
import TimelineMiniChart from "@/components/ui/TimelineMiniChart";
import ContradictionBanner from "@/components/ui/ContradictionBanner";
import { TYPE_COLORS } from "@/components/ui/EntityPill";

interface SearchPageProps {
    onEntityClick: (entity: Record<string, unknown>) => void;
}

export default function SearchPage({ onEntityClick }: SearchPageProps) {
    const [query, setQuery] = useState("");
    const [strictMode, setStrictMode] = useState(false);
    const [showFilters, setShowFilters] = useState(false);
    const mutation = useMutation({ mutationFn: (req: SearchRequest) => searchAPI(req) });

    const handleSearch = useCallback(() => {
        if (!query.trim()) return;
        mutation.mutate({ query: query.trim(), limit: 25, strict_evidence: strictMode });
    }, [query, strictMode, mutation]);

    const data = mutation.data;

    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1440px] mx-auto px-6 py-5">
                {/* Page header */}
                <div className="mb-5">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">Omniscient Search</h1>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">Multi-source search across 11+ biomedical databases</p>
                </div>

                {/* Query bar */}
                <div className="glass-card rounded-xl p-4 mb-5">
                    <div className="flex gap-3">
                        <div className="flex-1 relative">
                            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                            <input type="text" value={query} onChange={e => setQuery(e.target.value)}
                                onKeyDown={e => e.key === "Enter" && handleSearch()}
                                placeholder="Search proteins, genes, drugs, diseases, structures, trials, pathways…"
                                className="w-full pl-10 pr-4 py-2.5 rounded-lg border text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
                                style={{ borderColor: "var(--border)" }} />
                        </div>
                        <button onClick={handleSearch} disabled={mutation.isPending || !query.trim()}
                            className="px-6 py-2.5 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-40 hover:opacity-90"
                            style={{ background: "var(--accent)" }}>
                            {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : "Search"}
                        </button>
                    </div>
                    <div className="flex items-center gap-4 mt-3">
                        <button onClick={() => setStrictMode(!strictMode)}
                            className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)]">
                            {strictMode ? <ToggleRight size={16} className="text-[var(--accent)]" /> : <ToggleLeft size={16} />}
                            {strictMode ? "Strict Evidence" : "Assisted"}
                        </button>
                        <button onClick={() => setShowFilters(!showFilters)}
                            className={`flex items-center gap-1 text-xs hover:text-[var(--text-secondary)] ${showFilters ? "text-[var(--accent)]" : "text-[var(--text-muted)]"}`}>
                            <SlidersHorizontal size={12} /> Filters
                        </button>
                    </div>
                    {showFilters && (
                        <div className="flex items-center gap-4 mt-2 pl-1 text-xs text-[var(--text-muted)]">
                            Source filters coming in v2 — all 16 connectors are queried automatically.
                        </div>
                    )}
                </div>

                {/* Loading */}
                {mutation.isPending && (
                    <div className="flex items-center gap-3 py-16 justify-center text-[var(--text-muted)]">
                        <Loader2 size={20} className="animate-spin" />
                        <span className="text-sm">Querying databases…</span>
                    </div>
                )}

                {/* Error */}
                {mutation.isError && (
                    <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm mb-4">
                        <AlertCircle size={16} /> {(mutation.error as Error).message}
                    </div>
                )}

                {/* Results */}
                {data && <SearchResults data={data} onEntityClick={onEntityClick} />}

                {/* Empty */}
                {!data && !mutation.isPending && (
                    <div className="flex flex-col items-center justify-center py-20 text-center">
                        <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4" style={{ background: "var(--accent-subtle)" }}>
                            <Beaker size={24} className="text-[var(--accent)]" />
                        </div>
                        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">Start your discovery</h3>
                        <p className="text-xs text-[var(--text-muted)] max-w-sm">Enter a query, identifier, or gene symbol to search across UniProt, PubMed, OpenTargets, RCSB, ChEMBL, ClinicalTrials.gov, Reactome, AlphaFold, PubChem, and more.</p>
                    </div>
                )}
            </div>
        </div>
    );
}

/* ─── Results ─────────────────────────────────────────── */

function SearchResults({ data, onEntityClick }: { data: SearchResponse; onEntityClick: (e: Record<string, unknown>) => void }) {
    const catKeys = Object.keys(data.categories);
    const stats = data.summary_stats;
    const evidence = data.evidence_summary;

    // Build timeline data from publications
    const timelineData = useMemo(() => {
        const pubs = data.categories.publications?.rows || [];
        const byYear: Record<number, number> = {};
        pubs.forEach(p => { const y = p.year as number; if (y && y > 1990) byYear[y] = (byYear[y] || 0) + 1; });
        return Object.entries(byYear).sort(([a], [b]) => Number(a) - Number(b)).map(([y, c]) => ({ year: Number(y), count: c }));
    }, [data]);

    const confidencePct = evidence ? Math.round(evidence.overall_confidence * 100) : null;
    const contradictions = evidence?.contradictions || [];

    return (
        <div className="space-y-5">
            {/* Insight Strip — 3 columns */}
            <div className="grid grid-cols-3 gap-4">
                {/* Summary stats */}
                <div className="glass-card rounded-lg p-3">
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Summary</div>
                    <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold text-white" style={{ background: TYPE_COLORS[data.intent.intent] || "#6b7280" }}>
                            {data.intent.intent}
                        </span>
                        <span className="text-xs text-[var(--text-muted)]">{data.intent.method}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                        <span className="text-[var(--text-muted)]">Results</span><span className="font-medium text-[var(--text-primary)]">{stats.total_results}</span>
                        <span className="text-[var(--text-muted)]">Categories</span><span className="font-medium text-[var(--text-primary)]">{stats.categories_found}</span>
                        {stats.pubmed_count != null && <><span className="text-[var(--text-muted)]">PubMed</span><span className="font-medium text-[var(--text-primary)]">{stats.pubmed_count.toLocaleString()}</span></>}
                        {stats.clinical_trials_count != null && <><span className="text-[var(--text-muted)]">Trials</span><span className="font-medium text-[var(--text-primary)]">{stats.clinical_trials_count.toLocaleString()}</span></>}
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                        {data.provenance.sources_hit.map(s => (
                            <span key={s} className="px-1.5 py-0.5 text-[9px] rounded bg-slate-100 text-slate-500">{s}</span>
                        ))}
                    </div>
                    {data.timings.total && <div className="text-[9px] text-[var(--text-muted)] mt-1">{data.timings.total.toFixed(2)}s</div>}
                </div>

                {/* Timeline */}
                <TimelineMiniChart data={timelineData} label="Publications by Year" color="var(--accent)" />

                {/* Evidence confidence card */}
                {evidence ? (
                    <div className="glass-card rounded-lg p-3">
                        <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Evidence Quality</div>
                        <div className="flex items-center gap-2 mb-2">
                            <Shield size={14} className="text-[var(--text-muted)]" />
                            <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
                                <div
                                    className="h-full rounded-full transition-all"
                                    style={{
                                        width: `${confidencePct}%`,
                                        backgroundColor: (confidencePct ?? 0) >= 70 ? "#16a34a" : (confidencePct ?? 0) >= 40 ? "#d97706" : "#dc2626",
                                    }}
                                />
                            </div>
                            <span className="text-xs font-medium text-[var(--text-primary)]">{confidencePct}%</span>
                        </div>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                            <span className="text-[var(--text-muted)]">Citations</span>
                            <span className="font-medium text-[var(--text-primary)]">{evidence.evidence_count}</span>
                            <span className="text-[var(--text-muted)]">Contradictions</span>
                            <span className={`font-medium ${contradictions.length > 0 ? "text-amber-600" : "text-[var(--text-primary)]"}`}>
                                {contradictions.length}
                            </span>
                        </div>
                        {evidence.top_citations.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                                {evidence.top_citations.slice(0, 4).map((c, i) => (
                                    <span key={i} className="px-1.5 py-0.5 text-[9px] rounded bg-slate-100 text-slate-500 truncate max-w-[100px]">
                                        {c.source}
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>
                ) : (
                    <MiniGraphPreview nodes={data.preview_graph.nodes} edges={data.preview_graph.edges} />
                )}
            </div>

            {/* Graph preview if evidence card replaced it */}
            {evidence && (
                <MiniGraphPreview nodes={data.preview_graph.nodes} edges={data.preview_graph.edges} />
            )}

            {/* Contradictions */}
            {contradictions.length > 0 && (
                <div className="space-y-2">
                    {contradictions.slice(0, 3).map((c, i) => (
                        <ContradictionBanner key={i} contradiction={c} />
                    ))}
                    {contradictions.length > 3 && (
                        <p className="text-[10px] text-[var(--text-muted)] text-center">
                            +{contradictions.length - 3} more contradictions found
                        </p>
                    )}
                </div>
            )}

            {/* Errors */}
            {data.errors.length > 0 && (
                <div className="px-4 py-2 rounded-lg bg-amber-50 text-amber-800 text-xs">⚠ {data.errors.join("; ")}</div>
            )}

            {/* Categorized DataGrids */}
            {catKeys.length === 0 ? (
                <div className="text-center py-12 text-[var(--text-muted)] text-sm">No results found.</div>
            ) : (
                <CategoryTabs categories={data.categories} onEntityClick={onEntityClick} />
            )}
        </div>
    );
}

/* ─── Category Tabs + DataGrid ────────────────────────── */

function CategoryTabs({ categories, onEntityClick }: {
    categories: Record<string, { columns: string[]; rows: Record<string, unknown>[]; total: number }>;
    onEntityClick: (e: Record<string, unknown>) => void;
}) {
    const types = Object.keys(categories);
    const [activeTab, setActiveTab] = useState(types[0] || "");
    const cat = categories[activeTab];
    if (!cat) return null;

    const colDefs = cat.columns
        .filter(c => !["provenance", "properties", "entity_type", "canonical_name", "created_at", "updated_at", "xrefs", "tags", "synonyms", "sequence", "abstract"].includes(c))
        .map(c => ({ key: c, label: c.replace(/_/g, " ") }));

    return (
        <div>
            <div className="flex gap-1 mb-0 overflow-x-auto hide-scrollbar">
                {types.map(t => (
                    <button key={t} onClick={() => setActiveTab(t)}
                        className={`px-3 py-2 text-xs font-medium whitespace-nowrap rounded-t-lg transition-colors ${activeTab === t ? "bg-white text-[var(--accent)] border border-b-0" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)] bg-transparent"
                            }`} style={activeTab === t ? { borderColor: "var(--border)" } : undefined}>
                        {t} <span className="ml-1 opacity-50">({categories[t].total})</span>
                    </button>
                ))}
            </div>
            <DataGrid columns={colDefs} rows={cat.rows} onRowClick={onEntityClick} exportFilename={activeTab} entityType={activeTab} />
        </div>
    );
}
