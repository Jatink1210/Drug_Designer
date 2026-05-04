/** SmilesRenderer — 2D SMILES molecule rendering via smiles-drawer.
 *  Renders a SMILES string to a canvas element.
 */

import { useRef, useEffect } from "react";

interface SmilesRendererProps {
  smiles: string;
  width?: number;
  height?: number;
  theme?: "light" | "dark";
}

export default function SmilesRenderer({ smiles, width = 200, height = 150, theme = "dark" }: SmilesRendererProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current || !smiles) return;
    let cancelled = false;

    (async () => {
      try {
        const SmilesDrawer = await import("smiles-drawer");
        if (cancelled) return;

        const options = {
          width,
          height,
          bondThickness: 1.5,
          bondLength: 15,
          shortBondLength: 0.85,
          fontSize: 8,
          fontSizeLarge: 10,
          padding: 10,
          themes: {
            dark: {
              C: "#d1d5db",
              O: "#ef4444",
              N: "#3b82f6",
              S: "#eab308",
              P: "#f97316",
              F: "#22c55e",
              CL: "#22c55e",
              BR: "#a855f7",
              I: "#a855f7",
              H: "#9ca3af",
              BACKGROUND: "#00000000",
            },
            light: {
              C: "#374151",
              O: "#dc2626",
              N: "#2563eb",
              S: "#ca8a04",
              P: "#ea580c",
              F: "#16a34a",
              CL: "#16a34a",
              BR: "#9333ea",
              I: "#9333ea",
              H: "#6b7280",
              BACKGROUND: "#00000000",
            },
          },
        };

        // smiles-drawer v2 API
        const drawer = new (SmilesDrawer.SmiDrawer || SmilesDrawer.Drawer || SmilesDrawer.default)(options);
        if (typeof drawer.draw === "function") {
          drawer.draw(smiles, canvasRef.current, theme);
        } else if (typeof (SmilesDrawer as Record<string, unknown>).parse === "function") {
          const tree = (SmilesDrawer as Record<string, unknown> & { parse: (s: string) => unknown }).parse(smiles);
          const d = new (SmilesDrawer.Drawer as unknown as new (o: typeof options) => { draw: (t: unknown, c: HTMLCanvasElement, tt: string) => void })(options);
          d.draw(tree, canvasRef.current, theme);
        }
      } catch {
        // Fallback: draw SMILES as text on canvas
        const ctx = canvasRef.current?.getContext("2d");
        if (ctx) {
          ctx.clearRect(0, 0, width, height);
          ctx.fillStyle = theme === "dark" ? "#9ca3af" : "#374151";
          ctx.font = "10px monospace";
          const lines = [];
          for (let i = 0; i < smiles.length; i += Math.floor(width / 6)) {
            lines.push(smiles.slice(i, i + Math.floor(width / 6)));
          }
          lines.forEach((line, idx) => {
            ctx.fillText(line, 4, 14 + idx * 14);
          });
        }
      }
    })();

    return () => { cancelled = true; };
  }, [smiles, width, height, theme]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ width, height, display: "block" }}
    />
  );
}
