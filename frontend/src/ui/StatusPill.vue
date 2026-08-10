<template>
  <div class="inline-flex items-center gap-1.5">
    <span
      class="w-1.5 h-1.5 rounded-full shrink-0"
      :style="{ backgroundColor: resolvedColor }"
    />
    <span class="text-xs font-medium uppercase tracking-wider text-foreground leading-none">
      {{ label }}
    </span>
    <span
      v-if="count !== undefined"
      class="inline-flex items-center justify-center min-w-[1rem] h-4 px-1 rounded-full text-xs font-medium text-muted bg-default tabular-nums"
    >
      {{ count }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// The six status-category colours, routed through the semantic token layer
// rather than raw Tailwind hex. As hard-coded hex these never shifted with the
// theme — #a1a1aa/#e4e4e7 read fine on white and glare on a near-black
// surface — and they sat a visible step off the oklch palette every other
// chip and badge in the app draws from.
// `hexColor` below is untouched: a workflow state's own colour is user DATA,
// and data is exactly where raw colour belongs.
const NAMED = {
  gray:   'var(--muted-tertiary)',
  blue:   'var(--accent)',
  green:  'var(--success)',
  red:    'var(--danger)',
  orange: 'var(--warning)',
  purple: 'var(--info)',
}

const props = defineProps({
  label:    { type: String, required: true },
  color:    { type: String, default: 'gray' }, // gray | blue | green | red | orange | purple
  hexColor: { type: String, default: '' },     // direct hex from workflowState.color — overrides color
  count:    { type: Number, default: undefined },
})

const resolvedColor = computed(() => props.hexColor || NAMED[props.color] || NAMED.gray)
</script>
