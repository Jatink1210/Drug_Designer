/** TimelineMiniChart — simple bar chart showing counts by year. */

interface TimelineMiniChartProps {
    data: { year: number; count: number }[];
    label?: string;
    height?: number;
    color?: string;
}

export default function TimelineMiniChart({ data, label, height = 60, color = "var(--accent)" }: TimelineMiniChartProps) {
    if (data.length === 0) return null;
    const max = Math.max(...data.map(d => d.count));

    return (
        <div className="bg-white rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
            {label && <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">{label}</div>}
            <div className="flex items-end gap-[2px]" style={{ height }}>
                {data.map(d => {
                    const h = max > 0 ? (d.count / max) * height : 0;
                    return (
                        <div key={d.year} className="group relative flex-1 min-w-[3px]">
                            <div className="w-full rounded-t-sm transition-all hover:opacity-80"
                                style={{ height: Math.max(h, 2), background: color }} />
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-1.5 py-0.5 bg-slate-800 text-white text-[9px] rounded hidden group-hover:block whitespace-nowrap z-10">
                                {d.year}: {d.count}
                            </div>
                        </div>
                    );
                })}
            </div>
            <div className="flex justify-between mt-1">
                <span className="text-[9px] text-[var(--text-muted)]">{data[0]?.year}</span>
                <span className="text-[9px] text-[var(--text-muted)]">{data[data.length - 1]?.year}</span>
            </div>
        </div>
    );
}
