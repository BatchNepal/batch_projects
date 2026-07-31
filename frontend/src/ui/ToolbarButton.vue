<template>
  <button
    :class="cn(
      'inline-flex items-center justify-center w-7 h-7 rounded-md text-muted',
      'hover:text-foreground hover:bg-default transition-colors duration-90',
      'focus-visible:shadow-focus outline-none',
      'disabled:opacity-45 disabled:pointer-events-none',
      '[&>svg]:w-3.5 [&>svg]:h-3.5',
    )"
  >
    <slot />
  </button>
</template>

<script setup>
import { cn } from '@/lib/utils'
</script>