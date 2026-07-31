<template>
  <div class="flex flex-col items-center gap-1.5 group">
    <div
      :class="cn(
        'flex items-center justify-center size-11 rounded-full border bg-surface transition-colors',
        selected ? 'border-accent shadow-focus' : 'border-border shadow-surface group-hover:border-border-hover',
      )"
    >
      <Icon :icon="data.icon" :size="18" :stroke-width="1.5" class="text-muted" />
    </div>
    <p class="text-[11px] text-muted text-center leading-tight max-w-[72px] truncate">{{ data.label }}</p>
    <Handle type="target" :position="Position.Top" class="wf-handle" />
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'
import Icon from '@/ui/Icon.vue'
import { cn } from '@/lib/utils'

// Small circular nodes attached below a parent (e.g. a Chat Model/Memory/Tool
// hanging off an AI Agent-style node) — config attachments, not steps in the
// main flow. Dashed edges connect them (canvas-level edge style, not here).
defineProps({
  id:       { type: String, required: true },
  data:     { type: Object, required: true }, // { label, icon }
  selected: { type: Boolean, default: false },
})
</script>

<style scoped>
:deep(.wf-handle) {
  width: 7px;
  height: 7px;
  background: var(--surface);
  border: 1.5px solid var(--border-hover, var(--border));
}
</style>
