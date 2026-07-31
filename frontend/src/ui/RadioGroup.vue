<template>
  <div role="radiogroup" :class="cn('flex', orientation === 'horizontal' ? 'flex-row flex-wrap gap-4' : 'flex-col gap-2', $attrs.class)">
    <slot />
  </div>
</template>

<script setup>
import { provide, computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  modelValue:  { default: null },
  orientation: { type: String, default: 'vertical' }, // vertical | horizontal
})
const emit = defineEmits(['update:modelValue'])
provide('radioGroupValue', computed(() => props.modelValue))
provide('radioGroupSet',   (v) => emit('update:modelValue', v))
</script>
