<template>
  <apexchart type="bar" :height="height" width="100%" :options="options" :series="resolvedSeries" />
</template>

<script setup>
import { computed } from 'vue'
import { baseOptions, itemColors, PALETTE, fmtNum } from './apexTheme.js'

// Two modes:
//  - items: [{label,value,color?}] → single 100%-stacked composition bar (status "battery")
//  - categories + series           → full multi-category stacked bar
const props = defineProps({
  items:      { type: Array,  default: () => [] },
  categories: { type: Array,  default: null },
  series:     { type: Array,  default: null }, // [{ name, data:[...], color? }]
  height:     { type: [Number, String], default: '100%' },
  horizontal: { type: Boolean, default: true },
  format:     { type: Function, default: fmtNum },
})

const advanced = computed(() => Array.isArray(props.series))

const resolvedSeries = computed(() =>
  advanced.value
    ? props.series.map(s => ({ name: s.name, data: s.data }))
    : props.items.map(i => ({ name: i.label, data: [+i.value || 0] })),
)

const colors = computed(() =>
  advanced.value
    ? props.series.map((s, i) => s.color || PALETTE[i % PALETTE.length])
    : itemColors(props.items),
)

const options = computed(() => baseOptions({
  chart: { type: 'bar', stacked: true, stackType: advanced.value ? 'normal' : '100%' },
  colors: colors.value,
  plotOptions: { bar: { horizontal: props.horizontal, borderRadius: 3, columnWidth: '52%', barHeight: '46%' } },
  xaxis: { categories: advanced.value ? props.categories : [''] },
  legend: { show: true, position: 'bottom' },
  tooltip: { y: { formatter: props.format } },
  dataLabels: { enabled: false },
}))
</script>
