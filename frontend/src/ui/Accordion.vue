<template><div :class="cn('flex flex-col', $attrs.class)"><slot /></div></template>
<script setup>
import { cn } from '@/lib/utils'
</script>
