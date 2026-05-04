import { usePageConfidenceData } from "@/lib/PageConfidenceContext";

const FRESHNESS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  current: { bg: "rgba(16,185,129,0.15)", text: "#10b981", label: "Current" },
  stale:   { bg: "rgba(245,158,11,0.15)", text: "#f59e0b", label: "Stale" },
  unknown: { bg: "rgba(148,163,184,0.15)", text: "#94a3b8", label: "Unknown" },
};

export default function PageConfidenceBanner() {
  const confidence = usePageConfidenceData();
  if (!confidence) return null;

  const f = FRESHNESS_STYLES[confidence.freshness] ?? FRESHNESS_STYLES.unknown;

  return (
    <div
      className="w-full flex items-center gap-3 px-4 text-[10px] shrink-0"
      style={{ background: "var(--bg-surface)", borderBottom: "1px solid var(--border)", height: 26 }}
    >
      {/* Freshness tag */}
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-medium"
        style={{ background: f.bg, color: f.text }}
      >
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: f.text }} />
        {f.label}
        {confidence.freshnessDetail && (
          <span className="opacity-70 ml-0.5">· {confidence.freshnessDetail}</span>
        )}
      </span>

      {/* Source count */}
      <span style={{ color: "var(--text-muted)" }}>
        {confidence.sourceCount} source{confidence.sourceCount !== 1 ? "s" : ""}
        {confidence.sourcesQueried && confidence.sourcesQueried.length > 0 && (
          <span className="ml-1 opacity-60">({confidence.sourcesQueried.join(", ")})</span>
        )}
      </span>

      {/* Confidence bar if provided */}
      {confidence.avgConfidence != null && (
        <span className="ml-auto flex items-center gap-1.5" style={{ color: "var(--text-muted)" }}>
          Confidence
          <span className="inline-block w-16 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
            <span
              className="block h-full rounded-full"
              style={{ width: `${Math.round(confidence.avgConfidence * 100)}%`, background: "var(--accent)" }}
            />
          </span>
          <span className="font-medium" style={{ color: "var(--text-primary)" }}>
            {Math.round(confidence.avgConfidence * 100)}%
          </span>
        </span>
      )}
    </div>
  );
}
