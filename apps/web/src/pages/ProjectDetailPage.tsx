/** ProjectDetailPage — Project detail view (§20, §77 /projects/:projectId). */

import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Loader2, FolderArchive, Clock, FileText, Activity } from "lucide-react";
import { ensureApiBase } from "@/lib/api";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";

interface ProjectDetail {
  id: string;
  name: string;
  description: string;
  tags: string[];
  created_at: number;
  updated_at: number;
  memory: Record<string, unknown>;
  notes: { id: string; text: string; created_at: number }[];
  runs: { run_id: string; run_type: string; state: string; created_at: string }[];
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [errorMsg, setErrorMsg] = useState("");
  const [noteText, setNoteText] = useState("");

  useEffect(() => {
    if (!projectId) return;
    (async () => {
      setViewState("loading");
      try {
        const base = await ensureApiBase();
        const res = await fetch(`${base}/projects/${projectId}`);
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        const envelope = await res.json();
        setProject(envelope.data ?? envelope);
        setViewState("success");
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : "Failed to load project");
        setViewState("error");
      }
    })();
  }, [projectId]);

  const addNote = async () => {
    if (!noteText.trim() || !projectId) return;
    try {
      const base = await ensureApiBase();
      await fetch(`${base}/projects/${projectId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: noteText }),
      });
      setNoteText("");
      // reload
      const res = await fetch(`${base}/projects/${projectId}`);
      if (res.ok) {
        const envelope = await res.json();
        setProject(envelope.data ?? envelope);
      }
    } catch {
      /* best-effort */
    }
  };

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <Link to="/projects" className="inline-flex items-center gap-1 text-sm hover:underline" style={{ color: "var(--accent)" }}>
        <ArrowLeft size={14} /> Back to Projects
      </Link>

      <StateWrapper
        state={viewState}
        moduleName="Project Detail"
        emptyTitle="Project not found"
        emptyDescription="The requested project could not be located."
        errorInfo={{ code: "PROJECT_LOAD_ERROR", message: errorMsg, recoverable: true }}
        onRetry={() => window.location.reload()}
      >
        {project && (
          <>
            <header className="flex items-center gap-3">
              <FolderArchive size={28} style={{ color: "var(--accent)" }} />
              <div>
                <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{project.name}</h1>
                <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{project.description}</p>
              </div>
            </header>

            <div className="grid grid-cols-3 gap-4 text-sm">
              <div className="rounded-lg p-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                <Clock size={14} className="inline mr-1" style={{ color: "var(--text-muted)" }} />
                Created: {new Date(project.created_at).toLocaleDateString()}
              </div>
              <div className="rounded-lg p-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                <Activity size={14} className="inline mr-1" style={{ color: "var(--accent)" }} />
                Runs: {project.runs?.length ?? 0}
              </div>
              <div className="rounded-lg p-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                <FileText size={14} className="inline mr-1" style={{ color: "var(--success)" }} />
                Notes: {project.notes?.length ?? 0}
              </div>
            </div>

            {/* Notes section */}
            <section>
              <h2 className="text-lg font-semibold mb-2">Project Notes</h2>
              <div className="flex gap-2 mb-3">
                <input
                  className="flex-1 rounded px-3 py-1.5 text-sm"
                  style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
                  placeholder="Add a note…"
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addNote()}
                />
                <button onClick={addNote} className="px-3 py-1.5 text-sm text-white rounded transition-colors" style={{ background: "var(--accent)" }}>
                  Add
                </button>
              </div>
              {project.notes?.map((n) => (
                <div key={n.id} className="rounded-lg p-2 mb-1 text-sm" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                  {n.text}
                  <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>{new Date(n.created_at).toLocaleString()}</span>
                </div>
              ))}
            </section>

            {/* Recent runs */}
            <section>
              <h2 className="text-lg font-semibold mb-2">Recent Runs</h2>
              {(project.runs?.length ?? 0) === 0 ? (
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>No runs yet for this project.</p>
              ) : (
                <div className="space-y-1">
                  {project.runs.map((r) => (
                    <Link
                      key={r.run_id}
                      to={`/runs/${r.run_id}`}
                      className="block rounded-lg p-2 text-sm transition-colors"
                      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
                    >
                      <span className="font-medium">{r.run_type}</span>
                      <span className="ml-2" style={{ color: "var(--text-secondary)" }}>{r.state}</span>
                      <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>{r.created_at}</span>
                    </Link>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </StateWrapper>
    </div>
    </div>
  );
}
