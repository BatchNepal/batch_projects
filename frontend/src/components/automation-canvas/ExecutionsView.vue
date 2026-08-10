<template>
  <div class="flex-1 min-w-0 overflow-y-auto p-4">
    <div v-if="loading" class="flex justify-center py-10">
      <Icon :icon="Loader2" :size="20" class="animate-spin text-muted" />
    </div>
    <p v-else-if="!runs.length" class="text-sm text-muted text-center py-10">
      No runs yet — save an active workflow and let its trigger fire, or use Test workflow.
    </p>
    <div v-else class="flex flex-col gap-2 max-w-2xl mx-auto">
      <div v-for="run in runs" :key="run.run_id" class="rounded-lg border border-border overflow-hidden">
        <button
          type="button"
          class="w-full flex items-center gap-2.5 px-3 py-2.5 text-left hover:bg-surface-hover transition-colors"
          @click="toggle(run.run_id)"
        >
          <ChevronRight :size="14" class="text-muted shrink-0 transition-transform" :class="expanded === run.run_id ? 'rotate-90' : ''" />
          <span
            :class="cn('size-2 rounded-full shrink-0', run.status === 'Failed' ? 'bg-danger' : 'bg-success')"
          />
          <span class="text-sm text-foreground flex-1 min-w-0 truncate">{{ fmtDate(run.started_at) }}</span>
          <span
            :class="cn('text-xs font-medium px-1.5 py-0.5 rounded-full',
                       run.status === 'Failed' ? 'bg-danger-soft text-danger-soft-foreground' : 'bg-success-soft text-success-soft-foreground')"
          >{{ run.status }}</span>
          <Button size="sm" variant="light" @click.stop="emit('view-run', run)">View on canvas</Button>
        </button>
        <div v-if="expanded === run.run_id" class="border-t border-border divide-y divide-border">
          <div v-for="n in run.nodes" :key="n.node_id" class="flex flex-col gap-1 px-3 py-2 pl-9">
            <div class="flex items-center gap-2.5">
              <span
                :class="cn('size-1.5 rounded-full shrink-0',
                           n.status === 'Failed' ? 'bg-danger' : n.status === 'Skipped' ? 'bg-muted-tertiary' : 'bg-success')"
              />
              <span class="text-xs text-foreground flex-1 min-w-0 truncate">{{ labelFor(n.node_id) }}</span>
              <span class="text-xs text-muted shrink-0">{{ n.status }}</span>
            </div>
            <!-- Full message, not truncated — this used to be a 160px-clipped
                 span (title-tooltip only), which is exactly the "where did
                 the error actually come from" the audit flagged as missing.
                 Retry-attempt info (see api/automation.py/graph.go) already
                 rides inside this same message string. -->
            <p v-if="n.message" class="text-xs pl-4" :class="n.status === 'Failed' ? 'text-danger' : 'text-muted'">
              {{ n.message }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Loader2, ChevronRight } from 'lucide-vue-next'
import Icon from '@/ui/Icon.vue'
import Button from '@/ui/Button.vue'
import { cn } from '@/lib/utils'
import { getWorkflowRuns } from '@/utils/api'

// Editor/Executions toggle (WORKPLAN-PHASE25 A4) — this component
// IS the "Executions" side, swapped in for the canvas area by the parent's
// own toolbar toggle (no drawer, per spec). `nodes` is the CURRENTLY LOADED
// graph (Vue Flow runtime nodes) purely for label lookup — BP Workflow Run
// only stores node_id/node_type, not a label, since labels are user-editable
// and re-derivable from the live graph rather than duplicated into every run row.
const props = defineProps({
  workflowName: { type: String, default: null },
  nodes:        { type: Array, default: () => [] },
})
const emit = defineEmits(['view-run'])

const runs = ref([])
const loading = ref(false)
const expanded = ref(null)

function labelFor(nodeId) {
  return props.nodes.find((n) => n.id === nodeId)?.data?.label || nodeId
}
function toggle(runId) {
  expanded.value = expanded.value === runId ? null : runId
}
function fmtDate(s) {
  try {
    return new Date(s).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
  } catch { return s }
}

async function load() {
  if (!props.workflowName) { runs.value = []; return }
  loading.value = true
  try {
    runs.value = await getWorkflowRuns(props.workflowName)
  } catch {
    runs.value = []
  } finally {
    loading.value = false
  }
}
defineExpose({ load })
onMounted(load)
</script>
