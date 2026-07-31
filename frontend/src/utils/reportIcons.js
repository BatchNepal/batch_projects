// Curated, report-flavored icon + color palette for saved reports.
// Wrike-style: each report gets a colorful icon tile. Icons are lucide
// components; we store only the string name on the report and resolve it here.
import {
  BarChart3, BarChartBig, LineChart, AreaChart, PieChart, ChartPie,
  TrendingUp, TrendingDown, Activity, Gauge, Target, Flag, Rocket,
  GitBranch, Layers, Workflow, Timer, Clock, CalendarDays, Zap,
  Users, Briefcase, DollarSign, Wallet, Goal, Trophy, Sparkles,
  ClipboardList, FileBarChart2, Compass, Flame, Boxes, GitCompareArrows,
} from 'lucide-vue-next'

// name → component. The first entry is the default.
export const REPORT_ICONS = {
  FileBarChart2, BarChart3, BarChartBig, LineChart, AreaChart, PieChart, ChartPie,
  TrendingUp, TrendingDown, Activity, Gauge, Target, Flag, Rocket,
  GitBranch, Layers, Workflow, Timer, Clock, CalendarDays, Zap,
  Users, Briefcase, DollarSign, Wallet, Goal, Trophy, Sparkles,
  ClipboardList, Compass, Flame, Boxes, GitCompareArrows,
}

// Ordered list for the picker grid.
export const REPORT_ICON_NAMES = Object.keys(REPORT_ICONS)

// A vivid, Monday/Wrike-like accent palette for report tiles.
export const REPORT_COLORS = [
  '#0073EA', // blue
  '#579BFC', // light blue
  '#00C875', // green
  '#037F4C', // dark green
  '#FDAB3D', // orange
  '#FF7575', // coral
  '#E2445C', // red
  '#A25DDC', // purple
  '#9D50DD', // violet
  '#00D2D2', // teal
  '#784BD1', // indigo
  '#FF158A', // pink
]

export function reportIcon(name) {
  return REPORT_ICONS[name] || REPORT_ICONS.FileBarChart2
}
