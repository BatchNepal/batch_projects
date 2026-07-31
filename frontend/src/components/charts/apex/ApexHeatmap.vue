<template>
  <apexchart type="heatmap" :height="height" width="100%" :options="options" :series="series" />
</template>

<script setup>
import { computed } from 'vue'
import { baseOptions, PALETTE, fmtNum } from './apexTheme.js'

// series: [{ name, data: [{ x, y }, ...] }]
const props = defineProps({
  series: { type: Array,  default: () => [] },
  height: { type: [Number, String], default: '100%' },
  color:  { type: String, default: PALETTE[0] },
  format: { type: Function, default: fmtNum },
})

const options = computed(() => baseOptions({
  chart: { type: 'heatmap' },
  colors: [props.color],
  stroke: { width: 2, colors: ['#fff'] },
  plotOptions: { heatmap: { radius: 4, enableShades: true, shadeIntensity: 0.5 } },
  legend: { show: false },
  tooltip: { y: { formatter: props.format } },
}))
</script>
