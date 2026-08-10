<template>
  <label
    :class="cn('rd-root inline-flex items-center gap-2 cursor-pointer select-none', isDisabled && 'opacity-45 pointer-events-none')"
    :data-size="size"
    :data-color="color"
  >
    <input
      type="radio"
      class="rd-input sr-only"
      :checked="isSelected"
      :disabled="isDisabled"
      :value="value"
      :name="groupName || undefined"
      @change="select"
    />
    <span class="rd-control shrink-0" :class="{ 'rd-on': isSelected }">
      <span class="rd-dot" />
    </span>
    <span v-if="$slots.default" class="rd-label text-foreground leading-none"><slot /></span>
  </label>
</template>

<script setup>
import { computed, inject, unref } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  value:      { default: null },
  isDisabled: { type: Boolean, default: false },
  // Same axes and same default (`sm`) as Checkbox — these two are the same
  // control pattern and previously disagreed on every one of them: Radio was
  // a hardcoded 15px with no size or colour prop, against Checkbox's 16px.
  size:       { type: String, default: 'sm' },      // sm | md | lg
  color:      { type: String, default: 'primary' }, // primary | success | warning | danger | default
})

const groupValue    = inject('radioGroupValue', null)
const setGroupValue = inject('radioGroupSet',   () => {})
// Native radios only behave as ONE group (arrow-key navigation, single
// selection without JS) when they share a `name`. RadioGroup provides it;
// absent one they were independent checkboxes wearing radio styling.
const groupName     = inject('radioGroupName',  null)

/* unref is load-bearing: RadioGroup provides a computed REF, and inject hands
   it back as a ref (no auto-unwrap outside a template). The old code compared
   the ref object itself to props.value, which is never equal — so isSelected
   was permanently false and no radio could ever render as selected. Latent
   only because nothing in the app uses RadioGroup yet. */
const isSelected = computed(() => {
  const v = unref(groupValue)
  return v !== null && v !== undefined && v === props.value
})
function select() { setGroupValue(props.value) }
</script>

<style scoped>
.rd-root {
  --rd-size: 16px;
  --rd-dot: 6px;
  --rd-accent: var(--accent);
  --rd-accent-hover: var(--accent-hover);
  --rd-on-fg: var(--accent-foreground);
  font-size:var(--text-base);
}

.rd-root[data-size='md'] { --rd-size: 20px; --rd-dot: 8px;  font-size:var(--text-md); }
.rd-root[data-size='lg'] { --rd-size: 24px; --rd-dot: 10px; font-size:var(--text-md); }

.rd-root[data-color='success'] { --rd-accent: var(--success); --rd-accent-hover: var(--success-hover); --rd-on-fg: var(--success-foreground); }
.rd-root[data-color='warning'] { --rd-accent: var(--warning); --rd-accent-hover: var(--warning-hover); --rd-on-fg: var(--warning-foreground); }
.rd-root[data-color='danger']  { --rd-accent: var(--danger);  --rd-accent-hover: var(--danger-hover);  --rd-on-fg: var(--danger-foreground); }
.rd-root[data-color='default'] { --rd-accent: var(--foreground); --rd-accent-hover: var(--foreground); --rd-on-fg: var(--surface); }

.rd-label { font-size: inherit; }

.rd-control {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--rd-size);
  height: var(--rd-size);
  border-radius: var(--radius-full);
  border: 1.5px solid var(--field-border);
  background: var(--field-background);
  transition:
    background-color var(--duration-fast) var(--ease-out),
    border-color var(--duration-fast) var(--ease-out),
    transform var(--duration-instant) var(--ease-out);
}
.rd-control:active { transform: scale(0.92); }

@media (hover: hover) {
  .rd-root:hover .rd-control { border-color: var(--field-border-hover); }
}

.rd-on {
  border-color: var(--rd-accent);
  background: var(--rd-accent);
}
@media (hover: hover) {
  .rd-root:hover .rd-on { border-color: var(--rd-accent-hover); background: var(--rd-accent-hover); }
}

/* The dot scales in from the centre — same motion as Checkbox's mark, so a
   radio and a checkbox selecting feel like the same gesture. */
.rd-dot {
  display: block;
  width: var(--rd-dot);
  height: var(--rd-dot);
  border-radius: var(--radius-full);
  background: var(--rd-on-fg);
  opacity: 0;
  transform: scale(0.4);
  transition:
    opacity var(--duration-instant) var(--ease-out),
    transform var(--duration-fast) var(--ease-smooth);
}
.rd-on .rd-dot { opacity: 1; transform: scale(1); }

/* Focus ring (keyboard) — the native <input> is sr-only, so focus landed on an
   element with no visible box and NOTHING was drawn. Checkbox already solved
   this; Radio never did. */
.rd-input:focus-visible + .rd-control {
  outline: 2px solid var(--rd-accent);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .rd-control, .rd-dot { transition: none; }
  .rd-control:active { transform: none; }
}
</style>
