<template>
  <component
    :is="as"
    v-bind="extraAttrs"
    :disabled="as === 'button' ? isDisabled || isLoading : undefined"
    :aria-disabled="isDisabled || isLoading || undefined"
    :data-variant="variant"
    :data-color="color"
    :data-size="size"
    :data-loading="isLoading || undefined"
    :class="classes"
    @click="!isDisabled && !isLoading ? emit('click', $event) : $event.preventDefault()"
  >
    <span v-if="$slots.startContent" class="btn-icon" aria-hidden="true">
      <slot name="startContent" />
    </span>
    <Spinner v-if="isLoading" :size="size === 'lg' ? 'sm' : 'xs'" class="shrink-0" />
    <slot />
    <span v-if="$slots.endContent" class="btn-icon" aria-hidden="true">
      <slot name="endContent" />
    </span>
  </component>
</template>

<script setup>
import { computed, useAttrs } from 'vue'
import { cn } from '@/lib/utils'
import Spinner from './Spinner.vue'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  as:         { type: [String, Object], default: 'button' },
  color:      { type: String, default: 'default' },  // default | accent | success | warning | danger
  variant:    { type: String, default: 'solid' },    // solid | soft | outline | ghost | link
  size:       { type: String, default: 'md' },       // sm | md | lg
  isLoading:  { type: Boolean, default: false },
  isDisabled: { type: Boolean, default: false },
  isIconOnly: { type: Boolean, default: false },
  fullWidth:  { type: Boolean, default: false },
})

const emit = defineEmits(['click'])
const attrs = useAttrs()

const extraAttrs = computed(() => {
  const { class: _, ...rest } = attrs
  return rest
})

const SIZE = {
  xs: { base: 'h-6 text-xs', normal: 'px-2.5 gap-1',     icon: 'w-5' },
  sm: { base: 'h-7 text-xs', normal: 'px-2.5 gap-1.5', icon: 'w-7' },
  md: { base: 'h-8 text-sm', normal: 'px-3 gap-1.5',   icon: 'w-8' },
  lg: { base: 'h-9 text-sm', normal: 'px-4 gap-2',     icon: 'w-9' },
}

/* color × variant → Tailwind classes using CSS var-based colors */
const STYLES = {
  solid: {
    default: 'bg-default text-default-foreground hover:bg-default-hover',
    accent:  'bg-accent text-accent-foreground hover:bg-accent-hover',
    success: 'bg-success text-success-foreground hover:bg-success-hover',
    warning: 'bg-warning text-warning-foreground hover:bg-warning-hover',
    danger:  'bg-danger text-danger-foreground hover:bg-danger-hover',
  },
  soft: {
    default: 'bg-default text-default-foreground hover:bg-default-hover',
    accent:  'bg-accent-soft text-accent-soft-foreground hover:bg-accent-soft-hover',
    success: 'bg-success-soft text-success-soft-foreground hover:bg-success-soft-hover',
    warning: 'bg-warning-soft text-warning-soft-foreground hover:bg-warning-soft-hover',
    danger:  'bg-danger-soft text-danger-soft-foreground hover:bg-danger-soft-hover',
  },
  outline: {
    default: 'bg-transparent border border-border text-foreground hover:bg-default',
    accent:  'bg-transparent border border-accent text-accent hover:bg-accent-soft',
    success: 'bg-transparent border border-success text-success hover:bg-success-soft',
    warning: 'bg-transparent border border-warning text-warning hover:bg-warning-soft',
    danger:  'bg-transparent border border-danger text-danger hover:bg-danger-soft',
  },
  ghost: {
    default: 'bg-transparent text-foreground hover:bg-default',
    accent:  'bg-transparent text-accent hover:bg-accent-soft',
    success: 'bg-transparent text-success hover:bg-success-soft',
    warning: 'bg-transparent text-warning hover:bg-warning-soft',
    danger:  'bg-transparent text-danger hover:bg-danger-soft',
  },
  link: {
    default: 'bg-transparent text-foreground underline-offset-4 hover:underline',
    accent:  'bg-transparent text-accent underline-offset-4 hover:underline',
    success: 'bg-transparent text-success underline-offset-4 hover:underline',
    warning: 'bg-transparent text-warning underline-offset-4 hover:underline',
    danger:  'bg-transparent text-danger underline-offset-4 hover:underline',
  },
}

// `primary` is an alias for `accent` — many call sites use color="primary".
for (const variant of Object.values(STYLES)) variant.primary = variant.accent

const sz  = computed(() => SIZE[props.size]  ?? SIZE.md)
const col = computed(() => STYLES[props.variant]?.[props.color] ?? STYLES.solid.default)

const classes = computed(() => cn(
  'btn relative inline-flex items-center justify-center font-medium whitespace-nowrap',
  'select-none outline-none rounded-md',
  'transition-[background-color,box-shadow,transform,color,border-color]',
  'disabled:opacity-45 disabled:pointer-events-none',
  'active:scale-[0.96]',
  sz.value.base,
  props.isIconOnly ? sz.value.icon : sz.value.normal,
  col.value,
  props.fullWidth && 'w-full',
  props.isLoading && 'pointer-events-none',
  attrs.class,
))
</script>

<style scoped>
.btn {
  transition:
    background-color var(--duration-fast) var(--ease-out),
    border-color     var(--duration-fast) var(--ease-out),
    color            var(--duration-fast) var(--ease-out),
    box-shadow       var(--duration-fast) var(--ease-out),
    transform        var(--duration-base) var(--ease-smooth);
}
.btn:active {
  transition: transform var(--duration-instant) ease-out;
}
.btn-icon {
  display: contents;
}
.btn-icon > :deep(svg) {
  width:  14px;
  height: 14px;
  flex-shrink: 0;
  pointer-events: none;
}
</style>
