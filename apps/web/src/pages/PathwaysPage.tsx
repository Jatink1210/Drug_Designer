/** Pathways Explorer — Reactome / KEGG pathway browser with 3-column layout. */

import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, GitBranch, ExternalLink, Layers, Loader2, Dna } from "lucide-react";
import { pathwaysSearchAPI, pathwaysDetailAPI } from "@/lib/api";

export default function PathwaysPage() {
    const [query, setQuery] = useState("");
    const [debouncedQuery, setDebouncedQuery] = useState("");
    const [source, setSource] = useState<"reactome" | "kegg">("reactome");
    const [selectedId, setSelectedId] = useState<string | null>(null);

    // ── Debounce search input (300ms) ────────────────────
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    useEffect(() => {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
            setDebouncedQuery(query.trim());
        }, 300);
        return () => { if (timerRef.current) clearTimeout(timerRef.current); };
    }, [query]);

    // ── Search pathways ──────────────────────────────────
    const searchQ = useQuery({
        queryKey: ["pathwaySearch", debouncedQuery, source],
        queryFn: () => pathwaysSearchAPI(debouncedQuery, source, 20),
        enabled: debouncedQuery.length >= 2,
    });

    // ── Detail for selected pathway ──────────────────────
    const detailQ = useQuery({
        queryKey: ["pathwayDetail", selectedId],
        queryFn: () => pathwaysDetailAPI(selectedId!),
        enabled: !!selectedId,
    });

    const results = searchQ.data ?? [];
    const detail = detailQ.data;

    // Reset selection when source changes
    const handleSourceChange = useCallback((s: "reactome" | "kegg") => {
        setSource(s);
        setSelectedId(null);
    }, []);

    return (
        <div className="flex-1 flex overflow-hidden" style={{ background: "var(--bg-app)" }}>
            {/* ── Left — Search + Results List ──────────────── */}
            <div className="w-[300px] glass-sidebar border-r flex flex-col">
                <div className="p-3 border-b" style={{ borderColor: "var(--border)" }}>
                    <h2 className="text-xs font-semibold text-[var(--text-primary)] mb-2">Pathways</h2>
                    <div className="relative">
                        <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                        <input
                            type="text"
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            placeholder="Search pathways..."
                            className="w-full pl-8 pr-3 py-1.5 text-xs rounded border bg-[var(--bg-app)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                            style={{ borderColor: "var(--border)" }}
                        />
                    </div>
                    <div className="flex gap-1 mt-2">
                        {(["reactome", "kegg"] as const).map(s => (
                            <button
                                key={s}
                                onClick={() => handleSourceChange(s)}
                                className={`flex-1 px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                                    source === s
                                        ? "bg-indigo-50 text-[var(--accent)]"
                                        : "text-[var(--text-muted)] hover:bg-gray-50"
                                }`}
                            >
                                {s === "reactome" ? "Reactome" : "KEGG"}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Results list */}
                <div className="flex-1 overflow-y-auto p-2">
                    {searchQ.isLoading && debouncedQuery.length >= 2 && (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 size={16} className="animate-spin text-[var(--text-muted)]" />
                        </div>
                    )}

                    {searchQ.isError && (
                        <p className="text-xs text-red-500 p-2">
                            Search failed. Please try again.
                        </p>
                    )}

                    {!searchQ.isLoading && results.length === 0 && debouncedQuery.length >= 2 && (
                        <p className="text-xs text-[var(--text-muted)] p-2">No pathways found.</p>
                    )}

                    {debouncedQuery.length < 2 && !searchQ.data && (
                        <p className="text-xs text-[var(--text-muted)] p-2">
                            Type at least 2 characters to search
                        </p>
                    )}

                    {results.map(pw => (
                        <button
                            key={pw.id}
                            onClick={() => setSelectedId(pw.pathway_id || pw.id)}
                            className={`w-full text-left px-3 py-2.5 text-xs rounded mb-0.5 transition-colors ${
                                selectedId === (pw.pathway_id || pw.id)
                                    ? "bg-indigo-50 text-[var(--accent)]"
                                    : "text-[var(--text-secondary)] hover:bg-gray-50"
                            }`}
                        >
                            <div className="flex items-start gap-1.5">
                                <GitBranch size={12} className="mt-0.5 shrink-0 opacity-50" />
                                <div className="min-w-0">
                                    <div className="font-medium leading-tight">{pw.canonical_name}</div>
                                    {pw.description && (
                                        <div className="text-[10px] text-[var(--text-muted)] mt-0.5 line-clamp-2">
                                            {pw.description.length > 100
                                                ? pw.description.slice(0, 100) + "..."
                                                : pw.description}
                                        </div>
                                    )}
                                    {pw.species && (
                                        <span className="inline-block mt-1 px-1.5 py-0.5 text-[9px] rounded bg-slate-100 text-slate-500">
                                            {pw.species}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* ── Center — Pathway Diagram + Participants ──── */}
            <div className="flex-1 flex flex-col">
                <div className="glass-panel border-b px-4 py-2 flex items-center gap-3">
                    <GitBranch size={14} className="text-[var(--text-muted)]" />
                    <span className="text-xs text-[var(--text-muted)]">
                        {selectedId ? "Pathway Diagram" : "Pathway Viewer"}
                    </span>
                    {selectedId && detail && (
                        <span className="text-xs font-medium text-[var(--text-primary)]">
                            {detail.canonical_name}
                        </span>
                    )}
                    <span className="ml-auto text-[10px] text-[var(--text-muted)]">
                        {selectedId ? selectedId : "Select a pathway to view"}
                    </span>
                </div>

                {/* Main viewer area */}
                {!selectedId && (
                    <div className="flex-1 glass-panel flex items-center justify-center">
                        <div className="text-center">
                            <Layers size={48} className="text-slate-200 mx-auto mb-3" />
                            <p className="text-sm text-slate-400">Pathway Viewer</p>
                            <p className="text-xs text-slate-400 mt-1">
                                Search and select a pathway to view its interactive diagram
                            </p>
                        </div>
                    </div>
                )}

                {selectedId && (
                    <div className="flex-1 glass-panel relative">
                        {source === "reactome" ? (
                            <iframe
                                key={selectedId}
                                src={`https://reactome.org/PathwayBrowser/#/${selectedId}`}
                                className="w-full h-full border-0"
                                title={`Reactome Pathway ${selectedId}`}
                                sandbox="allow-scripts allow-same-origin allow-popups"
                            />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center">
                                <div className="text-center">
                                    <Layers size={40} className="text-slate-200 mx-auto mb-3" />
                                    <p className="text-sm text-slate-400">KEGG Pathway View</p>
                                    <p className="text-xs text-slate-400 mt-1">
                                        Pathway ID: {selectedId}
                                    </p>
                                    {detail?.url && (
                                        <a
                                            href={detail.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex items-center gap-1 mt-2 text-xs text-[var(--accent)] hover:underline"
                                        >
                                            Open on KEGG <ExternalLink size={10} />
                                        </a>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Participants bar */}
                <div className="h-[110px] glass-panel border-t px-4 py-3 flex flex-col">
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-1.5 flex items-center gap-1.5">
                        <Dna size={10} />
                        Pathway Participants
                    </div>

                    {!selectedId && (
                        <p className="text-xs text-[var(--text-muted)]">
                            Genes, proteins, and molecules involved in the selected pathway
                        </p>
                    )}

                    {selectedId && detailQ.isLoading && (
                        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                            <Loader2 size={12} className="animate-spin" /> Loading participants...
                        </div>
                    )}

                    {selectedId && detail && detail.genes && (
                        <div className="flex-1 overflow-x-auto overflow-y-hidden">
                            <div className="flex gap-1.5 flex-nowrap pb-1">
                                {detail.genes.map(gene => (
                                    <span
                                        key={gene}
                                        className="shrink-0 px-2 py-1 text-[10px] font-mono rounded bg-indigo-50 text-[var(--accent)] border border-indigo-100"
                                    >
                                        {gene}
                                    </span>
                                ))}
                                {detail.genes.length === 0 && (
                                    <span className="text-xs text-[var(--text-muted)]">No gene participants found</span>
                                )}
                            </div>
                            <div className="text-[10px] text-[var(--text-muted)] mt-1">
                                {detail.gene_count} gene{detail.gene_count !== 1 ? "s" : ""} total
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* ── Right — Pathway Details ──────────────────── */}
            <div className="w-[240px] glass-panel border-l flex flex-col">
                <div className="p-3 border-b" style={{ borderColor: "var(--border)" }}>
                    <h3 className="text-xs font-semibold text-[var(--text-primary)]">Pathway Details</h3>
                </div>
                <div className="flex-1 overflow-y-auto p-3">
                    {!selectedId && (
                        <p className="text-xs text-[var(--text-muted)]">Select a pathway to see details</p>
                    )}

                    {selectedId && detailQ.isLoading && (
                        <div className="flex items-center justify-center py-6">
                            <Loader2 size={16} className="animate-spin text-[var(--text-muted)]" />
                        </div>
                    )}

                    {selectedId && detailQ.isError && (
                        <p className="text-xs text-red-500">Failed to load pathway details.</p>
                    )}

                    {selectedId && detail && (
                        <div className="space-y-3">
                            <div className="space-y-2 text-xs">
                                <div>
                                    <span className="font-medium text-[var(--text-secondary)]">ID:</span>
                                    <span className="ml-1.5 text-[var(--text-muted)] font-mono">{detail.id}</span>
                                </div>
                                <div>
                                    <span className="font-medium text-[var(--text-secondary)]">Source:</span>
                                    <span className="ml-1.5">
                                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                            source === "reactome"
                                                ? "bg-indigo-50 text-indigo-600"
                                                : "bg-emerald-50 text-emerald-600"
                                        }`}>
                                            {source === "reactome" ? "Reactome" : "KEGG"}
                                        </span>
                                    </span>
                                </div>
                                <div>
                                    <span className="font-medium text-[var(--text-secondary)]">Name:</span>
                                    <span className="ml-1.5 text-[var(--text-primary)]">{detail.canonical_name}</span>
                                </div>
                                <div>
                                    <span className="font-medium text-[var(--text-secondary)]">Gene Count:</span>
                                    <span className="ml-1.5 text-[var(--text-primary)] font-medium">
                                        {detail.gene_count ?? 0}
                                    </span>
                                </div>
                            </div>

                            {/* External link */}
                            {detail.url && (
                                <div className="pt-2 border-t" style={{ borderColor: "var(--border)" }}>
                                    <a
                                        href={detail.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-1 text-xs text-[var(--accent)] hover:underline"
                                    >
                                        View on {source === "reactome" ? "Reactome" : "KEGG"}
                                        <ExternalLink size={10} />
                                    </a>
                                </div>
                            )}

                            {/* Gene list summary */}
                            {detail.genes && detail.genes.length > 0 && (
                                <div className="pt-2 border-t" style={{ borderColor: "var(--border)" }}>
                                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-1.5">
                                        Top Genes
                                    </div>
                                    <div className="flex flex-wrap gap-1">
                                        {detail.genes.slice(0, 15).map(gene => (
                                            <span
                                                key={gene}
                                                className="px-1.5 py-0.5 text-[9px] rounded bg-slate-100 text-slate-600 font-mono"
                                            >
                                                {gene}
                                            </span>
                                        ))}
                                        {detail.genes.length > 15 && (
                                            <span className="px-1.5 py-0.5 text-[9px] text-[var(--text-muted)]">
                                                +{detail.genes.length - 15} more
                                            </span>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Placeholder details when nothing is loaded */}
                    {selectedId && !detailQ.isLoading && !detail && !detailQ.isError && (
                        <div className="space-y-2 text-xs text-[var(--text-muted)]">
                            <div><span className="font-medium text-[var(--text-secondary)]">ID:</span> {selectedId}</div>
                            <div><span className="font-medium text-[var(--text-secondary)]">Source:</span> {source}</div>
                            <div><span className="font-medium text-[var(--text-secondary)]">Species:</span> --</div>
                            <div><span className="font-medium text-[var(--text-secondary)]">Gene Count:</span> --</div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
