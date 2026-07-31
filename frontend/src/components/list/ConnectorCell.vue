<template>
  <FieldDropdown width="w-80" :close-on-select="false">
    <template #trigger>
      <button class="cc-trigger" title="Connected tasks (across projects)">
        <template v-if="relations.length">
          <span v-for="l in relations.slice(0, 2)" :key="l.linked_task" class="cc-chip" :style="chipStyle(l)"
            :title="projLabel(l.linked_task_project) + ' · ' + l.linked_task_title + ' — ' + (l.linked_task_status || '')">
            <span class="cc-st-dot" :style="{ background: statusColor(l) }" />
            {{ l.linked_task_key }}
          </span>
          <span v-if="relations.length > 2" class="cc-more">+{{ relations.length - 2 }}</span>
        </template>
        <span v-else class="cc-empty">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>
          Connect
        </span>
      </button>
    </template>

    <div class="cc-panel" @click.stop>
      <input v-model="q" class="hui-field cc-search" placeholder="Search tasks in any project…" @input="onSearch" />
      <div class="cc-results">
        <div v-if="searching" class="cc-note">Searching…</div>
        <template v-else-if="results.length">
          <button v-for="t in results" :key="t.name" class="cc-result" @click="add(t)">
            <span class="cc-pj" :style="{ background: projColor(t.project) }">{{ t.project_key || projKey(t.project) }}</span>
            <span class="cc-result-key">{{ t.task_key }}</span>
            <span class="cc-result-title">{{ t.title }}</span>
          </button>
        </template>
        <div v-else-if="q" class="cc-note">No tasks found.</div>
        <div v-else class="cc-note">Link a task from this or another project.</div>
      </div>

      <template v-if="relations.length">
        <div class="cc-sep" />
        <p class="cc-hdr">Connected tasks</p>
        <div v-for="l in relations" :key="l.linked_task" class="cc-linked">
          <span class="cc-pj" :style="{ background: projColor(l.linked_task_project) }">{{ projKey(l.linked_task_project) }}</span>
          <span class="cc-linked-label">{{ l.linked_task_key }} · {{ l.linked_task_title }}</span>
          <span v-if="l.linked_task_status" class="cc-st-pill" :style="stPillStyle(l)">
            <span class="cc-st-dot" :style="{ background: statusColor(l) }" />{{ l.linked_task_status }}
          </span>
          <button class="cc-x cc-open" title="Open task" @click="store.openTaskDetail(l.linked_task)">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path stroke-linecap="round" stroke-linejoin="round" d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6m4-3h6m0 0v6m0-6L10 14"/></svg>
          </button>
          <button class="cc-x" title="Unlink" @click="remove(l)">
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
import { searchTasksGlobal, addTaskLink, removeTaskLink } from '@/utils/api'

const props = defineProps({
  issue: { type: Object, required: true },
})
const store = useProjectStore()

const q = ref('')
const results = ref([])
const searching = ref(false)
let timer = null

// "relates to" is the generic connector relation (cross-project allowed).
const relations = computed(() => (props.issue.links || []).filter(l => l.link_type === 'relates to'))

function proj(name) { return (store.projects || []).find(p => p.name === name) }
function projKey(name) { return (proj(name)?.key || name || '?').slice(0, 4).toUpperCase() }
function projLabel(name) { return proj(name)?.project_name || name || 'Project' }
function projColor(name) { return proj(name)?.project_color || 'var(--muted)' }

// Resolve the linked task's status colour from ITS OWN project workflow
// (cross-project: each board can define its own states/colours).
function statusColor(l) {
  const p = proj(l.linked_task_project)
  const st = (p?.workflow_states || []).find(s => s.name === l.linked_task_status)
  return st?.color
    || store.workflowStateMap?.[l.linked_task_status]?.color
    || 'var(--muted)'
}
function chipStyle(l) {
  const c = statusColor(l)
  return { background: `color-mix(in srgb, ${c} 16%, transparent)` }
}
function stPillStyle(l) {
  const c = statusColor(l)
  return { background: `color-mix(in srgb, ${c} 16%, transparent)`, color: `color-mix(in srgb, ${c} 75%, var(--foreground))` }
}

function onSearch() {
  clearTimeout(timer)
  const query = q.value.trim()
  if (!query) { results.value = []; return }
  searching.value = true
  timer = setTimeout(async () => {
    try {
      results.value = (await searchTasksGlobal(query, props.issue.name)) || []
    } catch { results.value = [] }
    finally { searching.value = false }
  }, 250)
}

async function add(t) {
  try {
    await addTaskLink(props.issue.name, t.name, 'relates to')
    props.issue.links = [
      ...(props.issue.links || []),
      { link_type: 'relates to', linked_task: t.name, linked_task_key: t.task_key,
        linked_task_title: t.title, linked_task_status: t.status, linked_task_project: t.project },
    ]
    q.value = ''; results.value = []
  } catch (e) {
    toast.error("Couldn't connect task", { description: String(e.message || e) })
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
.cc-trigger{display:inline-flex;align-items:center;gap:4px;min-height:26px;max-width:100%;padding:0 4px;background:none;border:none;cursor:pointer;font-family:inherit}
.cc-chip{display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 8px;font-size:11.5px;font-weight:600;font-family:var(--font-mono);color:var(--foreground);border-radius:2px;white-space:nowrap}
.cc-st-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.cc-st-pill{display:inline-flex;align-items:center;gap:4px;height:18px;padding:0 7px;border-radius:2px;font-size:10px;font-weight:600;white-space:nowrap;flex-shrink:0}
.cc-more{font-size:11px;font-weight:600;color:var(--muted)}
.cc-pj{display:inline-flex;align-items:center;justify-content:center;min-width:24px;height:16px;padding:0 4px;border-radius:2px;font-size:9px;font-weight:700;font-family:var(--font-mono);color:var(--accent-foreground);letter-spacing:.02em;flex-shrink:0}
.cc-empty{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--muted);opacity:0;transition:opacity .12s}
:global(.lv-row:hover) .cc-empty{opacity:1}
.cc-panel{padding:8px;min-width:300px}
.cc-search{width:100%;height:30px;font-size:12.5px;padding:0 8px;font-family:inherit;color:var(--foreground);outline:none}
.cc-results{max-height:180px;overflow-y:auto;margin-top:6px}
.cc-result{display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:5px 8px;border:none;background:none;border-radius:5px;cursor:pointer;font-family:inherit}
.cc-result:hover{background:var(--default)}
.cc-result-key{font-size:11px;font-weight:600;font-family:var(--font-mono);color:var(--muted);flex-shrink:0}
.cc-result-title{font-size:12.5px;color:var(--foreground);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cc-note{font-size:12px;color:var(--muted);padding:8px;text-align:center}
.cc-sep{height:1px;background:var(--separator);margin:8px 0 6px}
.cc-hdr{font-size:10.5px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin:0 0 4px;padding:0 2px}
.cc-linked{display:flex;align-items:center;gap:6px;padding:3px 4px;border-radius:5px}
.cc-linked:hover{background:var(--surface-secondary)}
.cc-linked-label{flex:1;font-size:12.5px;color:var(--foreground);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cc-x{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:none;background:none;border-radius:4px;color:var(--muted);cursor:pointer}
.cc-x:hover{background:var(--danger-soft);color:var(--danger)}
.cc-open:hover{background:var(--surface-secondary);color:var(--foreground)}
</style>
