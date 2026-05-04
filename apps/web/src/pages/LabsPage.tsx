/** LabsPage — Research Labs functional hub (§131, §77, Phase X). */

import { useQuery } from "@tanstack/react-query";
import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  FlaskConical,
  ArrowLeft,
  Loader2,
  AlertTriangle,
  CheckCircle,
  Play,
  Beaker,
  Atom,
  Shield,
  Target,
  Dna,
  Pill,
  Workflow,
  Clock,
  RefreshCw,
  Send,
  FileText,
  Microscope,
  ArrowRight,
  Upload,
  ToggleLeft,
  ToggleRight,
  Activity,
} from "lucide-react";
import {
  labsPocketRunAPI,
  labsAdmetRunAPI,
  labsRetrosynthesisRunAPI,
  labsVaccineRunAPI,
  labsMoleculeGenerationRunAPI,
  labsMetabolicEngineeringRunAPI,
  labsPharmacogenomicsRunAPI,
  runGetAPI,
  dossierCreateAPI,
  dossierUpdateAPI,
  runtimeDiagnosticsAPI,
} from "../lib/api";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";
import {
  readCockpitHandoff,
  persistCockpitHandoff,
} from "@/lib/canonicalProduct";
import type { SharedHandoffPayload } from "@/lib/canonicalProduct";
import { useRunProgress } from "@/lib/hooks";

/* ── Lab module definitions ────────────────────────────── */
interface LabDef {
  title: string;
  description: string;
  icon: typeof FlaskConical;
  color: string;
}

const LAB_MODULES: Record<string, LabDef> = {
  "target-discovery": {
    title: "Target Discovery Lab",
    description:
      "Deep pocket detection, binding-site analysis, and druggability assessment workflows.",
    icon: Target,
    color: "#22c55e",
  },
  admet: {
    title: "ADMET Prediction Lab",
    description:
      "Absorption, distribution, metabolism, excretion, and toxicity profiling for candidate molecules.",
    icon: Beaker,
    color: "#3b82f6",
  },
  retrosynthesis: {
    title: "Retrosynthesis Lab",
    description:
      "Multi-step synthetic route planning and feasibility scoring.",
    icon: Atom,
    color: "#f59e0b",
  },
  vaccine: {
    title: "Vaccine Design Lab",
    description:
      "Epitope prediction, immunogenicity scoring, and vaccine construct optimization.",
    icon: Shield,
    color: "#8b5cf6",
  },
  "molecule-generation": {
    title: "Molecule Generation Lab",
    description:
      "De novo molecule generation using RL + diffusion against target binding pockets.",
    icon: Dna,
    color: "#ec4899",
  },
  "pocket-detection": {
    title: "Pocket Detection Lab",
    description:
      "Deep pocket detection with druggability assessment using fpocket/P2Rank.",
    icon: Microscope,
    color: "#06b6d4",
  },
  "metabolic-engineering": {
    title: "Metabolic Engineering Lab",
    description:
      "Pathway flux analysis, enzyme engineering, and metabolic route optimization.",
    icon: Workflow,
    color: "#14b8a6",
  },
  pharmacogenomics: {
    title: "Pharmacogenomics Lab",
    description:
      "Gene-drug interaction analysis, variant impact prediction, and population pharmacogenomics.",
    icon: Pill,
    color: "#f97316",
  },
};

type RunStatus = "idle" | "loading" | "polling" | "success" | "error";

const TERMINAL_STATES = new Set(["COMPLETE", "FAILED", "ERROR", "complete", "failed", "error"]);
const POLL_INTERVAL = 3000;
const MAX_POLLS = 60; // 3 min max

/* ── Recent runs storage ───────────────────────────────── */
const RECENT_RUNS_KEY = "drug-designer:lab-recent-runs";

interface RecentRun {
  runId: string;
  labKey: string;
  labTitle: string;
  status: "running" | "complete" | "error";
  startedAt: string;
  summary?: string;
}

function saveRecentRun(run: RecentRun) {
  try {
    const existing = JSON.parse(localStorage.getItem(RECENT_RUNS_KEY) || "[]") as RecentRun[];
    const updated = [run, ...existing.filter((r) => r.runId !== run.runId)].slice(0, 20);
    localStorage.setItem(RECENT_RUNS_KEY, JSON.stringify(updated));
  } catch { /* ignore */ }
}

function loadRecentRuns(): RecentRun[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_RUNS_KEY) || "[]") as RecentRun[];
  } catch { return []; }
}

function updateRecentRunStatus(runId: string, status: RecentRun["status"], summary?: string) {
  try {
    const existing = JSON.parse(localStorage.getItem(RECENT_RUNS_KEY) || "[]") as RecentRun[];
    const updated = existing.map((r) =>
      r.runId === runId ? { ...r, status, summary: summary || r.summary } : r,
    );
    localStorage.setItem(RECENT_RUNS_KEY, JSON.stringify(updated));
  } catch { /* ignore */ }
}

type NativeCapability = {
  status?: string;
  available?: boolean;
  shipping_tier?: string;
  details?: string;
  install_hint?: string;
};

function useNativeToolCapabilities() {
  const { data } = useQuery({ queryKey: ["labsRuntimeDiagnostics"], queryFn: runtimeDiagnosticsAPI, staleTime: 60_000, retry: 1 });
  const diag = ((data as Record<string, unknown> | undefined) ?? {});
  const readCapability = (key: string): NativeCapability => {
    const raw = diag[key];
    return raw && typeof raw === "object" ? (raw as NativeCapability) : {};
  };

  return {
    fpocket: readCapability("fpocket"),
    p2rank: readCapability("p2rank"),
    nativeSummary: typeof diag.native_tools === "object" && diag.native_tools !== null
      ? String((diag.native_tools as Record<string, unknown>).summary || "")
      : "",
  };
}

/* ── Shared run hook: fire API call → detect QUEUED → poll for result ── */
function useLabRun(labKey?: string) {
  const [status, setStatus] = useState<RunStatus>("idle");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [pollCount, setPollCount] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // X-3.4: WebSocket progress streaming
  const wsProgress = useRunProgress(runId);

  const clearPoller = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  }, []);

  // Merge WS progress into status
  useEffect(() => {
    if (!wsProgress) return;
    if (wsProgress.isComplete) {
      // WS says complete — do a final poll to get full result
      clearPoller();
    }
    if (wsProgress.error) {
      clearPoller();
      setError(wsProgress.error);
      setStatus("error");
      if (runId) updateRecentRunStatus(runId, "error", wsProgress.error);
    }
  }, [wsProgress, clearPoller, runId]);

  // Poll for run completion
  useEffect(() => {
    if (status !== "polling" || !runId) return;
    clearPoller();

    timerRef.current = setInterval(async () => {
      try {
        const run = await runGetAPI(runId) as Record<string, unknown>;
        const runStatus = String(run.status ?? run.state ?? "").toUpperCase();
        setPollCount((c) => c + 1);

        if (TERMINAL_STATES.has(runStatus) || TERMINAL_STATES.has(String(run.status ?? ""))) {
          clearPoller();
          if (runStatus === "FAILED" || runStatus === "ERROR") {
            setError(String(run.error ?? run.message ?? "Run failed"));
            setStatus("error");
            updateRecentRunStatus(runId, "error", String(run.error ?? "Failed"));
          } else {
            setResult(run);
            setStatus("success");
            updateRecentRunStatus(runId, "complete", "Completed");
          }
        } else if (pollCount >= MAX_POLLS) {
          clearPoller();
          setResult(run);
          setStatus("success");
          updateRecentRunStatus(runId, "complete", "Completed (timeout)");
        }
      } catch {
        clearPoller();
        setError("Lost connection while polling for results");
        setStatus("error");
        if (runId) updateRecentRunStatus(runId, "error", "Connection lost");
      }
    }, POLL_INTERVAL);

    return clearPoller;
  }, [status, runId, clearPoller, pollCount]);

  const submit = useCallback(async (apiCall: () => Promise<unknown>) => {
    setStatus("loading"); setError(""); setResult(null); setRunId(null); setPollCount(0);
    clearPoller();
    try {
      const res = (await apiCall()) as Record<string, unknown>;
      // Unwrap envelope if present
      const data = (res.data ?? res) as Record<string, unknown>;
      const id = String(data.run_id ?? data.id ?? "");
      const resStatus = String(data.status ?? "").toUpperCase();

      if (id && labKey) {
        const labDef = LAB_MODULES[labKey];
        saveRecentRun({
          runId: id,
          labKey,
          labTitle: labDef?.title ?? labKey,
          status: "running",
          startedAt: new Date().toISOString(),
        });
      }

      // If queued/running, start polling
      if (id && (resStatus === "QUEUED" || resStatus === "RUNNING" || resStatus === "PENDING")) {
        setRunId(id);
        setResult(data);
        setStatus("polling");
      } else {
        setResult(data);
        setStatus("success");
        if (id) updateRecentRunStatus(id, "complete", "Completed");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Run failed");
      setStatus("error");
    }
  }, [clearPoller, labKey]);

  const reset = useCallback(() => {
    clearPoller();
    setStatus("idle"); setResult(null); setError(""); setRunId(null); setPollCount(0);
  }, [clearPoller]);

  return { status, result, error, runId, pollCount, wsProgress, submit, reset };
}

/* ── Cross-Lab Action Buttons (X-3.1, X-3.2, X-3.3) ──── */
function CrossLabActions({
  result,
  runId,
  labKey,
  labTitle,
}: {
  result: Record<string, unknown>;
  runId?: string | null;
  labKey?: string;
  labTitle?: string;
}) {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  const buildHandoff = useCallback((): SharedHandoffPayload => ({
    version: "phase0.v1",
    sourceModule: "research-labs",
    action: "open_in_design",
    targetRoute: "/design",
    query: labTitle || "Lab Result",
    createdAt: new Date().toISOString(),
    runId: runId || undefined,
    entities: [],
    provenance: [{
      source: labKey || "research-labs",
      runId: runId || undefined,
      retrievedAt: new Date().toISOString(),
    }],
    metadata: { labResult: result, labKey },
  }), [result, runId, labKey, labTitle]);

  // X-3.1: Send to Design Studio
  const sendToDesign = useCallback(() => {
    const payload = buildHandoff();
    payload.action = "open_in_design";
    payload.targetRoute = "/design";
    persistCockpitHandoff(payload);
    navigate("/design");
  }, [buildHandoff, navigate]);

  // X-3.2: Send to Cockpit
  const sendToCockpit = useCallback(() => {
    const payload = buildHandoff();
    payload.action = "run_cockpit_search";
    payload.targetRoute = "/workspace";
    persistCockpitHandoff(payload);
    navigate("/workspace");
  }, [buildHandoff, navigate]);

  // X-3.3: Append to Dossier
  const appendToDossier = useCallback(async () => {
    setSaving(true);
    try {
      const dossier = await dossierCreateAPI("", `Lab Result: ${labTitle || labKey}`) as Record<string, unknown> & {
        data?: Record<string, unknown>;
      };
      const dossierData = dossier.data ?? {};
      const dossierId = String(dossier.dossier_id ?? dossier.id ?? dossierData.dossier_id ?? "");
      if (dossierId) {
        await dossierUpdateAPI(dossierId, {
          body_json: {
            lab_result: result,
            lab_key: labKey,
            run_id: runId,
            appended_at: new Date().toISOString(),
            provenance: {
              source: `Research Labs / ${labTitle || labKey}`,
              run_id: runId,
              generated_at: new Date().toISOString(),
            },
          },
        });
        setSaved(dossierId);
      }
    } catch {
      /* silently fail — dossier creation is best-effort */
    } finally {
      setSaving(false);
    }
  }, [result, runId, labKey, labTitle]);

  return (
    <div className="flex items-center gap-2 flex-wrap mt-3 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
      <span className="text-[10px] uppercase tracking-widest font-bold mr-1" style={{ color: "var(--text-muted)" }}>
        Actions
      </span>
      <button
        onClick={sendToDesign}
        className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors hover:opacity-80"
        style={{ background: "rgba(59,130,246,0.12)", color: "#3b82f6" }}
      >
        <Send size={11} /> Design Studio
      </button>
      <button
        onClick={sendToCockpit}
        className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors hover:opacity-80"
        style={{ background: "rgba(34,197,94,0.12)", color: "#16a34a" }}
      >
        <ArrowRight size={11} /> Cockpit
      </button>
      <button
        onClick={appendToDossier}
        disabled={saving || !!saved}
        className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors hover:opacity-80"
        style={{
          background: saved ? "rgba(34,197,94,0.12)" : "rgba(168,85,247,0.12)",
          color: saved ? "#16a34a" : "#a855f7",
          opacity: saving ? 0.6 : 1,
        }}
      >
        {saving ? <Loader2 size={11} className="animate-spin" /> : <FileText size={11} />}
        {saved ? "Saved to Dossier" : "Append to Dossier"}
      </button>
    </div>
  );
}

/* ── Provenance Display ────────────────────────────────── */
function ProvenanceBar({ runId, labKey }: { runId?: string | null; labKey?: string }) {
  if (!runId && !labKey) return null;
  return (
    <div className="flex items-center gap-3 text-[10px] mt-2 pt-2" style={{ borderTop: "1px solid var(--border)", color: "var(--text-muted)" }}>
      <span className="uppercase tracking-widest font-bold">Provenance</span>
      {labKey && <span>Source: Research Labs / {LAB_MODULES[labKey]?.title ?? labKey}</span>}
      {runId && <span className="font-mono">Run: {runId.slice(0, 8)}…</span>}
      <span>{new Date().toISOString().slice(0, 19).replace("T", " ")} UTC</span>
    </div>
  );
}

/* ── WebSocket Progress Bar (X-3.4) ───────────────────── */
function WsProgressBar({ wsProgress }: { wsProgress: ReturnType<typeof useRunProgress> }) {
  if (!wsProgress) return null;
  const pct = wsProgress.progressPercent;
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between text-[10px] mb-1" style={{ color: "var(--text-muted)" }}>
        <span>{wsProgress.stage || wsProgress.state || "Processing"}</span>
        <span>{pct > 0 ? `${Math.round(pct)}%` : ""}</span>
      </div>
      <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${Math.max(pct, 2)}%`, background: "#3b82f6" }}
        />
      </div>
      {wsProgress.message && (
        <p className="text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>{wsProgress.message}</p>
      )}
    </div>
  );
}


/* ── Target Discovery Form (X-2.1) ────────────────────── */
function TargetDiscoveryForm() {
  const [targetId, setTargetId] = useState("");
  const [pdbId, setPdbId] = useState("");
  const [method, setMethod] = useState<"fpocket" | "p2rank">("fpocket");
  const [druggabilityThreshold, setDruggabilityThreshold] = useState(0.5);
  const lab = useLabRun("target-discovery");
  const { fpocket, p2rank, nativeSummary } = useNativeToolCapabilities();
  const fpocketAvailable = fpocket.available === true;
  const p2rankAvailable = p2rank.available === true;
  const selectedCapability = method === "fpocket" ? fpocket : p2rank;

  useEffect(() => {
    if (method === "fpocket" && !fpocketAvailable && p2rankAvailable) {
      setMethod("p2rank");
    }
    if (method === "p2rank" && !p2rankAvailable && fpocketAvailable) {
      setMethod("fpocket");
    }
  }, [method, fpocketAvailable, p2rankAvailable]);

  const run = () => {
    if (!(selectedCapability.available === true)) {
      lab.submit(() => Promise.reject(new Error(`${method} is not installed in this runtime. Pocket detection native tools are optional local-only capabilities.`)));
      return;
    }
    if (!targetId.trim() && !pdbId.trim()) {
      lab.submit(() => Promise.reject(new Error("Enter a target/gene symbol or PDB ID.")));
      return;
    }
    lab.submit(() =>
      labsPocketRunAPI(targetId.trim(), {
        pdb_id: pdbId.trim(),
        method,
        druggability_threshold: druggabilityThreshold,
      }),
    );
  };

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Target / Gene Symbol
          </label>
          <input
            type="text" value={targetId} onChange={(e) => setTargetId(e.target.value)}
            placeholder="e.g. EGFR" className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          />
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            PDB ID (optional)
          </label>
          <input
            type="text" value={pdbId} onChange={(e) => setPdbId(e.target.value)}
            placeholder="e.g. 1M17" className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Pocket Detection Method
          </label>
          <select
            value={method} onChange={(e) => setMethod(e.target.value as "fpocket" | "p2rank")}
            className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            <option value="fpocket" disabled={!fpocketAvailable}>fpocket (optional local)</option>
            <option value="p2rank" disabled={!p2rankAvailable}>P2Rank (optional local)</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Druggability Threshold: {druggabilityThreshold.toFixed(2)}
          </label>
          <input
            type="range" min={0} max={1} step={0.05}
            value={druggabilityThreshold}
            onChange={(e) => setDruggabilityThreshold(parseFloat(e.target.value))}
            className="w-full accent-[var(--accent)]"
          />
          <div className="flex justify-between text-[10px]" style={{ color: "var(--text-muted)" }}>
            <span>0.0 (all)</span><span>1.0 (strict)</span>
          </div>
        </div>
      </div>
      {nativeSummary && (
        <div className="rounded-lg border px-3 py-2 text-[11px] text-[var(--text-muted)] mb-4" style={{ borderColor: "var(--border)" }}>
          {nativeSummary}
        </div>
      )}
      {selectedCapability.available !== true && (
        <div className="rounded-lg border px-3 py-2 text-[11px] text-amber-700 mb-4" style={{ borderColor: "rgba(217,119,6,0.25)", background: "rgba(254,243,199,0.7)" }}>
          {selectedCapability.details || selectedCapability.install_hint || `${method} is unavailable in this runtime.`}
        </div>
      )}
      <RunButton status={lab.status} onClick={run} disabled={selectedCapability.available !== true} />
      <ResultArea
        status={lab.status} error={lab.error} result={lab.result}
        runId={lab.runId} pollCount={lab.pollCount} wsProgress={lab.wsProgress}
        labKey="target-discovery" labTitle="Target Discovery Lab"
      />
    </>
  );
}

/* ── ADMET Batch Form (X-2.2) ─────────────────────────── */
function AdmetForm() {
  const [smiles, setSmiles] = useState("");
  const [fileUpload, setFileUpload] = useState<File | null>(null);
  const lab = useLabRun("admet");

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileUpload(file);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      if (text) setSmiles(text);
    };
    reader.readAsText(file);
  };

  const smilesCount = useMemo(
    () => smiles.split("\n").map((s) => s.trim()).filter(Boolean).length,
    [smiles],
  );

  const run = () => {
    const list = smiles.split("\n").map((s) => s.trim()).filter(Boolean);
    if (list.length === 0) {
      lab.submit(() => Promise.reject(new Error("Enter at least one SMILES string.")));
      return;
    }
    lab.submit(() => labsAdmetRunAPI(list));
  };

  return (
    <>
      <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
        SMILES (one per line)
      </label>
      <textarea
        value={smiles} onChange={(e) => setSmiles(e.target.value)}
        rows={5} placeholder={"CC(=O)Oc1ccccc1C(=O)O\nCCO\nc1ccccc1"}
        className="w-full rounded border p-3 text-sm font-mono resize-y mb-2"
        style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
      />
      <div className="flex items-center gap-3 mb-4">
        <label
          className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium cursor-pointer hover:opacity-80"
          style={{ background: "rgba(59,130,246,0.1)", color: "#3b82f6" }}
        >
          <Upload size={12} /> Upload File
          <input type="file" accept=".txt,.csv,.smi" onChange={handleFileUpload} className="hidden" />
        </label>
        {fileUpload && (
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>{fileUpload.name}</span>
        )}
        <span className="text-xs ml-auto px-2 py-0.5 rounded-full font-medium"
          style={{ background: smilesCount > 0 ? "rgba(34,197,94,0.12)" : "rgba(156,163,175,0.12)", color: smilesCount > 0 ? "#16a34a" : "var(--text-muted)" }}>
          {smilesCount} molecule{smilesCount !== 1 ? "s" : ""}
        </span>
      </div>
      <RunButton status={lab.status} onClick={run} />
      <ResultArea
        status={lab.status} error={lab.error} result={lab.result}
        runId={lab.runId} pollCount={lab.pollCount} wsProgress={lab.wsProgress}
        labKey="admet" labTitle="ADMET Prediction Lab"
      />
    </>
  );
}

/* ── Retrosynthesis Form (X-2.3) ──────────────────────── */
function RetrosynthesisForm() {
  const [smiles, setSmiles] = useState("");
  const [maxSteps, setMaxSteps] = useState(6);
  const [commercialOnly, setCommercialOnly] = useState(true);
  const lab = useLabRun("retrosynthesis");

  const run = () => {
    if (!smiles.trim()) {
      lab.submit(() => Promise.reject(new Error("Enter a SMILES string.")));
      return;
    }
    lab.submit(() =>
      labsRetrosynthesisRunAPI(smiles.trim()),
    );
  };

  return (
    <>
      <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
        Target Molecule SMILES
      </label>
      <input
        type="text" value={smiles} onChange={(e) => setSmiles(e.target.value)}
        placeholder="e.g. CC(=O)Oc1ccccc1C(=O)O" className="rounded border px-3 py-1.5 text-sm w-full mb-4"
        style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Max Retrosynthetic Steps
          </label>
          <select
            value={maxSteps} onChange={(e) => setMaxSteps(Number(e.target.value))}
            className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            {[2, 3, 4, 5, 6, 8, 10].map((n) => (
              <option key={n} value={n}>{n} steps</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Commercial Reagents Only
          </label>
          <button
            onClick={() => setCommercialOnly(!commercialOnly)}
            className="flex items-center gap-2 rounded border px-3 py-1.5 text-sm w-full text-left"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            {commercialOnly ? <ToggleRight size={16} style={{ color: "#22c55e" }} /> : <ToggleLeft size={16} style={{ color: "var(--text-muted)" }} />}
            {commercialOnly ? "Yes — commercial only" : "No — include all reagents"}
          </button>
        </div>
      </div>
      <RunButton status={lab.status} onClick={run} />
      <ResultArea
        status={lab.status} error={lab.error} result={lab.result}
        runId={lab.runId} pollCount={lab.pollCount} wsProgress={lab.wsProgress}
        labKey="retrosynthesis" labTitle="Retrosynthesis Lab"
      />
    </>
  );
}

/* ── Vaccine Design Form (X-2.4) ──────────────────────── */
function VaccineForm() {
  const [sequence, setSequence] = useState("");
  const [population, setPopulation] = useState("global");
  const [epitopes, setEpitopes] = useState("");
  const [adjuvant, setAdjuvant] = useState("alum");
  const lab = useLabRun("vaccine");

  const run = () => {
    if (!sequence.trim()) {
      lab.submit(() => Promise.reject(new Error("Enter a protein sequence.")));
      return;
    }
    const epitopeList = epitopes.split(",").map((s) => s.trim()).filter(Boolean);
    lab.submit(() =>
      labsVaccineRunAPI(sequence.trim(), {
        population_context: population,
        target_epitopes: epitopeList,
        adjuvant,
      }),
    );
  };

  return (
    <>
      <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
        Pathogen Protein Sequence
      </label>
      <textarea
        value={sequence} onChange={(e) => setSequence(e.target.value)}
        rows={4} placeholder="MFVFLVLLPLVSSQ…" className="w-full rounded border p-3 text-sm font-mono resize-y mb-3"
        style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Population Context
          </label>
          <select
            value={population} onChange={(e) => setPopulation(e.target.value)}
            className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            <option value="global">Global</option>
            <option value="south-asian">South Asian</option>
            <option value="east-asian">East Asian</option>
            <option value="european">European</option>
            <option value="african">African</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Adjuvant Selection
          </label>
          <select
            value={adjuvant} onChange={(e) => setAdjuvant(e.target.value)}
            className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            <option value="alum">Alum (Aluminum salts)</option>
            <option value="mf59">MF59</option>
            <option value="as03">AS03</option>
            <option value="as04">AS04</option>
            <option value="cpg">CpG ODN</option>
            <option value="none">None</option>
          </select>
        </div>
      </div>
      <div className="mb-4">
        <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
          Target Epitopes (comma-separated, optional)
        </label>
        <input
          type="text" value={epitopes} onChange={(e) => setEpitopes(e.target.value)}
          placeholder="e.g. YLQPRTFLL, NYNYLYRLF" className="rounded border px-3 py-1.5 text-sm w-full"
          style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
        />
      </div>
      <RunButton status={lab.status} onClick={run} />
      <ResultArea
        status={lab.status} error={lab.error} result={lab.result}
        runId={lab.runId} pollCount={lab.pollCount} wsProgress={lab.wsProgress}
        labKey="vaccine" labTitle="Vaccine Design Lab"
      />
    </>
  );
}

/* ── Molecule Generation Form (X-2.5) ─────────────────── */
function MoleculeGenerationForm() {
  const [targetId, setTargetId] = useState("");
  const [numCandidates, setNumCandidates] = useState(10);
  const [mwMin, setMwMin] = useState(200);
  const [mwMax, setMwMax] = useState(600);
  const [logPMin, setLogPMin] = useState(-1);
  const [logPMax, setLogPMax] = useState(5);
  const [genMethod, setGenMethod] = useState<"rl" | "diffusion">("rl");
  const lab = useLabRun("molecule-generation");

  const run = () => {
    if (!targetId.trim()) {
      lab.submit(() => Promise.reject(new Error("Enter a target identifier.")));
      return;
    }
    lab.submit(() =>
      labsMoleculeGenerationRunAPI(targetId.trim(), {
        num_candidates: numCandidates,
        constraints: {
          mw_range: [mwMin, mwMax],
          logp_range: [logPMin, logPMax],
        },
        generation_method: genMethod,
      }),
    );
  };

  return (
    <>
      <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
        Target Gene / Protein
      </label>
      <input
        type="text" value={targetId} onChange={(e) => setTargetId(e.target.value)}
        placeholder="e.g. BRAF, P15056" className="rounded border px-3 py-1.5 text-sm w-full mb-4"
        style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
      />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Candidates
          </label>
          <select
            value={numCandidates} onChange={(e) => setNumCandidates(Number(e.target.value))}
            className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            {[5, 10, 20, 50, 100].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Generation Method
          </label>
          <button
            onClick={() => setGenMethod(genMethod === "rl" ? "diffusion" : "rl")}
            className="flex items-center gap-2 rounded border px-3 py-1.5 text-sm w-full text-left"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            {genMethod === "rl" ? <ToggleLeft size={16} style={{ color: "#ec4899" }} /> : <ToggleRight size={16} style={{ color: "#8b5cf6" }} />}
            {genMethod === "rl" ? "RL (PPO)" : "Diffusion"}
          </button>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            MW Range
          </label>
          <div className="flex items-center gap-1">
            <input
              type="number" value={mwMin} onChange={(e) => setMwMin(Number(e.target.value))}
              className="rounded border px-2 py-1.5 text-sm w-full"
              style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
            />
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>–</span>
            <input
              type="number" value={mwMax} onChange={(e) => setMwMax(Number(e.target.value))}
              className="rounded border px-2 py-1.5 text-sm w-full"
              style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
            />
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            LogP Range
          </label>
          <div className="flex items-center gap-1">
            <input
              type="number" step={0.5} value={logPMin} onChange={(e) => setLogPMin(Number(e.target.value))}
              className="rounded border px-2 py-1.5 text-sm w-full"
              style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
            />
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>–</span>
            <input
              type="number" step={0.5} value={logPMax} onChange={(e) => setLogPMax(Number(e.target.value))}
              className="rounded border px-2 py-1.5 text-sm w-full"
              style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
            />
          </div>
        </div>
      </div>
      <RunButton status={lab.status} onClick={run} />
      <ResultArea
        status={lab.status} error={lab.error} result={lab.result}
        runId={lab.runId} pollCount={lab.pollCount} wsProgress={lab.wsProgress}
        labKey="molecule-generation" labTitle="Molecule Generation Lab"
      />
    </>
  );
}


/* ── Pocket Detection Form (X-2.6) — NEW LAB ──────────── */
function PocketDetectionForm() {
  const [pdbId, setPdbId] = useState("");
  const [method, setMethod] = useState<"fpocket" | "p2rank">("fpocket");
  const lab = useLabRun("pocket-detection");
  const { fpocket, p2rank, nativeSummary } = useNativeToolCapabilities();
  const fpocketAvailable = fpocket.available === true;
  const p2rankAvailable = p2rank.available === true;
  const selectedCapability = method === "fpocket" ? fpocket : p2rank;

  useEffect(() => {
    if (method === "fpocket" && !fpocketAvailable && p2rankAvailable) {
      setMethod("p2rank");
    }
    if (method === "p2rank" && !p2rankAvailable && fpocketAvailable) {
      setMethod("fpocket");
    }
  }, [method, fpocketAvailable, p2rankAvailable]);

  const run = () => {
    if (!(selectedCapability.available === true)) {
      lab.submit(() => Promise.reject(new Error(`${method} is not installed in this runtime. Pocket detection native tools are optional local-only capabilities.`)));
      return;
    }
    if (!pdbId.trim()) {
      lab.submit(() => Promise.reject(new Error("Enter a PDB ID.")));
      return;
    }
    lab.submit(() =>
      labsPocketRunAPI("", {
        pdb_id: pdbId.trim(),
        method,
      }),
    );
  };

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            PDB ID
          </label>
          <input
            type="text" value={pdbId} onChange={(e) => setPdbId(e.target.value)}
            placeholder="e.g. 1M17, 6LU7" className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          />
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Detection Method
          </label>
          <select
            value={method} onChange={(e) => setMethod(e.target.value as "fpocket" | "p2rank")}
            className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            <option value="fpocket" disabled={!fpocketAvailable}>fpocket (geometry-based, optional local)</option>
            <option value="p2rank" disabled={!p2rankAvailable}>P2Rank (ML-based, optional local)</option>
          </select>
        </div>
      </div>
      {nativeSummary && (
        <div className="rounded-lg border px-3 py-2 text-[11px] text-[var(--text-muted)] mb-4" style={{ borderColor: "var(--border)" }}>
          {nativeSummary}
        </div>
      )}
      {selectedCapability.available !== true && (
        <div className="rounded-lg border px-3 py-2 text-[11px] text-amber-700 mb-4" style={{ borderColor: "rgba(217,119,6,0.25)", background: "rgba(254,243,199,0.7)" }}>
          {selectedCapability.details || selectedCapability.install_hint || `${method} is unavailable in this runtime.`}
        </div>
      )}
      <RunButton status={lab.status} onClick={run} disabled={selectedCapability.available !== true} />
      <ResultArea
        status={lab.status} error={lab.error} result={lab.result}
        runId={lab.runId} pollCount={lab.pollCount} wsProgress={lab.wsProgress}
        labKey="pocket-detection" labTitle="Pocket Detection Lab"
      />
    </>
  );
}

/* ── Metabolic Engineering Form (X-2.7) ───────────────── */
function MetabolicEngineeringForm() {
  const [organismId, setOrganismId] = useState("");
  const [targetCompound, setTargetCompound] = useState("");
  const [pathway, setPathway] = useState("auto");
  const [objective, setObjective] = useState("maximize_yield");
  const lab = useLabRun("metabolic-engineering");

  const run = () => {
    if (!organismId.trim() || !targetCompound.trim()) {
      lab.submit(() => Promise.reject(new Error("Enter both organism and target compound.")));
      return;
    }
    lab.submit(() => labsMetabolicEngineeringRunAPI(organismId.trim(), targetCompound.trim()));
  };

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Organism ID
          </label>
          <input
            type="text" value={organismId} onChange={(e) => setOrganismId(e.target.value)}
            placeholder="e.g. eco (E. coli), sce (S. cerevisiae)" className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          />
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Target Compound
          </label>
          <input
            type="text" value={targetCompound} onChange={(e) => setTargetCompound(e.target.value)}
            placeholder="e.g. Artemisinin, Lycopene" className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Pathway Selection
          </label>
          <select
            value={pathway} onChange={(e) => setPathway(e.target.value)}
            className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            <option value="auto">Auto-detect (recommended)</option>
            <option value="mevalonate">Mevalonate pathway</option>
            <option value="mep">MEP/DOXP pathway</option>
            <option value="shikimate">Shikimate pathway</option>
            <option value="polyketide">Polyketide pathway</option>
            <option value="fatty_acid">Fatty acid synthesis</option>
            <option value="amino_acid">Amino acid biosynthesis</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Optimization Objective
          </label>
          <select
            value={objective} onChange={(e) => setObjective(e.target.value)}
            className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            <option value="maximize_yield">Maximize Yield</option>
            <option value="maximize_titer">Maximize Titer</option>
            <option value="minimize_byproducts">Minimize Byproducts</option>
            <option value="maximize_growth">Maximize Growth Rate</option>
            <option value="balanced">Balanced (yield + growth)</option>
          </select>
        </div>
      </div>
      <RunButton status={lab.status} onClick={run} />
      <ResultArea
        status={lab.status} error={lab.error} result={lab.result}
        runId={lab.runId} pollCount={lab.pollCount} wsProgress={lab.wsProgress}
        labKey="metabolic-engineering" labTitle="Metabolic Engineering Lab"
      />
    </>
  );
}

/* ── Pharmacogenomics Form (X-2.8) ────────────────────── */
function PharmacogenomicsForm() {
  const [geneSymbol, setGeneSymbol] = useState("");
  const [drugId, setDrugId] = useState("");
  const [population, setPopulation] = useState("global");
  const [variantFilter, setVariantFilter] = useState("all");
  const lab = useLabRun("pharmacogenomics");

  const run = () => {
    if (!geneSymbol.trim() || !drugId.trim()) {
      lab.submit(() => Promise.reject(new Error("Enter both gene symbol and drug.")));
      return;
    }
    lab.submit(() => labsPharmacogenomicsRunAPI(geneSymbol.trim(), population));
  };

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Gene Symbol
          </label>
          <input
            type="text" value={geneSymbol} onChange={(e) => setGeneSymbol(e.target.value)}
            placeholder="e.g. CYP2D6, CYP3A4" className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          />
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Drug Name / ID
          </label>
          <input
            type="text" value={drugId} onChange={(e) => setDrugId(e.target.value)}
            placeholder="e.g. Tamoxifen, DB00675" className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Population
          </label>
          <select
            value={population} onChange={(e) => setPopulation(e.target.value)}
            className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            <option value="global">Global</option>
            <option value="south-asian">South Asian</option>
            <option value="east-asian">East Asian</option>
            <option value="european">European</option>
            <option value="african">African</option>
            <option value="indian">Indian (subcontinent)</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
            Variant Filter
          </label>
          <select
            value={variantFilter} onChange={(e) => setVariantFilter(e.target.value)}
            className="rounded border px-3 py-1.5 text-sm w-full"
            style={{ borderColor: "var(--border)", background: "var(--bg-app)", color: "var(--text-primary)" }}
          >
            <option value="all">All Variants</option>
            <option value="clinically_actionable">Clinically Actionable</option>
            <option value="high_frequency">High Frequency (&gt;5%)</option>
            <option value="loss_of_function">Loss of Function</option>
            <option value="gain_of_function">Gain of Function</option>
          </select>
        </div>
      </div>
      <RunButton status={lab.status} onClick={run} />
      <ResultArea
        status={lab.status} error={lab.error} result={lab.result}
        runId={lab.runId} pollCount={lab.pollCount} wsProgress={lab.wsProgress}
        labKey="pharmacogenomics" labTitle="Pharmacogenomics Lab"
      />
    </>
  );
}

/* ── Shared Run Button ─────────────────────────────────── */
function RunButton({ status, onClick, disabled = false }: { status: RunStatus; onClick: () => void; disabled?: boolean }) {
  const busy = status === "loading" || status === "polling";
  const blocked = busy || disabled;
  return (
    <button
      onClick={onClick}
      disabled={blocked}
      className="flex items-center gap-2 rounded px-4 py-2 text-sm font-medium transition-colors mb-4"
      style={{ background: "var(--accent)", color: "#fff", opacity: blocked ? 0.6 : 1 }}
    >
      {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
      {status === "loading" ? "Submitting…" : status === "polling" ? "Running…" : disabled ? "Unavailable in this runtime" : "Run Analysis"}
    </button>
  );
}

/* ── Shared Result Area ────────────────────────────────── */
function ResultArea({
  status,
  error,
  result,
  runId,
  pollCount,
  wsProgress,
  labKey,
  labTitle,
}: {
  status: RunStatus;
  error: string;
  result: Record<string, unknown> | null;
  runId?: string | null;
  pollCount?: number;
  wsProgress?: ReturnType<typeof useRunProgress>;
  labKey?: string;
  labTitle?: string;
}) {
  if (status === "error") {
    return (
      <div
        className="rounded-lg border p-4 flex items-start gap-3"
        style={{ borderColor: "#ef4444", background: "rgba(239,68,68,0.08)" }}
      >
        <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: "#ef4444" }} />
        <p className="text-sm" style={{ color: "#ef4444" }}>{error}</p>
      </div>
    );
  }

  /* ── Polling state: show tracking banner ────────────── */
  if (status === "polling" && result) {
    const elapsed = (pollCount ?? 0) * 3;
    return (
      <div
        className="rounded-lg border p-4"
        style={{ borderColor: "#3b82f6", background: "rgba(59,130,246,0.08)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <RefreshCw size={14} className="animate-spin" style={{ color: "#3b82f6" }} />
          <span className="text-xs font-bold uppercase tracking-widest" style={{ color: "#3b82f6" }}>
            Run in Progress
          </span>
          {runId && (
            <span className="text-xs font-mono ml-auto" style={{ color: "var(--text-muted)" }}>
              {runId}
            </span>
          )}
        </div>
        {/* X-3.4: WebSocket progress bar */}
        <WsProgressBar wsProgress={wsProgress ?? null} />
        <div className="flex items-center gap-3 mb-3">
          <Clock size={12} style={{ color: "var(--text-muted)" }} />
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Polling for results… {elapsed}s elapsed
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full font-medium"
            style={{ background: "rgba(59,130,246,0.15)", color: "#3b82f6" }}>
            {String(result.status ?? "QUEUED")}
          </span>
        </div>
        <StructuredResult data={result} />
      </div>
    );
  }

  if (status === "success" && result) {
    const resultRunId = (result.run_id ?? result.id ?? runId ?? "") as string;
    return (
      <div
        className="rounded-lg border p-4"
        style={{ borderColor: "var(--border)", background: "var(--bg-app)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <CheckCircle size={16} style={{ color: "#22c55e" }} />
          <span className="text-xs font-bold uppercase tracking-widest" style={{ color: "#22c55e" }}>
            Run Complete
          </span>
          {resultRunId && (
            <span className="text-xs font-mono ml-auto" style={{ color: "var(--text-muted)" }}>
              run {resultRunId}
            </span>
          )}
        </div>
        <StructuredResult data={result} />
        <ProvenanceBar runId={resultRunId} labKey={labKey} />
        <CrossLabActions
          result={result}
          runId={resultRunId}
          labKey={labKey}
          labTitle={labTitle}
        />
      </div>
    );
  }

  return null;
}

/* ── Structured result renderer ────────────────────────── */
function StructuredResult({ data }: { data: Record<string, unknown> }) {
  const skip = new Set(["run_id", "id", "status", "request_id", "trace_id"]);
  const entries = Object.entries(data).filter(([k]) => !skip.has(k));

  if (entries.length === 0) {
    return <p className="text-xs" style={{ color: "var(--text-muted)" }}>No additional data returned.</p>;
  }

  return (
    <div className="space-y-3">
      {entries.map(([key, val]) => (
        <ResultField key={key} label={key} value={val} />
      ))}
    </div>
  );
}

function ResultField({ label, value }: { label: string; value: unknown }) {
  const niceName = label.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  // Array of objects → table
  if (Array.isArray(value) && value.length > 0 && typeof value[0] === "object" && value[0] !== null) {
    const cols = Object.keys(value[0] as Record<string, unknown>);
    return (
      <div>
        <div className="text-[10px] font-bold uppercase tracking-widest mb-1" style={{ color: "var(--text-muted)" }}>
          {niceName} ({value.length})
        </div>
        <div className="overflow-x-auto" style={{ border: "1px solid var(--border)" }}>
          <table className="w-full text-xs">
            <thead>
              <tr style={{ background: "var(--bg-surface)" }}>
                {cols.map((c) => (
                  <th key={c} className="text-left py-1.5 px-2 font-semibold" style={{ color: "var(--text-muted)" }}>
                    {c.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {value.slice(0, 50).map((row, i) => (
                <tr key={i}>
                  {cols.map((c) => (
                    <td key={c} className="py-1 px-2" style={{ borderTop: "1px solid var(--border)" }}>
                      {formatCellValue((row as Record<string, unknown>)[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // Flat object → key-value grid
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    const ents = Object.entries(value as Record<string, unknown>);
    return (
      <div>
        <div className="text-[10px] font-bold uppercase tracking-widest mb-1" style={{ color: "var(--text-muted)" }}>
          {niceName}
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 p-3 rounded" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          {ents.map(([k, v]) => (
            <div key={k} className="flex items-baseline gap-2 text-xs">
              <span className="font-medium" style={{ color: "var(--text-muted)" }}>{k.replace(/_/g, " ")}:</span>
              <span style={{ color: "var(--text-primary)" }}>{formatCellValue(v)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Primitive value
  return (
    <div className="flex items-baseline gap-2 text-xs">
      <span className="font-bold uppercase tracking-widest text-[10px]" style={{ color: "var(--text-muted)" }}>{niceName}:</span>
      <span style={{ color: "var(--text-primary)" }}>{formatCellValue(value)}</span>
    </div>
  );
}

function formatCellValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(4);
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "string") return v.length > 120 ? v.slice(0, 120) + "…" : v;
  if (Array.isArray(v)) return v.length === 0 ? "[]" : `[${v.length} items]`;
  if (typeof v === "object") return JSON.stringify(v).slice(0, 100);
  return String(v);
}

/* ── Form selector per module ──────────────────────────── */
const MODULE_FORMS: Record<string, React.FC> = {
  "target-discovery": TargetDiscoveryForm,
  admet: AdmetForm,
  retrosynthesis: RetrosynthesisForm,
  vaccine: VaccineForm,
  "molecule-generation": MoleculeGenerationForm,
  "pocket-detection": PocketDetectionForm,
  "metabolic-engineering": MetabolicEngineeringForm,
  pharmacogenomics: PharmacogenomicsForm,
};


/* ── Lab Status Badge ──────────────────────────────────── */
function LabStatusBadge({ labKey }: { labKey: string }) {
  const recentRuns = useMemo(() => loadRecentRuns(), []);
  const labRuns = recentRuns.filter((r) => r.labKey === labKey);
  const lastRun = labRuns[0];

  if (!lastRun) {
    return (
      <span className="text-[10px] px-2 py-0.5 rounded-full font-medium"
        style={{ background: "rgba(156,163,175,0.12)", color: "var(--text-muted)" }}>
        idle
      </span>
    );
  }

  const colors: Record<string, { bg: string; fg: string }> = {
    running: { bg: "rgba(59,130,246,0.12)", fg: "#3b82f6" },
    complete: { bg: "rgba(34,197,94,0.12)", fg: "#16a34a" },
    error: { bg: "rgba(239,68,68,0.12)", fg: "#ef4444" },
  };
  const c = colors[lastRun.status] || colors.running;

  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium"
      style={{ background: c.bg, color: c.fg }}>
      {lastRun.status}
    </span>
  );
}

/* ── Recent Runs Section ───────────────────────────────── */
function RecentRunsSection() {
  const recentRuns = useMemo(() => loadRecentRuns(), []);

  if (recentRuns.length === 0) {
    return (
      <div className="text-center py-6">
        <Clock size={20} className="mx-auto mb-2" style={{ color: "var(--text-muted)" }} />
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          No recent runs. Launch a lab to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {recentRuns.slice(0, 8).map((run) => {
        const labDef = LAB_MODULES[run.labKey];
        const Icon = labDef?.icon ?? FlaskConical;
        const statusColors: Record<string, string> = {
          running: "#3b82f6",
          complete: "#22c55e",
          error: "#ef4444",
        };
        const elapsed = run.startedAt
          ? (() => {
              const ms = Date.now() - new Date(run.startedAt).getTime();
              if (ms < 60000) return `${Math.round(ms / 1000)}s ago`;
              if (ms < 3600000) return `${Math.round(ms / 60000)}m ago`;
              if (ms < 86400000) return `${Math.round(ms / 3600000)}h ago`;
              return `${Math.round(ms / 86400000)}d ago`;
            })()
          : "";

        return (
          <Link
            key={run.runId}
            to={`/labs/${run.labKey}`}
            className="flex items-center gap-3 rounded-lg border p-3 hover:border-[var(--accent)] transition-colors"
            style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
          >
            <Icon size={14} style={{ color: labDef?.color ?? "var(--text-muted)" }} />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium truncate" style={{ color: "var(--text-primary)" }}>
                {run.labTitle}
              </div>
              <div className="text-[10px] font-mono truncate" style={{ color: "var(--text-muted)" }}>
                {run.runId.slice(0, 12)}… {run.summary ? `— ${run.summary}` : ""}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>{elapsed}</span>
              <div className="w-2 h-2 rounded-full" style={{ background: statusColors[run.status] ?? "#9ca3af" }} />
            </div>
          </Link>
        );
      })}
    </div>
  );
}

/* ── Hub Status Overview ───────────────────────────────── */
function HubStatusOverview() {
  const recentRuns = useMemo(() => loadRecentRuns(), []);
  const running = recentRuns.filter((r) => r.status === "running").length;
  const completed = recentRuns.filter((r) => r.status === "complete").length;
  const errors = recentRuns.filter((r) => r.status === "error").length;
  const totalLabs = Object.keys(LAB_MODULES).length;
  const activeLabs = new Set(recentRuns.map((r) => r.labKey)).size;

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
      {[
        { label: "Total Labs", value: totalLabs, icon: FlaskConical, color: "var(--accent)" },
        { label: "Labs Used", value: activeLabs, icon: Activity, color: "#8b5cf6" },
        { label: "Running", value: running, icon: Loader2, color: "#3b82f6" },
        { label: "Completed", value: completed, icon: CheckCircle, color: "#22c55e" },
        { label: "Errors", value: errors, icon: AlertTriangle, color: "#ef4444" },
      ].map((stat) => {
        const StatIcon = stat.icon;
        return (
          <div
            key={stat.label}
            className="rounded-lg border p-3 text-center"
            style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
          >
            <StatIcon size={14} className="mx-auto mb-1" style={{ color: stat.color }} />
            <div className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{stat.value}</div>
            <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>{stat.label}</div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Page Component ────────────────────────────────────── */
export default function LabsPage() {
  const { module } = useParams<{ module: string }>();
  const [handoffLabel, setHandoffLabel] = useState<string | null>(null);
  const [recommendedModule, setRecommendedModule] = useState<string | null>(null);
  const lab = module ? LAB_MODULES[module] : null;

  useEffect(() => {
    const payload = readCockpitHandoff();
    if (!payload || payload.targetRoute !== "/labs") return;
    const entity = payload.entities[0];
    const label = entity?.entityName || payload.query;
    setHandoffLabel(label || null);
    if (!entity) return;
    if (["protein", "target", "gene"].includes(entity.entityType)) {
      setRecommendedModule("target-discovery");
      return;
    }
    if (["drug", "molecule", "compound"].includes(entity.entityType)) {
      setRecommendedModule("admet");
      return;
    }
    if (entity.entityType === "pathway") {
      setRecommendedModule("metabolic-engineering");
    }
  }, []);

  /* ── Individual lab module view ─────────────────────── */
  if (lab && module) {
    const FormComponent = MODULE_FORMS[module];
    const Icon = lab.icon;
    const labViewState: ViewState = MODULE_FORMS[module] ? "success" : "empty";
    return (
      <StateWrapper
        state={labViewState}
        moduleName="Labs"
        emptyTitle="No form available"
        emptyDescription="This lab module does not have a configuration form yet."
      >
        <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
          <Link
            to="/labs"
            className="inline-flex items-center gap-1 text-xs mb-4 hover:underline"
            style={{ color: "var(--accent)" }}
          >
            <ArrowLeft size={12} /> All Labs
          </Link>
          <div className="flex items-center gap-3 mb-1">
            <Icon size={20} style={{ color: lab.color }} />
            <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
              {lab.title}
            </h1>
            <LabStatusBadge labKey={module} />
          </div>
          <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
            {lab.description}
          </p>
          {handoffLabel && (
            <div className="mb-4 px-3 py-2 rounded-lg text-xs" style={{ background: "rgba(34, 197, 94, 0.08)", border: "1px solid rgba(34, 197, 94, 0.18)", color: "#166534" }}>
              Cockpit handoff loaded for {handoffLabel}.
            </div>
          )}

          <div
            className="rounded-lg border p-5"
            style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <FlaskConical size={14} style={{ color: lab.color }} />
              <span
                className="text-xs uppercase tracking-widest font-bold"
                style={{ color: lab.color }}
              >
                Configure &amp; Run
              </span>
            </div>
            {FormComponent ? <FormComponent /> : <p className="text-sm" style={{ color: "var(--text-muted)" }}>No form available for this lab module.</p>}
          </div>
        </div>
      </StateWrapper>
    );
  }

  const labEntries = Object.entries(LAB_MODULES);
  const viewState: ViewState = labEntries.length === 0 ? "empty" : "success";

  /* ── Hub view (X-1.1 redesign) ──────────────────────── */
  return (
    <StateWrapper
      state={viewState}
      moduleName="Labs"
      emptyTitle="No lab modules"
      emptyDescription="Research lab modules will appear here once configured."
    >
      <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
              Research Labs
            </h1>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Specialized analysis modules for target discovery, ADMET, retrosynthesis, vaccine design, and more.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <FlaskConical size={24} style={{ color: "var(--accent)" }} />
          </div>
        </div>

        {handoffLabel && (
          <div className="mb-6 px-4 py-3 rounded-lg flex items-center justify-between gap-3 flex-wrap" style={{ background: "rgba(34, 197, 94, 0.08)", border: "1px solid rgba(34, 197, 94, 0.18)" }}>
            <div>
              <div className="text-xs font-semibold" style={{ color: "#166534" }}>Cockpit handoff loaded</div>
              <div className="text-[11px]" style={{ color: "var(--text-primary)" }}>{handoffLabel}</div>
            </div>
            {recommendedModule ? (
              <Link to={`/labs/${recommendedModule}`} className="text-xs font-semibold hover:underline" style={{ color: "var(--accent)" }}>
                Open recommended lab →
              </Link>
            ) : null}
          </div>
        )}

        {/* Status Overview */}
        <HubStatusOverview />

        {/* Lab Cards with quick-launch and status */}
        <div className="mb-6">
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>
            Available Labs
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(LAB_MODULES).map(([key, info]) => {
              const Icon = info.icon;
              return (
                <div
                  key={key}
                  className="rounded-lg border p-5 group"
                  style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Icon size={18} style={{ color: info.color }} />
                    <h3 className="text-sm font-semibold flex-1" style={{ color: "var(--text-primary)" }}>
                      {info.title}
                    </h3>
                    <LabStatusBadge labKey={key} />
                  </div>
                  <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>
                    {info.description}
                  </p>
                  <Link
                    to={`/labs/${key}`}
                    className="inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors hover:opacity-80"
                    style={{ background: info.color, color: "#fff" }}
                  >
                    <Play size={11} /> Launch Lab
                  </Link>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Runs */}
        <div>
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>
            Recent Runs
          </h2>
          <div
            className="rounded-lg border p-4"
            style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
          >
            <RecentRunsSection />
          </div>
        </div>
      </div>
    </StateWrapper>
  );
}
