<template>
  <div ref="cwRoot" class="cw hide-scrollbar">
    <!-- column header: no icon — "Title (count)", description only if set -->
    <div class="cw-head">
      
      <div class="min-w-0 flex-1">
         <!-- drag handle -->
            <div class="drag-handle z-10  cursor-grab active:cursor-grabbing text-[--muted]"
              >
              <Icon :icon="GripVertical" :size="14" />
            </div>
        <p class="cw-title">{{ widget.title || defaultTitle }} <span class="cw-count">({{ total }})</span></p>
        <p v-if="widget.description" class="cw-sub">{{ widget.description }}</p>
      </div>
    </div>

    <!-- unconfigured: never silently defaults to a doctype — prompts instead -->
    <div v-if="unconfigured" class="cw-empty">
      <span class="cw-configure-icon"><Columns3 :size="18" /></span>
      <Button size="sm"  variant="bordered" @click="$emit('configure')">Configure</Button>
    </div>

    <!-- loading — shaped to match the REAL bucket-header + two-line
         WidgetRow structure below (marker + title / chip + date), not a
         couple of generic bars. Row count (5) is a reasonable average, not
         an attempt to predict the real count — the goal is "swaps to
         something the same general shape", not pixel-perfect, since the
         box itself is grid-sized and never moves regardless. -->
    <div v-else-if="loading && !rows.length" class="cw-body">
      <div class="cw-skel-group-head px-2 py-2">
        <Skeleton class="h-3 w-20 rounded-md" />
        <Skeleton class="h-3 w-5 rounded-md ml-auto" />
      </div>
      <div v-for="i in 5" :key="i" class="cw-skel-row">
        <div class="cw-skel-line1">
          <Skeleton class="size-4 rounded-[4px] shrink-0" />
          <Skeleton class="h-3.5 flex-1 rounded-md" />
        </div>
        <div class="cw-skel-line2">
          <Skeleton class="h-2.5 w-16 rounded-md" />
          <Skeleton class="h-2.5 w-10 rounded-md ml-auto" />
        </div>
      </div>
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
      <span class="text-sm text-[--muted]">Nothing here</span>
    </div>

    <!-- Grouped rows with sticky sub-headers. What the groups ARE depends on
         the widget's `group_by`: the Overdue/Today/This week time rail
         (default), one group per value of any field, or a single unlabelled
         group when grouping is off. The unlabelled case renders no header at
         all — an empty grey bar reads as a bug, not as "no grouping". -->
    <div v-else class="cw-body hide-scrollbar">
      <template v-if="showBuckets">
        <div v-for="b in buckets" :key="b.key" class="cw-group">
          <button
            v-if="b.label"
            type="button" class="cw-group-head shadow-sm px-2 py-2 font-semibold"
            :class="b.key === 'overdue' ? 'is-overdue' : ''"
            @click="toggleBucket(b.key)"
          >
            <ChevronDown :size="12" class="cw-group-chevron" :class="{ 'is-collapsed': collapsedBuckets.has(b.key) }" />
            <span class="cw-group-label text-foreground font-medium">{{ b.label }}</span>
            <span class="cw-group-count">{{ b.tasks.length }}</span>
          </button>
          <template v-if="!collapsedBuckets.has(b.key)">
            <WidgetRow
              v-for="r in b.tasks" :key="r.name"
              v-bind="rowProps(r)"
              @click="isTask ? openTask(r.name) : openRecord(r)"
            />
          </template>
        </div>
      </template>
      <template v-else>
        <WidgetRow
          v-for="r in rows" :key="r.name"
          v-bind="rowProps(r)"
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
import { ref, computed, watch, onMounted, onBeforeUnmount, provide } from 'vue'
import { Inbox, Columns3, Lock, ChevronDown } from 'lucide-vue-next'
import { Skeleton, Button } from '@/ui'
import { getColumnWidgetData, getDoctypeColumnData, getWidgetSourceFields } from '@/utils/api'
import { useProjectStore } from '@/stores/project'
import { withMinDuration } from '@/lib/utils'
import { resolveRowProps, fieldMetaLookup, templateFieldNames, COLUMN_WIDTH_KEY } from '@/utils/rowTemplate'
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

// ONE ResizeObserver for the whole column, provided down to every WidgetRow
// (see COLUMN_WIDTH_KEY in rowTemplate.js for the full rationale). Each row
// still measures its own line-2 container — that width genuinely differs per
// row, since a solo avatar or a date eats into it — but they no longer each
// own an observer to decide WHEN. A 500-row column was creating 500 of them;
// measured on a 3-widget/1500-row dashboard, that was 1508 observers firing a
// ~3.8s cascade of separately-scheduled re-renders on every mount and on
// every grid resize (edit mode, add-widget, any dialog that shifts layout).
const cwRoot = ref(null)
const columnWidth = ref(0)
provide(COLUMN_WIDTH_KEY, columnWidth)
let cwRO = null
onMounted(() => {
  if (!cwRoot.value) return
  cwRO = new ResizeObserver((entries) => {
    columnWidth.value = entries[0]?.contentRect?.width || cwRoot.value?.clientWidth || 0
  })
  cwRO.observe(cwRoot.value)
})
onBeforeUnmount(() => cwRO?.disconnect())

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

// Per-instance, session-only fold state (collapsible date-bucket
// headers) — keyed by bucket key, which is stable across reloads, so a
// column stays collapsed through its own data refreshes. Not persisted.
const collapsedBuckets = ref(new Set())
function toggleBucket(key) {
  const s = new Set(collapsedBuckets.value)
  if (s.has(key)) s.delete(key); else s.add(key)
  collapsedBuckets.value = s
}

async function loadTask() {
  const res = await getColumnWidgetData({
    scope: serialiseScope(effScope.value),
    // Only sent when a pre-unified-filters dashboard still carries one —
    // the endpoint's own default is now "no quick filter" (see its
    // docstring), so omitting these must not silently filter anything.
    filter_by: props.widget.filterBy || null,
    filter_value: props.widget.filterValue || null,
    status_filter: props.widget.statusFilter || 'open',
    filters: props.widget.filters || [],
    group_by: props.widget.group_by || 'date',
    extra_fields: templateFieldNames(props.widget.row_template, identityImageField.value),
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
    group_by: props.widget.group_by || 'date',
    extra_fields: templateFieldNames(props.widget.row_template, identityImageField.value),
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
    // Anti-flicker: a warm-cache response can resolve in under a frame,
    // which just flashes the skeleton instead of ever being seen — holds
    // the skeleton for a real minimum instead, never delays a slow load.
    await withMinDuration((isTask.value ? loadTask() : loadGeneric()))
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

// Same identity pair (theme + key-as-seed) Sidebar.vue's project list
// renders via ProjectAvatar — the real illustrated tile, not a generic
// line icon. Task-only: no other doctype this app renders has a "project".
function projectAvatarItem(r) {
  return { kind: 'avatar-project', theme: r.project_theme, seed: r.project_key, label: r.project_name }
}

function statusColor(v) {
  const s = String(v || '').toLowerCase()
  if (/done|complete|closed|resolved|active|won/.test(s)) return 'success'
  // Chip.vue only knows default|accent|success|warning|danger — 'primary'
  // isn't one of them and silently fell through to gray (STYLES.soft.default).
  if (/progress|review|testing|replied|open|contacted|negotiation/.test(s)) return 'accent'
  if (/block|hold|lost|inactive|junk/.test(s)) return 'danger'
  return 'default'
}

// Field metadata for whatever doctype this column effectively renders — the
// SAME source RowDesignerModal.vue's picker, the filter builder and group-by
// all use (get_widget_source_fields), so a saved row_template's
// Date/Datetime detection matches exactly what was offered when it was
// configured, and synthetic fields like project_key resolve here too.
const effDoctype = computed(() => (isTask.value ? 'BP Task' : props.widget.doctype))
const sourceFields = ref([])
watch(effDoctype, async (dt) => {
  sourceFields.value = dt ? await getWidgetSourceFields(dt).catch(() => []) : []
}, { immediate: true })
const fieldMeta = computed(() => fieldMetaLookup(sourceFields.value))
// The doctype's own photo field, if it has one — see get_widget_source_fields'
// is_identity_image tag / rowTemplate.js's 'identity' avatar branch.
const identityImageField = computed(() => sourceFields.value.find(f => f.is_identity_image)?.fieldname || null)

// Unconfigured (no row_template — the overwhelming majority until someone
// opts in) fallback. Task keeps its project tile — real, non-redundant
// data. Every OTHER doctype used to also get a hashed-initials avatar box
// here showing the record's own name right next to... the record's own
// name in the title — pure noise, removed. Its owner (a DIFFERENT
// identity, not redundant) still shows on line 2.
function fallbackLine1(r) {
  const items = []
  if (isTask.value) items.push(projectAvatarItem(r))
  items.push({ kind: 'text', text: r.title })
  return items
}
function fallbackLine2(r) {
  const items = []
  if (isTask.value) {
    // Status repeated only when the column isn't already a single-status
    // glance (filterBy === 'status' means every row already shares one).
    if (props.widget.filterBy !== 'status' && r.status) items.push({ kind: 'text', text: r.status, color: statusColor(r.status) })
    if (r.task_type) items.push({ kind: 'text', text: r.task_type, color: 'default' })
    items.push({ kind: 'avatars', people: r.assignees || [] })
  } else {
    if (r.status) items.push({ kind: 'text', text: r.status, color: statusColor(r.status) })
    for (const l of (r.labels || [])) items.push({ kind: 'text', text: String(l.value), color: 'default' })
    // r.owner is a resolved {user, full_name, user_image} object (see
    // get_doctype_column_data), not a bare username string — reuse the
    // 'avatars' renderer (already handles image-or-initials via Avatar.vue)
    // instead of a one-off shape.
    if (r.owner) items.push({ kind: 'avatars', people: [r.owner] })
  }
  return items
}

// A configured row_template takes over entirely; an unconfigured widget
// falls back to the layout above, so nothing existing regresses.
function rowProps(r) {
  if (props.widget.row_template) {
    const resolved = resolveRowProps(props.widget.row_template, r, {
      projectAvatar: () => projectAvatarItem(r),
      assignees: () => rowAvatars(r),
      fieldMeta: fieldMeta.value,
      fallbackTitle: () => r.title,
      identityImageField: identityImageField.value,
    })
    if (resolved) return resolved
  }
  return {
    line1: fallbackLine1(r),
    line2: fallbackLine2(r),
    date: isTask.value ? r.due_date : r.date,
  }
}

const cfgKey = () => [
  props.widget.doctype, serialiseScope(effScope.value), props.widget.filterBy, props.widget.filterValue,
  props.widget.statusFilter, JSON.stringify(props.widget.filters || []),
  JSON.stringify(props.widget.label_fields || []), props.widget.date_field,
  props.widget.group_by,
  // row_template drives the SELECT list (extra_fields), so a template change
  // genuinely needs a refetch, not just a re-render.
  JSON.stringify(templateFieldNames(props.widget.row_template, identityImageField.value)),
  props.refreshKey,
].join('|')
watch(cfgKey, load)
onMounted(load)
defineExpose({ load })
</script>

<style scoped>
.cw { height: 100%; display: flex; flex-direction: column; min-height: 0; }

.cw-head { display: flex; align-items: center; gap: 8px; flex-shrink: 0; padding: 10px; border-bottom: 1px solid var(--border); margin-bottom: 0px; }
.cw-title { font-size:var(--text-md); font-weight: 600; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cw-count { font-weight: 600; color: var(--muted); }
.cw-sub { font-size:var(--text-xs); color: var(--muted); margin-top: 0px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.cw-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; }
.cw-configure-icon { width: 32px; height: 32px; border-radius: 8px; display: grid; place-items: center; background: var(--surface-secondary); color: var(--muted); }
.cw-noaccess-title { font-size:var(--text-sm); font-weight: 600; color: var(--foreground); }
.cw-noaccess-sub { font-size:var(--text-xs); color: var(--muted); text-align: center; max-width: 200px; line-height: 1.45; margin-top: -4px; }

.cw-body { flex: 1; min-height: 0; overflow-y: auto; padding-top: 0px; }

.cw-skel-group-head { display: flex; align-items: center; background: #f2f2f2; }
.cw-skel-row { display: flex; flex-direction: column; gap: 6px; padding: 10px; border-bottom: 1px solid #e5e5e5; }
.cw-skel-line1 { display: flex; align-items: center; gap: 8px; }
.cw-skel-line2 { display: flex; align-items: center; gap: 6px; }

/* ── time rail ──────────────────────────────────────────────────────────
   Sticky sub-header per date bucket. Chrome stays neutral (composition law
   §1): the only colour is the 6px status dot, which is data — "this bucket
   is late" — not decoration. No border under it; the surface shift plus the
   whitespace does the separating (§3). */
.cw-group + .cw-group { margin-top: 10px; }

.cw-group-head {
  position: sticky; top: -1px; z-index: 1; width: 100%;
  display: flex; align-items: center; gap: 8px;
  background: #f2f2f2; border: none; cursor: pointer;
}
.cw-group-chevron { flex-shrink: 0; transition: transform .12s; color: var(--muted); }
.cw-group-chevron.is-collapsed { transform: rotate(-90deg); }
.cw-group-label {
  font-size:var(--text-xs); font-weight: 600;
  letter-spacing: 0.04em;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.cw-group-count {
  margin-left: auto; flex-shrink: 0;
  font-size:var(--text-xs); font-weight: 600; color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.cw-dot { width: 6px; height: 6px; border-radius: 999px; flex-shrink: 0; }
.dot-overdue   { background: var(--danger); }
.dot-today     { background: var(--warning); }
.dot-this_week { background: var(--accent); }
.dot-later     { background: var(--muted-tertiary); opacity: 0.55; }
.dot-no_date   { background: var(--border-secondary, var(--border)); }
</style>
