<template>
  <button
    :disabled="disabled"
    :class="cn(
      'flex items-center gap-2 w-full px-2 py-1.5 rounded-md text-sm text-left',
      'select-none cursor-pointer outline-none',
      'transition-colors duration-fast',
      'disabled:opacity-40 disabled:pointer-events-none',
      color === 'danger'
        ? 'text-danger hover:bg-danger-soft active:bg-danger-soft-hover focus-visible:bg-danger-soft'
        : active
          ? 'text-accent hover:bg-default active:bg-default-hover focus-visible:bg-default bg-accent-soft'
          : 'text-foreground hover:bg-default active:bg-default-hover focus-visible:bg-default',
    )"
    @click="handleClick"
  >
    <span v-if="$slots.startContent" class="shrink-0 flex items-center" :class="color === 'danger' ? '' : 'text-muted'">
      <slot name="startContent" />
    </span>
    <span class="flex-1 min-w-0 truncate"><slot /></span>
    <span v-if="$slots.endContent" class="shrink-0 flex items-center ml-auto text-muted">
      <slot name="endContent" />
    </span>
    <svg
      v-else-if="active"
      class="shrink-0 ml-auto text-accent"
      width="13" height="13" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" stroke-width="2.5"
      stroke-linecap="round" stroke-linejoin="round"
    ><path d="M5 13l4 4L19 7"/></svg>
  </button>
</template>

<script setup>
import { inject } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  color:        { type: String,  default: 'default' },
  disabled:     { type: Boolean, default: false },
  active:       { type: Boolean, default: false },
  closeOnClick: { type: Boolean, default: true },
})
const emit = defineEmits(['click'])

const dropdownHide = inject('dropdown-hide', null)

function handleClick(e) {
  if (props.disabled) return
  emit('click', e)
  if (props.closeOnClick) dropdownHide?.()
}
</script>

<style scoped>
button { transition: background-color var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out); }
button :deep(svg) { width: 14px; height: 14px; flex-shrink: 0; }
</style>
