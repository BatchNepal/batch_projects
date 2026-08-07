<template>
  <!-- max-w-xl to match steps 1/2/4 — this was max-w-2xl, so the content
       column visibly jumped wider on step 3 and back again on step 4. -->
  <div class="max-w-xl mx-auto px-6 py-12 space-y-8">
    <div class="mb-8">
      <h1 class="text-xl font-semibold text-foreground mb-2">Set workspace defaults</h1>
      <p class="text-sm text-muted">We'll use these to set up the first project we create for you next. You can change anything per project afterward.</p>
    </div>

    <!-- Default template -->
    <div>
      <p class="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Default project template</p>
      <!-- grid-cols-3 with 5 featured templates left a ragged 3+2; the auto-fit
           track keeps the row full at any width and collapses cleanly on
           mobile instead of squeezing three cards into 320px. -->
      <div class="ob-tiles">
        <button
          v-for="t in FEATURED_TEMPLATES"
          :key="t.id"
          type="button"
          :aria-pressed="modelValue.template === t.id"
          @click="updateField('template', t.id)"
          :class="[
            'ob-tile flex items-center gap-2 px-3 py-2.5 rounded-md border text-left text-sm font-medium',
            modelValue.template === t.id
              ? 'is-on bg-accent-soft text-foreground'
              : 'bg-overlay text-muted',
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
          :aria-pressed="isTypeSelected(t.name)"
          :class="[
            'ob-chip flex items-center gap-1.5 h-7 px-3 text-xs font-medium border',
            isTypeSelected(t.name)
              ? 'is-on bg-accent-soft text-accent-soft-foreground'
              : 'bg-surface-secondary text-muted',
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

<style scoped>
/* Selection used `border-2`, so picking a tile grew its border by 1px and
   nudged every sibling — and `transition-all` animated that reflow. Border
   stays hairline at 1px in both states; selection is carried by the accent
   colour and the tinted fill, and only paint properties transition. */
.ob-tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
}

.ob-tile,
.ob-chip {
  border-color: var(--border);
  cursor: pointer;
  transition:
    background-color 140ms var(--ease-out),
    border-color 140ms var(--ease-out),
    color 140ms var(--ease-out);
}

.ob-chip {
  /* Chips are the one control that takes a full radius, per the design law. */
  border-radius: var(--radius-full);
}

@media (hover: hover) {
  .ob-tile:not(.is-on):hover,
  .ob-chip:not(.is-on):hover {
    border-color: var(--border-tertiary);
    background: var(--surface-hover);
  }
}

.ob-tile.is-on,
.ob-chip.is-on {
  border-color: var(--accent);
}

@media (prefers-reduced-motion: reduce) {
  .ob-tile, .ob-chip { transition: none; }
}
</style>
