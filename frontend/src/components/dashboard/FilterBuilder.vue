<template>
  <div class="fb">
    <div v-for="(row, i) in rows" :key="i" class="fb-row">
      <!-- Field: a Combobox, not a Select. Sources like Sales Order expose
           90+ fields; a plain dropdown of that is a wall you scroll, not a
           control you use. -->
      <Combobox
        class="fb-field"
        :model-value="row.fieldname"
        :loader="q => searchFields(q)"
        placeholder="Field"
        @update:model-value="v => setField(i, v)"
      />

      <Select :model-value="row.operator" class="fb-op" @update:model-value="v => setOperator(i, v)">
        <SelectItem v-for="op in operatorsFor(row.fieldname)" :key="op.v" :value="op.v">{{ op.l }}</SelectItem>
      </Select>

      <!-- value: shape follows the operator, not just the fieldtype -->
      <template v-if="!isEmptyOp(row.operator)">
        <!-- relative date — the "no complex queries" path -->
        <Select
          v-if="row.operator === 'date_preset'"
          class="fb-value" :model-value="row.value"
          @update:model-value="v => setValue(i, v)"
        >
          <SelectItem v-for="p in datePresets" :key="p.value" :value="p.value">{{ p.label }}</SelectItem>
        </Select>

        <!-- explicit two-bound range -->
        <div v-else-if="row.operator === 'between'" class="fb-value fb-range">
          <Input
            :type="isDateField(row.fieldname) ? 'date' : 'number'"
            :model-value="rangePart(row.value, 0)" placeholder="From"
            @update:model-value="v => setRange(i, 0, v)"
          />
          <span class="fb-range-sep">→</span>
          <Input
            :type="isDateField(row.fieldname) ? 'date' : 'number'"
            :model-value="rangePart(row.value, 1)" placeholder="To"
            @update:model-value="v => setRange(i, 1, v)"
          />
        </div>

        <!-- link/select values, typeahead-backed; multi when "is any of" -->
        <Combobox
          v-else-if="isPickable(row.fieldname)"
          class="fb-value"
          :model-value="row.value"
          :multiple="row.operator === 'in' || row.operator === 'not in'"
          :loader="q => loadOptions(row.fieldname, q)"
          placeholder="Value"
          @update:model-value="v => setValue(i, v)"
        />

        <Input
          v-else class="fb-value"
          :type="inputTypeFor(row.fieldname)"
          :model-value="row.value" placeholder="Value"
          @update:model-value="v => setValue(i, v)"
        />
      </template>

      <button type="button" class="fb-remove outline-none focus-visible:shadow-focus" title="Remove filter" @click="removeRow(i)">
        <Icon :icon="X" :size="14" />
      </button>
    </div>

    <button type="button" class="fb-add outline-none focus-visible:shadow-focus" @click="addRow">
      <Icon :icon="Plus" :size="13" /> Add filter
    </button>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { Plus, X } from 'lucide-vue-next'
import { Select, SelectItem, Combobox, Input, Icon } from '@/ui'
import { getWidgetSourceFields, getWidgetSourceFieldOptions, getDatePresets } from '@/utils/api'

// Visual field + operator + value filter builder — doctype-agnostic. Fields
// come from the real schema (get_widget_source_fields), so this works
// identically for BP Task, Sales Order, Lead, Employee, ... with zero
// per-doctype UI branching.
//
// The operator vocabulary is fieldtype-driven, and every operator offered
// here is one the backend's _SAFE_FILTER_OPERATORS actually accepts — the
// two lists must stay in sync or a filter silently 500s at query time.
const props = defineProps({
  doctype: { type: String, required: true },
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const fields = ref([])
const fieldMeta = ref({})
async function loadFields() {
  fields.value = await getWidgetSourceFields(props.doctype).catch(() => [])
  fieldMeta.value = Object.fromEntries(fields.value.map(f => [f.fieldname, f]))
}
onMounted(loadFields)
watch(() => props.doctype, loadFields)

const datePresets = ref([])
getDatePresets().then(p => { datePresets.value = p || [] }).catch(() => {})

// Combobox loader shape: [{ value, label }]
function searchFields(q) {
  const needle = (q || '').toLowerCase()
  return fields.value
    .filter(f => !needle || f.label.toLowerCase().includes(needle) || f.fieldname.includes(needle))
    .slice(0, 50)
    .map(f => ({ value: f.fieldname, label: f.label }))
}

const rows = ref(props.modelValue.length ? props.modelValue.map(r => ({ ...r })) : [])
watch(() => props.modelValue, v => { rows.value = (v || []).map(r => ({ ...r })) })

function emitRows() { emit('update:modelValue', rows.value.map(r => ({ ...r }))) }

const TEXT_TYPES = new Set(['Data', 'Small Text', 'Text', 'Long Text', 'Text Editor'])
const DATE_TYPES = new Set(['Date', 'Datetime'])
const NUM_TYPES = new Set(['Int', 'Float', 'Currency', 'Percent'])

function ftOf(fieldname) { return fieldMeta.value[fieldname]?.fieldtype }
function isDateField(fieldname) { return DATE_TYPES.has(ftOf(fieldname)) }
function isPickable(fieldname) { const ft = ftOf(fieldname); return ft === 'Link' || ft === 'Select' }
function inputTypeFor(fieldname) {
  const ft = ftOf(fieldname)
  if (DATE_TYPES.has(ft)) return 'date'
  if (NUM_TYPES.has(ft)) return 'number'
  return 'text'
}

const EMPTY_OPS = [{ v: 'is_set', l: 'is set' }, { v: 'is_not_set', l: 'is empty' }]

function operatorsFor(fieldname) {
  const ft = ftOf(fieldname)
  if (DATE_TYPES.has(ft)) {
    // Relative first — it's the one people actually want, and it keeps
    // meaning the same thing as the dashboard ages.
    return [
      { v: 'date_preset', l: 'is' },
      { v: '<', l: 'is before' },
      { v: '>', l: 'is after' },
      { v: 'between', l: 'is between' },
      { v: '=', l: 'is exactly' },
      ...EMPTY_OPS,
    ]
  }
  if (NUM_TYPES.has(ft)) {
    return [
      { v: '=', l: '=' }, { v: '!=', l: '≠' },
      { v: '>', l: '>' }, { v: '<', l: '<' },
      { v: '>=', l: '≥' }, { v: '<=', l: '≤' },
      { v: 'between', l: 'is between' },
      ...EMPTY_OPS,
    ]
  }
  if (ft === 'Link' || ft === 'Select') {
    return [
      { v: '=', l: 'is' }, { v: '!=', l: 'is not' },
      { v: 'in', l: 'is any of' }, { v: 'not in', l: 'is none of' },
      ...EMPTY_OPS,
    ]
  }
  if (ft === 'Check') {
    return [{ v: '=', l: 'is' }]
  }
  if (TEXT_TYPES.has(ft)) {
    return [
      { v: 'like', l: 'contains' }, { v: 'not like', l: "doesn't contain" },
      { v: '=', l: 'is' }, { v: '!=', l: 'is not' },
      ...EMPTY_OPS,
    ]
  }
  return [{ v: '=', l: 'is' }, { v: '!=', l: 'is not' }, ...EMPTY_OPS]
}

function isEmptyOp(op) { return op === 'is_set' || op === 'is_not_set' }

async function loadOptions(fieldname, query) {
  if (!fieldname) return []
  return await getWidgetSourceFieldOptions(props.doctype, fieldname, query).catch(() => [])
}

// `between` carries a 2-slot array; keep the other slot intact while editing.
function rangePart(value, idx) { return Array.isArray(value) ? (value[idx] ?? '') : '' }
function setRange(i, idx, v) {
  const cur = Array.isArray(rows.value[i].value) ? [...rows.value[i].value] : ['', '']
  cur[idx] = v
  rows.value[i].value = cur
  emitRows()
}

// A fresh row defaults to the first operator its fieldtype offers, so a date
// field starts on "is <preset>" rather than an equality test nobody wants.
function defaultOpFor(fieldname) { return operatorsFor(fieldname)[0]?.v || '=' }
function defaultValueFor(fieldname, op) {
  if (op === 'between') return ['', '']
  if (op === 'in' || op === 'not in') return []
  if (op === 'date_preset') return 'today'
  return ''
}

function addRow() {
  const first = fields.value[0]?.fieldname || ''
  const op = defaultOpFor(first)
  rows.value.push({ fieldname: first, operator: op, value: defaultValueFor(first, op) })
  emitRows()
}
function removeRow(i) { rows.value.splice(i, 1); emitRows() }
function setField(i, v) {
  const op = defaultOpFor(v)
  rows.value[i] = { fieldname: v, operator: op, value: defaultValueFor(v, op) }
  emitRows()
}
function setOperator(i, v) {
  rows.value[i].operator = v
  rows.value[i].value = isEmptyOp(v) ? '' : defaultValueFor(rows.value[i].fieldname, v)
  emitRows()
}
function setValue(i, v) { rows.value[i].value = v; emitRows() }
</script>

<style scoped>
.fb { display: flex; flex-direction: column; gap: 8px; }
.fb-row { display: flex; align-items: center; gap: 6px; }
.fb-field { flex: 1.1; min-width: 0; }
.fb-op { flex: 0.85; min-width: 0; }
.fb-value { flex: 1.2; min-width: 0; }

.fb-range { display: flex; align-items: center; gap: 4px; }
.fb-range-sep { font-size: 11px; color: var(--muted); flex-shrink: 0; }

.fb-remove {
  flex-shrink: 0; width: 28px; height: 28px; border-radius: 6px;
  display: grid; place-items: center; color: var(--muted);
  transition: background-color .12s, color .12s;
}
.fb-remove:hover { background: var(--surface-secondary); color: var(--danger); }
.fb-add {
  align-self: flex-start; display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600; color: var(--accent); padding: 4px 2px;
}
.fb-add:hover { opacity: 0.8; }
</style>
