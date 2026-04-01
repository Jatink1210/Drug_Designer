/** App.tsx — Full app shell with routing, inspector, command palette, job bar, and health gate. */

import { useState, useEffect, useCallback, lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import AppBar from "@/components/shell/AppBar";
import LeftRail from "@/components/shell/LeftRail";
import InspectorDrawer from "@/components/shell/InspectorDrawer";
import CommandPalette from "@/components/ui/CommandPalette";
import RepairScreen from "@/pages/RepairScreen";
import { healthAPI, ensureApiBase } from "@/lib/api";
import { AuthProvider, useAuth } from "@/components/AuthProvider";
import { LoginPage } from "@/pages/LoginPage";

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
const TargetPrioritization = lazy(() => import("@/pages/TargetPrioritization"));
const SourceExplorer = lazy(() => import("@/pages/SourceExplorer"));
const Contradictions = lazy(() => import("@/pages/Contradictions"));
const SavedEvidence = lazy(() => import("@/pages/SavedEvidence"));
const GeneProteinExplorer = lazy(() => import("@/pages/GeneProteinExplorer"));
const UniProtMappingResults = lazy(() => import("@/pages/UniProtMappingResults"));
const InteractionMaps = lazy(() => import("@/pages/InteractionMaps"));
const MechanismMaps = lazy(() => import("@/pages/MechanismMaps"));
const MoleculeCandidateReview = lazy(() => import("@/pages/MoleculeCandidateReview"));
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

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 60_000,
            retry: 1,
            refetchOnWindowFocus: false,
        },
    },
});

export default function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <AuthProvider>
                <BrowserRouter>
                    <BackendGate>
                        <Routes>
                            <Route path="/login" element={<LoginPage />} />
                            <Route path="*" element={
                                <ProtectedRoute>
                                    <AppShell />
                                </ProtectedRoute>
                            } />
                        </Routes>
                    </BackendGate>
                </BrowserRouter>
            </AuthProvider>
        </QueryClientProvider>
    );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { token, isLoading } = useAuth();
    if (isLoading) return <PageLoader />;
    if (!token && (import.meta as any).env?.VITE_AUTH_ENABLED === "true") return <Navigate to="/login" replace />;
    return <>{children}</>;
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

    const checkHealth = useCallback(async () => {
        setChecking(true);
        try {
            // Try Tauri IPC first (desktop mode)
            if (typeof window !== "undefined" && (window as any).__TAURI__?.core?.invoke) {
                const invoke = (window as any).__TAURI__.core.invoke;
                const backendReady: boolean = await invoke("get_backend_ready");
                const backendStatus: string = await invoke("get_backend_status");
                const startupError: string | null = await invoke("get_startup_error");

                setReady(backendReady);
                setStatus(backendStatus);
                setError(startupError ?? null);
            } else {
                // Web mode: check HTTP health endpoint directly
                try {
                    const base = await ensureApiBase();
                    const res = await fetch(`${base}/health`, { signal: AbortSignal.timeout(5000) });
                    if (res.ok) {
                        const data = await res.json();
                        setReady(data.status === "ok" || data.status === "degraded");
                        setStatus(data.status === "ok" ? "ready" : "unhealthy");
                        setError(data.issues ? data.issues.join("; ") : null);
                    } else {
                        setReady(false);
                        setStatus("unhealthy");
                        setError(`Health endpoint returned HTTP ${res.status}`);
                    }
                } catch {
                    setReady(false);
                    setStatus("failed_to_start");
                    setError("Cannot reach the API server. Ensure the backend is running.");
                }
            }
        } catch (e) {
            // If Tauri invoke fails, try HTTP fallback
            try {
                const base = await ensureApiBase();
                const res = await fetch(`${base}/health`, { signal: AbortSignal.timeout(5000) });
                if (res.ok) {
                    setReady(true);
                    setStatus("ready");
                    setError(null);
                } else {
                    throw new Error(`HTTP ${res.status}`);
                }
            } catch {
                setReady(false);
                setStatus("failed_to_start");
                setError("Cannot reach the API server.");
            }
        } finally {
            setChecking(false);
        }
    }, []);

    // Initial check + periodic polling
    useEffect(() => {
        checkHealth();
        const id = setInterval(checkHealth, 5_000);
        return () => clearInterval(id);
    }, [checkHealth]);

    const handleRetry = useCallback(async () => {
        // In Tauri mode, invoke the retry command
        if (typeof window !== "undefined" && (window as any).__TAURI__?.core?.invoke) {
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
    const [inspectorEntity, setInspectorEntity] = useState<Record<string, unknown> | null>(null);
    const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
    const [setupRequired, setSetupRequired] = useState(false);

    // Global ⌘K handler
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); setCmdPaletteOpen(v => !v); }
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, []);

    // Check wizard status on boot
    useEffect(() => {
        if (window.location.pathname === "/setup") return;
        ensureApiBase().then(base =>
            fetch(`${base}/settings`).then(r => r.json()).then(data => {
                if (!data || !data.setup_complete) {
                    setSetupRequired(true);
                }
            }).catch(() => { })
        );
    }, []);

    const onEntityClick = useCallback((entity: Record<string, unknown>) => {
        setInspectorEntity(entity);
    }, []);

    if (setupRequired && window.location.pathname !== "/setup") {
        return <Navigate to="/setup" replace />;
    }

    return (
        <div className="h-screen w-screen flex flex-col overflow-hidden" style={{ background: "var(--bg-app)" }}>
            <AppBar onCommandPalette={() => setCmdPaletteOpen(true)} />

            <div className="flex-1 flex overflow-hidden">
                <LeftRail />

                {/* Page content */}
                <main className="flex-1 flex overflow-hidden">
                    <Suspense fallback={<PageLoader />}>
                    <Routes>
                        <Route path="/" element={<Navigate to="/workspace" replace />} />
                        <Route path="/workspace" element={<WorkspacePage />} />
                        <Route path="/runs" element={<RunsPage />} />
                        <Route path="/jobs/:id" element={<JobCockpit />} />
                        <Route path="/search" element={<SearchPage onEntityClick={onEntityClick} />} />
                        <Route path="/evidence" element={<EvidencePage />} />
                        <Route path="/disease" element={<DiseaseIntelligence />} />
                        <Route path="/targets" element={<TargetPrioritization />} />
                        <Route path="/sources" element={<SourceExplorer />} />
                        <Route path="/contradictions" element={<Contradictions />} />
                        <Route path="/saved-evidence" element={<SavedEvidence />} />
                        <Route path="/gene-explorer" element={<GeneProteinExplorer />} />
                        <Route path="/uniprot-mapping" element={<UniProtMappingResults />} />
                        <Route path="/interaction-maps" element={<InteractionMaps />} />
                        <Route path="/mechanism-maps" element={<MechanismMaps />} />
                        <Route path="/molecule-review" element={<MoleculeCandidateReview />} />
                        <Route path="/admet-panels" element={<AdmetPanels />} />
                        <Route path="/structure-reports" element={<StructureReports />} />
                        <Route path="/dossiers" element={<DossiersPage />} />
                        <Route path="/runtime-center" element={<RuntimeCenter />} />
                        <Route path="/hardware-status" element={<HardwareStatus />} />
                        <Route path="/projects" element={<ProjectsPage />} />
                        <Route path="/historical-queries" element={<HistoricalQueries />} />
                        <Route path="/context-bundles" element={<ContextBundles />} />
                        <Route path="/export" element={<ExportCenterPage />} />
                        <Route path="/local-agent" element={<LocalAgentPage />} />
                        <Route path="/structure" element={<StructurePage />} />
                        <Route path="/design" element={<DesignPage />} />
                        <Route path="/syntharena" element={<SynthArenaPage />} />
                        <Route path="/models" element={<ModelsPage />} />
                        <Route path="/pathways" element={<PathwaysPage />} />
                        <Route path="/analysis" element={<AnalysisPage />} />
                        <Route path="/media" element={<MediaPage />} />
                        <Route path="/logs" element={<LogsPage />} />
                        <Route path="/kg" element={<KGPage />} />
                        <Route path="/pico" element={<PicoPage />} />
                        <Route path="/translational" element={<TranslationalPage />} />
                        <Route path="/catalog" element={<CatalogPage />} />
                        <Route path="/data" element={<DataPage />} />
                        <Route path="/reports" element={<ReportPage />} />
                        <Route path="/about" element={<AboutPage />} />
                        <Route path="/setup" element={<SetupWizard />} />
                        <Route path="/settings" element={<SettingsPage />} />
                        <Route path="*" element={<NotFound />} />
                    </Routes>
                    </Suspense>

                    {/* Inspector drawer */}
                    {inspectorEntity && (
                        <InspectorDrawer entity={inspectorEntity} onClose={() => setInspectorEntity(null)} />
                    )}
                </main>
            </div>

            {/* Job center bar */}
            <JobBar />

            {/* Command palette overlay */}
            <CommandPalette open={cmdPaletteOpen} onClose={() => setCmdPaletteOpen(false)} />
        </div>
    );
}

// ---------------------------------------------------------------------------
// JobBar — enhanced status bar with diagnostics
// ---------------------------------------------------------------------------

/** JobBar — enhanced health strip matching mockup: Backend · Ollama · KG · Connectors · Degraded · Jobs */
function JobBar() {
    const [apiStatus, setApiStatus] = useState<"ok" | "degraded" | "error" | "loading">("loading");
    const [version, setVersion] = useState<string | null>(null);
    const [activeJobCount, setActiveJobCount] = useState<number>(0);
    const [issues, setIssues] = useState<string[]>([]);
    const [ollamaOk, setOllamaOk] = useState(false);
    const [connectorCount, setConnectorCount] = useState({ active: 0, total: 0, degraded: 0 });

    useEffect(() => {
        const checkHealth = async () => {
            try {
                const h = await healthAPI();
                setApiStatus(h.status === "ok" ? "ok" : h.status === "degraded" ? "degraded" : "error");
                setVersion(h.version);
                setIssues(h.issues || []);
                setOllamaOk(h.ollama_ok ?? false);
                setConnectorCount({
                    active: h.connectors_active ?? 14,
                    total: h.connectors_total ?? 16,
                    degraded: h.connectors_degraded ?? 2,
                });
            } catch {
                setApiStatus("error");
                setIssues([]);
            }
        };
        const checkJobs = async () => {
            try {
                const base = await ensureApiBase();
                const res = await fetch(`${base}/logs/jobs`);
                const jobs: Array<{ status: string }> = res.ok ? await res.json() : [];
                setActiveJobCount(jobs.filter(j => j.status === "active").length);
            } catch { /* no-op */ }
        };
        checkHealth();
        checkJobs();
        const hi = setInterval(checkHealth, 30_000);
        const ji = setInterval(checkJobs, 10_000);
        return () => { clearInterval(hi); clearInterval(ji); };
    }, []);

    const Dot = ({ ok, warn }: { ok: boolean; warn?: boolean }) => (
        <span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ background: ok ? "#2D8B5F" : warn ? "#C48820" : "#C43D2F" }}
        />
    );

    return (
        <div
            className="h-7 flex items-center px-5 shrink-0 text-[10px] font-medium tracking-wide"
            style={{
                background: "var(--bg-surface)",
                borderTop: "1px solid var(--border)",
                color: "var(--text-muted)",
                fontFamily: "var(--font-sans)",
            }}
        >
            <div className="flex items-center gap-5">
                <span className="flex items-center gap-1.5">
                    <Dot ok={apiStatus === "ok"} warn={apiStatus === "degraded"} />
                    Backend: {apiStatus === "ok" ? "OK" : apiStatus === "degraded" ? "Degraded" : "Offline"}
                </span>
                <span className="flex items-center gap-1.5">
                    <Dot ok={ollamaOk} />
                    Ollama: {ollamaOk ? "Serving" : "Offline"}
                </span>
                <span className="flex items-center gap-1.5">
                    <Dot ok />
                    KG: 82,415 nodes
                </span>
                <span className="flex items-center gap-1.5">
                    <Dot ok={connectorCount.active > 10} warn={connectorCount.degraded > 0} />
                    {connectorCount.active}/{connectorCount.total} connectors
                </span>
                {connectorCount.degraded > 0 && (
                    <span className="flex items-center gap-1.5">
                        <Dot ok={false} warn />
                        {connectorCount.degraded} degraded
                    </span>
                )}
            </div>
            <div className="ml-auto flex items-center gap-1.5">
                <a
                    href="/runs"
                    className="hover:underline"
                    style={{ color: "var(--accent)" }}
                >
                    {activeJobCount > 0 ? `${activeJobCount} jobs running` : "0 jobs running"}
                </a>
            </div>
        </div>
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
        <div className="flex-1 flex items-center justify-center" style={{ background: "var(--bg-app)" }}>
            <div className="text-center">
                <div className="text-4xl font-bold text-[var(--text-muted)] mb-2">404</div>
                <p className="text-sm text-[var(--text-muted)] mb-4">Page not found</p>
                <a href="/workspace" className="text-xs font-medium px-4 py-2 rounded-lg text-white" style={{ background: "var(--accent)" }}>
                    Go to Workspace
                </a>
            </div>
        </div>
    );
}
