<template>
  <button
    type="button"
    :disabled="isDisabled"
    :aria-label="ariaLabel"
    :class="cn('inline-flex items-center justify-center rounded-md text-muted hover:bg-default hover:text-foreground transition-colors duration-fast outline-none focus-visible:shadow-focus disabled:opacity-45 disabled:pointer-events-none', SIZE[size] ?? SIZE.md, $attrs.class)"
    v-bind="{ ...$attrs, class: undefined }"
    @click="emit('click', $event)"
  >
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" :class="ICON[size] ?? ICON.md">
      <path d="M18 6L6 18M6 6l12 12"/>
    </svg>
  </button>
</template>

<script setup>
import { cn } from '@/lib/utils'
defineOptions({ inheritAttrs: false })
defineProps({ size: { type: String, default: 'md' }, isDisabled: { type: Boolean, default: false }, ariaLabel: { type: String, default: 'Close' } })
const emit = defineEmits(['click'])
const SIZE = { sm: 'w-6 h-6', md: 'w-7 h-7', lg: 'w-8 h-8' }
const ICON = { sm: 'w-3 h-3', md: 'w-3.5 h-3.5', lg: 'w-4 h-4' }
</script>
