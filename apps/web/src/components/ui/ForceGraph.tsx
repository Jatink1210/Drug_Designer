/** ForceGraph — Interactive force-directed entity relationship graph.
 *  Inspired by Drug-Synth's PyVis visualization with entity-type color coding.
 *  Uses canvas + requestAnimationFrame for performance.
 */

import { useRef, useEffect, useState, useCallback } from "react";
import { Network, ZoomIn, ZoomOut, Maximize2, Minimize2, X } from "lucide-react";
import type { GraphNode, GraphEdge } from "@/lib/api";
import { ENTITY_COLORS, getEntityColor } from "@/lib/entityColors";

/* Entity-type color map — uses canonical ENTITY_COLORS */
const TYPE_COLORS: Record<string, string> = {
  ...ENTITY_COLORS,
  chemical: ENTITY_COLORS.molecule,
  phenotype: '#ea580c',
  source: '#6366f1',
};

interface SimNode {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  pinned: boolean;
}

interface SimEdge {
  source: string;
  target: string;
  label?: string;
  contradiction?: boolean;
  evidenceCount?: number;
  reason?: string;
  evidenceIds?: string[];
  relationshipType?: string;
  sourceDb?: string;
  confidence?: number;
  isDashed?: boolean;
}

interface ForceGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  height?: number;
  onNodeClick?: (node: GraphNode) => void;
  onEdgeClick?: (edge: GraphEdge) => void;
  expanded?: boolean;
  onToggleExpand?: () => void;
}

export default function ForceGraph({
  nodes,
  edges,
  height = 400,
  onNodeClick,
  onEdgeClick,
  expanded,
  onToggleExpand,
}: ForceGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const simNodesRef = useRef<SimNode[]>([]);
  const simEdgesRef = useRef<SimEdge[]>([]);
  const scaleRef = useRef(1);
  const offsetRef = useRef({ x: 0, y: 0 });
  const dragRef = useRef<{ nodeId: string | null; startX: number; startY: number; isPanning: boolean }>({
    nodeId: null, startX: 0, startY: 0, isPanning: false,
  });
  const hoveredRef = useRef<string | null>(null);
  const [stats, setStats] = useState({ nodes: 0, edges: 0 });
  const [selectedEdge, setSelectedEdge] = useState<SimEdge | null>(null);

  // Initialize simulation nodes
  useEffect(() => {
    if (nodes.length === 0) return;

    const degreeCounts: Record<string, number> = {};
    edges.forEach((e) => {
      degreeCounts[e.source] = (degreeCounts[e.source] || 0) + 1;
      degreeCounts[e.target] = (degreeCounts[e.target] || 0) + 1;
    });

    const canvas = canvasRef.current;
    const w = canvas?.width || 800;
    const h = canvas?.height || 400;

    simNodesRef.current = nodes.map((n) => {
      const degree = degreeCounts[n.id] || 1;
      // Use backend-provided color (from ENTITY_COLORS) or fall back to TYPE_COLORS lookup
      const nodeColor = (n as Record<string, unknown>).color as string
        || getEntityColor(n.type || "unknown");
      // Use backend-provided size (from betweenness centrality: 0.5 + c * 2.0) or fall back to degree-based
      const backendSize = (n as Record<string, unknown>).size as number | undefined;
      const nodeRadius = backendSize
        ? Math.min(backendSize * 10, 25) // Scale centrality-based size for canvas
        : Math.min(4 + Math.sqrt(degree) * 3, 20);
      return {
        id: n.id,
        label: n.label,
        type: n.type || "unknown",
        x: w / 2 + (Math.random() - 0.5) * w * 0.6,
        y: h / 2 + (Math.random() - 0.5) * h * 0.6,
        vx: 0,
        vy: 0,
        radius: nodeRadius,
        color: nodeColor,
        pinned: false,
      };
    });

    simEdgesRef.current = edges.map((e) => {
      const extra = e as unknown as Record<string, unknown>;
      const cState = String(extra.contradiction_state || "").toLowerCase();
      const relType = String(extra.relationship_type || extra.type || e.label || "");
      const isInferred = relType.includes("inferred") || relType.includes("CO_ASSOCIATED") || relType.includes("ALIAS_BRIDGE");
      return {
        source: e.source,
        target: e.target,
        label: e.label,
        contradiction:
          e.type === "contradiction" ||
          extra.contradiction === true ||
          cState === "flagged" ||
          cState === "confirmed",
        evidenceCount: typeof extra.evidence_count === "number" ? extra.evidence_count : undefined,
        reason: typeof extra.reason === "string" ? extra.reason : undefined,
        evidenceIds: Array.isArray(extra.evidence_ids) ? extra.evidence_ids as string[] : undefined,
        relationshipType: relType || undefined,
        sourceDb: typeof extra.source_db === "string" ? extra.source_db : undefined,
        confidence: typeof extra.confidence === "number" ? extra.confidence : undefined,
        isDashed: isInferred,
      };
    });

    setStats({ nodes: nodes.length, edges: edges.length });
    scaleRef.current = 1;
    offsetRef.current = { x: 0, y: 0 };
  }, [nodes, edges]);

  // Force simulation + render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let cooling = 1.0;
    const REPULSION = 2000;
    const ATTRACTION = 0.005;
    const DAMPING = 0.85;
    const CENTER_GRAVITY = 0.01;

    const tick = () => {
      const sNodes = simNodesRef.current;
      const sEdges = simEdgesRef.current;
      if (sNodes.length === 0) return;

      const w = canvas.width;
      const h = canvas.height;

      // Apply forces (Barnes-Hut simplified)
      if (cooling > 0.01) {
        // Repulsion between all pairs
        for (let i = 0; i < sNodes.length; i++) {
          for (let j = i + 1; j < sNodes.length; j++) {
            const a = sNodes[i];
            const b = sNodes[j];
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const d2 = dx * dx + dy * dy + 1;
            const force = (REPULSION * cooling) / d2;
            const fx = dx / Math.sqrt(d2) * force;
            const fy = dy / Math.sqrt(d2) * force;
            if (!a.pinned) { a.vx -= fx; a.vy -= fy; }
            if (!b.pinned) { b.vx += fx; b.vy += fy; }
          }
        }

        // Attraction along edges
        const nodeMap = new Map(sNodes.map((n) => [n.id, n]));
        for (const e of sEdges) {
          const a = nodeMap.get(e.source);
          const b = nodeMap.get(e.target);
          if (!a || !b) continue;
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const fx = dx * ATTRACTION * cooling;
          const fy = dy * ATTRACTION * cooling;
          if (!a.pinned) { a.vx += fx; a.vy += fy; }
          if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
        }

        // Center gravity
        for (const n of sNodes) {
          if (n.pinned) continue;
          n.vx += (w / 2 - n.x) * CENTER_GRAVITY * cooling;
          n.vy += (h / 2 - n.y) * CENTER_GRAVITY * cooling;
          n.vx *= DAMPING;
          n.vy *= DAMPING;
          n.x += n.vx;
          n.y += n.vy;
          // Bounds
          n.x = Math.max(n.radius, Math.min(w - n.radius, n.x));
          n.y = Math.max(n.radius, Math.min(h - n.radius, n.y));
        }

        cooling *= 0.995;
      }

      // Render
      ctx.save();
      ctx.clearRect(0, 0, w, h);
      ctx.translate(offsetRef.current.x, offsetRef.current.y);
      ctx.scale(scaleRef.current, scaleRef.current);

      // Draw edges
      const nodeMap = new Map(sNodes.map((n) => [n.id, n]));
      for (const e of sEdges) {
        const a = nodeMap.get(e.source);
        const b = nodeMap.get(e.target);
        if (!a || !b) continue;
        if (e.contradiction) {
          ctx.lineWidth = 1.5;
          ctx.strokeStyle = "rgba(239, 68, 68, 0.6)";
          ctx.setLineDash([4, 3]);
        } else if (e.isDashed) {
          ctx.lineWidth = 0.8;
          ctx.strokeStyle = "rgba(156, 163, 175, 0.45)";
          ctx.setLineDash([6, 4]);
        } else {
          ctx.lineWidth = 0.5;
          ctx.strokeStyle = "rgba(156, 163, 175, 0.3)";
          ctx.setLineDash([]);
        }
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // Draw nodes
      for (const n of sNodes) {
        const isHovered = hoveredRef.current === n.id;
        ctx.beginPath();
        ctx.arc(n.x, n.y, isHovered ? n.radius * 1.3 : n.radius, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.globalAlpha = isHovered ? 1 : 0.85;
        ctx.fill();
        ctx.globalAlpha = 1;

        if (isHovered) {
          ctx.strokeStyle = "#fff";
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        // Label (only for larger or hovered nodes)
        if (n.radius >= 8 || isHovered) {
          ctx.fillStyle = "#1f2937";
          ctx.font = `${isHovered ? "bold " : ""}${Math.max(9, n.radius * 0.9)}px Inter, sans-serif`;
          ctx.textAlign = "center";
          ctx.fillText(
            n.label.length > 20 ? n.label.slice(0, 18) + "…" : n.label,
            n.x,
            n.y - n.radius - 4,
          );
        }
      }

      ctx.restore();
      animRef.current = requestAnimationFrame(tick);
    };

    animRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animRef.current);
  }, [nodes, edges]);

  // Canvas resize
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const resize = () => {
      const w = parent.clientWidth || 800;
      const h = parent.clientHeight || height;
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
    };
    const ro = new ResizeObserver(resize);
    ro.observe(parent);
    resize();
    return () => ro.disconnect();
  }, [height]);

  // Mouse interactions
  const getNodeAt = useCallback((mx: number, my: number): SimNode | null => {
    const s = scaleRef.current;
    const ox = offsetRef.current.x;
    const oy = offsetRef.current.y;
    const x = (mx - ox) / s;
    const y = (my - oy) / s;
    for (const n of [...simNodesRef.current].reverse()) {
      const dx = n.x - x;
      const dy = n.y - y;
      if (dx * dx + dy * dy < (n.radius + 4) * (n.radius + 4)) return n;
    }
    return null;
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const node = getNodeAt(mx, my);
    if (node) {
      dragRef.current = { nodeId: node.id, startX: mx, startY: my, isPanning: false };
      node.pinned = true;
    } else {
      dragRef.current = { nodeId: null, startX: mx, startY: my, isPanning: true };
    }
  }, [getNodeAt]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    if (dragRef.current.nodeId) {
      const s = scaleRef.current;
      const node = simNodesRef.current.find((n) => n.id === dragRef.current.nodeId);
      if (node) {
        node.x += (mx - dragRef.current.startX) / s;
        node.y += (my - dragRef.current.startY) / s;
        dragRef.current.startX = mx;
        dragRef.current.startY = my;
      }
    } else if (dragRef.current.isPanning) {
      offsetRef.current.x += mx - dragRef.current.startX;
      offsetRef.current.y += my - dragRef.current.startY;
      dragRef.current.startX = mx;
      dragRef.current.startY = my;
    } else {
      const node = getNodeAt(mx, my);
      hoveredRef.current = node?.id ?? null;
      if (canvasRef.current) {
        canvasRef.current.style.cursor = node ? "pointer" : "default";
      }
    }
  }, [getNodeAt]);

  const handleMouseUp = useCallback(() => {
    if (dragRef.current.nodeId) {
      const node = simNodesRef.current.find((n) => n.id === dragRef.current.nodeId);
      if (node) node.pinned = false;
    }
    dragRef.current = { nodeId: null, startX: 0, startY: 0, isPanning: false };
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    scaleRef.current = Math.max(0.2, Math.min(5, scaleRef.current * factor));
  }, []);

  const getEdgeAt = useCallback((mx: number, my: number): SimEdge | null => {
    const s = scaleRef.current;
    const ox = offsetRef.current.x;
    const oy = offsetRef.current.y;
    const px = (mx - ox) / s;
    const py = (my - oy) / s;
    const nodeMap = new Map(simNodesRef.current.map((n) => [n.id, n]));
    let best: SimEdge | null = null;
    let bestDist = 6; // max pixel distance threshold
    for (const e of simEdgesRef.current) {
      const a = nodeMap.get(e.source);
      const b = nodeMap.get(e.target);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len2 = dx * dx + dy * dy;
      if (len2 === 0) continue;
      const t = Math.max(0, Math.min(1, ((px - a.x) * dx + (py - a.y) * dy) / len2));
      const cx = a.x + t * dx - px;
      const cy = a.y + t * dy - py;
      const dist = Math.sqrt(cx * cx + cy * cy);
      if (dist < bestDist) { bestDist = dist; best = e; }
    }
    return best;
  }, []);

  const handleClick = useCallback((e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const node = getNodeAt(mx, my);
    if (node && onNodeClick) {
      setSelectedEdge(null);
      onNodeClick({ id: node.id, label: node.label, type: node.type });
      return;
    }
    const simEdge = getEdgeAt(mx, my);
    if (simEdge) {
      setSelectedEdge(simEdge);
      if (onEdgeClick) {
        const origEdge = edges.find((oe) => oe.source === simEdge.source && oe.target === simEdge.target);
        if (origEdge) onEdgeClick(origEdge);
      }
    } else {
      setSelectedEdge(null);
    }
  }, [getNodeAt, getEdgeAt, onNodeClick, onEdgeClick, edges]);

  if (nodes.length === 0) {
    return (
      <div className="rounded-lg border p-6 text-center" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
        <Network size={32} className="text-[var(--border)] mx-auto mb-2" />
        <p className="text-xs text-[var(--text-muted)]">No entity graph data available</p>
      </div>
    );
  }

  // Type legend
  const typeCounts: Record<string, number> = {};
  nodes.forEach((n) => { typeCounts[n.type || "unknown"] = (typeCounts[n.type || "unknown"] || 0) + 1; });

  return (
    <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--border)", background: "#fafbfc" }}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-1.5">
          <Network size={14} className="text-[var(--accent)]" />
          <span className="text-xs font-semibold text-[var(--text-primary)]">Entity Relationship Graph</span>
          <span className="text-[10px] text-[var(--text-muted)] ml-1">{stats.nodes} nodes · {stats.edges} edges</span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => { scaleRef.current = Math.min(5, scaleRef.current * 1.2); }} className="p-1 rounded hover:bg-[var(--bg-inset)]" title="Zoom In"><ZoomIn size={13} className="text-[var(--text-muted)]" /></button>
          <button onClick={() => { scaleRef.current = Math.max(0.2, scaleRef.current * 0.8); }} className="p-1 rounded hover:bg-[var(--bg-inset)]" title="Zoom Out"><ZoomOut size={13} className="text-[var(--text-muted)]" /></button>
          {onToggleExpand && (
            <button onClick={onToggleExpand} className="p-1 rounded hover:bg-[var(--bg-inset)]" title={expanded ? "Collapse" : "Expand"}>
              {expanded ? <Minimize2 size={13} className="text-[var(--text-muted)]" /> : <Maximize2 size={13} className="text-[var(--text-muted)]" />}
            </button>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-1.5 px-3 py-1.5 border-b" style={{ borderColor: "var(--border)", background: "#fff" }}>
        {Object.entries(typeCounts).map(([type, count]) => (
          <span key={type} className="flex items-center gap-1 text-[10px]">
            <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: TYPE_COLORS[type.toLowerCase()] || "#6b7280" }} />
            <span className="text-[var(--text-muted)] capitalize">{type}</span>
            <span className="text-[var(--text-muted)]">({count})</span>
          </span>
        ))}
      </div>

      {/* Canvas */}
      <div style={{ height }} className="relative">
        <canvas
          ref={canvasRef}
          className="w-full h-full"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
          onClick={handleClick}
        />
        {/* Edge Detail Panel */}
        {selectedEdge && (
          <div
            className="absolute top-2 right-2 w-72 rounded-xl border shadow-lg p-3 space-y-2 z-10"
            style={{ background: "var(--bg-app)", borderColor: "var(--border)" }}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[var(--text-primary)]">Edge Detail</span>
              <button onClick={() => setSelectedEdge(null)} className="p-0.5 rounded hover:bg-[var(--bg-surface)]">
                <X size={12} className="text-[var(--text-muted)]" />
              </button>
            </div>
            <div className="text-[10px] text-[var(--text-muted)]">
              {selectedEdge.source} → {selectedEdge.target}
            </div>
            {selectedEdge.relationshipType && (
              <div className="text-[10px]">
                <span className="font-medium text-[var(--text-secondary)]">Type: </span>
                <span className="px-1.5 py-0.5 rounded-full bg-[var(--bg-surface)] text-[var(--text-primary)]">
                  {selectedEdge.relationshipType.replace(/_/g, " ")}
                </span>
              </div>
            )}
            {selectedEdge.reason && (
              <div className="text-[10px] text-[var(--text-secondary)]">
                <span className="font-medium">Reason: </span>{selectedEdge.reason}
              </div>
            )}
            {selectedEdge.sourceDb && (
              <div className="text-[10px] text-[var(--text-muted)]">
                <span className="font-medium">Source: </span>{selectedEdge.sourceDb}
              </div>
            )}
            {selectedEdge.confidence != null && (
              <div className="text-[10px] text-[var(--text-muted)]">
                <span className="font-medium">Confidence: </span>{(selectedEdge.confidence * 100).toFixed(0)}%
              </div>
            )}
            {selectedEdge.evidenceIds && selectedEdge.evidenceIds.length > 0 && (
              <div className="text-[10px] text-[var(--text-muted)]">
                <span className="font-medium">Evidence: </span>{selectedEdge.evidenceIds.length} item(s)
              </div>
            )}
            {selectedEdge.isDashed && (
              <div className="text-[9px] text-[var(--text-muted)] italic">Inferred relationship (dashed line)</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
