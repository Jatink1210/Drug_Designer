/** Context Bundles — Evidence bundle management (§7.2) */
import { useState, useEffect } from "react";
import { Archive, Layers, Plus, Loader2, Package } from "lucide-react";
import { evidenceBundlesListAPI, evidenceBundleCreateAPI } from "@/lib/api";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "@/lib/types";

interface Bundle {
  id: string;
  name: string;
  description?: string;
  item_count?: number;
  created_at?: string;
}

export default function ContextBundles() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  const fetchBundles = async () => {
    try {
      const data = await evidenceBundlesListAPI();
      setBundles((data as unknown as Bundle[]) || []);
    } catch {
      setBundles([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchBundles(); }, []);

  const viewState: ViewState =
    loading ? "loading" :
    bundles.length === 0 ? "empty" :
    "success";

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await evidenceBundleCreateAPI({ name: newName.trim() });
      setNewName("");
      await fetchBundles();
    } catch { /* ignore */ }
    setCreating(false);
  };

  return (
    <StateWrapper
      state={viewState}
      moduleName="Context Bundles"
      emptyTitle="No Bundles"
      emptyDescription="Create your first context bundle to get started."
      onRetry={fetchBundles}
    >
    <div
      className="flex-1 overflow-y-auto"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-[1100px] mx-auto px-6 py-5">
        <div className="mb-6">
          <h1 className="text-lg font-semibold text-[var(--text-primary)]">
            Saved Context Bundles
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            L0-L2 conversational memory architectures saved for swift context
            resurrection.
          </p>
        </div>

        {/* Create new bundle */}
        <div className="flex items-center gap-2 mb-6">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            placeholder="New bundle name..."
            className="flex-1 max-w-xs px-3 py-1.5 text-xs rounded-lg border border-border bg-surface"
            style={{ color: "var(--text-primary)" }}
          />
          <button
            onClick={handleCreate}
            disabled={creating || !newName.trim()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg text-white transition-colors disabled:opacity-50"
            style={{ background: "var(--accent)" }}
          >
            {creating ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            Create
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {bundles.map((b) => (
              <div
                key={b.id}
                className="card p-6 hover:-translate-y-1 transition-transform cursor-pointer"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Package size={16} className="text-[var(--accent)]" />
                  <span className="text-sm font-semibold text-[var(--text-primary)]">
                    {b.name}
                  </span>
                </div>
                {b.description && (
                  <p className="text-[11px] text-[var(--text-muted)] mb-2">
                    {b.description}
                  </p>
                )}
                <div className="flex items-center gap-3 text-[10px] text-[var(--text-secondary)]">
                  <span>{b.item_count ?? 0} items</span>
                  {b.created_at && (
                    <span>{new Date(b.created_at).toLocaleDateString()}</span>
                  )}
                </div>
              </div>
            ))}

            {bundles.length === 0 && (
              <div className="card p-6 border border-dashed border-border flex flex-col items-center justify-center min-h-[200px] text-center">
                <Layers size={24} className="text-[var(--text-muted)] mb-3" />
                <span className="text-xs text-[var(--text-primary)] font-medium">
                  No bundles yet
                </span>
                <span className="text-[10px] text-[var(--text-secondary)] mt-1">
                  Create one above to start capturing context
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
    </StateWrapper>
  );
}
