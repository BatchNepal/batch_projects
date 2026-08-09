<template>
  <Modal :open="open" size="2xl" @update:open="onClose">
    <ModalHeader>
      <template #title>Customize row</template>
    </ModalHeader>

    <ModalBody class="rd-body">
      <!-- ── Live preview ───────────────────────────────────────────────
           The REAL WidgetRow component, fed through the SAME resolver the
           column itself uses at runtime, inside a box pinned to a realistic
           column width — so overflow, truncation and the "+N" badge behave
           here exactly as they will on the dashboard, instead of looking
           roomier just because the dialog is wider than a column. -->
      <div class="rd-preview">
        <div class="rd-preview-head">
          <p class="rd-section-label !mb-0">Live preview</p>
          <div v-if="sampleRows.length > 1" class="rd-sample-nav">
            <button type="button" class="rd-nav-btn" title="Previous record" @click="cycleSample(-1)">
              <Icon :icon="ChevronLeft" :size="13" />
            </button>
            <span class="rd-sample-idx">{{ sampleIdx + 1 }} / {{ sampleRows.length }}</span>
            <button type="button" class="rd-nav-btn" title="Next record" @click="cycleSample(1)">
              <Icon :icon="ChevronRight" :size="13" />
            </button>
          </div>
        </div>
        <div class="rd-preview-stage">
          <div class="rd-preview-col">
            <WidgetRow
              v-if="previewProps"
              :line1="previewProps.line1" :line2="previewProps.line2"
              :date="previewProps.date" :solo="previewProps.solo"
            />
            <p v-else class="rd-preview-empty">Add a field below to design your row.</p>
          </div>
        </div>
        <p class="rd-preview-note">
          {{ activeSample ? 'Showing a real record from this widget.' : 'No records loaded — showing representative sample values.' }}
        </p>
      </div>

      <!-- ── Solo slot ──────────────────────────────────────────────────
           One block, rendered large and vertically centred on either edge of
           the row. Anything can go here — a thumbnail, an icon, an avatar, a
           project tile, the assignee stack, even a short text field. -->
      <div>
        <div class="rd-zone-head">
          <div>
            <p class="rd-section-label !mb-0">Solo</p>
            <p class="rd-section-hint">One big visual, {{ soloPosition === 'right' ? 'far right' : 'far left' }} — spans the row height</p>
          </div>
          <div class="flex items-center gap-1.5">
            <div v-if="draft.solo.length" class="rd-pos-toggle">
              <button type="button" :class="{ 'rd-pos-active': soloPosition !== 'right' }" title="Place on the left"
                @click="setSoloPosition('left')">
                <Icon :icon="PanelLeft" :size="12" /> Left
              </button>
              <button type="button" :class="{ 'rd-pos-active': soloPosition === 'right' }" title="Place on the right"
                @click="setSoloPosition('right')">
                Right <Icon :icon="PanelRight" :size="12" />
              </button>
            </div>
            <Combobox v-if="!draft.solo.length" :model-value="null" placeholder="+ Add…" size="sm" class="w-44"
              :options="fieldOptions()" @update:model-value="(v) => addBlock('solo', v)" />
          </div>
        </div>
        <draggable v-model="draft.solo" item-key="id" :group="{ name: 'rd-blocks', put: () => draft.solo.length === 0 }"
          handle=".rd-drag-handle" :animation="150" ghost-class="rd-ghost" class="rd-zone-list rd-zone-solo">
          <template #item="{ element }">
            <RowDesignerBlock
              :element="element" line="solo" :label="blockLabel(element)" :icon="blockIcon(element)"
              :is-field="element.kind === 'field'" :open="openSlotFor(element.id)"
              :choices="valueChoices[element.id] || []" :loading="!!loadingChoices[element.id]"
              @toggle-solo="toggleSolo('solo', element.id)" @toggle-config="(s) => toggleConfig(element, s)"
              @remove="removeBlock('solo', element.id)"
            />
          </template>
        </draggable>
        <p v-if="!draft.solo.length" class="rd-zone-empty rd-zone-empty-drop">Empty — add above, or drag a field here.</p>
      </div>

      <!-- ── Row 1 / Row 2 ──────────────────────────────────────────────
           An ordered list each; drag anything anywhere, across rows and in
           and out of Solo, as many as you want. Which row a field lands on
           decides its weight; Row 2 collapses into "+N" once it overflows. -->
      <div v-for="line in ['line1', 'line2']" :key="line">
        <div class="rd-zone-head">
          <div>
            <p class="rd-section-label !mb-0">{{ line === 'line1' ? 'Row 1' : 'Row 2' }}</p>
            <p class="rd-section-hint">
              {{ line === 'line1' ? 'Headline — always shown in full' : 'Detail — smaller, overflows into “+N”' }}
            </p>
          </div>
          <Combobox :model-value="null" placeholder="+ Add field…" size="sm" class="w-44"
            :options="fieldOptions()" @update:model-value="(v) => addBlock(line, v)" />
        </div>
        <draggable v-model="draft[line]" item-key="id" group="rd-blocks" handle=".rd-drag-handle"
          :animation="150" ghost-class="rd-ghost" class="rd-zone-list">
          <template #item="{ element }">
            <RowDesignerBlock
              :element="element" :line="line" :label="blockLabel(element)" :icon="blockIcon(element)"
              :is-field="element.kind === 'field'" :open="openSlotFor(element.id)"
              :choices="valueChoices[element.id] || []" :loading="!!loadingChoices[element.id]"
              @toggle-solo="toggleSolo(line, element.id)" @move="moveBlock(line, element.id)"
              @toggle-config="(s) => toggleConfig(element, s)" @remove="removeBlock(line, element.id)"
            />
          </template>
        </draggable>
        <p v-if="!draft[line].length" class="rd-zone-empty">Empty — add a field above, or drag one here.</p>
      </div>
    </ModalBody>

    <ModalFooter>
      <button type="button" class="rd-reset" @click="resetAll">Clear all</button>
      <Button variant="light" size="sm" @click="onClose">Cancel</Button>
      <Button color="accent" size="sm" @click="onSave">Save</Button>
    </ModalFooter>
  </Modal>
</template>

<script setup>
// Doctype-aware row designer, reachable from any Column widget's 3-dot menu.
// Which FIELDS go where is entirely free — drag anything between Solo, Row 1
// and Row 2, no cap. Which SLOT a field lands in decides how it renders:
// Solo = one big row-height visual on either edge, Row 1 = full headline,
// Row 2 = smaller detail that collapses into "+N". See rowTemplate.js's
// header for the full contract this designer and ColumnWidget.vue's real
// rendering both honour — the preview below runs through that same resolver,
// so it cannot drift from production output.
import { ref, reactive, computed, watch } from 'vue'
import draggable from 'vuedraggable'
import { Tag, User, Users, Image, PanelLeft, PanelRight, ChevronLeft, ChevronRight, Type } from 'lucide-vue-next'
import Modal from '@/ui/Modal.vue'
import ModalHeader from '@/ui/ModalHeader.vue'
import ModalBody from '@/ui/ModalBody.vue'
import ModalFooter from '@/ui/ModalFooter.vue'
import Button from '@/ui/Button.vue'
import Icon from '@/ui/Icon.vue'
import Combobox from '@/ui/Combobox.vue'
import WidgetRow from './WidgetRow.vue'
import RowDesignerBlock from './RowDesignerBlock.vue'
import { getFieldValueChoices, getWidgetSourceFields } from '@/utils/api'
import { resolveRowProps, fieldMetaLookup } from '@/utils/rowTemplate'

const props = defineProps({
  open:       { type: Boolean, default: false },
  doctype:    { type: String, required: true }, // effective doctype (BP Task, Lead, ...)
  isTask:     { type: Boolean, default: false },
  project:    { type: String, default: null },  // widget's single scoped project, if any
  template:   { type: Object, default: null },  // current widget.row_template, or null
  sampleRows: { type: Array, default: () => [] }, // real loaded rows, for the live preview
})
const emit = defineEmits(['update:open', 'save'])

// One field source for the whole column-widget surface: the designer's
// picker, the filter builder and group-by all read get_widget_source_fields,
// so what you can put in a row is exactly what you can filter and group by
// — including synthetics like Assignee and Project key that have no docfield.
const fields = ref([])
watch(() => props.doctype, async (dt) => {
  fields.value = dt ? await getWidgetSourceFields(dt).catch(() => []) : []
}, { immediate: true })
const fieldMeta = computed(() => fieldMetaLookup(fields.value))

let seq = 0
const nextId = () => `b${Date.now()}_${seq++}`

// solo is modelled as a 0-or-1 array purely so vuedraggable can treat it as
// just another drop zone (its `put` guard enforces the max); it serialises
// back to a single object/null on save.
const draft = reactive({ line1: [], line2: [], solo: [] })
const configuring = ref(null)
const soloPosition = ref('left')
// Declared before the immediate watcher below that resets it — an immediate
// watcher runs during setup(), so referencing a `const` defined further down
// the file throws a temporal-dead-zone error and takes the whole page with it.
const sampleIdx = ref(0)

function seedFromTemplate(t) {
  draft.line1 = (t?.line1 || []).map((b) => ({ ...b, id: b.id || nextId() }))
  draft.line2 = (t?.line2 || []).map((b) => ({ ...b, id: b.id || nextId() }))
  draft.solo = t?.solo ? [{ ...t.solo, id: t.solo.id || nextId() }] : []
  soloPosition.value = t?.solo?.position === 'right' ? 'right' : 'left'
}
watch(() => props.open, (v) => {
  if (!v) return
  seedFromTemplate(props.template)
  configuring.value = null
  sampleIdx.value = 0
}, { immediate: true })

// ── available fields ─────────────────────────────────────────────────────
// A field can appear twice — once as text, once as an avatar (Link/Image
// types only) — since those are materially different renderings of the same
// data, not duplicates.
function blockKey(b) {
  return b.kind === 'avatar' ? `avatar:${b.source}:${b.field || ''}` : `field:${b.field}`
}
const usedKeys = computed(() =>
  new Set([...draft.line1, ...draft.line2, ...draft.solo].map(blockKey))
)
const AVATAR_FIELDTYPES = new Set(['Link', 'Attach Image', 'Image', 'Attach'])

function fieldOptions() {
  const opts = []
  if (!usedKeys.value.has('avatar:identity:')) opts.push({ value: '__avatar:identity', label: 'Visual — Record identity' })
  if (props.isTask) {
    if (!usedKeys.value.has('avatar:project:')) opts.push({ value: '__avatar:project', label: 'Visual — Project' })
    if (!usedKeys.value.has('avatar:assignees:')) opts.push({ value: '__avatar:assignees', label: 'Visual — Assignees' })
  }
  for (const f of fields.value) {
    if (AVATAR_FIELDTYPES.has(f.fieldtype) && !usedKeys.value.has(`avatar:field:${f.fieldname}`)) {
      opts.push({ value: `__avatar:field:${f.fieldname}`, label: `Visual — ${f.label}` })
    }
    if (!usedKeys.value.has(`field:${f.fieldname}`)) {
      opts.push({ value: f.fieldname, label: f.label })
    }
  }
  return opts
}
function makeBlock(value) {
  if (value.startsWith('__avatar:')) {
    const rest = value.slice('__avatar:'.length)
    if (rest.startsWith('field:')) return { id: nextId(), kind: 'avatar', source: 'field', field: rest.slice(6) }
    return { id: nextId(), kind: 'avatar', source: rest }
  }
  return { id: nextId(), kind: 'field', field: value, color: null }
}
function addBlock(line, value) {
  if (!value) return
  if (line === 'solo' && draft.solo.length) return
  draft[line].push(makeBlock(value))
}
function removeBlock(line, id) {
  draft[line] = draft[line].filter((b) => b.id !== id)
  if (configuring.value?.id === id) configuring.value = null
}
function moveBlock(line, id) {
  const other = line === 'line1' ? 'line2' : 'line1'
  const idx = draft[line].findIndex((b) => b.id === id)
  if (idx === -1) return
  const [blk] = draft[line].splice(idx, 1)
  draft[other].push(blk)
}
// Promote to / demote from the solo slot. Promoting while solo is occupied
// swaps them, so the slot is never silently "full and ignoring you".
function toggleSolo(line, id) {
  if (line === 'solo') {
    const [blk] = draft.solo.splice(0, 1)
    if (blk) draft.line1.push(blk)
    return
  }
  const idx = draft[line].findIndex((b) => b.id === id)
  if (idx === -1) return
  const [blk] = draft[line].splice(idx, 1)
  const displaced = draft.solo.splice(0, 1)[0]
  draft.solo.push(blk)
  if (displaced) draft[line].splice(idx, 0, displaced)
}
function setSoloPosition(p) { soloPosition.value = p }

function blockIcon(b) {
  if (b.kind === 'avatar') {
    if (b.source === 'project') return Tag
    if (b.source === 'assignees') return Users
    if (b.source === 'field' && AVATAR_FIELDTYPES.has(fieldMeta.value(b.field)?.fieldtype)) return Image
    return User
  }
  return Type
}
function blockLabel(b) {
  if (b.kind === 'avatar') {
    if (b.source === 'identity') return 'Visual — Record identity'
    if (b.source === 'project') return 'Visual — Project'
    if (b.source === 'assignees') return 'Visual — Assignees'
    return `Visual — ${fieldMeta.value(b.field)?.label || b.field}`
  }
  return fieldMeta.value(b.field)?.label || b.field
}

// ── colour config (grounded values, never a type-and-hope box) ───────────
const valueChoices = ref({})   // block id -> string[]
const loadingChoices = ref({})
async function loadChoices(el) {
  if (valueChoices.value[el.id] !== undefined) return
  loadingChoices.value = { ...loadingChoices.value, [el.id]: true }
  try {
    const choices = await getFieldValueChoices(props.doctype, el.field, props.project)
    valueChoices.value = { ...valueChoices.value, [el.id]: choices || [] }
  } catch {
    valueChoices.value = { ...valueChoices.value, [el.id]: [] }
  } finally {
    loadingChoices.value = { ...loadingChoices.value, [el.id]: false }
  }
}
// `configuring` holds {id, slot} — a block has two independent colour slots
// (background and text), so "which block" alone can't say which editor is
// open. Clicking the already-open slot closes it; clicking the other swaps
// the panel over without closing.
function openSlotFor(id) {
  return configuring.value && configuring.value.id === id ? configuring.value.slot : null
}
function toggleConfig(b, slot = 'color') {
  if (configuring.value && configuring.value.id === b.id && configuring.value.slot === slot) {
    configuring.value = null
    return
  }
  configuring.value = { id: b.id, slot }
  loadChoices(b)
}

// ── live preview ─────────────────────────────────────────────────────────
const activeSample = computed(() => props.sampleRows[sampleIdx.value] || null)
function cycleSample(d) {
  const n = props.sampleRows.length
  if (!n) return
  sampleIdx.value = (sampleIdx.value + d + n) % n
}

// With no real records loaded, synthesise values that LOOK like real data per
// fieldtype (a date that formats, a number that reads as a number) rather
// than echoing field labels back — label-as-value made dates render as
// "Invalid Date" and made every chip the same width, so the preview taught
// you nothing about the real layout.
function sampleValueFor(fieldname) {
  const meta = fieldMeta.value(fieldname)
  const ft = meta?.fieldtype
  if (ft === 'Date' || ft === 'Datetime') {
    const d = new Date(); d.setDate(d.getDate() + 3)
    return d.toISOString().slice(0, 10)
  }
  if (ft === 'Check') return 1
  if (ft === 'Int' || ft === 'Float' || ft === 'Currency' || ft === 'Percent') return 42
  const choices = Object.values(valueChoices.value).find((c) => c?.length)
  if (ft === 'Select' && meta?.options?.length) return meta.options[0]
  if (fieldname === 'status' && choices?.length) return choices[0]
  return meta?.label || fieldname
}
const previewRecord = computed(() => {
  if (activeSample.value) return activeSample.value
  const rec = { title: 'Sample record title', name: 'SAMPLE-001' }
  for (const b of [...draft.line1, ...draft.line2, ...draft.solo]) {
    if (b.kind === 'field') rec[b.field] = sampleValueFor(b.field)
  }
  return rec
})
const previewProps = computed(() => resolveRowProps(
  {
    line1: draft.line1,
    line2: draft.line2,
    solo: draft.solo[0] ? { ...draft.solo[0], position: soloPosition.value } : null,
  },
  previewRecord.value,
  {
    projectAvatar: () => ({
      kind: 'avatar-project',
      theme: activeSample.value?.project_theme || 'koalaBlue',
      seed: activeSample.value?.project_key || 'SAMPLE',
      label: activeSample.value?.project_name || 'Sample project',
    }),
    assignees: () => (activeSample.value?.assignees?.length
      ? activeSample.value.assignees
      : [{ full_name: 'Alex Kim' }, { full_name: 'Sam Rai' }]),
    fieldMeta: fieldMeta.value,
    fallbackTitle: (r) => r?.title || r?.name || 'Sample record title',
  },
))

function resetAll() {
  draft.line1 = []; draft.line2 = []; draft.solo = []
  configuring.value = null
}
function onClose() { emit('update:open', false) }
function onSave() {
  emit('save', {
    line1: draft.line1.map(stripId),
    line2: draft.line2.map(stripId),
    solo: draft.solo[0] ? { ...stripId(draft.solo[0]), position: soloPosition.value } : null,
  })
  onClose()
}
function stripId({ id, ...rest }) { return rest }

</script>

<style scoped>
.rd-body { display: flex; flex-direction: column; gap: 16px; }

.rd-section-label { font-size: 12px; font-weight: 600; color: var(--foreground); margin-bottom: 6px; }
.rd-section-hint { font-size: 11px; color: var(--muted); margin-top: 1px; }

/* ── preview ─────────────────────────────────────────────────────────── */
.rd-preview { border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 10px 12px 8px; background: var(--surface-secondary); }
.rd-preview-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.rd-sample-nav { display: flex; align-items: center; gap: 2px; }
.rd-nav-btn {
  width: 22px; height: 22px; display: grid; place-items: center; border-radius: var(--radius-sm);
  color: var(--muted); background: none; border: none; cursor: pointer;
}
.rd-nav-btn:hover { background: var(--default); color: var(--foreground); }
.rd-sample-idx { font-size: 11px; font-weight: 600; color: var(--muted); font-variant-numeric: tabular-nums; min-width: 40px; text-align: center; }
.rd-preview-stage { display: flex; justify-content: center; }
/* Pinned to a realistic single-column width so truncation and the "+N"
   badge behave here exactly as they do on the real dashboard. */
.rd-preview-col { width: 330px; max-width: 100%; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); overflow: hidden; }
.rd-preview-empty { padding: 22px 12px; text-align: center; font-size: 12px; color: var(--muted); }
.rd-preview-note { font-size: 10.5px; color: var(--muted); margin-top: 7px; text-align: center; }

/* ── zones ───────────────────────────────────────────────────────────── */
.rd-zone-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 7px; }
.rd-zone-list { display: flex; flex-direction: column; gap: 5px; min-height: 4px; }
.rd-zone-solo { min-height: 0; }
.rd-zone-empty { font-size: 11.5px; color: var(--muted); font-style: italic; padding: 7px 2px; }
.rd-zone-empty-drop {
  border: 1px dashed var(--border); border-radius: var(--radius-md);
  padding: 12px; text-align: center; font-style: normal;
}

.rd-pos-toggle { display: flex; align-items: center; border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; flex-shrink: 0; }
.rd-pos-toggle button {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; font-weight: 600; padding: 5px 8px;
  color: var(--muted); background: var(--surface); border: none; cursor: pointer;
}
.rd-pos-toggle button:hover { background: var(--surface-secondary); color: var(--foreground); }
.rd-pos-toggle button.rd-pos-active { background: var(--accent-soft); color: var(--accent-soft-foreground); }

/* Applied by vuedraggable to the dragged RowDesignerBlock's root element —
   a child component's root does inherit the parent's scope id, so this
   scoped rule still matches. */
.rd-ghost { opacity: .4; }

.rd-reset { margin-right: auto; font-size: 12px; font-weight: 500; color: var(--muted); background: none; border: none; cursor: pointer; }
.rd-reset:hover { color: var(--danger); }
</style>
