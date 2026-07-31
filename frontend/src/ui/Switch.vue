<template>
  <button
    type="button"
    role="switch"
    :aria-checked="checked"
    :disabled="isDisabled"
    :class="cn('sw relative inline-flex shrink-0 items-center rounded-full outline-none focus-visible:shadow-focus', checked ? 'bg-accent' : 'bg-default', isDisabled ? 'opacity-45 cursor-not-allowed' : 'cursor-pointer')"
    @click="onClick"
  >
    <span :class="cn('sw-thumb block rounded-full bg-white shadow-xs', checked ? (size === 'sm' ? 'translate-x-[13px]' : 'translate-x-[16px]') : 'translate-x-[2px]')" />
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

// Dual API: supports BOTH `isSelected`/`update:isSelected` and the standard
// `v-model` (`modelValue`/`update:modelValue`). Call sites use both — emit both
// events on toggle so either binding stays in sync.
const props = defineProps({
  isSelected: { type: Boolean, default: undefined },
  modelValue: { type: Boolean, default: undefined },
  isDisabled: { type: Boolean, default: false },
  size:       { type: String,  default: 'md' }, // sm | md
})
const emit = defineEmits(['update:isSelected', 'update:modelValue'])

const checked = computed(() => props.isSelected ?? props.modelValue ?? false)

function onClick() {
  if (props.isDisabled) return
  const next = !checked.value
  emit('update:isSelected', next)
  emit('update:modelValue', next)
}
</script>

<style scoped>
.sw {
  width:  34px;
  height: 18px;
  transition: background-color var(--duration-fast) var(--ease-out);
}
.sw-thumb {
  width:  14px;
  height: 14px;
  transition: transform 160ms var(--ease-smooth);
}
</style>
