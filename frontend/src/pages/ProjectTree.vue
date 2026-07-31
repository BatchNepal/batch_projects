<template>
  <div class="flex flex-col h-full bg-overlay overflow-hidden">
    <div class="px-6 pt-5 pb-0 border-b border-border flex-shrink-0">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h1 class="text-[15px] font-semibold text-foreground leading-tight">Project Hierarchy</h1>
          <p class="text-xs text-muted mt-0.5">WBS tree — parent/child project structure</p>
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

      <div v-else class="space-y-0.5">
        <div v-for="item in flatTree" :key="item.name"
          class="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer hover:bg-surface-secondary transition-colors"
          :style="{ paddingLeft: (item.depth * 20 + 12) + 'px' }"
          @click="openProject(item)"
        >
          <button v-if="item.hasChildren" class="size-4 flex items-center justify-center text-muted shrink-0"
            @click.stop="toggle(item.name)">
            <ChevronRight v-if="!expanded.has(item.name)" class="size-3.5" />
            <ChevronDown v-else class="size-3.5" />
          </button>
          <span v-else class="size-4 shrink-0" />

          <ProjectAvatar :theme="item.theme" :seed="item.key" size="xs" />

          <span class="text-[13px] font-medium text-foreground truncate flex-1 min-w-0">{{ item.project_name }}</span>
          <span class="text-[10.5px] font-bold text-muted font-mono">{{ item.key }}</span>
          <span v-if="item.status"
            class="text-[10.5px] font-semibold px-2 py-0.5 rounded-full"
            :class="statusClass(item.status)">{{ item.status }}</span>
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
import { Spinner, ProjectAvatar } from '@/ui'
import { FolderTree, ChevronRight, ChevronDown } from 'lucide-vue-next'

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
    out.push({
      name: n.name,
      project_name: n.project_name,
      key: n.key,
      status: n.status,
      color: n.color,
      depth,
      hasChildren,
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
