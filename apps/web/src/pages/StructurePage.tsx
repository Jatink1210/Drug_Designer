/** Structure Workbench — RCSB-grade, all 7 tabs functional. */

import { useState, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Search, Box, Download, Loader2, ExternalLink } from "lucide-react";
import {
    structureSummaryAPI, structureAnnotationsAPI, structureExperimentAPI,
    structureSequenceAPI, structureSearchAPI,
    type StructureSummary, type StructureAnnotations, type ExperimentData, type SequenceData,
} from "@/lib/api";
import ConfidenceBar from "@/components/ui/ConfidenceBar";
import MolstarViewer from "@/components/viewer/MolstarViewer";

const TABS = ["Summary", "3D Structure", "Annotations", "Experiment", "Sequence", "Genome", "Versions"] as const;
type Tab = typeof TABS[number];

export default function StructurePage() {
    const navigate = useNavigate();
    const [query, setQuery] = useState("");
    const [pdbId, setPdbId] = useState("");
    const [activeTab, setActiveTab] = useState<Tab>("Summary");
    const [source, setSource] = useState<"pdb" | "alphafold">("pdb");
    const [afUniprotId, setAfUniprotId] = useState("");

    const summaryQ = useQuery({ queryKey: ["structure", pdbId, source], queryFn: () => structureSummaryAPI(pdbId), enabled: !!pdbId && source === "pdb" });
    const annotationsQ = useQuery({ queryKey: ["annotations", pdbId], queryFn: () => structureAnnotationsAPI(pdbId), enabled: !!pdbId && activeTab === "Annotations" });
    const experimentQ = useQuery({ queryKey: ["experiment", pdbId], queryFn: () => structureExperimentAPI(pdbId), enabled: !!pdbId && activeTab === "Experiment" });
    const sequenceQ = useQuery({ queryKey: ["sequence", pdbId], queryFn: () => structureSequenceAPI(pdbId), enabled: !!pdbId && activeTab === "Sequence" });
    const searchMut = useMutation({ mutationFn: (q: string) => structureSearchAPI(q) });

    const handleSearch = useCallback(() => {
        if (!query.trim()) return;
        // Check if it looks like a PDB ID (4 chars, starts with digit)
        const q = query.trim();
        if (/^\d[A-Za-z0-9]{3}$/.test(q)) {
            setPdbId(q.toUpperCase());
            setAfUniprotId("");
            setSource("pdb");
        } else if (/^[A-Z][0-9][A-Z0-9]{3,8}[0-9]$/i.test(q)) {
            // UniProt-like
            setPdbId("");
            setAfUniprotId(q.toUpperCase());
            setSource("alphafold");
        } else {
            searchMut.mutate(q);
        }
    }, [query, searchMut]);

    const data = summaryQ.data;
    const loading = summaryQ.isLoading || searchMut.isPending;
    const isAlphaFold = source === "alphafold" && !!afUniprotId;

    return (
        <div className="flex-1 flex overflow-hidden" style={{ background: "var(--bg-app)" }}>
            {/* Left — Navigator */}
            <div className="w-[280px] glass-sidebar border-r flex flex-col overflow-hidden">
                <div className="p-3 border-b" style={{ borderColor: "var(--border)" }}>
                    <h2 className="text-xs font-semibold text-[var(--text-primary)] mb-2">Structure Navigator</h2>
                    <div className="relative">
                        <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                        <input type="text" value={query} onChange={e => setQuery(e.target.value)}
                            onKeyDown={e => e.key === "Enter" && handleSearch()}
                            placeholder="PDB ID, UniProt, protein name…"
                            className="w-full pl-8 pr-3 py-1.5 text-xs rounded border bg-[var(--bg-app)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                            style={{ borderColor: "var(--border)" }} />
                    </div>
                    <div className="flex gap-1 mt-2">
                        <button onClick={() => setSource("pdb")} className={`flex-1 px-2 py-1 rounded text-[11px] font-medium ${source === "pdb" ? "bg-indigo-50 text-[var(--accent)]" : "text-[var(--text-muted)]"}`}>RCSB PDB</button>
                        <button onClick={() => setSource("alphafold")} className={`flex-1 px-2 py-1 rounded text-[11px] font-medium ${source === "alphafold" ? "bg-indigo-50 text-[var(--accent)]" : "text-[var(--text-muted)]"}`}>AlphaFold</button>
                    </div>
                </div>

                {/* Search results list */}
                <div className="flex-1 overflow-y-auto p-2">
                    {searchMut.data && (
                        <div className="space-y-0.5">
                            {((searchMut.data as any).result_set || []).map((r: any) => (
                                <button key={r.identifier} onClick={() => { setPdbId(r.identifier); setSource("pdb"); }}
                                    className={`w-full text-left px-2 py-1.5 text-xs rounded transition-colors ${pdbId === r.identifier ? "bg-indigo-50 text-[var(--accent)]" : "text-[var(--text-secondary)] hover:bg-gray-50"}`}>
                                    <div className="font-medium">{r.identifier}</div>
                                    <div className="text-[10px] text-[var(--text-muted)] truncate">{r.score?.toFixed(1)}</div>
                                </button>
                            ))}
                        </div>
                    )}
                    {!searchMut.data && !data && <p className="text-xs text-[var(--text-muted)] p-2">Enter a PDB ID or search term</p>}
                </div>

                {/* Quality metrics from loaded structure */}
                {data && (
                    <div className="p-3 border-t space-y-1" style={{ borderColor: "var(--border)" }}>
                        <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-1">Quality</div>
                        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                            <span className="text-[var(--text-muted)]">Resolution</span><span className="text-[var(--text-primary)] font-medium">{data.resolution ? data.resolution + " Å" : "—"}</span>
                            <span className="text-[var(--text-muted)]">Method</span><span className="text-[var(--text-primary)]">{data.method || "—"}</span>
                            <span className="text-[var(--text-muted)]">R-work</span><span className="text-[var(--text-primary)]">{data.r_work ?? "—"}</span>
                            <span className="text-[var(--text-muted)]">R-free</span><span className="text-[var(--text-primary)]">{data.r_free ?? "—"}</span>
                            <span className="text-[var(--text-muted)]">Released</span><span className="text-[var(--text-primary)]">{data.release_date?.slice(0, 10) || "—"}</span>
                        </div>
                    </div>
                )}
            </div>

            {/* Center */}
            <div className="flex-1 flex flex-col overflow-hidden">
                <div className="glass-panel border-b px-4 flex gap-0">
                    {TABS.map(t => (
                        <button key={t} onClick={() => setActiveTab(t)}
                            className={`px-3 py-2 text-[11px] font-medium border-b-2 ${activeTab === t ? "border-[var(--accent)] text-[var(--accent)]" : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]"}`}>{t}</button>
                    ))}
                </div>

                {loading && <div className="flex-1 flex items-center justify-center"><Loader2 size={20} className="animate-spin text-[var(--text-muted)]" /></div>}

                {!loading && !data && !isAlphaFold && (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="text-center">
                            <Box size={48} className="text-slate-200 mx-auto mb-3" />
                            <p className="text-sm text-slate-400">Enter a PDB ID or search term</p>
                        </div>
                    </div>
                )}

                {!loading && isAlphaFold && !data && (
                    <div className="flex-1 overflow-y-auto">
                        {activeTab === "3D Structure" ? (
                            <MolstarViewer pdbId={afUniprotId} source="alphafold" />
                        ) : (
                            <div className="p-5 space-y-4 max-w-[900px]">
                                <div className="rounded-lg border p-4" style={{ borderColor: "var(--border)" }}>
                                    <h2 className="text-base font-semibold text-[var(--text-primary)] mb-2">AlphaFold Predicted Structure</h2>
                                    <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] mb-3">
                                        <span className="px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 font-medium">{afUniprotId}</span>
                                        <span>AlphaFold DB Prediction</span>
                                    </div>
                                    <p className="text-xs text-[var(--text-secondary)]">
                                        This is an AI-predicted structure from AlphaFold DB. PDB summary, annotations, and experimental data
                                        are not available for predicted structures. Switch to the <strong>3D Structure</strong> tab to view the model.
                                    </p>
                                    <a href={`https://alphafold.ebi.ac.uk/entry/${afUniprotId}`} target="_blank" rel="noopener noreferrer"
                                       className="inline-flex items-center gap-1 mt-3 text-xs text-[var(--accent)]">
                                        View on AlphaFold DB <ExternalLink size={10} />
                                    </a>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {!loading && data && (
                    <div className="flex-1 overflow-y-auto">
                        {activeTab === "Summary" && <SummaryTab data={data} />}
                        {activeTab === "3D Structure" && <Viewer3DTab pdbId={data.pdb_id} source={source} />}
                        {activeTab === "Annotations" && <AnnotationsTab data={annotationsQ.data} loading={annotationsQ.isLoading} />}
                        {activeTab === "Experiment" && <ExperimentTab data={experimentQ.data} loading={experimentQ.isLoading} />}
                        {activeTab === "Sequence" && <SequenceTab sequences={sequenceQ.data} loading={sequenceQ.isLoading} />}
                        {activeTab === "Genome" && <GenomeTab data={data} />}
                        {activeTab === "Versions" && <VersionsTab data={data} />}
                    </div>
                )}
            </div>

            {/* Right — Downloads & Actions */}
            {(data || isAlphaFold) && (
                <div className="w-[240px] glass-panel border-l flex flex-col overflow-hidden">
                    <div className="p-3 border-b" style={{ borderColor: "var(--border)" }}>
                        <h3 className="text-xs font-semibold text-[var(--text-primary)]">Downloads</h3>
                    </div>
                    <div className="p-3 space-y-1">
                        {data ? Object.entries(data.downloads).map(([label, url]) => (
                            <a key={label} href={url} target="_blank" rel="noopener noreferrer"
                                className="flex items-center gap-2 px-2 py-1.5 text-xs rounded hover:bg-gray-50 text-[var(--text-secondary)]">
                                <Download size={11} className="text-[var(--text-muted)]" /> {label.replace(/_/g, " ")}
                            </a>
                        )) : isAlphaFold ? (
                            <p className="text-[10px] text-[var(--text-muted)] px-2 py-1">
                                Download options for AlphaFold predictions are available on the AlphaFold DB website.
                            </p>
                        ) : null}
                    </div>
                    <div className="p-3 border-t" style={{ borderColor: "var(--border)" }}>
                        <h3 className="text-xs font-semibold text-[var(--text-primary)] mb-2">Quick Actions</h3>
                        <div className="space-y-1">
                            <button
                                onClick={() => navigate(`/design?pdb=${data?.pdb_id || afUniprotId}`)}
                                className="w-full text-left px-2 py-1.5 text-xs rounded hover:bg-gray-50 text-[var(--text-secondary)]">
                                → Open in Design Studio
                            </button>
                        </div>

                    </div>
                    <div className="p-3 border-t mt-auto" style={{ borderColor: "var(--border)" }}>
                        {data ? (
                            <a href={data.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-[var(--accent)]">
                                View on RCSB <ExternalLink size={10} />
                            </a>
                        ) : isAlphaFold ? (
                            <a href={`https://alphafold.ebi.ac.uk/entry/${afUniprotId}`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-[var(--accent)]">
                                View on AlphaFold DB <ExternalLink size={10} />
                            </a>
                        ) : null}
                    </div>
                </div>
            )}
        </div>
    );
}

/* ─── Summary Tab ─────────────────────────────────────── */

function SummaryTab({ data }: { data: StructureSummary }) {
    return (
        <div className="p-5 space-y-5 max-w-[900px]">
            <div>
                <h2 className="text-base font-semibold text-[var(--text-primary)] mb-1">{data.title}</h2>
                <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                    <span className="px-1.5 py-0.5 rounded bg-indigo-50 text-[var(--accent)] font-medium">{data.pdb_id}</span>
                    <span>{data.classification}</span>
                    <span>•</span>
                    <span>{data.organism}</span>
                </div>
            </div>

            {/* Key metrics row */}
            <div className="grid grid-cols-5 gap-3">
                {[
                    { label: "Method", value: data.method },
                    { label: "Resolution", value: data.resolution ? data.resolution + " Å" : "—" },
                    { label: "R-work / R-free", value: `${data.r_work ?? "—"} / ${data.r_free ?? "—"}` },
                    { label: "Space Group", value: data.space_group || "—" },
                    { label: "Deposited", value: data.deposition_date?.slice(0, 10) || "—" },
                ].map(m => (
                    <div key={m.label} className="rounded-lg border p-2.5" style={{ borderColor: "var(--border)" }}>
                        <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase">{m.label}</div>
                        <div className="text-xs font-medium text-[var(--text-primary)] mt-0.5">{m.value}</div>
                    </div>
                ))}
            </div>

            {/* Citation */}
            {data.primary_citation.title && (
                <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-1">Primary Citation</div>
                    <p className="text-xs text-[var(--text-primary)]">{data.primary_citation.title}</p>
                    <p className="text-[10px] text-[var(--text-muted)] mt-0.5">{data.primary_citation.journal} ({data.primary_citation.year})</p>
                    <div className="flex gap-2 mt-1">
                        {data.primary_citation.doi && <a href={`https://doi.org/${data.primary_citation.doi}`} target="_blank" rel="noopener noreferrer" className="text-[10px] text-[var(--accent)]">DOI</a>}
                        {data.primary_citation.pmid && <a href={`https://pubmed.ncbi.nlm.nih.gov/${data.primary_citation.pmid}`} target="_blank" rel="noopener noreferrer" className="text-[10px] text-[var(--accent)]">PubMed</a>}
                    </div>
                </div>
            )}

            {/* Macromolecules table */}
            {data.macromolecules.length > 0 && (
                <div>
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Macromolecule Entities</div>
                    <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--border)" }}>
                        <table className="w-full text-xs">
                            <thead><tr className="bg-[var(--bg-app)]">
                                {["Entity", "Chains", "Length", "Organism", "UniProt", "Description"].map(h => (
                                    <th key={h} className="px-2 py-1.5 text-left text-[9px] font-semibold text-[var(--text-muted)] uppercase">{h}</th>
                                ))}
                            </tr></thead>
                            <tbody>
                                {data.macromolecules.map(m => (
                                    <tr key={m.entity_id} className="border-t" style={{ borderColor: "var(--border-light)" }}>
                                        <td className="px-2 py-1.5 font-medium">{m.entity_id}</td>
                                        <td className="px-2 py-1.5">{m.chains.join(", ")}</td>
                                        <td className="px-2 py-1.5">{m.length}</td>
                                        <td className="px-2 py-1.5 text-[var(--text-muted)]">{m.organism}</td>
                                        <td className="px-2 py-1.5">{m.uniprot_ids.map(u => (
                                            <a key={u} href={`https://www.uniprot.org/uniprot/${u}`} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] mr-1">{u}</a>
                                        ))}</td>
                                        <td className="px-2 py-1.5 text-[var(--text-muted)] max-w-[200px] truncate">{m.description}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Ligands */}
            {data.ligands.length > 0 && (
                <div>
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Chemical Components / Ligands</div>
                    <div className="flex flex-wrap gap-2">
                        {data.ligands.map(l => (
                            <div key={l.comp_id} className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--border)" }}>
                                <div className="text-xs font-semibold text-[var(--accent)]">{l.comp_id}</div>
                                <div className="text-[10px] text-[var(--text-muted)]">{l.name}</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Assemblies */}
            {data.assemblies.length > 0 && (
                <div>
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Biological Assemblies</div>
                    <div className="flex flex-wrap gap-2">
                        {data.assemblies.map(a => (
                            <div key={a.assembly_id} className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--border)" }}>
                                <div className="text-xs font-medium">Assembly {a.assembly_id}</div>
                                <div className="text-[10px] text-[var(--text-muted)]">{a.oligomeric_state} • {a.polymer_entity_count} chains</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

/* ─── 3D Structure (Mol* viewer) ───────────────────────── */

function Viewer3DTab({ pdbId, source }: { pdbId: string; source: "pdb" | "alphafold" }) {
    return (
        <MolstarViewer
            pdbId={pdbId}
            source={source === "alphafold" ? "alphafold" : "rcsb"}
        />
    );
}

/* ─── Annotations Tab ─────────────────────────────────── */

function AnnotationsTab({ data, loading }: { data?: StructureAnnotations; loading: boolean }) {
    if (loading) return <CenterLoader />;
    if (!data) return <EmptyState text="No annotation data" />;
    return (
        <div className="p-5 space-y-4 max-w-[900px]">
            <AnnotationSection title="Pfam Domains" items={data.pfam} />
            <AnnotationSection title="InterPro" items={data.interpro} />
            <AnnotationSection title="Gene Ontology" items={data.go} />
            <AnnotationSection title="EC Numbers" items={data.ec} />
            {data.ptms.length > 0 && <AnnotationSection title="Post-Translational Modifications" items={data.ptms as any} />}
        </div>
    );
}

function AnnotationSection({ title, items }: { title: string; items: Array<{ id: string; name: string }> }) {
    if (!items || items.length === 0) return null;
    return (
        <div>
            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">{title}</div>
            <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--border)" }}>
                <table className="w-full text-xs">
                    <thead><tr className="bg-[var(--bg-app)]"><th className="px-2 py-1.5 text-left text-[9px] font-semibold text-[var(--text-muted)] uppercase">ID</th><th className="px-2 py-1.5 text-left text-[9px] font-semibold text-[var(--text-muted)] uppercase">Name</th></tr></thead>
                    <tbody>{items.map((it, i) => (
                        <tr key={i} className="border-t" style={{ borderColor: "var(--border-light)" }}>
                            <td className="px-2 py-1 text-[var(--accent)]">{it.id}</td>
                            <td className="px-2 py-1">{it.name}</td>
                        </tr>
                    ))}</tbody>
                </table>
            </div>
        </div>
    );
}

/* ─── Experiment Tab ──────────────────────────────────── */

function ExperimentTab({ data, loading }: { data?: ExperimentData; loading: boolean }) {
    if (loading) return <CenterLoader />;
    if (!data) return <EmptyState text="No experiment data" />;
    return (
        <div className="p-5 space-y-4 max-w-[900px]">
            <PropGrid title="Data Collection" data={data.data_collection} />
            <PropGrid title="Crystal Growth" data={data.crystal_growth} />
            <PropGrid title="Refinement" data={data.refinement} />
            <PropGrid title="Unit Cell" data={data.cell} />
            {data.software.length > 0 && (
                <div>
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Software</div>
                    <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--border)" }}>
                        <table className="w-full text-xs">
                            <thead><tr className="bg-[var(--bg-app)]">{["Name", "Version", "Classification"].map(h => <th key={h} className="px-2 py-1.5 text-left text-[9px] font-semibold text-[var(--text-muted)] uppercase">{h}</th>)}</tr></thead>
                            <tbody>{data.software.map((s, i) => (
                                <tr key={i} className="border-t" style={{ borderColor: "var(--border-light)" }}>
                                    <td className="px-2 py-1 font-medium">{s.name}</td>
                                    <td className="px-2 py-1 text-[var(--text-muted)]">{s.version}</td>
                                    <td className="px-2 py-1 text-[var(--text-muted)]">{s.classification}</td>
                                </tr>
                            ))}</tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}

function PropGrid({ title, data }: { title: string; data: Record<string, unknown> }) {
    const entries = Object.entries(data).filter(([, v]) => v != null && v !== "");
    if (entries.length === 0) return null;
    return (
        <div>
            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">{title}</div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                {entries.map(([k, v]) => (
                    <div key={k} className="flex justify-between py-0.5 border-b border-dashed" style={{ borderColor: "var(--border-light)" }}>
                        <span className="text-xs text-[var(--text-muted)]">{k.replace(/_/g, " ")}</span>
                        <span className="text-xs text-[var(--text-primary)] font-medium">{String(v)}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

/* ─── Sequence Tab ────────────────────────────────────── */

function SequenceTab({ sequences, loading }: { sequences?: SequenceData[]; loading: boolean }) {
    if (loading) return <CenterLoader />;
    if (!sequences || sequences.length === 0) return <EmptyState text="No sequence data" />;
    return (
        <div className="p-5 space-y-4 max-w-[900px]">
            {sequences.map(seq => (
                <div key={seq.entity_id} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-semibold text-[var(--text-primary)]">{seq.entity_id}</span>
                        <span className="text-[10px] text-[var(--text-muted)]">Chains: {seq.chains.join(", ")}</span>
                        <span className="text-[10px] text-[var(--text-muted)]">{seq.length} residues</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100">{seq.type}</span>
                    </div>
                    <pre className="text-[10px] font-mono text-[var(--text-secondary)] bg-[var(--bg-app)] p-2 rounded overflow-x-auto leading-relaxed whitespace-pre-wrap break-all">
                        {seq.sequence}
                    </pre>
                    {seq.features.length > 0 && (
                        <div className="mt-2">
                            <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase mb-1">Features</div>
                            <div className="flex flex-wrap gap-1">
                                {seq.features.map((f, i) => (
                                    <span key={i} className="px-1.5 py-0.5 text-[9px] rounded bg-indigo-50 text-[var(--accent)]">
                                        {f.name || f.type} {f.start && f.end ? `(${f.start}–${f.end})` : ""}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}

/* ─── Genome Tab ──────────────────────────────────────── */

function GenomeTab({ data }: { data: StructureSummary }) {
    const uniprotIds = data.macromolecules.flatMap(m => m.uniprot_ids);
    const geneNames = data.macromolecules.flatMap(m => m.gene_names);
    return (
        <div className="p-5 space-y-4 max-w-[900px]">
            <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Gene Mapping</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                    <div><span className="text-[var(--text-muted)]">Genes:</span> <span className="font-medium">{geneNames.join(", ") || "—"}</span></div>
                    <div><span className="text-[var(--text-muted)]">UniProt:</span> {uniprotIds.map(u => (
                        <a key={u} href={`https://www.uniprot.org/uniprot/${u}`} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] mr-1">{u}</a>
                    ))}</div>
                </div>
                <p className="text-[10px] text-[var(--text-muted)] mt-2">Ensembl genome browser integration and variant overlay require Ensembl REST API connector (planned).</p>
            </div>
        </div>
    );
}

/* ─── Versions Tab ────────────────────────────────────── */

function VersionsTab({ data }: { data: StructureSummary }) {
    return (
        <div className="p-5 space-y-4 max-w-[900px]">
            <div className="text-xs text-[var(--text-muted)]">{data.revision_count} revisions</div>
            <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--border)" }}>
                <table className="w-full text-xs">
                    <thead><tr className="bg-[var(--bg-app)]">{["Version", "Date", "Type"].map(h => <th key={h} className="px-2 py-1.5 text-left text-[9px] font-semibold text-[var(--text-muted)] uppercase">{h}</th>)}</tr></thead>
                    <tbody>{data.revision_history.map((r, i) => (
                        <tr key={i} className="border-t" style={{ borderColor: "var(--border-light)" }}>
                            <td className="px-2 py-1 font-medium">{r.version}</td>
                            <td className="px-2 py-1 text-[var(--text-muted)]">{r.date?.slice(0, 10)}</td>
                            <td className="px-2 py-1 text-[var(--text-muted)]">{r.type}</td>
                        </tr>
                    ))}</tbody>
                </table>
            </div>
        </div>
    );
}

/* ─── Helpers ─────────────────────────────────────────── */

function CenterLoader() { return <div className="flex-1 flex items-center justify-center p-12"><Loader2 size={20} className="animate-spin text-[var(--text-muted)]" /></div>; }
function EmptyState({ text }: { text: string }) { return <div className="flex-1 flex items-center justify-center p-12 text-xs text-[var(--text-muted)]">{text}</div>; }
