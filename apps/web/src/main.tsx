import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// §5.3 / §O-5: Web-Vitals performance budget reporting + CLS monitoring
import('web-vitals')
  .then(({ onLCP, onINP, onCLS }) => {
    onLCP((metric: { value: number }) => { if (metric.value > 1200) console.warn(`[Perf] LCP budget exceeded: ${metric.value}ms`); });
    onINP((metric: { value: number }) => { if (metric.value > 200) console.warn(`[Perf] INP budget exceeded: ${metric.value}ms`); });
    onCLS((metric: { value: number; entries: PerformanceEntry[] }) => {
      if (metric.value > 0.1) {
        console.warn(`[Perf] CLS budget exceeded: ${metric.value.toFixed(4)}`);
        // Surface the offending entries to help diagnose the root cause
        if (metric.entries?.length) {
          metric.entries.forEach((entry: any) => {
            const shifted = entry.sources?.map((s: any) => s.node?.nodeName ?? "?").join(", ");
            console.warn(`  [CLS] shift=${entry.value?.toFixed(4)} elements=${shifted ?? "unknown"}`);
          });
        }
      }
    });
  })
  .catch(() => {});

// §O-5: Low-level PerformanceObserver for layout-shift — captures every individual
// shift event and reports if cumulative exceeds 0.05 in a 5 s window.
try {
  let _windowCLS = 0;
  let _windowStart = performance.now();
  const _clsObserver = new PerformanceObserver((list) => {
    for (const entry of list.getEntries() as any[]) {
      if (!entry.hadRecentInput) {
        const now = performance.now();
        if (now - _windowStart > 5000) {
          _windowCLS = 0;
          _windowStart = now;
        }
        _windowCLS += entry.value ?? 0;
        if (_windowCLS > 0.05) {
          console.warn(`[CLS-Observer] 5s window CLS=${_windowCLS.toFixed(4)} (threshold 0.05)`);
        }
      }
    }
  });
  _clsObserver.observe({ type: "layout-shift", buffered: true });
} catch {
  // PerformanceObserver not available in test/SSR environment — skip silently
}
