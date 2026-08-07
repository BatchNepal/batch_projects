<template>
  <KanbanColumnShell
    :title="title"
    :count="issues.length"
    :color="color"
    :collapsed="collapsed"
    @update:collapsed="collapsed = $event"
    :drag-over="isDragOver"
  >
    <template #header-actions>
      <button
        @click="$emit('add', title)"
        class="w-6 h-6 flex items-center justify-center rounded-md text-muted hover:text-foreground hover:bg-default transition-colors"
        title="Add task"
      >
        <Plus class="size-3.5" />
      </button>
    </template>

    <div
      ref="dropZone"
      class="flex-1 flex flex-col gap-0 rounded-lg transition-colors duration-200 min-h-[150px] relative"
      :class="isDragOver ? 'bg-default' : ''"
      @dragover.prevent="onDragOver"
      @dragenter.prevent="isDragOver = true"
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
    >
      <div class="flex-1 pb-1">
        <TransitionGroup name="task-list" tag="div" class="task-list-wrap">
          <TaskCard
            v-for="(issue, idx) in visibleIssues"
            :key="issue.name"
            :issue="issue"
            :index="idx"
            :mirror-chips="mirrorChips ? mirrorChips(issue) : []"
            @click="$emit('click-issue', issue.name)"
            @dragstart="onDragStart(issue, idx)"
            @context-menu="e => emit('context-menu', e)"
            @open-erp-doc="(dt, n) => emit('open-erp-doc', dt, n)"
          />
        </TransitionGroup>

        <Transition name="kc-empty">
          <div
            v-if="!issues.length"
            class="flex flex-col items-center justify-center h-24 mt-2 border-2 border-dashed border-border-secondary rounded-lg"
            :class="isDragOver ? 'opacity-0' : 'opacity-100'"
          >
            <span class="text-[12px] font-medium text-muted">No tasks</span>
          </div>
        </Transition>

        <button
          v-if="hiddenCount > 0"
          class="w-full mt-2 py-2 text-[12px] font-medium text-muted hover:text-foreground hover:bg-default rounded-md transition-colors border border-transparent hover:border-border-secondary"
          @click="showAll = !showAll"
        >
          {{
            showAll
              ? '↑ Show less'
              : `↓ Show ${hiddenCount} more ${
                  isCompletedCol ? 'completed ' : ''
                }issues`
          }}
        </button>
      </div>
    </div>
  </KanbanColumnShell>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Plus } from 'lucide-vue-next'
import KanbanColumnShell from '@/components/KanbanColumnShell.vue'
import TaskCard from '@/components/TaskCard.vue'
import { useProjectStore } from '@/stores/project'

const DONE_CAP = 15

const props = defineProps({
  title: String,
  issues: { type: Array, default: () => [] },
  color: { type: String, default: null },
  mirrorChips: { type: Function, default: null }
})

const emit = defineEmits([
  'move',
  'click-issue',
  'add',
  'context-action',
  'context-menu',
  'open-erp-doc'
])
const store = useProjectStore()
const isDragOver = ref(false)
const dropZone = ref(null)
const collapsed = ref(false)
const showAll = ref(false)
let leaveTimer = null

const isCompletedCol = computed(
  () => store.workflowStateMap?.[props.title]?.category === 'completed'
)

const visibleIssues = computed(() => {
  const list = props.issues.filter(Boolean)
  if (!isCompletedCol.value || showAll.value) return list
  return list.slice(0, DONE_CAP)
})

const hiddenCount = computed(() => {
  if (!isCompletedCol.value || showAll.value) return 0
  return Math.max(0, props.issues.filter(Boolean).length - DONE_CAP)
})

function onDragStart (issue, index) {
  window.__dragIssue = { issue, fromStatus: props.title, fromIndex: index }
}

function onDragOver (e) {
  e.preventDefault()
  e.dataTransfer.dropEffect = 'move'
  isDragOver.value = true
  if (leaveTimer) {
    clearTimeout(leaveTimer)
    leaveTimer = null
  }
}

function onDragLeave (e) {
  leaveTimer = setTimeout(() => {
    if (!dropZone.value?.contains(e.relatedTarget)) isDragOver.value = false
  }, 50)
}

function onDrop (e) {
  isDragOver.value = false
  const dragData = window.__dragIssue
  if (!dragData) return
  window.__dragIssue = null
  // Apply any remote event that arrived on this card while it was being
  // dragged (queued by the store instead of yanking it mid-gesture).
  store.flushDeferredRealtimeEvent(dragData.issue.name)
  const cards = Array.from(
    dropZone.value?.querySelectorAll('[data-issue]') || []
  )
  let newIndex = cards.length
  for (let i = 0; i < cards.length; i++) {
    const rect = cards[i].getBoundingClientRect()
    if (e.clientY < rect.top + rect.height / 2) {
      newIndex = i
      break
    }
  }
  emit('move', { issue: dragData.issue, newStatus: props.title, newIndex })
}
</script>

<style scoped>
/* Task card list enter/leave/move */
.task-list-wrap { position: relative; }

.task-list-enter-active {
  transition: opacity 0.22s ease, transform 0.22s cubic-bezier(0.22, 1, 0.36, 1);
}
.task-list-leave-active {
  transition: opacity 0.14s ease;
  position: absolute;
  left: 0; right: 0;
  pointer-events: none;
}
.task-list-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.task-list-leave-to { opacity: 0; }
.task-list-move {
  transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

/* Empty state fade */
.kc-empty-enter-active { transition: opacity 0.2s ease 0.1s; }
.kc-empty-leave-active { transition: opacity 0.1s ease; }
.kc-empty-enter-from,
.kc-empty-leave-to { opacity: 0; }
</style>
