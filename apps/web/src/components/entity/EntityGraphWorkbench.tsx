import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import {
  Download,
  LayoutGrid,
  Filter,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  Box,
  FlaskConical,
  BarChart3,
} from "lucide-react";
import type { GraphNode, EntityIntelligenceGraphEdge } from "@/lib/api";
import { ENTITY_COLORS } from "@/lib/entityColors";

const LAYOUTS = ["cose", "concentric", "grid", "circle", "breadthfirst"] as const;
type LayoutName = (typeof LAYOUTS)[number];

const TYPE_META: Record<string, { color: string; shape: string }> = {
  gene: { color: ENTITY_COLORS.gene, shape: "round-rectangle" },
  disease: { color: ENTITY_COLORS.disease, shape: "ellipse" },
  drug: { color: ENTITY_COLORS.drug, shape: "ellipse" },
  molecule: { color: ENTITY_COLORS.molecule, shape: "hexagon" },
  compound: { color: ENTITY_COLORS.compound, shape: "hexagon" },
  pathway: { color: ENTITY_COLORS.pathway, shape: "diamond" },
  protein: { color: ENTITY_COLORS.protein, shape: "round-rectangle" },
  publication: { color: ENTITY_COLORS.publication, shape: "rectangle" },
  clinical_trial: { color: ENTITY_COLORS.clinical_trial, shape: "tag" },
  target: { color: ENTITY_COLORS.target || "#8b5cf6", shape: "round-rectangle" },
  variant: { color: ENTITY_COLORS.variant, shape: "triangle" },
  source: { color: "#94a3b8", shape: "diamond" },
  query: { color: "#e11d48", shape: "star" },
};

interface HoverState {
  kind: "node" | "edge";
  x: number;
  y: number;
  title: string;
  lines: string[];
}

interface EntityGraphWorkbenchProps {
  title: string;
  nodes: GraphNode[];
  edges: EntityIntelligenceGraphEdge[];
  height?: number;
  emptyMessage?: string;
  onEdgeSelect?: (edge: EntityIntelligenceGraphEdge | null) => void;
  onAction?: (action: "structure" | "design" | "prioritize", nodes: GraphNode[]) => void;
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function edgeConfidence(edge: EntityIntelligenceGraphEdge): number {
  const raw = edge.properties?.confidence;
  return typeof raw === "number" ? raw : 0;
}

function buildGraphMl(nodes: GraphNode[], edges: EntityIntelligenceGraphEdge[]): string {
  const nodeXml = nodes.map((node) => `    <node id="${escapeXml(node.id)}"><data key="label">${escapeXml(node.label)}</data><data key="type">${escapeXml(node.type || "unknown")}</data></node>`).join("\n");
  const edgeXml = edges.map((edge, index) => `    <edge id="e${index}" source="${escapeXml(edge.source)}" target="${escapeXml(edge.target)}"><data key="label">${escapeXml(edge.label || edge.type || "RELATED")}</data></edge>`).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n  <key id="label" for="all" attr.name="label" attr.type="string"/>\n  <key id="type" for="node" attr.name="type" attr.type="string"/>\n  <graph edgedefault="undirected">\n${nodeXml}\n${edgeXml}\n  </graph>\n</graphml>`;
}

export default function EntityGraphWorkbench({
  title,
  nodes,
  edges,
  height = 520,
  emptyMessage = "No graph data available.",
  onEdgeSelect,
  onAction,
}: EntityGraphWorkbenchProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [layout, setLayout] = useState<LayoutName>("cose");
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set());
  const [minConfidence, setMinConfidence] = useState(0);
  const [hovered, setHovered] = useState<HoverState | null>(null);
  const [selectedNodes, setSelectedNodes] = useState<GraphNode[]>([]);

  const filtered = useMemo(() => {
    const typeFilterActive = activeTypes.size > 0;
    const visibleNodes = nodes.filter((node) => !typeFilterActive || activeTypes.has((node.type || "unknown").toLowerCase()));
    const visibleIds = new Set(visibleNodes.map((node) => node.id));
    const visibleEdges = edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target) && edgeConfidence(edge) >= minConfidence);
    return { nodes: visibleNodes, edges: visibleEdges };
  }, [activeTypes, edges, minConfidence, nodes]);

  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of nodes) {
      const key = (node.type || "unknown").toLowerCase();
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [nodes]);

  useEffect(() => {
    if (!containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 10 as any,
            color: "#0f172a",
            "text-wrap": "wrap" as any,
            "text-max-width": 140 as any,
            "text-valign": "bottom" as any,
            "text-margin-y": 5 as any,
            width: "mapData(size, 6, 40, 20, 46)" as any,
            height: "mapData(size, 6, 40, 20, 46)" as any,
            shape: "data(shape)" as any,
            "background-color": "data(color)",
            "border-width": 2,
            "border-color": "#ffffff",
          },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(confidence, 0, 1, 1, 4)",
            label: "data(label)",
            "font-size": 8,
            color: "#64748b",
            "curve-style": "bezier",
            "line-color": "data(color)",
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "text-rotation": "autorotate",
            "line-style": "data(lineStyle)" as any,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#0f172a",
            "border-width": 4,
          },
        },
        {
          selector: "edge:selected",
          style: {
            width: 5,
            "line-color": "#0f172a",
            "target-arrow-color": "#0f172a",
          },
        },
      ],
      selectionType: "additive",
      boxSelectionEnabled: true,
      wheelSensitivity: 0.25,
      minZoom: 0.15,
      maxZoom: 4,
    });

    cy.on("mouseover", "node", (event) => {
      const node = event.target;
      const rendered = node.renderedPosition();
      const attrs = node.data("attributes") as Record<string, unknown> | undefined;
      const identifiers = node.data("identifiers") as Record<string, string> | undefined;
      setHovered({
        kind: "node",
        x: rendered.x,
        y: rendered.y,
        title: String(node.data("label") || node.id()),
        lines: [
          String(node.data("type") || "unknown"),
          identifiers ? Object.entries(identifiers).slice(0, 3).map(([key, value]) => `${key}: ${value}`).join(" | ") : "",
          attrs?.score ? `score ${attrs.score}` : "",
        ].filter(Boolean),
      });
    });

    cy.on("mouseover", "edge", (event) => {
      const edge = event.target;
      const rendered = edge.midpoint();
      const props = edge.data("properties") as Record<string, unknown> | undefined;
      setHovered({
        kind: "edge",
        x: rendered.x,
        y: rendered.y,
        title: String(edge.data("label") || edge.id()),
        lines: [
          props?.source_name ? `src ${String(props.source_name)}` : "",
          props?.confidence != null ? `confidence ${Number(props.confidence).toFixed(2)}` : "",
          props?.contradiction_state ? `contradiction ${String(props.contradiction_state)}` : "",
        ].filter(Boolean),
      });
    });

    cy.on("mouseout", "node, edge", () => setHovered(null));

    cy.on("select unselect", () => {
      const current = cy.nodes(":selected").map((node) => ({
        id: String(node.id()),
        label: String(node.data("label") || node.id()),
        type: String(node.data("type") || "unknown"),
        properties: (node.data("attributes") as Record<string, unknown> | undefined) || {},
      }));
      setSelectedNodes(current);
    });

    cy.on("tap", "edge", (event) => {
      const edge = event.target;
      onEdgeSelect?.({
        id: String(edge.id()),
        source: String(edge.data("source")),
        target: String(edge.data("target")),
        label: String(edge.data("label") || "RELATED"),
        weight: Number(edge.data("confidence") || 1),
        type: String(edge.data("type") || edge.data("label") || "RELATED"),
        properties: (edge.data("properties") as Record<string, unknown> | undefined) || {},
      });
    });

    cy.on("tap", "node", (event) => {
      const node = event.target;
      const neighborhood = node.closedNeighborhood();
      cy.elements().unselect();
      neighborhood.select();
      cy.fit(neighborhood, 40);
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [onEdgeSelect]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().remove();
    const elements = [
      ...filtered.nodes.map((node) => {
        const nodeType = (node.type || "unknown").toLowerCase();
        const score = Number((node.properties as Record<string, unknown> | undefined)?.score || (node.properties as Record<string, unknown> | undefined)?.overall_score || 0);
        const meta = TYPE_META[nodeType] || { color: "#94a3b8", shape: "ellipse" };
        return {
          data: {
            id: node.id,
            label: node.label,
            type: nodeType,
            attributes: node.properties || {},
            identifiers: (node.properties as Record<string, unknown> | undefined)?.identifiers || {},
            color: meta.color,
            shape: meta.shape,
            size: Math.max(8, Math.min(40, 14 + score * 18)),
          },
        };
      }),
      ...filtered.edges.map((edge, index) => {
        const contradiction = String(edge.properties?.contradiction_state || "").toLowerCase();
        return {
          data: {
            id: edge.id || `edge-${index}-${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            label: edge.label || edge.type || "RELATED",
            type: edge.type || edge.label || "RELATED",
            confidence: edgeConfidence(edge),
            color: contradiction === "flagged" || contradiction === "confirmed" ? "#dc2626" : "#94a3b8",
            lineStyle: contradiction === "flagged" || contradiction === "confirmed" ? "dashed" : "solid",
            properties: edge.properties || {},
          },
        };
      }),
    ];
    cy.add(elements as cytoscape.ElementDefinition[]);
    cy.layout({ name: layout, animate: true, animationDuration: 350, padding: 28 } as cytoscape.LayoutOptions).run();
    cy.fit(undefined, 30);
    setSelectedNodes([]);
    onEdgeSelect?.(null);
  }, [filtered, layout, onEdgeSelect]);

  const downloadBlob = (content: string, fileName: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = fileName;
    anchor.click();
    URL.revokeObjectURL(href);
  };

  const exportPng = () => {
    const cy = cyRef.current;
    if (!cy) return;
    const anchor = document.createElement("a");
    anchor.href = cy.png({ full: true, scale: 2, bg: "#ffffff" });
    anchor.download = `${title.toLowerCase().replace(/\s+/g, "-")}.png`;
    anchor.click();
  };

  const exportJson = () => downloadBlob(JSON.stringify(filtered, null, 2), `${title.toLowerCase().replace(/\s+/g, "-")}.json`, "application/json");

  const exportGraphMl = () => downloadBlob(buildGraphMl(filtered.nodes, filtered.edges), `${title.toLowerCase().replace(/\s+/g, "-")}.graphml`, "application/graphml+xml");

  const exportSvg = () => {
    const cy = cyRef.current;
    if (!cy) return;
    const nodeMarkup = cy.nodes().map((node) => {
      const position = node.position();
      return `<g><circle cx="${position.x}" cy="${position.y}" r="16" fill="${escapeXml(String(node.data("color") || "#94a3b8"))}" /><text x="${position.x}" y="${position.y - 20}" text-anchor="middle" font-size="10" fill="#0f172a">${escapeXml(String(node.data("label") || node.id()))}</text></g>`;
    }).join("");
    const edgeMarkup = cy.edges().map((edge) => {
      const source = edge.source().position();
      const target = edge.target().position();
      return `<line x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" stroke="${escapeXml(String(edge.data("color") || "#94a3b8"))}" stroke-width="2" />`;
    }).join("");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800">${edgeMarkup}${nodeMarkup}</svg>`;
    downloadBlob(svg, `${title.toLowerCase().replace(/\s+/g, "-")}.svg`, "image/svg+xml");
  };

  if (nodes.length === 0) {
    return <div className="rounded-2xl border px-5 py-8 text-sm text-[var(--text-muted)]" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>{emptyMessage}</div>;
  }

  return (
    <div className="rounded-2xl border overflow-hidden" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
      <div className="px-4 py-3 border-b space-y-3" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-sm font-semibold text-[var(--text-primary)]">{title}</div>
            <div className="text-[11px] text-[var(--text-muted)]">{filtered.nodes.length} nodes · {filtered.edges.length} edges</div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={() => cyRef.current?.zoom((cyRef.current?.zoom() || 1) * 1.1)} className="px-2 py-1 rounded-lg border text-[11px]" style={{ borderColor: "var(--border)" }}><ZoomIn size={12} /></button>
            <button onClick={() => cyRef.current?.zoom((cyRef.current?.zoom() || 1) * 0.9)} className="px-2 py-1 rounded-lg border text-[11px]" style={{ borderColor: "var(--border)" }}><ZoomOut size={12} /></button>
            <button onClick={() => cyRef.current?.fit(undefined, 30)} className="px-2 py-1 rounded-lg border text-[11px] inline-flex items-center gap-1" style={{ borderColor: "var(--border)" }}><RefreshCw size={12} /> Fit</button>
            <select value={layout} onChange={(event) => setLayout(event.target.value as LayoutName)} className="px-2 py-1 rounded-lg border text-[11px]" style={{ borderColor: "var(--border)", background: "var(--bg-app)" }}>
              {LAYOUTS.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap text-[11px]">
          <span className="inline-flex items-center gap-1 text-[var(--text-muted)]"><Filter size={12} /> Confidence</span>
          <input type="range" min={0} max={1} step={0.05} value={minConfidence} onChange={(event) => setMinConfidence(Number(event.target.value))} />
          <span className="font-medium text-[var(--text-secondary)]">{minConfidence.toFixed(2)}+</span>
          <span className="mx-2 text-[var(--text-muted)] inline-flex items-center gap-1"><LayoutGrid size={12} /> Types</span>
          {typeCounts.map(([type, count]) => {
            const active = activeTypes.size === 0 || activeTypes.has(type);
            const color = TYPE_META[type]?.color || "#94a3b8";
            return (
              <button
                key={type}
                onClick={() => setActiveTypes((current) => {
                  const next = new Set(current);
                  if (next.has(type)) next.delete(type);
                  else next.add(type);
                  return next;
                })}
                className="px-2 py-1 rounded-full border inline-flex items-center gap-1"
                style={{ borderColor: `${color}55`, background: active ? `${color}18` : "transparent", color: active ? color : "var(--text-muted)" }}
              >
                <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                {type} {count}
              </button>
            );
          })}
          {activeTypes.size > 0 && <button onClick={() => setActiveTypes(new Set())} className="px-2 py-1 rounded-full border text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}>clear</button>}
        </div>

        {selectedNodes.length > 0 && (
          <div className="flex items-center justify-between gap-3 flex-wrap rounded-xl px-3 py-2" style={{ background: "rgba(79, 70, 229, 0.08)", border: "1px solid rgba(79, 70, 229, 0.18)" }}>
            <div className="text-[11px] text-[var(--text-secondary)]">{selectedNodes.length} selected: {selectedNodes.map((node) => node.label).slice(0, 4).join(", ")}</div>
            <div className="flex items-center gap-2 flex-wrap">
              <button onClick={() => onAction?.("structure", selectedNodes)} className="px-2 py-1 rounded-lg border text-[11px] inline-flex items-center gap-1" style={{ borderColor: "var(--border)" }}><Box size={12} /> Structure</button>
              <button onClick={() => onAction?.("design", selectedNodes)} className="px-2 py-1 rounded-lg border text-[11px] inline-flex items-center gap-1" style={{ borderColor: "var(--border)" }}><FlaskConical size={12} /> Design</button>
              <button onClick={() => onAction?.("prioritize", selectedNodes)} className="px-2 py-1 rounded-lg border text-[11px] inline-flex items-center gap-1" style={{ borderColor: "var(--border)" }}><BarChart3 size={12} /> Prioritize</button>
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={exportPng} className="px-2 py-1 rounded-lg border text-[11px] inline-flex items-center gap-1" style={{ borderColor: "var(--border)" }}><Download size={12} /> PNG</button>
          <button onClick={exportSvg} className="px-2 py-1 rounded-lg border text-[11px]" style={{ borderColor: "var(--border)" }}>SVG</button>
          <button onClick={exportJson} className="px-2 py-1 rounded-lg border text-[11px]" style={{ borderColor: "var(--border)" }}>JSON</button>
          <button onClick={exportGraphMl} className="px-2 py-1 rounded-lg border text-[11px]" style={{ borderColor: "var(--border)" }}>GraphML</button>
        </div>
      </div>

      <div className="relative" style={{ height }}>
        <div ref={containerRef} className="w-full h-full" />
        {hovered && (
          <div className="absolute z-10 max-w-[260px] rounded-xl border px-3 py-2 text-[11px] shadow-lg" style={{ left: Math.min(hovered.x + 16, 900), top: Math.min(hovered.y + 16, height - 80), background: "var(--bg-app)", borderColor: "var(--border)" }}>
            <div className="font-semibold text-[var(--text-primary)]">{hovered.title}</div>
            {hovered.lines.map((line) => <div key={line} className="text-[var(--text-muted)] mt-0.5">{line}</div>)}
          </div>
        )}
      </div>
    </div>
  );
}