/** AppBar — Top bar with logo, project selector, command palette, sign out, and user avatar. */

import { Search, FolderOpen, LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/components/AuthProvider";

interface AppBarProps {
    onCommandPalette: () => void;
}

export default function AppBar({ onCommandPalette }: AppBarProps) {
    const navigate = useNavigate();
    const { logout, user } = useAuth();
    const initials = user?.full_name
        ? user.full_name.split(" ").map((w: string) => w[0]).join("").toUpperCase().slice(0, 2)
        : "JP";

    const handleSignOut = () => {
        if (logout) logout();
        navigate("/login");
    };

    return (
        <header
            className="h-12 flex items-center px-6 shrink-0 z-20 border-b border-[var(--border)]"
            style={{ background: "var(--bg-elevated)" }}
        >
            {/* Logo */}
            <div
                className="flex items-center gap-1.5 mr-6 cursor-pointer"
                onClick={() => navigate("/workspace")}
            >
                <span
                    className="text-sm font-bold tracking-tight"
                    style={{ fontFamily: "var(--font-display)", color: "var(--accent)" }}
                >
                    Drug Designer
                </span>
                <sup
                    className="text-[8px] font-bold"
                    style={{ color: "var(--text-muted)" }}
                >
                    v2.0
                </sup>
            </div>

            {/* Project selector */}
            <button
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-medium border transition-colors hover:border-[var(--text-muted)]"
                style={{
                    borderColor: "var(--border)",
                    color: "var(--text-secondary)",
                    background: "var(--bg-surface)",
                }}
                onClick={() => navigate("/projects")}
                title="Switch project"
            >
                <FolderOpen size={12} />
                <span>Project: Alzheimer's Pipeline</span>
                <span style={{ color: "var(--text-muted)" }}>▾</span>
            </button>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Command palette trigger */}
            <button
                onClick={onCommandPalette}
                className="flex items-center gap-2 px-2.5 py-1 rounded border text-[11px] transition-colors hover:border-[var(--text-muted)] mr-3"
                style={{
                    borderColor: "var(--border)",
                    color: "var(--text-muted)",
                    background: "var(--bg-surface)",
                }}
            >
                <Search size={12} />
                <span>⌘K Search</span>
            </button>

            {/* Sign out */}
            <button
                onClick={handleSignOut}
                className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium transition-colors hover:bg-[var(--border-light)] mr-2"
                style={{ color: "var(--text-muted)" }}
                title="Sign out"
            >
                <LogOut size={11} />
                <span>Sign Out</span>
            </button>

            {/* User avatar */}
            <div
                className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold cursor-pointer"
                style={{
                    background: "var(--accent)",
                    color: "#fff",
                }}
                title={user?.full_name || "Dr. Jatin Patel"}
            >
                {initials}
            </div>
        </header>
    );
}
