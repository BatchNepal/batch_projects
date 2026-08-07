<template>
  <div class="relative" ref="rootEl">
    <!-- Trigger slot -->
    <div @click.stop="toggle">
      <slot name="trigger" :open="isOpen"/>
    </div>

    <!-- Dropdown -->
    <Teleport to="body">
      <Transition
        enter-active-class="transform transition-[opacity,transform] duration-200 ease-fluid"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transform transition-[opacity,transform] duration-100 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
        @after-enter="position"
        @enter-cancelled="position"
      >
        <div v-if="isOpen"
          ref="dropEl"
          :style="dropStyle"
          class="bp-overlay fixed z-dropdown bg-overlay rounded-lg shadow-overlay overflow-hidden"
          :class="[widthClass, !ready && 'invisible']"
          @click.stop>
          <!-- Search slot (optional) -->
          <slot name="search"/>
          <!-- Items. Single-selects close on pick; multi-selects pass :close-on-select="false". -->
          <div class="p-1 max-h-52 overflow-y-auto scrollbar-thin" @click="closeOnSelect && close()">
            <slot/>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  width: { type: String, default: 'w-44' },
  align: { type: String, default: 'left' }, // 'left' | 'right'
  closeOnSelect: { type: Boolean, default: true }, // false for multi-select (assignees, labels)
})

const emit = defineEmits(['open', 'close'])

const rootEl = ref(null)
const dropEl = ref(null)
const isOpen = ref(false)
const ready = ref(false)
const dropStyle = ref({})

const widthClass = computed(() => props.width)

async function toggle() {
  if (isOpen.value) { close(); return }
  isOpen.value = true
  ready.value = false
  emit('open')
  await nextTick()
  position()
  // Reveal only AFTER the panel is positioned at its final spot — otherwise
  // the first frame renders at the body default (no top/left yet) and the
  // panel visibly jumps/flashes into place.
  ready.value = true
}

function close() {
  isOpen.value = false
  ready.value = false
  emit('close')
}

function position() {
  if (!rootEl.value || !dropEl.value) return
  const rect = rootEl.value.getBoundingClientRect()
  // offsetWidth/offsetHeight give LAYOUT size, unaffected by the enter
  // transition's `scale(0.95)` transform — getBoundingClientRect would
  // measure the scaled box mid-animation and mis-place right-aligned /
  // flip-up panels.
  const dw = dropEl.value.offsetWidth
  const dh = dropEl.value.offsetHeight
  const vw = window.innerWidth
  const vh = window.innerHeight

  let top = rect.bottom + 4
  let left = props.align === 'right' ? rect.right - dw : rect.left

  // Flip up if too close to bottom
  if (top + dh > vh - 8) top = rect.top - dh - 4

  // Keep within horizontal bounds
  if (left + dw > vw - 8) left = vw - dw - 8
  if (left < 8) left = 8

  // `w-full` on a teleported-to-body dropdown would mean 100% of the VIEWPORT,
  // not the trigger. Resolve it to the trigger's actual pixel width so the
  // panel hugs its field (e.g. full-width selects in modals/drawers).
  const width = props.width === 'w-full' ? `${rect.width}px` : undefined
  dropStyle.value = { top: `${top}px`, left: `${left}px`, minWidth: `${rect.width}px`, width }
}

function onOutside(e) {
  // Clicks inside a nested Popover (e.g. DatePicker calendar opened from a
  // dropdown cell) must not close the parent dropdown.
  if (e.target.closest?.('[data-pop-content]')) return
  if (!isOpen.value) return
  if (rootEl.value?.contains(e.target)) return
  if (dropEl.value?.contains(e.target)) return
  close()
}

function onScroll() { if (isOpen.value) position() }
function onKeydown(e) { if (e.key === 'Escape') close() }

onMounted(() => {
  document.addEventListener('mousedown', onOutside, true)
  document.addEventListener('scroll', onScroll, true)
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  document.removeEventListener('mousedown', onOutside, true)
  document.removeEventListener('scroll', onScroll, true)
  document.removeEventListener('keydown', onKeydown)
})

defineExpose({ close, open: () => { if (!isOpen.value) toggle() } })
</script>

<style scoped>
.scrollbar-thin { scrollbar-width: thin; scrollbar-color: var(--scrollbar-thumb) transparent; }
.scrollbar-thin::-webkit-scrollbar { width: 4px; }
.scrollbar-thin::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 2px; }
</style>