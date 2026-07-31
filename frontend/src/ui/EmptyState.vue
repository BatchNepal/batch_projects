<template>
  <div class="flex flex-col items-center justify-center py-10 text-center" style="min-height:120px">
    <component v-if="icon" :is="icon" class="text-muted mb-3 shrink-0" style="width:28px;height:28px;stroke-width:1.5" />
    <p class="text-sm font-medium text-foreground">{{ title }}</p>
    <p v-if="description" class="text-xs text-muted mt-1 max-w-[220px] leading-relaxed">{{ description }}</p>
    <div v-if="$slots.action" class="mt-4"><slot name="action" /></div>
  </div>
</template>

<script setup>
defineProps({ icon: { default: null }, title: { type: String, required: true }, description: { type: String, default: '' } })
</script>
