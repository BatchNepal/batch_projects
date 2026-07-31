<template>
  <div
    v-if="collapsed"
    class="group flex flex-col items-center w-12 shrink-0 bg-background-secondary rounded-xl py-4 self-stretch cursor-pointer select-none hover:bg-default transition-colors duration-200 border border-transparent hover:border-border-secondary"
    @click="collapsed = false"
    :title="`${title} (${issues.length})`"
  >
    <button
      class="mb-4 opacity-0 group-hover:opacity-100 transition-opacity text-muted hover:text-muted"
    >
      <ChevronRight class="size-3.5" />
    </button>
    <span
      class="text-[11px] font-semibold text-muted uppercase tracking-[0.15em]"
      style="writing-mode: vertical-rl; transform: rotate(180deg)"
    >
      {{ title }}
    </span>
    <span
      class="mt-3 text-[10px] font-bold text-muted bg-overlay border border-border shadow-sm rounded-full w-5 h-5 flex items-center justify-center"
    >
      {{ issues.length }}
    </span>
  </div>

  <div
    v-else
    class="flex flex-col w-[330px] shrink-0 rounded-sm p-2.5 self-stretch border transition-colors duration-150"
    :class="isDragOver ? 'bg-accent-soft border-accent' : 'bg-background-secondary border-border'"
  >
    <div class="flex items-center justify-between mb-2.5 px-1.5 pb-2.5 pt-1 group">
      <div class="flex items-center gap-2.5">
        <div class="flex items-center gap-2">
          <span v-if="color" class="inline-block size-2 rounded-full shrink-0" :style="{ background: color }" />
          <p class="text-[13px] font-semibold text-foreground uppercase">
            {{ title }}
          </p>
        </div>

        <Transition name="kc-count" mode="out-in">
          <span
            :key="issues.length"
            class="text-[11px] font-medium text-muted px-2 py-0.5 rounded-full bg-default min-w-[20px] text-center"
          >
            {{ issues.length }}
          </span>
        </Transition>
      </div>
      <div
        class="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <button
          @click="$emit('add', title)"
          class="w-6 h-6 flex items-center justify-center rounded-md text-muted hover:text-foreground hover:bg-default transition-colors"
          title="Add task"
        >
          <Plus class="size-3.5" />
        </button>
        <button
          class="opacity-0 group-hover:opacity-100 transition-opacity w-5 h-5 flex items-center justify-center rounded-md text-muted hover:text-foreground hover:bg-default -ml-1"
          @click.stop="collapsed = true"
          title="Collapse column"
        >
          <ChevronLeft class="size-3" />
        </button>
      </div>
    </div>

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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ChevronRight, ChevronLeft, Plus } from 'lucide-vue-next'
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

/* Count badge number flip */
.kc-count-enter-active,
.kc-count-leave-active { transition: opacity 0.12s ease, transform 0.12s ease; }
.kc-count-enter-from { opacity: 0; transform: translateY(4px) scale(0.85); }
.kc-count-leave-to   { opacity: 0; transform: translateY(-4px) scale(0.85); }

/* Empty state fade */
.kc-empty-enter-active { transition: opacity 0.2s ease 0.1s; }
.kc-empty-leave-active { transition: opacity 0.1s ease; }
.kc-empty-enter-from,
.kc-empty-leave-to { opacity: 0; }
</style>
