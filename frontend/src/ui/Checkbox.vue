<template>
  <label
    :class="cn(
      'cb-root inline-flex gap-2 cursor-pointer select-none',
      $slots.default ? 'items-center' : '',
      isDisabled && 'opacity-45 pointer-events-none',
      $attrs.class,
    )"
    :data-size="size"
    :data-color="color"
  >
    <input
      ref="inputEl"
      type="checkbox"
      class="cb-input sr-only"
      :checked="isSelected"
      :disabled="isDisabled"
      :name="name || undefined"
      :value="value ?? undefined"
      :aria-describedby="describedBy || undefined"
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
    <span v-if="$slots.default" class="cb-label text-foreground leading-none"><slot /></span>
  </label>
</template>

<script setup>
import { ref, watchEffect } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  isSelected:      { type: Boolean, default: false },
  isDisabled:      { type: Boolean, default: false },
  isIndeterminate: { type: Boolean, default: false },
  // HeroUI's variant axes. `sm` is the default deliberately: it's the 16px box
  // the app already shipped, so adding the scale changes no existing screen.
  size:            { type: String, default: 'sm' },      // sm | md | lg
  color:           { type: String, default: 'primary' }, // primary | success | warning | danger | default
  name:            { type: String, default: '' },
  value:           { default: undefined },
  describedBy:     { type: String, default: '' },
})
const emit = defineEmits(['update:isSelected'])

/* `indeterminate` is a DOM PROPERTY, not an attribute — binding it in the
   template (`:indeterminate="…"`, as this did) sets an attribute the browser
   ignores, so the mixed state was never exposed to assistive tech even though
   the dash rendered. Assign the property directly. */
const inputEl = ref(null)
watchEffect(() => {
  if (inputEl.value) inputEl.value.indeterminate = props.isIndeterminate
})
</script>

<style scoped>
/* HeroUI checkbox recipe: a field-styled square whose accent fill scales in
   from the centre (::before), with a hover border and a focus ring.
   Every dimension and colour is driven by two vars set from data-size /
   data-color below, so Radio and Switch can mirror the exact same ladder. */
.cb-root {
  --cb-size: 16px;
  --cb-mark: 10px;
  --cb-radius: var(--radius-sm);
  --cb-accent: var(--accent);
  --cb-accent-hover: var(--accent-hover);
  --cb-on-fg: var(--accent-foreground);
  font-size:var(--text-base);
}

/* HeroUI's sm/md/lg ladder (16/20/24). */
.cb-root[data-size='md'] { --cb-size: 20px; --cb-mark: 13px; --cb-radius: var(--radius-md); font-size:var(--text-md); }
.cb-root[data-size='lg'] { --cb-size: 24px; --cb-mark: 15px; --cb-radius: var(--radius-md); font-size:var(--text-md); }

.cb-root[data-color='success'] { --cb-accent: var(--success); --cb-accent-hover: var(--success-hover); --cb-on-fg: var(--success-foreground); }
.cb-root[data-color='warning'] { --cb-accent: var(--warning); --cb-accent-hover: var(--warning-hover); --cb-on-fg: var(--warning-foreground); }
.cb-root[data-color='danger']  { --cb-accent: var(--danger);  --cb-accent-hover: var(--danger-hover);  --cb-on-fg: var(--danger-foreground); }
.cb-root[data-color='default'] { --cb-accent: var(--foreground); --cb-accent-hover: var(--foreground); --cb-on-fg: var(--surface); }

.cb-label { font-size: inherit; }

.cb-control {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--cb-size);
  height: var(--cb-size);
  overflow: hidden;
  border-radius: var(--cb-radius);
  border: 1.5px solid var(--field-border);
  /* was var(--field) — a token that has never existed, so the unchecked box
     had no fill at all and showed whatever sat behind it. */
  background: var(--field-background);
  color: var(--cb-on-fg);
  transition:
    background-color var(--duration-fast) var(--ease-out),
    border-color var(--duration-fast) var(--ease-out),
    transform var(--duration-instant) var(--ease-out);
}
.cb-control:active { transform: scale(0.92); }

/* accent fill that pops in on selection */
.cb-control::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  border-radius: inherit;
  background: var(--cb-accent);
  opacity: 0;
  transform: scale(0.7);
  transform-origin: center;
  transition:
    transform var(--duration-fast) var(--ease-out),
    opacity var(--duration-fast) var(--ease-out),
    background-color var(--duration-fast) var(--ease-out);
}

@media (hover: hover) {
  .cb-root:hover .cb-control { border-color: var(--field-border-hover); }
  .cb-root:hover .cb-control::before { background: var(--cb-accent-hover); }
}

.cb-on { border-color: transparent !important; }
.cb-on::before { opacity: 1; transform: scale(1); }

.cb-mark {
  position: relative;
  z-index: 1;
  width: var(--cb-mark);
  height: var(--cb-mark);
  opacity: 0;
  transform: scale(0.6);
  transition:
    opacity var(--duration-instant) var(--ease-out),
    transform var(--duration-fast) var(--ease-smooth);
}
.cb-on .cb-mark { opacity: 1; transform: scale(1); }

/* focus ring (keyboard) — the native input is sr-only, so the ring is drawn
   on the visible box via the sibling selector. */
.cb-input:focus-visible + .cb-control {
  outline: 2px solid var(--cb-accent);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .cb-control, .cb-control::before, .cb-mark { transition: none; }
  .cb-control:active { transform: none; }
}
</style>
