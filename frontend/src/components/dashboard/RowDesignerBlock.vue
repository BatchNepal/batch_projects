<template>
  <div>
    <div class="rd-block" :class="{ 'rd-block-open': !!open, 'rd-block-solo': line === 'solo' }">
      <span class="rd-drag-handle" title="Drag to reorder, or into another row">
        <Icon :icon="GripVertical" :size="12" />
      </span>
      <Icon :icon="icon" :size="13" class="text-muted shrink-0" />
      <span class="rd-block-label">{{ label }}</span>

      <button v-if="line === 'solo'" type="button" class="rd-block-action" title="Move back into Row 1"
        @click="$emit('toggle-solo')">
        <Icon :icon="Minimize2" :size="13" />
      </button>
      <button v-else type="button" class="rd-block-action" title="Make this the big solo visual"
        @click="$emit('toggle-solo')">
        <Icon :icon="Maximize2" :size="13" />
      </button>

      <button v-if="line !== 'solo'" type="button" class="rd-block-action"
        :title="line === 'line1' ? 'Move to Row 2' : 'Move to Row 1'" @click="$emit('move')">
        <Icon :icon="ArrowLeftRight" :size="13" />
      </button>

      <!-- Background, then text colour — two independent settings, so the
           swatch you see on each button is the thing that button controls.
           An unset background shows the hollow "transparent" swatch. -->
      <template v-if="isField">
        <button type="button" class="rd-block-action rd-swatch-btn"
          :class="{ 'rd-swatch-on': open === 'bg' }"
          :title="open === 'bg' ? 'Close background' : 'Background colour'"
          @click="$emit('toggle-config', 'bg')">
          <span class="rd-swatch" :class="{ 'rd-swatch-empty': !bgPreview }"
            :style="bgPreview ? { background: bgPreview } : {}" />
        </button>
        <button type="button" class="rd-block-action"
          :class="{ 'rd-swatch-on': open === 'color' }"
          :title="open === 'color' ? 'Close text colour' : 'Text colour'"
          @click="$emit('toggle-config', 'color')">
          <Icon :icon="Palette" :size="13" :style="colorPreview ? { color: colorPreview } : {}" />
        </button>
      </template>

      <button type="button" class="rd-block-action rd-block-remove" title="Remove" @click="$emit('remove')">
        <Icon :icon="X" :size="13" />
      </button>
    </div>

    <!-- One panel, driven by which button opened it. Per-value rows are only
         offered for genuinely enum-like fields (see get_field_value_choices'
         cardinality rule) — a free-text field gets a single colour instead of
         50 useless rows. -->
    <div v-if="open" class="rd-color-config">
      <p class="rd-color-head">{{ open === 'bg' ? 'Background colour' : 'Text colour' }}</p>

      <div v-if="loading" class="rd-color-row">
        <Spinner size="xs" />
        <span class="rd-color-row-label">Loading real values…</span>
      </div>

      <template v-else>
        <template v-if="choices.length">
          <div v-for="val in choices" :key="val" class="rd-color-row">
            <span class="rd-color-row-label">{{ val }}</span>
            <ColorPicker size="sm" :model-value="valueMapColor(val)" @update:model-value="(c) => setValueColor(val, c)" />
          </div>
        </template>

        <template v-else>
          <p class="rd-color-note">
            This field has no small fixed set of values — colour it as a whole below, or add specific values to highlight.
          </p>
          <div v-for="(val, i) in manualValues" :key="i" class="rd-color-row">
            <Input :model-value="val" size="sm" class="flex-1" placeholder="e.g. Done"
              @update:model-value="(v) => renameManualValue(i, v)" />
            <ColorPicker size="sm" :model-value="valueMapColor(val)" @update:model-value="(c) => setValueColor(val, c)" />
            <IconButton size="sm" variant="light" aria-label="Remove value" @click="removeManualValue(i)">
              <Icon :icon="Trash2" :size="12" />
            </IconButton>
          </div>
          <button type="button" class="rd-add-value" @click="addManualValue">+ Add a specific value</button>
        </template>

        <div class="rd-color-row rd-color-divider">
          <span class="rd-color-row-label">{{ hasPerValue ? 'Everything else' : 'All values' }}</span>
          <ColorPicker size="sm" :model-value="flatColor" @update:model-value="setFlatColor" />
        </div>
        <p v-if="open === 'bg'" class="rd-color-note">Leave unset for no background — the row stays transparent.</p>
      </template>
    </div>
  </div>
</template>

<script setup>
// One configurable block, shared verbatim by all three drop zones (Solo,
// Row 1, Row 2) so they can never drift into near-copies of each other.
// Lives in its own SFC rather than a render function inside the designer:
// Vue's scoped CSS is applied by the template compiler, so block markup
// built with h() would silently lose every one of these styles.
//
// `open` is the SLOT currently being edited ('bg' | 'color' | null), not a
// boolean — background and text colour are independent settings that happen
// to share one editor, so the panel needs to know which one it's writing to.
import { computed } from 'vue'
import { GripVertical, Palette, ArrowLeftRight, X, Trash2, Maximize2, Minimize2 } from 'lucide-vue-next'
import Icon from '@/ui/Icon.vue'
import Input from '@/ui/Input.vue'
import IconButton from '@/ui/IconButton.vue'
import Spinner from '@/ui/Spinner.vue'
import ColorPicker from '@/ui/ColorPicker.vue'

const props = defineProps({
  element:  { type: Object, required: true },  // the live, reactive block — mutated in place
  line:     { type: String, required: true },  // 'solo' | 'line1' | 'line2'
  label:    { type: String, default: '' },
  icon:     { type: [Object, Function], default: null },
  isField:  { type: Boolean, default: false },
  open:     { type: [String, null], default: null }, // 'bg' | 'color' | null
  choices:  { type: Array, default: () => [] },
  loading:  { type: Boolean, default: false },
})
defineEmits(['toggle-solo', 'move', 'toggle-config', 'remove'])

// Which of the block's two colour slots the open panel writes to.
const slot = computed(() => (props.open === 'bg' ? 'bg' : 'color'))
const cfg = computed(() => props.element[slot.value] || null)

function ensure(mode) {
  const el = props.element
  const k = slot.value
  if (!el[k]) el[k] = { mode, map: {}, fallback: null, value: null }
  else if (el[k].mode !== mode) el[k] = { ...el[k], mode }
  return el[k]
}

// Swatch previews on the collapsed row: a flat colour shows itself, a
// per-value map shows its fallback (the only colour that applies to every
// value), otherwise nothing — so the button never implies a colour it
// wouldn't actually paint.
function previewOf(c) {
  if (!c) return null
  return c.mode === 'value_map' ? (c.fallback || firstMapColor(c)) : (c.value || null)
}
function firstMapColor(c) {
  const vals = Object.values(c.map || {}).filter(Boolean)
  return vals.length ? vals[0] : null
}
const bgPreview = computed(() => previewOf(props.element.bg))
const colorPreview = computed(() => previewOf(props.element.color))

const manualValues = computed(() =>
  cfg.value?.mode === 'value_map' ? Object.keys(cfg.value.map || {}) : []
)
const hasPerValue = computed(() => props.choices.length > 0 || manualValues.value.length > 0)

function valueMapColor(val) {
  return cfg.value?.mode === 'value_map' ? (cfg.value.map?.[val] || null) : null
}
function setValueColor(val, color) {
  const c = ensure('value_map')
  c.map = { ...c.map, [val]: color }
}
const flatColor = computed(() => {
  const c = cfg.value
  if (!c) return null
  return c.mode === 'value_map' ? (c.fallback || null) : (c.value || null)
})
function setFlatColor(color) {
  const el = props.element, k = slot.value
  if (el[k]?.mode === 'value_map') { el[k].fallback = color; return }
  if (!color) { el[k] = null; return }
  ensure('flat').value = color
}
function addManualValue() {
  const c = ensure('value_map')
  c.map = { ...c.map, '': '#64748b' }
}
function renameManualValue(i, newVal) {
  const c = cfg.value
  const keys = Object.keys(c.map)
  const map = { ...c.map }
  const color = map[keys[i]]
  delete map[keys[i]]
  map[newVal] = color
  c.map = map
}
function removeManualValue(i) {
  const c = cfg.value
  const keys = Object.keys(c.map)
  const map = { ...c.map }
  delete map[keys[i]]
  c.map = map
}
</script>

<style scoped>
.rd-block {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 8px; border-radius: var(--radius-md);
  border: 1px solid var(--border); background: var(--surface);
}
.rd-block-open { border-color: var(--accent); }
.rd-block-solo { background: var(--accent-soft); border-color: var(--accent-soft); }
.rd-drag-handle { display: flex; cursor: grab; color: var(--muted); flex-shrink: 0; }
.rd-drag-handle:active { cursor: grabbing; }
.rd-block-label { flex: 1; min-width: 0; font-size:var(--text-sm); font-weight: 500; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rd-block-action {
  display: flex; align-items: center; justify-content: center; width: 24px; height: 24px;
  border-radius: var(--radius-sm); color: var(--muted); background: none; border: none; cursor: pointer; flex-shrink: 0;
  transition: background-color .12s, color .12s;
}
.rd-block-action:hover { background: var(--surface-secondary); color: var(--foreground); }
.rd-block-action.rd-swatch-on { background: var(--accent-soft); color: var(--accent-soft-foreground); }
.rd-block-remove:hover { color: var(--danger); background: var(--danger-soft); }

.rd-swatch {
  width: 14px; height: 14px; border-radius: 4px;
  border: 1px solid color-mix(in oklab, var(--foreground) 20%, transparent);
}
/* Unset background: a hollow swatch with a diagonal — reads as "transparent",
   not as "white". */
.rd-swatch-empty {
  background:
    linear-gradient(to top left,
      transparent calc(50% - 1px), var(--muted) calc(50% - 1px),
      var(--muted) calc(50% + 1px), transparent calc(50% + 1px));
}

.rd-color-config {
  display: flex; flex-direction: column; gap: 7px;
  margin: 4px 0 6px 22px; padding: 10px; border-radius: var(--radius-md);
  background: var(--surface-secondary); border: 1px solid var(--border);
  max-height: 260px; overflow-y: auto;
}
.rd-color-head { font-size:var(--text-xs); font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); }
.rd-color-row { display: flex; align-items: center; gap: 10px; }
.rd-color-divider { border-top: 1px solid var(--border); padding-top: 8px; }
.rd-color-row-label { flex: 1; min-width: 0; font-size:var(--text-sm); color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rd-color-note { font-size:var(--text-xs); color: var(--muted); line-height: 1.45; }
.rd-add-value { align-self: flex-start; font-size:var(--text-sm); font-weight: 600; color: var(--accent); background: none; border: none; cursor: pointer; padding: 2px 0; }
</style>
