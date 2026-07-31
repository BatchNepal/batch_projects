<template>
  <span
    :class="cn('inline-flex items-center justify-center shrink-0 overflow-hidden font-medium select-none', SIZE_CLASS[size] ?? SIZE_CLASS.md, RADIUS[radius] ?? 'rounded-full', $attrs.class)"
    :style="!src || imgError ? { background: bgStyle } : {}"
    :title="name || undefined"
    v-bind="{ ...$attrs, class: undefined }"
  >
    <img v-if="src && !imgError" :src="src" :alt="name" class="w-full h-full object-cover" @error="imgError = true" />
    <span v-else class="text-white leading-none select-none" :style="{ fontSize: FONT[size] ?? '12px' }">{{ initials }}</span>
  </span>
</template>

<script setup>
import { ref, computed } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  src:    { type: String,  default: '' },
  name:   { type: String,  default: '' },
  size:   { type: String,  default: 'md' },   // xs | sm | md | lg | xl
  radius: { type: String,  default: 'full' },
  color:  { type: String,  default: '' },
})

const imgError = ref(false)

const SIZE_CLASS = { xs: 'size-5', sm: 'size-6', md: 'size-8', lg: 'size-10', xl: 'size-12' }
const FONT       = { xs: '8px', sm: '9px', md: '11px', lg: '13px', xl: '16px' }
const RADIUS     = { none: 'rounded-none', sm: 'rounded-sm', md: 'rounded-md', lg: 'rounded-lg', full: 'rounded-full' }

// A flat single-color circle behind 1-2 letters is the one look every app
// defaults to — a two-stop gradient (still fully deterministic from the
// name, still a stable identity per person) reads far less generic for
// basically zero extra cost. Hue held constant, lightness/chroma swept
// across the two stops so it stays a genuine gradient rather than two
// unrelated colors jammed together.
const PALETTE_HUES = [254, 200, 151, 26, 72, 300, 230, 340, 170, 285]

const bgStyle = computed(() => {
  if (props.color) return props.color
  let h = 0
  for (const ch of (props.name || '?')) h = ch.charCodeAt(0) + ((h << 5) - h)
  const hue = PALETTE_HUES[Math.abs(h) % PALETTE_HUES.length]
  const angle = 115 + (Math.abs(h >> 3) % 60)
  return `linear-gradient(${angle}deg, oklch(0.68 0.19 ${hue}), oklch(0.52 0.21 ${(hue + 25) % 360}))`
})

const initials = computed(() => {
  if (!props.name) return '?'
  return props.name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
})
</script>
