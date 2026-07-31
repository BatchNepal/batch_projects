<template>
  <div ref="triggerRef" class="contents" @click="onOuterClick">
    <slot name="trigger" :open="open" :toggle="slotToggle" />
  </div>
  <Teleport to="body">
    <Transition name="drop">
      <div
        v-if="open"
        ref="contentRef"
        :style="pos"
        class="bp-overlay fixed z-dropdown overflow-hidden rounded-lg border border-border bg-overlay shadow-overlay p-1.5 outline-none"
        style="min-width: 180px"
        @click.stop
      >
        <slot />
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, provide, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
  placement:  { type: String, default: 'bottom-end' },
  sideOffset: { type: Number, default: 4 },
  minWidth:   { type: Number, default: 0 },
})

const open       = ref(false)
const triggerRef = ref(null)
const contentRef = ref(null)
const pos        = ref({})

function reposition() {
  const triggerEl = triggerRef.value?.firstElementChild ?? triggerRef.value
  if (!triggerEl || !contentRef.value) return
  const t = triggerEl.getBoundingClientRect()
  requestAnimationFrame(() => {
    if (!contentRef.value) return
    const f   = contentRef.value.getBoundingClientRect()
    const gap = props.sideOffset
    const vw  = window.innerWidth, vh = window.innerHeight
    const [side, align = 'end'] = props.placement.split('-')

    let top = side === 'top' ? t.top - f.height - gap : t.bottom + gap
    if (side === 'bottom' && top + f.height > vh - 8) top = t.top - f.height - gap
    if (side === 'top'    && top < 8)                  top = t.bottom + gap

    let left
    if (align === 'start')     left = t.left
    else if (align === 'end')  left = t.right - f.width
    else                       left = t.left + (t.width - f.width) / 2

    left = Math.max(8, Math.min(left, vw - f.width - 8))
    top  = Math.max(8, top)

    const mw = props.minWidth ? Math.max(props.minWidth, t.width) : undefined
    pos.value = { top: top+'px', left: left+'px', ...(mw ? { minWidth: mw+'px' } : {}) }
  })
}

function toggle() { open.value ? hide() : show() }
function show()   { open.value = true;  nextTick(reposition) }
function hide()   { open.value = false }
defineExpose({ open, show, hide, toggle })
provide('dropdown-hide', hide)

// Guard against double-toggle when a caller wires @click="toggle" on the slot trigger.
// The click would fire toggle() once via the slot prop AND again when it bubbles to the
// outer div. slotToggle sets a flag; onOuterClick skips if the flag was just set.
let _childToggled = false
function slotToggle() { _childToggled = true; toggle() }
function onOuterClick() { if (_childToggled) { _childToggled = false; return } toggle() }

function onPD(e)  { if (!open.value) return; if (contentRef.value?.contains(e.target) || triggerRef.value?.contains(e.target)) return; hide() }
function onKey(e) { if (e.key === 'Escape' && open.value) hide() }

onMounted(()      => { document.addEventListener('pointerdown', onPD, true); document.addEventListener('keydown', onKey, true) })
onBeforeUnmount(() => { document.removeEventListener('pointerdown', onPD, true); document.removeEventListener('keydown', onKey, true) })
watch(open, (v)   => {
  if (v) { window.addEventListener('scroll', reposition, true); window.addEventListener('resize', reposition) }
  else   { window.removeEventListener('scroll', reposition, true); window.removeEventListener('resize', reposition) }
})
</script>

<style scoped>
.drop-enter-active { transition: opacity 130ms var(--ease-out), transform 130ms var(--ease-smooth); }
.drop-leave-active { transition: opacity var(--duration-fast) var(--ease-in), transform var(--duration-fast) var(--ease-in); }
.drop-enter-from   { opacity: 0; transform: translateY(-4px) scale(0.97); }
.drop-leave-to     { opacity: 0; transform: scale(0.97); }
</style>
