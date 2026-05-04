/**
 * StateWrapper — Universal 6-State Handler (Drug Designer §Rule 2, §115)
 *
 * Every module must handle 6 states truthfully:
 *   1. initial   — first visit, no data yet
 *   2. loading   — fetching data, show real progress
 *   3. empty     — query returned zero results — explain WHY
 *   4. degraded  — partial data, some sources failed — show which
 *   5. error     — hard failure — explain with remediation
 *   6. success   — real data, render the content
 *
 * No module may show fake-success (green checkmarks with no real work).
 */

import React from "react";

export type ViewState =
  | "initial"
  | "loading"
  | "empty"
  | "degraded"
  | "error"
  | "success";

interface DegradedInfo {
  reason: string;
  affectedSources: string[];
}

interface ErrorInfo {
  code: string;
  message: string;
  suggestedAction?: string;
  recoverable?: boolean;
}

interface StateWrapperProps {
  state: ViewState;
  children: React.ReactNode;
  moduleName: string;

  // Loading state
  loadingMessage?: string;
  progressPercent?: number;

  // Empty state
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: { label: string; onClick: () => void };

  // Degraded state
  degradedInfo?: DegradedInfo;
  degradedChildren?: React.ReactNode;

  // Error state
  errorInfo?: ErrorInfo;
  onRetry?: () => void;
}

const StateWrapper: React.FC<StateWrapperProps> = ({
  state,
  children,
  moduleName,
  loadingMessage,
  progressPercent,
  emptyTitle,
  emptyDescription,
  emptyAction,
  degradedInfo,
  degradedChildren,
  errorInfo,
  onRetry,
}) => {
  // §65 WCAG AA: Announce state transitions to screen readers
  const isLiveState = state === "loading" || state === "error" || state === "degraded" || state === "empty";

  // ── Initial State ─────────────────────────────────────
  if (state === "initial") {
    return (
      <div
        className="state-wrapper state-initial"
        role="status"
        aria-label={`${moduleName} initial state`}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "3rem",
            gap: "1rem",
            color: "var(--text-muted)",
          }}
        >
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4m0 4h.01" />
          </svg>
          <p style={{ fontSize: "1.1rem", margin: 0 }}>Ready to begin</p>
          <p style={{ fontSize: "0.85rem", margin: 0, opacity: 0.7 }}>
            Start a query or action to see results in {moduleName}
          </p>
        </div>
      </div>
    );
  }

  // ── Loading State ─────────────────────────────────────
  if (state === "loading") {
    return (
      <div
        className="state-wrapper state-loading"
        role="status"
        aria-live="polite"
        aria-label={`${moduleName} loading`}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "3rem",
            gap: "1rem",
          }}
        >
          <div
            className="spinner"
            style={{
              width: 40,
              height: 40,
              border: "3px solid var(--border)",
              borderTopColor: "var(--accent)",
              borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
            }}
          />
          <p style={{ margin: 0, color: "var(--text-muted)" }}>
            {loadingMessage || `Loading ${moduleName}...`}
          </p>
          {progressPercent !== undefined && (
            <div
              style={{
                width: "200px",
                background: "var(--border)",
                borderRadius: "4px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${progressPercent}%`,
                  height: "4px",
                  background: "var(--accent)",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Empty State ───────────────────────────────────────
  if (state === "empty") {
    return (
      <div
        className="state-wrapper state-empty"
        role="status"
        aria-live="polite"
        aria-label={`${moduleName} empty`}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "3rem",
            gap: "0.75rem",
            color: "var(--text-muted)",
          }}
        >
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <line x1="9" y1="9" x2="15" y2="15" />
            <line x1="15" y1="9" x2="9" y2="15" />
          </svg>
          <p style={{ fontSize: "1.1rem", margin: 0, fontWeight: 600 }}>
            {emptyTitle || "No results found"}
          </p>
          <p
            style={{
              fontSize: "0.85rem",
              margin: 0,
              maxWidth: "400px",
              textAlign: "center",
            }}
          >
            {emptyDescription ||
              "The query returned zero results. Try different search terms or broaden your criteria."}
          </p>
          {emptyAction && (
            <button
              onClick={emptyAction.onClick}
              style={{
                marginTop: "0.5rem",
                padding: "0.5rem 1.25rem",
                borderRadius: "6px",
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                cursor: "pointer",
              }}
            >
              {emptyAction.label}
            </button>
          )}
        </div>
      </div>
    );
  }

  // ── Degraded State ────────────────────────────────────
  if (state === "degraded") {
    return (
      <div className="state-wrapper state-degraded">
        <div
          style={{
            padding: "0.75rem 1rem",
            margin: "0 0 1rem",
            borderRadius: "8px",
            background: "rgba(255, 171, 0, 0.1)",
            border: "1px solid rgba(255, 171, 0, 0.3)",
            display: "flex",
            alignItems: "flex-start",
            gap: "0.75rem",
          }}
          role="alert"
        >
          <span style={{ fontSize: "1.25rem" }}>⚠️</span>
          <div>
            <p
              style={{
                margin: 0,
                fontWeight: 600,
                color: "var(--warning)",
              }}
            >
              Partial results — some sources unavailable
            </p>
            {degradedInfo && (
              <p
                style={{
                  margin: "0.25rem 0 0",
                  fontSize: "0.8rem",
                  color: "var(--text-muted)",
                }}
              >
                {degradedInfo.reason}
                {degradedInfo.affectedSources.length > 0 && (
                  <> · Affected: {degradedInfo.affectedSources.join(", ")}</>
                )}
              </p>
            )}
          </div>
        </div>
        {degradedChildren || children}
      </div>
    );
  }

  // ── Error State ───────────────────────────────────────
  if (state === "error") {
    return (
      <div
        className="state-wrapper state-error"
        role="alert"
        aria-live="assertive"
        aria-label={`${moduleName} error`}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "3rem",
            gap: "0.75rem",
          }}
        >
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--error, #ef4444)"
            strokeWidth="1.5"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          <p
            style={{
              fontSize: "1.1rem",
              margin: 0,
              fontWeight: 600,
              color: "var(--error, #ef4444)",
            }}
          >
            {errorInfo?.message || "An error occurred"}
          </p>
          {errorInfo?.code && (
            <code
              style={{
                fontSize: "0.75rem",
                color: "var(--text-muted)",
                background: "var(--bg-surface)",
                padding: "0.25rem 0.5rem",
                borderRadius: "4px",
              }}
            >
              {errorInfo.code}
            </code>
          )}
          {errorInfo?.suggestedAction && (
            <p
              style={{
                fontSize: "0.85rem",
                margin: 0,
                color: "var(--text-muted)",
              }}
            >
              {errorInfo.suggestedAction}
            </p>
          )}
          {onRetry && (
            <button
              onClick={onRetry}
              style={{
                marginTop: "0.5rem",
                padding: "0.5rem 1.25rem",
                borderRadius: "6px",
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                cursor: "pointer",
              }}
            >
              Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  // ── Success State ─────────────────────────────────────
  return <div className="state-wrapper state-success" aria-live="polite">{children}</div>;
};

export default StateWrapper;
