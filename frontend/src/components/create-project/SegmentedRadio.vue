<template>
  <div class="grid grid-cols-4 gap-2.5">
    <button
      v-for="opt in options"
      :key="opt.id"
      type="button"
      class="bp-seg"
      :class="{ 'bp-seg--on': modelValue === opt.id }"
      :style="modelValue === opt.id
        ? { borderColor: opt.color, background: `color-mix(in oklab, ${opt.color || 'var(--muted)'} 5%, transparent)` }
        : null"
      @click="$emit('update:modelValue', opt.id)"
    >
      <span
        class="bp-seg-ic"
        :style="modelValue === opt.id
          ? { background: opt.color, color: 'var(--accent-foreground)' }
          : { background: `color-mix(in oklab, ${opt.color || 'var(--muted)'} 12%, transparent)`, color: opt.color }"
      >
        <component :is="opt.icon" :size="16" :stroke-width="2" />
      </span>
      <span class="bp-seg-label">{{ opt.label }}</span>
      <span class="bp-seg-sub">{{ opt.sublabel }}</span>

      <span
        v-if="modelValue === opt.id"
        class="bp-seg-check"
        :style="{ background: opt.color }"
      >
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
      </span>
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: 'internal' },
  options:    { type: Array, required: true },
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
/* Outlined choice cards, color-coded per engagement type. The type's color
   owns the selected state: border, soft bg tint, solid icon tile, check. */
.bp-seg {
  position: relative; display: flex; flex-direction: column; align-items: center;
  gap: 6px; padding: 12px 8px 11px; text-align: center; cursor: pointer;
  border-radius: var(--radius-md);
  border: 1px solid var(--field-border);
  background: var(--field-background);
  outline: none;
  transition:
    transform 250ms var(--ease-smooth),
    border-color 150ms var(--ease-out),
    background-color 150ms var(--ease-out),
    box-shadow 150ms var(--ease-out);
}
@media (hover: hover) {
  .bp-seg:hover:not(.bp-seg--on) { border-color: var(--field-border-hover); }
  .bp-seg:hover .bp-seg-ic { transform: scale(1.06); }
}
.bp-seg:active { transform: scale(0.98); transition: transform 40ms ease-out; }
.bp-seg:focus-visible {
  box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--focus);
}

.bp-seg-ic {
  display: grid; place-items: center; width: 30px; height: 30px;
  border-radius: var(--radius-md);
  transition: transform 150ms var(--ease-out), background-color 150ms var(--ease-out), color 150ms var(--ease-out);
}
.bp-seg-label { font-size:var(--text-sm); font-weight: var(--font-semibold); line-height: 1.2; margin-top: 2px; color: var(--foreground); }
.bp-seg-sub { font-size:var(--text-xs); line-height: 1.2; color: var(--muted); }

.bp-seg-check {
  position: absolute; top: -6px; right: -6px; width: 18px; height: 18px; border-radius: 50%;
  display: grid; place-items: center; color: var(--accent-foreground);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18);
  animation: seg-check-in 200ms var(--ease-smooth);
}
@keyframes seg-check-in {
  from { transform: scale(0.4); opacity: 0; }
  to   { transform: scale(1); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .bp-seg, .bp-seg-ic, .bp-seg-check { transition: none; animation: none; }
}
</style>
