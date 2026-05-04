/** JobCockpit.tsx — Results Inspector. */

import { useState, useEffect, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Loader2,
  Target,
  CheckCircle2,
  Image as ImageIcon,
  Download,
  Code,
  FileText,
  Network,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Brain,
  Search,
  Sparkles,
} from "lucide-react";
import DataGrid from "@/components/ui/DataGrid";
import MiniGraphPreview from "@/components/ui/MiniGraphPreview";
import { ensureApiBase } from "@/lib/api";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "@/lib/types";

export default function JobCockpit() {
  const { id } = useParams();
  const [activeTab, setActiveTab] = useState("overview");
  const [apiBase, setApiBase] = useState("/api");

  useEffect(() => {
    ensureApiBase().then(setApiBase);
  }, []);

  const { data: traceData, isLoading: isTraceLoading } = useQuery({
    queryKey: ["jobTrace", id, apiBase],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/jobs/${id}/trace`);
      if (!res.ok) throw new Error("Failed to fetch trace");
      return res.json();
    },
    enabled: apiBase !== "/api" || !(window as any).__TAURI__,
    refetchInterval: (query: any) =>
      query.state?.data?.trace?.status === "completed" ? false : 2000,
  });

  const { data: evidenceData } = useQuery({
    queryKey: ["jobEvidence", id, apiBase],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/evidence/jobs/${id}/evidence`);
      if (!res.ok) return { entities: [], edges: [] };
      return res.json();
    },
    enabled:
      activeTab === "evidence" && traceData?.trace?.status === "completed",
  });

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "evidence", label: "Evidence Table" },
    { id: "graph", label: "Graph Explorer" },
    { id: "ranking", label: "Ranking View" },
    { id: "analyze", label: "🧠 Analyze" },
    { id: "media", label: "Media Figures" },
    { id: "dossier", label: "Dossier" },
  ];

  const traceError = !traceData && !isTraceLoading;

  const viewState: ViewState =
    isTraceLoading && !traceData ? "loading" :
    traceError ? "error" :
    !traceData ? "empty" :
    "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="Job Cockpit"
      emptyTitle="No Trace Data"
      emptyDescription="No job trace found for this ID."
      errorInfo={traceError ? { code: 'TRACE_ERROR', message: 'Failed to load job trace data.' } : undefined}
    >
    <div className="flex-1 flex flex-col bg-app overflow-hidden">
      {/* Header */}
      <header className="h-16 px-6 border-b border-border glass-panel flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <Link
            to="/workspace"
            className="p-2 text-muted hover:bg-[var(--bg-surface)] hover:text-primary rounded-full transition-colors"
          >
            <ArrowLeft size={18} />
          </Link>
          <div>
            <h2 className="text-sm font-semibold text-primary">
              Job Cockpit: {id}
            </h2>
            <span className="text-xs text-muted flex items-center gap-1">
              {isTraceLoading || traceData?.trace?.status !== "completed" ? (
                <>
                  <Loader2 size={10} className="animate-spin text-accent" />{" "}
                  Running
                </>
              ) : (
                <>
                  <CheckCircle2 size={10} className="text-green-600" />{" "}
                  Completed
                </>
              )}
            </span>
          </div>
        </div>

        <div className="flex bg-[var(--bg-surface)] border border-border rounded-lg p-0.5">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-1.5 text-xs font-medium rounded-md transition-all ${activeTab === t.id ? "bg-white text-accent shadow-sm" : "text-muted hover:text-primary"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </header>

      {/* Content Area */}
      <main className="flex-1 overflow-y-auto p-6">
        {isTraceLoading && !traceData ? (
          <div className="flex items-center justify-center py-20 text-muted">
            <Loader2 size={24} className="animate-spin" />
          </div>
        ) : (
          <>
            {activeTab === "overview" && (
              <OverviewTab trace={traceData?.trace} />
            )}
            {activeTab === "evidence" && (
              <EvidenceTab evidence={evidenceData} />
            )}
            {activeTab === "graph" && (
              <GraphTab jobId={id!} apiBase={apiBase} />
            )}
            {activeTab === "ranking" && <RankingTab trace={traceData?.trace} />}
            {activeTab === "analyze" && (
              <AnalyzeTab apiBase={apiBase} />
            )}
            {activeTab === "media" && (
              <MediaTab jobId={id!} apiBase={apiBase} />
            )}
            {activeTab === "dossier" && (
              <DossierTab jobId={id!} apiBase={apiBase} />
            )}
          </>
        )}
      </main>
    </div>
    </StateWrapper>
  );
}

function OverviewTab({ trace }: { trace: any }) {
  if (!trace) return null;
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-surface border border-border p-5 rounded-xl">
        <h3 className="text-sm font-semibold text-primary mb-4 flex items-center gap-2">
          <Target size={16} className="text-accent" /> Synthesis Trace
        </h3>
        <div className="space-y-4">
          {trace.steps?.map((step: any, i: number) => (
            <div key={i} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div
                  className={`w-3 h-3 rounded-full mt-1 ${step.status === "warning" ? "bg-amber-400" : "bg-accent"}`}
                />
                {i < trace.steps.length - 1 && (
                  <div className="w-px h-full bg-border mt-1" />
                )}
              </div>
              <div className="flex-1 pb-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-primary">
                    {step.name}
                  </h4>
                  <span className="text-xs text-muted font-mono">
                    {step.duration_ms}ms
                  </span>
                </div>
                <p className="text-xs text-secondary mt-1">
                  {step.details?.outputs_summary}
                </p>
                {step.details?.evidence_refs?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {step.details.evidence_refs.map((ref: string) => (
                      <span
                        key={ref}
                        className="px-1.5 py-0.5 bg-[var(--bg-inset)] text-[10px] text-[var(--text-muted)] rounded font-mono"
                      >
                        {ref}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function EvidenceTab({ evidence }: { evidence: any }) {
  if (!evidence?.edges?.length)
    return (
      <div className="text-center py-12 text-sm text-muted">
        Awaiting structured evidence extraction...
      </div>
    );

  const rows = evidence.edges.map((e: any) => ({
    id: e.edge_id,
    source: e.src_entity,
    target: e.dst_entity,
    relation: e.relation_type,
    method: e.method,
    origin: e.source,
    locator: e.source_locator,
    score: e.score?.toFixed(2),
  }));

  return (
    <div className="card rounded-xl overflow-hidden h-full flex flex-col">
      <h3 className="px-4 py-3 border-b border-border text-xs font-semibold uppercase tracking-wider text-muted bg-[var(--bg-surface)]">
        Provenanced Edge Cache
      </h3>
      <div className="flex-1">
        <DataGrid
          columns={[
            { key: "source", label: "Source" },
            { key: "relation", label: "Relation" },
            { key: "target", label: "Target" },
            { key: "origin", label: "Origin DB" },
            { key: "locator", label: "Locator Hash" },
            { key: "score", label: "Score" },
          ]}
          rows={rows}
        />
      </div>
    </div>
  );
}

const LABEL_COLORS: Record<string, string> = {
  Protein: "#6366f1",
  Drug: "#f59e0b",
  Disease: "#ef4444",
  Pathway: "#10b981",
  Gene: "#8b5cf6",
  Publication: "#3b82f6",
  Compound: "#ec4899",
  Target: "#14b8a6",
  Query: "#94a3b8",
  ClinicalStudy: "#a855f7",
  Document: "#f97316",
};

function GraphTab({ jobId, apiBase }: { jobId: string; apiBase: string }) {
  const [zoom, setZoom] = useState(1);

  const { data: evidenceData, isLoading } = useQuery({
    queryKey: ["jobEvidenceGraph", jobId, apiBase],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/evidence/jobs/${jobId}/evidence`);
      if (!res.ok) return { entities: [], edges: [] };
      return res.json();
    },
  });

  const SVG_SIZE = 600;
  const CENTER = SVG_SIZE / 2;

  const { nodes, edges } = useMemo(() => {
    if (!evidenceData?.edges?.length) return { nodes: [], edges: [] };
    const nodeSet = new Map<string, { id: string; label: string }>();
    for (const edge of evidenceData.edges) {
      if (edge.src_entity && !nodeSet.has(edge.src_entity)) {
        nodeSet.set(edge.src_entity, {
          id: edge.src_entity,
          label: edge.method || "Entity",
        });
      }
      if (edge.dst_entity && !nodeSet.has(edge.dst_entity)) {
        nodeSet.set(edge.dst_entity, { id: edge.dst_entity, label: "Query" });
      }
    }
    const nodeArr = Array.from(nodeSet.values());
    const count = nodeArr.length;
    const radius = Math.min(CENTER - 50, count * 3);
    const layoutNodes = nodeArr.map((n, i) => {
      const angle = (2 * Math.PI * i) / count - Math.PI / 2;
      return {
        ...n,
        x: CENTER + radius * Math.cos(angle),
        y: CENTER + radius * Math.sin(angle),
        color: LABEL_COLORS[n.label] || "#94a3b8",
      };
    });
    const posMap = new Map(layoutNodes.map((n) => [n.id, { x: n.x, y: n.y }]));
    const layoutEdges = evidenceData.edges
      .map((e: any) => ({
        src: posMap.get(e.src_entity),
        tgt: posMap.get(e.dst_entity),
      }))
      .filter((e: any) => e.src && e.tgt);
    return { nodes: layoutNodes, edges: layoutEdges };
  }, [evidenceData, CENTER]);

  if (isLoading)
    return (
      <div className="h-full flex items-center justify-center text-muted">
        <Loader2 size={24} className="animate-spin" />
      </div>
    );

  if (!nodes.length) {
    return (
      <div className="h-full card rounded-xl flex flex-col items-center justify-center text-sm text-muted">
        <Network size={24} className="text-slate-400 mb-2" />
        No evidence graph for this job yet.
      </div>
    );
  }

  return (
    <div className="h-full card rounded-xl flex flex-col overflow-hidden relative">
      <div className="px-4 py-2 border-b border-border flex items-center justify-between bg-[var(--bg-surface)]">
        <span className="text-xs font-semibold text-muted uppercase tracking-wider">
          Evidence Graph
        </span>
        <span className="text-[10px] text-muted">
          {nodes.length} nodes, {edges.length} edges
        </span>
      </div>
      <div className="flex-1 flex items-center justify-center overflow-auto">
        <svg
          width={SVG_SIZE}
          height={SVG_SIZE}
          viewBox={`0 0 ${SVG_SIZE} ${SVG_SIZE}`}
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "center",
            transition: "transform 0.2s",
          }}
        >
          {edges.map((e: any, i: number) => (
            <line
              key={`e${i}`}
              x1={e.src.x}
              y1={e.src.y}
              x2={e.tgt.x}
              y2={e.tgt.y}
              stroke="#cbd5e1"
              strokeWidth={0.5}
              strokeOpacity={0.6}
            />
          ))}
          {nodes.map((n) => (
            <g key={n.id}>
              <circle
                cx={n.x}
                cy={n.y}
                r={6}
                fill={n.color}
                fillOpacity={0.85}
                stroke="white"
                strokeWidth={1}
              />
              {nodes.length <= 40 && (
                <text
                  x={n.x}
                  y={n.y + 16}
                  textAnchor="middle"
                  fontSize={7}
                  fill="#94a3b8"
                >
                  {n.id.length > 14 ? n.id.slice(0, 14) + "..." : n.id}
                </text>
              )}
            </g>
          ))}
        </svg>
      </div>
      <div className="absolute bottom-3 right-3 flex gap-1">
        <button
          onClick={() => setZoom((z) => Math.min(z + 0.2, 3))}
          className="p-1.5 rounded-lg card shadow-sm hover:bg-[var(--bg-surface)]"
        >
          <ZoomIn size={13} />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(z - 0.2, 0.3))}
          className="p-1.5 rounded-lg card shadow-sm hover:bg-[var(--bg-surface)]"
        >
          <ZoomOut size={13} />
        </button>
        <button
          onClick={() => setZoom(1)}
          className="p-1.5 rounded-lg card shadow-sm hover:bg-[var(--bg-surface)]"
        >
          <Maximize2 size={13} />
        </button>
      </div>
    </div>
  );
}

function RankingTab({ trace }: { trace: any }) {
  return (
    <div className="card p-6 rounded-xl max-w-3xl mx-auto">
      <h3 className="text-lg font-semibold text-primary mb-4">
        Therapeutic Priority Decompositions
      </h3>
      <p className="text-sm text-secondary mb-6">
        Generated from final synthesis weights.
      </p>
      <div className="space-y-3">
        {trace?.result?.top_targets?.map((target: string, i: number) => (
          <div
            key={target}
            className="flex items-center justify-between p-3 border border-border rounded-lg bg-surface"
          >
            <span className="text-sm font-medium text-primary flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-accent text-white flex items-center justify-center text-xs">
                {i + 1}
              </span>
              {target}
            </span>
            <div className="flex gap-2 text-xs">
              {(() => {
                const conf = trace?.result?.overall_confidence;
                const efficacyLabel =
                  conf >= 0.7
                    ? "High"
                    : conf >= 0.4
                      ? "Medium"
                      : conf != null
                        ? "Low"
                        : "N/A";
                const efficacyCls =
                  conf >= 0.7
                    ? "bg-green-50 text-green-700 border-green-100"
                    : conf >= 0.4
                      ? "bg-amber-50 text-amber-700 border-amber-100"
                      : conf != null
                        ? "bg-red-50 text-red-700 border-red-100"
                        : "bg-[var(--bg-surface)] text-[var(--text-muted)] border-slate-100";
                const contras = trace?.result?.contradictions?.length ?? null;
                const safetyLabel =
                  contras === 0 ? "Clear" : contras > 0 ? "Review" : "N/A";
                const safetyCls =
                  contras === 0
                    ? "bg-green-50 text-green-700 border-green-100"
                    : contras > 0
                      ? "bg-amber-50 text-amber-700 border-amber-100"
                      : "bg-[var(--bg-surface)] text-[var(--text-muted)] border-slate-100";
                return (
                  <>
                    <span className={`px-2 py-1 rounded border ${efficacyCls}`}>
                      Efficacy: {efficacyLabel}
                    </span>
                    <span className={`px-2 py-1 rounded border ${safetyCls}`}>
                      Safety: {safetyLabel}
                    </span>
                  </>
                );
              })()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MediaTab({ jobId, apiBase }: { jobId: string; apiBase: string }) {
  const { data: artifacts, isLoading } = useQuery({
    queryKey: ["jobMedia", jobId, apiBase],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/jobs/${jobId}/media`);
      if (!res.ok) throw new Error("Failed to fetch media");
      return res.json();
    },
  });

  if (isLoading)
    return (
      <div className="flex items-center justify-center py-20 text-muted">
        <Loader2 size={24} className="animate-spin" />
      </div>
    );
  if (!artifacts?.length)
    return (
      <div className="text-center py-12 text-sm text-muted">
        No publication-ready figures exist for this job yet.
      </div>
    );

  const download = (id: string, format: string) => {
    window.open(`${apiBase}/media/${id}/download?format=${format}`, "_blank");
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h3 className="text-lg font-semibold text-primary mb-2">
        Publication-Ready Artifacts
      </h3>
      <p className="text-sm text-secondary mb-6">
        Generated figures for scientific export. SVGs are recommended for
        vector-perfect scaling in print.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {artifacts.map((art: any) => (
          <div
            key={art.artifact_id}
            className="card rounded-xl overflow-hidden flex flex-col hover:shadow-md transition-shadow"
          >
            <div className="bg-[var(--bg-surface)] border-b border-border aspect-video flex items-center justify-center p-4 relative group">
              <img
                src={`${apiBase}/media/${art.artifact_id}/download?format=png`}
                alt={art.title}
                className="max-w-full max-h-full object-contain"
              />
            </div>
            <div className="p-4 flex-1 flex flex-col">
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2 py-0.5 bg-accent/10 text-accent text-[10px] font-bold rounded uppercase tracking-wider">
                  {art.type}
                </span>
                <span className="text-xs text-muted font-mono">
                  {new Date(art.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              <h4 className="font-semibold text-primary text-sm mb-1">
                {art.title}
              </h4>
              <p className="text-xs text-secondary mb-4 flex-1 leading-relaxed">
                {art.description}
              </p>
              <div className="flex items-center gap-2 pt-3 border-t border-border mt-auto">
                <button
                  onClick={() => download(art.artifact_id, "svg")}
                  className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 bg-accent/5 hover:bg-accent hover:text-white text-accent rounded-md transition-colors text-xs font-medium"
                >
                  <ImageIcon size={14} /> SVG
                </button>
                <button
                  onClick={() => download(art.artifact_id, "png")}
                  className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 bg-[var(--bg-inset)] hover:bg-slate-200 text-slate-700 rounded-md transition-colors text-xs font-medium"
                >
                  <Download size={14} /> PNG
                </button>
                <button
                  onClick={() => download(art.artifact_id, "json")}
                  className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 bg-[var(--bg-inset)] hover:bg-slate-200 text-slate-700 rounded-md transition-colors text-xs font-medium"
                >
                  <Code size={14} /> JSON
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DossierTab({ jobId, apiBase }: { jobId: string; apiBase: string }) {
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);

  const { data: dossier, isLoading } = useQuery({
    queryKey: ["jobDossier", jobId, apiBase],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/jobs/${jobId}/dossier?format=json`);
      if (!res.ok) return null;
      return res.json();
    },
  });

  const fetchHtmlPreview = async () => {
    const res = await fetch(`${apiBase}/jobs/${jobId}/dossier?format=html`);
    if (res.ok) setPreviewHtml(await res.text());
  };

  const downloadJson = () => {
    if (!dossier) return;
    const blob = new Blob([JSON.stringify(dossier, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dossier_${jobId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadHtml = async () => {
    const res = await fetch(`${apiBase}/jobs/${jobId}/dossier?format=html`);
    if (!res.ok) return;
    const html = await res.text();
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dossier_${jobId}.html`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const printPdf = async () => {
    const res = await fetch(`${apiBase}/jobs/${jobId}/dossier?format=pdf`);
    if (!res.ok) return;
    const html = await res.text();
    const w = window.open("", "_blank");
    if (w) {
      w.document.write(html);
      w.document.close();
      setTimeout(() => w.print(), 500);
    }
  };

  if (isLoading)
    return (
      <div className="flex items-center justify-center py-20 text-muted">
        <Loader2 size={24} className="animate-spin" />
      </div>
    );
  if (!dossier)
    return (
      <div className="text-center py-12 text-sm text-muted">
        No dossier available for this job.
      </div>
    );

  const sections: { label: string; key: string }[] = [
    { label: "Question", key: "question" },
    { label: "Constraints", key: "constraints" },
    { label: "Evidence", key: "evidence" },
    { label: "Rankings", key: "ranking_table" },
    { label: "Contradictions", key: "contradictions" },
    { label: "Assumptions", key: "assumptions_and_overrides" },
    { label: "Next Experiments", key: "recommended_next_experiments" },
    { label: "Run Recipe", key: "run_recipe" },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Export bar */}
      <div className="card rounded-xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileText size={20} className="text-accent" />
          <div>
            <h3 className="text-sm font-semibold text-primary">
              Decision Dossier
            </h3>
            <p className="text-xs text-muted">
              Complete reproducibility report with citations
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={downloadJson}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-inset)] hover:bg-slate-200 text-slate-700 rounded-md text-xs font-medium transition-colors"
          >
            <Download size={14} /> JSON
          </button>
          <button
            onClick={downloadHtml}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg-inset)] hover:bg-slate-200 text-slate-700 rounded-md text-xs font-medium transition-colors"
          >
            <Download size={14} /> HTML
          </button>
          <button
            onClick={printPdf}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-accent/10 hover:bg-accent hover:text-white text-accent rounded-md text-xs font-medium transition-colors"
          >
            <FileText size={14} /> PDF
          </button>
          {!previewHtml && (
            <button
              onClick={fetchHtmlPreview}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-border hover:bg-[var(--bg-surface)] text-primary rounded-md text-xs font-medium transition-colors"
            >
              Preview
            </button>
          )}
        </div>
      </div>

      {/* Inline HTML preview */}
      {previewHtml && (
        <div className="card rounded-xl overflow-hidden">
          <div className="flex justify-between items-center px-4 py-2 bg-[var(--bg-surface)] border-b border-border">
            <span className="text-xs font-medium text-muted uppercase tracking-wider">
              HTML Preview
            </span>
            <button
              onClick={() => setPreviewHtml(null)}
              className="text-xs text-muted hover:text-primary"
            >
              &times; Close
            </button>
          </div>
          <iframe
            srcDoc={previewHtml}
            className="w-full border-0"
            style={{ minHeight: 600 }}
            title="Dossier Preview"
            sandbox="allow-same-origin"
          />
        </div>
      )}

      {/* Section summaries */}
      {sections.map(({ label, key }) => {
        const val = dossier[key];
        if (!val) return null;

        return (
          <div key={key} className="card rounded-xl p-5">
            <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">
              {label}
            </h4>
            {typeof val === "string" ? (
              <p className="text-sm text-primary font-medium">{val}</p>
            ) : Array.isArray(val) ? (
              val.length === 0 ? (
                <p className="text-sm text-muted">None.</p>
              ) : typeof val[0] === "string" ? (
                <ul className="text-sm text-secondary space-y-1.5 list-disc list-inside">
                  {val.map((v: string, i: number) => (
                    <li key={i}>{v}</li>
                  ))}
                </ul>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b border-border text-muted uppercase tracking-wider">
                        {Object.keys(val[0]).map((k) => (
                          <th key={k} className="py-2 px-2 font-medium">
                            {k}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {val.map((row: Record<string, unknown>, i: number) => (
                        <tr
                          key={i}
                          className="border-b border-border/50 hover:bg-[var(--bg-surface)]"
                        >
                          {Object.values(row).map((v, j) => (
                            <td key={j} className="py-2 px-2 text-primary">
                              {typeof v === "object"
                                ? JSON.stringify(v)
                                : String(v)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            ) : typeof val === "object" ? (
              <pre className="text-xs bg-[var(--bg-surface)] border border-border rounded-lg p-3 overflow-x-auto text-primary">
                {JSON.stringify(val, null, 2)}
              </pre>
            ) : (
              <p className="text-sm text-primary">{String(val)}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Agentic Analysis Tab ─── */
const CATEGORY_COLORS: Record<string, { bg: string; text: string; icon: string }> = {
  proteins: { bg: "bg-indigo-50", text: "text-indigo-700", icon: "🧬" },
  genes: { bg: "bg-violet-50", text: "text-violet-700", icon: "🔬" },
  drugs: { bg: "bg-amber-50", text: "text-amber-700", icon: "💊" },
  diseases: { bg: "bg-red-50", text: "text-red-700", icon: "🦠" },
  publications: { bg: "bg-blue-50", text: "text-blue-700", icon: "📄" },
  trials: { bg: "bg-emerald-50", text: "text-emerald-700", icon: "🏥" },
  pathways: { bg: "bg-teal-50", text: "text-teal-700", icon: "🔗" },
};

function AnalyzeTab({ apiBase }: { apiBase: string }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runAnalysis = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const base = apiBase.endsWith("/api") ? apiBase.replace(/\/api$/, "/api/v1") : apiBase;
      const res = await fetch(`${base}/cockpit/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), limit: 30 }),
      });
      if (!res.ok) throw new Error(`Analysis failed (${res.status})`);
      const json = await res.json();
      setResult(json.data ?? json);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Search bar */}
      <div className="card rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
            <Brain size={20} className="text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-primary">Agentic Analysis</h3>
            <p className="text-xs text-muted">Multi-source AI-powered drug discovery intelligence</p>
          </div>
        </div>
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runAnalysis()}
              placeholder="e.g. BRCA1 breast cancer resistance mechanisms..."
              className="w-full pl-10 pr-4 py-2.5 border border-border rounded-lg text-sm focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none"
            />
          </div>
          <button
            onClick={runAnalysis}
            disabled={loading || !query.trim()}
            className="px-5 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2 transition-opacity"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            Analyze
          </button>
        </div>
        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      </div>

      {/* Results */}
      {result && (
        <>
          {/* AI Summary */}
          {result.summary && (
            <div className="card rounded-xl p-5">
              <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3 flex items-center gap-2">
                <Sparkles size={14} className="text-accent" /> AI Synthesis
              </h4>
              <p className="text-sm text-primary leading-relaxed whitespace-pre-wrap">{result.summary}</p>
              {result.latency_ms && (
                <span className="mt-3 inline-block text-[10px] text-muted font-mono">⏱ {result.latency_ms}ms</span>
              )}
            </div>
          )}

          {/* Stats strip */}
          {result.stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(result.stats).map(([k, v]) => (
                <div key={k} className="card rounded-xl p-4 text-center">
                  <div className="text-xl font-bold text-accent">{String(v)}</div>
                  <div className="text-[10px] text-muted uppercase tracking-wider mt-1">{k.replace(/_/g, " ")}</div>
                </div>
              ))}
            </div>
          )}

          {/* Source breakdown */}
          {result.source_breakdown && Object.keys(result.source_breakdown).length > 0 && (
            <div className="card rounded-xl p-5">
              <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Source Breakdown</h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(result.source_breakdown).map(([src, ct]) => (
                  <span key={src} className="px-3 py-1.5 bg-[var(--bg-inset)] rounded-full text-xs font-medium text-primary">
                    {src} <span className="text-accent font-bold ml-1">{String(ct)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Categorized entities */}
          {result.categories && Object.keys(result.categories).length > 0 && (
            <div className="space-y-4">
              {Object.entries(result.categories).map(([cat, items]) => {
                const arr = items as any[];
                if (!arr?.length) return null;
                const style = CATEGORY_COLORS[cat] || { bg: "bg-[var(--bg-surface)]", text: "text-slate-700", icon: "📌" };
                return (
                  <div key={cat} className="card rounded-xl overflow-hidden">
                    <div className={`px-4 py-2.5 ${style.bg} border-b border-border flex items-center justify-between`}>
                      <span className={`text-xs font-semibold uppercase tracking-wider ${style.text}`}>
                        {style.icon} {cat} ({arr.length})
                      </span>
                    </div>
                    <div className="p-3">
                      <div className="flex flex-wrap gap-2">
                        {arr.slice(0, 20).map((item: any, i: number) => (
                          <span key={i} className={`px-2.5 py-1 rounded-lg text-xs font-medium ${style.bg} ${style.text}`}>
                            {typeof item === "string" ? item : item.name || item.id || JSON.stringify(item)}
                          </span>
                        ))}
                        {arr.length > 20 && (
                          <span className="px-2.5 py-1 rounded-lg text-xs text-muted">+{arr.length - 20} more</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Mini graph preview */}
          {result.graph && (result.graph.nodes?.length > 0 || result.graph.edges?.length > 0) && (
            <div className="card rounded-xl p-5">
              <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Entity Graph Preview</h4>
              <div className="h-[300px]">
                <MiniGraphPreview nodes={result.graph.nodes} edges={result.graph.edges} />
              </div>
            </div>
          )}
        </>
      )}

      {/* Empty state */}
      {!result && !loading && (
        <div className="text-center py-16">
          <Brain size={40} className="mx-auto text-slate-400 mb-4" />
          <h4 className="text-sm font-medium text-muted">Enter a query to start autonomous analysis</h4>
          <p className="text-xs text-muted mt-1">Searches 30+ biomedical sources → AI synthesis → knowledge graph</p>
        </div>
      )}
    </div>
  );
}
