<template>
  <label :class="cn('inline-flex items-center gap-2 cursor-pointer select-none', isDisabled && 'opacity-45 pointer-events-none')">
    <input type="radio" :checked="isSelected" :disabled="isDisabled" :value="value" class="sr-only" @change="select" />
    <span :class="cn('radio shrink-0 flex items-center justify-center rounded-full border', isSelected ? 'border-accent bg-accent' : 'border-[var(--field-border)] bg-field hover:border-[var(--field-border-hover)]')">
      <span v-if="isSelected" class="block rounded-full bg-accent-foreground" style="width:5px;height:5px" />
    </span>
    <span v-if="$slots.default" class="text-sm text-foreground leading-none"><slot /></span>
  </label>
</template>

<script setup>
import { computed, inject } from 'vue'
import { cn } from '@/lib/utils'
const props = defineProps({ value: { default: null }, isDisabled: { type: Boolean, default: false } })
const groupValue    = inject('radioGroupValue', null)
const setGroupValue = inject('radioGroupSet',   () => {})
const isSelected    = computed(() => groupValue !== null && groupValue === props.value)
function select() { setGroupValue(props.value) }
</script>

<style scoped>
.radio {
  width: 15px;
  height: 15px;
  transition: background-color var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out);
}
</style>
