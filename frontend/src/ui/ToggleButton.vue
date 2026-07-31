<template>
  <button
    type="button"
    :aria-pressed="isSelected"
    :disabled="isDisabled"
    :class="cn(
      'inline-flex items-center justify-center gap-1.5 h-8 px-3 rounded-md text-sm font-medium',
      'transition-colors duration-90 select-none outline-none',
      'disabled:opacity-45 disabled:pointer-events-none focus-visible:shadow-focus',
      isSelected ? 'bg-accent-soft text-accent-soft-foreground' : 'text-muted hover:text-foreground hover:bg-default',
      $attrs.class,
    )"
    v-bind="{ ...$attrs, class: undefined }"
    @click="!isDisabled && emit('update:isSelected', !isSelected)"
  >
    <slot />
  </button>
</template>

<script setup>
import { cn } from '@/lib/utils'
defineOptions({ inheritAttrs: false })
defineProps({ isSelected: { type: Boolean, default: false }, isDisabled: { type: Boolean, default: false } })
const emit = defineEmits(['update:isSelected'])
</script>
