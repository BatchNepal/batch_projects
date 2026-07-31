<template>
  <apexchart type="donut" :height="height" width="100%" :options="options" :series="series" />
</template>

<script setup>
import { computed } from 'vue'
import { baseOptions, itemColors, fmtNum } from './apexTheme.js'

const props = defineProps({
  items:      { type: Array,  default: () => [] }, // [{ label, value, color? }]
  height:     { type: [Number, String], default: '100%' },
  showLegend: { type: Boolean, default: true },
  format:     { type: Function, default: fmtNum },
})

const series = computed(() => props.items.map(i => +i.value || 0))

const options = computed(() => baseOptions({
  chart: { type: 'donut' },
  colors: itemColors(props.items),
  labels: props.items.map(i => i.label),
  stroke: { width: 0 },
  legend: { show: props.showLegend, position: 'right' },
  plotOptions: {
    pie: {
      donut: {
        size: '68%',
        labels: {
          show: true,
          total: {
            show: true,
            label: 'Total',
            fontSize: '11px',
            color: 'var(--muted)',
            formatter: (w) => props.format(w.globals.seriesTotals.reduce((a, b) => a + b, 0)),
          },
          value: { fontSize: '20px', fontWeight: 700, color: 'var(--foreground)', formatter: props.format },
        },
      },
    },
  },
  tooltip: { y: { formatter: props.format } },
  yaxis: { labels: { show: false } },
  grid: { padding: { top: 0, right: 0, bottom: 0, left: 0 } },
}))
</script>
