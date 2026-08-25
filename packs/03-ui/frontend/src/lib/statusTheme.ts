/**
 * Intelligent color system for Lucy.
 *
 * Semantic mapping:
 *   GREEN  = Alive / Online / Completed / Success
 *   ORANGE = Waiting / Idle / Queued / Pending
 *   RED    = Crash / Offline / Failed / Error
 *   BLUE   = Running / Active operation
 *   GRAY   = Unknown / Cancelled / Neutral
 *
 * Every component imports from here — change once, update everywhere.
 */

export type SemanticColor = 'green' | 'orange' | 'red' | 'blue' | 'gray'

export interface StatusStyle {
  /** Semantic color key */
  semantic: SemanticColor
  /** Tailwind text color class */
  text: string
  /** Tailwind bg color class (with opacity) */
  bg: string
  /** Tailwind border color class */
  border: string
  /** Tailwind solid bg for dots/indicators */
  dot: string
  /** Tailwind gradient for bars/fills */
  fill: string
  /** Hex value for charts (Recharts) */
  hex: string
  /** Animation class for badges/indicators */
  animation?: string
  /** Human-readable label (FR) */
  label: string
  /** Icon name from lucide-react (mapped in component) */
  icon: string
}

const STYLES: Record<string, StatusStyle> = {
  // --- Agent statuses ---
  online: {
    semantic: 'green',
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    dot: 'bg-emerald-400',
    fill: 'from-emerald-500 to-emerald-400',
    hex: '#22c55e',
    animation: 'animate-pulse-soft',
    label: 'Vivant',
    icon: 'radio',
  },
  offline: {
    semantic: 'red',
    text: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
    dot: 'bg-rose-400',
    fill: 'from-rose-500 to-rose-400',
    hex: '#ef4444',
    label: 'Crash',
    icon: 'x-circle',
  },
  idle: {
    semantic: 'orange',
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    dot: 'bg-amber-400',
    fill: 'from-amber-500 to-amber-400',
    hex: '#f59e0b',
    animation: 'animate-pulse-soft',
    label: 'En attente',
    icon: 'clock',
  },
  unknown: {
    semantic: 'gray',
    text: 'text-base-content/50',
    bg: 'bg-base-300',
    border: 'border-base-content/10',
    dot: 'bg-base-content/40',
    fill: 'from-base-content/40 to-base-content/30',
    hex: '#6b7280',
    label: 'Inconnu',
    icon: 'help-circle',
  },

  // --- Task statuses ---
  running: {
    semantic: 'blue',
    text: 'text-sky-400',
    bg: 'bg-sky-500/10',
    border: 'border-sky-500/30',
    dot: 'bg-sky-400',
    fill: 'from-sky-500 to-sky-400',
    hex: '#0ea5e9',
    animation: 'animate-pulse-fast',
    label: 'En cours',
    icon: 'loader',
  },
  queued: {
    semantic: 'orange',
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    dot: 'bg-amber-400',
    fill: 'from-amber-500 to-amber-400',
    hex: '#f59e0b',
    animation: 'animate-pulse-soft',
    label: 'En file',
    icon: 'clock',
  },
  completed: {
    semantic: 'green',
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    dot: 'bg-emerald-400',
    fill: 'from-emerald-500 to-emerald-400',
    hex: '#22c55e',
    label: 'Terminé',
    icon: 'check-circle',
  },
  failed: {
    semantic: 'red',
    text: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
    dot: 'bg-rose-400',
    fill: 'from-rose-500 to-rose-400',
    hex: '#ef4444',
    label: 'Échec',
    icon: 'x-circle',
  },
  cancelled: {
    semantic: 'gray',
    text: 'text-base-content/50',
    bg: 'bg-base-300',
    border: 'border-base-content/10',
    dot: 'bg-base-content/40',
    fill: 'from-base-content/40 to-base-content/30',
    hex: '#6b7280',
    label: 'Annulé',
    icon: 'ban',
  },
  pending: {
    semantic: 'orange',
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    dot: 'bg-amber-400',
    fill: 'from-amber-500 to-amber-400',
    hex: '#f59e0b',
    animation: 'animate-pulse-soft',
    label: 'En attente',
    icon: 'clock',
  },

  // --- Priority colors ---
  critical: {
    semantic: 'red',
    text: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
    dot: 'bg-rose-400',
    fill: 'from-rose-500 to-rose-400',
    hex: '#ef4444',
    label: 'Critique',
    icon: 'alert-triangle',
  },
  high: {
    semantic: 'orange',
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    dot: 'bg-amber-400',
    fill: 'from-amber-500 to-amber-400',
    hex: '#f59e0b',
    label: 'Haute',
    icon: 'arrow-up',
  },
  normal: {
    semantic: 'blue',
    text: 'text-sky-400',
    bg: 'bg-sky-500/10',
    border: 'border-sky-500/30',
    dot: 'bg-sky-400',
    fill: 'from-sky-500 to-sky-400',
    hex: '#0ea5e9',
    label: 'Normale',
    icon: 'minus',
  },
  low: {
    semantic: 'gray',
    text: 'text-base-content/50',
    bg: 'bg-base-300',
    border: 'border-base-content/10',
    dot: 'bg-base-content/40',
    fill: 'from-base-content/40 to-base-content/30',
    hex: '#6b7280',
    label: 'Basse',
    icon: 'arrow-down',
  },
}

/** Get the style for a status string. Falls back to 'unknown'. */
export function getStatusStyle(status: string | undefined | null): StatusStyle {
  const key = (status || 'unknown').toLowerCase()
  return STYLES[key] ?? STYLES.unknown
}

/** Get just the semantic color for a status */
export function getSemanticColor(status: string | undefined | null): SemanticColor {
  return getStatusStyle(status).semantic
}

/** Get the hex color for chart libraries */
export function getStatusHex(status: string | undefined | null): string {
  return getStatusStyle(status).hex
}

/** Map of semantic color → hex (for chart palettes) */
export const SEMANTIC_HEX: Record<SemanticColor, string> = {
  green: '#22c55e',
  orange: '#f59e0b',
  red: '#ef4444',
  blue: '#0ea5e9',
  gray: '#6b7280',
}

/** Chart color palette in semantic order */
export const CHART_PALETTE = [
  SEMANTIC_HEX.green,
  SEMANTIC_HEX.orange,
  SEMANTIC_HEX.red,
  SEMANTIC_HEX.blue,
  SEMANTIC_HEX.gray,
]
