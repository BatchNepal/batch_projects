<template>
  <component
    :is="as"
    :disabled="as === 'button' ? isDisabled : undefined"
    :aria-disabled="isDisabled || undefined"
    :class="cn(
      'icon-btn inline-grid place-items-center shrink-0 rounded-md select-none outline-none',
      'active:scale-[0.90] disabled:opacity-45 disabled:pointer-events-none',
      'focus-visible:shadow-focus',
      SIZE[size] ?? SIZE.md,
      STYLES[variant]?.[color] ?? STYLES.ghost.default,
      $attrs.class,
    )"
    v-bind="extraAttrs"
    @click="!isDisabled ? emit('click', $event) : $event.preventDefault()"
  >
    <slot />
  </component>
</template>

<script setup>
import { computed, useAttrs } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  as:         { type: [String, Object], default: 'button' },
  color:      { type: String,  default: 'default' }, // default | accent | danger
  variant:    { type: String,  default: 'ghost' },   // ghost | soft | solid
  size:       { type: String,  default: 'md' },      // xs | sm | md | lg
  isDisabled: { type: Boolean, default: false },
})
const emit = defineEmits(['click'])
const attrs = useAttrs()
const extraAttrs = computed(() => { const { class: _, ...rest } = attrs; return rest })

const SIZE = {
  xs: 'h-6 w-6  [&>svg]:w-3   [&>svg]:h-3',
  sm: 'h-7 w-7  [&>svg]:w-3.5 [&>svg]:h-3.5',
  md: 'h-8 w-8  [&>svg]:w-4   [&>svg]:h-4',
  lg: 'h-9 w-9  [&>svg]:w-4.5 [&>svg]:h-4.5',
}

const STYLES = {
  ghost: {
    default: 'text-muted hover:bg-default hover:text-foreground',
    accent:  'text-accent hover:bg-accent-soft',
    danger:  'text-danger hover:bg-danger-soft',
  },
  outline: {
    default: 'bg-transparent border border-border text-muted hover:bg-default hover:text-foreground',
    accent:  'bg-transparent border border-accent text-accent hover:bg-accent-soft',
    danger:  'bg-transparent border border-danger text-danger hover:bg-danger-soft',
  },
  soft: {
    default: 'bg-default text-foreground hover:bg-default-hover',
    accent:  'bg-accent-soft text-accent-soft-foreground hover:bg-accent-soft-hover',
    danger:  'bg-danger-soft text-danger-soft-foreground hover:bg-danger-soft-hover',
  },
  solid: {
    default: 'bg-default text-default-foreground hover:bg-default-hover',
    accent:  'bg-accent text-accent-foreground hover:bg-accent-hover',
    danger:  'bg-danger text-danger-foreground hover:bg-danger-hover',
  },
}
</script>

<style scoped>
.icon-btn {
  transition:
    background-color var(--duration-fast) var(--ease-out),
    color            var(--duration-fast) var(--ease-out),
    transform        200ms var(--ease-smooth);
}
.icon-btn:active { transition: transform 40ms ease-out; }
</style>
