<template>
  <div
    class="group flex items-center gap-2.5 px-4 h-10 hover:bg-surface-secondary transition-colors cursor-pointer select-none"
    @click="emit('click', task)"
  >
    <!-- Priority signal -->
    <PriorityIcon :priority="task.priority" class="shrink-0" />

    <!-- Status badge -->
    <StatusBadge :label="task.status" :status="task.status" class="shrink-0" />

    <!-- Task title — main content -->
    <p class="flex-1 text-sm text-foreground truncate leading-none">{{ task.title }}</p>

    <!-- Due date -->
    <DueDateChip :date="task.due_date" class="shrink-0" />

    <!-- Subtask progress bar -->
    <div v-if="task.subtask_count" class="shrink-0 w-16">
      <InlineProgress :value="subtaskPct" size="xs" />
    </div>

    <!-- Assignee avatar -->
    <div v-if="task.assignee_color || task.assignee_initials"
      class="shrink-0 size-5 rounded-full flex items-center justify-center text-white text-[9px] font-bold"
      :style="{ backgroundColor: task.assignee_color || 'var(--muted)' }"
      :title="task.assignee"
    >{{ task.assignee_initials || '?' }}</div>

    <!-- Hover actions -->
    <div class="shrink-0 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
      <button type="button" title="Mark done" class="p-1 rounded text-muted hover:text-green-500 transition-colors"
        @click.stop="emit('done', task)">
        <svg class="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
        </svg>
      </button>
      <button type="button" title="More options" class="p-1 rounded text-muted hover:text-muted transition-colors"
        @click.stop="emit('menu', task)">
        <svg class="size-3.5" fill="currentColor" viewBox="0 0 24 24">
          <circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import PriorityIcon from '@/components/PriorityIcon.vue'
import StatusBadge from '@/ui/StatusBadge.vue'
import DueDateChip from '@/ui/DueDateChip.vue'
import InlineProgress from '@/ui/InlineProgress.vue'

const props = defineProps({
  task: { type: Object, required: true },
  // task shape: { title, status, priority, due_date, assignee, assignee_initials, assignee_color, subtask_count, subtask_done }
})
const emit = defineEmits(['click', 'done', 'menu'])

const subtaskPct = computed(() => {
  const t = props.task
  if (!t.subtask_count) return 0
  return Math.round(((t.subtask_done || 0) / t.subtask_count) * 100)
})
</script>
