import { useEffect, useState } from "react";
import { Layers, Loader2, RotateCcw } from "lucide-react";

type OverlaySource = {
  label: string;
  pdbId?: string;
  structureUrl?: string;
  structureText?: string;
  color: string;
};

type OverlayAlignment = {
  leftSelection?: string;
  rightSelection?: string;
};

const REPRESENTATIONS = [
  { id: "cartoon", label: "Cartoon" },
  { id: "backbone", label: "Backbone" },
  { id: "surface", label: "Surface" },
] as const;

type RepresentationId = (typeof REPRESENTATIONS)[number]["id"];

function buildInput(source: OverlaySource): { file: Blob | string; ext?: string } {
  if (source.structureText) {
    return {
      file: new Blob([source.structureText], { type: "text/plain" }),
      ext: "pdb",
    };
  }
  if (source.structureUrl) {
    return { file: source.structureUrl };
  }
  if (source.pdbId) {
    return { file: `rcsb://${source.pdbId}` };
  }
  throw new Error(`Missing structure source for ${source.label}`);
}

export default function StructureComparisonViewer({
  left,
  right,
  alignment,
}: {
  left: OverlaySource;
  right: OverlaySource;
  alignment?: OverlayAlignment;
}) {
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const [representation, setRepresentation] = useState<RepresentationId>("cartoon");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const leftSelection = alignment?.leftSelection || "polymer";
  const rightSelection = alignment?.rightSelection || "polymer";

  useEffect(() => {
    if (!container) return;

    const mountNode = container;
    let disposed = false;
    let stage: any = null;
    let handleResize: (() => void) | null = null;

    async function renderOverlay() {
      setLoading(true);
      setError(null);

      try {
        const nglModule = (await import("ngl")) as unknown as {
          Stage: new (element: HTMLElement, params?: Record<string, unknown>) => any;
        };
        if (disposed) return;

        stage = new nglModule.Stage(mountNode, {
          backgroundColor: "#0f172a",
          cameraType: "orthographic",
          tooltip: true,
        });

        const leftInput = buildInput(left);
        const rightInput = buildInput(right);
        const [leftComponent, rightComponent] = await Promise.all([
          stage.loadFile(leftInput.file, { ext: leftInput.ext, defaultRepresentation: false }),
          stage.loadFile(rightInput.file, { ext: rightInput.ext, defaultRepresentation: false }),
        ]);
        if (disposed) return;

        leftComponent.addRepresentation(representation, {
          colorScheme: "uniform",
          colorValue: left.color,
          sele: leftSelection,
          opacity: representation === "surface" ? 0.48 : 0.92,
          roughness: 0.22,
          metalness: 0,
          useWorker: false,
        });
        rightComponent.addRepresentation(representation, {
          colorScheme: "uniform",
          colorValue: right.color,
          sele: rightSelection,
          opacity: representation === "surface" ? 0.38 : 0.68,
          roughness: 0.22,
          metalness: 0,
          useWorker: false,
        });

        rightComponent.superpose(leftComponent, true, rightSelection, leftSelection);
        stage.autoView();

        handleResize = () => {
          stage.handleResize();
        };
        window.addEventListener("resize", handleResize);
        setLoading(false);
      } catch (nextError) {
        if (disposed) return;
        setError(nextError instanceof Error ? nextError.message : "Unable to render structure overlay");
        setLoading(false);
      }
    }

    void renderOverlay();

    return () => {
      disposed = true;
      if (handleResize) {
        window.removeEventListener("resize", handleResize);
      }
      if (stage) {
        stage.dispose();
      }
    };
  }, [
    container,
    left.color,
    left.label,
    left.pdbId,
    left.structureText,
    left.structureUrl,
    leftSelection,
    representation,
    right.color,
    right.label,
    right.pdbId,
    right.structureText,
    right.structureUrl,
    rightSelection,
  ]);

  return (
    <div className="overflow-hidden rounded-[28px] border" style={{ borderColor: "rgba(15, 23, 42, 0.08)", background: "#0f172a" }}>
      <div className="border-b px-4 py-3" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-white/90">
              <Layers size={14} />
              Overlay viewer
            </div>
            <div className="mt-1 text-[11px] text-white/60">
              {right.label} superposed onto {left.label}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {REPRESENTATIONS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setRepresentation(item.id)}
                className="rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] transition-colors"
                style={{
                  borderColor: representation === item.id ? "rgba(147, 197, 253, 0.55)" : "rgba(255,255,255,0.1)",
                  background: representation === item.id ? "rgba(96, 165, 250, 0.16)" : "transparent",
                  color: representation === item.id ? "#dbeafe" : "rgba(255,255,255,0.72)",
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] text-white/70">
          <span className="inline-flex items-center gap-2 rounded-full border px-3 py-1" style={{ borderColor: "rgba(96, 165, 250, 0.35)" }}>
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: left.color }} />
            {left.label}
          </span>
          <span className="inline-flex items-center gap-2 rounded-full border px-3 py-1" style={{ borderColor: "rgba(248, 113, 113, 0.35)" }}>
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: right.color }} />
            {right.label}
          </span>
          <span className="inline-flex items-center gap-2 rounded-full border px-3 py-1" style={{ borderColor: "rgba(255,255,255,0.12)" }}>
            <RotateCcw size={12} />
            Sequence-guided CA superposition
          </span>
        </div>
      </div>

      <div className="relative h-[540px]">
        <div ref={setContainer} className="h-full w-full" />
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-950/45">
            <Loader2 size={22} className="animate-spin text-white/80" />
          </div>
        ) : null}
        {error ? (
          <div className="absolute inset-x-6 bottom-6 rounded-2xl border px-4 py-3 text-xs text-white/80" style={{ borderColor: "rgba(248, 113, 113, 0.28)", background: "rgba(15, 23, 42, 0.85)" }}>
            {error}
          </div>
        ) : null}
      </div>
    </div>
  );
}