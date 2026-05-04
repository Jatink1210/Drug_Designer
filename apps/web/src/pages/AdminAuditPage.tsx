/** AdminAuditPage — Audit log viewer (ADMIN role only) (§L-6) */
import { useState, useEffect, useCallback } from "react";
import { ScrollText, Shield, Search, RefreshCw, ChevronDown } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { ensureApiBase } from "@/lib/api";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

interface AuditEntry {
  id: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

const ACTION_COLORS: Record<string, string> = {
  login: "#10b981",
  logout: "#6b7280",
  create: "#3b82f6",
  update: "#f59e0b",
  delete: "#ef4444",
  read: "#8b5cf6",
};

function actionColor(action: string): string {
  const key = Object.keys(ACTION_COLORS).find((k) => action.toLowerCase().includes(k));
  return key ? ACTION_COLORS[key] : "#6b7280";
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default function AdminAuditPage() {
  const { user } = useAuth();
  const [viewState, setViewState] = useState<ViewState>("initial");
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");

  // Filters
  const [filterUser, setFilterUser] = useState("");
  const [filterAction, setFilterAction] = useState("");
  const [limit, setLimit] = useState(100);

  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchAuditLog = useCallback(async () => {
    setViewState("loading");
    setErrorMsg("");
    try {
      const base = ensureApiBase();
      const params = new URLSearchParams();
      if (filterUser.trim()) params.set("user_id", filterUser.trim());
      if (filterAction.trim()) params.set("action", filterAction.trim());
      params.set("limit", String(limit));
      const res = await fetch(`${base}/security/audit-log?${params.toString()}`);
      if (res.status === 403 || res.status === 401) {
        setErrorMsg("Access denied — Admin role required.");
        setViewState("error");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const data = json.data ?? json;
      setEntries(Array.isArray(data.entries) ? data.entries : []);
      setTotal(typeof data.total === "number" ? data.total : (data.entries?.length ?? 0));
      setViewState(Array.isArray(data.entries) && data.entries.length === 0 ? "empty" : "success");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load audit log");
      setViewState("error");
    }
  }, [filterUser, filterAction, limit]);

  useEffect(() => {
    if (user?.role === "admin") {
      fetchAuditLog();
    }
  }, [user, fetchAuditLog]);

  if (user && user.role !== "admin") {
    return (
      <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <Shield size={40} style={{ color: "var(--text-muted)" }} />
          <h2 className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>Access Denied</h2>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Admin role required to view the audit log.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
      <div className="p-6 max-w-6xl mx-auto space-y-5">
        {/* Header */}
        <header className="flex items-center gap-3">
          <ScrollText size={26} style={{ color: "var(--accent)" }} />
          <div>
            <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Audit Log</h1>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              System-wide user action history · Admin only
            </p>
          </div>
        </header>

        {/* Filter bar */}
        <div className="flex flex-wrap gap-3 p-4 rounded-lg" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <div className="flex items-center gap-2 flex-1 min-w-40">
            <Search size={14} style={{ color: "var(--text-muted)" }} />
            <input
              className="flex-1 bg-transparent text-sm outline-none"
              style={{ color: "var(--text-primary)" }}
              placeholder="Filter by user ID…"
              value={filterUser}
              onChange={(e) => setFilterUser(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2 flex-1 min-w-40">
            <input
              className="flex-1 rounded px-2 py-1 text-sm"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              placeholder="Filter by action…"
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
            />
          </div>
          <select
            className="rounded px-2 py-1 text-sm"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          >
            <option value={50}>50 rows</option>
            <option value={100}>100 rows</option>
            <option value={250}>250 rows</option>
            <option value={500}>500 rows</option>
          </select>
          <button
            onClick={fetchAuditLog}
            disabled={viewState === "loading"}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded text-white disabled:opacity-50 transition-colors"
            style={{ background: "var(--accent)" }}
            title={viewState === "loading" ? "unavailable: loading" : "Refresh audit log"}
          >
            <RefreshCw size={13} className={viewState === "loading" ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>

        {/* Summary */}
        {viewState === "success" && (
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Showing {entries.length} of {total} entries
          </p>
        )}

        <StateWrapper
          state={viewState}
          moduleName="Audit Log"
          loadingMessage="Loading audit log entries…"
          emptyTitle="No audit entries"
          emptyDescription="No log entries match the current filters."
          errorInfo={{ code: "AUDIT_ERROR", message: errorMsg, recoverable: true }}
          onRetry={fetchAuditLog}
        >
          <div className="overflow-x-auto rounded-lg" style={{ border: "1px solid var(--border)" }}>
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr style={{ background: "var(--bg-surface)", borderBottom: "1px solid var(--border)" }}>
                  <th className="text-left px-3 py-2.5 font-semibold" style={{ color: "var(--text-muted)" }}>Timestamp</th>
                  <th className="text-left px-3 py-2.5 font-semibold" style={{ color: "var(--text-muted)" }}>User</th>
                  <th className="text-left px-3 py-2.5 font-semibold" style={{ color: "var(--text-muted)" }}>Action</th>
                  <th className="text-left px-3 py-2.5 font-semibold" style={{ color: "var(--text-muted)" }}>Resource</th>
                  <th className="text-left px-3 py-2.5 font-semibold" style={{ color: "var(--text-muted)" }}>IP</th>
                  <th className="text-left px-3 py-2.5 font-semibold" style={{ color: "var(--text-muted)" }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <>
                    <tr
                      key={entry.id}
                      className="transition-colors"
                      style={{ borderBottom: "1px solid var(--border)" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-elevated)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                    >
                      <td className="px-3 py-2 whitespace-nowrap font-mono" style={{ color: "var(--text-muted)" }}>
                        {formatDate(entry.created_at)}
                      </td>
                      <td className="px-3 py-2 font-mono" style={{ color: "var(--text-primary)" }}>
                        {entry.user_id}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className="px-1.5 py-0.5 rounded text-white text-[10px] font-semibold"
                          style={{ background: actionColor(entry.action) }}
                        >
                          {entry.action}
                        </span>
                      </td>
                      <td className="px-3 py-2" style={{ color: "var(--text-secondary)" }}>
                        <span>{entry.resource_type}</span>
                        {entry.resource_id && (
                          <span className="ml-1 font-mono text-[10px]" style={{ color: "var(--text-muted)" }}>
                            #{entry.resource_id}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 font-mono" style={{ color: "var(--text-muted)" }}>
                        {entry.ip_address ?? "—"}
                      </td>
                      <td className="px-3 py-2">
                        {entry.details && Object.keys(entry.details).length > 0 ? (
                          <button
                            className="flex items-center gap-1 text-[10px] underline"
                            style={{ color: "var(--accent)" }}
                            onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                            aria-expanded={expandedId === entry.id}
                          >
                            <ChevronDown
                              size={10}
                              className={`transition-transform ${expandedId === entry.id ? "rotate-180" : ""}`}
                            />
                            {expandedId === entry.id ? "Hide" : "Show"}
                          </button>
                        ) : (
                          <span style={{ color: "var(--text-muted)" }}>—</span>
                        )}
                      </td>
                    </tr>
                    {expandedId === entry.id && entry.details && (
                      <tr key={`${entry.id}-detail`} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td colSpan={6} className="px-3 py-2" style={{ background: "var(--bg-surface)" }}>
                          <pre className="text-[10px] font-mono whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>
                            {JSON.stringify(entry.details, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </StateWrapper>
      </div>
    </div>
  );
}
