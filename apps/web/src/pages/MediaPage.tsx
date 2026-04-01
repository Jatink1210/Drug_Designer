import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Expand, Image as ImageIcon } from "lucide-react";
import { ensureApiBase } from "@/lib/api";

interface Job {
    job_id: string;
    name: string;
    status: string;
}

interface Artifact {
    artifact_id: string;
    type: string;
    title: string;
    description: string;
    svg_path: string | null;
    png_path: string | null;
}

export default function MediaPage() {
    const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
    const [apiBase, setApiBase] = useState("");

    useEffect(() => { ensureApiBase().then(setApiBase); }, []);

    const { data: jobs } = useQuery<Job[]>({
        queryKey: ["media-jobs"],
        queryFn: async () => {
            const base = await ensureApiBase();
            const res = await fetch(`${base}/logs/jobs`);
            if (!res.ok) return [];
            return res.json();
        },
    });

    const jobId = selectedJobId || (jobs && jobs.length > 0 ? jobs[0].job_id : null);

    const { data: artifacts, isLoading } = useQuery<Artifact[]>({
        queryKey: ["media-figures", jobId],
        queryFn: async () => {
            if (!jobId) return [];
            const base = await ensureApiBase();
            const res = await fetch(`${base}/jobs/${jobId}/media`);
            if (!res.ok) return [];
            return res.json();
        },
        enabled: !!jobId,
    });

    const downloadArtifact = (artifactId: string, format: "svg" | "png") => {
        if (!apiBase) return;
        const a = document.createElement("a");
        a.href = `${apiBase}/media/${artifactId}/download?format=${format}`;
        a.download = `${artifactId}.${format}`;
        a.click();
    };

    const exportAll = () => {
        if (!artifacts || !apiBase) return;
        for (const art of artifacts) {
            if (art.png_path) downloadArtifact(art.artifact_id, "png");
        }
    };

    return (
        <div className="flex-1 flex flex-col h-full bg-[var(--bg-app)] overflow-hidden">
            {/* Header */}
            <div className="shrink-0 h-14 border-b border-[var(--border)] bg-[var(--bg-surface)] flex items-center px-6 justify-between">
                <div className="flex items-center gap-3">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">Media Gallery</h1>
                    <select
                        value={jobId || ""}
                        onChange={(e) => setSelectedJobId(e.target.value || null)}
                        className="text-xs bg-[var(--bg-app)] border border-[var(--border)] text-[var(--text-secondary)] px-2 py-1 rounded-md outline-none"
                    >
                        {!jobs?.length && <option value="">No jobs</option>}
                        {jobs?.map((j) => (
                            <option key={j.job_id} value={j.job_id}>
                                {j.name || j.job_id}
                            </option>
                        ))}
                    </select>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={exportAll}
                        disabled={!artifacts?.length}
                        className="flex items-center gap-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-3 py-1.5 rounded-md text-sm font-medium transition-colors shadow-sm disabled:opacity-40"
                    >
                        <Download size={14} />
                        Export All
                    </button>
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-auto p-6">
                <div className="max-w-7xl mx-auto space-y-6">
                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center p-20 text-[var(--text-muted)]">
                            <div className="w-8 h-8 border-4 border-[var(--border)] border-t-[var(--accent)] rounded-full animate-spin mb-4" />
                            <p>Loading figures…</p>
                        </div>
                    ) : !artifacts || artifacts.length === 0 ? (
                        <div className="flex flex-col items-center justify-center p-20 text-[var(--text-muted)] text-center border-2 border-dashed border-[var(--border)] rounded-[var(--radius-lg)]">
                            <ImageIcon size={32} className="mb-2 opacity-50" />
                            <p>No figures available for this job.</p>
                            <p className="text-xs mt-1">Run a query to generate publication-ready figures.</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-8">
                            {artifacts.map((art) => (
                                <div key={art.artifact_id} className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-[var(--radius-lg)] overflow-hidden shadow-[var(--shadow-md)] flex flex-col group">
                                    <div className="aspect-[4/3] bg-white relative flex items-center justify-center border-b border-[var(--border-light)] overflow-hidden p-2">
                                        {apiBase && art.png_path ? (
                                            <img
                                                src={`${apiBase}/media/${art.artifact_id}/download?format=png`}
                                                alt={art.title}
                                                className="w-full h-full object-contain"
                                            />
                                        ) : (
                                            <div className="flex flex-col items-center text-[var(--text-muted)]">
                                                <ImageIcon size={32} className="opacity-30 mb-1" />
                                                <span className="text-xs">No preview</span>
                                            </div>
                                        )}
                                        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                                            <button
                                                onClick={() => downloadArtifact(art.artifact_id, "png")}
                                                title="Download PNG"
                                                className="bg-white/90 text-[var(--text-primary)] p-1.5 rounded shadow-sm hover:text-[var(--accent)]"
                                            >
                                                <Expand size={14} />
                                            </button>
                                        </div>
                                    </div>
                                    <div className="p-4 flex flex-col gap-1">
                                        <div className="flex justify-between items-start">
                                            <h3 className="font-semibold text-base text-[var(--text-primary)]">{art.title}</h3>
                                            <span className="text-[10px] text-[var(--text-secondary)] font-medium tracking-wide bg-[var(--border-light)] px-2 py-0.5 rounded uppercase">
                                                {art.type}
                                            </span>
                                        </div>
                                        <p className="text-sm text-[var(--text-secondary)] mt-1 line-clamp-2">
                                            {art.description}
                                        </p>

                                        <div className="grid grid-cols-2 gap-2 mt-4 pt-4 border-t border-[var(--border-light)]">
                                            <button
                                                onClick={() => downloadArtifact(art.artifact_id, "svg")}
                                                disabled={!art.svg_path}
                                                className="flex items-center justify-center gap-1.5 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--border-light)] rounded font-medium transition-colors disabled:opacity-30"
                                            >
                                                <Download size={12} /> SVG
                                            </button>
                                            <button
                                                onClick={() => downloadArtifact(art.artifact_id, "png")}
                                                disabled={!art.png_path}
                                                className="flex items-center justify-center gap-1.5 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--border-light)] rounded font-medium transition-colors disabled:opacity-30"
                                            >
                                                <Download size={12} /> PNG
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
