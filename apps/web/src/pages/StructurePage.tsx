/** Structure Workbench — Phase T aligned shell with predicted-model parity. */

import { useState, useCallback, useEffect, useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Search,
  Box,
  Download,
  Loader2,
  ExternalLink,
  Target,
  Layers,
  FlaskConical,
  ArrowUpRight,
  Dna,
  Orbit,
} from "lucide-react";
import {
  structureSummaryAPI,
  structureAnnotationsAPI,
  structureCompareAPI,
  structureExperimentAPI,
  structureSequenceAPI,
  structureSearchAPI,
  structureBindingSitesAPI,
  structurePredictAPI,
  type StructureCompareResult,
  type StructureSummary,
  type StructureAnnotations,
  type ExperimentData,
  type SequenceData,
} from "@/lib/api";
import ConfidenceBar from "@/components/ui/ConfidenceBar";
import MolstarViewer from "@/components/viewer/MolstarViewer";
import StructureComparisonViewer from "@/components/viewer/StructureComparisonViewer";
import StateWrapper from "@/components/ui/StateWrapper";
import { useSetPageConfidence } from "@/lib/PageConfidenceContext";
import { persistCockpitHandoff, readCockpitHandoff } from "@/lib/canonicalProduct";
import type { ViewState } from "@/lib/types";

const TABS = [
  "Summary",
  "3D Structure",
  "Binding Sites",
  "Annotations",
  "Experiment",
  "Sequence",
  "Genome",
  "Comparison",
  "Versions",
] as const;

type Tab = (typeof TABS)[number];
type PredictionPayload = Record<string, unknown>;
type SequenceTrack = SequenceData & { residue_confidence?: number[] };
type MutationFeature = { name: string; range: string; type: string };
type StructurePocket = {
  _key?: string;
  pdb_id?: string;
  name?: string;
  source?: string;
  confidence?: number;
  residues?: unknown[];
  [key: string]: unknown;
};
type ConfidenceBand = {
  label: string;
  color: string;
  bg: string;
  border: string;
};
type ConfidenceRegion = ConfidenceBand & {
  start: number;
  end: number;
  average: number;
};

function normalizePlddtScore(score: number): number {
  if (!Number.isFinite(score)) return 0;
  return score <= 1 ? score * 100 : score;
}

function getConfidenceBand(score: number): ConfidenceBand {
  const normalized = normalizePlddtScore(score);
  if (normalized >= 90) {
    return {
      label: "Very high",
      color: "#0f3dbe",
      bg: "rgba(15, 61, 190, 0.08)",
      border: "rgba(15, 61, 190, 0.18)",
    };
  }
  if (normalized >= 70) {
    return {
      label: "High",
      color: "#1f8fd8",
      bg: "rgba(31, 143, 216, 0.09)",
      border: "rgba(31, 143, 216, 0.18)",
    };
  }
  if (normalized >= 50) {
    return {
      label: "Low",
      color: "#a16a06",
      bg: "rgba(245, 201, 56, 0.14)",
      border: "rgba(196, 136, 32, 0.24)",
    };
  }
  return {
    label: "Very low",
    color: "#c65a1e",
    bg: "rgba(246, 132, 62, 0.12)",
    border: "rgba(198, 90, 30, 0.24)",
  };
}

function buildConfidenceRegions(scores: number[]): ConfidenceRegion[] {
  if (!scores.length) return [];

  const normalized = scores.map(normalizePlddtScore);
  const regions: ConfidenceRegion[] = [];
  let startIndex = 0;
  let currentBand = getConfidenceBand(normalized[0]);
  let bucketValues = [normalized[0]];

  for (let index = 1; index < normalized.length; index += 1) {
    const nextBand = getConfidenceBand(normalized[index]);
    if (nextBand.label === currentBand.label) {
      bucketValues.push(normalized[index]);
      continue;
    }

    regions.push({
      ...currentBand,
      start: startIndex + 1,
      end: index,
      average: bucketValues.reduce((sum, value) => sum + value, 0) / bucketValues.length,
    });
    startIndex = index;
    currentBand = nextBand;
    bucketValues = [normalized[index]];
  }

  regions.push({
    ...currentBand,
    start: startIndex + 1,
    end: normalized.length,
    average: bucketValues.reduce((sum, value) => sum + value, 0) / bucketValues.length,
  });
  return regions;
}

function buildSequenceChunks(sequence: string, scores: number[], chunkSize = 12) {
  const normalized = scores.map(normalizePlddtScore);
  const chunks: Array<{
    key: string;
    start: number;
    end: number;
    text: string;
    avg: number;
    band: ConfidenceBand;
  }> = [];

  for (let index = 0; index < sequence.length; index += chunkSize) {
    const text = sequence.slice(index, index + chunkSize);
    const slice = normalized.slice(index, index + text.length);
    const avg = slice.length
      ? slice.reduce((sum, value) => sum + value, 0) / slice.length
      : 0;
    chunks.push({
      key: `${index}:${text}`,
      start: index + 1,
      end: index + text.length,
      text,
      avg,
      band: getConfidenceBand(avg),
    });
  }

  return chunks;
}

function isMutationFeature(feature: { type: string; name: string }): boolean {
  return /mutat|variant|substitution|conflict|natural variation/i.test(
    `${feature.type} ${feature.name}`,
  );
}

function extractMutationFeatures(sequences?: SequenceTrack[]): MutationFeature[] {
  if (!sequences?.length) return [];
  return sequences.flatMap((sequence) =>
    sequence.features
      .filter(isMutationFeature)
      .map((feature) => ({
        name: feature.name || feature.type || "Mutation",
        range:
          feature.start && feature.end
            ? feature.start === feature.end
              ? `${feature.start}`
              : `${feature.start}-${feature.end}`
            : "Position unavailable",
        type: feature.type || "feature",
      })),
  );
}

function formatCompactValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return String(value);
}

function looksLikeUniProt(value: string): boolean {
  return /^[A-Z][0-9][A-Z0-9]{3,8}[0-9]$/i.test(value.trim());
}

export default function StructurePage() {
  const navigate = useNavigate();
  const setConfidence = useSetPageConfidence();

  const [query, setQuery] = useState("");
  const [pdbId, setPdbId] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("Summary");
  const [source, setSource] = useState<"pdb" | "alphafold">("pdb");
  const [afTarget, setAfTarget] = useState("");
  const [comparePdb, setComparePdb] = useState("");
  const [selectedPocket, setSelectedPocket] = useState<StructurePocket | null>(null);
  const [predictedStructureUrl, setPredictedStructureUrl] = useState<string | null>(null);

  const searchMut = useMutation({
    mutationFn: (needle: string) => structureSearchAPI(needle),
  });

  const predictionQ = useQuery({
    queryKey: ["structurePrediction", afTarget],
    queryFn: () => structurePredictAPI(afTarget),
    enabled: source === "alphafold" && !!afTarget,
  });

  const predictionPayload = useMemo<PredictionPayload | null>(() => {
    return (predictionQ.data as PredictionPayload | undefined) ?? null;
  }, [predictionQ.data]);

  const predictionSource = typeof predictionPayload?.source === "string" ? predictionPayload.source : "";
  const resolvedPdbId =
    source === "pdb"
      ? pdbId
      : predictionSource === "rcsb"
        ? String(predictionPayload?.resolved_pdb_id || "")
        : "";

  const summaryQ = useQuery({
    queryKey: ["structureSummary", pdbId],
    queryFn: () => structureSummaryAPI(pdbId),
    enabled: source === "pdb" && !!pdbId,
  });

  const annotationsQ = useQuery({
    queryKey: ["structureAnnotations", resolvedPdbId],
    queryFn: () => structureAnnotationsAPI(resolvedPdbId),
    enabled: !!resolvedPdbId && activeTab === "Annotations",
  });

  const experimentQ = useQuery({
    queryKey: ["structureExperiment", resolvedPdbId],
    queryFn: () => structureExperimentAPI(resolvedPdbId),
    enabled: !!resolvedPdbId,
  });

  const sequenceQ = useQuery({
    queryKey: ["structureSequence", resolvedPdbId],
    queryFn: () => structureSequenceAPI(resolvedPdbId),
    enabled: !!resolvedPdbId,
  });

  const bindingTargetId = resolvedPdbId || afTarget;
  const bindingSitesQ = useQuery({
    queryKey: ["structureBindingSites", bindingTargetId],
    queryFn: () => structureBindingSitesAPI(bindingTargetId),
    enabled: !!bindingTargetId && activeTab === "Binding Sites",
  });

  const compareQ = useQuery({
    queryKey: ["structureCompare", comparePdb],
    queryFn: () => structureSummaryAPI(comparePdb),
    enabled: !!comparePdb && activeTab === "Comparison",
  });

  useEffect(() => {
    const pdbString = typeof predictionPayload?.pdb_string === "string" ? predictionPayload.pdb_string : "";
    if (!pdbString) {
      setPredictedStructureUrl(null);
      return;
    }
    const nextUrl = URL.createObjectURL(new Blob([pdbString], { type: "chemical/x-pdb" }));
    setPredictedStructureUrl(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [predictionPayload]);

  const predictionSummary = useMemo<StructureSummary | null>(() => {
    if (!predictionPayload) return null;
    if (predictionSource === "rcsb") {
      return predictionPayload as unknown as StructureSummary;
    }

    const sequence = typeof predictionPayload.sequence === "string" ? predictionPayload.sequence : "";
    const title = String(predictionPayload.title || predictionPayload.uniprot_id || afTarget || "Predicted structure");
    const organism = String(predictionPayload.organism || "Predicted model");
    const uniprotId = String(predictionPayload.uniprot_id || afTarget || "");
    return {
      pdb_id: uniprotId || String(predictionPayload.target_id || "prediction"),
      title,
      classification: predictionSource === "esm3" ? "ESM-3 predicted structure" : "AlphaFold predicted structure",
      organism,
      expression_system: "",
      method: predictionSource === "esm3" ? "ESM-3 Forge prediction" : "AlphaFold DB prediction",
      resolution: null,
      r_work: null,
      r_free: null,
      space_group: "Predicted",
      cell_dimensions: {},
      deposition_date: "",
      release_date: "",
      revision_date: "",
      primary_citation: {
        title: predictionSource === "esm3" ? "ESM-3 predicted model" : "AlphaFold DB predicted model",
        journal: predictionSource === "esm3" ? "EvolutionaryScale Forge" : "AlphaFold Protein Structure Database",
        year: null,
        doi: "",
        pmid: "",
      },
      macromolecules: [
        {
          entity_id: uniprotId || "A",
          type: "protein",
          chains: ["A"],
          length: sequence.length || (Array.isArray(predictionPayload.plddt) ? predictionPayload.plddt.length : null),
          sequence,
          organism,
          uniprot_ids: uniprotId ? [uniprotId] : [],
          gene_names: typeof predictionPayload.gene_symbol === "string" && predictionPayload.gene_symbol ? [predictionPayload.gene_symbol] : [],
          description: title,
        },
      ],
      ligands: [],
      assemblies: [
        {
          assembly_id: "predicted",
          polymer_entity_count: 1,
          oligomeric_state: "monomer",
          kind: predictionSource || "prediction",
        },
      ],
      revision_count: 1,
      revision_history: [
        {
          version: 1,
          date: "",
          type: predictionSource || "prediction",
        },
      ],
      downloads: (predictionPayload.downloads as Record<string, string> | undefined) || {},
      url: String(predictionPayload.url || ""),
    };
  }, [afTarget, predictionPayload, predictionSource]);

  const data = source === "pdb" ? summaryQ.data : predictionSummary;
  const isPredictedModel = source === "alphafold" && !!afTarget && predictionSource !== "rcsb";
  const structureSourceLabel =
    source === "pdb"
      ? "RCSB PDB"
      : predictionSource === "esm3"
        ? "ESM-3 Forge"
        : predictionSource === "alphafold"
          ? "AlphaFold DB"
          : predictionSource === "rcsb"
            ? "RCSB fallback"
            : "Predicted structure";

  const compareMetricsQ = useQuery({
    queryKey: ["structureCompareMetrics", data?.pdb_id, comparePdb, predictionSource],
    queryFn: () => {
      const primaryRequest =
        source === "pdb"
          ? { left_pdb_id: data?.pdb_id }
          : predictionSource === "esm3"
            ? {
                left_pdb_text:
                  typeof predictionPayload?.pdb_string === "string" ? predictionPayload.pdb_string : undefined,
              }
            : typeof predictionPayload?.model_url === "string"
              ? { left_structure_url: predictionPayload.model_url }
              : { left_pdb_id: data?.pdb_id };

      return structureCompareAPI({
        ...primaryRequest,
        right_pdb_id: comparePdb,
      });
    },
    enabled: !!comparePdb && !!data && activeTab === "Comparison",
  });

  const predictedTracks = useMemo<SequenceTrack[] | undefined>(() => {
    if (!isPredictedModel || !predictionPayload) return undefined;
    const sequence = typeof predictionPayload.sequence === "string" ? predictionPayload.sequence : "";
    const normalizedConfidence = Array.isArray(predictionPayload.plddt)
      ? predictionPayload.plddt
          .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
          .map(normalizePlddtScore)
      : [];

    const derivedSequence = sequence || (normalizedConfidence.length ? "X".repeat(normalizedConfidence.length) : "");
    const confidenceRegions = buildConfidenceRegions(normalizedConfidence);
    return [
      {
        entity_id: String(predictionPayload.uniprot_id || predictionPayload.target_id || afTarget || "prediction"),
        chains: ["A"],
        length: derivedSequence.length || null,
        sequence: derivedSequence,
        type: "predicted-model",
        residue_confidence: normalizedConfidence,
        features: confidenceRegions.map((region) => ({
          type: "pLDDT",
          name: `${region.label} confidence`,
          start: region.start,
          end: region.end,
        })),
      },
    ];
  }, [afTarget, isPredictedModel, predictionPayload]);

  const sequenceTracks = useMemo<SequenceTrack[] | undefined>(() => {
    if (isPredictedModel) return predictedTracks;
    return (sequenceQ.data as SequenceTrack[] | undefined) ?? undefined;
  }, [isPredictedModel, predictedTracks, sequenceQ.data]);

  const mutationFeatures = useMemo(() => extractMutationFeatures(sequenceTracks), [sequenceTracks]);
  const residueConfidence = sequenceTracks?.[0]?.residue_confidence ?? [];
  const confidenceRegions = useMemo(() => buildConfidenceRegions(residueConfidence), [residueConfidence]);
  const averageConfidence =
    residueConfidence.length > 0
      ? residueConfidence.reduce((sum, value) => sum + normalizePlddtScore(value), 0) / residueConfidence.length
      : null;

  useEffect(() => {
    if (!data && !afTarget && !pdbId) {
      setConfidence(null);
      return;
    }
    setConfidence({
      freshness: "current",
      sourceCount: 1,
      sourcesQueried: [structureSourceLabel],
      avgConfidence: averageConfidence ? averageConfidence / 100 : undefined,
    });
    return () => setConfidence(null);
  }, [averageConfidence, data, afTarget, pdbId, setConfidence, structureSourceLabel]);

  useEffect(() => {
    const payload = readCockpitHandoff();
    if (!payload || payload.targetRoute !== "/structure") return;
    const entity = payload.entities[0];
    const seededQuery =
      entity?.identifiers?.pdb_id ||
      entity?.identifiers?.uniprot_id ||
      entity?.entityName ||
      payload.query;
    if (!seededQuery) return;
    setQuery(seededQuery);
    if (/^\d[A-Za-z0-9]{3}$/.test(seededQuery)) {
      setPdbId(seededQuery.toUpperCase());
      setAfTarget("");
      setSource("pdb");
      return;
    }
    setPdbId("");
    setAfTarget(seededQuery);
    setSource("alphafold");
  }, []);

  useEffect(() => {
    setSelectedPocket(null);
  }, [pdbId, afTarget, source]);

  const handleSearch = useCallback(() => {
    const trimmed = query.trim();
    if (!trimmed) return;
    if (/^\d[A-Za-z0-9]{3}$/.test(trimmed)) {
      setPdbId(trimmed.toUpperCase());
      setAfTarget("");
      setSource("pdb");
      return;
    }
    if (source === "alphafold") {
      setPdbId("");
      setAfTarget(trimmed);
      return;
    }
    if (looksLikeUniProt(trimmed)) {
      setPdbId("");
      setAfTarget(trimmed.toUpperCase());
      setSource("alphafold");
      return;
    }
    searchMut.mutate(trimmed);
  }, [query, searchMut, source]);

  const openInDesign = useCallback(() => {
    const targetId = data?.pdb_id || afTarget;
    if (!targetId) return;
    persistCockpitHandoff({
      version: "phase0.v1",
      sourceModule: "structure",
      action: "open_in_design",
      targetRoute: "/design",
      query: targetId,
      createdAt: new Date().toISOString(),
      entities: [
        {
          entityId: targetId,
          entityType: "protein",
          entityName: data?.title || targetId,
          sourceCategory: structureSourceLabel,
          identifiers: {
            pdb_id: data?.pdb_id || resolvedPdbId || "",
            uniprot_id: looksLikeUniProt(afTarget) ? afTarget.toUpperCase() : "",
          },
          attributes: {
            bindingSite: selectedPocket,
            structureSource: predictionSource || source,
          },
        },
      ],
      provenance: [
        {
          source: structureSourceLabel,
          retrievedAt: new Date().toISOString(),
          confidence: averageConfidence,
        },
      ],
      metadata: {
        bindingSite: selectedPocket,
        fallbackChain: predictionPayload?.fallback_chain,
      },
    });
    navigate("/design");
  }, [
    afTarget,
    averageConfidence,
    data,
    navigate,
    predictionPayload,
    predictionSource,
    resolvedPdbId,
    selectedPocket,
    source,
    structureSourceLabel,
  ]);

  const openGraph = useCallback(() => {
    const seed = data?.macromolecules[0]?.gene_names[0] || afTarget || data?.pdb_id || data?.title || query;
    if (!seed) return;
    navigate(`/graph?q=${encodeURIComponent(seed)}`);
  }, [afTarget, data, navigate, query]);

  const openPathways = useCallback(() => {
    const seed = data?.macromolecules[0]?.gene_names[0] || afTarget || data?.pdb_id || query;
    if (!seed) return;
    navigate(`/pathways?q=${encodeURIComponent(seed)}`);
  }, [afTarget, data, navigate, query]);

  const openEntityIntelligence = useCallback(() => {
    const seed = data?.macromolecules[0]?.gene_names[0] || afTarget || data?.title || query;
    if (!seed) return;
    navigate(`/entity-intelligence?query=${encodeURIComponent(seed)}`);
  }, [afTarget, data, navigate, query]);

  const loading = searchMut.isPending || (source === "pdb" ? summaryQ.isLoading : predictionQ.isLoading);
  const errorMessage =
    (summaryQ.error as Error | null)?.message ||
    (predictionQ.error as Error | null)?.message ||
    (searchMut.error as Error | null)?.message ||
    "";
  const searchResults = ((searchMut.data as { result_set?: Array<Record<string, unknown>> } | undefined)?.result_set || []) as Array<Record<string, unknown>>;
  const hasSelection = !!data || !!afTarget || !!pdbId;
  const wrapperState: ViewState = loading ? "loading" : errorMessage ? "error" : "success";
  const primaryOverlayText =
    source === "alphafold" && predictionSource === "esm3" && typeof predictionPayload?.pdb_string === "string"
      ? predictionPayload.pdb_string
      : undefined;
  const primaryOverlayUrl =
    source === "alphafold" && predictionSource !== "esm3"
      ? typeof predictionPayload?.model_url === "string"
        ? predictionPayload.model_url
        : undefined
      : undefined;

  return (
    <StateWrapper
      state={wrapperState}
      moduleName="Structure Workbench"
      loadingMessage="Resolving structure sources and annotations..."
      errorInfo={errorMessage ? { code: "structure_lookup_failed", message: errorMessage } : undefined}
      onRetry={hasSelection ? handleSearch : undefined}
    >
      <div
        className="flex-1 overflow-y-auto"
        style={{
          background:
            "radial-gradient(circle at top, rgba(223, 231, 244, 0.45), transparent 42%), linear-gradient(180deg, #f7f3eb 0%, #f6f4ef 48%, #f1efe9 100%)",
        }}
      >
        <div className="mx-auto w-full max-w-[1680px] px-4 py-4">
          <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)_320px]">
            <aside
              className="overflow-hidden rounded-[26px] border shadow-sm"
              style={{ borderColor: "rgba(30, 41, 59, 0.08)", background: "rgba(255,255,255,0.84)", backdropFilter: "blur(10px)" }}
            >
              <div className="border-b px-4 py-4" style={{ borderColor: "var(--border)" }}>
                <div className="text-[10px] font-semibold uppercase tracking-[0.28em] text-[var(--text-muted)]">
                  Structure Workbench
                </div>
                <h2 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">Lookup</h2>
                <div className="relative mt-3">
                  <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                  <input
                    type="text"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    onKeyDown={(event) => event.key === "Enter" && handleSearch()}
                    placeholder="PDB ID, UniProt, gene, protein, organism..."
                    className="w-full rounded-xl border px-9 py-2 text-xs focus:outline-none focus:ring-2"
                    style={{ borderColor: "var(--border)", background: "rgba(248,246,240,0.8)", color: "var(--text-primary)", boxShadow: "inset 0 1px 0 rgba(255,255,255,0.4)" }}
                  />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setSource("pdb")}
                    className="rounded-xl px-3 py-2 text-[11px] font-medium transition-colors"
                    style={{
                      background: source === "pdb" ? "rgba(43, 78, 135, 0.12)" : "rgba(15, 23, 42, 0.03)",
                      color: source === "pdb" ? "#214b8e" : "var(--text-muted)",
                      border: `1px solid ${source === "pdb" ? "rgba(43, 78, 135, 0.18)" : "rgba(15, 23, 42, 0.05)"}`,
                    }}
                  >
                    RCSB PDB
                  </button>
                  <button
                    onClick={() => setSource("alphafold")}
                    className="rounded-xl px-3 py-2 text-[11px] font-medium transition-colors"
                    style={{
                      background: source === "alphafold" ? "rgba(114, 56, 209, 0.12)" : "rgba(15, 23, 42, 0.03)",
                      color: source === "alphafold" ? "#6d38c9" : "var(--text-muted)",
                      border: `1px solid ${source === "alphafold" ? "rgba(114, 56, 209, 0.18)" : "rgba(15, 23, 42, 0.05)"}`,
                    }}
                  >
                    ESM / AlphaFold
                  </button>
                </div>
                <button
                  onClick={handleSearch}
                  className="mt-3 w-full rounded-xl px-3 py-2 text-xs font-semibold text-white"
                  style={{ background: "linear-gradient(135deg, #2d4d87, #5c72b5)" }}
                >
                  Resolve structure
                </button>
              </div>

              <div className="max-h-[460px] overflow-y-auto px-3 py-3">
                {searchResults.length > 0 ? (
                  <div className="space-y-2">
                    {searchResults.map((result) => {
                      const identifier = String(result.identifier || result.id || "");
                      return (
                        <button
                          key={identifier}
                          onClick={() => {
                            setPdbId(identifier.toUpperCase());
                            setAfTarget("");
                            setSource("pdb");
                          }}
                          className="w-full rounded-2xl border px-3 py-3 text-left transition-colors"
                          style={{
                            borderColor: pdbId === identifier ? "rgba(43, 78, 135, 0.24)" : "rgba(15, 23, 42, 0.06)",
                            background: pdbId === identifier ? "rgba(43, 78, 135, 0.06)" : "rgba(248,246,240,0.72)",
                          }}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold text-[var(--text-primary)]">{identifier}</span>
                            <span className="text-[10px] text-[var(--text-muted)]">{formatCompactValue(result.score)}</span>
                          </div>
                          <div className="mt-1 text-[10px] text-[var(--text-muted)]">
                            {String(result.title || result.name || "RCSB result")}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-2xl border px-4 py-4 text-xs" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.7)" }}>
                    <div className="font-semibold text-[var(--text-primary)]">Reference shell cues</div>
                    <div className="mt-2 text-[var(--text-muted)]">
                      Compact left navigator, centered workbench canvas, restrained controls, inspector cards on the right.
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t px-4 py-4" style={{ borderColor: "var(--border)" }}>
                <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">Quality</div>
                {averageConfidence !== null ? (
                  <div className="mt-3 rounded-2xl border px-3 py-3" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.72)" }}>
                    <div className="mb-2 text-[11px] font-medium text-[var(--text-primary)]">Predicted confidence</div>
                    <ConfidenceBar value={Math.min(1, Math.max(0, averageConfidence / 100))} label="Average pLDDT" reasoning={`${structureSourceLabel} residue-confidence summary`} />
                  </div>
                ) : data ? (
                  <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-[11px]">
                    <span className="text-[var(--text-muted)]">Resolution</span>
                    <span className="font-medium text-[var(--text-primary)]">{data.resolution ? `${data.resolution} A` : "-"}</span>
                    <span className="text-[var(--text-muted)]">Method</span>
                    <span className="font-medium text-[var(--text-primary)]">{data.method || "-"}</span>
                    <span className="text-[var(--text-muted)]">R-free</span>
                    <span className="font-medium text-[var(--text-primary)]">{formatCompactValue(data.r_free)}</span>
                    <span className="text-[var(--text-muted)]">Chains</span>
                    <span className="font-medium text-[var(--text-primary)]">
                      {data.macromolecules.reduce((sum, molecule) => sum + molecule.chains.length, 0)}
                    </span>
                  </div>
                ) : (
                  <div className="mt-3 text-[11px] text-[var(--text-muted)]">
                    Search a structure to inspect experimental or predicted quality metrics.
                  </div>
                )}
              </div>
            </aside>

            <section
              className="min-w-0 overflow-hidden rounded-[30px] border shadow-sm"
              style={{ borderColor: "rgba(30, 41, 59, 0.08)", background: "rgba(255,253,248,0.94)" }}
            >
              <div
                className="border-b px-6 py-8"
                style={{
                  borderColor: "rgba(30, 41, 59, 0.08)",
                  background:
                    "radial-gradient(circle at top, rgba(220, 228, 245, 0.9), rgba(255,253,248,0.98) 58%)",
                }}
              >
                <div className="mx-auto max-w-[860px] text-center">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.34em] text-[var(--text-muted)]">
                    Structure / Fallback Chain
                  </div>
                  <h1 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-[var(--text-primary)]">
                    {data?.title || (source === "alphafold" && afTarget ? `Predicted model for ${afTarget}` : "Centered structure workbench")}
                  </h1>
                  <p className="mx-auto mt-3 max-w-[700px] text-sm leading-6 text-[var(--text-muted)]">
                    Video-parity shell: quiet left navigator, focused central canvas, rich right inspector. ESM resolves first, AlphaFold backs it up, RCSB closes the gap when prediction is unavailable.
                  </p>
                  <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
                    <span className="rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em]" style={{ borderColor: "rgba(43, 78, 135, 0.16)", color: "#214b8e", background: "rgba(43, 78, 135, 0.06)" }}>
                      {structureSourceLabel}
                    </span>
                    {(data?.pdb_id || afTarget) && (
                      <span className="rounded-full border px-3 py-1 text-[10px] font-medium" style={{ borderColor: "rgba(15, 23, 42, 0.08)", color: "var(--text-secondary)", background: "rgba(255,255,255,0.66)" }}>
                        {(data?.pdb_id || afTarget) as string}
                      </span>
                    )}
                    {data?.organism && (
                      <span className="rounded-full border px-3 py-1 text-[10px] font-medium" style={{ borderColor: "rgba(15, 23, 42, 0.08)", color: "var(--text-secondary)", background: "rgba(255,255,255,0.66)" }}>
                        {data.organism}
                      </span>
                    )}
                  </div>
                  {data && (
                    <div className="mt-6 grid gap-3 sm:grid-cols-4">
                      {[
                        { label: "Method", value: data.method || structureSourceLabel },
                        { label: "Resolution", value: data.resolution ? `${data.resolution} A` : "Predicted" },
                        { label: "Binding context", value: selectedPocket ? String(selectedPocket.pdb_id || selectedPocket.name || "Pocket selected") : "Choose a pocket" },
                        { label: "Evidence links", value: data.primary_citation.title ? "Reference ready" : "Source record ready" },
                      ].map((item) => (
                        <div key={item.label} className="rounded-2xl border px-4 py-3 text-left" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.74)" }}>
                          <div className="text-[9px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">{item.label}</div>
                          <div className="mt-1 text-sm font-medium text-[var(--text-primary)]">{item.value}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="border-b px-4 py-2" style={{ borderColor: "rgba(30, 41, 59, 0.08)", background: "rgba(255,255,255,0.62)" }}>
                <div className="flex flex-wrap gap-1">
                  {TABS.map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className="rounded-full px-4 py-2 text-[11px] font-medium transition-colors"
                      style={{
                        background: activeTab === tab ? "rgba(43, 78, 135, 0.1)" : "transparent",
                        color: activeTab === tab ? "#214b8e" : "var(--text-muted)",
                        border: `1px solid ${activeTab === tab ? "rgba(43, 78, 135, 0.18)" : "transparent"}`,
                      }}
                    >
                      {tab}
                    </button>
                  ))}
                </div>
              </div>

              <div className="min-h-[720px]">
                {!hasSelection && !loading ? (
                  <div className="flex min-h-[720px] items-center justify-center px-8 py-16">
                    <div className="max-w-[620px] text-center">
                      <Orbit size={48} className="mx-auto text-slate-400" />
                      <h2 className="mt-5 text-2xl font-semibold tracking-[-0.03em] text-[var(--text-primary)]">
                        Search experimental or predicted structures
                      </h2>
                      <p className="mx-auto mt-3 max-w-[560px] text-sm leading-6 text-[var(--text-muted)]">
                        Look up a PDB entry, UniProt accession, gene symbol, protein name, or organism. The workbench will choose the strongest source path and keep binding-site context ready for Design Studio.
                      </p>
                    </div>
                  </div>
                ) : !data && !loading ? (
                  <EmptyState text="No structure record resolved for the current query." />
                ) : data ? (
                  <div className="overflow-y-auto">
                    {activeTab === "Summary" && <SummaryTab data={data} sourceLabel={structureSourceLabel} />}
                    {activeTab === "3D Structure" && (
                      <Viewer3DTab
                        pdbId={data.pdb_id}
                        source={isPredictedModel ? "alphafold" : "pdb"}
                        structureUrl={
                          isPredictedModel
                            ? predictionSource === "esm3"
                              ? predictedStructureUrl || undefined
                              : typeof predictionPayload?.cif_url === "string"
                                ? predictionPayload.cif_url
                                : typeof predictionPayload?.model_url === "string"
                                  ? predictionPayload.model_url
                                  : undefined
                            : undefined
                        }
                        structureFormat={predictionSource === "esm3" ? "pdb" : "cif"}
                        plddt={residueConfidence.length > 0}
                      />
                    )}
                    {activeTab === "Binding Sites" && (
                      <BindingSitesTab
                        data={bindingSitesQ.data}
                        loading={bindingSitesQ.isLoading}
                        selectedPocket={selectedPocket}
                        onSelectPocket={setSelectedPocket}
                        onImport={openInDesign}
                      />
                    )}
                    {activeTab === "Annotations" && (
                      <AnnotationsTab data={annotationsQ.data} loading={annotationsQ.isLoading} predictedMode={isPredictedModel} />
                    )}
                    {activeTab === "Experiment" && (
                      <ExperimentTab data={experimentQ.data} loading={experimentQ.isLoading} predictedMode={isPredictedModel} />
                    )}
                    {activeTab === "Sequence" && (
                      <SequenceTab
                        sequences={sequenceTracks}
                        loading={!isPredictedModel && sequenceQ.isLoading}
                        predictedMode={isPredictedModel}
                      />
                    )}
                    {activeTab === "Genome" && (
                      <GenomeTab data={data} mutationFeatures={mutationFeatures} predictedMode={isPredictedModel} />
                    )}
                    {activeTab === "Comparison" && (
                      <ComparisonTab
                        primaryData={data}
                        primarySourceLabel={structureSourceLabel}
                        primaryStructureText={primaryOverlayText}
                        primaryStructureUrl={primaryOverlayUrl}
                        comparePdb={comparePdb}
                        setComparePdb={setComparePdb}
                        compareData={compareQ.data}
                        compareLoading={compareQ.isLoading || compareMetricsQ.isLoading}
                        compareMetrics={compareMetricsQ.data}
                      />
                    )}
                    {activeTab === "Versions" && <VersionsTab data={data} sourceLabel={structureSourceLabel} />}
                  </div>
                ) : null}
              </div>
            </section>

            <aside>
              <StructureInspectorPanel
                data={data}
                experiment={experimentQ.data}
                mutationFeatures={mutationFeatures}
                confidenceRegions={confidenceRegions}
                averageConfidence={averageConfidence}
                structureSourceLabel={structureSourceLabel}
                selectedPocket={selectedPocket}
                isPredictedModel={isPredictedModel}
                afTarget={afTarget}
                onOpenInDesign={openInDesign}
                onOpenGraph={openGraph}
                onOpenPathways={openPathways}
                onOpenEntityIntelligence={openEntityIntelligence}
              />
            </aside>
          </div>
        </div>
      </div>
    </StateWrapper>
  );
}

function StructureInspectorPanel({
  data,
  experiment,
  mutationFeatures,
  confidenceRegions,
  averageConfidence,
  structureSourceLabel,
  selectedPocket,
  isPredictedModel,
  afTarget,
  onOpenInDesign,
  onOpenGraph,
  onOpenPathways,
  onOpenEntityIntelligence,
}: {
  data: StructureSummary | null | undefined;
  experiment?: ExperimentData;
  mutationFeatures: MutationFeature[];
  confidenceRegions: ConfidenceRegion[];
  averageConfidence: number | null;
  structureSourceLabel: string;
  selectedPocket: StructurePocket | null;
  isPredictedModel: boolean;
  afTarget: string;
  onOpenInDesign: () => void;
  onOpenGraph: () => void;
  onOpenPathways: () => void;
  onOpenEntityIntelligence: () => void;
}) {
  const externalUrl = isPredictedModel
    ? `https://alphafold.ebi.ac.uk/entry/${encodeURIComponent(afTarget)}`
    : data?.url || "";
  const chains = data?.macromolecules.flatMap((molecule) => molecule.chains) || [];

  return (
    <div className="space-y-4">
      <div
        className="overflow-hidden rounded-[26px] border shadow-sm"
        style={{ borderColor: "rgba(30, 41, 59, 0.08)", background: "rgba(255,255,255,0.84)", backdropFilter: "blur(10px)" }}
      >
        <div className="border-b px-4 py-4" style={{ borderColor: "var(--border)" }}>
          <div className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[var(--text-muted)]">Inspector</div>
          <h3 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">Actions and provenance</h3>
        </div>
        <div className="space-y-2 px-4 py-4">
          <ActionButton icon={<ArrowUpRight size={13} />} label="Import to Design Studio" detail={selectedPocket ? "Binding site attached" : "Attach pocket if selected"} onClick={onOpenInDesign} />
          <ActionButton icon={<Layers size={13} />} label="Open in Knowledge Graph" detail="Cross-link protein, gene, pathway, disease context" onClick={onOpenGraph} />
          <ActionButton icon={<Dna size={13} />} label="Run Entity Intelligence" detail="Send canonical target context into merged discovery flow" onClick={onOpenEntityIntelligence} />
          <ActionButton icon={<Target size={13} />} label="Explore pathways" detail="Follow pathway overlays and disease context" onClick={onOpenPathways} />
        </div>
      </div>

      <InspectorCard title="Experimental details" subtitle={structureSourceLabel}>
        {averageConfidence !== null ? (
          <div className="space-y-3">
            <ConfidenceBar value={Math.min(1, Math.max(0, averageConfidence / 100))} label="Average pLDDT" reasoning="Per-residue confidence parsed from the active predicted model." />
            <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-[11px]">
              <span className="text-[var(--text-muted)]">Model source</span>
              <span className="font-medium text-[var(--text-primary)]">{structureSourceLabel}</span>
              <span className="text-[var(--text-muted)]">Confidence</span>
              <span className="font-medium text-[var(--text-primary)]">{averageConfidence.toFixed(1)}</span>
              <span className="text-[var(--text-muted)]">Pocket</span>
              <span className="font-medium text-[var(--text-primary)]">{selectedPocket ? String(selectedPocket.pdb_id || selectedPocket.name || "Selected") : "Not selected"}</span>
            </div>
          </div>
        ) : data ? (
          <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-[11px]">
            <span className="text-[var(--text-muted)]">Method</span>
            <span className="font-medium text-[var(--text-primary)]">{data.method || "-"}</span>
            <span className="text-[var(--text-muted)]">Resolution</span>
            <span className="font-medium text-[var(--text-primary)]">{data.resolution ? `${data.resolution} A` : "-"}</span>
            <span className="text-[var(--text-muted)]">R-work / R-free</span>
            <span className="font-medium text-[var(--text-primary)]">{formatCompactValue(data.r_work)} / {formatCompactValue(data.r_free)}</span>
            <span className="text-[var(--text-muted)]">Space group</span>
            <span className="font-medium text-[var(--text-primary)]">{data.space_group || "-"}</span>
            <span className="text-[var(--text-muted)]">Organism</span>
            <span className="font-medium text-[var(--text-primary)]">{data.organism || "-"}</span>
          </div>
        ) : (
          <div className="text-[11px] text-[var(--text-muted)]">Resolve a structure to inspect experiment metadata.</div>
        )}
        {experiment?.software?.length ? (
          <div className="mt-3 rounded-2xl border px-3 py-3" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.74)" }}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Software</div>
            <div className="mt-2 space-y-1 text-[11px] text-[var(--text-secondary)]">
              {experiment.software.slice(0, 4).map((item) => (
                <div key={`${item.name}:${item.version}`} className="flex items-center justify-between gap-3">
                  <span>{item.name}</span>
                  <span className="text-[var(--text-muted)]">{item.version || item.classification || "-"}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </InspectorCard>

      <InspectorCard title="Chains and ligands" subtitle={data?.classification || "Structure composition"}>
        <div className="space-y-3 text-[11px]">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Chains</div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {chains.length ? chains.map((chain) => (
                <span key={chain} className="rounded-full border px-2.5 py-1" style={{ borderColor: "rgba(15, 23, 42, 0.08)", background: "rgba(248,246,240,0.74)", color: "var(--text-secondary)" }}>
                  Chain {chain}
                </span>
              )) : <span className="text-[var(--text-muted)]">No chain metadata available</span>}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Ligands</div>
            <div className="mt-2 space-y-2">
              {data?.ligands.length ? data.ligands.slice(0, 6).map((ligand) => (
                <a
                  key={ligand.comp_id}
                  href={`https://www.rcsb.org/ligand/${ligand.comp_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between rounded-2xl border px-3 py-2 text-[11px]"
                  style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.74)", color: "var(--text-secondary)" }}
                >
                  <span>
                    <span className="font-semibold text-[var(--text-primary)]">{ligand.comp_id}</span>
                    <span className="ml-2 text-[var(--text-muted)]">{ligand.name}</span>
                  </span>
                  <ExternalLink size={11} />
                </a>
              )) : <div className="text-[var(--text-muted)]">No ligand annotations for the active structure.</div>}
            </div>
          </div>
        </div>
      </InspectorCard>

      <InspectorCard title="References and mutations" subtitle="Scientific decision support">
        <div className="space-y-3 text-[11px]">
          {data?.primary_citation?.title ? (
            <div className="rounded-2xl border px-3 py-3" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.74)" }}>
              <div className="font-semibold text-[var(--text-primary)]">{data.primary_citation.title}</div>
              <div className="mt-1 text-[var(--text-muted)]">{data.primary_citation.journal || structureSourceLabel}{data.primary_citation.year ? ` (${data.primary_citation.year})` : ""}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {data.primary_citation.doi ? (
                  <a href={`https://doi.org/${data.primary_citation.doi}`} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)]">
                    DOI
                  </a>
                ) : null}
                {data.primary_citation.pmid ? (
                  <a href={`https://pubmed.ncbi.nlm.nih.gov/${data.primary_citation.pmid}`} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)]">
                    PubMed
                  </a>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="text-[var(--text-muted)]">Predicted structures keep source provenance even when experimental citations are unavailable.</div>
          )}
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Mutation tracks</div>
            <div className="mt-2 space-y-2">
              {mutationFeatures.length ? mutationFeatures.slice(0, 6).map((feature) => (
                <div key={`${feature.type}:${feature.range}:${feature.name}`} className="rounded-2xl border px-3 py-2" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.74)" }}>
                  <div className="font-medium text-[var(--text-primary)]">{feature.name}</div>
                  <div className="mt-1 text-[var(--text-muted)]">{feature.range} · {feature.type}</div>
                </div>
              )) : <div className="text-[var(--text-muted)]">No curated mutation annotations in the active chain features.</div>}
            </div>
          </div>
        </div>
      </InspectorCard>

      {confidenceRegions.length > 0 && (
        <InspectorCard title="pLDDT regions" subtitle="Residue-confidence highlighting">
          <div className="space-y-2">
            {confidenceRegions.map((region) => (
              <div key={`${region.start}-${region.end}-${region.label}`} className="rounded-2xl border px-3 py-3" style={{ borderColor: region.border, background: region.bg }}>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[11px] font-semibold" style={{ color: region.color }}>
                    {region.label}
                  </span>
                  <span className="text-[10px] text-[var(--text-muted)]">{region.average.toFixed(1)}</span>
                </div>
                <div className="mt-1 text-[11px] text-[var(--text-secondary)]">Residues {region.start}-{region.end}</div>
              </div>
            ))}
          </div>
        </InspectorCard>
      )}

      {data && (
        <InspectorCard title="Downloads" subtitle="Primary source artifacts">
          <div className="space-y-2">
            {Object.entries(data.downloads || {}).map(([label, url]) => (
              <a
                key={label}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between rounded-2xl border px-3 py-2 text-[11px]"
                style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.74)", color: "var(--text-secondary)" }}
              >
                <span className="flex items-center gap-2">
                  <Download size={12} />
                  {label.replace(/_/g, " ")}
                </span>
                <ExternalLink size={11} />
              </a>
            ))}
            {externalUrl ? (
              <a href={externalUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[11px] text-[var(--accent)]">
                Open source record <ExternalLink size={11} />
              </a>
            ) : null}
          </div>
        </InspectorCard>
      )}
    </div>
  );
}

function InspectorCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div
      className="overflow-hidden rounded-[26px] border shadow-sm"
      style={{ borderColor: "rgba(30, 41, 59, 0.08)", background: "rgba(255,255,255,0.84)", backdropFilter: "blur(10px)" }}
    >
      <div className="border-b px-4 py-4" style={{ borderColor: "var(--border)" }}>
        <div className="text-sm font-semibold text-[var(--text-primary)]">{title}</div>
        {subtitle ? <div className="mt-1 text-[11px] text-[var(--text-muted)]">{subtitle}</div> : null}
      </div>
      <div className="px-4 py-4">{children}</div>
    </div>
  );
}

function ActionButton({ icon, label, detail, onClick }: { icon: React.ReactNode; label: string; detail: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-start gap-3 rounded-2xl border px-3 py-3 text-left transition-colors"
      style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.74)" }}
    >
      <span className="mt-0.5 text-[var(--accent)]">{icon}</span>
      <span>
        <span className="block text-[11px] font-semibold text-[var(--text-primary)]">{label}</span>
        <span className="mt-1 block text-[10px] leading-4 text-[var(--text-muted)]">{detail}</span>
      </span>
    </button>
  );
}

function SummaryTab({ data, sourceLabel }: { data: StructureSummary; sourceLabel: string }) {
  return (
    <div className="px-6 py-6">
      <div className="mx-auto max-w-[980px] space-y-6">
        <div className="grid gap-3 sm:grid-cols-5">
          {[
            { label: "Method", value: data.method || sourceLabel },
            { label: "Resolution", value: data.resolution ? `${data.resolution} A` : "Predicted" },
            { label: "R-work / R-free", value: `${formatCompactValue(data.r_work)} / ${formatCompactValue(data.r_free)}` },
            { label: "Space group", value: data.space_group || "-" },
            { label: "Deposited", value: data.deposition_date?.slice(0, 10) || "-" },
          ].map((metric) => (
            <div key={metric.label} className="rounded-3xl border px-4 py-4" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
              <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">{metric.label}</div>
              <div className="mt-2 text-sm font-medium text-[var(--text-primary)]">{metric.value}</div>
            </div>
          ))}
        </div>

        {data.primary_citation.title ? (
          <div className="rounded-[28px] border px-5 py-5" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">Primary citation</div>
            <div className="mt-2 text-base font-medium text-[var(--text-primary)]">{data.primary_citation.title}</div>
            <div className="mt-1 text-sm text-[var(--text-muted)]">{data.primary_citation.journal || sourceLabel}{data.primary_citation.year ? ` (${data.primary_citation.year})` : ""}</div>
            <div className="mt-3 flex flex-wrap gap-3 text-[11px]">
              {data.primary_citation.doi ? <a href={`https://doi.org/${data.primary_citation.doi}`} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)]">DOI</a> : null}
              {data.primary_citation.pmid ? <a href={`https://pubmed.ncbi.nlm.nih.gov/${data.primary_citation.pmid}`} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)]">PubMed</a> : null}
            </div>
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <div className="rounded-[28px] border px-5 py-5" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">Chains and macromolecules</div>
            <div className="mt-4 overflow-hidden rounded-3xl border" style={{ borderColor: "rgba(15, 23, 42, 0.06)" }}>
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ background: "rgba(248,246,240,0.9)" }}>
                    {[
                      "Entity",
                      "Chains",
                      "Length",
                      "Organism",
                      "UniProt",
                    ].map((header) => (
                      <th key={header} className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.macromolecules.map((molecule) => (
                    <tr key={molecule.entity_id} className="border-t" style={{ borderColor: "rgba(15, 23, 42, 0.06)" }}>
                      <td className="px-3 py-3 font-medium text-[var(--text-primary)]">{molecule.entity_id}</td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">{molecule.chains.join(", ") || "-"}</td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">{formatCompactValue(molecule.length)}</td>
                      <td className="px-3 py-3 text-[var(--text-muted)]">{molecule.organism || "-"}</td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">
                        {molecule.uniprot_ids.length ? molecule.uniprot_ids.join(", ") : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-[28px] border px-5 py-5" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">Ligands and assemblies</div>
            <div className="mt-4 space-y-3">
              {data.ligands.length ? data.ligands.map((ligand) => (
                <div key={ligand.comp_id} className="rounded-2xl border px-3 py-3" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.82)" }}>
                  <div className="text-xs font-semibold text-[var(--text-primary)]">{ligand.comp_id}</div>
                  <div className="mt-1 text-[11px] text-[var(--text-muted)]">{ligand.name || "Ligand"}</div>
                </div>
              )) : <div className="text-[11px] text-[var(--text-muted)]">No ligand metadata for this structure.</div>}

              {data.assemblies.length ? (
                <div className="rounded-2xl border px-3 py-3" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.82)" }}>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Assemblies</div>
                  <div className="mt-2 space-y-2 text-[11px] text-[var(--text-secondary)]">
                    {data.assemblies.map((assembly) => (
                      <div key={assembly.assembly_id} className="flex items-center justify-between gap-3">
                        <span>Assembly {assembly.assembly_id}</span>
                        <span className="text-[var(--text-muted)]">{assembly.oligomeric_state || assembly.kind || "-"}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Viewer3DTab({
  pdbId,
  source,
  structureUrl,
  structureFormat,
  plddt,
}: {
  pdbId: string;
  source: "pdb" | "alphafold";
  structureUrl?: string;
  structureFormat?: "pdb" | "cif";
  plddt: boolean;
}) {
  return (
    <div className="px-6 py-6">
      <div className="mx-auto max-w-[1180px] overflow-hidden rounded-[30px] border" style={{ borderColor: "rgba(15, 23, 42, 0.08)", background: "#0f172a" }}>
        <MolstarViewer
          pdbId={pdbId}
          source={source === "alphafold" ? "alphafold" : "rcsb"}
          structureUrl={structureUrl}
          structureFormat={structureFormat}
          plddt={plddt}
        />
      </div>
    </div>
  );
}

function AnnotationsTab({
  data,
  loading,
  predictedMode,
}: {
  data?: StructureAnnotations;
  loading: boolean;
  predictedMode: boolean;
}) {
  if (loading) return <CenterLoader />;
  if (!data && predictedMode) {
    return <EmptyState text="Predicted models do not expose full experimental annotation adapters. Canonical sequence, pLDDT, and source provenance remain available." />;
  }
  if (!data) return <EmptyState text="No annotation data" />;
  return (
    <div className="px-6 py-6">
      <div className="mx-auto max-w-[980px] space-y-5">
        <AnnotationSection title="Pfam domains" items={data.pfam} />
        <AnnotationSection title="InterPro" items={data.interpro} />
        <AnnotationSection title="Gene Ontology" items={data.go} />
        <AnnotationSection title="EC numbers" items={data.ec} />
      </div>
    </div>
  );
}

function AnnotationSection({ title, items }: { title: string; items: Array<{ id: string; name: string }> }) {
  if (!items.length) return null;
  return (
    <div className="rounded-[28px] border px-5 py-5" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">{title}</div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <div key={`${item.id}:${item.name}`} className="rounded-2xl border px-3 py-3" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.82)" }}>
            <div className="text-xs font-semibold text-[var(--text-primary)]">{item.id}</div>
            <div className="mt-1 text-[11px] text-[var(--text-muted)]">{item.name}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ExperimentTab({
  data,
  loading,
  predictedMode,
}: {
  data?: ExperimentData;
  loading: boolean;
  predictedMode: boolean;
}) {
  if (loading) return <CenterLoader />;
  if (!data && predictedMode) {
    return <EmptyState text="Predicted structures are surfaced truthfully: no crystal-growth or refinement records exist, but provenance and confidence tracks remain visible." />;
  }
  if (!data) return <EmptyState text="No experiment data" />;
  return (
    <div className="px-6 py-6">
      <div className="mx-auto max-w-[980px] space-y-5">
        <PropGrid title="Data collection" data={data.data_collection} />
        <PropGrid title="Crystal growth" data={data.crystal_growth} />
        <PropGrid title="Refinement" data={data.refinement} />
        <PropGrid title="Unit cell" data={data.cell} />
      </div>
    </div>
  );
}

function PropGrid({ title, data }: { title: string; data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([, value]) => value !== null && value !== undefined && value !== "");
  if (!entries.length) return null;
  return (
    <div className="rounded-[28px] border px-5 py-5" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">{title}</div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {entries.map(([key, value]) => (
          <div key={key} className="flex items-center justify-between rounded-2xl border px-3 py-3 text-[11px]" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.82)" }}>
            <span className="text-[var(--text-muted)]">{key.replace(/_/g, " ")}</span>
            <span className="font-medium text-[var(--text-primary)]">{formatCompactValue(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SequenceTab({
  sequences,
  loading,
  predictedMode,
}: {
  sequences?: SequenceTrack[];
  loading: boolean;
  predictedMode: boolean;
}) {
  if (loading) return <CenterLoader />;
  if (!sequences?.length) return <EmptyState text="No sequence data" />;

  return (
    <div className="px-6 py-6">
      <div className="mx-auto max-w-[980px] space-y-5">
        {sequences.map((sequence) => {
          const chunks = sequence.residue_confidence?.length
            ? buildSequenceChunks(sequence.sequence, sequence.residue_confidence)
            : [];
          const regions = sequence.residue_confidence?.length
            ? buildConfidenceRegions(sequence.residue_confidence)
            : [];
          return (
            <div key={sequence.entity_id} className="rounded-[28px] border px-5 py-5" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-[var(--text-primary)]">{sequence.entity_id}</span>
                <span className="rounded-full border px-2.5 py-1 text-[10px]" style={{ borderColor: "rgba(15, 23, 42, 0.08)", background: "rgba(248,246,240,0.74)", color: "var(--text-secondary)" }}>
                  Chains: {sequence.chains.join(", ") || "A"}
                </span>
                <span className="rounded-full border px-2.5 py-1 text-[10px]" style={{ borderColor: "rgba(15, 23, 42, 0.08)", background: "rgba(248,246,240,0.74)", color: "var(--text-secondary)" }}>
                  {sequence.length || sequence.sequence.length} residues
                </span>
                <span className="rounded-full border px-2.5 py-1 text-[10px]" style={{ borderColor: "rgba(15, 23, 42, 0.08)", background: predictedMode ? "rgba(33,75,142,0.07)" : "rgba(248,246,240,0.74)", color: predictedMode ? "#214b8e" : "var(--text-secondary)" }}>
                  {predictedMode ? "Predicted model" : sequence.type}
                </span>
              </div>

              {chunks.length ? (
                <>
                  <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                    {chunks.map((chunk) => (
                      <div key={chunk.key} className="rounded-2xl border px-3 py-3" style={{ borderColor: chunk.band.border, background: chunk.band.bg }}>
                        <div className="flex items-center justify-between gap-2 text-[9px] uppercase tracking-[0.14em]" style={{ color: chunk.band.color }}>
                          <span>{chunk.band.label}</span>
                          <span>{chunk.start}-{chunk.end}</span>
                        </div>
                        <div className="mt-2 break-all font-mono text-[11px] leading-5 text-[var(--text-primary)]">{chunk.text}</div>
                        <div className="mt-2 text-[10px] text-[var(--text-muted)]">Avg pLDDT {chunk.avg.toFixed(1)}</div>
                      </div>
                    ))}
                  </div>
                  {regions.length ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {regions.map((region) => (
                        <span key={`${region.start}-${region.end}-${region.label}`} className="rounded-full border px-3 py-1 text-[10px] font-medium" style={{ borderColor: region.border, background: region.bg, color: region.color }}>
                          {region.label}: {region.start}-{region.end}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <pre className="mt-4 overflow-x-auto rounded-3xl border p-4 font-mono text-[11px] leading-6 text-[var(--text-secondary)]" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.82)" }}>
                  {sequence.sequence}
                </pre>
              )}

              {sequence.features.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {sequence.features.map((feature, index) => (
                    <span key={`${feature.type}:${feature.name}:${index}`} className="rounded-full border px-3 py-1 text-[10px]" style={{ borderColor: "rgba(43, 78, 135, 0.14)", background: "rgba(43, 78, 135, 0.06)", color: "#214b8e" }}>
                      {feature.name || feature.type}
                      {feature.start && feature.end ? ` (${feature.start}-${feature.end})` : ""}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GenomeTab({
  data,
  mutationFeatures,
  predictedMode,
}: {
  data: StructureSummary;
  mutationFeatures: MutationFeature[];
  predictedMode: boolean;
}) {
  const uniprotIds = data.macromolecules.flatMap((molecule) => molecule.uniprot_ids).filter(Boolean);
  const geneNames = data.macromolecules.flatMap((molecule) => molecule.gene_names).filter(Boolean);
  const primaryGene = geneNames[0] || "";
  const primaryUniProt = uniprotIds[0] || "";

  return (
    <div className="px-6 py-6">
      <div className="mx-auto max-w-[980px] rounded-[28px] border px-5 py-5" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
        <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">Genome links</div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border px-4 py-4" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.82)" }}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Canonical IDs</div>
            <div className="mt-3 space-y-2 text-[11px] text-[var(--text-secondary)]">
              <div>Genes: {geneNames.length ? geneNames.join(", ") : "No gene mapping"}</div>
              <div>UniProt: {uniprotIds.length ? uniprotIds.join(", ") : "No UniProt cross-link"}</div>
              <div>Mode: {predictedMode ? "Predicted structure cross-link" : "Experimental structure cross-link"}</div>
            </div>
          </div>
          <div className="rounded-2xl border px-4 py-4" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.82)" }}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">External genome browsers</div>
            <div className="mt-3 flex flex-wrap gap-3 text-[11px]">
              {primaryGene ? (
                <a href={`https://www.genecards.org/cgi-bin/carddisp.pl?gene=${encodeURIComponent(primaryGene)}`} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)]">
                  GeneCards
                </a>
              ) : null}
              {primaryUniProt ? (
                <a href={`https://www.ensembl.org/Multi/Search/Results?q=${encodeURIComponent(primaryUniProt)}`} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)]">
                  Ensembl
                </a>
              ) : null}
              {primaryUniProt ? (
                <a href={`https://www.uniprot.org/uniprotkb/${encodeURIComponent(primaryUniProt)}/entry`} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)]">
                  UniProt locus
                </a>
              ) : null}
            </div>
            <div className="mt-3 text-[11px] text-[var(--text-muted)]">
              Variant and mutation context stays aligned with Sequence and Inspector cards; external browsers provide exon and locus depth when needed.
            </div>
          </div>
        </div>
        {mutationFeatures.length ? (
          <div className="mt-5 rounded-2xl border px-4 py-4" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(248,246,240,0.82)" }}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Mutation summary</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {mutationFeatures.map((feature) => (
                <span key={`${feature.type}:${feature.range}:${feature.name}`} className="rounded-full border px-3 py-1 text-[10px]" style={{ borderColor: "rgba(15, 23, 42, 0.08)", background: "white", color: "var(--text-secondary)" }}>
                  {feature.name} · {feature.range}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function VersionsTab({ data, sourceLabel }: { data: StructureSummary; sourceLabel: string }) {
  return (
    <div className="px-6 py-6">
      <div className="mx-auto max-w-[980px] rounded-[28px] border px-5 py-5" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">Versions and provenance</div>
            <div className="mt-1 text-sm font-medium text-[var(--text-primary)]">{data.revision_count} tracked revision(s)</div>
          </div>
          <span className="rounded-full border px-3 py-1 text-[10px] font-medium" style={{ borderColor: "rgba(15, 23, 42, 0.08)", background: "rgba(248,246,240,0.74)", color: "var(--text-secondary)" }}>
            {sourceLabel}
          </span>
        </div>
        <div className="mt-4 overflow-hidden rounded-3xl border" style={{ borderColor: "rgba(15, 23, 42, 0.06)" }}>
          <table className="w-full text-xs">
            <thead>
              <tr style={{ background: "rgba(248,246,240,0.9)" }}>
                {[
                  "Version",
                  "Date",
                  "Type",
                ].map((header) => (
                  <th key={header} className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.revision_history.map((revision, index) => (
                <tr key={`${revision.version}:${revision.date}:${index}`} className="border-t" style={{ borderColor: "rgba(15, 23, 42, 0.06)" }}>
                  <td className="px-3 py-3 font-medium text-[var(--text-primary)]">{formatCompactValue(revision.version)}</td>
                  <td className="px-3 py-3 text-[var(--text-secondary)]">{revision.date?.slice(0, 10) || "-"}</td>
                  <td className="px-3 py-3 text-[var(--text-muted)]">{revision.type || sourceLabel}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function BindingSitesTab({
  data,
  loading,
  selectedPocket,
  onSelectPocket,
  onImport,
}: {
  data: Record<string, unknown> | undefined;
  loading: boolean;
  selectedPocket: StructurePocket | null;
  onSelectPocket: (pocket: StructurePocket) => void;
  onImport: () => void;
}) {
  if (loading) return <CenterLoader />;
  const pockets: StructurePocket[] = (((data?.pockets as Array<Record<string, unknown>> | undefined) || []).map((pocket, index) => ({
    ...pocket,
    _key: `${String(pocket.source || "pocket")}:${String(pocket.pdb_id || index)}`,
  })) as StructurePocket[]).sort((a, b) => {
    // Sort by druggability_score descending, then by confidence descending
    const scoreA = typeof a.druggability_score === "number" ? a.druggability_score : typeof a.confidence === "number" ? a.confidence : 0;
    const scoreB = typeof b.druggability_score === "number" ? b.druggability_score : typeof b.confidence === "number" ? b.confidence : 0;
    return scoreB - scoreA;
  });

  return (
    <div className="px-6 py-6">
      <div className="mx-auto max-w-[980px] space-y-5">
        <div className="rounded-[28px] border px-5 py-5" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
          <div className="flex items-center gap-2">
            <Target size={15} className="text-[var(--accent)]" />
            <div className="text-sm font-semibold text-[var(--text-primary)]">Binding sites and pocket import</div>
          </div>
          <div className="mt-2 text-[11px] leading-5 text-[var(--text-muted)]">
            Select a pocket, inspect confidence and source, then import the active binding-site context directly into Design Studio.
          </div>
        </div>

        {pockets.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {pockets.map((pocket) => {
              const confidence = typeof pocket.confidence === "number" ? pocket.confidence : null;
              const isSelected = selectedPocket?._key === pocket._key;
              return (
                <button
                  key={String(pocket._key)}
                  type="button"
                  onClick={() => onSelectPocket(pocket)}
                  className="rounded-[24px] border px-4 py-4 text-left transition-colors"
                  style={{
                    borderColor: isSelected ? "rgba(43, 78, 135, 0.24)" : "rgba(15, 23, 42, 0.06)",
                    background: isSelected ? "rgba(43, 78, 135, 0.06)" : "rgba(255,255,255,0.72)",
                  }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-xs font-semibold text-[var(--text-primary)]">{String(pocket.pdb_id || pocket.name || "Pocket")}</div>
                      <div className="mt-1 text-[10px] text-[var(--text-muted)]">{String(pocket.source || "Predicted site")}</div>
                    </div>
                    <div className="text-right">
                      {typeof pocket.druggability_score === "number" ? (
                        <div className="text-[11px] font-semibold" style={{ color: pocket.druggability_score >= 0.7 ? "#10b981" : pocket.druggability_score >= 0.4 ? "#f59e0b" : "#ef4444" }}>
                          Drug. {(pocket.druggability_score as number * 100).toFixed(0)}%
                        </div>
                      ) : confidence !== null ? (
                        <span className="text-[10px] font-medium text-[var(--text-secondary)]">{Math.round(confidence * 100)}%</span>
                      ) : null}
                    </div>
                  </div>
                  {/* Druggability score bar */}
                  {typeof pocket.druggability_score === "number" && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-[9px] text-[var(--text-muted)] w-16">Druggability</span>
                      <div className="flex-1 h-1.5 rounded-full" style={{ background: "var(--border)" }}>
                        <div className="h-1.5 rounded-full" style={{ width: `${Math.round((pocket.druggability_score as number) * 100)}%`, background: (pocket.druggability_score as number) >= 0.7 ? "#10b981" : (pocket.druggability_score as number) >= 0.4 ? "#f59e0b" : "#ef4444" }} />
                      </div>
                    </div>
                  )}
                  {/* Volume and center coordinates */}
                  <div className="mt-2 flex flex-wrap gap-3 text-[9px] text-[var(--text-muted)]">
                    {typeof pocket.volume === "number" && <span>Vol: {(pocket.volume as number).toFixed(1)} Å³</span>}
                    {Array.isArray(pocket.center) && (pocket.center as number[]).length === 3 && (
                      <span>Center: [{(pocket.center as number[]).map((c: number) => c.toFixed(1)).join(", ")}]</span>
                    )}
                    {typeof pocket.source === "string" && <span>Source: {pocket.source}</span>}
                  </div>
                  {Array.isArray(pocket.residues) && pocket.residues.length ? (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {pocket.residues.slice(0, 12).map((residue: unknown, index: number) => (
                        <span key={`${pocket._key}:${index}`} className="rounded-full border px-2 py-1 text-[9px]" style={{ borderColor: "rgba(15, 23, 42, 0.08)", background: "rgba(248,246,240,0.74)", color: "var(--text-secondary)" }}>
                          {String(residue)}
                        </span>
                      ))}
                      {pocket.residues.length > 12 && <span className="text-[9px] text-[var(--text-muted)]">+{pocket.residues.length - 12} more</span>}
                    </div>
                  ) : null}
                  <div className="mt-3 text-[10px] text-[var(--accent)]">{isSelected ? "Selected for design import" : "Select pocket"}</div>
                </button>
              );
            })}
          </div>
        ) : (
          <EmptyState text="No pocket annotations available for the active structure." />
        )}

        <div className="flex justify-end">
          <button
            onClick={onImport}
            className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold text-white"
            style={{ background: "linear-gradient(135deg, #2d4d87, #5c72b5)" }}
          >
            <FlaskConical size={13} />
            Import selected site to Design Studio
          </button>
        </div>
      </div>
    </div>
  );
}

function ComparisonTab({
  primaryData,
  primarySourceLabel,
  primaryStructureText,
  primaryStructureUrl,
  comparePdb,
  setComparePdb,
  compareData,
  compareLoading,
  compareMetrics,
}: {
  primaryData: StructureSummary;
  primarySourceLabel: string;
  primaryStructureText?: string;
  primaryStructureUrl?: string;
  comparePdb: string;
  setComparePdb: (value: string) => void;
  compareData?: StructureSummary;
  compareLoading: boolean;
  compareMetrics?: StructureCompareResult;
}) {
  const [draft, setDraft] = useState(comparePdb);

  return (
    <div className="px-6 py-6">
      <div className="mx-auto max-w-[1180px] space-y-5">
        <div className="rounded-[28px] border px-5 py-5" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
          <div className="flex items-center gap-2">
            <Layers size={15} className="text-[var(--accent)]" />
            <div className="text-sm font-semibold text-[var(--text-primary)]">Structure comparison</div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-xs text-[var(--text-muted)]">Compare {primaryData.pdb_id} with</span>
            <input
              type="text"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && setComparePdb(draft.trim().toUpperCase())}
              placeholder="Enter second PDB ID"
              className="rounded-xl border px-3 py-2 text-xs focus:outline-none focus:ring-2"
              style={{ borderColor: "var(--border)", background: "rgba(248,246,240,0.8)" }}
            />
            <button
              onClick={() => setComparePdb(draft.trim().toUpperCase())}
              className="rounded-xl px-4 py-2 text-xs font-semibold text-white"
              style={{ background: "linear-gradient(135deg, #2d4d87, #5c72b5)" }}
            >
              Compare
            </button>
          </div>
        </div>

        {compareLoading ? <CenterLoader /> : null}

        {!comparePdb && !compareLoading ? (
          <EmptyState text="Enter a second PDB ID to overlay two structures and compute backbone RMSD." />
        ) : null}

        {compareData ? (
          <>
            <StructureComparisonViewer
              left={{
                label: `${primaryData.pdb_id} (${primarySourceLabel})`,
                pdbId: primaryStructureText || primaryStructureUrl ? undefined : primaryData.pdb_id,
                structureText: primaryStructureText,
                structureUrl: primaryStructureUrl,
                color: "#60a5fa",
              }}
              right={{
                label: compareData.pdb_id,
                pdbId: compareData.pdb_id,
                color: "#f87171",
              }}
              alignment={
                compareMetrics
                  ? {
                      leftSelection: compareMetrics.left_selection,
                      rightSelection: compareMetrics.right_selection,
                    }
                  : undefined
              }
            />

            {compareMetrics ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {[
                  {
                    label: "Backbone RMSD",
                    value: `${compareMetrics.rmsd.toFixed(2)} A`,
                    detail: `${compareMetrics.aligned_residues} aligned residues`,
                  },
                  {
                    label: "Chain pair",
                    value: `${compareMetrics.left_chain} vs ${compareMetrics.right_chain}`,
                    detail: `${compareMetrics.left_residue_range} / ${compareMetrics.right_residue_range}`,
                  },
                  {
                    label: "Sequence identity",
                    value: `${Math.round(compareMetrics.sequence_identity * 100)}%`,
                    detail: `${compareMetrics.matching_residues} matching residues`,
                  },
                  {
                    label: "Coverage",
                    value: `${Math.round(compareMetrics.coverage_left * 100)}% / ${Math.round(compareMetrics.coverage_right * 100)}%`,
                    detail: `${compareMetrics.left_chain_length} aa vs ${compareMetrics.right_chain_length} aa`,
                  },
                ].map((metric) => (
                  <div key={metric.label} className="rounded-[24px] border px-4 py-4" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
                    <div className="text-[9px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">{metric.label}</div>
                    <div className="mt-2 text-xl font-semibold tracking-[-0.02em] text-[var(--text-primary)]">{metric.value}</div>
                    <div className="mt-1 text-[11px] text-[var(--text-muted)]">{metric.detail}</div>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="rounded-[28px] border overflow-hidden" style={{ borderColor: "rgba(15, 23, 42, 0.06)", background: "rgba(255,255,255,0.72)" }}>
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ background: "rgba(248,246,240,0.9)" }}>
                    {[
                      "Metric",
                      primaryData.pdb_id,
                      compareData.pdb_id,
                    ].map((header) => (
                      <th key={header} className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Method", primaryData.method, compareData.method],
                    ["Resolution", primaryData.resolution ? `${primaryData.resolution} A` : "-", compareData.resolution ? `${compareData.resolution} A` : "-"],
                    ["Organism", primaryData.organism || "-", compareData.organism || "-"],
                    ["Selected chain", compareMetrics?.left_chain || "-", compareMetrics?.right_chain || "-"],
                    ["Chains", `${primaryData.macromolecules.reduce((sum, molecule) => sum + molecule.chains.length, 0)}`, `${compareData.macromolecules.reduce((sum, molecule) => sum + molecule.chains.length, 0)}`],
                    ["Ligands", `${primaryData.ligands.length}`, `${compareData.ligands.length}`],
                    ["Deposited", primaryData.deposition_date?.slice(0, 10) || "-", compareData.deposition_date?.slice(0, 10) || "-"],
                  ].map(([label, left, right]) => (
                    <tr key={String(label)} className="border-t" style={{ borderColor: "rgba(15, 23, 42, 0.06)" }}>
                      <td className="px-3 py-3 font-medium text-[var(--text-primary)]">{label}</td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">{left}</td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">{right}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

function CenterLoader() {
  return (
    <div className="flex min-h-[420px] items-center justify-center p-12">
      <Loader2 size={22} className="animate-spin text-[var(--text-muted)]" />
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex min-h-[420px] items-center justify-center p-12 text-center text-sm text-[var(--text-muted)]">
      <div className="max-w-[520px]">{text}</div>
    </div>
  );
}
