/**
 * BQL — Batch Query Language
 * Compiles to queryTasks() or getWidgetData() parameters.
 *
 * Syntax:
 *   [field OPERATOR value [AND ...]] [GROUP BY field] [VIEW charttype] [METRIC metricname] [LIMIT n]
 *
 * Operators:  =  !=  <  >  <=  >=  IN (...)  NOT IN (...)  LIKE  IS NULL  IS NOT NULL
 * Fields:     project, status, assignee, priority, sprint, epic,
 *             task_type (or type), labels (or label), due, created, title
 * Aggregate:  GROUP BY status|assignee|priority|sprint|epic|type|label
 * Views:      VIEW bar|hbar|line|area|donut  (default: bar when GROUP BY present)
 * Metrics:    METRIC count|sum|avg            (default: count)
 * Paging:     LIMIT n
 * Special:    "me"           → current user (backend resolves)
 *             "today"        → today's ISO date
 *             "today+Nd"     → N days from today
 *             "today-Nd"     → N days before today
 *             "current"      → current sprint
 */

const FIELD_MAP = {
  project: 'project',
  status: 'status',
  assignee: 'assignee',
  priority: 'priority',
  sprint: 'sprint',
  epic: 'epic',
  type: 'task_type',
  task_type: 'task_type',
  labels: 'labels',
  label: 'labels',
  due: 'due',
  due_date: 'due',
  created: 'created',
  created_at: 'created',
  title: 'search',
  text: 'search',
  search: 'search',
}

// Allowed GROUP BY field names → maps to getWidgetData group_by values
const GROUP_BY_MAP = {
  status: 'status',
  assignee: 'assignee',
  priority: 'priority',
  sprint: 'sprint',
  epic: 'epic',
  type: 'task_type',
  task_type: 'task_type',
  label: 'labels',
  labels: 'labels',
  project: 'project',
}

function resolveValue(val) {
  if (val === null || val === undefined) return val
  if (val === 'today') return isoToday(0)
  const m = val.match(/^today([+-])(\d+)d$/)
  if (m) return isoToday(parseInt(m[2]) * (m[1] === '+' ? 1 : -1))
  return val
}

function isoToday(offsetDays = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().slice(0, 10)
}

// ── tokenizer ────────────────────────────────────────────────────────────────

function tokenize(src) {
  const tokens = []
  let i = 0
  const s = src.trim()

  while (i < s.length) {
    if (/\s/.test(s[i])) { i++; continue }

    // String literals
    if (s[i] === '"' || s[i] === "'") {
      const q = s[i++]
      let str = ''
      while (i < s.length && s[i] !== q) {
        if (s[i] === '\\') { i++; str += s[i] || '' }
        else str += s[i]
        i++
      }
      i++ // closing quote
      tokens.push({ t: 'str', v: str })
      continue
    }

    if (s[i] === '(') { tokens.push({ t: 'lparen' }); i++; continue }
    if (s[i] === ')') { tokens.push({ t: 'rparen' }); i++; continue }
    if (s[i] === ',') { tokens.push({ t: 'comma' });  i++; continue }

    // Two-char operators first
    if (s[i] === '!' && s[i+1] === '=') { tokens.push({ t: 'op', v: '!=' }); i += 2; continue }
    if (s[i] === '>' && s[i+1] === '=') { tokens.push({ t: 'op', v: '>=' }); i += 2; continue }
    if (s[i] === '<' && s[i+1] === '=') { tokens.push({ t: 'op', v: '<=' }); i += 2; continue }
    if (s[i] === '=') { tokens.push({ t: 'op', v: '=' }); i++; continue }
    if (s[i] === '>') { tokens.push({ t: 'op', v: '>' }); i++; continue }
    if (s[i] === '<') { tokens.push({ t: 'op', v: '<' }); i++; continue }

    // Identifiers / keywords
    if (/[a-zA-Z_]/.test(s[i])) {
      let id = ''
      while (i < s.length && /[a-zA-Z0-9_]/.test(s[i])) id += s[i++]
      const up = id.toUpperCase()
      const KWORDS = ['AND', 'OR', 'IN', 'NOT', 'LIKE', 'IS', 'NULL',
                      'GROUP', 'BY', 'VIEW', 'METRIC', 'LIMIT', 'ORDER', 'SORT', 'ASC', 'DESC']
      if (KWORDS.includes(up)) tokens.push({ t: 'kw', v: up })
      else tokens.push({ t: 'id', v: id.toLowerCase() })
      continue
    }

    // Numbers (bare, without quotes)
    if (/\d/.test(s[i])) {
      let num = ''
      while (i < s.length && /[\d.]/.test(s[i])) num += s[i++]
      tokens.push({ t: 'str', v: num })
      continue
    }

    i++ // skip unknown
  }

  return tokens
}

// ── parser ───────────────────────────────────────────────────────────────────

function parseFull(tokens) {
  let i = 0
  const peek = () => tokens[i]
  const next = () => tokens[i++]

  function parseList() {
    if (!peek() || peek().t !== 'lparen') throw new Error('Expected "(" for IN list')
    next() // (
    const vals = []
    while (peek() && peek().t !== 'rparen') {
      if (peek().t === 'comma') { next(); continue }
      vals.push(resolveValue(next().v))
    }
    if (!peek()) throw new Error('Unterminated IN list — missing ")"')
    next() // )
    return vals
  }

  function parseCondition() {
    const fieldTok = next()
    if (!fieldTok || fieldTok.t !== 'id') throw new Error(`Expected field name, got "${fieldTok?.v}"`)
    const field = fieldTok.v
    const p = peek()
    if (!p) throw new Error(`Expected operator after "${field}"`)

    if (p.t === 'kw' && p.v === 'NOT') {
      next()
      if (!peek() || peek().v !== 'IN') throw new Error('Expected IN after NOT')
      next()
      return { field, op: 'NOT IN', value: parseList() }
    }
    if (p.t === 'kw' && p.v === 'IN') {
      next()
      return { field, op: 'IN', value: parseList() }
    }
    if (p.t === 'kw' && p.v === 'LIKE') {
      next()
      const v = next()
      return { field, op: 'LIKE', value: v?.v ?? '' }
    }
    if (p.t === 'kw' && p.v === 'IS') {
      next()
      if (peek()?.v === 'NOT') { next(); next(); return { field, op: '!=', value: null } }
      next()
      return { field, op: '=', value: null }
    }

    const op = next()
    if (op.t !== 'op') throw new Error(`Expected operator, got "${op.v}"`)
    const val = next()
    return { field, op: op.v, value: resolveValue(val?.v) }
  }

  const conditions = []
  let group_by = null
  let view = null
  let metric = 'count'
  let limit = null
  let sort_by = null
  let sort_order = null

  while (i < tokens.length) {
    const t = peek()
    if (!t) break

    // Skip AND / OR conjunctions
    if (t.t === 'kw' && (t.v === 'AND' || t.v === 'OR')) { next(); continue }

    // GROUP BY field
    if (t.t === 'kw' && t.v === 'GROUP') {
      next()
      if (peek()?.v === 'BY') next()
      const gf = next()
      group_by = GROUP_BY_MAP[gf?.v] || gf?.v || 'status'
      continue
    }

    // VIEW charttype
    if (t.t === 'kw' && t.v === 'VIEW') {
      next()
      const vt = next()
      view = vt?.v?.toLowerCase() || 'bar'
      continue
    }

    // METRIC metricname
    if (t.t === 'kw' && t.v === 'METRIC') {
      next()
      const mt = next()
      metric = mt?.v?.toLowerCase() || 'count'
      continue
    }

    // LIMIT n
    if (t.t === 'kw' && t.v === 'LIMIT') {
      next()
      const lt = next()
      limit = parseInt(lt?.v) || 100
      continue
    }

    // ORDER/SORT BY field [ASC|DESC]
    if (t.t === 'kw' && (t.v === 'ORDER' || t.v === 'SORT')) {
      next()
      if (peek()?.v === 'BY') next()
      const sf = next()
      sort_by = sf?.v || 'modified'
      if (peek()?.t === 'kw' && (peek().v === 'ASC' || peek().v === 'DESC')) {
        sort_order = next().v.toLowerCase()
      }
      continue
    }

    conditions.push(parseCondition())
  }

  return { conditions, group_by, view, metric, limit, sort_by, sort_order }
}

// ── public API ────────────────────────────────────────────────────────────────

/**
 * Parse BQL into structured result.
 * Returns { ok, conditions, group_by, view, metric, limit, sort_by, sort_order, error }
 */
export function parseBQL(bql) {
  if (!bql || !bql.trim()) return { ok: true, conditions: [], group_by: null, view: null, metric: 'count', limit: null }
  try {
    const tokens = tokenize(bql)
    const result = parseFull(tokens)
    return { ok: true, ...result }
  } catch (e) {
    return { ok: false, conditions: [], group_by: null, view: null, metric: 'count', limit: null, error: e.message }
  }
}

/** Validate BQL and return { ok, error }. */
export function validateBQL(bql) {
  const { ok, error } = parseBQL(bql)
  return { ok, error }
}

/**
 * Compile BQL into queryTasks() parameters: { project, filters, sort_by, sort_order, limit }.
 * Only relevant when no GROUP BY is present.
 */
export function bqlToQueryParams(bql) {
  const parsed = parseBQL(bql)
  if (!parsed.ok) return { error: parsed.error }

  let project = null
  const filters = {}

  for (const cond of parsed.conditions) {
    const mapped = FIELD_MAP[cond.field]
    if (!mapped) continue

    if (mapped === 'project') { project = Array.isArray(cond.value) ? cond.value[0] : cond.value; continue }

    if (mapped === 'due') {
      if (cond.op === '<' || cond.op === '<=') filters.due_before = cond.value
      else if (cond.op === '>' || cond.op === '>=') filters.due_after = cond.value
      continue
    }

    if (mapped === 'created') {
      if (cond.op === '>' || cond.op === '>=') filters.created_after = cond.value
      continue
    }

    if (mapped === 'search') {
      filters.search = Array.isArray(cond.value) ? cond.value.join(' ') : cond.value
      continue
    }

    filters[mapped] = cond.value
  }

  return {
    project,
    filters,
    sort_by: parsed.sort_by || 'modified',
    sort_order: parsed.sort_order || 'desc',
    limit: parsed.limit || 100,
  }
}

/**
 * Compile BQL into getWidgetData() parameters.
 * Used when GROUP BY is present.
 * Returns { scope, group_by, metric, project }
 */
export function bqlToWidgetDataParams(bql) {
  const parsed = parseBQL(bql)
  if (!parsed.ok) return { error: parsed.error }

  // Extract project from conditions for scope
  let project = null
  for (const cond of parsed.conditions) {
    if (FIELD_MAP[cond.field] === 'project') {
      project = Array.isArray(cond.value) ? cond.value[0] : cond.value
      break
    }
  }

  return {
    scope: project || 'all',
    group_by: parsed.group_by || 'status',
    metric: parsed.metric || 'count',
    project,
  }
}

// ── docs / examples ───────────────────────────────────────────────────────────

export const BQL_EXAMPLES = [
  { label: 'My open tasks',         bql: `project = "PROJ" AND assignee = "me" AND status = "Open"` },
  { label: 'Overdue high priority', bql: `project = "PROJ" AND priority = "High" AND due < "today"` },
  { label: 'Current sprint bugs',   bql: `project = "PROJ" AND sprint = "current" AND task_type = "Bug"` },
  { label: 'By status (chart)',      bql: `project = "PROJ" GROUP BY status VIEW donut` },
  { label: 'Assignee workload',      bql: `project = "PROJ" GROUP BY assignee VIEW hbar METRIC count` },
  { label: 'Priority breakdown',     bql: `project = "PROJ" GROUP BY priority VIEW bar` },
  { label: 'Recently created',       bql: `project = "PROJ" AND created > "today-7d"` },
]

export const BQL_FIELD_DOCS = [
  { field: 'project',   desc: 'Project key',                                       example: 'project = "BATCH"' },
  { field: 'status',    desc: 'Task status name',                                   example: 'status = "Open"' },
  { field: 'assignee',  desc: 'Assignee — use "me" for yourself',                  example: 'assignee = "me"' },
  { field: 'priority',  desc: 'Priority (High / Medium / Low)',                     example: 'priority = "High"' },
  { field: 'sprint',    desc: 'Sprint — use "current" for active one',              example: 'sprint = "current"' },
  { field: 'epic',      desc: 'Epic name or ID',                                    example: 'epic = "Auth Epic"' },
  { field: 'task_type', desc: 'Issue type (Bug, Story, Task…)',                     example: 'task_type = "Bug"' },
  { field: 'labels',    desc: 'Labels — use IN for multiple',                       example: 'labels IN ("api", "core")' },
  { field: 'due',       desc: 'Due date — supports < today, today+Nd',             example: 'due < "today"' },
  { field: 'created',   desc: 'Creation date — supports > today-Nd',               example: 'created > "today-7d"' },
  { field: 'title',     desc: 'Title text search',                                  example: 'title LIKE "login%"' },
]

export const BQL_CLAUSE_DOCS = [
  { clause: 'GROUP BY field', desc: 'Aggregate into a chart. Switches widget to chart mode.', example: 'GROUP BY status' },
  { clause: 'VIEW type',      desc: 'Chart type: bar | hbar | line | area | donut',           example: 'VIEW donut' },
  { clause: 'METRIC name',    desc: 'Aggregation: count | sum | avg',                          example: 'METRIC count' },
  { clause: 'LIMIT n',        desc: 'Max rows to fetch (table mode)',                          example: 'LIMIT 50' },
  { clause: 'ORDER BY field', desc: 'Sort results: ASC | DESC',                               example: 'ORDER BY created ASC' },
]
