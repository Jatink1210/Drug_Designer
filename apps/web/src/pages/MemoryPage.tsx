/** MemoryPage (Notes) — Project notes and accumulated context (§77, §119). */

import { useMemo } from "react";
import { useProjectList } from "@/lib/hooks";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";

interface MemoryNote {
  id: string;
  text: string;
  created_at: number;
}

export default function MemoryPage() {
  const { data: projects, state, error, refetch } = useProjectList();

  const notes = useMemo(() => {
    const allNotes: MemoryNote[] = [];
    for (const p of Array.isArray(projects) ? projects : []) {
      if ((p as any).notes) allNotes.push(...(p as any).notes);
    }
    return allNotes;
  }, [projects]);

  const viewState: ViewState =
    state === "loading" ? "loading" :
    state === "error" ? "error" :
    notes.length === 0 ? "empty" :
    "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="Notes"
      emptyTitle="No notes yet"
      emptyDescription="Notes attached to projects will appear here."
      errorInfo={error ? { code: "FETCH_ERROR", message: error } : undefined}
      onRetry={error ? refetch : undefined}
    >
    <div className="flex-1 overflow-y-auto p-6">
      <h1 className="text-xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
        Notes
      </h1>
      <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
        Project notes, context objects, and session history.
      </p>
      {state === "loading" ? (
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>Loading…</p>
      ) : notes.length === 0 ? (
        <div className="rounded-lg border p-8 text-center" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            No memory notes yet. Notes attached to projects will appear here.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {notes.map((n) => (
            <li key={n.id} className="rounded-lg border p-3" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
              <p className="text-sm" style={{ color: "var(--text-primary)" }}>{n.text}</p>
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                {new Date(n.created_at * 1000).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
    </StateWrapper>
  );
}
