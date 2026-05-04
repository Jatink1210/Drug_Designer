/** CommandPalette — ⌘K global search + Agentic Auto-Pilot (§50). */

import { useState, useEffect, useRef } from "react";
import { Search, X, ArrowRight, Zap } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

interface Command {
  label: string;
  path: string;
  section: string;
}

const COMMANDS: Command[] = [
  // Discovery
  { label: "Cockpit", path: "/workspace", section: "Discovery" },
  { label: "Evidence Search", path: "/evidence/search", section: "Discovery" },
  { label: "Disease Workbench", path: "/disease", section: "Discovery" },
  { label: "Target Prioritization", path: "/targets", section: "Discovery" },

  // Analysis
  { label: "Knowledge Graph", path: "/graph", section: "Analysis" },
  { label: "Pathways", path: "/pathways", section: "Analysis" },
  { label: "PPI Network", path: "/ppi", section: "Analysis" },
  { label: "Gene/Protein Explorer", path: "/gene-explorer", section: "Analysis" },
  { label: "Interaction Maps", path: "/interaction-maps", section: "Analysis" },
  { label: "Mechanism Maps", path: "/mechanism-maps", section: "Analysis" },
  { label: "3D Structures", path: "/structure", section: "Analysis" },
  { label: "Design Studio", path: "/design", section: "Analysis" },
  { label: "ADMET Panels", path: "/admet-panels", section: "Analysis" },
  { label: "Structure Reports", path: "/structure-reports", section: "Analysis" },

  // Workflows
  { label: "Translational Research", path: "/translational", section: "Workflows" },
  { label: "SynthArena", path: "/syntharena", section: "Workflows" },
  { label: "Scenario Arena", path: "/scenario-arena", section: "Workflows" },
  { label: "Contradictions", path: "/evidence/contradictions", section: "Workflows" },
  { label: "PICO Verification", path: "/pico", section: "Workflows" },

  // Labs
  { label: "Research Labs", path: "/labs", section: "Labs" },
  { label: "Target Discovery Lab", path: "/labs/target-discovery", section: "Labs" },
  { label: "Pocket Lab", path: "/labs/pocket", section: "Labs" },
  { label: "Molecule Generation Lab", path: "/labs/molecule-generation", section: "Labs" },
  { label: "ADMET Lab", path: "/labs/admet", section: "Labs" },
  { label: "Retrosynthesis Lab", path: "/labs/retrosynthesis", section: "Labs" },
  { label: "Vaccine Lab", path: "/labs/vaccine", section: "Labs" },
  { label: "Metabolic Engineering Lab", path: "/labs/metabolic-engineering", section: "Labs" },
  { label: "Pharmacogenomics Lab", path: "/labs/pharmacogenomics", section: "Labs" },

  // Output
  { label: "Decision Dossiers", path: "/dossiers", section: "Output" },
  { label: "Reports", path: "/reports", section: "Output" },
  { label: "System Logs", path: "/logs", section: "Output" },
  { label: "Media Library", path: "/media", section: "Output" },
  { label: "Export Center", path: "/exports", section: "Output" },
  { label: "Project Memory", path: "/memory", section: "Output" },

  // Evidence Detail
  { label: "Evidence Workspace", path: "/evidence", section: "Evidence" },
  { label: "Source Explorer", path: "/sources", section: "Evidence" },
  { label: "Saved Evidence", path: "/saved-evidence", section: "Evidence" },
  { label: "Query History", path: "/historical-queries", section: "Evidence" },
  { label: "Context Bundles", path: "/context-bundles", section: "Evidence" },

  // Platform
  { label: "Model Center", path: "/models", section: "Platform" },
  { label: "Runtime Center", path: "/runtime", section: "Platform" },
  { label: "Local Agent", path: "/runtime/local-agent", section: "Platform" },
  { label: "Hardware Status", path: "/runtime/hardware", section: "Platform" },
  { label: "Operations", path: "/operations", section: "Platform" },
  { label: "Settings", path: "/settings", section: "Platform" },

  // Projects & Runs
  { label: "Projects", path: "/projects", section: "Projects" },
  { label: "Runs & Jobs", path: "/runs", section: "Projects" },

  // Utility
  { label: "Entity Catalog", path: "/catalog", section: "Utility" },
  { label: "Data Manager", path: "/data", section: "Utility" },
  { label: "About & Diagnostics", path: "/about", section: "Utility" },
];

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const [dagLoading, setDagLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelected(0);
      setDagLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // §65 WCAG AA: Focus trap — keep Tab cycling within the palette when open
  useEffect(() => {
    if (!open) return;
    const handleTrap = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const palette = document.querySelector("[data-command-palette]") as HTMLElement | null;
      if (!palette) return;
      const focusable = palette.querySelectorAll<HTMLElement>(
        'input, button, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleTrap);
    return () => window.removeEventListener("keydown", handleTrap);
  }, [open]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        if (!open) onClose(); /* toggle via parent */
      }
      if (e.key === "Escape" && open) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const filtered = COMMANDS.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase()),
  );

  // §50: Show DAG Auto-Pilot option when query looks like a natural language prompt
  const showDagOption = query.trim().length > 10 && filtered.length === 0;

  const exec = (cmd: Command) => {
    navigate(cmd.path);
    onClose();
  };

  /** §50: Submit natural language prompt to DAG Planner endpoint.
   *  §50.3: Ghost Execution — the API creates a Run and returns run_id.
   *  Navigate to /runs/{run_id} so the user sees live DAG progress via WebSocket.
   */
  const submitDag = async () => {
    if (!query.trim() || dagLoading) return;
    setDagLoading(true);
    try {
      const base = (window as any).__API_BASE__ || "/api/v1";
      const res = await fetch(`${base}/dag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ prompt: query.trim(), auto_execute: true }),
      });
      if (res.ok) {
        const json = await res.json();
        const runId = json?.data?.run_id;
        onClose();
        // Navigate to the specific run so user sees live Ghost Execution progress
        navigate(runId ? `/runs/${runId}` : "/runs");
      }
    } catch { /* intentionally swallowed — degraded state handled by global error */ } finally {
      setDagLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelected((s) => Math.min(s + 1, filtered.length - (showDagOption ? 0 : 1)));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelected((s) => Math.max(s - 1, 0));
    }
    if (e.key === "Enter") {
      if (showDagOption && selected === 0) {
        submitDag();
      } else if (filtered[selected]) {
        exec(filtered[selected]);
      }
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      data-command-palette
    >
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" />
      <div
        className="relative glass-elevated rounded-xl w-[520px] overflow-hidden border"
        style={{ borderColor: "var(--border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center gap-3 px-4 py-3 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <Search size={16} className="text-[var(--text-muted)]" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Search workbenches, entities, commands…"
            className="flex-1 text-sm bg-transparent outline-none placeholder:text-[var(--text-muted)]"
          />
          <button onClick={onClose} className="p-1 rounded hover:bg-[var(--bg-inset)]">
            <X size={14} className="text-[var(--text-muted)]" />
          </button>
        </div>
        <div className="max-h-[300px] overflow-y-auto py-1">
          {/* §50: Agentic Auto-Pilot DAG planner option */}
          {showDagOption && (
            <button
              onClick={submitDag}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors ${selected === 0 ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-primary)] hover:bg-[var(--border-light)]"}`}
            >
              <Zap size={14} className="text-orange-500" />
              <span className="flex-1">
                {dagLoading ? "Planning DAG…" : `Auto-Pilot: "${query.trim().slice(0, 60)}${query.trim().length > 60 ? "…" : ""}"`}
              </span>
              <span className="text-[10px] text-orange-500 font-semibold">
                Agentic
              </span>
            </button>
          )}
          {filtered.length === 0 && !showDagOption && (
            <div className="px-4 py-6 text-center text-sm text-[var(--text-muted)]">
              No results
            </div>
          )}
          {filtered.map((cmd, i) => (
            <button
              key={cmd.path}
              onClick={() => exec(cmd)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors ${selected === i ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-primary)] hover:bg-[var(--border-light)]"}`}
            >
              <ArrowRight size={14} className="opacity-40" />
              <span className="flex-1">{cmd.label}</span>
              <span className="text-[10px] text-[var(--text-muted)]">
                {cmd.section}
              </span>
            </button>
          ))}
        </div>
        <div
          className="px-4 py-2 border-t text-[10px] text-[var(--text-muted)] flex gap-3"
          style={{ borderColor: "var(--border)" }}
        >
          <span>↑↓ Navigate</span>
          <span>↵ Open</span>
          <span>Esc Close</span>
        </div>
      </div>
    </div>
  );
}
