/** Contradictions — Side-by-side Source A ⚔️ Source B dispute audit.
 *  Shows active contradictions with matched claim cards, assessment, and resolution actions.
 */

import { useState, useEffect } from "react";
import { AlertTriangle, CheckCircle, Flag, Loader2 } from "lucide-react";
import { ensureApiBase } from "@/lib/api";

interface ContradictionSource {
    claim: string;
    source: string;
    id: string;
    year: number;
    detail: string;
}

interface Contradiction {
    number: number;
    title: string;
    sourceA: ContradictionSource;
    sourceB: ContradictionSource;
    assessment: string;
    resolved: boolean;
}

const DEMO_CONTRADICTIONS: Contradiction[] = [
    {
        number: 1,
        title: "EGFR T790M Resistance Frequency",
        sourceA: {
            claim: "T790M accounts for 50-60% of resistance cases",
            source: "PubMed",
            id: "PMID:38291045 · 2024 · Cited 142x · Meta-analysis (n=2,847)",
            year: 2024,
            detail: "Meta-analysis",
        },
        sourceB: {
            claim: "T790M frequency declining to 30-40% with liquid biopsy",
            source: "PubMed",
            id: "PMID:37891234 · 2023 · Cited 89x · Prospective cohort (n=1,203)",
            year: 2023,
            detail: "Prospective cohort",
        },
        assessment: "Both sources are credible. Discrepancy may reflect detection methodology (tissue biopsy vs. liquid biopsy) and temporal trends as 3rd-gen TKIs become first-line.",
        resolved: false,
    },
    {
        number: 2,
        title: "APOE ε2 Protective vs. Risk Variant",
        sourceA: {
            claim: "APOE ε2 is protective against AD (OR=0.56)",
            source: "GWAS",
            id: "Study:GCST90027158 · 2023 · n=788,989",
            year: 2023,
            detail: "GWAS",
        },
        sourceB: {
            claim: "APOE ε2 homozygosity associated with Type III hyperlipoproteinemia",
            source: "DisGeNET",
            id: "GDA:C0020479 · Score: 0.78 · 34 publications",
            year: 2024,
            detail: "Genetic association",
        },
        assessment: "Not a true contradiction — APOE ε2 is protective for AD but a risk factor for a different condition (hyperlipoproteinemia). Recommend recording both with disease specificity.",
        resolved: false,
    },
    {
        number: 3,
        title: "BACE1 Inhibitor Clinical Viability",
        sourceA: {
            claim: "Verubecestat Phase III: cognitive worsening vs. placebo",
            source: "ClinicalTrials",
            id: "NCT01739348 · 2024 · Phase III (n=1,958)",
            year: 2024,
            detail: "Clinical trial",
        },
        sourceB: {
            claim: "Next-gen BACE1 inhibitors show improved benefit-risk in preclinical",
            source: "PubMed",
            id: "PMID:39012445 · 2024 · Cited 12x · Review",
            year: 2024,
            detail: "Review article",
        },
        assessment: "Temporal evidence gap — clinical failure of first-gen BACE1 inhibitors does not preclude second-gen candidates. Flag for expert pharmacology review.",
        resolved: false,
    },
];

const SOURCE_COLORS: Record<string, string> = {
    PubMed: "#3b82f6",
    GWAS: "#f59e0b",
    DisGeNET: "#8b5cf6",
    ClinicalTrials: "#10b981",
    ChEMBL: "#0891b2",
};

export default function Contradictions() {
    const [contradictions, setContradictions] = useState<Contradiction[]>(DEMO_CONTRADICTIONS);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        (async () => {
            try {
                const base = await ensureApiBase();
                const res = await fetch(`${base}/evidence/contradictions`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.length) setContradictions(data);
                }
            } catch {
                // Use demo data
            }
        })();
    }, []);

    const handleAction = (cNum: number, action: string) => {
        // In production, would POST to backend
        if (action === "include_both") {
            setContradictions(cs => cs.map(c => c.number === cNum ? { ...c, resolved: true } : c));
        }
    };

    const activeCount = contradictions.filter(c => !c.resolved).length;

    return (
        <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
            <h1 className="text-xl mb-1" style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>
                Contradiction Audit
            </h1>
            <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
                Cross-evidence contradiction detection · Source-vs-source comparison · Conflict resolution workflow
            </p>

            {/* Summary bar */}
            <div
                className="flex items-center gap-4 py-2.5 px-4 mb-5"
                style={{ borderLeft: "3px solid #C48820", background: "var(--bg-surface)" }}
            >
                <span className="text-sm font-bold" style={{ color: "#C48820" }}>
                    {activeCount} active contradiction{activeCount !== 1 ? "s" : ""}
                </span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Project: Alzheimer's Pipeline
                </span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Last scan: 2m ago
                </span>
            </div>

            {loading && (
                <div className="flex items-center justify-center py-16">
                    <Loader2 size={20} className="animate-spin" style={{ color: "var(--accent)" }} />
                </div>
            )}

            {/* Contradiction cards */}
            {contradictions.map(c => (
                <div
                    key={c.number}
                    className="mb-5 pb-5"
                    style={{ borderLeft: `3px solid ${c.resolved ? "#2D8B5F" : "#C48820"}`, paddingLeft: 16 }}
                >
                    <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle size={16} style={{ color: c.resolved ? "#2D8B5F" : "#C48820" }} />
                        <span className="text-sm font-semibold">
                            Contradiction #{c.number}: {c.title}
                        </span>
                        {c.resolved && (
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded" style={{ background: "#ecfdf5", color: "#047857" }}>
                                ✓ Resolved
                            </span>
                        )}
                    </div>

                    {/* Source A vs Source B cards */}
                    <div className="flex gap-3 mb-3">
                        {/* Source A */}
                        <div
                            className="flex-1 p-4 rounded-sm"
                            style={{ border: "1px solid var(--border)", background: "#fdf8f0" }}
                        >
                            <div className="text-[9px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "#C48820" }}>
                                Source A
                            </div>
                            <div className="text-sm font-semibold mb-2" style={{ lineHeight: 1.4 }}>
                                "{c.sourceA.claim}"
                            </div>
                            <div className="flex items-center gap-2 text-[10px]">
                                <span
                                    className="px-1.5 py-0.5 rounded-sm font-bold text-white text-[8px]"
                                    style={{ background: SOURCE_COLORS[c.sourceA.source] || "#6b7280" }}
                                >
                                    {c.sourceA.source}
                                </span>
                                <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "9px" }}>
                                    {c.sourceA.id}
                                </span>
                            </div>
                        </div>

                        {/* VS separator */}
                        <div className="flex items-center">
                            <span className="text-lg" title="versus">⚔️</span>
                        </div>

                        {/* Source B */}
                        <div
                            className="flex-1 p-4 rounded-sm"
                            style={{ border: "1px solid var(--border)", background: "#fdf8f0" }}
                        >
                            <div className="text-[9px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "#C48820" }}>
                                Source B
                            </div>
                            <div className="text-sm font-semibold mb-2" style={{ lineHeight: 1.4 }}>
                                "{c.sourceB.claim}"
                            </div>
                            <div className="flex items-center gap-2 text-[10px]">
                                <span
                                    className="px-1.5 py-0.5 rounded-sm font-bold text-white text-[8px]"
                                    style={{ background: SOURCE_COLORS[c.sourceB.source] || "#6b7280" }}
                                >
                                    {c.sourceB.source}
                                </span>
                                <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "9px" }}>
                                    {c.sourceB.id}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Assessment */}
                    <div className="text-[11px] mb-3" style={{ color: "var(--text-secondary)", lineHeight: 1.6 }}>
                        <strong>Assessment:</strong> {c.assessment}
                    </div>

                    {/* Actions */}
                    {!c.resolved && (
                        <div className="flex gap-2">
                            <button
                                className="btn-primary px-3 py-1.5 text-[10px] flex items-center gap-1"
                                onClick={() => handleAction(c.number, "include_both")}
                            >
                                → Include Both in Dossier
                            </button>
                            <button className="px-3 py-1.5 text-[10px] border rounded flex items-center gap-1" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>
                                <CheckCircle size={10} /> Accept Source A
                            </button>
                            <button className="px-3 py-1.5 text-[10px] border rounded flex items-center gap-1" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>
                                <CheckCircle size={10} /> Accept Source B
                            </button>
                            <button className="px-3 py-1.5 text-[10px] border rounded flex items-center gap-1" style={{ borderColor: "var(--border)", color: "#C48820" }}>
                                <Flag size={10} /> Flag for Expert Review
                            </button>
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}
