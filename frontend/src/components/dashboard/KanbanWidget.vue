<template>
  <div class="kw">
    <!-- 5, not 3 — real column count comes FROM the data we haven't loaded
         yet (project workflow_states / generic group-by values), so an
         exact match isn't available upfront; 5 sits closer to the typical
         4-8 statuses a real board has than the old 3 did. -->
    <div v-if="loading && !columns.length" class="kw-loading">
      <Skeleton v-for="i in 5" :key="i" class="w-[330px] h-full rounded-sm shrink-0" />
    </div>

    <div v-else-if="!columns.length && !loading" class="kw-empty">
      <Inbox :size="18" class="text-muted opacity-60" />
      <span class="text-[12px] text-muted">No data for this scope</span>
    </div>

    <!-- Say plainly why cards can't be dragged, rather than leaving a board
         that looks interactive but silently ignores every drop. -->
    <p v-if="!canDrag" class="kw-readonly-note">
      Read-only — drag-and-drop moves cards by status. Group by Status to enable it.
    </p>

    <div v-if="columns.length" class="kw-cols">
      <KanbanColumnShell
        v-for="col in columns" :key="col.key"
        :title="col.label" :count="col.rows.length" :color="col.color"
        :collapsed="collapsedCols.has(col.key)"
        @update:collapsed="v => setCollapsed(col.key, v)"
        :drag-over="dragOverKey === col.key"
      >
        <div
          class="kw-col-body"
          :data-col-key="col.key"
          @dragover.prevent="onDragOver"
          @dragenter.prevent="onDragEnter(col.key)"
          @dragleave="onDragLeave(col.key, $event)"
          @drop.prevent="onDrop(col)"
        >
          <template v-if="isTask">
            <TaskCard
              v-for="row in col.rows" :key="row.name"
              :issue="row"
              @click="store.openTaskDetail(row.name)"
            />
          </template>
          <template v-else>
            <DocCard
              v-for="row in col.rows" :key="row.name"
              :row="row"
              @click="openQuickview(row)"
            />
          </template>
          <p v-if="!col.rows.length" class="kw-col-empty">No records</p>
        </div>
      </KanbanColumnShell>
    </div>

    <DocQuickview
      v-if="!isTask"
      :open="quickview.open" :doctype="widget.doctype" :name="quickview.name"
      @update:open="v => (quickview.open = v)"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Inbox } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Skeleton } from '@/ui'
import KanbanColumnShell from '@/components/KanbanColumnShell.vue'
import TaskCard from '@/components/TaskCard.vue'
import DocCard from './DocCard.vue'
import DocQuickview from './DocQuickview.vue'
import { useProjectStore } from '@/stores/project'
import { getColumnWidgetData, getDoctypeGroupData, getDoctypeColumnData, updateTaskStatus, updateWidgetSourceField } from '@/utils/api'
import { DEFAULT_STATUSES } from '@/stores/dashboards'
import { confirmDialog } from '@/composables/useConfirmDialog'

// Full multi-column kanban board for any widget-source doctype — auto-
// generates one column per distinct group_by value. BP Task uses the exact
// same KanbanColumnShell + TaskCard the real per-project Board.vue uses (see
// KanbanColumn.vue), so a Task-sourced board here is visually identical to
// the real thing. Other doctypes use DocCard, styled the same but fed
// from the doctype-agnostic get_doctype_column_data engine. Drag-and-drop is
// supported for both (see onDrop below) — validation is real: BP Task goes
// through update_task_status's _completing_into_blocked() check (same as
// the real board), other doctypes go through Frappe's own doc.save()
// validate() hooks (update_widget_source_field, mirrors the automation
// rule's "Update ERPNext Document" write path).
const props = defineProps({
  widget: { type: Object, required: true },
  reportScope: { type: [String, Array], default: 'all' },
  refreshKey: { type: Number, default: 0 },
})

const store = useProjectStore()
const isTask = computed(() => (props.widget.doctype || 'BP Task') === 'BP Task')

const columns = ref([])
const loading = ref(false)
const collapsedCols = ref(new Set())
function setCollapsed(key, v) {
  const s = new Set(collapsedCols.value)
  v ? s.add(key) : s.delete(key)
  collapsedCols.value = s
}

const effScope = computed(() => (props.widget.scope && props.widget.scope !== 'inherit' ? props.widget.scope : props.reportScope))
function serialiseScope(s) {
  if (Array.isArray(s)) return s.length === 0 ? 'all' : s.length === 1 ? s[0] : JSON.stringify(s)
  return s || 'all'
}

// One grouped request, not one request per column. This used to fire N
// parallel get_column_widget_data calls (one per status) purely to rebuild
// what a single grouped call already returns — an N+1 that grew with every
// status a project defined.
const MAX_KANBAN_COLUMNS = 12

async function loadTaskColumns() {
  const scope = effScope.value
  const groupBy = props.widget.group_by || 'status'

  // A kanban wants to show a status column even when it's EMPTY — that's
  // where you drop things. Grouped data only ever contains non-empty
  // groups, so the project's declared workflow states are merged in as the
  // expected column set, in their real pipeline order.
  let expected = []
  let colorMap = {}
  if (groupBy === 'status') {
    expected = DEFAULT_STATUSES
    if (scope && scope !== 'all' && !Array.isArray(scope)) {
      const proj = store.projects.find(p => p.name === scope || p.key === scope)
      const ws = (proj?.workflow_states || []).filter(Boolean)
      if (ws.length) {
        expected = ws.map(s => s.name || s)
        colorMap = Object.fromEntries(ws.map(s => [s.name || s, s.color]))
      }
    }
  }

  const res = await getColumnWidgetData({
    scope: serialiseScope(scope), status_filter: 'all', group_by: groupBy,
    filters: props.widget.filters || [],
  })
  const byKey = Object.fromEntries((res?.buckets || []).map(b => [b.key, b]))

  const keys = [...expected]
  for (const b of res?.buckets || []) if (!keys.includes(b.key)) keys.push(b.key)

  columns.value = keys.slice(0, MAX_KANBAN_COLUMNS).map(k => ({
    key: k,
    label: byKey[k]?.label || k,
    color: colorMap[k] || null,
    rows: byKey[k]?.tasks || [],
  }))
}

async function loadDoctypeColumns() {
  const doctype = props.widget.doctype
  const groupBy = props.widget.group_by || 'status'
  const filters = props.widget.filters || []
  const group = await getDoctypeGroupData({ doctype, group_by: groupBy, filters, scope: null })
  const items = (group.items || []).slice(0, 8)
  const results = await Promise.all(items.map(item => {
    const f = item.key === '__none__'
      ? [...filters, { fieldname: groupBy, operator: 'is_not_set' }]
      : [...filters, { fieldname: groupBy, operator: '=', value: item.key }]
    return getDoctypeColumnData({
      doctype, filters: f, limit: 100,
      label_fields: props.widget.label_fields || [], date_field: props.widget.date_field || null,
    })
  }))
  columns.value = items.map((item, i) => ({
    key: item.key, label: item.label, color: null,
    rows: results[i]?.rows || [],
  }))
}

async function load() {
  if (!props.widget.doctype && !isTask.value) return
  loading.value = true
  try {
    if (isTask.value) await loadTaskColumns()
    else await loadDoctypeColumns()
  } catch {
    columns.value = []
  } finally {
    loading.value = false
  }
}

const quickview = ref({ open: false, name: '' })
function openQuickview(row) {
  quickview.value = { open: true, name: row.name }
}

// ── drag-and-drop ──────────────────────────────────────────────────────
const dragOverKey = ref(null)
let leaveTimer = null
function onDragOver(e) { e.dataTransfer.dropEffect = 'move' }
function onDragEnter(key) {
  dragOverKey.value = key
  if (leaveTimer) { clearTimeout(leaveTimer); leaveTimer = null }
}
function onDragLeave(key) {
  leaveTimer = setTimeout(() => { if (dragOverKey.value === key) dragOverKey.value = null }, 50)
}

async function onDrop(col) {
  dragOverKey.value = null
  if (leaveTimer) clearTimeout(leaveTimer)
  if (!canDrag.value) return
  if (isTask.value) {
    const drag = window.__dragIssue
    if (!drag) return
    window.__dragIssue = null
    await dropTask(drag.issue, col.key)
  } else {
    const drag = window.__dragKanbanRow
    if (!drag) return
    window.__dragKanbanRow = null
    await dropGeneric(drag.row, col.key)
  }
}

function moveRowBetweenColumns(name, fromKey, toKey, rowFactory) {
  const fromCol = columns.value.find(c => c.key === fromKey)
  const toCol = columns.value.find(c => c.key === toKey)
  let moved = null
  if (fromCol) {
    const i = fromCol.rows.findIndex(r => r.name === name)
    if (i > -1) [moved] = fromCol.rows.splice(i, 1)
  }
  if (toCol) toCol.rows.unshift(rowFactory ? rowFactory(moved) : moved)
  return { fromCol, toCol, moved }
}

// Real validation, not a stub: _completing_into_blocked() (board.py) blocks
// moving into a completed-category status with unresolved dependencies —
// the same rule the real Board.vue enforces. confirmDialog() mirrors the
// existing app-wide pattern for a destructive-ish override (see
// MoneyDrawer.vue's submit confirm) rather than inventing a toast-action UI.
async function dropTask(issue, newStatus, force = false) {
  if (issue.status === newStatus && !force) return
  const { fromCol, toCol } = moveRowBetweenColumns(issue.name, issue.status, newStatus, (r) => ({ ...r, status: newStatus }))
  try {
    const res = await updateTaskStatus(issue.name, newStatus, null, force)
    if (res?.blocked) {
      moveRowBetweenColumns(issue.name, newStatus, issue.status, () => issue) // revert
      if (await confirmDialog(`This move is blocked (${(res.blockers || []).join(', ') || 'unresolved dependencies'}). Force it anyway?`)) {
        await dropTask(issue, newStatus, true)
      }
    }
  } catch (e) {
    toast.error(e.message || 'Failed to move task')
    load()
  }
}

// Non-Task doctypes have no dependency-blocker concept — Frappe's own
// doc.save() validate() hooks are the real validation (update_widget_source_field).
async function dropGeneric(row, newKey) {
  const fromCol = columns.value.find(c => c.rows.some(r => r.name === row.name))
  if (fromCol?.key === newKey) return
  moveRowBetweenColumns(row.name, fromCol?.key, newKey, () => row)
  try {
    await updateWidgetSourceField(props.widget.doctype, row.name, props.widget.group_by, newKey === '__none__' ? null : newKey)
  } catch (e) {
    toast.error(e.message || 'Failed to update record')
    load()
  }
}

// Dropping a card writes the grouped field. For BP Task that write is
// update_task_status, which enforces the real dependency-blocking rules —
// there is deliberately no generic "set any BP Task field" write path
// (update_widget_source_field refuses BP Task for exactly that reason), so
// a Task board grouped by anything else is read-only rather than silently
// writing around that validation.
const canDrag = computed(() =>
  !isTask.value || (props.widget.group_by || 'status') === 'status'
)

const cfgKey = () => [props.widget.doctype, props.widget.group_by, JSON.stringify(props.widget.filters || []), serialiseScope(effScope.value), props.refreshKey].join('|')
watch(cfgKey, load)
onMounted(load)
</script>

<style scoped>
.kw { height: 100%; display: flex; flex-direction: column; min-height: 0; }
.kw-readonly-note {
  flex-shrink: 0; font-size: 11px; color: var(--muted);
  padding: 4px 8px 6px;
}
.kw-cols { flex: 1; min-height: 0; display: flex; gap: 12px; align-items: stretch; overflow-x: auto; overflow-y: hidden; padding-bottom: 4px; }
.kw-col-body { flex: 1; min-height: 0; overflow-y: auto; }
.kw-col-empty { text-align: center; font-size: 12px; color: var(--muted); padding: 24px 0; }
.kw-loading { flex: 1; display: flex; gap: 12px; }
.kw-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; }
</style>
