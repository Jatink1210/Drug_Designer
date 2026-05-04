/** ExportCenterPage — Centralized export surface for all artifacts (§28, §71). */

import { useState, useEffect } from "react";
import { exportsListAPI, exportCreateAPI, exportDownloadAPI, ensureApiBase } from "@/lib/api";
import StateWrapper, { type ViewState } from "@/components/ui/StateWrapper";
import {
  Download,
  FileText,
  Table2,
  Network,
  FlaskConical,
  Archive,
  Plus,
  Loader2,
} from "lucide-react";

interface ExportRecord {
  id: string;
  format: string;
  title: string;
  status: string;
  created_at?: string;
  file_size_bytes?: number;
}

interface ExportGroup {
  category: string;
  icon: React.ReactNode;
  items: ExportRecord[];
}

function groupExports(records: ExportRecord[]): ExportGroup[] {
  const map: Record<string, ExportRecord[]> = {};
  for (const r of records) {
    const cat = formatToCategory(r.format);
    (map[cat] ??= []).push(r);
  }
  return Object.entries(map).map(([category, items]) => ({
    category,
    icon: categoryIcon(category),
    items,
  }));
}

function formatToCategory(fmt: string): string {
  switch (fmt) {
    case "pdf": case "docx": return "Decision Dossiers";
    case "csv": return "Evidence Tables";
    case "graphml": case "cytoscape": return "Graph Snapshots";
    case "sdf": case "pdb": return "Molecule Exports";
    case "png": return "Media Exports";
    default: return "General Exports";
  }
}

function categoryIcon(cat: string): React.ReactNode {
  switch (cat) {
    case "Decision Dossiers": return <FileText size={16} />;
    case "Evidence Tables": return <Table2 size={16} />;
    case "Graph Snapshots": return <Network size={16} />;
    case "Molecule Exports": return <FlaskConical size={16} />;
    default: return <Archive size={16} />;
  }
}

export default function ExportCenterPage() {
  const [groups, setGroups] = useState<ExportGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchExports = async () => {
    setFetchError(null);
    try {
      const data = await exportsListAPI();
      const records = (data as unknown as ExportRecord[]) || [];
      setGroups(records.length > 0 ? groupExports(records) : []);
    } catch (err: unknown) {
      setFetchError(err instanceof Error ? err.message : "Failed to load exports");
      setGroups([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchExports(); }, []);

  const handleDownload = async (item: ExportRecord) => {
    if (item.status === "completed") {
      await exportDownloadAPI(item.id);
    }
  };

  const handleNewExport = async () => {
    setCreating(true);
    setCreateError(null);
    try {
      await exportCreateAPI({ format: "json", scope: {}, title: "Quick Export" });
      await fetchExports();
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Export creation failed");
    }
    setCreating(false);
  };

  return (
    <div
      className="flex-1 overflow-y-auto p-8"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="flex items-center justify-between mb-1">
        <h1
          className="text-xl"
          style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
        >
          Export Center
        </h1>
        <button
          onClick={handleNewExport}
          disabled={creating}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg text-white transition-colors disabled:opacity-50"
          style={{ background: "var(--accent)" }}
        >
          {creating ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
          New Export
        </button>
      </div>
      <p className="text-xs mb-6" style={{ color: "var(--text-muted)" }}>
        Download dossiers, evidence tables, graph snapshots, and reproducibility
        traces.
      </p>

      {fetchError && (
        <div className="rounded-lg border p-4 flex items-center gap-3 mb-4"
          style={{ borderColor: "#ef4444", background: "rgba(239,68,68,0.08)" }}>
          <span className="text-sm" style={{ color: "#ef4444" }}>{fetchError}</span>
          <button onClick={fetchExports}
            className="ml-auto px-3 py-1 rounded text-xs font-medium bg-red-100 text-red-700 hover:bg-red-200">
            Retry
          </button>
        </div>
      )}

      {createError && (
        <div className="rounded-lg border p-3 flex items-center gap-2 mb-4"
          style={{ borderColor: "#f59e0b", background: "rgba(245,158,11,0.08)" }}>
          <span className="text-xs" style={{ color: "#d97706" }}>{createError}</span>
          <button onClick={() => setCreateError(null)}
            className="ml-auto text-amber-500 hover:text-amber-700 text-xs">×</button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        groups.map((group) => (
          <div key={group.category} className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span style={{ color: "var(--text-muted)" }}>{group.icon}</span>
              <span
                className="text-[10px] font-bold uppercase tracking-widest"
                style={{ color: "var(--text-muted)" }}
              >
                {group.category}
              </span>
            </div>

            {group.items.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-4 py-3 px-4 mb-1 transition-colors"
                style={{ borderBottom: "1px solid var(--border)" }}
              >
                <div className="flex-1">
                  <div className="text-sm font-semibold">{item.title || `Export ${item.id.slice(0, 8)}`}</div>
                  <div
                    className="text-[11px]"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {item.format?.toUpperCase()} · {item.status}
                    {item.created_at && ` · ${new Date(item.created_at).toLocaleDateString()}`}
                    {item.file_size_bytes != null && ` · ${(item.file_size_bytes / 1024).toFixed(0)} KB`}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {item.status === "completed" && (
                    <button
                      onClick={() => handleDownload(item)}
                      className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-semibold rounded transition-colors"
                      style={{
                        border: "1px solid var(--border)",
                        color: "var(--accent)",
                        background: "var(--bg-elevated)",
                      }}
                    >
                      <Download size={10} />
                      Download
                    </button>
                  )}
                  {item.status === "pending" && (
                    <span className="text-[10px] text-[var(--text-muted)]">Processing...</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  );
}
