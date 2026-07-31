<template>
  <div ref="mountEl" class="zoom-reset" />
</template>

<script setup>
/**
 * ExcalidrawHost.vue — the Vue/React seam.
 *
 * Excalidraw is a React component; this SPA is Vue 3. There is no Vue port,
 * so this wrapper mounts a *separate* React root inside a plain div and
 * hand-feeds it props imperatively. Vue never reconciles into this subtree —
 * React owns everything below `mountEl`. The two frameworks never touch.
 *
 * `initialData` is deliberately one-shot: Excalidraw treats it as the seed
 * for the FIRST mount only (its own documented behavior) — this wrapper
 * mirrors that by only ever mounting once (see `mounted` below). To load a
 * different drawing, unmount this component (:key on the drawing id) rather
 * than expecting a data change to reset the canvas.
 *
 * `.zoom-reset` (see <style>): the app scales its entire chrome via CSS
 * `zoom` on <html> for "comfortable" density (index.css --ui-zoom). Excalidraw
 * computes its own pointer→scene coordinate math assuming standard unzoomed
 * pixels; left alone, its canvas renders shapes correctly (its own internal
 * transform) but its separately-computed resize-handle/hit-test layer drifts
 * from what's visible by a roughly constant offset — the exact same category
 * of bug this app already hit with Gantt drag math, and the same fix used for
 * teleported popovers (.bp-overlay in index.css): counter-zoom the subtree
 * back to 1×. Unlike .bp-overlay this box isn't position:fixed — it must
 * still exactly fill its container. That fill is done via `position:
 * absolute; inset:0` (not width/height:100% on a static flex child) —
 * zoom canceling against a flex-computed *height* percentage is a known
 * rough edge (percentage-height-in-flex is its own can of worms even
 * without zoom in the mix); inset:0 against the nearest positioned
 * ancestor resolves both axes the same way and has proven reliable here.
 * The parent (DrawCanvas.vue's canvas container) must be `position:
 * relative` with a definite height for this to have something to fill.
 */
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { createRoot } from 'react-dom/client'
import { createElement } from 'react'
import { Excalidraw, restore } from '@excalidraw/excalidraw'
import '@excalidraw/excalidraw/index.css'

const props = defineProps({
  initialData: { type: Object, default: null }, // { elements, appState, files } or null
  viewModeEnabled: { type: Boolean, default: false },
})
const emit = defineEmits(['change', 'ready'])

const mountEl = ref(null)
let root = null
let api = null
let mounted = false

function renderApp() {
  if (!root) return
  root.render(
    createElement(Excalidraw, {
      excalidrawAPI: (a) => { api = a; emit('ready', a) },
      initialData: !mounted ? restore(props.initialData || { elements: [], appState: {} }, null, null) : undefined,
      viewModeEnabled: props.viewModeEnabled,
      onChange: (elements, appState, files) => emit('change', elements, appState, files),
    }),
  )
  mounted = true
}

onMounted(() => {
  root = createRoot(mountEl.value)
  renderApp()
})

// viewModeEnabled is a normal reactive prop Excalidraw re-reads on every
// render (unlike initialData) — safe to re-render for this one.
watch(() => props.viewModeEnabled, renderApp)

onBeforeUnmount(() => {
  // Unmounting synchronously during React's own commit phase logs a warning;
  // defer one tick so React finishes whatever it's mid-flight on first.
  const r = root
  root = null
  setTimeout(() => r?.unmount(), 0)
})

defineExpose({
  getApi: () => api,
})
</script>

<style scoped>
.zoom-reset {
  /* top/left + explicit width/height, NOT inset:0 — combining inset:0 with
     an explicit width/height over-constrains the box (four position/size
     declarations on each axis, when only two are needed) and lets the
     browser silently drop one, which can render this taller/wider than its
     container and bleed over sibling chrome (e.g. the DrawCanvas header). */
  position: absolute;
  top: 0;
  left: 0;
  zoom: calc(1 / var(--ui-zoom));
  width: calc(100% * var(--ui-zoom));
  height: calc(100% * var(--ui-zoom));
}
</style>
