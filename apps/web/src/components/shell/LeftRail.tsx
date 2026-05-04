/** LeftRail — Light sidebar navigation with grouped links.
 *  5 groups: Discovery · Analysis · Workflows · Output · System
 *  Light bg, accent-blue active, responsive mobile support.
 */

import {
  Compass,
  Search,
  Activity,
  Network,
  GitBranch,
  Box,
  FlaskConical,
  Microscope,
  Swords,
  AlertTriangle,
  CheckSquare,
  FileText,
  StickyNote,
  FolderOpen,
  ScrollText,
  Settings,
  Beaker,
  Crosshair,
  Dna,
  Link2,
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { useState, useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import {
  CANONICAL_MODULE_ROUTES,
  CANONICAL_NAV_SECTIONS,
  type CanonicalModuleKey,
} from "@/lib/canonicalProduct";

interface NavItem {
  path: string;
  label: string;
  icon: React.ReactNode;
  badge?: string;
  badgeKey?: string;
  adminOnly?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const ICONS_BY_MODULE: Record<CanonicalModuleKey, React.ReactNode> = {
  cockpit: <Compass size={16} />,
  "evidence-search": <Search size={16} />,
  "entity-intelligence": <Activity size={16} />,
  "knowledge-graph": <Network size={16} />,
  pathways: <GitBranch size={16} />,
  structure: <Box size={16} />,
  design: <FlaskConical size={16} />,
  "clinical-design": <Microscope size={16} />,
  syntharena: <Swords size={16} />,
  "research-labs": <Beaker size={16} />,
  "contradiction-similarity": <AlertTriangle size={16} />,
  "pico-verification": <CheckSquare size={16} />,
  settings: <Settings size={16} />,
};

const BADGE_KEY_BY_MODULE: Partial<Record<CanonicalModuleKey, string>> = {
  "entity-intelligence": "disease_queries",
};

const SECTIONS: NavSection[] = CANONICAL_NAV_SECTIONS.map((section) => ({
  title: section.title,
  items: CANONICAL_MODULE_ROUTES.filter((route) => route.section === section.key).map((route) => ({
    path: route.path,
    label: route.label,
    icon: ICONS_BY_MODULE[route.key],
    badgeKey: BADGE_KEY_BY_MODULE[route.key],
  })),
}));

export default function LeftRail({ isOpen, onClose }: { isOpen?: boolean; onClose?: () => void }) {
  const location = useLocation();
  const { user } = useAuth();
  const [counts, setCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    fetch("/api/v1/cockpit/nav-counts", { cache: "no-store" })
      .then((r) => r.json())
      .then((env) => { if (env.data) setCounts(env.data); })
      .catch(() => {});
  }, []);

  const getBadge = (item: NavItem): string | undefined => {
    if (item.badgeKey && counts[item.badgeKey]) {
      return String(counts[item.badgeKey]);
    }
    return item.badge;
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="sidebar-overlay fixed inset-0 z-40"
          style={{ background: "rgba(0,0,0,0.3)" }}
          onClick={onClose}
        />
      )}

      <nav
        aria-label="Main navigation"
        className={`sidebar-desktop shrink-0 flex flex-col py-4 overflow-y-auto hide-scrollbar ${isOpen ? "open" : ""}`}
        style={{
          width: 240,
          minWidth: 240,
          background: "var(--bg-sidebar)",
          borderRight: "1px solid var(--border)",
        }}
      >
        {SECTIONS.map((section, si) => (
          <div key={section.title} className={si > 0 ? "mt-3" : ""}>
            {/* Section header */}
            <div
              className="px-5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em]"
              style={{ color: "var(--text-muted)" }}
            >
              {section.title}
            </div>

            {/* Navigation items */}
            {section.items.filter((item) => !item.adminOnly || user?.role === "admin").map((item) => {
              const isActive =
                location.pathname === item.path ||
                location.pathname.startsWith(item.path + "/");
              const badge = getBadge(item);

              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={`sidebar-link ${isActive ? "active" : ""}`}
                  onClick={() => onClose?.()}
                >
                  <span className="shrink-0 flex items-center justify-center w-[20px]">
                    {item.icon}
                  </span>
                  <span className="flex-1 truncate">{item.label}</span>
                  {badge && (
                    <span
                      className="shrink-0 text-[10px] font-semibold rounded-full px-1.5 py-0.5 max-w-[40px] truncate"
                      title={badge}
                      style={{
                        background: isActive ? "var(--accent-subtle)" : "var(--bg-surface)",
                        color: isActive ? "var(--accent)" : "var(--text-muted)",
                        minWidth: 20,
                        textAlign: "center",
                      }}
                    >
                      {badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>
    </>
  );
}
