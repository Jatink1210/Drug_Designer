import { Link2, Sparkles, RefreshCw } from "lucide-react";
import { useGraphSample } from "@/lib/hooks";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "@/lib/types";

type Node = { id: string; name?: string; type?: string };
type Edge = { source: string; target: string; type?: string };

export default function InteractionMaps() {
  const { data, state, refetch } = useGraphSample();

  const nodes: Node[] = data?.nodes ?? [];
  const edges: Edge[] = data?.edges ?? [];
  const loading = state === "loading";

  // Execute physical radial distribution mapping for topology display (D3 Force equivalent baseline)
  const radius = 220;
  const centerX = 350;
  const centerY = 300;

  const positionedNodes = nodes.map((n, i) => {
    const angle = (i / (nodes.length || 1)) * 2 * Math.PI;
    return {
      ...n,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });

  const viewState: ViewState =
    loading ? "loading" :
    nodes.length === 0 ? "empty" :
    "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="Interaction Maps"
      emptyTitle="No Graph Data"
      emptyDescription="Run a query to populate the interaction graph."
      onRetry={refetch}
    >
    <div
      className="flex-1 overflow-y-auto"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-[1100px] mx-auto px-6 py-5">
        <div className="mb-6 flex justify-between items-center">
          <div>
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">
              Interaction Maps
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Live Topological Pathways generated via OpenViking NetworkX Graph
              States
            </p>
          </div>
          <button
            onClick={refetch}
            className="glass-button flex items-center gap-2 px-4 py-2 text-sm"
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />{" "}
            Resample Network
          </button>
        </div>

        <div className="card overflow-hidden h-[600px] relative flex items-center justify-center bg-black/20">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,var(--primary-glow)_0%,transparent_70%)] opacity-10"></div>

          {nodes.length === 0 && !loading ? (
            <div className="text-center z-10 flex flex-col items-center gap-3">
              <Link2 size={40} className="text-[var(--text-muted)]/50" />
              <div className="text-sm font-semibold text-[var(--text-primary)]">
                No Heterogeneous Nodes Present
              </div>
              <p className="text-xs text-[var(--text-muted)] max-w-sm">
                Execute Disease Intelligence or Autoresearch queries to
                dynamically populate the underlying Python database graph.
              </p>
            </div>
          ) : (
            <svg
              width="700"
              height="600"
              className="absolute z-10 drop-shadow-2xl"
            >
              {edges.map((e, i) => {
                const src = positionedNodes.find((n) => n.id === e.source);
                const dst = positionedNodes.find((n) => n.id === e.target);
                if (!src || !dst) return null;
                return (
                  <line
                    key={i}
                    x1={src.x}
                    y1={src.y}
                    x2={dst.x}
                    y2={dst.y}
                    stroke="var(--accent)"
                    strokeWidth="1.5"
                    strokeOpacity="0.3"
                  />
                );
              })}
              {positionedNodes.map((n, i) => (
                <g
                  key={i}
                  transform={`translate(${n.x},${n.y})`}
                  className="cursor-pointer hover:scale-125 transition-transform duration-300"
                >
                  <circle
                    r="14"
                    fill="var(--surface)"
                    stroke="var(--accent)"
                    strokeWidth="2"
                    strokeOpacity="0.8"
                  />
                  <circle
                    r="6"
                    fill="var(--accent)"
                    className="animate-pulse opacity-50"
                  />
                  <text
                    y="-22"
                    textAnchor="middle"
                    fill="var(--text-primary)"
                    fontSize="11"
                    className="drop-shadow-md font-mono tracking-wider"
                  >
                    {n.id.includes(":")
                      ? n.id.split(":")[1].substring(0, 8)
                      : n.id.substring(0, 8)}
                  </text>
                  <text
                    y="22"
                    textAnchor="middle"
                    fill="var(--text-muted)"
                    fontSize="9"
                  >
                    {n.type || "ENTITY"}
                  </text>
                </g>
              ))}
              {/* Central Hub visualizer anchor */}
              {nodes.length > 0 && (
                <g transform={`translate(${centerX},${centerY})`}>
                  <circle
                    r="25"
                    fill="none"
                    stroke="var(--border)"
                    strokeWidth="1"
                    strokeDasharray="4 4"
                    className="animate-[spin_10s_linear_infinite]"
                  />
                  <Sparkles
                    size={20}
                    className="text-amber-500 absolute -translate-x-1/2 -translate-y-1/2"
                  />
                </g>
              )}
            </svg>
          )}
        </div>
      </div>
    </div>
    </StateWrapper>
  );
}
