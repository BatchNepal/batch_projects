import { ClipboardList, Clock, Wallet, RefreshCw } from 'lucide-vue-next'

// Engagement colors follow the same systematic-color rule as template
// categories: color carries meaning, one hue per engagement model.
export const PROJECT_TYPES = [
  { id: 'internal', label: 'Internal',         sublabel: 'No billing',     icon: ClipboardList, color: '#64748B' },
  { id: 'tm',       label: 'Time & Materials',  sublabel: 'Hourly billing', icon: Clock,         color: '#2684FF' },
  { id: 'fixed',    label: 'Fixed price',       sublabel: 'Lump sum',       icon: Wallet,        color: '#16A34A' },
  { id: 'retainer', label: 'Retainer',          sublabel: 'Monthly',        icon: RefreshCw,     color: '#8B5CF6' },
]

export const VISIBILITY_OPTIONS = [
  { value: 'workspace', label: 'Workspace — all members can view' },
  { value: 'private',   label: 'Private — lead only' },
  { value: 'team',      label: 'Team-only — assignees only' },
]

export const PROJECT_ICON_OPTIONS = [
  'Folder', 'Briefcase', 'Code', 'Palette', 'BarChart3',
  'Wrench', 'Layers', 'Compass', 'Cpu', 'Building2', 'HardHat', 'Sparkles',
  'Activity', 'Aperture', 'Archive', 'Award', 'Battery', 'Bell', 
  'Bluetooth', 'Book', 'Bookmark', 'Box', 'Camera', 'Cast', 
  'Cloud', 'Coffee', 'Cpu', 'Crosshair', 'Database', 'Disc'
]

// Curated, muted palette aligned to the Joy UI design language (tokens.css).
// Deliberately not neon Tailwind brights — these read as premium and sit
// comfortably next to the app's status/priority colors. First = brand blue.
export const PROJECT_COLOR_SWATCHES = [
  '#0B6BCB', // brand blue
  '#0E6B93', // info blue
  '#0891B2', // cyan
  '#0F766E', // teal
  '#1F7A1F', // green
  '#4D7C0F', // olive
  '#A16207', // golden
  '#B45309', // amber
  '#C2410C', // burnt orange
  '#C41C1C', // red
  '#BE185D', // raspberry
  '#9333EA', // purple
  '#6D28D9', // violet
  '#4F46E5', // indigo
  '#475569', // slate
  '#334155', // graphite
]
