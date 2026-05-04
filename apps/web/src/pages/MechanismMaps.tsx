import { useState, useCallback } from "react";
import { GitMerge, Search, ArrowRight, ExternalLink, Download, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "../lib/types";
import { pathwaysSearchAPI, pathwayMembersAPI, pathwayDiseaseContextAPI } from "@/lib/api";

interface PathwayHit {
  pathway_id: string;
  name: string;
  source: string;
  gene_count?: number;
  description?: string;
}

interface MemberNode {
  id: string;
  name: string;
  type: string;
  role?: string;
}

export default function MechanismMaps() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [diseaseCtx, setDiseaseCtx] = useState("");
  const [pathways, setPathways] = useState<PathwayHit[]>([]);
  const [selected, setSelected] = useState<PathwayHit | null>(null);
  const [members, setMembers] = useState<MemberNode[]>([]);
  const [diseaseOverlay, setDiseaseOverlay] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [memberLoading, setMemberLoading] = useState(false);

  const onSearch = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSelected(null);
    setMembers([]);
    setDiseaseOverlay(null);
    try {
      const res = await pathwaysSearchAPI(query.trim(), undefined, 20);
      const hits = (res as any)?.pathways ?? (res as any)?.results ?? [];
      setPathways(
        hits.map((p: any) => ({
          pathway_id: p.pathway_id ?? p.id ?? "",
          name: p.name ?? p.pathway_id ?? "Unknown",
          source: p.source ?? "Unknown",
          gene_count: p.gene_count ?? p.members?.length ?? 0,
          description: p.description ?? "",
        }))
      );
    } catch {
      setPathways([]);
    } finally {
      setLoading(false);
    }
  }, [query]);

  const onSelectPathway = useCallback(
    async (pw: PathwayHit) => {
      setSelected(pw);
      setMemberLoading(true);
      setDiseaseOverlay(null);
      try {
        const res = await pathwayMembersAPI(pw.pathway_id);
        const items = (res as any)?.members ?? (res as any)?.genes ?? [];
        setMembers(
          items.map((m: any) => ({
            id: m.id ?? m.gene_symbol ?? m.name ?? "",
            name: m.name ?? m.gene_symbol ?? m.id ?? "",
            type: m.type ?? "gene",
            role: m.role ?? m.function ?? "",
          }))
        );
      } catch {
        setMembers([]);
      }
      // Fetch disease context overlay if disease provided
      if (diseaseCtx.trim()) {
        try {
          const ctx = await pathwayDiseaseContextAPI(pw.pathway_id, diseaseCtx.trim());
          setDiseaseOverlay(ctx as any);
        } catch {
          setDiseaseOverlay(null);
        }
      }
      setMemberLoading(false);
    },
    [diseaseCtx]
  );

  const viewState: ViewState = loading
    ? "loading"
    : pathways.length === 0 && !selected
    ? "empty"
    : "success";

  // Simple cascade layout
  const cascadeRadius = 200;
  const cx = 350;
  const cy = 280;

  return (
    <StateWrapper
      state={viewState}
      moduleName="Mechanism Maps"
      emptyTitle="No mechanism maps"
      emptyDescription="Search for a pathway to explore its mechanistic cascade."
    >
      <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
        <div className="max-w-[1200px] mx-auto px-6 py-5">
          {/* Header */}
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h1 className="text-lg font-semibold text-[var(--text-primary)]">
                Mechanism Maps
              </h1>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Trace the mechanistic cascade from molecular perturbation to phenotypic outcome.
              </p>
            </div>
          </div>

          {/* Search bar */}
          <div className="card border border-border p-4 rounded-xl mb-5">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  className="w-full bg-[var(--bg-surface)] border border-border rounded-lg pl-9 pr-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                  placeholder="Search pathways (e.g. MAPK signaling, apoptosis, PI3K-Akt)..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && onSearch()}
                />
              </div>
              <div className="w-48 relative">
                <input
                  className="w-full bg-[var(--bg-surface)] border border-border rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                  placeholder="Disease context..."
                  value={diseaseCtx}
                  onChange={(e) => setDiseaseCtx(e.target.value)}
                />
              </div>
              <button
                onClick={onSearch}
                disabled={loading || !query.trim()}
                className="glass-button flex items-center gap-2 px-5 py-2 text-sm disabled:opacity-50"
              >
                {loading ? <RefreshCw size={14} className="animate-spin" /> : <Search size={14} />}
                Search
              </button>
            </div>
          </div>

          <div className="grid grid-cols-12 gap-5">
            {/* Pathway list */}
            <div className="col-span-4">
              <div className="card border border-border rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-border">
                  <h2 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                    Pathways ({pathways.length})
                  </h2>
                </div>
                <div className="max-h-[600px] overflow-y-auto divide-y divide-border">
                  {pathways.length === 0 && !loading && (
                    <div className="p-6 text-center">
                      <GitMerge size={32} className="mx-auto text-[var(--text-muted)] opacity-30 mb-3" />
                      <p className="text-xs text-[var(--text-muted)]">
                        Search for a pathway to begin mapping mechanisms.
                      </p>
                    </div>
                  )}
                  {pathways.map((pw) => (
                    <button
                      key={pw.pathway_id}
                      onClick={() => onSelectPathway(pw)}
                      className={`w-full text-left px-4 py-3 hover:bg-[var(--bg-surface)] transition-colors ${
                        selected?.pathway_id === pw.pathway_id ? "bg-[var(--accent)]/10 border-l-2 border-[var(--accent)]" : ""
                      }`}
                    >
                      <div className="text-sm font-medium text-[var(--text-primary)] mb-1 truncate">
                        {pw.name}
                      </div>
                      <div className="flex items-center gap-2 text-[10px] text-[var(--text-muted)]">
                        <span className="px-1.5 py-0.5 bg-[var(--bg-surface)] rounded font-mono">{pw.source}</span>
                        {pw.gene_count ? <span>{pw.gene_count} genes</span> : null}
                      </div>
                      {pw.description && (
                        <p className="text-[10px] text-[var(--text-muted)] mt-1 line-clamp-2">{pw.description}</p>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Mechanism visualization */}
            <div className="col-span-8">
              {selected ? (
                <div className="space-y-4">
                  {/* Header card */}
                  <div className="card border border-border rounded-xl p-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <h2 className="text-base font-semibold text-[var(--text-primary)]">{selected.name}</h2>
                        <p className="text-xs text-[var(--text-muted)] mt-1">
                          <span className="font-mono">{selected.pathway_id}</span> · {selected.source} · {members.length} members
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => navigate(`/pathways?id=${encodeURIComponent(selected.pathway_id)}`)}
                          className="glass-button flex items-center gap-1.5 px-3 py-1.5 text-xs"
                        >
                          <ExternalLink size={12} /> View in Pathways
                        </button>
                        <button
                          onClick={() => navigate(`/graph?entity=${encodeURIComponent(selected.name)}`)}
                          className="glass-button flex items-center gap-1.5 px-3 py-1.5 text-xs"
                        >
                          <ExternalLink size={12} /> Explore in KG
                        </button>
                      </div>
                    </div>
                    {diseaseOverlay && (
                      <div className="mt-3 p-3 bg-amber-500/5 border border-amber-500/20 rounded-lg">
                        <div className="text-xs font-semibold text-amber-400 mb-1">Disease Context: {diseaseCtx}</div>
                        <p className="text-[10px] text-[var(--text-muted)]">
                          {(diseaseOverlay as any)?.summary ?? "Disease-pathway context enrichment loaded."}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Cascade graph */}
                  <div className="card border border-border rounded-xl overflow-hidden">
                    {memberLoading ? (
                      <div className="flex items-center justify-center h-[500px]">
                        <RefreshCw size={24} className="animate-spin text-[var(--accent)]" />
                      </div>
                    ) : members.length > 0 ? (
                      <div className="relative h-[560px] bg-black/20">
                        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,var(--primary-glow)_0%,transparent_70%)] opacity-10" />
                        <svg width="700" height="560" className="absolute inset-0 z-10 mx-auto">
                          {/* Draw edges from center hub to nodes */}
                          {members.slice(0, 24).map((_, i) => {
                            const total = Math.min(members.length, 24);
                            const angle = (i / total) * 2 * Math.PI - Math.PI / 2;
                            const x = cx + cascadeRadius * Math.cos(angle);
                            const y = cy + cascadeRadius * Math.sin(angle);
                            return (
                              <line
                                key={`e-${i}`}
                                x1={cx}
                                y1={cy}
                                x2={x}
                                y2={y}
                                stroke="var(--accent)"
                                strokeWidth="1.5"
                                strokeOpacity="0.25"
                                strokeDasharray="4 2"
                              />
                            );
                          })}
                          {/* Draw sequential cascade arrows between adjacent nodes */}
                          {members.slice(0, 24).map((_, i) => {
                            if (i === 0) return null;
                            const total = Math.min(members.length, 24);
                            const a1 = ((i - 1) / total) * 2 * Math.PI - Math.PI / 2;
                            const a2 = (i / total) * 2 * Math.PI - Math.PI / 2;
                            const x1 = cx + cascadeRadius * Math.cos(a1);
                            const y1 = cy + cascadeRadius * Math.sin(a1);
                            const x2 = cx + cascadeRadius * Math.cos(a2);
                            const y2 = cy + cascadeRadius * Math.sin(a2);
                            return (
                              <line
                                key={`c-${i}`}
                                x1={x1}
                                y1={y1}
                                x2={x2}
                                y2={y2}
                                stroke="var(--accent)"
                                strokeWidth="1"
                                strokeOpacity="0.15"
                              />
                            );
                          })}
                          {/* Central hub */}
                          <g transform={`translate(${cx},${cy})`}>
                            <circle r="28" fill="var(--surface)" stroke="var(--accent)" strokeWidth="2" />
                            <text textAnchor="middle" y="4" fill="var(--accent)" fontSize="10" fontWeight="600">
                              {selected.source}
                            </text>
                          </g>
                          {/* Member nodes */}
                          {members.slice(0, 24).map((m, i) => {
                            const total = Math.min(members.length, 24);
                            const angle = (i / total) * 2 * Math.PI - Math.PI / 2;
                            const x = cx + cascadeRadius * Math.cos(angle);
                            const y = cy + cascadeRadius * Math.sin(angle);
                            const typeColor =
                              m.type === "gene" ? "#60a5fa" :
                              m.type === "compound" ? "#a78bfa" :
                              m.type === "disease" ? "#f472b6" :
                              "#34d399";
                            return (
                              <g
                                key={m.id + i}
                                transform={`translate(${x},${y})`}
                                className="cursor-pointer hover:scale-110 transition-transform"
                                onClick={() => navigate(`/search?q=${encodeURIComponent(m.name)}`)}
                              >
                                <circle r="16" fill="var(--surface)" stroke={typeColor} strokeWidth="2" />
                                <circle r="5" fill={typeColor} opacity="0.6" />
                                <text
                                  y="-22"
                                  textAnchor="middle"
                                  fill="var(--text-primary)"
                                  fontSize="10"
                                  className="font-mono"
                                >
                                  {m.name.length > 10 ? m.name.slice(0, 10) + "…" : m.name}
                                </text>
                                <text y="28" textAnchor="middle" fill="var(--text-muted)" fontSize="8">
                                  {m.type}
                                </text>
                              </g>
                            );
                          })}
                        </svg>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-[500px] text-center">
                        <GitMerge size={40} className="text-[var(--text-muted)] opacity-30 mb-4" />
                        <p className="text-sm text-[var(--text-muted)]">No members found for this pathway.</p>
                      </div>
                    )}
                  </div>

                  {/* Members table */}
                  {members.length > 0 && (
                    <div className="card border border-border rounded-xl overflow-hidden">
                      <div className="px-4 py-3 border-b border-border flex justify-between items-center">
                        <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                          Cascade Members ({members.length})
                        </h3>
                        <div className="flex gap-2">
                          <button
                            onClick={() => navigate(`/targets?genes=${members.filter(m => m.type === "gene").map(m => m.name).join(",")}`)}
                            className="glass-button flex items-center gap-1 px-3 py-1.5 text-xs"
                          >
                            <ArrowRight size={11} /> Rank as Targets
                          </button>
                        </div>
                      </div>
                      <div className="max-h-[300px] overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider border-b border-border">
                              <th className="text-left px-4 py-2 font-medium">Name</th>
                              <th className="text-left px-4 py-2 font-medium">ID</th>
                              <th className="text-left px-4 py-2 font-medium">Type</th>
                              <th className="text-left px-4 py-2 font-medium">Role</th>
                              <th className="px-4 py-2 font-medium">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {members.map((m, i) => (
                              <tr key={m.id + i} className="border-b border-border/50 hover:bg-[var(--bg-surface)] transition-colors">
                                <td className="px-4 py-2 text-[var(--text-primary)] font-medium">{m.name}</td>
                                <td className="px-4 py-2 font-mono text-xs text-[var(--text-muted)]">{m.id}</td>
                                <td className="px-4 py-2">
                                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                                    m.type === "gene" ? "bg-blue-500/10 text-blue-400" :
                                    m.type === "compound" ? "bg-purple-500/10 text-purple-400" :
                                    m.type === "disease" ? "bg-pink-500/10 text-pink-400" :
                                    "bg-emerald-500/10 text-emerald-400"
                                  }`}>
                                    {m.type}
                                  </span>
                                </td>
                                <td className="px-4 py-2 text-xs text-[var(--text-muted)]">{m.role || "—"}</td>
                                <td className="px-4 py-2 text-center">
                                  <button
                                    onClick={() => navigate(`/search?q=${encodeURIComponent(m.name)}`)}
                                    className="text-[var(--accent)] hover:underline text-xs"
                                  >
                                    Search
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="card border border-border p-12 text-center rounded-xl flex flex-col items-center justify-center min-h-[500px]">
                  <GitMerge size={50} className="text-[#6060ff]/30 mb-6" />
                  <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-3">
                    Select a Pathway
                  </h2>
                  <p className="text-xs text-[var(--text-muted)] max-w-lg mx-auto">
                    Search for a biological pathway and select it to visualize the mechanistic cascade
                    from molecular perturbation to phenotypic outcome.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </StateWrapper>
  );
}
