<template>
  <!-- Select — a real fixed enum from the doctype's own meta, not free text -->
  <Combobox
    v-if="fieldMeta?.fieldtype === 'Select'"
    :model-value="modelValue" size="sm" class="flex-1" :placeholder="placeholder || 'Value…'"
    :options="(fieldMeta.options || []).map(o => ({ value: o, label: o }))"
    @update:model-value="v => emit('update:modelValue', v)"
  />

  <div v-else-if="fieldMeta?.fieldtype === 'Check'" class="flex items-center h-8">
    <Switch
      :model-value="modelValue === '1' || modelValue === 1"
      @update:model-value="v => emit('update:modelValue', v ? '1' : '0')"
    />
  </div>

  <Input
    v-else-if="fieldMeta?.fieldtype === 'Date'"
    :model-value="modelValue" type="date" size="sm" class="flex-1"
    @update:model-value="v => emit('update:modelValue', v)"
  />

  <Input
    v-else-if="['Int', 'Float', 'Currency', 'Percent'].includes(fieldMeta?.fieldtype)"
    :model-value="modelValue" type="number" size="sm" class="flex-1" :placeholder="placeholder || 'Value…'"
    @update:model-value="v => emit('update:modelValue', v)"
  />

  <!-- Link to a searchable doctype: real typeahead against actual ERPNext
       records, clear/unlink built into Combobox, label persisted so a
       reloaded value shows its real title (not the raw docname). -->
  <Combobox
    v-else-if="fieldMeta?.fieldtype === 'Link' && searchableLinkDoctype(fieldMeta.options)"
    :model-value="modelValue" :model-label="resolvedLabel" size="sm" class="flex-1"
    :loader="q => searchErp(fieldMeta.options, q)" :min-chars="1"
    :placeholder="placeholder || `Search ${fieldMeta.options}…`"
    @update:model-value="v => emit('update:modelValue', v)"
    @update:model-label="v => emit('update:modelLabel', v)"
  />

  <div v-else-if="fieldMeta?.fieldtype === 'Link'" class="flex-1 flex flex-col gap-0.5">
    <Input :model-value="modelValue" size="sm" :placeholder="placeholder || 'Value…'"
      @update:model-value="v => emit('update:modelValue', v)" />
    <p class="text-[10.5px] text-muted leading-snug">
      {{ fieldMeta.options }} isn't searchable here yet — type the exact document name.
    </p>
  </div>

  <Input
    v-else
    :model-value="modelValue" size="sm" class="flex-1" :placeholder="placeholder || 'Value…'"
    @update:model-value="v => emit('update:modelValue', v)"
  />
</template>

<script setup>
// The ONE fieldtype-adaptive ERPNext value editor — reused by both
// automation builders (flat editor's "Fields to set" rows, canvas's
// "Fields to update" keyvalue rows, and any per-doctype condition value)
// instead of three separately hand-rolled per-fieldtype v-if chains.
import { computed } from 'vue'
import Combobox from '@/ui/Combobox.vue'
import Input from '@/ui/Input.vue'
import Switch from '@/ui/Switch.vue'
import { searchErpDocuments } from '@/utils/api'
import { useErpDoctypeFields, searchableLinkDoctype } from '@/composables/useErpDoctypeFields'

const props = defineProps({
  fieldMeta:   { type: Object, default: null }, // {fieldname,label,fieldtype,options} — options = target doctype for Link, choice list for Select
  modelValue:  { default: '' },
  modelLabel:  { type: String, default: '' },   // known label for modelValue, if the caller already has one (e.g. hydrated from a saved rule)
  placeholder: { type: String, default: '' },
  // BP Project the caller is scoped to (null for a workspace-scope
  // automation) — threaded through to search_erp_documents so a project's
  // own financial documents (Sales Order, Timesheet, ...) stay scoped to
  // it instead of searching every project's records.
  project:     { type: String, default: null },
})
const emit = defineEmits(['update:modelValue', 'update:modelLabel'])

const { erpDocLabel } = useErpDoctypeFields()

function searchErp(doctype, q) {
  return searchErpDocuments(doctype, q, props.project).then(rows => rows.map(r => ({ value: r.name, label: r.label })))
}

// Prefer a label the caller already knows; otherwise resolve+cache one for
// an already-set value so it reads as a real title on first render, not the
// raw docname (the composable's cache means this is a single network round
// trip per document, ever, for the whole session).
const resolvedLabel = computed(() => {
  if (props.modelLabel) return props.modelLabel
  if (fieldMeta.value?.fieldtype === 'Link' && props.modelValue) {
    return erpDocLabel(fieldMeta.value.options, props.modelValue)
  }
  return ''
})
const fieldMeta = computed(() => props.fieldMeta)
</script>
