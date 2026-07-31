<template>
  <div ref="triggerRef" class="contents" @click="onOuterClick">
    <slot name="trigger" :open="isOpen" :toggle="slotToggle" />
  </div>
  <Teleport to="body">
    <Transition name="pop">
      <div
        v-if="isOpen"
        ref="contentRef"
        :style="pos"
        data-pop-content
        :class="['bp-overlay fixed z-popover bg-overlay border border-border rounded-lg shadow-overlay outline-none', padding]"
        @click.stop
      >
        <slot />
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
  open:       { type: Boolean, default: undefined },
  placement:  { type: String,  default: 'bottom' },
  sideOffset: { type: Number,  default: 6 },
  padding:    { type: String,  default: 'p-3' },
})
const emit = defineEmits(['update:open'])

const controlled    = computed(() => props.open !== undefined)
const _open         = ref(false)
const isOpen        = computed({
  get: () => controlled.value ? props.open : _open.value,
  set: (v) => controlled.value ? emit('update:open', v) : (_open.value = v),
})

const triggerRef = ref(null)
const contentRef = ref(null)
// Start offscreen — a fixed element with no top/left renders at its static
// position (end of <body>), which users saw as a popup "at the left/bottom".
const OFFSCREEN  = { top: '-9999px', left: '-9999px' }
const pos        = ref({ ...OFFSCREEN })

function reposition() {
  requestAnimationFrame(() => {
    const triggerEl = triggerRef.value?.firstElementChild ?? triggerRef.value
    if (!triggerEl || !contentRef.value) return
    // measure both rects in the same frame, after content has painted
    const t   = triggerEl.getBoundingClientRect()
    const f   = contentRef.value.getBoundingClientRect()
    if (!t.width && !t.height) return
    const gap = props.sideOffset
    const vw  = window.innerWidth, vh = window.innerHeight
    const [side, align = 'center'] = props.placement.split('-')
    let top, left

    if (side === 'bottom')      top = t.bottom + gap
    else if (side === 'top')    top = t.top - f.height - gap
    else if (side === 'left')   top = t.top + (t.height - f.height) / 2
    else                        top = t.top + (t.height - f.height) / 2

    if (side === 'left')        left = t.left - f.width - gap
    else if (side === 'right')  left = t.right + gap
    else if (align === 'start') left = t.left
    else if (align === 'end')   left = t.right - f.width
    else                        left = t.left + (t.width - f.width) / 2

    if (side === 'bottom' && top + f.height > vh - 8) top = t.top - f.height - gap
    if (side === 'top'    && top < 8)                  top = t.bottom + gap

    left = Math.max(8, Math.min(left, vw - f.width - 8))
    top  = Math.max(8, top)
    pos.value = { top: top + 'px', left: left + 'px' }
  })
}

function handleClick()  { isOpen.value = !isOpen.value }
function show()         { isOpen.value = true }
function hide()         { isOpen.value = false }

// Reposition on every open (any code path) and track scroll/resize while
// open — table scrolling must carry the popup with its anchor.
watch(isOpen, (v) => {
  if (v) {
    pos.value = { ...OFFSCREEN }
    nextTick(reposition)
    window.addEventListener('scroll', reposition, true)
    window.addEventListener('resize', reposition)
  } else {
    pos.value = { ...OFFSCREEN }
    window.removeEventListener('scroll', reposition, true)
    window.removeEventListener('resize', reposition)
  }
})
defineExpose({ show, hide })

let _childToggled = false
function slotToggle() { _childToggled = true; handleClick() }
function onOuterClick() { if (_childToggled) { _childToggled = false; return } handleClick() }

function onPD(e) {
  if (!isOpen.value) return
  if (contentRef.value?.contains(e.target) || triggerRef.value?.contains(e.target)) return
  hide()
}
function onKey(e) { if (e.key === 'Escape' && isOpen.value) hide() }

onMounted(()      => { document.addEventListener('pointerdown', onPD, true); document.addEventListener('keydown', onKey, true) })
onBeforeUnmount(() => { document.removeEventListener('pointerdown', onPD, true); document.removeEventListener('keydown', onKey, true) })

watch(isOpen, (v) => {
  if (v) { window.addEventListener('scroll', reposition, true); window.addEventListener('resize', reposition) }
  else   { window.removeEventListener('scroll', reposition, true); window.removeEventListener('resize', reposition) }
})
</script>

<style scoped>
.pop-enter-active { transition: opacity 130ms var(--ease-out), transform 130ms var(--ease-smooth); }
.pop-leave-active { transition: opacity var(--duration-fast) var(--ease-in), transform var(--duration-fast) var(--ease-in); }
.pop-enter-from   { opacity: 0; transform: scale(0.95) translateY(-2px); }
.pop-leave-to     { opacity: 0; transform: scale(0.97); }
</style>
