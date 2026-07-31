<template>
  <template v-if="isLoaded"><slot /></template>
  <span
    v-else
    :class="cn('skel block relative overflow-hidden rounded-md pointer-events-none', $attrs.class)"
    v-bind="{ ...$attrs, class: undefined }"
    aria-hidden="true"
  />
</template>

<script setup>
import { cn } from '@/lib/utils'
defineOptions({ inheritAttrs: false })
defineProps({ isLoaded: { type: Boolean, default: false } })
</script>

<style scoped>
/* Exact HeroUI v3 skeleton (packages/styles/components/skeleton.css):
   base = surface-tertiary at 70%, shimmer sweeps via surface-tertiary, 2s linear */
.skel {
  background-color: color-mix(in oklab, var(--surface-tertiary) 70%, transparent);
}
.skel::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent 0%, var(--surface-tertiary) 50%, transparent 100%);
  animation: skel-shimmer 2s linear infinite;
}
@keyframes skel-shimmer {
  100% { transform: translateX(100%); }
}
@media (prefers-reduced-motion: reduce) {
  .skel::after { animation: none; }
}
</style>
