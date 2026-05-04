import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bookmark, Search, Loader2, AlertTriangle, ExternalLink } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { evidenceBundlesListAPI } from "../lib/api";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";

export default function SavedEvidence() {
  const navigate = useNavigate();
  const [projectFilter, setProjectFilter] = useState("");

  const {
    data: bundles,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["saved-evidence-bundles", projectFilter],
    queryFn: () => evidenceBundlesListAPI(projectFilter || undefined),
  });

  const bundleList = Array.isArray(bundles) ? bundles : [];

  const viewState: ViewState =
    isLoading ? "loading" :
    error ? "error" :
    bundleList.length === 0 ? "empty" :
    "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="Saved Evidence"
      emptyTitle="No saved evidence"
      emptyDescription="Collections of curated scientific literature will appear here once saved."
      errorInfo={error ? { code: "FETCH_ERROR", message: String(error) } : undefined}
      onRetry={error ? () => window.location.reload() : undefined}
    >
    <div
      className="flex-1 overflow-y-auto"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-[1100px] mx-auto px-6 py-5">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1
              className="text-lg font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              Saved Evidence Sets
            </h1>
            <p
              className="text-xs mt-0.5"
              style={{ color: "var(--text-muted)" }}
            >
              Collections of curated scientific literature and extracted claims
              for project context.
            </p>
          </div>
          <button
            onClick={() => navigate("/evidence")}
            className="flex items-center gap-2 rounded px-4 py-2 text-xs font-medium"
            style={{ background: "var(--accent)", color: "#fff" }}
            aria-label="Go to Evidence Search"
          >
            <Search size={14} /> Search Evidence
          </button>
        </div>

        {/* Filter */}
        <div className="mb-4">
          <input
            type="text"
            placeholder="Filter by project ID…"
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            className="rounded border px-3 py-1.5 text-sm w-full max-w-xs"
            style={{
              borderColor: "var(--border)",
              background: "var(--bg-surface)",
              color: "var(--text-primary)",
            }}
            aria-label="Filter bundles by project ID"
          />
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-16">
            <Loader2
              size={24}
              className="animate-spin"
              style={{ color: "var(--accent)" }}
            />
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            className="rounded-lg border p-4 flex items-start gap-3 mb-4"
            style={{
              borderColor: "#ef4444",
              background: "rgba(239,68,68,0.08)",
            }}
            role="alert"
          >
            <AlertTriangle
              size={16}
              className="mt-0.5 shrink-0"
              style={{ color: "#ef4444" }}
            />
            <p className="text-sm" style={{ color: "#ef4444" }}>
              Failed to load saved evidence bundles. Check backend connectivity.
            </p>
          </div>
        )}

        {/* Empty */}
        {!isLoading && !error && bundleList.length === 0 && (
          <div className="card flex flex-col items-center justify-center p-12 text-center border-dashed border-[var(--border)]">
            <Bookmark
              size={40}
              className="mb-4"
              style={{ color: "var(--text-muted)" }}
            />
            <h3
              className="text-sm font-medium mb-2"
              style={{ color: "var(--text-primary)" }}
            >
              No Saved Evidence
            </h3>
            <p
              className="text-xs max-w-sm mb-6"
              style={{ color: "var(--text-muted)" }}
            >
              You haven't pinned any evidence sets to your Project Memory. Use
              the Evidence Search module to curate bundles.
            </p>
            <button
              onClick={() => navigate("/evidence")}
              className="glass-button text-xs flex items-center gap-2 px-6 py-2"
              aria-label="Go to Evidence Search"
            >
              <Search size={14} /> Go to Evidence Search
            </button>
          </div>
        )}

        {/* Results */}
        {!isLoading && bundleList.length > 0 && (
          <div className="space-y-3">
            {bundleList.map((bundle: Record<string, unknown>) => {
              const id = (bundle.id ?? bundle.bundle_id ?? "") as string;
              const title = (bundle.title ?? bundle.name ?? `Bundle ${id.slice(0, 8)}`) as string;
              const itemCount = (bundle.item_count ?? bundle.evidence_count ?? 0) as number;
              const createdAt = bundle.created_at as string | undefined;

              return (
                <div
                  key={id}
                  className="rounded-lg border p-4 flex items-center justify-between hover:border-[var(--accent)] transition-colors"
                  style={{
                    borderColor: "var(--border)",
                    background: "var(--bg-surface)",
                  }}
                >
                  <div>
                    <h3
                      className="text-sm font-medium"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {title}
                    </h3>
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                      {itemCount} item{itemCount !== 1 ? "s" : ""}
                      {createdAt && ` · ${new Date(createdAt).toLocaleDateString()}`}
                    </p>
                  </div>
                  <button
                    onClick={() => navigate(`/evidence/workspace/${id}`)}
                    className="flex items-center gap-1 text-xs rounded px-3 py-1.5 border hover:border-[var(--accent)]"
                    style={{
                      borderColor: "var(--border)",
                      color: "var(--text-muted)",
                    }}
                    aria-label={`Open bundle ${title}`}
                  >
                    <ExternalLink size={12} /> Open
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
    </StateWrapper>
  );
}
