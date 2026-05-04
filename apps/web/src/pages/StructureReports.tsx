import { useState, useEffect } from "react";
import { NotebookPen, Download, RefreshCw, ExternalLink, Box, FileText, Filter } from "lucide-react";
import { useNavigate } from "react-router-dom";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "../lib/types";
import { ensureApiBase } from "@/lib/api";

interface StructureReport {
  id: string;
  pdb_id: string;
  title: string;
  resolution?: string;
  method?: string;
  organism?: string;
  alphafold_confidence?: number;
  created_at?: string;
  pocket_count?: number;
}

export default function StructureReports() {
  const navigate = useNavigate();
  const [reports, setReports] = useState<StructureReport[]>([]);
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [filterText, setFilterText] = useState("");

  const fetchReports = () => {
    setViewState("loading");
    ensureApiBase().then((base) =>
      fetch(`${base}/structure/search?q=protein&limit=50`, { credentials: "include" })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((env) => {
          const items = env?.data?.structures ?? env?.data?.results ?? env?.data ?? [];
          const mapped: StructureReport[] = (Array.isArray(items) ? items : []).map(
            (s: Record<string, unknown>) => ({
              id: String(s.pdb_id || s.id || s.entry_id || ""),
              pdb_id: String(s.pdb_id || s.entry_id || s.id || ""),
              title: String(s.title || s.name || s.struct_title || "Untitled Structure"),
              resolution: s.resolution ? `${s.resolution} Å` : undefined,
              method: s.experimental_method ? String(s.experimental_method) : s.method ? String(s.method) : undefined,
              organism: s.organism ? String(s.organism) : undefined,
              alphafold_confidence: typeof s.plddt === "number" ? s.plddt : typeof s.confidence === "number" ? s.confidence : undefined,
              created_at: s.created_at ? String(s.created_at) : s.deposition_date ? String(s.deposition_date) : undefined,
              pocket_count: typeof s.pocket_count === "number" ? s.pocket_count : undefined,
            }),
          );
          setReports(mapped);
          setViewState(mapped.length === 0 ? "empty" : "success");
        })
        .catch(() => setViewState("error")),
    );
  };

  useEffect(() => { fetchReports(); }, []);

  const filtered = reports.filter(
    (r) =>
      r.pdb_id.toLowerCase().includes(filterText.toLowerCase()) ||
      r.title.toLowerCase().includes(filterText.toLowerCase()),
  );

  return (
    <StateWrapper
      state={viewState}
      moduleName="Structure Reports"
      emptyTitle="No structure reports"
      emptyDescription="Analyze a protein structure to generate reports."
      onRetry={fetchReports}
    >
      <div
        className="flex-1 overflow-y-auto"
        style={{ background: "var(--bg-app)" }}
      >
        <div className="max-w-[1100px] mx-auto px-6 py-5">
          {/* Header */}
          <div className="mb-5 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
            <div>
              <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
                Structure Reports
              </h1>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                PDB resolution scores, AlphaFold confidences, pocket detection results, and structural analysis logs.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={fetchReports}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-medium border transition-all hover:shadow-sm"
                style={{ borderColor: "var(--border)", color: "var(--text-secondary)", background: "var(--bg-surface)" }}
              >
                <RefreshCw size={12} /> Refresh
              </button>
              <button
                onClick={() => navigate("/structure")}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-medium text-white transition-all hover:shadow-sm"
                style={{ background: "var(--accent)" }}
              >
                <Box size={12} /> Open Structure Viewer
              </button>
            </div>
          </div>

          {/* Filter */}
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg border mb-4"
            style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}
          >
            <Filter size={13} style={{ color: "var(--text-muted)" }} />
            <input
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              placeholder="Filter by PDB ID or title…"
              className="flex-1 text-[12px] bg-transparent outline-none"
              style={{ color: "var(--text-primary)" }}
            />
            <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
              {filtered.length} of {reports.length}
            </span>
          </div>

          {/* Reports grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filtered.map((r) => (
              <div
                key={r.id}
                className="flex flex-col gap-3 p-4 rounded-lg border transition-all hover:shadow-md cursor-pointer group"
                style={{ borderColor: "var(--border)", background: "var(--bg-elevated)" }}
                onClick={() => navigate(`/structure/${r.pdb_id}`)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                      style={{ background: "var(--accent-subtle, rgba(59,130,246,0.1))" }}
                    >
                      <Box size={16} style={{ color: "var(--accent)" }} />
                    </div>
                    <div>
                      <div className="text-[13px] font-semibold font-mono" style={{ color: "var(--accent)" }}>
                        {r.pdb_id}
                      </div>
                      <div className="text-[11px] truncate max-w-[280px]" style={{ color: "var(--text-secondary)" }}>
                        {r.title}
                      </div>
                    </div>
                  </div>
                  <ExternalLink size={12} className="opacity-0 group-hover:opacity-50 transition-opacity shrink-0 mt-1" style={{ color: "var(--text-muted)" }} />
                </div>

                {/* Metadata row */}
                <div className="flex flex-wrap gap-2">
                  {r.resolution && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--bg-surface)", color: "var(--text-muted)" }}>
                      Resolution: {r.resolution}
                    </span>
                  )}
                  {r.method && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--bg-surface)", color: "var(--text-muted)" }}>
                      {r.method}
                    </span>
                  )}
                  {r.organism && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--bg-surface)", color: "var(--text-muted)" }}>
                      {r.organism}
                    </span>
                  )}
                  {r.alphafold_confidence !== undefined && (
                    <span
                      className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                      style={{
                        background: r.alphafold_confidence > 70 ? "rgba(16,185,129,0.1)" : "rgba(245,158,11,0.1)",
                        color: r.alphafold_confidence > 70 ? "#10b981" : "#f59e0b",
                      }}
                    >
                      pLDDT: {r.alphafold_confidence.toFixed(1)}
                    </span>
                  )}
                  {r.pocket_count !== undefined && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--bg-surface)", color: "var(--text-muted)" }}>
                      {r.pocket_count} pocket{r.pocket_count !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>

                {r.created_at && (
                  <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                    {new Date(r.created_at).toLocaleDateString()}
                  </div>
                )}
              </div>
            ))}
          </div>

          {filtered.length === 0 && reports.length > 0 && (
            <div className="text-center py-12">
              <FileText size={28} className="mx-auto mb-3" style={{ color: "var(--text-muted)", opacity: 0.4 }} />
              <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
                No reports match "{filterText}"
              </p>
            </div>
          )}
        </div>
      </div>
    </StateWrapper>
  );
}
