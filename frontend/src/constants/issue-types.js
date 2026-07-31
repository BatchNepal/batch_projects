// ─── Issue type catalog ───────────────────────────────────────────────────────
// One cross-industry catalog. Templates select a domain-appropriate subset, and
// the create editor only shows the pool relevant to the chosen industry — so a
// construction project never sees "Story"/"Spike", and a software project never
// sees "Submittal"/"Punch Item". Colors follow the Joy palette.

export const ISSUE_TYPES = [
  // Universal
  { name: 'Task',         color: '#0B6BCB', icon: 'CheckSquare',    description: 'A unit of work to be completed.' },
  { name: 'Milestone',    color: '#1F7A1F', icon: 'Flag',           description: 'A key delivery point or deadline.' },
  { name: 'Sub-task',     color: '#636B74', icon: 'GitBranch',      description: 'A smaller piece of work under a task.' },

  // Software
  { name: 'Bug',          color: '#C41C1C', icon: 'Bug',            description: 'A defect that needs fixing.' },
  { name: 'Story',        color: '#7C3AED', icon: 'BookOpen',       description: 'A requirement from the user’s perspective.' },
  { name: 'Epic',         color: '#0E6B93', icon: 'Layers',         description: 'A large body of work spanning many tasks.' },
  { name: 'Spike',        color: '#9A5B13', icon: 'Zap',            description: 'A time-boxed research or investigation.' },

  // Construction / EPC
  { name: 'RFI',          color: '#0E6B93', icon: 'HelpCircle',     description: 'Request for information from a stakeholder.' },
  { name: 'Submittal',    color: '#9A5B13', icon: 'FileCheck',      description: 'Material or shop drawing submitted for approval.' },
  { name: 'Change Order', color: '#B45309', icon: 'FileDiff',       description: 'A change to scope, cost, or schedule.' },
  { name: 'Punch Item',   color: '#C41C1C', icon: 'ClipboardCheck', description: 'A defect to fix before handover.' },
  { name: 'Inspection',   color: '#1F7A1F', icon: 'SearchCheck',    description: 'A site or quality inspection.' },

  // Services / Creative
  { name: 'Deliverable',  color: '#7C3AED', icon: 'Package',        description: 'A client-facing deliverable.' },
  { name: 'Request',      color: '#0E6B93', icon: 'Inbox',          description: 'A client ask or support ticket.' },
  { name: 'Approval',     color: '#1F7A1F', icon: 'CircleCheck',    description: 'A sign-off or approval gate.' },
  { name: 'Revision',     color: '#9A5B13', icon: 'RotateCcw',      description: 'A round of requested changes.' },
  { name: 'Asset',        color: '#BE185D', icon: 'Image',          description: 'A creative or media asset.' },

  // Operations
  { name: 'Work Order',   color: '#0B6BCB', icon: 'ClipboardList',  description: 'A scheduled operational job.' },
  { name: 'Incident',     color: '#C41C1C', icon: 'TriangleAlert',  description: 'An unplanned disruption to resolve.' },
  { name: 'Maintenance',  color: '#9A5B13', icon: 'Wrench',         description: 'Preventive or scheduled maintenance.' },
]

// Default selected types per template (the project starts with these).
export const TEMPLATE_ISSUE_TYPES = {
  blank:             ['Task'],
  kanban:            ['Task', 'Bug', 'Story'],
  scrum:             ['Task', 'Bug', 'Story', 'Epic'],
  'bug-tracking':    ['Bug', 'Task', 'Sub-task'],
  'client-delivery': ['Task', 'Deliverable', 'Milestone'],
  retainer:          ['Task', 'Request', 'Revision'],
  'site-management': ['Task', 'RFI', 'Submittal', 'Inspection', 'Milestone'],
  'rfi-tracking':    ['RFI', 'Submittal', 'Sub-task'],
  'recurring-ops':   ['Task', 'Work Order', 'Maintenance'],
  'asset-tracking':  ['Task', 'Work Order', 'Incident'],
  simple:            ['Task'],
}

// The pool of types the editor offers, by template category. Keeps the chooser
// industry-appropriate instead of dumping the whole catalog on every project.
export const ISSUE_TYPE_POOLS = {
  Software:     ['Task', 'Bug', 'Story', 'Epic', 'Spike', 'Sub-task', 'Milestone'],
  Construction: ['Task', 'Milestone', 'RFI', 'Submittal', 'Change Order', 'Punch Item', 'Inspection', 'Sub-task'],
  Services:     ['Task', 'Milestone', 'Deliverable', 'Request', 'Approval', 'Revision', 'Asset', 'Sub-task'],
  Operations:   ['Task', 'Work Order', 'Incident', 'Maintenance', 'Request', 'Milestone', 'Sub-task'],
  General:      ['Task', 'Milestone', 'Sub-task', 'Request'],
}
