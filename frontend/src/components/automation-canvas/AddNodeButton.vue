<template>
  <div class="flex items-center justify-center">
    <Handle type="target" :position="Position.Left" class="wf-handle" style="opacity: 0" />
    <button
      type="button"
      class="flex items-center justify-center size-6 rounded-md border border-dashed border-border text-muted bg-surface hover:border-accent hover:text-accent hover:bg-accent-soft transition-colors"
      @click="emit('add', id)"
    >
      <Plus :size="14" :stroke-width="2" />
    </button>
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'
import { Plus } from 'lucide-vue-next'

// A dangling "+" placeholder node — sits at the end of an open edge,
// inviting the next step (n8n's own affordance for this is the pattern
// being followed; this is our own component/markup, not their code).
defineProps({ id: { type: String, required: true } })
const emit = defineEmits(['add'])
</script>

<style scoped>
:deep(.wf-handle) { width: 1px; height: 1px; }
</style>
