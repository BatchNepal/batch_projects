<template>
  <label :class="cn('cb-root inline-flex gap-2 cursor-pointer select-none', $slots.default ? 'items-center' : '', isDisabled && 'opacity-45 pointer-events-none', $attrs.class)">
    <input
      type="checkbox"
      class="cb-input sr-only"
      :checked="isSelected"
      :disabled="isDisabled"
      :indeterminate="isIndeterminate"
      @change="emit('update:isSelected', $event.target.checked)"
    />
    <span class="cb-control shrink-0" :class="{ 'cb-on': isSelected || isIndeterminate }">
      <!-- indeterminate dash -->
      <svg v-if="isIndeterminate" class="cb-mark" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3" stroke-linecap="round">
        <path d="M6 12h12" />
      </svg>
      <!-- checkmark -->
      <svg v-else class="cb-mark" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
        <path d="M5 13l4 4L19 7" />
      </svg>
    </span>
    <span v-if="$slots.default" class="text-sm text-foreground leading-none"><slot /></span>
  </label>
</template>

<script setup>
import { cn } from '@/lib/utils'
defineProps({
  isSelected:      { type: Boolean, default: false },
  isDisabled:      { type: Boolean, default: false },
  isIndeterminate: { type: Boolean, default: false },
})
const emit = defineEmits(['update:isSelected'])
</script>

<style scoped>
/* HeroUI checkbox recipe: a field-styled square whose accent fill scales in
   from the centre (::before), with a soft field shadow, hover border, and a
   focus ring. Mirrors @heroui/styles/components/checkbox.css. */
.cb-control {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  overflow: hidden;
  border-radius: var(--radius-md, 6px);
  border: 1.5px solid var(--field-border);
  background: var(--field);
  box-shadow: var(--field-shadow);
  color: var(--accent-foreground);
  transition:
    background-color 200ms var(--ease-out),
    border-color 200ms var(--ease-out),
    transform 100ms var(--ease-out);
}
.cb-control:active { transform: scale(0.9); }

/* accent fill that pops in on selection */
.cb-control::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  border-radius: inherit;
  background: var(--accent);
  opacity: 0;
  transform: scale(0.7);
  transform-origin: center;
  transition:
    transform 120ms var(--ease-out),
    opacity 180ms var(--ease-out),
    background-color 200ms var(--ease-out);
}

/* hover (unselected) */
.cb-root:hover .cb-control { border-color: var(--field-border-hover); }
.cb-root:hover .cb-control::before { background: var(--accent-hover); }

/* selected / indeterminate */
.cb-on { border-color: transparent !important; }
.cb-on::before { opacity: 1; transform: scale(1); }

/* checkmark / dash */
.cb-mark {
  position: relative;
  z-index: 1;
  width: 10px;
  height: 10px;
  opacity: 0;
  transform: scale(0.6);
  transition:
    opacity 140ms var(--ease-out),
    transform 180ms cubic-bezier(0.32, 0.72, 0, 1);
}
.cb-on .cb-mark { opacity: 1; transform: scale(1); }

/* focus ring (keyboard) */
.cb-input:focus-visible + .cb-control {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
