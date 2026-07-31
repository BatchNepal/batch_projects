<template>
  <div class="flex items-center gap-2 w-full">
    <div class="flex-1 rounded-full overflow-hidden" :class="trackH">
      <div
        class="h-full rounded-full transition-[width,background-color] duration-400 ease-out"
        :class="fillColor"
        :style="{ width: clamped + '%' }"
      ></div>
    </div>
    <span v-if="showLabel" class="shrink-0 text-xs text-muted tabular-nums w-7 text-right">{{ clamped }}%</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value:      { type: Number, default: 0 },  // 0–100
  size:       { type: String, default: 'sm' }, // xs | sm | md
  showLabel:  { type: Boolean, default: false },
  autoColor:  { type: Boolean, default: true },
  color:      { type: String, default: '' }, // override: blue | green | amber | red
})

const clamped = computed(() => Math.min(100, Math.max(0, props.value)))

const trackH = computed(() => ({ xs: 'h-1', sm: 'h-1.5', md: 'h-2' }[props.size] ?? 'h-1.5'))

const fillColor = computed(() => {
  if (props.color) return {
    blue: 'bg-accent', green: 'bg-success', amber: 'bg-warning', red: 'bg-danger'
  }[props.color] ?? 'bg-accent'
  if (!props.autoColor) return 'bg-accent'
  const v = clamped.value
  if (v >= 80) return 'bg-success'
  if (v >= 50) return 'bg-accent'
  if (v >= 25) return 'bg-warning'
  return 'bg-danger'
})
</script>
