<template>
  <div class="fp-section">
    <div class="fp-section-head">
      <span class="fp-section-label">{{ label }}</span>
      <button v-if="modelValue" type="button" class="fp-clear" @click="emit('select', null)">Clear</button>
    </div>

    <div v-if="showSearch" class="fp-search-row">
      <Search :size="12" class="text-muted shrink-0" />
      <input v-model="q" class="fp-search-input" placeholder="Search…" @keydown.stop />
    </div>

    <ul class="fp-list no-scrollbar" role="listbox">
      <li
        v-for="opt in filtered" :key="opt.value"
        role="option"
        class="fp-opt"
        :class="{ selected: opt.value === modelValue }"
        @click="toggle(opt)"
      >
        <slot name="swatch" :option="opt" />
        <span class="fp-opt-label">{{ opt.label }}</span>
        <Check v-if="opt.value === modelValue" :size="13" class="shrink-0 ml-auto" />
      </li>
      <li v-if="!filtered.length" class="fp-empty">No matches</li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Search, Check } from 'lucide-vue-next'

const props = defineProps({
  label:      { type: String, required: true },
  options:    { type: Array, default: () => [] },
  modelValue: { type: [String, null], default: null },
  searchable: { type: Boolean, default: null }, // null = auto (search only when > 6 options)
})
const emit = defineEmits(['select'])

const q = ref('')
const showSearch = computed(() => props.searchable ?? props.options.length > 6)

const filtered = computed(() => {
  if (!showSearch.value || !q.value.trim()) return props.options
  const needle = q.value.trim().toLowerCase()
  return props.options.filter(o => o.label.toLowerCase().includes(needle))
})

function toggle(opt) {
  emit('select', opt.value === props.modelValue ? null : opt.value)
}
</script>

<style scoped>
.fp-section { padding: 6px 4px; }
.fp-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 6px 4px;
}
.fp-section-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .02em;
  color: var(--muted);
}
.fp-clear {
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
}
.fp-clear:hover { color: var(--danger); }

.fp-search-row {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  margin: 0 2px 4px;
  padding: 0 8px;
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
}
.fp-search-input {
  flex: 1;
  min-width: 0;
  background: transparent;
  outline: none;
  font-size: 12px;
  color: var(--foreground);
}
.fp-search-input::placeholder { color: var(--muted); }

.fp-list {
  max-height: 208px;
  overflow-y: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.fp-list::-webkit-scrollbar { display: none; }
.fp-opt {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 30px;
  padding: 0 6px;
  border-radius: var(--radius-md);
  font-size: 12.5px;
  color: var(--foreground);
  cursor: pointer;
  transition: background-color .1s;
}
.fp-opt:hover { background: var(--surface-secondary); }
.fp-opt.selected {
  background: var(--accent-soft);
  color: var(--accent-soft-foreground);
  font-weight: 500;
}
.fp-opt-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fp-empty {
  padding: 10px 6px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}

/* :slotted — the actual .fp-swatch/.fp-dot spans are written in the PARENT's
   template (FilterDrawer.vue's #swatch slot content), so they carry the
   parent's scope id, not this component's. A plain scoped rule here never
   matches them at all (collapsed to an unsized sliver of background color) —
   :slotted() is Vue's mechanism for a child's scoped style to reach content
   the parent injected into its own slot. */
:slotted(.fp-swatch) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}
:slotted(.fp-dot) {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  flex-shrink: 0;
}
</style>
