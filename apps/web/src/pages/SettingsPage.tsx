/** Settings — tabbed config: General, Sources, Models & Runtime, API Keys, Performance, Audit, Logs.
 *  Phase BB Settings Expansion (BB-1 through BB-11). */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Loader2,
  Save,
  Cpu,
  HardDrive,
  Trash2,
  Download,
  CheckCircle2,
  XCircle,
  Wand2,
  Radio,
  Settings as SettingsIcon,
  Zap,
  ScrollText,
  KeyRound,
  Gauge,
  ShieldCheck,
  Eye,
  EyeOff,
  Pencil,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  Monitor,
} from "lucide-react";
import {
  runtimesListAPI,
  runtimesRecommendAPI,
  modelsCatalogAPI,
  modelsInstalledAPI,
  modelsDeleteAPI,
  settingsGetAPI,
  settingsUpdateAPI,
  ensureApiBase,
  dataSetKeyAPI,
  dataDeleteKeyAPI,
  dataStorageAPI,
  dataCacheAPI,
  dataClearCacheAPI,
  runtimeDiagnosticsAPI,
  securityAuditLogAPI,
  type RuntimesResponse,
  type RecommendResponse,
  type ModelCatalogEntry,
  type InstalledModel,
  type AuditLogParams,
} from "@/lib/api";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "@/lib/types";
import { useToast } from "@/lib/ToastContext";
import { useTheme, type Theme } from "@/contexts/ThemeContext";
import SourceExplorer from "./SourceExplorer";
import LogsPage from "./LogsPage";

/* ─── Tab definitions ─────────────────────────────────── */

const SETTINGS_TABS = [
  { id: "general", label: "General", icon: SettingsIcon },
  { id: "sources", label: "Sources", icon: Radio },
  { id: "models", label: "Runtime", icon: Zap },
  { id: "apikeys", label: "Security", icon: KeyRound },
  { id: "performance", label: "Storage", icon: Gauge },
  { id: "notifications", label: "Notifications", icon: ShieldCheck },
  { id: "export", label: "Export", icon: ScrollText },
  { id: "accessibility", label: "Accessibility", icon: Eye },
  { id: "advanced", label: "Advanced", icon: Wand2 },
  { id: "diagnostics", label: "Diagnostics", icon: Cpu },
] as const;

type SettingsTab = (typeof SETTINGS_TABS)[number]["id"];

export default function SettingsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const pathTab = window.location.pathname === "/logs" ? "diagnostics" : null;
  const initialTab = pathTab || (searchParams.get("tab") as SettingsTab) || "general";
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab);

  const switchTab = (tab: SettingsTab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ background: "var(--bg-app)" }}>
      {/* Tab bar */}
      <div
        className="shrink-0 flex items-center gap-1 px-6 pt-3 pb-0 border-b overflow-x-auto"
        style={{ borderColor: "var(--border)" }}
      >
        <SettingsIcon size={16} className="text-[var(--accent)] mr-2 shrink-0" />
        <span className="text-sm font-semibold text-[var(--text-primary)] mr-4 shrink-0">Settings</span>
        {SETTINGS_TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => switchTab(t.id)}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors border-b-2 whitespace-nowrap"
            style={{
              color: activeTab === t.id ? "var(--accent)" : "var(--text-muted)",
              borderColor: activeTab === t.id ? "var(--accent)" : "transparent",
            }}
          >
            <t.icon size={13} />
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto">
        {activeTab === "general" && <GeneralSettingsTab />}
        {activeTab === "sources" && <SourceExplorer />}
        {activeTab === "models" && <ModelsRuntimeTab />}
        {activeTab === "apikeys" && <APIKeysTab />}
        {activeTab === "performance" && <PerformanceTab />}
        {activeTab === "notifications" && <NotificationsTab />}
        {activeTab === "export" && <ExportTab />}
        {activeTab === "accessibility" && <AccessibilityTab />}
        {activeTab === "advanced" && <AdvancedTab />}
        {activeTab === "diagnostics" && <DiagnosticsTab />}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   BB-1, BB-5, BB-10, BB-11 — General Settings Tab
   ═══════════════════════════════════════════════════════════ */

const RUNTIME_MODES = [
  { value: "hosted", label: "Hosted" },
  { value: "local", label: "Local" },
  { value: "auto", label: "Auto" },
] as const;

const RETENTION_OPTIONS = [
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
  { value: "1y", label: "1 year" },
  { value: "forever", label: "Forever" },
] as const;

const THEME_OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const;

const FONT_SIZE_OPTIONS = [
  { value: "small", label: "Small" },
  { value: "medium", label: "Medium" },
  { value: "large", label: "Large" },
] as const;

const EXPORT_FORMATS = ["PDF", "DOCX", "JSON", "CSV"] as const;

function GeneralSettingsTab() {
  const qc = useQueryClient();
  const { addToast } = useToast();
  const { setTheme } = useTheme();
  const [formData, setFormData] = useState<Record<string, unknown>>({});

  const { data: settings, isLoading: loadingSettings } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsGetAPI,
  });

  useEffect(() => {
    if (settings) setFormData(settings);
  }, [settings]);

  const saveMut = useMutation({
    mutationFn: (s: Record<string, unknown>) => settingsUpdateAPI(s),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      addToast({ type: "success", title: "General settings saved", message: "Your preferences have been updated." });
    },
    onError: (err: Error) => {
      addToast({ type: "error", title: "Failed to save settings", message: err.message || "An unexpected error occurred." });
    },
  });

  const handleChange = (k: string, v: unknown) => {
    setFormData((prev) => ({ ...prev, [k]: v }));
    // Immediate preview: apply theme change without waiting for save
    if (k === "theme") {
      setTheme(v as Theme);
    }
    // Immediate preview: apply font size change
    if (k === "font_size") {
      const sizeMap: Record<string, string> = { small: "14px", medium: "16px", large: "18px" };
      document.documentElement.style.fontSize = sizeMap[v as string] || "16px";
    }
    // Immediate preview: apply reduced motion toggle
    if (k === "reduced_motion") {
      if (v) {
        document.documentElement.classList.add("reduce-motion");
      } else {
        document.documentElement.classList.remove("reduce-motion");
      }
    }
  };

  if (loadingSettings)
    return (
      <div className="p-8">
        <Loader2 className="animate-spin text-[var(--text-muted)]" />
      </div>
    );

  return (
    <div className="max-w-3xl mx-auto px-6 py-5 space-y-5">
      {/* BB-1: Runtime Mode */}
      <div className="card rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Runtime Mode</h2>
        <p className="text-[10px] text-[var(--text-muted)]">
          Choose how inference is routed: Hosted (cloud), Local (on-device), or Auto (best available).
        </p>
        <select
          value={String(formData.runtime_mode || "auto")}
          onChange={(e) => handleChange("runtime_mode", e.target.value)}
          className="w-full border rounded-lg text-sm p-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
          style={{ borderColor: "var(--border)" }}
          aria-label="Runtime mode"
        >
          {RUNTIME_MODES.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
        {/* Runtime status indicator — updates within 5s of save */}
        <RuntimeStatusIndicator currentMode={String(formData.runtime_mode || "auto")} />
      </div>

      {/* BB-5: Privacy & Data Retention */}
      <div className="card rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Privacy & Data Retention</h2>
        <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer">
          <input
            type="checkbox"
            checked={!!formData.privacy_mode}
            onChange={(e) => handleChange("privacy_mode", e.target.checked)}
            className="rounded border-gray-300"
          />
          Privacy mode — keep all data local
        </label>
        <div>
          <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Data Retention Period</label>
          <select
            value={String(formData.data_retention || "30d")}
            onChange={(e) => handleChange("data_retention", e.target.value)}
            className="w-full border rounded-lg text-sm p-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{ borderColor: "var(--border)" }}
            aria-label="Data retention period"
          >
            {RETENTION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* AirLLM Toggle (existing) */}
      <div className="card rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">AirLLM</h2>
        <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer">
          <input
            type="checkbox"
            checked={formData.airllm_enabled !== false}
            onChange={(e) => handleChange("airllm_enabled", e.target.checked)}
            className="rounded border-gray-300"
          />
          Enable AirLLM (on by default)
        </label>
        <p className="text-[10px] text-[var(--text-muted)]">
          AirLLM enables efficient large model inference through model partitioning.
        </p>
      </div>

      {/* BB-10: Theming & Accessibility */}
      <div className="card rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Theming & Accessibility</h2>
        <div>
          <label className="block text-xs font-medium text-[var(--text-muted)] mb-2">Theme</label>
          <div className="grid grid-cols-3 gap-2">
            {THEME_OPTIONS.map((t) => {
              const Icon = t.icon;
              const selected = String(formData.theme || "system") === t.value;
              return (
                <button
                  key={t.value}
                  onClick={() => handleChange("theme", t.value)}
                  className={`p-3 rounded-lg border text-left text-xs transition-all ${selected ? "ring-2 ring-[var(--accent)] border-transparent bg-[var(--bg-app)]" : "hover:bg-[var(--bg-surface)]"}`}
                  style={{ borderColor: "var(--border)" }}
                >
                  <Icon size={14} className="mb-1 text-[var(--text-muted)]" />
                  <div className="font-medium text-[var(--text-primary)]">{t.label}</div>
                </button>
              );
            })}
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Font Size</label>
          <select
            value={String(formData.font_size || "medium")}
            onChange={(e) => handleChange("font_size", e.target.value)}
            className="w-full border rounded-lg text-sm p-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{ borderColor: "var(--border)" }}
            aria-label="Font size"
          >
            {FONT_SIZE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer">
          <input
            type="checkbox"
            checked={!!formData.reduced_motion}
            onChange={(e) => handleChange("reduced_motion", e.target.checked)}
            className="rounded border-gray-300"
          />
          Reduced motion — minimize animations
        </label>
      </div>

      {/* BB-11: Export Format Defaults */}
      <div className="card rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Export Format Defaults</h2>
        <p className="text-[10px] text-[var(--text-muted)]">
          Choose the default format for report and data exports.
        </p>
        <div className="flex flex-wrap gap-3">
          {EXPORT_FORMATS.map((fmt) => (
            <label key={fmt} className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] cursor-pointer">
              <input
                type="radio"
                name="export_format"
                value={fmt}
                checked={String(formData.default_export_format || "PDF") === fmt}
                onChange={() => handleChange("default_export_format", fmt)}
                className="text-[var(--accent)]"
              />
              {fmt}
            </label>
          ))}
        </div>
      </div>

      {/* Save */}
      <div className="flex justify-end pb-8">
        <button
          onClick={() => saveMut.mutate(formData)}
          disabled={saveMut.isPending}
          className="px-6 py-2.5 rounded-lg text-sm font-medium text-white flex items-center gap-2 hover:opacity-90 disabled:opacity-40"
          style={{ background: "var(--accent)" }}
        >
          {saveMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          Save Changes
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   BB-2 — Models & Runtime Tab (enhanced, keeps existing)
   ═══════════════════════════════════════════════════════════ */

function ModelsRuntimeTab() {
  const qc = useQueryClient();
  const { addToast } = useToast();
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [pullModel, setPullModel] = useState("");
  const [pullProgress, setPullProgress] = useState<string | null>(null);
  const [isPulling, setIsPulling] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const { data: settings, isLoading: loadingSettings } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsGetAPI,
  });
  const { data: runtimes } = useQuery<RuntimesResponse>({
    queryKey: ["runtimes"],
    queryFn: runtimesListAPI,
  });
  const { data: catalog } = useQuery<ModelCatalogEntry[]>({
    queryKey: ["catalog"],
    queryFn: modelsCatalogAPI,
  });
  const { data: installed, refetch: refetchInstalled } = useQuery<InstalledModel[]>({
    queryKey: ["installed"],
    queryFn: modelsInstalledAPI,
  });

  useEffect(() => {
    if (settings) setFormData(settings);
  }, [settings]);

  const saveMut = useMutation({
    mutationFn: (s: Record<string, unknown>) => settingsUpdateAPI(s),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["runtimes"] });
      addToast({ type: "success", title: "Runtime settings saved", message: "Compute and model configuration updated." });
    },
    onError: (err: Error) => {
      addToast({ type: "error", title: "Failed to save runtime settings", message: err.message || "An unexpected error occurred." });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => modelsDeleteAPI(id),
    onSuccess: () => refetchInstalled(),
  });

  const handlePull = useCallback(async () => {
    if (!pullModel) return;
    setIsPulling(true);
    setPullProgress("Starting download...");
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const base = await ensureApiBase();
      const resp = await fetch(`${base}/models/pull/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: pullModel }),
        signal: ctrl.signal,
      });
      const reader = resp.body?.getReader();
      const decoder = new TextDecoder();
      if (reader) {
        let buf = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() || "";
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const d = JSON.parse(line.slice(6));
                if (d.status)
                  setPullProgress(
                    d.status +
                      (d.completed && d.total
                        ? ` (${Math.round((d.completed / d.total) * 100)}%)`
                        : ""),
                  );
              } catch { /* skip */ }
            }
          }
        }
      }
      setPullProgress("Done!");
      refetchInstalled();
    } catch (e) {
      if ((e as Error).name !== "AbortError")
        setPullProgress(`Error: ${(e as Error).message}`);
    } finally {
      setIsPulling(false);
      abortRef.current = null;
    }
  }, [pullModel, refetchInstalled]);

  const handleChange = (k: string, v: unknown) =>
    setFormData((prev) => ({ ...prev, [k]: v }));

  if (loadingSettings)
    return (
      <div className="p-8">
        <Loader2 className="animate-spin text-[var(--text-muted)]" />
      </div>
    );

  const caps = runtimes?.capabilities;
  const hasGpu = caps ? caps.gpu !== "none" && caps.gpu !== "unknown" : false;
  const computeMode = String(formData.compute_mode || "auto");
  const selectedModel = catalog?.find((m) => m.name === formData.model_id);

  return (
    <div className="max-w-3xl mx-auto px-6 py-5 space-y-5">
      {/* Hardware Dashboard */}
      {caps && <HardwareCard caps={caps} />}

      {/* Compute & Runtime */}
      <div className="card rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Compute & Runtime</h2>
        <div>
          <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Compute Mode</label>
          <div className="grid grid-cols-3 gap-2">
            {([["auto", "Auto", Wand2], ["cpu", "CPU", Cpu], ["gpu", "GPU", HardDrive]] as const).map(
              ([val, lbl, Icon]) => (
                <button
                  key={val}
                  onClick={() => handleChange("compute_mode", val)}
                  disabled={val === "gpu" && !hasGpu}
                  className={`p-3 rounded-lg border text-left text-xs transition-all ${computeMode === val ? "ring-2 ring-[var(--accent)] border-transparent bg-[var(--bg-app)]" : "hover:bg-[var(--bg-surface)]"} ${val === "gpu" && !hasGpu ? "opacity-40 cursor-not-allowed" : ""}`}
                  style={{ borderColor: "var(--border)" }}
                >
                  <Icon size={14} className="mb-1 text-[var(--text-muted)]" />
                  <div className="font-medium text-[var(--text-primary)]">{lbl}</div>
                  {val === "auto" && <span className="text-[9px] text-[var(--accent)]">Recommended</span>}
                </button>
              ),
            )}
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Inference Runtime</label>
          <select
            value={String(formData.runtime || "llama.cpp")}
            onChange={(e) => handleChange("runtime", e.target.value)}
            className="w-full border rounded-lg text-sm p-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{ borderColor: "var(--border)" }}
          >
            {(runtimes?.available ?? []).map((r) => (
              <option key={r.id} value={r.id} disabled={r.status === "not_installed"}>
                {r.name}{r.status === "not_installed" ? " (Not Installed)" : ""}
              </option>
            ))}
          </select>
        </div>
        {formData.runtime === "remote" && (
          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Remote Endpoint URL</label>
            <input
              type="text"
              value={String(formData.remote_base_url || "")}
              onChange={(e) => handleChange("remote_base_url", e.target.value)}
              placeholder="https://api.openai.com/v1"
              className="w-full border rounded-lg text-sm p-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              style={{ borderColor: "var(--border)" }}
            />
          </div>
        )}
      </div>

      {/* BB-2: Enhanced Active Model — includes Gemma 4 26B, llama3.1:8b, custom endpoint */}
      <div className="card rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Active Model</h2>
        <select
          value={String(formData.model_id || "")}
          onChange={(e) => handleChange("model_id", e.target.value)}
          className="w-full border rounded-lg text-sm p-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
          style={{ borderColor: "var(--border)" }}
        >
          <option value="">Select a model...</option>
          {/* Pinned recommended models */}
          <option value="Gemma-4-26B-A4B">Gemma 4 26B (recommended)</option>
          <option value="llama3.1:8b">llama3.1:8b</option>
          <option value="custom">Custom endpoint...</option>
          {/* Catalog models */}
          {catalog
            ?.filter((m) => m.name !== "Gemma-4-26B-A4B" && m.ollama_id !== "llama3.1:8b")
            .map((m) => (
              <option key={m.name} value={m.name}>
                {m.name} ({m.parameters}, {m.size_gb} GB)
              </option>
            ))}
        </select>
        {String(formData.model_id) === "custom" && (
          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Custom Model Endpoint</label>
            <input
              type="text"
              value={String(formData.custom_model_endpoint || "")}
              onChange={(e) => handleChange("custom_model_endpoint", e.target.value)}
              placeholder="https://your-model-server.example.com/v1"
              className="w-full border rounded-lg text-sm p-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              style={{ borderColor: "var(--border)" }}
            />
          </div>
        )}
        {selectedModel && <ModelInfoCard model={selectedModel} caps={caps} />}
      </div>

      {/* Installed Models */}
      <div className="card rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Installed Models</h2>
        {installed && installed.length > 0 ? (
          <div className="space-y-2">
            {installed.map((m) => (
              <div
                key={m.name}
                className="flex items-center justify-between px-3 py-2 rounded-lg border text-xs"
                style={{ borderColor: "var(--border)" }}
              >
                <div>
                  <span className="font-medium text-[var(--text-primary)]">{m.name}</span>
                  <span className="ml-2 text-[var(--text-muted)]">{(m.size / 1e9).toFixed(1)} GB</span>
                </div>
                <button
                  onClick={() => deleteMut.mutate(m.name)}
                  disabled={deleteMut.isPending}
                  className="text-red-500 hover:text-red-700 p-1"
                  aria-label={`Delete model ${m.name}`}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-[var(--text-muted)]">No models installed in Ollama.</p>
        )}
        <div className="pt-2 border-t" style={{ borderColor: "var(--border)" }}>
          <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Pull New Model</label>
          <div className="flex gap-2">
            <select
              value={pullModel}
              onChange={(e) => setPullModel(e.target.value)}
              className="flex-1 border rounded-lg text-sm p-2 bg-white"
              style={{ borderColor: "var(--border)" }}
            >
              <option value="">Select model to pull...</option>
              {catalog?.map((m) => (
                <option key={m.name} value={m.ollama_id}>
                  {m.name} ({m.size_gb} GB)
                </option>
              ))}
            </select>
            <button
              onClick={handlePull}
              disabled={!pullModel || isPulling}
              className="px-4 py-2 rounded-lg text-xs font-medium text-white disabled:opacity-40"
              style={{ background: "var(--accent)" }}
            >
              {isPulling ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            </button>
          </div>
          {pullProgress && (
            <div className="mt-2 px-3 py-2 rounded bg-[var(--bg-surface)] text-xs text-[var(--text-muted)]">
              {pullProgress}
            </div>
          )}
        </div>
      </div>

      {/* Save */}
      <div className="flex justify-end pb-8">
        <button
          onClick={() => saveMut.mutate(formData)}
          disabled={saveMut.isPending}
          className="px-6 py-2.5 rounded-lg text-sm font-medium text-white flex items-center gap-2 hover:opacity-90 disabled:opacity-40"
          style={{ background: "var(--accent)" }}
        >
          {saveMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          Save Changes
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   BB-4 — API Keys Tab
   ═══════════════════════════════════════════════════════════ */

const API_KEY_SERVICES = [
  { id: "ESM_FORGE_API_KEY", label: "ESM Forge" },
  { id: "NCBI_API_KEY", label: "NCBI" },
  { id: "DISGENET_API_KEY", label: "DisGeNET" },
  { id: "CHEMBL_API_KEY", label: "ChEMBL" },
  { id: "PUBCHEM_API_KEY", label: "PubChem" },
  { id: "OPENAI_API_KEY", label: "OpenAI" },
] as const;

interface KeyRowProps {
  service: string;
  label: string;
  hasKey: boolean;
  onSave: (service: string, key: string) => void;
  onDelete: (service: string) => void;
  isSaving: boolean;
  isDeleting: boolean;
}

function APIKeyRow({ service, label, hasKey, onSave, onDelete, isSaving, isDeleting }: KeyRowProps) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [showValue, setShowValue] = useState(false);

  const handleSave = () => {
    if (!value.trim()) return;
    onSave(service, value.trim());
    setValue("");
    setEditing(false);
    setShowValue(false);
  };

  const handleCancel = () => {
    setValue("");
    setEditing(false);
    setShowValue(false);
  };

  return (
    <div
      className="flex items-center justify-between px-4 py-3 rounded-lg border text-xs"
      style={{ borderColor: "var(--border)" }}
    >
      <div className="flex-1 min-w-0">
        <div className="font-medium text-[var(--text-primary)]">{label}</div>
        <div className="text-[var(--text-muted)] text-[10px] font-mono">{service}</div>
      </div>

      {editing ? (
        <div className="flex items-center gap-2 ml-3">
          <div className="relative">
            <input
              type={showValue ? "text" : "password"}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Enter API key..."
              className="border rounded-lg text-xs p-2 pr-8 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)] w-56"
              style={{ borderColor: "var(--border)" }}
              autoComplete="off"
              aria-label={`API key for ${label}`}
            />
            <button
              type="button"
              onClick={() => setShowValue(!showValue)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              aria-label={showValue ? "Hide key" : "Show key"}
            >
              {showValue ? <EyeOff size={12} /> : <Eye size={12} />}
            </button>
          </div>
          <button
            onClick={handleSave}
            disabled={!value.trim() || isSaving}
            className="px-3 py-1.5 rounded-lg text-[10px] font-medium text-white disabled:opacity-40"
            style={{ background: "var(--accent)" }}
          >
            {isSaving ? <Loader2 size={10} className="animate-spin" /> : "Save"}
          </button>
          <button
            onClick={handleCancel}
            className="px-3 py-1.5 rounded-lg text-[10px] font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] border"
            style={{ borderColor: "var(--border)" }}
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-2 ml-3">
          {hasKey ? (
            <>
              <span className="text-[var(--text-muted)] font-mono text-[10px]">••••••••</span>
              <span className="px-1.5 py-0.5 rounded bg-green-100 text-green-700 text-[9px] font-medium">Set</span>
            </>
          ) : (
            <span className="px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-700 text-[9px] font-medium">Not set</span>
          )}
          <button
            onClick={() => setEditing(true)}
            className="p-1.5 rounded hover:bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            aria-label={`Edit ${label} key`}
          >
            <Pencil size={12} />
          </button>
          {hasKey && (
            <button
              onClick={() => onDelete(service)}
              disabled={isDeleting}
              className="p-1.5 rounded hover:bg-red-50 text-red-400 hover:text-red-600"
              aria-label={`Delete ${label} key`}
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function APIKeysTab() {
  const qc = useQueryClient();

  const { data: keysData, isLoading, isError, refetch } = useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => {
      const base = await ensureApiBase();
      const resp = await fetch(`${base}/data/keys`, { credentials: "include", cache: "no-store" });
      if (!resp.ok) throw new Error(`Failed to fetch keys: ${resp.status}`);
      const json = await resp.json();
      if (json?.data !== undefined && json?.request_id !== undefined) return json.data as Record<string, boolean>;
      return json as Record<string, boolean>;
    },
  });

  const saveMut = useMutation({
    mutationFn: ({ service, key }: { service: string; key: string }) => dataSetKeyAPI(service, key),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (service: string) => dataDeleteKeyAPI(service),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const viewState: ViewState = isLoading ? "loading" : isError ? "error" : "success";

  return (
    <div className="max-w-3xl mx-auto px-6 py-5 space-y-5">
      <StateWrapper
        state={viewState}
        moduleName="API Keys"
        onRetry={() => refetch()}
        errorInfo={isError ? { code: "KEYS_FETCH", message: "Failed to load API key status" } : undefined}
      >
        <div className="card rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">API Key Vault</h2>
            <p className="text-[10px] text-[var(--text-muted)]">Keys are stored encrypted. Raw values are never displayed.</p>
          </div>
          <div className="space-y-2">
            {API_KEY_SERVICES.map((svc) => (
              <APIKeyRow
                key={svc.id}
                service={svc.id}
                label={svc.label}
                hasKey={!!(keysData && keysData[svc.id])}
                onSave={(service, key) => saveMut.mutate({ service, key })}
                onDelete={(service) => deleteMut.mutate(service)}
                isSaving={saveMut.isPending}
                isDeleting={deleteMut.isPending}
              />
            ))}
          </div>
        </div>
      </StateWrapper>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   BB-6, BB-7, BB-8 — Performance Tab
   ═══════════════════════════════════════════════════════════ */

function PerformanceTab() {
  const qc = useQueryClient();
  const { addToast } = useToast();
  const [formData, setFormData] = useState<Record<string, unknown>>({});

  const { data: settings, isLoading: loadingSettings } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsGetAPI,
  });

  useEffect(() => {
    if (settings) setFormData(settings);
  }, [settings]);

  const saveMut = useMutation({
    mutationFn: (s: Record<string, unknown>) => settingsUpdateAPI(s),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      addToast({ type: "success", title: "Storage settings saved", message: "Cache and throughput configuration updated." });
    },
    onError: (err: Error) => {
      addToast({ type: "error", title: "Failed to save storage settings", message: err.message || "An unexpected error occurred." });
    },
  });

  // BB-7: Storage diagnostics
  const { data: storageData, isLoading: loadingStorage, refetch: refetchStorage } = useQuery({
    queryKey: ["storage-diagnostics"],
    queryFn: dataStorageAPI,
    refetchInterval: 30_000,
  });

  // BB-6: Cache info
  const { data: cacheData, isLoading: loadingCache, refetch: refetchCache } = useQuery({
    queryKey: ["cache-info"],
    queryFn: dataCacheAPI,
  });

  const clearCacheMut = useMutation({
    mutationFn: dataClearCacheAPI,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cache-info"] });
    },
  });

  // BB-8: Plugin diagnostics
  const { data: runtimeDiag, isLoading: loadingDiag, refetch: refetchDiag } = useQuery({
    queryKey: ["runtime-diagnostics"],
    queryFn: runtimeDiagnosticsAPI,
    refetchInterval: 30_000,
  });

  const handleChange = (k: string, v: unknown) =>
    setFormData((prev) => ({ ...prev, [k]: v }));

  if (loadingSettings)
    return (
      <div className="p-8">
        <Loader2 className="animate-spin text-[var(--text-muted)]" />
      </div>
    );

  const cacheTtl = Number(formData.cache_ttl_hours ?? 24);
  const maxConcurrent = Number(formData.max_concurrent_requests ?? 10);
  const requestTimeout = Number(formData.request_timeout_seconds ?? 30);

  return (
    <div className="max-w-3xl mx-auto px-6 py-5 space-y-5">
      {/* BB-6: Cache & Throughput Tuning */}
      <div className="card rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Cache & Throughput</h2>
          <button
            onClick={() => clearCacheMut.mutate()}
            disabled={clearCacheMut.isPending}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-medium text-red-600 hover:bg-red-50 border border-red-200"
          >
            {clearCacheMut.isPending ? <Loader2 size={10} className="animate-spin" /> : <Trash2 size={10} />}
            Clear Cache
          </button>
        </div>

        {/* Cache TTL */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">Cache TTL</label>
            <span className="text-xs text-[var(--text-primary)] font-medium">{cacheTtl}h</span>
          </div>
          <input
            type="range"
            min={1}
            max={168}
            value={cacheTtl}
            onChange={(e) => handleChange("cache_ttl_hours", Number(e.target.value))}
            className="w-full accent-[var(--accent)]"
            aria-label="Cache TTL in hours"
          />
          <div className="flex justify-between text-[9px] text-[var(--text-muted)]">
            <span>1h</span><span>168h (7d)</span>
          </div>
        </div>

        {/* Max Concurrent Requests */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">Max Concurrent Requests</label>
            <span className="text-xs text-[var(--text-primary)] font-medium">{maxConcurrent}</span>
          </div>
          <input
            type="range"
            min={1}
            max={50}
            value={maxConcurrent}
            onChange={(e) => handleChange("max_concurrent_requests", Number(e.target.value))}
            className="w-full accent-[var(--accent)]"
            aria-label="Max concurrent requests"
          />
          <div className="flex justify-between text-[9px] text-[var(--text-muted)]">
            <span>1</span><span>50</span>
          </div>
        </div>

        {/* Request Timeout */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">Request Timeout</label>
            <span className="text-xs text-[var(--text-primary)] font-medium">{requestTimeout}s</span>
          </div>
          <input
            type="range"
            min={5}
            max={120}
            value={requestTimeout}
            onChange={(e) => handleChange("request_timeout_seconds", Number(e.target.value))}
            className="w-full accent-[var(--accent)]"
            aria-label="Request timeout in seconds"
          />
          <div className="flex justify-between text-[9px] text-[var(--text-muted)]">
            <span>5s</span><span>120s</span>
          </div>
        </div>

        {/* Cache stats */}
        {cacheData && (
          <div className="pt-2 border-t text-xs text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}>
            <div className="grid grid-cols-3 gap-3">
              <StatCell label="Entries" value={String((cacheData as Record<string, unknown>).entries ?? "—")} />
              <StatCell label="Hit Rate" value={`${(cacheData as Record<string, unknown>).hit_rate ?? "—"}%`} />
              <StatCell label="Size" value={String((cacheData as Record<string, unknown>).size_mb ?? "—") + " MB"} />
            </div>
          </div>
        )}

        {/* Save performance settings */}
        <div className="flex justify-end pt-2">
          <button
            onClick={() => saveMut.mutate(formData)}
            disabled={saveMut.isPending}
            className="px-4 py-2 rounded-lg text-xs font-medium text-white flex items-center gap-2 hover:opacity-90 disabled:opacity-40"
            style={{ background: "var(--accent)" }}
          >
            {saveMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            Save
          </button>
        </div>
      </div>

      {/* BB-7: Storage Diagnostics */}
      <div className="card rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Storage Diagnostics</h2>
          <button
            onClick={() => refetchStorage()}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] border"
            style={{ borderColor: "var(--border)" }}
          >
            <RefreshCw size={10} />
            Refresh
          </button>
        </div>
        {loadingStorage ? (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Loader2 size={12} className="animate-spin" /> Loading storage info...
          </div>
        ) : storageData ? (
          <div className="space-y-3">
            {(["object_store", "vector_store", "graph_store"] as const).map((storeKey) => {
              const store = (storageData as Record<string, Record<string, unknown>>)[storeKey];
              if (!store) return null;
              const status = String(store.status ?? "unknown");
              const isOk = status === "connected" || status === "healthy" || status === "ok";
              return (
                <div
                  key={storeKey}
                  className="flex items-center justify-between px-3 py-2 rounded-lg border text-xs"
                  style={{ borderColor: "var(--border)" }}
                >
                  <div className="flex items-center gap-2">
                    {isOk ? (
                      <CheckCircle2 size={12} className="text-green-600" />
                    ) : (
                      <XCircle size={12} className="text-red-500" />
                    )}
                    <span className="font-medium text-[var(--text-primary)] capitalize">
                      {storeKey.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-[var(--text-muted)]">
                    {store.collections !== undefined && <span>Collections: {String(store.collections)}</span>}
                    {store.disk_usage !== undefined && <span>Disk: {String(store.disk_usage)}</span>}
                    <span className={isOk ? "text-green-600" : "text-red-500"}>{status}</span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-[var(--text-muted)]">No storage data available.</p>
        )}
      </div>

      {/* BB-8: Plugin Diagnostics */}
      <div className="card rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Plugin Diagnostics</h2>
          <button
            onClick={() => refetchDiag()}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] border"
            style={{ borderColor: "var(--border)" }}
          >
            <RefreshCw size={10} />
            Refresh
          </button>
        </div>
        {loadingDiag ? (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Loader2 size={12} className="animate-spin" /> Checking plugins...
          </div>
        ) : runtimeDiag ? (
          <div className="space-y-2">
            {typeof (runtimeDiag as Record<string, unknown>).native_tools === "object" && (runtimeDiag as Record<string, unknown>).native_tools !== null && (
              <div className="rounded-lg border px-3 py-2 text-[11px] text-[var(--text-muted)]" style={{ borderColor: "var(--border)" }}>
                {String((((runtimeDiag as Record<string, Record<string, unknown>>).native_tools || {}).summary) || "")}
              </div>
            )}
            {(["rdkit", "vina", "fpocket", "p2rank", "gpu"] as const).map((plugin) => {
              const info = (runtimeDiag as Record<string, Record<string, unknown>>)[plugin];
              const status = info ? String(info.status ?? "unknown") : "not_found";
              const isOk = status === "available" || status === "ok" || status === "connected" || status === "healthy";
              const version = info?.version ? String(info.version) : null;
              const shippingTier = info?.shipping_tier ? String(info.shipping_tier) : null;
              const details = info?.details ? String(info.details) : null;
              return (
                <div
                  key={plugin}
                  className="px-3 py-2 rounded-lg border text-xs"
                  style={{ borderColor: "var(--border)" }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      {isOk ? (
                        <CheckCircle2 size={12} className="text-green-600" />
                      ) : (
                        <XCircle size={12} className="text-yellow-500" />
                      )}
                      <span className="font-medium text-[var(--text-primary)] uppercase">{plugin}</span>
                      {version && <span className="text-[var(--text-muted)]">v{version}</span>}
                      {shippingTier && <span className="text-[10px] text-[var(--text-muted)]">{shippingTier}</span>}
                    </div>
                    <span className={isOk ? "text-green-600" : "text-yellow-600"}>{status}</span>
                  </div>
                  {details && <div className="mt-1 pl-5 text-[10px] text-[var(--text-muted)]">{details}</div>}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-[var(--text-muted)]">No diagnostics data available.</p>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   BB-9 — Audit Tab
   ═══════════════════════════════════════════════════════════ */

const AUDIT_ACTION_FILTERS = [
  { value: "", label: "All actions" },
  { value: "login", label: "Login" },
  { value: "logout", label: "Logout" },
  { value: "settings.update", label: "Settings Update" },
  { value: "data.export", label: "Data Export" },
  { value: "key.create", label: "Key Create" },
  { value: "key.delete", label: "Key Delete" },
  { value: "model.pull", label: "Model Pull" },
  { value: "model.delete", label: "Model Delete" },
  { value: "run.create", label: "Run Create" },
  { value: "run.cancel", label: "Run Cancel" },
] as const;

const AUDIT_PAGE_SIZE = 25;

function AuditTab() {
  const [actionFilter, setActionFilter] = useState("");
  const [page, setPage] = useState(0);

  const params: AuditLogParams = useMemo(
    () => ({
      action: actionFilter || undefined,
      limit: AUDIT_PAGE_SIZE,
      offset: page * AUDIT_PAGE_SIZE,
    }),
    [actionFilter, page],
  );

  const { data: auditLogs, isLoading, isError, refetch } = useQuery({
    queryKey: ["audit-logs", params],
    queryFn: () => securityAuditLogAPI(params),
  });

  const logs = auditLogs ?? [];
  const hasMore = logs.length === AUDIT_PAGE_SIZE;

  const viewState: ViewState = isLoading
    ? "loading"
    : isError
      ? "error"
      : logs.length === 0
        ? "empty"
        : "success";

  const handleFilterChange = (action: string) => {
    setActionFilter(action);
    setPage(0);
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-5 space-y-5">
      <div className="card rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Audit Log</h2>
          <div className="flex items-center gap-2">
            <select
              value={actionFilter}
              onChange={(e) => handleFilterChange(e.target.value)}
              className="border rounded-lg text-xs p-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              style={{ borderColor: "var(--border)" }}
              aria-label="Filter by action"
            >
              {AUDIT_ACTION_FILTERS.map((f) => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
            <button
              onClick={() => refetch()}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] border"
              style={{ borderColor: "var(--border)" }}
            >
              <RefreshCw size={10} />
              Refresh
            </button>
          </div>
        </div>

        <StateWrapper
          state={viewState}
          moduleName="Audit Log"
          onRetry={() => refetch()}
          emptyTitle="No audit entries"
          emptyDescription="No audit log entries match the current filter."
          errorInfo={isError ? { code: "AUDIT_FETCH", message: "Failed to load audit logs" } : undefined}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b" style={{ borderColor: "var(--border)" }}>
                  <th className="text-left py-2 px-2 font-medium text-[var(--text-muted)]">Timestamp</th>
                  <th className="text-left py-2 px-2 font-medium text-[var(--text-muted)]">User</th>
                  <th className="text-left py-2 px-2 font-medium text-[var(--text-muted)]">Action</th>
                  <th className="text-left py-2 px-2 font-medium text-[var(--text-muted)]">Resource</th>
                  <th className="text-left py-2 px-2 font-medium text-[var(--text-muted)]">IP</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((entry, i) => {
                  const e = entry as Record<string, unknown>;
                  return (
                    <tr
                      key={`${String(e.timestamp)}-${i}`}
                      className="border-b hover:bg-[var(--bg-surface)]"
                      style={{ borderColor: "var(--border)" }}
                    >
                      <td className="py-2 px-2 text-[var(--text-muted)] whitespace-nowrap">
                        {e.timestamp ? new Date(String(e.timestamp)).toLocaleString() : "—"}
                      </td>
                      <td className="py-2 px-2 text-[var(--text-primary)]">{String(e.user_id ?? e.user ?? "—")}</td>
                      <td className="py-2 px-2">
                        <span className="px-1.5 py-0.5 rounded bg-[var(--bg-inset)] text-[var(--text-primary)] font-mono text-[10px]">
                          {String(e.action ?? "—")}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-[var(--text-muted)]">{String(e.resource ?? e.resource_type ?? "—")}</td>
                      <td className="py-2 px-2 text-[var(--text-muted)] font-mono">{String(e.ip ?? e.ip_address ?? "—")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between pt-3">
            <span className="text-[10px] text-[var(--text-muted)]">
              Page {page + 1}{logs.length > 0 ? ` · ${logs.length} entries` : ""}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-medium disabled:opacity-40 border"
                style={{ borderColor: "var(--border)" }}
              >
                <ChevronLeft size={10} />
                Prev
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!hasMore}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-medium disabled:opacity-40 border"
                style={{ borderColor: "var(--border)" }}
              >
                Next
                <ChevronRight size={10} />
              </button>
            </div>
          </div>
        </StateWrapper>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Shared Sub-components (preserved from original)
   ═══════════════════════════════════════════════════════════ */

/** Displays the current active runtime status after saving runtime mode. */
function RuntimeStatusIndicator({ currentMode }: { currentMode: string }) {
  const { data: runtimes } = useQuery<RuntimesResponse>({
    queryKey: ["runtimes"],
    queryFn: runtimesListAPI,
    refetchInterval: 5_000, // Update within 5 seconds of save
  });

  const activeRuntime = runtimes?.available?.find(
    (r) => r.status === "running" || r.status === "active" || r.status === "installed",
  );
  const modeLabel = currentMode.charAt(0).toUpperCase() + currentMode.slice(1);

  return (
    <div
      className="flex items-center gap-2 mt-2 px-3 py-2 rounded-lg text-xs"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      <div
        className="w-2 h-2 rounded-full shrink-0"
        style={{ background: activeRuntime ? "var(--success, #10b981)" : "var(--warning, #f59e0b)" }}
      />
      <span className="text-[var(--text-secondary)]">
        Mode: <span className="font-medium text-[var(--text-primary)]">{modeLabel}</span>
        {activeRuntime && (
          <>
            {" · "}Active: <span className="font-medium text-[var(--text-primary)]">{activeRuntime.name}</span>
          </>
        )}
        {!activeRuntime && " · No active runtime detected"}
      </span>
    </div>
  );
}

function HardwareCard({
  caps,
}: {
  caps: NonNullable<RuntimesResponse["capabilities"]>;
}) {
  const [rec, setRec] = useState<RecommendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [recError, setRecError] = useState<string | null>(null);
  const handleRecommend = async () => {
    setLoading(true);
    setRecError(null);
    try {
      setRec(await runtimesRecommendAPI());
    } catch (e: unknown) {
      setRecError(e instanceof Error ? e.message : "Auto-detect failed");
    }
    setLoading(false);
  };

  return (
    <div className="card rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Hardware
        </h2>
        <button
          onClick={handleRecommend}
          disabled={loading}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-medium text-white hover:opacity-90"
          style={{ background: "var(--accent)" }}
        >
          {loading ? (
            <Loader2 size={10} className="animate-spin" />
          ) : (
            <Wand2 size={10} />
          )}
          Auto-Detect
        </button>
      </div>
      <div className="grid grid-cols-4 gap-3 text-xs">
        <StatCell label="CPU Cores" value={String(caps.cpu_cores)} />
        <StatCell label="RAM" value={`${caps.ram_gb} GB`} />
        <StatCell label="GPU" value={caps.gpu_name || caps.gpu} />
        <StatCell
          label="VRAM"
          value={caps.vram_gb ? `${caps.vram_gb} GB` : "N/A"}
        />
      </div>
      {recError && (
        <div className="mt-3 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-xs flex items-center gap-2">
          <span className="text-red-600">{recError}</span>
          <button onClick={() => setRecError(null)} className="ml-auto text-red-400 hover:text-red-600">×</button>
        </div>
      )}
      {rec && rec.recommended_model && (
        <div className="mt-3 px-3 py-2 rounded-lg bg-green-50 border border-green-200 text-xs">
          <span className="font-medium text-green-800">Recommended:</span>{" "}
          <span className="text-green-700">{rec.recommended_model.name}</span>{" "}
          <span className="text-green-600">
            on {rec.compute_mode.toUpperCase()}
          </span>
          <span className="text-green-500 ml-1">
            ({rec.compatible_models.length} compatible models)
          </span>
        </div>
      )}
    </div>
  );
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[var(--text-muted)] text-[10px] uppercase tracking-wider">
        {label}
      </div>
      <div className="font-medium text-[var(--text-primary)] mt-0.5">
        {value}
      </div>
    </div>
  );
}

function ModelInfoCard({
  model,
  caps,
}: {
  model: ModelCatalogEntry;
  caps?: RuntimesResponse["capabilities"];
}) {
  const ramOk = caps ? caps.ram_gb >= model.min_ram_gb : true;
  const vramOk = caps ? caps.vram_gb >= model.min_vram_gb : true;

  return (
    <div
      className="rounded-lg border p-3 text-xs space-y-2"
      style={{ borderColor: "var(--border)" }}
    >
      <div className="flex items-center justify-between">
        <span className="font-medium text-[var(--text-primary)]">
          {model.name}
        </span>
        <div className="flex gap-1">
          {(model.tags ?? []).map((t) => (
            <span
              key={t}
              className="px-1.5 py-0.5 rounded bg-[var(--bg-inset)] text-[var(--text-muted)] text-[9px]"
            >
              {t}
            </span>
          ))}
        </div>
      </div>
      <p className="text-[var(--text-muted)]">{model.description}</p>
      <div className="grid grid-cols-4 gap-2">
        <StatCell label="Size" value={`${model.size_gb} GB`} />
        <StatCell label="Params" value={model.parameters} />
        <StatCell label="Context" value={`${model.context_window}`} />
        <StatCell label="Quant" value={model.default_quantization} />
      </div>
      <div className="flex gap-3 pt-1">
        <CompatBadge
          label="CPU"
          ok={ramOk}
          detail={`Needs ${model.min_ram_gb} GB RAM`}
        />
        <CompatBadge
          label="GPU"
          ok={vramOk}
          detail={`Needs ${model.min_vram_gb} GB VRAM`}
        />
      </div>
    </div>
  );
}

function CompatBadge({
  label,
  ok,
  detail,
}: {
  label: string;
  ok: boolean;
  detail: string;
}) {
  return (
    <div className="flex items-center gap-1 text-[10px]" title={detail}>
      {ok ? (
        <CheckCircle2 size={10} className="text-green-600" />
      ) : (
        <XCircle size={10} className="text-red-500" />
      )}
      <span className={ok ? "text-green-700" : "text-red-600"}>
        {label}: {ok ? "Compatible" : "Insufficient"}
      </span>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Notifications Tab (Task 25)
   ═══════════════════════════════════════════════════════════ */

function NotificationsTab() {
  const [prefs, setPrefs] = useState({
    emailAlerts: false,
    runCompletionAlerts: true,
    degradedSourceAlerts: true,
    weeklyDigest: false,
    errorAlerts: true,
  });

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Notification Preferences</h2>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Configure how and when you receive alerts.</p>
      <div className="space-y-3">
        {Object.entries(prefs).map(([key, value]) => (
          <label key={key} className="flex items-center gap-3 p-3 rounded-lg cursor-pointer" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <input
              type="checkbox"
              checked={value}
              onChange={() => setPrefs((p) => ({ ...p, [key]: !p[key as keyof typeof p] }))}
              className="rounded"
            />
            <span className="text-sm" style={{ color: "var(--text-primary)" }}>
              {key.replace(/([A-Z])/g, " $1").replace(/^./, (s) => s.toUpperCase())}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Export Tab (Task 25)
   ═══════════════════════════════════════════════════════════ */

function ExportTab() {
  const [defaultFormat, setDefaultFormat] = useState("PDF");

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Export Settings</h2>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Configure default export formats and templates.</p>
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Default Export Format</label>
          <select
            value={defaultFormat}
            onChange={(e) => setDefaultFormat(e.target.value)}
            className="rounded px-3 py-2 text-sm w-48"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            {["PDF", "DOCX", "JSON", "CSV", "SDF"].map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>
        <div className="p-4 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <h3 className="text-sm font-medium mb-2" style={{ color: "var(--text-primary)" }}>Export Templates</h3>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>Custom export templates can be configured for dossiers, evidence bundles, and lab results.</p>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Accessibility Tab (Task 25)
   ═══════════════════════════════════════════════════════════ */

function AccessibilityTab() {
  const [fontSize, setFontSize] = useState("medium");
  const [highContrast, setHighContrast] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Accessibility</h2>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Customize display preferences for better accessibility.</p>
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Font Size</label>
          <div className="flex gap-2">
            {["small", "medium", "large"].map((size) => (
              <button
                key={size}
                onClick={() => setFontSize(size)}
                className="px-4 py-2 rounded text-sm capitalize"
                style={{
                  background: fontSize === size ? "var(--accent)" : "var(--bg-surface)",
                  color: fontSize === size ? "white" : "var(--text-primary)",
                  border: `1px solid ${fontSize === size ? "var(--accent)" : "var(--border)"}`,
                }}
              >
                {size}
              </button>
            ))}
          </div>
        </div>
        <label className="flex items-center gap-3 p-3 rounded-lg cursor-pointer" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <input type="checkbox" checked={highContrast} onChange={() => setHighContrast(!highContrast)} className="rounded" />
          <div>
            <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>High Contrast Mode</span>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>Increase contrast for better readability</p>
          </div>
        </label>
        <label className="flex items-center gap-3 p-3 rounded-lg cursor-pointer" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <input type="checkbox" checked={reduceMotion} onChange={() => setReduceMotion(!reduceMotion)} className="rounded" />
          <div>
            <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Reduce Motion</span>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>Minimize animations and transitions</p>
          </div>
        </label>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Advanced Tab (Task 25)
   ═══════════════════════════════════════════════════════════ */

function AdvancedTab() {
  const [debugMode, setDebugMode] = useState(false);
  const [logLevel, setLogLevel] = useState("info");
  const [cacheClearing, setCacheClearing] = useState(false);

  const clearCache = async () => {
    setCacheClearing(true);
    try {
      await dataClearCacheAPI();
    } catch {
      // ignore
    }
    setCacheClearing(false);
  };

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Advanced Settings</h2>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Debug mode, logging, and cache management.</p>
      <div className="space-y-4">
        <label className="flex items-center gap-3 p-3 rounded-lg cursor-pointer" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <input type="checkbox" checked={debugMode} onChange={() => setDebugMode(!debugMode)} className="rounded" />
          <div>
            <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Debug Mode</span>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>Enable verbose logging and developer tools</p>
          </div>
        </label>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Log Level</label>
          <select
            value={logLevel}
            onChange={(e) => setLogLevel(e.target.value)}
            className="rounded px-3 py-2 text-sm w-48"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            {["debug", "info", "warning", "error"].map((l) => (
              <option key={l} value={l}>{l.toUpperCase()}</option>
            ))}
          </select>
        </div>
        <div className="p-4 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <h3 className="text-sm font-medium mb-2" style={{ color: "var(--text-primary)" }}>Cache Management</h3>
          <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>Clear cached connector responses, embeddings, and graph queries.</p>
          <button
            onClick={clearCache}
            disabled={cacheClearing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs text-white"
            style={{ background: "var(--accent)" }}
          >
            {cacheClearing ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
            Clear All Caches
          </button>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Diagnostics Tab (Task 25)
   ═══════════════════════════════════════════════════════════ */

function DiagnosticsTab() {
  const [diagnostics, setDiagnostics] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await runtimeDiagnosticsAPI();
        setDiagnostics(data);
      } catch {
        setDiagnostics({ error: "Failed to load diagnostics" });
      }
      setLoading(false);
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center gap-2">
        <Loader2 size={16} className="animate-spin" style={{ color: "var(--accent)" }} />
        <span className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading diagnostics…</span>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>System Diagnostics</h2>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>System health metrics, performance data, and database connection status.</p>
      <div className="space-y-4">
        {diagnostics && Object.entries(diagnostics).map(([key, value]) => (
          <div key={key} className="p-4 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <h3 className="text-sm font-medium mb-1 capitalize" style={{ color: "var(--text-primary)" }}>
              {key.replace(/_/g, " ")}
            </h3>
            <pre className="text-xs overflow-auto" style={{ color: "var(--text-secondary)" }}>
              {typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}
