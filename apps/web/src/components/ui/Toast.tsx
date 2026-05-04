/**
 * Toast — Unified toast notification component (§114 + Platform Polish).
 *
 * Re-exports the global ToastProvider/useToast from ToastContext and provides
 * standalone <Toast> and <ToastContainer> components for direct rendering.
 *
 * Supports: success, error, info, warning variants.
 * Auto-dismisses after configurable duration (default 4000ms).
 * Positioned bottom-right with stacking.
 * Respects reduced-motion preference (no slide animation when enabled).
 */

import React, { useState, useEffect, useCallback, createContext, useContext, type ReactNode } from "react";

/* ─── Re-export global context hook ─────────────────────── */
export { useToast } from "@/lib/ToastContext";

/* ─── Types ─────────────────────────────────────────────── */
export type ToastVariant = "success" | "error" | "warning" | "info";

export interface ToastProps {
  id?: string;
  message?: string;
  title?: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
  closable?: boolean;
  onClose?: () => void;
  action?: ReactNode;
  icon?: ReactNode | null;
  showProgress?: boolean;
  isLoading?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

/* ─── Variant styles ────────────────────────────────────── */
const variantConfig: Record<ToastVariant, { bg: string; border: string; iconChar: string; color: string }> = {
  success: { bg: "rgba(16,185,129,0.1)", border: "rgba(16,185,129,0.3)", iconChar: "✓", color: "#10b981" },
  error:   { bg: "rgba(239,68,68,0.1)",  border: "rgba(239,68,68,0.3)",  iconChar: "✕", color: "#ef4444" },
  warning: { bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.3)", iconChar: "⚠", color: "#f59e0b" },
  info:    { bg: "rgba(59,130,246,0.1)", border: "rgba(59,130,246,0.3)", iconChar: "ℹ", color: "#3b82f6" },
};

/* ─── Helpers ───────────────────────────────────────────── */
function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return (
    document.documentElement.classList.contains("reduce-motion") ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/* ─── Single Toast Component ────────────────────────────── */
export const Toast: React.FC<ToastProps> = ({
  message,
  title,
  description,
  variant = "info",
  duration = 4000,
  closable = true,
  onClose,
  action,
  icon,
  showProgress = false,
  isLoading = false,
  className = "",
  style: customStyle,
}) => {
  const [visible, setVisible] = useState(true);
  const [animatingOut, setAnimatingOut] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [remaining, setRemaining] = useState(duration);
  const [startTime, setStartTime] = useState(Date.now());

  const cfg = variantConfig[variant];

  const handleClose = useCallback(() => {
    setAnimatingOut(true);
    // Allow animation to play, then remove
    setTimeout(() => {
      setVisible(false);
      onClose?.();
    }, 150);
  }, [onClose]);

  // Auto-dismiss timer with pause-on-hover
  useEffect(() => {
    if (duration <= 0 || hovered) return;
    setStartTime(Date.now());
    const timer = setTimeout(handleClose, remaining);
    return () => clearTimeout(timer);
  }, [duration, hovered, remaining, handleClose]);

  // Track remaining time when hover starts
  useEffect(() => {
    if (hovered && duration > 0) {
      const elapsed = Date.now() - startTime;
      setRemaining((prev) => Math.max(0, prev - elapsed));
    }
  }, [hovered, duration, startTime]);

  if (!visible) return null;

  const reduced = prefersReducedMotion();

  const renderIcon = () => {
    if (icon === null) return null;
    if (isLoading) {
      return (
        <span data-testid="toast-spinner" style={{ color: cfg.color, fontWeight: 700, fontSize: "1rem", flexShrink: 0 }}>
          ⟳
        </span>
      );
    }
    if (icon !== undefined) return icon;
    return (
      <span
        data-testid="toast-icon"
        className={`icon-${variant}`}
        style={{ color: cfg.color, fontWeight: 700, fontSize: "1rem", flexShrink: 0 }}
      >
        {cfg.iconChar}
      </span>
    );
  };

  return (
    <div
      role="alert"
      aria-live={variant === "error" ? "assertive" : "polite"}
      className={`variant-${variant} ${animatingOut ? "animate-out" : "animate-in"} ${className}`}
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "0.75rem",
        padding: "0.75rem 1rem",
        borderRadius: "8px",
        background: cfg.bg,
        border: `1px solid ${cfg.border}`,
        backdropFilter: "blur(8px)",
        minWidth: "280px",
        maxWidth: "400px",
        animation: reduced ? "none" : undefined,
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
        position: "relative",
        overflow: "hidden",
        ...customStyle,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {renderIcon()}
      <div style={{ flex: 1, minWidth: 0 }}>
        {title && (
          <p role="heading" aria-level={3} style={{ margin: 0, fontWeight: 600, fontSize: "0.85rem", color: "var(--text-primary, #1a1a1a)" }}>
            {title}
          </p>
        )}
        {(description || message) && (
          <p style={{ margin: title ? "0.25rem 0 0" : 0, fontSize: "0.8rem", color: title ? "var(--text-muted, #888)" : "var(--text-primary, #1a1a1a)", fontWeight: title ? 400 : 600 }}>
            {description || message}
          </p>
        )}
        {action && <div style={{ marginTop: "0.5rem" }}>{action}</div>}
      </div>
      {closable && (
        <button
          onClick={handleClose}
          aria-label="Close notification"
          style={{ background: "none", border: "none", color: "var(--text-muted, #888)", cursor: "pointer", padding: 0, fontSize: "1rem", lineHeight: 1 }}
        >
          ×
        </button>
      )}
      {showProgress && duration > 0 && (
        <div
          data-testid="toast-progress"
          className="animate"
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            height: "2px",
            background: cfg.color,
            animation: reduced ? "none" : `toastProgress ${duration}ms linear forwards`,
            width: "100%",
          }}
        />
      )}
    </div>
  );
};

/* ─── Toast Container ───────────────────────────────────── */
export type ToastPosition = "top-right" | "top-left" | "bottom-right" | "bottom-left" | "top-center" | "bottom-center";

interface ToastContainerProps {
  position?: ToastPosition;
  maxToasts?: number;
  children?: ReactNode;
}

const positionMap: Record<ToastPosition, React.CSSProperties> = {
  "top-right":      { top: "1rem", right: "1rem" },
  "top-left":       { top: "1rem", left: "1rem" },
  "bottom-right":   { bottom: "1rem", right: "1rem" },
  "bottom-left":    { bottom: "1rem", left: "1rem" },
  "top-center":     { top: "1rem", left: "50%", transform: "translateX(-50%)" },
  "bottom-center":  { bottom: "1rem", left: "50%", transform: "translateX(-50%)" },
};

export const ToastContainer: React.FC<ToastContainerProps> = ({
  position = "bottom-right",
  maxToasts,
  children,
}) => {
  const childArray = React.Children.toArray(children);

  return (
    <div
      data-testid="toast-container"
      className={`position-${position}`}
      style={{
        position: "fixed",
        ...positionMap[position],
        zIndex: 9999,
        display: "flex",
        flexDirection: position.startsWith("top") ? "column" : "column-reverse",
        gap: "0.5rem",
        pointerEvents: "none",
      }}
    >
      {childArray.map((child, i) => (
        <div
          key={i}
          style={{
            pointerEvents: "auto",
            visibility: maxToasts && i >= maxToasts ? "hidden" : "visible",
          }}
        >
          {child}
        </div>
      ))}
    </div>
  );
};

export default Toast;
