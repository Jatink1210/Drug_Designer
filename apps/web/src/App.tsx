/** App.tsx — Full app shell with routing, inspector, command palette, job bar, and health gate. */

import { useState, useEffect, useCallback, useRef, lazy, Suspense, Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import AppBar from "@/components/shell/AppBar";
import LeftRail from "@/components/shell/LeftRail";
import InspectorDrawer from "@/components/shell/InspectorDrawer";
import HealthStrip from "@/components/shell/HealthStrip";
import PageConfidenceBanner from "@/components/shell/PageConfidenceBanner";
import { OfflineBanner, NetworkDegradedBanner } from "@/components/ui/OfflineBanner";
import CommandPalette from "@/components/ui/CommandPalette";
import NotificationToast from "@/components/ui/NotificationToast";
import RepairScreen from "@/pages/RepairScreen";
import { cockpitSourceHealthAPI, healthAPI, ensureApiBase } from "@/lib/api";
import { AuthProvider, useAuth } from "@/components/AuthProvider";
import { LoginPage } from "@/pages/LoginPage";
import { PageConfidenceProvider } from "@/lib/PageConfidenceContext";
import { ToastProvider, useToast } from "@/lib/ToastContext";
import { InspectorProvider, useInspector } from "@/lib/InspectorContext";
import { ThemeProvider } from "@/contexts/ThemeContext";

const SearchPage = lazy(() => import("@/pages/SearchPage"));
const WorkspacePage = lazy(() => import("@/pages/WorkspacePage"));
const JobCockpit = lazy(() => import("@/pages/JobCockpit"));
const EvidencePage = lazy(() => import("@/pages/EvidencePage"));
const StructurePage = lazy(() => import("@/pages/StructurePage"));
const DesignPage = lazy(() => import("@/pages/DesignPage"));
const PathwaysPage = lazy(() => import("@/pages/PathwaysPage"));
const AnalysisPage = lazy(() => import("@/pages/AnalysisPage"));
const KGPage = lazy(() => import("@/pages/KGPage"));
const PicoPage = lazy(() => import("@/pages/PICOVerification"));
const TranslationalPage = lazy(() => import("@/pages/TranslationalResearch"));
const CatalogPage = lazy(() => import("@/pages/CatalogPage"));
const DataPage = lazy(() => import("@/pages/DataPage"));
const ReportPage = lazy(() => import("@/pages/ReportPage"));
const AboutPage = lazy(() => import("@/pages/AboutPage"));
const MediaPage = lazy(() => import("@/pages/MediaPage"));
const LogsPage = lazy(() => import("@/pages/LogsPage"));
const SetupWizard = lazy(() => import("@/pages/SetupWizard"));
const SettingsPage = lazy(() => import("@/pages/SettingsPage"));
const RunsPage = lazy(() => import("@/pages/RunsPage"));
const SynthArenaPage = lazy(() => import("@/pages/SynthArenaPage"));
const ModelsPage = lazy(() => import("@/pages/ModelsPage"));
const DiseaseIntelligence = lazy(() => import("@/pages/DiseaseIntelligence"));
const EntityIntelligencePage = lazy(() => import("@/pages/EntityIntelligence"));
const SourceExplorer = lazy(() => import("@/pages/SourceExplorer"));
const Contradictions = lazy(() => import("@/pages/Contradictions"));
const SavedEvidence = lazy(() => import("@/pages/SavedEvidence"));
const UniProtMappingResults = lazy(
  () => import("@/pages/UniProtMappingResults"),
);
const MechanismMaps = lazy(() => import("@/pages/MechanismMaps"));
const MoleculeCandidateReview = lazy(
  () => import("@/pages/MoleculeCandidateReview"),
);
const AdmetPanels = lazy(() => import("@/pages/AdmetPanels"));
const StructureReports = lazy(() => import("@/pages/StructureReports"));
const DossiersPage = lazy(() => import("@/pages/DossiersPage"));
const RuntimeCenter = lazy(() => import("@/pages/RuntimeCenter"));
const HardwareStatus = lazy(() => import("@/pages/HardwareStatus"));
const ProjectsPage = lazy(() => import("@/pages/ProjectsPage"));
const HistoricalQueries = lazy(() => import("@/pages/HistoricalQueries"));
const ContextBundles = lazy(() => import("@/pages/ContextBundles"));
const ExportCenterPage = lazy(() => import("@/pages/ExportCenterPage"));
const LocalAgentPage = lazy(() => import("@/pages/LocalAgentPage"));
const LabsPage = lazy(() => import("@/pages/LabsPage"));
const ScenarioArenaPage = lazy(() => import("@/pages/ScenarioArenaPage"));
const TranslationPage = lazy(() => import("@/pages/TranslationPage"));
const MemoryPage = lazy(() => import("@/pages/MemoryPage"));
const ProjectDetailPage = lazy(() => import("@/pages/ProjectDetailPage"));
const RunDetailPage = lazy(() => import("@/pages/RunDetailPage"));
const RetrosynthesisPage = lazy(() => import("@/pages/RetrosynthesisPage"));
const VaccineLabPage = lazy(() => import("@/pages/VaccineLabPage"));
const PocketLabPage = lazy(() => import("@/pages/PocketLabPage"));
const MoleculeGenerationLabPage = lazy(() => import("@/pages/MoleculeGenerationLabPage"));
const MetabolicEngineeringLabPage = lazy(() => import("@/pages/MetabolicEngineeringLabPage"));
const PharmacogenomicsLabPage = lazy(() => import("@/pages/PharmacogenomicsLabPage"));
const OperationsPage = lazy(() => import("@/pages/OperationsPage"));
const ConsensusPage = lazy(() => import("@/pages/ConsensusPage"));
const AdminAuditPage = lazy(() => import("@/pages/AdminAuditPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
      throwOnError: false,
    },
    mutations: {
      throwOnError: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
        <InspectorProvider>
        <ThemeProvider>
        <BrowserRouter>
          <ErrorBoundary>
            <BackendGate>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route
                  path="*"
                  element={
                    <ProtectedRoute>
                      <AppShell />
                    </ProtectedRoute>
                  }
                />
              </Routes>
            </BackendGate>
          </ErrorBoundary>
        </BrowserRouter>
        </ThemeProvider>
        </InspectorProvider>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// ErrorBoundary — catches unhandled React errors (§115)
// ---------------------------------------------------------------------------

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen w-screen flex items-center justify-center" style={{ background: "var(--bg-app)" }}>
          <div className="text-center max-w-md px-6">
            <div className="text-4xl font-bold text-red-500 mb-2">Error</div>
            <p className="text-sm text-[var(--text-muted)] mb-4">
              {this.state.error?.message || "An unexpected error occurred."}
            </p>
            <button
              onClick={() => { this.setState({ hasError: false, error: null }); window.location.href = "/workspace"; }}
              className="text-xs font-medium px-4 py-2 rounded-lg text-white"
              style={{ background: "var(--accent)" }}
            >
              Return to Workspace
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <PageLoader />;
  if (!isAuthenticated && (import.meta as any).env?.VITE_AUTH_ENABLED === "true")
    return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function LegacyEntityRedirect({ mode }: { mode: string }) {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  params.set("mode", mode);
  return <Navigate to={`/entity-intelligence?${params.toString()}`} replace />;
}

function LegacyGraphRedirect({ mode }: { mode: string }) {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  params.set("mode", mode);
  return <Navigate to={`/graph?${params.toString()}`} replace />;
}

/** DeprecatedRouteRedirect — redirects to /workspace with a toast notification */
function DeprecatedRouteRedirect({ label }: { label: string }) {
  const { addToast } = useToast();
  useEffect(() => {
    addToast({
      type: "info",
      title: "Page Moved",
      message: `${label} has moved to Cockpit`,
      duration: 5000,
    });
  }, [label, addToast]);
  return <Navigate to="/workspace" replace />;
}

// ---------------------------------------------------------------------------
// BackendGate — blocks the entire app until the backend is healthy
// ---------------------------------------------------------------------------

/**
 * Checks backend health via Tauri IPC (desktop) or HTTP (web).
 * If the backend is not ready, shows RepairScreen instead of children.
 */
function BackendGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState("starting");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  // Track consecutive failures — only show RepairScreen after 3+ in a row.
  // This prevents transient timeouts (e.g. during a long search request
  // saturating browser connection limits) from flashing the error screen.
  const failCountRef = useRef(0);
  const wasEverReady = useRef(false);

  const checkHealth = useCallback(async () => {
    setChecking(true);

    const markHealthy = (s: string, e: string | null) => {
      failCountRef.current = 0;
      wasEverReady.current = true;
      setReady(true);
      setStatus(s);
      setError(e);
    };

    const markUnhealthy = (s: string, e: string) => {
      failCountRef.current += 1;
      // First-time startup: fail immediately.  After app was healthy, require
      // 3 consecutive failures so a single timeout during heavy API work
      // doesn't flash the full-page error overlay.
      const threshold = wasEverReady.current ? 3 : 1;
      if (failCountRef.current >= threshold) {
        setReady(false);
        setStatus(s);
        setError(e);
      }
      // else: keep previous ready state — transient failure, ignore it
    };

    try {
      // Try Tauri IPC first (desktop mode)
      if (
        typeof window !== "undefined" &&
        (window as any).__TAURI__?.core?.invoke
      ) {
        const invoke = (window as any).__TAURI__.core.invoke;
        const backendReady: boolean = await invoke("get_backend_ready");
        const backendStatus: string = await invoke("get_backend_status");
        const startupError: string | null = await invoke("get_startup_error");

        if (backendReady) {
          markHealthy(backendStatus, startupError ?? null);
        } else {
          markUnhealthy(backendStatus, startupError ?? "Backend not ready");
        }
      } else {
        // Web mode: check HTTP health endpoint directly
        // Use /api/health (not /api/v1/health) for reliable Vite proxy forwarding
        try {
          const res = await fetch("/api/health", {
            signal: AbortSignal.timeout(8000),
            cache: "no-store",
          });
          const ct = res.headers.get("content-type") || "";
          if (res.ok && ct.includes("application/json")) {
            const data = await res.json();
            if (data.status === "ok" || data.status === "degraded") {
              markHealthy(data.status === "ok" ? "ready" : "unhealthy",
                data.issues ? data.issues.join("; ") : null);
            } else {
              markUnhealthy("unhealthy", `Health status: ${data.status}`);
            }
          } else {
            markUnhealthy("unhealthy", `Health endpoint returned HTTP ${res.status}`);
          }
        } catch {
          markUnhealthy("failed_to_start",
            "Cannot reach the API server. Ensure the backend is running.");
        }
      }
    } catch {
      // If Tauri invoke fails, try HTTP fallback
      try {
        const res = await fetch("/api/health", {
          signal: AbortSignal.timeout(8000),
          cache: "no-store",
        });
        const ct = res.headers.get("content-type") || "";
        if (res.ok && ct.includes("application/json")) {
          markHealthy("ready", null);
        } else {
          throw new Error(`HTTP ${res.status}`);
        }
      } catch {
        markUnhealthy("failed_to_start", "Cannot reach the API server.");
      }
    } finally {
      setChecking(false);
    }
  }, []);

  // Initial check + periodic polling (8s interval — gives long requests headroom)
  useEffect(() => {
    checkHealth();
    const id = setInterval(checkHealth, 8_000);
    return () => clearInterval(id);
  }, [checkHealth]);

  const handleRetry = useCallback(async () => {
    // In Tauri mode, invoke the retry command
    if (
      typeof window !== "undefined" &&
      (window as any).__TAURI__?.core?.invoke
    ) {
      try {
        await (window as any).__TAURI__.core.invoke("retry_backend_start");
      } catch {
        // Ignore invoke errors
      }
    }
    // Re-check health after a brief delay
    setTimeout(checkHealth, 3_000);
  }, [checkHealth]);

  // Show repair screen if not ready (and not still doing initial check)
  if (!ready && !checking) {
    return <RepairScreen status={status} error={error} onRetry={handleRetry} />;
  }

  // While still checking on first load, show a loading spinner
  if (!ready && checking) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-[var(--bg-app)]">
        <div className="flex flex-col items-center">
          <div className="w-8 h-8 border border-[var(--border)] border-t-[var(--accent)] rounded-full animate-spin mb-4" />
          <p className="text-xs uppercase tracking-widest font-bold text-[var(--accent)]">
            Initializing Engine
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

// ---------------------------------------------------------------------------
// AppShell — main layout (only rendered when backend is healthy)
// ---------------------------------------------------------------------------

function AppShell() {
  const { entity: inspectorEntity, openInspector, closeInspector } = useInspector();
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const [setupRequired, setSetupRequired] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // ── Health strip state (§114) ──
  const [healthData, setHealthData] = useState({
    runtimeMode: "hosted" as "hosted" | "local" | "auto",
    activeModel: "",
    sourcesHealthy: 0,
    sourcesDegraded: 0,
    sourcesDown: 0,
    activeRuns: 0,
    isConnected: false,
    degradedWarning: undefined as string | undefined,
    projectName: undefined as string | undefined,
    lastRunAt: undefined as string | undefined,
  });

  // ── Notification toast (§114) — via global context ──
  const { toasts, addToast, dismissToast } = useToast();
  const prevHealthRef = useRef({ isConnected: false, sourcesDegraded: 0 });

  // Poll health API to feed HealthStrip and detect toast-worthy events
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const [h, sourceHealth] = await Promise.all([
          healthAPI(),
          cockpitSourceHealthAPI().catch(() => null),
        ]);
        if (!mounted) return;
        const sourceEntries = Array.isArray((sourceHealth as { sources?: Array<{ status?: string | null }> } | null)?.sources)
          ? ((sourceHealth as { sources: Array<{ status?: string | null }> }).sources)
          : [];

        const derivedSourceCounts = sourceEntries.reduce(
          (counts, entry) => {
            const status = (entry.status || "").toLowerCase();
            if (["healthy", "ok", "pass", "active"].includes(status)) {
              counts.healthy += 1;
            } else if (["degraded", "warning"].includes(status)) {
              counts.degraded += 1;
            } else {
              counts.down += 1;
            }
            return counts;
          },
          { healthy: 0, degraded: 0, down: 0 },
        );

        const derivedTotal = typeof (sourceHealth as { count?: number } | null)?.count === "number"
          ? (sourceHealth as { count: number }).count
          : sourceEntries.length;

        const healthy = typeof h.connectors_active === "number" ? h.connectors_active : derivedSourceCounts.healthy;
        const degraded = typeof h.connectors_degraded === "number" ? h.connectors_degraded : derivedSourceCounts.degraded;
        const total = typeof h.connectors_total === "number"
          ? h.connectors_total
          : derivedTotal;
        setHealthData({
          runtimeMode: (h.runtime_mode as any) ?? "hosted",
          activeModel: h.active_model ?? "",
          sourcesHealthy: healthy,
          sourcesDegraded: degraded,
          sourcesDown: Math.max(0, total - healthy - degraded),
          activeRuns: h.active_runs ?? 0,
          isConnected: h.status === "ok" || h.status === "degraded",
          degradedWarning: degraded > 0 ? `${degraded} source${degraded > 1 ? "s" : ""} degraded` : undefined,
          projectName: h.active_project_name ?? undefined,
          lastRunAt: h.last_run_at ?? undefined,
        });
        // §114 Toast producers: notify on health transitions
        const prev = prevHealthRef.current;
        const nowConnected = h.status === "ok" || h.status === "degraded";
        if (prev.isConnected && !nowConnected) {
          addToast({ type: "error", title: "Connection Lost", message: "API server unreachable. Retrying…", duration: 8000 });
        } else if (!prev.isConnected && nowConnected && prev.isConnected !== undefined) {
          addToast({ type: "success", title: "Reconnected", message: "API connection restored.", duration: 4000 });
        }
        if (degraded > 0 && degraded !== prev.sourcesDegraded) {
          addToast({ type: "warning", title: "Sources Degraded", message: `${degraded} data source${degraded > 1 ? "s" : ""} running in degraded mode.`, duration: 6000 });
        }
        prevHealthRef.current = { isConnected: nowConnected, sourcesDegraded: degraded };
      } catch {
        if (!mounted) return;
        setHealthData((prev) => ({ ...prev, isConnected: false }));
      }
    };
    poll();
    const id = setInterval(poll, 15_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  // Global ⌘K handler
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // ── Cross-tab state sync via localStorage ──
  // When setup completes in any tab, all tabs get notified immediately.
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === "dss_setup_complete" && e.newValue === "true") {
        setSetupRequired(false);
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);

  // Check wizard status on boot — localStorage first, then API
  useEffect(() => {
    if (window.location.pathname === "/setup") return;
    // Fast path: localStorage cache
    if (localStorage.getItem("dss_setup_complete") === "true") {
      setSetupRequired(false);
      return;
    }
    ensureApiBase().then((base) =>
      fetch(`${base}/settings`, { cache: "no-store" })
        .then((r) => r.json())
        .then((envelope) => {
          const data = envelope?.data ?? envelope;
          if (data?.setup_complete) {
            localStorage.setItem("dss_setup_complete", "true");
            setSetupRequired(false);
          } else {
            setSetupRequired(true);
          }
        })
        .catch(() => {}),
    );
  }, []);

  const onEntityClick = useCallback((entity: Record<string, unknown>) => {
    openInspector(entity);
  }, [openInspector]);

  if (setupRequired && window.location.pathname !== "/setup") {
    return <Navigate to="/setup" replace />;
  }

  return (
    <PageConfidenceProvider>
    <div
      className="h-screen w-screen flex flex-col overflow-hidden"
      style={{ background: "var(--bg-app)" }}
    >
      {/* §65 WCAG AA: Skip-to-content link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:rounded-lg focus:text-sm focus:font-medium focus:text-white"
        style={{ background: "var(--accent)" }}
      >
        Skip to main content
      </a>

      <AppBar onCommandPalette={() => setCmdPaletteOpen(true)} onMenuToggle={() => setSidebarOpen(v => !v)} />

      {/* §114 HealthStrip — always visible runtime/source status */}
      <HealthStrip {...healthData} />

      {/* §66.1 Offline overlay — navigator.onLine */}
      <OfflineBanner />
      {/* §66.2 Degraded banner — API health failures */}
      <NetworkDegradedBanner apiHealthy={healthData.isConnected} />

      <PageConfidenceBanner />

      <div className="flex-1 flex overflow-hidden">
        <LeftRail isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        {/* Page content */}
        <main id="main-content" className="flex-1 flex overflow-hidden" role="main" aria-label="Main content">
          <ErrorBoundary>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Navigate to="/workspace" replace />} />
              <Route path="/home" element={<WorkspacePage />} />
              <Route path="/workspace" element={<WorkspacePage />} />
              <Route path="/cockpit" element={<WorkspacePage />} />
              <Route path="/runs" element={<RunsPage />} />
              <Route path="/runs/:runId" element={<RunDetailPage />} />
              <Route path="/jobs/:id" element={<JobCockpit />} />
              <Route
                path="/search"
                element={<SearchPage onEntityClick={onEntityClick} />}
              />

              {/* Phase 0 canonical product routes */}
              <Route
                path="/entity-intelligence"
                element={<EntityIntelligencePage />}
              />
              <Route
                path="/clinical-design"
                element={<TranslationalPage />}
              />
              <Route
                path="/contradiction-similarity"
                element={<Contradictions />}
              />
              <Route
                path="/pico-verification"
                element={<PicoPage />}
              />

              {/* §77 Evidence routes */}
              <Route path="/evidence" element={<EvidencePage />} />
              <Route
                path="/evidence/search"
                element={<SearchPage onEntityClick={onEntityClick} />}
              />
              <Route path="/evidence/workspace" element={<EvidencePage />} />
              <Route path="/evidence/workspace/:bundleId" element={<ContextBundles />} />
              <Route path="/evidence/sources" element={<SourceExplorer />} />
              <Route path="/evidence/contradictions" element={<Contradictions />} />

              {/* §77 Intelligence routes — merged Disease Workbench */}
              <Route path="/disease" element={<LegacyEntityRedirect mode="disease" />} />
              <Route path="/disease/:runId" element={<LegacyEntityRedirect mode="disease" />} />
              <Route path="/targets" element={<LegacyEntityRedirect mode="targets" />} />
              <Route path="/targets/:runId" element={<LegacyEntityRedirect mode="targets" />} />
              <Route path="/mapping/uniprot/:queryId" element={<LegacyEntityRedirect mode="structure" />} />
              <Route path="/mapping/uniprot" element={<LegacyEntityRedirect mode="structure" />} />
              <Route path="/ppi" element={<LegacyEntityRedirect mode="ppi" />} />

              {/* Compat aliases for old paths */}
              <Route path="/sources" element={<SourceExplorer />} />
              <Route path="/contradictions" element={<Contradictions />} />
              <Route path="/saved-evidence" element={<SavedEvidence />} />
              <Route path="/gene-explorer" element={<LegacyEntityRedirect mode="disease" />} />
              <Route path="/uniprot-mapping" element={<LegacyEntityRedirect mode="structure" />} />
              <Route path="/interaction-maps" element={<LegacyGraphRedirect mode="ppi" />} />
              <Route path="/mechanism-maps" element={<MechanismMaps />} />

              {/* §77 Graph/Pathways */}
              <Route path="/graph" element={<KGPage />} />
              <Route path="/graph/:entityId" element={<KGPage />} />
              <Route path="/kg" element={<KGPage />} />
              <Route path="/pathways" element={<PathwaysPage />} />
              <Route path="/pathways/:pathwayId" element={<PathwaysPage />} />

              {/* §77 Structure/Design */}
              <Route path="/structure" element={<StructurePage />} />
              <Route path="/structure/:targetId" element={<StructurePage />} />
              <Route path="/design" element={<DesignPage />} />
              <Route path="/design/candidates/:candidateId" element={<MoleculeCandidateReview />} />
              <Route path="/molecule-review" element={<MoleculeCandidateReview />} />
              <Route path="/admet-panels" element={<AdmetPanels />} />
              <Route path="/structure-reports" element={<StructureReports />} />

              {/* §77 Translational — merged Clinical Stage + Translation */}
              <Route path="/translation" element={<TranslationalPage />} />
              <Route path="/translational" element={<TranslationalPage />} />

              {/* §77 Platform/Models */}
              <Route path="/models" element={<ModelsPage />} />
              <Route path="/runtime" element={<RuntimeCenter />} />
              <Route path="/runtime/local-agent" element={<LocalAgentPage />} />
              <Route path="/runtime/hardware" element={<HardwareStatus />} />
              <Route path="/runtime-center" element={<RuntimeCenter />} />
              <Route path="/hardware-status" element={<HardwareStatus />} />
              <Route path="/local-agent" element={<LocalAgentPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/settings/sources" element={<SettingsPage />} />
              <Route path="/settings/security" element={<SettingsPage />} />
              <Route path="/settings/storage" element={<SettingsPage />} />
              <Route path="/settings/diagnostics" element={<SettingsPage />} />
              <Route path="/settings/logs" element={<SettingsPage />} />

              {/* §77 Memory/Outputs — Deprecated pages redirect to Cockpit (Task 24) */}
              <Route path="/dossiers" element={<DossiersPage />} />
              <Route path="/dossiers/:dossierId" element={<DossiersPage />} />
              <Route path="/reports" element={<DeprecatedRouteRedirect label="Reports" />} />
              <Route path="/reports/:reportId" element={<DeprecatedRouteRedirect label="Reports" />} />
              <Route path="/logs" element={<LogsPage />} />
              <Route path="/media" element={<MediaPage />} />
              <Route path="/exports" element={<DeprecatedRouteRedirect label="Export Center" />} />
              <Route path="/export" element={<DeprecatedRouteRedirect label="Export Center" />} />
              <Route path="/memory" element={<DeprecatedRouteRedirect label="Memory" />} />
              <Route path="/memory/:objectId" element={<DeprecatedRouteRedirect label="Memory" />} />
              <Route path="/notes" element={<DeprecatedRouteRedirect label="Notes" />} />
              <Route path="/notes/:objectId" element={<DeprecatedRouteRedirect label="Notes" />} />

              {/* §77 Projects — Operations redirects to Cockpit (Task 24) */}
              <Route path="/projects" element={<ProjectsPage />} />
              <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
              <Route path="/operations" element={<DeprecatedRouteRedirect label="Operations" />} />
              <Route path="/admin/audit" element={<AdminAuditPage />} />
              <Route path="/consensus" element={<ConsensusPage />} />

              {/* §77 SynthArena/Labs/Scenario */}
              <Route path="/syntharena" element={<SynthArenaPage />} />
              <Route path="/syntharena/:sessionId" element={<SynthArenaPage />} />
              <Route path="/scenario-arena" element={<ScenarioArenaPage />} />
              <Route path="/labs" element={<LabsPage />} />
              <Route path="/labs/pocket" element={<PocketLabPage />} />
              <Route path="/labs/molecule-generation" element={<MoleculeGenerationLabPage />} />
              <Route path="/labs/admet" element={<AdmetPanels />} />
              <Route path="/labs/retrosynthesis" element={<RetrosynthesisPage />} />
              <Route path="/labs/vaccine" element={<VaccineLabPage />} />
              <Route path="/labs/metabolic-engineering" element={<MetabolicEngineeringLabPage />} />
              <Route path="/labs/pharmacogenomics" element={<PharmacogenomicsLabPage />} />
              <Route path="/labs/:module" element={<LabsPage />} />

              {/* Utility pages */}
              <Route path="/analysis" element={<AnalysisPage />} />
              <Route path="/pico" element={<PicoPage />} />
              <Route path="/catalog" element={<CatalogPage />} />
              <Route path="/data" element={<DataPage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/setup" element={<SetupWizard />} />
              <Route path="/historical-queries" element={<HistoricalQueries />} />
              <Route path="/context-bundles" element={<ContextBundles />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
          </ErrorBoundary>

          {/* Inspector drawer — accessible from any page via useInspector() */}
          {inspectorEntity && (
            <InspectorDrawer
              entity={inspectorEntity}
              onClose={closeInspector}
            />
          )}
        </main>
      </div>

      {/* §114 NotificationToast — global transient alerts */}
      <NotificationToast toasts={toasts} onDismiss={dismissToast} position="bottom-right" />

      {/* Command palette overlay */}
      <CommandPalette
        open={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
      />
    </div>
    </PageConfidenceProvider>
  );
}

/** PageLoader — minimal centered spinner shown while lazy pages load. */
function PageLoader() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

/** NotFound — 404 catch-all for unknown routes. */
function NotFound() {
  return (
    <div
      className="flex-1 flex items-center justify-center"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="text-center">
        <div className="text-4xl font-bold text-[var(--text-muted)] mb-2">
          404
        </div>
        <p className="text-sm text-[var(--text-muted)] mb-4">Page not found</p>
        <a
          href="/workspace"
          className="text-xs font-medium px-4 py-2 rounded-lg text-white"
          style={{ background: "var(--accent)" }}
        >
          Go to Workspace
        </a>
      </div>
    </div>
  );
}
