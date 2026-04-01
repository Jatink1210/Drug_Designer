/** Knowledge Graph Explorer — macro galaxy view with SVG canvas. */

import { useState, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
    Search, Network, ZoomIn, ZoomOut, Maximize2, Download,
    Layers, Loader2, Play, ArrowRight, X,
} from "lucide-react";
import {
    graphStatsAPI, graphSampleAPI, graphNeighborhoodAPI,
    type GraphStats, type GraphSample,
} from "@/lib/api";

// ── Color palette for entity types ────────────────────────
const LABEL_COLORS: Record<string, string> = {
    Protein:     "#6366f1",
    Drug:        "#f59e0b",
    Disease:     "#ef4444",
    Pathway:     "#10b981",
    Gene:        "#8b5cf6",
    Publication: "#3b82f6",
    Compound:    "#ec4899",
    Target:      "#14b8a6",
    Organism:    "#f97316",
    Phenotype:   "#a855f7",
};

const DEFAULT_COLOR = "#94a3b8";

function colorForLabel(label: string): string {
    return LABEL_COLORS[label] ?? DEFAULT_COLOR;
}

export default function KGPage() {
    const navigate = useNavigate();
    const [graphData, setGraphData] = useState<GraphSample | null>(null);
    const [loadingGraph, setLoadingGraph] = useState(false);
    const [svgZoom, setSvgZoom] = useState(1);
    const [hoveredNode, setHoveredNode] = useState<string | null>(null);
    const [neighborhoodOpen, setNeighborhoodOpen] = useState(false);
    const [neighborhoodId, setNeighborhoodId] = useState("");
    const [neighborhoodResult, setNeighborhoodResult] = useState<Record<string, unknown> | null>(null);
    const [neighborhoodLoading, setNeighborhoodLoading] = useState(false);
    const [neighborhoodError, setNeighborhoodError] = useState<string | null>(null);
    const [kgSearch, setKgSearch] = useState("");
    const [graphError, setGraphError] = useState<string | null>(null);

    // ── Fetch Graph Stats ────────────────────────────────
    const statsQ = useQuery({
        queryKey: ["graphStats"],
        queryFn: graphStatsAPI,
    });

    const stats: GraphStats | undefined = statsQ.data;

    // ── Top entity type labels ───────────────────────────
    const topEntityTypes = useMemo(() => {
        if (!stats?.nodes) return [];
        return Object.entries(stats.nodes)
            .sort(([, a], [, b]) => b - a)
            .slice(0, 6);
    }, [stats]);

    // ── Load graph sample ────────────────────────────────
    const handleLoadGraph = useCallback(async () => {
        setLoadingGraph(true);
        setGraphError(null);
        try {
            const data = await graphSampleAPI(100);
            setGraphData(data);
        } catch (err: unknown) {
            setGraphError(err instanceof Error ? err.message : "Failed to load graph sample");
        } finally {
            setLoadingGraph(false);
        }
    }, []);

    // ── Circular layout for SVG nodes ────────────────────
    const SVG_SIZE = 700;
    const CENTER = SVG_SIZE / 2;

    const layoutNodes = useMemo(() => {
        if (!graphData?.nodes || graphData.nodes.length === 0) return [];
        const count = graphData.nodes.length;
        const radius = Math.min(CENTER - 60, count * 2.5);
        return graphData.nodes.map((node, i) => {
            const angle = (2 * Math.PI * i) / count - Math.PI / 2;
            return {
                ...node,
                x: CENTER + radius * Math.cos(angle),
                y: CENTER + radius * Math.sin(angle),
                color: colorForLabel(node.label),
            };
        });
    }, [graphData, CENTER]);

    // ── Build a lookup map for edge rendering ────────────
    const nodePositionMap = useMemo(() => {
        const m = new Map<string, { x: number; y: number }>();
        for (const n of layoutNodes) {
            m.set(n.id, { x: n.x, y: n.y });
        }
        return m;
    }, [layoutNodes]);

    // ── Zoom controls ────────────────────────────────────
    const zoomIn = () => setSvgZoom(z => Math.min(z + 0.2, 3));
    const zoomOut = () => setSvgZoom(z => Math.max(z - 0.2, 0.3));
    const zoomReset = () => setSvgZoom(1);

    // ── Query Neighborhood ───────────────────────────────
    const handleQueryNeighborhood = useCallback(async () => {
        if (!neighborhoodId.trim()) return;
        setNeighborhoodLoading(true);
        setNeighborhoodError(null);
        try {
            const result = await graphNeighborhoodAPI(neighborhoodId.trim(), 1);
            setNeighborhoodResult(result);
        } catch (err: unknown) {
            setNeighborhoodError(err instanceof Error ? err.message : "Failed to query neighborhood");
        } finally {
            setNeighborhoodLoading(false);
        }
    }, [neighborhoodId]);

    // ── Export current graph sample as JSON ──────────────
    const exportSubgraph = useCallback(() => {
        if (!graphData) return;
        const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "subgraph.json"; a.click();
        URL.revokeObjectURL(url);
    }, [graphData]);

    // ── KG search: press Enter to run neighborhood query ─
    const handleKgSearchKey = async (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter" && kgSearch.trim()) {
            const id = kgSearch.trim();
            setNeighborhoodId(id);
            setNeighborhoodOpen(true);
            setNeighborhoodLoading(true);
            setNeighborhoodError(null);
            try {
                const result = await graphNeighborhoodAPI(id, 1);
                setNeighborhoodResult(result);
            } catch (err: unknown) {
                setNeighborhoodError(err instanceof Error ? err.message : "Failed to query neighborhood");
            } finally {
                setNeighborhoodLoading(false);
            }
        }
    };

    // ── Cluster summary from stats ───────────────────────
    const clusterEntries = useMemo(() => {
        if (!stats?.nodes) return [];
        return Object.entries(stats.nodes)
            .sort(([, a], [, b]) => b - a)
            .slice(0, 8);
    }, [stats]);

    return (
        <div className="flex-1 flex overflow-hidden" style={{ background: "var(--bg-app)" }}>
            {/* ── Main area ────────────────────────────────── */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Stats bar */}
                <div className="glass-panel border-b px-4 py-2.5 flex items-center gap-6">
                    <div className="flex items-center gap-2">
                        <Network size={14} className="text-[var(--accent)]" />
                        <span className="text-xs font-semibold text-[var(--text-primary)]">Knowledge Graph</span>
                    </div>

                    {statsQ.isLoading && (
                        <Loader2 size={12} className="animate-spin text-[var(--text-muted)]" />
                    )}

                    {stats && (
                        <>
                            <Stat label="Nodes" value={(stats.total_nodes || 0).toLocaleString()} />
                            <Stat label="Edges" value={(stats.total_edges || 0).toLocaleString()} />
                            {topEntityTypes.length > 0 && (
                                <div className="flex items-center gap-1.5">
                                    {topEntityTypes.slice(0, 4).map(([label, count]) => (
                                        <span
                                            key={label}
                                            className="px-1.5 py-0.5 text-[9px] rounded font-medium"
                                            style={{
                                                backgroundColor: colorForLabel(label) + "18",
                                                color: colorForLabel(label),
                                            }}
                                        >
                                            {label}: {count.toLocaleString()}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </>
                    )}

                    {!statsQ.isLoading && statsQ.isError && (
                        <span className="text-[10px] text-red-500">Failed to load stats</span>
                    )}

                    <div className="ml-auto flex gap-2">
                        <div className="relative">
                            <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                            <input
                                type="text"
                                value={kgSearch}
                                onChange={e => setKgSearch(e.target.value)}
                                onKeyDown={handleKgSearchKey}
                                placeholder="Search entity ID, press Enter…"
                                className="pl-7 pr-3 py-1 text-xs rounded border bg-[var(--bg-app)]"
                                style={{ borderColor: "var(--border)", width: 200 }}
                            />
                        </div>
                    </div>
                </div>

                {/* Galaxy canvas */}
                <div className="flex-1 bg-slate-50 relative flex items-center justify-center overflow-hidden">
                    {!graphData && !loadingGraph && (
                        <div className="text-center">
                            {graphError && (
                                <div className="mb-4 px-4 py-2 rounded-lg bg-red-50 text-red-700 text-xs inline-flex items-center gap-2">
                                    <span>{graphError}</span>
                                </div>
                            )}
                            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 mx-auto mb-4 flex items-center justify-center">
                                <Network size={40} className="text-indigo-300" />
                            </div>
                            <p className="text-sm text-slate-400 font-medium">Global Knowledge Graph</p>
                            <p className="text-xs text-slate-400 mt-1 max-w-sm">
                                Sampled overview of all entities and relationships. Select a region or query to extract a subgraph for deep analysis.
                            </p>
                            <div className="flex gap-2 mt-4 justify-center">
                                <button
                                    onClick={handleLoadGraph}
                                    className="px-3 py-1.5 text-xs rounded-lg text-white flex items-center gap-1.5"
                                    style={{ background: "var(--accent)" }}
                                >
                                    <Play size={11} /> Load Graph
                                </button>
                            </div>
                        </div>
                    )}

                    {loadingGraph && (
                        <div className="text-center">
                            <Loader2 size={28} className="animate-spin text-[var(--accent)] mx-auto mb-3" />
                            <p className="text-xs text-slate-400">Sampling knowledge graph...</p>
                        </div>
                    )}

                    {graphData && !loadingGraph && (
                        <div className="w-full h-full overflow-auto flex items-center justify-center">
                            <svg
                                width={SVG_SIZE}
                                height={SVG_SIZE}
                                viewBox={`0 0 ${SVG_SIZE} ${SVG_SIZE}`}
                                style={{ transform: `scale(${svgZoom})`, transformOrigin: "center center", transition: "transform 0.2s" }}
                            >
                                {/* Edges */}
                                {graphData.edges.map((edge, i) => {
                                    const src = nodePositionMap.get(edge.source);
                                    const tgt = nodePositionMap.get(edge.target);
                                    if (!src || !tgt) return null;
                                    return (
                                        <line
                                            key={`e-${i}`}
                                            x1={src.x}
                                            y1={src.y}
                                            x2={tgt.x}
                                            y2={tgt.y}
                                            stroke="#cbd5e1"
                                            strokeWidth={0.5}
                                            strokeOpacity={0.6}
                                        />
                                    );
                                })}

                                {/* Nodes */}
                                {layoutNodes.map(node => {
                                    const isHovered = hoveredNode === node.id;
                                    const nodeRadius = isHovered ? 8 : 6;
                                    return (
                                        <g
                                            key={node.id}
                                            onMouseEnter={() => setHoveredNode(node.id)}
                                            onMouseLeave={() => setHoveredNode(null)}
                                            style={{ cursor: "pointer" }}
                                        >
                                            <circle
                                                cx={node.x}
                                                cy={node.y}
                                                r={nodeRadius}
                                                fill={node.color}
                                                fillOpacity={isHovered ? 1 : 0.85}
                                                stroke={isHovered ? node.color : "white"}
                                                strokeWidth={isHovered ? 2.5 : 1}
                                            />
                                            {isHovered && (
                                                <text
                                                    x={node.x}
                                                    y={node.y - 12}
                                                    textAnchor="middle"
                                                    fontSize={10}
                                                    fontWeight={600}
                                                    fill="#334155"
                                                >
                                                    {node.id}
                                                </text>
                                            )}
                                            {/* Always show labels if few enough nodes */}
                                            {layoutNodes.length <= 40 && !isHovered && (
                                                <text
                                                    x={node.x}
                                                    y={node.y + 16}
                                                    textAnchor="middle"
                                                    fontSize={7}
                                                    fill="#94a3b8"
                                                >
                                                    {node.id.length > 12 ? node.id.slice(0, 12) + "..." : node.id}
                                                </text>
                                            )}
                                        </g>
                                    );
                                })}

                                {/* Legend */}
                                {(() => {
                                    const uniqueLabels = [...new Set(layoutNodes.map(n => n.label))].slice(0, 8);
                                    return uniqueLabels.map((label, i) => (
                                        <g key={label} transform={`translate(16, ${16 + i * 18})`}>
                                            <circle cx={6} cy={6} r={5} fill={colorForLabel(label)} fillOpacity={0.85} />
                                            <text x={16} y={10} fontSize={9} fill="#64748b">{label}</text>
                                        </g>
                                    ));
                                })()}
                            </svg>
                        </div>
                    )}

                    {/* Controls overlay */}
                    <div className="absolute bottom-4 right-4 flex gap-1">
                        <button onClick={zoomIn} className="p-2 rounded-lg glass-card shadow-sm hover:bg-gray-50">
                            <ZoomIn size={14} />
                        </button>
                        <button onClick={zoomOut} className="p-2 rounded-lg glass-card shadow-sm hover:bg-gray-50">
                            <ZoomOut size={14} />
                        </button>
                        <button onClick={zoomReset} className="p-2 rounded-lg glass-card shadow-sm hover:bg-gray-50">
                            <Maximize2 size={14} />
                        </button>
                    </div>

                    {/* Node count badge */}
                    {graphData && (
                        <div className="absolute top-3 left-3 px-2 py-1 rounded glass-card shadow-sm text-[10px] text-[var(--text-muted)]">
                            {graphData.nodes.length} nodes, {graphData.edges.length} edges loaded
                        </div>
                    )}
                </div>

                {/* Cluster summaries */}
                <div className="h-[120px] glass-panel border-t px-4 py-3 overflow-x-auto">
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Cluster Summaries</div>
                    <div className="flex gap-3">
                        {statsQ.isLoading && (
                            <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                                <Loader2 size={12} className="animate-spin" /> Loading cluster data...
                            </div>
                        )}
                        {clusterEntries.length === 0 && !statsQ.isLoading && (
                            <div className="text-xs text-[var(--text-muted)]">No cluster data available</div>
                        )}
                        {clusterEntries.map(([label, count]) => (
                            <div
                                key={label}
                                className="shrink-0 w-[140px] rounded-lg border p-2"
                                style={{ borderColor: "var(--border)" }}
                            >
                                <div className="flex items-center gap-1.5">
                                    <span
                                        className="w-2 h-2 rounded-full shrink-0"
                                        style={{ backgroundColor: colorForLabel(label) }}
                                    />
                                    <div className="text-xs font-medium text-[var(--text-primary)] truncate">{label}</div>
                                </div>
                                <div className="text-[10px] text-[var(--text-muted)] mt-0.5">
                                    {count.toLocaleString()} entities
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* ── Right — Lens Tools ──────────────────────── */}
            <div className="w-[220px] glass-panel border-l flex flex-col overflow-hidden">
                <div className="p-3 border-b" style={{ borderColor: "var(--border)" }}>
                    <h3 className="text-xs font-semibold text-[var(--text-primary)]">Lens Tools</h3>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-1">
                    <button
                        onClick={handleLoadGraph}
                        disabled={loadingGraph}
                        className="w-full text-left px-2 py-2 rounded hover:bg-gray-50 text-xs flex items-center gap-1.5"
                    >
                        {loadingGraph
                            ? <Loader2 size={12} className="animate-spin" />
                            : <Play size={12} className="opacity-70" />
                        }
                        {loadingGraph ? "Loading..." : "Load Graph Sample"}
                    </button>
                    <button
                        onClick={() => navigate("/analysis")}
                        className="w-full text-left px-2 py-2 rounded hover:bg-gray-50 text-xs flex items-center gap-1.5"
                    >
                        <Layers size={12} className="opacity-70" />Extract Subgraph
                    </button>
                    <button
                        onClick={() => setNeighborhoodOpen(!neighborhoodOpen)}
                        className="w-full text-left px-2 py-2 rounded hover:bg-gray-50 text-xs flex items-center gap-1.5"
                    >
                        <Search size={12} className="opacity-70" />Query Neighborhood
                    </button>

                    {/* Neighborhood input */}
                    {neighborhoodOpen && (
                        <div className="ml-4 space-y-2 pt-1">
                            <div className="relative">
                                <input
                                    type="text"
                                    value={neighborhoodId}
                                    onChange={e => setNeighborhoodId(e.target.value)}
                                    onKeyDown={e => e.key === "Enter" && handleQueryNeighborhood()}
                                    placeholder="Entity ID..."
                                    className="w-full px-2 py-1.5 text-xs rounded border bg-[var(--bg-app)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                                    style={{ borderColor: "var(--border)" }}
                                />
                            </div>
                            <button
                                onClick={handleQueryNeighborhood}
                                disabled={neighborhoodLoading || !neighborhoodId.trim()}
                                className="w-full px-2 py-1.5 text-xs rounded text-white flex items-center justify-center gap-1"
                                style={{ background: "var(--accent)", opacity: (!neighborhoodId.trim() || neighborhoodLoading) ? 0.5 : 1 }}
                            >
                                {neighborhoodLoading
                                    ? <Loader2 size={10} className="animate-spin" />
                                    : <ArrowRight size={10} />
                                }
                                {neighborhoodLoading ? "Querying..." : "Query"}
                            </button>
                            {neighborhoodError && (
                                <p className="text-[10px] text-red-500">{neighborhoodError}</p>
                            )}
                            {neighborhoodResult && (
                                <div className="rounded border p-2 text-[10px]" style={{ borderColor: "var(--border)" }}>
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="font-semibold text-[var(--text-primary)]">Result</span>
                                        <button onClick={() => setNeighborhoodResult(null)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                                            <X size={10} />
                                        </button>
                                    </div>
                                    <pre className="text-[9px] text-[var(--text-muted)] overflow-auto max-h-[100px] whitespace-pre-wrap">
                                        {JSON.stringify(neighborhoodResult, null, 2)}
                                    </pre>
                                </div>
                            )}
                        </div>
                    )}

                    <button
                        onClick={() => navigate("/analysis")}
                        className="w-full text-left px-2 py-2 rounded hover:bg-gray-50 text-xs flex items-center gap-1.5"
                    >
                        <Network size={12} className="opacity-70" />Open in Graph Lab
                    </button>
                    <button
                        onClick={exportSubgraph}
                        disabled={!graphData}
                        className="w-full text-left px-2 py-2 rounded hover:bg-gray-50 text-xs flex items-center gap-1.5 disabled:opacity-40"
                    >
                        <Download size={12} className="opacity-70" />Export Subgraph
                    </button>
                </div>
                <div className="p-3 border-t" style={{ borderColor: "var(--border)" }}>
                    <div className="text-[10px] text-[var(--text-muted)] space-y-1">
                        <p>Large graphs are sampled (max 5000 nodes displayed)</p>
                        <p>Use Lens tools to extract regions for deep analysis</p>
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ── Helper components ─────────────────────────────────── */

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div className="text-center">
            <div className="text-xs font-semibold text-[var(--text-primary)]">{value}</div>
            <div className="text-[9px] text-[var(--text-muted)]">{label}</div>
        </div>
    );
}
