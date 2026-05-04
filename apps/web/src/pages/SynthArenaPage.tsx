/** SynthArenaPage — Drug candidate comparison arena with session list + comparison matrix.
 *  Session list view: cards showing name, target, compound count, status.
 *  Detail view: 10-criteria × N candidates comparison matrix with score bars.
 */

import { useState } from "react";
import {
  FlaskConical,
  FileText,
  GitBranch,
  Plus,
  Trophy,
  Loader2,
  RefreshCw,
  Trash2,
  ArrowLeft,
  Star,
  Download,
} from "lucide-react";
import { ensureApiBase, synthArenaGetSessionAPI } from "@/lib/api";
import { useSynthArenaSessions } from "@/lib/hooks";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "@/lib/types";

interface ArenaSession {
  id: string;
  name: string;
  target: string;
  compound_count: number;
  created_at: number;
  status: string;
}

interface Candidate {
  name: string;
  smiles: string;
  chemblId: string;
  scores: Record<string, number>;
  overall: number;
  winner: boolean;
  notes?: string;
  source?: string;
  evidenceNote?: string;
}

interface ArenaScenario {
  id: string;
  name: string;
  description?: string;
  parameters?: Record<string, unknown>;
}

interface SessionDetail {
  id: string;
  name: string;
  target: string;
  description?: string;
  compounds?: Array<Record<string, unknown>>;
  scores?: Record<string, { values?: Record<string, number>; notes?: string }>;
  rankings?: Array<Record<string, unknown>>;
  scenarios?: ArenaScenario[];
  debate_history?: Array<{ role: string; response: string }>;
  dossier_consensus?: string;
}

const CRITERIA = [
  "Binding Affinity",
  "Selectivity",
  "ADMET Score",
  "Synthetic Accessibility",
  "Solubility",
  "Metabolic Stability",
  "hERG Liability",
  "Novelty",
  "Patent Freedom",
  "Evidence Support",
];

function formatTime(ts: number) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function scoreColor(v: number) {
  if (v >= 0.85) return "#2D8B5F";
  if (v >= 0.65) return "#C48820";
  return "#C43D2F";
}

export default function SynthArenaPage() {
  const { data: sessions, state, refetch } = useSynthArenaSessions();
  const loading = state === "loading";
  const [selectedSession, setSelectedSession] = useState<ArenaSession | null>(
    null,
  );
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newTarget, setNewTarget] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newScenarioName, setNewScenarioName] = useState("");
  const [newScenarioDescription, setNewScenarioDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null);

  const createSession = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const base = await ensureApiBase();
      await fetch(`${base}/syntharena/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName, target: newTarget, description: newDescription }),
      });
      const list = await fetch(`${base}/syntharena/sessions`);
      const listPayload = await list.json().catch(() => null);
      const created = ((listPayload?.data ?? listPayload) as ArenaSession[] | undefined)?.find((session) => session.name === newName);
      if (created && newScenarioName.trim()) {
        await fetch(`${base}/syntharena/sessions/${created.id}/add-scenario`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: newScenarioName,
            description: newScenarioDescription,
            parameters: { focus_target: newTarget || "unassigned" },
          }),
        });
      }
      setNewName("");
      setNewTarget("");
      setNewDescription("");
      setNewScenarioName("");
      setNewScenarioDescription("");
      setShowCreate(false);
      refetch();
    } catch {
      /* empty */
    }
    setCreating(false);
  };

  const deleteSession = async (id: string) => {
    try {
      const base = await ensureApiBase();
      await fetch(`${base}/syntharena/sessions/${id}`, { method: "DELETE" });
      refetch();
    } catch {
      /* empty */
    }
  };

  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [addCompoundOpen, setAddCompoundOpen] = useState(false);
  const [compName, setCompName] = useState("");
  const [compSmiles, setCompSmiles] = useState("");
  const [compSource, setCompSource] = useState("manual");
  const [compEvidence, setCompEvidence] = useState("");
  const [addingComp, setAddingComp] = useState(false);
  const [debating, setDebating] = useState(false);
  const [scenarioOpen, setScenarioOpen] = useState(false);
  const [scenarioName, setScenarioName] = useState("");
  const [scenarioDescription, setScenarioDescription] = useState("");
  const [scenarioParameters, setScenarioParameters] = useState('{"focus":"balanced"}');

  const fetchSessionDetail = async (id: string) => {
    setLoadingCandidates(true);
    try {
      const detail = await synthArenaGetSessionAPI(id) as any;
      setSessionDetail(detail as SessionDetail);
      const compounds = detail?.compounds || [];
      const scores = detail?.scores || {};
      const rankings = detail?.rankings || [];
      const mapped: Candidate[] = compounds.map((c: any) => {
        const cScores: Record<string, number> = {};
        const scoreEntry = scores[c.name];
        if (scoreEntry?.values) {
          for (const [k, v] of Object.entries(scoreEntry.values)) {
            const label = k.replace(/_/g, " ").replace(/\b\w/g, (l: string) => l.toUpperCase());
            cScores[label] = (v as number) / 100;
          }
        }
        const overall = Object.values(cScores).length
          ? Object.values(cScores).reduce((a, b) => a + b, 0) / Object.values(cScores).length
          : 0;
        const rank = rankings.find((r: any) => r.compound === c.name);
        return {
          name: c.name,
          smiles: c.smiles || "",
          chemblId: c.source || "",
          scores: cScores,
          overall,
          winner: rank?.rank === 1,
          notes: scoreEntry?.notes || "",
          source: c.source || "manual",
          evidenceNote: typeof c.properties?.evidence_note === "string" ? c.properties.evidence_note : "",
        };
      });
      setCandidates(mapped);
    } catch {
      setSessionDetail(null);
      setCandidates([]);
    }
    setLoadingCandidates(false);
  };

  const openSession = (s: ArenaSession) => {
    setSelectedSession(s);
    fetchSessionDetail(s.id);
  };

  const addCompound = async () => {
    if (!selectedSession || !compName.trim()) return;
    setAddingComp(true);
    try {
      const base = await ensureApiBase();
      await fetch(`${base}/syntharena/sessions/${selectedSession.id}/compounds`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: compName,
          smiles: compSmiles,
          source: compSource,
          properties: {
            evidence_note: compEvidence,
          },
        }),
      });
      setCompName("");
      setCompSmiles("");
      setCompSource("manual");
      setCompEvidence("");
      setAddCompoundOpen(false);
      fetchSessionDetail(selectedSession.id);
    } catch { /* empty */ }
    setAddingComp(false);
  };

  const addScenario = async () => {
    if (!selectedSession || !scenarioName.trim()) return;
    try {
      const base = await ensureApiBase();
      await fetch(`${base}/syntharena/sessions/${selectedSession.id}/add-scenario`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: scenarioName,
          description: scenarioDescription,
          parameters: JSON.parse(scenarioParameters || "{}"),
        }),
      });
      setScenarioName("");
      setScenarioDescription("");
      setScenarioParameters('{"focus":"balanced"}');
      setScenarioOpen(false);
      fetchSessionDetail(selectedSession.id);
    } catch {
      /* empty */
    }
  };

  const simulateDebate = async () => {
    if (!selectedSession) return;
    setDebating(true);
    try {
      const base = await ensureApiBase();
      await fetch(`${base}/syntharena/sessions/${selectedSession.id}/simulate_debate`, {
        method: "POST",
      });
      fetchSessionDetail(selectedSession.id);
    } catch { /* empty */ }
    setDebating(false);
  };

  const sessionList: ArenaSession[] = Array.isArray(sessions) ? sessions : [];
  const failedSessions = sessionList.filter((s) => s.status === "failed" || s.status === "error");
  const showCreateForm = showCreate || sessionList.length === 0;

  const viewState: ViewState = state === "error"
    ? "error"
    : loading
      ? "loading"
      : failedSessions.length > 0 || state === "degraded"
        ? "degraded"
        : "success";

  // --- Detail view (comparison matrix) ---
  if (selectedSession) {
    return (
      <div
        className="flex-1 overflow-y-auto p-6"
        style={{ background: "var(--bg-app)" }}
      >
        {/* Back + header */}
        <button
          onClick={() => { setSelectedSession(null); setCandidates([]); setSessionDetail(null); }}
          className="flex items-center gap-1 text-[11px] font-medium mb-3 transition-colors"
          style={{ color: "var(--accent)" }}
        >
          <ArrowLeft size={12} /> All Sessions
        </button>
        <div className="flex items-center justify-between mb-1">
          <h1
            className="text-xl"
            style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
          >
            {selectedSession.name}
          </h1>
          <div className="flex gap-2">
            <button
              onClick={() => setScenarioOpen(!scenarioOpen)}
              className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded border"
              style={{ borderColor: "var(--border)", color: "var(--accent)" }}
            >
              <GitBranch size={10} /> Scenario
            </button>
            <button
              onClick={() => setAddCompoundOpen(!addCompoundOpen)}
              className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded border"
              style={{ borderColor: "var(--border)", color: "var(--accent)" }}
            >
              <Plus size={10} /> Add Candidate
            </button>
            {candidates.length > 0 && (
              <button
                onClick={simulateDebate}
                disabled={debating}
                className="btn-primary flex items-center gap-1 px-2 py-1 text-[10px]"
              >
                {debating ? <Loader2 size={10} className="animate-spin" /> : <Trophy size={10} />}
                {debating ? "Debating…" : "Simulate Debate"}
              </button>
            )}
            <button
              onClick={async () => {
                const base = await ensureApiBase();
                const res = await fetch(`${base}/syntharena/sessions/${selectedSession.id}/export`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ format: "json" }),
                });
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${selectedSession.name}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded border"
              style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
            >
              <Download size={10} /> Export
            </button>
            <button
              onClick={() => {
                downloadJson(`${selectedSession.name.replace(/\s+/g, "_").toLowerCase()}_dossier.json`, {
                  session: sessionDetail,
                  candidates,
                  exported_at: new Date().toISOString(),
                });
              }}
              className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded border"
              style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
            >
              <FileText size={10} /> Export to Dossier
            </button>
          </div>
        </div>
        <p className="text-xs mb-5" style={{ color: "var(--text-muted)" }}>
          Target: {selectedSession.target || "—"} · {candidates.length} candidates · {CRITERIA.length} criteria
        </p>

        {scenarioOpen && (
          <div className="p-4 mb-4" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
            <div className="grid md:grid-cols-2 gap-3 mb-3">
              <input
                type="text"
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                placeholder="Scenario name"
                className="px-2.5 py-1.5 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
              <input
                type="text"
                value={scenarioDescription}
                onChange={(e) => setScenarioDescription(e.target.value)}
                placeholder="Scenario description"
                className="px-2.5 py-1.5 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
            </div>
            <textarea
              value={scenarioParameters}
              onChange={(e) => setScenarioParameters(e.target.value)}
              rows={4}
              className="w-full px-2.5 py-1.5 text-xs rounded border font-mono mb-3"
              style={{ borderColor: "var(--border)" }}
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setScenarioOpen(false)} className="px-3 py-1 text-[10px] rounded border" style={{ borderColor: "var(--border)" }}>Cancel</button>
              <button onClick={addScenario} disabled={!scenarioName.trim()} className="btn-primary px-3 py-1 text-[10px]">Add Scenario</button>
            </div>
          </div>
        )}

        {/* Add compound form */}
        {addCompoundOpen && (
          <div className="p-4 mb-4" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
            <div className="grid md:grid-cols-2 gap-3 mb-3">
              <input
                type="text"
                value={compName}
                onChange={(e) => setCompName(e.target.value)}
                placeholder="Compound name"
                className="flex-1 px-2.5 py-1.5 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
              <input
                type="text"
                value={compSmiles}
                onChange={(e) => setCompSmiles(e.target.value)}
                placeholder="SMILES (optional)"
                className="flex-1 px-2.5 py-1.5 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
              <input
                type="text"
                value={compSource}
                onChange={(e) => setCompSource(e.target.value)}
                placeholder="Evidence source (manual, ChEMBL, dossier)"
                className="flex-1 px-2.5 py-1.5 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
            </div>
            <textarea
              value={compEvidence}
              onChange={(e) => setCompEvidence(e.target.value)}
              rows={3}
              placeholder="Evidence note or rationale"
              className="w-full px-2.5 py-1.5 text-xs rounded border mb-3"
              style={{ borderColor: "var(--border)" }}
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setAddCompoundOpen(false)} className="px-3 py-1 text-[10px] rounded border" style={{ borderColor: "var(--border)" }}>Cancel</button>
              <button onClick={addCompound} disabled={addingComp || !compName.trim()} className="btn-primary px-3 py-1 text-[10px]">
                {addingComp ? <Loader2 size={10} className="animate-spin" /> : "Add"}
              </button>
            </div>
          </div>
        )}

        {/* Loading state for candidates */}
        {loadingCandidates && (
          <div className="flex items-center justify-center py-12">
            <Loader2 size={20} className="animate-spin" style={{ color: "var(--accent)" }} />
          </div>
        )}

        {/* Empty candidates state */}
        {!loadingCandidates && candidates.length === 0 && (
          <div className="empty-state">
            <FlaskConical size={32} />
            <p className="mt-3">No candidates yet. Add compounds then run Simulate Debate to auto-score.</p>
          </div>
        )}

        {/* Comparison matrix table */}
        {!loadingCandidates && candidates.length > 0 && (
        <div
          className="overflow-x-auto"
          style={{ border: "1px solid var(--border)" }}
        >
          <table className="w-full text-xs" style={{ minWidth: 700 }}>
            <thead>
              <tr style={{ background: "var(--bg-surface)" }}>
                <th
                  className="text-left py-2.5 px-3 font-semibold"
                  style={{ width: 180 }}
                >
                  Criterion
                </th>
                {candidates.map((c) => (
                  <th
                    key={c.name}
                    className="text-center py-2.5 px-3 font-semibold"
                    style={{ minWidth: 140 }}
                  >
                    <div>{c.name}</div>
                    {c.winner && (
                      <span
                        className="text-[8px] font-bold px-1 py-0.5 rounded"
                        style={{ background: "#2D8B5F", color: "#fff" }}
                      >
                        🏆 WINNER
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {CRITERIA.map((criterion) => {
                const maxVal = Math.max(
                  ...candidates.map((c) => c.scores[criterion] || 0),
                );
                return (
                  <tr key={criterion}>
                    <td
                      className="py-2 px-3 font-medium"
                      style={{ borderBottom: "1px solid var(--border)" }}
                    >
                      {criterion}
                    </td>
                    {candidates.map((c) => {
                      const val = c.scores[criterion] || 0;
                      const isBest = val === maxVal && val > 0;
                      return (
                        <td
                          key={c.name}
                          className="py-2 px-3 text-center"
                          style={{
                            borderBottom: "1px solid var(--border)",
                            fontWeight: isBest ? 700 : 400,
                          }}
                        >
                          <div className="flex flex-col items-center gap-1">
                            <span style={{ color: scoreColor(val) }}>
                              {(val * 100).toFixed(0)}%
                            </span>
                            <div
                              className="w-16 h-1.5 rounded-full"
                              style={{ background: "var(--border)" }}
                            >
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${val * 100}%`,
                                  background: scoreColor(val),
                                }}
                              />
                            </div>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
              {/* Overall row */}
              <tr style={{ background: "var(--bg-surface)" }}>
                <td className="py-2.5 px-3 font-bold">Overall Score</td>
                {candidates.map((c) => (
                  <td
                    key={c.name}
                    className="py-2.5 px-3 text-center font-bold text-sm"
                    style={{ color: "var(--accent)" }}
                  >
                    {c.overall.toFixed(2)}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>

        )}

        {/* Candidate detail cards */}
        {!loadingCandidates && candidates.length > 0 && (
        <div className="grid grid-cols-3 gap-4 mt-6">
          {candidates.map((c) => (
            <div
              key={c.name}
              className="p-4"
              style={{
                border: "1px solid var(--border)",
                background: "var(--bg-surface)",
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-semibold">{c.name}</span>
                {c.winner && <Star size={12} style={{ color: "#C48820" }} />}
              </div>
              <div
                className="text-[9px] mb-2"
                style={{
                  fontFamily: "var(--font-mono)",
                  color: "var(--text-muted)",
                }}
              >
                {c.chemblId}
              </div>
              <div
                className="text-[9px] p-1.5 rounded overflow-x-auto"
                style={{
                  background: "var(--bg-elevated)",
                  fontFamily: "var(--font-mono)",
                  color: "var(--text-secondary)",
                }}
              >
                {c.smiles.length > 40 ? c.smiles.slice(0, 40) + "…" : c.smiles}
              </div>
              <div className="mt-2 text-[10px] text-[var(--text-muted)]">Source: {c.source || "manual"}</div>
              {c.evidenceNote && <div className="mt-1 text-[10px] text-[var(--text-muted)]">Evidence: {c.evidenceNote}</div>}
              {c.notes && <div className="mt-1 text-[10px] text-[var(--text-secondary)]">Score note: {c.notes}</div>}
            </div>
          ))}
        </div>
        )}

        {sessionDetail?.scenarios && sessionDetail.scenarios.length > 0 && (
          <div className="mt-6 p-4" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
            <div className="section-label mb-2">Scenarios</div>
            <div className="grid md:grid-cols-2 gap-3">
              {sessionDetail.scenarios.map((scenario) => (
                <div key={scenario.id} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                  <div className="text-xs font-semibold text-[var(--text-primary)]">{scenario.name}</div>
                  <div className="text-[10px] text-[var(--text-muted)] mt-1">{scenario.description || "No description"}</div>
                  {scenario.parameters && (
                    <pre className="mt-2 text-[10px] whitespace-pre-wrap break-words text-[var(--text-secondary)]">
                      {JSON.stringify(scenario.parameters, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {sessionDetail?.debate_history && sessionDetail.debate_history.length > 0 && (
          <div className="mt-6 p-4" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
            <div className="section-label mb-2">Debate Evidence</div>
            <div className="grid md:grid-cols-2 gap-3">
              {sessionDetail.debate_history.map((entry, index) => (
                <div key={`${entry.role}-${index}`} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                  <div className="text-[10px] font-semibold uppercase text-[var(--text-muted)]">{entry.role}</div>
                  <div className="text-xs text-[var(--text-secondary)] mt-2 whitespace-pre-wrap">{entry.response}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {(sessionDetail?.dossier_consensus || candidates.some((candidate) => candidate.winner)) && (
          <div className="mt-6 p-4" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
            <div className="section-label mb-2">Winner Rationale</div>
            <div className="text-xs text-[var(--text-secondary)] whitespace-pre-wrap">
              {sessionDetail?.dossier_consensus || `${candidates.find((candidate) => candidate.winner)?.name || "Top candidate"} leads based on the current weighted score matrix.`}
            </div>
          </div>
        )}

        <div className="mt-6 p-4" style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
          <div className="section-label mb-2">Provenance</div>
          <div className="space-y-2 text-xs text-[var(--text-muted)]">
            {candidates.map((candidate) => (
              <div key={`${candidate.name}-prov`} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                <div className="font-semibold text-[var(--text-primary)]">{candidate.name}</div>
                <div>Source record: {candidate.source || "manual"}</div>
                <div>Evidence note: {candidate.evidenceNote || "No evidence note attached"}</div>
                <div>Model note: {candidate.notes || "No model note attached"}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // --- Session list view ---
  return (
    <StateWrapper
      state={viewState}
      moduleName="SynthArena"
      degradedInfo={failedSessions.length > 0 ? { reason: "Some arena sessions encountered errors.", affectedSources: failedSessions.map((s) => s.name) } : undefined}
    >
    <div
      className="flex-1 overflow-y-auto p-6"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-1">
          <h1
            className="text-xl"
            style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
          >
            SynthArena
          </h1>
          <div className="flex gap-2">
            <button
              onClick={refetch}
              className="flex items-center gap-1 px-2 py-1 text-[10px] rounded border transition-colors"
              style={{
                borderColor: "var(--border)",
                color: "var(--text-muted)",
              }}
            >
              <RefreshCw size={10} /> Refresh
            </button>
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="btn-primary flex items-center gap-1 px-3 py-1.5 text-[10px]"
            >
              <Plus size={10} /> New Session
            </button>
          </div>
        </div>
        <p className="text-xs mb-5" style={{ color: "var(--text-muted)" }}>
          Compare and rank drug candidates against customizable evidence-backed
          criteria
        </p>

        {/* Create form */}
        {showCreateForm && (
          <div
            className="p-4 mb-5"
            style={{
              border: "1px solid var(--border)",
              background: "var(--bg-surface)",
            }}
          >
            <div className="grid md:grid-cols-2 gap-3 mb-3">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Session name (e.g. EGFR Inhibitor Comparison)"
                className="flex-1 px-2.5 py-1.5 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
              <input
                type="text"
                value={newTarget}
                onChange={(e) => setNewTarget(e.target.value)}
                placeholder="Target protein (optional)"
                className="flex-1 px-2.5 py-1.5 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
              <input
                type="text"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="Comparison goal or dossier context"
                className="flex-1 px-2.5 py-1.5 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
            </div>
            <div className="grid md:grid-cols-2 gap-3 mb-3">
              <input
                type="text"
                value={newScenarioName}
                onChange={(e) => setNewScenarioName(e.target.value)}
                placeholder="Initial scenario name (optional)"
                className="flex-1 px-2.5 py-1.5 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
              <input
                type="text"
                value={newScenarioDescription}
                onChange={(e) => setNewScenarioDescription(e.target.value)}
                placeholder="Scenario summary"
                className="flex-1 px-2.5 py-1.5 text-xs rounded border"
                style={{ borderColor: "var(--border)" }}
              />
            </div>
            <div className="flex justify-end gap-2">
              {sessionList.length > 0 && (
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-3 py-1 text-[10px] rounded border"
                  style={{ borderColor: "var(--border)" }}
                >
                  Cancel
                </button>
              )}
              <button
                onClick={createSession}
                disabled={creating || !newName.trim()}
                className="btn-primary px-3 py-1 text-[10px]"
              >
                {creating ? (
                  <Loader2 size={10} className="animate-spin" />
                ) : (
                  "Create"
                )}
              </button>
            </div>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2
              size={20}
              className="animate-spin"
              style={{ color: "var(--accent)" }}
            />
          </div>
        )}

        {/* Empty state */}
        {!loading && sessionList.length === 0 && (
          <div className="p-5 rounded-xl border" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
            <div className="flex items-center gap-3 mb-2">
              <Trophy size={28} style={{ color: "var(--accent)" }} />
              <div>
                <div className="text-sm font-semibold">Create-first arena</div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Start with a session, define a scenario, then add compounds and simulate the debate.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Sessions */}
        {!loading && sessionList.length > 0 && (
          <div className="space-y-2">
            {sessionList.map((s) => (
              <div
                key={s.id}
                className="flex items-center gap-4 p-4 cursor-pointer transition-colors hover:border-[var(--text-muted)]"
                style={{
                  border: "1px solid var(--border)",
                  background: "var(--bg-surface)",
                }}
                onClick={() => openSession(s)}
              >
                <FlaskConical size={18} style={{ color: "var(--accent)" }} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold">{s.name}</div>
                  <div
                    className="text-[11px]"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {s.target && `Target: ${s.target} · `}
                    {s.compound_count} compounds · {formatTime(s.created_at)}
                  </div>
                </div>
                <span
                  className="text-[9px] font-bold px-1.5 py-0.5 rounded-sm uppercase"
                  style={{
                    background: s.status === "ranked" ? "#ecfdf5" : "#fffbeb",
                    color: s.status === "ranked" ? "#047857" : "#b45309",
                  }}
                >
                  {s.status}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSession(s.id);
                  }}
                  className="p-1 rounded text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Criteria info */}
        <div
          className="mt-6 p-4"
          style={{
            border: "1px solid var(--border)",
            background: "var(--bg-surface)",
          }}
        >
          <div className="section-label mb-2">Default Scoring Criteria</div>
          <div className="flex flex-wrap gap-2">
            {CRITERIA.map((c) => (
              <span
                key={c}
                className="text-[10px] font-medium px-2 py-1 rounded"
                style={{
                  background: "var(--accent-subtle)",
                  color: "var(--accent)",
                }}
              >
                {c}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
    </StateWrapper>
  );
}
