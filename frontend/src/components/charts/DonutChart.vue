<template>
  <div class="dn" ref="el" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size" class="dn-svg" :class="{ on: mounted }">
      <g :transform="`rotate(-90 ${cx} ${cx})`">
        <circle :cx="cx" :cy="cx" :r="r" fill="none" stroke="var(--surface-secondary)" :stroke-width="sw" />
        <circle
          v-for="(s, i) in segs" :key="i"
          class="dn-seg" :class="{ dim: hi > -1 && hi !== i }"
          :cx="cx" :cy="cx" :r="r" fill="none" :stroke="s.color"
          :stroke-width="hi === i ? sw + 3 : sw" stroke-linecap="round"
          :stroke-dasharray="`${s.len} ${C - s.len}`" :stroke-dashoffset="s.off"
          @mousemove="hover(i, $event)" @mouseleave="hi = -1" />
      </g>
    </svg>
    <div class="dn-center">
      <span class="dn-total">{{ fmt(total) }}</span>
      <span v-if="label" class="dn-label">{{ label }}</span>
    </div>
    <div v-if="hi > -1" class="dn-tip" :style="{ left: tipX + 'px', top: tipY + 'px' }">
      <span class="dn-tip-l">{{ items[hi].label }}</span>
      <span class="dn-tip-v"><i :style="{ background: items[hi].color }" />{{ fmt(items[hi].value) }} · {{ pctOf(items[hi].value) }}%</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  size: { type: Number, default: 132 },
  label: { type: String, default: '' },
  format: { type: Function, default: null },
})

const sw = computed(() => Math.round(props.size * 0.14))
const r = computed(() => (props.size - sw.value) / 2 - 2)
const cx = computed(() => props.size / 2)
const C = computed(() => 2 * Math.PI * r.value)
const total = computed(() => props.items.reduce((a, i) => a + (i.value || 0), 0))

const segs = computed(() => {
  const t = total.value || 1
  const gap = 6
  let acc = 0
  return props.items.map(it => {
    const seg = (it.value / t) * C.value
    const len = Math.max(0, seg - gap)
    const off = -acc
    acc += seg
    return { color: it.color, len, off }
  })
})

const el = ref(null)
const mounted = ref(false)
onMounted(() => requestAnimationFrame(() => requestAnimationFrame(() => { mounted.value = true })))

function fmt(v) { return props.format ? props.format(v) : (Number.isInteger(v) ? v : (+v).toFixed(1)) }
function pctOf(v) { return total.value ? Math.round((v / total.value) * 100) : 0 }

const hi = ref(-1), tipX = ref(0), tipY = ref(0)
function hover(i, e) { hi.value = i; const rc = el.value.getBoundingClientRect(); tipX.value = e.clientX - rc.left + 12; tipY.value = e.clientY - rc.top - 8 }
</script>

<style scoped>
.dn { position: relative; flex-shrink: 0; }
.dn-svg { display: block; transform: scale(.86); opacity: 0; transition: transform .5s cubic-bezier(.22, 1, .36, 1), opacity .4s; }
.dn-svg.on { transform: scale(1); opacity: 1; }
.dn-seg { cursor: pointer; transition: stroke-width .16s, opacity .16s; }
.dn-seg.dim { opacity: .3; }

.dn-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px; pointer-events: none; }
.dn-total { font-size: 19px; font-weight: var(--font-bold); color: var(--foreground); letter-spacing: -0.02em; }
.dn-label { font-size: 10px; color: var(--muted); }

.dn-tip {
  position: absolute; z-index: 20; pointer-events: none; transform: translateY(-100%);
  background: var(--foreground); color: var(--background); border-radius: 8px; padding: 6px 9px;
  display: flex; flex-direction: column; gap: 1px; box-shadow: 0 4px 14px rgba(11, 13, 14, .25); white-space: nowrap;
}
.dn-tip-l { font-size: 10.5px; color: var(--border-secondary); }
.dn-tip-v { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: var(--font-semibold); }
.dn-tip-v i { width: 8px; height: 8px; border-radius: 2px; }
</style>
