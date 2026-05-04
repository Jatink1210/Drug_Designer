/** EntityDetailDrawer — Slide-out drawer showing AI overview, publications,
 *  patents, clinical trials, related entities, and action buttons when an
 *  entity is clicked from any categorized table.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  X,
  ExternalLink,
  BookOpen,
  FileText,
  FlaskConical,
  Box,
  Network,
  Loader2,
  Sparkles,
  ArrowRight,
  Activity,
  Dna,
  Pill,
  Target,
  GitBranch,
} from "lucide-react";
import { cockpitEntityDetailAPI } from "@/lib/api";
import { getEntityColor } from "@/lib/entityColors";
import { persistCockpitHandoff, type SharedHandoffPayload } from "@/lib/canonicalProduct";

interface EntityDetailDrawerProps {
  entityId: string;
  entityType: string;
  entityName: string;
  identifiers?: Record<string, string>;
  onClose: () => void;
}

const TYPE_ICONS: Record<string, typeof Dna> = {
  protein: Dna,
  gene: Dna,
  disease: Activity,
  drug: Pill,
  compound: FlaskConical,
  pathway: GitBranch,
  publication: BookOpen,
  clinical_trial: FileText,
  variant: Dna,
  molecule: FlaskConical,
  target: Target,
};

export default function EntityDetailDrawer({
  entityId,
  entityType,
  entityName,
  identifiers,
  onClose,
}: EntityDetailDrawerProps) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"overview" | "publications" | "trials" | "related">("overview");

  const detailQ = useQuery({
    queryKey: ["entityDetail", entityId],
    queryFn: () => cockpitEntityDetailAPI(entityId),
    retry: 1,
  });

  const detail = detailQ.data as Record<string, unknown> | undefined;
  const color = getEntityColor(entityType);
  const Icon = TYPE_ICONS[entityType.toLowerCase()] || Target;

  const aiOverview = typeof detail?.ai_overview === "string" ? detail.ai_overview : "";
  const publications = Array.isArray(detail?.publications) ? (detail.publications as Array<Record<string, unknown>>) : [];
  const patents = Array.isArray(detail?.patents) ? (detail.patents as Array<Record<string, unknown>>) : [];
  const clinicalTrials = Array.isArray(detail?.clinical_trials) ? (detail.clinical_trials as Array<Record<string, unknown>>) : [];
  const relatedEntities = Array.isArray(detail?.related_entities) ? (detail.related_entities as Array<Record<string, unknown>>) : [];
  const actionButtons = Array.isArray(detail?.action_buttons) ? (detail.action_buttons as Array<Record<string, unknown>>) : [];

  const buildHandoff = (route: string, action: SharedHandoffPayload["action"]): SharedHandoffPayload => ({
    version: "phase0.v1",
    sourceModule: "cockpit",
    action,
    targetRoute: route,
    query: entityName,
    createdAt: new Date().toISOString(),
    entities: [{
      entityId,
      entityType: entityType as SharedHandoffPayload["entities"][number]["entityType"],
      entityName,
      sourceCategory: "entity-detail",
      identifiers: identifiers || {},
      attributes: {},
    }],
    provenance: [{ source: "entity-detail", retrievedAt: new Date().toISOString() }],
    metadata: {},
  });

  const navigateTo = (route: string, action: SharedHandoffPayload["action"]) => {
    persistCockpitHandoff(buildHandoff(route, action));
    navigate(route);
    onClose();
  };

  const tabs = [
    { key: "overview" as const, label: "Overview" },
    { key: "publications" as const, label: `Publications (${publications.length})` },
    { key: "trials" as const, label: `Trials (${clinicalTrials.length})` },
    { key: "related" as const, label: `Related (${relatedEntities.length})` },
  ];

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" />

      {/* Drawer */}
      <div
        className="relative w-full max-w-[480px] h-full overflow-y-auto shadow-2xl"
        style={{ background: "var(--bg-app)", borderLeft: `3px solid ${color}` }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 px-5 py-4 border-b" style={{ borderColor: "var(--border)", background: "var(--bg-app)" }}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <span
                className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                style={{ background: `${color}15`, color }}
              >
                <Icon size={18} />
              </span>
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-[var(--text-primary)] truncate">{entityName}</h2>
                <div className="flex items-center gap-2 mt-0.5">
                  <span
                    className="px-2 py-0.5 rounded-full text-[10px] font-semibold capitalize"
                    style={{ background: `${color}15`, color }}
                  >
                    {entityType}
                  </span>
                  <span className="text-[10px] text-[var(--text-muted)] font-mono">{entityId}</span>
                </div>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-[var(--bg-surface)]"
            >
              <X size={16} className="text-[var(--text-muted)]" />
            </button>
          </div>

          {/* Cross-references */}
          {identifiers && Object.keys(identifiers).length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {Object.entries(identifiers).slice(0, 6).map(([db, id]) => (
                <span
                  key={db}
                  className="px-2 py-0.5 rounded-lg text-[10px] font-mono"
                  style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
                >
                  {db}: {id}
                </span>
              ))}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <button
              onClick={() => navigateTo("/structure", "open_in_structure")}
              className="px-3 py-1.5 rounded-lg border text-[11px] font-medium inline-flex items-center gap-1.5"
              style={{ borderColor: "var(--border)" }}
            >
              <Box size={12} /> View Structure
            </button>
            <button
              onClick={() => navigateTo("/design", "open_in_design")}
              className="px-3 py-1.5 rounded-lg border text-[11px] font-medium inline-flex items-center gap-1.5"
              style={{ borderColor: "var(--border)" }}
            >
              <FlaskConical size={12} /> Design Studio
            </button>
            <button
              onClick={() => navigateTo("/graph", "open_in_graph")}
              className="px-3 py-1.5 rounded-lg border text-[11px] font-medium inline-flex items-center gap-1.5"
              style={{ borderColor: "var(--border)" }}
            >
              <Network size={12} /> Knowledge Graph
            </button>
            <button
              onClick={() => navigateTo("/entity-intelligence", "run_entity_intelligence")}
              className="px-3 py-1.5 rounded-lg border text-[11px] font-medium inline-flex items-center gap-1.5"
              style={{ borderColor: "var(--border)" }}
            >
              <Sparkles size={12} /> Entity Intel
            </button>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mt-3">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className="px-3 py-1.5 rounded-lg text-[11px] font-medium"
                style={{
                  background: activeTab === tab.key ? `${color}12` : "transparent",
                  color: activeTab === tab.key ? color : "var(--text-muted)",
                  border: `1px solid ${activeTab === tab.key ? `${color}30` : "transparent"}`,
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="px-5 py-4 space-y-4">
          {detailQ.isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={20} className="animate-spin text-[var(--text-muted)]" />
              <span className="ml-2 text-xs text-[var(--text-muted)]">Loading entity details…</span>
            </div>
          )}

          {detailQ.isError && (
            <div className="rounded-xl border px-4 py-3 text-xs text-[var(--text-muted)]" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
              Entity detail API unavailable. Showing basic information only.
            </div>
          )}

          {activeTab === "overview" && (
            <>
              {aiOverview ? (
                <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                  <div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)] mb-2">
                    <Sparkles size={13} style={{ color }} /> AI Overview
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">{aiOverview}</p>
                </div>
              ) : !detailQ.isLoading && (
                <div className="rounded-xl border p-4 text-xs text-[var(--text-muted)]" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
                  No AI overview available for this entity.
                </div>
              )}

              {/* Backend-provided action buttons */}
              {actionButtons.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-[var(--text-primary)]">Suggested Actions</div>
                  {actionButtons.map((btn, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        const route = typeof btn.route === "string" ? btn.route : "/";
                        const action = typeof btn.action === "string" ? btn.action as SharedHandoffPayload["action"] : "run_cockpit_search";
                        navigateTo(route, action);
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg border text-xs flex items-center justify-between"
                      style={{ borderColor: "var(--border)" }}
                    >
                      <span>{typeof btn.label === "string" ? btn.label : "Action"}</span>
                      <ArrowRight size={12} className="text-[var(--text-muted)]" />
                    </button>
                  ))}
                </div>
              )}

              {/* Patents */}
              {patents.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-[var(--text-primary)]">Patents ({patents.length})</div>
                  {patents.slice(0, 5).map((patent, i) => (
                    <div key={i} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                      <div className="text-xs font-medium text-[var(--text-primary)]">{String(patent.title || patent.patent_id || `Patent ${i + 1}`)}</div>
                      <div className="text-[10px] text-[var(--text-muted)] mt-1">{String(patent.assignee || "")} · {String(patent.date || "")}</div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {activeTab === "publications" && (
            <div className="space-y-2">
              {publications.length === 0 && !detailQ.isLoading && (
                <div className="text-xs text-[var(--text-muted)] py-4 text-center">No publications found.</div>
              )}
              {publications.map((pub, i) => (
                <div key={i} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                  <div className="text-xs font-medium text-[var(--text-primary)]">{String(pub.title || `Publication ${i + 1}`)}</div>
                  <div className="text-[10px] text-[var(--text-muted)] mt-1">
                    {String(pub.authors || "")} · {String(pub.journal || "")} · {String(pub.year || "")}
                  </div>
                  {typeof pub.doi === "string" && pub.doi && (
                    <a
                      href={`https://doi.org/${pub.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] inline-flex items-center gap-1 mt-1 hover:underline"
                      style={{ color }}
                    >
                      <ExternalLink size={10} /> {pub.doi}
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}

          {activeTab === "trials" && (
            <div className="space-y-2">
              {clinicalTrials.length === 0 && !detailQ.isLoading && (
                <div className="text-xs text-[var(--text-muted)] py-4 text-center">No clinical trials found.</div>
              )}
              {clinicalTrials.map((trial, i) => (
                <div key={i} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                  <div className="text-xs font-medium text-[var(--text-primary)]">{String(trial.title || trial.nct_id || `Trial ${i + 1}`)}</div>
                  <div className="text-[10px] text-[var(--text-muted)] mt-1">
                    {String(trial.phase || "")} · {String(trial.status || "")} · {String(trial.nct_id || "")}
                  </div>
                  {typeof trial.url === "string" && trial.url && (
                    <a
                      href={trial.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] inline-flex items-center gap-1 mt-1 hover:underline"
                      style={{ color }}
                    >
                      <ExternalLink size={10} /> View on ClinicalTrials.gov
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}

          {activeTab === "related" && (
            <div className="space-y-2">
              {relatedEntities.length === 0 && !detailQ.isLoading && (
                <div className="text-xs text-[var(--text-muted)] py-4 text-center">No related entities found.</div>
              )}
              {relatedEntities.map((rel, i) => {
                const relColor = getEntityColor(String(rel.entity_type || "unknown"));
                return (
                  <div key={i} className="rounded-lg border p-3 flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
                    <div>
                      <div className="text-xs font-medium text-[var(--text-primary)]">{String(rel.name || rel.entity_id || `Entity ${i + 1}`)}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <span
                          className="px-1.5 py-0.5 rounded-full text-[9px] font-semibold capitalize"
                          style={{ background: `${relColor}15`, color: relColor }}
                        >
                          {String(rel.entity_type || "unknown")}
                        </span>
                        <span className="text-[10px] text-[var(--text-muted)]">{String(rel.relationship || "")}</span>
                      </div>
                    </div>
                    <ArrowRight size={12} className="text-[var(--text-muted)]" />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
