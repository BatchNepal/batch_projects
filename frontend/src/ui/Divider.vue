<template>
  <div
    :class="cn(
      orientation === 'vertical' ? 'w-px self-stretch bg-separator' : 'w-full border-t border-separator',
      $attrs.class,
    )"
    role="separator"
    :aria-orientation="orientation"
  />
</template>

<script setup>
import { cn } from '@/lib/utils'
defineProps({ orientation: { type: String, default: 'horizontal' } }) // horizontal | vertical
</script>
