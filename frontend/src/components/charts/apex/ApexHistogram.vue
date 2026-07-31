<template>
  <apexchart type="bar" :height="height" width="100%" :options="options" :series="series" />
</template>

<script setup>
import { computed } from 'vue'
import { baseOptions, PALETTE, fmtNum } from './apexTheme.js'

// Buckets raw numeric values into bins (e.g. cycle-time distribution).
const props = defineProps({
  values: { type: Array,  default: () => [] }, // [number, ...]
  bins:   { type: Number, default: 8 },
  height: { type: [Number, String], default: '100%' },
  color:  { type: String, default: PALETTE[0] },
  unit:   { type: String, default: '' },
  format: { type: Function, default: fmtNum },
})

const buckets = computed(() => {
  const vals = props.values.map(Number).filter(v => !Number.isNaN(v))
  if (!vals.length) return { labels: [], counts: [] }
  const min = Math.min(...vals), max = Math.max(...vals)
  const span = max - min || 1
  const n = Math.max(1, props.bins)
  const size = span / n
  const counts = new Array(n).fill(0)
  for (const v of vals) {
    let idx = Math.floor((v - min) / size)
    if (idx >= n) idx = n - 1
    counts[idx]++
  }
  const labels = counts.map((_, i) => {
    const lo = min + i * size
    const hi = lo + size
    return `${Math.round(lo)}–${Math.round(hi)}${props.unit}`
  })
  return { labels, counts }
})

const series = computed(() => [{ name: 'Count', data: buckets.value.counts }])

const options = computed(() => baseOptions({
  chart: { type: 'bar' },
  colors: [props.color],
  plotOptions: { bar: { borderRadius: 2, columnWidth: '92%' } },
  legend: { show: false },
  xaxis: { categories: buckets.value.labels },
  tooltip: { y: { formatter: props.format } },
  dataLabels: { enabled: false },
}))
</script>
