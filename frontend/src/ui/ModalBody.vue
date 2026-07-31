<template>
  <div :class="cn('flex-1 overflow-y-auto px-5 py-3 text-sm text-foreground', $attrs.class)"><slot /></div>
</template>
<script setup>
import { cn } from '@/lib/utils'
defineOptions({ inheritAttrs: false })
</script>
