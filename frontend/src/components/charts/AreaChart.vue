<template>
  <div class="ac" ref="el">
    <svg v-if="w" :width="w" :height="height" class="ac-svg" :class="{ on: mounted }">
      <defs>
        <linearGradient :id="gid" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="color" stop-opacity="0.28" />
          <stop offset="100%" :stop-color="color" stop-opacity="0.02" />
        </linearGradient>
      </defs>

      <line v-for="t in yTicks" :key="t.v" :x1="ML" :x2="w - MR" :y1="t.y" :y2="t.y" class="ac-grid" />
      <text v-for="t in yTicks" :key="'l' + t.v" :x="ML - 8" :y="t.y + 3" class="ac-axis" text-anchor="end">{{ fmt(t.v) }}</text>

      <path :d="areaPath" :fill="`url(#${gid})`" class="ac-area" />
      <path :d="linePath" fill="none" :stroke="color" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" class="ac-line" />

      <g v-if="hi > -1">
        <line :x1="pts[hi].x" :x2="pts[hi].x" :y1="MT" :y2="height - MB" class="ac-cross" />
        <circle :cx="pts[hi].x" :cy="pts[hi].y" r="4" :fill="color" stroke="#fff" stroke-width="1.5" />
      </g>

      <rect v-for="(p, i) in pts" :key="'h' + i" :x="p.x - band / 2" :y="MT" :width="band" :height="height - MT - MB"
            fill="transparent" @mousemove="hover(i, $event)" @mouseleave="hi = -1" />

      <text v-for="(it, i) in shownLabels" :key="'x' + i" :x="pts[it].x" :y="height - MB + 14" class="ac-axis" text-anchor="middle">{{ trunc(items[it].label) }}</text>
    </svg>

    <div v-if="hi > -1" class="ac-tip" :style="{ left: pts[hi].x + 'px', top: (pts[hi].y - 8) + 'px' }">
      <span class="ac-tip-l">{{ items[hi].label }}</span>
      <span class="ac-tip-v"><i :style="{ background: color }" />{{ fmt(items[hi].value) }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  height: { type: Number, default: 220 },
  color: { type: String, default: '#0B6BCB' },
  format: { type: Function, default: null },
})

const ML = 34, MR = 12, MT = 12, MB = 24
const el = ref(null), w = ref(0), mounted = ref(false)
const gid = 'acg-' + Math.random().toString(36).slice(2, 7)
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
const yTicks = computed(() => { const o = []; for (let i = 0; i <= 4; i++) { const v = yMax.value * i / 4; o.push({ v: Math.round(v * 10) / 10, y: MT + chartH.value - (v / yMax.value) * chartH.value }) } return o })

const n = computed(() => props.items.length || 1)
const band = computed(() => (w.value - ML - MR) / Math.max(1, n.value - 1 || 1))
const pts = computed(() => props.items.map((it, i) => ({
  x: ML + (n.value > 1 ? (i / (n.value - 1)) * (w.value - ML - MR) : 0),
  y: MT + chartH.value - (it.value / yMax.value) * chartH.value,
})))

function smooth(p) {
  if (p.length < 2) return p.length ? `M${p[0].x},${p[0].y}` : ''
  let d = `M${p[0].x},${p[0].y}`
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] || p[i], p1 = p[i], p2 = p[i + 1], p3 = p[i + 2] || p2
    const c1x = p1.x + (p2.x - p0.x) / 6, c1y = p1.y + (p2.y - p0.y) / 6
    const c2x = p2.x - (p3.x - p1.x) / 6, c2y = p2.y - (p3.y - p1.y) / 6
    d += ` C${c1x},${c1y} ${c2x},${c2y} ${p2.x},${p2.y}`
  }
  return d
}
const linePath = computed(() => smooth(pts.value))
const areaPath = computed(() => {
  if (!pts.value.length) return ''
  const base = props.height - MB
  return smooth(pts.value) + ` L${pts.value[pts.value.length - 1].x},${base} L${pts.value[0].x},${base} Z`
})
const shownLabels = computed(() => {
  const total = n.value
  const step = Math.ceil(total / 8)
  const out = []
  for (let i = 0; i < total; i += step) out.push(i)
  if (out[out.length - 1] !== total - 1) out.push(total - 1)
  return out
})

function fmt(v) { return props.format ? props.format(v) : (Number.isInteger(v) ? v : (+v).toFixed(1)) }
function trunc(s) { s = String(s); return s.length > 7 ? s.slice(0, 6) + '…' : s }

const hi = ref(-1)
function hover(i) { hi.value = i }
</script>

<style scoped>
.ac { position: relative; width: 100%; }
.ac-svg { display: block; }
.ac-grid { stroke: var(--surface-secondary); stroke-width: 1; shape-rendering: crispEdges; }
.ac-axis { fill: var(--muted); font-size:var(--text-xs); font-family: var(--font-sans); }
.ac-cross { stroke: var(--border-secondary); stroke-width: 1; stroke-dasharray: 3 3; }

.ac-area { opacity: 0; transition: opacity .6s ease; }
.ac-svg.on .ac-area { opacity: 1; }
.ac-line { stroke-dasharray: 2000; stroke-dashoffset: 2000; }
.ac-svg.on .ac-line { transition: stroke-dashoffset 1s cubic-bezier(.4, 0, .2, 1); stroke-dashoffset: 0; }

.ac-tip {
  position: absolute; z-index: 20; pointer-events: none; transform: translate(-50%, -100%);
  background: var(--foreground); color: var(--background); border-radius: 8px; padding: 6px 9px;
  display: flex; flex-direction: column; gap: 1px; box-shadow: 0 4px 14px rgba(11, 13, 14, .25); white-space: nowrap;
}
.ac-tip-l { font-size:var(--text-xs); color: var(--border-secondary); }
.ac-tip-v { display: inline-flex; align-items: center; gap: 6px; font-size:var(--text-base); font-weight: var(--font-semibold); }
.ac-tip-v i { width: 8px; height: 8px; border-radius: 2px; }
</style>
