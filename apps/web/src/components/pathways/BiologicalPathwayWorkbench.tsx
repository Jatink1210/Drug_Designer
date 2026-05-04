import { useMemo, useState } from "react";

interface PathwayEntity {
  entityId: string;
  entityType: string;
  entityName: string;
  identifiers?: Record<string, string>;
  attributes?: Record<string, unknown>;
  sourceCategory?: string;
}

interface PathwaySnapshot {
  id: string;
  name: string;
  source: string;
  genes: string[];
  pathwayType: string;
}

interface PathwayDiseaseContext {
  rewired_genes?: string[];
  therapeutic_targets?: string[];
  context?: Record<string, unknown>;
}

interface GraphNode {
  id: string;
  label: string;
  type: "pathway" | "gene" | "protein" | "disease" | "compound";
  x: number;
  y: number;
  width?: number;
  height?: number;
  fill: string;
  outline?: string;
  meta: Record<string, unknown> & {
    source_db?: string;
    source_url?: string;
    source?: string;
    rewired?: boolean;
    therapeutic?: boolean;
  };
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  sourceName: string;
  evidenceSentence: string;
  diseaseContext: string;
  relation: string;
  line: string;
  lineWidth: number;
}

interface BiologicalPathwayWorkbenchProps {
  primary: PathwaySnapshot | null;
  secondary?: PathwaySnapshot | null;
  carriedEntities?: PathwayEntity[];
  diseaseContext?: PathwayDiseaseContext | null;
  query?: string;
}

const TYPE_STYLE = {
  pathway: { fill: "#e0e7ff", outline: "#4338ca" },
  gene: { fill: "#f5f3ff", outline: "#7c3aed" },
  protein: { fill: "#eef2ff", outline: "#4f46e5" },
  disease: { fill: "#fee2e2", outline: "#dc2626" },
  compound: { fill: "#ffedd5", outline: "#d97706" },
} as const;

/* Source database color coding */
const SOURCE_COLORS: Record<string, string> = {
  kegg: "#059669",      // emerald
  reactome: "#4338ca",  // indigo
  wikipathways: "#7c3aed", // purple
  string: "#3b82f6",
  intact: "#6366f1",
  default: "#94a3b8",
};

function polar(cx: number, cy: number, radius: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) };
}

function inferPathwayType(name: string): string {
  const lower = name.toLowerCase();
  if (/(metabolic|biosynthesis|metabolism|catabolism)/.test(lower)) return "metabolic";
  if (/(signal|signaling|kinase|cascade|receptor)/.test(lower)) return "signaling";
  if (/(disease|cancer|infection|syndrome|disorder)/.test(lower)) return "disease";
  if (/(transcription|regulatory|epigen|rna|dna|gene expression)/.test(lower)) return "gene_regulatory";
  return "general";
}

function linePath(source: GraphNode, target: GraphNode): string {
  const midX = (source.x + target.x) / 2;
  const bend = source.type === "pathway" || target.type === "pathway" ? 0 : source.y < target.y ? -24 : 24;
  return `M ${source.x} ${source.y} Q ${midX} ${(source.y + target.y) / 2 + bend} ${target.x} ${target.y}`;
}

export default function BiologicalPathwayWorkbench({
  primary,
  secondary,
  carriedEntities = [],
  diseaseContext,
  query = "",
}: BiologicalPathwayWorkbenchProps) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  const model = useMemo(() => {
    if (!primary) {
      return { nodes: [] as GraphNode[], edges: [] as GraphEdge[], typeLabel: "general" };
    }

    const nodes: GraphNode[] = [];
    const edges: GraphEdge[] = [];
    const typeLabel = primary.pathwayType || inferPathwayType(primary.name);
    const center = { x: secondary ? 340 : 500, y: 220 };
    const comparisonCenter = { x: 700, y: 220 };
    const compounds = carriedEntities.filter((entity) => ["drug", "molecule", "compound"].includes(entity.entityType)).slice(0, 6);
    const diseases = carriedEntities.filter((entity) => entity.entityType === "disease").slice(0, 4);
    const rewiredGenes = new Set((diseaseContext?.rewired_genes || []).map((gene) => gene.toUpperCase()));
    const therapeuticTargets = new Set((diseaseContext?.therapeutic_targets || []).map((gene) => gene.toUpperCase()));

    const primaryNode: GraphNode = {
      id: `pathway:${primary.id}`,
      label: primary.name,
      type: "pathway",
      x: center.x,
      y: center.y,
      width: 190,
      height: 76,
      fill: TYPE_STYLE.pathway.fill,
      outline: TYPE_STYLE.pathway.outline,
      meta: {
        source: primary.source,
        pathwayId: primary.id,
        pathwayType: typeLabel,
        geneCount: primary.genes.length,
      },
    };
    nodes.push(primaryNode);

    const primaryGenes = primary.genes.slice(0, 14);
    primaryGenes.forEach((gene, index) => {
      const angle = 200 + index * (140 / Math.max(primaryGenes.length, 1));
      const pos = polar(center.x, center.y + 120, 220, angle);
      const geneNode: GraphNode = {
        id: `gene:${primary.id}:${gene}`,
        label: gene,
        type: "gene",
        x: pos.x,
        y: pos.y,
        fill: rewiredGenes.has(gene.toUpperCase()) ? "#fecaca" : therapeuticTargets.has(gene.toUpperCase()) ? "#dcfce7" : TYPE_STYLE.gene.fill,
        outline: rewiredGenes.has(gene.toUpperCase()) ? "#dc2626" : therapeuticTargets.has(gene.toUpperCase()) ? "#059669" : TYPE_STYLE.gene.outline,
        meta: {
          source: primary.source,
          pathwayId: primary.id,
          shared: secondary ? secondary.genes.includes(gene) : false,
          rewired: rewiredGenes.has(gene.toUpperCase()),
          therapeutic: therapeuticTargets.has(gene.toUpperCase()),
          source_db: primary.source,
          source_url: primary.source === "Reactome" ? `https://reactome.org/content/detail/${primary.id}` : primary.source === "KEGG" ? `https://www.kegg.jp/entry/${primary.id}` : "",
        },
      };
      nodes.push(geneNode);
      edges.push({
        id: `edge:${primary.id}:${gene}`,
        source: primaryNode.id,
        target: geneNode.id,
        sourceName: primary.source,
        relation: rewiredGenes.has(gene.toUpperCase()) ? "rewired_member" : "member_gene",
        evidenceSentence: `${gene} is part of ${primary.name} in ${primary.source}.`,
        diseaseContext: rewiredGenes.has(gene.toUpperCase()) ? `Gene shows disease-context rewiring for ${query || primary.name}.` : `Canonical ${primary.source} pathway membership.`,
        line: rewiredGenes.has(gene.toUpperCase()) ? "#dc2626" : "#94a3b8",
        lineWidth: rewiredGenes.has(gene.toUpperCase()) ? 3 : 2,
      });
    });

    compounds.forEach((entity, index) => {
      const pos = polar(center.x - 210, center.y + 20, 100, -40 + index * 24);
      const compoundNode: GraphNode = {
        id: `compound:${entity.entityId}`,
        label: entity.entityName,
        type: "compound",
        x: pos.x,
        y: pos.y,
        fill: TYPE_STYLE.compound.fill,
        outline: TYPE_STYLE.compound.outline,
        meta: {
          source: entity.sourceCategory || "handoff",
          identifiers: entity.identifiers || {},
        },
      };
      nodes.push(compoundNode);
      edges.push({
        id: `edge:compound:${entity.entityId}`,
        source: compoundNode.id,
        target: primaryNode.id,
        sourceName: entity.sourceCategory || "handoff",
        relation: "compound_overlay",
        evidenceSentence: `${entity.entityName} is overlaid from carried context to inspect pathway relevance.`,
        diseaseContext: query ? `Overlay anchored on query ${query}.` : "Cross-module synthesis overlay.",
        line: "#d97706",
        lineWidth: 2,
      });
    });

    diseases.forEach((entity, index) => {
      const pos = polar(center.x + 210, center.y - 20, 110, 210 + index * 26);
      const diseaseNode: GraphNode = {
        id: `disease:${entity.entityId}`,
        label: entity.entityName,
        type: "disease",
        x: pos.x,
        y: pos.y,
        fill: TYPE_STYLE.disease.fill,
        outline: TYPE_STYLE.disease.outline,
        meta: {
          source: entity.sourceCategory || "handoff",
          identifiers: entity.identifiers || {},
        },
      };
      nodes.push(diseaseNode);
      edges.push({
        id: `edge:disease:${entity.entityId}`,
        source: diseaseNode.id,
        target: primaryNode.id,
        sourceName: entity.sourceCategory || "handoff",
        relation: "disease_context",
        evidenceSentence: `${entity.entityName} was carried into pathway synthesis for disease-context mapping.`,
        diseaseContext: query ? `Relevant to query ${query}.` : "Cross-module disease overlay.",
        line: "#dc2626",
        lineWidth: 2,
      });
    });

    if (query && diseases.length === 0) {
      const diseaseNode: GraphNode = {
        id: `disease:query:${query}`,
        label: query,
        type: "disease",
        x: center.x + 220,
        y: center.y - 80,
        fill: TYPE_STYLE.disease.fill,
        outline: TYPE_STYLE.disease.outline,
        meta: { source: "query", query },
      };
      nodes.push(diseaseNode);
      edges.push({
        id: `edge:query:${query}`,
        source: diseaseNode.id,
        target: primaryNode.id,
        sourceName: primary.source,
        relation: "query_context",
        evidenceSentence: `${query} provides disease or topic context for ${primary.name}.`,
        diseaseContext: "Topic-driven pathway synthesis.",
        line: "#dc2626",
        lineWidth: 2,
      });
    }

    if (secondary) {
      const secondaryType = secondary.pathwayType || inferPathwayType(secondary.name);
      const secondaryNode: GraphNode = {
        id: `pathway:${secondary.id}`,
        label: secondary.name,
        type: "pathway",
        x: comparisonCenter.x,
        y: comparisonCenter.y,
        width: 190,
        height: 76,
        fill: "#f3e8ff",
        outline: "#9333ea",
        meta: {
          source: secondary.source,
          pathwayId: secondary.id,
          pathwayType: secondaryType,
          geneCount: secondary.genes.length,
        },
      };
      nodes.push(secondaryNode);

      const sharedGenes = new Set(primary.genes.filter((gene) => secondary.genes.includes(gene)));
      secondary.genes.slice(0, 14).forEach((gene, index) => {
        const pos = polar(comparisonCenter.x, comparisonCenter.y + 120, 220, -20 + index * (140 / Math.max(secondary.genes.slice(0, 14).length, 1)));
        const shared = sharedGenes.has(gene);
        const geneNode: GraphNode = {
          id: `gene:${secondary.id}:${gene}`,
          label: gene,
          type: "gene",
          x: pos.x,
          y: pos.y,
          fill: shared ? "#dcfce7" : TYPE_STYLE.gene.fill,
          outline: shared ? "#16a34a" : TYPE_STYLE.gene.outline,
          meta: {
            source: secondary.source,
            pathwayId: secondary.id,
            shared,
          },
        };
        nodes.push(geneNode);
        edges.push({
          id: `edge:${secondary.id}:${gene}`,
          source: secondaryNode.id,
          target: geneNode.id,
          sourceName: secondary.source,
          relation: shared ? "shared_member_gene" : "member_gene",
          evidenceSentence: `${gene} is ${shared ? "shared across both pathways and" : "a member gene in"} ${secondary.name}.`,
          diseaseContext: shared ? `Shared biological overlap between ${primary.name} and ${secondary.name}.` : `Specific to ${secondary.name}.`,
          line: shared ? "#16a34a" : "#94a3b8",
          lineWidth: shared ? 3 : 2,
        });
      });

      edges.push({
        id: `edge:pathway-compare:${primary.id}:${secondary.id}`,
        source: primaryNode.id,
        target: secondaryNode.id,
        sourceName: `${primary.source} + ${secondary.source}`,
        relation: "pathway_comparison",
        evidenceSentence: `${primary.name} is compared against ${secondary.name} to highlight shared and divergent biology.`,
        diseaseContext: `Shared genes: ${primary.genes.filter((gene) => secondary.genes.includes(gene)).length}.`,
        line: "#7c3aed",
        lineWidth: 3,
      });
    }

    return { nodes, edges, typeLabel };
  }, [carriedEntities, diseaseContext, primary, query, secondary]);

  const selectedNode = model.nodes.find((node) => node.id === selectedNodeId) || null;
  const selectedEdge = model.edges.find((edge) => edge.id === selectedEdgeId) || null;

  if (!primary) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-[var(--text-muted)]">
        Select a pathway to build the biological synthesis map.
      </div>
    );
  }

  return (
    <div className="grid lg:grid-cols-[1fr,300px] h-full">
      <div className="relative overflow-auto p-4" style={{ background: "linear-gradient(180deg, rgba(99,102,241,0.04), rgba(255,255,255,0))" }}>
        <div className="flex items-center gap-2 mb-3 text-[11px] text-[var(--text-muted)]">
          <span className="px-2 py-1 rounded-full" style={{ background: "rgba(79,70,229,0.08)", color: "#4338ca" }}>{model.typeLabel.replace(/_/g, " ")}</span>
          <span>{secondary ? "Comparison mode" : "Synthesis mode"}</span>
          <span>{model.nodes.length} nodes</span>
          <span>{model.edges.length} edges</span>
        </div>
        <svg viewBox="0 0 1000 620" className="w-full min-h-[560px] rounded-2xl border bg-white" style={{ borderColor: "var(--border)" }}>
          {model.edges.map((edge) => {
            const source = model.nodes.find((node) => node.id === edge.source);
            const target = model.nodes.find((node) => node.id === edge.target);
            if (!source || !target) return null;
            return (
              <path
                key={edge.id}
                d={linePath(source, target)}
                stroke={edge.line}
                strokeWidth={edge.lineWidth}
                fill="none"
                strokeDasharray={edge.relation.includes("comparison") ? "8 6" : undefined}
                opacity={selectedEdgeId === edge.id || !selectedEdgeId ? 0.9 : 0.35}
                className="cursor-pointer"
                onClick={() => {
                  setSelectedNodeId(null);
                  setSelectedEdgeId(edge.id);
                }}
              />
            );
          })}
          {model.nodes.map((node) => (
            <g
              key={node.id}
              className="cursor-pointer"
              onClick={() => {
                setSelectedEdgeId(null);
                setSelectedNodeId(node.id);
              }}
              opacity={selectedNodeId === node.id || !selectedNodeId ? 1 : 0.45}
            >
              {node.type === "pathway" ? (
                <rect
                  x={node.x - (node.width || 170) / 2}
                  y={node.y - (node.height || 64) / 2}
                  rx="18"
                  width={node.width || 170}
                  height={node.height || 64}
                  fill={node.fill}
                  stroke={node.outline}
                  strokeWidth="2"
                />
              ) : (
                <circle cx={node.x} cy={node.y} r={node.type === "compound" ? 28 : node.type === "disease" ? 32 : 26} fill={node.fill} stroke={node.outline} strokeWidth="2" />
              )}
              <text
                x={node.x}
                y={node.type === "pathway" ? node.y - 6 : node.y + 4}
                textAnchor="middle"
                fontSize={node.type === "pathway" ? "12" : "11"}
                fontWeight="600"
                fill="#0f172a"
              >
                {node.label.length > (node.type === "pathway" ? 24 : 14) ? `${node.label.slice(0, node.type === "pathway" ? 24 : 14)}…` : node.label}
              </text>
              {node.type === "pathway" && (
                <text x={node.x} y={node.y + 14} textAnchor="middle" fontSize="10" fill="#475569">
                  {String(node.meta.source || "")}
                </text>
              )}
              {/* Source database color dot */}
              {node.meta.source_db && (
                <circle
                  cx={node.x + (node.type === "pathway" ? (node.width || 170) / 2 - 8 : 18)}
                  cy={node.y - (node.type === "pathway" ? (node.height || 64) / 2 - 8 : 18)}
                  r={4}
                  fill={SOURCE_COLORS[String(node.meta.source_db || node.meta.source || "").toLowerCase()] || SOURCE_COLORS.default}
                  stroke="#fff"
                  strokeWidth={1}
                />
              )}
            </g>
          ))}
        </svg>
        {/* Legend */}
        <div className="flex flex-wrap gap-3 mt-2 px-2 text-[10px] text-[var(--text-muted)]">
          <span className="font-semibold">Sources:</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: SOURCE_COLORS.kegg }} />KEGG</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: SOURCE_COLORS.reactome }} />Reactome</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: SOURCE_COLORS.wikipathways }} />WikiPathways</span>
          <span className="mx-2">|</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block border-2" style={{ borderColor: "#dc2626", background: "#fecaca" }} />Disease-affected</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full inline-block border-2" style={{ borderColor: "#059669", background: "#dcfce7" }} />Therapeutic target</span>
        </div>
      </div>

      <div className="border-l p-4 space-y-4 overflow-y-auto" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">Renderer</div>
          <div className="text-sm font-semibold text-[var(--text-primary)] mt-1">Biological pathway workbench</div>
          <div className="text-[11px] text-[var(--text-muted)] mt-1">Custom SVG layout for metabolic, signaling, disease, and regulatory pathways with compare and synthesis overlays.</div>
        </div>

        {selectedNode && (
          <div className="rounded-xl border p-3 space-y-2" style={{ borderColor: "var(--border)" }}>
            <div className="text-xs font-semibold text-[var(--text-primary)]">Node detail</div>
            <div className="text-sm font-semibold">{selectedNode.label}</div>
            <div className="text-[11px] text-[var(--text-muted)] capitalize">{selectedNode.type}</div>
            {selectedNode.meta.source_db && (
              <div className="text-[11px] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ background: SOURCE_COLORS[String(selectedNode.meta.source_db || selectedNode.meta.source || "").toLowerCase()] || SOURCE_COLORS.default }} />
                <span className="font-medium text-[var(--text-secondary)]">Source: {String(selectedNode.meta.source_db || selectedNode.meta.source || "unknown")}</span>
              </div>
            )}
            {selectedNode.meta.source_url && (
              <a href={String(selectedNode.meta.source_url)} target="_blank" rel="noopener noreferrer" className="text-[10px] text-blue-600 hover:underline">View in source database →</a>
            )}
            {selectedNode.meta.rewired && (
              <div className="text-[10px] px-2 py-1 rounded-lg" style={{ background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca" }}>Disease-affected gene</div>
            )}
            {selectedNode.meta.therapeutic && (
              <div className="text-[10px] px-2 py-1 rounded-lg" style={{ background: "#f0fdf4", color: "#059669", border: "1px solid #bbf7d0" }}>Therapeutic target</div>
            )}
            <div className="text-[11px] text-[var(--text-secondary)]">
              {Object.entries(selectedNode.meta)
                .filter(([k]) => !["source_db", "source_url", "rewired", "therapeutic"].includes(k))
                .map(([label, value]) => `${label}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`).join(" · ")}
            </div>
          </div>
        )}

        {selectedEdge && (
          <div className="rounded-xl border p-3 space-y-2" style={{ borderColor: `${selectedEdge.line}55` }}>
            <div className="text-xs font-semibold text-[var(--text-primary)]">Connection provenance</div>
            <div className="text-[11px] text-[var(--text-secondary)]">{selectedEdge.relation.replace(/_/g, " ")}</div>
            <div className="text-[11px] text-[var(--text-muted)]">Source DB: {selectedEdge.sourceName}</div>
            <div className="text-[11px] text-[var(--text-secondary)]">{selectedEdge.evidenceSentence}</div>
            <div className="text-[11px] text-[var(--text-muted)]">Disease context: {selectedEdge.diseaseContext}</div>
          </div>
        )}

        {!selectedNode && !selectedEdge && (
          <div className="rounded-xl border p-3 text-[11px] text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}>
            Click any node or connection to inspect explanation, source attribution, and disease context.
          </div>
        )}
      </div>
    </div>
  );
}