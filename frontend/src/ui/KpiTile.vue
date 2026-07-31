<template>
  <div class="kpi-tile bg-surface rounded-[10px] border border-border px-5 py-4 cursor-pointer select-none outline-none focus-visible:shadow-focus" @click="emit('click')">
    <div class="flex items-start gap-3">
      <div v-if="icon" class="shrink-0 size-9 rounded-[10px] flex items-center justify-center" :class="ICON_BG[iconColor] ?? ICON_BG.default">
        <component :is="icon" class="size-[18px]" :class="ICON_FG[iconColor] ?? ICON_FG.default" :stroke-width="2" />
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-xs font-medium uppercase tracking-wider text-muted leading-none">{{ label }}</p>

        <div class="mt-3 flex items-baseline gap-2">
          <p class="text-[28px] font-semibold text-foreground tabular-nums leading-none">{{ value }}</p>
          <span
            v-if="delta !== null && delta !== undefined"
            class="inline-flex items-center gap-0.5 text-xs font-medium tabular-nums"
            :class="deltaGood ? 'text-success-soft-foreground' : 'text-danger-soft-foreground'"
          >
            <svg class="size-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round"
                :d="deltaGood ? 'M7 17l10-10M17 7H7m10 0v10' : 'M7 7l10 10M17 17H7m10 0V7'" />
            </svg>
            {{ Math.abs(delta) }}%
          </span>
        </div>

        <p class="mt-1.5 text-xs text-muted leading-snug tabular-nums">{{ subline }}</p>

        <div v-if="progress !== null && progress !== undefined" class="mt-3 h-1 rounded-full bg-default overflow-hidden">
          <div
            class="h-full rounded-full transition-[width] duration-400 ease-out"
            :class="progress >= 90 ? 'bg-warning' : 'bg-accent'"
            :style="{ width: Math.min(progress, 100) + '%' }"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const ICON_BG = {
  default: 'bg-default',
  accent:  'bg-accent-soft',
  success: 'bg-success-soft',
  warning: 'bg-warning-soft',
  danger:  'bg-danger-soft',
}
const ICON_FG = {
  default: 'text-muted',
  accent:  'text-accent',
  success: 'text-success',
  warning: 'text-warning',
  danger:  'text-danger',
}

defineProps({
  label:     { type: String, required: true },
  value:     { required: true },
  subline:   { type: String, default: '' },
  delta:     { default: null },
  deltaGood: { type: Boolean, default: true },
  progress:  { default: null },
  icon:      { type: [Object, Function], default: null },
  iconColor: { type: String, default: 'default' }, // default | accent | success | warning | danger
})
const emit = defineEmits(['click'])
</script>

<style scoped>
.kpi-tile {
  box-shadow: var(--shadow-xs);
  transition:
    transform 200ms var(--ease-smooth),
    border-color var(--duration-base) var(--ease-out),
    box-shadow var(--duration-base) var(--ease-out);
}
.kpi-tile:hover {
  border-color: var(--border-secondary);
  box-shadow: var(--shadow-md);
}
.kpi-tile:active {
  transform: scale(0.97);
  transition: transform 40ms ease-out;
}
</style>
