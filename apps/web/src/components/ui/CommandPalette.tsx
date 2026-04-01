/** CommandPalette — ⌘K global search overlay. */

import { useState, useEffect, useRef } from "react";
import { Search, X, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface CommandPaletteProps {
    open: boolean;
    onClose: () => void;
}

interface Command {
    label: string;
    path: string;
    section: string;
}

const COMMANDS: Command[] = [
    { label: "Search", path: "/search", section: "Workbenches" },
    { label: "Evidence & Literature", path: "/evidence", section: "Workbenches" },
    { label: "Structure Workbench", path: "/structure", section: "Workbenches" },
    { label: "Docking & Design", path: "/design", section: "Workbenches" },
    { label: "Pathways", path: "/pathways", section: "Workbenches" },
    { label: "Graph Lab", path: "/analysis", section: "Workbenches" },
    { label: "Knowledge Graph", path: "/kg", section: "Workbenches" },
    { label: "PICO Verification", path: "/pico", section: "Workbenches" },
    { label: "Translational Research", path: "/translational", section: "Workbenches" },
    { label: "Entity Catalog", path: "/catalog", section: "Workbenches" },
    { label: "Data Manager", path: "/data", section: "Workbenches" },
    { label: "About & Diagnostics", path: "/about", section: "Workbenches" },
];

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
    const [query, setQuery] = useState("");
    const [selected, setSelected] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        if (open) { setQuery(""); setSelected(0); setTimeout(() => inputRef.current?.focus(), 50); }
    }, [open]);

    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); if (!open) onClose(); /* toggle via parent */ }
            if (e.key === "Escape" && open) onClose();
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [open, onClose]);

    const filtered = COMMANDS.filter(c => c.label.toLowerCase().includes(query.toLowerCase()));

    const exec = (cmd: Command) => { navigate(cmd.path); onClose(); };

    const handleKey = (e: React.KeyboardEvent) => {
        if (e.key === "ArrowDown") { e.preventDefault(); setSelected(s => Math.min(s + 1, filtered.length - 1)); }
        if (e.key === "ArrowUp") { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); }
        if (e.key === "Enter" && filtered[selected]) exec(filtered[selected]);
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]" onClick={onClose}>
            <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" />
            <div className="relative glass-elevated rounded-xl w-[520px] overflow-hidden border" style={{ borderColor: "var(--border)" }}
                onClick={e => e.stopPropagation()}>
                <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
                    <Search size={16} className="text-[var(--text-muted)]" />
                    <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)} onKeyDown={handleKey}
                        placeholder="Search workbenches, entities, commands…"
                        className="flex-1 text-sm bg-transparent outline-none placeholder:text-[var(--text-muted)]" />
                    <button onClick={onClose} className="p-1 rounded hover:bg-gray-100"><X size={14} className="text-[var(--text-muted)]" /></button>
                </div>
                <div className="max-h-[300px] overflow-y-auto py-1">
                    {filtered.length === 0 && <div className="px-4 py-6 text-center text-sm text-[var(--text-muted)]">No results</div>}
                    {filtered.map((cmd, i) => (
                        <button key={cmd.path} onClick={() => exec(cmd)}
                            className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors ${selected === i ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-primary)] hover:bg-[var(--border-light)]"}`}>
                            <ArrowRight size={14} className="opacity-40" />
                            <span className="flex-1">{cmd.label}</span>
                            <span className="text-[10px] text-[var(--text-muted)]">{cmd.section}</span>
                        </button>
                    ))}
                </div>
                <div className="px-4 py-2 border-t text-[10px] text-[var(--text-muted)] flex gap-3" style={{ borderColor: "var(--border)" }}>
                    <span>↑↓ Navigate</span><span>↵ Open</span><span>Esc Close</span>
                </div>
            </div>
        </div>
    );
}
