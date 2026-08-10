<template>
  <Modal :open="!!store.pendingBlock" @update:open="onToggle" size="sm" :radius="'xl'" hideCloseButton>
    <div v-if="store.pendingBlock" class="p-5 w-full">
      <div class="flex items-start gap-3 mb-4">
        <span class="shrink-0 w-9 h-9 rounded-lg grid place-items-center bg-warning-soft text-warning-soft-foreground">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.7 3.86a2 2 0 0 0-3.4 0z"/></svg>
        </span>
        <div class="min-w-0">
          <h3 class="text-md font-semibold text-foreground leading-tight">Complete this blocked task?</h3>
          <p class="text-base text-muted mt-1">It's blocked by {{ blockers.length }} unfinished {{ blockers.length === 1 ? 'task' : 'tasks' }}.</p>
        </div>
      </div>
      <ul class="space-y-1.5 mb-5 max-h-44 overflow-y-auto">
        <li v-for="b in blockers" :key="b.name" class="flex items-center gap-2 px-2.5 py-2 rounded-md bg-surface-secondary border border-separator">
          <span class="text-xs font-mono font-semibold text-muted shrink-0">{{ b.task_key }}</span>
          <span class="flex-1 truncate text-base text-foreground">{{ b.title }}</span>
          <span class="text-xs font-medium px-1.5 py-0.5 rounded shrink-0" :style="{ background: wfColor(b.status) + '1A', color: wfColor(b.status) }">{{ b.status }}</span>
        </li>
      </ul>
      <div class="flex justify-end gap-2">
        <button class="h-8 px-3.5 rounded-md text-base font-medium text-foreground hover:bg-default transition-colors" @click="store.cancelBlockedStatus()">Cancel</button>
        <button class="h-8 px-3.5 rounded-md text-base font-semibold text-accent-foreground bg-accent hover:bg-[var(--accent-hover)] transition-colors" @click="store.confirmBlockedStatus()">Mark done anyway</button>
      </div>
    </div>
  </Modal>
</template>

<script setup>
import { computed } from 'vue'
import Modal from '@/ui/Modal.vue'
import { useProjectStore } from '@/stores/project'

const store = useProjectStore()
const blockers = computed(() => store.pendingBlock?.blockers || [])
function wfColor(s) { return store.workflowStateMap?.[s]?.color || 'var(--muted)' }
function onToggle(v) { if (!v) store.cancelBlockedStatus() }
</script>
