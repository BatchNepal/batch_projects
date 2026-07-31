<template>
  <apexchart type="bar" :height="height" width="100%" :options="options" :series="series" />
</template>

<script setup>
import { computed } from 'vue'
import { baseOptions, itemColors, fmtNum } from './apexTheme.js'

const props = defineProps({
  items:      { type: Array,  default: () => [] }, // [{ label, value, color? }]
  height:     { type: [Number, String], default: '100%' },
  horizontal: { type: Boolean, default: false },
  format:     { type: Function, default: fmtNum },
})

// Use an empty series name — label comes from the x-axis category per data point.
const series = computed(() => [{ name: '', data: props.items.map(i => +i.value || 0) }])

const options = computed(() => baseOptions({
  chart: { type: 'bar' },
  colors: itemColors(props.items),
  plotOptions: {
    bar: {
      horizontal: props.horizontal,
      distributed: true,           // one color per bar
      borderRadius: 4,
      borderRadiusApplication: 'end',
      columnWidth: '58%',
      barHeight: '64%',
    },
  },
  legend: { show: false },
  xaxis: { categories: props.items.map(i => i.label) },
  // In horizontal mode Apex swaps axes — the y-axis then displays the
  // category *strings*, not numbers, so the base theme's numeric
  // fmtNum formatter must not apply there (it silently coerces every
  // label to "0"). Pass the category through as-is instead. Key is
  // omitted entirely (not set to undefined) when not horizontal, since
  // the merge helper treats an explicit undefined as "wipe this key".
  ...(props.horizontal ? { yaxis: { labels: { formatter: (v) => v } } } : {}),
  tooltip: {
    y: {
      formatter: props.format,
      // For distributed bars the "series name" is empty; show the x-axis category as the label.
      title: {
        formatter: (_, { dataPointIndex, w }) => {
          const cat = w?.config?.xaxis?.categories?.[dataPointIndex]
          return cat ? cat + ':' : ''
        },
      },
    },
  },
  dataLabels: {
    enabled: props.horizontal,
    formatter: props.format,
    style: { fontSize: '11px', fontWeight: 600, colors: ['#fff'] },
  },
}))
</script>
