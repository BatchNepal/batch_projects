<template>
  <div class="flex flex-col h-full overflow-hidden bg-surface">
    <header class="shrink-0 flex items-center h-[52px] gap-2 px-4 border-b bg-surface">
      <button class="shrink-0 size-8 grid place-items-center rounded-lg text-[--muted] hover:text-[--foreground] hover:bg-default transition-colors" title="Back to dashboard" @click="goBack">
        <Icon :icon="ArrowLeft" :size="16" />
      </button>
      <div class="min-w-0">
        <h1 class="text-[15px] font-semibold text-[--foreground] truncate">{{ widget?.title || 'Widget' }}</h1>
        <p v-if="widget?.description" class="text-[12px] text-[--muted] truncate">{{ widget.description }}</p>
      </div>
      <button
        class="ml-auto shrink-0 h-8 px-2.5 inline-flex items-center gap-1.5 rounded-lg text-[12px] text-muted hover:text-foreground hover:bg-default transition-colors cursor-pointer outline-none"
        title="Refresh"
        @click="refresh"
      >
        <Icon :icon="RefreshCw" :size="14" :class="refreshing ? 'animate-spin text-[--accent]' : ''" />
        Refresh
      </button>
    </header>

    <div class="flex-1 min-h-0 p-5">
      <div v-if="initializing" class="h-full flex items-center justify-center">
        <Skeleton class="h-full w-full rounded-lg" />
      </div>
      <EmptyState v-else-if="!widget" :icon="LayoutDashboard" title="Widget not found" description="It may have been removed from this dashboard." />
      <div v-else class="h-full">
        <WidgetView :widget="merged" :height="bodyHeight" :scope-label="scopeLabel" :fmt="fmtNum" :pill="PILL" :report-scope="dashboardScope" :refresh-key="refreshKey" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useDashboardsStore } from '@/stores/dashboards'
import { getWidgetData } from '@/utils/api'
import { fmtNum } from '@/components/charts/apex/apexTheme.js'
import { PRESETS } from '@/components/dashboard/presets.js'
import WidgetView from '@/components/dashboard/WidgetView.vue'
import { Icon, EmptyState, Skeleton } from '@/ui'
import { ArrowLeft, RefreshCw, LayoutDashboard } from 'lucide-vue-next'

// "Solo page" widget view — the same widget content a dashboard tile shows,
// but taking the whole page (Board.vue's own posture: a normal /workspace
// page, not a public/share link). View-only: editing config stays on the
// dashboard itself, reached via DashboardView.vue's per-widget "Open as
// page" kebab action.
const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const dashboardsStore = useDashboardsStore()

const SELF_LOADING = new Set(['table', 'query', 'text', 'header', 'column', 'kanban'])
const PILL = {
  blue:  { bg: 'var(--accent-soft)',       color: 'var(--accent-soft-foreground)' },
  green: { bg: 'var(--success-soft)',      color: 'var(--success-soft-foreground)' },
  amber: { bg: 'var(--warning-soft)',      color: 'var(--warning-soft-foreground)' },
  red:   { bg: 'var(--danger-soft)',       color: 'var(--danger-soft-foreground)' },
  cyan:  { bg: 'var(--accent-soft)',       color: 'var(--accent-soft-foreground)' },
  teal:  { bg: 'var(--success-soft)',      color: 'var(--success-soft-foreground)' },
  gray:  { bg: 'var(--surface-secondary)', color: 'var(--muted)' },
}

const dashboardId = computed(() => route.params.dashboardId)
const widgetId = computed(() => route.params.widgetId)
const dashboard = computed(() => dashboardsStore.getDashboard(dashboardId.value))
const widget = computed(() => (dashboard.value?.widgets || []).find(w => w.id === widgetId.value) || null)
const dashboardScope = computed(() => dashboard.value?.scope || 'all')
function effScope(w) { return w.scope && w.scope !== 'inherit' ? w.scope : dashboardScope.value }
function serialiseScope(s) {
  if (Array.isArray(s)) return s.length === 0 ? 'all' : s.length === 1 ? s[0] : JSON.stringify(s)
  return s || 'all'
}

const data = ref(null)
const loading = ref(false)
const merged = computed(() => (widget.value ? { ...widget.value, data: data.value, loading: loading.value } : null))

async function loadOrchestrated() {
  if (!widget.value || SELF_LOADING.has(widget.value.type)) return
  loading.value = true
  try {
    if (widget.value.type === 'preset') {
      data.value = await PRESETS[widget.value.preset].fetch({
        ...widget.value, scope: serialiseScope(effScope(widget.value)),
        period: 'last_30_days', milestone: dashboard.value?.milestone || null,
      })
    } else {
      data.value = await getWidgetData({ scope: serialiseScope(effScope(widget.value)), group_by: widget.value.group_by, metric: widget.value.metric })
    }
  } catch { /* WidgetView's own empty state handles a null data.value */ }
  finally { loading.value = false }
}

const refreshing = ref(false)
const refreshKey = ref(0)
async function refresh() {
  refreshing.value = true
  refreshKey.value++
  try { await loadOrchestrated() } finally { refreshing.value = false }
}

function scopeLabel(s) {
  if (!s || s === 'inherit') s = dashboardScope.value
  if (s === 'all') return 'All projects'
  if (Array.isArray(s)) return s.length === 1 ? (store.projects.find(p => p.name === s[0])?.project_name || s[0]) : `${s.length} projects`
  return store.projects.find(p => p.name === s)?.project_name || s
}
const bodyHeight = ref(600)

const initializing = ref(true)
async function init() {
  initializing.value = true
  await dashboardsStore.load()
  await dashboardsStore.ensureDashboard(dashboardId.value)
  if (!store.projects.length) { try { await store.fetchProjects() } catch {} }
  await loadOrchestrated()
  initializing.value = false
}
onMounted(init)

function goBack() { router.push(`/workspace/dashboards/${dashboardId.value}`) }
</script>
