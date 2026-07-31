export const WORKFLOW_PRESETS = {
  blank: [
    { name: 'Backlog', color: '#64748B', category: 'unstarted' },
    { name: 'Done',    color: '#12B76A', category: 'completed' },
  ],
  kanban: [
    { name: 'To Do',       color: '#64748B', category: 'unstarted' },
    { name: 'In Progress', color: '#2684FF', category: 'started' },
    { name: 'In Review',   color: '#8B5CF6', category: 'started' },
    { name: 'Done',        color: '#12B76A', category: 'completed' },
    { name: 'Cancelled',   color: '#94A3B8', category: 'cancelled' },
  ],
  scrum: [
    { name: 'Backlog',     color: '#64748B', category: 'unstarted' },
    { name: 'To Do',       color: '#64748B', category: 'unstarted' },
    { name: 'In Progress', color: '#2684FF', category: 'started' },
    { name: 'In Review',   color: '#8B5CF6', category: 'started' },
    { name: 'Done',        color: '#12B76A', category: 'completed' },
  ],
  'bug-tracking': [
    { name: 'New',         color: '#64748B', category: 'unstarted' },
    { name: 'Triaged',     color: '#2684FF', category: 'started' },
    { name: 'In Progress', color: '#0EA5E9', category: 'started' },
    { name: 'Resolved',    color: '#12B76A', category: 'completed' },
  ],
  'client-delivery': [
    { name: 'Scoping',     color: '#64748B', category: 'unstarted' },
    { name: 'In Progress', color: '#2684FF', category: 'started' },
    { name: 'In Review',   color: '#8B5CF6', category: 'started' },
    { name: 'Delivered',   color: '#12B76A', category: 'completed' },
    { name: 'Invoiced',    color: '#14B8A6', category: 'completed' },
  ],
  retainer: [
    { name: 'To Do',       color: '#64748B', category: 'unstarted' },
    { name: 'In Progress', color: '#2684FF', category: 'started' },
    { name: 'In Review',   color: '#8B5CF6', category: 'started' },
    { name: 'Done',        color: '#12B76A', category: 'completed' },
    { name: 'Cancelled',   color: '#94A3B8', category: 'cancelled' },
  ],
  'site-management': [
    { name: 'Planned',    color: '#64748B', category: 'unstarted' },
    { name: 'Active',     color: '#2684FF', category: 'started' },
    { name: 'Inspected',  color: '#8B5CF6', category: 'started' },
    { name: 'Approved',   color: '#12B76A', category: 'completed' },
    { name: 'Closed',     color: '#64748B', category: 'completed' },
  ],
  'rfi-tracking': [
    { name: 'Open',              color: '#64748B', category: 'unstarted' },
    { name: 'Awaiting Response', color: '#2684FF', category: 'started' },
    { name: 'Resolved',          color: '#12B76A', category: 'completed' },
    { name: 'Cancelled',         color: '#94A3B8', category: 'cancelled' },
  ],
  'recurring-ops': [
    { name: 'To Do', color: '#64748B', category: 'unstarted' },
    { name: 'In Progress', color: '#2684FF', category: 'started' },
    { name: 'Done',  color: '#12B76A', category: 'completed' },
  ],
  'asset-tracking': [
    { name: 'Active',            color: '#2684FF', category: 'started' },
    { name: 'Under Maintenance', color: '#8B5CF6', category: 'started' },
    { name: 'Decommissioned',    color: '#64748B', category: 'cancelled' },
  ],
  simple: [
    { name: 'To Do', color: '#64748B', category: 'unstarted' },
    { name: 'In Progress', color: '#2684FF', category: 'started' },
    { name: 'Done',  color: '#12B76A', category: 'completed' },
  ],
}

export const STATUS_COLOR_PALETTE = [
  '#64748B', '#64748B', '#2684FF', '#0EA5E9', '#14B8A6',
  '#8B5CF6', '#94A3B8', '#12B76A', '#0E6B93', '#BE185D',
]

export const CATEGORY_STYLES = {
  unstarted: { bg: '#F0F4F8', color: '#64748B', label: 'Unstarted' },
  started:   { bg: '#E3EFFB', color: '#2684FF', label: 'Started' },
  completed: { bg: '#E3FBE3', color: '#12B76A', label: 'Completed' },
  cancelled: { bg: '#FCE4E4', color: '#94A3B8', label: 'Cancelled' },
}
