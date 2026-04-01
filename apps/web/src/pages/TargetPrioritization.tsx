/** TargetPrioritization — Split-panel ranked target list with evidence inspector.
 *  Left: ranked target list with score bars, source counts, contradiction counts.
 *  Right: inspector drawer with evidence list, source distribution, actions.
 *  Wires to POST /api/targets/prioritize (falls back to demo data).
 */

import { useState, useEffect } from "react";
import { Target, ExternalLink, AlertTriangle, ChevronRight, RefreshCw } from "lucide-react";
import { ensureApiBase } from "@/lib/api";

interface TargetEvidence {
    source: string;
    title: string;
    id: string;
    year: number;
    type: string;
}

interface RankedTarget {
    rank: number;
    gene: string;
    uniprotId: string;
    score: number;
    sourceCount: number;
    contradictions: number;
    gdaScore: number;
    evidence: TargetEvidence[];
    rationale: string;
}

const DEMO_TARGETS: RankedTarget[] = [
    {
        rank: 1, gene: "EGFR", uniprotId: "P00533", score: 0.94, sourceCount: 8,
        contradictions: 1, gdaScore: 0.91,
        rationale: "Highest genetic association across DisGeNET (GDA 0.91), OpenTargets (0.87), plus strong literature support (142 publications). 1 contradiction regarding T790M resistance frequency.",
        evidence: [
            { source: "DisGeNET", title: "EGFR GDA score 0.91 for NSCLC", id: "C0007131", year: 2024, type: "Association" },
            { source: "OpenTargets", title: "EGFR tractability: small molecule + antibody", id: "ENSG00000146648", year: 2024, type: "Tractability" },
            { source: "PubMed", title: "EGFR T790M gatekeeper mutation resistance", id: "PMID:38291045", year: 2024, type: "Literature" },
            { source: "ChEMBL", title: "Osimertinib IC50: 0.8 nM (T790M)", id: "CHEMBL3353410", year: 2024, type: "Bioactivity" },
            { source: "ClinicalTrials", title: "Phase III FLAURA-2: Osimertinib + chemo", id: "NCT04035486", year: 2023, type: "Clinical" },
        ],
    },
    {
        rank: 2, gene: "ALK", uniprotId: "Q9UM73", score: 0.87, sourceCount: 6,
        contradictions: 0, gdaScore: 0.84,
        rationale: "Strong ALK fusion association. 6 supporting sources with no contradictions. Multiple approved therapies validate target.",
        evidence: [
            { source: "DisGeNET", title: "ALK GDA 0.84 for NSCLC", id: "C0007131", year: 2024, type: "Association" },
            { source: "PubMed", title: "ALK rearrangements in NSCLC (5%)", id: "PMID:37891022", year: 2023, type: "Literature" },
            { source: "ChEMBL", title: "Lorlatinib IC50: 0.7 nM", id: "CHEMBL3039502", year: 2024, type: "Bioactivity" },
        ],
    },
    {
        rank: 3, gene: "KRAS", uniprotId: "P01116", score: 0.82, sourceCount: 7,
        contradictions: 0, gdaScore: 0.88,
        rationale: "KRAS G12C mutation targetable by sotorasib/adagrasib. High genetic association but historically 'undruggable' — now resolved.",
        evidence: [
            { source: "DisGeNET", title: "KRAS GDA 0.88 for NSCLC", id: "C0007131", year: 2024, type: "Association" },
            { source: "PubMed", title: "Sotorasib covalent G12C inhibition", id: "PMID:38102341", year: 2024, type: "Literature" },
        ],
    },
    {
        rank: 4, gene: "MET", uniprotId: "P08581", score: 0.76, sourceCount: 5,
        contradictions: 1, gdaScore: 0.72,
        rationale: "MET amplification as bypass resistance mechanism. 1 contradiction: some studies show MET exon 14 as independent driver vs. resistance mechanism.",
        evidence: [
            { source: "PubMed", title: "MET amplification as bypass resistance", id: "PMID:37891234", year: 2023, type: "Literature" },
            { source: "ChEMBL", title: "Capmatinib IC50: 0.13 nM", id: "CHEMBL4297578", year: 2023, type: "Bioactivity" },
        ],
    },
    {
        rank: 5, gene: "ROS1", uniprotId: "P08922", score: 0.71, sourceCount: 4,
        contradictions: 0, gdaScore: 0.65,
        rationale: "ROS1 fusions in ~2% of NSCLC. Crizotinib and entrectinib approved. Lower prevalence but high therapeutic confidence.",
        evidence: [
            { source: "DisGeNET", title: "ROS1 GDA 0.65 for NSCLC", id: "C0007131", year: 2024, type: "Association" },
        ],
    },
    {
        rank: 6, gene: "BRAF", uniprotId: "P15056", score: 0.68, sourceCount: 5,
        contradictions: 0, gdaScore: 0.71,
        rationale: "BRAF V600E in ~2% of NSCLC. Dabrafenib + trametinib approved combination.",
        evidence: [
            { source: "DisGeNET", title: "BRAF GDA 0.71 for NSCLC", id: "C0007131", year: 2024, type: "Association" },
        ],
    },
    {
        rank: 7, gene: "RET", uniprotId: "P07949", score: 0.63, sourceCount: 4,
        contradictions: 0, gdaScore: 0.58,
        rationale: "RET fusions in ~1-2% of NSCLC. Selpercatinib and pralsetinib are selective RET inhibitors.",
        evidence: [
            { source: "DisGeNET", title: "RET GDA 0.58 for NSCLC", id: "C0007131", year: 2024, type: "Association" },
        ],
    },
    {
        rank: 8, gene: "NTRK1", uniprotId: "P04629", score: 0.55, sourceCount: 3,
        contradictions: 0, gdaScore: 0.42,
        rationale: "NTRK fusions are rare (<1%) but highly actionable with larotrectinib/entrectinib.",
        evidence: [
            { source: "DisGeNET", title: "NTRK1 GDA 0.42 for NSCLC", id: "C0007131", year: 2024, type: "Association" },
        ],
    },
];

const SOURCE_COLORS: Record<string, string> = {
    DisGeNET: "#8b5cf6",
    OpenTargets: "#ef4444",
    PubMed: "#3b82f6",
    ChEMBL: "#0891b2",
    ClinicalTrials: "#10b981",
    KEGG: "#22c55e",
    GWAS: "#f59e0b",
    STRING: "#6366f1",
};

export default function TargetPrioritization() {
    const [targets, setTargets] = useState<RankedTarget[]>(DEMO_TARGETS);
    const [selected, setSelected] = useState<RankedTarget | null>(DEMO_TARGETS[0]);
    const [loading, setLoading] = useState(false);

    // Try to fetch from backend
    useEffect(() => {
        (async () => {
            try {
                const base = await ensureApiBase();
                const res = await fetch(`${base}/targets/prioritize`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ disease: "NSCLC", genes: ["EGFR", "ALK", "KRAS", "MET", "ROS1", "BRAF", "RET", "NTRK1"] }),
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.targets?.length) {
                        setTargets(data.targets);
                        setSelected(data.targets[0]);
                    }
                }
            } catch {
                // Use demo data
            }
        })();
    }, []);

    return (
        <div className="flex-1 flex overflow-hidden" style={{ background: "var(--bg-app)" }}>
            {/* Left panel — ranked list */}
            <div className="flex-1 overflow-y-auto p-6" style={{ borderRight: "1px solid var(--border)" }}>
                <div className="flex items-center justify-between mb-1">
                    <h1 className="text-xl" style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>
                        Target Prioritization
                    </h1>
                    <button
                        className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded transition-colors"
                        style={{ border: "1px solid var(--border)", color: "var(--accent)" }}
                        onClick={() => setLoading(l => !l)}
                    >
                        <RefreshCw size={10} className={loading ? "animate-spin" : ""} />
                        Re-rank
                    </button>
                </div>
                <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
                    Evidence-backed multi-source scoring · {targets.length} targets ranked · Disease: NSCLC
                </p>

                {/* Ranked target rows */}
                {targets.map(t => (
                    <div
                        key={t.gene}
                        className="flex items-center gap-3 py-3 px-3 cursor-pointer transition-colors"
                        style={{
                            borderBottom: "1px solid var(--border)",
                            background: selected?.gene === t.gene ? "var(--accent-subtle)" : "transparent",
                            borderLeft: selected?.gene === t.gene ? "3px solid var(--accent)" : "3px solid transparent",
                        }}
                        onClick={() => setSelected(t)}
                    >
                        {/* Rank */}
                        <div
                            className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0"
                            style={{
                                background: t.rank <= 3 ? "var(--accent)" : "var(--border)",
                                color: t.rank <= 3 ? "#fff" : "var(--text-muted)",
                            }}
                        >
                            {t.rank}
                        </div>

                        {/* Target info */}
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold">{t.gene}</span>
                                <span className="text-[9px] font-medium" style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                                    {t.uniprotId}
                                </span>
                            </div>
                            <div className="flex items-center gap-3 mt-1">
                                <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                                    {t.sourceCount} sources
                                </span>
                                {t.contradictions > 0 && (
                                    <span className="text-[10px] flex items-center gap-0.5" style={{ color: "#C48820" }}>
                                        <AlertTriangle size={9} /> {t.contradictions}
                                    </span>
                                )}
                                <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                                    GDA: {t.gdaScore.toFixed(2)}
                                </span>
                            </div>
                        </div>

                        {/* Score bar */}
                        <div className="w-24 shrink-0">
                            <div className="flex items-center justify-between text-[10px] font-semibold mb-0.5">
                                <span>Score</span>
                                <span style={{ color: "var(--accent)" }}>{t.score.toFixed(2)}</span>
                            </div>
                            <div className="w-full h-1.5 rounded-full" style={{ background: "var(--border)" }}>
                                <div
                                    className="h-full rounded-full"
                                    style={{
                                        width: `${t.score * 100}%`,
                                        background: t.score > 0.8 ? "#2D8B5F" : t.score > 0.6 ? "#C48820" : "#C43D2F",
                                    }}
                                />
                            </div>
                        </div>

                        <ChevronRight size={14} style={{ color: "var(--text-muted)" }} className="shrink-0" />
                    </div>
                ))}
            </div>

            {/* Right panel — inspector */}
            {selected && (
                <div className="w-[380px] shrink-0 overflow-y-auto p-5" style={{ background: "var(--bg-surface)" }}>
                    <div className="flex items-center gap-2 mb-1">
                        <Target size={18} style={{ color: "var(--accent)" }} />
                        <h2 className="text-lg font-bold" style={{ fontFamily: "var(--font-display)" }}>
                            {selected.gene}
                        </h2>
                        <span className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{ background: "var(--accent)", color: "#fff" }}>
                            Rank #{selected.rank}
                        </span>
                    </div>
                    <div className="text-[11px] mb-4" style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                        UniProt: {selected.uniprotId}
                    </div>

                    {/* Score breakdown */}
                    <div className="section-label mb-2">Score Breakdown</div>
                    <div className="flex items-center gap-3 mb-4">
                        <div className="flex-1">
                            <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>Overall Score</div>
                            <div className="text-lg font-bold" style={{ color: "var(--accent)" }}>{selected.score.toFixed(2)}</div>
                        </div>
                        <div className="flex-1">
                            <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>GDA Score</div>
                            <div className="text-lg font-bold">{selected.gdaScore.toFixed(2)}</div>
                        </div>
                        <div className="flex-1">
                            <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>Sources</div>
                            <div className="text-lg font-bold">{selected.sourceCount}</div>
                        </div>
                    </div>

                    {/* Why this rank? */}
                    <div className="section-label mb-2">Why This Rank?</div>
                    <div
                        className="text-[11px] p-3 mb-4"
                        style={{
                            color: "var(--text-secondary)",
                            background: "var(--bg-elevated)",
                            border: "1px solid var(--border)",
                            lineHeight: 1.6,
                        }}
                    >
                        {selected.rationale}
                    </div>

                    {/* Source distribution */}
                    <div className="section-label mb-2">Source Distribution</div>
                    <div className="flex gap-1 h-5 mb-2">
                        {selected.evidence.map((ev, i) => (
                            <div
                                key={i}
                                className="flex-1 rounded-sm"
                                style={{ background: SOURCE_COLORS[ev.source] || "#6b7280" }}
                                title={`${ev.source}: ${ev.title}`}
                            />
                        ))}
                    </div>
                    <div className="flex flex-wrap gap-x-3 gap-y-1 mb-4">
                        {[...new Set(selected.evidence.map(e => e.source))].map(src => (
                            <span key={src} className="flex items-center gap-1 text-[9px]">
                                <span className="w-2 h-2 rounded-sm" style={{ background: SOURCE_COLORS[src] || "#6b7280" }} />
                                {src}
                            </span>
                        ))}
                    </div>

                    {/* Evidence list */}
                    <div className="section-label mb-2">Evidence ({selected.evidence.length})</div>
                    {selected.evidence.map((ev, i) => (
                        <div
                            key={i}
                            className="py-2 text-[11px]"
                            style={{ borderBottom: "1px solid var(--border)" }}
                        >
                            <div className="flex items-center gap-1.5">
                                <span
                                    className="text-[8px] font-bold px-1 py-0.5 rounded-sm"
                                    style={{ background: SOURCE_COLORS[ev.source] || "#6b7280", color: "#fff" }}
                                >
                                    {ev.source}
                                </span>
                                <span className="font-medium">{ev.title}</span>
                            </div>
                            <div className="mt-0.5" style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "9px" }}>
                                {ev.id} · {ev.year} · {ev.type}
                            </div>
                        </div>
                    ))}

                    {/* Actions */}
                    <div className="flex gap-2 mt-4">
                        <button className="btn-primary px-3 py-1.5 text-[10px] flex items-center gap-1">
                            <ExternalLink size={10} /> → Dossier
                        </button>
                        <button className="px-3 py-1.5 text-[10px] border rounded flex items-center gap-1" style={{ borderColor: "var(--border)", color: "var(--accent)" }}>
                            → Design Studio
                        </button>
                        <button className="px-3 py-1.5 text-[10px] border rounded" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
                            Export
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
