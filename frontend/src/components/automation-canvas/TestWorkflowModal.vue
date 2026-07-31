<template>
  <Modal :open="open" size="sm" @update:open="emit('update:open', $event)">
    <ModalHeader title="Test workflow" subtitle="Fires the real trigger against a task — actions run for real, same as a genuine event." />
    <ModalBody>
      <Input
        v-model="query" placeholder="Search tasks…" size="sm"
        @update:model-value="onSearch"
      />
      <div v-if="searching" class="flex justify-center py-4">
        <Icon :icon="Loader2" :size="16" class="animate-spin text-muted" />
      </div>
      <p v-else-if="!results.length" class="text-[12px] text-muted text-center py-4">
        {{ query ? 'No matching tasks.' : 'No tasks in scope yet.' }}
      </p>
      <div v-else class="flex flex-col gap-0.5 max-h-72 overflow-y-auto">
        <button
          v-for="t in results" :key="t.name" type="button"
          class="flex items-center gap-2 px-2.5 py-2 rounded-md text-left hover:bg-surface-hover transition-colors"
          @click="emit('select', t.name)"
        >
          <span class="min-w-0 flex-1">
            <p class="text-sm text-foreground truncate">{{ t.title }}</p>
            <p class="text-xs text-muted truncate">
              {{ t.task_key }} · {{ t.status }}<span v-if="t.project_name"> · {{ t.project_name }}</span>
            </p>
          </span>
        </button>
      </div>
    </ModalBody>
    <ModalFooter>
      <Button variant="light" size="sm" @click="emit('update:open', false)">Cancel</Button>
    </ModalFooter>
  </Modal>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import Modal from '@/ui/Modal.vue'
import ModalHeader from '@/ui/ModalHeader.vue'
import ModalBody from '@/ui/ModalBody.vue'
import ModalFooter from '@/ui/ModalFooter.vue'
import Input from '@/ui/Input.vue'
import Button from '@/ui/Button.vue'
import Icon from '@/ui/Icon.vue'
import { searchTasks, searchTasksGlobal } from '@/utils/api'

// project-scope workflows search within their own project only; workspace-
// scope ones search everywhere the user can see (mirrors the spec's own
// "task search within project scope; workspace scope = search all").
const props = defineProps({
  open:    { type: Boolean, default: false },
  scope:   { type: String, default: 'workspace' },
  project: { type: String, default: null },
})
const emit = defineEmits(['update:open', 'select'])

const query = ref('')
const results = ref([])
const searching = ref(false)
let timer = null

async function runSearch() {
  searching.value = true
  try {
    results.value = props.scope === 'project' && props.project
      ? await searchTasks(query.value.trim(), props.project)
      : await searchTasksGlobal(query.value.trim())
  } catch {
    results.value = []
  } finally {
    searching.value = false
  }
}
function onSearch() {
  clearTimeout(timer)
  timer = setTimeout(runSearch, 250)
}

// Empty query matches everything server-side (LIKE '%%') — used deliberately
// to show a "recent tasks" starting list rather than an empty modal.
watch(() => props.open, (v) => {
  if (!v) return
  query.value = ''
  runSearch()
})
</script>
