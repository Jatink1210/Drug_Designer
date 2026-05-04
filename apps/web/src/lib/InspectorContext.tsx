/** InspectorContext — §114 Right Inspector/Detail Drawer.
 *  Any page can open the drawer by calling openInspector(entity).
 */

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

interface InspectorContextValue {
  entity: Record<string, unknown> | null;
  openInspector: (entity: Record<string, unknown>) => void;
  closeInspector: () => void;
}

const InspectorContext = createContext<InspectorContextValue | null>(null);

export function InspectorProvider({ children }: { children: ReactNode }) {
  const [entity, setEntity] = useState<Record<string, unknown> | null>(null);

  const openInspector = useCallback((e: Record<string, unknown>) => {
    setEntity(e);
  }, []);

  const closeInspector = useCallback(() => {
    setEntity(null);
  }, []);

  return (
    <InspectorContext.Provider value={{ entity, openInspector, closeInspector }}>
      {children}
    </InspectorContext.Provider>
  );
}

export function useInspector() {
  const ctx = useContext(InspectorContext);
  if (!ctx) throw new Error("useInspector must be used within InspectorProvider");
  return ctx;
}
