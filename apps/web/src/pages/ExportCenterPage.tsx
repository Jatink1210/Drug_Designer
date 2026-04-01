/** ExportCenterPage — Centralized export surface for all artifacts across all modules. */

import { useState, useEffect } from "react";
import { ensureApiBase } from "@/lib/api";
import { Download, FileText, Table2, Network, FlaskConical, Archive } from "lucide-react";

interface ExportItem {
    id: string;
    type: string;
    title: string;
    subtitle: string;
    formats: string[];
    created?: string;
}

interface ExportGroup {
    category: string;
    icon: React.ReactNode;
    items: ExportItem[];
}

const MOCK_GROUPS: ExportGroup[] = [
    {
        category: "Decision Dossiers",
        icon: <FileText size={16} />,
        items: [
            { id: "d1", type: "dossier", title: "Alzheimer's EGFR Dossier", subtitle: "12 sections · 47 citations", formats: ["HTML", "JSON", "PDF"], created: "Mar 24" },
            { id: "d2", type: "dossier", title: "NSCLC Resistance Analysis", subtitle: "8 sections · 23 citations", formats: ["HTML", "JSON"], created: "Mar 22" },
            { id: "d3", type: "dossier", title: "BACE1 Inhibitor Review", subtitle: "6 sections · 18 citations", formats: ["HTML", "JSON", "PDF"], created: "Mar 20" },
        ],
    },
    {
        category: "Evidence Tables",
        icon: <Table2 size={16} />,
        items: [
            { id: "e1", type: "evidence", title: "EGFR Inhibitors", subtitle: "47 items pinned", formats: ["CSV", "JSON"], created: "Mar 24" },
            { id: "e2", type: "evidence", title: "Alzheimer's Targets", subtitle: "12 items pinned", formats: ["CSV", "JSON"], created: "Mar 23" },
        ],
    },
    {
        category: "Disease Intelligence Workbooks",
        icon: <FileText size={16} />,
        items: [
            { id: "w1", type: "workbook", title: "Alzheimer's Pipeline", subtitle: "12 targets, 142 genes", formats: ["Excel"], created: "Mar 24" },
        ],
    },
    {
        category: "Graph Snapshots",
        icon: <Network size={16} />,
        items: [
            { id: "g1", type: "graph", title: "EGFR Subgraph", subtitle: "89 nodes, 234 edges", formats: ["JSON", "SVG"], created: "Mar 24" },
        ],
    },
    {
        category: "SynthArena Sessions",
        icon: <FlaskConical size={16} />,
        items: [
            { id: "a1", type: "arena", title: "EGFR T790M Candidates", subtitle: "3 candidates, 10 criteria", formats: ["CSV", "JSON"], created: "Mar 25" },
        ],
    },
    {
        category: "Molecule Reports",
        icon: <FlaskConical size={16} />,
        items: [
            { id: "m1", type: "molecule", title: "Osimertinib Analog Set", subtitle: "3 analogs, ADMET + binding", formats: ["CSV", "SDF"], created: "Mar 24" },
        ],
    },
    {
        category: "Run Recipes & Trace Bundles",
        icon: <Archive size={16} />,
        items: [
            { id: "r1", type: "trace", title: "Run #8 Context Bundle", subtitle: "Full reproducibility trace", formats: ["ZIP"], created: "Mar 24" },
            { id: "r2", type: "trace", title: "Run #5 Context Bundle", subtitle: "Full reproducibility trace", formats: ["ZIP"], created: "Mar 22" },
        ],
    },
];

export default function ExportCenterPage() {
    const [groups, setGroups] = useState<ExportGroup[]>(MOCK_GROUPS);

    useEffect(() => {
        // Try to fetch from backend; fall back to mock data
        (async () => {
            try {
                const base = await ensureApiBase();
                const res = await fetch(`${base}/exports`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.groups) setGroups(data.groups);
                }
            } catch {
                // Use mock data
            }
        })();
    }, []);

    const handleDownload = (item: ExportItem, format: string) => {
        // Placeholder: would trigger actual download via backend
        alert(`Downloading ${item.title} as ${format}...`);
    };

    return (
        <div className="flex-1 overflow-y-auto p-8" style={{ background: "var(--bg-app)" }}>
            <h1
                className="text-xl mb-1"
                style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
            >
                Export Center
            </h1>
            <p className="text-xs mb-6" style={{ color: "var(--text-muted)" }}>
                Download dossiers, evidence tables, graph snapshots, and reproducibility traces.
                File names follow: drugdesigner_{"{type}_{id}_{date}.{ext}"}
            </p>

            {groups.map(group => (
                <div key={group.category} className="mb-6">
                    <div className="flex items-center gap-2 mb-3">
                        <span style={{ color: "var(--text-muted)" }}>{group.icon}</span>
                        <span
                            className="text-[10px] font-bold uppercase tracking-widest"
                            style={{ color: "var(--text-muted)" }}
                        >
                            {group.category}
                        </span>
                    </div>

                    {group.items.map(item => (
                        <div
                            key={item.id}
                            className="flex items-center gap-4 py-3 px-4 mb-1 transition-colors"
                            style={{
                                borderBottom: "1px solid var(--border)",
                            }}
                        >
                            <div className="flex-1">
                                <div className="text-sm font-semibold">{item.title}</div>
                                <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                                    {item.subtitle}{item.created && ` · ${item.created}`}
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                {item.formats.map(fmt => (
                                    <button
                                        key={fmt}
                                        onClick={() => handleDownload(item, fmt)}
                                        className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-semibold rounded transition-colors"
                                        style={{
                                            border: "1px solid var(--border)",
                                            color: "var(--accent)",
                                            background: "var(--bg-elevated)",
                                        }}
                                    >
                                        <Download size={10} />
                                        {fmt}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            ))}
        </div>
    );
}
