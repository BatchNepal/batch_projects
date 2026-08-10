<template>
  <div
    :data-row="row.name"
    draggable="true"
    class="group relative bg-overlay rounded-[7px] mb-3 py-4 px-3.5 cursor-grab active:cursor-grabbing select-none border border-border dc-shadow hover:border-border-secondary transition-[box-shadow,border-color,opacity] duration-150 ease-[cubic-bezier(0.25,0.1,0.25,1)]"
    :class="isDragging ? 'opacity-40' : ''"
    @click="$emit('click')"
    @dragstart="onDragStart"
    @dragend="isDragging = false"
  >
    <h3 class="text-md text-foreground font-semibold leading-snug tracking-tight line-clamp-2">
      {{ row.title }}
    </h3>

    <div v-if="row.status" class="mt-2">
      <span class="inline-flex items-center px-2 py-0.5 rounded-xs text-xs font-semibold text-muted bg-default border border-border">
        {{ row.status }}
      </span>
    </div>

    <div v-if="row.labels?.length" class="mt-3 flex flex-col gap-1">
      <div v-for="l in row.labels" :key="l.label" class="flex items-center gap-1.5 text-sm">
        <span class="text-muted">{{ l.label }}:</span>
        <span class="text-foreground font-medium truncate">{{ l.value ?? '—' }}</span>
      </div>
    </div>

    <div v-if="row.date" class="mt-2">
      <span class="inline-flex items-center px-2 py-0.5 rounded-xs text-xs font-semibold text-muted bg-default border border-border">
        {{ fmtDate(row.date) }}
      </span>
    </div>

    <div class="flex items-center pr-2 justify-between mt-3">
      <span class="text-xs pt-[1px] font-semibold text-muted tracking-tight uppercase truncate">
        {{ row.name }}
      </span>
      <Avatar v-if="row.owner" :name="row.owner.full_name" size="xs" class="shrink-0" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Avatar } from '@/ui'

// Card for any non-BP-Task widget-source doctype — same container
// classes/spacing/shadow token as TaskCard.vue so it reads as the same
// family of card, fed from get_doctype_column_data's row shape instead of a
// BP Task's fields (no task-type icon/subtask progress-bar — those are
// Task-specific concepts other doctypes don't have).
const props = defineProps({
  row: { type: Object, required: true }, // { name, title, status, owner, date, labels: [{label,value}] }
})
defineEmits(['click'])

const isDragging = ref(false)
// Own drag payload key (not window.__dragIssue, TaskCard.vue's — a
// different shape, and keeping them distinct avoids any cross-talk if a
// Task-kanban and a generic-kanban widget are ever both on one page).
function onDragStart(e) {
  isDragging.value = true
  window.__dragKanbanRow = { row: props.row }
  e.dataTransfer.effectAllowed = 'move'
}

function fmtDate(d) {
  try { return new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) }
  catch { return d }
}
</script>

<style scoped>
.dc-shadow { box-shadow: var(--card-shadow); }
.dc-shadow:hover { box-shadow: var(--surface-shadow-hover); }
</style>
