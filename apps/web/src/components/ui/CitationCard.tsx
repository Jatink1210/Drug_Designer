/** CitationCard — compact citation display with source badge, ID, confidence. */

import { ExternalLink } from "lucide-react";
import type { CitationRefDTO } from "@/lib/api";

const SOURCE_COLORS: Record<string, string> = {
  PubMed: "#d97706",
  ClinicalTrials: "#059669",
  ChEMBL: "#7c3aed",
  UniProt: "#2563eb",
  DOI: "#dc2626",
  OpenTargets: "#0891b2",
  RCSB: "#db2777",
  PubChem: "#ea580c",
};

const TYPE_INDICATORS: Record<string, { label: string; color: string }> = {
  supporting: { label: "Supporting", color: "#16a34a" },
  contradicting: { label: "Contradicting", color: "#dc2626" },
  neutral: { label: "Neutral", color: "#6b7280" },
};

export default function CitationCard({
  citation,
}: {
  citation: CitationRefDTO;
}) {
  const sourceColor = SOURCE_COLORS[citation.source] || "#6b7280";
  const typeInfo =
    TYPE_INDICATORS[citation.evidence_type] || TYPE_INDICATORS.neutral;
  const confidencePct = Math.round(citation.confidence * 100);

  return (
    <a
      href={citation.url || undefined}
      target="_blank"
      rel="noopener noreferrer"
      className="block px-3 py-2 rounded-lg border hover:shadow-sm transition-all"
      style={{ borderColor: "var(--border)" }}
    >
      <div className="flex items-center gap-2 mb-1">
        {/* Source badge */}
        <span
          className="px-1.5 py-0.5 rounded text-[9px] font-semibold text-white"
          style={{ backgroundColor: sourceColor }}
        >
          {citation.source}
        </span>
        {/* External ID */}
        <span className="text-[10px] font-mono text-[var(--text-muted)] truncate">
          {citation.external_id}
        </span>
        {citation.year && (
          <span className="text-[10px] text-[var(--text-muted)]">
            ({citation.year})
          </span>
        )}
        <ExternalLink
          size={8}
          className="text-[var(--text-muted)] shrink-0 ml-auto"
        />
      </div>

      {/* Title */}
      {citation.title && (
        <p className="text-[11px] text-[var(--text-secondary)] leading-tight line-clamp-2 mb-1.5">
          {citation.title}
        </p>
      )}

      {/* Bottom: confidence bar + evidence type */}
      <div className="flex items-center gap-2">
        {/* Confidence bar */}
        <div className="flex-1 h-1.5 rounded-full bg-[var(--bg-inset)] overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${confidencePct}%`,
              backgroundColor:
                confidencePct >= 70
                  ? "#16a34a"
                  : confidencePct >= 40
                    ? "#d97706"
                    : "#dc2626",
            }}
          />
        </div>
        <span className="text-[9px] text-[var(--text-muted)] w-7 text-right">
          {confidencePct}%
        </span>
        {/* Evidence type indicator */}
        <span
          className="px-1.5 py-0.5 rounded text-[8px] font-medium"
          style={{
            color: typeInfo.color,
            backgroundColor: `${typeInfo.color}15`,
          }}
        >
          {typeInfo.label}
        </span>
      </div>
    </a>
  );
}
