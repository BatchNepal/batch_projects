<template>
  <div class="flex items-start flex-wrap gap-12">
    <div v-for="metric in metrics" :key="metric.label" class="flex flex-col min-w-[72px]">
      <span class="text-[11px] font-medium uppercase tracking-wider text-muted leading-none mb-2">
        {{ metric.label }}
      </span>
      <span
        class="text-[28px] font-semibold leading-none tabular-nums"
        :class="!metric.value && metric.value !== '0' ? 'text-muted' : 'text-foreground'"
      >
        {{ metric.value ?? '—' }}
      </span>
      <!-- Trend indicator: { delta: number, period: string } -->
      <div v-if="metric.trend" class="flex items-center gap-1 mt-2">
        <span
          class="text-[11px] font-medium tabular-nums"
          :class="metric.trend.delta > 0 ? 'text-success' : metric.trend.delta < 0 ? 'text-danger' : 'text-muted'"
        >
          {{ metric.trend.delta > 0 ? '↑' : metric.trend.delta < 0 ? '↓' : '—' }}
          {{ Math.abs(metric.trend.delta) }}
        </span>
        <span class="text-[11px] text-muted">{{ metric.trend.period }}</span>
      </div>
      <span v-else-if="metric.sub" class="text-[11px] text-muted mt-2 leading-none">
        {{ metric.sub }}
      </span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  // [{ label, value, sub?, trend?: { delta: number, period: string } }]
  metrics: { type: Array, required: true },
})
</script>
