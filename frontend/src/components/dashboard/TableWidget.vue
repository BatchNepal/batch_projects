<template>
  <div class="tw">
    <!-- toolbar -->
    <div class="tw-bar">
      <div class="tw-title-wrap">
        <p class="tw-title">{{ widget.title || 'Table' }}</p>
        <p class="tw-sub">{{ scopeText }} · {{ total }} row{{ total === 1 ? '' : 's' }}</p>
      </div>
      <div class="tw-actions">
        <div class="w-[190px]">
          <Input v-model="q" size="sm" placeholder="Search…" isClearable>
            <template #startContent><Icon :icon="Search" :size="15" class="text-[--muted]" /></template>
          </Input>
        </div>
        <IconButton variant="light" size="sm" title="Export CSV" @click="exportCsv"><Download :size="15" /></IconButton>
      </div>
    </div>

    <!-- table -->
    <div class="tw-table">
      <DataTable :columns="cols" :rows="pageRows" :loading="loading"
        :sort-key="effSortBy" :sort-dir="effSortDir" @sort="toggleSort">
        <template #cell-status="{ value }">
          <Chip size="sm" :color="statusColor(value)" variant="flat">{{ value || '—' }}</Chip>
        </template>
        <template #cell-priority="{ value }">
          <span class="tw-pri" :class="priClass(value)">{{ value || '—' }}</span>
        </template>
        <template #cell-due_date="{ value }">
          <span :class="dueClass(value)">{{ fmtDate(value) }}</span>
        </template>
        <template #cell-assignees="{ value }">
          <span v-if="value && value.length" class="text-[--foreground] truncate">{{ value.map(a => a.full_name || a.user).join(', ') }}</span>
          <span v-else class="tw-muted">—</span>
        </template>
      </DataTable>
    </div>

    <!-- footer -->
    <div v-if="totalPages > 1" class="tw-foot">
      <Pagination v-model:page="page" :total="totalPages" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getReportTasks } from '@/utils/api'
import { DataTable, Pagination, IconButton, Chip, Input, Icon } from '@/ui'
import { Search, Download } from 'lucide-vue-next'

const props = defineProps({
  widget: { type: Object, required: true }, // { scope, statusFilter, columns:[keys], pageSize }
  scopeLabel: { type: Function, required: true },
  reportScope: { type: [String, Array], default: 'all' },
  refreshKey: { type: Number, default: 0 },
})

// Resolve "inherit" against the report-level filter bar.
const effScope = computed(() => (props.widget.scope && props.widget.scope !== 'inherit' ? props.widget.scope : props.reportScope))
// Serialise scope for the API — arrays become a JSON string the backend parses.
function serialiseScope(s) {
  if (Array.isArray(s)) return s.length === 0 ? 'all' : s.length === 1 ? s[0] : JSON.stringify(s)
  return s || 'all'
}

const COLUMN_DEFS = {
  task_key:        { label: 'Key', width: '92px' },
  title:           { label: 'Title' },
  status:          { label: 'Status', width: '132px' },
  priority:        { label: 'Priority', width: '104px' },
  project_name:    { label: 'Project', width: '150px' },
  assignees:       { label: 'Assignee', width: '160px' },
  task_type:       { label: 'Type', width: '110px' },
  epic:            { label: 'Epic', width: '130px' },
  sprint:          { label: 'Sprint', width: '120px' },
  due_date:        { label: 'Due', width: '108px' },
  start_date:      { label: 'Start', width: '108px' },
  story_points:    { label: 'Points', width: '78px' },
  estimated_hours: { label: 'Est. h', width: '80px' },
  actual_hours:    { label: 'Logged h', width: '92px' },
  reporter:        { label: 'Reporter', width: '150px' },
  modified:        { label: 'Updated', width: '120px' },
}
const DEFAULT_COLS = ['task_key', 'title', 'status', 'priority', 'assignees', 'due_date']

const cols = computed(() => {
  const keys = props.widget.columns?.length ? props.widget.columns : DEFAULT_COLS
  return keys.filter((k) => COLUMN_DEFS[k]).map((k) => ({ key: k, label: COLUMN_DEFS[k].label, width: COLUMN_DEFS[k].width, sortable: SORTABLE.has(k) }))
})

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const q = ref('')
const page = ref(1)
const sortKey = ref('')   // header-click override; '' = use widget config
const sortDir = ref('desc')

const pageSize = computed(() => Number(props.widget.pageSize) || 10)
const scopeText = computed(() => props.scopeLabel(effScope.value))
const pageRows = computed(() => rows.value)
const filtered = computed(() => rows.value) // alias kept for the row-count label
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const effSortBy = computed(() => sortKey.value || props.widget.sortBy || 'modified')
const effSortDir = computed(() => (sortKey.value ? sortDir.value : (props.widget.sortOrder || 'desc')))

// Server-side: fetch ALL tasks in scope, one page at a time.
async function load() {
  loading.value = true
  try {
    const res = await getReportTasks({
      scope: serialiseScope(effScope.value),
      status_filter: props.widget.statusFilter || 'open',
      priority: props.widget.priority || null,
      search: q.value.trim() || null,
      sort_by: effSortBy.value,
      sort_order: effSortDir.value,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    rows.value = res?.tasks || []
    total.value = res?.total || 0
  } catch { rows.value = []; total.value = 0 }
  finally { loading.value = false }
}

// Header-click sorting (server-side).
function toggleSort(key) {
  if (!SORTABLE.has(key)) return
  if (sortKey.value === key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortKey.value = key; sortDir.value = 'asc' }
  page.value = 1
}
const SORTABLE = new Set(['task_key', 'title', 'priority', 'due_date', 'start_date', 'story_points', 'modified', 'creation'])

// Reload when the page changes.
watch(page, load)
// Debounced reload on search.
let searchTimer
watch(q, () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { page.value === 1 ? load() : (page.value = 1) }, 280) })
// Reset to page 1 + reload when config / scope / sort / refresh changes.
const cfgKey = () => [
  serialiseScope(effScope.value), props.widget.statusFilter, props.widget.priority,
  effSortBy.value, effSortDir.value, pageSize.value, props.refreshKey,
].join('|')
watch(cfgKey, () => { page.value === 1 ? load() : (page.value = 1) })
onMounted(load)
defineExpose({ load })

function fmtDate(s) {
  if (!s) return '—'
  try { return new Date(s.length > 10 ? s : s + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) } catch { return s }
}
function statusColor(v) {
  const s = String(v || '').toLowerCase()
  if (/done|complete|closed|resolved/.test(s)) return 'success'
  if (/progress|review|testing/.test(s)) return 'primary'
  if (/block|hold/.test(s)) return 'danger'
  return 'default'
}
function priClass(v) {
  const s = String(v || '').toLowerCase()
  if (/urgent|highest|blocker/.test(s)) return 'pri-urgent'
  if (/high/.test(s)) return 'pri-high'
  if (/medium/.test(s)) return 'pri-med'
  return 'pri-low'
}
function dueClass(v) {
  if (!v) return 'tw-muted'
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const d = new Date((v.length > 10 ? v : v + 'T00:00:00'))
  if (d < today) return 'tw-overdue'
  return ''
}

function csvCell(row, k) {
  let v = row[k]
  if (k === 'assignees' && Array.isArray(v)) v = v.map(a => a.full_name || a.user).join('; ')
  return `"${String(v ?? '').replace(/"/g, '""')}"`
}
async function exportCsv() {
  // Export the full filtered result set, not just the current page.
  let exportRows = rows.value
  try {
    const res = await getReportTasks({
      scope: serialiseScope(effScope.value), status_filter: props.widget.statusFilter || 'open',
      priority: props.widget.priority || null, search: q.value.trim() || null,
      sort_by: effSortBy.value, sort_order: effSortDir.value, limit: 5000, offset: 0,
    })
    if (res?.tasks) exportRows = res.tasks
  } catch {}
  const keys = cols.value.map((c) => c.key)
  const head = cols.value.map((c) => c.label).join(',')
  const lines = exportRows.map((row) => keys.map((k) => csvCell(row, k)).join(','))
  const csv = [head, ...lines].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `${(props.widget.title || 'report').replace(/\s+/g, '_')}.csv`
  a.click(); URL.revokeObjectURL(url)
}
</script>

<style scoped>
.tw { height: 100%; display: flex; flex-direction: column; min-height: 0; }
.tw-bar { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; flex-shrink: 0; margin-bottom: 8px; }
.tw-title { font-size: 13px; font-weight: 600; color: var(--foreground); }
.tw-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
.tw-actions { display: flex; align-items: center; gap: 6px; }
.tw-search { position: relative; display: flex; align-items: center; }
.tw-search-ic { position: absolute; left: 8px; color: var(--muted); pointer-events: none; }
.tw-search-in { height: 30px; width: 150px; padding: 0 10px 0 28px; font-size: 13px; border-radius: 6px; background: var(--surface-secondary); color: var(--foreground); outline: none; border: 1px solid transparent; transition: all .12s; }
.tw-search-in:focus { background: var(--surface); border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in oklab, var(--accent) 15%, transparent); }
.tw-table { flex: 1; min-height: 0; overflow: auto; }
.tw-foot { flex-shrink: 0; display: flex; justify-content: flex-end; padding-top: 8px; }
.tw-muted { color: var(--muted); }
.tw-overdue { color: var(--danger); font-weight: 600; }
.tw-pri { font-size: 12px; font-weight: 600; }
.pri-urgent { color: var(--danger); }
.pri-high { color: var(--warning); }
.pri-med { color: var(--warning); }
.pri-low { color: var(--muted); }
</style>
