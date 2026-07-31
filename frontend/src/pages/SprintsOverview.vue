<template>
  <div class="so-root">

    <div v-if="loading" class="space-y-5 p-1">
      <Skeleton class="h-8 w-56 rounded" />
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Skeleton v-for="i in 4" :key="i" class="h-20 rounded-lg" />
      </div>
      <Skeleton class="h-64 rounded-lg" />
    </div>

    <template v-else>
      <!-- Header -->
      <div class="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <div class="flex items-center gap-3 mb-1">
            <router-link :to="`/workspace/${route.params.key}/backlog`" class="text-muted hover:text-foreground transition-colors">
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
            </router-link>
            <h1 class="text-xl font-semibold text-foreground">Sprints Overview</h1>
          </div>
          <p class="ml-9 text-[12.5px] text-muted">{{ store.currentProject?.project_name || route.params.key }} · {{ sprints.length }} sprint{{ sprints.length === 1 ? '' : 's' }}</p>
        </div>
        <button class="so-btn so-btn--ghost" :disabled="refreshing" @click="load({ silent: true })">
          <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" :class="{ 'animate-spin': refreshing }"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
          Refresh
        </button>
      </div>

      <!-- Stat cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div class="so-stat-card">
          <span class="so-stat-label">Active sprint</span>
          <span class="so-stat-value so-stat-value--sm">{{ activeSprint ? activeSprint.sprint_name : '—' }}</span>
        </div>
        <div class="so-stat-card">
          <span class="so-stat-label">Completed sprints</span>
          <span class="so-stat-value">{{ completedSprints.length }}</span>
        </div>
        <div class="so-stat-card">
          <span class="so-stat-label">Avg velocity</span>
          <span class="so-stat-value">{{ avgVelocity }}<span class="text-[13px] font-normal text-muted"> pts</span></span>
        </div>
        <div class="so-stat-card">
          <span class="so-stat-label">Trend</span>
          <span class="so-stat-value so-stat-value--sm" :class="trendClass">{{ trendLabel }}</span>
        </div>
      </div>

      <!-- Velocity chart -->
      <div class="so-card mb-6">
        <h2 class="so-card-title">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
          Velocity
          <span v-if="completedSprints.length" class="text-xs font-normal text-muted ml-2">avg {{ avgVelocity }} pts/sprint</span>
        </h2>
        <apexchart v-if="velocityOptions" type="bar" height="240" :options="velocityOptions" :series="velocitySeries" />
        <div v-else class="flex items-center justify-center h-48 text-[12.5px] text-muted">
          No completed sprints yet — velocity shows up once a sprint finishes.
        </div>
      </div>

      <!-- All sprints table -->
      <div class="so-card">
        <h2 class="so-card-title">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>
          All sprints
        </h2>
        <div class="so-table">
          <div class="so-row so-row--head">
            <span class="so-col so-col--name">Sprint</span>
            <span class="so-col so-col--status">Status</span>
            <span class="so-col so-col--dates">Dates</span>
            <span class="so-col so-col--num">Tasks</span>
            <span class="so-col so-col--num">Pts done</span>
            <span class="so-col so-col--progress">Progress</span>
          </div>
          <router-link
            v-for="s in orderedSprints" :key="s.name"
            :to="`/workspace/${route.params.key}/sprint/${s.name}`"
            class="so-row"
          >
            <span class="so-col so-col--name">
              <span class="so-status-dot" :class="dotClass(s.status)" />
              {{ s.sprint_name }}
            </span>
            <span class="so-col so-col--status">
              <span class="so-badge" :class="badgeClass(s.status)">{{ s.status }}</span>
            </span>
            <span class="so-col so-col--dates">{{ fmtRange(s.start_date, s.end_date) }}</span>
            <span class="so-col so-col--num">{{ s.completed_count || 0 }}<span class="text-muted">/{{ s.issue_count || 0 }}</span></span>
            <span class="so-col so-col--num">{{ s.completed_points || 0 }}<span class="text-muted">/{{ s.total_points || 0 }}</span></span>
            <span class="so-col so-col--progress">
              <span class="so-progress"><span class="so-progress-fill" :style="{ width: pct(s) + '%' }" /></span>
              <span class="so-progress-pct">{{ pct(s) }}%</span>
            </span>
          </router-link>
          <EmptyState
            v-if="!sprints.length"
            :icon="Rocket"
            title="No sprints yet"
            description="Sprints are created from the Backlog — pull tasks in and start one to see velocity here."
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import VueApexCharts from 'vue3-apexcharts'
import { Rocket } from 'lucide-vue-next'
import { Skeleton, EmptyState } from '@/ui'
import { getSprints } from '@/utils/api'
import { useProjectStore } from '@/stores/project'

const route = useRoute()
const store = useProjectStore()
const apexchart = VueApexCharts

// `loading` drives the full-page skeleton and is only ever true for the
// very first load; `refreshing` drives the inline spinner on the Refresh
// button so a manual refresh doesn't blank out data the user is looking at.
const loading = ref(true)
const refreshing = ref(false)
const sprints = ref([])

async function load({ silent = false } = {}) {
  if (silent) refreshing.value = true
  else loading.value = true
  try {
    if (!store.projects.length) await store.fetchProjects()
    const proj = store.projects.find(p => p.key === route.params.key)
    if (!proj) return
    if (!store.currentProject || store.currentProject.key !== route.params.key) {
      await store.fetchBoard(proj.name)
    }
    sprints.value = await getSprints(proj.name)
  } finally {
    loading.value = false
    refreshing.value = false
  }
}
onMounted(() => load())
watch(() => route.params.key, () => load())

const activeSprint = computed(() => sprints.value.find(s => s.status === 'Active'))
const completedSprints = computed(() => sprints.value.filter(s => s.status === 'Completed'))
const orderedSprints = computed(() => {
  const rank = { Active: 0, Planning: 1, Completed: 2 }
  return [...sprints.value].sort((a, b) => (rank[a.status] ?? 3) - (rank[b.status] ?? 3))
})

const avgVelocity = computed(() => {
  const done = completedSprints.value
  if (!done.length) return 0
  const total = done.reduce((sum, s) => sum + (s.completed_points || 0), 0)
  return Math.round((total / done.length) * 10) / 10
})

const trendLabel = computed(() => {
  const done = completedSprints.value
  if (done.length < 2) return 'Not enough data'
  const last = done[done.length - 1].completed_points || 0
  const prev = done[done.length - 2].completed_points || 0
  if (prev === 0) return last > 0 ? 'Up' : 'Flat'
  const delta = Math.round(((last - prev) / prev) * 100)
  if (delta > 0) return `+${delta}%`
  if (delta < 0) return `${delta}%`
  return 'Flat'
})
const trendClass = computed(() => {
  const l = trendLabel.value
  if (l.startsWith('+') || l === 'Up') return 'text-success'
  if (l.startsWith('-')) return 'text-danger'
  return 'text-muted'
})

function fmtDate(v) {
  if (!v) return ''
  try { return new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) } catch { return v }
}
function fmtRange(start, end) {
  if (!start && !end) return '—'
  return `${fmtDate(start)} → ${fmtDate(end)}`
}
function pct(s) {
  const total = s.total_points || 0
  if (!total) return s.issue_count ? Math.round(((s.completed_count || 0) / s.issue_count) * 100) : 0
  return Math.round(((s.completed_points || 0) / total) * 100)
}
function badgeClass(status) {
  const map = {
    Planning: 'bg-default text-muted',
    Active: 'bg-accent-soft text-accent-soft-foreground',
    Completed: 'bg-success-soft text-success-soft-foreground',
  }
  return map[status] || 'bg-default text-muted'
}
function dotClass(status) {
  const map = { Planning: 'so-dot--planning', Active: 'so-dot--active', Completed: 'so-dot--completed' }
  return map[status] || 'so-dot--planning'
}

// Resolve real design tokens for ApexCharts (SVG rendering needs literal
// color values, not var() refs — so we read the computed CSS custom
// properties once rather than hardcoding new hex).
function tokenColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888'
}

const velocityOptions = computed(() => {
  const done = completedSprints.value
  if (!done.length) return null
  const accent = tokenColor('--accent')
  const warning = tokenColor('--warning')
  return {
    chart: { type: 'bar', toolbar: { show: false }, fontFamily: 'inherit', background: 'transparent' },
    colors: [accent],
    plotOptions: { bar: { borderRadius: 6, columnWidth: '55%' } },
    xaxis: {
      categories: done.map(s => s.sprint_name),
      labels: { style: { fontSize: '11px' } },
    },
    yaxis: {
      title: { text: 'Points completed', style: { fontSize: '11px' } },
      labels: { style: { fontSize: '11px' } },
    },
    tooltip: { theme: 'dark' },
    grid: { borderColor: 'rgba(128,128,128,0.15)', strokeDashArray: 5 },
    annotations: avgVelocity.value > 0 ? {
      yaxis: [{
        y: avgVelocity.value,
        borderColor: warning,
        borderWidth: 2,
        strokeDashArray: 6,
        label: { text: `Avg: ${avgVelocity.value}`, style: { color: warning, fontSize: '11px' }, position: 'right' },
      }],
    } : undefined,
  }
})
const velocitySeries = computed(() => [{ name: 'Completed', data: completedSprints.value.map(s => s.completed_points || 0) }])
</script>

<style scoped>
.so-root { padding: 20px 24px 60px; }

.so-btn {
  display: inline-flex; align-items: center; gap: 5px; height: 28px; padding: 0 11px;
  font-size: 12px; font-weight: 600; font-family: inherit; border-radius: var(--radius-md); cursor: pointer;
  white-space: nowrap; transition: background .1s, border-color .1s; border: 1.5px solid transparent;
}
.so-btn--ghost { color: var(--foreground); background: var(--surface); border-color: var(--border); }
.so-btn--ghost:hover { background: var(--surface-secondary); }
.so-btn--ghost:disabled { opacity: var(--disabled-opacity); cursor: var(--cursor-disabled); }

.so-stat-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 12px 14px;
  display: flex; flex-direction: column; gap: 3px;
}
.so-stat-label { font-size: 10.5px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
.so-stat-value { font-size: 20px; font-weight: 700; color: var(--foreground); line-height: 1.15; font-variant-numeric: tabular-nums; }
.so-stat-value--sm { font-size: 14px; font-weight: 600; }

.so-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 16px 18px 12px; }
.so-card-title { font-size: 13px; font-weight: 600; color: var(--foreground); display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }

.so-table { display: flex; flex-direction: column; }
.so-row {
  display: grid; grid-template-columns: 1.6fr 0.9fr 1.1fr 0.6fr 0.7fr 1.2fr; align-items: center;
  gap: 10px; padding: 9px 4px; border-bottom: 1px solid var(--separator); text-decoration: none; color: inherit;
}
.so-row:last-child { border-bottom: none; }
.so-row--head { color: var(--muted); font-size: 10.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; border-bottom: 1px solid var(--border); }
.so-row:not(.so-row--head):hover { background: var(--surface-secondary); border-radius: var(--radius-sm); }
.so-col { font-size: 12.5px; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.so-col--name { display: flex; align-items: center; gap: 7px; font-weight: 600; }
.so-col--dates { color: var(--muted); }
.so-col--num { font-variant-numeric: tabular-nums; }
.so-col--progress { display: flex; align-items: center; gap: 8px; }

.so-status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.so-dot--planning { background: var(--muted-tertiary); }
.so-dot--active { background: var(--accent); }
.so-dot--completed { background: var(--success); }

.so-badge { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: var(--radius-full); font-size: 11px; font-weight: 600; }

.so-progress { flex: 1; height: 4px; border-radius: var(--radius-xs); background: var(--default); overflow: hidden; }
.so-progress-fill { display: block; height: 100%; background: var(--accent); border-radius: var(--radius-xs); }
.so-progress-pct { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; width: 32px; text-align: right; flex-shrink: 0; }
</style>
