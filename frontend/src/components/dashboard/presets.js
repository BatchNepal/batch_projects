// Preset report templates — the handful of reports agile teams reach for.
// Each preset declares how to FETCH its slice and BUILD a normalized render spec.
// Render specs are consumed by PresetWidget.vue. All powered by EXISTING endpoints.
import { getReports, getWidgetData, getPortfolio, getMarginReport, getWorkload, getUtilization, queryTasks, getSprintReport, getSprints, getMilestoneReport } from '@/utils/api'
import {
  TrendingDown, BarChart3, Layers, GitCompareArrows, PieChart, Timer, Users,
  Globe, DollarSign, Gauge, Clock, AlertTriangle, GitBranch, Activity,
} from 'lucide-vue-next'

const C = { ideal: '#98a2b3', remaining: '#3b82f6', committed: '#bae6fd', completed: '#10b981', created: '#06b6d4' }

function proj(cfg) { return cfg.scope && cfg.scope !== 'all' ? cfg.scope : null }

// Pass custom date range when period === 'custom' and dates are provided
function fetchReports(cfg) {
  if (cfg.period === 'custom' && cfg.fromDate && cfg.toDate)
    return getReports(proj(cfg), 'last_30_days', cfg.fromDate, cfg.toDate)
  return getReports(proj(cfg), cfg.period)
}

function isoToday() { return new Date().toISOString().slice(0, 10) }
function ageDays(created) {
  if (!created) return 0
  const ms = Date.now() - new Date(created).getTime()
  return Math.max(0, Math.floor(ms / 86400000))
}

export const PRESETS = {
  burndown: {
    label: 'Burndown',
    desc: 'Remaining work vs the ideal line across the sprint',
    icon: TrendingDown, pill: 'blue', needsPeriod: true,
    defaultSize: { w: 6, h: 21, minW: 3, minH: 8 },
    fetch: (cfg) => fetchReports(cfg),
    build: (d) => {
      const days = d?.burndown?.days || []
      return {
        title: d?.burndown?.sprint ? `Burndown — ${d.burndown.sprint}` : 'Burndown',
        kind: 'combo', empty: !days.length, emptyText: 'No active sprint in this project',
        categories: days.map((p) => p.label),
        series: [
          { name: 'Ideal',     type: 'line', data: days.map((p) => p.ideal),     color: C.ideal },
          { name: 'Remaining', type: 'line', data: days.map((p) => p.remaining), color: C.remaining },
        ],
      }
    },
  },

  velocity: {
    label: 'Velocity',
    desc: 'Committed vs completed work per sprint',
    icon: BarChart3, pill: 'cyan', needsPeriod: true,
    defaultSize: { w: 6, h: 21, minW: 3, minH: 8 },
    fetch: (cfg) => fetchReports(cfg),
    build: (d) => {
      const v = d?.velocity || []
      const hasPts = v.some((x) => (x.committed || 0) || (x.completed || 0))
      return {
        title: 'Velocity', kind: 'combo', empty: !v.length || !hasPts, emptyText: 'No story points logged on sprints yet',
        categories: v.map((x) => x.label),
        series: [
          { name: 'Committed', type: 'column', data: v.map((x) => x.committed), color: C.committed },
          { name: 'Completed', type: 'column', data: v.map((x) => x.completed), color: C.completed },
        ],
      }
    },
  },

  cumulative_flow: {
    label: 'Cumulative Flow',
    desc: 'Status distribution over time — spot bottlenecks',
    icon: Layers, pill: 'teal', needsPeriod: true,
    defaultSize: { w: 8, h: 21, minW: 4, minH: 8 },
    fetch: (cfg) => fetchReports(cfg),
    build: (d) => {
      const cf = d?.cumulative_flow
      const labels = cf?.labels || []
      const series = (cf?.series || []).map((s) => ({ name: s.name, data: s.counts, color: s.color }))
      const hasData = series.some((s) => (s.data || []).some((n) => (n || 0) > 0))
      return {
        title: 'Cumulative Flow', kind: 'stacked', horizontal: false,
        empty: !labels.length || !hasData, emptyText: 'No history in this period',
        categories: labels,
        series,
      }
    },
  },

  throughput: {
    label: 'Created vs Resolved',
    desc: 'Throughput — issues created vs completed per period',
    icon: GitCompareArrows, pill: 'teal', needsPeriod: true,
    defaultSize: { w: 6, h: 21, minW: 3, minH: 8 },
    fetch: (cfg) => fetchReports(cfg),
    build: (d) => {
      const t = d?.throughput || []
      const hasFlow = t.some((x) => (x.created || 0) || (x.completed || 0))
      return {
        title: 'Created vs Resolved', kind: 'combo', empty: !hasFlow, emptyText: 'No activity in this period',
        categories: t.map((x) => x.label),
        series: [
          { name: 'Created',   type: 'column', data: t.map((x) => x.created),   color: C.created },
          { name: 'Completed', type: 'line',   data: t.map((x) => x.completed), color: C.completed },
        ],
      }
    },
  },

  status_breakdown: {
    label: 'Status Breakdown',
    desc: 'Share of issues by status',
    icon: PieChart, pill: 'amber', needsPeriod: true,
    defaultSize: { w: 4, h: 21, minW: 3, minH: 8 },
    fetch: (cfg) => fetchReports(cfg),
    build: (d) => {
      const sb = (d?.status_breakdown || []).filter((s) => (s.count || 0) > 0)
      return {
        title: 'Status Breakdown', kind: 'donut', empty: !sb.length, emptyText: 'No tasks in this scope',
        items: sb.map((s) => ({ label: s.name, value: s.count, color: s.color })),
      }
    },
  },

  cycle_time: {
    label: 'Cycle Time',
    desc: 'Average days from start to done',
    icon: Timer, pill: 'green', needsPeriod: true,
    defaultSize: { w: 3, h: 13, minW: 2, minH: 5 },
    fetch: (cfg) => fetchReports(cfg),
    build: (d) => {
      const ct = d?.cycle_time || {}
      return {
        title: 'Avg Cycle Time', kind: 'metric', empty: ct.completed_count == null,
        value: ct.avg_days ?? 0, unit: 'd',
        foot: `${ct.completed_count || 0} completed`,
      }
    },
  },

  workload: {
    label: 'Workload by Assignee',
    desc: 'Open work distributed across the team',
    icon: Users, pill: 'red', needsPeriod: false,
    defaultSize: { w: 6, h: 21, minW: 3, minH: 8 },
    fetch: (cfg) => getWidgetData({ scope: cfg.scope || 'all', group_by: 'assignee', metric: 'count' }),
    build: (d) => {
      const items = d?.items || []
      return {
        title: 'Workload by Assignee', kind: 'hbar', empty: !items.length, emptyText: 'No assigned work',
        items: items.slice(0, 12),
      }
    },
  },

  portfolio_health: {
    label: 'Portfolio Health',
    desc: 'RAG status, progress, and overdue tasks across all projects',
    icon: Globe, pill: 'blue', needsPeriod: false,
    defaultSize: { w: 12, h: 22, minW: 6, minH: 10 },
    fetch: () => getPortfolio(),
    build: (d) => {
      const projects = d?.projects || []
      return {
        title: 'Portfolio Health', kind: 'portfolio',
        empty: !projects.length, emptyText: 'No active projects',
        summary: d?.summary || {},
        projects,
      }
    },
  },

  erp_margin: {
    label: 'Project Margin',
    desc: 'Revenue, cost and gross margin from ERPNext billing data',
    icon: DollarSign, pill: 'green', needsPeriod: true,
    defaultSize: { w: 8, h: 21, minW: 4, minH: 8 },
    fetch: (cfg) => getMarginReport(cfg.period || 'last_30_days'),
    build: (d) => {
      const projects = (d?.projects || []).slice(0, 12)
      if (!projects.length) return { title: 'Project Margin', kind: 'hbar', empty: true, emptyText: 'No billing data' }
      // Show revenue vs cost as dual-series combo chart
      return {
        title: 'Project Margin', kind: 'combo',
        empty: false,
        categories: projects.map((p) => p.project_name || p.project),
        series: [
          { name: 'Revenue', type: 'column', data: projects.map((p) => +(p.revenue || 0).toFixed(0)), color: '#10b981' },
          { name: 'Cost',    type: 'column', data: projects.map((p) => +(p.cost    || 0).toFixed(0)), color: '#f59e0b' },
          { name: 'Margin',  type: 'line',   data: projects.map((p) => +(p.margin  || 0).toFixed(0)), color: '#06b6d4' },
        ],
        foot: d?.summary ? `Total margin: ${((d.summary.margin_pct || 0)).toFixed(1)}%` : '',
      }
    },
  },

  utilization: {
    label: 'Team Utilization',
    desc: 'Billable hours % per person from ERPNext Timesheets',
    icon: Gauge, pill: 'cyan', needsPeriod: true,
    defaultSize: { w: 6, h: 21, minW: 3, minH: 8 },
    fetch: (cfg) => getUtilization(cfg.period || 'last_30_days'),
    build: (d) => {
      const members = d?.members || []
      return {
        title: 'Team Utilization', kind: 'hbar',
        empty: !members.length, emptyText: 'No timesheet data',
        items: members.slice(0, 12).map((m) => ({
          label: m.full_name || m.user,
          value: +(m.utilization_pct || 0).toFixed(1),
          color: (m.utilization_pct || 0) >= 80 ? '#10b981' : (m.utilization_pct || 0) >= 50 ? '#f59e0b' : '#ef4444',
        })),
      }
    },
  },

  capacity_plan: {
    label: 'Capacity vs Allocated',
    desc: 'Forward-looking allocation vs capacity per person from project tasks',
    icon: Clock, pill: 'amber', needsPeriod: false,
    defaultSize: { w: 6, h: 21, minW: 3, minH: 8 },
    fetch: () => getWorkload(4),
    build: (d) => {
      const members = d?.members || []
      return {
        title: 'Capacity vs Allocated', kind: 'hbar',
        empty: !members.length, emptyText: 'No allocation data',
        items: members.slice(0, 12).map((m) => {
          const allocated = (m.weeks || []).reduce((s, w) => s + (w.allocated || 0), 0)
          const capacity  = (m.weeks || []).reduce((s, w) => s + (w.capacity  || 40), 0)
          const pct = capacity ? Math.round((allocated / capacity) * 100) : 0
          return {
            label: m.full_name || m.user,
            value: pct,
            color: pct > 100 ? '#ef4444' : pct > 80 ? '#f59e0b' : '#10b981',
          }
        }),
      }
    },
  },

  issue_age: {
    label: 'Issue Age',
    desc: 'Oldest open issues ranked by days since creation',
    icon: AlertTriangle, pill: 'red', needsPeriod: false,
    defaultSize: { w: 8, h: 22, minW: 4, minH: 10 },
    // query_tasks (queryTasks's backend)
    // requires a REAL project for its permission check — access.require(
    // None, role) throws for any non-instance-admin. Every OTHER preset in
    // this file is either already proj(cfg)-safe via getReports, or was
    // never project-scoped to begin with (portfolio/margin/utilization/
    // capacity are workspace-wide APIs by design) — this was the one
    // genuine gap. Restructuring query_tasks itself to support a
    // cross-project mode is real, separate surgery on a function that also
    // backs get_board/get_backlog — out of scope for a dashboard-widget
    // fix. Degrade gracefully at workspace scope instead of crashing.
    fetch: (cfg) => {
      const p = proj(cfg)
      if (!p) return Promise.resolve([])
      return queryTasks(p, {}, null, 'creation', 'asc', 25, 0)
    },
    build: (raw) => {
      const tasks = Array.isArray(raw) ? raw : (raw?.tasks || [])
      const items = tasks.map((t) => ({
        name:     t.name,
        task_key: t.task_key,
        title:    t.title || t.subject,
        status:   t.status,
        priority: t.priority,
        assignees:t.assignees,
        age:      ageDays(t.creation || t.created),
      })).sort((a, b) => b.age - a.age)
      return {
        title: 'Issue Age', kind: 'issue_age',
        empty: !items.length, emptyText: 'No open issues',
        items,
      }
    },
  },
}

PRESETS.sprint_report = {
  label: 'Sprint Report',
  desc: 'Committed vs added mid-sprint · completion rate · spillover',
  icon: GitBranch, pill: 'blue', needsPeriod: false,
  defaultSize: { w: 8, h: 28, minW: 5, minH: 12 },
  // fetch must be called with cfg.sprintName set by the widget config or most-recent sprint
  fetch: async (cfg) => {
    const p = proj(cfg)
    if (!p) return { _noProject: true }
    let sn = cfg.sprintName
    if (!sn) {
      // auto-pick active or most-recent sprint
      const sprints = await getSprints(p)
      const active = (sprints || []).find((s) => s.status === 'Active')
      const latest = active || (sprints || []).slice(-1)[0]
      if (!latest) return { _noSprint: true }
      sn = latest.name
    }
    return getSprintReport(p, sn)
  },
  build: (d) => {
    if (!d || d._noProject) return { title: 'Sprint Report', kind: 'sprint_report', empty: true, emptyText: 'Scope this report to a single project to see its sprint report' }
    if (d._noSprint) return { title: 'Sprint Report', kind: 'sprint_report', empty: true, emptyText: 'No sprints in this project yet — create one to see the report' }
    return {
      title: d.sprint_label ? `Sprint: ${d.sprint_label}` : 'Sprint Report',
      kind: 'sprint_report',
      empty: !d.summary?.total,
      emptyText: 'No tasks in sprint',
      summary: d.summary || {},
      goal: d.goal,
      status: d.status,
      start_date: d.start_date,
      end_date: d.end_date,
      committed: d.committed || [],
      added: d.added || [],
      completed: d.completed || [],
      spillover: d.spillover || [],
      burndown: (d.burndown && d.burndown.days?.length) ? {
        categories: d.burndown.days.map((x) => x.date),
        series: [
          { name: 'Ideal',     type: 'line', data: d.burndown.days.map((x) => x.ideal),     color: C.ideal },
          { name: 'Remaining', type: 'line', data: d.burndown.days.map((x) => x.remaining), color: C.remaining },
        ],
      } : null,
    }
  },
}

PRESETS.milestone_finance = {
  label: 'Milestone Health (ERP)',
  desc: 'Delivery % plus hours, billable value and budget burn — the ERP moat.',
  icon: DollarSign, pill: 'green', needsPeriod: false, needsMilestone: true,
  defaultSize: { w: 8, h: 17, minW: 4, minH: 8 },
  fetch: (cfg) => cfg.milestone ? getMilestoneReport(cfg.milestone) : Promise.resolve(null),
  build: (d) => {
    if (!d) return { title: 'Milestone Health', kind: 'kpis', empty: true, emptyText: "Set this report's scope to a milestone" }
    const f = d.financials, dl = d.delivery
    const cur = d.currency ? d.currency + ' ' : ''
    const money = (n) => cur + (Number(n) || 0).toLocaleString()
    return {
      title: `Milestone — ${d.title}`,
      kind: 'kpis',
      tiles: [
        { label: 'Completion', value: dl.completion_pct + '%', sub: `${dl.done}/${dl.total} tasks`, color: '#00C875' },
        { label: 'Points done', value: dl.points_done, sub: `of ${dl.points_total}`, color: '#0073EA' },
        { label: 'Actual hours', value: f.actual_hours, sub: `${f.estimated_hours} est`, color: '#FDAB3D' },
        { label: 'Billable value', value: money(f.billable_value), sub: `${f.billable_hours}h billable`, color: '#037F4C' },
        { label: 'Cost to date', value: money(f.cost), sub: f.budget ? `of ${money(f.budget)}` : 'no budget set', color: '#E2445C' },
        { label: 'Budget used', value: f.budget_used_pct != null ? f.budget_used_pct + '%' : '—', sub: 'of budget', color: '#A25DDC' },
      ],
    }
  },
}

PRESETS.cycle_time_control = {
  label: 'Cycle Time Chart',
  desc: 'Scatter of days per task with P50 / P85 / P95 lines',
  icon: Activity, pill: 'green', needsPeriod: true,
  defaultSize: { w: 8, h: 22, minW: 4, minH: 10 },
  fetch: (cfg) => fetchReports(cfg),
  build: (d) => {
    const ct = d?.cycle_time || {}
    const scatter = ct.scatter || []
    if (!scatter.length) return { title: 'Cycle Time Chart', kind: 'scatter', empty: true, emptyText: 'No completed tasks in this period' }
    const pts = scatter.map((p) => [new Date(p.date).getTime(), p.days])
    return {
      title: 'Cycle Time Chart',
      kind: 'scatter',
      empty: false,
      series: [{ name: 'Cycle Days', data: pts, color: '#3b82f6' }],
      p50: ct.p50 || 0,
      p85: ct.p85 || 0,
      p95: ct.p95 || 0,
      avg: ct.avg_days || 0,
      sample: ct.sample || 0,
    }
  },
}

export const PRESET_LIST = Object.entries(PRESETS).map(([key, p]) => ({ key, ...p }))
