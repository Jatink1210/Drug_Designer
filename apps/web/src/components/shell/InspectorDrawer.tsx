/** InspectorDrawer — 8-tab global entity detail panel. */

import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  X,
  ExternalLink,
  Copy,
  Send,
  Bookmark,
  Download,
  Shield,
  Loader2,
} from "lucide-react";
import ConfidenceBar from "@/components/ui/ConfidenceBar";
import EvidenceBadge from "@/components/ui/EvidenceBadge";
import EntityPill from "@/components/ui/EntityPill";
import CitationCard from "@/components/ui/CitationCard";
import ContradictionBanner from "@/components/ui/ContradictionBanner";
import { graphNeighborhoodAPI, pathwaysSearchAPI } from "@/lib/api";
import type { CitationRefDTO, ContradictionDTO } from "@/lib/api";

interface InspectorDrawerProps {
  entity: Record<string, unknown> | null;
  onClose: () => void;
}

const TABS = [
  "Overview",
  "IDs",
  "Evidence",
  "Relationships",
  "Structures",
  "Pathways",
  "Notes",
  "Export",
] as const;
type Tab = (typeof TABS)[number];

export default function InspectorDrawer({
  entity,
  onClose,
}: InspectorDrawerProps) {
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const drawerRef = useRef<HTMLDivElement>(null);

  // §65 WCAG AA: Focus trap — keep Tab cycling within the drawer when open
  useEffect(() => {
    if (!entity) return;
    const handleTrap = (e: KeyboardEvent) => {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key !== "Tab") return;
      const el = drawerRef.current;
      if (!el) return;
      const focusable = el.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleTrap);
    return () => window.removeEventListener("keydown", handleTrap);
  }, [entity, onClose]);

  if (!entity) return null;

  const name = String(
    entity.canonical_name || entity.name || entity.title || entity.id || "—",
  );
  const type = String(entity.entity_type || "unknown");

  return (
    <div ref={drawerRef} className="w-[380px] glass-panel border-l flex flex-col shrink-0 overflow-hidden" role="complementary" aria-label={`Inspector: ${name}`}>
      {/* Header */}
      <div
        className="px-4 py-3 border-b flex items-start gap-3"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="flex-1 min-w-0">
          <EntityPill type={type} name={name.slice(0, 40)} />
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mt-1.5 leading-tight">
            {name}
          </h3>
          <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
            {String(entity.id || "")}
          </p>
        </div>
        <div className="flex gap-1 shrink-0">
          <button
            onClick={() => {
              const id = String(entity.id || "unknown");
              const bookmarks: string[] = JSON.parse(
                localStorage.getItem("inspector-bookmarks") || "[]",
              );
              if (!bookmarks.includes(id)) {
                bookmarks.push(id);
                localStorage.setItem(
                  "inspector-bookmarks",
                  JSON.stringify(bookmarks),
                );
              }
            }}
            title="Bookmark this entity"
            className="p-1 rounded hover:bg-gray-100 text-[var(--text-muted)]"
          >
            <Bookmark size={14} />
          </button>
          <button
            disabled
            title="Send to workspace (v2)"
            className="p-1 rounded text-[var(--text-muted)] opacity-40 cursor-not-allowed"
          >
            <Send size={14} />
          </button>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 text-[var(--text-muted)]"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div
        className="flex overflow-x-auto border-b px-1 gap-0 hide-scrollbar"
        style={{ borderColor: "var(--border)" }}
      >
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-2.5 py-2 text-[11px] font-medium whitespace-nowrap border-b-2 transition-colors ${
              activeTab === t
                ? "border-[var(--accent)] text-[var(--accent)]"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeTab === "Overview" && <OverviewTab entity={entity} />}
        {activeTab === "IDs" && <IDsTab entity={entity} />}
        {activeTab === "Evidence" && <EvidenceTab entity={entity} />}
        {activeTab === "Relationships" && <RelationshipsTab entity={entity} />}
        {activeTab === "Structures" && <StructuresTab entity={entity} />}
        {activeTab === "Pathways" && <PathwaysTab entity={entity} />}
        {activeTab === "Notes" && (
          <NotesTab entityId={String(entity.id || "")} />
        )}
        {activeTab === "Export" && <ExportTab entity={entity} />}
      </div>
    </div>
  );
}

/* ─── Tab contents ────────────────────────────────────── */

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1.5">
        {title}
      </h4>
      {children}
    </div>
  );
}

function PropRow({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined || value === "") return null;
  const display = Array.isArray(value)
    ? (value as string[]).join(", ")
    : String(value);
  const isUrl = typeof value === "string" && value.startsWith("http");
  return (
    <div
      className="flex gap-2 py-1 border-b border-dashed"
      style={{ borderColor: "var(--border-light)" }}
    >
      <span className="text-[11px] text-[var(--text-muted)] w-28 shrink-0">
        {label}
      </span>
      {isUrl ? (
        <a
          href={value as string}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[11px] text-[var(--accent)] hover:underline flex items-center gap-1"
        >
          Link <ExternalLink size={9} />
        </a>
      ) : (
        <span className="text-[11px] text-[var(--text-primary)] break-all">
          {display}
        </span>
      )}
    </div>
  );
}

function OverviewTab({ entity }: { entity: Record<string, unknown> }) {
  const desc = String(
    entity.description ||
      entity.function_description ||
      "No description available.",
  );
  const provenance =
    (entity.provenance as Array<Record<string, unknown>>) || [];
  const fields = [
    "organism",
    "gene_symbol",
    "length",
    "method",
    "resolution",
    "phase",
    "status",
    "formula",
    "molecular_weight",
    "logp",
    "clinical_phase",
    "drug_type",
    "species",
  ];

  return (
    <>
      <Section title="Description">
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {desc}
        </p>
      </Section>
      <Section title="Key Properties">
        {fields.map((f) => (
          <PropRow key={f} label={f.replace(/_/g, " ")} value={entity[f]} />
        ))}
      </Section>
      {provenance.length > 0 && (
        <Section title="Provenance">
          {provenance.map((p, i) => (
            <div key={i} className="flex items-center gap-2 py-1">
              <span className="text-[10px] font-medium text-[var(--text-secondary)]">
                {String(p.source_name || p.source || "")}
              </span>
              {p.confidence_score != null && (
                <ConfidenceBar
                  value={Number(p.confidence_score)}
                  reasoning={String(
                    p.confidence_reasoning || p.reasoning || "",
                  )}
                />
              )}
            </div>
          ))}
        </Section>
      )}
    </>
  );
}

function IDsTab({ entity }: { entity: Record<string, unknown> }) {
  const idFields = [
    "id",
    "uniprot_id",
    "pdb_id",
    "nct_id",
    "pmid",
    "doi",
    "chembl_url",
    "pubchem_url",
    "url",
    "ensembl_id",
    "inchi_key",
    "smiles",
  ];
  const xrefs =
    (entity.xrefs as Array<{ source: string; id: string; url?: string }>) || [];
  return (
    <>
      <Section title="Canonical IDs">
        {idFields.map((f) => (
          <PropRow key={f} label={f.replace(/_/g, " ")} value={entity[f]} />
        ))}
      </Section>
      {xrefs.length > 0 && (
        <Section title="Cross-References">
          {xrefs.map((x, i) => (
            <div key={i} className="flex items-center gap-2 py-1">
              <span className="text-[10px] font-medium text-[var(--text-muted)]">
                {x.source}
              </span>
              <span className="text-[10px] text-[var(--text-secondary)]">
                {x.id}
              </span>
              {x.url && (
                <a href={x.url} target="_blank" rel="noopener noreferrer">
                  <ExternalLink size={9} className="text-[var(--accent)]" />
                </a>
              )}
            </div>
          ))}
        </Section>
      )}
    </>
  );
}

function EvidenceTab({ entity }: { entity: Record<string, unknown> }) {
  const pmid = entity.pmid as string | undefined;
  const nctId = entity.nct_id as string | undefined;
  const doi = entity.doi as string | undefined;
  const confidence = entity._confidence as number | undefined;
  const evidenceRefs = (entity._evidence_refs as CitationRefDTO[]) || [];
  const contradictions = (entity._contradictions as ContradictionDTO[]) || [];

  return (
    <>
      {/* Confidence score */}
      {confidence != null && (
        <Section title="Overall Confidence">
          <div className="flex items-center gap-3">
            <Shield size={14} className="text-[var(--text-muted)]" />
            <div className="flex-1">
              <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.round(confidence * 100)}%`,
                    backgroundColor:
                      confidence >= 0.7
                        ? "#16a34a"
                        : confidence >= 0.4
                          ? "#d97706"
                          : "#dc2626",
                  }}
                />
              </div>
            </div>
            <span className="text-xs font-medium text-[var(--text-primary)]">
              {Math.round(confidence * 100)}%
            </span>
          </div>
        </Section>
      )}

      {/* Quick badges */}
      <Section title="Evidence Records">
        <div className="flex flex-wrap gap-1.5 mb-2">
          {pmid && (
            <EvidenceBadge
              type="pmid"
              value={pmid}
              year={entity.year as number | undefined}
              confidence={confidence}
            />
          )}
          {nctId && (
            <EvidenceBadge type="nct" value={nctId} confidence={confidence} />
          )}
          {doi && (
            <EvidenceBadge
              type="doi"
              value={doi}
              year={entity.year as number | undefined}
              confidence={confidence}
            />
          )}
        </div>
      </Section>

      {/* Full citation list */}
      {evidenceRefs.length > 0 && (
        <Section title={`Citations (${evidenceRefs.length})`}>
          <div className="space-y-2">
            {evidenceRefs.map((ref, i) => (
              <CitationCard key={`${ref.external_id}-${i}`} citation={ref} />
            ))}
          </div>
        </Section>
      )}

      {/* Contradictions */}
      {contradictions.length > 0 && (
        <Section title={`Contradictions (${contradictions.length})`}>
          <div className="space-y-2">
            {contradictions.map((c, i) => (
              <ContradictionBanner key={i} contradiction={c} />
            ))}
          </div>
        </Section>
      )}

      {evidenceRefs.length === 0 && !pmid && !nctId && (
        <p className="text-xs text-[var(--text-muted)]">
          No evidence references available for this entity.
        </p>
      )}
    </>
  );
}

function RelationshipsTab({ entity }: { entity: Record<string, unknown> }) {
  const entityId = String(entity.id || "");
  const { data, isLoading, isError } = useQuery({
    queryKey: ["inspector-relationships", entityId],
    queryFn: () => graphNeighborhoodAPI(entityId, 1),
    enabled: !!entityId,
  });

  type NeighNode = { id: string; label?: string; type?: string };
  type NeighEdge = { source: string; target: string; type?: string };
  const nodes: NeighNode[] = (data as any)?.nodes ?? [];
  const edges: NeighEdge[] = (data as any)?.edges ?? [];

  return (
    <Section title="Relationships">
      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <Loader2 size={12} className="animate-spin" /> Loading…
        </div>
      )}
      {isError && (
        <p className="text-xs text-red-500">Failed to load relationships.</p>
      )}
      {!isLoading && !isError && nodes.length === 0 && (
        <p className="text-xs text-[var(--text-muted)]">
          No graph relationships found for this entity.
        </p>
      )}
      {nodes.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] text-[var(--text-muted)] mb-1">
            {nodes.length} connected node{nodes.length > 1 ? "s" : ""},{" "}
            {edges.length} edge{edges.length !== 1 ? "s" : ""}
          </p>
          {edges.slice(0, 10).map((e, i) => (
            <div
              key={i}
              className="flex items-center gap-2 py-1 border-b border-dashed"
              style={{ borderColor: "var(--border-light)" }}
            >
              <span className="text-[10px] font-mono text-[var(--text-muted)] truncate max-w-[90px]">
                {e.source}
              </span>
              <span className="text-[9px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded">
                {e.type ?? "—"}
              </span>
              <span className="text-[10px] font-mono text-[var(--text-muted)] truncate max-w-[90px]">
                {e.target}
              </span>
            </div>
          ))}
          {edges.length > 10 && (
            <p className="text-[10px] text-[var(--text-muted)]">
              +{edges.length - 10} more edges
            </p>
          )}
        </div>
      )}
    </Section>
  );
}

function StructuresTab({ entity }: { entity: Record<string, unknown> }) {
  const pdbIds = (entity.pdb_ids as string[]) || [];
  return (
    <Section title="Structures">
      {pdbIds.length > 0 ? (
        <div className="space-y-1">
          {pdbIds.map((id) => (
            <a
              key={id}
              href={`https://www.rcsb.org/structure/${id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-xs text-[var(--accent)] hover:underline"
            >
              {id} <ExternalLink size={9} />
            </a>
          ))}
        </div>
      ) : (
        <p className="text-xs text-[var(--text-muted)]">
          No structures linked.
        </p>
      )}
    </Section>
  );
}

function PathwaysTab({ entity }: { entity: Record<string, unknown> }) {
  const entityName = String(
    entity.canonical_name || entity.name || entity.id || "",
  );
  const { data, isLoading, isError } = useQuery({
    queryKey: ["inspector-pathways", entityName],
    queryFn: () => pathwaysSearchAPI(entityName, "reactome", 5),
    enabled: !!entityName,
  });

  const pathways = data ?? [];

  return (
    <Section title="Pathways (Reactome)">
      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <Loader2 size={12} className="animate-spin" /> Searching…
        </div>
      )}
      {isError && (
        <p className="text-xs text-red-500">Failed to load pathways.</p>
      )}
      {!isLoading && !isError && pathways.length === 0 && (
        <p className="text-xs text-[var(--text-muted)]">
          No Reactome pathways found for "{entityName}".
        </p>
      )}
      {pathways.slice(0, 6).map((pw) => (
        <div
          key={pw.id}
          className="flex items-start gap-2 py-1.5 border-b border-dashed"
          style={{ borderColor: "var(--border-light)" }}
        >
          <div className="flex-1 min-w-0">
            <p className="text-[11px] text-[var(--text-primary)] font-medium leading-tight truncate">
              {pw.canonical_name}
            </p>
            {pw.species && (
              <p className="text-[10px] text-[var(--text-muted)]">
                {pw.species}
              </p>
            )}
          </div>
          {pw.url && (
            <a href={pw.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink
                size={10}
                className="text-[var(--accent)] shrink-0 mt-0.5"
              />
            </a>
          )}
        </div>
      ))}
    </Section>
  );
}

function NotesTab({ entityId }: { entityId: string }) {
  const storageKey = `inspector-note-${entityId}`;
  const [note, setNote] = useState(
    () => localStorage.getItem(storageKey) ?? "",
  );

  const handleChange = (val: string) => {
    setNote(val);
    if (val) {
      localStorage.setItem(storageKey, val);
    } else {
      localStorage.removeItem(storageKey);
    }
  };

  return (
    <Section title="Notes">
      <textarea
        value={note}
        onChange={(e) => handleChange(e.target.value)}
        placeholder="Add notes about this entity…"
        className="w-full h-24 px-2.5 py-2 text-xs rounded border bg-[var(--bg-app)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] resize-none"
        style={{ borderColor: "var(--border)" }}
      />
      {note && (
        <p className="text-[10px] text-[var(--text-muted)] mt-1">
          Saved to browser storage.
        </p>
      )}
    </Section>
  );
}

function ExportTab({ entity }: { entity: Record<string, unknown> }) {
  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(entity, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `entity_${entity.id || "unknown"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Section title="Export Options">
      <button
        onClick={exportJSON}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs rounded border hover:bg-gray-50 transition-colors"
        style={{ borderColor: "var(--border)" }}
      >
        <Download size={12} /> Export as JSON
      </button>
      <button
        onClick={() => {
          const name = String(
            entity.canonical_name ||
              entity.name ||
              entity.title ||
              entity.id ||
              "Unknown",
          );
          const id = String(entity.id || "");
          const type = String(entity.entity_type || "entity");
          const source =
            ((entity.provenance as Array<Record<string, unknown>>)?.[0]
              ?.source_name as string) || "Drug Designer";
          const citation = `${name} [${type}] (${id}). Retrieved from ${source} via Drug Designer.`;
          navigator.clipboard.writeText(citation);
        }}
        className="flex items-center gap-2 w-full px-3 py-2 mt-2 text-xs rounded border hover:bg-gray-50 transition-colors"
        style={{ borderColor: "var(--border)" }}
      >
        <Copy size={12} /> Copy Citation
      </button>
    </Section>
  );
}
