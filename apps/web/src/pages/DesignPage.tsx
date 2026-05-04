/** Molecule Design Studio — 6-step SOTA workflow. */

import { useState, useMemo, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  FlaskConical,
  Target,
  Search,
  Play,
  Download,
  Loader2,
  BarChart3,
  ArrowRight,
  CheckCircle2,
  Circle,
  Beaker,
  FileText,
  RefreshCw,
  ChevronDown,
  AlertCircle,
  Box,
  Plus,
  Settings2,
  GitBranch,
  Send,
  Sparkles,
} from "lucide-react";
import {
  moleculeScoreAPI,
  moleculeADMETAPI,
  moleculeAnalogsAPI,
  moleculeNoveltyAPI,
  designStartSessionAPI,
  designIterationsAPI,
  dockingRunAPI,
  runtimeDiagnosticsAPI,
  labsRetrosynthesisRunAPI,
  ppoOptimizeAPI,
  designDiffusionGenerateAPI,
  designSendToLabAPI,
  type PhysiochemProps,
  type ADMETResult,
  type DockingRequest,
} from "@/lib/api";
import { useRunProgress } from "@/lib/hooks";
import StateWrapper from "@/components/ui/StateWrapper";
import { useSetPageConfidence } from "@/lib/PageConfidenceContext";
import { readCockpitHandoff } from "@/lib/canonicalProduct";
import type { ViewState } from "@/lib/types";

const STEPS = [
  { id: 1, label: "Target & Site", icon: <Target size={14} /> },
  { id: 2, label: "Starting Ligands", icon: <FlaskConical size={14} /> },
  { id: 3, label: "Analogs", icon: <RefreshCw size={14} /> },
  { id: 4, label: "Score", icon: <BarChart3 size={14} /> },
  { id: 5, label: "Novelty", icon: <FileText size={14} /> },
  { id: 6, label: "Retrosynthesis", icon: <GitBranch size={14} /> },
  { id: 7, label: "Summary", icon: <Beaker size={14} /> },
] as const;

type CapabilityInfo = {
  status?: string;
  available?: boolean;
  shipping_tier?: string;
  details?: string;
  install_hint?: string;
  version?: string;
};

function getCapability(diag: Record<string, unknown>, key: string): CapabilityInfo {
  const raw = diag[key];
  return raw && typeof raw === "object" ? (raw as CapabilityInfo) : {};
}

function capabilityTone(status?: string): string {
  if (status === "available") return "bg-green-50 text-green-600";
  if (status === "cpu_only") return "bg-blue-50 text-blue-600";
  return "bg-amber-50 text-amber-700";
}

/** Plugin status panel — checks runtime diagnostics to show real availability */
function PluginStatusPanel({ diag }: { diag: Record<string, unknown> }) {
  const plugins = useMemo(() => {
    const rdkit = getCapability(diag, "rdkit");
    const vina = getCapability(diag, "vina");
    const fpocket = getCapability(diag, "fpocket");
    const p2rank = getCapability(diag, "p2rank");
    const gpu = getCapability(diag, "gpu");
    return [
      { name: "RDKit", status: rdkit.status || "not_detected", tier: rdkit.shipping_tier || "supported", hint: rdkit.details || rdkit.install_hint || "" },
      { name: "AutoDock Vina", status: vina.status || "not_detected", tier: vina.shipping_tier || "optional_local", hint: vina.details || vina.install_hint || "" },
      { name: "fpocket", status: fpocket.status || "not_detected", tier: fpocket.shipping_tier || "optional_local", hint: fpocket.details || fpocket.install_hint || "" },
      { name: "P2Rank", status: p2rank.status || "not_detected", tier: p2rank.shipping_tier || "optional_local", hint: p2rank.details || p2rank.install_hint || "" },
      { name: "GPU Accel.", status: gpu.status || "not_detected", tier: gpu.shipping_tier || "optional_acceleration", hint: gpu.details || "Optional acceleration only" },
    ];
  }, [diag]);

  const nativeSummary = typeof diag.native_tools === "object" && diag.native_tools !== null
    ? String((diag.native_tools as Record<string, unknown>).summary || "")
    : "";

  return (
    <div className="space-y-1 text-xs">
      {plugins.map((p) => (
        <div key={p.name} className="flex items-center justify-between py-0.5" title={p.hint}>
          <span className="text-[var(--text-secondary)]">{p.name} <span className="text-[10px] text-[var(--text-muted)]">{p.tier === "optional_local" ? "optional local" : p.tier}</span></span>
          <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${capabilityTone(p.status)}`}>
            {p.status}
          </span>
        </div>
      ))}
      {nativeSummary && (
        <div className="mt-2 rounded-lg border px-2.5 py-2 text-[10px] text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}>
          {nativeSummary}
        </div>
      )}
    </div>
  );
}

export default function DesignPage() {
  const [step, setStep] = useState(1);
  const [targetPdb, setTargetPdb] = useState("");
  const [center, setCenter] = useState([0, 0, 0]);
  const [boxSize, setBoxSize] = useState([20, 20, 20]);
  const [smilesList, setSmilesList] = useState<string[]>([]);
  const [smilesInput, setSmilesInput] = useState("");
  const [analogMethod, setAnalogMethod] = useState("similarity");
  const [bindingSiteMethod, setBindingSiteMethod] = useState("fpocket");
  const [designSession, setDesignSession] = useState<Record<string, unknown> | null>(null);
  const [handoffBindingSite, setHandoffBindingSite] = useState<Record<string, unknown> | null>(null);
  const { data: runtimeDiagnostics } = useQuery({ queryKey: ["designRuntimeDiagnostics"], queryFn: runtimeDiagnosticsAPI, staleTime: 60_000, retry: 1 });
  const runtimeDiag = ((runtimeDiagnostics as Record<string, unknown> | undefined) ?? {});
  const vinaCapability = useMemo(() => getCapability(runtimeDiag, "vina"), [runtimeDiag]);
  const fpocketCapability = useMemo(() => getCapability(runtimeDiag, "fpocket"), [runtimeDiag]);
  const p2rankCapability = useMemo(() => getCapability(runtimeDiag, "p2rank"), [runtimeDiag]);
  const nativeToolsSummary = typeof runtimeDiag.native_tools === "object" && runtimeDiag.native_tools !== null
    ? String((runtimeDiag.native_tools as Record<string, unknown>).summary || "")
    : "";
  const vinaAvailable = vinaCapability.available === true;
  const fpocketAvailable = fpocketCapability.available === true;
  const p2rankAvailable = p2rankCapability.available === true;

  useEffect(() => {
    const payload = readCockpitHandoff();
    if (!payload || payload.targetRoute !== "/design") return;
    const entity = payload.entities[0];
    const seededTarget = entity?.identifiers?.pdb_id || entity?.identifiers?.uniprot_id || payload.query;
    const seededSmiles = entity?.identifiers?.smiles || (typeof entity?.attributes?.smiles === "string" ? entity.attributes.smiles : "");
    const seededBindingSite = (entity?.attributes?.bindingSite as Record<string, unknown> | undefined) || (payload.metadata?.bindingSite as Record<string, unknown> | undefined);
    if (seededTarget) {
      setTargetPdb(seededTarget);
      setStep(1);
    }
    if (seededBindingSite) {
      setHandoffBindingSite(seededBindingSite);
      setBindingSiteMethod(typeof seededBindingSite.source === "string" ? seededBindingSite.source : "fpocket");
      if (Array.isArray(seededBindingSite.center) && seededBindingSite.center.length === 3) {
        setCenter(seededBindingSite.center as number[]);
      }
      if (Array.isArray(seededBindingSite.box_size) && seededBindingSite.box_size.length === 3) {
        setBoxSize(seededBindingSite.box_size as number[]);
      }
    }
    if (seededSmiles) {
      setSmilesInput(seededSmiles);
      setSmilesList((prev) => prev.includes(seededSmiles) ? prev : [seededSmiles, ...prev].slice(0, 5));
      setStep(2);
    }
  }, []);

  useEffect(() => {
    if (bindingSiteMethod === "fpocket" && !fpocketAvailable && !handoffBindingSite) {
      setBindingSiteMethod(p2rankAvailable ? "p2rank" : "manual");
    }
    if (bindingSiteMethod === "p2rank" && !p2rankAvailable) {
      setBindingSiteMethod(fpocketAvailable ? "fpocket" : "manual");
    }
  }, [bindingSiteMethod, fpocketAvailable, p2rankAvailable, handoffBindingSite]);

  const startSessionMut = useMutation({
    mutationFn: ({
      targetId,
      bindingSite,
    }: {
      targetId: string;
      bindingSite?: Record<string, unknown>;
    }) => designStartSessionAPI(targetId, undefined, bindingSite, { origin: "design_page" }),
    onSuccess: (data) => {
      const session = ((data as any)?.data ?? data ?? null) as Record<string, unknown> | null;
      if (session) setDesignSession(session);
    },
  });

  // H-5: PPO optimization state
  const [ppoRunId, setPpoRunId] = useState<string | null>(null);
  const ppoProgress = useRunProgress(ppoRunId);
  const ppoOptimizeMut = useMutation({
    mutationFn: ({ targetId, seedSmiles }: { targetId: string; seedSmiles?: string }) =>
      ppoOptimizeAPI(targetId, seedSmiles, {}, 50),
    onSuccess: (data: any) => {
      const runId = data?.data?.run_id ?? data?.run_id;
      if (runId) setPpoRunId(runId);
    },
  });

  // U-3.3: Docking WebSocket progress tracking
  const [dockingRunId, setDockingRunId] = useState<string | null>(null);
  const dockingProgress = useRunProgress(dockingRunId);

  // U-2.5: Diffusion-based molecule generation
  const diffusionMut = useMutation({
    mutationFn: ({ numAtoms, numCandidates }: { numAtoms?: number; numCandidates?: number }) =>
      designDiffusionGenerateAPI(numAtoms, undefined, targetPdb, undefined, numCandidates),
    onSuccess: (data: any) => {
      // Add generated candidates to SMILES list if they have coordinates
      const candidates = data?.candidates ?? data?.data?.candidates ?? [];
      const generated = candidates.filter((c: any) => c.status === "generated");
      if (generated.length > 0) {
        // Diffusion returns atom features + coordinates, not SMILES directly.
        // Mark them as available for downstream processing.
      }
    },
  });

  // U-4.5: Send to Research Lab
  const sendToLabMut = useMutation({
    mutationFn: ({ labType, smiles }: { labType: string; smiles: string }) =>
      designSendToLabAPI(
        labType,
        smiles,
        targetPdb,
        undefined,
        handoffBindingSite || { center, box_size: boxSize },
        {
          scores: scoreMut.data || null,
          admet: admetMut.data || null,
        },
        typeof designSession?.session_id === "string" ? designSession.session_id : "",
      ),
  });

  // API mutations
  const scoreMut = useMutation({
    mutationFn: (s: string[]) => moleculeScoreAPI(s),
  });
  const admetMut = useMutation({
    mutationFn: (s: string[]) => moleculeADMETAPI(s),
  });
  const analogsMut = useMutation({
    mutationFn: ({ smiles, method }: { smiles: string; method: string }) =>
      moleculeAnalogsAPI(smiles, method),
  });
  const noveltyMut = useMutation({
    mutationFn: (s: string) => moleculeNoveltyAPI(s),
  });
  const dockingMut = useMutation({
    mutationFn: (req: DockingRequest) => dockingRunAPI(req),
    onSuccess: (data: any) => {
      // U-3.3: Capture the WebSocket run_id for real-time progress tracking
      const wsRunId = data?.ws_run_id ?? data?.data?.ws_run_id;
      if (wsRunId) setDockingRunId(wsRunId);
    },
  });
  const iterationsQ = useQuery({
    queryKey: ["designIterations"],
    queryFn: designIterationsAPI,
    enabled: step === 7,
  });

  const setConfidence = useSetPageConfidence();
  useEffect(() => {
    if (smilesList.length > 0) {
      setConfidence({ freshness: "current", sourceCount: 1, sourcesQueried: ["Molecule Designer"] });
    } else {
      setConfidence(null);
    }
    return () => setConfidence(null);
  }, [smilesList, setConfidence]);

  const addSmiles = () => {
    if (smilesInput.trim()) {
      setSmilesList((prev) => [...prev, smilesInput.trim()]);

      setSmilesInput("");
    }
  };

  const designViewState: ViewState = scoreMut.isPending || admetMut.isPending || analogsMut.isPending || noveltyMut.isPending || dockingMut.isPending ? "loading" : "success";

  return (
    <StateWrapper state={designViewState} moduleName="Molecule Design">
    <div
      className="flex-1 overflow-y-auto"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-[1200px] mx-auto px-6 py-5">
        <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1" style={{ letterSpacing: "-0.01em" }}>
          Molecule Design Studio
        </h1>
        <p className="text-[12px] text-[var(--text-muted)] mb-6">
          Target → Ligands → Analogs → Score → Novelty → Report
        </p>
        {nativeToolsSummary && (
          <div className="mb-4 rounded-xl border px-4 py-3 text-xs text-[var(--text-muted)]" style={{ borderColor: "var(--border)", background: "var(--bg-elevated)" }}>
            {nativeToolsSummary}
          </div>
        )}

        {/* Stepper */}
        <div className="card rounded-xl p-3 mb-6 flex items-center gap-1" style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)" }}>
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex items-center gap-1">
              <button
                onClick={() => setStep(s.id)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  step === s.id
                    ? "text-[var(--accent)] shadow-sm"
                    : step > s.id
                      ? "text-green-600"
                      : "text-[var(--text-muted)]"
                }`}
                style={step === s.id ? { background: "rgba(59, 130, 246, 0.08)", border: "1px solid rgba(59, 130, 246, 0.15)" } : undefined}
              >
                {step > s.id ? <CheckCircle2 size={13} /> : s.icon}
                <span className="hidden md:inline">{s.label}</span>
              </button>
              {i < STEPS.length - 1 && (
                <ArrowRight
                  size={12}
                  className="text-[var(--border)] shrink-0"
                />
              )}
            </div>
          ))}
        </div>

        {/* Step content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Main content */}
          <div className="lg:col-span-2 card rounded-xl p-5">
            {step === 1 && (
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <Target size={14} /> Choose Target & Binding Site
                </h2>
                <div>
                  <label className="text-xs font-medium text-[var(--text-secondary)] mb-1 block">
                    Receptor PDB ID
                  </label>
                  <input
                    type="text"
                    value={targetPdb}
                    onChange={(e) => setTargetPdb(e.target.value)}
                    placeholder="e.g. 6LU7"
                    className="w-full px-3 py-2 text-xs rounded-lg border"
                    style={{ borderColor: "var(--border)" }}
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-[var(--text-secondary)] mb-1 block">
                    Binding Site Selection
                  </label>
                  <select
                    value={bindingSiteMethod}
                    onChange={(e) => setBindingSiteMethod(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-lg border"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <option value="fpocket" disabled={!fpocketAvailable}>
                      Auto-detect pockets (fpocket, optional local)
                    </option>
                    <option value="ligand">
                      Ligand-based (select co-crystallized ligand)
                    </option>
                    <option value="p2rank" disabled={!p2rankAvailable}>P2Rank prediction (optional local)</option>
                    <option value="manual">Manual coordinates</option>
                  </select>
                  {(!fpocketAvailable || !p2rankAvailable) && (
                    <div className="mt-2 rounded-lg border px-3 py-2 text-[11px] text-amber-700" style={{ borderColor: "rgba(217,119,6,0.25)", background: "rgba(254,243,199,0.7)" }}>
                      Auto pocket detection only appears as supported when the native binary is installed in this runtime. Missing tools are treated as optional local-only features.
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[10px] text-[var(--text-muted)]">
                      Center X
                    </label>
                    <input
                      type="number"
                      value={center[0]}
                      onChange={(e) =>
                        setCenter([+e.target.value, center[1], center[2]])
                      }
                      className="w-full px-2 py-1.5 text-xs rounded border"
                      style={{ borderColor: "var(--border)" }}
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-[var(--text-muted)]">
                      Center Y
                    </label>
                    <input
                      type="number"
                      value={center[1]}
                      onChange={(e) =>
                        setCenter([center[0], +e.target.value, center[2]])
                      }
                      className="w-full px-2 py-1.5 text-xs rounded border"
                      style={{ borderColor: "var(--border)" }}
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-[var(--text-muted)]">
                      Center Z
                    </label>
                    <input
                      type="number"
                      value={center[2]}
                      onChange={(e) =>
                        setCenter([center[0], center[1], +e.target.value])
                      }
                      className="w-full px-2 py-1.5 text-xs rounded border"
                      style={{ borderColor: "var(--border)" }}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[10px] text-[var(--text-muted)]">
                      Box X
                    </label>
                    <input
                      type="number"
                      value={boxSize[0]}
                      onChange={(e) =>
                        setBoxSize([+e.target.value, boxSize[1], boxSize[2]])
                      }
                      className="w-full px-2 py-1.5 text-xs rounded border"
                      style={{ borderColor: "var(--border)" }}
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-[var(--text-muted)]">
                      Box Y
                    </label>
                    <input
                      type="number"
                      value={boxSize[1]}
                      onChange={(e) =>
                        setBoxSize([boxSize[0], +e.target.value, boxSize[2]])
                      }
                      className="w-full px-2 py-1.5 text-xs rounded border"
                      style={{ borderColor: "var(--border)" }}
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-[var(--text-muted)]">
                      Box Z
                    </label>
                    <input
                      type="number"
                      value={boxSize[2]}
                      onChange={(e) =>
                        setBoxSize([boxSize[0], boxSize[1], +e.target.value])
                      }
                      className="w-full px-2 py-1.5 text-xs rounded border"
                      style={{ borderColor: "var(--border)" }}
                    />
                  </div>
                </div>
                <button
                  onClick={async () => {
                    if (!targetPdb) return;
                    const activeBindingSite = handoffBindingSite || { source: bindingSiteMethod, center, box_size: boxSize };
                    const existingTarget = typeof designSession?.target_id === "string" ? designSession.target_id : "";
                    if (!designSession || existingTarget !== targetPdb) {
                      await startSessionMut.mutateAsync({ targetId: targetPdb, bindingSite: activeBindingSite });
                    }
                    setStep(2);
                  }}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-white"
                  style={{ background: "var(--accent)" }}
                >
                  Continue →
                </button>
                {(designSession || startSessionMut.isPending) && (
                  <div className="rounded-lg border p-3 mt-3" style={{ borderColor: "var(--border)" }}>
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-1">Design session</div>
                    {startSessionMut.isPending ? (
                      <div className="text-xs text-[var(--text-muted)] flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Starting canonical design session…</div>
                    ) : (
                      <div className="space-y-1 text-xs">
                        <div><span className="text-[var(--text-muted)]">Session:</span> <span className="font-mono">{String(designSession?.session_id || designSession?.run_id || "—")}</span></div>
                        <div><span className="text-[var(--text-muted)]">Status:</span> <span className="font-medium">{String(designSession?.status || "ready")}</span></div>
                        <div><span className="text-[var(--text-muted)]">Stream:</span> <span className="font-mono">{String(designSession?.stream_channel || "—")}</span></div>
                        {handoffBindingSite && <div className="text-[var(--text-muted)]">Imported binding site context from Structure Workbench.</div>}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {step === 2 && (
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <FlaskConical size={14} /> Starting Ligands
                </h2>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={smilesInput}
                    onChange={(e) => setSmilesInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addSmiles()}
                    placeholder="Enter SMILES string…"
                    className="flex-1 px-3 py-2 text-xs rounded-lg border font-mono"
                    style={{ borderColor: "var(--border)" }}
                  />
                  <button
                    onClick={addSmiles}
                    className="px-3 py-2 rounded-lg text-xs border hover:bg-[var(--bg-surface)]"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <Plus size={12} />
                  </button>
                </div>

                {smilesList.length > 0 && (
                  <div
                    className="rounded-lg border p-3"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">
                      {smilesList.length} Ligands
                    </div>
                    {smilesList.map((s, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 py-1 border-b border-dashed"
                        style={{ borderColor: "var(--border-light)" }}
                      >
                        <span className="text-[10px] text-[var(--text-muted)] w-6">
                          {i + 1}.
                        </span>
                        <span className="text-xs font-mono text-[var(--text-secondary)] flex-1 truncate">
                          {s}
                        </span>
                        <button
                          onClick={() =>
                            setSmilesList((prev) =>
                              prev.filter((_, j) => j !== i),
                            )
                          }
                          className="text-[10px] text-red-400 hover:text-red-600"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <button
                  onClick={() => setStep(3)}
                  disabled={smilesList.length === 0}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-white disabled:opacity-40"
                  style={{ background: "var(--accent)" }}
                >
                  Continue →
                </button>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <RefreshCw size={14} /> Generate Analogs
                </h2>
                <div className="flex gap-2">
                  <select
                    value={analogMethod}
                    onChange={(e) => setAnalogMethod(e.target.value)}
                    className="px-3 py-2 text-xs rounded-lg border"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <option value="similarity">
                      Tanimoto Similarity (PubChem)
                    </option>
                    <option value="scaffold_hop">
                      Scaffold Hopping (Murcko)
                    </option>
                    <option value="enumeration">R-group Enumeration</option>
                    <option value="diffusion">Diffusion-based (plugin)</option>
                  </select>
                  <button
                    onClick={() =>
                      analogsMut.mutate({
                        smiles: smilesList[0],
                        method: analogMethod,
                      })
                    }
                    disabled={analogsMut.isPending || smilesList.length === 0}
                    className="px-4 py-2 rounded-lg text-xs font-medium text-white disabled:opacity-40"
                    style={{ background: "var(--accent)" }}
                  >
                    {analogsMut.isPending ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      "Generate"
                    )}
                  </button>
                </div>
                {analogsMut.data && (
                  <div
                    className="rounded-lg border p-3"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">
                      Analogs
                    </div>
                    {((analogsMut.data as any).analogs || []).map(
                      (a: any, i: number) => (
                        <div
                          key={i}
                          className="flex items-center gap-2 py-1 border-b border-dashed"
                          style={{ borderColor: "var(--border-light)" }}
                        >
                          <span className="text-xs font-mono text-[var(--text-secondary)] flex-1 truncate">
                            {a.smiles || a.scaffold || JSON.stringify(a)}
                          </span>
                          {a.mw && (
                            <span className="text-[10px] text-[var(--text-muted)]">
                              MW:{a.mw}
                            </span>
                          )}
                          <button
                            onClick={() =>
                              setSmilesList((prev) => [
                                ...prev,
                                a.smiles || a.scaffold,
                              ])
                            }
                            className="text-[10px] text-[var(--accent)]"
                          >
                            + Add
                          </button>
                        </div>
                      ),
                    )}
                  </div>
                )}
                {/* U-2.5: Diffusion-based de novo molecule generation */}
                <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles size={13} className="text-purple-500" />
                    <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">De Novo Generation (Diffusion)</span>
                  </div>
                  <p className="text-[10px] text-[var(--text-muted)] mb-2">
                    Generate novel molecular graphs using the E(n)-equivariant Graph Diffusion Model conditioned on the target binding pocket.
                  </p>
                  <div className="flex gap-2 items-end">
                    <div>
                      <label className="text-[9px] text-[var(--text-muted)] block mb-0.5">Atoms</label>
                      <select
                        className="px-2 py-1 text-[10px] rounded border"
                        style={{ borderColor: "var(--border)" }}
                        defaultValue="32"
                        id="diffusion-atoms"
                      >
                        <option value="16">16</option>
                        <option value="24">24</option>
                        <option value="32">32</option>
                        <option value="48">48</option>
                        <option value="64">64</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[9px] text-[var(--text-muted)] block mb-0.5">Candidates</label>
                      <select
                        className="px-2 py-1 text-[10px] rounded border"
                        style={{ borderColor: "var(--border)" }}
                        defaultValue="5"
                        id="diffusion-count"
                      >
                        <option value="1">1</option>
                        <option value="3">3</option>
                        <option value="5">5</option>
                        <option value="10">10</option>
                      </select>
                    </div>
                    <button
                      onClick={() => {
                        const atoms = parseInt((document.getElementById("diffusion-atoms") as HTMLSelectElement)?.value || "32");
                        const count = parseInt((document.getElementById("diffusion-count") as HTMLSelectElement)?.value || "5");
                        diffusionMut.mutate({ numAtoms: atoms, numCandidates: count });
                      }}
                      disabled={diffusionMut.isPending}
                      className="px-3 py-1 rounded-lg text-[10px] font-medium text-white disabled:opacity-40 flex items-center gap-1"
                      style={{ background: "#8b5cf6" }}
                    >
                      {diffusionMut.isPending ? <Loader2 size={10} className="animate-spin" /> : <Sparkles size={10} />}
                      {diffusionMut.isPending ? "Generating…" : "Generate"}
                    </button>
                  </div>
                  {diffusionMut.data && (
                    <div className="mt-2 space-y-1">
                      <div className="text-[10px] text-[var(--text-muted)]">
                        {(diffusionMut.data as any).total ?? 0} molecule(s) generated via {(diffusionMut.data as any).model || "GraphDiffusionModel"}
                        {(diffusionMut.data as any).status === "degraded" && (
                          <span className="ml-1 text-amber-500">(degraded — PyTorch unavailable)</span>
                        )}
                      </div>
                      {((diffusionMut.data as any).candidates ?? []).map((c: any, i: number) => (
                        <div key={c.id || i} className="flex items-center gap-2 py-0.5 text-[10px] border-t border-dashed" style={{ borderColor: "var(--border-light)" }}>
                          <span className="font-mono text-[var(--accent)]">#{i + 1}</span>
                          <span className="text-[var(--text-secondary)]">
                            {c.status === "generated" ? `${c.num_atoms} atoms • 3D coords` : c.message || c.status}
                          </span>
                          <span className={`ml-auto text-[9px] px-1.5 py-0.5 rounded-full ${c.status === "generated" ? "bg-green-50 text-green-600" : "bg-amber-50 text-amber-600"}`}>
                            {c.status}
                          </span>
                        </div>
                      ))}
                      {(diffusionMut.data as any).run_id && (
                        <div className="text-[9px] text-[var(--text-muted)] mt-1">
                          Run: <span className="font-mono">{(diffusionMut.data as any).run_id}</span>
                        </div>
                      )}
                    </div>
                  )}
                  {diffusionMut.isError && (
                    <div className="text-[10px] text-red-500 mt-1">
                      <AlertCircle size={10} className="inline mr-1" />
                      {diffusionMut.error instanceof Error ? diffusionMut.error.message : "Generation failed"}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => setStep(4)}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-white"
                  style={{ background: "var(--accent)" }}
                >
                  Continue →
                </button>
              </div>
            )}

            {step === 4 && (
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <BarChart3 size={14} /> Score Compounds
                </h2>
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={() => scoreMut.mutate(smilesList)}
                    disabled={scoreMut.isPending}
                    className="px-4 py-2 rounded-lg text-xs font-medium text-white disabled:opacity-40"
                    style={{ background: "var(--accent)" }}
                  >
                    {scoreMut.isPending ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      "Physicochemical"
                    )}
                  </button>
                  <button
                    onClick={() => admetMut.mutate(smilesList)}
                    disabled={admetMut.isPending}
                    className="px-4 py-2 rounded-lg text-xs border hover:bg-[var(--bg-surface)] disabled:opacity-40"
                    style={{ borderColor: "var(--border)" }}
                  >
                    {admetMut.isPending ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      "ADMET"
                    )}
                  </button>
                  {targetPdb && smilesList.length > 0 && (
                    <button
                      onClick={() => dockingMut.mutate({
                        receptor_path: targetPdb,
                        ligand_path: smilesList[0],
                        center,
                        box_size: boxSize,
                        engine: "vina",
                        exhaustiveness: 8,
                        num_modes: 9,
                      })}
                      disabled={dockingMut.isPending || !vinaAvailable}
                      title={!vinaAvailable ? (vinaCapability.details || vinaCapability.install_hint || "AutoDock Vina is unavailable in this runtime") : undefined}
                      className="px-4 py-2 rounded-lg text-xs border hover:bg-[var(--bg-surface)] disabled:opacity-40 flex items-center gap-1.5"
                      style={{ borderColor: "var(--border)" }}
                    >
                      {dockingMut.isPending ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <><Box size={12} /> Docking</>
                      )}
                    </button>
                  )}
                </div>
                {!vinaAvailable && targetPdb && smilesList.length > 0 && (
                  <div className="rounded-lg border px-3 py-2 text-[11px] text-amber-700" style={{ borderColor: "rgba(217,119,6,0.25)", background: "rgba(254,243,199,0.7)" }}>
                    AutoDock Vina is not installed in this runtime. Docking is disabled because it is an optional local-native capability, not part of the default hosted release path.
                  </div>
                )}
                {scoreMut.data && <ScoreTable data={scoreMut.data} />}
                {admetMut.data && <ADMETSummary data={admetMut.data} />}
                {dockingMut.data && (
                  <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">
                      Docking Results — {(dockingMut.data as any).engine}
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs mb-2">
                      <div className="p-2 rounded bg-[var(--bg-app)]">
                        <div className="text-[9px] text-[var(--text-muted)]">Status</div>
                        <div className={`font-semibold ${(dockingMut.data as any).status === "success" ? "text-green-600" : "text-amber-600"}`}>
                          {(dockingMut.data as any).status}
                        </div>
                      </div>
                      <div className="p-2 rounded bg-[var(--bg-app)]">
                        <div className="text-[9px] text-[var(--text-muted)]">Time</div>
                        <div className="font-mono">{(dockingMut.data as any).elapsed_seconds?.toFixed(1)}s</div>
                      </div>
                      <div className="p-2 rounded bg-[var(--bg-app)]">
                        <div className="text-[9px] text-[var(--text-muted)]">Poses</div>
                        <div className="font-mono">{(dockingMut.data as any).poses?.length ?? 0}</div>
                      </div>
                      <div className="p-2 rounded bg-[var(--bg-app)]">
                        <div className="text-[9px] text-[var(--text-muted)]">Best ΔG</div>
                        <div className="font-mono text-green-600">
                          {(dockingMut.data as any).poses?.[0]?.affinity_kcal?.toFixed(2) ?? "—"} kcal/mol
                        </div>
                      </div>
                    </div>
                    {(dockingMut.data as any).run_id && (
                      <div className="text-[10px] text-[var(--text-muted)] mb-2">Docking run: <span className="font-mono">{(dockingMut.data as any).run_id}</span></div>
                    )}
                    {((dockingMut.data as any).poses ?? []).length > 0 && (
                      <div className="table-scroll-container">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-[9px] text-[var(--text-muted)] uppercase">
                            <th className="text-left py-1">Rank</th>
                            <th className="text-left py-1">Affinity (kcal/mol)</th>
                            <th className="text-left py-1">RMSD l.b.</th>
                            <th className="text-left py-1">RMSD u.b.</th>
                          </tr>
                        </thead>
                        <tbody>
                          {((dockingMut.data as any).poses as any[]).map((p: any, i: number) => (
                            <tr key={i} className="border-t" style={{ borderColor: "var(--border-light)" }}>
                              <td className="py-1 font-medium">{p.rank}</td>
                              <td className="py-1 font-mono">{p.affinity_kcal?.toFixed(2)}</td>
                              <td className="py-1 font-mono text-[var(--text-muted)]">{p.rmsd_lb?.toFixed(2) ?? "—"}</td>
                              <td className="py-1 font-mono text-[var(--text-muted)]">{p.rmsd_ub?.toFixed(2) ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      </div>
                    )}
                    {(dockingMut.data as any).error && (
                      <div className="text-xs text-red-500 mt-1">{(dockingMut.data as any).error}</div>
                    )}
                  </div>
                )}
                {/* U-3.3: Real-time docking progress via WebSocket */}
                {dockingMut.isPending && dockingProgress && (
                  <div className="rounded-lg border p-3" style={{ borderColor: "var(--accent)", background: "rgba(59,130,246,0.04)" }}>
                    <div className="flex items-center gap-2 mb-2">
                      <Loader2 size={12} className="animate-spin text-[var(--accent)]" />
                      <span className="text-[10px] font-semibold text-[var(--accent)] uppercase">Docking in Progress</span>
                    </div>
                    <div className="w-full h-1.5 rounded-full mb-1.5" style={{ background: "var(--bg-inset)" }}>
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{ width: `${dockingProgress.progressPercent}%`, background: "var(--accent)" }}
                      />
                    </div>
                    <div className="flex justify-between text-[10px]">
                      <span className="text-[var(--text-muted)]">{dockingProgress.message || "Running..."}</span>
                      <span className="text-[var(--text-muted)] font-mono">{dockingProgress.progressPercent}%</span>
                    </div>
                  </div>
                )}
                {dockingProgress?.isComplete && !dockingMut.isPending && (
                  <div className="text-[10px] text-green-600 flex items-center gap-1">
                    <CheckCircle2 size={10} /> Docking completed via WebSocket stream
                  </div>
                )}
                <button
                  onClick={() => setStep(5)}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-white"
                  style={{ background: "var(--accent)" }}
                >
                  Continue →
                </button>
              </div>
            )}

            {step === 5 && (
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <FileText size={14} /> Novelty Validation
                </h2>
                {smilesList.map((s, i) => (
                  <div key={i} className="flex gap-2 items-start">
                    <span className="text-xs font-mono text-[var(--text-muted)] w-48 truncate shrink-0">
                      {s}
                    </span>
                    <button
                      onClick={() => noveltyMut.mutate(s)}
                      disabled={noveltyMut.isPending}
                      className="px-2 py-1 text-[10px] rounded border hover:bg-[var(--bg-surface)]"
                      style={{ borderColor: "var(--border)" }}
                    >
                      Check
                    </button>
                  </div>
                ))}
                {noveltyMut.data && (
                  <div
                    className="rounded-lg border p-3"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <div
                      className={`text-sm font-semibold ${(noveltyMut.data as any).novelty_assessment === "potentially_novel" ? "text-green-600" : "text-amber-600"}`}
                    >
                      {(noveltyMut.data as any).novelty_assessment ===
                      "potentially_novel"
                        ? "✓ Potentially Novel"
                        : "⚠ Known Compound"}
                    </div>
                    <div className="text-xs text-[var(--text-muted)] mt-1">
                      Publications: {(noveltyMut.data as any).publication_hits}{" "}
                      | Patents: {(noveltyMut.data as any).patent_hits}
                    </div>
                  </div>
                )}
                <button
                  onClick={() => setStep(6)}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-white"
                  style={{ background: "var(--accent)" }}
                >
                  Continue →
                </button>
              </div>
            )}

            {step === 6 && (
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <GitBranch size={14} /> Retrosynthesis Planning
                </h2>
                <p className="text-xs text-[var(--text-muted)]">
                  Plan synthetic routes for your top candidates using RSGPT + MCTS tree search.
                </p>
                {smilesList.map((s, i) => (
                  <RetroSynthCard key={i} smiles={s} />
                ))}
                <button
                  onClick={() => setStep(7)}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-white"
                  style={{ background: "var(--accent)" }}
                >
                  Continue →
                </button>
              </div>
            )}

            {step === 7 && (
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <Beaker size={14} /> Iteration Summary
                </h2>
                <div className="card-grid text-xs">
                  <div
                    className="rounded-lg border p-3"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">
                      Target
                    </div>
                    <div className="font-medium mt-0.5">{targetPdb || "—"}</div>
                  </div>
                  <div
                    className="rounded-lg border p-3"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">
                      Compounds
                    </div>
                    <div className="font-medium mt-0.5">
                      {smilesList.length}
                    </div>
                  </div>
                  <div
                    className="rounded-lg border p-3"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">
                      Status
                    </div>
                    {scoreMut.data || admetMut.data || noveltyMut.data || dockingMut.data ? (
                      <div className="font-medium mt-0.5 text-green-600">
                        Data collected — ready to export
                      </div>
                    ) : (
                      <div className="font-medium mt-0.5 text-amber-600">
                        No scoring data yet
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      const bundle = {
                        target: targetPdb,
                        bindingSite: bindingSiteMethod,
                        center,
                        boxSize,
                        compounds: smilesList,
                        scores: scoreMut.data || null,
                        admet: admetMut.data || null,
                        docking: dockingMut.data || null,
                        novelty: noveltyMut.data || null,
                        exportedAt: new Date().toISOString(),
                      };
                      const blob = new Blob([JSON.stringify(bundle, null, 2)], {
                        type: "application/json",
                      });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `design_bundle_${targetPdb || "export"}.json`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                    className="px-4 py-2 rounded-lg text-xs font-medium text-white"
                    style={{ background: "var(--accent)" }}
                  >
                    <Download size={12} className="inline mr-1" /> Export Bundle
                    (JSON)
                  </button>
                </div>
                {iterationsQ.data && (iterationsQ.data as any[]).length > 0 && (
                  <div
                    className="rounded-lg border p-3 mt-4"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">
                      Previous Iterations
                    </div>
                    {(iterationsQ.data as any[]).map((it: any) => (
                      <div
                        key={it.iteration_id}
                        className="flex items-center gap-2 py-1 text-xs border-b border-dashed"
                        style={{ borderColor: "var(--border-light)" }}
                      >
                        <span className="font-mono text-[var(--accent)]">
                          {it.iteration_id}
                        </span>
                        <span className="text-[var(--text-muted)]">
                          {it.target}
                        </span>
                        <span className="text-[var(--text-muted)]">
                          {it.num_compounds} cpds
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Sidebar — context panel */}
          <div className="space-y-4">
            <div className="card rounded-xl p-4">
              <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">
                Compound Library
              </h3>
              <div className="text-xs text-[var(--text-muted)]">
                {smilesList.length} compound(s)
              </div>
              <div className="mt-2 space-y-1 max-h-[200px] overflow-y-auto">
                {smilesList.map((s, i) => (
                  <div
                    key={i}
                    className="text-[10px] font-mono text-[var(--text-secondary)] truncate py-0.5"
                  >
                    {s}
                  </div>
                ))}
              </div>
            </div>
            <div className="card rounded-xl p-4">
              <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">
                Docking Config
              </h3>
              <div className="text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Engine</span>
                  <span>{vinaAvailable ? "AutoDock Vina" : "Docking disabled (Vina unavailable)"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Target</span>
                  <span>{targetPdb || "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Center</span>
                  <span className="font-mono">{center.join(", ")}</span>
                </div>
              </div>
            </div>
            <div className="card rounded-xl p-4">
              <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">
                Plugins
              </h3>
              <PluginStatusPanel diag={runtimeDiag} />
            </div>

            {/* H-5: PPO Optimization Panel */}
            <div className="card rounded-xl p-4">
              <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">
                PPO Optimization
              </h3>
              <button
                className="w-full text-xs py-1.5 px-3 rounded-lg font-medium mb-2"
                style={{ background: "var(--accent)", color: "#fff", opacity: ppoOptimizeMut.isPending ? 0.6 : 1 }}
                disabled={ppoOptimizeMut.isPending || !targetPdb}
                onClick={() =>
                  ppoOptimizeMut.mutate({
                    targetId: targetPdb,
                    seedSmiles: smilesList[0],
                  })
                }
              >
                {ppoOptimizeMut.isPending ? "Queuing…" : "Run PPO Optimize"}
              </button>
              {ppoProgress && !ppoProgress.isComplete && (
                <div className="space-y-1">
                  <span className="text-[10px]" style={{ color: "var(--accent)" }}>
                    {ppoProgress.stage || "Optimizing…"}
                  </span>
                  <div className="w-full h-1.5 rounded-full" style={{ background: "var(--bg-inset)" }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${ppoProgress.progressPercent}%`, background: "var(--accent)" }}
                    />
                  </div>
                  <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                    {ppoProgress.progressPercent}%
                  </span>
                </div>
              )}
              {ppoProgress?.isComplete && (
                <p className="text-[10px] text-green-600">Optimization complete.</p>
              )}
              {!targetPdb && (
                <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                  Set a Target PDB ID in Step 1 to enable.
                </p>
              )}
            </div>

            {/* U-4.5: Save to Research Lab */}
            <div className="card rounded-xl p-4">
              <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">
                <Send size={10} className="inline mr-1" />
                Send to Research Lab
              </h3>
              <p className="text-[10px] text-[var(--text-muted)] mb-2">
                Send the current molecule context to a specialized lab for deeper analysis.
              </p>
              <div className="space-y-1">
                {[
                  { key: "admet", label: "ADMET Lab", desc: "Batch ADMET profiling" },
                  { key: "retrosynthesis", label: "Retrosynthesis Lab", desc: "Route planning" },
                  { key: "target-discovery", label: "Target Discovery", desc: "Pocket analysis" },
                  { key: "molecule-generation", label: "Molecule Gen.", desc: "RL + diffusion" },
                  { key: "pharmacogenomics", label: "Pharmacogenomics", desc: "Gene-drug interactions" },
                ].map((lab) => (
                  <button
                    key={lab.key}
                    onClick={() =>
                      sendToLabMut.mutate({
                        labType: lab.key,
                        smiles: smilesList[0] || "",
                      })
                    }
                    disabled={sendToLabMut.isPending || (!smilesList.length && !targetPdb)}
                    className="w-full text-left px-2 py-1.5 text-[10px] rounded hover:bg-[var(--bg-surface)] disabled:opacity-40 flex items-center justify-between group"
                    title={lab.desc}
                  >
                    <span className="text-[var(--text-secondary)] group-hover:text-[var(--accent)]">{lab.label}</span>
                    <Send size={8} className="text-[var(--text-muted)] group-hover:text-[var(--accent)]" />
                  </button>
                ))}
              </div>
              {sendToLabMut.isPending && (
                <div className="flex items-center gap-1.5 mt-2 text-[10px] text-[var(--accent)]">
                  <Loader2 size={10} className="animate-spin" /> Sending to lab…
                </div>
              )}
              {sendToLabMut.isSuccess && (
                <div className="mt-2 rounded border p-2 text-[10px]" style={{ borderColor: "var(--border)", background: "rgba(34,197,94,0.05)" }}>
                  <div className="text-green-600 font-medium flex items-center gap-1">
                    <CheckCircle2 size={10} /> Sent to {(sendToLabMut.data as any)?.lab_type} lab
                  </div>
                  <div className="text-[var(--text-muted)] mt-0.5">
                    Run: <span className="font-mono">{(sendToLabMut.data as any)?.run_id}</span>
                  </div>
                  <div className="text-[var(--text-muted)]">
                    Status: {(sendToLabMut.data as any)?.status}
                  </div>
                </div>
              )}
              {sendToLabMut.isError && (
                <div className="text-[10px] text-red-500 mt-2">
                  <AlertCircle size={10} className="inline mr-1" />
                  {sendToLabMut.error instanceof Error ? sendToLabMut.error.message : "Failed to send"}
                </div>
              )}
              {!smilesList.length && !targetPdb && (
                <p className="text-[10px] text-[var(--text-muted)] mt-2">
                  Add compounds or set a target to enable lab handoff.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
    </StateWrapper>
  );
}

/* ─── Retrosynthesis Card ──────────────────────────────── */

function RetroSynthCard({ smiles }: { smiles: string }) {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runRetro = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await labsRetrosynthesisRunAPI(smiles);
      setResult(res as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retrosynthesis failed");
    }
    setLoading(false);
  };

  const routes = result?.routes as Record<string, unknown>[] | undefined;
  const steps = result?.steps as Record<string, unknown>[] | undefined;

  return (
    <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-mono text-[var(--text-muted)] truncate flex-1" title={smiles}>
          {smiles.length > 50 ? smiles.slice(0, 48) + "…" : smiles}
        </span>
        <button
          onClick={runRetro}
          disabled={loading}
          className="px-2 py-1 text-[10px] rounded border hover:bg-[var(--bg-surface)] flex items-center gap-1"
          style={{ borderColor: "var(--border)" }}
        >
          {loading ? <Loader2 size={10} className="animate-spin" /> : <GitBranch size={10} />}
          {loading ? "Planning…" : "Plan Route"}
        </button>
      </div>

      {error && (
        <div className="text-[10px] text-red-600 bg-red-50 rounded px-2 py-1 mb-2">
          <AlertCircle size={10} className="inline mr-1" />{error}
        </div>
      )}

      {result && (
        <div className="space-y-2">
          {/* Route summary */}
          <div className="text-[10px] text-[var(--text-muted)]">
            {routes ? `${routes.length} route(s) found` : steps ? `${steps.length} step(s)` : "Analysis complete"}
          </div>

          {/* Show route steps */}
          {(routes || steps || []).slice(0, 5).map((r, i) => (
            <div key={i} className="flex items-center gap-2 text-[10px] py-1 border-t border-dashed" style={{ borderColor: "var(--border-light)" }}>
              <span className="font-bold text-[var(--accent)] shrink-0">Step {i + 1}</span>
              <span className="text-[var(--text-muted)]">{String(r.reaction || r.name || r.type || "Transform")}</span>
              {r.confidence != null && (
                <span className="ml-auto font-mono text-[9px]" style={{ color: Number(r.confidence) > 0.7 ? "#22c55e" : "#f59e0b" }}>
                  {(Number(r.confidence) * 100).toFixed(0)}% conf
                </span>
              )}
            </div>
          ))}

          {/* Feasibility score */}
          {result.feasibility_score != null && (
            <div className="text-xs mt-2 font-medium" style={{ color: Number(result.feasibility_score) > 0.6 ? "#22c55e" : "#f59e0b" }}>
              Feasibility: {(Number(result.feasibility_score) * 100).toFixed(0)}%
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Score Table ──────────────────────────────────────── */

function ScoreTable({ data }: { data: PhysiochemProps[] }) {
  return (
    <div
      className="rounded-lg border overflow-hidden table-scroll-container"
      style={{ borderColor: "var(--border)" }}
    >
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-[var(--bg-app)]">
            {[
              "SMILES",
              "MW",
              "LogP",
              "HBD",
              "HBA",
              "TPSA",
              "Rotatable",
              "Lipinski",
              "Drug-like",
            ].map((h) => (
              <th
                key={h}
                className="px-2 py-1.5 text-left text-[9px] font-semibold text-[var(--text-muted)] uppercase"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((d, i) => (
            <tr
              key={i}
              className="border-t"
              style={{ borderColor: "var(--border-light)" }}
            >
              <td className="px-2 py-1 font-mono max-w-[120px] truncate">
                {d.smiles}
              </td>
              <td className="px-2 py-1">{d.mw ?? "—"}</td>
              <td className="px-2 py-1">{d.logp ?? "—"}</td>
              <td className="px-2 py-1">{d.hbd}</td>
              <td className="px-2 py-1">{d.hba}</td>
              <td className="px-2 py-1">{d.tpsa ?? "—"}</td>
              <td className="px-2 py-1">{d.rotatable_bonds}</td>
              <td className="px-2 py-1">{d.lipinski_violations}</td>
              <td className="px-2 py-1">
                <span
                  className={
                    d.druglikeness === "pass"
                      ? "text-green-600"
                      : "text-amber-600"
                  }
                >
                  {d.druglikeness}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** I-4: Uncertainty badge for conformal interval width. */
function UncertaintyBadge({ ci }: { ci?: { interval?: [number, number]; calibrated: boolean } }) {
  if (!ci || !ci.calibrated || !ci.interval) {
    return <span className="text-[9px] text-[var(--text-muted)] italic">uncalibrated</span>;
  }
  const width = ci.interval[1] - ci.interval[0];
  const color = width < 0.2 ? "#34d399" : width < 0.4 ? "#fbbf24" : "#f87171";
  const label = width < 0.2 ? "narrow" : width < 0.4 ? "moderate" : "wide";
  return (
    <span
      className="text-[9px] px-1.5 py-0.5 rounded-full font-medium"
      style={{ background: `${color}22`, color }}
      title={`90% CI: [${ci.interval[0].toFixed(3)}, ${ci.interval[1].toFixed(3)}]`}
    >
      ±{(width / 2).toFixed(2)} {label}
    </span>
  );
}

function ADMETSummary({ data }: { data: ADMETResult[] }) {
  return (
    <div className="space-y-2">
      {data.map((d, i) => (
        <div
          key={i}
          className="rounded-lg border p-3"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="text-xs font-mono text-[var(--text-secondary)] mb-2 truncate">
            {d.smiles}
          </div>
          <div className="grid grid-cols-5 gap-2">
            {(
              [
                "absorption",
                "distribution",
                "metabolism",
                "excretion",
                "toxicity",
              ] as const
            ).map((cat) => (
              <div key={cat}>
                <div className="text-[9px] font-semibold text-[var(--text-muted)] uppercase mb-1 flex items-center gap-1">
                  {cat}
                  {/* I-4: Uncertainty badge per ADMET category */}
                  <UncertaintyBadge ci={d.conformal_intervals?.[cat] as any} />
                </div>
                {Object.entries(d[cat]).map(([k, v]) => (
                  <div key={k} className="text-[10px] py-0.5">
                    <span className="text-[var(--text-muted)]">
                      {k.replace(/_/g, " ")}:
                    </span>{" "}
                    <span
                      className={
                        typeof v === "boolean"
                          ? v
                            ? "text-amber-600"
                            : "text-green-600"
                          : "text-[var(--text-primary)]"
                      }
                    >
                      {typeof v === "boolean" ? (v ? "Yes" : "No") : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
          <div className="mt-2 text-[10px] text-[var(--text-muted)] flex items-center gap-2">
            <span>SA:{" "}
            {(d.synthetic_accessibility &&
              (d.synthetic_accessibility as any).feasibility) ||
              "—"}
            </span>
            {/* I-4: SA score uncertainty badge */}
            <UncertaintyBadge ci={d.conformal_intervals?.["synthetic_accessibility"] as any} />
          </div>
        </div>
      ))}
    </div>
  );
}
