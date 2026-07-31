<template>
  <img
    :src="resolveProjectTheme(theme, seed).icon"
    :alt="resolveProjectTheme(theme, seed).label"
    :class="cn('shrink-0 object-cover', SIZE[size] ?? SIZE.md)"
  />
</template>

<script setup>
import { cn } from '@/lib/utils'
import { resolveProjectTheme } from '@/constants/project-themes'

defineProps({
  theme: { type: String, default: '' },
  seed:  { type: String, default: '' },  // fallback identity (project key) for legacy rows with no theme set
  size:  { type: String, default: 'md' }, // xs | sm | md | lg
})

const SIZE = {
  xs: 'size-4 rounded-[4px]',
  sm: 'size-5 rounded-[5px]',
  md: 'size-8 rounded-[7px]',
  lg: 'size-9 rounded-[10px]',
}
</script>
