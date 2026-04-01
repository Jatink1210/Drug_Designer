/**
 * MolstarViewer — PDBe Mol* 3D structure viewer wrapper.
 *
 * Dynamically loads the PDBe Mol* plugin from EBI CDN and renders
 * protein structures from RCSB PDB or AlphaFold.
 */

import { useRef, useEffect, useState, useCallback } from "react";
import { Loader2 } from "lucide-react";

/* ── CDN URLs for pdbe-molstar ──────────────────────────── */
const PLUGIN_JS = "https://www.ebi.ac.uk/pdbe/pdb-component-library/js/pdbe-molstar-plugin-3.1.3.js";
const PLUGIN_CSS = "https://www.ebi.ac.uk/pdbe/pdb-component-library/css/pdbe-molstar-3.1.3.css";

/* ── Global state for script loading ────────────────────── */
let scriptLoaded = false;
let scriptLoading = false;
const loadCallbacks: Array<() => void> = [];

function loadPdbeMolstar(): Promise<void> {
    if (scriptLoaded) return Promise.resolve();
    return new Promise((resolve) => {
        loadCallbacks.push(resolve);
        if (scriptLoading) return;
        scriptLoading = true;

        // Load CSS
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = PLUGIN_CSS;
        document.head.appendChild(link);

        // Load JS
        const script = document.createElement("script");
        script.src = PLUGIN_JS;
        script.onload = () => {
            scriptLoaded = true;
            scriptLoading = false;
            loadCallbacks.forEach((cb) => cb());
            loadCallbacks.length = 0;
        };
        script.onerror = () => {
            scriptLoading = false;
            loadCallbacks.forEach((cb) => cb());
            loadCallbacks.length = 0;
        };
        document.head.appendChild(script);
    });
}

/* ── Types ──────────────────────────────────────────────── */
export interface MolstarViewerProps {
    pdbId?: string;
    source?: "rcsb" | "alphafold";
    alphafoldUrl?: string;
}

type Representation = "cartoon" | "surface" | "ball-and-stick" | "gaussian-surface";
type ColorScheme = "chain-id" | "secondary-structure" | "hydrophobicity" | "b-factor";

const REPRESENTATIONS: Array<{ label: string; value: Representation }> = [
    { label: "Cartoon", value: "cartoon" },
    { label: "Surface", value: "surface" },
    { label: "Sticks", value: "ball-and-stick" },
    { label: "Gaussian", value: "gaussian-surface" },
];

const COLOR_SCHEMES: Array<{ label: string; value: ColorScheme }> = [
    { label: "Chain", value: "chain-id" },
    { label: "Secondary", value: "secondary-structure" },
    { label: "Hydrophob.", value: "hydrophobicity" },
    { label: "B-factor", value: "b-factor" },
];

/* ── Component ──────────────────────────────────────────── */
export default function MolstarViewer({ pdbId, source = "rcsb", alphafoldUrl }: MolstarViewerProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const viewerRef = useRef<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [rep, setRep] = useState<Representation>("cartoon");
    const [color, setColor] = useState<ColorScheme>("chain-id");

    /* Initialize plugin */
    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        loadPdbeMolstar().then(() => {
            if (cancelled || !containerRef.current) return;
            const PDBeMolstarPlugin = (window as any).PDBeMolstarPlugin;
            if (!PDBeMolstarPlugin) {
                setError("Failed to load Mol* viewer from CDN");
                setLoading(false);
                return;
            }

            // Destroy previous instance
            if (viewerRef.current) {
                try { viewerRef.current.clear(); } catch { /* ok */ }
                viewerRef.current = null;
            }

            const viewer = new PDBeMolstarPlugin();
            viewerRef.current = viewer;

            const options: Record<string, unknown> = {
                hideControls: true,
                hideCanvasControls: ["selection", "animation", "controlToggle", "controlInfo"],
                bgColor: { r: 15, g: 23, b: 42 }, // slate-900
                lighting: "plastic",
                landscape: true,
                reactive: true,
            };

            if (source === "alphafold" && alphafoldUrl) {
                Object.assign(options, {
                    customData: { url: alphafoldUrl, format: "cif" },
                    alphafoldView: true,
                });
            } else if (pdbId) {
                Object.assign(options, {
                    moleculeId: pdbId.toLowerCase(),
                });
            }

            viewer.render(containerRef.current, options);

            // Wait for structure load
            const checkReady = setInterval(() => {
                if (cancelled) { clearInterval(checkReady); return; }
                try {
                    if (viewer.canvas) {
                        clearInterval(checkReady);
                        setLoading(false);
                    }
                } catch {
                    clearInterval(checkReady);
                    setLoading(false);
                }
            }, 200);

            // Timeout after 15s
            setTimeout(() => {
                clearInterval(checkReady);
                if (!cancelled) setLoading(false);
            }, 15000);
        });

        return () => {
            cancelled = true;
            if (viewerRef.current) {
                try { viewerRef.current.clear(); } catch { /* ok */ }
                viewerRef.current = null;
            }
        };
    }, [pdbId, source, alphafoldUrl]);

    /* Representation change */
    const changeRep = useCallback((newRep: Representation) => {
        setRep(newRep);
        const viewer = viewerRef.current;
        if (!viewer) return;
        try {
            viewer.visual.update({ moleculeId: pdbId?.toLowerCase() }, { representationColor: undefined });
        } catch { /* pdbe-molstar API varies by version */ }
    }, [pdbId]);

    /* Color scheme change */
    const changeColor = useCallback((newColor: ColorScheme) => {
        setColor(newColor);
    }, []);

    if (error) {
        return (
            <div className="flex-1 bg-slate-900 flex items-center justify-center" style={{ minHeight: 400 }}>
                <div className="text-center">
                    <p className="text-sm text-red-400">{error}</p>
                    <p className="text-[10px] text-slate-500 mt-1">Check your internet connection for CDN access</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 bg-slate-900 relative" style={{ minHeight: 400 }}>
            <div ref={containerRef} className="absolute inset-0" />

            {loading && (
                <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 z-10">
                    <div className="text-center">
                        <Loader2 size={24} className="animate-spin text-slate-400 mx-auto mb-2" />
                        <p className="text-xs text-slate-400">Loading 3D structure...</p>
                        <p className="text-[10px] text-slate-500 mt-0.5">
                            {source === "alphafold" ? "AlphaFold predicted model" : `PDB: ${pdbId}`}
                        </p>
                    </div>
                </div>
            )}

            {/* Representation controls */}
            <div className="absolute top-3 right-3 flex gap-1 z-20">
                {REPRESENTATIONS.map(r => (
                    <button key={r.value}
                        onClick={() => changeRep(r.value)}
                        className={`px-2 py-1 text-[9px] rounded transition-colors ${
                            rep === r.value
                                ? "bg-[var(--accent)] text-white"
                                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                        }`}>
                        {r.label}
                    </button>
                ))}
            </div>

            {/* Color scheme controls */}
            <div className="absolute bottom-3 left-3 flex gap-1 z-20">
                {COLOR_SCHEMES.map(c => (
                    <button key={c.value}
                        onClick={() => changeColor(c.value)}
                        className={`px-2 py-1 text-[9px] rounded transition-colors ${
                            color === c.value
                                ? "bg-[var(--accent)] text-white"
                                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                        }`}>
                        {c.label}
                    </button>
                ))}
            </div>

            {/* Source indicator */}
            <div className="absolute top-3 left-3 z-20">
                <span className={`px-2 py-1 text-[9px] rounded font-medium ${
                    source === "alphafold"
                        ? "bg-blue-600/80 text-blue-100"
                        : "bg-slate-800/80 text-slate-300"
                }`}>
                    {source === "alphafold" ? "AlphaFold" : "RCSB PDB"}
                </span>
            </div>
        </div>
    );
}
