/** WorkspacePage — Home Dashboard with metrics, connector health, and activity table.
 *  Matches the mockup's data-rich home cockpit layout.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
    Search, Database, Network, Target, FlaskConical, FileText,
    Activity, Cpu, AlertTriangle, CheckCircle, ArrowRight
} from "lucide-react";
import { ensureApiBase, healthAPI } from "@/lib/api";

interface MetricCard {
    label: string;
    value: string;
    sub: string;
    trend: string;
    icon: React.ReactNode;
}

const CONNECTORS = [
    { name: "PubMed", status: "active" }, { name: "ChEMBL", status: "active" },
    { name: "DisGeNET", status: "active" }, { name: "OpenTargets", status: "active" },
    { name: "KEGG", status: "active" }, { name: "UniProt", status: "active" },
    { name: "STRING", status: "active" }, { name: "ClinicalTrials", status: "active" },
    { name: "RCSB PDB", status: "active" }, { name: "DrugBank", status: "active" },
    { name: "GWAS Catalog", status: "active" }, { name: "Reactome", status: "active" },
    { name: "PheKnowLator", status: "active" }, { name: "BioGRID", status: "active" },
    { name: "PharmGKB", status: "degraded" }, { name: "COSMIC", status: "degraded" },
    { name: "IntAct", status: "active" }, { name: "Ensembl", status: "active" },
];

const ACTIVITIES = [
    { action: "Evidence search", detail: "EGFR T790M resistance mechanisms", tag: "Search", time: "2m ago", route: "/search" },
    { action: "Target ranked", detail: "EGFR → Rank #1 (Score: 0.94)", tag: "Target", time: "5m ago", route: "/targets" },
    { action: "Contradiction detected", detail: "T790M resistance frequency discrepancy", tag: "Alert", time: "8m ago", route: "/contradictions" },
    { action: "UniProt batch map", detail: "12 proteins → 10 resolved, 2 pending", tag: "Mapping", time: "12m ago", route: "/uniprot-mapping" },
    { action: "PICO verified", detail: "EGFR meta-analysis → Strong grade", tag: "Quality", time: "15m ago", route: "/pico" },
    { action: "Arena session", detail: "EGFR T790M Candidates — 3 compounds", tag: "Arena", time: "20m ago", route: "/syntharena" },
    { action: "Dossier created", detail: "Alzheimer's EGFR Dossier (12 sections)", tag: "Output", time: "30m ago", route: "/dossiers" },
    { action: "Model loaded", detail: "ESM2-8M embedding model activated", tag: "Model", time: "45m ago", route: "/models" },
];

export default function WorkspacePage() {
    const [metrics, setMetrics] = useState<MetricCard[]>([
        { label: "Evidence Items", value: "47", sub: "across 7 sources", trend: "+12 today", icon: <Search size={16} /> },
        { label: "KG Nodes", value: "82,415", sub: "243,891 edges", trend: "+1,204 this week", icon: <Network size={16} /> },
        { label: "Targets Ranked", value: "8", sub: "NSCLC pipeline", trend: "Top: EGFR (0.94)", icon: <Target size={16} /> },
        { label: "Active Models", value: "5", sub: "3 local, 2 cloud", trend: "ESM2, PubMedBERT", icon: <Cpu size={16} /> },
        { label: "Contradictions", value: "3", sub: "2 pending review", trend: "1 resolved", icon: <AlertTriangle size={16} /> },
        { label: "Dossiers", value: "3", sub: "47 total citations", trend: "Last: Mar 24", icon: <FileText size={16} /> },
    ]);
    const navigate = useNavigate();

    const tagColor = (tag: string) => {
        const m: Record<string, string> = {
            Search: "#3b82f6", Target: "#8b5cf6", Alert: "#C48820", Mapping: "#0891b2",
            Quality: "#2D8B5F", Arena: "#ef4444", Output: "#10b981", Model: "#6366f1",
        };
        return m[tag] || "#6b7280";
    };

    return (
        <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
            <h1 className="text-xl mb-1" style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>
                Home
            </h1>
            <p className="text-xs mb-5" style={{ color: "var(--text-muted)" }}>
                Project: Alzheimer's Pipeline · Drug discovery cockpit · Last sync: 2m ago
            </p>

            {/* Metric cards grid */}
            <div className="grid grid-cols-6 gap-3 mb-6">
                {metrics.map(m => (
                    <div key={m.label} className="p-3" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
                        <div className="flex items-center gap-1.5 mb-1.5">
                            <span style={{ color: "var(--accent)" }}>{m.icon}</span>
                            <span className="text-[9px] font-bold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
                                {m.label}
                            </span>
                        </div>
                        <div className="text-lg font-bold" style={{ fontFamily: "var(--font-display)" }}>{m.value}</div>
                        <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{m.sub}</div>
                        <div className="text-[9px] mt-1" style={{ color: "var(--accent)" }}>{m.trend}</div>
                    </div>
                ))}
            </div>

            <div className="grid grid-cols-3 gap-4">
                {/* Left column — Connector Health */}
                <div className="col-span-1">
                    <div className="section-label mb-2">Connector Health ({CONNECTORS.length})</div>
                    <div className="p-3" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
                        <div className="flex flex-wrap gap-1.5">
                            {CONNECTORS.map(c => (
                                <span
                                    key={c.name}
                                    className="flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9px] font-medium"
                                    style={{
                                        background: c.status === "active" ? "#ecfdf5" : "#fffbeb",
                                        color: c.status === "active" ? "#047857" : "#b45309",
                                        border: `1px solid ${c.status === "active" ? "#d1fae5" : "#fde68a"}`,
                                    }}
                                >
                                    <span
                                        className="w-1 h-1 rounded-full"
                                        style={{ background: c.status === "active" ? "#2D8B5F" : "#C48820" }}
                                    />
                                    {c.name}
                                </span>
                            ))}
                        </div>
                    </div>

                    {/* Embedding Models */}
                    <div className="section-label mb-2 mt-4">Embedding & AI Models</div>
                    <div className="p-3 space-y-2" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
                        {[
                            { name: "ESM2-8M", type: "Protein", status: "active" },
                            { name: "PubMedBERT", type: "Text", status: "active" },
                            { name: "ChemBERTa", type: "Molecule", status: "active" },
                            { name: "Llama 3 8B", type: "RAG / Chat", status: "degraded" },
                            { name: "BioMistral", type: "Scientific QA", status: "offline" },
                        ].map(m => (
                            <div key={m.name} className="flex items-center justify-between text-[10px]">
                                <div>
                                    <span className="font-semibold">{m.name}</span>
                                    <span className="ml-1" style={{ color: "var(--text-muted)" }}>({m.type})</span>
                                </div>
                                <span className="flex items-center gap-1"
                                    style={{ color: m.status === "active" ? "#2D8B5F" : m.status === "degraded" ? "#C48820" : "#C43D2F" }}
                                >
                                    {m.status === "active" ? <CheckCircle size={9} /> : <AlertTriangle size={9} />}
                                    {m.status}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Right column — Activity feed + Quick Actions */}
                <div className="col-span-2">
                    <div className="section-label mb-2">Recent Activity</div>
                    <div style={{ border: "1px solid var(--border)" }}>
                        {ACTIVITIES.map((a, i) => (
                            <div
                                key={i}
                                className="flex items-center gap-3 py-2.5 px-3 cursor-pointer transition-colors hover:bg-[var(--accent-subtle)]"
                                style={{ borderBottom: i < ACTIVITIES.length - 1 ? "1px solid var(--border)" : "none" }}
                                onClick={() => navigate(a.route)}
                            >
                                <span
                                    className="text-[8px] font-bold px-1.5 py-0.5 rounded-sm"
                                    style={{ background: tagColor(a.tag), color: "#fff", minWidth: 48, textAlign: "center" }}
                                >
                                    {a.tag}
                                </span>
                                <div className="flex-1 min-w-0">
                                    <span className="text-[11px] font-semibold">{a.action}</span>
                                    <span className="text-[11px] ml-2" style={{ color: "var(--text-muted)" }}>{a.detail}</span>
                                </div>
                                <span className="text-[9px] shrink-0" style={{ color: "var(--text-muted)" }}>{a.time}</span>
                                <ArrowRight size={11} style={{ color: "var(--text-muted)" }} />
                            </div>
                        ))}
                    </div>

                    {/* Quick actions */}
                    <div className="section-label mb-2 mt-4">Quick Actions</div>
                    <div className="flex gap-2">
                        <button className="btn-primary px-3 py-1.5 text-[10px] flex items-center gap-1" onClick={() => navigate("/search")}>
                            <Search size={10} /> New Evidence Search
                        </button>
                        <button className="px-3 py-1.5 text-[10px] border rounded flex items-center gap-1"
                            style={{ borderColor: "var(--border)", color: "var(--accent)" }}
                            onClick={() => navigate("/targets")}
                        >
                            <Target size={10} /> Run Target Prioritization
                        </button>
                        <button className="px-3 py-1.5 text-[10px] border rounded flex items-center gap-1"
                            style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                            onClick={() => navigate("/syntharena")}
                        >
                            <FlaskConical size={10} /> Open SynthArena
                        </button>
                        <button className="px-3 py-1.5 text-[10px] border rounded flex items-center gap-1"
                            style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                            onClick={() => navigate("/export")}
                        >
                            <Database size={10} /> Export Center
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
