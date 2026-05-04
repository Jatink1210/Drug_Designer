/**
 * HealthStrip — Minimal system health bar.
 * Shows connection, runtime, model, sources, active runs.
 * §Rule 3: No fake health.
 */

import React from "react";

interface HealthStripProps {
  runtimeMode: "hosted" | "local" | "auto";
  activeModel: string;
  sourcesHealthy: number;
  sourcesDegraded: number;
  sourcesDown: number;
  activeRuns: number;
  isConnected: boolean;
  degradedWarning?: string;
  projectName?: string;
  lastRunAt?: string;
  /** True after all reconnect attempts are exhausted — WS permanently lost */
  permanentlyDisconnected?: boolean;
}

const pill = (bg: string, color: string, text: string) => (
  <span
    style={{
      padding: "1px 8px",
      borderRadius: "9999px",
      background: bg,
      color,
      fontWeight: 600,
      fontSize: "10px",
      letterSpacing: "0.02em",
    }}
  >
    {text}
  </span>
);

const label = (t: string) => (
  <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>{t}</span>
);

const val = (t: string) => (
  <span style={{ color: "var(--text-secondary)", fontSize: "11px", fontWeight: 500 }}>{t}</span>
);

const dot = (color: string) => (
  <span
    style={{
      width: 6,
      height: 6,
      borderRadius: "50%",
      background: color,
      display: "inline-block",
      boxShadow: `0 0 6px ${color}40`,
    }}
  />
);

const sep = () => (
  <span
    style={{
      width: 1,
      height: 14,
      background: "var(--border)",
      display: "inline-block",
      flexShrink: 0,
    }}
  />
);

const HealthStrip: React.FC<HealthStripProps> = ({
  runtimeMode,
  activeModel,
  sourcesHealthy,
  sourcesDegraded,
  sourcesDown,
  activeRuns,
  isConnected,
  degradedWarning,
  projectName,
  lastRunAt,
  permanentlyDisconnected = false,
}) => {
  const totalSources = sourcesHealthy + sourcesDegraded + sourcesDown;
  const hasIssues = sourcesDegraded > 0 || sourcesDown > 0 || !isConnected;

  return (
    <div
      className="health-strip"
      role="status"
      aria-label="System health"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "14px",
        padding: "5px 20px",
        fontFamily: "var(--font-body)",
        background: hasIssues
          ? "rgba(245, 158, 11, 0.04)"
          : "var(--bg-app)",
        borderBottom: "1px solid var(--border)",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Connection */}
      <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        {dot(isConnected ? "var(--success)" : "var(--error)")}
        <span style={{ fontSize: "11px", fontWeight: 500, color: isConnected ? "var(--success)" : "var(--error)" }}>
          {isConnected ? "Online" : permanentlyDisconnected ? "Connection Lost" : "Offline"}
        </span>
      </span>

      {permanentlyDisconnected && (
        <>
          {sep()}
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            {pill("rgba(239,68,68,0.15)", "#ef4444", "⛔ Real-time updates unavailable — reload to reconnect")}
          </span>
        </>
      )}

      {sep()}

      {/* Runtime */}
      <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        {label("Runtime")}
        {pill(
          runtimeMode === "local" ? "rgba(139,92,246,0.1)" : "rgba(59,130,246,0.1)",
          runtimeMode === "local" ? "#8b5cf6" : "var(--accent)",
          runtimeMode.toUpperCase(),
        )}
      </span>

      {sep()}

      {/* Model */}
      {activeModel && (
        <>
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            {label("Model")}
            {val(activeModel)}
          </span>
          {sep()}
        </>
      )}

      {/* Project */}
      {projectName && (
        <>
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            {label("Project")}
            <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-primary)" }}>{projectName}</span>
          </span>
          {sep()}
        </>
      )}

      {/* Last run */}
      {lastRunAt && (
        <>
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            {label("Last run")}
            {val(lastRunAt)}
          </span>
          {sep()}
        </>
      )}

      {/* Sources */}
      <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        {label("Sources")}
        <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <span style={{ color: "var(--success)", fontSize: "11px", fontWeight: 600 }}>{sourcesHealthy}</span>
          {sourcesDegraded > 0 && (
            <span style={{ color: "var(--warning)", fontSize: "11px", fontWeight: 600 }}>· {sourcesDegraded}</span>
          )}
          {sourcesDown > 0 && (
            <span style={{ color: "var(--error)", fontSize: "11px", fontWeight: 600 }}>· {sourcesDown}</span>
          )}
          <span style={{ color: "var(--text-muted)", fontSize: "10px" }}>/ {totalSources}</span>
        </span>
      </span>

      {/* Active Runs */}
      {activeRuns > 0 && (
        <>
          {sep()}
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span
              style={{
                width: 8,
                height: 8,
                border: "1.5px solid var(--border)",
                borderTopColor: "var(--accent)",
                borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
                display: "inline-block",
              }}
            />
            <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--accent)" }}>
              {activeRuns} active
            </span>
          </span>
        </>
      )}

      {/* Degraded Warning */}
      {degradedWarning && (
        <span
          style={{
            marginLeft: "auto",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          {pill("rgba(245,158,11,0.12)", "var(--warning)", `⚠ ${degradedWarning}`)}
        </span>
      )}
    </div>
  );
};

export default HealthStrip;
