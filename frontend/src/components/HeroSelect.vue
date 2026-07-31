<template>
  <div class="relative flex flex-col gap-1.5" :class="width" ref="containerRef">

    <label v-if="label" class="text-[12.5px] font-semibold tracking-wide" :class="error ? 'text-danger' : 'text-muted'">
      {{ label }} <span v-if="required" class="text-danger">*</span>
    </label>

    <button
      type="button"
      :disabled="disabled"
      :aria-expanded="isOpen"
      class="ui-trigger group flex w-full items-center justify-between text-left outline-none transition-all duration-150"
      :class="[
        triggerClass || 'rounded-md',
        triggerSizeClass || 'min-h-[36px] px-3 text-[13px]',
        disabled
          ? 'opacity-50 cursor-not-allowed bg-default text-muted'
          : error
            ? 'bg-danger-soft text-danger ring-1 ring-danger/30'
            : isOn
              ? 'bg-accent-soft text-[var(--accent-soft-foreground)] font-medium'
              : 'bg-transparent text-foreground/70 hover:bg-surface-secondary hover:border-muted hover:text-foreground'
      ]"
      @click="toggle"
      @keydown.escape="close"
    >
      <div class="ui-trigger-label flex-1 flex items-center min-w-0 gap-2">
        <slot name="trigger" :selected="selectedOption" :is-open="isOpen">
          <div class="flex items-center gap-2 w-full">
            <img v-if="rich && selectedOption?.avatar" :src="selectedOption.avatar" class="h-5 w-5 rounded-full object-cover bg-default shrink-0" />
            <span class="truncate font-medium" :class="modelValue ? 'text-foreground' : 'text-muted'">
              {{ triggerText }}
            </span>
          </div>
        </slot>
      </div>

      <div class="flex items-center shrink-0 ml-2 gap-1">
        <span
          v-if="clearable && modelValue"
          @click.stop="clear"
          class="p-0.5 rounded-md text-muted hover:text-foreground hover:bg-default/70 cursor-pointer transition-colors"
        >
          <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
        </span>
        <svg
          v-if="!hideChevron"
          class="shrink-0 text-muted transition-transform duration-200"
          :class="[chevronSizeClass || 'h-3.5 w-3.5', isOpen ? 'rotate-180' : '']"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
        </svg>
      </div>
    </button>

    <span v-if="hint" class="text-xs ml-1" :class="error ? 'text-danger' : 'text-muted'">{{ hint }}</span>

    <!-- Dropdown -->
    <div
      :class="[
        'ui-popover absolute z-[500] top-[calc(100%+6px)] origin-top',
        'bg-overlay rounded-xl p-1 shadow-overlay',
        'transition-all duration-150',
        isOpen ? 'opacity-100 scale-100 translate-y-0' : 'pointer-events-none opacity-0 scale-[0.98] -translate-y-1',
        align === 'right' ? 'right-0' : 'left-0',
        popoverClass,
        popoverWidth || 'w-full',
      ]"
    >
      <!-- Search slot or built-in search -->
      <slot name="search"></slot>
      <div v-if="searchable && !hasSearchSlot" class="flex items-center gap-2 px-3 py-2.5 border-b border-separator/80">
        <svg class="w-3.5 h-3.5 text-muted shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          placeholder="Search…"
          class="flex-1 text-[12.5px] bg-transparent border-none outline-none text-foreground placeholder:text-muted"
          @click.stop
          @keydown.space.stop
        />
      </div>

      <ul role="listbox" class="no-scrollbar max-h-60 overflow-y-auto outline-none">
        <li
          v-for="opt in listOptions"
          :key="opt.value"
          @click="select(opt)"
          class="flex w-full cursor-pointer select-none items-center gap-2 rounded-lg px-2.5 py-[7px] text-[13px] transition-colors duration-100"
          :class="opt.value === modelValue
            ? 'bg-accent-soft text-[var(--accent-soft-foreground)] font-semibold'
            : 'text-foreground hover:bg-default'"
        >
          <slot name="option" :option="opt">
            <div v-if="opt.avatar && rich" class="flex items-center gap-3 flex-1 min-w-0">
              <img :src="opt.avatar" class="h-8 w-8 rounded-full object-cover shrink-0 bg-default" alt=""/>
              <div class="flex flex-col min-w-0">
                <span class="block truncate font-medium">{{ opt.label }}</span>
                <span v-if="opt.desc" class="block truncate text-[12px] text-muted">{{ opt.desc }}</span>
              </div>
            </div>
            <div v-else-if="opt.desc && rich" class="flex flex-col min-w-0 flex-1">
              <span class="block truncate">{{ opt.label }}</span>
              <span class="block truncate text-[12px] text-muted">{{ opt.desc }}</span>
            </div>
            <span v-else class="flex-1 truncate">{{ opt.label }}</span>
          </slot>

          <svg v-if="opt.value === modelValue" class="h-3.5 w-3.5 shrink-0 ml-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
          </svg>
        </li>
        <li v-if="!listOptions.length" class="px-2.5 py-3 text-[13px] text-muted text-center">
          {{ emptyText || 'No options available' }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, useSlots } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number, Boolean, null] },
  options: { type: Array, default: () => [] },
  label: String,
  hint: String,
  placeholder: { type: String, default: 'Select an option' },
  width: { type: String, default: 'w-[320px]' },
  popoverWidth: String,
  align: { type: String, default: 'left' },
  disabled: Boolean,
  error: Boolean,
  required: Boolean,
  clearable: Boolean,
  isOn: Boolean,
  triggerClass: String,
  triggerSizeClass: String,
  chevronSizeClass: String,
  popoverClass: String,
  rich: Boolean,
  hideChevron: Boolean,
  emptyText: String,
  searchable: { type: Boolean, default: true }
})

const emit = defineEmits(['update:modelValue', 'change'])
const slots = useSlots()

const isOpen = ref(false)
const containerRef = ref(null)
const searchQuery = ref('')
const searchInputRef = ref(null)
const hasSearchSlot = computed(() => !!slots.search)

const normalizedOptions = computed(() =>
  (props.options || []).map(option =>
    option && typeof option === 'object'
      ? { ...option, value: option.value, label: option.label ?? String(option.value ?? '') }
      : { value: option, label: String(option ?? '') }
  )
)

const listOptions = computed(() => {
  let opts = normalizedOptions.value
  if (props.searchable && searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    opts = opts.filter(o => o.label.toLowerCase().includes(q) || String(o.value ?? '').toLowerCase().includes(q))
  }
  return opts
})

const selectedOption = computed(() => normalizedOptions.value.find(o => o.value === props.modelValue) || null)
const triggerText = computed(() => selectedOption.value?.label ?? props.placeholder)

function toggle() {
  if (props.disabled) return
  isOpen.value = !isOpen.value
  if (isOpen.value && props.searchable && !hasSearchSlot.value) {
    setTimeout(() => searchInputRef.value?.focus(), 50)
  } else if (!isOpen.value) {
    searchQuery.value = ''
  }
}

function close() { isOpen.value = false; searchQuery.value = '' }
function select(opt) { emit('update:modelValue', opt.value); emit('change', opt); close() }
function clear() { emit('update:modelValue', null); emit('change', null) }

function onOutside(e) {
  if (isOpen.value && containerRef.value && !containerRef.value.contains(e.target)) close()
}

onMounted(() => document.addEventListener('mousedown', onOutside))
onUnmounted(() => document.removeEventListener('mousedown', onOutside))
</script>

<style scoped>
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
