/** Source Explorer Page — Real-time source monitoring (§17, §62) */
import { useState, useEffect, useCallback } from "react";
import {
  Database,
  Link2,
  CheckCircle,
  Activity,
  Globe,
  XCircle,
  RefreshCw,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { sourcesListAPI, sourcesHealthAPI, sourceToggleAPI, sourceRefreshAPI } from "@/lib/api";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

interface SourceInfo {
  source_id: string;
  name: string;
  category: string;
  enabled: boolean;
  status?: "healthy" | "degraded" | "down";
  latency_ms?: number;
  error_rate?: number;
  records?: string;
}

export default function SourceExplorer() {
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const fetchSources = useCallback(async () => {
    setFetchError(null);
    try {
      const [rawList, health] = await Promise.all([
        sourcesListAPI().catch(() => []),
        sourcesHealthAPI().catch(() => []),
      ]);
      // Backend returns { sources: [...], total: N } or may return array directly
      const list = Array.isArray(rawList) ? rawList : ((rawList as any)?.sources ?? []);
      const healthArr = Array.isArray(health) ? health : ((health as any)?.circuit_breakers ? [] : []);
      const healthMap = new Map(
        healthArr.map((h: any) => [h.source_id || h.source_name, h]),
      );
      const merged = list.map((s: any) => {
        const h = healthMap.get(s.source_id || s.source_name) || {};
        return {
          source_id: s.source_id || s.source_name || s.id,
          name: s.name || s.source_name || s.source_id,
          category: s.category || s.source_family || "unknown",
          enabled: s.enabled ?? (s.status === "active"),
          status: s.status === "active" ? "healthy" : s.status,
          latency_ms: s.latency_ms,
          error_rate: s.error_rate,
          records: s.records,
          ...h,
        };
      });
      setSources(merged);
      setLastChecked(new Date());
    } catch (err: unknown) {
      setFetchError(err instanceof Error ? err.message : "Failed to load sources");
      setSources([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSources();
     const id = setInterval(fetchSources, 30_000);
    return () => clearInterval(id);
  }, [fetchSources]);

  const handleToggle = async (sourceId: string, enabled: boolean) => {
    try {
      await sourceToggleAPI(sourceId, !enabled);
      setSources((prev) =>
        prev.map((s) =>
          s.source_id === sourceId ? { ...s, enabled: !enabled } : s,
        ),
      );
    } catch { /* ignore */ }
  };

  const handleRefresh = async (sourceId: string) => {
    setRefreshing(sourceId);
    try {
      await sourceRefreshAPI(sourceId);
      await fetchSources();
    } catch { /* ignore */ }
    setRefreshing(null);
  };

  const statusIcon = (s: SourceInfo) => {
    if (!s.enabled) return <XCircle size={10} className="text-[var(--text-muted)]" />;
    switch (s.status) {
      case "healthy":
        return <CheckCircle size={10} className="text-green-500" />;
      case "degraded":
        return <Activity size={10} className="text-amber-500" />;
      case "down":
        return <XCircle size={10} className="text-red-500" />;
      default:
        return <CheckCircle size={10} className="text-green-500" />;
    }
  };

  const statusBadge = (s: SourceInfo) => {
    if (!s.enabled) return { text: "Disabled", cls: "bg-gray-500/10 text-[var(--text-muted)] border-gray-500/20" };
    switch (s.status) {
      case "degraded":
        return { text: "Degraded", cls: "bg-amber-500/10 text-amber-500 border-amber-500/20" };
      case "down":
        return { text: "Offline", cls: "bg-red-500/10 text-red-500 border-red-500/20" };
      default:
        return { text: "Online", cls: "bg-green-500/10 text-green-500 border-green-500/20" };
    }
  };

  const hasDegraded = sources.some((s) => s.enabled && s.status === "degraded");
  const viewState: ViewState = loading
    ? "loading"
    : fetchError && sources.length === 0
      ? "error"
      : hasDegraded
        ? "degraded"
        : "success";

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ background: "var(--bg-app)" }}>
        <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-[1100px] mx-auto px-6 py-5">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">
              Source Explorer
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Inspect the active scientific databases powering the inference
              engines.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)] px-3 py-1.5 rounded-full border border-border bg-surface shadow-sm">
            <Activity size={14} className="text-green-500" />
            {sources.filter((s) => s.enabled && s.status !== "down").length}/{sources.length} Sources Active
            {lastChecked && (
              <span className="text-[var(--text-muted)] ml-1" title={lastChecked.toISOString()}>
                · checked {lastChecked.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sources.map((s) => {
            const badge = statusBadge(s);
            return (
              <div
                key={s.source_id}
                className="card p-5 hover:-translate-y-1 transition-transform relative overflow-hidden group"
              >
                <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                  <Database size={64} />
                </div>
                <div className="flex items-center justify-between mb-4 relative z-10">
                  <div className="text-sm font-semibold text-[var(--text-primary)]">
                    {s.name}
                  </div>
                  <span
                    className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border ${badge.cls}`}
                  >
                    {statusIcon(s)} {badge.text}
                  </span>
                </div>
                <div className="space-y-2 relative z-10">
                  <div className="flex items-center justify-between text-xs text-[var(--text-secondary)] border-b border-border/50 pb-1">
                    <span className="flex items-center gap-1.5">
                      <Globe size={12} /> Domain
                    </span>
                    <span>{s.category}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-[var(--text-secondary)] border-b border-border/50 pb-1">
                    <span className="flex items-center gap-1.5">
                      <Activity size={12} /> Latency
                    </span>
                    <span className="font-mono">
                      {s.latency_ms != null ? `${s.latency_ms}ms` : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-[var(--text-secondary)] pb-1">
                    <span className="flex items-center gap-1.5">
                      <Link2 size={12} /> Error Rate
                    </span>
                    <span className="font-mono">
                      {s.error_rate != null
                        ? `${(s.error_rate * 100).toFixed(1)}%`
                        : "0%"}
                    </span>
                  </div>
                </div>
                {/* Controls */}
                <div className="flex items-center gap-2 mt-3 relative z-10">
                  <button
                    onClick={() => handleToggle(s.source_id, s.enabled)}
                    className="flex items-center gap-1 text-[10px] px-2 py-1 rounded border border-border hover:bg-surface/80 transition-colors"
                    title={s.enabled ? "Disable" : "Enable"}
                  >
                    {s.enabled ? (
                      <ToggleRight size={12} className="text-green-500" />
                    ) : (
                      <ToggleLeft size={12} className="text-[var(--text-muted)]" />
                    )}
                    {s.enabled ? "On" : "Off"}
                  </button>
                  <button
                    onClick={() => handleRefresh(s.source_id)}
                    disabled={refreshing === s.source_id}
                    className="flex items-center gap-1 text-[10px] px-2 py-1 rounded border border-border hover:bg-surface/80 transition-colors disabled:opacity-50"
                    title="Refresh health"
                  >
                    <RefreshCw
                      size={12}
                      className={refreshing === s.source_id ? "animate-spin" : ""}
                    />
                    Refresh
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
