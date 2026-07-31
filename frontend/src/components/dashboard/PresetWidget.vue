<template>
  <div v-if="widget.loading && !widget.data" class="pw-state"><div class="pw-spin" /><span>Loading…</span></div>
  <div v-else-if="spec.empty" class="pw-state muted">{{ spec.emptyText || 'No data' }}</div>

  <!-- kpis kind: grid of colored stat tiles (milestone health) -->
  <div v-else-if="spec.kind === 'kpis'" class="pw-kpis">
    <p class="pw-title">{{ widget.title || spec.title }}</p>
    <div class="pw-kpi-grid">
      <div v-for="(t, i) in spec.tiles" :key="i" class="pw-kpi-tile" :style="{ '--kpi': t.color }">
        <span class="pw-kpi-label">{{ t.label }}</span>
        <span class="pw-kpi-val">{{ t.value }}</span>
        <span v-if="t.sub" class="pw-kpi-sub">{{ t.sub }}</span>
      </div>
    </div>
  </div>

  <!-- metric kind -->
  <div v-else-if="spec.kind === 'metric'" class="pw-metric">
    <p class="pw-title">{{ widget.title || spec.title }}</p>
    <div class="pw-num-wrap"><p class="pw-num">{{ fmt(spec.value) }}<small v-if="spec.unit">{{ spec.unit }}</small></p></div>
    <p class="pw-foot">{{ spec.foot }}</p>
  </div>

  <!-- portfolio health: project list with progress bars -->
  <div v-else-if="spec.kind === 'portfolio'" class="pw-portfolio">
    <p class="pw-title">{{ widget.title || spec.title }}</p>
    <div class="pw-pf-kpis">
      <div class="pw-pf-kpi"><span class="pw-pf-v">{{ spec.summary.projects || 0 }}</span><span class="pw-pf-l">Projects</span></div>
      <div class="pw-pf-kpi"><span class="pw-pf-v">{{ spec.summary.tasks || 0 }}</span><span class="pw-pf-l">Tasks</span></div>
      <div class="pw-pf-kpi"><span class="pw-pf-v">{{ spec.summary.done_pct || 0 }}<small>%</small></span><span class="pw-pf-l">Complete</span></div>
      <div class="pw-pf-kpi"><span class="pw-pf-v" :class="{ 'pw-danger': (spec.summary.overdue || 0) > 0 }">{{ spec.summary.overdue || 0 }}</span><span class="pw-pf-l">Overdue</span></div>
    </div>
    <div class="pw-pf-list">
      <div class="pw-pf-header">
        <span>Project</span><span class="pw-pf-prog-col">Progress</span><span class="pw-pf-r">Tasks</span><span class="pw-pf-r">Overdue</span>
      </div>
      <div v-for="p in spec.projects" :key="p.name" class="pw-pf-row">
        <div class="pw-pf-proj">
          <span class="pw-pf-dot" :style="{ background: p.color || 'var(--muted)' }" />
          <div class="min-w-0">
            <div class="pw-pf-name">{{ p.project_name }}</div>
            <div class="pw-pf-key">{{ p.key }}<template v-if="p.client"> · {{ p.client }}</template></div>
          </div>
        </div>
        <div class="pw-pf-prog-col">
          <div class="pw-pf-track">
            <div class="pw-pf-seg" :style="{ width: pct(p.done, p.total) + '%', background: '#10b981' }" />
            <div class="pw-pf-seg" :style="{ width: pct(p.started, p.total) + '%', background: '#3b82f6' }" />
          </div>
          <span class="pw-pf-pct">{{ p.done_pct }}%</span>
        </div>
        <span class="pw-pf-r">{{ p.total }}</span>
        <span class="pw-pf-r"><span v-if="p.overdue > 0" class="pw-pf-overdue">{{ p.overdue }}</span><span v-else class="pw-muted">—</span></span>
      </div>
    </div>
  </div>

  <!-- issue age table -->
  <div v-else-if="spec.kind === 'issue_age'" class="pw-age">
    <p class="pw-title">{{ widget.title || spec.title }}</p>
    <div class="pw-age-table-wrap">
      <table class="pw-age-tbl">
        <thead>
          <tr>
            <th class="pw-th">Key</th>
            <th class="pw-th">Title</th>
            <th class="pw-th">Status</th>
            <th class="pw-th pw-th-r">Age</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in spec.items" :key="row.task_key" class="pw-age-tr">
            <td class="pw-td pw-td-key">{{ row.task_key }}</td>
            <td class="pw-td pw-td-title">{{ row.title }}</td>
            <td class="pw-td">
              <span class="pw-status-chip" :class="statusClass(row.status)">{{ row.status }}</span>
            </td>
            <td class="pw-td pw-td-r">
              <span class="pw-age-badge" :class="ageClass(row.age)">{{ row.age }}d</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- sprint report -->
  <div v-else-if="spec.kind === 'sprint_report'" class="pw-sprint">
    <div class="pw-sprint-head">
      <div>
        <p class="pw-title">{{ widget.title || spec.title }}</p>
        <p v-if="spec.goal" class="pw-sub">Goal: {{ spec.goal }}</p>
      </div>
      <span class="pw-sprint-status" :class="sprintStatusClass(spec.status)">{{ spec.status }}</span>
    </div>
    <!-- KPI row -->
    <div class="pw-sprint-kpis">
      <div class="pw-sprint-kpi">
        <span class="pw-sprint-kv">{{ spec.summary.total || 0 }}</span>
        <span class="pw-sprint-kl">Total</span>
      </div>
      <div class="pw-sprint-kpi">
        <span class="pw-sprint-kv">{{ spec.summary.completed || 0 }}</span>
        <span class="pw-sprint-kl">Done</span>
      </div>
      <div class="pw-sprint-kpi">
        <span class="pw-sprint-kv">{{ spec.summary.spillover || 0 }}</span>
        <span class="pw-sprint-kl">Spillover</span>
      </div>
      <div class="pw-sprint-kpi pw-sprint-kpi-pct">
        <span class="pw-sprint-kv">{{ spec.summary.completion_rate || 0 }}<small>%</small></span>
        <span class="pw-sprint-kl">Done rate</span>
      </div>
    </div>
    <!-- progress bar -->
    <div class="pw-sprint-track-wrap">
      <div class="pw-sprint-track">
        <div class="pw-sprint-done-seg"  :style="{ width: pct(spec.summary.completed, spec.summary.total) + '%' }" />
        <div class="pw-sprint-scope-seg" :style="{ width: pct(spec.summary.added, spec.summary.total) + '%' }" />
      </div>
      <div class="pw-sprint-legend">
        <span><span class="pw-sprint-dot done" />Committed ({{ spec.summary.committed }})</span>
        <span><span class="pw-sprint-dot added" />Added ({{ spec.summary.added }})</span>
        <span><span class="pw-sprint-dot spill" />Spillover ({{ spec.summary.spillover }})</span>
      </div>
    </div>
    <!-- burndown: ideal vs remaining points across the sprint -->
    <div v-if="spec.burndown" class="pw-sprint-burndown">
      <p class="pw-sprint-col-hd">Burndown</p>
      <ApexCombo :categories="spec.burndown.categories" :series="spec.burndown.series" :height="180" :format="fmt" />
    </div>
    <!-- task lists side by side -->
    <div class="pw-sprint-lists">
      <div class="pw-sprint-col">
        <p class="pw-sprint-col-hd">Completed ({{ spec.completed.length }})</p>
        <div class="pw-sprint-col-body">
          <div v-for="t in spec.completed" :key="t.name" class="pw-sprint-task pw-sprint-task-done">
            <span class="pw-sprint-tick">✓</span>
            <span class="pw-sprint-tk">{{ t.task_key }}</span>
            <span class="pw-sprint-tt">{{ t.title }}</span>
            <span class="pw-sprint-pts" v-if="t.story_points">{{ t.story_points }}pt</span>
          </div>
          <p v-if="!spec.completed.length" class="pw-sprint-none">None yet</p>
        </div>
      </div>
      <div class="pw-sprint-col">
        <p class="pw-sprint-col-hd">Remaining ({{ spec.spillover.length }})</p>
        <div class="pw-sprint-col-body">
          <div v-for="t in spec.spillover" :key="t.name" class="pw-sprint-task">
            <span class="pw-sprint-status-dot" :style="{ background: '#94a3b8' }" />
            <span class="pw-sprint-tk">{{ t.task_key }}</span>
            <span class="pw-sprint-tt">{{ t.title }}</span>
            <span class="pw-sprint-pts" v-if="t.story_points">{{ t.story_points }}pt</span>
          </div>
          <p v-if="!spec.spillover.length" class="pw-sprint-none">All done!</p>
        </div>
      </div>
    </div>
    <p v-if="spec.summary.added" class="pw-sprint-scope-note">
      {{ spec.summary.added }} task{{ spec.summary.added !== 1 ? 's' : '' }} added mid-sprint
      ({{ spec.summary.added_pts }}pts) — scope creep indicator
    </p>
  </div>

  <!-- scatter / control chart -->
  <div v-else-if="spec.kind === 'scatter'" class="pw-chart">
    <div class="pw-head">
      <p class="pw-title">{{ widget.title || spec.title }}</p>
      <p class="pw-sub">{{ spec.sample }} tasks · P50={{ spec.p50 }}d · P85={{ spec.p85 }}d · P95={{ spec.p95 }}d</p>
    </div>
    <div class="pw-body">
      <ApexScatter :series="spec.series" :height="chartH" />
    </div>
  </div>

  <!-- chart kinds -->
  <div v-else class="pw-chart">
    <div class="pw-head">
      <p class="pw-title">{{ widget.title || spec.title }}</p>
      <p v-if="spec.foot" class="pw-sub">{{ spec.foot }}</p>
      <p v-else-if="widget.description" class="pw-sub">{{ widget.description }}</p>
    </div>
    <div class="pw-body">
      <ApexCombo      v-if="spec.kind === 'combo'"   :categories="spec.categories" :series="spec.series" :height="chartH" :format="fmt" />
      <ApexStackedBar v-else-if="spec.kind === 'stacked'" :categories="spec.categories" :series="spec.series" :horizontal="spec.horizontal" :height="chartH" :format="fmt" />
      <ApexDonut      v-else-if="spec.kind === 'donut'"   :items="spec.items" :height="chartH" :format="fmt" />
      <ApexBar        v-else-if="spec.kind === 'hbar'"    :items="spec.items" horizontal :height="chartH" :format="fmt" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ApexCombo, ApexStackedBar, ApexDonut, ApexBar, ApexScatter } from '@/components/charts/apex'
import { PRESETS } from './presets.js'

const props = defineProps({
  widget: { type: Object, required: true },
  height: { type: Number, default: 200 },
  fmt:    { type: Function, required: true },
})

const spec = computed(() => {
  const p = PRESETS[props.widget.preset]
  if (!p) return { empty: true, emptyText: 'Unknown report' }
  try { return p.build(props.widget.data) }
  catch { return { empty: true, emptyText: 'No data' } }
})

const chartH = computed(() => Math.max(80, props.height - 44))

function pct(v, total) { return total ? Math.round((v / total) * 100) : 0 }

function statusClass(v) {
  const s = String(v || '').toLowerCase()
  if (/done|complete|closed|resolved/.test(s)) return 'pw-sc-done'
  if (/progress|review|testing/.test(s)) return 'pw-sc-progress'
  if (/block|hold/.test(s)) return 'pw-sc-blocked'
  return 'pw-sc-open'
}

function sprintStatusClass(v) {
  const s = String(v || '').toLowerCase()
  if (s === 'active') return 'pw-sst-active'
  if (s === 'completed') return 'pw-sst-done'
  return 'pw-sst-open'
}

function ageClass(days) {
  if (days > 30) return 'pw-age-critical'
  if (days > 14) return 'pw-age-high'
  if (days > 7)  return 'pw-age-med'
  return 'pw-age-low'
}
</script>

<style scoped>
.pw-state { height: 100%; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 12px; color: var(--muted); }
.muted { color: var(--border); }
.pw-spin { width: 16px; height: 16px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: pw-spin .7s linear infinite; }
@keyframes pw-spin { to { transform: rotate(360deg) } }

.pw-title { font-size: 13px; font-weight: 600; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pw-sub   { font-size: 11px; color: var(--muted); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* metric */
.pw-kpis { height: 100%; display: flex; flex-direction: column; }
.pw-kpi-grid { flex: 1; display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; margin-top: 12px; align-content: start; }
.pw-kpi-tile { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; border-radius: 10px; background: color-mix(in oklab, var(--kpi) 9%, var(--surface)); border-left: 3px solid var(--kpi); }
.pw-kpi-label { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.03em; }
.pw-kpi-val { font-size: 21px; line-height: 1.1; font-weight: 700; letter-spacing: -0.02em; color: var(--foreground); font-variant-numeric: tabular-nums; }
.pw-kpi-sub { font-size: 11px; color: var(--muted); }

.pw-metric { height: 100%; display: flex; flex-direction: column; }
.pw-num-wrap { flex: 1; display: flex; flex-direction: column; justify-content: center; margin-top: 12px; }
.pw-num { font-size: 30px; line-height: 1; font-weight: 700; letter-spacing: -0.02em; color: var(--foreground); font-variant-numeric: tabular-nums; }
.pw-num small { font-size: 15px; font-weight: 600; color: var(--muted); margin-left: 2px; }
.pw-foot { margin-top: auto; padding-top: 10px; font-size: 11px; color: var(--muted); }

/* generic chart wrapper */
.pw-chart { height: 100%; display: flex; flex-direction: column; gap: 8px; }
.pw-head  { flex-shrink: 0; }
.pw-body  { flex: 1; min-height: 0; }

/* portfolio */
.pw-portfolio { height: 100%; display: flex; flex-direction: column; gap: 8px; overflow: hidden; }
.pw-pf-kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; flex-shrink: 0; }
.pw-pf-kpi { background: var(--surface-secondary); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; display: flex; flex-direction: column; gap: 2px; }
.pw-pf-v { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; color: var(--foreground); }
.pw-pf-v.pw-danger { color: var(--danger); }
.pw-pf-v small { font-size: 12px; font-weight: 600; color: var(--muted); margin-left: 1px; }
.pw-pf-l { font-size: 10px; color: var(--muted); }
.pw-pf-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 0; }
.pw-pf-header { display: grid; grid-template-columns: 1fr 120px 50px 50px; gap: 8px; padding: 4px 8px; font-size: 10px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; border-bottom: 1px solid var(--border); }
.pw-pf-row { display: grid; grid-template-columns: 1fr 120px 50px 50px; gap: 8px; padding: 7px 8px; border-bottom: 1px solid var(--border); align-items: center; }
.pw-pf-row:hover { background: var(--surface-secondary); }
.pw-pf-proj { display: flex; align-items: center; gap: 7px; min-width: 0; }
.pw-pf-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.pw-pf-name { font-size: 12px; font-weight: 600; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pw-pf-key { font-size: 10px; color: var(--muted); }
.pw-pf-prog-col { display: flex; align-items: center; gap: 6px; }
.pw-pf-track { flex: 1; height: 5px; border-radius: 3px; background: var(--border); overflow: hidden; display: flex; }
.pw-pf-seg { height: 100%; transition: width .3s; }
.pw-pf-pct { font-size: 10px; color: var(--muted); white-space: nowrap; min-width: 28px; text-align: right; }
.pw-pf-r { font-size: 12px; color: var(--muted); text-align: center; }
.pw-pf-overdue { color: var(--danger); font-weight: 600; }
.pw-muted { color: var(--border); }

/* issue age table */
.pw-age { height: 100%; display: flex; flex-direction: column; gap: 8px; overflow: hidden; }
.pw-age-table-wrap { flex: 1; overflow-y: auto; }
.pw-age-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.pw-th { padding: 5px 8px; text-align: left; font-size: 10px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; border-bottom: 1px solid var(--border); background: var(--surface-secondary); position: sticky; top: 0; }
.pw-th-r { text-align: right; }
.pw-age-tr:hover { background: var(--surface-secondary); }
.pw-td { padding: 6px 8px; color: var(--foreground); border-bottom: 1px solid var(--border); vertical-align: middle; }
.pw-td-key { color: var(--accent); font-weight: 600; white-space: nowrap; }
.pw-td-title { max-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pw-td-r { text-align: right; }

.pw-status-chip { display: inline-block; font-size: 10px; font-weight: 600; padding: 1px 7px; border-radius: 20px; }
.pw-sc-done     { background: var(--success-soft); color: var(--success); }
.pw-sc-progress { background: var(--accent-soft); color: var(--accent-soft-foreground); }
.pw-sc-blocked  { background: var(--danger-soft); color: var(--danger); }
.pw-sc-open     { background: var(--surface-secondary); color: var(--muted); }

.pw-age-badge { display: inline-block; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 6px; }
.pw-age-critical { background: var(--danger-soft);  color: var(--danger); }
.pw-age-high     { background: var(--warning-soft); color: var(--warning); }
.pw-age-med      { background: var(--warning-soft); color: var(--warning); }
.pw-age-low      { background: var(--success-soft); color: var(--success); }

/* sprint report */
.pw-sprint { height: 100%; display: flex; flex-direction: column; gap: 8px; overflow: hidden; }
.pw-sprint-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; flex-shrink: 0; }
.pw-sprint-status { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 20px; white-space: nowrap; }
.pw-sst-active { background: var(--accent-soft); color: var(--accent-soft-foreground); }
.pw-sst-done   { background: var(--success-soft); color: var(--success); }
.pw-sst-open   { background: var(--surface-secondary); color: var(--muted); }
.pw-sprint-kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; flex-shrink: 0; }
.pw-sprint-kpi { background: var(--surface-secondary); border: 1px solid var(--border); border-radius: 8px; padding: 6px 10px; display: flex; flex-direction: column; gap: 1px; }
.pw-sprint-kv  { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; color: var(--foreground); }
.pw-sprint-kv small { font-size: 12px; font-weight: 600; color: var(--muted); margin-left: 1px; }
.pw-sprint-kl  { font-size: 10px; color: var(--muted); }
.pw-sprint-kpi-pct .pw-sprint-kv { color: var(--accent); }
.pw-sprint-track-wrap { flex-shrink: 0; }
.pw-sprint-track { height: 6px; border-radius: 3px; background: var(--border); overflow: hidden; display: flex; }
.pw-sprint-done-seg  { height: 100%; background: #10b981; transition: width .3s; }
.pw-sprint-scope-seg { height: 100%; background: #f59e0b; transition: width .3s; }
.pw-sprint-legend { display: flex; gap: 12px; margin-top: 5px; flex-wrap: wrap; }
.pw-sprint-legend span { display: flex; align-items: center; gap: 4px; font-size: 10px; color: var(--muted); }
.pw-sprint-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.pw-sprint-dot.done  { background: #10b981; }
.pw-sprint-dot.added { background: #f59e0b; }
.pw-sprint-dot.spill { background: var(--border); }
.pw-sprint-lists { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; min-height: 0; overflow: hidden; }
.pw-sprint-col { display: flex; flex-direction: column; min-height: 0; }
.pw-sprint-col-hd { font-size: 10px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; padding: 0 4px 4px; flex-shrink: 0; }
.pw-sprint-col-body { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.pw-sprint-task { display: flex; align-items: center; gap: 5px; padding: 4px 6px; border-radius: 5px; border: 1px solid var(--border); background: var(--surface); font-size: 11px; min-width: 0; }
.pw-sprint-task:hover { background: var(--surface-secondary); }
.pw-sprint-task-done { opacity: .7; }
.pw-sprint-tick { color: #10b981; font-size: 10px; flex-shrink: 0; }
.pw-sprint-status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.pw-sprint-tk { color: var(--accent); font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.pw-sprint-tt { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--foreground); }
.pw-sprint-pts { color: var(--muted); white-space: nowrap; flex-shrink: 0; }
.pw-sprint-none { font-size: 11px; color: var(--muted); padding: 6px 4px; }
.pw-sprint-scope-note { font-size: 10px; color: var(--warning); flex-shrink: 0; }
</style>
