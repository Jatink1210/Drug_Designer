/** PICOVerification — PICO (Population, Intervention, Comparison, Outcome) quality grading table.
 *  4-column assessment with Strong/Moderate/Weak grading, progress bars, and grading key.
 */

import { useState, useEffect } from "react";
import { ensureApiBase } from "@/lib/api";

interface PICOItem {
    title: string;
    id: string;
    population: { text: string; status: "pass" | "partial" | "fail"; detail: string };
    intervention: { text: string; status: "pass" | "partial" | "fail"; detail: string };
    comparison: { text: string; status: "pass" | "partial" | "fail"; detail: string };
    outcome: { text: string; status: "pass" | "partial" | "fail"; detail: string };
    overall: "Strong" | "Moderate" | "Weak";
}

const DEMO_ITEMS: PICOItem[] = [
    {
        title: "EGFR T790M meta-analysis",
        id: "PMID:38291045",
        population: { text: "NSCLC\nn=2,847", status: "pass", detail: "Well-defined" },
        intervention: { text: "3rd-gen TKI", status: "pass", detail: "Clear intervention" },
        comparison: { text: "vs 1st/2nd gen", status: "pass", detail: "Active comparator" },
        outcome: { text: "PFS, OS", status: "pass", detail: "Hard endpoints" },
        overall: "Strong",
    },
    {
        title: "APOE ε4 GWAS",
        id: "GCST90027158",
        population: { text: "General\nn=788,989", status: "pass", detail: "Large N" },
        intervention: { text: "Observational", status: "partial", detail: "No intervention" },
        comparison: { text: "ε4 vs ε3", status: "pass", detail: "Genotype comparison" },
        outcome: { text: "AD risk OR", status: "pass", detail: "Defined outcome" },
        overall: "Strong",
    },
    {
        title: "Verubecestat Phase III",
        id: "NCT01739348",
        population: { text: "Mild-mod AD\nn=1,958", status: "pass", detail: "Clear eligibility" },
        intervention: { text: "BACE1 inh", status: "pass", detail: "Defined drug" },
        comparison: { text: "vs placebo", status: "pass", detail: "Placebo-controlled" },
        outcome: { text: "Worsening", status: "partial", detail: "Negative signal" },
        overall: "Moderate",
    },
    {
        title: "Next-gen BACE1 review",
        id: "PMID:39012445",
        population: { text: "Preclinical", status: "partial", detail: "No human data" },
        intervention: { text: "In vitro/vivo", status: "partial", detail: "Animal models" },
        comparison: { text: "No comparator", status: "fail", detail: "Missing" },
        outcome: { text: "Preliminary", status: "partial", detail: "Surrogate only" },
        overall: "Weak",
    },
];

const statusIcon = (s: "pass" | "partial" | "fail") =>
    s === "pass" ? "✓" : s === "partial" ? "~" : "✗";

const statusColor = (s: "pass" | "partial" | "fail") =>
    s === "pass" ? "#2D8B5F" : s === "partial" ? "#C48820" : "#C43D2F";

const overallBar = (o: "Strong" | "Moderate" | "Weak") => ({
    width: o === "Strong" ? "100%" : o === "Moderate" ? "60%" : "30%",
    color: o === "Strong" ? "#2D8B5F" : o === "Moderate" ? "#C48820" : "#C43D2F",
});

export default function PICOVerification() {
    const [items, setItems] = useState<PICOItem[]>(DEMO_ITEMS);

    useEffect(() => {
        (async () => {
            try {
                const base = await ensureApiBase();
                const res = await fetch(`${base}/evidence/pico`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.length) setItems(data);
                }
            } catch { /* demo data */ }
        })();
    }, []);

    return (
        <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
            <h1 className="text-xl mb-1" style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>
                PICO Verification
            </h1>
            <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
                Population · Intervention · Comparison · Outcome — structured evidence quality assessment
            </p>

            {/* Summary */}
            <div
                className="flex items-center gap-4 py-2.5 px-4 mb-5"
                style={{ borderLeft: "3px solid var(--accent)", background: "var(--bg-surface)" }}
            >
                <span className="text-sm font-semibold" style={{ color: "var(--accent)" }}>
                    {items.length} evidence items under review
                </span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Framework: PICO (Sackett 1997)
                </span>
            </div>

            {/* PICO table */}
            <div className="overflow-x-auto" style={{ border: "1px solid var(--border)" }}>
                <table className="w-full text-xs" style={{ minWidth: 800 }}>
                    <thead>
                        <tr style={{ background: "var(--bg-surface)" }}>
                            <th className="text-left py-2.5 px-3 font-semibold" style={{ width: 200, color: "var(--text-muted)" }}>Evidence</th>
                            <th className="text-center py-2.5 px-3 font-semibold" style={{ color: "var(--text-muted)" }}>Population</th>
                            <th className="text-center py-2.5 px-3 font-semibold" style={{ color: "var(--text-muted)" }}>Intervention</th>
                            <th className="text-center py-2.5 px-3 font-semibold" style={{ color: "var(--text-muted)" }}>Comparison</th>
                            <th className="text-center py-2.5 px-3 font-semibold" style={{ color: "var(--text-muted)" }}>Outcome</th>
                            <th className="text-center py-2.5 px-3 font-semibold" style={{ color: "var(--text-muted)" }}>Overall</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items.map(item => {
                            const ob = overallBar(item.overall);
                            return (
                                <tr key={item.id}>
                                    <td className="py-3 px-3" style={{ borderBottom: "1px solid var(--border)" }}>
                                        <div className="font-semibold">{item.title}</div>
                                        <div style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)", fontSize: "9px" }}>{item.id}</div>
                                    </td>
                                    {(["population", "intervention", "comparison", "outcome"] as const).map(col => {
                                        const cell = item[col];
                                        return (
                                            <td key={col} className="py-3 px-3 text-center" style={{ borderBottom: "1px solid var(--border)" }}>
                                                <span style={{ color: statusColor(cell.status), fontWeight: 600 }}>
                                                    {statusIcon(cell.status)} {cell.text.split("\n")[0]}
                                                </span>
                                                {cell.text.includes("\n") && (
                                                    <div style={{ color: "var(--accent)", fontSize: "10px" }}>
                                                        {cell.text.split("\n")[1]}
                                                    </div>
                                                )}
                                            </td>
                                        );
                                    })}
                                    <td className="py-3 px-3 text-center" style={{ borderBottom: "1px solid var(--border)" }}>
                                        <div className="flex flex-col items-center gap-1">
                                            <div className="w-16 h-2 rounded-full" style={{ background: "var(--border)" }}>
                                                <div className="h-full rounded-full" style={{ width: ob.width, background: ob.color }} />
                                            </div>
                                            <span className="text-[9px] font-bold" style={{ color: ob.color }}>
                                                {item.overall}
                                            </span>
                                        </div>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Grading key */}
            <div className="mt-4 p-4" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
                <div className="text-xs font-semibold mb-2">📋 PICO Grading Key</div>
                <div className="flex gap-6 text-[10px]">
                    <span className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-sm" style={{ background: "#2D8B5F" }} />
                        <strong>✓ Strong</strong> — Well-defined, large N, controlled
                    </span>
                    <span className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-sm" style={{ background: "#C48820" }} />
                        <strong>~ Moderate</strong> — Partially defined, observational, or small N
                    </span>
                    <span className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-sm" style={{ background: "#C43D2F" }} />
                        <strong>✗ Weak</strong> — Missing element, preclinical only, or no comparator
                    </span>
                </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2 mt-4">
                <button className="btn-primary px-3 py-1.5 text-[10px]">→ Add Verified to Dossier</button>
                <button className="px-3 py-1.5 text-[10px] border rounded" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>← Evidence Workspace</button>
                <button className="px-3 py-1.5 text-[10px] border rounded" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>Export PICO Table</button>
            </div>
        </div>
    );
}
