<template>
  <svg
    :class="cn('spinner shrink-0', SIZE[size] ?? SIZE.md, $attrs.class)"
    viewBox="0 0 24 24"
    fill="none"
    v-bind="{ ...$attrs, class: undefined }"
    aria-hidden="true"
  >
    <circle cx="12" cy="12" r="9.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="50 50" />
  </svg>
</template>

<script setup>
import { cn } from '@/lib/utils'
defineOptions({ inheritAttrs: false })
defineProps({ size: { type: String, default: 'md' } })
const SIZE = { xs: 'size-3', sm: 'size-3.5', md: 'size-4', lg: 'size-5' }
</script>

<style scoped>
.spinner {
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
