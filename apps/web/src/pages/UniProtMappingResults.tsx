/** UniProtMappingResults — Batch protein mapping table with resolution status.
 *  Shows mapped proteins with UniProt ID, length, gene, organism, evidence level.
 *  Handles unresolved/failed states with Retry buttons.
 */

import { useState, useEffect } from "react";
import { Link2, RefreshCw, CheckCircle, AlertCircle } from "lucide-react";
import { ensureApiBase } from "@/lib/api";
import type { ViewState } from "../lib/types";
import StateWrapper from "@/components/ui/StateWrapper";

interface MappedProtein {
  input: string;
  uniprotId: string;
  name: string;
  length: number;
  gene: string;
  organism: string;
  evidenceLevel: number;
  resolved: boolean;
}

export default function UniProtMappingResults() {
  const [proteins, setProteins] = useState<MappedProtein[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const base = await ensureApiBase();
        const res = await fetch(`${base}/evidence/uniprot-map`);
        if (res.ok) {
          const data = await res.json();
          if (data.length) setProteins(data);
        }
      } catch (err: unknown) {
        /* no fallback — viewState will show empty */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const resolved = proteins.filter((p) => p.resolved);
  const unresolved = proteins.filter((p) => !p.resolved);

  const viewState: ViewState =
    loading ? "loading" :
    proteins.length === 0 ? "empty" :
    "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="UniProt Mapping"
      emptyTitle="No mapping results"
      emptyDescription="Submit protein names to see batch UniProt mappings."
    >
    <div
      className="flex-1 overflow-y-auto p-6"
      style={{ background: "var(--bg-app)" }}
    >
      <h1
        className="text-xl mb-1"
        style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
      >
        UniProt Mapping
      </h1>
      <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
        Batch protein name → UniProt accession resolution · Organism
        verification · Evidence level scoring
      </p>

      {/* Summary */}
      <div
        className="flex items-center gap-4 py-2.5 px-4 mb-5"
        style={{
          borderLeft: "3px solid var(--accent)",
          background: "var(--bg-surface)",
        }}
      >
        <span
          className="text-sm font-semibold"
          style={{ color: "var(--accent)" }}
        >
          {resolved.length} resolved
        </span>
        {unresolved.length > 0 && (
          <span className="text-sm font-semibold" style={{ color: "#C43D2F" }}>
            {unresolved.length} unresolved
          </span>
        )}
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {proteins.length} total queries · Project: Alzheimer's Pipeline
        </span>
      </div>

      {/* Mapping table */}
      <div
        className="overflow-x-auto"
        style={{ border: "1px solid var(--border)" }}
      >
        <table className="w-full text-xs">
          <thead>
            <tr style={{ background: "var(--bg-surface)" }}>
              <th
                className="text-left py-2.5 px-3 font-semibold"
                style={{ color: "var(--text-muted)" }}
              >
                Input
              </th>
              <th
                className="text-left py-2.5 px-3 font-semibold"
                style={{ color: "var(--text-muted)" }}
              >
                UniProt ID
              </th>
              <th
                className="text-left py-2.5 px-3 font-semibold"
                style={{ color: "var(--text-muted)" }}
              >
                Protein Name
              </th>
              <th
                className="text-right py-2.5 px-3 font-semibold"
                style={{ color: "var(--text-muted)" }}
              >
                Length
              </th>
              <th
                className="text-left py-2.5 px-3 font-semibold"
                style={{ color: "var(--text-muted)" }}
              >
                Gene
              </th>
              <th
                className="text-left py-2.5 px-3 font-semibold"
                style={{ color: "var(--text-muted)" }}
              >
                Organism
              </th>
              <th
                className="text-center py-2.5 px-3 font-semibold"
                style={{ color: "var(--text-muted)" }}
              >
                Evidence
              </th>
              <th
                className="text-center py-2.5 px-3 font-semibold"
                style={{ color: "var(--text-muted)" }}
              >
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {proteins.map((p) => (
              <tr key={p.input}>
                <td
                  className="py-2.5 px-3 font-semibold"
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  {p.input}
                </td>
                <td
                  className="py-2.5 px-3"
                  style={{
                    borderBottom: "1px solid var(--border)",
                    fontFamily: "var(--font-mono)",
                    color: p.resolved ? "var(--accent)" : "var(--text-muted)",
                  }}
                >
                  {p.uniprotId}
                </td>
                <td
                  className="py-2.5 px-3"
                  style={{
                    borderBottom: "1px solid var(--border)",
                    color: "var(--text-secondary)",
                  }}
                >
                  {p.name}
                </td>
                <td
                  className="py-2.5 px-3 text-right"
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  {p.length > 0 ? `${p.length} aa` : "—"}
                </td>
                <td
                  className="py-2.5 px-3"
                  style={{
                    borderBottom: "1px solid var(--border)",
                    color: "var(--text-secondary)",
                  }}
                >
                  {p.gene}
                </td>
                <td
                  className="py-2.5 px-3"
                  style={{
                    borderBottom: "1px solid var(--border)",
                    color: "var(--text-muted)",
                  }}
                >
                  {p.organism}
                </td>
                <td
                  className="py-2.5 px-3 text-center"
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  {p.evidenceLevel > 0 ? (
                    <span
                      className="text-[10px] font-bold"
                      style={{
                        color: p.evidenceLevel >= 4 ? "#2D8B5F" : "#C48820",
                      }}
                    >
                      {"★".repeat(p.evidenceLevel)}
                      {"☆".repeat(5 - p.evidenceLevel)}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td
                  className="py-2.5 px-3 text-center"
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  {p.resolved ? (
                    <span
                      className="flex items-center justify-center gap-1 text-[10px] font-bold"
                      style={{ color: "#2D8B5F" }}
                    >
                      <CheckCircle size={11} /> Resolved
                    </span>
                  ) : (
                    <button
                      className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded"
                      style={{ color: "#C43D2F", border: "1px solid #C43D2F" }}
                    >
                      <RefreshCw size={9} /> Retry
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Actions */}
      <div className="flex gap-2 mt-4">
        <button className="btn-primary px-3 py-1.5 text-[10px] flex items-center gap-1">
          <Link2 size={10} /> → Map to Targets
        </button>
        <button
          className="px-3 py-1.5 text-[10px] border rounded"
          style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
        >
          Export Mapping Table
        </button>
      </div>
    </div>
    </StateWrapper>
  );
}
