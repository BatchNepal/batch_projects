<template>
  <svg :viewBox="`0 0 ${W} ${H}`" :width="width" :height="height" style="overflow:visible" aria-hidden="true">
    <polyline
      v-if="points"
      :points="points"
      fill="none"
      :stroke="lineColor"
      :stroke-width="strokeWidth"
      stroke-linejoin="round"
      stroke-linecap="round"
    />
    <circle
      v-if="lastX !== null"
      :cx="lastX"
      :cy="lastY"
      :r="dotR"
      :fill="dotColor"
    />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data:        { type: Array, default: () => [] },
  width:       { type: Number, default: 120 },
  height:      { type: Number, default: 28 },
  lineColor:   { type: String, default: 'var(--border-secondary)' },
  dotColor:    { type: String, default: 'var(--accent)' },
  strokeWidth: { type: Number, default: 1.5 },
  dotR:        { type: Number, default: 2.5 },
})

const W   = props.width
const H   = props.height
const PAD = 4

const points = computed(() => {
  const d = props.data
  if (!d?.length || d.length < 2) return ''
  const min = Math.min(...d), max = Math.max(...d)
  const range = max - min || 1
  return d.map((v, i) => {
    const x = PAD + (i / (d.length - 1)) * (W - PAD * 2)
    const y = H - PAD - ((v - min) / range) * (H - PAD * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})

const lastX = computed(() => {
  const d = props.data
  if (!d?.length) return null
  return PAD + ((d.length - 1) / (d.length - 1)) * (W - PAD * 2)
})

const lastY = computed(() => {
  const d = props.data
  if (!d?.length) return null
  const min = Math.min(...d), max = Math.max(...d)
  const range = max - min || 1
  return H - PAD - ((d[d.length - 1] - min) / range) * (H - PAD * 2)
})
</script>
