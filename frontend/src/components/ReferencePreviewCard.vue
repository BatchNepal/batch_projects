<template>
  <div ref="triggerWrapRef" class="contents" @mouseenter="onEnter" @mouseleave="onLeave">
    <slot name="trigger" />
  </div>

  <Teleport to="body">
    <Transition name="rpc-fade">
      <div
        v-if="open"
        ref="cardRef"
        :style="pos"
        class="bp-overlay fixed z-tooltip pointer-events-none w-64 rounded-lg border border-border bg-overlay shadow-overlay p-3"
      >
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted mb-2">{{ doctype }}</p>

        <div v-if="!preview" class="flex items-center gap-2 text-xs text-muted py-1">
          <Spinner size="xs" /> Loading…
        </div>

        <div v-else-if="preview.state === 'ready'" class="flex flex-col gap-1.5">
          <div v-for="f in preview.fields" :key="f.fieldname" class="flex items-center justify-between gap-3 text-xs">
            <span class="text-muted">{{ f.label }}</span>
            <span class="text-foreground font-medium truncate max-w-[60%]">
              {{ formatMirrorValue(preview.row[f.fieldname], f.fieldtype, preview.row) || '—' }}
            </span>
          </div>
        </div>

        <p v-else-if="preview.state === 'unmirrored'" class="text-xs text-muted py-1">
          No preview available for {{ doctype }}.
        </p>

        <p v-else class="text-xs text-muted py-1">
          No access to preview this document.
        </p>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, onBeforeUnmount, nextTick } from 'vue'
import Spinner from '@/ui/Spinner.vue'
import { fetchMirrorPreview } from '@/composables/useMirrorPreview'
import { formatMirrorValue } from '@/utils/mirrorFormat.js'

const props = defineProps({
  doctype: { type: String, required: true },
  name:    { type: String, required: true },
  // BP Project name — optional, but without it the backend can't tell
  // whether to strip Currency fields for a caller lacking view_money
  // on the relevant project.
  project: { type: String, default: null },
  delay:   { type: Number, default: 350 }, // hover-intent — never fire on mere mouse-transit
})

const open           = ref(false)
const preview        = ref(null)
const triggerWrapRef = ref(null)
const cardRef        = ref(null)
const pos            = ref({})
let showTimer = null

function reposition() {
  const trigger = triggerWrapRef.value?.firstElementChild ?? triggerWrapRef.value
  if (!trigger || !cardRef.value) return
  const t = trigger.getBoundingClientRect()
  const c = cardRef.value.getBoundingClientRect()
  const vw = window.innerWidth, vh = window.innerHeight
  const gap = 6

  let top = t.bottom + gap
  if (top + c.height > vh - 8) top = t.top - c.height - gap // flip up near viewport bottom
  let left = t.left
  if (left + c.width > vw - 8) left = vw - c.width - 8
  if (left < 8) left = 8

  pos.value = { top: `${top}px`, left: `${left}px` }
}

function onEnter() {
  clearTimeout(showTimer)
  showTimer = setTimeout(async () => {
    open.value = true
    preview.value = null
    await nextTick()
    reposition()
    const result = await fetchMirrorPreview(props.doctype, props.name, props.project)
    if (!open.value) return // hovered away before the fetch resolved
    preview.value = result
    await nextTick()
    reposition()
  }, props.delay)
}

function onLeave() {
  clearTimeout(showTimer)
  open.value = false
}

onBeforeUnmount(() => clearTimeout(showTimer))
</script>

<style scoped>
.rpc-fade-enter-active { transition: opacity 120ms ease-out, transform 120ms ease-out; }
.rpc-fade-leave-active { transition: opacity 80ms ease-in; }
.rpc-fade-enter-from   { opacity: 0; transform: translateY(3px); }
.rpc-fade-leave-to     { opacity: 0; }
</style>
