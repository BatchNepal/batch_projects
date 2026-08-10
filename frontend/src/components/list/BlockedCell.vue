<template>
  <FieldDropdown width="w-72" :close-on-select="false">
    <template #trigger>
      <button class="bc-trigger" title="Blocking tasks">
        <template v-if="blockers.length">
          <span v-for="l in blockers.slice(0, 2)" :key="l.linked_task" class="bc-chip"
            :title="l.linked_task_title + ' — ' + l.linked_task_status">
            <span class="bc-dot" :style="{ background: statusColor(l.linked_task_status) }" />
            {{ l.linked_task_key }}
          </span>
          <span v-if="blockers.length > 2" class="bc-more">+{{ blockers.length - 2 }}</span>
        </template>
        <span v-else class="bc-empty">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
          Link
        </span>
      </button>
    </template>

    <div class="bc-panel" @click.stop>
      <input v-model="q" class="hui-field bc-search" placeholder="Search tasks…" @input="onSearch" />
      <div class="bc-results">
        <div v-if="searching" class="bc-note">Searching…</div>
        <template v-else-if="results.length">
          <button v-for="t in results" :key="t.name" class="bc-result" @click="add(t)">
            <span class="bc-result-key">{{ t.task_key }}</span>
            <span class="bc-result-title">{{ t.title }}</span>
          </button>
        </template>
        <div v-else-if="q" class="bc-note">No tasks found.</div>
        <div v-else class="bc-note">Type to find the task blocking this one.</div>
      </div>

      <template v-if="blockers.length">
        <div class="bc-sep" />
        <p class="bc-hdr">Blocked by</p>
        <div v-for="l in blockers" :key="l.linked_task" class="bc-linked">
          <span class="bc-dot" :style="{ background: statusColor(l.linked_task_status) }" />
          <span class="bc-linked-label">{{ l.linked_task_key }} · {{ l.linked_task_title }}</span>
          <button class="bc-x bc-open" title="Open task" @click="store.openTaskDetail(l.linked_task)">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path stroke-linecap="round" stroke-linejoin="round" d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6m4-3h6m0 0v6m0-6L10 14"/></svg>
          </button>
          <button class="bc-x" title="Unlink" @click="remove(l)">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
      </template>
    </div>
  </FieldDropdown>
</template>

<script setup>
import { ref, computed } from 'vue'
import { toast } from 'vue-sonner'
import FieldDropdown from '@/components/FieldDropdown.vue'
import { useProjectStore } from '@/stores/project'
import { searchTasks, addTaskLink, removeTaskLink } from '@/utils/api'

const props = defineProps({
  issue: { type: Object, required: true },
})
const store = useProjectStore()

const q = ref('')
const results = ref([])
const searching = ref(false)
let timer = null

const blockers = computed(() => (props.issue.links || []).filter(l => l.link_type === 'is blocked by'))

function statusColor(s) { return store.workflowStateMap?.[s]?.color || 'var(--muted)' }

function onSearch() {
  clearTimeout(timer)
  const query = q.value.trim()
  if (!query) { results.value = []; return }
  searching.value = true
  timer = setTimeout(async () => {
    try {
      results.value = (await searchTasks(query, store.currentProject?.name, props.issue.name)) || []
    } catch { results.value = [] }
    finally { searching.value = false }
  }, 250)
}

async function add(t) {
  try {
    await addTaskLink(props.issue.name, t.name, 'is blocked by')
    props.issue.links = [
      ...(props.issue.links || []),
      { link_type: 'is blocked by', linked_task: t.name, linked_task_key: t.task_key,
        linked_task_title: t.title, linked_task_status: t.status },
    ]
    q.value = ''; results.value = []
  } catch (e) {
    toast.error("Couldn't link task", { description: String(e.message || e) })
  }
}

async function remove(l) {
  const prev = props.issue.links
  props.issue.links = prev.filter(x => x !== l)
  try {
    await removeTaskLink(props.issue.name, l.linked_task, l.link_type)
  } catch (e) {
    props.issue.links = prev
    toast.error("Couldn't unlink", { description: String(e.message || e) })
  }
}
</script>

<style scoped>
.bc-trigger{display:inline-flex;align-items:center;gap:4px;min-height:26px;max-width:100%;padding:0 4px;background:none;border:none;cursor:pointer;font-family:inherit}
.bc-chip{display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 8px;font-size:var(--text-sm);font-weight:500;font-family:var(--font-mono);color:var(--foreground);background:var(--surface-secondary);border-radius:2px;white-space:nowrap}
.bc-more{font-size:var(--text-xs);color:var(--muted)}
.bc-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.bc-empty{display:inline-flex;align-items:center;gap:5px;font-size:var(--text-sm);color:var(--muted);opacity:0;transition:opacity .12s}
:global(.lv-row:hover) .bc-empty{opacity:1}
.bc-panel{padding:8px;min-width:260px}
.bc-search{width:100%;height:30px;font-size:var(--text-sm);padding:0 8px;font-family:inherit;color:var(--foreground);outline:none}
.bc-results{max-height:160px;overflow-y:auto;margin-top:6px}
.bc-result{display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:5px 8px;border:none;background:none;border-radius:5px;cursor:pointer;font-family:inherit}
.bc-result:hover{background:var(--default)}
.bc-result-key{font-size:var(--text-xs);font-weight:600;font-family:var(--font-mono);color:var(--muted);flex-shrink:0}
.bc-result-title{font-size:var(--text-sm);color:var(--foreground);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bc-note{font-size:var(--text-sm);color:var(--muted);padding:8px;text-align:center}
.bc-sep{height:1px;background:var(--separator);margin:8px 0 6px}
.bc-hdr{font-size:var(--text-xs);font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin:0 0 4px;padding:0 2px}
.bc-linked{display:flex;align-items:center;gap:6px;padding:3px 4px;border-radius:5px}
.bc-linked:hover{background:var(--surface-secondary)}
.bc-linked-label{flex:1;font-size:var(--text-sm);color:var(--foreground);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bc-x{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:none;background:none;border-radius:4px;color:var(--muted);cursor:pointer}
.bc-x:hover{background:var(--danger-soft);color:var(--danger)}
.bc-open:hover{background:var(--surface-secondary);color:var(--foreground)}
</style>
