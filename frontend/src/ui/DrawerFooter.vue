<template>
  <div :class="cn('shrink-0 flex items-center justify-end gap-2 px-5 py-4 border-t border-separator', $attrs.class)"><slot /></div>
</template>
<script setup>
import { cn } from '@/lib/utils'
defineOptions({ inheritAttrs: false })
</script>
