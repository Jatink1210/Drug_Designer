/**
 * RepairScreen — Shown when the backend is unhealthy.
 *
 * This replaces the normal app shell until the backend passes its health
 * check.  It shows diagnostics, troubleshooting steps, and a retry button.
 */

import { useState, useEffect } from "react";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from '../lib/types';

interface RepairScreenProps {
  status: string;
  error: string | null;
  onRetry: () => void;
}

export default function RepairScreen({
  status,
  error,
  onRetry,
}: RepairScreenProps) {
  const [retrying, setRetrying] = useState(false);
  const [dots, setDots] = useState("");

  // Animate dots while retrying
  useEffect(() => {
    if (!retrying) return;
    const id = setInterval(() => {
      setDots((d) => (d.length >= 3 ? "" : d + "."));
    }, 500);
    return () => clearInterval(id);
  }, [retrying]);

  const handleRetry = () => {
    setRetrying(true);
    onRetry();
    // Reset after 15s to allow another attempt
    setTimeout(() => setRetrying(false), 15_000);
  };

  const statusConfig = getStatusConfig(status);

  return (
    <StateWrapper state={"success" as ViewState} moduleName="Recovery">
    <div
      className="min-h-screen w-full flex items-center justify-center overflow-y-auto"
      style={{
        background:
          "linear-gradient(135deg, var(--bg-app) 0%, var(--bg-surface) 50%, var(--bg-elevated) 100%)",
      }}
    >
      <div
        style={{
          maxWidth: 520,
          width: "100%",
          padding: 40,
          borderRadius: 16,
          background: "var(--bg-elevated)",
          border: "1px solid var(--border)",
          backdropFilter: "blur(20px)",
          textAlign: "center",
          boxShadow: "0 4px 24px rgba(0,0,0,0.06)",
        }}
      >
        {/* Status indicator */}
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: "50%",
            margin: "0 auto 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: statusConfig.bgColor,
            boxShadow: `0 0 32px ${statusConfig.glowColor}`,
          }}
        >
          <span style={{ fontSize: 28 }}>{statusConfig.icon}</span>
        </div>

        {/* Title */}
        <h1
          style={{
            fontSize: 22,
            fontWeight: 700,
            color: "var(--text-primary)",
            margin: "0 0 8px",
            fontFamily: "'Inter', system-ui, sans-serif",
          }}
        >
          {statusConfig.title}
        </h1>

        {/* Subtitle */}
        <p
          style={{
            fontSize: 14,
            color: "var(--text-secondary)",
            margin: "0 0 24px",
            lineHeight: 1.6,
            fontFamily: "'Inter', system-ui, sans-serif",
          }}
        >
          {statusConfig.description}
        </p>

        {/* Error detail */}
        {error && (
          <div
            style={{
              textAlign: "left",
              padding: 16,
              borderRadius: 10,
              background: "rgba(255,80,80,0.06)",
              border: "1px solid rgba(255,80,80,0.15)",
              marginBottom: 24,
              fontSize: 12,
              color: "var(--error, #c44)",
              fontFamily: "monospace",
              lineHeight: 1.6,
              wordBreak: "break-word",
            }}
          >
            {error}
          </div>
        )}

        {/* Troubleshooting steps */}
        <div
          style={{
            textAlign: "left",
            marginBottom: 28,
            padding: "16px 20px",
            borderRadius: 10,
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: 1,
              marginBottom: 12,
              fontFamily: "'Inter', system-ui, sans-serif",
            }}
          >
            Troubleshooting
          </div>
          <ul
            style={{
              margin: 0,
              padding: "0 0 0 18px",
              fontSize: 12,
              color: "var(--text-secondary)",
              lineHeight: 2,
              fontFamily: "'Inter', system-ui, sans-serif",
            }}
          >
            {status === "python_not_found" ? (
              <>
                <li>
                  Install <strong>Python 3.10+</strong> from{" "}
                  <a
                    href="https://python.org"
                    target="_blank"
                    rel="noopener"
                    style={{ color: "var(--accent)" }}
                  >
                    python.org
                  </a>
                </li>
                <li>
                  Ensure{" "}
                  <code
                    style={{
                      color: "var(--accent)",
                      background: "var(--bg-surface)",
                      padding: "2px 6px",
                      borderRadius: 4,
                    }}
                  >
                    python3
                  </code>{" "}
                  is in your system PATH
                </li>
                <li>Restart the application after installing</li>
              </>
            ) : (
              <>
                <li>Check that all Python dependencies are installed</li>
                <li>
                  Run{" "}
                  <code
                    style={{
                      color: "var(--accent)",
                      background: "var(--bg-surface)",
                      padding: "2px 6px",
                      borderRadius: 4,
                    }}
                  >
                    pip install -r requirements.txt
                  </code>{" "}
                  in the api directory
                </li>
                <li>Check terminal output for import errors</li>
                <li>Ensure port is not already in use by another process</li>
              </>
            )}
          </ul>
        </div>

        {/* Retry button */}
        <button
          onClick={handleRetry}
          disabled={retrying}
          style={{
            width: "100%",
            padding: "12px 24px",
            borderRadius: 10,
            border: "none",
            background: retrying
              ? "var(--bg-surface)"
              : "var(--accent)",
            color: retrying ? "var(--text-muted)" : "#ffffff",
            fontSize: 14,
            fontWeight: 600,
            cursor: retrying ? "not-allowed" : "pointer",
            transition: "all 0.2s ease",
            fontFamily: "'Inter', system-ui, sans-serif",
            boxShadow: retrying ? "none" : "0 4px 16px rgba(80,80,255,0.3)",
          }}
        >
          {retrying ? `Reconnecting${dots}` : "Retry Connection"}
        </button>

        {/* Version footer */}
        <div
          style={{
            marginTop: 24,
            fontSize: 10,
            color: "var(--text-muted)",
            fontFamily: "'Inter', system-ui, sans-serif",
          }}
        >
          Drug Designer v1.0.0 • Scientific Discovery Studio
        </div>
      </div>
    </div>
    </StateWrapper>
  );
}

function getStatusConfig(status: string) {
  switch (status) {
    case "python_not_found":
      return {
        icon: "🐍",
        title: "Python Not Found",
        description:
          "The scientific backend requires Python 3.10 or later. Please install Python and restart the application.",
        bgColor: "rgba(255, 160, 40, 0.15)",
        glowColor: "rgba(255, 160, 40, 0.2)",
      };
    case "failed_to_start":
      return {
        icon: "⚠️",
        title: "Backend Failed to Start",
        description:
          "The API server could not be launched. This is usually caused by missing dependencies or configuration issues.",
        bgColor: "rgba(255, 80, 80, 0.15)",
        glowColor: "rgba(255, 80, 80, 0.2)",
      };
    case "unhealthy":
      return {
        icon: "🔴",
        title: "Backend Unhealthy",
        description:
          "The API server started but did not pass its health check. It may still be initializing or encountering runtime errors.",
        bgColor: "rgba(255, 80, 80, 0.15)",
        glowColor: "rgba(255, 80, 80, 0.2)",
      };
    default: // "starting" or unknown
      return {
        icon: "⏳",
        title: "Starting Backend",
        description:
          "The scientific backend is starting up. This may take a few seconds on first launch.",
        bgColor: "rgba(100, 140, 255, 0.15)",
        glowColor: "rgba(100, 140, 255, 0.2)",
      };
  }
}
