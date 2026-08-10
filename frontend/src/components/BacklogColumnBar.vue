<template>
  <div v-if="active" class="bl-colbar" :class="mode === 'footer' ? 'bl-colbar--footer' : 'bl-colbar--header'" :style="{ gridTemplateColumns: gridTemplate }">
    <div class="bl-cbcell bl-cbcell--border" style="grid-column: span 4"></div>
    <div v-if="columns.epic" class="bl-cbcell bl-cbcell--border bl-colbar-lbl">{{ mode === 'footer' ? '' : 'Epic' }}</div>
    <div v-if="columns.points" class="bl-cbcell bl-cbcell--border bl-cbcell--num bl-colbar-lbl">
      {{ mode === 'footer' ? agg.points : 'Est. SP' }}
    </div>
    <div v-if="columns.actualPoints" class="bl-cbcell bl-cbcell--border bl-cbcell--num bl-colbar-lbl">
      {{ mode === 'footer' ? agg.actualPoints : 'Act. SP' }}
    </div>
    <div v-if="columns.unplanned" class="bl-cbcell bl-cbcell--border bl-cbcell--num bl-colbar-lbl">
      {{ mode === 'footer' ? `${agg.unplanned}/${agg.total}` : 'Unpl.' }}
    </div>
    <div class="bl-cbcell bl-cbcell--border"></div>
    <div class="bl-cbcell bl-cbcell--border"></div>
    <div class="bl-cbcell"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { blGridTemplate } from '@/utils/backlogGrid.js'

const props = defineProps({
  columns: { type: Object, required: true },
  issues:  { type: Array, default: () => [] }, // required for mode="footer"
  mode:    { type: String, default: 'header' }, // 'header' | 'footer'
})

const active = computed(() => props.columns.epic || props.columns.points || props.columns.actualPoints || props.columns.unplanned)
const gridTemplate = computed(() => blGridTemplate(props.columns))

const agg = computed(() => {
  let points = 0, actualPoints = 0, unplanned = 0
  for (const i of props.issues) {
    points += i.story_points || 0
    actualPoints += i.actual_points || 0
    if (i.is_unplanned) unplanned++
  }
  return { points, actualPoints, unplanned, total: props.issues.length }
})
</script>

<style scoped>
.bl-colbar {
  display: grid; align-items: center; height: 22px; padding: 0 14px;
}
.bl-colbar--header {
  border-bottom: 1px solid var(--separator);
  background: var(--surface-secondary);
}
.bl-colbar--footer {
  border-top: 1px solid var(--separator);
  background: var(--surface-secondary);
}
.bl-cbcell { display: flex; align-items: center; height: 100%; padding: 0 8px; min-width: 0; }
.bl-cbcell:first-child { padding-left: 0; }
.bl-cbcell--border { border-right: 1px solid var(--separator); }
.bl-cbcell--num { justify-content: center; }
.bl-colbar-lbl {
  font-size:var(--text-xs); font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.04em;
  font-variant-numeric: tabular-nums;
}
</style>
