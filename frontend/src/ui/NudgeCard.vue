<template>
  <Teleport to="body">
    <Transition name="nudge">
      <div
        v-if="modelValue"
        class="bp-overlay fixed bottom-4 right-4 z-toast w-[340px] max-w-[calc(100vw-2rem)] bg-overlay border border-border rounded-[12px] shadow-overlay p-4"
        role="status"
      >
        <div class="flex items-start gap-3">
          <div v-if="$slots.icon || icon" class="shrink-0 size-8 rounded-[8px] bg-accent-soft flex items-center justify-center text-accent">
            <slot name="icon"><component :is="icon" :size="16" :stroke-width="1.75" /></slot>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] font-semibold text-foreground leading-snug">{{ title }}</p>
            <p v-if="description" class="mt-0.5 text-[12.5px] text-muted leading-relaxed">{{ description }}</p>
            <div v-if="$slots.actions" class="mt-2.5 flex items-center gap-2">
              <slot name="actions" />
            </div>
          </div>
          <button
            type="button"
            class="shrink-0 -mr-1 -mt-1 size-6 rounded-md flex items-center justify-center text-muted hover:text-foreground hover:bg-surface-secondary transition-colors"
            aria-label="Dismiss"
            @click="emit('dismiss')"
          >
            <X :size="14" :stroke-width="1.75" />
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { X } from 'lucide-vue-next'

defineProps({
  modelValue:  { type: Boolean, default: false },
  title:       { type: String, required: true },
  description: { type: String, default: '' },
  icon:        { type: [Object, Function], default: null },
})
const emit = defineEmits(['dismiss'])
</script>

<style scoped>
.nudge-enter-active { transition: opacity var(--duration-toast) var(--ease-out), transform var(--duration-toast) var(--ease-smooth); }
.nudge-leave-active  { transition: opacity var(--duration-base) var(--ease-in), transform var(--duration-base) var(--ease-in); }
.nudge-enter-from, .nudge-leave-to { opacity: 0; transform: translateY(8px) scale(0.98); }
</style>
