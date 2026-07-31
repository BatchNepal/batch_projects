<template>
  <div :class="cn('flex-1 min-h-0 overflow-y-auto px-5 py-4', $attrs.class)"><slot /></div>
</template>
<script setup>
import { cn } from '@/lib/utils'
defineOptions({ inheritAttrs: false })
</script>
