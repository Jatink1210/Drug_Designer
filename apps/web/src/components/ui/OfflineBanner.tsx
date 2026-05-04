/**
 * OfflineBanner — Full-screen overlay when network is unavailable (§66.1, §66.2)
 *
 * Uses `navigator.onLine` + `online`/`offline` events for connectivity detection.
 * Shows a degraded-mode banner when API failure rate exceeds threshold.
 */
import React, { useEffect, useState } from "react";

/** True offline: browser has no network at all. */
function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  return online;
}

export const OfflineBanner: React.FC = () => {
  const online = useOnlineStatus();

  if (online) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <div className="rounded-2xl bg-red-900/90 px-10 py-8 text-center shadow-2xl max-w-md">
        <svg
          className="mx-auto mb-4 h-12 w-12 text-red-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M18.364 5.636a9 9 0 010 12.728M5.636 18.364a9 9 0 010-12.728M12 9v4m0 4h.01"
          />
        </svg>
        <h2 className="text-xl font-bold text-white mb-2">You are offline</h2>
        <p className="text-red-200 text-sm">
          Drug Designer requires a network connection. Reconnect to continue.
        </p>
      </div>
    </div>
  );
};

/**
 * NetworkDegradedBanner — shows a dismissible warning banner when API
 * health checks are returning errors but the browser still has connectivity.
 */
export const NetworkDegradedBanner: React.FC<{ apiHealthy: boolean }> = ({
  apiHealthy,
}) => {
  const [dismissed, setDismissed] = useState(false);
  const online = useOnlineStatus();

  // Reset dismissed state when health recovers then degrades again
  useEffect(() => {
    if (apiHealthy) setDismissed(false);
  }, [apiHealthy]);

  if (!online || apiHealthy || dismissed) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-0 z-50 flex items-center justify-between gap-3 bg-amber-600/90 px-4 py-2 text-sm text-white shadow-md"
    >
      <span>
        ⚠ Network degraded — some features may be slower or unavailable.
      </span>
      <button
        onClick={() => setDismissed(true)}
        className="shrink-0 rounded px-2 py-0.5 text-xs font-medium hover:bg-amber-700/60"
        aria-label="Dismiss degraded network warning"
      >
        Dismiss
      </button>
    </div>
  );
};

export default OfflineBanner;
