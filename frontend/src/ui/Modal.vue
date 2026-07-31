<template>
  <Teleport to="body">
    <Transition name="mfade">
      <div v-if="open" class="bp-overlay fixed inset-0" :style="{ zIndex: myZIndex, background: 'var(--backdrop)' }" @click="isDismissable && emit('update:open', false)" />
    </Transition>
    <Transition name="mzoom">
      <div v-if="open" class="bp-overlay fixed inset-0 flex items-center justify-center p-4 pointer-events-none" :style="{ zIndex: myZIndex }">
        <div
          :class="cn('relative pointer-events-auto bg-overlay shadow-overlay flex flex-col max-h-[88vh] overflow-hidden', SIZE[size] ?? SIZE.md, 'rounded-xl', $attrs.class)"
          @click.stop
        > 
          <button
            v-if="!hideCloseButton"
            class="absolute top-3 right-3 z-10 flex items-center justify-center rounded-md text-muted hover:bg-default hover:text-foreground transition-colors outline-none focus-visible:shadow-focus"
            style="width:28px;height:28px"
            @click="emit('update:open', false)"
            aria-label="Close"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
// Stacking context: every Modal instance used to share the
// SAME static --z-modal (400) for both its own backdrop and content, so two
// simultaneously-open modals (a confirm dialog over a drawer, say) tied on
// z-index and fell back to Teleport/DOM append order — whichever mounted
// LAST visually won, regardless of which one actually OPENED last.
//
// This state MUST live in a plain (non-setup) <script> block: everything
// inside <script setup> compiles into the component's setup() function body,
// so a `const` declared there is a fresh per-INSTANCE local, not a shared
// singleton — two <Modal> instances each got their own empty Set and both
// happily claimed slot 0. A plain <script> block runs once per MODULE
// (import), so this really is shared across every Modal instance in the app.
//
// _usedSlots is a set of smallest-available-integer slots, not a running
// counter, deliberately: modals don't always close in the order they
// opened (a confirm dialog opened from a drawer typically closes first, but
// nothing guarantees that), and a counter that only ever increments would,
// over a long session, walk straight past --z-dropdown (410) after just ~5
// opens at +2 each. Claiming/releasing from a set instead means only
// CURRENTLY-open modals ever hold a slot, so the max in-use slot is bounded
// by how many modals are open AT ONCE (realistically 2-3), never by how
// many have opened over the component's lifetime.
const _usedSlots = new Set()
export function _claimSlot() {
  let s = 0
  while (_usedSlots.has(s)) s++
  _usedSlots.add(s)
  return s
}
export function _releaseSlot(s) { _usedSlots.delete(s) }
export function _anySlotsUsed() { return _usedSlots.size > 0 }
</script>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { cn } from '@/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  open:            { type: Boolean, default: false },
  size:            { type: String,  default: 'md' },
  isDismissable:   { type: Boolean, default: true },
  hideCloseButton: { type: Boolean, default: false },
})
const emit = defineEmits(['update:open'])

const SIZE = {
  xs: 'w-full max-w-xs', sm: 'w-full max-w-sm', md: 'w-full max-w-md',
  lg: 'w-full max-w-lg', xl: 'w-full max-w-xl', '2xl': 'w-full max-w-2xl',
  '3xl': 'w-full max-w-3xl', full: 'w-screen h-screen max-h-screen rounded-none',
}

const mySlot = ref(-1)
// +2 per slot keeps even several stacked modals well clear of --z-dropdown
// (410) and --z-toast (500) above, without touching those separately-
// tracked layers.
const myZIndex = computed(() => 400 + Math.max(mySlot.value, 0) * 2)

function onKey(e) { if (e.key === 'Escape' && props.open) emit('update:open', false) }

watch(() => props.open, (v) => {
  if (v) {
    mySlot.value = _claimSlot()
    document.addEventListener('keydown', onKey)
  } else {
    if (mySlot.value >= 0) _releaseSlot(mySlot.value)
    mySlot.value = -1
    document.removeEventListener('keydown', onKey)
  }
  // Only release the body scroll lock once NO modal is left open — closing
  // one of two stacked modals used to always reset overflow, silently
  // re-enabling background scroll while the other was still open.
  document.body.style.overflow = _anySlotsUsed() ? 'hidden' : ''
})
onBeforeUnmount(() => {
  if (mySlot.value >= 0) _releaseSlot(mySlot.value)
  document.body.style.overflow = _anySlotsUsed() ? 'hidden' : ''
  document.removeEventListener('keydown', onKey)
})
</script>

<style scoped>
.mfade-enter-active { transition: opacity var(--duration-base) var(--ease-out); }
.mfade-leave-active { transition: opacity var(--duration-fast) var(--ease-in); }
.mfade-enter-from, .mfade-leave-to { opacity: 0; }

.mzoom-enter-active { transition: opacity var(--duration-modal) var(--ease-out), transform var(--duration-modal) var(--ease-smooth); }
.mzoom-leave-active { transition: opacity var(--duration-base) var(--ease-in), transform var(--duration-base) var(--ease-in); }
.mzoom-enter-from   { opacity: 0; transform: scale(0.96) translateY(4px); }
.mzoom-leave-to     { opacity: 0; transform: scale(0.97); }
</style>
