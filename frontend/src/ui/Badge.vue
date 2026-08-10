<template>
  <span class="relative inline-flex shrink-0">
    <slot />
    <span
      v-if="!isInvisible"
      :class="cn(
        'absolute z-10 flex items-center justify-center font-medium whitespace-nowrap rounded-full',
        isDot ? DOT_SIZE[size] : SIZE_MAP[size],
        COLOR_MAP[color] ?? COLOR_MAP.default,
        showOutline && 'ring-2 ring-[var(--surface)]',
        PLACEMENT_MAP[placement],
      )"
    >
      <span v-if="!isDot" class="px-1 leading-none">{{ displayContent }}</span>
    </span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  content:     { type: [String, Number], default: '' },
  color:       { type: String,  default: 'danger' },    // default | accent | success | warning | danger
  size:        { type: String,  default: 'md' },        // sm | md | lg
  placement:   { type: String,  default: 'top-right' }, // top-right | top-left | bottom-right | bottom-left
  max:         { type: Number,  default: 99 },
  showOutline: { type: Boolean, default: true },
  isInvisible: { type: Boolean, default: false },
  isDot:       { type: Boolean, default: false },
})

const displayContent = computed(() => {
  if (props.isDot) return ''
  const n = Number(props.content)
  return (!isNaN(n) && n > props.max) ? `${props.max}+` : props.content
})

const SIZE_MAP = { sm: 'min-h-[14px] min-w-[14px] text-micro', md: 'min-h-4 min-w-4 text-xs', lg: 'min-h-5 min-w-5 text-xs' }
const DOT_SIZE = { sm: 'size-1.5', md: 'size-2', lg: 'size-2.5' }

const COLOR_MAP = {
  default: 'bg-default text-default-foreground',
  accent:  'bg-accent text-accent-foreground',
  success: 'bg-success text-success-foreground',
  warning: 'bg-warning text-warning-foreground',
  danger:  'bg-danger text-danger-foreground',
}

const PLACEMENT_MAP = {
  'top-right':    'top-0 right-0 translate-x-1/2 -translate-y-1/2',
  'top-left':     'top-0 left-0 -translate-x-1/2 -translate-y-1/2',
  'bottom-right': 'bottom-0 right-0 translate-x-1/2 translate-y-1/2',
  'bottom-left':  'bottom-0 left-0 -translate-x-1/2 translate-y-1/2',
}
</script>
