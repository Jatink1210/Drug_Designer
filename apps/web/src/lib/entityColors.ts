/** Canonical entity-type color map used across all pages for consistent visual identity. */
export const ENTITY_COLORS: Record<string, string> = {
  protein: '#7c3aed',
  gene: '#6366f1',
  disease: '#dc2626',
  drug: '#e11d48',
  compound: '#d97706',
  pathway: '#0891b2',
  publication: '#3b82f6',
  clinical_trial: '#059669',
  variant: '#ea580c',
  molecule: '#f59e0b',
  target: '#8b5cf6',
  unknown: '#94a3b8',
};

/** Get the color for an entity type, falling back to gray for unknown types. */
export function getEntityColor(entityType: string): string {
  return ENTITY_COLORS[entityType.toLowerCase()] || ENTITY_COLORS.unknown;
}
