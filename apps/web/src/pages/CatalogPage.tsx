/** Entity Catalog — faceted browsing + bulk operations. */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Search,
  Download,
  Database,
  Settings2,
  Plus,
  Loader2,
} from "lucide-react";
import DataGrid from "@/components/ui/DataGrid";
import { catalogStatsAPI, catalogSearchAPI } from "@/lib/api";
import StateWrapper from "@/components/ui/StateWrapper";import type { ViewState } from "@/lib/types";
/* ── Main Component ─────────────────────────────────────── */

export default function CatalogPage() {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  /* Fetch collection stats on mount */
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["catalog-stats"],
    queryFn: catalogStatsAPI,
    staleTime: 5 * 60_000,
  });

  /* Entity types derived from stats */
  const entityTypes = useMemo(() => {
    if (!stats?.collections) return [];
    return Object.entries(stats.collections)
      .sort(([, a], [, b]) => b - a)
      .map(([name, count]) => ({ name, count }));
  }, [stats]);

  /* Auto-select first entity type once stats arrive */
  const activeType = selectedType ?? entityTypes[0]?.name ?? null;

  /* Fetch catalog items for selected type */
  const {
    data: searchResult,
    isLoading: searchLoading,
    isFetching: searchFetching,
  } = useQuery({
    queryKey: ["catalog-search", activeType],
    queryFn: () => catalogSearchAPI(activeType!, 50),
    enabled: !!activeType,
  });

  /* Auto-detect DataGrid columns from the first result item */
  const columns = useMemo(() => {
    const items = searchResult?.items;
    if (!items || items.length === 0) return [];
    const firstItem = items[0];
    return Object.keys(firstItem).map((key) => ({
      key,
      label: key.replace(/_/g, " "),
      width: key === "id" || key === "name" || key === "label" ? 180 : 140,
    }));
  }, [searchResult]);

  /* Filtered entity types for sidebar search */
  const filteredTypes = useMemo(() => {
    if (!searchQuery) return entityTypes;
    const q = searchQuery.toLowerCase();
    return entityTypes.filter((t) => t.name.toLowerCase().includes(q));
  }, [entityTypes, searchQuery]);

  /* §A3.1: Compute view state from query status */
  const viewState: ViewState = statsLoading ? "loading" : !stats ? "empty" : "success";

  return (
    <StateWrapper state={viewState} moduleName="Data Catalog">
    <div
      className="flex-1 flex overflow-hidden"
      style={{ background: "var(--bg-app)" }}
    >
      {/* Left -- Facets */}
      <div className="w-[240px] glass-sidebar border-r flex flex-col overflow-hidden">
        <div className="p-3 border-b" style={{ borderColor: "var(--border)" }}>
          <h2 className="text-xs font-semibold text-[var(--text-primary)] mb-2">
            Filters
          </h2>
          <div className="relative">
            <Search
              size={13}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter..."
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded border bg-[var(--bg-app)]"
              style={{ borderColor: "var(--border)" }}
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          <FacetSection title="Entity Type">
            {statsLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2
                  size={16}
                  className="animate-spin text-[var(--text-muted)]"
                />
              </div>
            ) : filteredTypes.length === 0 ? (
              <div className="text-xs text-[var(--text-muted)] py-2 text-center">
                No types found
              </div>
            ) : (
              filteredTypes.map((t) => (
                <button
                  key={t.name}
                  onClick={() => setSelectedType(t.name)}
                  className={`w-full text-left px-2 py-1 text-xs rounded transition-colors flex items-center justify-between ${
                    activeType === t.name
                      ? "bg-indigo-50 text-[var(--accent)]"
                      : "text-[var(--text-secondary)] hover:bg-[var(--bg-surface)]"
                  }`}
                >
                  <span>{t.name}</span>
                  <span className="text-[10px] opacity-60 tabular-nums">
                    {t.count.toLocaleString()}
                  </span>
                </button>
              ))
            )}
          </FacetSection>
          <FacetSection title="Provider Domains">
            {[
              {
                domain: "Proteomics",
                providers: ["UniProt", "InterPro", "STRING"],
                count: 3,
              },
              {
                domain: "Genomics",
                providers: ["Ensembl", "GenomeAsia", "IndiGen", "IGVDB"],
                count: 4,
              },
              {
                domain: "Chemistry",
                providers: ["ChEMBL", "PubChem", "DrugBank"],
                count: 3,
              },
              {
                domain: "Literature",
                providers: ["PubMed", "Europe PMC"],
                count: 2,
              },
              {
                domain: "Structures",
                providers: ["RCSB PDB", "AlphaFold"],
                count: 2,
              },
              {
                domain: "Clinical",
                providers: ["ClinicalTrials.gov", "DisGeNET"],
                count: 2,
              },
              { domain: "Pathways", providers: ["Reactome", "KEGG"], count: 2 },
              {
                domain: "Patents",
                providers: ["PatentsView", "USPTO"],
                count: 2,
              },
              { domain: "Targets", providers: ["OpenTargets"], count: 1 },
            ].map((d) => (
              <div
                key={d.domain}
                className="flex items-center justify-between px-2 py-1 text-xs text-[var(--text-secondary)]"
              >
                <span>{d.domain}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 tabular-nums">
                  {d.count}
                </span>
              </div>
            ))}
            <div
              className="text-[10px] text-[var(--text-muted)] px-2 pt-1 border-t mt-1"
              style={{ borderColor: "var(--border)" }}
            >
              21 connectors across 9 scientific domains
            </div>
          </FacetSection>
        </div>
      </div>

      {/* Main -- DataGrid */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="glass-panel border-b px-4 py-2.5 flex items-center gap-3">
          <Database size={14} className="text-[var(--accent)]" />
          <span className="text-sm font-semibold text-[var(--text-primary)]">
            Entity Catalog
          </span>
          {activeType && (
            <span className="text-xs text-[var(--text-muted)]">
              &mdash; {activeType}s
              {searchResult && (
                <span className="ml-1">
                  ({searchResult.total.toLocaleString()} total)
                </span>
              )}
            </span>
          )}
          <div className="ml-auto flex gap-2">
            <button
              onClick={() => {
                if (!searchResult?.items?.length) return;
                const blob = new Blob(
                  [JSON.stringify(searchResult.items, null, 2)],
                  { type: "application/json" },
                );
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `catalog_${activeType || "export"}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              disabled={!searchResult?.items?.length}
              className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border hover:bg-[var(--bg-surface)] disabled:opacity-40"
              style={{ borderColor: "var(--border)" }}
            >
              <Download size={11} /> Export All ({activeType})
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden p-4">
          {searchLoading || searchFetching ? (
            <div className="card rounded-xl p-8 h-full flex items-center justify-center">
              <div className="flex flex-col items-center gap-3">
                <Loader2
                  size={28}
                  className="animate-spin text-[var(--accent)]"
                />
                <p className="text-sm text-[var(--text-muted)]">
                  Loading {activeType} data...
                </p>
              </div>
            </div>
          ) : !searchResult || searchResult.items.length === 0 ? (
            <div className="card rounded-xl p-8 h-full flex items-center justify-center">
              <div className="text-center">
                <Database size={40} className="text-slate-400 mx-auto mb-3" />
                <p className="text-sm text-[var(--text-muted)] font-medium">No Results</p>
                <p className="text-xs text-[var(--text-muted)] mt-1">
                  {activeType
                    ? `No ${activeType} entities found. Try a different entity type.`
                    : "Select an entity type from the sidebar to browse the catalog."}
                </p>
              </div>
            </div>
          ) : (
            <DataGrid
              columns={columns}
              rows={searchResult.items}
              maxHeight={600}
              exportFilename={`catalog-${activeType}`}
              entityType={activeType ?? undefined}
            />
          )}
        </div>

        {/* Bottom bar -- collection stats */}
        <div className="glass-panel border-t px-4 py-2.5 flex items-center gap-4">
          <Settings2 size={12} className="text-[var(--text-muted)]" />
          <span className="text-[10px] text-[var(--text-muted)]">
            Collections:
          </span>
          {statsLoading ? (
            <Loader2
              size={12}
              className="animate-spin text-[var(--text-muted)]"
            />
          ) : stats?.collections ? (
            <>
              {Object.entries(stats.collections)
                .slice(0, 8)
                .map(([name, count]) => (
                  <span
                    key={name}
                    className={`text-[10px] px-1.5 py-0.5 rounded ${
                      activeType === name
                        ? "bg-indigo-100 text-indigo-700"
                        : "bg-[var(--bg-inset)] text-[var(--text-muted)]"
                    }`}
                  >
                    {name}: {count.toLocaleString()}
                  </span>
                ))}
              <span className="text-[10px] text-[var(--text-muted)] ml-auto">
                Total: {stats.total.toLocaleString()} entities
              </span>
            </>
          ) : (
            <span className="text-[10px] text-[var(--text-muted)]">
              No stats available
            </span>
          )}
        </div>
      </div>
    </div>
    </StateWrapper>
  );
}

/* ── Sub-components ─────────────────────────────────────── */

function FacetSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1.5">
        {title}
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}
