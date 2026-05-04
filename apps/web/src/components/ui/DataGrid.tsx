import { useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Download,
  ChevronDown,
  ChevronRight,
  Filter,
  Columns,
  ExternalLink,
  MoreHorizontal,
  Eye,
  Send,
  Plus,
} from "lucide-react";

interface Column {
  key: string;
  label?: string;
  width?: number;
  pinned?: boolean;
  hidden?: boolean;
}

interface DataGridProps {
  columns: Column[];
  rows: Record<string, unknown>[];
  onRowClick?: (row: Record<string, unknown>) => void;
  maxHeight?: number;
  exportFilename?: string;
  entityType?: string;
}

export default function DataGrid({
  columns,
  rows,
  onRowClick,
  maxHeight = 480,
  exportFilename = "export",
  entityType,
}: DataGridProps) {
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<string>("");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [visibleCols, setVisibleCols] = useState<Set<string>>(
    new Set(columns.filter((c) => !c.hidden).map((c) => c.key)),
  );
  const [showColPicker, setShowColPicker] = useState(false);
  const [contextRow, setContextRow] = useState<number | null>(null);

  const filtered = useMemo(() => {
    let data = [...rows];
    if (search) {
      const q = search.toLowerCase();
      data = data.filter((r) =>
        Object.values(r).some((v) =>
          String(v ?? "")
            .toLowerCase()
            .includes(q),
        ),
      );
    }
    if (sortKey) {
      data.sort((a, b) => {
        const av = a[sortKey],
          bv = b[sortKey];
        const cmp = String(av ?? "").localeCompare(
          String(bv ?? ""),
          undefined,
          { numeric: true },
        );
        return sortDir === "asc" ? cmp : -cmp;
      });
    }
    return data;
  }, [rows, search, sortKey, sortDir]);

  const activeCols = columns.filter((c) => visibleCols.has(c.key));

  const handleSort = (key: string) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const exportData = useCallback(
    (format: "csv" | "json") => {
      if (format === "json") {
        const blob = new Blob([JSON.stringify(filtered, null, 2)], {
          type: "application/json",
        });
        dl(blob, `${exportFilename}.json`);
      } else {
        const keys = activeCols.map((c) => c.key);
        const header = keys.join(",");
        const body = filtered
          .map((r) =>
            keys
              .map((k) => {
                const val = String(r[k] ?? "")
                  .replace(/"/g, '""')
                  .replace(/\r\n|\r|\n/g, " ");
                return `"${val}"`;
              })
              .join(","),
          )
          .join("\n");
        dl(
          new Blob([header + "\n" + body], { type: "text/csv" }),
          `${exportFilename}.csv`,
        );
      }
    },
    [filtered, activeCols, exportFilename],
  );

  return (
    <div className="card rounded-lg overflow-hidden">
      {/* Toolbar */}
      <div
        className="flex items-center gap-2 px-3 py-2 border-b"
        style={{ borderColor: "var(--border-light)" }}
      >
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter rows…"
          className="px-2.5 py-1 text-xs rounded border bg-[var(--bg-app)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          style={{ borderColor: "var(--border)", width: 180 }}
        />
        <div className="relative">
          <button
            onClick={() => setShowColPicker(!showColPicker)}
            className="flex items-center gap-1 px-2 py-1 text-xs text-[var(--text-muted)] rounded hover:bg-[var(--bg-surface)]"
          >
            <Columns size={12} /> Columns
          </button>
          {showColPicker && (
            <div
              className="absolute top-8 left-0 z-30 bg-[var(--bg-elevated)] border rounded-lg shadow-lg p-2 w-48"
              style={{ borderColor: "var(--border)" }}
            >
              {columns.map((c) => (
                <label
                  key={c.key}
                  className="flex items-center gap-2 px-2 py-1 text-xs cursor-pointer hover:bg-[var(--bg-surface)] rounded"
                >
                  <input
                    type="checkbox"
                    checked={visibleCols.has(c.key)}
                    onChange={() => {
                      const s = new Set(visibleCols);
                      s.has(c.key) ? s.delete(c.key) : s.add(c.key);
                      setVisibleCols(s);
                      setShowColPicker(false);
                    }}
                  />
                  {c.label || c.key}
                </label>
              ))}
            </div>
          )}
        </div>
        <span className="text-xs text-[var(--text-muted)]">
          {filtered.length} rows
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => exportData("csv")}
            className="flex items-center gap-1 px-2 py-1 text-xs text-[var(--text-muted)] rounded hover:bg-[var(--bg-surface)]"
          >
            <Download size={11} /> CSV
          </button>
          <button
            onClick={() => exportData("json")}
            className="flex items-center gap-1 px-2 py-1 text-xs text-[var(--text-muted)] rounded hover:bg-[var(--bg-surface)]"
          >
            <Download size={11} /> JSON
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-auto" style={{ maxHeight }}>
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-app)] sticky top-0 z-10">
            <tr>
              <th className="w-8 px-2 py-2" />
              {activeCols.map((c) => (
                <th
                  key={c.key}
                  onClick={() => handleSort(c.key)}
                  className="px-3 py-2 text-left text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider cursor-pointer hover:text-[var(--text-secondary)] select-none"
                  style={{ minWidth: c.width || 100 }}
                >
                  {c.label || c.key.replace(/_/g, " ")}
                  {sortKey === c.key && (
                    <span className="ml-1">
                      {sortDir === "asc" ? "↑" : "↓"}
                    </span>
                  )}
                </th>
              ))}
              <th className="w-10 px-2 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-light)]">
            {filtered.map((row, idx) => (
              <>
                <tr
                  key={idx}
                  onClick={() => onRowClick?.(row)}
                  className="hover:bg-[var(--accent-subtle)]/30 cursor-pointer transition-colors group"
                >
                  <td className="px-2 py-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedRow(expandedRow === idx ? null : idx);
                      }}
                      className="text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                    >
                      {expandedRow === idx ? (
                        <ChevronDown size={14} />
                      ) : (
                        <ChevronRight size={14} />
                      )}
                    </button>
                  </td>
                  {activeCols.map((c) => {
                    const val = row[c.key];
                    const s = Array.isArray(val)
                      ? (val as string[]).slice(0, 3).join(", ")
                      : String(val ?? "—");
                    const isUrl =
                      typeof val === "string" && val.startsWith("http");
                    return (
                      <td
                        key={c.key}
                        className="px-3 py-2 text-[var(--text-primary)] max-w-[280px] truncate"
                      >
                        {isUrl ? (
                          <a
                            href={val as string}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[var(--accent)] hover:underline inline-flex items-center gap-1"
                            onClick={(e) => e.stopPropagation()}
                          >
                            Link <ExternalLink size={10} />
                          </a>
                        ) : (
                          s
                        )}
                      </td>
                    );
                  })}
                  <td className="px-2 py-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setContextRow(contextRow === idx ? null : idx);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[var(--bg-inset)] text-[var(--text-muted)]"
                    >
                      <MoreHorizontal size={14} />
                    </button>
                    {contextRow === idx && (
                      <div
                        className="absolute right-4 mt-1 z-30 bg-[var(--bg-elevated)] border rounded-lg shadow-lg py-1 w-48"
                        style={{ borderColor: "var(--border)" }}
                      >
                        <button
                          className="w-full px-3 py-1.5 text-xs text-left hover:bg-[var(--bg-surface)] flex items-center gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            onRowClick?.(row);
                            setContextRow(null);
                          }}
                        >
                          <Eye size={12} /> Open in Inspector
                        </button>
                        <button
                          className="w-full px-3 py-1.5 text-xs text-left hover:bg-[var(--bg-surface)] flex items-center gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            setContextRow(null);
                            navigate(
                              `/workspace?entity=${encodeURIComponent(String(row.id || row.canonical_name || ""))}`,
                            );
                          }}
                        >
                          <Send size={12} /> Send to Workbench
                        </button>
                        <button
                          className="w-full px-3 py-1.5 text-xs text-left hover:bg-[var(--bg-surface)] flex items-center gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            setContextRow(null);
                            navigate(
                              `/workspace?entity=${encodeURIComponent(String(row.id || row.canonical_name || ""))}`,
                            );
                          }}
                        >
                          <Plus size={12} /> Add to Project
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
                {expandedRow === idx && (
                  <tr key={`exp-${idx}`}>
                    <td
                      colSpan={activeCols.length + 2}
                      className="bg-[var(--bg-app)] px-6 py-3"
                    >
                      <RowExpansion row={row} />
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RowExpansion({ row }: { row: Record<string, unknown> }) {
  const provenance =
    (row.provenance as Array<{
      source_name?: string;
      source_url?: string;
      confidence_score?: number;
    }>) || [];
  return (
    <div className="space-y-2">
      {row.description &&
        ((
          <p className="text-xs text-[var(--text-secondary)]">
            {String(row.description).slice(0, 300)}
          </p>
        ) as any)}
      {provenance.length > 0 && (
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-[var(--text-muted)]">
            Sources:
          </span>
          {provenance.map((p, i) => (
            <a
              key={i}
              href={p.source_url || "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-[var(--accent)] hover:underline"
            >
              {p.source_name || "source"}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function dl(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
