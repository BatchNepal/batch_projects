<template>
  <div class="inline-flex items-center gap-1.5">
    <span
      class="w-1.5 h-1.5 rounded-full shrink-0"
      :style="{ backgroundColor: resolvedColor }"
    />
    <span class="text-[11px] font-medium uppercase tracking-wider text-foreground leading-none">
      {{ label }}
    </span>
    <span
      v-if="count !== undefined"
      class="inline-flex items-center justify-center min-w-[1rem] h-4 px-1 rounded-full text-[10px] font-medium text-muted bg-default tabular-nums"
    >
      {{ count }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const NAMED = {
  gray:   '#a1a1aa',
  blue:   '#60a5fa',
  green:  '#22c55e',
  red:    '#ef4444',
  orange: '#f97316',
  purple: '#a855f7',
}

const props = defineProps({
  label:    { type: String, required: true },
  color:    { type: String, default: 'gray' }, // gray | blue | green | red | orange | purple
  hexColor: { type: String, default: '' },     // direct hex from workflowState.color — overrides color
  count:    { type: Number, default: undefined },
})

const resolvedColor = computed(() => props.hexColor || NAMED[props.color] || NAMED.gray)
</script>
