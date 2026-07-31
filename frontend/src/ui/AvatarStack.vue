<template>
  <div class="flex items-center -space-x-1.5">
    <Avatar
      v-for="(a, i) in visible"
      :key="i"
      :name="a.name"
      :src="a.src"
      :color="a.color"
      :size="size"
      class="ring-2 ring-[var(--surface)]"
      :title="a.name"
    />
    <span
      v-if="overflow > 0"
      class="inline-flex items-center justify-center rounded-full font-medium text-muted bg-default ring-2 ring-[var(--surface)]"
      :class="OVERFLOW_SIZE[size]"
      :style="{ fontSize: FONT[size] }"
    >+{{ overflow }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Avatar from './Avatar.vue'

const props = defineProps({
  avatars: { type: Array,  default: () => [] }, // [{ name, src?, color? }]
  max:     { type: Number, default: 3 },
  size:    { type: String, default: 'sm' }, // xs | sm | md
})

const OVERFLOW_SIZE = { xs: 'size-5', sm: 'size-6', md: 'size-8' }
const FONT          = { xs: '8px', sm: '9px', md: '11px' }

const visible  = computed(() => props.avatars.slice(0, props.max))
const overflow = computed(() => Math.max(0, props.avatars.length - props.max))
</script>
