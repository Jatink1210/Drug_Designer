/** ContradictionDetailDrawer — Right-side drawer for directional conflict detail view (§L-5) */
import { useEffect, useRef } from "react";
import { X, ArrowUp, ArrowDown, AlertTriangle } from "lucide-react";

interface ContradictionSource {
  claim: string;
  source: string;
  id: string;
  year: number;
  detail: string;
}

export interface ContradictionDetail {
  number: number;
  title: string;
  contradiction_type?: string;
  sourceA: ContradictionSource;
  sourceB: ContradictionSource;
  assessment: string;
  resolved: boolean;
}

const SOURCE_COLORS: Record<string, string> = {
  PubMed: "#3b82f6",
  GWAS: "#f59e0b",
  DisGeNET: "#8b5cf6",
  ClinicalTrials: "#10b981",
  ChEMBL: "#0891b2",
};

function directionArrow(claim: string) {
  const lower = claim.toLowerCase();
  if (/increase|upregulat|activat|enhance|promot|induce/i.test(lower))
    return { icon: <ArrowUp size={14} className="text-green-500" />, label: "Increases / Activates" };
  if (/decrease|downregulat|inhibit|suppress|reduc|block/i.test(lower))
    return { icon: <ArrowDown size={14} className="text-red-500" />, label: "Decreases / Inhibits" };
  return { icon: null, label: "Neutral / Unspecified" };
}

interface Props {
  contradiction: ContradictionDetail | null;
  onClose: () => void;
}

export default function ContradictionDetailDrawer({ contradiction, onClose }: Props) {
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (contradiction) {
      drawerRef.current?.focus();
    }
  }, [contradiction]);

  useEffect(() => {
    if (!contradiction) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [contradiction, onClose]);

  if (!contradiction) return null;

  const dirA = directionArrow(contradiction.sourceA.claim);
  const dirB = directionArrow(contradiction.sourceB.claim);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Drawer */}
      <div
        ref={drawerRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={`Contradiction ${contradiction.number} detail`}
        className="fixed right-0 top-0 bottom-0 w-full max-w-lg z-50 flex flex-col shadow-2xl outline-none"
        style={{ background: "var(--bg-app)", borderLeft: "1px solid var(--border)" }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-3 px-5 py-4"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <AlertTriangle size={18} style={{ color: "#C48820" }} />
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-bold truncate" style={{ color: "var(--text-primary)" }}>
              Contradiction #{contradiction.number}
            </h2>
            <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>
              {contradiction.title}
            </p>
          </div>
          {contradiction.contradiction_type && (
            <span
              className="text-[9px] font-bold px-2 py-0.5 rounded"
              style={{ background: "#fef3c7", color: "#92400e" }}
            >
              {contradiction.contradiction_type.replace(/_/g, " ")}
            </span>
          )}
          <button
            onClick={onClose}
            aria-label="Close contradiction detail"
            className="ml-1 p-1 rounded hover:bg-[var(--bg-elevated)] transition-colors"
            style={{ color: "var(--text-muted)" }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Directional conflict side-by-side */}
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>
              Directional Conflict
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {/* Source A */}
              <div
                className="p-4 rounded-lg space-y-2"
                style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
              >
                <div className="flex items-center gap-1.5">
                  {dirA.icon}
                  <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: "#C48820" }}>
                    Source A
                  </span>
                </div>
                <p className="text-[11px] font-medium leading-relaxed" style={{ color: "var(--text-primary)" }}>
                  "{contradiction.sourceA.claim}"
                </p>
                <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                  {dirA.label}
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span
                    className="px-1.5 py-0.5 rounded text-white text-[8px] font-bold"
                    style={{ background: SOURCE_COLORS[contradiction.sourceA.source] || "#6b7280" }}
                  >
                    {contradiction.sourceA.source}
                  </span>
                  <span className="text-[9px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                    {contradiction.sourceA.id}
                  </span>
                  {contradiction.sourceA.year > 0 && (
                    <span className="text-[9px]" style={{ color: "var(--text-muted)" }}>
                      {contradiction.sourceA.year}
                    </span>
                  )}
                </div>
                {contradiction.sourceA.detail && (
                  <p className="text-[10px] leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                    {contradiction.sourceA.detail}
                  </p>
                )}
              </div>

              {/* Source B */}
              <div
                className="p-4 rounded-lg space-y-2"
                style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
              >
                <div className="flex items-center gap-1.5">
                  {dirB.icon}
                  <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: "#C48820" }}>
                    Source B
                  </span>
                </div>
                <p className="text-[11px] font-medium leading-relaxed" style={{ color: "var(--text-primary)" }}>
                  "{contradiction.sourceB.claim}"
                </p>
                <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                  {dirB.label}
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span
                    className="px-1.5 py-0.5 rounded text-white text-[8px] font-bold"
                    style={{ background: SOURCE_COLORS[contradiction.sourceB.source] || "#6b7280" }}
                  >
                    {contradiction.sourceB.source}
                  </span>
                  <span className="text-[9px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                    {contradiction.sourceB.id}
                  </span>
                  {contradiction.sourceB.year > 0 && (
                    <span className="text-[9px]" style={{ color: "var(--text-muted)" }}>
                      {contradiction.sourceB.year}
                    </span>
                  )}
                </div>
                {contradiction.sourceB.detail && (
                  <p className="text-[10px] leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                    {contradiction.sourceB.detail}
                  </p>
                )}
              </div>
            </div>
          </section>

          {/* Assessment */}
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
              Assessment
            </h3>
            <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              {contradiction.assessment}
            </p>
          </section>

          {/* Status */}
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
              Status
            </h3>
            {contradiction.resolved ? (
              <span
                className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded"
                style={{ background: "#ecfdf5", color: "#047857" }}
              >
                ✓ Resolved
              </span>
            ) : (
              <span
                className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded"
                style={{ background: "#fef3c7", color: "#92400e" }}
              >
                ⚠ Active — Awaiting resolution
              </span>
            )}
          </section>
        </div>

        {/* Footer */}
        <div
          className="px-5 py-3 flex justify-end"
          style={{ borderTop: "1px solid var(--border)" }}
        >
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs rounded border transition-colors hover:bg-[var(--bg-elevated)]"
            style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
          >
            Close
          </button>
        </div>
      </div>
    </>
  );
}
