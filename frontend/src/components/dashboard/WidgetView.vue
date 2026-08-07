<template>
  <!-- TABLE (self-loading) -->
  <TableWidget v-if="widget.type === 'table'" :widget="widget" :scope-label="scopeLabel" :report-scope="reportScope" :refresh-key="refreshKey" />

  <!-- QUERY / BQL (self-loading, supports chart + table mode) -->
  <QueryWidget v-else-if="widget.type === 'query'" :widget="widget" :height="height" :report-scope="reportScope" :refresh-key="refreshKey" @bql-change="$emit('bql-change', $event)" />

  <!-- TEXT / NOTE annotation widget -->
  <TextWidget v-else-if="widget.type === 'text'" :widget="widget" @text-change="$emit('text-change', $event)" />

  <!-- HEADER / TITLE — plain section divider, no data -->
  <HeaderWidget v-else-if="widget.type === 'header'" :widget="widget" />

  <!-- PRESET report template (handles its own loading/empty) -->
  <PresetWidget v-else-if="widget.type === 'preset'" :widget="widget" :height="height" :fmt="fmt" />

  <!-- COLUMN — one glance/monitoring column (self-loading); templates
       compose N of these side by side into a full board -->
  <ColumnWidget v-else-if="widget.type === 'column'" :widget="widget" :scope-label="scopeLabel" :report-scope="reportScope" :refresh-key="refreshKey" @configure="$emit('configure')" />

  <!-- KANBAN — a full multi-column board (self-loading), any widget-source
       doctype. Looks/behaves like the real per-project Board.vue for BP Task. -->
  <KanbanWidget v-else-if="widget.type === 'kanban'" :widget="widget" :report-scope="reportScope" :refresh-key="refreshKey" />

  <!-- Loading skeleton -->
  <div v-else-if="widget.loading && !widget.data" class="h-full flex flex-col gap-3 p-1">
    <div class="flex items-start justify-between gap-2">
      <div class="flex flex-col gap-1.5 flex-1">
        <Skeleton class="h-3 w-32 rounded-md" />
        <Skeleton class="h-2.5 w-48 rounded-md" />
      </div>
      <Skeleton class="h-7 w-7 rounded-lg shrink-0" />
    </div>
    <Skeleton v-if="widget.type === 'metric'" class="h-8 w-24 rounded-md mt-2" />
    <Skeleton v-else class="flex-1 rounded-lg" />
  </div>

  <!-- Hard empty: no payload at all (failed/never loaded) -->
  <div v-else-if="!widget.data" class="wv-state">
    <div class="flex flex-col items-center gap-1.5 text-center">
      <Inbox :size="18" class="text-[--muted] opacity-60" />
      <span class="text-[12px] text-[--muted]">No data for this scope</span>
    </div>
  </div>

  <!-- METRIC — a single KPI; 0 is a valid value, never "No data" -->
  <div v-else-if="widget.type === 'metric'" class="wv-metric">
    <div class="wv-top">
      <div class="wv-titles">
        <p class="wv-title">{{ widget.title || defaultTitle }}</p>
        <p v-if="widget.description" class="wv-sub">{{ widget.description }}</p>
      </div>
      <span class="wv-pill" :style="pillStyle"><TrendingUp :size="14" /></span>
    </div>
    <div class="wv-num-wrap"><p class="wv-num">{{ fmt(widget.data.total) }}</p></div>
    <p class="wv-foot">{{ scopeLabel(widget.scope) }}</p>
  </div>

  <!-- CHART -->
  <div v-else class="wv-chart">
    <div class="wv-titles wv-chart-head">
      <p class="wv-title">{{ widget.title || defaultTitle }}</p>
      <p class="wv-sub">{{ widget.description || `${scopeLabel(widget.scope)} · by ${groupLabel}` }}</p>
    </div>
    <div class="wv-chart-body">
      <div v-if="!items.length" class="wv-state h-full">
        <span class="text-[12px] text-[--muted]">No data for this scope</span>
      </div>
      <ApexBar        v-else-if="ct === 'bar'"     :items="items" :height="chartH" :format="fmt" />
      <ApexBar        v-else-if="ct === 'hbar'"    :items="items" horizontal :height="chartH" :format="fmt" />
      <ApexStackedBar v-else-if="ct === 'stacked'" :items="items" :height="chartH" :format="fmt" />
      <ApexLine       v-else-if="ct === 'line'"    :items="items" :height="chartH" :format="fmt" />
      <ApexArea       v-else-if="ct === 'area'"    :items="items" :height="chartH" :format="fmt" />
      <ApexGauge      v-else-if="ct === 'gauge'"   :items="items" :height="chartH" :format="fmt" />
      <ApexDonut      v-else                       :items="items" :height="chartH" :format="fmt" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { TrendingUp, Inbox } from 'lucide-vue-next'
import { Skeleton } from '@/ui'
import { ApexBar, ApexStackedBar, ApexLine, ApexArea, ApexDonut, ApexGauge } from '@/components/charts/apex'
import TableWidget from './TableWidget.vue'
import PresetWidget from './PresetWidget.vue'
import QueryWidget from './QueryWidget.vue'
import TextWidget from './TextWidget.vue'
import HeaderWidget from './HeaderWidget.vue'
import ColumnWidget from './ColumnWidget.vue'
import KanbanWidget from './KanbanWidget.vue'

const props = defineProps({
  widget: { type: Object, required: true },
  height: { type: Number, default: 200 },
  scopeLabel: { type: Function, required: true },
  fmt: { type: Function, required: true },
  pill: { type: Object, required: true },
  reportScope: { type: [String, Array], default: 'all' },
  refreshKey: { type: Number, default: 0 },
})

defineEmits(['bql-change', 'text-change', 'configure'])

const METRIC_L = { count: 'Task count', story_points: 'Story points', estimated_hours: 'Estimated hours', actual_hours: 'Logged hours' }
const GROUP_L = { status: 'status', assignee: 'assignee', priority: 'priority', task_type: 'type', epic: 'epic', project: 'project' }

const ct = computed(() => props.widget.chartType || 'bar')
const items = computed(() => {
  const all = props.widget.data?.items || []
  if (['bar', 'hbar', 'line', 'area', 'stacked'].includes(ct.value)) return all.slice(0, 14)
  return all.slice(0, 8)
})
const groupLabel = computed(() => GROUP_L[props.widget.group_by] || props.widget.group_by)
const defaultTitle = computed(() => {
  const m = METRIC_L[props.widget.metric] || props.widget.metric
  return props.widget.type === 'metric' ? m : `${m} by ${groupLabel.value}`
})
const pillStyle = computed(() => { const p = props.pill[props.widget.colorScheme] || props.pill.gray; return { background: p.bg, color: p.color } })
const chartH = computed(() => Math.max(80, props.height - 44))
</script>

<style scoped>
.wv-state { height: 100%; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 12px; color: var(--muted); }

.wv-titles { min-width: 0; }
.wv-title { font-size: 13px; font-weight: 600; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wv-sub { font-size: 11px; color: var(--muted); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* metric */
.wv-metric { height: 100%; display: flex; flex-direction: column; }
.wv-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.wv-pill { padding: 6px; border-radius: 6px; display: grid; place-items: center; flex-shrink: 0; }
.wv-num-wrap { flex: 1; display: flex; flex-direction: column; justify-content: center; margin-top: 12px; }
.wv-num { font-size: 30px; line-height: 1; font-weight: 700; letter-spacing: -0.02em; color: var(--foreground); font-variant-numeric: tabular-nums; }
.wv-foot { margin-top: auto; padding-top: 10px; font-size: 11px; color: var(--muted); }

/* chart */
.wv-chart { height: 100%; display: flex; flex-direction: column; gap: 8px; }
.wv-chart-head { flex-shrink: 0; }
.wv-chart-body { flex: 1; min-height: 0; }
</style>
