<template>
  <span :class="cls">
    <span class="size-1.5 rounded-full shrink-0" :class="dotCls"></span>
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  label:  { type: String, default: '' },
  status: { type: String, default: '' }, // open | in_progress | in_review | done | blocked | cancelled
  color:  { type: String, default: '' }, // override hex e.g. '#22c55e'
})

const MAP = {
  open:        { dot: 'bg-muted',   bg: 'bg-default',   text: 'text-muted'   },
  in_progress: { dot: 'bg-accent',   bg: 'bg-accent-soft',    text: 'text-accent-soft-foreground'   },
  in_review:   { dot: 'bg-info',       bg: 'bg-info-soft',  text: 'text-info-soft-foreground' },
  done:        { dot: 'bg-success',  bg: 'bg-success-soft',   text: 'text-success-soft-foreground'  },
  closed:      { dot: 'bg-success',  bg: 'bg-success-soft',   text: 'text-success-soft-foreground'  },
  completed:   { dot: 'bg-success',  bg: 'bg-success-soft',   text: 'text-success-soft-foreground'  },
  blocked:     { dot: 'bg-danger',    bg: 'bg-danger-soft',     text: 'text-danger-soft-foreground'    },
  cancelled:   { dot: 'bg-muted',   bg: 'bg-surface-secondary',    text: 'text-muted'   },
}

function resolve(raw) {
  const key = (raw || '').toLowerCase().replace(/[\s-]/g, '_')
  if (MAP[key]) return MAP[key]
  if (key.includes('progress') || key.includes('active')) return MAP.in_progress
  if (key.includes('review'))   return MAP.in_review
  if (key.includes('done') || key.includes('complete') || key.includes('resolved') || key.includes('closed')) return MAP.done
  if (key.includes('block'))    return MAP.blocked
  if (key.includes('cancel'))   return MAP.cancelled
  return MAP.open
}

const cfg    = computed(() => resolve(props.status || props.label))
const dotCls = computed(() => props.color ? '' : cfg.value.dot)
const cls    = computed(() => cn(
  'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-xs font-medium leading-5 whitespace-nowrap',
  cfg.value.bg,
  cfg.value.text,
))
</script>
