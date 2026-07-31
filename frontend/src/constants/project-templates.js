import {
  FilePlus, LayoutGrid, IterationCcw, Bug, Briefcase, RefreshCw,
  HardHat, FileQuestion, CalendarClock, Package, CircleDashed,
} from 'lucide-vue-next'

export const TEMPLATE_CATEGORIES = ['Software', 'Services', 'Construction', 'Operations', 'General']

// Jira/monday-style category accenting — tile bg gets a soft tint of the
// color, the icon gets the full color. Saturated and distinct per industry.
export const CATEGORY_COLORS = {
  'Start fresh': '#64748B',
  Software:      '#2684FF',
  Services:      '#8B5CF6',
  Construction:  '#F59E0B',
  Operations:    '#16A34A',
  General:       '#64748B',
}

export const TEMPLATES = [
  { id: 'blank',           label: 'Blank',          icon: FilePlus,      category: null,           description: 'Start from scratch with no presets.' },
  { id: 'kanban',          label: 'Kanban',          icon: LayoutGrid,    category: 'Software',     description: 'Continuous flow for engineering teams.' },
  { id: 'scrum',           label: 'Scrum',           icon: IterationCcw,  category: 'Software',     description: 'Sprint-based delivery with backlog.' },
  { id: 'bug-tracking',    label: 'Bug tracking',    icon: Bug,           category: 'Software',     description: 'Triage, fix, and close defects fast.' },
  { id: 'client-delivery', label: 'Client delivery', icon: Briefcase,     category: 'Services',     description: 'Scoping through invoicing.',            defaultProjectType: 'tm' },
  { id: 'retainer',        label: 'Retainer',        icon: RefreshCw,     category: 'Services',     description: 'Monthly recurring engagements.',        defaultProjectType: 'retainer' },
  { id: 'site-management', label: 'Site management', icon: HardHat,       category: 'Construction', description: 'Phases, inspections, approvals.' },
  { id: 'rfi-tracking',    label: 'RFI tracking',    icon: FileQuestion,  category: 'Construction', description: 'Request for information workflow.' },
  { id: 'recurring-ops',   label: 'Recurring ops',   icon: CalendarClock, category: 'Operations',   description: 'Repeating operational tasks.' },
  { id: 'asset-tracking',  label: 'Asset tracking',  icon: Package,       category: 'Operations',   description: 'Track assets by ID, serial, location.' },
  { id: 'simple',          label: 'Simple',          icon: CircleDashed,  category: 'General',      description: 'Three states, one task type.' },
]

// Jira calls its work item an "Issue"; Wrike/Monday/Asana call it a "Task" —
// hardcoding either everywhere reads wrong for the other half of our
// templates (a "Bug tracking" software project vs. a "Site management"
// construction one). Software is the one category whose users actually
// come from Jira; everything else maps to the more universal "Task".
export function getTaskWord(templateId) {
  const tpl = TEMPLATES.find(t => t.id === templateId)
  return tpl?.category === 'Software' ? 'Issue' : 'Task'
}
