<template>
  <Modal :open="modelValue" size="sm" @update:open="$emit('update:modelValue', $event)">
    <ModalHeader title="Keyboard shortcuts" />
    <ModalBody>
      <div class="flex flex-col gap-1">
        <div v-for="s in SHORTCUTS" :key="s.label" class="flex items-center justify-between py-1.5">
          <span class="text-foreground">{{ s.label }}</span>
          <kbd class="text-[10px] font-medium text-muted bg-overlay px-1.5 py-0.5 border border-border rounded shadow-sm shrink-0">{{ s.key }}</kbd>
        </div>
      </div>
    </ModalBody>
  </Modal>
</template>

<script setup>
import Modal from '@/ui/Modal.vue'
import ModalHeader from '@/ui/ModalHeader.vue'
import ModalBody from '@/ui/ModalBody.vue'

defineProps({ modelValue: { type: Boolean, default: false } })
defineEmits(['update:modelValue'])

const SHORTCUTS = [
  { label: 'Search & commands', key: '⌘K' },
  { label: 'Create task', key: 'C' },
  { label: 'Assign selected task', key: 'A' },
  { label: 'This cheat sheet', key: '?' },
]
</script>
