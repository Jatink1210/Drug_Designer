/**
 * NotificationToast — Transient Alert System (Drug Designer §3.2)
 *
 * Displays transient notifications for: run completions, errors,
 * degraded source warnings, export readiness, and system alerts.
 *
 * Auto-dismisses after configurable duration. Can be stacked.
 */

import React, { useState, useEffect, useCallback } from "react";

type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number; // ms, default 5000
  dismissible?: boolean;
  action?: { label: string; onClick: () => void };
}

interface NotificationToastProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
  position?: "top-right" | "bottom-right" | "top-left" | "bottom-left";
}

const typeStyles: Record<
  ToastType,
  { bg: string; border: string; icon: string; color: string }
> = {
  success: {
    bg: "rgba(16, 185, 129, 0.1)",
    border: "rgba(16, 185, 129, 0.3)",
    icon: "✓",
    color: "#10b981",
  },
  error: {
    bg: "rgba(239, 68, 68, 0.1)",
    border: "rgba(239, 68, 68, 0.3)",
    icon: "✕",
    color: "#ef4444",
  },
  warning: {
    bg: "rgba(245, 158, 11, 0.1)",
    border: "rgba(245, 158, 11, 0.3)",
    icon: "⚠",
    color: "#f59e0b",
  },
  info: {
    bg: "rgba(59, 130, 246, 0.1)",
    border: "rgba(59, 130, 246, 0.3)",
    icon: "ℹ",
    color: "#3b82f6",
  },
};

const positionStyles: Record<string, React.CSSProperties> = {
  "top-right": { top: "1rem", right: "1rem" },
  "bottom-right": { bottom: "1rem", right: "1rem" },
  "top-left": { top: "1rem", left: "1rem" },
  "bottom-left": { bottom: "1rem", left: "1rem" },
};

const SingleToast: React.FC<{
  toast: Toast;
  onDismiss: (id: string) => void;
}> = ({ toast, onDismiss }) => {
  const style = typeStyles[toast.type];
  const duration = toast.duration ?? 4000;

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => onDismiss(toast.id), duration);
      return () => clearTimeout(timer);
    }
  }, [toast.id, duration, onDismiss]);

  // Respect reduced-motion preference: skip slide animation
  const prefersReducedMotion =
    typeof window !== "undefined" &&
    (document.documentElement.classList.contains("reduce-motion") ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  return (
    <div
      role="alert"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "0.75rem",
        padding: "0.75rem 1rem",
        borderRadius: "8px",
        background: style.bg,
        border: `1px solid ${style.border}`,
        backdropFilter: "blur(8px)",
        minWidth: "280px",
        maxWidth: "400px",
        animation: prefersReducedMotion ? "none" : "slideIn 0.25s ease-out",
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
      }}
    >
      <span
        style={{
          color: style.color,
          fontWeight: 700,
          fontSize: "1rem",
          flexShrink: 0,
        }}
      >
        {style.icon}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            margin: 0,
            fontWeight: 600,
            fontSize: "0.85rem",
            color: "var(--text-primary)",
          }}
        >
          {toast.title}
        </p>
        {toast.message && (
          <p
            style={{
              margin: "0.25rem 0 0",
              fontSize: "0.75rem",
              color: "var(--text-muted)",
            }}
          >
            {toast.message}
          </p>
        )}
        {toast.action && (
          <button
            onClick={toast.action.onClick}
            style={{
              marginTop: "0.5rem",
              padding: "0.25rem 0.75rem",
              borderRadius: "4px",
              background: style.color,
              color: "#fff",
              border: "none",
              cursor: "pointer",
              fontSize: "0.75rem",
            }}
          >
            {toast.action.label}
          </button>
        )}
      </div>
      {toast.dismissible !== false && (
        <button
          onClick={() => onDismiss(toast.id)}
          style={{
            background: "none",
            border: "none",
            color: "var(--text-muted)",
            cursor: "pointer",
            padding: "0",
            fontSize: "1rem",
            lineHeight: 1,
          }}
        >
          ×
        </button>
      )}
    </div>
  );
};

const NotificationToast: React.FC<NotificationToastProps> = ({
  toasts,
  onDismiss,
  position = "top-right",
}) => {
  if (toasts.length === 0) return null;

  return (
    <div
      className="notification-toast-container"
      style={{
        position: "fixed",
        ...positionStyles[position],
        zIndex: 9999,
        display: "flex",
        flexDirection: position.startsWith("top") ? "column" : "column-reverse",
        gap: "0.5rem",
        pointerEvents: "none",
      }}
    >
      {toasts.map((toast) => (
        <div key={toast.id} style={{ pointerEvents: "auto" }}>
          <SingleToast toast={toast} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
};

export default NotificationToast;
