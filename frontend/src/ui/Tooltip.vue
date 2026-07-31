<template>
  <div ref="wrapRef" class="contents" @mouseenter="show" @mouseleave="startHide" @focusin="show" @focusout="hide">
    <slot name="trigger" />
  </div>
  <Teleport to="body">
    <Transition name="tt">
      <div
        v-if="open"
        ref="contentRef"
        :style="pos"
        class="bp-overlay fixed z-tooltip pointer-events-none max-w-[260px] px-2 py-1 rounded-md text-xs leading-snug shadow-lg select-none"
        style="background:var(--foreground);color:var(--background)"
      >
        <slot>{{ content }}</slot>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
  placement: { type: String, default: 'top' },
  delay:     { type: Number, default: 280 },
  // Shorthand for a plain-text tooltip — must exist:
  // TeamHome.vue's usage (:content="p.project_name",
  // no default slot) turned out to render nothing at all, since this prop
  // never existed. Default slot still wins when both are given, for call
  // sites that need richer content than a plain string.
  content:   { type: String, default: '' },
})

const open       = ref(false)
const wrapRef    = ref(null)
const contentRef = ref(null)
const pos        = ref({})
let showTimer = null, hideTimer = null

function reposition() {
  const trigger = wrapRef.value?.firstElementChild ?? wrapRef.value
  if (!trigger || !contentRef.value) return
  const t = trigger.getBoundingClientRect()
  requestAnimationFrame(() => {
    if (!contentRef.value) return
    const f   = contentRef.value.getBoundingClientRect()
    const gap = 5
    const vw  = window.innerWidth, vh = window.innerHeight
    const side = props.placement.split('-')[0]
    let top  = side === 'bottom' ? t.bottom + gap : t.top - f.height - gap
    let left = t.left + (t.width - f.width) / 2
    left = Math.max(8, Math.min(left, vw - f.width - 8))
    top  = Math.max(8, Math.min(top,  vh - f.height - 8))
    pos.value = { top: top + 'px', left: left + 'px' }
  })
}

function show()      { clearTimeout(hideTimer); showTimer = setTimeout(() => { open.value = true; nextTick(reposition) }, props.delay) }
function startHide() { clearTimeout(showTimer); hideTimer = setTimeout(() => { open.value = false }, 80) }
function hide()      { clearTimeout(showTimer); open.value = false }
onBeforeUnmount(()  => { clearTimeout(showTimer); clearTimeout(hideTimer) })
</script>

<style scoped>
.tt-enter-active { transition: opacity 130ms var(--ease-out), transform 130ms var(--ease-smooth); }
.tt-leave-active { transition: opacity var(--duration-fast) var(--ease-in); }
.tt-enter-from   { opacity: 0; transform: translateY(3px); }
.tt-leave-to     { opacity: 0; }
</style>
