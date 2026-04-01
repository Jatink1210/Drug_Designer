/** EvidenceBadge — clickable badge for PMID / NCT / DOI / Patent IDs with optional confidence. */

import { ExternalLink } from "lucide-react";

interface EvidenceBadgeProps {
    type: "pmid" | "nct" | "doi" | "patent" | "url";
    value: string;
    year?: number;
    confidence?: number;
    onClick?: () => void;
}

const LINK_TEMPLATES: Record<string, (v: string) => string> = {
    pmid: v => `https://pubmed.ncbi.nlm.nih.gov/${v.replace("PMID:", "")}/`,
    nct: v => `https://clinicaltrials.gov/study/${v}`,
    doi: v => `https://doi.org/${v}`,
    patent: v => `https://patents.google.com/patent/${v}`,
    url: v => v,
};

function confidenceColor(c: number): string {
    if (c >= 0.7) return "#16a34a";
    if (c >= 0.4) return "#d97706";
    return "#dc2626";
}

export default function EvidenceBadge({ type, value, year, confidence, onClick }: EvidenceBadgeProps) {
    const url = LINK_TEMPLATES[type]?.(value) || value;
    const label = type.toUpperCase();

    return (
        <a href={url} target="_blank" rel="noopener noreferrer" onClick={e => { if (onClick) { e.preventDefault(); onClick(); } }}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors">
            {confidence != null && (
                <span
                    className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ backgroundColor: confidenceColor(confidence) }}
                    title={`Confidence: ${Math.round(confidence * 100)}%`}
                />
            )}
            <span className="font-semibold">{label}</span>
            <span className="truncate max-w-[80px]">{value.replace("PMID:", "").replace("NCT", "")}</span>
            {year && <span className="text-slate-400">({year})</span>}
            <ExternalLink size={8} />
        </a>
    );
}
