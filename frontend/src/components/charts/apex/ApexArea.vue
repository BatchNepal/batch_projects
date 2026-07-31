<template>
  <apexchart type="area" :height="height" width="100%" :options="options" :series="series" />
</template>

<script setup>
import { computed } from 'vue'
import { baseOptions, PALETTE, fmtNum } from './apexTheme.js'

const props = defineProps({
  items:  { type: Array,  default: () => [] }, // [{ label, value, color? }]
  height: { type: [Number, String], default: '100%' },
  format: { type: Function, default: fmtNum },
})

const color = computed(() => props.items[0]?.color || PALETTE[0])
const series = computed(() => [{ name: '', data: props.items.map(i => +i.value || 0) }])

const options = computed(() => baseOptions({
  chart: { type: 'area' },
  colors: [color.value],
  stroke: { curve: 'smooth', width: 2.5 },
  fill: { type: 'solid', opacity: 0.12 },
  markers: { size: 0, hover: { size: 5 } },
  xaxis: { categories: props.items.map(i => i.label) },
  tooltip: {
    y: {
      formatter: props.format,
      title: { formatter: () => '' },  // hide generic "Value:" prefix
    },
  },
}))
</script>
