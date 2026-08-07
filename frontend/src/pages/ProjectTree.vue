<template>
  <div class="flex flex-col h-full bg-overlay overflow-hidden">
    <div class="px-6 pt-5 pb-0 border-b border-border flex-shrink-0">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h1 class="text-[15px] font-semibold text-foreground leading-tight">Project Hierarchy</h1>
          <p class="text-xs text-muted mt-0.5">WBS tree — parent/child project structure, with delivery status per node</p>
        </div>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto px-6 py-4">
      <div v-if="loading" class="flex items-center justify-center py-16">
        <Spinner class="w-5 h-5 text-primary" />
      </div>

      <div v-else-if="!flatTree.length" class="flex flex-col items-center py-16 text-muted">
        <GitBranch class="size-8 mb-3 opacity-40" />
        <p class="text-sm font-medium">No projects</p>
        <p class="text-xs mt-1">Create a project to see the hierarchy.</p>
      </div>

      <div v-else class="max-w-[1600px] mx-auto">
        <div v-for="item in flatTree" :key="item.name" class="pt-row" :style="{ paddingLeft: (item.depth * 24) + 'px' }">
          <!-- tree connector guides, one per ancestor depth level -->
          <span v-for="d in item.depth" :key="d" class="pt-guide" :style="{ left: ((d - 1) * 24 + 19) + 'px' }" />

          <div class="pt-row-content" @click="openProject(item)">
            <button v-if="item.hasChildren" class="pt-toggle" @click.stop="toggle(item.name)">
              <ChevronRight v-if="!expanded.has(item.name)" class="size-3.5" />
              <ChevronDown v-else class="size-3.5" />
            </button>
            <span v-else class="pt-toggle-spacer" />

            <ProjectAvatar :theme="item.theme" :seed="item.key" size="xs" />

            <div class="pt-identity">
              <span class="pt-name">{{ item.project_name }}</span>
              <span class="pt-key">{{ item.key }}</span>
            </div>

            <span v-if="item.leadName" class="pt-lead" :title="`Lead: ${item.leadName}`">
              <Avatar :name="item.leadName" size="xs" />
              <span class="pt-lead-name">{{ item.leadName }}</span>
            </span>

            <span v-if="item.taskCount" class="pt-progress" :title="`${item.doneCount} of ${item.taskCount} tasks done`">
              <span class="pt-progress-track">
                <span class="pt-progress-fill" :style="{ width: item.progressPct + '%' }" />
              </span>
              <span class="pt-progress-label">{{ item.doneCount }}/{{ item.taskCount }}</span>
            </span>
            <span v-else class="pt-progress pt-progress-empty">No tasks</span>

            <DueDateChip v-if="item.dueDate" :date="item.dueDate" />

            <span v-if="item.status" class="pt-status" :class="statusClass(item.status)">{{ item.status }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { getProjectTree } from '@/utils/api'
import { Spinner, ProjectAvatar, Avatar, DueDateChip } from '@/ui'
import { GitBranch, ChevronRight, ChevronDown } from 'lucide-vue-next'

const router = useRouter()
const store = useProjectStore()
const loading = ref(true)
const tree = ref([])
const expanded = ref(new Set())

function toggle(name) {
  const s = new Set(expanded.value)
  s.has(name) ? s.delete(name) : s.add(name)
  expanded.value = s
}

function openProject(item) {
  router.push(store.projectLanding(item.key))
}

function statusClass(s) {
  if (s === 'Active') return 'bg-success-soft text-success-soft-foreground'
  if (s === 'On Hold') return 'bg-warning-soft text-warning-soft-foreground'
  if (s === 'Archived') return 'bg-default text-muted'
  return 'bg-default text-muted'
}

function flatten(nodes, depth) {
  const out = []
  for (const n of nodes) {
    const hasChildren = n.children?.length
    const taskCount = n.task_count || 0
    const doneCount = n.done_count || 0
    out.push({
      name: n.name,
      project_name: n.project_name,
      key: n.key,
      status: n.status,
      color: n.color,
      theme: n.theme,
      depth,
      hasChildren,
      taskCount,
      doneCount,
      progressPct: taskCount ? Math.round((doneCount / taskCount) * 100) : 0,
      leadName: n.lead_name || null,
      dueDate: n.target_end_date || null,
    })
    if (hasChildren && expanded.value.has(n.name)) {
      out.push(...flatten(n.children, depth + 1))
    }
  }
  return out
}

const flatTree = computed(() => flatten(tree.value, 0))

async function load() {
  loading.value = true
  try {
    tree.value = await getProjectTree()
    // Auto-expand root level
    for (const n of tree.value) expanded.value.add(n.name)
  } catch (e) { tree.value = [] }
  finally { loading.value = false }
}

onMounted(load)
</script>

<style scoped>
.pt-row { position: relative; }

/* Vertical guide line for each ancestor level — the actual "tree" look;
   plain indentation alone reads as a generic bulleted list, not a WBS. */
.pt-guide { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--border); }

.pt-row-content {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; margin: 1px 0; border-radius: 8px;
  cursor: pointer; transition: background-color .12s;
}
.pt-row-content:hover { background: var(--surface-secondary); }

.pt-toggle { width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; color: var(--muted); flex-shrink: 0; }
.pt-toggle-spacer { width: 16px; flex-shrink: 0; }

.pt-identity { display: flex; align-items: baseline; gap: 6px; min-width: 0; flex: 1 1 260px; }
.pt-name { font-size: 13px; font-weight: 500; color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pt-key { font-size: 10.5px; font-weight: 700; color: var(--muted); font-family: monospace; flex-shrink: 0; }

.pt-lead { display: flex; align-items: center; gap: 5px; flex-shrink: 0; width: 132px; }
.pt-lead-name { font-size: 11.5px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.pt-progress { display: flex; align-items: center; gap: 6px; flex-shrink: 0; width: 96px; }
.pt-progress-empty { font-size: 11px; color: var(--muted); width: auto; }
.pt-progress-track { width: 48px; height: 4px; border-radius: 2px; background: var(--surface-secondary); overflow: hidden; flex-shrink: 0; }
.pt-progress-fill { display: block; height: 100%; background: var(--success); border-radius: 2px; }
.pt-progress-label { font-size: 10.5px; color: var(--muted); font-variant-numeric: tabular-nums; }

.pt-status { font-size: 10.5px; font-weight: 600; padding: 2px 8px; border-radius: 999px; flex-shrink: 0; }
</style>
