<template>
  <div
    :class="cn('flex flex-col gap-1.5 relative', fullWidth ? 'w-full' : 'w-fit', $attrs.class)"
    v-bind="{ ...$attrs, class: undefined }"
  >
    <label v-if="label" :for="uid" class="text-base font-medium leading-none text-foreground">
      {{ label }}<span v-if="isRequired" class="text-danger ml-0.5" aria-hidden="true">*</span>
    </label>

    <!-- Trigger: text input (+ chip row when multiple) -->
    <div
      ref="triggerRef"
      :class="cn(
        'hui-field cbx-trigger flex items-center flex-wrap gap-1 px-2 cursor-text',
        multiple ? 'min-h-9 py-1' : SIZE[size] ?? SIZE.md,
        isOpen && 'is-active',
        isInvalid && 'is-invalid',
        isDisabled && 'opacity-45 pointer-events-none',
        fullWidth ? 'w-full' : 'w-fit',
      )"
      @click="onTriggerClick"
    >
      <span
        v-for="v in selectedList" :key="v"
        class="shrink-0"
      >
        <Chip size="sm" variant="soft" is-closeable @close.stop="removeValue(v)">
          {{ labelFor(v) }}
        </Chip>
      </span>

      <input
        :id="uid"
        ref="inputRef"
        type="text"
        :value="query"
        :placeholder="selectedList.length ? '' : placeholder"
        :disabled="isDisabled"
        class="flex-1 min-w-[60px] h-7 bg-transparent outline-none text-sm text-foreground placeholder:text-[var(--field-placeholder)]"
        autocomplete="off"
        @input="onInput"
        @focus="open"
        @keydown="onKey"
      />

      <Spinner v-if="loading" size="sm" class="shrink-0" />
      <button
        v-if="!multiple && modelValue && !isDisabled && !loading"
        type="button"
        class="shrink-0 flex items-center justify-center rounded text-[var(--field-placeholder)] hover:text-foreground hover:bg-default transition-colors"
        style="width:18px;height:18px"
        aria-label="Clear"
        @click.stop="clearValue"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </button>
      <svg
        v-if="!loading"
        class="shrink-0 text-[var(--field-placeholder)] transition-transform duration-base"
        :class="[isOpen && 'rotate-180', size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4']"
        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"
      ><path d="M6 9l6 6 6-6"/></svg>
    </div>

    <!-- Floating listbox -->
    <Teleport to="body">
      <Transition name="cbx-pop">
        <div
          v-show="isOpen"
          ref="listboxRef"
          role="listbox"
          :aria-label="label || 'Options'"
          :style="pos"
          class="bp-overlay fixed z-dropdown bg-overlay rounded-lg shadow-overlay p-1 outline-none overflow-y-auto"
          style="max-height: 280px; max-width: min(360px, calc(100vw - 16px))"
          tabindex="-1"
        >
          <div v-if="loading && !filtered.length" class="px-2.5 py-3 text-base text-muted text-center">Searching…</div>
          <div v-else-if="!filtered.length && !canCreate" class="px-2.5 py-3 text-base text-muted text-center">
            {{ query.length < minChars ? `Type at least ${minChars} characters…` : 'No matches' }}
          </div>
          <div
            v-for="(opt, i) in filtered" :key="opt.value"
            role="option"
            :aria-selected="isSelected(opt.value)"
            :tabindex="-1"
            :class="cn(
              'cbx-item relative flex items-center gap-2 px-2.5 rounded-sm cursor-pointer select-none min-h-[32px] py-1.5 text-sm',
              'text-foreground outline-none hover:bg-default',
              i === highlighted && 'bg-default',
              isSelected(opt.value) && 'font-medium',
            )"
            @mouseenter="highlighted = i"
            @click="selectOption(opt)"
          >
            <span class="flex-1 truncate text-start">{{ opt.label }}</span>
            <svg v-if="isSelected(opt.value)" class="shrink-0 text-foreground" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>
          </div>
          <div
            v-if="canCreate"
            role="option"
            :class="cn(
              'cbx-item flex items-center gap-2 px-2.5 rounded-sm cursor-pointer select-none min-h-[32px] py-1.5 text-sm text-accent',
              highlighted === filtered.length && 'bg-default',
            )"
            @mouseenter="highlighted = filtered.length"
            @click="createValue"
          >
            Create "{{ query }}"
          </div>
        </div>
      </Transition>
    </Teleport>

    <p v-if="isInvalid && errorMessage" class="text-sm text-danger leading-snug">{{ errorMessage }}</p>
    <p v-else-if="description" class="text-sm text-muted leading-snug">{{ description }}</p>
  </div>
</template>

<script setup>
// Combobox — searchable single/multi select, the ONE such primitive in @/ui
//. API deliberately mirrors Select.vue (v-model, size,
// fullWidth) so swapping a Select for a Combobox is a one-tag change.
//
// Two data modes:
//   options: static [{value,label}] array — client-side substring filter.
//   loader:  async (query) => [{value,label}] — server-backed, debounced
//            var(--duration-slow), only called once `query.length >= minChars`.
// Never both; loader wins if both are passed.
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount, useId } from 'vue'
import { cn } from '@/lib/utils'
import Chip from './Chip.vue'
import Spinner from './Spinner.vue'

defineOptions({ inheritAttrs: false })

const SIZE = { sm: 'h-8 text-base', md: 'h-9 text-sm', lg: 'h-10 text-sm' }

const props = defineProps({
  modelValue:   { default: '' },        // string (single) or array (multiple)
  modelLabel:   { type: String, default: '' }, // authoritative label for the current single modelValue — lets a caller that already knows the label (e.g. a resolved ERP document title) skip a redundant search round trip
  options:      { type: Array,  default: null },  // [{value,label}]
  loader:       { type: Function, default: null }, // async (query) => [{value,label}]
  minChars:     { type: Number, default: 0 },
  multiple:     { type: Boolean, default: false },
  allowCreate:  { type: Boolean, default: false },
  label:        { type: String,  default: '' },
  placeholder:  { type: String,  default: 'Search…' },
  description:  { type: String,  default: '' },
  errorMessage: { type: String,  default: '' },
  size:         { type: String,  default: 'md' },
  isDisabled:   { type: Boolean, default: false },
  isRequired:   { type: Boolean, default: false },
  isInvalid:    { type: Boolean, default: false },
  fullWidth:    { type: Boolean, default: true },
})
// update:modelLabel is optional/additive — fires alongside update:modelValue
// (single-select only) with the label of whatever just became the value, so
// a caller wired to a search loader (e.g. ERPNext Link fields) can persist
// {value, label} together and never has to separately re-resolve a label
// for a value it just watched the user pick.
const emit = defineEmits(['update:modelValue', 'update:modelLabel', 'create'])

const uid = useId()
const isOpen = ref(false)
const query = ref('')
const loading = ref(false)
const highlighted = ref(0)
const asyncResults = ref(null) // null = not yet searched this session
const knownLabels = ref({})    // value -> label, for chips/selected display when not in current filtered list

const triggerRef = ref(null)
const inputRef   = ref(null)
const listboxRef = ref(null)
const pos = ref({})

const selectedList = computed(() =>
  props.multiple ? (Array.isArray(props.modelValue) ? props.modelValue : []) : []
)

function labelFor(value) {
  if (value == null || value === '') return ''
  if (value === props.modelValue && props.modelLabel) return props.modelLabel
  return knownLabels.value[value]
    ?? (props.options || []).find(o => o.value === value)?.label
    ?? String(value)
}
function isSelected(value) {
  return props.multiple ? selectedList.value.includes(value) : props.modelValue === value
}

// Seed knownLabels from static options immediately + track anything the
// loader returns, so a chip/selected-label survives after the listbox
// closes and its results are cleared.
watch(() => props.options, (opts) => {
  for (const o of opts || []) knownLabels.value[o.value] = o.label
}, { immediate: true })

const filtered = computed(() => {
  const pool = props.loader ? (asyncResults.value || []) : (props.options || [])
  if (props.loader) return pool // server already filtered
  const q = query.value.trim().toLowerCase()
  const base = q ? pool.filter(o => o.label.toLowerCase().includes(q)) : pool
  return props.multiple ? base.filter(o => !selectedList.value.includes(o.value)) : base
})

const canCreate = computed(() =>
  props.allowCreate && query.value.trim().length > 0 &&
  !filtered.value.some(o => o.label.toLowerCase() === query.value.trim().toLowerCase())
)

let debounceTimer = null
function runLoader() {
  if (!props.loader) return
  clearTimeout(debounceTimer)
  if (query.value.trim().length < props.minChars) {
    asyncResults.value = []
    loading.value = false
    return
  }
  loading.value = true
  debounceTimer = setTimeout(async () => {
    try {
      const results = await props.loader(query.value.trim())
      asyncResults.value = results || []
      for (const o of asyncResults.value) knownLabels.value[o.value] = o.label
    } catch {
      asyncResults.value = []
    } finally {
      loading.value = false
    }
  }, 300)
}

function onInput(e) {
  query.value = e.target.value
  highlighted.value = 0
  if (!isOpen.value) open()
  if (props.loader) runLoader()
}

function reposition() {
  if (!triggerRef.value || !listboxRef.value) return
  const t = triggerRef.value.getBoundingClientRect()
  requestAnimationFrame(() => {
    if (!listboxRef.value) return
    const f  = listboxRef.value.getBoundingClientRect()
    const vw = window.innerWidth, vh = window.innerHeight
    const gap = 4
    let top  = t.bottom + gap
    let left = t.left
    if (top + f.height > vh - 8) top = t.top - f.height - gap
    left = Math.max(8, Math.min(left, vw - f.width - 8))
    pos.value = { top: top + 'px', left: left + 'px', minWidth: t.width + 'px' }
  })
}

function open() {
  if (props.isDisabled) return
  isOpen.value = true
  nextTick(reposition)
  if (props.loader && asyncResults.value === null) runLoader()
}
function close() {
  isOpen.value = false
  query.value = props.multiple ? '' : (labelFor(props.modelValue) || '')
}
function onTriggerClick() {
  inputRef.value?.focus()
  if (!isOpen.value) open()
}

function selectOption(opt) {
  if (props.multiple) {
    const next = [...selectedList.value, opt.value]
    emit('update:modelValue', next)
    query.value = ''
    knownLabels.value[opt.value] = opt.label
    inputRef.value?.focus()
    // stay open — multi-select keeps adding
  } else {
    knownLabels.value[opt.value] = opt.label
    emit('update:modelValue', opt.value)
    emit('update:modelLabel', opt.label)
    close()
  }
}
function removeValue(value) {
  emit('update:modelValue', selectedList.value.filter(v => v !== value))
}
function clearValue() {
  query.value = ''
  emit('update:modelValue', '')
  emit('update:modelLabel', '')
}
function createValue() {
  const val = query.value.trim()
  emit('create', val)
  if (props.multiple) {
    emit('update:modelValue', [...selectedList.value, val])
    knownLabels.value[val] = val
    query.value = ''
  } else {
    knownLabels.value[val] = val
    emit('update:modelValue', val)
    emit('update:modelLabel', val)
    close()
  }
}

function onKey(e) {
  const total = filtered.value.length + (canCreate.value ? 1 : 0)
  if (e.key === 'ArrowDown') { e.preventDefault(); if (!isOpen.value) return open(); highlighted.value = (highlighted.value + 1) % Math.max(total, 1) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); highlighted.value = (highlighted.value - 1 + Math.max(total, 1)) % Math.max(total, 1) }
  else if (e.key === 'Enter') {
    e.preventDefault()
    if (!isOpen.value) return open()
    if (highlighted.value < filtered.value.length) selectOption(filtered.value[highlighted.value])
    else if (canCreate.value) createValue()
  } else if (e.key === 'Escape') { close(); inputRef.value?.blur() }
  else if (e.key === 'Backspace' && !query.value && props.multiple && selectedList.value.length) {
    removeValue(selectedList.value[selectedList.value.length - 1])
  }
}

// Single-select: reflect the current value's label into the input when
// not actively typing/open (so it reads like Select's trigger text).
watch(() => props.modelValue, (v) => {
  if (!props.multiple && !isOpen.value) query.value = v ? labelFor(v) : ''
}, { immediate: true })

function onPD(e) {
  if (!isOpen.value) return
  if (triggerRef.value?.contains(e.target) || listboxRef.value?.contains(e.target)) return
  close()
}
onMounted(()       => document.addEventListener('pointerdown', onPD, true))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onPD, true))

watch(isOpen, v => {
  if (v) { window.addEventListener('scroll', reposition, true); window.addEventListener('resize', reposition) }
  else   { window.removeEventListener('scroll', reposition, true); window.removeEventListener('resize', reposition) }
})
</script>

<style scoped>
.cbx-trigger { font-family: inherit; }
.cbx-item { transition: background-color var(--duration-fast) var(--ease-out); }
.cbx-pop-enter-active { transition: opacity var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-smooth); }
.cbx-pop-leave-active { transition: opacity var(--duration-fast) var(--ease-in), transform var(--duration-fast) var(--ease-in); }
.cbx-pop-enter-from  { opacity: 0; transform: scale(0.96) translateY(-3px); }
.cbx-pop-leave-to    { opacity: 0; transform: scale(0.97); }
</style>
