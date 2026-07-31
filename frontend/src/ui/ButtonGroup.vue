<template>
  <div
    :class="cn(
      'inline-flex items-center',
      orientation === 'vertical' ? 'flex-col' : 'flex-row',
      fullWidth && 'w-full',
      $attrs.class,
    )"
    role="group"
  >
    <slot />
  </div>
</template>

<script setup>
import { provide, computed, useAttrs } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  variant:     { type: String,  default: undefined },   // passed down to Buttons via context
  size:        { type: String,  default: undefined },
  orientation: { type: String,  default: 'horizontal' }, // horizontal | vertical
  fullWidth:   { type: Boolean, default: false },
  isDisabled:  { type: Boolean, default: false },
})

// Buttons inside read this context and apply group radius (no rounding on inner edges).
provide('buttonGroup', {
  variant:     computed(() => props.variant),
  size:        computed(() => props.size),
  isDisabled:  computed(() => props.isDisabled),
  orientation: computed(() => props.orientation),
})
</script>

<style scoped>
/* Strip inner border-radius from children so they butt up cleanly */
:deep(> *:not(:first-child):not(:last-child)) {
  border-radius: 0 !important;
}
:deep(> *:first-child:not(:last-child)) {
  border-top-right-radius: 0 !important;
  border-bottom-right-radius: 0 !important;
}
:deep(> *:last-child:not(:first-child)) {
  border-top-left-radius: 0 !important;
  border-bottom-left-radius: 0 !important;
}
/* Vertical orientation */
:deep(.flex-col > *:first-child:not(:last-child)) {
  border-bottom-left-radius: 0 !important;
  border-bottom-right-radius: 0 !important;
  border-top-right-radius: revert !important;
}
:deep(.flex-col > *:last-child:not(:first-child)) {
  border-top-left-radius: 0 !important;
  border-top-right-radius: 0 !important;
  border-bottom-left-radius: revert !important;
}
/* Collapse shared borders so they don't double */
:deep(> *:not(:first-child)) {
  margin-left: -1px;
}
</style>
