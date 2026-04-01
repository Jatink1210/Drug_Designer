/** MiniGraphPreview — lightweight entity graph chip display. */

import { Network } from "lucide-react";
import type { GraphNode, GraphEdge } from "@/lib/api";
import { TYPE_COLORS } from "./EntityPill";

interface MiniGraphPreviewProps {
    nodes: GraphNode[];
    edges: GraphEdge[];
    onExpand?: () => void;
}

export default function MiniGraphPreview({ nodes, edges, onExpand }: MiniGraphPreviewProps) {
    if (nodes.length === 0) return null;
    const typeCounts: Record<string, number> = {};
    nodes.forEach(n => { typeCounts[n.type] = (typeCounts[n.type] || 0) + 1; });

    return (
        <div className="bg-white rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5">
                    <Network size={14} className="text-[var(--accent)]" />
                    <span className="text-xs font-semibold text-[var(--text-primary)]">Entity Graph</span>
                </div>
                <span className="text-[10px] text-[var(--text-muted)]">{nodes.length}n / {edges.length}e</span>
            </div>
            <div className="flex flex-wrap gap-1 mb-2">
                {Object.entries(typeCounts).map(([type, count]) => (
                    <span key={type} className="px-1.5 py-0.5 rounded text-[10px] font-medium text-white"
                        style={{ background: TYPE_COLORS[type] || "#6b7280" }}>
                        {type} ({count})
                    </span>
                ))}
            </div>
            <div className="flex flex-wrap gap-1">
                {nodes.slice(0, 12).map(n => (
                    <span key={n.id} className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600 truncate max-w-[120px]">
                        {n.label}
                    </span>
                ))}
                {nodes.length > 12 && <span className="text-[10px] text-[var(--text-muted)]">+{nodes.length - 12} more</span>}
            </div>
            {onExpand && (
                <button onClick={onExpand} className="mt-2 text-[10px] text-[var(--accent)] hover:underline">
                    Open in Graph Lab →
                </button>
            )}
        </div>
    );
}
