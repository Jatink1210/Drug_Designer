import { useEffect, useMemo, useState } from "react";
import {
  CheckSquare,
  Circle,
  Dna,
  ExternalLink,
  FlaskConical,
  GitCompareArrows,
  Loader2,
  Microscope,
  Network,
  Search,
  Target,
  X,
} from "lucide-react";

import ForceGraph from "@/components/ui/ForceGraph";
import { useToast } from "@/lib/ToastContext";
import {
  entityDetailAPI,
  graphNeighborhoodAPI,
  targetCompareAPI,
  type CockpitAnalysisResult,
  type EntityDetail,
  type GraphEdge,
  type GraphNode,
} from "@/lib/api";
import type {
  CockpitEntityType,
  SharedEntitySchema,
  SharedHandoffPayload,
  SharedProvenancePayload,
} from "@/lib/canonicalProduct";

type CategoryData = CockpitAnalysisResult["categories"][number];

interface CockpitEntityExplorerProps {
  query: string;
  runId: string;
  categories: CategoryData[];
  graph: CockpitAnalysisResult["graph"];
  onNavigateWithPayload: (route: string, payload: SharedHandoffPayload) => void;
}

interface SelectedEntityItem {
  key: string;
  category: string;
  entity: SharedEntitySchema;
  provenance: SharedProvenancePayload;
  row: Record<string, unknown>;
}

const TAB_ORDER = [
  "proteins",
  "genes",
  "drugs",
  "diseases",
  "publications",
  "pathways",
  "interactions",
  "compounds",
  "clinical_trials",
  "variants",
] as const;

const CATEGORY_LABELS: Record<string, string> = {
  proteins: "Proteins",
  genes: "Genes",
  drugs: "Drugs",
  diseases: "Diseases",
  publications: "Publications",
  pathways: "Pathways",
  interactions: "Interactions",
  compounds: "Compounds",
  clinical_trials: "Clinical Trials",
  variants: "Variants",
};

const CATEGORY_ENTITY_TYPE: Record<string, CockpitEntityType> = {
  proteins: "protein",
  genes: "gene",
  drugs: "drug",
  diseases: "disease",
  publications: "publication",
  pathways: "pathway",
  interactions: "target",
  compounds: "compound",
  clinical_trials: "clinical_trial",
  variants: "variant",
};

const PREFERRED_COLUMNS: Record<string, string[]> = {
  proteins: ["symbol", "name", "protein_name", "uniprot_id", "score", "confidence", "source"],
  genes: ["symbol", "gene", "name", "ensembl_id", "score", "confidence", "source"],
  drugs: ["drug_name", "name", "drugbank_id", "chembl_id", "score", "confidence", "source"],
  diseases: ["disease_name", "name", "mondo_id", "mesh_id", "score", "confidence", "source"],
  publications: ["title", "year", "journal", "pmid", "doi", "source"],
  pathways: ["pathway_name", "name", "pathway_id", "source_db", "score", "confidence"],
  interactions: ["source", "target", "type", "confidence", "evidence_count", "source_db"],
  compounds: ["compound_name", "name", "smiles", "chembl_id", "score", "confidence", "source"],
  clinical_trials: ["title", "nct_id", "phase", "status", "source", "confidence"],
  variants: ["variant", "gene", "clinvar_id", "score", "confidence", "source"],
};

const ID_KEYS = [
  "entity_id",
  "id",
  "uniprot_id",
  "ensembl_id",
  "drugbank_id",
  "chembl_id",
  "pathway_id",
  "pmid",
  "pubmed_id",
  "doi",
  "nct_id",
  "clinvar_id",
  "symbol",
  "gene",
  "name",
  "title",
];

const NAME_KEYS = [
  "entity_name",
  "name",
  "title",
  "drug_name",
  "disease_name",
  "pathway_name",
  "protein_name",
  "compound_name",
  "symbol",
  "gene",
  "variant",
];

function getString(row: Record<string, unknown>, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return undefined;
}

function buildEntity(category: string, row: Record<string, unknown>, index: number): SharedEntitySchema {
  const entityId = getString(row, ID_KEYS) ?? `${category}-${index + 1}`;
  const entityName = getString(row, NAME_KEYS) ?? entityId;
  const identifiers = Object.fromEntries(
    Object.entries(row)
      .filter(([key, value]) => /id$|_id$|symbol|gene|smiles|doi|pmid|nct/i.test(key) && typeof value === "string" && value.trim())
      .map(([key, value]) => [key, value as string]),
  );

  return {
    entityId,
    entityType: CATEGORY_ENTITY_TYPE[category] ?? "unknown",
    entityName,
    sourceCategory: category,
    identifiers,
    attributes: row,
  };
}

function buildProvenance(category: string, row: Record<string, unknown>, runId: string): SharedProvenancePayload {
  const sourceRecordId = getString(row, ID_KEYS);
  const confidenceValue = row.confidence ?? row.score ?? row.relevance_score;

  return {
    source: String(row.source ?? row.source_db ?? category),
    sourceRecordId,
    retrievedAt: new Date().toISOString(),
    confidence: typeof confidenceValue === "number" ? confidenceValue : null,
    contradictionState: typeof row.contradiction_state === "string" ? row.contradiction_state : null,
    evidenceCount: typeof row.evidence_count === "number" ? row.evidence_count : null,
    runId,
  };
}

function preferredColumns(category: string, rows: Array<Record<string, unknown>>, fallbackColumns: string[]): string[] {
  const firstRow = rows[0] ?? {};
  const preferred = PREFERRED_COLUMNS[category] ?? [];
  const selected = preferred.filter((column) => column in firstRow);
  const seen = new Set(selected);
  for (const column of fallbackColumns) {
    if (!seen.has(column) && !column.startsWith("_")) {
      selected.push(column);
      seen.add(column);
    }
    if (selected.length >= 7) break;
  }
  return selected;
}

function formatValue(value: unknown): string {
  if (value == null || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === "object") return JSON.stringify(value).slice(0, 120);
  return String(value);
}

function DetailList({ items, emptyLabel }: { items: Array<Record<string, unknown>>; emptyLabel: string }) {
  if (!items.length) {
    return <div className="text-[11px] italic" style={{ color: "var(--text-muted)" }}>{emptyLabel}</div>;
  }

  return (
    <div className="space-y-2">
      {items.slice(0, 10).map((item, index) => {
        const title = getString(item, ["title", "name", "drug_name", "identifier", "id"]) ?? `Item ${index + 1}`;
        const subtitle = [getString(item, ["journal", "assignee", "status", "phase"]), getString(item, ["year", "pmid", "nct_id", "source"])].filter(Boolean).join(" • ");
        const url = getString(item, ["url", "link", "source_url"]);
        return (
          <div key={`${title}-${index}`} className="rounded-lg p-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="text-[12px] font-semibold" style={{ color: "var(--text-primary)" }}>{title}</div>
                {subtitle && <div className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>{subtitle}</div>}
              </div>
              {url && (
                <a href={url} target="_blank" rel="noopener noreferrer" className="shrink-0" style={{ color: "#3b82f6" }}>
                  <ExternalLink size={12} />
                </a>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function CockpitEntityExplorer({
  query,
  runId,
  categories,
  graph,
  onNavigateWithPayload,
}: CockpitEntityExplorerProps) {
  const { addToast } = useToast();
  const orderedCategories = useMemo(() => {
    const byCategory = new Map(categories.map((item) => [item.category, item]));
    return TAB_ORDER.map((key) => byCategory.get(key)).filter(Boolean) as CategoryData[];
  }, [categories]);
  const [activeCategory, setActiveCategory] = useState<string>(orderedCategories[0]?.category ?? "");
  const [selectedItems, setSelectedItems] = useState<Record<string, SelectedEntityItem>>({});
  const [detailItem, setDetailItem] = useState<SelectedEntityItem | null>(null);
  const [detailTab, setDetailTab] = useState<"overview" | "publications" | "patents" | "citations" | "clinical_trials">("overview");
  const [detailData, setDetailData] = useState<EntityDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [compareFeature, setCompareFeature] = useState<"entity" | "structure" | "design">("entity");
  const [compareRows, setCompareRows] = useState<Array<Record<string, unknown>>>([]);
  const [compareLoading, setCompareLoading] = useState(false);
  const [miniGraph, setMiniGraph] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);

  useEffect(() => {
    if (!orderedCategories.some((item) => item.category === activeCategory)) {
      setActiveCategory(orderedCategories[0]?.category ?? "");
    }
  }, [orderedCategories, activeCategory]);

  useEffect(() => {
    if (!detailItem) {
      setDetailData(null);
      return;
    }

    let cancelled = false;
    setDetailLoading(true);
    entityDetailAPI({
      entity_id: detailItem.entity.entityId,
      entity_type: detailItem.entity.entityType,
      entity_name: detailItem.entity.entityName,
    })
      .then((response) => {
        if (!cancelled) setDetailData(response);
      })
      .catch(() => {
        if (!cancelled) {
          setDetailData(null);
          addToast({
            type: "warning",
            title: "Entity detail unavailable",
            message: `Could not load live detail for ${detailItem.entity.entityName}.`,
          });
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [detailItem, addToast]);

  const activeData = orderedCategories.find((item) => item.category === activeCategory) ?? orderedCategories[0];
  const tableColumns = useMemo(() => {
    if (!activeData) return [];
    return preferredColumns(activeData.category, activeData.rows, activeData.columns.length > 0 ? activeData.columns : Object.keys(activeData.rows[0] ?? {}));
  }, [activeData]);

  const graphNodes = useMemo<GraphNode[]>(() => {
    return (graph.nodes ?? []).map((node) => ({
      id: String((node as Record<string, unknown>).id ?? ""),
      label: String((node as Record<string, unknown>).label ?? (node as Record<string, unknown>).id ?? ""),
      type: String((node as Record<string, unknown>).type ?? "unknown"),
      properties: (node as Record<string, unknown>).properties as Record<string, unknown> | undefined,
    }));
  }, [graph.nodes]);

  const graphEdges = useMemo<GraphEdge[]>(() => {
    return (graph.edges ?? []).map((edge) => ({
      source: String((edge as Record<string, unknown>).source ?? ""),
      target: String((edge as Record<string, unknown>).target ?? ""),
      label: String((edge as Record<string, unknown>).label ?? (edge as Record<string, unknown>).type ?? "related_to"),
      weight: Number((edge as Record<string, unknown>).weight ?? 1),
      type: typeof (edge as Record<string, unknown>).type === "string" ? String((edge as Record<string, unknown>).type) : undefined,
    }));
  }, [graph.edges]);

  const selectedEntityList = Object.values(selectedItems);

  const openEntity = (category: string, row: Record<string, unknown>, index: number) => {
    const entity = buildEntity(category, row, index);
    const provenance = buildProvenance(category, row, runId);
    setDetailTab("overview");
    setDetailItem({ key: `${category}:${entity.entityId}:${entity.entityName}`, category, entity, provenance, row });
  };

  const toggleSelection = (category: string, row: Record<string, unknown>, index: number) => {
    const entity = buildEntity(category, row, index);
    const provenance = buildProvenance(category, row, runId);
    const key = `${category}:${entity.entityId}:${entity.entityName}`;
    setSelectedItems((prev) => {
      if (prev[key]) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: { key, category, entity, provenance, row } };
    });
  };

  const navigateForEntities = (route: string, action: SharedHandoffPayload["action"], entities: SelectedEntityItem[]) => {
    const payload: SharedHandoffPayload = {
      version: "phase0.v1",
      sourceModule: "cockpit",
      action,
      targetRoute: route,
      query,
      createdAt: new Date().toISOString(),
      runId,
      entities: entities.map((item) => item.entity),
      provenance: entities.map((item) => item.provenance),
      metadata: {
        categories: entities.map((item) => item.category),
      },
    };

    onNavigateWithPayload(route, payload);
  };

  const runSimilarityCompare = async () => {
    if (selectedEntityList.length < 2) {
      addToast({ type: "info", title: "Select at least two entities", message: "Choose two or more rows before running compare." });
      return;
    }

    setCompareLoading(true);
    try {
      const targetLike = selectedEntityList.every((item) => ["gene", "protein", "target"].includes(item.entity.entityType));
      if (targetLike) {
        const symbols = selectedEntityList.map((item) => item.entity.identifiers?.symbol ?? item.entity.identifiers?.gene ?? item.entity.entityName);
        const response = await targetCompareAPI(symbols);
        const comparison = Array.isArray(response.comparison) ? response.comparison : [];
        setCompareRows(comparison);
      } else {
        const localCompare = selectedEntityList.map((item) => ({
          entity_name: item.entity.entityName,
          entity_type: item.entity.entityType,
          source: item.provenance.source,
          confidence: item.provenance.confidence,
        }));
        setCompareRows(localCompare);
        addToast({
          type: "info",
          title: "Local compare fallback",
          message: "Backend compare is target-specific. Showing side-by-side compare for the selected entities.",
        });
      }
    } catch {
      addToast({ type: "error", title: "Compare failed", message: "Could not compare the selected entities." });
    } finally {
      setCompareLoading(false);
    }
  };

  const runConnectivityCheck = async () => {
    if (!selectedEntityList.length) {
      addToast({ type: "info", title: "No entities selected", message: "Select entities first to build a mini graph." });
      return;
    }

    setGraphLoading(true);
    try {
      const selectedIds = new Set(selectedEntityList.map((item) => item.entity.entityId.toLowerCase()));
      const selectedNames = new Set(selectedEntityList.map((item) => item.entity.entityName.toLowerCase()));
      const localNodes = graphNodes.filter((node) => selectedIds.has(node.id.toLowerCase()) || selectedNames.has(node.label.toLowerCase()));
      const localNodeIds = new Set(localNodes.map((node) => node.id));
      const localEdges = graphEdges.filter((edge) => localNodeIds.has(edge.source) || localNodeIds.has(edge.target));

      if (localNodes.length > 0 && localEdges.length > 0) {
        setMiniGraph({ nodes: localNodes, edges: localEdges });
        return;
      }

      const neighborhood = await graphNeighborhoodAPI(selectedEntityList[0].entity.entityId, 1) as Record<string, unknown>;
      const remoteNodes = (Array.isArray(neighborhood.nodes) ? neighborhood.nodes : Array.isArray((neighborhood.graph as Record<string, unknown> | undefined)?.nodes) ? ((neighborhood.graph as Record<string, unknown>).nodes as unknown[]) : []) as Array<Record<string, unknown>>;
      const remoteEdges = (Array.isArray(neighborhood.edges) ? neighborhood.edges : Array.isArray((neighborhood.graph as Record<string, unknown> | undefined)?.edges) ? ((neighborhood.graph as Record<string, unknown>).edges as unknown[]) : []) as Array<Record<string, unknown>>;

      setMiniGraph({
        nodes: remoteNodes.map((node) => ({
          id: String(node.id ?? ""),
          label: String(node.label ?? node.id ?? ""),
          type: String(node.type ?? "unknown"),
        })),
        edges: remoteEdges.map((edge) => ({
          source: String(edge.source ?? ""),
          target: String(edge.target ?? ""),
          label: String(edge.label ?? edge.type ?? "related_to"),
          weight: Number(edge.weight ?? 1),
          type: typeof edge.type === "string" ? String(edge.type) : undefined,
        })),
      });
    } catch {
      addToast({ type: "error", title: "Connectivity check failed", message: "Could not build a mini graph for the selected entities." });
    } finally {
      setGraphLoading(false);
    }
  };

  const applyCompareFeature = () => {
    if (selectedEntityList.length < 1) {
      addToast({ type: "info", title: "No entities selected", message: "Select entities first before running a downstream workflow." });
      return;
    }

    if (compareFeature === "entity") {
      navigateForEntities("/entity-intelligence", "run_entity_intelligence", selectedEntityList);
      return;
    }
    if (compareFeature === "structure") {
      navigateForEntities("/structure", "open_in_structure", selectedEntityList);
      return;
    }
    navigateForEntities("/design", "open_in_design", selectedEntityList);
  };

  return (
    <div className="mt-6 rounded-xl" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
      <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2 flex-wrap">
          {orderedCategories.map((category) => {
            const active = category.category === activeCategory;
            return (
              <button
                key={category.category}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-semibold"
                style={{
                  background: active ? "var(--accent)" : "var(--bg-app)",
                  color: active ? "#fff" : "var(--text-primary)",
                  border: active ? "1px solid transparent" : "1px solid var(--border)",
                }}
                onClick={() => setActiveCategory(category.category)}
              >
                <span>{CATEGORY_LABELS[category.category] ?? category.category}</span>
                <span className="px-1.5 py-0.5 rounded-full text-[10px]" style={{ background: active ? "rgba(255,255,255,0.18)" : "var(--bg-elevated)" }}>{category.count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {activeData ? (
        <>
          <div className="px-4 py-3 flex items-center justify-between gap-3 flex-wrap" style={{ borderBottom: "1px solid var(--border)" }}>
            <div>
              <div className="text-[12px] font-semibold" style={{ color: "var(--text-primary)" }}>
                {CATEGORY_LABELS[activeData.category] ?? activeData.category} Table
              </div>
              <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                Click a row for detail. Select rows to compare, graph, or hand off.
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button onClick={runSimilarityCompare} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold" style={{ background: "#6366f112", color: "#6366f1", border: "1px solid #6366f122" }}>
                {compareLoading ? <Loader2 size={11} className="animate-spin" /> : <GitCompareArrows size={11} />} Find Similarities
              </button>
              <button onClick={runConnectivityCheck} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold" style={{ background: "#0891b212", color: "#0891b2", border: "1px solid #0891b222" }}>
                {graphLoading ? <Loader2 size={11} className="animate-spin" /> : <Network size={11} />} See How Connected
              </button>
              <div className="flex items-center gap-2">
                <select value={compareFeature} onChange={(event) => setCompareFeature(event.target.value as "entity" | "structure" | "design")} className="text-[10px] py-1.5 px-2 rounded" style={{ background: "var(--bg-app)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                  <option value="entity">Run Entity Intelligence</option>
                  <option value="structure">Open Structure</option>
                  <option value="design">Open Design Studio</option>
                </select>
                <button onClick={applyCompareFeature} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold" style={{ background: "var(--accent)", color: "#fff", border: "none" }}>
                  <Target size={11} /> Run Feature
                </button>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-[11px]" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "var(--bg-app)" }}>
                  <th className="px-3 py-2 text-left" style={{ borderBottom: "1px solid var(--border)", width: 40 }}>
                    <CheckSquare size={12} style={{ color: "var(--text-muted)" }} />
                  </th>
                  <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border)", width: 32 }}>#</th>
                  {tableColumns.map((column) => (
                    <th key={column} className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
                      {column.replace(/_/g, " ")}
                    </th>
                  ))}
                  <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border)", width: 110 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {activeData.rows.slice(0, 40).map((row, index) => {
                  const entity = buildEntity(activeData.category, row, index);
                  const selectionKey = `${activeData.category}:${entity.entityId}:${entity.entityName}`;
                  const checked = Boolean(selectedItems[selectionKey]);
                  return (
                    <tr key={selectionKey} className="cursor-pointer hover:bg-[var(--bg-app)]" style={{ borderBottom: "1px solid var(--border)" }} onClick={() => openEntity(activeData.category, row, index)}>
                      <td className="px-3 py-2" onClick={(event) => event.stopPropagation()}>
                        <button onClick={() => toggleSelection(activeData.category, row, index)}>
                          {checked ? <CheckSquare size={14} style={{ color: "var(--accent)" }} /> : <Circle size={14} style={{ color: "var(--text-muted)" }} />}
                        </button>
                      </td>
                      <td className="px-3 py-2 text-[10px]" style={{ color: "var(--text-muted)" }}>{index + 1}</td>
                      {tableColumns.map((column) => (
                        <td key={column} className="px-3 py-2" style={{ color: "var(--text-primary)", maxWidth: 220 }}>
                          <span className="break-words">{formatValue(row[column])}</span>
                        </td>
                      ))}
                      <td className="px-3 py-2" onClick={(event) => event.stopPropagation()}>
                        <button className="text-[10px] px-2 py-1 rounded font-semibold" style={{ background: "var(--bg-app)", color: "var(--accent)", border: "1px solid var(--border)" }} onClick={() => openEntity(activeData.category, row, index)}>
                          Details
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {selectedEntityList.length > 0 && (
            <div className="px-4 py-4 space-y-4" style={{ borderTop: "1px solid var(--border)" }}>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                  Compare Tray ({selectedEntityList.length})
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedEntityList.map((item) => (
                    <span key={item.key} className="px-2.5 py-1 rounded-full text-[10px] font-semibold" style={{ background: "var(--accent)12", color: "var(--accent)", border: "1px solid var(--accent)22" }}>
                      {item.entity.entityName}
                    </span>
                  ))}
                </div>
              </div>

              {compareRows.length > 0 && (
                <div className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--bg-app)" }}>
                  <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
                    Similarity / Side-by-side Result
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-[11px]" style={{ borderCollapse: "collapse" }}>
                      <thead>
                        <tr style={{ background: "var(--bg-surface)" }}>
                          {Object.keys(compareRows[0]).slice(0, 6).map((column) => (
                            <th key={column} className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
                              {column.replace(/_/g, " ")}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {compareRows.map((row, index) => (
                          <tr key={`compare-${index}`} style={{ borderBottom: "1px solid var(--border)" }}>
                            {Object.keys(compareRows[0]).slice(0, 6).map((column) => (
                              <td key={column} className="px-3 py-2" style={{ color: "var(--text-primary)" }}>{formatValue(row[column])}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {miniGraph && miniGraph.nodes.length > 0 && (
                <div className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--bg-app)" }}>
                  <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
                    Mini Connectivity Graph
                  </div>
                  <div className="p-3">
                    <ForceGraph nodes={miniGraph.nodes} edges={miniGraph.edges} height={220} />
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      ) : (
        <div className="p-4 text-[11px] italic" style={{ color: "var(--text-muted)" }}>No entity tables available for this analysis.</div>
      )}

      {detailItem && (
        <div className="fixed inset-0 z-50 flex justify-end" style={{ background: "rgba(15, 23, 42, 0.28)" }}>
          <div className="h-full w-full max-w-[460px]" style={{ background: "var(--bg-elevated)", borderLeft: "1px solid var(--border)", boxShadow: "-12px 0 32px rgba(15, 23, 42, 0.16)" }}>
            <div className="flex items-start justify-between gap-3 px-5 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                  {CATEGORY_LABELS[detailItem.category] ?? detailItem.category}
                </div>
                <div className="text-[16px] font-semibold mt-1" style={{ color: "var(--text-primary)" }}>{detailItem.entity.entityName}</div>
                <div className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>{detailItem.entity.entityId}</div>
              </div>
              <button onClick={() => setDetailItem(null)} className="rounded-full p-2" style={{ background: "var(--bg-app)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                <X size={14} />
              </button>
            </div>

            <div className="px-5 py-3 flex items-center gap-2 flex-wrap" style={{ borderBottom: "1px solid var(--border)" }}>
              {[
                { key: "overview", label: "Overview" },
                { key: "publications", label: "Publications" },
                { key: "patents", label: "Patents" },
                { key: "citations", label: "Citations" },
                { key: "clinical_trials", label: "Clinical Trials" },
              ].map((tab) => {
                const active = tab.key === detailTab;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setDetailTab(tab.key as typeof detailTab)}
                    className="px-2.5 py-1 rounded-full text-[10px] font-semibold"
                    style={{
                      background: active ? "var(--accent)" : "var(--bg-app)",
                      color: active ? "#fff" : "var(--text-primary)",
                      border: active ? "1px solid transparent" : "1px solid var(--border)",
                    }}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>

            <div className="px-5 py-4 overflow-y-auto h-[calc(100%-195px)]">
              <div className="flex items-center gap-2 flex-wrap mb-4">
                <button onClick={() => navigateForEntities("/structure", "open_in_structure", [detailItem])} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold" style={{ background: "#7c3aed12", color: "#7c3aed", border: "1px solid #7c3aed22" }}>
                  <Dna size={11} /> Open in Structure
                </button>
                <button onClick={() => navigateForEntities("/design", "open_in_design", [detailItem])} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold" style={{ background: "#d9770612", color: "#d97706", border: "1px solid #d9770622" }}>
                  <FlaskConical size={11} /> Open in Design Studio
                </button>
                <button onClick={() => navigateForEntities("/entity-intelligence", "run_entity_intelligence", [detailItem])} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold" style={{ background: "#10b98112", color: "#10b981", border: "1px solid #10b98122" }}>
                  <Target size={11} /> Run Entity Intelligence
                </button>
                <button onClick={() => toggleSelection(detailItem.category, detailItem.row, 0)} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold" style={{ background: "#6366f112", color: "#6366f1", border: "1px solid #6366f122" }}>
                  <GitCompareArrows size={11} /> Compare
                </button>
                <button onClick={() => navigateForEntities("/dossiers", "append_to_dossier", [detailItem])} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold" style={{ background: "#ec489912", color: "#ec4899", border: "1px solid #ec489922" }}>
                  <Microscope size={11} /> Append to Dossier
                </button>
                <button onClick={() => navigateForEntities("/labs", "open_in_labs", [detailItem])} className="flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-semibold" style={{ background: "#0891b212", color: "#0891b2", border: "1px solid #0891b222" }}>
                  <Network size={11} /> Send to Lab
                </button>
              </div>

              {detailLoading ? (
                <div className="flex items-center gap-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
                  <Loader2 size={12} className="animate-spin" /> Loading live entity detail…
                </div>
              ) : detailTab === "overview" ? (
                <div className="space-y-4">
                  <div className="rounded-lg p-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                    <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                      Description
                    </div>
                    <div className="text-[12px] leading-6" style={{ color: "var(--text-primary)" }}>
                      {detailData?.description || "No live description returned for this entity yet."}
                    </div>
                  </div>

                  <div className="rounded-lg p-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                    <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                      Identifiers & Provenance
                    </div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-[11px]">
                      {Object.entries(detailItem.entity.identifiers ?? {}).slice(0, 8).map(([key, value]) => (
                        <div key={key}>
                          <div style={{ color: "var(--text-muted)" }}>{key.replace(/_/g, " ")}</div>
                          <div style={{ color: "var(--text-primary)" }}>{value}</div>
                        </div>
                      ))}
                      <div>
                        <div style={{ color: "var(--text-muted)" }}>Source</div>
                        <div style={{ color: "var(--text-primary)" }}>{detailItem.provenance.source}</div>
                      </div>
                      <div>
                        <div style={{ color: "var(--text-muted)" }}>Run</div>
                        <div style={{ color: "var(--text-primary)" }}>{detailItem.provenance.runId || "-"}</div>
                      </div>
                    </div>
                  </div>

                  {detailData?.chembl_data?.length ? (
                    <div className="rounded-lg p-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                      <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                        ChEMBL / Molecule Data
                      </div>
                      <DetailList items={detailData.chembl_data} emptyLabel="No chemistry detail." />
                    </div>
                  ) : null}
                </div>
              ) : detailTab === "publications" ? (
                <DetailList items={detailData?.publications ?? []} emptyLabel="No publications available." />
              ) : detailTab === "patents" ? (
                <DetailList items={detailData?.patents ?? []} emptyLabel="No patents available." />
              ) : detailTab === "citations" ? (
                <DetailList items={detailData?.publications ?? []} emptyLabel="No citations available." />
              ) : (
                <DetailList items={detailData?.clinical_trials ?? []} emptyLabel="No clinical trials available." />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}