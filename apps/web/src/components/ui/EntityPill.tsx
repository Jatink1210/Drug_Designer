/** EntityPill — compact entity badge with type icon and name. */

const TYPE_COLORS: Record<string, string> = {
  protein: "#6366f1",
  gene: "#0891b2",
  molecule: "#d97706",
  drug: "#059669",
  disease: "#dc2626",
  pathway: "#7c3aed",
  structure: "#0284c7",
  clinical_trial: "#4f46e5",
  publication: "#64748b",
  patent: "#92400e",
  interaction: "#0d9488",
  variant: "#be185d",
  assay: "#7c2d12",
};

interface EntityPillProps {
  type: string;
  name: string;
  id?: string;
  onClick?: () => void;
}

export default function EntityPill({
  type,
  name,
  id,
  onClick,
}: EntityPillProps) {
  const color = TYPE_COLORS[type] || "#6b7280";
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium hover:opacity-80 transition-opacity max-w-[200px]"
      style={{
        background: `${color}12`,
        color,
        border: `1px solid ${color}30`,
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{ background: color }}
      />
      <span className="truncate">{name}</span>
      {id && <span className="opacity-60 truncate">({id})</span>}
    </button>
  );
}

export { TYPE_COLORS };
