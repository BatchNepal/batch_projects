<template>
  <div
    role="radiogroup"
    :aria-label="ariaLabel || undefined"
    :aria-orientation="orientation"
    :class="cn('flex', orientation === 'horizontal' ? 'flex-row flex-wrap gap-4' : 'flex-col gap-2', $attrs.class)"
  >
    <slot />
  </div>
</template>

<script setup>
import { provide, computed, useId } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  modelValue:  { default: null },
  orientation: { type: String, default: 'vertical' }, // vertical | horizontal
  ariaLabel:   { type: String, default: '' },
  name:        { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

/* A shared `name` is what makes the browser treat these as ONE radio group:
   without it each <input type="radio"> is its own group, so native arrow-key
   navigation doesn't work and nothing enforces single-selection at the DOM
   level. Auto-generated per group unless the caller supplies one (they only
   need to for real form posts). */
const uid = useId()
provide('radioGroupName',  computed(() => props.name || `rg-${uid}`))
provide('radioGroupValue', computed(() => props.modelValue))
provide('radioGroupSet',   (v) => emit('update:modelValue', v))
</script>
