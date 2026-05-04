/** Breadcrumb — §114 Top App Bar breadcrumb showing current location in nav hierarchy. */

import { useLocation, Link } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";

/** Route → human-readable label mapping */
const ROUTE_LABELS: Record<string, string> = {
  workspace: "Cockpit",
  home: "Cockpit",
  cockpit: "Cockpit",
  evidence: "Evidence",
  search: "Evidence Search",
  sources: "Source Explorer",
  contradictions: "Contradictions",
  disease: "Disease Workbench",
  targets: "Target Prioritization",
  graph: "Knowledge Graph",
  kg: "Knowledge Graph",
  pathways: "Pathways",
  ppi: "PPI Network",
  "gene-explorer": "Gene/Protein Explorer",
  "interaction-maps": "Interaction Maps",
  "mechanism-maps": "Mechanism Maps",
  structure: "3D Structures",
  "structure-reports": "Structure Reports",
  design: "Design Studio",
  "molecule-review": "Molecule Review",
  "admet-panels": "ADMET Panels",
  translational: "Translational Research",
  translation: "Translational Research",
  syntharena: "SynthArena",
  "scenario-arena": "Scenario Arena",
  labs: "Research Labs",
  "target-discovery": "Target Discovery Lab",
  pocket: "Pocket Lab",
  "molecule-generation": "Molecule Generation Lab",
  admet: "ADMET Lab",
  retrosynthesis: "Retrosynthesis Lab",
  vaccine: "Vaccine Lab",
  "metabolic-engineering": "Metabolic Engineering Lab",
  pharmacogenomics: "Pharmacogenomics Lab",
  pico: "PICO Verification",
  dossiers: "Dossiers",
  reports: "Reports",
  logs: "System Logs",
  media: "Media Library",
  exports: "Export Center",
  export: "Export Center",
  memory: "Project Memory",
  notes: "Notes",
  models: "Model Center",
  runtime: "Runtime Center",
  "local-agent": "Local Agent",
  hardware: "Hardware Status",
  "runtime-center": "Runtime Center",
  "hardware-status": "Hardware Status",
  settings: "Settings",
  operations: "Operations",
  projects: "Projects",
  runs: "Runs & Jobs",
  jobs: "Job Detail",
  catalog: "Entity Catalog",
  data: "Data Manager",
  about: "About & Diagnostics",
  "saved-evidence": "Saved Evidence",
  "historical-queries": "Query History",
  "context-bundles": "Context Bundles",
  "uniprot-mapping": "UniProt Mapping",
  mapping: "Mapping",
  uniprot: "UniProt",
  setup: "Setup Wizard",
};

/** Section grouping for second-level breadcrumb context */
const SECTION_MAP: Record<string, string> = {
  evidence: "Evidence",
  search: "Evidence",
  sources: "Evidence",
  contradictions: "Evidence",
  "saved-evidence": "Evidence",
  "historical-queries": "Evidence",
  "context-bundles": "Evidence",
  disease: "Intelligence",
  targets: "Intelligence",
  graph: "Graph & Pathways",
  kg: "Graph & Pathways",
  pathways: "Graph & Pathways",
  ppi: "Graph & Pathways",
  "gene-explorer": "Graph & Pathways",
  "interaction-maps": "Graph & Pathways",
  "mechanism-maps": "Graph & Pathways",
  structure: "Structure & Design",
  "structure-reports": "Structure & Design",
  design: "Structure & Design",
  "molecule-review": "Structure & Design",
  "admet-panels": "Structure & Design",
  translational: "Workflows",
  translation: "Workflows",
  syntharena: "Workflows",
  "scenario-arena": "Workflows",
  labs: "Workflows",
  pico: "Workflows",
  dossiers: "Outputs",
  reports: "Outputs",
  logs: "Outputs",
  media: "Outputs",
  exports: "Outputs",
  export: "Outputs",
  memory: "Outputs",
  notes: "Outputs",
  models: "Platform",
  runtime: "Platform",
  "local-agent": "Platform",
  hardware: "Platform",
  "runtime-center": "Platform",
  "hardware-status": "Platform",
  settings: "Platform",
  operations: "Platform",
  projects: "Projects",
  runs: "Runs",
  jobs: "Runs",
};

export default function Breadcrumb() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);

  if (segments.length === 0) return null;

  const firstSeg = segments[0];
  const section = SECTION_MAP[firstSeg];
  const crumbs: { label: string; path?: string }[] = [];

  // Always show Home as first
  crumbs.push({ label: "Home", path: "/workspace" });

  // Add section if exists and different from page label
  if (section && section !== "Cockpit") {
    crumbs.push({ label: section });
  }

  // Build page crumbs from path segments
  let pathAccum = "";
  for (const seg of segments) {
    pathAccum += `/${seg}`;
    const label = ROUTE_LABELS[seg];
    if (label) {
      // Don't duplicate if same as section
      if (crumbs.length > 0 && crumbs[crumbs.length - 1].label === label) continue;
      crumbs.push({ label, path: pathAccum });
    } else if (/^[a-f0-9-]{8,}$/i.test(seg)) {
      // UUID-like → show truncated
      crumbs.push({ label: seg.slice(0, 8) + "…" });
    }
  }

  // Last crumb = current page (no link)
  const lastIdx = crumbs.length - 1;

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1 text-[11px] min-w-0"
    >
      {crumbs.map((crumb, i) => (
        <span key={i} className="flex items-center gap-1 min-w-0">
          {i > 0 && (
            <ChevronRight
              size={10}
              className="shrink-0"
              style={{ color: "var(--text-muted)" }}
            />
          )}
          {i === 0 ? (
            <Link
              to={crumb.path!}
              className="flex items-center gap-1 hover:underline"
              style={{ color: "var(--text-muted)" }}
            >
              <Home size={11} className="shrink-0" />
            </Link>
          ) : i < lastIdx && crumb.path ? (
            <Link
              to={crumb.path}
              className="truncate hover:underline"
              style={{ color: "var(--text-muted)" }}
            >
              {crumb.label}
            </Link>
          ) : (
            <span
              className="truncate font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              {crumb.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  );
}
