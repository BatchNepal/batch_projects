<template>
  <div class="grid grid-cols-2 gap-3 items-start">
    <Card
      v-for="t in visibleTypes"
      :key="t.name"
      variant="default"
      isPressable
      bordered
      :shadow="isSelected(t.name)"
      :class="[
        'transition-all duration-200 border-2 text-left w-full block',
        isSelected(t.name)
          ? 'border-accent bg-accent-soft'
          : 'border-transparent bg-overlay hover:bg-default border-border'
      ]"
      @press="toggle(t.name)"
      noPadding
    >
      <div class="flex items-start gap-3 p-3">
        <Checkbox 
          :checked="isSelected(t.name)"
          size="md"
          radius="md"
          class="mt-0.5 pointer-events-none"
        />
        <div class="flex flex-col gap-1 min-w-0">
          <div class="flex items-center gap-1.5 h-4">
            <span class="w-2 h-2 rounded-full shrink-0" :style="{ backgroundColor: t.color }" />
            <span class="text-sm font-semibold text-foreground leading-none">{{ t.name }}</span>
          </div>
          <span class="text-xs text-muted leading-snug">{{ t.description }}</span>
        </div>
      </div>
    </Card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ISSUE_TYPES } from '@/constants/issue-types'
import Card from '@/ui/Card.vue'
import Checkbox from '@/ui/Checkbox.vue'

const props = defineProps({
  modelValue: { type: Array, required: true },
  // Names of issue types relevant to this project's industry. Empty = whole catalog.
  pool: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const CATALOG = Object.fromEntries(ISSUE_TYPES.map(t => [t.name, t]))

const visibleTypes = computed(() => {
  const names = props.pool?.length ? [...props.pool] : ISSUE_TYPES.map(t => t.name)
  // Always include currently-selected types, even if outside the pool.
  for (const n of props.modelValue) if (!names.includes(n)) names.push(n)
  return names.map(n => CATALOG[n] || { name: n, color: '#636B74', description: '' })
})

const isSelected = (name) => props.modelValue.includes(name)

function toggle(name) {
  const next = isSelected(name)
    ? props.modelValue.filter(n => n !== name)
    : [...props.modelValue, name]
  if (next.length > 0) emit('update:modelValue', next)
}
</script>
