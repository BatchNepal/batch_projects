<template>
  <div class="flex flex-col items-center justify-center py-20 text-center" style="min-height:320px">
    <img v-if="image" :src="image" class="text-muted mb-3 shrink-0" style="width: auto;height:160px;" />
    <component v-else-if="icon" :is="icon" class="text-muted mb-3 shrink-0" style="width:28px;height:28px;" />
    <p class="text-md font-semibold text-foreground">{{ title }}</p>
    <p v-if="description" class="text-sm text-muted mt-0.5 mb-3 max-w-[220px] leading-relaxed">{{ description }}</p>
    <div v-if="$slots.action" class="mt-4"><slot name="action" /></div>
  </div>
</template>

<script setup>
defineProps({ icon: { default: null }, image: { default: null }, title: { type: String, required: true }, description: { type: String, default: '' } })
</script>
