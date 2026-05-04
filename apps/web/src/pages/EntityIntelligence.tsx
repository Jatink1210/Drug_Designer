import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Box,
  Dna,
  FlaskConical,
  FolderUp,
  GitBranch,
  Loader2,
  Network,
  Save,
  Search,
  Sparkles,
  Upload,
} from "lucide-react";
import {
  entityIntelligenceAnalyzeAPI,
  evidenceBundleCreateAPI,
  targetCompareAPI,
  type EntityIntelligenceAnalyzeResult,
  type EntityIntelligenceEntity,
  type EntityIntelligenceResolvedSlot,
  type EntityIntelligenceSlotType,
  type GraphNode,
} from "@/lib/api";
import EntityGraphWorkbench from "@/components/entity/EntityGraphWorkbench";
import { persistCockpitHandoff, readCockpitHandoff, type CockpitEntityType, type SharedHandoffPayload } from "@/lib/canonicalProduct";
import { useToast } from "@/lib/ToastContext";
import { useSetPageConfidence } from "@/lib/PageConfidenceContext";

type ModeKey = "disease" | "targets" | "graph" | "ppi" | "pathways" | "structure" | "enrichment" | "export";

interface SlotState {
  slotIndex: number;
  declaredType: EntityIntelligenceSlotType;
  text: string;
  values: string[];
  fileName?: string;
}

const DEFAULT_SLOTS: SlotState[] = Array.from({ length: 5 }, (_, index) => ({
  slotIndex: index,
  declaredType: "blank",
  text: "",
  values: [],
}));

const SLOT_TYPES: Array<{ value: EntityIntelligenceSlotType; label: string }> = [
  { value: "blank", label: "/Blank" },
  { value: "disease", label: "/Disease" },
  { value: "gene", label: "/Gene" },
  { value: "protein", label: "/Protein" },
  { value: "molecule", label: "/Molecule" },
  { value: "drug", label: "/Drug" },
  { value: "variant", label: "/Variant" },
];

const MODE_LABELS: Record<ModeKey, string> = {
  disease: "Disease Intelligence",
  targets: "Target Prioritization",
  graph: "Graph Mode",
  ppi: "PPI Mode",
  pathways: "Pathway Mode",
  structure: "Structure Mode",
  enrichment: "Enrichment / Clustering",
  export: "Export / Save Bundle",
};

const SLOT_META: Record<EntityIntelligenceSlotType, { icon: typeof Search; color: string }> = {
  blank: { icon: Search, color: "#64748b" },
  disease: { icon: Activity, color: "#dc2626" },
  gene: { icon: Dna, color: "#7c3aed" },
  protein: { icon: Dna, color: "#4f46e5" },
  molecule: { icon: FlaskConical, color: "#d97706" },
  drug: { icon: FlaskConical, color: "#2563eb" },
  variant: { icon: GitBranch, color: "#0891b2" },
};

function normalizeMode(value: string | null): ModeKey {
  if (value === "targets" || value === "graph" || value === "ppi" || value === "pathways" || value === "structure" || value === "enrichment" || value === "export") {
    return value;
  }
  return "disease";
}

function inferSlotTypeFromEntity(entityType?: string): EntityIntelligenceSlotType {
  if (!entityType) return "blank";
  if (entityType === "drug") return "drug";
  if (entityType === "gene") return "gene";
  if (entityType === "protein" || entityType === "target") return "protein";
  if (entityType === "molecule" || entityType === "compound") return "molecule";
  if (entityType === "variant") return "variant";
  if (entityType === "disease") return "disease";
  return "blank";
}

function parseDelimitedText(raw: string): string[] {
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length === 0) return [];
  const delimiter = lines.some((line) => line.includes("\t")) ? "\t" : lines.some((line) => line.includes(",")) ? "," : null;
  const rows = delimiter ? lines.map((line) => line.split(delimiter).map((cell) => cell.trim()).filter(Boolean)) : lines.map((line) => [line]);
  const looksLikeHeader = rows.length > 1 && rows[0].every((cell) => /name|gene|protein|disease|drug|molecule|variant|id|symbol/i.test(cell));
  const dataRows = looksLikeHeader ? rows.slice(1) : rows;
  return dataRows.flat().filter(Boolean);
}

function hasFilledSlots(slots: SlotState[]): boolean {
  return slots.some((slot) => slot.text.trim() || slot.values.length > 0);
}

function toCockpitEntityType(entityType?: string): CockpitEntityType {
  if (entityType === "protein" || entityType === "gene" || entityType === "drug" || entityType === "disease" || entityType === "molecule" || entityType === "pathway" || entityType === "variant" || entityType === "publication" || entityType === "clinical_trial" || entityType === "target" || entityType === "compound") {
    return entityType;
  }
  return "unknown";
}

function buildHandoff(route: string, action: SharedHandoffPayload["action"], query: string, entities: EntityIntelligenceEntity[], runId?: string): SharedHandoffPayload {
  return {
    version: "phase0.v1",
    sourceModule: "entity-intelligence",
    action,
    targetRoute: route,
    query,
    createdAt: new Date().toISOString(),
    runId,
    entities: entities.map((entity) => ({
      ...entity,
      entityType: toCockpitEntityType(entity.entityType),
    })),
    provenance: entities.map((entity) => ({
      source: entity.sourceCategory || "entity-intelligence",
      retrievedAt: new Date().toISOString(),
      runId,
    })),
    metadata: {
      module: "entity-intelligence",
    },
  };
}

function entityToGraphNode(entity: EntityIntelligenceEntity): GraphNode {
  return {
    id: entity.entityId,
    label: entity.entityName,
    type: entity.entityType,
    properties: {
      identifiers: entity.identifiers || {},
      ...(entity.attributes || {}),
    },
  };
}

export default function EntityIntelligence() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { addToast } = useToast();
  const setConfidence = useSetPageConfidence();

  const [slots, setSlots] = useState<SlotState[]>(DEFAULT_SLOTS);
  const [activeMode, setActiveMode] = useState<ModeKey>(normalizeMode(searchParams.get("mode")));
  const [result, setResult] = useState<EntityIntelligenceAnalyzeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEntityKeys, setSelectedEntityKeys] = useState<Set<string>>(new Set());
  const [selectedEdge, setSelectedEdge] = useState<Record<string, unknown> | null>(null);
  const [pendingAutoRun, setPendingAutoRun] = useState(false);
  const seededRef = useRef(false);

  const selectedEntities = useMemo(() => {
    if (!result) return [] as EntityIntelligenceEntity[];
    const all = [
      ...result.entities,
      ...((result.targetPrioritization.targets || []).map((target) => ({
        entityId: target.symbol,
        entityType: "gene",
        entityName: target.symbol,
        identifiers: { HGNC: target.symbol },
        attributes: { score: target.composite_score, signals: target.signals },
      })) as EntityIntelligenceEntity[]),
    ];
    return all.filter((entity) => selectedEntityKeys.has(`${entity.entityType}:${entity.entityId}`));
  }, [result, selectedEntityKeys]);

  const selectedSymbols = useMemo(() => {
    return selectedEntities.filter((entity) => entity.entityType === "gene" || entity.entityType === "protein" || entity.entityType === "target").map((entity) => entity.entityName.toUpperCase()).slice(0, 6);
  }, [selectedEntities]);

  const compareQuery = useQuery({
    queryKey: ["entity-intelligence-compare", selectedSymbols.join(",")],
    queryFn: () => targetCompareAPI(selectedSymbols),
    enabled: selectedSymbols.length >= 2,
  });

  useEffect(() => {
    if (result) {
      setConfidence({
        freshness: "current",
        sourceCount: result.provenance.length,
        sourcesQueried: result.provenance.map((item) => item.source),
      });
    } else {
      setConfidence(null);
    }
    return () => setConfidence(null);
  }, [result, setConfidence]);

  useEffect(() => {
    if (seededRef.current) return;
    const payload = readCockpitHandoff();
    const query = searchParams.get("query") || payload?.query || "";
    const entity = payload?.entities?.[0];
    const declaredType = inferSlotTypeFromEntity(entity?.entityType);
    const genes = searchParams.get("genes");
    if (!query && !genes) return;
    seededRef.current = true;
    setSlots((current) => current.map((slot, index) => index === 0 ? {
      ...slot,
      declaredType: declaredType !== "blank" ? declaredType : (genes ? "gene" : slot.declaredType),
      text: query || (genes ? genes.split(",")[0] : ""),
      values: genes ? genes.split(",").map((item) => item.trim()).filter(Boolean) : slot.values,
    } : slot));
    setPendingAutoRun(true);
    if (searchParams.get("mode")) {
      setActiveMode(normalizeMode(searchParams.get("mode")));
    }
  }, [searchParams]);

  useEffect(() => {
    if (pendingAutoRun && hasFilledSlots(slots)) {
      setPendingAutoRun(false);
      void handleAnalyze();
    }
  }, [pendingAutoRun, slots]);

  const handleSlotChange = (slotIndex: number, patch: Partial<SlotState>) => {
    setSlots((current) => current.map((slot) => slot.slotIndex === slotIndex ? { ...slot, ...patch } : slot));
  };

  const toggleEntitySelection = (entity: EntityIntelligenceEntity) => {
    const key = `${entity.entityType}:${entity.entityId}`;
    setSelectedEntityKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  async function handleAnalyze() {
    if (!hasFilledSlots(slots)) {
      setError("At least one slot must contain a typed value or CSV list.");
      return;
    }
    setLoading(true);
    setError(null);
    setSelectedEdge(null);
    try {
      const payload = await entityIntelligenceAnalyzeAPI({
        slots: slots
          .filter((slot) => slot.text.trim() || slot.values.length > 0)
          .map((slot) => ({
            slot_index: slot.slotIndex,
            declared_type: slot.declaredType,
            value: slot.text.trim(),
            values: slot.values,
          })),
        graph_max_nodes: 600,
        graph_depth: 2,
      });
      setResult(payload);
      setActiveMode((current) => searchParams.get("mode") ? normalizeMode(searchParams.get("mode")) : current);
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        if (payload.summary.graphQuery) next.set("query", payload.summary.graphQuery);
        next.set("mode", activeMode);
        return next;
      }, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Entity intelligence analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  const downloadJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = `entity-intelligence-${result.summary.graphQuery.replace(/\s+/g, "-") || "bundle"}.json`;
    anchor.click();
    URL.revokeObjectURL(href);
  };

  const saveBundle = async () => {
    if (!result) return;
    try {
      await evidenceBundleCreateAPI({
        name: `Entity Intelligence — ${result.summary.graphQuery || "bundle"}`,
        description: `Merged entity analysis with ${result.summary.entityCount} resolved entities and ${result.summary.geneCount} genes.`,
      });
      addToast({ type: "success", title: "Bundle saved", message: "Created contextual evidence bundle for this entity run." });
    } catch (err) {
      addToast({ type: "error", title: "Bundle save failed", message: err instanceof Error ? err.message : "Unknown error" });
    }
  };

  const navigateWithEntities = (route: string, action: SharedHandoffPayload["action"], entities: EntityIntelligenceEntity[]) => {
    if (!result || entities.length === 0) return;
    persistCockpitHandoff(buildHandoff(route, action, result.summary.graphQuery, entities, result.run_id));
    navigate(route);
  };

  const handleGraphAction = (action: "structure" | "design" | "prioritize", nodes: GraphNode[]) => {
    const mappedEntities = nodes.map((node) => ({
      entityId: node.id,
      entityType: node.type,
      entityName: node.label,
      identifiers: ((node.properties as Record<string, unknown> | undefined)?.identifiers as Record<string, string> | undefined) || {},
      attributes: node.properties,
      sourceCategory: "entity-intelligence-graph",
    }));
    if (action === "structure") {
      navigateWithEntities("/structure", "open_in_structure", mappedEntities);
      return;
    }
    if (action === "design") {
      navigateWithEntities("/design", "open_in_design", mappedEntities);
      return;
    }
    setActiveMode("targets");
    setSelectedEntityKeys(new Set(mappedEntities.map((entity) => `${entity.entityType}:${entity.entityId}`)));
  };

  const compareRows = Array.isArray((compareQuery.data as Record<string, unknown> | undefined)?.comparison)
    ? ((compareQuery.data as Record<string, unknown>).comparison as Array<Record<string, unknown>>)
    : [];

  const slotResults = useMemo(() => {
    const map = new Map<number, EntityIntelligenceResolvedSlot>();
    for (const slot of result?.resolvedSlots || []) {
      map.set(slot.slotIndex, slot);
    }
    return map;
  }, [result]);

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-[1560px] mx-auto px-6 py-5 space-y-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">Entity Intelligence</h1>
            <p className="text-xs text-[var(--text-muted)] mt-1">Five-slot merged disease + target + gene/protein + PPI workbench with unified ID resolution and direct structure/design handoff.</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={handleAnalyze} disabled={loading} className="px-4 py-2 rounded-xl text-xs font-semibold text-white inline-flex items-center gap-2 disabled:opacity-50" style={{ background: "var(--accent)" }}>
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} Analyze
            </button>
            <button onClick={downloadJson} disabled={!result} className="px-3 py-2 rounded-xl border text-xs font-medium disabled:opacity-40" style={{ borderColor: "var(--border)" }}>Export JSON</button>
            <button onClick={saveBundle} disabled={!result} className="px-3 py-2 rounded-xl border text-xs font-medium inline-flex items-center gap-1 disabled:opacity-40" style={{ borderColor: "var(--border)" }}><Save size={12} /> Save Bundle</button>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {slots.map((slot) => {
            const slotMeta = SLOT_META[slot.declaredType];
            const SlotIcon = slotMeta.icon;
            const slotResult = slotResults.get(slot.slotIndex);
            const previewEntity = slotResult?.results[0];
            const topConfidence = slotResult?.provenance.map((item) => item.confidence).find((value): value is number => typeof value === "number");
            return (
            <div key={slot.slotIndex} className="rounded-2xl border p-4 space-y-3" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
              <div className="flex items-center justify-between gap-2">
                <div className="inline-flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)]">
                  <span className="w-7 h-7 rounded-full inline-flex items-center justify-center" style={{ background: `${slotMeta.color}18`, color: slotMeta.color }}>
                    <SlotIcon size={13} />
                  </span>
                  Slot {slot.slotIndex + 1}
                </div>
                <select value={slot.declaredType} onChange={(event) => handleSlotChange(slot.slotIndex, { declaredType: event.target.value as EntityIntelligenceSlotType })} className="text-[11px] rounded-lg border px-2 py-1" style={{ borderColor: "var(--border)", background: "var(--bg-app)" }}>
                  {SLOT_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
                </select>
              </div>

              <div className="relative">
                <Search size={14} className="absolute left-3 top-3 text-[var(--text-muted)]" />
                <textarea
                  value={slot.text}
                  onChange={(event) => handleSlotChange(slot.slotIndex, { text: event.target.value })}
                  rows={3}
                  placeholder="Manual text input or paste a delimited list"
                  className="w-full rounded-xl border pl-9 pr-3 py-2 text-xs resize-none"
                  style={{ borderColor: "var(--border)", background: "var(--bg-app)" }}
                />
              </div>

              <label className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border text-[11px] font-medium cursor-pointer" style={{ borderColor: "var(--border)" }}>
                <Upload size={12} /> Upload CSV/TSV
                <input
                  type="file"
                  accept=".csv,.tsv,.txt"
                  className="hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;
                    const reader = new FileReader();
                    reader.onload = () => {
                      const values = parseDelimitedText(String(reader.result || ""));
                      handleSlotChange(slot.slotIndex, { values, fileName: file.name, text: slot.text || values.slice(0, 5).join(", ") });
                    };
                    reader.readAsText(file);
                  }}
                />
              </label>

              <div className="text-[11px] text-[var(--text-muted)]">
                {slot.fileName ? <span className="inline-flex items-center gap-1"><FolderUp size={12} /> {slot.fileName}</span> : "No file loaded"}
                {slot.values.length > 0 ? <span className="ml-2 font-medium text-[var(--text-secondary)]">{slot.values.length} parsed values</span> : null}
              </div>

              {previewEntity && (
                <div className="rounded-xl border px-3 py-2 text-[11px]" style={{ borderColor: `${slotMeta.color}30`, background: `${slotMeta.color}0d` }}>
                  <div className="font-semibold truncate" style={{ color: slotMeta.color }} title={previewEntity.entityName}>{previewEntity.entityName}</div>
                  <div className="text-[var(--text-muted)] mt-1">{Object.entries(previewEntity.identifiers || {}).slice(0, 3).map(([label, value]) => `${label}: ${value}`).join(" · ") || previewEntity.entityId}</div>
                  {typeof topConfidence === "number" ? <div className="mt-1 text-[var(--text-secondary)]">confidence {topConfidence.toFixed(2)}</div> : null}
                </div>
              )}
            </div>
          );})}
        </div>

        {error && (
          <div className="rounded-2xl border px-4 py-3 text-sm text-red-700 inline-flex items-center gap-2" style={{ borderColor: "rgba(239,68,68,0.25)", background: "rgba(239,68,68,0.07)" }}>
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {result && (
          <>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-3 py-1 rounded-full text-[11px] font-semibold bg-indigo-50 text-indigo-700">{result.summary.entityCount} entities</span>
              <span className="px-3 py-1 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700">{result.summary.geneCount} genes</span>
              <span className="px-3 py-1 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700">{result.summary.elapsed_ms} ms</span>
              {result.degraded_sources?.length ? <span className="px-3 py-1 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700">degraded: {result.degraded_sources.join(", ")}</span> : null}
            </div>

            <div className="rounded-2xl border p-4 space-y-3" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
              <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]"><Activity size={16} /> Resolution Results</div>
              <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
                {result.resolvedSlots.map((slot: EntityIntelligenceResolvedSlot) => (
                  <div key={slot.slotIndex} className="rounded-xl border p-3 space-y-2" style={{ borderColor: "var(--border)" }}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-xs font-semibold text-[var(--text-primary)]">Slot {slot.slotIndex + 1} · {slot.resolvedType}</div>
                      <div className="text-[10px] text-[var(--text-muted)]">{slot.queryValues.join(", ")}</div>
                    </div>
                    {slot.provenance.length > 0 && (
                      <div className="text-[10px] text-[var(--text-muted)]">
                        {slot.provenance.slice(0, 2).map((item) => `${item.source}${typeof item.confidence === "number" ? ` ${item.confidence.toFixed(2)}` : ""}`).join(" · ")}
                      </div>
                    )}
                    {slot.results.map((entity) => {
                      const key = `${entity.entityType}:${entity.entityId}`;
                      const checked = selectedEntityKeys.has(key);
                      return (
                        <label key={key} className="flex items-start gap-2 rounded-lg border p-2 cursor-pointer" style={{ borderColor: checked ? "rgba(79,70,229,0.35)" : "var(--border)", background: checked ? "rgba(79,70,229,0.08)" : "transparent" }}>
                          <input type="checkbox" checked={checked} onChange={() => toggleEntitySelection(entity)} className="mt-0.5" />
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-[var(--text-primary)] truncate" title={entity.entityName}>{entity.entityName}</div>
                            <div className="text-[10px] text-[var(--text-muted)]">{Object.entries(entity.identifiers || {}).slice(0, 3).map(([label, value]) => `${label}: ${value}`).join(" · ") || entity.entityId}</div>
                            {Array.isArray(entity.attributes?.alternatives) && (entity.attributes?.alternatives as string[]).length > 0 ? <div className="text-[10px] text-[var(--text-muted)] mt-1">alts: {(entity.attributes?.alternatives as string[]).slice(0, 3).join(", ")}</div> : null}
                          </div>
                        </label>
                      );
                    })}
                    {slot.conflicts.length > 0 && <div className="text-[10px] text-rose-600">{slot.conflicts.join(" · ")}</div>}
                  </div>
                ))}
              </div>
            </div>

            {selectedEntities.length > 0 && (
              <div className="rounded-2xl border p-4 space-y-3" style={{ borderColor: "rgba(79,70,229,0.2)", background: "rgba(79,70,229,0.06)" }}>
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div>
                    <div className="text-sm font-semibold text-[var(--text-primary)]">Compare Selected Entities</div>
                    <div className="text-[11px] text-[var(--text-muted)]">{selectedEntities.map((entity) => entity.entityName).join(", ")}</div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <button onClick={() => navigateWithEntities("/structure", "open_in_structure", selectedEntities)} className="px-3 py-2 rounded-xl border text-[11px] font-medium inline-flex items-center gap-1" style={{ borderColor: "var(--border)" }}><Box size={12} /> Open in Structure</button>
                    <button onClick={() => navigateWithEntities("/design", "open_in_design", selectedEntities)} className="px-3 py-2 rounded-xl border text-[11px] font-medium inline-flex items-center gap-1" style={{ borderColor: "var(--border)" }}><FlaskConical size={12} /> Open in Design</button>
                    <button onClick={() => setActiveMode("targets")} className="px-3 py-2 rounded-xl border text-[11px] font-medium inline-flex items-center gap-1" style={{ borderColor: "var(--border)" }}><BarChart3 size={12} /> Run Prioritization</button>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {selectedEntities.map((entity) => (
                    <div key={`${entity.entityType}:${entity.entityId}`} className="rounded-xl border p-3" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                      <div className="text-xs font-semibold text-[var(--text-primary)] truncate" title={entity.entityName}>{entity.entityName}</div>
                      <div className="text-[10px] text-[var(--text-muted)] capitalize">{entity.entityType}</div>
                      <div className="text-[10px] text-[var(--text-secondary)] mt-2">{Object.entries(entity.identifiers || {}).map(([label, value]) => `${label}: ${value}`).join(" · ") || entity.entityId}</div>
                    </div>
                  ))}
                </div>

                {compareRows.length > 0 && (
                  <div className="overflow-x-auto table-scroll-container rounded-xl border" style={{ borderColor: "var(--border)" }}>
                    <table className="w-full text-xs">
                      <thead style={{ background: "var(--bg-app)" }}>
                        <tr>
                          <th className="px-3 py-2 text-left">Gene</th>
                          <th className="px-3 py-2 text-left">Composite</th>
                          <th className="px-3 py-2 text-left">GWAS</th>
                          <th className="px-3 py-2 text-left">Druggability</th>
                          <th className="px-3 py-2 text-left">Literature</th>
                        </tr>
                      </thead>
                      <tbody>
                        {compareRows.map((row, index) => (
                          <tr key={`${row.gene_symbol || row.uniprot_id || index}`} className="border-t" style={{ borderColor: "var(--border)" }}>
                            <td className="px-3 py-2">{String(row.gene_symbol || "")}</td>
                            <td className="px-3 py-2">{Number(row.composite_score || 0).toFixed(3)}</td>
                            <td className="px-3 py-2">{Number(row.gwas_score || 0).toFixed(3)}</td>
                            <td className="px-3 py-2">{Number(row.druggability_score || 0).toFixed(3)}</td>
                            <td className="px-3 py-2">{Number(row.literature_score || 0).toFixed(3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2 flex-wrap">
              {(Object.keys(MODE_LABELS) as ModeKey[]).map((mode) => (
                <button key={mode} onClick={() => { setActiveMode(mode); setSearchParams((current) => { const next = new URLSearchParams(current); next.set("mode", mode); return next; }, { replace: true }); }} className="px-3 py-2 rounded-xl text-xs font-semibold border" style={{ borderColor: activeMode === mode ? "rgba(79,70,229,0.35)" : "var(--border)", background: activeMode === mode ? "rgba(79,70,229,0.08)" : "transparent", color: activeMode === mode ? "#4338ca" : "var(--text-secondary)" }}>{MODE_LABELS[mode]}</button>
              ))}
            </div>

            {activeMode === "disease" && (
              <div className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]"><Activity size={16} /> Disease Intelligence</div>
                <div className="mt-4 grid gap-4 lg:grid-cols-[1.2fr,1fr]">
                  <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                    <div className="text-xs font-semibold text-[var(--text-primary)]">Normalized disease queries</div>
                    <div className="mt-3 space-y-3">
                      {result.diseaseIntelligence.queries.map((item) => (
                        <div key={item.query} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                          <div className="text-xs font-semibold">{item.normalized}</div>
                          <div className="text-[10px] text-[var(--text-muted)] mt-1">{Object.entries(item.identifiers || {}).map(([label, value]) => `${label}: ${value}`).join(" · ")}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                    <div className="text-xs font-semibold text-[var(--text-primary)]">Top candidate genes</div>
                    <div className="mt-3 space-y-2 max-h-[420px] overflow-y-auto">
                      {result.diseaseIntelligence.candidateGenes.slice(0, 20).map((item) => (
                        <div key={String(item.symbol)} className="rounded-lg border p-2 flex items-center justify-between gap-3" style={{ borderColor: "var(--border)" }}>
                          <div>
                            <div className="text-xs font-semibold">{String(item.symbol || "")}</div>
                            <div className="text-[10px] text-[var(--text-muted)]">{String(item.uniprot_id || "") || "No UniProt"}</div>
                          </div>
                          <div className="text-[10px] font-semibold text-indigo-600">{Number(item.overall_score || 0).toFixed(3)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeMode === "targets" && (
              <div className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]"><BarChart3 size={16} /> Target Prioritization</div>
                <div className="mt-4 overflow-x-auto table-scroll-container rounded-xl border" style={{ borderColor: "var(--border)" }}>
                  <table className="w-full text-xs">
                    <thead style={{ background: "var(--bg-app)" }}>
                      <tr>
                        <th className="px-3 py-2 text-left">Select</th>
                        <th className="px-3 py-2 text-left">Rank</th>
                        <th className="px-3 py-2 text-left">Symbol</th>
                        <th className="px-3 py-2 text-left">Composite</th>
                        <th className="px-3 py-2 text-left">Score Breakdown</th>
                        <th className="px-3 py-2 text-left">Signals</th>
                        <th className="px-3 py-2 text-left">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.targetPrioritization.targets.map((target) => {
                        const entity: EntityIntelligenceEntity = {
                          entityId: target.symbol,
                          entityType: "gene",
                          entityName: target.symbol,
                          identifiers: { HGNC: target.symbol },
                          attributes: { score: target.composite_score, explanation: target.explanation },
                          sourceCategory: "entity-intelligence",
                        };
                        const key = `${entity.entityType}:${entity.entityId}`;
                        const selected = selectedEntityKeys.has(key);
                        return (
                          <tr key={target.symbol} className="border-t" style={{ borderColor: "var(--border)" }}>
                            <td className="px-3 py-2"><input type="checkbox" checked={selected} onChange={() => toggleEntitySelection(entity)} /></td>
                            <td className="px-3 py-2">{target.rank}</td>
                            <td className="px-3 py-2 font-semibold">{target.symbol}</td>
                            <td className="px-3 py-2">
                              <span className="font-mono font-semibold" style={{ color: target.composite_score >= 0.7 ? "#10b981" : target.composite_score >= 0.4 ? "#f59e0b" : "#ef4444" }}>
                                {target.composite_score.toFixed(3)}
                              </span>
                            </td>
                            <td className="px-3 py-2 min-w-[200px]">
                              {(() => {
                                const signals = target.signals as Record<string, unknown> | undefined;
                                const dims = [
                                  { key: "gwas", label: "GWAS", color: "#6366f1" },
                                  { key: "pathway", label: "Pathway", color: "#0891b2" },
                                  { key: "druggability", label: "Drug.", color: "#059669" },
                                  { key: "safety", label: "Safety", color: "#d97706" },
                                  { key: "literature", label: "Lit.", color: "#3b82f6" },
                                ];
                                return (
                                  <div className="space-y-1">
                                    {dims.map((dim) => {
                                      const val = typeof signals?.[dim.key] === "number" ? (signals[dim.key] as number) : typeof signals?.[`${dim.key}_score`] === "number" ? (signals[`${dim.key}_score`] as number) : 0;
                                      return (
                                        <div key={dim.key} className="flex items-center gap-1.5">
                                          <span className="w-10 text-[9px] text-[var(--text-muted)] truncate">{dim.label}</span>
                                          <div className="flex-1 h-1.5 rounded-full" style={{ background: "var(--border)" }}>
                                            <div className="h-1.5 rounded-full" style={{ width: `${Math.round(Math.min(1, val) * 100)}%`, background: dim.color }} />
                                          </div>
                                          <span className="text-[9px] font-mono w-7 text-right" style={{ color: dim.color }}>{(val * 100).toFixed(0)}</span>
                                        </div>
                                      );
                                    })}
                                  </div>
                                );
                              })()}
                              {target.explanation && (
                                <div className="text-[9px] text-[var(--text-muted)] mt-1 italic">{target.explanation}</div>
                              )}
                              {target.contradiction_flag && (
                                <div className="text-[9px] text-rose-600 mt-0.5 font-medium">⚠ Contradictory evidence</div>
                              )}
                            </td>
                            <td className="px-3 py-2">{target.sources.join(", ")}</td>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2 flex-wrap">
                                <button onClick={() => navigateWithEntities("/structure", "open_in_structure", [entity])} className="px-2 py-1 rounded-lg border text-[10px]" style={{ borderColor: "var(--border)" }}>Structure</button>
                                <button onClick={() => navigateWithEntities("/design", "open_in_design", [entity])} className="px-2 py-1 rounded-lg border text-[10px]" style={{ borderColor: "var(--border)" }}>Design</button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeMode === "graph" && (
              <div className="space-y-4">
                <EntityGraphWorkbench title="Entity Intelligence Graph" nodes={result.graph.nodes} edges={result.graph.edges} onEdgeSelect={(edge) => setSelectedEdge(edge as unknown as Record<string, unknown> | null)} onAction={handleGraphAction} />

                {/* Graph Analysis Tools Panel (Task 11.2) */}
                <div className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                  <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]"><Network size={16} /> Graph Analysis Tools</div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                      <div className="text-xs font-semibold text-[var(--text-primary)]">Centrality</div>
                      <div className="text-[10px] text-[var(--text-muted)] mt-1">Betweenness centrality identifies key bridge nodes in the network.</div>
                      <div className="mt-2 text-[10px] text-[var(--text-secondary)]">
                        {result.graph.nodes.length > 0 ? `${result.graph.nodes.length} nodes analyzed` : "No nodes"}
                      </div>
                    </div>
                    <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                      <div className="text-xs font-semibold text-[var(--text-primary)]">Communities</div>
                      <div className="text-[10px] text-[var(--text-muted)] mt-1">Louvain community detection groups densely connected entities.</div>
                      <div className="mt-2 text-[10px] text-[var(--text-secondary)]">
                        {result.enrichment?.communities?.communities ? `${(result.enrichment.communities.communities as unknown[]).length} communities` : "Run enrichment mode"}
                      </div>
                    </div>
                    <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                      <div className="text-xs font-semibold text-[var(--text-primary)]">Shortest Path</div>
                      <div className="text-[10px] text-[var(--text-muted)] mt-1">Find shortest path between two selected entities in the graph.</div>
                      <div className="mt-2 text-[10px] text-[var(--text-secondary)]">Select 2 nodes to compute</div>
                    </div>
                    <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                      <div className="text-xs font-semibold text-[var(--text-primary)]">Subgraph</div>
                      <div className="text-[10px] text-[var(--text-muted)] mt-1">Extract a subgraph around selected entities for focused analysis.</div>
                      <div className="mt-2 text-[10px] text-[var(--text-secondary)]">{result.graph.edges.length} edges total</div>
                    </div>
                  </div>
                </div>

                {selectedEdge && (
                  <div className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                    <div className="text-sm font-semibold text-[var(--text-primary)]">Edge Provenance</div>
                    <div className="text-xs text-[var(--text-secondary)] mt-2">{String(selectedEdge.label || selectedEdge.type || "RELATED")}</div>
                    <div className="text-[11px] text-[var(--text-muted)] mt-2">{Object.entries((selectedEdge.properties as Record<string, unknown> | undefined) || {}).map(([label, value]) => `${label}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`).join(" · ") || "No extra edge metadata"}</div>
                  </div>
                )}
              </div>
            )}

            {activeMode === "ppi" && (
              <EntityGraphWorkbench title="Protein-Protein Interaction Mode" nodes={result.ppi.nodes} edges={result.ppi.edges} emptyMessage="No STRING-derived interactions available for current gene pool." onAction={handleGraphAction} />
            )}

            {activeMode === "pathways" && (
              <div className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]"><GitBranch size={16} /> Pathway Overlay</div>
                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {result.pathways.enrichedPathways.map((pathway) => (
                    <div key={pathway.pathway_id} className="rounded-xl border p-3 space-y-2" style={{ borderColor: "var(--border)" }}>
                      <div className="text-xs font-semibold text-[var(--text-primary)] truncate" title={pathway.name}>{pathway.name}</div>
                      <div className="text-[10px] text-[var(--text-muted)]">{pathway.source} · {pathway.hit_count} hits</div>
                      <div className="text-[10px] text-[var(--text-secondary)]">{pathway.genes.slice(0, 6).join(", ")}</div>
                      <button onClick={() => {
                        persistCockpitHandoff(buildHandoff("/pathways", "open_in_pathways", pathway.name, result.entities, result.run_id));
                        navigate("/pathways");
                      }} className="px-2 py-1 rounded-lg border text-[10px] inline-flex items-center gap-1" style={{ borderColor: "var(--border)" }}>
                        Open in Pathways <ArrowRight size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeMode === "structure" && (
              <div className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]"><Box size={16} /> Structure Candidates</div>
                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {result.structures.map((structure) => {
                    const entity: EntityIntelligenceEntity = {
                      entityId: structure.uniprotId || structure.geneSymbol,
                      entityType: "protein",
                      entityName: structure.entityName,
                      identifiers: { UNIPROT: structure.uniprotId, PDB: structure.pdbId, ALPHAFOLD: structure.alphafoldId },
                      attributes: { geneSymbol: structure.geneSymbol },
                    };
                    return (
                      <div key={`${structure.entityName}-${structure.uniprotId}`} className="rounded-xl border p-3 space-y-2" style={{ borderColor: "var(--border)" }}>
                        <div className="text-xs font-semibold text-[var(--text-primary)] truncate" title={structure.entityName}>{structure.entityName}</div>
                        <div className="text-[10px] text-[var(--text-muted)]">UniProt {structure.uniprotId || "—"}</div>
                        <div className="text-[10px] text-[var(--text-muted)]">PDB {structure.pdbId || "—"} · AlphaFold {structure.alphafoldId || "—"}</div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <button onClick={() => navigateWithEntities("/structure", "open_in_structure", [entity])} className="px-2 py-1 rounded-lg border text-[10px]" style={{ borderColor: "var(--border)" }}>Open Structure</button>
                          <button onClick={() => navigateWithEntities("/design", "open_in_design", [entity])} className="px-2 py-1 rounded-lg border text-[10px]" style={{ borderColor: "var(--border)" }}>Send to Design</button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {activeMode === "enrichment" && (
              <div className="grid gap-4 lg:grid-cols-[1.1fr,1fr]">
                <div className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                  <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]"><Network size={16} /> Louvain communities</div>
                  <div className="mt-4 space-y-2">
                    {Array.isArray(result.enrichment.communities.communities) ? (result.enrichment.communities.communities as Array<Record<string, unknown>>).map((community) => (
                      <div key={String(community.id)} className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                        <div className="text-xs font-semibold">{String(community.label || community.id)}</div>
                        <div className="text-[10px] text-[var(--text-muted)] mt-1">size {String(community.size || 0)}</div>
                        <div className="text-[10px] text-[var(--text-secondary)] mt-1">{Array.isArray(community.nodes) ? (community.nodes as string[]).slice(0, 8).join(", ") : ""}</div>
                      </div>
                    )) : <div className="text-xs text-[var(--text-muted)]">No community output.</div>}
                  </div>
                </div>
                <div className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                  <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]"><Dna size={16} /> GO term enrichment</div>
                  <div className="mt-4 space-y-2 max-h-[420px] overflow-y-auto">
                    {result.enrichment.goTerms.map((term) => (
                      <div key={term.go_id} className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                        <div className="text-xs font-semibold">{term.name}</div>
                        <div className="text-[10px] text-[var(--text-muted)]">{term.go_id} · {term.aspect} · {term.hit_count} hits</div>
                        <div className="text-[10px] text-[var(--text-secondary)] mt-1">{term.genes.slice(0, 8).join(", ")}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeMode === "export" && (
              <div className="rounded-2xl border p-4 space-y-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                <div className="text-sm font-semibold text-[var(--text-primary)]">Export / Save Bundle</div>
                <div className="grid gap-3 md:grid-cols-3">
                  <button onClick={downloadJson} className="rounded-xl border px-4 py-4 text-left" style={{ borderColor: "var(--border)" }}>
                    <div className="text-xs font-semibold">JSON export</div>
                    <div className="text-[11px] text-[var(--text-muted)] mt-1">Download resolved entities, targets, graph, pathways, and enrichment output.</div>
                  </button>
                  <button onClick={saveBundle} className="rounded-xl border px-4 py-4 text-left" style={{ borderColor: "var(--border)" }}>
                    <div className="text-xs font-semibold">Save bundle</div>
                    <div className="text-[11px] text-[var(--text-muted)] mt-1">Persist this merged run as a contextual evidence bundle for later dossier work.</div>
                  </button>
                  <button onClick={() => navigateWithEntities("/graph", "open_in_graph", result.entities)} className="rounded-xl border px-4 py-4 text-left" style={{ borderColor: "var(--border)" }}>
                    <div className="text-xs font-semibold">Open canonical KG</div>
                    <div className="text-[11px] text-[var(--text-muted)] mt-1">Carry the current resolved entity context into the graph explorer.</div>
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}