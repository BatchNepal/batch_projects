<template>
  <div
    v-if="!dismissed"
    role="alert"
    :class="cn('relative flex items-start gap-3 rounded-lg p-3.5', STYLES[color] ?? STYLES.default, $attrs.class)"
    v-bind="{ ...$attrs, class: undefined }"
  >
    <slot name="icon">
      <svg v-if="!hideIcon" class="shrink-0 mt-0.5" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path v-if="color === 'success'" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        <path v-else-if="color === 'warning'" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
        <path v-else-if="color === 'danger'" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        <path v-else d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
    </slot>

    <div class="flex flex-1 flex-col gap-0.5 min-w-0">
      <p v-if="title" class="text-sm font-semibold leading-snug">{{ title }}</p>
      <p v-if="description || $slots.default" class="text-sm leading-snug opacity-85"><slot>{{ description }}</slot></p>
      <slot name="action" />
    </div>

    <button
      v-if="isDismissable"
      type="button"
      class="shrink-0 flex items-center justify-center w-6 h-6 rounded opacity-60 hover:opacity-100 transition-opacity outline-none"
      aria-label="Dismiss"
      @click="dismissed = true; emit('close')"
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 6L6 18M6 6l12 12"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  title:         { type: String,  default: '' },
  description:   { type: String,  default: '' },
  color:         { type: String,  default: 'default' }, // default | accent | success | warning | danger
  hideIcon:      { type: Boolean, default: false },
  isDismissable: { type: Boolean, default: false },
})
const emit      = defineEmits(['close'])
const dismissed = ref(false)

const STYLES = {
  default: 'bg-default text-foreground',
  accent:  'bg-accent-soft text-accent-soft-foreground',
  success: 'bg-success-soft text-success-soft-foreground',
  warning: 'bg-warning-soft text-warning-soft-foreground',
  danger:  'bg-danger-soft text-danger-soft-foreground',
}
</script>
