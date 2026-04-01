import { useState } from "react";
import { Dna, Search, Loader2, ExternalLink, Globe, BookOpen } from "lucide-react";
import { ensureApiBase } from "@/lib/api";

type GeneResult = { gene_id: string; symbol: string; description: string; organism: string; uniprot_id?: string; ensembl_id?: string };

export default function GeneProteinExplorer() {
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<GeneResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [searched, setSearched] = useState(false);

    const search = async () => {
        if (!query.trim()) return;
        setLoading(true); setSearched(false);
        try {
            const base = await ensureApiBase();
            // Query UniProt for protein data
            const uniRes = await fetch(`https://rest.uniprot.org/uniprotkb/search?query=${encodeURIComponent(query)}&size=10&format=json`);
            const geneResults: GeneResult[] = [];
            if (uniRes.ok) {
                const data = await uniRes.json();
                for (const entry of (data.results || [])) {
                    geneResults.push({
                        gene_id: entry.primaryAccession || "",
                        symbol: entry.genes?.[0]?.geneName?.value || entry.primaryAccession || "",
                        description: entry.proteinDescription?.recommendedName?.fullName?.value || "",
                        organism: entry.organism?.scientificName || "",
                        uniprot_id: entry.primaryAccession || "",
                        ensembl_id: ""
                    });
                }
            }
            // Also try Ensembl if it looks like a gene symbol
            if (geneResults.length === 0 || query.length <= 10) {
                try {
                    const ensRes = await fetch(`https://rest.ensembl.org/xrefs/symbol/homo_sapiens/${encodeURIComponent(query)}?content-type=application/json`);
                    if (ensRes.ok) {
                        const ensData = await ensRes.json();
                        for (const x of ensData.slice(0, 5)) {
                            if (!geneResults.find(g => g.ensembl_id === x.id)) {
                                geneResults.push({ gene_id: x.id, symbol: query.toUpperCase(), description: x.type || "", organism: "Homo sapiens", ensembl_id: x.id });
                            }
                        }
                    }
                } catch { /* Ensembl may be rate limited */ }
            }
            setResults(geneResults);
        } catch { /* */ }
        setLoading(false); setSearched(true);
    };

    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1100px] mx-auto px-6 py-5">
                <div className="mb-6 flex justify-between items-center">
                    <div>
                        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Gene/Protein Explorer</h1>
                        <p className="text-xs text-[var(--text-muted)] mt-0.5">Deep inspection via live UniProt + Ensembl REST APIs.</p>
                    </div>
                    <div className="px-3 py-1 bg-surface border border-border rounded shadow-sm text-xs font-mono text-[var(--text-secondary)]">Target Space: Ensembl & UniProt</div>
                </div>

                <div className="glass-card p-5 mb-6">
                    <div className="flex gap-3">
                        <input type="text" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && search()}
                            placeholder="e.g. EGFR, BRCA1, P04637, ENSG00000146648..."
                            className="flex-1 p-2.5 rounded-lg border border-border bg-[var(--bg-app)] text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]" />
                        <button onClick={search} disabled={loading || !query.trim()} className="glass-button flex items-center gap-2 text-xs px-5 py-2">
                            {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} Search
                        </button>
                    </div>
                </div>

                {loading && <div className="flex justify-center py-16"><Loader2 size={24} className="animate-spin text-[var(--accent)]" /></div>}

                {searched && !loading && results.length === 0 && (
                    <div className="glass-card p-10 flex flex-col items-center text-center">
                        <Dna className="text-[var(--accent)] mb-4 opacity-70" size={48} />
                        <h2 className="text-sm text-[var(--text-primary)] font-medium mb-2">No Results Found</h2>
                        <p className="text-xs text-[var(--text-secondary)] max-w-md">Try a gene symbol (EGFR), UniProt accession (P04637), or Ensembl ID.</p>
                    </div>
                )}

                {results.length > 0 && (
                    <div className="glass-card overflow-hidden">
                        <div className="px-5 py-4 border-b border-border flex items-center gap-2">
                            <Dna size={16} className="text-[var(--accent)]" />
                            <h2 className="text-sm font-semibold text-[var(--text-primary)]">{results.length} Gene/Protein Matches</h2>
                        </div>
                        <table className="w-full text-left text-xs">
                            <thead>
                                <tr className="border-b border-border bg-surface/50">
                                    <th className="px-5 py-3 font-medium text-[var(--text-muted)]">Symbol</th>
                                    <th className="px-5 py-3 font-medium text-[var(--text-muted)]">Description</th>
                                    <th className="px-5 py-3 font-medium text-[var(--text-muted)]">Organism</th>
                                    <th className="px-5 py-3 font-medium text-[var(--text-muted)]">Links</th>
                                </tr>
                            </thead>
                            <tbody>
                                {results.map((g, i) => (
                                    <tr key={i} className="border-b border-border/50 hover:bg-surface/30 transition-colors">
                                        <td className="px-5 py-3 font-semibold text-[var(--accent)] font-mono">{g.symbol}</td>
                                        <td className="px-5 py-3 text-[var(--text-primary)] max-w-[300px] truncate">{g.description || "—"}</td>
                                        <td className="px-5 py-3 text-[var(--text-muted)] italic">{g.organism}</td>
                                        <td className="px-5 py-3">
                                            <div className="flex gap-2">
                                                {g.uniprot_id && <a href={`https://www.uniprot.org/uniprot/${g.uniprot_id}`} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] hover:underline flex items-center gap-0.5"><Globe size={10} /> UniProt</a>}
                                                {g.ensembl_id && <a href={`https://ensembl.org/Homo_sapiens/Gene/Summary?g=${g.ensembl_id}`} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:underline flex items-center gap-0.5"><BookOpen size={10} /> Ensembl</a>}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
