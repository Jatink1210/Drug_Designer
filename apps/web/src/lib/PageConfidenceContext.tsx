import { createContext, useContext, useState, type ReactNode } from "react";

export interface PageConfidenceData {
  freshness: "current" | "stale" | "unknown";
  freshnessDetail?: string;
  sourceCount: number;
  sourcesQueried?: string[];
  confidenceRange?: [number, number];
  avgConfidence?: number;
}

interface PageConfidenceContextType {
  confidence: PageConfidenceData | null;
  setConfidence: (data: PageConfidenceData | null) => void;
}

const PageConfidenceContext = createContext<PageConfidenceContextType>({
  confidence: null,
  setConfidence: () => {},
});

export function PageConfidenceProvider({ children }: { children: ReactNode }) {
  const [confidence, setConfidence] = useState<PageConfidenceData | null>(null);
  return (
    <PageConfidenceContext.Provider value={{ confidence, setConfidence }}>
      {children}
    </PageConfidenceContext.Provider>
  );
}

export function useSetPageConfidence() {
  const { setConfidence } = useContext(PageConfidenceContext);
  return setConfidence;
}

export function usePageConfidenceData() {
  return useContext(PageConfidenceContext).confidence;
}
