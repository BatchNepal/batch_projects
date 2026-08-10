<template>
  <FieldDropdown align="right" width="w-72" @open="onOpen">
    <template #trigger>
      <button class="emf-trigger" title="Show ERPNext fields on cards">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 3v18m6-18v18M3 9h18M3 15h18"/></svg>
        ERP fields
        <span v-if="cols.length" class="emf-count">{{ cols.length }}</span>
      </button>
    </template>

    <div class="emf-panel" @click.stop>
      <p class="emf-hdr">Show ERPNext fields on cards</p>

      <div v-if="cols.length" class="emf-active">
        <div v-for="c in cols" :key="c.doctype + ':' + c.field" class="emf-active-row">
          <span class="emf-active-label">{{ dtAbbr(c.doctype) }} · {{ fieldLabel(c.doctype, c.field) }}</span>
          <button class="emf-x" @click="$emit('remove', c.doctype, c.field)">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
      </div>

      <select v-model="pickDoctype" class="hui-field emf-select">
        <option :value="null" disabled>Choose a doctype…</option>
        <option v-for="dt in Object.keys(schema)" :key="dt" :value="dt">{{ dt }}</option>
      </select>

      <div v-if="pickDoctype" class="emf-fields">
        <button
          v-for="f in (schema[pickDoctype] || [])" :key="f.fieldname"
          class="emf-field-opt"
          :disabled="isActive(pickDoctype, f.fieldname)"
          @click="$emit('add', pickDoctype, f.fieldname)"
        >
          {{ f.label }}
          <Check v-if="isActive(pickDoctype, f.fieldname)" :size="12"/>
        </button>
        <p v-if="!(schema[pickDoctype] || []).length" class="emf-note">No mirrorable fields for this doctype.</p>
      </div>
    </div>
  </FieldDropdown>
</template>

<script setup>
import { ref } from 'vue'
import { Check } from 'lucide-vue-next'
import FieldDropdown from '@/components/FieldDropdown.vue'

const props = defineProps({
  schema: { type: Object, default: () => ({}) },
  cols:   { type: Array,  default: () => [] },
})
defineEmits(['add', 'remove'])

const pickDoctype = ref(null)

function dtAbbr(dt) { return dt.split(' ').map(w => w[0]).join('').toUpperCase() }
function fieldLabel(dt, field) { return (props.schema[dt] || []).find(f => f.fieldname === field)?.label || field }
function isActive(dt, field) { return props.cols.some(c => c.doctype === dt && c.field === field) }
function onOpen() { if (!pickDoctype.value) pickDoctype.value = Object.keys(props.schema)[0] || null }
</script>

<style scoped>
.emf-trigger{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 10px;font-size:var(--text-sm);font-weight:600;color:var(--foreground);background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);cursor:pointer}
.emf-trigger:hover{background:var(--surface-secondary)}
.emf-count{display:inline-flex;align-items:center;justify-content:center;min-width:15px;height:15px;padding:0 3px;font-size:var(--text-xs);font-weight:700;color:var(--accent-soft-foreground);background:var(--accent-soft);border-radius:999px}
.emf-panel{padding:10px;min-width:260px}
.emf-hdr{font-size:var(--text-xs);font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin:0 0 8px}
.emf-active{display:flex;flex-direction:column;gap:2px;margin-bottom:8px}
.emf-active-row{display:flex;align-items:center;justify-content:space-between;gap:6px;padding:3px 4px;border-radius:5px}
.emf-active-row:hover{background:var(--surface-secondary)}
.emf-active-label{font-size:var(--text-sm);color:var(--foreground)}
.emf-x{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border:none;background:none;border-radius:4px;color:var(--muted);cursor:pointer}
.emf-x:hover{background:var(--danger-soft);color:var(--danger)}
.emf-select{width:100%;height:30px;font-size:var(--text-sm);padding:0 8px;font-family:inherit;color:var(--foreground);cursor:pointer;margin-bottom:6px}
.emf-fields{display:flex;flex-direction:column;gap:1px;max-height:160px;overflow-y:auto}
.emf-field-opt{display:flex;align-items:center;justify-content:space-between;gap:6px;width:100%;text-align:left;padding:5px 8px;border:none;background:none;border-radius:5px;cursor:pointer;font-size:var(--text-sm);color:var(--foreground);font-family:inherit}
.emf-field-opt:hover:not(:disabled){background:var(--default)}
.emf-field-opt:disabled{color:var(--accent);cursor:default}
.emf-note{font-size:var(--text-sm);color:var(--muted);padding:6px 2px}
</style>
