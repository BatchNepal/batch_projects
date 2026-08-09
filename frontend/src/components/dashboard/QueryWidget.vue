<template>
  <div class="qw">
    <!-- header -->
    <div class="qw-head">
      <div class="qw-meta">
        <p class="qw-title">{{ widget.title || 'BQL Query' }}</p>
        <p v-if="parseResult.ok && mode === 'table'" class="qw-sub">{{ rows.length }} row{{ rows.length !== 1 ? 's' : '' }} · Batch Query Language</p>
        <p v-else-if="parseResult.ok && mode === 'chart'" class="qw-sub">{{ chartItems.length }} groups · {{ parseResult.group_by }} chart</p>
        <p v-else-if="!parseResult.ok && widget.bql" class="qw-err-sub">{{ parseResult.error }}</p>
        <p v-else class="qw-sub">Batch Query Language</p>
      </div>
      <div class="flex items-center gap-1 shrink-0">
        <button class="qw-btn" title="Toggle BQL editor" :class="{ 'qw-btn-active': editorOpen }" @click="editorOpen = !editorOpen">
          <Code2 :size="13" />
        </button>
        <button class="qw-btn" title="Refresh" :class="{ 'animate-spin': loading }" @click="load">
          <RefreshCw :size="13" />
        </button>
        <button v-if="mode === 'table'" class="qw-btn" title="Export CSV" @click="exportCsv">
          <Download :size="13" />
        </button>
      </div>
    </div>

    <!-- inline BQL editor -->
    <div v-if="editorOpen" class="qw-editor-wrap">
      <textarea
        v-model="localBql"
        class="qw-editor"
        placeholder="project = &quot;PROJ&quot; AND status = &quot;Open&quot;&#10;OR: project = &quot;PROJ&quot; GROUP BY status VIEW donut"
        rows="3"
        spellcheck="false"
        @keydown.ctrl.enter.prevent="commitBql"
        @keydown.meta.enter.prevent="commitBql"
      />
      <div class="qw-editor-foot">
        <span class="qw-hint">Ctrl+Enter to run · <strong>GROUP BY field</strong> for charts</span>
        <button class="qw-run-btn" :disabled="!localBql.trim()" @click="commitBql">Run</button>
      </div>
      <div class="qw-examples">
        <span class="qw-ex-label">Examples:</span>
        <button v-for="ex in BQL_EXAMPLES" :key="ex.label" class="qw-ex-pill" @click="loadExample(ex.bql)">{{ ex.label }}</button>
      </div>
    </div>

    <!-- no BQL yet -->
    <div v-if="!widget.bql && !editorOpen" class="qw-empty">
      <div class="qw-empty-icon"><TerminalSquare :size="22" /></div>
      <p class="qw-empty-title">Write a BQL query</p>
      <p class="qw-empty-sub">Click <Code2 :size="12" class="inline" /> above to open the editor. Add <code class="qw-code">GROUP BY field</code> to render a chart.</p>
    </div>

    <!-- BQL error -->
    <div v-else-if="!parseResult.ok && widget.bql" class="qw-empty">
      <AlertCircle :size="20" class="text-[--danger]" />
      <p class="qw-empty-title text-[--danger]">BQL syntax error</p>
      <p class="qw-empty-sub">{{ parseResult.error }}</p>
    </div>

    <!-- CHART MODE -->
    <template v-else-if="mode === 'chart'">
      <div v-if="loading && !chartItems.length" class="qw-skels">
        <div v-for="n in 4" :key="n" class="qw-skel-row">
          <Skeleton class="h-3 w-24 rounded" />
          <Skeleton class="h-3 flex-1 rounded" />
        </div>
      </div>
      <div v-else-if="chartItems.length" class="qw-chart-body">
        <ApexDonut  v-if="chartView === 'donut'"  :items="chartItems" :height="chartH" />
        <ApexBar    v-else-if="chartView === 'hbar'" :items="chartItems" :horizontal="true" :height="chartH" />
        <ApexLine   v-else-if="chartView === 'line'" :items="chartItems" :height="chartH" />
        <ApexArea   v-else-if="chartView === 'area'" :items="chartItems" :height="chartH" />
        <ApexBar    v-else                           :items="chartItems" :height="chartH" />
      </div>
      <div v-else class="qw-empty">
        <SearchX :size="20" class="text-[--border]" />
        <p class="qw-empty-sub">No data for this query</p>
      </div>
    </template>

    <!-- TABLE MODE -->
    <template v-else-if="mode === 'table'">
      <!-- row count follows the widget's own configured pageSize (capped —
           a 50-row skeleton is its own kind of ugly) instead of a hardcoded
           5, so it stops visibly growing/shrinking the moment real rows
           replace it. -->
      <div v-if="loading && !rows.length" class="qw-skels">
        <div v-for="n in Math.min(pageSize, 10)" :key="n" class="qw-skel-row">
          <Skeleton class="h-3 w-20 rounded" />
          <Skeleton class="h-3 flex-1 rounded" />
          <Skeleton class="h-3 w-24 rounded" />
          <Skeleton class="h-3 w-20 rounded" />
        </div>
      </div>

      <template v-else-if="rows.length">
        <div class="qw-table-wrap">
          <table class="qw-tbl">
            <thead>
              <tr>
                <th v-for="col in visibleCols" :key="col.key" class="qw-th" :style="col.width ? { width: col.width } : {}">{{ col.label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in pageRows" :key="row.name" class="qw-tr">
                <td v-for="col in visibleCols" :key="col.key" class="qw-td">
                  <template v-if="col.key === 'status'">
                    <Chip size="sm" :color="statusColor(row.status)" variant="flat">{{ row.status || '—' }}</Chip>
                  </template>
                  <template v-else-if="col.key === 'priority'">
                    <span class="qw-pri" :class="priClass(row.priority)">{{ row.priority || '—' }}</span>
                  </template>
                  <template v-else-if="col.key === 'due_date'">
                    <span :class="dueClass(row.due_date)">{{ fmtDate(row.due_date) }}</span>
                  </template>
                  <template v-else-if="col.key === 'assignees'">
                    {{ (row.assignees || []).map(a => a.full_name || a.user).join(', ') || '—' }}
                  </template>
                  <template v-else>{{ row[col.key] ?? '—' }}</template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="totalPages > 1" class="qw-foot">
          <Pagination v-model:page="page" :total="totalPages" />
        </div>
      </template>

      <div v-else-if="parseResult.ok && widget.bql" class="qw-empty">
        <SearchX :size="20" class="text-[--border]" />
        <p class="qw-empty-sub">No tasks match this query</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { queryTasks, getWidgetData, queryBqlGroupBy } from '@/utils/api'
import { parseBQL, bqlToQueryParams, bqlToWidgetDataParams, BQL_EXAMPLES } from '@/utils/bql'
import { Skeleton, Chip, Pagination } from '@/ui'
import { ApexBar, ApexDonut, ApexLine, ApexArea } from '@/components/charts/apex'
import { Code2, RefreshCw, Download, TerminalSquare, AlertCircle, SearchX } from 'lucide-vue-next'

const props = defineProps({
  widget:      { type: Object,  required: true },
  height:      { type: Number,  default: 200 },
  reportScope: { type: String,  default: 'all' },
  refreshKey:  { type: Number,  default: 0 },
})

const emit = defineEmits(['bql-change'])

const rows       = ref([])
const chartItems = ref([])
const loading    = ref(false)
const page       = ref(1)
const editorOpen = ref(!props.widget.bql)
const localBql   = ref(props.widget.bql || '')

const parseResult = computed(() => parseBQL(props.widget.bql || ''))

// chart or table mode depends on GROUP BY presence
const mode      = computed(() => parseResult.value.group_by ? 'chart' : 'table')
const chartView = computed(() => parseResult.value.view || 'bar')
const chartH    = computed(() => Math.max(80, props.height - 80))

const COLS = [
  { key: 'task_key', label: 'Key',      width: '92px' },
  { key: 'title',    label: 'Title' },
  { key: 'status',   label: 'Status',   width: '130px' },
  { key: 'priority', label: 'Priority', width: '100px' },
  { key: 'assignees',label: 'Assignee', width: '150px' },
  { key: 'due_date', label: 'Due',      width: '100px' },
]
const visibleCols = computed(() => {
  const keys = props.widget.columns?.length ? props.widget.columns : COLS.map(c => c.key)
  return COLS.filter(c => keys.includes(c.key))
})

const pageSize   = computed(() => Number(props.widget.pageSize) || 15)
const totalPages = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize.value)))
const pageRows   = computed(() => {
  const s = (page.value - 1) * pageSize.value
  return rows.value.slice(s, s + pageSize.value)
})

async function load() {
  const bql = props.widget.bql
  if (!bql || !bql.trim()) return
  const parsed = parseBQL(bql)
  if (!parsed.ok) return

  loading.value = true

  try {
    if (parsed.group_by) {
      // Chart mode — use query_bql_group_by so WHERE filters (sprint, status, etc.) apply
      const wdp = bqlToWidgetDataParams(bql)
      const qp  = bqlToQueryParams(bql)
      const scope = wdp.scope && wdp.scope !== 'all' ? wdp.scope
        : (props.widget.scope && props.widget.scope !== 'inherit' && props.widget.scope !== 'all' ? props.widget.scope
          : (props.reportScope && props.reportScope !== 'all' ? props.reportScope : 'all'))
      const data = await queryBqlGroupBy(scope, qp.filters || {}, wdp.group_by, wdp.metric)
      chartItems.value = data?.items || []
    } else {
      // Table mode — call queryTasks
      const params = bqlToQueryParams(bql)
      if (params.error) return
      const proj = params.project
        || (props.widget.scope && props.widget.scope !== 'inherit' && props.widget.scope !== 'all' ? props.widget.scope : null)
        || (props.reportScope && props.reportScope !== 'all' ? props.reportScope : null)
      const raw = await queryTasks(proj, params.filters, null, params.sort_by, params.sort_order, params.limit, 0)
      rows.value = Array.isArray(raw) ? raw : (raw?.tasks || raw?.results || [])
      page.value = 1
    }
  } catch {
    rows.value = []
    chartItems.value = []
  } finally {
    loading.value = false
  }
}

function commitBql() {
  const v = localBql.value.trim()
  emit('bql-change', v)
  editorOpen.value = false
}

function loadExample(bql) { localBql.value = bql }

function exportCsv() {
  const keys = visibleCols.value.map(c => c.key)
  const head = visibleCols.value.map(c => c.label).join(',')
  const lines = rows.value.map(row =>
    keys.map(k => `"${String(row[k] ?? '').replace(/"/g, '""')}"`).join(','))
  const csv = [head, ...lines].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `${(props.widget.title || 'bql_query').replace(/\s+/g, '_')}.csv`
  a.click(); URL.revokeObjectURL(url)
}

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
  if (/urgent|highest|blocker/.test(s)) return 'qw-pri-urgent'
  if (/high/.test(s)) return 'qw-pri-high'
  if (/medium/.test(s)) return 'qw-pri-med'
  return 'qw-pri-low'
}
function dueClass(v) {
  if (!v) return 'qw-muted'
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const d = new Date(v.length > 10 ? v : v + 'T00:00:00')
  return d < today ? 'qw-overdue' : ''
}

watch(() => [props.widget.bql, props.reportScope], load)
watch(() => props.refreshKey, load)
onMounted(load)
defineExpose({ load })
</script>

<style scoped>
.qw { height: 100%; display: flex; flex-direction: column; min-height: 0; gap: 8px; }

/* header */
.qw-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; flex-shrink: 0; }
.qw-meta { min-width: 0; }
.qw-title { font-size: 13px; font-weight: 600; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.qw-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
.qw-err-sub { font-size: 11px; color: var(--danger); margin-top: 2px; }
.qw-btn {
  width: 26px; height: 26px; border-radius: 7px; display: grid; place-items: center;
  color: var(--muted); border: 1px solid transparent; background: transparent;
  cursor: pointer; transition: all .12s;
}
.qw-btn:hover { background: var(--surface-secondary); color: var(--foreground); }
.qw-btn-active { background: var(--accent-soft); color: var(--accent-soft-foreground); border-color: var(--accent-soft); }

/* editor */
.qw-editor-wrap { flex-shrink: 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--surface-secondary); }
.qw-editor {
  width: 100%; display: block; padding: 8px 10px; font-size: 12px; font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
  line-height: 1.6; color: var(--foreground); background: transparent; border: none; resize: none; outline: none;
}
.qw-editor-foot { display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; border-top: 1px solid var(--border); background: var(--surface-secondary); }
.qw-hint { font-size: 11px; color: var(--muted); }
.qw-run-btn {
  height: 26px; padding: 0 12px; border-radius: 6px; font-size: 12px; font-weight: 600;
  background: var(--accent); color: var(--accent-foreground); border: none; cursor: pointer; transition: opacity .12s;
}
.qw-run-btn:hover { opacity: .88; }
.qw-run-btn:disabled { opacity: .45; cursor: not-allowed; }
.qw-examples { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 6px 10px 8px; }
.qw-ex-label { font-size: 11px; color: var(--muted); white-space: nowrap; }
.qw-ex-pill {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted); cursor: pointer; white-space: nowrap; transition: all .1s;
}
.qw-ex-pill:hover { background: var(--surface-secondary); }

/* skeleton rows */
.qw-skels { display: flex; flex-direction: column; gap: 8px; flex: 1; padding-top: 4px; }
.qw-skel-row { display: flex; gap: 12px; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border); }

/* chart */
.qw-chart-body { flex: 1; min-height: 0; }

/* table */
.qw-table-wrap { flex: 1; min-height: 0; overflow: auto; }
.qw-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.qw-th { padding: 6px 10px; text-align: left; font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; border-bottom: 1px solid var(--border); white-space: nowrap; background: var(--surface-secondary); position: sticky; top: 0; z-index: 1; }
.qw-tr:hover { background: var(--surface-secondary); }
.qw-td { padding: 7px 10px; color: var(--foreground); border-bottom: 1px solid var(--border); vertical-align: middle; }
.qw-td:first-child { color: var(--accent); font-weight: 600; white-space: nowrap; }

.qw-foot { flex-shrink: 0; display: flex; justify-content: flex-end; padding-top: 6px; }

/* empty / error */
.qw-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; text-align: center; padding: 16px; }
.qw-empty-icon { width: 40px; height: 40px; border-radius: 8px; background: var(--surface-secondary); display: grid; place-items: center; color: var(--muted); }
.qw-empty-title { font-size: 13px; font-weight: 600; color: var(--foreground); }
.qw-empty-sub { font-size: 12px; color: var(--muted); max-width: 280px; line-height: 1.5; }
.qw-code { font-family: ui-monospace, monospace; font-size: 11px; background: var(--surface-secondary); padding: 1px 4px; border-radius: 4px; color: var(--accent); }

.qw-muted { color: var(--muted); }
.qw-overdue { color: var(--danger); font-weight: 600; }
.qw-pri { font-size: 12px; font-weight: 600; }
.qw-pri-urgent { color: var(--danger); }
.qw-pri-high { color: var(--warning); }
.qw-pri-med { color: var(--warning); }
.qw-pri-low { color: var(--muted); }
</style>
