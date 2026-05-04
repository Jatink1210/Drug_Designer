/**
 * React Hooks — Drug Designer API & WebSocket Consumers
 *
 * These hooks abstract API calls and WebSocket subscriptions into
 * reusable, type-safe React primitives. They use the ResponseEnvelope
 * type (§78) to ensure every consumer handles degraded/error states.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import type {
  ResponseEnvelope,
  RunRecord,
  RunEvent,
  EvidenceItem,
  TargetRankingItem,
  DiseaseNormalizationResult,
  ProjectSummary,
  SourceHealth,
  ViewState,
} from "./types";
import { useSetPageConfidence } from "./PageConfidenceContext";

const API_BASE = "/api/v1";

// ── Generic Fetch Hook ──────────────────────────────────────

interface UseApiResult<T> {
  data: T | null;
  envelope: ResponseEnvelope<T> | null;
  state: ViewState;
  error: string | null;
  refetch: () => void;
}

function useApi<T>(url: string, options?: { skip?: boolean }): UseApiResult<T> {
  const [envelope, setEnvelope] = useState<ResponseEnvelope<T> | null>(null);
  const [state, setState] = useState<ViewState>("initial");
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (options?.skip) return;
    setState("loading");
    setError(null);
    try {
      const res = await fetch(`${API_BASE}${url}`, { credentials: "include", cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const env: ResponseEnvelope<T> = await res.json();
      setEnvelope(env);

      if (env.status === "error") {
        setState("error");
        setError(env.errors?.[0]?.message || "Unknown error");
      } else if (env.status === "degraded") {
        setState("degraded");
      } else if (
        !env.data ||
        (Array.isArray(env.data) && env.data.length === 0)
      ) {
        setState("empty");
      } else {
        setState("success");
      }
    } catch (err: any) {
      setState("error");
      setError(err.message || "Network error");
    }
  }, [url, options?.skip]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data: envelope?.data ?? null,
    envelope,
    state,
    error,
    refetch: fetchData,
  };
}

// ── Run Progress Hook (WebSocket) ───────────────────────────

interface RunProgress {
  runId: string;
  state: string;
  stage: string;
  progressPercent: number;
  message: string;
  sourcesCompleted: number;
  sourcesTotal: number;
  elapsedMs: number;
  degradedSources: string[];
  error?: string;
  isComplete: boolean;
}

function useRunProgress(runId: string | null): RunProgress | null {
  const [progress, setProgress] = useState<RunProgress | null>(null);
  const startTimeRef = useRef<number>(Date.now());

  useEffect(() => {
    if (!runId) return;

    startTimeRef.current = Date.now();
    let disposed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let socket: WebSocket | null = null;

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/runs/${encodeURIComponent(runId)}`;

    const connect = () => {
      if (disposed) return;
      socket = new WebSocket(wsUrl);

      socket.onmessage = (message) => {
        try {
          const event: RunEvent = JSON.parse(message.data);
          const p = event.payload || {};
          setProgress((prev) => ({
            runId,
            state: p.state || prev?.state || "RUNNING",
            stage: p.stage || prev?.stage || "",
            progressPercent: p.progress_pct ?? prev?.progressPercent ?? 0,
            message: p.message || p.error || prev?.message || "",
            sourcesCompleted: p.sources_completed ?? prev?.sourcesCompleted ?? 0,
            sourcesTotal: p.sources_total ?? prev?.sourcesTotal ?? 0,
            elapsedMs: Date.now() - startTimeRef.current,
            degradedSources: p.degraded_sources ?? prev?.degradedSources ?? [],
            error: event.event === "run.error" || event.event === "run.failed"
              ? (p.error || p.message || prev?.error)
              : prev?.error,
            isComplete: event.event === "run.complete" || event.event === "run.completed",
          }));
        } catch {
          // Ignore malformed websocket payloads and keep polling fallback alive.
        }
      };

      socket.onclose = () => {
        if (disposed) return;
        retryTimer = setTimeout(connect, 1000);
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      socket?.close(1000, "run progress cleanup");
    };
  }, [runId]);

  return progress;
}

// ── Domain Hooks ────────────────────────────────────────────

function useProject(projectId: string) {
  return useApi<ProjectSummary>(`/projects/${projectId}`);
}

function useProjectList() {
  return useApi<ProjectSummary[]>("/projects");
}

function useEvidenceSearch(query: string, projectId: string) {
  return useApi<EvidenceItem[]>(
    `/evidence/search?q=${encodeURIComponent(query)}&project_id=${projectId}`,
    {
      skip: !query,
    },
  );
}

function useTargetRankings(runId: string) {
  return useApi<TargetRankingItem[]>(`/targets/ranked?run_id=${runId}`);
}

function useDiseaseIntelligence(diseaseId: string) {
  return useApi<DiseaseNormalizationResult>(`/disease/${diseaseId}`);
}

function useSourceHealth() {
  return useApi<SourceHealth[]>("/sources/health");
}

function useRunHistory(projectId: string) {
  return useApi<RunRecord[]>(`/runs?project_id=${projectId}`);
}

// ── Additional Domain Hooks ─────────────────────────────────

function useJobsHistory() {
  const result = useApi<any>("/runs?limit=50");
  // /runs returns { runs: [...], pagination: {...} } — unwrap to flat array
  const runs = result.data?.runs ?? (Array.isArray(result.data) ? result.data : []);
  return { ...result, data: runs };
}

function usePICOItems() {
  return useApi<any[]>("/evidence/pico");
}

function useContradictions() {
  return useApi<any[]>("/evidence/contradictions");
}

function useGraphSample(limit = 25) {
  return useApi<any>(`/graph/sample?limit=${limit}`);
}

function useSynthArenaSessions() {
  return useApi<any[]>("/syntharena/sessions");
}

function useMoleculeLibrary() {
  return useApi<any[]>("/molecules/library");
}

function useRunDetail(runId: string) {
  return useApi<any>(`/runs/${runId}`, { skip: !runId });
}

// ── Mutations (POST/PUT/DELETE) ─────────────────────────────

interface UseMutationResult<TInput, TOutput> {
  execute: (input: TInput) => Promise<ResponseEnvelope<TOutput> | null>;
  loading: boolean;
  error: string | null;
}

function useMutation<TInput, TOutput>(
  method: "POST" | "PUT" | "DELETE",
  url: string,
): UseMutationResult<TInput, TOutput> {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(
    async (input: TInput) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}${url}`, {
          method,
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: method !== "DELETE" ? JSON.stringify(input) : undefined,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const env: ResponseEnvelope<TOutput> = await res.json();
        setLoading(false);
        return env;
      } catch (err: any) {
        setError(err.message);
        setLoading(false);
        return null;
      }
    },
    [method, url],
  );

  return { execute, loading, error };
}

// ── Convenience Mutation Hooks ──────────────────────────────

function useCreateRun() {
  return useMutation<
    { run_type: string; input: Record<string, unknown>; project_id: string },
    RunRecord
  >("POST", "/runs");
}

function useSaveEvidence() {
  return useMutation<
    { evidence_items: EvidenceItem[]; project_id: string },
    { saved_count: number }
  >("POST", "/evidence/save");
}

function usePageConfidence(envelope: ResponseEnvelope<any> | null) {
  const setConfidence = useSetPageConfidence();
  useEffect(() => {
    if (!envelope) { setConfidence(null); return; }
    const prov = envelope.provenance;
    const generatedAt = prov?.generated_at ? new Date(prov.generated_at) : null;
    const ageMs = generatedAt ? Date.now() - generatedAt.getTime() : null;
    const freshness = ageMs === null ? "unknown" as const : ageMs < 86400000 ? "current" as const : "stale" as const;
    const freshnessDetail = ageMs === null ? undefined : ageMs < 60000 ? "just now" : ageMs < 3600000 ? `${Math.round(ageMs / 60000)} min ago` : ageMs < 86400000 ? `${Math.round(ageMs / 3600000)}h ago` : `>${Math.round(ageMs / 86400000)}d old`;
    setConfidence({
      freshness,
      freshnessDetail,
      sourceCount: prov?.sources?.length ?? 0,
      sourcesQueried: prov?.sources,
    });
    return () => setConfidence(null);
  }, [envelope, setConfidence]);
}

export {
  useApi,
  useRunProgress,
  useProject,
  useProjectList,
  useEvidenceSearch,
  useTargetRankings,
  useDiseaseIntelligence,
  useSourceHealth,
  useRunHistory,
  useJobsHistory,
  usePICOItems,
  useContradictions,
  useGraphSample,
  useSynthArenaSessions,
  useMoleculeLibrary,
  useRunDetail,
  useMutation,
  useCreateRun,
  useSaveEvidence,
  usePageConfidence,
};
