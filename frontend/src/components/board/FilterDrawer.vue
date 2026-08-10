<template>
  <span class="ph-icon-btn-wrap">
    <IconButton
      variant="outline" size="sm"
      :color="activeCount > 0 ? 'accent' : 'default'"
      :class="{ 'ph-icon-btn-on': open }"
      title="Filter"
      @click="open = true"
    >
      <ListFilter :size="15" :stroke-width="1.75" />
    </IconButton>
    <span v-if="activeCount" class="ph-tool-badge">{{ activeCount }}</span>
  </span>

  <Drawer :open="open" @update:open="open = $event" size="sm" placement="right">
    <DrawerHeader class="border-b" @close="open = false">
      <h2 class="text-sm font-semibold">Filter</h2>
    </DrawerHeader>

    <DrawerBody class="p-2">
      <FpSection
        v-if="taskTypes.length"
        label="Type"
        :options="taskTypes.map(t => ({ value: t.name, label: t.name, color: t.color }))"
        :model-value="store.boardViewState.filterType"
        @select="v => store.boardViewState.filterType = v"
      >
        <template #swatch="{ option }">
          <span class="fp-swatch" :style="{ background: option.color }">{{ option.label.charAt(0) }}</span>
        </template>
      </FpSection>

      <div v-if="taskTypes.length && projectLabels.length" class="fp-divider" />

      <FpSection
        v-if="projectLabels.length"
        label="Label"
        :options="projectLabels.map(l => ({ value: l.label, label: l.label, color: l.color }))"
        :model-value="store.boardViewState.filterLabel"
        @select="v => store.boardViewState.filterLabel = v"
      >
        <template #swatch="{ option }">
          <span class="fp-dot" :style="{ background: option.color }" />
        </template>
      </FpSection>

      <div v-if="projectLabels.length && assignees.length" class="fp-divider" />

      <FpSection
        v-if="assignees.length"
        label="Assignee"
        :options="assignees.map(a => ({ value: a, label: a }))"
        :model-value="store.boardViewState.filterAssignee"
        @select="v => store.boardViewState.filterAssignee = v"
      >
        <template #swatch="{ option }">
          <Avatar :name="option.label" size="xs" class="shrink-0" />
        </template>
      </FpSection>

      <div v-if="assignees.length" class="fp-divider" />

      <FpSection
        label="Priority"
        :options="PRIORITIES"
        :searchable="false"
        :model-value="store.boardViewState.filterPriority"
        @select="v => store.boardViewState.filterPriority = v"
      >
        <template #swatch="{ option }">
          <PriorityIcon :priority="option.value" />
        </template>
      </FpSection>
    </DrawerBody>

    <DrawerFooter v-if="activeCount" class="justify-between">
      <span class="text-sm text-muted">{{ activeCount }} filter{{ activeCount > 1 ? 's' : '' }} active</span>
      <Button size="sm" variant="outline" color="default" @click="clearAll">Clear all</Button>
    </DrawerFooter>
  </Drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ListFilter } from 'lucide-vue-next'
import { Avatar, Button, IconButton, Drawer, DrawerHeader, DrawerBody, DrawerFooter } from '@/ui'
import PriorityIcon from '@/components/PriorityIcon.vue'
import FpSection from './FpSection.vue'
import { useProjectStore } from '@/stores/project'
import { PRIORITIES } from '@/utils/constants.js'

defineProps({
  assignees: { type: Array, default: () => [] },
})

const store = useProjectStore()
const open  = ref(false)

const taskTypes    = computed(() => store.taskTypes || [])
const projectLabels = computed(() => store.projectLabels || [])

const activeCount = computed(() => {
  const v = store.boardViewState
  return [v.filterType, v.filterLabel, v.filterAssignee, v.filterPriority].filter(Boolean).length
})

function clearAll() {
  store.boardViewState.filterType     = null
  store.boardViewState.filterLabel    = null
  store.boardViewState.filterAssignee = null
  store.boardViewState.filterPriority = null
}
</script>

<style scoped>
/* Shared trigger-button chrome for the ProjectHeader tool row (Filter,
   Display, Saved views) now lives on the real IconButton component instead
   of 3 files each hand-rolling their own near-identical button — this file
   only adds what IconButton doesn't have: the "drawer is open" pinned state
   and the active-filter-count badge. */
.ph-icon-btn-wrap { position: relative; display: inline-flex; }
.ph-icon-btn-on { background: var(--surface-secondary); color: var(--foreground); }
.ph-tool-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 15px;
  height: 15px;
  padding: 0 4px;
  border-radius: 9999px;
  background: var(--accent-soft);
  color: var(--accent-soft-foreground);
  font-size:var(--text-xs);
  font-weight: 600;
  pointer-events: none;
}

.fp-divider {
  height: 1px;
  background: var(--separator);
  margin: 4px 2px;
}
</style>
