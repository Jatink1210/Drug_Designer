/**
 * UI Component Library - Apple Design System
 * 
 * Implements FR-UI-003: Component Library (Apple-Style)
 * 
 * This module exports all Apple-style UI components following the design system
 * established in Tasks 7.1 (SF Pro typography) and 7.2 (binary color system).
 */

// Core Components
export { Button } from './Button';
export type { ButtonProps, ButtonVariant, ButtonSize, ButtonState } from './Button';

export { Card } from './Card';
export type { CardProps, CardVariant, CardState } from './Card';

export { Navigation } from './Navigation';
export type { NavigationProps, NavigationItem } from './Navigation';

// Form Components
export { Input } from './Input';
export type { InputProps, InputVariant, InputSize, InputState } from './Input';

export { Textarea } from './Textarea';
export type { TextareaProps, TextareaSize, TextareaState } from './Textarea';

export { Select } from './Select';
export type { SelectProps, SelectOption, SelectSize, SelectState } from './Select';

export { Checkbox } from './Checkbox';
export type { CheckboxProps, CheckboxSize } from './Checkbox';

export { Radio } from './Radio';
export type { RadioProps, RadioSize } from './Radio';

// Overlay Components
export { Modal } from './Modal';
export type { ModalProps, ModalSize } from './Modal';

export { Tooltip } from './Tooltip';
export type { TooltipProps, TooltipPosition } from './Tooltip';

// Data Display Components
export { Table } from './Table';
export type { TableProps, TableColumn } from './Table';

// Specialized Components
export { default as CitationCard } from './CitationCard';
export { default as CommandPalette } from './CommandPalette';
export { default as ConfidenceBar } from './ConfidenceBar';
export { default as ContradictionBanner } from './ContradictionBanner';
export { default as DataGrid } from './DataGrid';
export { default as EntityPill } from './EntityPill';
export { default as EvidenceBadge } from './EvidenceBadge';
export { default as ForceGraph } from './ForceGraph';
export { default as MiniGraphPreview } from './MiniGraphPreview';
export { default as NotificationToast } from './NotificationToast';
export { default as OfflineBanner } from './OfflineBanner';
export { default as ProvenanceBadge } from './ProvenanceBadge';
export { default as RunProgressTracker } from './RunProgressTracker';
export { default as SmilesRenderer } from './SmilesRenderer';
export { default as StateWrapper } from './StateWrapper';
export { default as TimelineMiniChart } from './TimelineMiniChart';
