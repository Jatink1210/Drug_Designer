/**
 * BackendDegradedIndicator — Shows a compact degraded status indicator
 * when specific backend services are unavailable.
 *
 * Fetches /api/v1/health and displays failed services inline.
 */
import { useState, useEffect } from "react";
import { AlertTriangle } from "lucide-react";

interface HealthResponse {
  status: "ok" | "degraded" | "error";
  services?: Record<string, { status: string; error?: string }>;
  failed_services?: string[] | null;
}

export default function BackendDegradedIndicator() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let mounted = true;

    const checkHealth = async () => {
      try {
        const res = await fetch("/api/v1/health", {
          signal: AbortSignal.timeout(5000),
          cache: "no-store",
        });
        if (res.ok) {
          const data = await res.json();
          if (mounted) setHealth(data);
        }
      } catch {
        // Silently ignore — the main BackendGate handles full outages
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30_000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // Reset dismissed when health recovers
  useEffect(() => {
    if (health?.status === "ok") setDismissed(false);
  }, [health?.status]);

  if (!health || health.status === "ok" || dismissed) return null;

  const failedServices = health.failed_services || [];
  if (failedServices.length === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 px-3 py-1.5 text-[10px] rounded-lg mb-3"
      style={{
        background: "rgba(245, 158, 11, 0.08)",
        border: "1px solid rgba(245, 158, 11, 0.2)",
        color: "#92400e",
      }}
    >
      <AlertTriangle size={12} className="shrink-0" />
      <span>
        Degraded: {failedServices.join(", ")} unavailable. Some features may be limited.
      </span>
      <button
        onClick={() => setDismissed(true)}
        className="ml-auto text-[9px] underline shrink-0"
      >
        Dismiss
      </button>
    </div>
  );
}
