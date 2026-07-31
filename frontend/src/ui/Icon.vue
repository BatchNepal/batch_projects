<template>
  <component
    :is="icon"
    :size="size"
    :stroke-width="strokeWidth"
    class="shrink-0"
    v-bind="$attrs"
  />
</template>

<script setup>
defineOptions({ inheritAttrs: false })

defineProps({
  icon:        { required: true },
  size:        { type: Number, default: 16 },
  strokeWidth: { type: Number, default: 1.5 },
})
</script>
