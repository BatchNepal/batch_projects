<template>
  <div class="max-w-2xl mx-auto px-6 py-12 space-y-8">
    <div class="mb-8">
      <h1 class="text-xl font-semibold text-foreground mb-2">Set workspace defaults</h1>
      <p class="text-sm text-muted">We'll use these to set up the first project we create for you next. You can change anything per project afterward.</p>
    </div>

    <!-- Default template -->
    <div>
      <p class="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Default project template</p>
      <div class="grid grid-cols-3 gap-2">
        <button
          v-for="t in FEATURED_TEMPLATES"
          :key="t.id"
          type="button"
          @click="updateField('template', t.id)"
          :class="[
            'flex items-center gap-2 px-3 py-2.5 rounded-md border-2 text-left transition-all text-sm font-medium',
            modelValue.template === t.id
              ? 'border-accent bg-accent-soft text-foreground'
              : 'border-border bg-overlay text-muted hover:border-border-secondary',
          ]"
        >
          <component :is="t.icon" :size="15" :stroke-width="1.5"
            :class="modelValue.template === t.id ? 'text-accent' : 'text-muted'" />
          {{ t.label }}
        </button>
      </div>
    </div>

    <!-- Default task/issue types -->
    <div>
      <p class="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Default {{ taskWord.toLowerCase() }} types</p>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="t in ISSUE_TYPES"
          :key="t.name"
          type="button"
          @click="toggleType(t.name)"
          :class="[
            'flex items-center gap-1.5 h-7 px-3 text-xs font-medium rounded-sm border transition-all',
            isTypeSelected(t.name)
              ? 'border-accent bg-accent-soft text-accent-soft-foreground'
              : 'border-border bg-surface-secondary text-muted hover:border-border-secondary',
          ]"
        >
          <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: t.color }"/>
          {{ t.name }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { TEMPLATES, getTaskWord } from '@/constants/project-templates'
import { ISSUE_TYPES } from '@/constants/issue-types'

const FEATURED_TEMPLATES = TEMPLATES.filter(t => ['kanban', 'scrum', 'simple', 'client-delivery', 'site-management'].includes(t.id))

const props = defineProps({ modelValue: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue'])

const taskWord = computed(() => getTaskWord(props.modelValue.template))

function updateField(field, value) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}

const isTypeSelected = (name) => props.modelValue.issueTypes.includes(name)

function toggleType(name) {
  const current = props.modelValue.issueTypes
  const next = isTypeSelected(name)
    ? current.filter(n => n !== name)
    : [...current, name]
  if (next.length > 0) updateField('issueTypes', next)
}
</script>
