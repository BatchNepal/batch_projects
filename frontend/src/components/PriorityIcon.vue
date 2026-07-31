<template>
  <span :title="priority" class="pi-root" :class="`pi-${key}`">
    <span
      v-for="(filled, i) in cfg.bars" :key="i"
      class="pi-bar"
      :style="{
        height: HEIGHTS[i],
        background: mono ? 'currentColor' : (filled ? cfg.color : 'currentColor'),
        opacity: filled ? (mono ? 0.35 + i * 0.2 : 1) : (mono ? 0.14 : 0.18),
      }"
    />
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  priority: { type: String, default: 'Medium' },
  mono: { type: Boolean, default: false },
})

const CONFIG = {
  Highest: { bars: [true, true, true, true],   color: '#EF4444', key: 'highest' },
  High:    { bars: [true, true, true, false],  color: '#F97316', key: 'high'    },
  Medium:  { bars: [true, true, false, false], color: '#F59E0B', key: 'medium'  },
  Low:     { bars: [true, false, false, false],color: '#60A5FA', key: 'low'     },
  Lowest:  { bars: [true, false, false, false],color: '#94A3B8', key: 'lowest'  },
}

// stepped heights — taller right to left signal look
const HEIGHTS = ['5px', '8px', '11px', '14px']

const cfg = computed(() => CONFIG[props.priority] || CONFIG.Medium)
const key = computed(() => CONFIG[props.priority]?.key || 'medium')
</script>

<style scoped>
.pi-root {
  display: inline-flex;
  align-items: flex-end;
  gap: 1.5px;
  height: 14px;
  flex-shrink: 0;
}
.pi-bar {
  width: 3px;
  border-radius: 1px;
  flex-shrink: 0;
  transition: opacity .15s;
}
</style>