<template>
  <div class="flex flex-col h-full bg-overlay overflow-hidden">
    <div class="px-6 pt-5 pb-0 border-b border-border flex-shrink-0">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h1 class="text-[15px] font-semibold text-foreground leading-tight">Triage</h1>
          <p class="text-xs text-muted mt-0.5">Tasks that need review and assignment</p>
        </div>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto px-6 py-4">
      <div v-if="loading" class="flex items-center justify-center py-16">
        <Spinner class="w-5 h-5 text-primary" />
      </div>

      <div v-else-if="!tasks.length" class="flex flex-col items-center py-16 text-muted">
        <Inbox class="size-8 mb-3 opacity-40" />
        <p class="text-sm font-medium">All clear</p>
        <p class="text-xs mt-1">No tasks waiting for triage.</p>
      </div>

      <div v-else class="space-y-1">
        <div v-for="t in tasks" :key="t.name"
          class="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-surface-secondary cursor-pointer transition-colors"
          @click="store.openTaskDetail(t.name)">
          <span class="flex items-center justify-center size-6 rounded text-[10px] font-bold shrink-0"
            :style="{ background: typeColor(t.task_type) + '20', color: typeColor(t.task_type) }">
            {{ (t.task_type || 'T').charAt(0) }}
          </span>
          <div class="flex-1 min-w-0">
            <div class="text-[13px] font-medium text-foreground truncate">{{ t.title }}</div>
            <div class="flex items-center gap-2 text-[11px] text-muted mt-0.5">
              <span class="font-mono font-semibold">{{ t.task_key }}</span>
              <span>{{ t.project_name }}</span>
              <template v-if="t.assignees?.length">
                <span>·</span>
                <span>{{ t.assignees.map(a => a.full_name).join(', ') }}</span>
              </template>
            </div>
          </div>
          <PriorityIcon :priority="t.priority" />
          <button class="text-[11px] font-semibold text-accent hover:underline shrink-0"
            @click.stop="doTriaged(t)">Mark triaged</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useProjectStore } from '@/stores/project'
import { getTriageQueue, markTriaged } from '@/utils/api'
import { Spinner, PriorityIcon } from '@/ui'
import { Inbox } from 'lucide-vue-next'

const store = useProjectStore()
const loading = ref(true)
const tasks = ref([])

const TYPE_COLORS = {
  Task: '#0B6BCB', Bug: '#C41C1C', Story: '#7C3AED',
  Epic: '#0F766E', Deliverable: '#B45309', Milestone: '#BE185D',
}
function typeColor(t) { return TYPE_COLORS[t] || '#636B74' }

async function load() {
  loading.value = true
  try { tasks.value = await getTriageQueue() }
  catch (e) { tasks.value = [] }
  finally { loading.value = false }
}

async function doTriaged(t) {
  try {
    await markTriaged(t.name)
    tasks.value = tasks.value.filter(x => x.name !== t.name)
  } catch (e) { console.error(e) }
}

onMounted(load)
</script>
