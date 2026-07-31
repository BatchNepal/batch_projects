// the recipe gallery catalog. Each entry is a LOOSE draft
// (not the full blankDraft()/blankAction() shape AutomationRuleEditor uses
// internally — the editor's own recipeDraft-hydration deep-merges these
// partial overrides onto its real defaults, so a recipe only needs to
// specify what actually differs). `erpOnly: true` recipes are hidden
// unless the workspace's own get_automation_options().triggers actually
// contains an erp.* entry (feature-detection — never hardcode
// the assumption that it shipped).
//
// Client-side only, no network/AI dependency — search below is a plain
// keyword/substring match over `keywords` + `label`.

export const RECIPE_CATEGORIES = [
  { id: 'basics',       label: 'Basics' },
  { id: 'assignment',   label: 'Assignment' },
  { id: 'dates',        label: 'Dates' },
  { id: 'communication',label: 'Communication' },
  { id: 'status',       label: 'Status flows' },
  { id: 'erp',          label: 'ERP & Billing' },
]

export const AUTOMATION_RECIPES = [
  // ── Basics ──────────────────────────────────────────────────────────────
  {
    id: 'basic-assign-on-create', category: 'basics', featured: true,
    label: 'Assign new tasks to someone',
    keywords: ['assign', 'new', 'create', 'owner'],
    draft: { trigger_event: 'task.created', actions: [{ type: 'Assign Issue', cfg: { mode: 'set' } }] },
  },
  {
    id: 'basic-label-on-create', category: 'basics', featured: true,
    label: 'Label every new task',
    keywords: ['label', 'new', 'create', 'tag'],
    draft: { trigger_event: 'task.created', actions: [{ type: 'Add Label' }] },
  },
  {
    id: 'basic-priority-on-create', category: 'basics',
    label: 'Set a default priority for new tasks',
    keywords: ['priority', 'new', 'default'],
    draft: { trigger_event: 'task.created', actions: [{ type: 'Set Priority', cfg: { priority: 'Medium' } }] },
  },
  {
    id: 'basic-comment-on-create', category: 'basics',
    label: 'Post a welcome comment on new tasks',
    keywords: ['comment', 'new', 'welcome'],
    draft: { trigger_event: 'task.created', actions: [{ type: 'Add Comment' }] },
  },
  {
    id: 'basic-scratch', category: 'basics', isBlank: true,
    label: 'Start from scratch',
    keywords: [],
    draft: { trigger_event: 'task.status_changed', actions: [{ type: 'Change Status' }] },
  },

  // ── Assignment ──────────────────────────────────────────────────────────
  {
    id: 'assign-on-priority', category: 'assignment', featured: true,
    label: 'Route Highest-priority tasks to someone',
    keywords: ['assign', 'priority', 'urgent', 'route'],
    draft: {
      trigger_event: 'task.field_changed', trig: { field: 'priority', to: 'Highest' },
      actions: [{ type: 'Assign Issue', cfg: { mode: 'set' } }],
    },
  },
  {
    id: 'assign-on-label', category: 'assignment',
    label: 'Assign tasks with a specific label',
    keywords: ['assign', 'label', 'tag'],
    draft: {
      trigger_event: 'task.created',
      conditions: [{ field: 'labels', op: 'contains', value: '' }],
      actions: [{ type: 'Assign Issue', cfg: { mode: 'add' } }],
    },
  },
  {
    id: 'notify-on-assign', category: 'assignment',
    label: 'Notify someone when they get assigned',
    keywords: ['notify', 'assign', 'assignee'],
    draft: { trigger_event: 'task.assigned', actions: [{ type: 'Notify', cfg: { to: 'assignees' } }] },
  },
  {
    id: 'unassign-notify', category: 'assignment',
    label: 'Notify the reporter when a task is unassigned',
    keywords: ['unassign', 'notify', 'reporter'],
    draft: { trigger_event: 'task.unassigned', actions: [{ type: 'Notify', cfg: { to: 'reporter' } }] },
  },

  // ── Dates ───────────────────────────────────────────────────────────────
  {
    id: 'due-soon-notify', category: 'dates', featured: true,
    label: 'Notify assignees when a task is due soon',
    keywords: ['due', 'soon', 'deadline', 'reminder'],
    draft: { trigger_event: 'task.due_soon', actions: [{ type: 'Notify', cfg: { to: 'assignees' } }] },
  },
  {
    id: 'overdue-escalate', category: 'dates',
    label: 'Bump priority when a task becomes overdue',
    keywords: ['overdue', 'late', 'escalate', 'priority'],
    draft: { trigger_event: 'task.overdue', actions: [{ type: 'Set Priority', cfg: { priority: 'Highest' } }] },
  },
  {
    id: 'set-due-on-status', category: 'dates',
    label: 'Set a due date when work starts',
    keywords: ['due', 'date', 'start', 'in progress'],
    draft: {
      trigger_event: 'task.field_changed', trig: { field: 'status' },
      actions: [{ type: 'Set Due Date', cfg: { dueMode: 'in_days', dueDays: 5 } }],
    },
  },
  {
    id: 'relative-reminder', category: 'dates',
    label: 'Remind the team N days before a date',
    keywords: ['reminder', 'relative', 'before', 'schedule'],
    draft: {
      trigger_event: 'schedule.relative', trig: { field: 'due_date', offset_days: 2, direction: 'before' },
      actions: [{ type: 'Notify', cfg: { to: 'assignees' } }],
    },
  },

  // ── Communication ───────────────────────────────────────────────────────
  {
    id: 'notify-on-comment', category: 'communication',
    label: 'Notify watchers on new comments',
    keywords: ['comment', 'notify', 'watcher'],
    draft: { trigger_event: 'comment.added', actions: [{ type: 'Notify', cfg: { to: 'watchers' } }] },
  },
  {
    id: 'notify-on-done', category: 'communication', featured: true,
    label: 'Notify the reporter when their task is done',
    keywords: ['notify', 'done', 'complete', 'reporter'],
    draft: {
      trigger_event: 'task.field_changed', trig: { field: 'status' },
      actions: [{ type: 'Notify', cfg: { to: 'reporter', message: 'Your task was marked done.' } }],
    },
  },
  {
    id: 'comment-on-priority-change', category: 'communication',
    label: 'Leave a note when priority changes',
    keywords: ['comment', 'priority', 'change', 'log'],
    draft: {
      trigger_event: 'task.field_changed', trig: { field: 'priority' },
      actions: [{ type: 'Add Comment' }],
    },
  },

  // ── Status flows ────────────────────────────────────────────────────────
  {
    id: 'block-move-notify', category: 'status', featured: true,
    label: 'Alert when a blocked task is moved anyway',
    keywords: ['blocked', 'status', 'alert', 'move'],
    draft: {
      trigger_event: 'task.status_changed',
      actions: [{ type: 'Notify', cfg: { to: 'assignees', message: 'This task moved while blocked — double check dependencies.' } }],
    },
  },
  {
    id: 'sprint-move-comment', category: 'status',
    label: 'Comment when a task changes sprint',
    keywords: ['sprint', 'move', 'comment'],
    draft: { trigger_event: 'task.moved_sprint', actions: [{ type: 'Add Comment' }] },
  },
  {
    id: 'label-on-status', category: 'status',
    label: 'Label tasks that reach a specific status',
    keywords: ['label', 'status', 'tag'],
    draft: {
      trigger_event: 'task.field_changed', trig: { field: 'status' },
      actions: [{ type: 'Add Label' }],
    },
  },
  {
    id: 'create-followup-on-done', category: 'status',
    label: 'Spin up a follow-up task when one is done',
    keywords: ['create', 'followup', 'done', 'next task'],
    draft: {
      trigger_event: 'task.field_changed', trig: { field: 'status' },
      actions: [{ type: 'Create Issue', cfg: { title: 'Follow-up', link_to_trigger: true } }],
    },
  },

  // ── ERP & Billing (feature-detected — only shown if 21B's erp.* triggers exist) ──
  {
    id: 'erp-invoice-notify', category: 'erp', erpOnly: true, featured: true,
    label: 'Notify the PM when an invoice is submitted',
    keywords: ['invoice', 'erp', 'billing', 'notify', 'sales invoice'],
    draft: { trigger_event: 'erp.invoice_submitted', actions: [{ type: 'Notify' }] },
  },
  {
    id: 'erp-payment-received', category: 'erp', erpOnly: true, featured: true,
    label: 'Notify when an invoice is fully paid',
    keywords: ['payment', 'paid', 'invoice', 'outstanding', 'erp'],
    draft: {
      trigger_event: 'erp.payment_received',
      conditions: [{ field: 'outstanding', op: 'eq', value: 0 }],
      actions: [{ type: 'Notify', cfg: { message: 'Invoice fully paid.' } }],
    },
  },
  {
    id: 'erp-so-confirmed-comment', category: 'erp', erpOnly: true,
    label: 'Log a comment when a Sales Order is confirmed',
    keywords: ['sales order', 'confirmed', 'erp', 'comment'],
    draft: { trigger_event: 'erp.so_confirmed', actions: [{ type: 'Notify' }] },
  },
]

export function filterRecipes(recipes, query, hasErpTriggers) {
  const visible = recipes.filter(r => !r.erpOnly || hasErpTriggers)
  const q = (query || '').trim().toLowerCase()
  if (!q) return visible
  return visible.filter(r =>
    r.label.toLowerCase().includes(q) ||
    r.keywords.some(k => k.includes(q) || q.includes(k)) ||
    r.category.includes(q)
  )
}
