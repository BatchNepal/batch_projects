// The ONE rule→sentence renderer. Used by
// AutomationRuleEditor's sentence hero AND AutomationRules' manage-list
// rows (token spans, not a plain-string summarize()) — one
// implementation, not two.
//
// Returns an array of spans: [{ text, bold, key }]. `bold` marks a
// clickable token (trigger / a condition clause / an action); `key`
// identifies which part it is for click-to-focus wiring in the builder
// ('trigger', 'cond:0', 'action:1', …). Plain-text joiners (", if ", " and
// ", ", then ", ", ") are not bold and have no key.

function fieldLabel(field, options) {
  // A condition field can come from any of the per-trigger sources (see
  // condition_fields_source in automation.py / NodeConfigPanel.vue) — not
  // just the default task-oriented condition_fields list, or e.g. an
  // erp.* rule's "amount"/"customer" clause would fall back to its raw
  // (lowercase) field key instead of a real label.
  const sources = [
    options.condition_fields, options.erp_finance_condition_fields,
    options.project_event_condition_fields, options.sprint_event_condition_fields,
  ]
  for (const list of sources) {
    const hit = list?.find(f => f.value === field)
    if (hit) return hit.label
  }
  return field
}
function opLabel(op, options) {
  return options.operators?.find(o => o.value === op)?.label || op
}
export function conditionClauses(rule) {
  if (Array.isArray(rule.conditions)) return rule.conditions
  const c = rule.conditions || {}
  return [...(c.all || []), ...(c.any || [])]
}
function condPhrase(c, options) {
  const f = fieldLabel(c.field, options)
  if (c.op === 'is_set') return `${f} is set`
  if (c.op === 'is_not_set') return `${f} is empty`
  if (c.op === 'changed') return `${f} changed`
  const val = Array.isArray(c.value) ? c.value.join(', ') : c.value
  return `${f} ${opLabel(c.op, options)} ${val ?? '—'}`
}
export function actionPhrase(a) {
  const c = a.config || a.cfg || {}
  switch (a.type) {
    case 'Change Status': return `set status to ${c.status || '—'}`
    case 'Assign Issue': {
      const who = (c.assignees || []).join(', ') || 'nobody'
      return c.mode === 'add' ? `assign ${who}` : `set assignees to ${who}`
    }
    case 'Set Priority': return `set priority to ${c.priority || '—'}`
    case 'Set Due Date': return c.mode === 'on_date'
      ? `set due date to ${c.date || '—'}`
      : `set due date to ${c.days ?? 0} day${(c.days === 1) ? '' : 's'} from now`
    case 'Add Label': return `add label${(c.labels || []).length > 1 ? 's' : ''} ${(c.labels || []).join(', ') || '—'}`
    case 'Add Comment': return 'post a comment'
    case 'Notify': return `notify ${c.to || (c.users || []).join(', ') || 'the team'}`
    case 'Create Issue': return `create a task "${c.title || '—'}"`
    case 'Update ERPNext Document': return `update the ${c.doctype || 'ERPNext'} document`
    case 'Send Email': {
      // c.to is Notify's role STRING ('assignees' etc) in the live draft
      // shape (blankAction()'s shared cfg defaults) but a real recipient
      // ARRAY in the saved config shape ({to,subject,message}, buildActionConfig's
      // own output) — c.emailTo is what the live draft form actually binds
      // to (see AutomationRuleEditor.vue). Check both, only .join() a real array.
      const to = Array.isArray(c.emailTo) ? c.emailTo : (Array.isArray(c.to) ? c.to : [])
      return `email ${to.join(', ') || 'the recipients'}`
    }
    default: return a.type
  }
}

/** rule: {trigger_event, conditions, actions} (server shape) OR
 *  {trigger_event, conditions: [...], actions:[{type,cfg}]} (draft shape —
 *  actionPhrase reads either .config or .cfg). options: get_automation_options()
 *  payload (triggers/operators/condition_fields). */
export function ruleSentence(rule, options) {
  const spans = []
  // board.py's own trigger labels already read "When a task's status
  // changes" etc (_AUTOMATION_TRIGGERS) — a hardcoded second "When " here
  // doubled up into "When When a task's status changes" for every rule.
  // Only the raw/unmatched fallback (a legacy trigger_event with no
  // matching option, or none at all) still needs its own lead-in.
  const trigLabel = options.triggers?.find(t => t.value === rule.trigger_event)?.label
  const trig = trigLabel || rule.trigger_event || 'something happens'
  if (!trigLabel) spans.push({ text: 'When ', bold: false })
  spans.push({ text: trig, bold: true, key: 'trigger' })

  const clauses = conditionClauses(rule)
  if (clauses.length) {
    spans.push({ text: ', if ', bold: false })
    clauses.forEach((c, i) => {
      if (i > 0) spans.push({ text: ' and ', bold: false })
      spans.push({ text: condPhrase(c, options), bold: true, key: `cond:${i}` })
    })
  }
  spans.push({ text: ', then ', bold: false })

  const actions = rule.actions || []
  if (!actions.length) {
    spans.push({ text: 'this happens', bold: true, key: 'action:0' })
  } else {
    actions.forEach((a, i) => {
      if (i > 0) spans.push({ text: ', then ', bold: false })
      spans.push({ text: actionPhrase(a), bold: true, key: `action:${i}` })
    })
  }
  return spans
}

/** Plain-string fallback (e.g. for places that can't render token spans). */
export function ruleSentenceText(rule, options) {
  return ruleSentence(rule, options).map(s => s.text).join('')
}
