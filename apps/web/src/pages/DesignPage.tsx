/** Molecule Design Studio — 6-step SOTA workflow. */

import { useState, useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
    FlaskConical, Target, Search, Play, Download, Loader2, BarChart3,
    ArrowRight, CheckCircle2, Circle, Beaker, FileText, RefreshCw,
    ChevronDown, AlertCircle, Box, Plus, Settings2
} from "lucide-react";
import {
    moleculeScoreAPI, moleculeADMETAPI, moleculeAnalogsAPI,
    moleculeNoveltyAPI, designIterationsAPI, dockingRunAPI,
    type PhysiochemProps, type ADMETResult, type DockingRequest,
} from "@/lib/api";

const STEPS = [
    { id: 1, label: "Target & Site", icon: <Target size={14} /> },
    { id: 2, label: "Starting Ligands", icon: <FlaskConical size={14} /> },
    { id: 3, label: "Analogs", icon: <RefreshCw size={14} /> },
    { id: 4, label: "Score", icon: <BarChart3 size={14} /> },
    { id: 5, label: "Novelty", icon: <FileText size={14} /> },
    { id: 6, label: "Summary", icon: <Beaker size={14} /> },
] as const;

export default function DesignPage() {
    const [step, setStep] = useState(1);
    const [targetPdb, setTargetPdb] = useState("");
    const [center, setCenter] = useState([0, 0, 0]);
    const [boxSize, setBoxSize] = useState([20, 20, 20]);
    const [smilesList, setSmilesList] = useState<string[]>([]);
    const [smilesInput, setSmilesInput] = useState("");
    const [analogMethod, setAnalogMethod] = useState("similarity");
    const [bindingSiteMethod, setBindingSiteMethod] = useState("fpocket");

    // API mutations
    const scoreMut = useMutation({ mutationFn: (s: string[]) => moleculeScoreAPI(s) });
    const admetMut = useMutation({ mutationFn: (s: string[]) => moleculeADMETAPI(s) });
    const analogsMut = useMutation({ mutationFn: ({ smiles, method }: { smiles: string; method: string }) => moleculeAnalogsAPI(smiles, method) });
    const noveltyMut = useMutation({ mutationFn: (s: string) => moleculeNoveltyAPI(s) });
    const iterationsQ = useQuery({ queryKey: ["designIterations"], queryFn: designIterationsAPI, enabled: step === 6 });

    const addSmiles = () => {
        if (smilesInput.trim()) {
            setSmilesList(prev => [...prev, smilesInput.trim()]);
            setSmilesInput("");
        }
    };

    return (
        <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
            <div className="max-w-[1200px] mx-auto px-6 py-5">
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">Molecule Design Studio</h1>
                <p className="text-xs text-[var(--text-muted)] mb-5">Target → Ligands → Analogs → Score → Novelty → Report</p>

                {/* Stepper */}
                <div className="glass-card rounded-xl p-3 mb-5 flex items-center gap-1">
                    {STEPS.map((s, i) => (
                        <div key={s.id} className="flex items-center gap-1">
                            <button onClick={() => setStep(s.id)}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${step === s.id ? "bg-indigo-50 text-[var(--accent)]" : step > s.id ? "text-green-600" : "text-[var(--text-muted)]"
                                    }`}>
                                {step > s.id ? <CheckCircle2 size={13} /> : s.icon}
                                <span className="hidden md:inline">{s.label}</span>
                            </button>
                            {i < STEPS.length - 1 && <ArrowRight size={12} className="text-[var(--border)] shrink-0" />}
                        </div>
                    ))}
                </div>

                {/* Step content */}
                <div className="grid grid-cols-3 gap-4">
                    {/* Main content */}
                    <div className="col-span-2 glass-card rounded-xl p-5">
                        {step === 1 && (
                            <div className="space-y-4">
                                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2"><Target size={14} /> Choose Target & Binding Site</h2>
                                <div>
                                    <label className="text-xs font-medium text-[var(--text-secondary)] mb-1 block">Receptor PDB ID</label>
                                    <input type="text" value={targetPdb} onChange={e => setTargetPdb(e.target.value)} placeholder="e.g. 6LU7"
                                        className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                                </div>
                                <div>
                                    <label className="text-xs font-medium text-[var(--text-secondary)] mb-1 block">Binding Site Selection</label>
                                    <select value={bindingSiteMethod} onChange={e => setBindingSiteMethod(e.target.value)} className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }}>
                                        <option value="fpocket">Auto-detect pockets (fpocket)</option>
                                        <option value="ligand">Ligand-based (select co-crystallized ligand)</option>
                                        <option value="p2rank">P2Rank prediction</option>
                                        <option value="manual">Manual coordinates</option>
                                    </select>
                                </div>
                                <div className="grid grid-cols-3 gap-2">
                                    <div><label className="text-[10px] text-[var(--text-muted)]">Center X</label><input type="number" value={center[0]} onChange={e => setCenter([+e.target.value, center[1], center[2]])} className="w-full px-2 py-1.5 text-xs rounded border" style={{ borderColor: "var(--border)" }} /></div>
                                    <div><label className="text-[10px] text-[var(--text-muted)]">Center Y</label><input type="number" value={center[1]} onChange={e => setCenter([center[0], +e.target.value, center[2]])} className="w-full px-2 py-1.5 text-xs rounded border" style={{ borderColor: "var(--border)" }} /></div>
                                    <div><label className="text-[10px] text-[var(--text-muted)]">Center Z</label><input type="number" value={center[2]} onChange={e => setCenter([center[0], center[1], +e.target.value])} className="w-full px-2 py-1.5 text-xs rounded border" style={{ borderColor: "var(--border)" }} /></div>
                                </div>
                                <div className="grid grid-cols-3 gap-2">
                                    <div><label className="text-[10px] text-[var(--text-muted)]">Box X</label><input type="number" value={boxSize[0]} onChange={e => setBoxSize([+e.target.value, boxSize[1], boxSize[2]])} className="w-full px-2 py-1.5 text-xs rounded border" style={{ borderColor: "var(--border)" }} /></div>
                                    <div><label className="text-[10px] text-[var(--text-muted)]">Box Y</label><input type="number" value={boxSize[1]} onChange={e => setBoxSize([boxSize[0], +e.target.value, boxSize[2]])} className="w-full px-2 py-1.5 text-xs rounded border" style={{ borderColor: "var(--border)" }} /></div>
                                    <div><label className="text-[10px] text-[var(--text-muted)]">Box Z</label><input type="number" value={boxSize[2]} onChange={e => setBoxSize([boxSize[0], boxSize[1], +e.target.value])} className="w-full px-2 py-1.5 text-xs rounded border" style={{ borderColor: "var(--border)" }} /></div>
                                </div>
                                <button onClick={() => setStep(2)} className="px-4 py-2 rounded-lg text-xs font-medium text-white" style={{ background: "var(--accent)" }}>Continue →</button>
                            </div>
                        )}

                        {step === 2 && (
                            <div className="space-y-4">
                                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2"><FlaskConical size={14} /> Starting Ligands</h2>
                                <div className="flex gap-2">
                                    <input type="text" value={smilesInput} onChange={e => setSmilesInput(e.target.value)}
                                        onKeyDown={e => e.key === "Enter" && addSmiles()}
                                        placeholder="Enter SMILES string…" className="flex-1 px-3 py-2 text-xs rounded-lg border font-mono" style={{ borderColor: "var(--border)" }} />
                                    <button onClick={addSmiles} className="px-3 py-2 rounded-lg text-xs border hover:bg-gray-50" style={{ borderColor: "var(--border)" }}><Plus size={12} /></button>
                                </div>

                                {smilesList.length > 0 && (
                                    <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                                        <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">{smilesList.length} Ligands</div>
                                        {smilesList.map((s, i) => (
                                            <div key={i} className="flex items-center gap-2 py-1 border-b border-dashed" style={{ borderColor: "var(--border-light)" }}>
                                                <span className="text-[10px] text-[var(--text-muted)] w-6">{i + 1}.</span>
                                                <span className="text-xs font-mono text-[var(--text-secondary)] flex-1 truncate">{s}</span>
                                                <button onClick={() => setSmilesList(prev => prev.filter((_, j) => j !== i))} className="text-[10px] text-red-400 hover:text-red-600">✕</button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                                <button onClick={() => setStep(3)} disabled={smilesList.length === 0}
                                    className="px-4 py-2 rounded-lg text-xs font-medium text-white disabled:opacity-40" style={{ background: "var(--accent)" }}>Continue →</button>
                            </div>
                        )}

                        {step === 3 && (
                            <div className="space-y-4">
                                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2"><RefreshCw size={14} /> Generate Analogs</h2>
                                <div className="flex gap-2">
                                    <select value={analogMethod} onChange={e => setAnalogMethod(e.target.value)} className="px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }}>
                                        <option value="similarity">Tanimoto Similarity (PubChem)</option>
                                        <option value="scaffold_hop">Scaffold Hopping (Murcko)</option>
                                        <option value="enumeration">R-group Enumeration</option>
                                        <option value="diffusion">Diffusion-based (plugin)</option>
                                    </select>
                                    <button onClick={() => analogsMut.mutate({ smiles: smilesList[0], method: analogMethod })}
                                        disabled={analogsMut.isPending || smilesList.length === 0}
                                        className="px-4 py-2 rounded-lg text-xs font-medium text-white disabled:opacity-40" style={{ background: "var(--accent)" }}>
                                        {analogsMut.isPending ? <Loader2 size={14} className="animate-spin" /> : "Generate"}
                                    </button>
                                </div>
                                {analogsMut.data && (
                                    <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                                        <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Analogs</div>
                                        {((analogsMut.data as any).analogs || []).map((a: any, i: number) => (
                                            <div key={i} className="flex items-center gap-2 py-1 border-b border-dashed" style={{ borderColor: "var(--border-light)" }}>
                                                <span className="text-xs font-mono text-[var(--text-secondary)] flex-1 truncate">{a.smiles || a.scaffold || JSON.stringify(a)}</span>
                                                {a.mw && <span className="text-[10px] text-[var(--text-muted)]">MW:{a.mw}</span>}
                                                <button onClick={() => setSmilesList(prev => [...prev, a.smiles || a.scaffold])} className="text-[10px] text-[var(--accent)]">+ Add</button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                                <button onClick={() => setStep(4)} className="px-4 py-2 rounded-lg text-xs font-medium text-white" style={{ background: "var(--accent)" }}>Continue →</button>
                            </div>
                        )}

                        {step === 4 && (
                            <div className="space-y-4">
                                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2"><BarChart3 size={14} /> Score Compounds</h2>
                                <div className="flex gap-2">
                                    <button onClick={() => scoreMut.mutate(smilesList)} disabled={scoreMut.isPending}
                                        className="px-4 py-2 rounded-lg text-xs font-medium text-white disabled:opacity-40" style={{ background: "var(--accent)" }}>
                                        {scoreMut.isPending ? <Loader2 size={14} className="animate-spin" /> : "Physicochemical"}
                                    </button>
                                    <button onClick={() => admetMut.mutate(smilesList)} disabled={admetMut.isPending}
                                        className="px-4 py-2 rounded-lg text-xs border hover:bg-gray-50 disabled:opacity-40" style={{ borderColor: "var(--border)" }}>
                                        {admetMut.isPending ? <Loader2 size={14} className="animate-spin" /> : "ADMET"}
                                    </button>
                                </div>
                                {scoreMut.data && <ScoreTable data={scoreMut.data} />}
                                {admetMut.data && <ADMETSummary data={admetMut.data} />}
                                <button onClick={() => setStep(5)} className="px-4 py-2 rounded-lg text-xs font-medium text-white" style={{ background: "var(--accent)" }}>Continue →</button>
                            </div>
                        )}

                        {step === 5 && (
                            <div className="space-y-4">
                                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2"><FileText size={14} /> Novelty Validation</h2>
                                {smilesList.map((s, i) => (
                                    <div key={i} className="flex gap-2 items-start">
                                        <span className="text-xs font-mono text-[var(--text-muted)] w-48 truncate shrink-0">{s}</span>
                                        <button onClick={() => noveltyMut.mutate(s)} disabled={noveltyMut.isPending} className="px-2 py-1 text-[10px] rounded border hover:bg-gray-50" style={{ borderColor: "var(--border)" }}>Check</button>
                                    </div>
                                ))}
                                {noveltyMut.data && (
                                    <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                                        <div className={`text-sm font-semibold ${(noveltyMut.data as any).novelty_assessment === "potentially_novel" ? "text-green-600" : "text-amber-600"}`}>
                                            {(noveltyMut.data as any).novelty_assessment === "potentially_novel" ? "✓ Potentially Novel" : "⚠ Known Compound"}
                                        </div>
                                        <div className="text-xs text-[var(--text-muted)] mt-1">
                                            Publications: {(noveltyMut.data as any).publication_hits} | Patents: {(noveltyMut.data as any).patent_hits}
                                        </div>
                                    </div>
                                )}
                                <button onClick={() => setStep(6)} className="px-4 py-2 rounded-lg text-xs font-medium text-white" style={{ background: "var(--accent)" }}>Continue →</button>
                            </div>
                        )}

                        {step === 6 && (
                            <div className="space-y-4">
                                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2"><Beaker size={14} /> Iteration Summary</h2>
                                <div className="grid grid-cols-3 gap-3 text-xs">
                                    <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                                        <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">Target</div>
                                        <div className="font-medium mt-0.5">{targetPdb || "—"}</div>
                                    </div>
                                    <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                                        <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">Compounds</div>
                                        <div className="font-medium mt-0.5">{smilesList.length}</div>
                                    </div>
                                    <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                                        <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">Status</div>
                                        {scoreMut.data || admetMut.data || noveltyMut.data ? (
                                            <div className="font-medium mt-0.5 text-green-600">Data collected — ready to export</div>
                                        ) : (
                                            <div className="font-medium mt-0.5 text-amber-600">No scoring data yet</div>
                                        )}
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <button onClick={() => {
                                            const bundle = { target: targetPdb, bindingSite: bindingSiteMethod, center, boxSize, compounds: smilesList, scores: scoreMut.data || null, admet: admetMut.data || null, novelty: noveltyMut.data || null, exportedAt: new Date().toISOString() };
                                            const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
                                            const url = URL.createObjectURL(blob);
                                            const a = document.createElement("a"); a.href = url; a.download = `design_bundle_${targetPdb || "export"}.json`; a.click();
                                            URL.revokeObjectURL(url);
                                        }}
                                        className="px-4 py-2 rounded-lg text-xs font-medium text-white" style={{ background: "var(--accent)" }}>
                                        <Download size={12} className="inline mr-1" /> Export Bundle (JSON)
                                    </button>

                                </div>
                                {iterationsQ.data && (iterationsQ.data as any[]).length > 0 && (
                                    <div className="rounded-lg border p-3 mt-4" style={{ borderColor: "var(--border)" }}>
                                        <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Previous Iterations</div>
                                        {(iterationsQ.data as any[]).map((it: any) => (
                                            <div key={it.iteration_id} className="flex items-center gap-2 py-1 text-xs border-b border-dashed" style={{ borderColor: "var(--border-light)" }}>
                                                <span className="font-mono text-[var(--accent)]">{it.iteration_id}</span>
                                                <span className="text-[var(--text-muted)]">{it.target}</span>
                                                <span className="text-[var(--text-muted)]">{it.num_compounds} cpds</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Sidebar — context panel */}
                    <div className="space-y-4">
                        <div className="glass-card rounded-xl p-4">
                            <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Compound Library</h3>
                            <div className="text-xs text-[var(--text-muted)]">{smilesList.length} compound(s)</div>
                            <div className="mt-2 space-y-1 max-h-[200px] overflow-y-auto">
                                {smilesList.map((s, i) => (
                                    <div key={i} className="text-[10px] font-mono text-[var(--text-secondary)] truncate py-0.5">{s}</div>
                                ))}
                            </div>
                        </div>
                        <div className="glass-card rounded-xl p-4">
                            <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Docking Config</h3>
                            <div className="text-xs space-y-1">
                                <div className="flex justify-between"><span className="text-[var(--text-muted)]">Engine</span><span>AutoDock Vina</span></div>
                                <div className="flex justify-between"><span className="text-[var(--text-muted)]">Target</span><span>{targetPdb || "—"}</span></div>
                                <div className="flex justify-between"><span className="text-[var(--text-muted)]">Center</span><span className="font-mono">{center.join(", ")}</span></div>
                            </div>
                        </div>
                        <div className="glass-card rounded-xl p-4">
                            <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Plugins</h3>
                            <div className="space-y-1 text-xs">
                                {[
                                    { name: "RDKit", status: "not detected", hint: "Install python rdkit package" },
                                    { name: "AutoDock Vina", status: "not detected", hint: "Install vina binary" },
                                    { name: "fpocket", status: "not detected", hint: "Install fpocket binary" },
                                    { name: "AiZynthFinder", status: "not available", hint: "Planned for future release" },
                                    { name: "Diffusion Model", status: "not available", hint: "Planned for future release" },
                                ].map(p => (
                                    <div key={p.name} className="flex items-center justify-between py-0.5" title={p.hint}>
                                        <span className="text-[var(--text-secondary)]">{p.name}</span>
                                        <span className={`text-[9px] px-1 py-0.5 rounded ${p.status === "not detected" ? "bg-amber-50 text-amber-600" : "bg-slate-100 text-slate-400"}`}>{p.status}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ─── Score Table ──────────────────────────────────────── */

function ScoreTable({ data }: { data: PhysiochemProps[] }) {
    return (
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--border)" }}>
            <table className="w-full text-xs">
                <thead><tr className="bg-[var(--bg-app)]">
                    {["SMILES", "MW", "LogP", "HBD", "HBA", "TPSA", "Rotatable", "Lipinski", "Drug-like"].map(h => (
                        <th key={h} className="px-2 py-1.5 text-left text-[9px] font-semibold text-[var(--text-muted)] uppercase">{h}</th>
                    ))}
                </tr></thead>
                <tbody>{data.map((d, i) => (
                    <tr key={i} className="border-t" style={{ borderColor: "var(--border-light)" }}>
                        <td className="px-2 py-1 font-mono max-w-[120px] truncate">{d.smiles}</td>
                        <td className="px-2 py-1">{d.mw ?? "—"}</td>
                        <td className="px-2 py-1">{d.logp ?? "—"}</td>
                        <td className="px-2 py-1">{d.hbd}</td>
                        <td className="px-2 py-1">{d.hba}</td>
                        <td className="px-2 py-1">{d.tpsa ?? "—"}</td>
                        <td className="px-2 py-1">{d.rotatable_bonds}</td>
                        <td className="px-2 py-1">{d.lipinski_violations}</td>
                        <td className="px-2 py-1"><span className={d.druglikeness === "pass" ? "text-green-600" : "text-amber-600"}>{d.druglikeness}</span></td>
                    </tr>
                ))}</tbody>
            </table>
        </div>
    );
}

function ADMETSummary({ data }: { data: ADMETResult[] }) {
    return (
        <div className="space-y-2">
            {data.map((d, i) => (
                <div key={i} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                    <div className="text-xs font-mono text-[var(--text-secondary)] mb-2 truncate">{d.smiles}</div>
                    <div className="grid grid-cols-5 gap-2">
                        {(["absorption", "distribution", "metabolism", "excretion", "toxicity"] as const).map(cat => (
                            <div key={cat}>
                                <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase mb-1">{cat}</div>
                                {Object.entries(d[cat]).map(([k, v]) => (
                                    <div key={k} className="text-[10px] py-0.5">
                                        <span className="text-[var(--text-muted)]">{k.replace(/_/g, " ")}:</span>{" "}
                                        <span className={typeof v === "boolean" ? (v ? "text-amber-600" : "text-green-600") : "text-[var(--text-primary)]"}>
                                            {typeof v === "boolean" ? (v ? "Yes" : "No") : String(v)}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        ))}
                    </div>
                    <div className="mt-2 text-[10px] text-[var(--text-muted)]">SA: {d.synthetic_accessibility && (d.synthetic_accessibility as any).feasibility || "—"}</div>
                </div>
            ))}
        </div>
    );
}
