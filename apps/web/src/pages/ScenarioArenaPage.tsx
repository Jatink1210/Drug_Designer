/** ScenarioArenaPage — Scenario Simulation & Comparison Arena (§72 #12, §43).
 *
 * Allows users to define multiple exploration scenarios with different weight
 * profiles, compare projected outcomes side-by-side, and export comparative
 * scorecards.  Backed by SynthArena sessions with scenario add/score APIs.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Layers,
  Plus,
  Play,
  Trash2,
  Download,
  Loader2,
  AlertTriangle,
  BarChart3,
} from "lucide-react";
import {
  synthArenaCreateSessionAPI,
  synthArenaListSessionsAPI,
  synthArenaGetSessionAPI,
  synthArenaAddScenarioAPI,
  synthArenaExportSessionAPI,
} from "../lib/api";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";

/* ── Types ─────────────────────────────────────────────── */
interface Scenario {
  title: string;
  weights: Record<string, number>;
}

const DEFAULT_WEIGHTS: Record<string, number> = {
  genetic: 0.3,
  tractability: 0.2,
  safety: 0.2,
  novelty: 0.15,
  literature: 0.15,
};

/* ── Page Component ────────────────────────────────────── */
export default function ScenarioArenaPage() {
  const qc = useQueryClient();

  /* session list */
  const {
    data: sessions,
    isLoading: sessionsLoading,
    error: sessionsError,
  } = useQuery({
    queryKey: ["scenario-sessions"],
    queryFn: () => synthArenaListSessionsAPI(),
  });

  /* active session */
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const {
    data: activeSession,
    isLoading: sessionLoading,
  } = useQuery({
    queryKey: ["scenario-session", activeSessionId],
    queryFn: () => synthArenaGetSessionAPI(activeSessionId!),
    enabled: !!activeSessionId,
  });

  /* create session mutation */
  const createSession = useMutation({
    mutationFn: () => synthArenaCreateSessionAPI(),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["scenario-sessions"] });
      const id = (res as Record<string, unknown>)?.id ?? (res as Record<string, unknown>)?.session_id;
      if (typeof id === "string") setActiveSessionId(id);
    },
  });

  /* add scenario form state */
  const [scenarioTitle, setScenarioTitle] = useState("");
  const [weights, setWeights] = useState<Record<string, number>>({ ...DEFAULT_WEIGHTS });

  const addScenario = useMutation({
    mutationFn: (scenario: Scenario) =>
      synthArenaAddScenarioAPI(activeSessionId!, scenario as unknown as Record<string, unknown>),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scenario-session", activeSessionId] });
      setScenarioTitle("");
      setWeights({ ...DEFAULT_WEIGHTS });
    },
  });

  const exportSession = useMutation({
    mutationFn: () => synthArenaExportSessionAPI(activeSessionId!, "json"),
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `scenario_session_${activeSessionId!.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  const handleAddScenario = () => {
    if (!scenarioTitle.trim() || !activeSessionId) return;
    addScenario.mutate({ title: scenarioTitle.trim(), weights });
  };

  const updateWeight = (key: string, val: number) => {
    setWeights((prev) => ({ ...prev, [key]: Math.max(0, Math.min(1, val)) }));
  };

  const sessionList = Array.isArray(sessions) ? sessions : [];

  const viewState: ViewState =
    sessionsLoading ? "loading" :
    sessionsError ? "error" :
    sessionList.length === 0 ? "empty" :
    "success";

  /* ── Render ──────────────────────────────────────────── */
  return (
    <StateWrapper
      state={viewState}
      moduleName="Scenario Arena"
      emptyTitle="No scenario sessions"
      emptyDescription="Create a new session to define exploration scenarios with different weight profiles."
      errorInfo={sessionsError ? { code: "FETCH_ERROR", message: String(sessionsError) } : undefined}
      onRetry={sessionsError ? () => window.location.reload() : undefined}
    >
    <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--bg-app)" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Layers size={20} style={{ color: "var(--accent)" }} />
            <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
              Scenario Arena
            </h1>
          </div>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Define exploration scenarios with different weight profiles and compare projected outcomes.
          </p>
        </div>
        <button
          onClick={() => createSession.mutate()}
          disabled={createSession.isPending}
          className="flex items-center gap-2 rounded px-4 py-2 text-sm font-medium"
          style={{ background: "var(--accent)", color: "#fff" }}
          aria-label="Create new scenario session"
        >
          {createSession.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          New Session
        </button>
      </div>

      {/* Error */}
      {sessionsError && (
        <div
          className="rounded-lg border p-4 flex items-start gap-3 mb-4"
          style={{ borderColor: "#ef4444", background: "rgba(239,68,68,0.08)" }}
          role="alert"
        >
          <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: "#ef4444" }} />
          <p className="text-sm" style={{ color: "#ef4444" }}>
            Failed to load sessions. Check backend connectivity.
          </p>
        </div>
      )}

      {/* Loading */}
      {sessionsLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={24} className="animate-spin" style={{ color: "var(--accent)" }} />
        </div>
      )}

      {/* Session list */}
      {!sessionsLoading && !sessionsError && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: session list */}
          <div className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: "var(--text-muted)" }}>
              Sessions
            </h2>
            {Array.isArray(sessions) && sessions.length === 0 && (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                No sessions yet. Create one to start comparing scenarios.
              </p>
            )}
            {Array.isArray(sessions) &&
              sessions.map((s: Record<string, unknown>) => {
                const sid = (s.id ?? s.session_id) as string;
                return (
                  <button
                    key={sid}
                    onClick={() => setActiveSessionId(sid)}
                    className="w-full text-left rounded-lg border p-3 transition-colors"
                    style={{
                      borderColor: sid === activeSessionId ? "var(--accent)" : "var(--border)",
                      background: sid === activeSessionId ? "rgba(59,130,246,0.06)" : "var(--bg-surface)",
                    }}
                    aria-label={`Select session ${sid}`}
                  >
                    <span className="text-sm font-medium block truncate" style={{ color: "var(--text-primary)" }}>
                      Session {sid.slice(0, 8)}
                    </span>
                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                      {(s.scenario_count as number) ?? 0} scenarios
                    </span>
                  </button>
                );
              })}
          </div>

          {/* Right: active session detail */}
          <div className="lg:col-span-2">
            {!activeSessionId && (
              <div className="rounded-lg border border-dashed p-12 text-center" style={{ borderColor: "var(--border)" }}>
                <BarChart3 size={32} className="mx-auto mb-3" style={{ color: "var(--text-muted)" }} />
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                  Select or create a session to add and compare scenarios.
                </p>
              </div>
            )}

            {activeSessionId && (
              <div className="space-y-4">
                {/* Session header */}
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                    Session {activeSessionId.slice(0, 8)}
                  </h2>
                  <button
                    onClick={() => exportSession.mutate()}
                    disabled={exportSession.isPending}
                    className="flex items-center gap-1.5 text-xs rounded px-3 py-1.5 border"
                    style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
                    aria-label="Export session"
                  >
                    {exportSession.isPending ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                    Export
                  </button>
                </div>

                {/* Existing scenarios */}
                {sessionLoading && (
                  <div className="flex justify-center py-8">
                    <Loader2 size={20} className="animate-spin" style={{ color: "var(--accent)" }} />
                  </div>
                )}
                {activeSession && (
                  <div className="space-y-2">
                    {(
                      (activeSession as Record<string, unknown>).scenarios as Record<string, unknown>[] | undefined
                    )?.map((sc, i) => (
                      <div
                        key={i}
                        className="rounded-lg border p-3 group"
                        style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                            {(sc.title as string) || `Scenario ${i + 1}`}
                          </span>
                          <button
                            onClick={() => {
                              // Remove scenario by index (update local scenarios)
                              const scenarios = [...((activeSession as Record<string, unknown>).scenarios as Record<string, unknown>[])];
                              scenarios.splice(i, 1);
                              // Optimistically update the cache
                              qc.setQueryData(["scenario-session", activeSessionId], {
                                ...activeSession as Record<string, unknown>,
                                scenarios,
                              });
                            }}
                            className="opacity-0 group-hover:opacity-100 transition-opacity rounded p-1 hover:bg-red-50"
                            title="Remove scenario"
                          >
                            <Trash2 size={12} style={{ color: "#ef4444" }} />
                          </button>
                        </div>
                        {sc.weights != null && (
                          <div className="flex flex-wrap gap-2 mt-1">
                            {Object.entries(sc.weights as Record<string, number>).map(([k, v]) => (
                              <span
                                key={k}
                                className="text-xs rounded px-2 py-0.5"
                                style={{ background: "var(--bg-app)", color: "var(--text-muted)" }}
                              >
                                {k}: {String(v)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )) ?? (
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        No scenarios added yet.
                      </p>
                    )}
                  </div>
                )}

                {/* Add scenario form */}
                <div
                  className="rounded-lg border p-4"
                  style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
                >
                  <h3 className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: "var(--accent)" }}>
                    Add Scenario
                  </h3>
                  <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-muted)" }}>
                    Title
                  </label>
                  <input
                    type="text"
                    value={scenarioTitle}
                    onChange={(e) => setScenarioTitle(e.target.value)}
                    placeholder="e.g. Conservative Safety-First"
                    className="rounded border px-3 py-1.5 text-sm w-full mb-3"
                    style={{
                      borderColor: "var(--border)",
                      background: "var(--bg-app)",
                      color: "var(--text-primary)",
                    }}
                    aria-label="Scenario title"
                  />
                  <label className="text-xs font-medium block mb-2" style={{ color: "var(--text-muted)" }}>
                    Weight Profile
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
                    {Object.entries(weights).map(([key, val]) => (
                      <div key={key}>
                        <label className="text-xs block mb-0.5 capitalize" style={{ color: "var(--text-muted)" }}>
                          {key}
                        </label>
                        <input
                          type="number"
                          step={0.05}
                          min={0}
                          max={1}
                          value={val}
                          onChange={(e) => updateWeight(key, parseFloat(e.target.value) || 0)}
                          className="rounded border px-2 py-1 text-xs w-full"
                          style={{
                            borderColor: "var(--border)",
                            background: "var(--bg-app)",
                            color: "var(--text-primary)",
                          }}
                          aria-label={`${key} weight`}
                        />
                      </div>
                    ))}
                  </div>
                  {(() => {
                    const sum = Object.values(weights).reduce((a, b) => a + b, 0);
                    if (Math.abs(sum - 1.0) > 0.01) {
                      return (
                        <div className="flex items-center gap-1.5 mb-3 text-xs px-2 py-1 rounded"
                          style={{ background: "rgba(245,158,11,0.1)", color: "#d97706" }}>
                          <AlertTriangle size={10} />
                          Weights sum to {sum.toFixed(2)} — recommended total is 1.00
                        </div>
                      );
                    }
                    return null;
                  })()}
                  <button
                    onClick={handleAddScenario}
                    disabled={addScenario.isPending || !scenarioTitle.trim()}
                    className="flex items-center gap-2 rounded px-4 py-2 text-sm font-medium"
                    style={{
                      background: "var(--accent)",
                      color: "#fff",
                      opacity: addScenario.isPending || !scenarioTitle.trim() ? 0.5 : 1,
                    }}
                    aria-label="Add scenario"
                  >
                    {addScenario.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                    Add Scenario
                  </button>
                  {addScenario.isError && (
                    <p className="text-xs mt-2" style={{ color: "#ef4444" }}>
                      Failed to add scenario. Please retry.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
    </StateWrapper>
  );
}
