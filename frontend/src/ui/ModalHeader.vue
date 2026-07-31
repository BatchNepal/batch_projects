<template>
  <div :class="cn('shrink-0 flex flex-col gap-1 px-5 pt-5 pb-3', $attrs.class)">
    <slot name="title">
      <h2 v-if="title" class="text-md font-semibold text-foreground leading-snug pr-8">{{ title }}</h2>
    </slot>
    <slot name="subtitle">
      <p v-if="subtitle" class="text-sm text-muted leading-snug">{{ subtitle }}</p>
    </slot>
    <slot />
  </div>
</template>

<script setup>
import { cn } from '@/lib/utils'
defineOptions({ inheritAttrs: false })
defineProps({ title: String, subtitle: String })
</script>
