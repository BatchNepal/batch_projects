<template>
  <div
    :class="cn('flex flex-col gap-1.5', fullWidth ? 'w-full' : 'w-fit', $attrs.class)"
    v-bind="{ ...$attrs, class: undefined }"
  >
    <label v-if="label" :for="uid" class="text-[13px] font-medium leading-none text-foreground">
      {{ label }}<span v-if="isRequired" class="text-danger ml-0.5" aria-hidden="true">*</span>
    </label>

    <!-- Trigger — HeroUI v2 select trigger: flat filled field -->
    <button
      :id="uid"
      ref="triggerRef"
      type="button"
      :disabled="isDisabled"
      :aria-expanded="isOpen"
      :aria-haspopup="'listbox'"
      :class="cn(
        'hui-field sel-trigger inline-flex items-center justify-between gap-2 px-3',
        'text-foreground  select-none cursor-pointer',
        isOpen && 'is-active',
        isInvalid && 'is-invalid',
        'disabled:opacity-45 disabled:cursor-not-allowed',
        SIZE[size] ?? SIZE.md,
        fullWidth ? 'w-full' : 'w-fit',
      )"
      @click="toggle"
      @keydown="onTriggerKey"
    >
      <span
        class="flex-1 truncate font-medium text-start leading-none"
        :class="selectedLabel ? 'text-foreground' : 'text-[var(--field-placeholder)]'"
      >{{ selectedLabel || placeholder }}</span>
      <svg
        class="shrink-0 text-[var(--field-placeholder)] transition-transform duration-base"
        :class="[isOpen && 'rotate-180', size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4']"
        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"
      ><path d="M6 9l6 6 6-6"/></svg>
    </button>

    <!-- Floating listbox — HeroUI select__popover: bg-overlay + overlay shadow, no border -->
    <Teleport to="body">
      <Transition name="sel-pop">
        <div
          v-show="isOpen"
          ref="listboxRef"
          role="listbox"
          :aria-label="label || 'Options'"
          :style="pos"
          class="bp-overlay fixed z-dropdown bg-white rounded-lg shadow-overlay p-1 outline-none overflow-y-auto"
          style="max-height: 280px; max-width: min(360px, calc(100vw - 16px))"
          tabindex="-1"
          @keydown="onListKey"
        >
          <slot />
        </div>
      </Transition>
    </Teleport>

    <p v-if="isInvalid && errorMessage" class="text-[12px] text-danger leading-snug">{{ errorMessage }}</p>
    <p v-else-if="description" class="text-[12px] text-muted leading-snug">{{ description }}</p>
  </div>
</template>

<script setup>
import { ref, reactive, computed, provide, nextTick, onMounted, onBeforeUnmount, watch, useId } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

// Field heights: sm 32 / md 36 / lg 40
const SIZE = {
  sm: 'h-8 text-[13px]',
  md: 'h-9 text-sm',
  lg: 'h-10 text-sm',
}

const props = defineProps({
  modelValue:   { default: '' },
  label:        { type: String,  default: '' },
  placeholder:  { type: String,  default: '' },
  description:  { type: String,  default: '' },
  errorMessage: { type: String,  default: '' },
  size:         { type: String,  default: 'md' },
  isDisabled:   { type: Boolean, default: false },
  isRequired:   { type: Boolean, default: false },
  isInvalid:    { type: Boolean, default: false },
  fullWidth:    { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue'])

// Unique id for label association (useId — the old per-instance counter
// reset to 1 for every Select, producing duplicate DOM ids)
const uid = useId()

// Option registry: value → label text
const optionLabels = reactive({})
const selectedLabel = computed(() => optionLabels[props.modelValue] ?? '')

// Open state + positioning
const isOpen     = ref(false)
const triggerRef = ref(null)
const listboxRef = ref(null)
const pos        = ref({})

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

function open()  { isOpen.value = true;  nextTick(reposition) }
function close() { isOpen.value = false; triggerRef.value?.focus() }
function toggle(){ isOpen.value ? close() : open() }

// Keyboard on trigger
function onTriggerKey(e) {
  if (['ArrowDown','ArrowUp','Enter',' '].includes(e.key)) {
    e.preventDefault()
    if (!isOpen.value) open()
    else nextTick(() => focusItem(e.key === 'ArrowUp' ? -1 : 0))
  }
  if (e.key === 'Escape') close()
}

// Keyboard inside listbox
function onListKey(e) {
  const items = [...(listboxRef.value?.querySelectorAll('[role="option"]:not([aria-disabled="true"])') || [])]
  const idx   = items.findIndex(el => el === document.activeElement)
  if (e.key === 'ArrowDown') { e.preventDefault(); items[(idx + 1) % items.length]?.focus() }
  if (e.key === 'ArrowUp')   { e.preventDefault(); items[(idx - 1 + items.length) % items.length]?.focus() }
  if (e.key === 'Escape')    { e.preventDefault(); close() }
  if (e.key === 'Tab')       { close() }
}

function focusItem(i) {
  const items = [...(listboxRef.value?.querySelectorAll('[role="option"]:not([aria-disabled="true"])') || [])]
  const idx   = i < 0 ? items.length - 1 : i
  items[idx]?.focus()
}

// Click-outside
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

// Provide context to SelectItem children
provide('select-ctx', {
  modelValue: computed(() => props.modelValue),
  size:       computed(() => props.size),
  onSelect(value) { emit('update:modelValue', value); close() },
  register(value, label) { optionLabels[value] = label },
  unregister(value)      { delete optionLabels[value] },
})
</script>

<style scoped>
.sel-trigger { font-family: inherit; }
.sel-pop-enter-active { transition: opacity var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-smooth); }
.sel-pop-leave-active { transition: opacity var(--duration-fast) var(--ease-in), transform var(--duration-fast) var(--ease-in); }
.sel-pop-enter-from  { opacity: 0; transform: scale(0.96) translateY(-3px); }
.sel-pop-leave-to    { opacity: 0; transform: scale(0.97); }
</style>
