<template>
  <div class="cw">
    <!-- column header: no icon — "Title (count)", description only if set -->
    <div class="cw-head">
      <div class="min-w-0 flex-1">
        <p class="cw-title">{{ widget.title || defaultTitle }} <span class="cw-count">({{ total }})</span></p>
        <p v-if="widget.description" class="cw-sub">{{ widget.description }}</p>
      </div>
    </div>

    <!-- unconfigured: never silently defaults to a doctype — prompts instead -->
    <div v-if="unconfigured" class="cw-empty">
      <span class="cw-configure-icon"><Columns3 :size="18" /></span>
      <Button size="sm" variant="bordered" @click="$emit('configure')">Configure</Button>
    </div>

    <!-- loading -->
    <div v-else-if="loading && !rows.length" class="cw-body">
      <Skeleton class="h-4 w-16 rounded-md mb-2" />
      <Skeleton class="h-10 w-full rounded-lg mb-1" />
      <Skeleton class="h-10 w-full rounded-lg" />
    </div>

    <!-- no access — a dashboard can be shared with someone who lacks ERP
         permission on one of its sources (System Manager has no Sales Order
         read right in stock ERPNext, for instance). Say so plainly instead
         of rendering a silently-empty column that reads as "no data". -->
    <div v-else-if="noAccess" class="cw-empty">
      <span class="cw-configure-icon"><Lock :size="16" /></span>
      <span class="cw-noaccess-title">No access</span>
      <span class="cw-noaccess-sub">You don't have permission to read {{ sourceLabel }}.</span>
    </div>

    <!-- empty -->
    <div v-else-if="!rows.length" class="cw-empty">
      <Inbox :size="16" class="text-[--muted] opacity-60" />
      <span class="text-[11.5px] text-[--muted]">Nothing here</span>
    </div>

    <!-- Wrike-style time rail: sticky Overdue/Today/This week/Later
         sub-headers. Only when the source has a real DEADLINE field to
         bucket on (the backend returns no buckets for historical dates like
         posting_date — filing every past record under "Overdue" is noise).
         `bucketed: false` on the widget forces the plain list back. -->
    <div v-else class="cw-body">
      <template v-if="showBuckets">
        <div v-for="b in buckets" :key="b.key" class="cw-group">
          <div class="cw-group-head" :class="b.key === 'overdue' ? 'is-overdue' : ''">
            <span class="cw-dot" :class="`dot-${b.key}`" />
            <span class="cw-group-label">{{ b.label }}</span>
            <span class="cw-group-count">{{ b.tasks.length }}</span>
          </div>
          <WidgetRow
            v-for="r in b.tasks" :key="r.name"
            :title="r.title"
            :chips="isTask ? taskChips(r) : genericChips(r)"
            :avatars="rowAvatars(r)"
            :date="isTask ? r.due_date : r.date"
            @click="isTask ? openTask(r.name) : openRecord(r)"
          />
        </div>
      </template>
      <template v-else>
        <WidgetRow
          v-for="r in rows" :key="r.name"
          :title="r.title"
          :chips="isTask ? taskChips(r) : genericChips(r)"
          :avatars="rowAvatars(r)"
          :date="isTask ? r.due_date : r.date"
          @click="isTask ? openTask(r.name) : openRecord(r)"
        />
      </template>
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
import { Inbox, Columns3, Lock } from 'lucide-vue-next'
import { Skeleton, Button } from '@/ui'
import { getColumnWidgetData, getDoctypeColumnData } from '@/utils/api'
import { useProjectStore } from '@/stores/project'
import WidgetRow from './WidgetRow.vue'
import DocQuickview from './DocQuickview.vue'

const props = defineProps({
  widget: { type: Object, required: true }, // { title, description, scope, filterBy, filterValue, statusFilter, doctype, filters, label_fields, date_field, color }
  scopeLabel: { type: Function, required: true },
  reportScope: { type: [String, Array], default: 'all' },
  refreshKey: { type: Number, default: 0 },
})
defineEmits(['configure'])

const store = useProjectStore()

// doctype === 'BP Task' is explicit, never assumed. The ONLY other case
// treated as Task is a widget saved before `doctype` existed at all (has
// filterBy but no doctype) — real back-compat for existing data, not a
// default opinion applied to a fresh widget. A brand-new widget with
// neither is `unconfigured`, not silently "Task".
const isTask = computed(() => props.widget.doctype === 'BP Task' || (!props.widget.doctype && !!props.widget.filterBy))
const unconfigured = computed(() => !props.widget.doctype && !props.widget.filterBy)

const effScope = computed(() => (props.widget.scope && props.widget.scope !== 'inherit' ? props.widget.scope : props.reportScope))
function serialiseScope(s) {
  if (Array.isArray(s)) return s.length === 0 ? 'all' : s.length === 1 ? s[0] : JSON.stringify(s)
  return s || 'all'
}

const defaultTitle = computed(() => props.widget.filterValue || props.widget.doctype || 'Column')

const rows = ref([])
const buckets = ref([])
const total = ref(0)
const loading = ref(false)
const noAccess = ref(false)

const sourceLabel = computed(() => props.widget.doctype || 'this source')

// Buckets render unless the widget explicitly opts out. `rows` is always
// populated too, so toggling `bucketed` never needs a refetch.
const showBuckets = computed(() => props.widget.bucketed !== false && buckets.value.length > 0)

async function loadTask() {
  const res = await getColumnWidgetData({
    scope: serialiseScope(effScope.value),
    filter_by: props.widget.filterBy || 'assignee',
    filter_value: props.widget.filterValue || null,
    status_filter: props.widget.statusFilter || 'open',
    // Filter-builder rows stack on top of the quick picker (AND).
    filters: props.widget.filters || [],
  })
  // Buckets arrive due-date ordered (overdue → today → this week → later →
  // no date), so the flat fallback is just a concatenation of them.
  buckets.value = res?.buckets || []
  rows.value = buckets.value.flatMap(b => b.tasks)
  total.value = res?.total || 0
}

async function loadGeneric() {
  const res = await getDoctypeColumnData({
    doctype: props.widget.doctype,
    filters: props.widget.filters || [],
    label_fields: props.widget.label_fields || [],
    // undefined (not null) lets the backend fall back to this doctype's own
    // default deadline field; an explicit '' is the user's "no date" choice.
    date_field: props.widget.date_field === undefined ? undefined : props.widget.date_field,
    limit: 200,
  })
  rows.value = res?.rows || []
  buckets.value = res?.buckets || []
  total.value = res?.total || 0
}

function reset() { rows.value = []; buckets.value = []; total.value = 0 }

async function load() {
  if (unconfigured.value) { reset(); noAccess.value = false; return }
  loading.value = true
  noAccess.value = false
  try {
    if (isTask.value) await loadTask()
    else await loadGeneric()
  } catch (e) {
    reset()
    // The backend's PermissionError message arrives as a plain Error (see
    // utils/api.js's frappe.exceptions.* regex) — there's no status code left
    // to switch on by the time it reaches here.
    noAccess.value = /permission|not permitted|forbidden/i.test(e?.message || '')
  }
  finally { loading.value = false }
}

// Read-mostly glance column — click through to the real task (TaskDetail is
// mounted globally in App.vue) or the generic quickview drawer for anything
// else. No drag-and-drop: that lives on the real per-project Board.vue (and
// the 'kanban' widget, which does support it — see KanbanWidget.vue).
function openTask(name) {
  store.openTaskDetail(name)
}
const quickview = ref({ open: false, name: '' })
function openRecord(r) {
  quickview.value = { open: true, name: r.name }
}

function rowAvatars(r) {
  if (isTask.value) return r.assignees || []
  return r.owner ? [r.owner] : []
}

function statusColor(v) {
  const s = String(v || '').toLowerCase()
  if (/done|complete|closed|resolved|active|won/.test(s)) return 'success'
  if (/progress|review|testing|replied|open|contacted|negotiation/.test(s)) return 'primary'
  if (/block|hold|lost|inactive|junk/.test(s)) return 'danger'
  return 'default'
}
// Status shown again only when the column ISN'T already a single-status
// glance (filterBy === 'status' means every row already shares one status —
// showing it a second time is redundant, same posture the old card version
// used).
function taskChips(t) {
  const chips = []
  if (props.widget.filterBy !== 'status' && t.status) chips.push({ text: t.status, color: statusColor(t.status) })
  if (t.task_type) chips.push({ text: t.task_type, color: 'default' })
  return chips
}
function genericChips(r) {
  const chips = []
  if (r.status) chips.push({ text: r.status, color: statusColor(r.status) })
  for (const l of (r.labels || [])) chips.push({ text: String(l.value), color: 'default', title: l.label })
  return chips
}

const cfgKey = () => [
  props.widget.doctype, serialiseScope(effScope.value), props.widget.filterBy, props.widget.filterValue,
  props.widget.statusFilter, JSON.stringify(props.widget.filters || []),
  JSON.stringify(props.widget.label_fields || []), props.widget.date_field, props.refreshKey,
].join('|')
watch(cfgKey, load)
onMounted(load)
defineExpose({ load })
</script>

<style scoped>
.cw { height: 100%; display: flex; flex-direction: column; min-height: 0; }

.cw-head { display: flex; align-items: center; gap: 8px; flex-shrink: 0; padding-bottom: 10px; border-bottom: 1px solid var(--border); margin-bottom: 4px; }
.cw-title { font-size: 13.5px; font-weight: 600; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cw-count { font-weight: 500; color: var(--muted); }
.cw-sub { font-size: 11.5px; color: var(--muted); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.cw-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; }
.cw-configure-icon { width: 32px; height: 32px; border-radius: 8px; display: grid; place-items: center; background: var(--surface-secondary); color: var(--muted); }
.cw-noaccess-title { font-size: 12.5px; font-weight: 500; color: var(--foreground); }
.cw-noaccess-sub { font-size: 11.5px; color: var(--muted); text-align: center; max-width: 200px; line-height: 1.45; margin-top: -4px; }

.cw-body { flex: 1; min-height: 0; overflow-y: auto; padding-top: 2px; }

/* ── time rail ──────────────────────────────────────────────────────────
   Sticky sub-header per date bucket. Chrome stays neutral (composition law
   §1): the only colour is the 6px status dot, which is data — "this bucket
   is late" — not decoration. No border under it; the surface shift plus the
   whitespace does the separating (§3). */
.cw-group + .cw-group { margin-top: 10px; }

.cw-group-head {
  position: sticky; top: 0; z-index: 1;
  display: flex; align-items: center; gap: 6px;
  padding: 5px 2px 5px 0;
  background: var(--surface);
}
.cw-group-label {
  font-size: 11px; font-weight: 500; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.cw-group-head.is-overdue .cw-group-label { color: var(--danger-soft-foreground); }
.cw-group-count {
  margin-left: auto; flex-shrink: 0;
  font-size: 10.5px; font-weight: 500; color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.cw-dot { width: 6px; height: 6px; border-radius: 999px; flex-shrink: 0; }
.dot-overdue   { background: var(--danger); }
.dot-today     { background: var(--warning); }
.dot-this_week { background: var(--accent); }
.dot-later     { background: var(--muted-tertiary); opacity: 0.55; }
.dot-no_date   { background: var(--border-secondary, var(--border)); }
</style>
