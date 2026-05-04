/** OperationsPage — Merged Projects & Runs management. */

import { useState } from "react";
import { FolderOpen, Play, BarChart3 } from "lucide-react";

// Dynamically import the actual pages
import ProjectsPage from "./ProjectsPage";
import RunsPage from "./RunsPage";

const TABS = [
  { id: "projects", label: "Projects", icon: FolderOpen },
  { id: "runs", label: "Runs", icon: Play },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function OperationsPage() {
  const [tab, setTab] = useState<TabId>("projects");

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Tab bar */}
      <div
        className="shrink-0 flex items-center gap-1 px-4 pt-3 pb-0 border-b"
        style={{ borderColor: "var(--border)", background: "var(--bg-app)" }}
      >
        <BarChart3 size={16} className="text-[var(--accent)] mr-2" />
        <span className="text-sm font-semibold text-[var(--text-primary)] mr-4">
          Operations
        </span>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors border-b-2"
            style={{
              color: tab === t.id ? "var(--accent)" : "var(--text-muted)",
              borderColor: tab === t.id ? "var(--accent)" : "transparent",
            }}
          >
            <t.icon size={13} />
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {tab === "projects" && <ProjectsPage />}
        {tab === "runs" && <RunsPage />}
      </div>
    </div>
  );
}
