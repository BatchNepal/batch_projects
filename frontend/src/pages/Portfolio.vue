<template>
  <div class="min-h-full bg-[var(--background)] font-sans text-[var(--foreground)]">
    <div class="max-w-[1600px] mx-auto px-6 py-6">
      <header class="flex items-center justify-between mb-6 gap-4">
        <div>
          <h1 class="text-xl font-semibold text-foreground leading-7">Portfolio</h1>
          <p v-if="data" class="text-[13px] text-muted mt-0.5">
            {{ data.summary.projects }} active {{ data.summary.projects === 1 ? 'project' : 'projects' }}
          </p>
        </div>
      </header>

      <div v-if="loading" class="grid place-items-center" style="height:50vh">
        <div class="pf-spinner" />
      </div>

      <template v-else-if="data">
        <!-- KPI strip — shared KpiTile, not a hand-rolled card -->
        <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-6">
          <KpiTile label="Active projects" :value="data.summary.projects" />
          <KpiTile label="Total tasks" :value="data.summary.tasks" />
          <KpiTile label="Complete" :value="`${data.summary.done_pct}%`" />
          <KpiTile label="Overdue tasks" :value="data.summary.overdue" :delta-good="data.summary.overdue === 0" />
          <KpiTile label="At risk" :value="data.summary.at_risk" :delta-good="data.summary.at_risk === 0" />
          <KpiTile label="Off track" :value="data.summary.off_track" :delta-good="data.summary.off_track === 0" />
        </div>

        <!-- Toolbar -->
        <div class="flex items-center gap-2 mb-3 flex-wrap">
          <Input v-model="query" size="sm" is-clearable placeholder="Search projects…" class="max-w-[240px]">
            <template #startContent><Icon :icon="Search" class="size-3.5 text-muted" /></template>
          </Input>
          <Select v-model="groupBy" size="sm" class="w-[150px]">
            <SelectItem value="none">No grouping</SelectItem>
            <SelectItem value="client">Group by client</SelectItem>
            <SelectItem value="lead">Group by lead</SelectItem>
            <SelectItem value="health">Group by health</SelectItem>
          </Select>
          <Select v-model="healthFilter" size="sm" class="w-[140px]">
            <SelectItem value="all">Any health</SelectItem>
            <SelectItem value="On track">On track</SelectItem>
            <SelectItem value="At risk">At risk</SelectItem>
            <SelectItem value="Off track">Off track</SelectItem>
          </Select>
        </div>

        <template v-if="!filteredProjects.length">
          <EmptyState :icon="Search" title="No matching projects" description="Try a different search or filter." />
        </template>

        <template v-else>
          <div v-for="group in groupedProjects" :key="group.key" class="mb-5">
            <p v-if="groupBy !== 'none'" class="text-[11px] font-semibold text-muted uppercase tracking-wider mb-1.5">
              {{ group.label }} <span class="tabular-nums">({{ group.items.length }})</span>
            </p>
            <div class="pf-list" :class="{ 'pf-list--no-money': !data.can_view_money }">
              <div class="pf-head-row">
                <span>Project</span><span>Health</span><span>Progress</span>
                <span v-if="data.can_view_money">Budget</span>
                <span>Timeline</span>
                <span class="pf-r">Tasks</span><span class="pf-r">Overdue</span><span class="pf-r">Due</span>
              </div>
              <template v-for="p in group.items" :key="p.name">
                <div class="pf-row" @click="toggleExpand(p.name)">
                  <div class="pf-proj">
                    <Icon :icon="expanded.has(p.name) ? ChevronDown : ChevronRight" class="size-3.5 text-muted shrink-0" />
                    <ProjectAvatar :theme="p.theme" :seed="p.key" size="xs" />
                    <div class="min-w-0">
                      <div class="pf-name" @click.stop="openProject(p)">{{ p.project_name }}</div>
                      <div class="pf-meta">
                        <span class="pf-key">{{ p.key }}</span>
                        <template v-if="p.client"><span class="pf-dot-sep">·</span>{{ p.client }}</template>
                        <template v-if="p.lead"><span class="pf-dot-sep">·</span>{{ p.lead }}</template>
                        <template v-if="p.milestone_count"><span class="pf-dot-sep">·</span>{{ p.milestone_count }} milestone{{ p.milestone_count === 1 ? '' : 's' }}</template>
                      </div>
                    </div>
                  </div>

                  <StatusPill :label="p.health" :hex-color="healthColor(p.health)" />

                  <div class="pf-progress">
                    <div class="pf-track">
                      <div class="pf-seg" :style="{ width: pct(p.done, p.total) + '%', background: 'var(--success)' }" />
                      <div class="pf-seg" :style="{ width: pct(p.started, p.total) + '%', background: 'var(--accent)' }" />
                      <div class="pf-seg" :style="{ width: pct(p.todo, p.total) + '%', background: 'var(--border)' }" />
                    </div>
                    <span class="pf-pct tabular-nums">{{ p.done_pct }}%</span>
                  </div>

                  <div v-if="data.can_view_money" class="pf-money">
                    <template v-if="p.budget > 0">
                      <div class="pf-track">
                        <div class="pf-seg" :style="{ width: Math.min(p.budget_used_pct, 100) + '%', background: p.budget_used_pct > 100 ? 'var(--danger)' : 'var(--accent)' }" />
                      </div>
                      <span class="pf-pct tabular-nums">{{ Math.round(p.budget_used_pct) }}%</span>
                    </template>
                    <span v-else class="pf-muted">No budget</span>
                  </div>

                  <div class="pf-timeline">
                    <div class="pf-timeline-track">
                      <div class="pf-timeline-bar" :style="timelineBarStyle(p)" />
                      <div class="pf-timeline-today" :style="{ left: todayOffsetPct + '%' }" />
                    </div>
                  </div>

                  <span class="pf-r pf-tasks tabular-nums">{{ p.total }}</span>
                  <span class="pf-r"><span v-if="p.overdue > 0" class="pf-overdue tabular-nums">{{ p.overdue }}</span><span v-else class="pf-muted">—</span></span>
                  <span class="pf-r pf-due" :class="{ 'pf-due-late': isLate(p) }">{{ p.target_end_date ? fmtDate(p.target_end_date) : '—' }}</span>
                </div>

                <!-- Expandable milestones -->
                <div v-if="expanded.has(p.name)" class="pf-expand">
                  <template v-if="p.milestones.length">
                    <div v-for="m in p.milestones" :key="m.name" class="pf-milestone-row">
                      <Icon :icon="Flag" class="size-3 text-muted shrink-0" />
                      <span class="pf-milestone-title">{{ m.title }}</span>
                      <StatusPill :label="m.status" :color="m.status === 'Completed' ? 'green' : m.status === 'Overdue' ? 'red' : 'gray'" />
                      <span class="pf-milestone-due tabular-nums">{{ m.due_date ? fmtDate(m.due_date) : 'No due date' }}</span>
                    </div>
                  </template>
                  <p v-else class="pf-empty-mini">No milestones on this project.</p>
                </div>
              </template>
            </div>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { getPortfolio } from '@/utils/api'
import { toast } from 'vue-sonner'
import { Icon, KpiTile, Input, Select, SelectItem, EmptyState, StatusPill, ProjectAvatar } from '@/ui'
import { Search, ChevronDown, ChevronRight, Flag } from 'lucide-vue-next'

const router = useRouter()
const store = useProjectStore()
const loading = ref(true)
const data = ref(null)
const query = ref('')
const groupBy = ref('none')
const healthFilter = ref('all')
const expanded = ref(new Set())

function pct(v, total) { return total ? (v / total) * 100 : 0 }
function fmtDate(s) { return s ? new Date(s + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '' }
function isLate(p) {
  if (!p.target_end_date) return false
  return new Date(p.target_end_date + 'T00:00:00') < new Date() && p.done_pct < 100
}
function openProject(p) { router.push(store.projectLanding(p.key)) }
function toggleExpand(name) {
  const s = new Set(expanded.value)
  s.has(name) ? s.delete(name) : s.add(name)
  expanded.value = s
}
function healthColor(h) {
  return { 'On track': 'var(--success)', 'At risk': 'var(--warning)', 'Off track': 'var(--danger)' }[h] || 'var(--muted)'
}

// ── Timeline — shared axis across every visible project, CSS bars only ──
const timelineAxis = computed(() => {
  const dates = []
  for (const p of (data.value?.projects || [])) {
    if (p.start_date) dates.push(new Date(p.start_date + 'T00:00:00').getTime())
    if (p.target_end_date) dates.push(new Date(p.target_end_date + 'T00:00:00').getTime())
  }
  const now = Date.now()
  dates.push(now)
  if (!dates.length) return { min: now, max: now }
  const min = Math.min(...dates), max = Math.max(...dates)
  const pad = Math.max((max - min) * 0.05, 86400000 * 3)
  return { min: min - pad, max: max + pad }
})
const todayOffsetPct = computed(() => {
  const { min, max } = timelineAxis.value
  const span = max - min
  return span ? ((Date.now() - min) / span) * 100 : 50
})
function timelineBarStyle(p) {
  const { min, max } = timelineAxis.value
  const span = max - min
  if (!span || !p.start_date || !p.target_end_date) return { display: 'none' }
  const s = new Date(p.start_date + 'T00:00:00').getTime()
  const e = new Date(p.target_end_date + 'T00:00:00').getTime()
  const left = ((s - min) / span) * 100
  const width = Math.max(((e - s) / span) * 100, 1.5)
  return { left: left + '%', width: width + '%' }
}

// ── Toolbar: search + health filter + grouping ──
const filteredProjects = computed(() => {
  let out = data.value?.projects || []
  if (healthFilter.value !== 'all') out = out.filter(p => p.health === healthFilter.value)
  const q = query.value.trim().toLowerCase()
  if (q) out = out.filter(p =>
    p.project_name.toLowerCase().includes(q) || p.key.toLowerCase().includes(q) ||
    (p.client || '').toLowerCase().includes(q) || (p.lead || '').toLowerCase().includes(q))
  return out
})
const groupedProjects = computed(() => {
  if (groupBy.value === 'none') return [{ key: 'all', label: '', items: filteredProjects.value }]
  const keyFor = groupBy.value === 'client' ? (p => p.client || 'No client')
    : groupBy.value === 'lead' ? (p => p.lead || 'No lead')
    : (p => p.health)
  const order = groupBy.value === 'health' ? ['Off track', 'At risk', 'On track'] : null
  const map = new Map()
  for (const p of filteredProjects.value) {
    const k = keyFor(p)
    if (!map.has(k)) map.set(k, [])
    map.get(k).push(p)
  }
  const keys = order ? order.filter(k => map.has(k)) : [...map.keys()].sort()
  return keys.map(k => ({ key: k, label: k, items: map.get(k) }))
})

async function load() {
  loading.value = true
  try {
    data.value = await getPortfolio()
  } catch (e) {
    toast.error("Couldn't load portfolio", { description: String(e.message || e) })
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.pf-spinner { width: 24px; height: 24px; border: 2.5px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: pf-spin .7s linear infinite; }
@keyframes pf-spin { to { transform: rotate(360deg) } }

.pf-list { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; }
.pf-head-row, .pf-row { display: grid; grid-template-columns: minmax(200px, 1.6fr) 110px minmax(150px, 1.4fr) minmax(110px, 1fr) minmax(140px, 1.4fr) 60px 70px 110px; align-items: center; gap: 12px; padding: 10px 16px; }
/* Money-blind viewers (view_money gating): the Budget column is
   never RENDERED for them (not just hidden) — the grid template drops a
   column too, so the remaining 7 stay aligned instead of leaving a gap. */
.pf-list--no-money .pf-head-row, .pf-list--no-money .pf-row { grid-template-columns: minmax(200px, 1.6fr) 110px minmax(150px, 1.4fr) minmax(140px, 1.4fr) 60px 70px 110px; }
.pf-head-row { font-size: var(--text-xs); font-weight: var(--font-semibold); text-transform: uppercase; letter-spacing: .04em; color: var(--muted); border-bottom: 1px solid var(--border); }
.pf-row { border-bottom: 1px solid var(--surface-secondary); cursor: pointer; transition: background .12s; }
.pf-row:last-child { border-bottom: none; }
.pf-row:hover { background: var(--surface-hover); }
.pf-r { text-align: right; }

.pf-proj { display: flex; align-items: center; gap: 8px; min-width: 0; }
.pf-name { font-size: var(--text-sm); font-weight: var(--font-semibold); color: var(--foreground); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pf-name:hover { text-decoration: underline; }
.pf-meta { display: flex; align-items: center; gap: 5px; font-size: var(--text-xs); color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pf-key { font-family: var(--font-mono); font-weight: var(--font-semibold); color: var(--muted); }
.pf-dot-sep { color: var(--border-secondary); }

.pf-progress, .pf-money { display: flex; align-items: center; gap: 8px; }
.pf-track { flex: 1; height: 7px; border-radius: 4px; background: var(--surface-secondary); display: flex; overflow: hidden; }
.pf-seg { height: 100%; transition: width .3s ease; }
.pf-pct { font-size: var(--text-xs); font-weight: var(--font-semibold); color: var(--muted); width: 32px; text-align: right; flex-shrink: 0; }

.pf-timeline-track { position: relative; height: 7px; border-radius: 4px; background: var(--surface-secondary); }
.pf-timeline-bar { position: absolute; top: 0; height: 100%; border-radius: 4px; background: var(--accent-soft); border: 1px solid var(--accent); }
.pf-timeline-today { position: absolute; top: -2px; width: 2px; height: 11px; background: var(--danger); border-radius: 1px; }

.pf-tasks { font-size: var(--text-sm); color: var(--foreground); }
.pf-overdue { display: inline-flex; min-width: 20px; justify-content: center; font-size: var(--text-xs); font-weight: var(--font-bold); color: var(--danger); background: var(--danger-soft); padding: 1px 6px; border-radius: 6px; }
.pf-muted { color: var(--border-secondary); font-size: var(--text-xs); }
.pf-due { font-size: var(--text-sm); color: var(--muted); }
.pf-due-late { color: var(--danger); font-weight: var(--font-medium); }

.pf-expand { background: var(--surface-secondary); padding: 8px 16px 8px 46px; border-bottom: 1px solid var(--surface-secondary); }
.pf-milestone-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: var(--text-xs); }
.pf-milestone-title { flex: 1; color: var(--foreground); }
.pf-milestone-due { color: var(--muted); }
.pf-empty-mini { font-size: var(--text-xs); color: var(--muted); padding: 4px 0; }

@media (max-width: 900px) {
  .pf-head-row, .pf-row { grid-template-columns: 1.5fr 90px 1.2fr; }
  .pf-head-row > *:nth-child(n+4), .pf-row > *:nth-child(n+4) { display: none; }
}
</style>
