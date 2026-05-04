/** Graph Lab — Cytoscape-grade graph analysis workbench. */

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import cytoscape from "cytoscape";
import {
  Filter,
  BarChart3,
  Network,
  Table2,
  Download,
  Layout,
  MousePointer2,
  Settings2,
  Maximize2,
  Loader2,
} from "lucide-react";
import { graphSampleAPI, graphStatsAPI, graphNeighborhoodAPI, type GraphSample, type GraphStats } from "@/lib/api";
import StateWrapper from "@/components/ui/StateWrapper";
import ProvenanceBadge from "@/components/ui/ProvenanceBadge";
import type { ViewState } from "@/lib/types";
/* ── Constants ──────────────────────────────────────────── */

const LAYOUTS = [
  "cose",
  "concentric",
  "grid",
  "circle",
  "breadthfirst",
] as const;
type LayoutName = (typeof LAYOUTS)[number];

const NODE_COLOR_MAP: Record<string, string> = {
  protein: "#3b82f6", // blue
  gene: "#22c55e", // green
  disease: "#ef4444", // red
  drug: "#a855f7", // purple
  molecule: "#f59e0b", // amber
  pathway: "#06b6d4", // cyan
  structure: "#ec4899", // pink
};
const DEFAULT_NODE_COLOR = "#6b7280";

const NODE_TYPES = [
  "protein",
  "gene",
  "disease",
  "drug",
  "molecule",
  "pathway",
  "structure",
];

 
const CY_STYLE: any[] = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "font-size": 10,
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 4,
      width: 28,
      height: 28,
      "background-color": DEFAULT_NODE_COLOR,
      "border-width": 2,
      "border-color": "#ffffff",
      color: "#374151",
    },
  },
  // Per-type colour classes
  ...Object.entries(NODE_COLOR_MAP).map(([type, color]) => ({
    selector: `node.${type}`,
    style: { "background-color": color },
  })),
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": "#9ca3af",
      "curve-style": "bezier",
      "target-arrow-shape": "triangle",
      "target-arrow-color": "#9ca3af",
      "arrow-scale": 0.6,
      label: "data(label)",
      "font-size": 8,
      "text-rotation": "autorotate",
      color: "#9ca3af",
      "text-opacity": 0.7,
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 3,
      "border-color": "#6366f1",
      "background-opacity": 1,
    },
  },
  {
    selector: "node.hidden-filter",
    style: {
      display: "none",
    },
  },
];

const COSE_DEFAULTS = {
  name: "cose",
  animate: true,
  animationDuration: 500,
  nodeRepulsion: () => 8000,
  idealEdgeLength: () => 80,
  edgeElasticity: () => 100,
  gravity: 0.25,
  numIter: 1000,
  padding: 40,
};

/* ── Helpers ────────────────────────────────────────────── */

function toElements(data: GraphSample): cytoscape.ElementDefinition[] {
  const nodes: cytoscape.ElementDefinition[] = data.nodes.map((n) => {
    const nodeType = (
      (n.properties?.type as string) ||
      n.label ||
      ""
    ).toLowerCase();
    return {
      data: { id: n.id, label: n.label, ...n.properties },
      classes: nodeType,
    };
  });
  const edges: cytoscape.ElementDefinition[] = data.edges.map((e, i) => ({
    data: {
      id: `e-${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      label: e.type,
      ...e.properties,
    },
  }));
  return [...nodes, ...edges];
}

function layoutOptions(name: LayoutName): cytoscape.LayoutOptions {
  if (name === "cose") return COSE_DEFAULTS as cytoscape.LayoutOptions;
  return {
    name,
    animate: true,
    animationDuration: 400,
    padding: 40,
  } as cytoscape.LayoutOptions;
}

/* ── Main Component ─────────────────────────────────────── */

export default function AnalysisPage() {
  const [sidePanel, setSidePanel] = useState<
    "filters" | "algorithms" | "style" | null
  >("filters");
  const [selectedLayout, setSelectedLayout] = useState<LayoutName>("cose");
  const [showTable, setShowTable] = useState(false);
  const [tableTab, setTableTab] = useState<"nodes" | "edges">("nodes");
  const [nodeCount, setNodeCount] = useState(0);
  const [edgeCount, setEdgeCount] = useState(0);
  const [graphLoaded, setGraphLoaded] = useState(false);
  const [loadRequested, setLoadRequested] = useState(true);
  const [sampleLimit, setSampleLimit] = useState(500);
  const [searchEntity, setSearchEntity] = useState("");
  const [neighborDepth, setNeighborDepth] = useState(2);

  /* Cytoscape refs */
  const cyRef = useRef<HTMLDivElement>(null);
  const cyInstance = useRef<cytoscape.Core | null>(null);

  /* Table data mirrors */
  const [tableNodes, setTableNodes] = useState<
    Array<{ id: string; label: string; type: string }>
  >([]);
  const [tableEdges, setTableEdges] = useState<
    Array<{ source: string; target: string; type: string; sourceName?: string; sourceFamily?: string; confidence?: number; contradictionState?: "none" | "flagged" | "confirmed"; retrievedAt?: string }>
  >([]);

  /* Graph stats to show total available */
  const statsQ = useQuery({
    queryKey: ["graph-stats"],
    queryFn: graphStatsAPI,
  });

  /* API query — auto-loads on mount with high limit */
  const {
    data: graphData,
    isFetching: isLoading,
    refetch,
  } = useQuery({
    queryKey: ["graph-sample", sampleLimit],
    queryFn: () => graphSampleAPI(sampleLimit),
    enabled: loadRequested,
  });

  /* Update counts helper */
  const syncCounts = useCallback(() => {
    const cy = cyInstance.current;
    if (!cy) return;
    setNodeCount(cy.nodes().length);
    setEdgeCount(cy.edges().length);
  }, []);

  /* Neighborhood search */
  const handleNeighborhood = useCallback(async () => {
    if (!searchEntity.trim()) return;
    try {
      const result = await graphNeighborhoodAPI(searchEntity.trim(), neighborDepth) as any;
      const cy = cyInstance.current;
      if (!cy || !result) return;
      // Merge neighborhood nodes/edges into graph
      const newNodes = (result.nodes || []).map((n: any) => {
        const nodeType = ((n.properties?.type as string) || n.label || "").toLowerCase();
        return { data: { id: n.id, label: n.label, ...n.properties }, classes: nodeType };
      });
      const newEdges = (result.edges || []).map((e: any, i: number) => ({
        data: { id: `ne-${e.source}-${e.target}-${i}`, source: e.source, target: e.target, label: e.type, ...e.properties },
      }));
      // Add only new elements
      const existingIds = new Set(cy.nodes().map((n) => n.id()));
      const toAdd = [...newNodes.filter((n: any) => !existingIds.has(n.data.id)), ...newEdges];
      if (toAdd.length > 0) {
        cy.add(toAdd);
        cy.layout(layoutOptions(selectedLayout)).run();
        syncCounts();
      }
    } catch (err) {
      console.error("Neighborhood fetch failed:", err);
    }
  }, [searchEntity, neighborDepth, selectedLayout, syncCounts]);

  /* Initialize cytoscape on mount */
  useEffect(() => {
    if (!cyRef.current) return;

    const cy = cytoscape({
      container: cyRef.current,
      style: CY_STYLE,
      layout: { name: "preset" },
      minZoom: 0.1,
      maxZoom: 5,
      wheelSensitivity: 0.3,
    });

    cyInstance.current = cy;

    return () => {
      cy.destroy();
      cyInstance.current = null;
    };
  }, []);

  /* Load data into cytoscape when graphData arrives */
  useEffect(() => {
    const cy = cyInstance.current;
    if (!cy || !graphData) return;

    cy.elements().remove();
    const elements = toElements(graphData);
    cy.add(elements);
    cy.layout(layoutOptions(selectedLayout)).run();
    setGraphLoaded(true);
    syncCounts();

    /* Build table mirrors */
    setTableNodes(
      graphData.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        type: (
          (n.properties?.type as string) ||
          n.label ||
          "unknown"
        ).toLowerCase(),
      })),
    );
    setTableEdges(
      graphData.edges.map((e) => ({
        source: e.source,
        target: e.target,
        type: e.type,
        sourceName: (e.properties?.source_name as string) || undefined,
        sourceFamily: (e.properties?.source_family as string) || undefined,
        confidence: typeof e.properties?.confidence === "number" ? e.properties.confidence : undefined,
        contradictionState: (e.properties?.contradiction_state as "none" | "flagged" | "confirmed") || undefined,
        retrievedAt: (e.properties?.retrieved_at as string) || undefined,
      })),
    );
  }, [graphData, selectedLayout, syncCounts]);

  /* Actions */
  const handleLoadFromSearch = () => {
    if (loadRequested) {
      refetch();
    } else {
      setLoadRequested(true);
    }
  };

  const handleRunLayout = () => {
    const cy = cyInstance.current;
    if (!cy || cy.elements().length === 0) return;
    cy.layout(layoutOptions(selectedLayout)).run();
  };

  const handleFit = () => {
    const cy = cyInstance.current;
    if (!cy) return;
    cy.fit(undefined, 40);
  };

  const handleExportPng = () => {
    const cy = cyInstance.current;
    if (!cy || cy.elements().length === 0) return;
    const pngData = cy.png({ full: true, scale: 2, bg: "#ffffff" });
    const a = document.createElement("a");
    a.href = pngData;
    a.download = "graph_export.png";
    a.click();
  };

  /* §A3.1: Compute view state from query status */
  const analysisViewState: ViewState = isLoading ? "loading" : graphLoaded ? "success" : "initial";

  return (
    <StateWrapper state={analysisViewState} moduleName="Graph Analysis">
    <div
      className="flex-1 flex overflow-hidden"
      style={{ background: "var(--bg-app)" }}
    >
      {/* Left toolbar */}
      <div className="w-10 glass-sidebar border-r flex flex-col items-center py-2 gap-1">
        <ToolButton icon={<MousePointer2 size={14} />} label="Select" active />
        <ToolButton
          icon={<Maximize2 size={14} />}
          label="Lasso — requires extension"
          disabled
        />
        <div className="w-6 h-px bg-[var(--border)] my-1" />
        <ToolButton
          icon={<Filter size={14} />}
          label="Filters"
          onClick={() =>
            setSidePanel(sidePanel === "filters" ? null : "filters")
          }
          active={sidePanel === "filters"}
        />
        <ToolButton
          icon={<BarChart3 size={14} />}
          label="Algorithms"
          onClick={() =>
            setSidePanel(sidePanel === "algorithms" ? null : "algorithms")
          }
          active={sidePanel === "algorithms"}
        />
        <ToolButton
          icon={<Settings2 size={14} />}
          label="Style"
          onClick={() => setSidePanel(sidePanel === "style" ? null : "style")}
          active={sidePanel === "style"}
        />
        <div className="w-6 h-px bg-[var(--border)] my-1" />
        <ToolButton
          icon={<Table2 size={14} />}
          label="Table"
          onClick={() => setShowTable(!showTable)}
          active={showTable}
        />
        <ToolButton
          icon={<Download size={14} />}
          label="Export PNG"
          onClick={handleExportPng}
        />
      </div>

      {/* Side panel */}
      {sidePanel && (
        <div className="w-[240px] glass-sidebar border-r overflow-y-auto">
          {sidePanel === "filters" && <FiltersPanel cyInstance={cyInstance} />}
          {sidePanel === "algorithms" && (
            <AlgorithmsPanel cyInstance={cyInstance} />
          )}
          {sidePanel === "style" && <StylePanel cyInstance={cyInstance} />}
        </div>
      )}

      {/* Main canvas */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Canvas toolbar */}
        <div className="glass-panel border-b px-3 py-2 flex items-center gap-2">
          <Layout size={13} className="text-[var(--text-muted)]" />
          <select
            value={selectedLayout}
            onChange={(e) => setSelectedLayout(e.target.value as LayoutName)}
            className="text-xs border rounded px-2 py-1 bg-[var(--bg-app)]"
            style={{ borderColor: "var(--border)" }}
          >
            {LAYOUTS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
          <button
            onClick={handleRunLayout}
            className="text-xs px-2 py-1 rounded border hover:bg-[var(--bg-surface)] transition-colors"
            style={{ borderColor: "var(--border)" }}
          >
            Run Layout
          </button>
          <button
            onClick={handleFit}
            className="text-xs px-2 py-1 rounded border hover:bg-[var(--bg-surface)] transition-colors"
            style={{ borderColor: "var(--border)" }}
          >
            Fit
          </button>
          <div className="mx-2 h-4 w-px bg-[var(--border)]" />
          {/* Entity search */}
          <div className="flex items-center gap-1">
            <input
              type="text"
              value={searchEntity}
              onChange={(e) => setSearchEntity(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleNeighborhood()}
              placeholder="Explore entity (e.g., BRCA1)..."
              className="text-xs border rounded px-2 py-1 w-40 bg-[var(--bg-app)]"
              style={{ borderColor: "var(--border)" }}
            />
            <select
              value={neighborDepth}
              onChange={(e) => setNeighborDepth(Number(e.target.value))}
              className="text-xs border rounded px-1 py-1 bg-[var(--bg-app)] w-14"
              style={{ borderColor: "var(--border)" }}
            >
              <option value={1}>d=1</option>
              <option value={2}>d=2</option>
              <option value={3}>d=3</option>
            </select>
            <button
              onClick={handleNeighborhood}
              className="text-xs px-2 py-1 rounded border hover:bg-[var(--bg-surface)] transition-colors"
              style={{ borderColor: "var(--border)" }}
            >
              Expand
            </button>
          </div>
          <span className="ml-auto text-[10px] text-[var(--text-muted)]">
            {nodeCount} nodes &bull; {edgeCount} edges
            {statsQ.data ? ` / ${statsQ.data.total_nodes} total` : ""}
          </span>
        </div>

        {/* Graph canvas */}
        <div
          className="flex-1 relative"
          style={{ background: "var(--bg-app)" }}
        >
          {/* Cytoscape container — always mounted */}
          <div ref={cyRef} className="absolute inset-0" />

          {/* Overlay when empty */}
          {!graphLoaded && !isLoading && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="text-center pointer-events-auto">
                <Network size={48} className="text-slate-400 mx-auto mb-3" />
                <p className="text-sm text-[var(--text-muted)] font-medium">
                  Cytoscape.js Canvas
                </p>
                <p className="text-xs text-[var(--text-muted)] mt-1">
                  Import data or run a search to populate the graph
                </p>
                <div className="flex gap-2 mt-4 justify-center">
                  <button
                    onClick={handleLoadFromSearch}
                    className="px-3 py-1.5 text-xs rounded-lg border hover:bg-white transition-colors"
                    style={{ borderColor: "var(--border)" }}
                  >
                    Load Full Graph
                  </button>
                  <select
                    value={sampleLimit}
                    onChange={(e) => setSampleLimit(Number(e.target.value))}
                    className="text-xs border rounded px-2 py-1 bg-white"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <option value={100}>100 nodes</option>
                    <option value={250}>250 nodes</option>
                    <option value={500}>500 nodes</option>
                    <option value={1000}>All nodes</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* Loading spinner */}
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/60">
              <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
                <Loader2 size={18} className="animate-spin" />
                Loading graph data...
              </div>
            </div>
          )}

          {/* Floating reload button when graph is loaded */}
          {graphLoaded && !isLoading && (
            <div className="absolute top-3 right-3 flex gap-1.5">
              <select
                value={sampleLimit}
                onChange={(e) => { setSampleLimit(Number(e.target.value)); }}
                className="text-[11px] rounded-md border bg-white/80 px-1.5 py-1 shadow-sm"
                style={{ borderColor: "var(--border)" }}
              >
                <option value={100}>100</option>
                <option value={250}>250</option>
                <option value={500}>500</option>
                <option value={1000}>All</option>
              </select>
              <button
                onClick={handleLoadFromSearch}
                className="px-2.5 py-1 text-[11px] rounded-md border bg-white/80 hover:bg-white transition-colors shadow-sm"
                style={{ borderColor: "var(--border)" }}
              >
                Reload
              </button>
            </div>
          )}
        </div>

        {/* Bottom table */}
        {showTable && (
          <div className="h-[200px] glass-panel border-t overflow-auto">
            <div
              className="px-3 py-2 border-b flex items-center gap-3"
              style={{ borderColor: "var(--border)" }}
            >
              <button
                onClick={() => setTableTab("nodes")}
                className={`text-[11px] font-medium pb-1 ${tableTab === "nodes" ? "text-[var(--accent)] border-b-2 border-[var(--accent)]" : "text-[var(--text-muted)]"}`}
              >
                Nodes ({tableNodes.length})
              </button>
              <button
                onClick={() => setTableTab("edges")}
                className={`text-[11px] font-medium pb-1 ${tableTab === "edges" ? "text-[var(--accent)] border-b-2 border-[var(--accent)]" : "text-[var(--text-muted)]"}`}
              >
                Edges ({tableEdges.length})
              </button>
            </div>

            {tableNodes.length === 0 && tableEdges.length === 0 ? (
              <div className="px-3 py-4 text-xs text-[var(--text-muted)] text-center">
                No data loaded
              </div>
            ) : tableTab === "nodes" ? (
              <table className="w-full text-xs">
                <thead className="bg-[var(--bg-app)] sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-1.5 font-semibold text-[var(--text-muted)] uppercase text-[10px]">
                      ID
                    </th>
                    <th className="text-left px-3 py-1.5 font-semibold text-[var(--text-muted)] uppercase text-[10px]">
                      Label
                    </th>
                    <th className="text-left px-3 py-1.5 font-semibold text-[var(--text-muted)] uppercase text-[10px]">
                      Type
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-light)]">
                  {tableNodes.map((n) => (
                    <tr
                      key={n.id}
                      className="hover:bg-[var(--accent-subtle)]/30"
                    >
                      <td className="px-3 py-1.5 text-[var(--text-primary)] font-mono">
                        {n.id}
                      </td>
                      <td className="px-3 py-1.5 text-[var(--text-primary)]">
                        {n.label}
                      </td>
                      <td className="px-3 py-1.5">
                        <span
                          className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium text-white"
                          style={{
                            backgroundColor:
                              NODE_COLOR_MAP[n.type] || DEFAULT_NODE_COLOR,
                          }}
                        >
                          {n.type}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table className="w-full text-xs">
                <thead className="bg-[var(--bg-app)] sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-1.5 font-semibold text-[var(--text-muted)] uppercase text-[10px]">
                      Source
                    </th>
                    <th className="text-left px-3 py-1.5 font-semibold text-[var(--text-muted)] uppercase text-[10px]">
                      Target
                    </th>
                    <th className="text-left px-3 py-1.5 font-semibold text-[var(--text-muted)] uppercase text-[10px]">
                      Type
                    </th>
                    <th className="text-left px-3 py-1.5 font-semibold text-[var(--text-muted)] uppercase text-[10px]">
                      Provenance
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-light)]">
                  {tableEdges.map((e, i) => (
                    <tr
                      key={`${e.source}-${e.target}-${i}`}
                      className="hover:bg-[var(--accent-subtle)]/30"
                    >
                      <td className="px-3 py-1.5 text-[var(--text-primary)] font-mono">
                        {e.source}
                      </td>
                      <td className="px-3 py-1.5 text-[var(--text-primary)] font-mono">
                        {e.target}
                      </td>
                      <td className="px-3 py-1.5 text-[var(--text-secondary)]">
                        {e.type}
                      </td>
                      <td className="px-3 py-1.5">
                        {e.sourceName ? (
                          <ProvenanceBadge
                            sourceName={e.sourceName}
                            sourceFamily={e.sourceFamily}
                            confidence={e.confidence}
                            contradictionState={e.contradictionState}
                            retrievedAt={e.retrievedAt}
                            compact
                          />
                        ) : (
                          <span className="text-[var(--text-muted)]">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>    </StateWrapper>  );
}

/* ── Sub-components ─────────────────────────────────────── */

function ToolButton({
  icon,
  label,
  active,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={disabled ? undefined : onClick}
      title={label}
      className={`w-8 h-8 rounded flex items-center justify-center transition-colors ${disabled ? "text-[var(--text-muted)] opacity-40 cursor-not-allowed" : active ? "bg-indigo-50 text-[var(--accent)]" : "text-[var(--text-muted)] hover:bg-[var(--bg-surface)]"}`}
    >
      {icon}
    </button>
  );
}

function FiltersPanel({
  cyInstance,
}: {
  cyInstance: React.RefObject<cytoscape.Core | null>;
}) {
  const [visibleTypes, setVisibleTypes] = useState<Record<string, boolean>>(
    () => Object.fromEntries(NODE_TYPES.map((t) => [t, true])),
  );
  const toggleType = (type: string) => {
    const newVisible = { ...visibleTypes, [type]: !visibleTypes[type] };
    setVisibleTypes(newVisible);
    const cy = cyInstance.current;
    if (!cy) return;
    // Show/hide nodes by toggling the hidden-filter class
    cy.nodes().forEach((node) => {
      const nodeType =
        (node.classes() as unknown as string[]).find((c: string) =>
          NODE_TYPES.includes(c),
        ) || "";
      if (nodeType === type) {
        if (newVisible[type]) {
          node.removeClass("hidden-filter");
        } else {
          node.addClass("hidden-filter");
        }
      }
    });
  };

  return (
    <div className="p-3 space-y-4">
      <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">
        Node Types
      </div>
      {NODE_TYPES.map((t) => (
        <label
          key={t}
          className="flex items-center gap-2 text-xs cursor-pointer"
        >
          <input
            type="checkbox"
            checked={visibleTypes[t]}
            onChange={() => toggleType(t)}
            className="rounded"
          />
          <span
            className="inline-block w-2.5 h-2.5 rounded-full mr-1"
            style={{ backgroundColor: NODE_COLOR_MAP[t] || DEFAULT_NODE_COLOR }}
          />
          {t}
        </label>
      ))}
    </div>
  );
}

function AlgorithmsPanel({
  cyInstance,
}: {
  cyInstance: React.RefObject<cytoscape.Core | null>;
}) {
  const [lastRun, setLastRun] = useState<string | null>(null);

  const runDegree = () => {
    const cy = cyInstance.current;
    if (!cy || cy.nodes().length === 0) return;
    // Compute degree centrality per node
    const nodes = cy.nodes();
    const maxDeg = Math.max(1, ...nodes.map((n) => n.degree(false)));
    nodes.forEach((node) => {
      const val = node.degree(false) / maxDeg;
      node.data("centrality", val);
      node.style("width", 16 + val * 40);
      node.style("height", 16 + val * 40);
    });
    setLastRun("Degree Centrality");
  };

  const runBetweenness = () => {
    const cy = cyInstance.current;
    if (!cy || cy.nodes().length === 0) return;
    const bc = cy
      .elements()
      .betweennessCentrality({ directed: false, weight: () => 1 });
    cy.nodes().forEach((node) => {
      const val = bc.betweennessNormalized(node);
      node.data("centrality", val);
      node.style("width", 16 + val * 40);
      node.style("height", 16 + val * 40);
    });
    setLastRun("Betweenness");
  };

  const runCloseness = () => {
    const cy = cyInstance.current;
    if (!cy || cy.nodes().length === 0) return;
    const ccn = cy
      .elements()
      .closenessCentralityNormalized({ directed: false, weight: () => 1 });
    cy.nodes().forEach((node) => {
      const val = ccn.closeness(node);
      node.data("centrality", val);
      node.style("width", 16 + val * 40);
      node.style("height", 16 + val * 40);
    });
    setLastRun("Closeness");
  };

  const resetSizes = () => {
    const cy = cyInstance.current;
    if (!cy) return;
    cy.nodes().forEach((node) => {
      node.style("width", 28);
      node.style("height", 28);
      node.removeData("centrality");
    });
    setLastRun(null);
  };

  const algorithms = [
    {
      name: "Degree Centrality",
      desc: "Identify hub nodes",
      action: runDegree,
    },
    { name: "Betweenness", desc: "Find bridge nodes", action: runBetweenness },
    { name: "Closeness", desc: "Find central nodes", action: runCloseness },
  ];

  return (
    <div className="p-3 space-y-1">
      <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">
        Graph Algorithms
      </div>
      {algorithms.map((a) => (
        <button
          key={a.name}
          onClick={a.action}
          className="w-full text-left px-2 py-2 rounded transition-colors hover:bg-[var(--bg-surface)]"
        >
          <div className="text-xs font-medium text-[var(--text-primary)]">
            {a.name}
          </div>
          <div className="text-[10px] text-[var(--text-muted)]">{a.desc}</div>
        </button>
      ))}

      {lastRun && (
        <div className="mt-2 space-y-1">
          <div className="text-[10px] text-green-600 font-medium">
            Last run: {lastRun}
          </div>
          <button
            onClick={resetSizes}
            className="text-[10px] text-[var(--accent)] hover:underline"
          >
            Reset node sizes
          </button>
        </div>
      )}
    </div>
  );
}

function StylePanel({
  cyInstance,
}: {
  cyInstance: React.RefObject<cytoscape.Core | null>;
}) {
  const [nodeColorBy, setNodeColorBy] = useState("Entity Type");
  const [nodeSizeBy, setNodeSizeBy] = useState("Uniform");
  const [edgeWidthBy, setEdgeWidthBy] = useState("Uniform");

  const applyNodeSize = (mode: string) => {
    setNodeSizeBy(mode);
    const cy = cyInstance.current;
    if (!cy) return;
    if (mode === "Uniform") {
      cy.nodes().forEach((n) => {
        n.style("width", 28);
        n.style("height", 28);
      });
    } else if (mode === "Degree") {
      const nodes = cy.nodes();
      const maxDeg = Math.max(1, ...nodes.map((n) => n.degree(false)));
      nodes.forEach((n) => {
        const val = n.degree(false) / maxDeg;
        const size = 16 + val * 40;
        n.style("width", size);
        n.style("height", size);
      });
    }
  };

  const applyNodeColor = (mode: string) => {
    setNodeColorBy(mode);
    const cy = cyInstance.current;
    if (!cy) return;
    if (mode === "Entity Type") {
      // Reset to class-based coloring
      cy.nodes().forEach((n) => {
        n.style("background-color", "");
      });
    } else if (mode === "Centrality") {
      // Color by centrality data if present
      cy.nodes().forEach((n) => {
        const val = n.data("centrality") as number | undefined;
        if (val != null) {
          const r = Math.round(255 * val);
          const b = Math.round(255 * (1 - val));
          n.style("background-color", `rgb(${r},80,${b})`);
        }
      });
    }
  };

  const applyEdgeWidth = (mode: string) => {
    setEdgeWidthBy(mode);
    const cy = cyInstance.current;
    if (!cy) return;
    if (mode === "Uniform") {
      cy.edges().forEach((e) => {
        e.style("width", 1.5);
      });
    } else if (mode === "Weight") {
      cy.edges().forEach((e) => {
        const w = Number(e.data("weight") || 1);
        e.style("width", Math.max(0.5, Math.min(w * 2, 6)));
      });
    }
  };

  return (
    <div className="p-3 space-y-3">
      <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">
        Node Color by
      </div>
      <select
        value={nodeColorBy}
        onChange={(e) => applyNodeColor(e.target.value)}
        className="w-full text-xs border rounded px-2 py-1"
        style={{ borderColor: "var(--border)" }}
      >
        <option>Entity Type</option>
        <option>Centrality</option>
      </select>
      <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">
        Node Size by
      </div>
      <select
        value={nodeSizeBy}
        onChange={(e) => applyNodeSize(e.target.value)}
        className="w-full text-xs border rounded px-2 py-1"
        style={{ borderColor: "var(--border)" }}
      >
        <option>Uniform</option>
        <option>Degree</option>
      </select>
      <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">
        Edge Width by
      </div>
      <select
        value={edgeWidthBy}
        onChange={(e) => applyEdgeWidth(e.target.value)}
        className="w-full text-xs border rounded px-2 py-1"
        style={{ borderColor: "var(--border)" }}
      >
        <option>Uniform</option>
        <option>Weight</option>
      </select>
      <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mt-2">
        Legend
      </div>
      <div className="space-y-1">
        {Object.entries(NODE_COLOR_MAP).map(([type, color]) => (
          <div
            key={type}
            className="flex items-center gap-2 text-xs text-[var(--text-secondary)]"
          >
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ backgroundColor: color }}
            />
            {type}
          </div>
        ))}
      </div>
    </div>
  );
}
