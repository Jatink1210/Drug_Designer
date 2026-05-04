/** ContradictionBanner — side-by-side display of contradictory findings. */

import { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from "lucide-react";
import type { ContradictionDTO } from "@/lib/api";

const SEVERITY_STYLES: Record<
  string,
  { border: string; bg: string; text: string }
> = {
  high: { border: "#dc2626", bg: "#fef2f2", text: "#991b1b" },
  moderate: { border: "#d97706", bg: "#fffbeb", text: "#92400e" },
  low: { border: "#6b7280", bg: "#f9fafb", text: "#374151" },
};

function SourceRef({ source }: { source: ContradictionDTO["source_a"] }) {
  return (
    <div className="text-[10px] mt-1 text-[var(--text-muted)]">
      <span className="font-medium">{source.source}</span>
      {source.external_id && (
        <span className="font-mono ml-1">{source.external_id}</span>
      )}
      {source.url && (
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-0.5 ml-1 text-[var(--accent)] hover:underline"
        >
          <ExternalLink size={7} />
        </a>
      )}
    </div>
  );
}

export default function ContradictionBanner({
  contradiction,
}: {
  contradiction: ContradictionDTO;
}) {
  const [expanded, setExpanded] = useState(false);
  const style =
    SEVERITY_STYLES[contradiction.severity] || SEVERITY_STYLES.moderate;

  return (
    <div
      className="rounded-lg border-l-4 overflow-hidden"
      style={{ borderColor: style.border, backgroundColor: style.bg }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
      >
        <AlertTriangle size={12} style={{ color: style.text }} />
        <span
          className="text-[11px] font-medium flex-1"
          style={{ color: style.text }}
        >
          Contradictory evidence ({contradiction.severity})
        </span>
        {expanded ? (
          <ChevronUp size={12} style={{ color: style.text }} />
        ) : (
          <ChevronDown size={12} style={{ color: style.text }} />
        )}
      </button>

      {/* Details */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-start">
            {/* Claim A */}
            <div className="rounded p-2 bg-white/70">
              <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed line-clamp-3">
                {contradiction.claim_a}
              </p>
              <SourceRef source={contradiction.source_a} />
            </div>
            {/* Divider */}
            <div className="flex items-center px-1">
              <span
                className="text-[10px] font-bold"
                style={{ color: style.text }}
              >
                vs
              </span>
            </div>
            {/* Claim B */}
            <div className="rounded p-2 bg-white/70">
              <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed line-clamp-3">
                {contradiction.claim_b}
              </p>
              <SourceRef source={contradiction.source_b} />
            </div>
          </div>
          {contradiction.explanation && (
            <p className="text-[10px] italic" style={{ color: style.text }}>
              {contradiction.explanation}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
