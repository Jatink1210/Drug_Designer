/**
 * RunProgressTracker — Inline Run Monitoring (Drug Designer §51, §57)
 *
 * Shows real-time progress of a tracked Run via WebSocket events.
 * §51: Every run MUST emit granular WebSocket pulses — not a single
 * meaningless spinner.
 *
 * Displays: run type, current stage, progress bar, sources completed,
 * elapsed time, and any degraded/error signals.
 */

import React, { useState, useEffect } from "react";

interface RunProgress {
  runId: string;
  runType: string;
  state: string;
  stage: string;
  progressPercent: number;
  message: string;
  sourcesCompleted: number;
  sourcesTotal: number;
  elapsedMs: number;
  degradedSources: string[];
  error?: string;
}

interface RunProgressTrackerProps {
  progress: RunProgress;
  compact?: boolean;
  onCancel?: (runId: string) => void;
  onInspect?: (runId: string) => void;
}

const stateColors: Record<string, string> = {
  CREATED: "#6b7280",
  QUEUED: "#6366f1",
  RUNNING: "#3b82f6",
  PARTIAL_SUCCESS: "#f59e0b",
  SUCCESS: "#10b981",
  FAILED: "#ef4444",
  CANCELLED: "#6b7280",
  TIMED_OUT: "#f59e0b",
};

const formatElapsed = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
};

const RunProgressTracker: React.FC<RunProgressTrackerProps> = ({
  progress,
  compact = false,
  onCancel,
  onInspect,
}) => {
  const isActive = ["CREATED", "QUEUED", "RUNNING"].includes(progress.state);
  const isDone = ["SUCCESS", "PARTIAL_SUCCESS"].includes(progress.state);
  const hasError = ["FAILED", "TIMED_OUT"].includes(progress.state);
  const color = stateColors[progress.state] || "#6b7280";

  return (
    <div
      className="run-progress-tracker"
      style={{
        padding: compact ? "0.5rem 0.75rem" : "0.75rem 1rem",
        borderRadius: "8px",
        background: "var(--bg-surface)",
        border: `1px solid ${hasError ? "rgba(239, 68, 68, 0.3)" : "var(--border)"}`,
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {isActive && (
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                border: "2px solid var(--border)",
                borderTopColor: color,
                animation: "spin 0.8s linear infinite",
                display: "inline-block",
              }}
            />
          )}
          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>
            {progress.runType}
          </span>
          <span
            style={{
              padding: "0.1rem 0.4rem",
              borderRadius: "3px",
              fontSize: "0.65rem",
              background: `${color}22`,
              color,
              fontWeight: 600,
            }}
          >
            {progress.state}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span
            style={{
              fontSize: "0.7rem",
              color: "var(--text-muted)",
              fontFamily: "monospace",
            }}
          >
            {formatElapsed(progress.elapsedMs)}
          </span>
          {onInspect && (
            <button
              onClick={() => onInspect(progress.runId)}
              style={{
                padding: "0.15rem 0.5rem",
                borderRadius: "4px",
                fontSize: "0.7rem",
                background: "transparent",
                border: "1px solid var(--border)",
                color: "var(--text-muted)",
                cursor: "pointer",
              }}
            >
              Inspect
            </button>
          )}
          {isActive && onCancel && (
            <button
              onClick={() => onCancel(progress.runId)}
              style={{
                padding: "0.15rem 0.5rem",
                borderRadius: "4px",
                fontSize: "0.7rem",
                background: "transparent",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                color: "#ef4444",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {isActive && (
        <div>
          <div
            style={{
              width: "100%",
              height: "4px",
              background: "var(--border)",
              borderRadius: "2px",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${progress.progressPercent}%`,
                height: "100%",
                background: color,
                transition: "width 0.5s ease",
              }}
            />
          </div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: "0.25rem",
              fontSize: "0.7rem",
              color: "var(--text-muted)",
            }}
          >
            <span>
              {progress.stage}: {progress.message}
            </span>
            <span>
              {progress.sourcesCompleted}/{progress.sourcesTotal} sources
            </span>
          </div>
        </div>
      )}

      {/* Degraded sources */}
      {progress.degradedSources.length > 0 && (
        <div
          style={{
            fontSize: "0.7rem",
            color: "#f59e0b",
            display: "flex",
            alignItems: "center",
            gap: "0.35rem",
          }}
        >
          ⚠ Degraded: {progress.degradedSources.join(", ")}
        </div>
      )}

      {/* Error */}
      {progress.error && (
        <div
          style={{
            fontSize: "0.75rem",
            color: "#ef4444",
            padding: "0.35rem 0.5rem",
            background: "rgba(239, 68, 68, 0.08)",
            borderRadius: "4px",
          }}
        >
          {progress.error}
        </div>
      )}
    </div>
  );
};

export default RunProgressTracker;
