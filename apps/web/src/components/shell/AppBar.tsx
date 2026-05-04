/** AppBar — Clean top bar with logo, project selector, search, notifications, user. */

import { useState, useEffect, useRef } from "react";
import { Search, FolderOpen, LogOut, Bell, Activity, Command, Menu, ChevronDown, Check } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/components/AuthProvider";
import { ensureApiBase } from "@/lib/api";
import Breadcrumb from "./Breadcrumb";

interface AppBarProps {
  onCommandPalette: () => void;
  onMenuToggle?: () => void;
}

export default function AppBar({ onCommandPalette, onMenuToggle }: AppBarProps) {
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const [projectName, setProjectName] = useState("Loading…");
  const [projects, setProjects] = useState<{id: string; name: string}[]>([]);
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);
  const projectDropdownRef = useRef<HTMLDivElement>(null);
  const [activeRunCount, setActiveRunCount] = useState(0);
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<{id: string; text: string; time: string}[]>([]);
  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((w: string) => w[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "JP";

  useEffect(() => {
    let mounted = true;
    ensureApiBase().then((base) =>
      fetch(`${base}/projects`, { credentials: "include" })
        .then((r) => r.ok ? r.json() : null)
        .then((env) => {
          if (!mounted) return;
          const list = env?.data?.projects ?? env?.data ?? env?.projects ?? [];
          if (Array.isArray(list) && list.length > 0) {
            setProjects(list.map((p: Record<string, unknown>) => ({
              id: String(p.id || p.project_id || ""),
              name: String(p.name || p.title || "Untitled"),
            })));
            setProjectName(String(list[0].name || list[0].title || "Untitled Project"));
          } else {
            setProjectName("No Project");
            setProjects([]);
          }
        })
        .catch(() => { if (mounted) { setProjectName("No Project"); setProjects([]); } }),
    );
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    let mounted = true;
    const poll = () => {
      ensureApiBase().then((base) =>
        fetch(`${base}/runs?state=RUNNING&limit=50`, { credentials: "include" })
          .then((r) => r.ok ? r.json() : null)
          .then((env) => {
            if (!mounted) return;
            const runs = env?.data?.runs ?? env?.data ?? env?.runs ?? [];
            const active = Array.isArray(runs) ? runs.filter((r: Record<string, unknown>) => {
              const st = String(r.state || r.status || "").toUpperCase();
              return st === "RUNNING" || st === "QUEUED" || st === "PENDING";
            }) : [];
            setActiveRunCount(active.length);
            const notes = (Array.isArray(runs) ? runs : []).slice(0, 5).map((r: Record<string, unknown>) => ({
              id: String(r.id || r.run_id || Math.random()),
              text: `${r.run_type || "Run"} — ${String(r.state || "unknown").toLowerCase()}`,
              time: r.created_at ? new Date(r.created_at as string).toLocaleTimeString() : "",
            }));
            setNotifications(notes);
          })
          .catch(() => {}),
      );
    };
    poll();
    const iv = setInterval(poll, 15_000);
    return () => { mounted = false; clearInterval(iv); };
  }, []);

  const handleSignOut = () => {
    if (logout) logout();
    navigate("/login");
  };

  // Close project dropdown on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (projectDropdownRef.current && !projectDropdownRef.current.contains(e.target as Node)) {
        setShowProjectDropdown(false);
      }
    };
    if (showProjectDropdown) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showProjectDropdown]);

  return (
    <header
      role="banner"
      aria-label="Application header"
      className="h-14 flex items-center px-5 shrink-0 z-20 border-b"
      style={{
        background: "var(--bg-elevated)",
        borderColor: "var(--border)",
      }}
    >
      {/* Mobile menu button */}
      <button
        onClick={onMenuToggle}
        className="mobile-menu-btn items-center justify-center p-2 rounded-md mr-2 transition-colors hover:bg-[var(--bg-surface)]"
        style={{ color: "var(--text-secondary)" }}
        aria-label="Toggle navigation menu"
      >
        <Menu size={20} />
      </button>

      {/* Logo */}
      <div
        className="desktop-brand flex items-center gap-2 mr-8 cursor-pointer select-none"
        onClick={() => navigate("/workspace")}
      >
        {/* Logo mark */}
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center"
          style={{ background: "var(--accent)" }}
        >
          <span className="text-white text-xs font-bold">DD</span>
        </div>
        <div className="flex flex-col">
          <span
            className="text-[13px] font-semibold leading-tight"
            style={{ color: "var(--text-primary)" }}
          >
            Drug Designer
          </span>
          <span className="text-[9px] font-medium" style={{ color: "var(--text-muted)" }}>
            Scientific Workbench
          </span>
        </div>
      </div>

      {/* Project selector — §114 dropdown with switch */}
      <div className="relative" ref={projectDropdownRef}>
        <button
          className="flex items-center gap-2 px-3 py-1.5 rounded-md text-[12px] font-medium border transition-all hover:border-[var(--border-strong)] hover:shadow-sm"
          style={{
            borderColor: showProjectDropdown ? "var(--accent)" : "var(--border)",
            color: "var(--text-secondary)",
            background: "var(--bg-app)",
          }}
          onClick={() => setShowProjectDropdown((v) => !v)}
          title="Switch project"
        >
          <FolderOpen size={13} style={{ color: "var(--text-muted)" }} />
          <span className="max-w-[140px] truncate">{projectName}</span>
          <ChevronDown size={11} style={{ color: "var(--text-muted)", transform: showProjectDropdown ? "rotate(180deg)" : "none", transition: "transform 0.15s" }} />
        </button>
        {showProjectDropdown && (
          <div
            className="absolute left-0 top-10 w-64 rounded-lg overflow-hidden z-50"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            <div
              className="px-4 py-2.5 border-b text-[10px] font-semibold uppercase tracking-wide"
              style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
            >
              Switch Project
            </div>
            {projects.length === 0 ? (
              <div className="px-4 py-4 text-[12px] text-center" style={{ color: "var(--text-muted)" }}>
                No projects available
              </div>
            ) : (
              <div className="max-h-52 overflow-y-auto">
                {projects.map((p) => (
                  <button
                    key={p.id}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-[12px] text-left hover:bg-[var(--bg-surface)] transition-colors"
                    style={{ color: p.name === projectName ? "var(--accent)" : "var(--text-primary)" }}
                    onClick={() => {
                      setProjectName(p.name);
                      setShowProjectDropdown(false);
                      navigate(`/projects/${p.id}`);
                    }}
                  >
                    {p.name === projectName && <Check size={12} style={{ color: "var(--accent)" }} />}
                    {p.name !== projectName && <span className="w-3" />}
                    <span className="truncate">{p.name}</span>
                  </button>
                ))}
              </div>
            )}
            <div className="border-t" style={{ borderColor: "var(--border)" }}>
              <button
                className="w-full px-4 py-2.5 text-[11px] font-medium text-left hover:bg-[var(--bg-surface)] transition-colors"
                style={{ color: "var(--accent)" }}
                onClick={() => { setShowProjectDropdown(false); navigate("/projects"); }}
              >
                View all projects →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* §114 Breadcrumb — current page location */}
      <div className="ml-4 hidden md:flex">
        <Breadcrumb />
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Command palette trigger */}
      <button
        onClick={onCommandPalette}
        className="desktop-search flex items-center gap-2 px-3 py-1.5 rounded-md border text-[12px] transition-all hover:border-[var(--border-strong)] hover:shadow-sm mr-3"
        style={{
          borderColor: "var(--border)",
          color: "var(--text-muted)",
          background: "var(--bg-app)",
        }}
      >
        <Search size={13} />
        <span>Search</span>
        <kbd
          className="text-[10px] font-mono px-1.5 py-0.5 rounded border ml-2"
          style={{
            borderColor: "var(--border)",
            background: "var(--bg-elevated)",
            color: "var(--text-muted)",
          }}
        >
          ⌘K
        </kbd>
      </button>

      {/* Active runs indicator */}
      <button
        onClick={() => navigate("/runs")}
        className="relative flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all hover:bg-[var(--bg-surface)] mr-1"
        style={{ color: activeRunCount > 0 ? "var(--accent)" : "var(--text-muted)" }}
        title={`${activeRunCount} active run(s)`}
      >
        <Activity size={14} className={activeRunCount > 0 ? "animate-pulse" : ""} />
        {activeRunCount > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 min-w-[16px] h-[16px] flex items-center justify-center rounded-full text-[9px] font-bold text-white"
            style={{ background: "var(--accent)" }}
          >
            {activeRunCount}
          </span>
        )}
      </button>

      {/* Notifications bell */}
      <div className="relative mr-1">
        <button
          onClick={() => setShowNotifications(!showNotifications)}
          className="flex items-center px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all hover:bg-[var(--bg-surface)]"
          style={{ color: notifications.length > 0 ? "var(--text-secondary)" : "var(--text-muted)" }}
          title="Notifications"
        >
          <Bell size={14} />
          {notifications.length > 0 && (
            <span
              className="absolute -top-0.5 -right-0.5 min-w-[16px] h-[16px] flex items-center justify-center rounded-full text-[9px] font-bold text-white"
              style={{ background: "var(--warning)" }}
            >
              {notifications.length}
            </span>
          )}
        </button>
        {showNotifications && (
          <div
            className="absolute right-0 top-10 w-72 rounded-lg overflow-hidden z-50"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            <div
              className="px-4 py-2.5 border-b text-[11px] font-semibold uppercase tracking-wide"
              style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
            >
              Recent Activity
            </div>
            {notifications.length === 0 ? (
              <div className="px-4 py-6 text-[12px] text-center" style={{ color: "var(--text-muted)" }}>
                No recent activity
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className="px-4 py-2.5 border-b text-[12px] hover:bg-[var(--bg-surface)] cursor-pointer transition-colors"
                  style={{ borderColor: "var(--border-light)" }}
                  onClick={() => { navigate("/runs"); setShowNotifications(false); }}
                >
                  <div style={{ color: "var(--text-primary)" }}>{n.text}</div>
                  <div className="text-[10px] mt-0.5" style={{ color: "var(--text-muted)" }}>{n.time}</div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Sign out */}
      <button
        onClick={handleSignOut}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all hover:bg-[var(--bg-surface)] mr-3"
        style={{ color: "var(--text-muted)" }}
        title="Sign out"
      >
        <LogOut size={13} />
      </button>

      {/* User avatar */}
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-bold cursor-pointer"
        style={{
          background: "linear-gradient(135deg, var(--accent), var(--accent-deep))",
          color: "#fff",
          boxShadow: "0 2px 8px rgba(59, 130, 246, 0.3)",
        }}
        title={user?.full_name || "Dr. Jatin Patel"}
      >
        {initials}
      </div>
    </header>
  );
}
