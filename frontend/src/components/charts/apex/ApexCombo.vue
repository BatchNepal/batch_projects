<template>
  <apexchart type="line" :height="height" width="100%" :options="options" :series="series" />
</template>

<script setup>
import { computed } from 'vue'
import { baseOptions, PALETTE, fmtNum } from './apexTheme.js'

// Mixed bar + line chart (e.g. Created vs Resolved throughput).
// series: [{ name, type:'column'|'line', data:[...], color? }]
const props = defineProps({
  categories: { type: Array,  default: () => [] },
  series:     { type: Array,  default: () => [] },
  height:     { type: [Number, String], default: '100%' },
  format:     { type: Function, default: fmtNum },
})

const options = computed(() => baseOptions({
  chart: { type: 'line' },
  colors: props.series.map((s, i) => s.color || PALETTE[i % PALETTE.length]),
  stroke: { width: props.series.map(s => (s.type === 'line' ? 3 : 0)), curve: 'smooth' },
  plotOptions: { bar: { borderRadius: 3, columnWidth: '52%' } },
  markers: { size: 0, hover: { size: 5 } },
  xaxis: { categories: props.categories },
  legend: { show: true, position: 'bottom' },
  tooltip: { shared: true, intersect: false, y: { formatter: props.format } },
  fill: { type: 'solid', opacity: props.series.map(s => (s.type === 'line' ? 1 : 0.9)) },
}))
</script>
