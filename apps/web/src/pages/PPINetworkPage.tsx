/** PPI Network Explorer — Protein-Protein Interaction visualization via STRING DB.
 *  Select genes from target prioritization → visualize interaction network + pathways.
 */

import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import {
  Network, Search, Loader2, Download, Filter, Dna,
  ZoomIn, ZoomOut, Maximize2, Info, ExternalLink,
} from "lucide-react";
import { ensureApiBase } from "@/lib/api";

interface PPINode {
  id: string;
  label: string;
  is_query_gene: boolean;
}

interface PPIEdge {
  source: string;
  target: string;
  score: number;
  id: string;
}

const PRESETS = [
  { label: "NSCLC Targets", genes: ["EGFR", "ALK", "KRAS", "MET", "ROS1", "BRAF", "RET"] },
  { label: "Alzheimer's", genes: ["APP", "PSEN1", "PSEN2", "APOE", "MAPT", "BACE1", "TREM2"] },
  { label: "Breast Cancer", genes: ["BRCA1", "BRCA2", "HER2", "ESR1", "PIK3CA", "TP53"] },
];

export default function PPINetworkPage() {
  const [genesInput, setGenesInput] = useState("");
  const [nodes, setNodes] = useState<PPINode[]>([]);
  const [edges, setEdges] = useState<PPIEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [threshold, setThreshold] = useState(0.4);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [nodePositions, setNodePositions] = useState<Record<string, { x: number; y: number }>>({});

  const fetchPPI = useCallback(async (genes: string[]) => {
    if (genes.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const base = await ensureApiBase();
      const res = await fetch(`${base}/targets/ppi-network`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ genes, score_threshold: threshold }),
      });
      if (!res.ok) throw new Error("Failed to fetch PPI network");
      const envelope = await res.json();
      const data = envelope?.data ?? envelope;
      setNodes(data.nodes || []);
      setEdges(data.edges || []);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }, [threshold]);

  const handleSubmit = useCallback(() => {
    const genes = genesInput.split(/[,;\s]+/).map(g => g.trim().toUpperCase()).filter(Boolean);
    fetchPPI(genes);
  }, [genesInput, fetchPPI]);

  // Force-directed layout simulation
  useEffect(() => {
    if (nodes.length === 0) return;
    const positions: Record<string, { x: number; y: number; vx: number; vy: number }> = {};
    const W = 700, H = 500;
    nodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length;
      const r = Math.min(W, H) * 0.35;
      positions[n.id] = { x: W / 2 + r * Math.cos(angle), y: H / 2 + r * Math.sin(angle), vx: 0, vy: 0 };
    });

    // Simple force simulation (50 iterations)
    for (let iter = 0; iter < 80; iter++) {
      const damping = 0.85;
      // Repulsion between all nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = positions[nodes[i].id], b = positions[nodes[j].id];
          let dx = a.x - b.x, dy = a.y - b.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = 5000 / (dist * dist);
          const fx = (dx / dist) * force, fy = (dy / dist) * force;
          a.vx += fx; a.vy += fy;
          b.vx -= fx; b.vy -= fy;
        }
      }
      // Attraction along edges
      for (const e of edges) {
        const a = positions[e.source], b = positions[e.target];
        if (!a || !b) continue;
        let dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = (dist - 120) * 0.05 * e.score;
        const fx = (dx / dist) * force, fy = (dy / dist) * force;
        a.vx += fx; a.vy += fy;
        b.vx -= fx; b.vy -= fy;
      }
      // Center gravity
      for (const n of nodes) {
        const p = positions[n.id];
        p.vx += (W / 2 - p.x) * 0.01;
        p.vy += (H / 2 - p.y) * 0.01;
        p.x += p.vx * damping;
        p.y += p.vy * damping;
        p.vx *= damping;
        p.vy *= damping;
        p.x = Math.max(30, Math.min(W - 30, p.x));
        p.y = Math.max(30, Math.min(H - 30, p.y));
      }
    }
    const finalPos: Record<string, { x: number; y: number }> = {};
    for (const [id, p] of Object.entries(positions)) {
      finalPos[id] = { x: p.x, y: p.y };
    }
    setNodePositions(finalPos);
  }, [nodes, edges]);

  // Canvas rendering
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || nodes.length === 0 || Object.keys(nodePositions).length === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = 700 * dpr;
    canvas.height = 500 * dpr;
    ctx.scale(dpr * zoom, dpr * zoom);
    ctx.clearRect(0, 0, 700, 500);

    // Draw edges
    for (const e of edges) {
      const a = nodePositions[e.source], b = nodePositions[e.target];
      if (!a || !b) continue;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = `rgba(139, 92, 246, ${Math.min(e.score, 1) * 0.6 + 0.1})`;
      ctx.lineWidth = Math.max(1, e.score * 3);
      ctx.stroke();
      // Score label
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      ctx.font = "8px sans-serif";
      ctx.fillStyle = "rgba(100,100,100,0.6)";
      ctx.fillText(e.score.toFixed(2), mx - 10, my - 3);
    }

    // Draw nodes
    for (const n of nodes) {
      const p = nodePositions[n.id];
      if (!p) continue;
      const r = n.is_query_gene ? 18 : 12;
      const isSelected = selectedNode === n.id;

      // Glow for selected
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, r + 6, 0, 2 * Math.PI);
        ctx.fillStyle = "rgba(139, 92, 246, 0.15)";
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = n.is_query_gene ? "#8b5cf6" : "#e5e7eb";
      ctx.fill();
      ctx.strokeStyle = isSelected ? "#6d28d9" : n.is_query_gene ? "#7c3aed" : "#d1d5db";
      ctx.lineWidth = isSelected ? 3 : 1.5;
      ctx.stroke();

      // Label
      ctx.font = `${n.is_query_gene ? "bold" : "normal"} 10px sans-serif`;
      ctx.fillStyle = n.is_query_gene ? "#fff" : "#374151";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(n.label, p.x, p.y);
    }
  }, [nodes, edges, nodePositions, selectedNode, zoom]);

  // Handle canvas click
  const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / zoom;
    const y = (e.clientY - rect.top) / zoom;
    for (const n of nodes) {
      const p = nodePositions[n.id];
      if (!p) continue;
      const dx = p.x - x, dy = p.y - y;
      if (dx * dx + dy * dy < 400) {
        setSelectedNode(n.id);
        return;
      }
    }
    setSelectedNode(null);
  }, [nodes, nodePositions, zoom]);

  const selectedEdges = useMemo(() => {
    if (!selectedNode) return [];
    return edges.filter(e => e.source === selectedNode || e.target === selectedNode)
      .sort((a, b) => b.score - a.score);
  }, [selectedNode, edges]);

  const connectedCount = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of edges) {
      counts[e.source] = (counts[e.source] || 0) + 1;
      counts[e.target] = (counts[e.target] || 0) + 1;
    }
    return counts;
  }, [edges]);

  const handleExport = useCallback(() => {
    const rows = ["source,target,score", ...edges.map(e => `${e.source},${e.target},${e.score}`)];
    const blob = new Blob([rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "ppi_network.csv"; a.click();
    URL.revokeObjectURL(url);
  }, [edges]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ background: "var(--bg-app)" }}>
      {/* Header */}
      <div className="shrink-0 px-6 pt-5 pb-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2 mb-2">
          <Network size={18} style={{ color: "var(--accent)" }} />
          <h1 className="text-lg font-bold">PPI Network Explorer</h1>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-50 text-purple-600 font-semibold">STRING DB</span>
        </div>
        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <label className="text-[9px] font-bold uppercase tracking-wider block mb-1" style={{ color: "var(--text-muted)" }}>
              Gene Symbols (comma-separated)
            </label>
            <input
              value={genesInput}
              onChange={e => setGenesInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSubmit()}
              placeholder="e.g. EGFR, ALK, KRAS, MET, BRAF"
              className="w-full text-xs px-3 py-2 rounded-lg border"
              style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
            />
          </div>
          <div className="w-32">
            <label className="text-[9px] font-bold uppercase tracking-wider block mb-1" style={{ color: "var(--text-muted)" }}>
              Min Score
            </label>
            <input
              type="number"
              value={threshold}
              onChange={e => setThreshold(+e.target.value)}
              min={0} max={1} step={0.05}
              className="w-full text-xs px-3 py-2 rounded-lg border"
              style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={loading || !genesInput.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50"
            style={{ background: "var(--accent)" }}
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
            {loading ? "Loading…" : "Fetch Network"}
          </button>
        </div>
        <div className="flex items-center gap-1.5 mt-2">
          <span className="text-[9px] font-medium" style={{ color: "var(--text-muted)" }}>Presets:</span>
          {PRESETS.map(p => (
            <button
              key={p.label}
              onClick={() => { setGenesInput(p.genes.join(", ")); fetchPPI(p.genes); }}
              disabled={loading}
              className="text-[10px] px-2 py-0.5 rounded-full font-medium border"
              style={{ borderColor: "var(--border)", color: "var(--accent)" }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mx-6 mt-3 p-3 rounded-lg bg-red-50 text-red-600 text-xs">{error}</div>
      )}

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Network visualization */}
        <div className="flex-1 p-4 flex flex-col items-center justify-center relative">
          {nodes.length === 0 && !loading && (
            <div className="text-center">
              <Network size={48} className="mx-auto mb-3 text-gray-400" />
              <div className="text-sm font-semibold text-[var(--text-muted)]">No network loaded</div>
              <div className="text-[10px] text-[var(--text-muted)] mt-1">Enter gene symbols above to visualize protein interactions</div>
            </div>
          )}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
              <Loader2 size={16} className="animate-spin" /> Fetching interactions from STRING DB...
            </div>
          )}
          {nodes.length > 0 && !loading && (
            <>
              {/* Stats bar */}
              <div className="flex gap-3 mb-3 w-full max-w-[700px]">
                {[
                  { label: "Nodes", value: nodes.length, color: "#8b5cf6" },
                  { label: "Edges", value: edges.length, color: "#3b82f6" },
                  { label: "Query Genes", value: nodes.filter(n => n.is_query_gene).length, color: "#10b981" },
                  { label: "Avg Score", value: edges.length > 0 ? (edges.reduce((s, e) => s + e.score, 0) / edges.length).toFixed(2) : "—", color: "#f59e0b" },
                ].map(s => (
                  <span key={s.label} className="text-[10px] font-semibold px-2 py-1 rounded flex items-center gap-1"
                    style={{ background: `${s.color}10`, color: s.color, border: `1px solid ${s.color}20` }}>
                    {s.label}: {s.value}
                  </span>
                ))}
                <button onClick={handleExport} className="ml-auto text-[10px] px-2 py-1 rounded border flex items-center gap-1"
                  style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
                  <Download size={9} /> CSV
                </button>
              </div>
              {/* Canvas */}
              <div className="relative rounded-xl border overflow-hidden" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                <canvas
                  ref={canvasRef}
                  width={700}
                  height={500}
                  style={{ width: 700, height: 500, cursor: "pointer" }}
                  onClick={handleCanvasClick}
                />
                {/* Zoom controls */}
                <div className="absolute bottom-3 right-3 flex gap-1">
                  <button onClick={() => setZoom(z => Math.min(z + 0.2, 3))} className="w-7 h-7 rounded bg-white border flex items-center justify-center shadow-sm"
                    style={{ borderColor: "var(--border)" }}>
                    <ZoomIn size={12} />
                  </button>
                  <button onClick={() => setZoom(z => Math.max(z - 0.2, 0.4))} className="w-7 h-7 rounded bg-white border flex items-center justify-center shadow-sm"
                    style={{ borderColor: "var(--border)" }}>
                    <ZoomOut size={12} />
                  </button>
                  <button onClick={() => setZoom(1)} className="w-7 h-7 rounded bg-white border flex items-center justify-center shadow-sm"
                    style={{ borderColor: "var(--border)" }}>
                    <Maximize2 size={12} />
                  </button>
                </div>
                {/* Legend */}
                <div className="absolute top-3 left-3 bg-white/90 border rounded-lg p-2 text-[9px] space-y-1" style={{ borderColor: "var(--border)" }}>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-purple-500" />
                    <span>Query Gene</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-gray-200 border border-gray-300" />
                    <span>Interactor</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-6 h-0.5 bg-purple-400" />
                    <span>Interaction (thickness = score)</span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Right panel — details */}
        {nodes.length > 0 && (
          <div className="w-[300px] shrink-0 overflow-y-auto p-4 border-l" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
            {selectedNode ? (
              <>
                <div className="flex items-center gap-2 mb-3">
                  <Dna size={14} className="text-purple-500" />
                  <h3 className="text-sm font-bold">{selectedNode}</h3>
                  {nodes.find(n => n.id === selectedNode)?.is_query_gene && (
                    <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-600 font-semibold">Query Gene</span>
                  )}
                </div>
                <div className="text-[10px] mb-3" style={{ color: "var(--text-muted)" }}>
                  {connectedCount[selectedNode] || 0} interactions · Click edges below for details
                </div>
                <div className="section-label mb-2">Interactions ({selectedEdges.length})</div>
                <div className="space-y-1.5">
                  {selectedEdges.map(e => {
                    const partner = e.source === selectedNode ? e.target : e.source;
                    return (
                      <div key={e.id} className="flex items-center gap-2 p-2 rounded-lg text-xs" style={{ background: "var(--bg-app)", border: "1px solid var(--border)" }}>
                        <span className="font-semibold text-purple-600">{partner}</span>
                        <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                          <div className="h-full rounded-full bg-purple-400" style={{ width: `${e.score * 100}%` }} />
                        </div>
                        <span className="font-mono text-[10px]" style={{ color: e.score > 0.7 ? "#22c55e" : e.score > 0.4 ? "#f59e0b" : "#ef4444" }}>
                          {e.score.toFixed(3)}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <a
                  href={`https://string-db.org/network/${selectedNode}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-[10px] text-purple-500 mt-3 hover:underline"
                >
                  <ExternalLink size={10} /> View on STRING DB
                </a>
              </>
            ) : (
              <>
                <div className="section-label mb-2">Node Degree Ranking</div>
                <div className="space-y-1">
                  {nodes
                    .slice()
                    .sort((a, b) => (connectedCount[b.id] || 0) - (connectedCount[a.id] || 0))
                    .map((n, i) => (
                      <div
                        key={n.id}
                        className="flex items-center gap-2 p-2 rounded text-xs cursor-pointer hover:bg-[var(--bg-surface)]"
                        style={{ border: "1px solid var(--border)" }}
                        onClick={() => setSelectedNode(n.id)}
                      >
                        <span className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold"
                          style={{ background: n.is_query_gene ? "#8b5cf6" : "#e5e7eb", color: n.is_query_gene ? "#fff" : "#6b7280" }}>
                          {i + 1}
                        </span>
                        <span className="font-semibold flex-1">{n.label}</span>
                        <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
                          {connectedCount[n.id] || 0} edges
                        </span>
                      </div>
                    ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
