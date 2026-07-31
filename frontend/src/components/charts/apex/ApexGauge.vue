<template>
  <apexchart type="radialBar" :height="height" width="100%" :options="options" :series="series" />
</template>

<script setup>
import { computed } from 'vue'
import { baseOptions, itemColors, fmtNum } from './apexTheme.js'

// Two modes:
//  - items: [{label,value,color?}] → one ring per category, % of total
//  - value + max                   → single gauge
const props = defineProps({
  items:  { type: Array,  default: () => [] },
  value:  { type: Number, default: null },
  max:    { type: Number, default: 100 },
  label:  { type: String, default: '' },
  height: { type: [Number, String], default: '100%' },
  format: { type: Function, default: fmtNum },
})

const single = computed(() => props.value !== null)
const total = computed(() => props.items.reduce((a, b) => a + (+b.value || 0), 0) || 1)

const series = computed(() =>
  single.value
    ? [Math.round(((+props.value || 0) / (props.max || 1)) * 100)]
    : props.items.map(i => Math.round(((+i.value || 0) / total.value) * 100)),
)

const options = computed(() => baseOptions({
  chart: { type: 'radialBar' },
  colors: single.value ? undefined : itemColors(props.items),
  labels: single.value ? [props.label || 'Value'] : props.items.map(i => i.label),
  stroke: { lineCap: 'round' },
  legend: { show: false },
  plotOptions: {
    radialBar: {
      hollow: { size: single.value ? '60%' : '38%' },
      track: { background: 'var(--surface-secondary)', strokeWidth: '100%' },
      dataLabels: {
        name: { fontSize: '12px', color: 'var(--muted)', offsetY: single.value ? -8 : 0 },
        value: {
          fontSize: single.value ? '24px' : '13px',
          fontWeight: 700,
          color: 'var(--foreground)',
          formatter: (v) => (single.value ? props.format((+props.value || 0)) : v + '%'),
        },
        total: single.value ? undefined : { show: true, label: 'Total', color: 'var(--muted)', formatter: () => props.format(total.value) },
      },
    },
  },
  yaxis: { labels: { show: false } },
  grid: { padding: { top: 0, right: 0, bottom: 0, left: 0 }, yaxis: { lines: { show: false } } },
  tooltip: { enabled: false },
}))
</script>
