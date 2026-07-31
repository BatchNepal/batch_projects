<template><div :class="cn('flex items-center gap-1', $attrs.class)"><slot /></div></template>
<script setup>
import { cn } from '@/lib/utils'
</script>
