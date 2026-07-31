<template>
  <div class="max-w-xl mx-auto px-6 py-12 space-y-6">
    <div class="mb-8">
      <h1 class="text-xl font-semibold text-foreground mb-2">Set up your workspace</h1>
      <p class="text-sm text-muted">What should we call your organisation?</p>
    </div>

    <!-- Workspace name -->
    <Input
      label="Workspace name"
      isRequired
      :modelValue="modelValue.name"
      @update:modelValue="update('name', $event)"
      placeholder="e.g. Acme Engineering"
      size="sm"
    />
  </div>
</template>

<script setup>
import { Input } from '@/ui'

const props = defineProps({ modelValue: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue'])

function update(field, value) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
</script>
