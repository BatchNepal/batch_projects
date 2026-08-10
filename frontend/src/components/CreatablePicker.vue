<template>
  <div class="cp-search-wrap">
    <input
      ref="inputEl"
      v-model="q"
      class="cp-search"
      :placeholder="searchPlaceholder"
      @click.stop
      @keydown.stop
      @keydown.enter="onEnter"
    />
  </div>

  <DropdownItem v-if="allowEmpty && !q.trim()" :active="!modelValue" @click="$emit('select', null)">
    {{ emptyLabel }}
  </DropdownItem>

  <DropdownItem
    v-for="o in filtered" :key="o.key"
    :active="isActive(o.key)"
    @click="$emit('select', o.key)"
  >
    <span v-if="o.color" class="cp-dot" :style="{ background: o.color }" />
    {{ o.label }}
  </DropdownItem>

  <p v-if="!filtered.length && !q.trim()" class="cp-empty">No {{ noun }}s yet — type to create one</p>

  <DropdownItem v-if="q.trim() && !exactMatch" :class="{ 'opacity-60 pointer-events-none': creating }" @click="onCreate">
    <Plus :size="12" class="shrink-0 text-muted" />
    Create&nbsp;<strong>&ldquo;{{ q.trim() }}&rdquo;</strong>
  </DropdownItem>
</template>

<script setup>
// Reusable "pick from existing, or type to create a new one" list — built so
// Status/Epic/Sprint/Label pickers (previously 4 near-identical dropdown
// bodies each, once per row-template variant: flat/grouped x parent/child)
// don't each hand-roll their own search+create logic. Backend specifics
// (what fields a new Epic vs Sprint vs Label actually needs) stay with the
// caller — this component only emits 'create' with the typed text and lets
// the caller resolve it to a real key, then itself emits 'select'.
import { ref, computed, nextTick, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import DropdownItem from '@/components/DropdownItem.vue'

const props = defineProps({
  options:           { type: Array, required: true },  // [{key, label, color?}]
  modelValue:        { type: [String, Array, null], default: null },
  multiple:          { type: Boolean, default: false }, // modelValue is an array; 'select' toggles membership
  noun:              { type: String, default: 'item' }, // "epic", "label", ...
  emptyLabel:        { type: String, default: 'None' },
  allowEmpty:        { type: Boolean, default: true },
  searchPlaceholder: { type: String, default: '' },
  autofocus:         { type: Boolean, default: true },
})
const emit = defineEmits(['select', 'create'])

const inputEl = ref(null)
const q = ref('')
const creating = ref(false)

function isActive(key) {
  return props.multiple
    ? Array.isArray(props.modelValue) && props.modelValue.includes(key)
    : props.modelValue === key
}

const filtered = computed(() => {
  const needle = q.value.trim().toLowerCase()
  if (!needle) return props.options
  return props.options.filter(o => o.label.toLowerCase().includes(needle))
})
const exactMatch = computed(() => {
  const needle = q.value.trim().toLowerCase()
  return props.options.some(o => o.label.toLowerCase() === needle)
})

async function onCreate() {
  const name = q.value.trim()
  if (!name || creating.value) return
  creating.value = true
  try {
    await emit('create', name)
    q.value = ''
  } finally {
    creating.value = false
  }
}
function onEnter() {
  if (q.value.trim() && !exactMatch.value) onCreate()
}

onMounted(() => {
  if (props.autofocus) nextTick(() => inputEl.value?.focus())
})
</script>

<style scoped>
.cp-search-wrap {
  padding: 8px 12px;
  border-bottom: 1px solid var(--separator);
}
.cp-search {
  width: 100%;
  font-size:var(--text-base);
  font-family: inherit;
  color: var(--foreground);
  background: none;
  border: none;
  outline: none;
}
.cp-search::placeholder { color: var(--muted); }
.cp-empty {
  padding: 8px 12px;
  font-size:var(--text-sm);
  color: var(--muted);
}
.cp-dot {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  flex-shrink: 0;
}
</style>
