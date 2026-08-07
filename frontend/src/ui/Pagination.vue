<template>
  <nav role="navigation" aria-label="Pagination" :class="cn('flex items-center gap-0.5', $attrs.class)" v-bind="{ ...$attrs, class: undefined }">
    <button
      v-if="showControls"
      type="button"
      :disabled="page <= 1"
      :class="cn(itemCls, 'px-2', page <= 1 && 'opacity-40 pointer-events-none')"
      aria-label="Previous page"
      @click="goTo(page - 1)"
    >
      <svg :width="ICON[size]" :height="ICON[size]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 19l-7-7 7-7"/></svg>
    </button>

    <template v-for="item in pages" :key="item">
      <span v-if="item === '...'" :class="cn(itemCls, 'pointer-events-none text-muted')" aria-hidden="true">…</span>
      <button
        v-else
        type="button"
        :aria-label="`Page ${item}`"
        :aria-current="item === page ? 'page' : undefined"
        :class="cn(itemCls, item === page ? 'bg-accent text-accent-foreground' : 'text-foreground hover:bg-default')"
        @click="goTo(item)"
      >{{ item }}</button>
    </template>

    <button
      v-if="showControls"
      type="button"
      :disabled="page >= total"
      :class="cn(itemCls, 'px-2', page >= total && 'opacity-40 pointer-events-none')"
      aria-label="Next page"
      @click="goTo(page + 1)"
    >
      <svg :width="ICON[size]" :height="ICON[size]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg>
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  page:         { type: Number, default: 1 },
  total:        { type: Number, required: true },
  siblings:     { type: Number, default: 1 },
  boundaries:   { type: Number, default: 1 },
  size:         { type: String, default: 'md' }, // sm | md | lg
  showControls: { type: Boolean, default: true },
})
const emit = defineEmits(['update:page'])

function goTo(p) { if (p >= 1 && p <= props.total) emit('update:page', p) }

const pages = computed(() => {
  const { page, total, siblings, boundaries } = props
  if (total <= 1) return [1]
  const range = (s, e) => Array.from({ length: e - s + 1 }, (_, i) => s + i)
  const left  = Math.max(2, page - siblings)
  const right = Math.min(total - 1, page + siblings)
  return [
    ...range(1, Math.min(boundaries, left - 1)),
    ...(left  > boundaries + 2     ? ['...'] : []),
    ...range(left, right),
    ...(right < total - boundaries - 1 ? ['...'] : []),
    ...range(Math.max(total - boundaries + 1, right + 1), total),
  ]
})

const SIZE_H = { sm: 'h-7 min-w-7 text-xs', md: 'h-8 min-w-8 text-sm', lg: 'h-9 min-w-9 text-sm' }
const ICON   = { sm: 12, md: 13, lg: 14 }
const itemCls = computed(() => cn('inline-flex items-center justify-center rounded-md font-medium select-none outline-none transition-colors duration-fast focus-visible:shadow-focus', SIZE_H[props.size] ?? SIZE_H.md))
</script>
