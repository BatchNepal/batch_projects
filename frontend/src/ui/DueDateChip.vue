<template>
  <span v-if="date" :class="cls" class="inline-flex items-center gap-1 text-xs tabular-nums whitespace-nowrap">
    <svg v-if="overdue" class="size-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
      <circle cx="12" cy="12" r="10"/><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l2 2"/>
    </svg>
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  date:     { default: null },  // ISO string or Date
  relative: { type: Boolean, default: true },
  // Table/column contexts (My Tasks' "Due date" column) need the actual
  // value visible in the cell, not just a relative label — "13d overdue"
  // with no date anywhere tells you nothing until you do the math against
  // today, and a dedicated column exists precisely so you don't have to.
  // Compact contexts (kanban cards, TaskRow, ProjectTree) keep the relative
  // label unchanged; this is opt-in per call site, default off.
  absolute: { type: Boolean, default: false },
})

const now = new Date()
now.setHours(0, 0, 0, 0)

const parsed = computed(() => {
  if (!props.date) return null
  const d = new Date(props.date)
  d.setHours(0, 0, 0, 0)
  return d
})

const diffDays = computed(() => {
  if (!parsed.value) return null
  return Math.round((parsed.value - now) / 86400000)
})

const overdue = computed(() => diffDays.value !== null && diffDays.value < 0)
const today   = computed(() => diffDays.value === 0)
const soon    = computed(() => diffDays.value !== null && diffDays.value > 0 && diffDays.value <= 3)

const absoluteLabel = computed(() =>
  parsed.value ? parsed.value.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''
)

const label = computed(() => {
  if (!parsed.value) return ''
  if (props.absolute) return absoluteLabel.value
  const d = diffDays.value
  if (d < 0)  return `${Math.abs(d)}d overdue`
  if (d === 0) return 'Today'
  if (d === 1) return 'Tomorrow'
  if (props.relative && d <= 14) return `${d}d`
  return absoluteLabel.value
})

const cls = computed(() => {
  if (overdue.value) return 'text-danger font-medium'
  if (today.value)   return 'text-warning font-medium'
  if (soon.value)    return 'text-warning'
  return 'text-muted'
})
</script>
