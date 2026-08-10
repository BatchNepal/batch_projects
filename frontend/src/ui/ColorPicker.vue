<template>
  <Dropdown placement="bottom-start" :side-offset="6">
    <template #trigger="{ toggle }">
      <button
        type="button" class="cp-trigger" :class="size === 'sm' ? 'cp-trigger-sm' : ''"
        @click="toggle"
      >
        <span class="cp-swatch" :style="modelValue ? { background: modelValue } : {}">
          <svg v-if="!modelValue" viewBox="0 0 16 16" class="cp-swatch-empty"><path d="M2 2l12 12" stroke="currentColor" stroke-width="1.4" /></svg>
        </span>
        <span v-if="label" class="cp-trigger-label">{{ label }}</span>
      </button>
    </template>

    <div class="cp-panel">
      <!-- Curated hue presets — one click covers most real picks, same
           posture most label pickers settle on. Ring shows when the
           current color matches one exactly. -->
      <div class="cp-dot-row">
        <button
          v-for="c in PRESETS" :key="c"
          type="button" class="cp-dot" :class="{ 'cp-dot-active': isActive(c) }"
          :style="{ background: c }" :title="c"
          @click="pick(c)"
        />
      </div>

      <!-- Saturation/value field: white→hue horizontally, hue→black
           vertically — the standard HSV square, built from two CSS
           gradients over a flat hue background rather than canvas/SVG. -->
      <div ref="svRef" class="cp-sv" :style="{ background: svBackground }" @pointerdown="onSvPointerDown">
        <div class="cp-sv-handle" :style="{ left: sat + '%', top: (100 - val) + '%' }" />
      </div>

      <div class="cp-hue-row">
        <div ref="hueRef" class="cp-hue" @pointerdown="onHuePointerDown">
          <div class="cp-hue-handle" :style="{ left: (hue / 360 * 100) + '%', background: hueHandleColor }" />
        </div>
        <button type="button" class="cp-shuffle" title="Random color" @click="randomize">
          <Icon :icon="Shuffle" :size="14" />
        </button>
      </div>

      <div class="cp-hex-row">
        <span class="cp-hex-dot" :style="{ background: currentHex }" />
        <input
          v-model="hexDraft" class="cp-hex-input" placeholder="#RRGGBB" maxlength="7"
          spellcheck="false" @keydown.enter="commitHexDraft" @blur="commitHexDraft"
        />
      </div>

      <button v-if="modelValue" type="button" class="cp-clear" @click="pick(null)">Clear color</button>
    </div>
  </Dropdown>
</template>

<script setup>
// The custom picker: "the generic color picker looks bad on many places" —
// a native <input type="color"> is exactly that generic picker (a
// different, inconsistent-looking OS dialog per browser/platform), so this
// avoids it entirely. Full HSV picker (preset dots + saturation/value field
// + hue slider + hex readout) — pointer-driven, no canvas, mirroring the
// same "read the pointer position off a bounding rect" pattern the
// dashboard's own custom resize handle already uses (see DashboardView.vue's
// onCustomResizeStart/Move/End).
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { Shuffle } from 'lucide-vue-next'
import Dropdown from './Dropdown.vue'
import Icon from './Icon.vue'

const props = defineProps({
  modelValue: { type: String, default: null }, // hex string, or null = unset/default
  label:      { type: String, default: '' },
  size:       { type: String, default: 'md' }, // sm | md
})
const emit = defineEmits(['update:modelValue'])

const PRESETS = [
  '#ef4444', '#f97316', '#f59e0b', '#22c55e', '#06b6d4',
  '#3b82f6', '#8b5cf6', '#ec4899', '#f43f5e',
]

// ── HSV <-> hex ──────────────────────────────────────────────────────────
function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '')
  if (!m) return [0, 0, 0]
  return [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)]
}
function rgbToHsv(r, g, b) {
  r /= 255; g /= 255; b /= 255
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min
  let h = 0
  if (d !== 0) {
    if (max === r) h = 60 * (((g - b) / d) % 6)
    else if (max === g) h = 60 * ((b - r) / d + 2)
    else h = 60 * ((r - g) / d + 4)
  }
  if (h < 0) h += 360
  return { h, s: max === 0 ? 0 : (d / max) * 100, v: max * 100 }
}
function hsvToRgb(h, s, v) {
  s /= 100; v /= 100
  const c = v * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m = v - c
  let r = 0, g = 0, b = 0
  if (h < 60) [r, g, b] = [c, x, 0]
  else if (h < 120) [r, g, b] = [x, c, 0]
  else if (h < 180) [r, g, b] = [0, c, x]
  else if (h < 240) [r, g, b] = [0, x, c]
  else if (h < 300) [r, g, b] = [x, 0, c]
  else [r, g, b] = [c, 0, x]
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)]
}
function rgbToHex(r, g, b) { return '#' + [r, g, b].map((n) => n.toString(16).padStart(2, '0')).join('') }
function hexToHsv(hex) { const [r, g, b] = hexToRgb(hex); return rgbToHsv(r, g, b) }
function hsvToHex(h, s, v) { return rgbToHex(...hsvToRgb(h, s, v)) }

// Local h/s/v is the actual drag state — round-tripping every pixel move
// through hex would drift hue whenever s or v hits 0 (a hex of pure black or
// white has no recoverable hue). Only re-synced from the prop when it
// changes to something OUR OWN emit didn't just produce.
const hue = ref(0), sat = ref(0), val = ref(100)
const currentHex = computed(() => hsvToHex(hue.value, sat.value, val.value))
watch(
  () => props.modelValue,
  (v) => {
    if (!v || v.toLowerCase() === currentHex.value.toLowerCase()) return
    const hsv = hexToHsv(v)
    hue.value = hsv.h; sat.value = hsv.s; val.value = hsv.v
  },
  { immediate: true },
)

const hexDraft = ref(props.modelValue || '')
watch(currentHex, (h) => { hexDraft.value = h })
watch(() => props.modelValue, (v) => { if (v) hexDraft.value = v })

function emitColor() { emit('update:modelValue', currentHex.value) }
function isActive(c) { return !!props.modelValue && c.toLowerCase() === props.modelValue.toLowerCase() }
function pick(c) {
  if (c) { const hsv = hexToHsv(c); hue.value = hsv.h; sat.value = hsv.s; val.value = hsv.v }
  emit('update:modelValue', c)
}
function commitHexDraft() {
  if (/^#[0-9a-fA-F]{6}$/.test(hexDraft.value)) pick(hexDraft.value)
  else hexDraft.value = currentHex.value
}
function randomize() {
  hue.value = Math.floor(Math.random() * 360)
  sat.value = 55 + Math.random() * 40
  val.value = 70 + Math.random() * 25
  emitColor()
}

const svBackground = computed(() =>
  `linear-gradient(to top, #000, transparent), linear-gradient(to right, #fff, transparent), hsl(${hue.value}, 100%, 50%)`
)
const hueHandleColor = computed(() => `hsl(${hue.value}, 100%, 50%)`)

// ── pointer drag: SV field ──────────────────────────────────────────────
const svRef = ref(null)
let svDragging = false
function svUpdate(e) {
  const r = svRef.value.getBoundingClientRect()
  const x = Math.min(Math.max(e.clientX - r.left, 0), r.width)
  const y = Math.min(Math.max(e.clientY - r.top, 0), r.height)
  sat.value = (x / r.width) * 100
  val.value = 100 - (y / r.height) * 100
  emitColor()
}
function onSvPointerDown(e) {
  svDragging = true
  svUpdate(e)
  window.addEventListener('pointermove', onSvPointerMove)
  window.addEventListener('pointerup', onSvPointerUp)
}
function onSvPointerMove(e) { if (svDragging) svUpdate(e) }
function onSvPointerUp() {
  svDragging = false
  window.removeEventListener('pointermove', onSvPointerMove)
  window.removeEventListener('pointerup', onSvPointerUp)
}

// ── pointer drag: hue slider ─────────────────────────────────────────────
const hueRef = ref(null)
let hueDragging = false
function hueUpdate(e) {
  const r = hueRef.value.getBoundingClientRect()
  const x = Math.min(Math.max(e.clientX - r.left, 0), r.width)
  hue.value = (x / r.width) * 360
  emitColor()
}
function onHuePointerDown(e) {
  hueDragging = true
  hueUpdate(e)
  window.addEventListener('pointermove', onHuePointerMove)
  window.addEventListener('pointerup', onHuePointerUp)
}
function onHuePointerMove(e) { if (hueDragging) hueUpdate(e) }
function onHuePointerUp() {
  hueDragging = false
  window.removeEventListener('pointermove', onHuePointerMove)
  window.removeEventListener('pointerup', onHuePointerUp)
}

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onSvPointerMove)
  window.removeEventListener('pointerup', onSvPointerUp)
  window.removeEventListener('pointermove', onHuePointerMove)
  window.removeEventListener('pointerup', onHuePointerUp)
})
</script>

<style scoped>
.cp-trigger {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 6px; border-radius: var(--radius-md);
  border: 1px solid var(--border); background: var(--surface);
  cursor: pointer; transition: border-color .12s;
}
.cp-trigger:hover { border-color: var(--border-hover, var(--border)); }
.cp-trigger-sm { padding: 3px 5px; }

.cp-swatch {
  display: flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; border-radius: var(--radius-sm);
  border: 1px solid color-mix(in oklab, var(--foreground) 12%, transparent);
  color: var(--muted); flex-shrink: 0;
}
.cp-swatch-empty { width: 10px; height: 10px; }

.cp-trigger-label { font-size:var(--text-sm); font-weight: 500; color: var(--foreground); }

.cp-panel { display: flex; flex-direction: column; gap: 10px; padding: 4px; width: 216px; }

.cp-dot-row { display: flex; align-items: center; justify-content: space-between; }
.cp-dot {
  width: 20px; height: 20px; border-radius: 999px; cursor: pointer; flex-shrink: 0;
  border: 2px solid transparent; box-shadow: 0 0 0 1px color-mix(in oklab, var(--foreground) 10%, transparent) inset;
  transition: transform .1s;
}
.cp-dot:hover { transform: scale(1.15); }
.cp-dot-active { border-color: var(--surface); box-shadow: 0 0 0 2px var(--foreground); }

.cp-sv {
  position: relative; width: 100%; aspect-ratio: 1.35; border-radius: var(--radius-md);
  cursor: crosshair; touch-action: none; overflow: hidden;
}
.cp-sv-handle {
  position: absolute; width: 14px; height: 14px; border-radius: 999px;
  border: 2px solid #fff; box-shadow: 0 0 0 1px rgb(0 0 0 / .35), 0 1px 3px rgb(0 0 0 / .3);
  transform: translate(-50%, -50%); pointer-events: none;
}

.cp-hue-row { display: flex; align-items: center; gap: 8px; }
.cp-hue {
  position: relative; flex: 1; height: 12px; border-radius: 999px; cursor: pointer; touch-action: none;
  background: linear-gradient(to right, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00);
}
.cp-hue-handle {
  position: absolute; top: 50%; width: 16px; height: 16px; border-radius: 999px;
  border: 2px solid #fff; box-shadow: 0 0 0 1px rgb(0 0 0 / .35), 0 1px 3px rgb(0 0 0 / .3);
  transform: translate(-50%, -50%); pointer-events: none;
}
.cp-shuffle {
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  width: 26px; height: 26px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted); cursor: pointer;
}
.cp-shuffle:hover { color: var(--foreground); background: var(--surface-secondary); }

.cp-hex-row {
  display: flex; align-items: center; gap: 8px; height: 30px; padding: 0 10px;
  border-radius: var(--radius-md); background: var(--surface-secondary);
}
.cp-hex-dot { width: 14px; height: 14px; border-radius: 999px; flex-shrink: 0; box-shadow: 0 0 0 1px color-mix(in oklab, var(--foreground) 12%, transparent) inset; }
.cp-hex-input {
  flex: 1; min-width: 0; height: 100%; border: none; background: none; outline: none;
  font-size:var(--text-sm); font-weight: 500; font-family: var(--font-mono, monospace); color: var(--foreground);
}

.cp-clear {
  font-size:var(--text-sm); font-weight: 500; color: var(--muted); background: none; border: none;
  cursor: pointer; text-align: left; padding: 2px 0;
}
.cp-clear:hover { color: var(--danger); }
</style>
