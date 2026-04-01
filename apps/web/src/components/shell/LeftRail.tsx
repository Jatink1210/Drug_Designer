/** LeftRail — 172px always-visible grouped navigation matching the Impeccable mockup.
 *  5 groups: Discovery · Analysis · Workflows · Output · System
 *  Each item: icon + label + optional badge count.
 *  Active item: 3px left accent border.
 */

import {
    Home, Search, Pin, Radio, Activity, Target, Link2,
    Network, GitBranch, Box, FlaskConical,
    Microscope, Swords, AlertTriangle, CheckSquare,
    FileText, ClipboardList, Package,
    Cpu, Zap, Satellite, Monitor,
    FolderOpen, Play, ScrollText, Image as ImageIcon, Settings
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";

interface NavItem {
    path: string;
    label: string;
    icon: React.ReactNode;
    badge?: string;
}

interface NavSection {
    title: string;
    items: NavItem[];
}

const SECTIONS: NavSection[] = [
    {
        title: "Discovery",
        items: [
            { path: "/workspace", label: "Home", icon: <Home size={15} /> },
            { path: "/search", label: "Evidence Search", icon: <Search size={15} />, badge: "47" },
            { path: "/evidence", label: "Evidence Workspace", icon: <Pin size={15} />, badge: "12" },
            { path: "/sources", label: "Source Explorer", icon: <Radio size={15} />, badge: "18" },
            { path: "/disease", label: "Disease Intel", icon: <Activity size={15} />, badge: "12" },
            { path: "/targets", label: "Targets", icon: <Target size={15} />, badge: "8" },
            { path: "/uniprot-mapping", label: "UniProt Mapping", icon: <Link2 size={15} />, badge: "10" },
        ],
    },
    {
        title: "Analysis",
        items: [
            { path: "/kg", label: "Knowledge Graph", icon: <Network size={15} />, badge: "82K" },
            { path: "/pathways", label: "Pathways", icon: <GitBranch size={15} />, badge: "6" },
            { path: "/structure", label: "Structures", icon: <Box size={15} />, badge: "5" },
            { path: "/design", label: "Design Studio", icon: <FlaskConical size={15} />, badge: "3" },
        ],
    },
    {
        title: "Workflows",
        items: [
            { path: "/translational", label: "Clinical Stage", icon: <Microscope size={15} />, badge: "4" },
            { path: "/syntharena", label: "SynthArena", icon: <Swords size={15} />, badge: "3" },
            { path: "/contradictions", label: "Contradictions", icon: <AlertTriangle size={15} />, badge: "3" },
            { path: "/pico", label: "PICO Verify", icon: <CheckSquare size={15} />, badge: "4" },
        ],
    },
    {
        title: "Output",
        items: [
            { path: "/dossiers", label: "Dossiers", icon: <ClipboardList size={15} />, badge: "3" },
            { path: "/reports", label: "Reports", icon: <FileText size={15} />, badge: "4" },
            { path: "/export", label: "Export Center", icon: <Package size={15} /> },
        ],
    },
    {
        title: "System",
        items: [
            { path: "/models", label: "Models", icon: <Cpu size={15} />, badge: "5" },
            { path: "/runtime-center", label: "Runtime", icon: <Zap size={15} /> },
            { path: "/local-agent", label: "Local Agent", icon: <Satellite size={15} /> },
            { path: "/hardware-status", label: "Hardware", icon: <Monitor size={15} /> },
            { path: "/projects", label: "Projects", icon: <FolderOpen size={15} />, badge: "3" },
            { path: "/runs", label: "Runs", icon: <Play size={15} />, badge: "12" },
            { path: "/logs", label: "Logs", icon: <ScrollText size={15} /> },
            { path: "/media", label: "Media", icon: <ImageIcon size={15} />, badge: "4" },
            { path: "/settings", label: "Settings", icon: <Settings size={15} /> },
        ],
    },
];

export default function LeftRail() {
    const location = useLocation();

    return (
        <nav
            className="shrink-0 border-r border-[var(--border)] flex flex-col py-3 overflow-y-auto hide-scrollbar"
            style={{
                width: 172,
                minWidth: 172,
                background: "var(--bg-app)",
            }}
        >
            {SECTIONS.map((section, si) => (
                <div key={section.title} className={si > 0 ? "mt-1" : ""}>
                    {/* Section header */}
                    <div
                        className="px-4 py-1.5 text-[9px] font-bold uppercase tracking-[0.08em] text-[var(--text-muted)]"
                        style={{ letterSpacing: "0.08em" }}
                    >
                        {section.title}
                    </div>

                    {/* Navigation items */}
                    {section.items.map(item => {
                        const isActive =
                            location.pathname === item.path ||
                            location.pathname.startsWith(item.path + "/");

                        return (
                            <NavLink
                                key={item.path}
                                to={item.path}
                                className="flex items-center gap-2.5 pl-3 pr-2 py-[5px] mx-1 text-[11px] font-medium transition-colors relative group"
                                style={{
                                    color: isActive ? "var(--accent)" : "var(--text-secondary)",
                                    background: isActive ? "var(--accent-subtle)" : "transparent",
                                    borderLeft: isActive ? "3px solid var(--accent)" : "3px solid transparent",
                                    borderRadius: "0 4px 4px 0",
                                }}
                            >
                                <span className="shrink-0 flex items-center justify-center w-[18px]">
                                    {item.icon}
                                </span>
                                <span className="flex-1 truncate">{item.label}</span>
                                {item.badge && (
                                    <span
                                        className="shrink-0 text-[9px] font-bold rounded-sm px-1 py-px"
                                        style={{
                                            background: isActive ? "var(--accent)" : "var(--border)",
                                            color: isActive ? "#fff" : "var(--text-muted)",
                                            minWidth: 18,
                                            textAlign: "center",
                                        }}
                                    >
                                        {item.badge}
                                    </span>
                                )}
                            </NavLink>
                        );
                    })}
                </div>
            ))}
        </nav>
    );
}
