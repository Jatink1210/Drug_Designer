import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  Loader2,
  Network,
  RefreshCw,
  Search,
} from "lucide-react";
import {
  graphBuildAPI,
  graphStatsAPI,
  type EntityIntelligenceGraphEdge,
  type GraphBuildResult,
  type GraphNode,
} from "@/lib/api";
import EntityGraphWorkbench from "@/components/entity/EntityGraphWorkbench";
import EntityDetailDrawer from "@/components/entity/EntityDetailDrawer";
import { persistCockpitHandoff, readCockpitHandoff, type SharedHandoffPayload } from "@/lib/canonicalProduct";
import { useSetPageConfidence } from "@/lib/PageConfidenceContext";

type GraphMode = "full" | "ppi" | "disease" | "target" | "contradictions";

function buildGraphHandoff(route: string, action: SharedHandoffPayload["action"], query: string, entities: Array<{ id: string; label: string; type: string; properties?: Record<string, unknown> }>): SharedHandoffPayload {
  return {
    version: "phase0.v1",
    sourceModule: "knowledge-graph",
    action,
    targetRoute: route,
    query,
    createdAt: new Date().toISOString(),
    entities: entities.map((entity) => ({
      entityId: entity.id,
      entityType: entity.type as any,
      entityName: entity.label,
      identifiers: (entity.properties?.identifiers as Record<string, string> | undefined) || {},
      attributes: entity.properties || {},
      sourceCategory: "knowledge-graph",
    })),
    provenance: entities.map(() => ({
      source: "knowledge-graph",
      retrievedAt: new Date().toISOString(),
    })),
    metadata: {
      mode: "knowledge-graph",
    },
  };
}

function oneHopNeighborhood(edges: EntityIntelligenceGraphEdge[], seedIds: string[]): Set<string> {
  const ids = new Set(seedIds);
  for (const edge of edges) {
    if (ids.has(edge.source) || ids.has(edge.target)) {
      ids.add(edge.source);
      ids.add(edge.target);
    }
  }
  return ids;
}

function contradictionState(edge: EntityIntelligenceGraphEdge): string {
  return String(edge.properties?.contradiction_state || "none").toLowerCase();
}

export default function KGPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") || "";
  const initialMode = (searchParams.get("mode") as GraphMode | null) || "full";

  const [query, setQuery] = useState(initialQuery);
  const [activeMode, setActiveMode] = useState<GraphMode>(initialMode);
  const [graphResult, setGraphResult] = useState<GraphBuildResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [degradedSources, setDegradedSources] = useState<string[]>([]);
  const [focusTargetId, setFocusTargetId] = useState<string>("");
  const [selectedEdge, setSelectedEdge] = useState<EntityIntelligenceGraphEdge | null>(null);
  const [handoffSummary, setHandoffSummary] = useState<{ query: string; runId?: string; entityCount: number } | null>(null);
  const [drawerEntity, setDrawerEntity] = useState<{ id: string; type: string; name: string } | null>(null);
  const searchTriggered = useRef(false);

  const statsQ = useQuery({ queryKey: ["graphStats"], queryFn: graphStatsAPI });
  const setConfidence = useSetPageConfidence();

  const handleSearch = useCallback(async (term?: string) => {
    const nextQuery = (term || query).trim();
    if (!nextQuery) return;
    setLoading(true);
    setError(null);
    setSelectedEdge(null);
    try {
      const result = await graphBuildAPI(nextQuery, 1200);
      setGraphResult(result);
      setDegradedSources(result.degraded_sources || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to build graph");
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    if (initialQuery && !searchTriggered.current) {
      searchTriggered.current = true;
      void handleSearch(initialQuery);
    }
  }, [handleSearch, initialQuery]);

  useEffect(() => {
    const payload = readCockpitHandoff();
    if (!payload || payload.targetRoute !== "/graph") return;
    const seededQuery = initialQuery || payload.query || payload.entities[0]?.entityName || "";
    if (!seededQuery) return;
    setHandoffSummary({ query: seededQuery, runId: payload.runId, entityCount: payload.entities.length });
    if (!initialQuery && !searchTriggered.current) {
      searchTriggered.current = true;
      setQuery(seededQuery);
      void handleSearch(seededQuery);
    }
  }, [handleSearch, initialQuery]);

  useEffect(() => {
    if (graphResult) {
      setConfidence({
        freshness: "current",
        sourceCount: Object.keys(graphResult.stats.entity_types).length,
        sourcesQueried: Object.keys(graphResult.stats.entity_types),
      });
    } else {
      setConfidence(null);
    }
    return () => setConfidence(null);
  }, [graphResult, setConfidence]);

  const rawEdges = useMemo(() => (graphResult?.edges || []) as EntityIntelligenceGraphEdge[], [graphResult]);
  const targetCandidates = useMemo(() => {
    return (graphResult?.nodes || []).filter((node) => ["gene", "protein", "target"].includes((node.type || "unknown").toLowerCase())).slice(0, 20);
  }, [graphResult]);

  useEffect(() => {
    if (!focusTargetId && targetCandidates[0]?.id) {
      setFocusTargetId(targetCandidates[0].id);
    }
  }, [focusTargetId, targetCandidates]);

  const modeView = useMemo(() => {
    if (!graphResult) {
      return { nodes: [] as GraphNode[], edges: [] as EntityIntelligenceGraphEdge[], emptyMessage: "Search to build a graph." };
    }
    const nodes = graphResult.nodes;
    const edges = rawEdges;

    if (activeMode === "full") {
      return { nodes, edges, emptyMessage: "No graph data." };
    }

    if (activeMode === "ppi") {
      const keptNodes = nodes.filter((node) => ["gene", "protein", "target"].includes((node.type || "unknown").toLowerCase()));
      const keptIds = new Set(keptNodes.map((node) => node.id));
      return {
        nodes: keptNodes,
        edges: edges.filter((edge) => keptIds.has(edge.source) && keptIds.has(edge.target)),
        emptyMessage: "No protein interaction neighborhood in current graph.",
      };
    }

    if (activeMode === "disease") {
      const diseaseIds = nodes.filter((node) => (node.type || "unknown").toLowerCase() === "disease").map((node) => node.id);
      const keptIds = oneHopNeighborhood(edges, diseaseIds);
      return {
        nodes: nodes.filter((node) => keptIds.has(node.id)),
        edges: edges.filter((edge) => keptIds.has(edge.source) && keptIds.has(edge.target)),
        emptyMessage: "No disease-centered subgraph in current graph.",
      };
    }

    if (activeMode === "target") {
      const keptIds = focusTargetId ? oneHopNeighborhood(edges, [focusTargetId]) : new Set<string>();
      return {
        nodes: nodes.filter((node) => keptIds.has(node.id)),
        edges: edges.filter((edge) => keptIds.has(edge.source) && keptIds.has(edge.target)),
        emptyMessage: "Pick a target neighborhood to inspect.",
      };
    }

    const contradictionEdges = edges.filter((edge) => contradictionState(edge) === "flagged" || contradictionState(edge) === "confirmed" || String(edge.type || "").toLowerCase() === "contradiction");
    const contradictionIds = new Set<string>();
    for (const edge of contradictionEdges) {
      contradictionIds.add(edge.source);
      contradictionIds.add(edge.target);
    }
    return {
      nodes: nodes.filter((node) => contradictionIds.has(node.id)),
      edges: contradictionEdges,
      emptyMessage: "No contradiction edges in current graph.",
    };
  }, [activeMode, focusTargetId, graphResult, rawEdges]);

  const handleAction = (action: "structure" | "design" | "prioritize", nodes: GraphNode[]) => {
    if (nodes.length === 0) return;
    if (action === "prioritize") {
      const nextTarget = nodes.find((node) => ["gene", "protein", "target"].includes((node.type || "").toLowerCase()));
      if (nextTarget) {
        setFocusTargetId(nextTarget.id);
        setActiveMode("target");
      }
      return;
    }

    const entities = nodes.map((node) => ({
      id: node.id,
      label: node.label,
      type: node.type,
      properties: node.properties,
    }));
    if (action === "structure") {
      persistCockpitHandoff(buildGraphHandoff("/structure", "open_in_structure", query, entities));
      navigate("/structure");
      return;
    }
    persistCockpitHandoff(buildGraphHandoff("/design", "open_in_design", query, entities));
    navigate("/design");
  };

  return (
    <>
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-[1560px] mx-auto px-6 py-5 space-y-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 text-[var(--accent)]"><Network size={16} /><span className="text-sm font-semibold text-[var(--text-primary)]">Knowledge Graph</span></div>
            <p className="text-xs text-[var(--text-muted)] mt-1">Full KG, PPI, disease subgraph, target neighborhood, contradiction overlay, edge provenance, and export.</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative min-w-[300px]">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => { if (event.key === "Enter") void handleSearch(); }}
                placeholder="Search gene, disease, drug, pathway..."
                className="w-full rounded-xl border pl-9 pr-3 py-2 text-sm"
                style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
              />
            </div>
            <button onClick={() => void handleSearch()} disabled={loading || !query.trim()} className="px-4 py-2 rounded-xl text-xs font-semibold text-white inline-flex items-center gap-2 disabled:opacity-50" style={{ background: "var(--accent)" }}>
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Network size={14} />} Build Graph
            </button>
          </div>
        </div>

        {handoffSummary && (
          <div className="rounded-2xl border px-4 py-3 text-[11px] flex items-center gap-2 flex-wrap" style={{ borderColor: "rgba(34,197,94,0.2)", background: "rgba(34,197,94,0.08)", color: "#166534" }}>
            <span className="font-semibold">Cockpit handoff</span>
            <span>{handoffSummary.query}</span>
            {handoffSummary.runId ? <span>run {handoffSummary.runId}</span> : null}
            <span>{handoffSummary.entityCount} carried entities</span>
          </div>
        )}

        {error && (
          <div className="rounded-2xl border px-4 py-3 text-sm text-red-700 inline-flex items-center gap-2" style={{ borderColor: "rgba(239,68,68,0.25)", background: "rgba(239,68,68,0.07)" }}>
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {degradedSources.length > 0 && !error && (
          <div className="rounded-2xl border px-4 py-3 text-[11px] flex items-center gap-2" style={{ borderColor: "rgba(245,158,11,0.22)", background: "rgba(245,158,11,0.08)", color: "#92400e" }}>
            <AlertTriangle size={14} /> Partial graph. Degraded sources: {degradedSources.join(", ")}
            <button onClick={() => void handleSearch()} className="ml-auto px-2 py-1 rounded-lg border text-[10px] inline-flex items-center gap-1" style={{ borderColor: "rgba(245,158,11,0.35)" }}><RefreshCw size={10} /> Retry</button>
          </div>
        )}

        {statsQ.isError && !graphResult && !error && (
          <div className="rounded-2xl border px-4 py-3 text-[11px] flex items-center gap-2" style={{ borderColor: "rgba(245,158,11,0.22)", background: "rgba(245,158,11,0.08)", color: "#92400e" }}>
            <AlertTriangle size={14} /> Graph backend stats unavailable.
            <button onClick={() => statsQ.refetch()} className="ml-auto px-2 py-1 rounded-lg border text-[10px] inline-flex items-center gap-1" style={{ borderColor: "rgba(245,158,11,0.35)" }}><RefreshCw size={10} /> Retry</button>
          </div>
        )}

        {!graphResult && !loading && (
          <div className="rounded-3xl border px-8 py-12 text-center" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
            <div className="w-24 h-24 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: "linear-gradient(135deg, rgba(79,70,229,0.12), rgba(37,99,235,0.14))" }}>
              <Network size={40} className="text-indigo-500" />
            </div>
            <div className="text-lg font-semibold text-[var(--text-primary)]">Connected biomedical graph</div>
            <div className="text-sm text-[var(--text-muted)] mt-2">Search to build a graph, then switch between full KG, PPI, disease, target-neighborhood, and contradiction views.</div>
            {statsQ.data ? <div className="text-[11px] text-[var(--text-muted)] mt-4">Stored KG: {statsQ.data.total_nodes.toLocaleString()} nodes · {statsQ.data.total_edges.toLocaleString()} edges</div> : null}
          </div>
        )}

        {graphResult && (
          <>
            <div className="flex items-center gap-2 flex-wrap">
              {(["full", "ppi", "disease", "target", "contradictions"] as GraphMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setActiveMode(mode)}
                  className="px-3 py-2 rounded-xl border text-xs font-semibold"
                  style={{
                    borderColor: activeMode === mode ? "rgba(79,70,229,0.35)" : "var(--border)",
                    background: activeMode === mode ? "rgba(79,70,229,0.08)" : "transparent",
                    color: activeMode === mode ? "#4338ca" : "var(--text-secondary)",
                  }}
                >
                  {mode === "full" ? "Full KG" : mode === "ppi" ? "PPI Mode" : mode === "disease" ? "Disease Subgraph" : mode === "target" ? "Target Neighborhood" : "Contradiction Overlay"}
                </button>
              ))}
              {activeMode === "target" && (
                <select value={focusTargetId} onChange={(event) => setFocusTargetId(event.target.value)} className="px-3 py-2 rounded-xl border text-xs" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                  {targetCandidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.label}</option>)}
                </select>
              )}
              <div className="ml-auto flex items-center gap-2 flex-wrap text-[11px] text-[var(--text-muted)]">
                <span>{modeView.nodes.length} nodes</span>
                <span>{modeView.edges.length} edges</span>
                <span>{graphResult.stats.latency_ms} ms</span>
              </div>
            </div>

            <EntityGraphWorkbench
              title="Knowledge Graph Workbench"
              nodes={modeView.nodes}
              edges={modeView.edges}
              emptyMessage={modeView.emptyMessage}
              onEdgeSelect={(edge) => setSelectedEdge(edge)}
              onAction={handleAction}
            />

            {selectedEdge && (
              <div className="rounded-2xl border p-4 space-y-2" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                <div className="text-sm font-semibold text-[var(--text-primary)]">Edge Provenance</div>
                <div className="text-xs text-[var(--text-secondary)]">{selectedEdge.source} → {selectedEdge.target} · {selectedEdge.label || selectedEdge.type || "RELATED"}</div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 text-[11px]">
                  <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                    <div className="font-semibold text-[var(--text-primary)]">Evidence sentence</div>
                    <div className="text-[var(--text-muted)] mt-1">{String(selectedEdge.properties?.evidence_sentence || "No sentence-level evidence attached.")}</div>
                  </div>
                  <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                    <div className="font-semibold text-[var(--text-primary)]">Source and citation</div>
                    <div className="text-[var(--text-muted)] mt-1">DB: {String(selectedEdge.properties?.source_name || "unknown")}</div>
                    <div className="text-[var(--text-muted)] mt-1">Citation: {String(selectedEdge.properties?.citation || "Not provided")}</div>
                  </div>
                  <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                    <div className="font-semibold text-[var(--text-primary)]">Confidence and contradiction</div>
                    <div className="text-[var(--text-muted)] mt-1">Confidence: {typeof selectedEdge.properties?.confidence === "number" ? selectedEdge.properties.confidence.toFixed(2) : "n/a"}</div>
                    <div className="text-[var(--text-muted)] mt-1">Contradiction: {String(selectedEdge.properties?.contradiction_state || "none")}</div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
    {drawerEntity && (
      <EntityDetailDrawer
        entityId={drawerEntity.id}
        entityType={drawerEntity.type}
        entityName={drawerEntity.name}
        onClose={() => setDrawerEntity(null)}
      />
    )}
    </>
  );
}
