/** ConfidenceBar — horizontal 0–1 bar with tooltip and semantic label. */

interface ConfidenceBarProps {
  value: number; // 0–1
  label?: string;
  reasoning?: string;
}

function confidenceLabel(value: number): string {
  if (value >= 0.8) return "High";
  if (value >= 0.5) return "Moderate";
  if (value >= 0.3) return "Low";
  return "Very Low";
}

export default function ConfidenceBar({
  value,
  label,
  reasoning,
}: ConfidenceBarProps) {
  const pct = Math.round(value * 100);
  const color = value >= 0.8 ? "#059669" : value >= 0.5 ? "#d97706" : "#dc2626";
  const semantic = confidenceLabel(value);

  return (
    <div className="group relative inline-flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-2 rounded-full bg-[var(--bg-inset)] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span
        className="text-[10px] font-medium w-12 text-right"
        style={{ color }}
      >
        {pct}% <span className="text-[8px] opacity-70">{semantic}</span>
      </span>
      {(reasoning || label) && (
        <div className="absolute bottom-full left-0 mb-1.5 px-2.5 py-1.5 bg-slate-800 text-white text-[10px] rounded-md shadow-lg hidden group-hover:block z-50 max-w-[220px] leading-relaxed">
          {label && <div className="font-semibold mb-0.5">{label}</div>}
          {reasoning && <div className="opacity-80">{reasoning}</div>}
        </div>
      )}
    </div>
  );
}
