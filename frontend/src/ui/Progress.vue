<template>
  <div :class="cn('flex flex-col gap-1.5 w-full', $attrs.class)" v-bind="{ ...$attrs, class: undefined }">
    <div v-if="label || showValueLabel" class="flex items-center justify-between">
      <span v-if="label" class="text-xs font-medium text-foreground">{{ label }}</span>
      <span v-if="showValueLabel" class="text-xs text-muted ml-auto tabular-nums">{{ valueLabel }}</span>
    </div>

    <div
      role="progressbar"
      :aria-valuenow="isIndeterminate ? undefined : clamped"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-label="label || 'Progress'"
      :class="cn('relative w-full overflow-hidden rounded-full', TRACK_SIZE[size] ?? TRACK_SIZE.md)"
      style="background-color: var(--default);"
    >
      <div
        :class="cn('h-full rounded-full transition-[width] duration-slower ease-out', COLOR[color] ?? COLOR.accent, isIndeterminate && 'indeterminate')"
        :style="isIndeterminate ? {} : { width: clamped + '%' }"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  value:          { type: Number,  default: 0 },
  label:          { type: String,  default: '' },
  color:          { type: String,  default: 'accent' }, // accent | success | warning | danger | default
  size:           { type: String,  default: 'md' },     // sm | md | lg
  showValueLabel: { type: Boolean, default: false },
  isIndeterminate:{ type: Boolean, default: false },
})

const clamped = computed(() => Math.min(100, Math.max(0, props.value)))

const valueLabel = computed(() => {
  try { return new Intl.NumberFormat('en', { style: 'percent' }).format(clamped.value / 100) }
  catch { return `${clamped.value}%` }
})

const TRACK_SIZE = { sm: 'h-1', md: 'h-1.5', lg: 'h-2' }

const COLOR = {
  accent:  'bg-accent',
  success: 'bg-success',
  warning: 'bg-warning',
  danger:  'bg-danger',
  default: 'bg-default-foreground',
}
</script>

<style scoped>
.indeterminate {
  width: 35% !important;
  animation: indeterminate 1.5s ease-in-out infinite;
}
@keyframes indeterminate {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
}
</style>
