<template>
  <svg
    width="14"
    height="14"
    viewBox="0 0 14 14"
    :aria-label="priority || 'none'"
    role="img"
    class="shrink-0"
  >
    <rect x="0"  y="9" width="3" height="5"  rx="0.5" :fill="colors[0]" />
    <rect x="5"  y="6" width="3" height="8"  rx="0.5" :fill="colors[1]" />
    <rect x="10" y="3" width="3" height="11" rx="0.5" :fill="colors[2]" />
    <!-- Urgent dot sits just above bar 3, distinguishing it from high at 14px -->
    <circle v-if="normalized === 'urgent'" cx="11.5" cy="1.5" r="1.5" fill="#ef4444" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  priority: { type: String, default: '' },
})

// Normalize both naming conventions:
//   App uses:    Highest / High / Medium / Low / Lowest / (empty)
//   Pattern doc: urgent  / high / medium / low / none
const NORM = {
  '': 'none', none: 'none',
  lowest: 'low',  low: 'low',
  medium: 'medium',
  high: 'high',
  highest: 'urgent', urgent: 'urgent',
}
const normalized = computed(() => NORM[(props.priority || '').toLowerCase()] ?? 'none')

// none recedes to near-invisible; high (orange) and urgent (red) are visually distinct at 14px
const PALETTE = {
  none:   ['#e4e4e7', '#f4f4f5', '#f4f4f5'],
  low:    ['#60a5fa', '#e4e4e7', '#f4f4f5'],
  medium: ['#f97316', '#f97316', '#e4e4e7'],
  high:   ['#f97316', '#f97316', '#f97316'],
  urgent: ['#ef4444', '#ef4444', '#ef4444'],
}
const colors = computed(() => PALETTE[normalized.value])
</script>
