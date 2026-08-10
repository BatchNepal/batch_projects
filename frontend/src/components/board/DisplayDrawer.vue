<template>
  <IconButton
    variant="outline" size="sm"
    :color="isNonDefault ? 'accent' : 'default'"
    :class="{ 'ph-icon-btn-on': open }"
    title="Display"
    @click="open = true"
  >
    <SlidersHorizontal :size="15" :stroke-width="1.75" />
  </IconButton>

  <Drawer :open="open" @update:open="open = $event" size="sm" placement="right">
    <DrawerHeader class="border-b" @close="open = false">
      <h2 class="text-sm font-semibold">Display</h2>
    </DrawerHeader>

    <DrawerBody class="p-2">
      <div class="dp-section">
        <div class="dp-section-label">Group by</div>
        <ul class="dp-list" role="listbox">
          <li
            v-for="o in groupByOptions" :key="o.value"
            class="dp-opt" :class="{ selected: store.boardGroupBy === o.value }"
            @click="store.boardGroupBy = o.value"
          >
            <span class="dp-opt-label">{{ o.label }}</span>
            <Check v-if="store.boardGroupBy === o.value" :size="13" class="shrink-0 ml-auto" />
          </li>
        </ul>
      </div>

      <div class="dp-divider" />

      <div class="dp-section">
        <div class="dp-section-label">Sort by</div>
        <ul class="dp-list" role="listbox">
          <li
            v-for="o in sortByOptions" :key="o.value"
            class="dp-opt" :class="{ selected: store.boardSortBy === o.value }"
            @click="store.boardSortBy = o.value"
          >
            <span class="dp-opt-label">{{ o.label }}</span>
            <Check v-if="store.boardSortBy === o.value" :size="13" class="shrink-0 ml-auto" />
          </li>
        </ul>
      </div>

      <div class="dp-divider" />

      <label class="dp-toggle-row">
        <span>Show subtasks</span>
        <Switch :model-value="!!store.showChildIssues" size="sm" @update:model-value="onToggleSubtasks" />
      </label>
    </DrawerBody>

    <DrawerFooter v-if="isNonDefault" class="justify-end">
      <Button size="sm" variant="outline" color="default" @click="resetDefaults">Reset to default</Button>
    </DrawerFooter>
  </Drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { SlidersHorizontal, Check } from 'lucide-vue-next'
import { Button, Switch, IconButton, Drawer, DrawerHeader, DrawerBody, DrawerFooter } from '@/ui'
import { useProjectStore } from '@/stores/project'

const store = useProjectStore()
const open  = ref(false)

const groupByOptions = [
  { value: 'status',   label: 'Status' },
  { value: 'priority', label: 'Priority' },
  { value: 'assignee', label: 'Assignee' },
  { value: 'type',     label: 'Task Type' },
  { value: 'label',    label: 'Label' },
]
const sortByOptions = [
  { value: 'board_order', label: 'Manual order' },
  { value: 'priority',    label: 'Priority' },
  { value: 'due_date',    label: 'Due date' },
  { value: 'title',       label: 'Title (A–Z)' },
  { value: 'creation',    label: 'Created' },
]

const isNonDefault = computed(() =>
  store.boardGroupBy !== 'status' || store.boardSortBy !== 'board_order' || !!store.showChildIssues
)

async function onToggleSubtasks(val) {
  store.showChildIssues = val
  await store.refreshBoard()
}

async function resetDefaults() {
  store.boardGroupBy = 'status'
  store.boardSortBy  = 'board_order'
  if (store.showChildIssues) await onToggleSubtasks(false)
}
</script>

<style scoped>
/* "Drawer is open" pinned state — IconButton itself only knows hover/active,
   not this persistent toggled-open look (see FilterDrawer.vue's comment). */
.ph-icon-btn-on { background: var(--surface-secondary); color: var(--foreground); }

.dp-section { padding: 2px 2px 4px; }
.dp-section-label {
  font-size:var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .02em;
  color: var(--muted);
  padding: 0 6px 4px;
}
.dp-list { display: flex; flex-direction: column; }
.dp-opt {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 6px;
  border-radius: var(--radius-md);
  font-size:var(--text-sm);
  color: var(--foreground);
  cursor: pointer;
  transition: background-color .1s;
}
.dp-opt:hover { background: var(--surface-secondary); }
.dp-opt.selected {
  background: var(--accent-soft);
  color: var(--accent-soft-foreground);
  font-weight: 500;
}
.dp-opt-label { flex: 1; min-width: 0; }

.dp-divider {
  height: 1px;
  background: var(--separator);
  margin: 4px 2px;
}

.dp-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 34px;
  padding: 0 6px;
  font-size:var(--text-sm);
  font-weight: 500;
  color: var(--foreground);
  cursor: pointer;
}
</style>
