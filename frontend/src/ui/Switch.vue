<template>
  <button
    type="button"
    role="switch"
    :aria-checked="checked"
    :aria-label="ariaLabel || undefined"
    :disabled="isDisabled"
    :data-size="size"
    :data-color="color"
    :class="cn(
      'sw relative inline-flex shrink-0 items-center rounded-full',
      checked ? 'sw-on' : 'sw-off',
      isDisabled ? 'opacity-45 cursor-not-allowed' : 'cursor-pointer',
      $attrs.class,
    )"
    @click="onClick"
  >
    <span class="sw-thumb block rounded-full" />
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
  // `md` stays the default and keeps the exact 34x18 track the app already
  // ships, so no existing screen shifts. `size` previously changed ONLY the
  // thumb's travel distance — the track stayed 34x18 at every size, so
  // size="sm" rendered a full-width track with a thumb that stopped short.
  size:       { type: String,  default: 'md' },      // sm | md | lg
  color:      { type: String,  default: 'primary' }, // primary | success | warning | danger
  ariaLabel:  { type: String,  default: '' },
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
/* Track/thumb geometry comes from vars so the ON translate is DERIVED
   (track - thumb - 2x inset) instead of the hardcoded translate-x-[13px] /
   [16px] magic numbers it used before — those had to be hand-corrected for
   every new size, which is why `lg` never existed. */
.sw {
  --sw-w: 34px;
  --sw-h: 18px;
  --sw-thumb: 14px;
  --sw-inset: 2px;
  --sw-accent: var(--accent);

  width: var(--sw-w);
  height: var(--sw-h);
  transition: background-color var(--duration-fast) var(--ease-out);
}

.sw[data-size='sm'] { --sw-w: 30px; --sw-h: 16px; --sw-thumb: 12px; }
.sw[data-size='lg'] { --sw-w: 44px; --sw-h: 24px; --sw-thumb: 20px; }

.sw[data-color='success'] { --sw-accent: var(--success); }
.sw[data-color='warning'] { --sw-accent: var(--warning); }
.sw[data-color='danger']  { --sw-accent: var(--danger); }

.sw-off { background: var(--default); }
.sw-on  { background: var(--sw-accent); }

/* --surface-hover was the wrong token — it's tuned for hover on a white
   panel background, not on --default (an already-grey track). In dark
   theme the two are the EXACT same oklch value, so hover did nothing at
   all; in light theme the delta was 0.018 lightness, not perceptible.
   --default-hover exists for precisely this — "the hover state of
   --default" — and has real contrast in both themes. */
@media (hover: hover) {
  .sw-off:not(:disabled):hover { background: var(--default-hover); }
  /* ON had no hover rule at all — --sw-accent is set dynamically per
     data-color, so there's no matching "-hover" token to reach for the way
     the off-track has one; a filter darkens whichever accent is active
     without needing a hover variant of every colour variable. */
  .sw-on:not(:disabled):hover { filter: brightness(0.92); }
}

.sw-thumb {
  width: var(--sw-thumb);
  height: var(--sw-thumb);
  /* was bg-white — correct by luck on a coloured track, wrong on the grey OFF
     track in dark mode, where pure white is the brightest thing on screen. */
  background: var(--surface);
  box-shadow: var(--shadow-xs);
  transform: translateX(var(--sw-inset));
  transition: transform var(--duration-base) var(--ease-smooth);
}

.sw-on .sw-thumb {
  transform: translateX(calc(var(--sw-w) - var(--sw-thumb) - var(--sw-inset)));
}

.sw:focus-visible {
  outline: 2px solid var(--sw-accent);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .sw, .sw-thumb { transition: none; }
}
</style>
