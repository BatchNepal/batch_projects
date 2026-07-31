<template>
  <span :class="classes">
    <span v-if="variant === 'dot'" :class="['shrink-0 rounded-full', DOT_COLOR[color] ?? 'bg-default-foreground']" style="width:6px;height:6px" aria-hidden="true" />
    <slot name="startContent" />
    <slot />
    <button
      v-if="isCloseable"
      type="button"
      class="shrink-0 flex items-center ml-0.5 -mr-0.5 opacity-60 hover:opacity-100 transition-opacity focus:outline-none"
      @click.stop="emit('close')"
      aria-label="Remove"
    >
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 6L6 18M6 6l12 12"/>
      </svg>
    </button>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  color:       { type: String,  default: 'default' }, // default | accent | success | warning | danger
  variant:     { type: String,  default: 'soft' },    // solid | soft | outline | dot
  size:        { type: String,  default: 'md' },      // sm | md | lg
  isCloseable: { type: Boolean, default: false },
  isDisabled:  { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const SIZE = {
  sm: 'h-5 px-2 text-xs gap-1',
  md: 'h-[22px] px-2.5 text-xs gap-1',
  lg: 'h-6 px-3 text-xs gap-1.5',
}

const STYLES = {
  solid: {
    default: 'bg-default text-default-foreground',
    accent:  'bg-accent text-accent-foreground',
    success: 'bg-success text-success-foreground',
    warning: 'bg-warning text-warning-foreground',
    danger:  'bg-danger text-danger-foreground',
  },
  soft: {
    default: 'bg-default text-default-foreground',
    accent:  'bg-accent-soft text-accent-soft-foreground',
    success: 'bg-success-soft text-success-soft-foreground',
    warning: 'bg-warning-soft text-warning-soft-foreground',
    danger:  'bg-danger-soft text-danger-soft-foreground',
  },
  outline: {
    default: 'border border-border text-foreground',
    accent:  'border border-accent text-accent',
    success: 'border border-success text-success',
    warning: 'border border-warning text-warning',
    danger:  'border border-danger text-danger',
  },
  dot: {
    default: 'bg-default text-default-foreground pl-1.5',
    accent:  'bg-accent-soft text-accent-soft-foreground pl-1.5',
    success: 'bg-success-soft text-success-soft-foreground pl-1.5',
    warning: 'bg-warning-soft text-warning-soft-foreground pl-1.5',
    danger:  'bg-danger-soft text-danger-soft-foreground pl-1.5',
  },
}

const DOT_COLOR = {
  default: 'bg-default-foreground',
  accent:  'bg-accent',
  success: 'bg-success',
  warning: 'bg-warning',
  danger:  'bg-danger',
}

const classes = computed(() => cn(
  'inline-flex items-center justify-center font-medium whitespace-nowrap select-none rounded-md',
  SIZE[props.size] ?? SIZE.md,
  STYLES[props.variant]?.[props.color] ?? STYLES.soft.default,
  props.isDisabled && 'opacity-45 pointer-events-none',
))
</script>
