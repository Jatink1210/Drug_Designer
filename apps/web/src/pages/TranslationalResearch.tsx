import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Brain,
  CheckCircle2,
  ClipboardList,
  Database,
  Download,
  ExternalLink,
  FileText,
  FlaskConical,
  Layers,
  Loader2,
  Microscope,
  Plus,
  Shield,
  Sparkles,
  Target,
} from "lucide-react";
import { ensureApiBase } from "@/lib/api";
import StateWrapper from "@/components/ui/StateWrapper";
import { persistCockpitHandoff, readCockpitHandoff } from "@/lib/canonicalProduct";
import type { ViewState } from "@/lib/types";

interface Artifact {
  artifact_type: string;
  content: Record<string, unknown>;
  created_at?: string;
}

interface Project {
  id: string;
  name: string;
  description: string;
  current_stage: string;
  artifacts?: Artifact[];
  created_at?: string;
  updated_at?: string;
}

type StageStatus = "idle" | "running" | "success" | "error";

interface StageExecution {
  status: StageStatus;
  label: string;
  request?: Record<string, unknown>;
  data?: Record<string, unknown>;
  provenance?: Record<string, unknown>;
  error?: string;
  updatedAt?: string;
}

const CLINICAL_STEPS = [
  { id: 1, key: "intake", label: "Project Intake", icon: ClipboardList, color: "#0f766e", requirements: "Project name, scope, disease/topic" },
  { id: 2, key: "evidence", label: "Clinical Evidence Ingestion", icon: FileText, color: "#0f766e", requirements: "Patient ID, clinical note, record type" },
  { id: 3, key: "phenotype", label: "Phenotype Review", icon: Brain, color: "#2563eb", requirements: "EHR record IDs, clustering settings" },
  { id: 4, key: "tissue", label: "Tissue / Context Mapping", icon: Microscope, color: "#7c3aed", requirements: "Image reference, analysis type" },
  { id: 5, key: "biomarker", label: "Biomarker Definition", icon: Database, color: "#9333ea", requirements: "Sample ID, FCS reference" },
  { id: 6, key: "genomics", label: "Genomics / Variant Review", icon: Activity, color: "#db2777", requirements: "VCF reference, variant list" },
  { id: 7, key: "disruption", label: "Pathway Disruption Analysis", icon: Layers, color: "#ea580c", requirements: "Variant IDs" },
  { id: 8, key: "drug-match", label: "AI Drug Matching", icon: Target, color: "#d97706", requirements: "Disrupted pathways, genes, patient context" },
  { id: 9, key: "therapy", label: "Therapy Stratification / Trials", icon: Shield, color: "#16a34a", requirements: "Patient profile, therapy types, disease keyword" },
  { id: 10, key: "review", label: "Export / Handoff / Review", icon: Sparkles, color: "#0891b2", requirements: "Bundle review, export, next-step routing" },
] as const;

function parseCsv(text: string): string[] {
  return text
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function safeParseJson(text: string, fallback: Record<string, unknown> = {}): Record<string, unknown> {
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return fallback;
  }
}

function safeParseVariantList(text: string): Array<Record<string, unknown>> {
  try {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed) ? (parsed as Array<Record<string, unknown>>) : [];
  } catch {
    return [];
  }
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function StatusPill({ status }: { status: StageStatus }) {
  const palette = {
    idle: "bg-slate-100 text-slate-600",
    running: "bg-blue-50 text-blue-600",
    success: "bg-emerald-50 text-emerald-600",
    error: "bg-red-50 text-red-600",
  } as const;
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${palette[status]}`}>{status}</span>;
}

function JsonPreview({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
      <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">{title}</div>
      <pre className="text-[10px] leading-5 whitespace-pre-wrap break-words text-[var(--text-secondary)]">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

function StageResultPanel({
  step,
  execution,
  onBundle,
}: {
  step: (typeof CLINICAL_STEPS)[number];
  execution?: StageExecution;
  onBundle: () => void;
}) {
  if (!execution) {
    return (
      <div className="rounded-xl border p-4 text-sm text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}>
        Run this step to inspect outputs, provenance, and export controls.
      </div>
    );
  }

  return (
    <div className="rounded-xl border p-4 space-y-3" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-[var(--text-primary)]">{step.label}</div>
          <div className="text-[11px] text-[var(--text-muted)]">{execution.label}</div>
        </div>
        <StatusPill status={execution.status} />
      </div>

      {execution.error && <div className="text-xs text-red-600">{execution.error}</div>}

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => navigator.clipboard.writeText(JSON.stringify(execution.data ?? {}, null, 2))}
          className="px-3 py-1.5 text-[11px] rounded-lg border"
          style={{ borderColor: "var(--border)" }}
        >
          Copy JSON
        </button>
        <button
          onClick={() => downloadJson(`${step.key}_artifact.json`, execution.data ?? {})}
          className="px-3 py-1.5 text-[11px] rounded-lg border"
          style={{ borderColor: "var(--border)" }}
        >
          Export JSON
        </button>
        <button
          onClick={onBundle}
          className="px-3 py-1.5 text-[11px] rounded-lg border"
          style={{ borderColor: "var(--border)" }}
        >
          Save to Review Bundle
        </button>
      </div>

      {execution.request && <JsonPreview title="Input requirements / request" value={execution.request} />}
      {execution.data && <JsonPreview title="Output artifacts" value={execution.data} />}
      {execution.provenance && <JsonPreview title="Evidence links / provenance" value={execution.provenance} />}
      {execution.updatedAt && <div className="text-[10px] text-[var(--text-muted)]">Updated {execution.updatedAt}</div>}
    </div>
  );
}

export default function TranslationalResearch() {
  const navigate = useNavigate();
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeStepId, setActiveStepId] = useState(1);
  const [bundleSteps, setBundleSteps] = useState<number[]>([]);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [stageExecutions, setStageExecutions] = useState<Record<number, StageExecution>>({});
  const [inputs, setInputs] = useState({
    topic: "",
    patientId: "PATIENT-001",
    recordType: "clinical_note",
    rawText: "",
    picoText: "",
    ehrRecordIds: "",
    minClusterSize: "5",
    imageRef: "",
    analysisType: "histopathology",
    sampleId: "",
    fcsFileRef: "",
    vcfFileRef: "",
    variantsJson: JSON.stringify([{ gene: "TP53", hgvs: "p.R175H" }], null, 2),
    variantIds: "",
    disruptedPathways: "",
    geneSymbols: "",
    patientContextJson: JSON.stringify({ age: 57, diagnosis: "seed topic", comorbidities: ["hypertension"] }, null, 2),
    patientProfileJson: JSON.stringify({ age: 57, diagnosis: "seed topic", genetic_profile: {}, hla_type: "unknown" }, null, 2),
    therapyTypes: "targeted therapy, immunotherapy",
    trialDisease: "",
  });

  useEffect(() => {
    ensureApiBase().then(setApiBase);
  }, []);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) || null,
    [projects, selectedProjectId],
  );

  const setExecution = useCallback((stepId: number, execution: StageExecution) => {
    setStageExecutions((current) => ({ ...current, [stepId]: execution }));
  }, []);

  const requestJson = useCallback(
    async (path: string, body?: Record<string, unknown>, method: "GET" | "POST" = "POST") => {
      if (!apiBase) throw new Error("API base unavailable");
      const response = await fetch(`${apiBase}${path}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail || `Request failed with status ${response.status}`);
      }
      return {
        data: (payload?.data ?? payload) as Record<string, unknown>,
        provenance: (payload?.provenance ?? null) as Record<string, unknown> | null,
      };
    },
    [apiBase],
  );

  const fetchProjects = useCallback(async () => {
    if (!apiBase) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/translational/projects`);
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error("Failed to load clinical projects");
      const nextProjects = (payload?.data ?? payload ?? []) as Project[];
      setProjects(nextProjects);
      if (!selectedProjectId && nextProjects.length > 0) {
        setSelectedProjectId(nextProjects[0].id);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load clinical projects");
    } finally {
      setLoading(false);
    }
  }, [apiBase, selectedProjectId]);

  useEffect(() => {
    if (apiBase) fetchProjects();
  }, [apiBase, fetchProjects]);

  useEffect(() => {
    const payload = readCockpitHandoff();
    if (!payload || payload.targetRoute !== "/clinical-design") return;
    const seededTopic = payload.entities[0]?.entityName || payload.query;
    if (!seededTopic) return;
    setProjectName((current) => current || seededTopic.slice(0, 72));
    setProjectDescription((current) => current || `Clinical pipeline seeded from cockpit handoff for ${seededTopic}`);
    setInputs((current) => ({
      ...current,
      topic: current.topic || seededTopic,
      rawText: current.rawText || seededTopic,
      picoText: current.picoText || seededTopic,
      geneSymbols: current.geneSymbols || seededTopic,
      trialDisease: current.trialDisease || seededTopic,
      patientContextJson: current.patientContextJson.includes("seed topic")
        ? JSON.stringify({ age: 57, diagnosis: seededTopic, comorbidities: ["hypertension"] }, null, 2)
        : current.patientContextJson,
      patientProfileJson: current.patientProfileJson.includes("seed topic")
        ? JSON.stringify({ age: 57, diagnosis: seededTopic, genetic_profile: {}, hla_type: "unknown" }, null, 2)
        : current.patientProfileJson,
    }));
  }, []);

  const createProject = async () => {
    if (!apiBase || !projectName.trim()) return;
    setError(null);
    try {
      const response = await fetch(`${apiBase}/translational/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: projectName,
          description: projectDescription || `Clinical design pipeline for ${projectName}`,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || "Failed to create project");
      const created = (payload?.data ?? payload) as Project;
      setSelectedProjectId(created.id);
      setProjectName("");
      setProjectDescription("");
      setActiveStepId(2);
      await fetchProjects();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to create project");
    }
  };

  const runStage = async (
    stepId: number,
    label: string,
    requestBody: Record<string, unknown>,
    runner: () => Promise<{ data: Record<string, unknown>; provenance: Record<string, unknown> | null }>,
  ) => {
    setExecution(stepId, {
      status: "running",
      label,
      request: requestBody,
      updatedAt: new Date().toLocaleString(),
    });
    try {
      const result = await runner();
      setExecution(stepId, {
        status: "success",
        label,
        request: requestBody,
        data: result.data,
        provenance: result.provenance || undefined,
        updatedAt: new Date().toLocaleString(),
      });
      setBundleSteps((current) => Array.from(new Set([...current, stepId])).sort((left, right) => left - right));
    } catch (nextError) {
      setExecution(stepId, {
        status: "error",
        label,
        request: requestBody,
        error: nextError instanceof Error ? nextError.message : "Stage execution failed",
        updatedAt: new Date().toLocaleString(),
      });
    }
  };

  const executeEvidenceStage = async () => {
    if (!selectedProject) return;
    const ingestRequest = {
      record_type: inputs.recordType,
      raw_text: inputs.rawText,
      patient_id: inputs.patientId,
      project_id: selectedProject.id,
    };
    await runStage(2, "Clinical evidence ingested", ingestRequest, async () => {
      const ingest = await requestJson("/clinical/ingest", ingestRequest);
      const pico = inputs.picoText.trim()
        ? await requestJson("/clinical/pico/extract", { text: inputs.picoText, use_llm: true })
        : null;
      return {
        data: {
          ingest: ingest.data,
          pico: pico?.data ?? null,
        },
        provenance: {
          ingest: ingest.provenance,
          pico: pico?.provenance ?? null,
        },
      };
    });
  };

  const executePhenotypeStage = async () => {
    if (!selectedProject) return;
    const requestBody = {
      ehr_record_ids: parseCsv(inputs.ehrRecordIds),
      min_cluster_size: Number(inputs.minClusterSize || 5),
      project_id: selectedProject.id,
    };
    await runStage(3, "Phenotype clusters refreshed", requestBody, async () => requestJson("/clinical/phenotype-cluster", requestBody));
  };

  const executeTissueStage = async () => {
    if (!selectedProject) return;
    const requestBody = {
      image_ref: inputs.imageRef,
      analysis_type: inputs.analysisType,
      project_id: selectedProject.id,
    };
    await runStage(4, "Tissue context mapped", requestBody, async () => requestJson("/clinical/tissue-analysis", requestBody));
  };

  const executeBiomarkerStage = async () => {
    if (!selectedProject) return;
    const requestBody = {
      sample_id: inputs.sampleId,
      fcs_file_ref: inputs.fcsFileRef,
      project_id: selectedProject.id,
    };
    await runStage(5, "Biomarkers quantified", requestBody, async () => requestJson("/clinical/biomarker-quantify", requestBody));
  };

  const executeGenomicsStage = async () => {
    if (!selectedProject) return;
    const sequencingRequest = {
      vcf_file_ref: inputs.vcfFileRef,
      patient_id: inputs.patientId,
      project_id: selectedProject.id,
    };
    await runStage(6, "Genomics and variant review complete", sequencingRequest, async () => {
      const sequencing = await requestJson("/clinical/genomic-sequence", sequencingRequest);
      const pathogenicityRequest = {
        variants: safeParseVariantList(inputs.variantsJson),
        project_id: selectedProject.id,
      };
      const pathogenicity = await requestJson("/clinical/pathogenicity-predict", pathogenicityRequest);
      return {
        data: {
          sequencing: sequencing.data,
          pathogenicity: pathogenicity.data,
        },
        provenance: {
          sequencing: sequencing.provenance,
          pathogenicity: pathogenicity.provenance,
        },
      };
    });
  };

  const executeDisruptionStage = async () => {
    if (!selectedProject) return;
    const requestBody = {
      variant_ids: parseCsv(inputs.variantIds),
      project_id: selectedProject.id,
    };
    await runStage(7, "Pathway disruption modeled", requestBody, async () => requestJson("/clinical/disruption-model", requestBody));
  };

  const executeDrugMatchStage = async () => {
    if (!selectedProject) return;
    const requestBody = {
      disrupted_pathways: parseCsv(inputs.disruptedPathways),
      gene_symbols: parseCsv(inputs.geneSymbols),
      patient_context: safeParseJson(inputs.patientContextJson, {}),
      project_id: selectedProject.id,
    };
    await runStage(8, "Drug matching refreshed", requestBody, async () => requestJson("/clinical/drug-match", requestBody));
  };

  const executeTherapyStage = async () => {
    if (!selectedProject) return;
    const requestBody = {
      patient_profile: safeParseJson(inputs.patientProfileJson, {}),
      therapy_types: parseCsv(inputs.therapyTypes),
      project_id: selectedProject.id,
    };
    await runStage(9, "Therapy stratification complete", requestBody, async () => {
      const therapy = await requestJson("/clinical/therapy-stratify", requestBody);
      const trials = inputs.trialDisease.trim()
        ? await requestJson(`/clinical/india-trials/${encodeURIComponent(inputs.trialDisease)}`, undefined, "GET")
        : null;
      return {
        data: {
          therapy: therapy.data,
          india_trials: trials?.data ?? null,
        },
        provenance: {
          therapy: therapy.provenance,
          india_trials: trials?.provenance ?? null,
        },
      };
    });
  };

  const exportMarkdownBundle = async () => {
    if (!apiBase || !selectedProject) return;
    const response = await fetch(`${apiBase}/translational/projects/${selectedProject.id}/export`);
    const payload = await response.json().catch(() => null);
    if (!response.ok) throw new Error("Failed to export markdown evidence bundle");
    const report = payload?.data?.markdown_report || payload?.markdown_report || "# No report available";
    const blob = new Blob([report], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${selectedProject.name.replace(/\s+/g, "_").toLowerCase()}_clinical_bundle.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const reviewBundle = useMemo(
    () => ({
      project: selectedProject,
      included_steps: bundleSteps,
      stages: bundleSteps.reduce<Record<number, StageExecution>>((bundle, stepId) => {
        if (stageExecutions[stepId]) bundle[stepId] = stageExecutions[stepId];
        return bundle;
      }, {}),
    }),
    [bundleSteps, selectedProject, stageExecutions],
  );

  const handoffGenes = useMemo(() => parseCsv(inputs.geneSymbols).slice(0, 8), [inputs.geneSymbols]);

  const sendGenesToPathways = () => {
    if (handoffGenes.length === 0) return;
    persistCockpitHandoff({
      version: "phase0.v1",
      sourceModule: "clinical-design",
      action: "open_in_pathways",
      targetRoute: "/pathways",
      query: handoffGenes.join(", "),
      createdAt: new Date().toISOString(),
      entities: handoffGenes.map((gene) => ({
        entityId: gene,
        entityType: "gene",
        entityName: gene,
        sourceCategory: "clinical-design",
        identifiers: { symbol: gene },
      })),
      provenance: [{
        source: "Clinical Design Pipeline",
        retrievedAt: new Date().toISOString(),
      }],
      metadata: { step: "drug-match", projectId: selectedProject?.id },
    });
    navigate("/pathways");
  };

  const activeStep = CLINICAL_STEPS.find((step) => step.id === activeStepId) || CLINICAL_STEPS[0];
  const activeExecution = stageExecutions[activeStep.id];
  const viewState: ViewState = loading ? "loading" : error ? "error" : "success";

  return (
    <StateWrapper state={viewState} moduleName="Clinical Design Pipeline">
      <div className="flex-1 flex overflow-hidden" style={{ background: "var(--bg-app)" }}>
        <div className="w-[310px] glass-sidebar border-r flex flex-col overflow-hidden">
          <div className="p-4 border-b" style={{ borderColor: "var(--border)" }}>
            <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2 mb-3">
              <FlaskConical size={15} className="text-[var(--accent)]" /> Clinical Design
            </h2>
            <div className="space-y-2">
              <input
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="Project intake name"
                className="w-full px-3 py-2 text-xs rounded-lg border"
                style={{ borderColor: "var(--border)" }}
              />
              <textarea
                value={projectDescription}
                onChange={(event) => setProjectDescription(event.target.value)}
                placeholder="Clinical scope, hypothesis, evidence focus"
                rows={3}
                className="w-full px-3 py-2 text-xs rounded-lg border"
                style={{ borderColor: "var(--border)" }}
              />
              <button
                onClick={createProject}
                disabled={!projectName.trim()}
                className="w-full px-3 py-2 rounded-lg text-xs font-semibold text-white inline-flex items-center justify-center gap-2 disabled:opacity-50"
                style={{ background: "var(--accent)" }}
              >
                <Plus size={12} /> Create Intake Project
              </button>
            </div>
          </div>

          <div className="p-4 border-b" style={{ borderColor: "var(--border)" }}>
            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Pipeline Progress</div>
            <div className="space-y-1.5">
              {CLINICAL_STEPS.map((step) => {
                const Icon = step.icon;
                const execution = stageExecutions[step.id];
                return (
                  <button
                    key={step.id}
                    onClick={() => setActiveStepId(step.id)}
                    className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-left ${activeStepId === step.id ? "bg-white shadow-sm" : "hover:bg-[var(--bg-surface)]"}`}
                  >
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white" style={{ background: step.color }}>
                      <Icon size={13} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-[var(--text-primary)] truncate">{step.id}. {step.label}</div>
                      <div className="text-[10px] text-[var(--text-muted)] truncate">{step.requirements}</div>
                    </div>
                    {execution?.status === "success" && <CheckCircle2 size={13} className="text-emerald-500" />}
                    {execution?.status === "running" && <Loader2 size={13} className="text-blue-500 animate-spin" />}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase mb-2">Projects</div>
            <div className="space-y-2">
              {projects.map((project) => (
                <button
                  key={project.id}
                  onClick={() => setSelectedProjectId(project.id)}
                  className={`w-full text-left rounded-xl border p-3 ${selectedProjectId === project.id ? "bg-white shadow-sm" : "bg-transparent"}`}
                  style={{ borderColor: selectedProjectId === project.id ? "var(--accent)" : "var(--border)" }}
                >
                  <div className="text-xs font-semibold text-[var(--text-primary)]">{project.name}</div>
                  <div className="text-[11px] text-[var(--text-muted)] mt-1">{project.description}</div>
                  <div className="text-[10px] text-[var(--text-muted)] mt-2">Artifacts: {project.artifacts?.length || 0}</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="px-6 py-5 border-b" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-start justify-between gap-6 flex-wrap">
              <div>
                <h1 className="text-xl font-semibold text-[var(--text-primary)]">10-Step Clinical Design Pipeline</h1>
                <p className="text-sm text-[var(--text-muted)] mt-1">
                  Intake, evidence ingestion, phenotype review, tissue mapping, biomarkers, genomics, disruption, drug matching, therapy stratification, and export.
                </p>
              </div>
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={() => downloadJson("clinical_design_bundle.json", { ...reviewBundle, exportedAt: new Date().toISOString() })}
                  className="px-4 py-2 rounded-lg text-xs font-semibold border"
                  style={{ borderColor: "var(--border)" }}
                >
                  <Download size={12} className="inline mr-1" /> Export JSON Bundle
                </button>
                <button
                  onClick={async () => {
                    try {
                      await exportMarkdownBundle();
                    } catch (nextError) {
                      setError(nextError instanceof Error ? nextError.message : "Failed to export markdown bundle");
                    }
                  }}
                  disabled={!selectedProject}
                  className="px-4 py-2 rounded-lg text-xs font-semibold border disabled:opacity-50"
                  style={{ borderColor: "var(--border)" }}
                >
                  <FileText size={12} className="inline mr-1" /> Export Markdown Bundle
                </button>
                <button
                  onClick={sendGenesToPathways}
                  disabled={handoffGenes.length === 0}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50"
                  style={{ background: "var(--accent)" }}
                >
                  <ArrowRight size={12} className="inline mr-1" /> Handoff Genes to Pathways
                </button>
              </div>
            </div>

            {selectedProject && (
              <div className="grid md:grid-cols-4 gap-3 mt-4">
                {[
                  { label: "Project", value: selectedProject.name },
                  { label: "Artifacts", value: String(selectedProject.artifacts?.length || 0) },
                  { label: "Bundle Steps", value: String(bundleSteps.length) },
                  { label: "Active Stage", value: activeStep.label },
                ].map((item) => (
                  <div key={item.label} className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">{item.label}</div>
                    <div className="text-sm font-semibold text-[var(--text-primary)] mt-1">{item.value}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="grid xl:grid-cols-[minmax(0,1.2fr),380px] gap-5 p-6">
            <div className="space-y-5">
              <div className="rounded-2xl border p-5" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
                  <div>
                    <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase">Step {activeStep.id}</div>
                    <h2 className="text-lg font-semibold text-[var(--text-primary)]">{activeStep.label}</h2>
                    <p className="text-sm text-[var(--text-muted)] mt-1">Input requirements: {activeStep.requirements}</p>
                  </div>
                  <StatusPill status={activeExecution?.status || "idle"} />
                </div>

                {activeStep.id === 1 && (
                  <div className="space-y-4">
                    <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)" }}>
                      <div className="text-sm font-semibold text-[var(--text-primary)] mb-2">Project intake</div>
                      <p className="text-xs text-[var(--text-muted)] leading-6">
                        Intake is anchored on the translational project registry so the clinical stages can reuse stable project IDs for evidence, tissue, biomarker, genomics, and export flows.
                      </p>
                    </div>
                    {selectedProject ? (
                      <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)" }}>
                        <div className="text-xs font-semibold text-[var(--text-primary)]">Active project</div>
                        <div className="text-sm font-semibold mt-1">{selectedProject.name}</div>
                        <div className="text-xs text-[var(--text-muted)] mt-1">{selectedProject.description}</div>
                        <button
                          onClick={() => setActiveStepId(2)}
                          className="mt-3 px-4 py-2 rounded-lg text-xs font-semibold text-white"
                          style={{ background: "var(--accent)" }}
                        >
                          Continue to Evidence Ingestion
                        </button>
                      </div>
                    ) : (
                      <div className="text-xs text-[var(--text-muted)]">Create or select a project in the left rail to unlock downstream stages.</div>
                    )}
                  </div>
                )}

                {activeStep.id === 2 && (
                  <div className="space-y-4">
                    <div className="grid md:grid-cols-2 gap-3">
                      <input value={inputs.patientId} onChange={(event) => setInputs((current) => ({ ...current, patientId: event.target.value }))} placeholder="Patient identifier" className="px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                      <select value={inputs.recordType} onChange={(event) => setInputs((current) => ({ ...current, recordType: event.target.value }))} className="px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }}>
                        <option value="clinical_note">Clinical note</option>
                        <option value="ehr">EHR</option>
                        <option value="family_history">Family history</option>
                      </select>
                    </div>
                    <textarea value={inputs.rawText} onChange={(event) => setInputs((current) => ({ ...current, rawText: event.target.value }))} placeholder="Paste unstructured clinical evidence or EHR text" rows={8} className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    <textarea value={inputs.picoText} onChange={(event) => setInputs((current) => ({ ...current, picoText: event.target.value }))} placeholder="Optional PICO extraction text" rows={5} className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    <button onClick={executeEvidenceStage} disabled={!selectedProject || !inputs.rawText.trim()} className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>Run Evidence Ingestion + PICO</button>
                  </div>
                )}

                {activeStep.id === 3 && (
                  <div className="space-y-4">
                    <textarea value={inputs.ehrRecordIds} onChange={(event) => setInputs((current) => ({ ...current, ehrRecordIds: event.target.value }))} placeholder="Comma-separated EHR record IDs from ingestion" rows={4} className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    <input value={inputs.minClusterSize} onChange={(event) => setInputs((current) => ({ ...current, minClusterSize: event.target.value }))} placeholder="Minimum cluster size" className="px-3 py-2 text-xs rounded-lg border w-full md:w-[240px]" style={{ borderColor: "var(--border)" }} />
                    <button onClick={executePhenotypeStage} disabled={!selectedProject || parseCsv(inputs.ehrRecordIds).length === 0} className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>Run Phenotype Review</button>
                  </div>
                )}

                {activeStep.id === 4 && (
                  <div className="space-y-4">
                    <input value={inputs.imageRef} onChange={(event) => setInputs((current) => ({ ...current, imageRef: event.target.value }))} placeholder="Histopathology image reference" className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    <select value={inputs.analysisType} onChange={(event) => setInputs((current) => ({ ...current, analysisType: event.target.value }))} className="px-3 py-2 text-xs rounded-lg border w-full md:w-[260px]" style={{ borderColor: "var(--border)" }}>
                      <option value="histopathology">Histopathology</option>
                      <option value="immunohistochemistry">Immunohistochemistry</option>
                    </select>
                    <button onClick={executeTissueStage} disabled={!selectedProject || !inputs.imageRef.trim()} className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>Run Tissue Mapping</button>
                  </div>
                )}

                {activeStep.id === 5 && (
                  <div className="space-y-4">
                    <div className="grid md:grid-cols-2 gap-3">
                      <input value={inputs.sampleId} onChange={(event) => setInputs((current) => ({ ...current, sampleId: event.target.value }))} placeholder="Sample ID" className="px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                      <input value={inputs.fcsFileRef} onChange={(event) => setInputs((current) => ({ ...current, fcsFileRef: event.target.value }))} placeholder="FCS file reference" className="px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    </div>
                    <button onClick={executeBiomarkerStage} disabled={!selectedProject || !inputs.sampleId.trim() || !inputs.fcsFileRef.trim()} className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>Run Biomarker Quantification</button>
                  </div>
                )}

                {activeStep.id === 6 && (
                  <div className="space-y-4">
                    <input value={inputs.vcfFileRef} onChange={(event) => setInputs((current) => ({ ...current, vcfFileRef: event.target.value }))} placeholder="VCF file reference" className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    <textarea value={inputs.variantsJson} onChange={(event) => setInputs((current) => ({ ...current, variantsJson: event.target.value }))} placeholder="Variants JSON array" rows={8} className="w-full px-3 py-2 text-xs rounded-lg border font-mono" style={{ borderColor: "var(--border)" }} />
                    <button onClick={executeGenomicsStage} disabled={!selectedProject || !inputs.vcfFileRef.trim()} className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>Run Genomics + Pathogenicity</button>
                  </div>
                )}

                {activeStep.id === 7 && (
                  <div className="space-y-4">
                    <textarea value={inputs.variantIds} onChange={(event) => setInputs((current) => ({ ...current, variantIds: event.target.value }))} placeholder="Comma-separated variant IDs for disruption modeling" rows={5} className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    <button onClick={executeDisruptionStage} disabled={!selectedProject || parseCsv(inputs.variantIds).length === 0} className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>Run Disruption Modeling</button>
                  </div>
                )}

                {activeStep.id === 8 && (
                  <div className="space-y-4">
                    <textarea value={inputs.disruptedPathways} onChange={(event) => setInputs((current) => ({ ...current, disruptedPathways: event.target.value }))} placeholder="Disrupted pathway IDs" rows={4} className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    <textarea value={inputs.geneSymbols} onChange={(event) => setInputs((current) => ({ ...current, geneSymbols: event.target.value }))} placeholder="Gene symbols driving the match" rows={4} className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    <textarea value={inputs.patientContextJson} onChange={(event) => setInputs((current) => ({ ...current, patientContextJson: event.target.value }))} placeholder="Patient context JSON" rows={7} className="w-full px-3 py-2 text-xs rounded-lg border font-mono" style={{ borderColor: "var(--border)" }} />
                    <div className="flex gap-2 flex-wrap">
                      <button onClick={executeDrugMatchStage} disabled={!selectedProject || parseCsv(inputs.geneSymbols).length === 0} className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>Run AI Drug Matching</button>
                      <button onClick={sendGenesToPathways} disabled={handoffGenes.length === 0} className="px-4 py-2 rounded-lg text-xs font-semibold border disabled:opacity-50" style={{ borderColor: "var(--border)" }}>Handoff to Pathways</button>
                    </div>
                  </div>
                )}

                {activeStep.id === 9 && (
                  <div className="space-y-4">
                    <textarea value={inputs.patientProfileJson} onChange={(event) => setInputs((current) => ({ ...current, patientProfileJson: event.target.value }))} placeholder="Patient profile JSON" rows={7} className="w-full px-3 py-2 text-xs rounded-lg border font-mono" style={{ borderColor: "var(--border)" }} />
                    <input value={inputs.therapyTypes} onChange={(event) => setInputs((current) => ({ ...current, therapyTypes: event.target.value }))} placeholder="Therapy types" className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    <input value={inputs.trialDisease} onChange={(event) => setInputs((current) => ({ ...current, trialDisease: event.target.value }))} placeholder="India trials disease keyword" className="w-full px-3 py-2 text-xs rounded-lg border" style={{ borderColor: "var(--border)" }} />
                    <button onClick={executeTherapyStage} disabled={!selectedProject} className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>Run Therapy Stratification + Trial Review</button>
                  </div>
                )}

                {activeStep.id === 10 && (
                  <div className="space-y-4">
                    <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)" }}>
                      <div className="text-sm font-semibold text-[var(--text-primary)]">Review bundle</div>
                      <div className="text-xs text-[var(--text-muted)] mt-1">{bundleSteps.length} stages currently saved for export and review.</div>
                      <div className="flex flex-wrap gap-2 mt-3">
                        {bundleSteps.map((stepId) => {
                          const step = CLINICAL_STEPS.find((candidate) => candidate.id === stepId);
                          return step ? (
                            <span key={stepId} className="px-2 py-1 rounded-full text-[10px] font-semibold" style={{ background: `${step.color}18`, color: step.color }}>
                              {step.label}
                            </span>
                          ) : null;
                        })}
                      </div>
                    </div>
                    <div className="grid md:grid-cols-2 gap-3">
                      <button onClick={() => downloadJson("clinical_design_bundle.json", { ...reviewBundle, exportedAt: new Date().toISOString() })} className="px-4 py-2 rounded-lg text-xs font-semibold border" style={{ borderColor: "var(--border)" }}>
                        <Download size={12} className="inline mr-1" /> Export JSON Bundle
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            await exportMarkdownBundle();
                          } catch (nextError) {
                            setError(nextError instanceof Error ? nextError.message : "Markdown export failed");
                          }
                        }}
                        disabled={!selectedProject}
                        className="px-4 py-2 rounded-lg text-xs font-semibold border disabled:opacity-50"
                        style={{ borderColor: "var(--border)" }}
                      >
                        <FileText size={12} className="inline mr-1" /> Export Markdown Evidence Bundle
                      </button>
                      <button onClick={sendGenesToPathways} disabled={handoffGenes.length === 0} className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
                        <ArrowRight size={12} className="inline mr-1" /> Send Clinical Genes to Pathways
                      </button>
                      <button onClick={() => navigate("/syntharena")} className="px-4 py-2 rounded-lg text-xs font-semibold border" style={{ borderColor: "var(--border)" }}>
                        <ExternalLink size={12} className="inline mr-1" /> Open SynthArena Review
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <StageResultPanel
                step={activeStep}
                execution={activeExecution}
                onBundle={() => setBundleSteps((current) => Array.from(new Set([...current, activeStep.id])).sort((left, right) => left - right))}
              />

              <div className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                <div className="text-sm font-semibold text-[var(--text-primary)] mb-2">Stage Coverage</div>
                <div className="space-y-2 text-xs text-[var(--text-muted)]">
                  <div>Clinical evidence ingestion, phenotype review, tissue mapping, biomarkers, genomics, disruption modeling, drug matching, therapy stratification, and India trial review are all wired to backend clinical routes.</div>
                  <div>Project intake and markdown export remain on the translational project registry so stage artifacts keep a stable project anchor.</div>
                  <div>Per-stage controls include input requirements, status, artifact preview, provenance, copy/export actions, and bundle save.</div>
                </div>
              </div>

              <div className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                <div className="text-sm font-semibold text-[var(--text-primary)] mb-2">Review Bundle Snapshot</div>
                <div className="text-[11px] text-[var(--text-muted)] mb-3">Current project plus all saved stage outputs.</div>
                <pre className="text-[10px] leading-5 whitespace-pre-wrap break-words text-[var(--text-secondary)] max-h-[360px] overflow-auto">
                  {JSON.stringify(reviewBundle, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </StateWrapper>
  );
}