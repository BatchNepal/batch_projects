<template>
  <Modal :open="open" @update:open="$emit('update:open', $event)" size="sm">
    <div class="p-5 w-full">
      <h3 class="text-md font-semibold text-foreground leading-tight mb-0.5">Capacity</h3>
      <p class="text-sm text-muted mb-4">{{ data?.sprint_name || '…' }} — allocated hours vs. weekly capacity</p>

      <div v-if="loading" class="py-8 flex items-center justify-center">
        <Spinner size="sm" />
      </div>

      <template v-else-if="data">
        <div v-if="!data.members.length" class="py-8 text-center">
          <p class="text-base text-muted">No assigned tasks with estimated hours yet.</p>
        </div>
        <div v-else class="space-y-3 max-h-[360px] overflow-y-auto pr-1">
          <div v-for="m in data.members" :key="m.user" class="flex items-center gap-3">
            <span class="cap-av" :style="{ background: avatarColor(m.user) }">{{ initials(m.full_name) }}</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between mb-1">
                <p class="text-sm font-medium text-foreground truncate">{{ m.full_name }}</p>
                <p class="text-sm tabular-nums shrink-0 ml-2" :class="pctClass(m)">
                  {{ m.allocated_hours }}h / {{ m.capacity_hours }}h
                </p>
              </div>
              <div class="cap-bar">
                <div class="cap-bar-fill" :class="pctFillClass(m)" :style="{ width: Math.min(100, pct(m)) + '%' }" />
              </div>
            </div>
          </div>
        </div>
        <p v-if="data.unassigned_task_count" class="text-sm text-muted mt-4 pt-3 border-t border-separator">
          {{ data.unassigned_task_count }} task{{ data.unassigned_task_count === 1 ? '' : 's' }} in this sprint have no assignee yet.
        </p>
      </template>
    </div>
  </Modal>
</template>

<script setup>
import { ref, watch } from 'vue'
import Modal from '@/ui/Modal.vue'
import Spinner from '@/ui/Spinner.vue'
import { getSprintCapacity } from '@/utils/api'
import { avatarColor, initials } from '@/utils/constants.js'

const props = defineProps({
  open:   { type: Boolean, default: false },
  sprint: { type: String, default: null },
})
defineEmits(['update:open'])

const loading = ref(false)
const data = ref(null)

watch(() => [props.open, props.sprint], async ([isOpen, sprint]) => {
  if (!isOpen || !sprint) return
  loading.value = true
  data.value = null
  try { data.value = await getSprintCapacity(sprint) }
  finally { loading.value = false }
}, { immediate: true })

function pct(m) { return m.capacity_hours > 0 ? (m.allocated_hours / m.capacity_hours) * 100 : 0 }
function pctClass(m) {
  const p = pct(m)
  if (p > 110) return 'text-danger'
  if (p >= 95) return 'text-warning-soft-foreground'
  return 'text-muted'
}
function pctFillClass(m) {
  const p = pct(m)
  if (p > 110) return 'cap-fill-danger'
  if (p >= 95) return 'cap-fill-warning'
  if (p >= 70) return 'cap-fill-success'
  return 'cap-fill-accent'
}
</script>

<style scoped>
.cap-av {
  width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--accent-foreground); font-size:var(--text-xs); font-weight: 700;
}
.cap-bar { width: 100%; height: 6px; background: var(--border); border-radius: 99px; overflow: hidden; }
.cap-bar-fill { height: 100%; border-radius: 99px; transition: width .3s; }
.cap-fill-accent  { background: var(--accent); }
.cap-fill-success { background: var(--success); }
.cap-fill-warning  { background: var(--warning); }
.cap-fill-danger  { background: var(--danger); }
</style>
