/**
 * ProvenanceBadge — Source Provenance Display (Drug Designer §Rule 6, §4.2)
 *
 * Displays evidence source lineage inline: source name, retrieval time,
 * confidence hint, and contradiction state.
 *
 * Every meaningful scientific output must preserve source lineage (§4.2).
 */

import React from "react";

interface ProvenanceBadgeProps {
  sourceName: string;
  sourceFamily?: string;
  confidence?: number;
  contradictionState?: "none" | "flagged" | "confirmed";
  retrievedAt?: string;
  url?: string;
  compact?: boolean;
}

const confidenceColor = (c: number): string => {
  if (c >= 0.8) return "#10b981";
  if (c >= 0.5) return "#f59e0b";
  return "#ef4444";
};

const ProvenanceBadge: React.FC<ProvenanceBadgeProps> = ({
  sourceName,
  sourceFamily,
  confidence,
  contradictionState = "none",
  retrievedAt,
  url,
  compact = false,
}) => {
  const hasContradiction = contradictionState !== "none";

  const badge = (
    <span
      className="provenance-badge"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.35rem",
        padding: compact ? "0.1rem 0.4rem" : "0.2rem 0.6rem",
        borderRadius: "4px",
        fontSize: compact ? "0.65rem" : "0.75rem",
        fontFamily: "var(--font-mono, monospace)",
        background: hasContradiction
          ? "rgba(239, 68, 68, 0.1)"
          : "rgba(59, 130, 246, 0.08)",
        border: `1px solid ${hasContradiction ? "rgba(239, 68, 68, 0.3)" : "rgba(59, 130, 246, 0.15)"}`,
        color: "var(--text-muted)",
        cursor: url ? "pointer" : "default",
      }}
      title={`Source: ${sourceName}${sourceFamily ? ` (${sourceFamily})` : ""}${retrievedAt ? ` | Retrieved: ${retrievedAt}` : ""}${confidence !== undefined ? ` | Confidence: ${(confidence * 100).toFixed(0)}%` : ""}`}
    >
      {/* Source name */}
      <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
        {sourceName}
      </span>

      {/* Confidence dot */}
      {confidence !== undefined && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: confidenceColor(confidence),
            display: "inline-block",
          }}
        />
      )}

      {/* Contradiction indicator */}
      {contradictionState === "flagged" && (
        <span
          style={{ color: "#f59e0b", fontWeight: 700 }}
          title="Contradiction flagged"
        >
          ⚡
        </span>
      )}
      {contradictionState === "confirmed" && (
        <span
          style={{ color: "#ef4444", fontWeight: 700 }}
          title="Contradiction confirmed"
        >
          ⚠
        </span>
      )}
    </span>
  );

  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        style={{ textDecoration: "none" }}
      >
        {badge}
      </a>
    );
  }

  return badge;
};

export default ProvenanceBadge;
