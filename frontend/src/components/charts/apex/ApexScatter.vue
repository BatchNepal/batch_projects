<template>
  <apexchart type="scatter" :height="height" width="100%" :options="options" :series="series" />
</template>

<script setup>
import { computed } from 'vue'
import { baseOptions, fmtNum } from './apexTheme.js'

// series: [{ name, data: [[x, y], ...], color? }]
const props = defineProps({
  series: { type: Array,  default: () => [] },
  height: { type: [Number, String], default: '100%' },
  format: { type: Function, default: fmtNum },
})

const options = computed(() => baseOptions({
  chart: { type: 'scatter' },
  colors: props.series.map((s) => s.color).filter(Boolean),
  markers: { size: 6 },
  xaxis: { type: 'numeric', tickAmount: 6 },
  legend: { show: props.series.length > 1, position: 'bottom' },
  tooltip: { y: { formatter: props.format } },
}))
</script>
