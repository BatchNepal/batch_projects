<template>
  <div class="ch" ref="el">
    <svg v-if="w" :width="w" :height="height" class="ch-svg" :class="{ on: mounted }">
      <defs>
        <linearGradient v-for="(it, i) in items" :key="i" :id="gid(i)" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="it.color" stop-opacity="0.95" />
          <stop offset="100%" :stop-color="it.color" stop-opacity="0.62" />
        </linearGradient>
      </defs>

      <!-- gridlines + y axis -->
      <g>
        <line v-for="t in yTicks" :key="'g' + t.v" :x1="ML" :x2="w - MR" :y1="t.y" :y2="t.y" class="ch-grid" />
        <text v-for="t in yTicks" :key="'l' + t.v" :x="ML - 8" :y="t.y + 3" class="ch-axis" text-anchor="end">{{ fmt(t.v) }}</text>
      </g>

      <!-- bars -->
      <g>
        <template v-for="(it, i) in items" :key="i">
          <rect
            class="ch-bar" :class="{ dim: hi > -1 && hi !== i }"
            :x="bx(i)" :y="by(it.value)" :width="bw" :height="bh(it.value)"
            :rx="Math.min(5, bw / 2)" :fill="`url(#${gid(i)})`"
            :style="{ transitionDelay: i * 28 + 'ms' }"
            @mousemove="hover(i, $event)" @mouseleave="hi = -1" />
          <text :x="bx(i) + bw / 2" :y="height - MB + 14" class="ch-axis" text-anchor="middle">{{ trunc(it.label) }}</text>
        </template>
      </g>
    </svg>

    <div v-if="hi > -1" class="ch-tip" :style="{ left: tipX + 'px', top: tipY + 'px' }">
      <span class="ch-tip-l">{{ items[hi].label }}</span>
      <span class="ch-tip-v"><i :style="{ background: items[hi].color }" />{{ fmt(items[hi].value) }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  height: { type: Number, default: 220 },
  format: { type: Function, default: null },
})

const ML = 36, MR = 10, MT = 12, MB = 24
const el = ref(null)
const w = ref(0)
const mounted = ref(false)
const uid = Math.random().toString(36).slice(2, 7)
let ro
onMounted(() => {
  ro = new ResizeObserver(e => { w.value = Math.floor(e[0].contentRect.width) })
  ro.observe(el.value)
  requestAnimationFrame(() => requestAnimationFrame(() => { mounted.value = true }))
})
onUnmounted(() => ro && ro.disconnect())

const maxV = computed(() => Math.max(1, ...props.items.map(i => i.value)))
function niceMax(v) { const p = Math.pow(10, Math.floor(Math.log10(v))); const n = v / p; const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10; return m * p }
const yMax = computed(() => niceMax(maxV.value))
const chartH = computed(() => props.height - MT - MB)
const yTicks = computed(() => {
  const out = []
  for (let i = 0; i <= 4; i++) { const v = yMax.value * i / 4; out.push({ v: Math.round(v * 10) / 10, y: MT + chartH.value - (v / yMax.value) * chartH.value }) }
  return out
})
const n = computed(() => props.items.length || 1)
const band = computed(() => (w.value - ML - MR) / n.value)
const bw = computed(() => Math.max(6, Math.min(band.value * 0.6, 46)))
function bx(i) { return ML + i * band.value + (band.value - bw.value) / 2 }
function bh(v) { return Math.max(v > 0 ? 2 : 0, (v / yMax.value) * chartH.value) }
function by(v) { return MT + chartH.value - bh(v) }
function gid(i) { return `chg-${uid}-${i}` }
function fmt(v) { return props.format ? props.format(v) : (Number.isInteger(v) ? v : (+v).toFixed(1)) }
function trunc(s) { s = String(s); return s.length > 9 ? s.slice(0, 8) + '…' : s }

const hi = ref(-1), tipX = ref(0), tipY = ref(0)
function hover(i, e) { hi.value = i; const r = el.value.getBoundingClientRect(); tipX.value = e.clientX - r.left + 12; tipY.value = e.clientY - r.top - 8 }
</script>

<style scoped>
.ch { position: relative; width: 100%; }
.ch-svg { display: block; }
.ch-grid { stroke: var(--surface-secondary); stroke-width: 1; shape-rendering: crispEdges; }
.ch-axis { fill: var(--muted); font-size:var(--text-xs); font-family: var(--font-sans); }

.ch-bar {
  cursor: pointer;
  transform: scaleY(0); transform-box: fill-box; transform-origin: bottom center;
  transition: transform .55s cubic-bezier(.22, 1, .36, 1), opacity .15s, filter .15s;
}
.ch-svg.on .ch-bar { transform: scaleY(1); }
.ch-bar:hover { filter: brightness(1.06); }
.ch-bar.dim { opacity: .32; }

.ch-tip {
  position: absolute; z-index: 20; pointer-events: none; transform: translateY(-100%);
  background: var(--foreground); color: var(--background); border-radius: 8px; padding: 6px 9px;
  display: flex; flex-direction: column; gap: 1px; box-shadow: 0 4px 14px rgba(11, 13, 14, .25); white-space: nowrap;
}
.ch-tip-l { font-size:var(--text-xs); color: var(--border-secondary); }
.ch-tip-v { display: inline-flex; align-items: center; gap: 6px; font-size:var(--text-base); font-weight: var(--font-semibold); }
.ch-tip-v i { width: 8px; height: 8px; border-radius: 2px; }
</style>
