<template>
  <div class="sprint-detail-root">
    <!-- Loading state -->
    <div v-if="loading" class="space-y-5 p-1">
      <Skeleton class="h-8 w-48 rounded" />
      <Skeleton class="h-4 w-72" />
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Skeleton class="h-64 rounded-lg" />
        <Skeleton class="h-64 rounded-lg" />
      </div>
    </div>

    <template v-else-if="data">
      <!-- Header -->
      <div class="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <div class="flex items-center gap-3 mb-1">
            <router-link
              :to="`/workspace/${route.params.key}/backlog`"
              class="text-fg-muted hover:text-fg transition-colors"
            >
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
            </router-link>
            <span
              class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold"
              :class="statusBadgeClass(data.status)"
            >{{ data.status }}</span>
            <h1 class="text-xl font-semibold text-fg">{{ data.sprint_name }}</h1>
          </div>
          <div class="flex items-center gap-4 text-sm text-fg-muted ml-9">
            <span v-if="data.start_date && data.end_date" class="flex items-center gap-1.5">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
              {{ fmtDate(data.start_date) }} → {{ fmtDate(data.end_date) }}
            </span>
            <span class="flex items-center gap-1.5">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>
              {{ projectName }}
            </span>
          </div>
          <p v-if="data.goal" class="ml-9 mt-2 text-sm text-fg-muted italic">"{{ data.goal }}"</p>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <button class="btn-secondary text-xs" @click="refresh">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
            Refresh
          </button>
        </div>
      </div>

      <!-- Stat cards -->
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <div class="stat-card">
          <span class="stat-label">% Complete</span>
          <span class="stat-value">{{ data.burndown.pct_complete_effort }}%</span>
          <div class="stat-bar mt-1.5"><div class="stat-fill" :style="{width: data.burndown.pct_complete_effort + '%'}" /></div>
        </div>
        <div class="stat-card">
          <span class="stat-label">Tasks Done</span>
          <span class="stat-value">{{ data.burndown.completed_count }}<span class="text-sm font-normal text-fg-muted">/{{ data.burndown.total_tasks }}</span></span>
        </div>
        <div class="stat-card">
          <span class="stat-label">{{ labels.effortLabel }} Done</span>
          <span class="stat-value">{{ data.burndown.completed_effort }}<span class="text-sm font-normal text-fg-muted">/{{ data.burndown.total_effort }}</span></span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Days Left</span>
          <span class="stat-value">{{ Math.max(0, data.burndown.days_total - data.burndown.days_elapsed) }}<span class="text-sm font-normal text-fg-muted">/{{ data.burndown.days_total }}</span></span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Scope Change</span>
          <span class="stat-value" :class="data.burndown.scope_change > 0 ? 'text-amber-500' : 'text-emerald-500'">{{ data.burndown.scope_change > 0 ? '+' : '' }}{{ data.burndown.scope_change }} {{ labels.effortAbbr }}</span>
        </div>
      </div>

      <!-- Charts -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-5 mb-6">
        <!-- Burndown -->
        <div class="chart-card">
          <h2 class="chart-title">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"/></svg>
            {{ labels.effortLabel }} Remaining
          </h2>
          <apexchart
            v-if="burndownOptions"
            type="line"
            height="280"
            :options="burndownOptions"
            :series="burndownSeries"
          />
          <div v-else class="flex items-center justify-center h-64 text-sm text-fg-muted">
            No burndown data — sprint may not have dates set.
          </div>
        </div>

        <!-- Burnup -->
        <div class="chart-card">
          <h2 class="chart-title">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
            {{ labels.effortLabel }} Completed vs Scope
          </h2>
          <apexchart
            v-if="burnupOptions"
            type="line"
            height="280"
            :options="burnupOptions"
            :series="burnupSeries"
          />
          <div v-else class="flex items-center justify-center h-64 text-sm text-fg-muted">
            No burnup data.
          </div>
        </div>
      </div>

      <!-- Velocity -->
      <div v-if="data.velocity && data.velocity.sprints && data.velocity.sprints.length" class="chart-card mb-6">
        <h2 class="chart-title">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
            {{ labels.cycleLabel }} Completion History
            <span class="text-xs font-normal text-fg-muted ml-2">avg {{ data.velocity.average_effort }} {{ labels.effortAbbr }}/{{ labels.cycleLabel.toLowerCase() }} · {{ data.velocity.trend }}</span>
        </h2>
        <apexchart
          v-if="velocityOptions"
          type="bar"
          height="220"
          :options="velocityOptions"
          :series="velocitySeries"
        />
      </div>

      <!-- Cycle Time (if project-level data available) -->
      <div v-if="data.cycle_time && data.cycle_time.task_count > 0" class="chart-card mb-6">
        <h2 class="chart-title">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          Cycle Time
          <span class="text-xs font-normal text-fg-muted ml-2">avg {{ data.cycle_time.cycle_time_avg_days }}d · p50 {{ data.cycle_time.cycle_time_p50 }}d · p90 {{ data.cycle_time.cycle_time_p90 }}d</span>
        </h2>
        <apexchart
          v-if="cycleTimeOptions"
          type="bar"
          height="220"
          :options="cycleTimeOptions"
          :series="cycleTimeSeries"
        />
      </div>

      <!-- Status breakdown -->
      <div v-if="data.status_counts && Object.keys(data.status_counts).length" class="chart-card">
        <h2 class="chart-title">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>
          Tasks by Status
        </h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 mt-2">
          <div
            v-for="(count, status) in data.status_counts"
            :key="status"
            class="stat-card"
          >
            <span class="stat-label">{{ status }}</span>
            <span class="stat-value">{{ count }}</span>
          </div>
        </div>
      </div>

    </template>

    <div v-else class="flex flex-col items-center justify-center py-20 gap-3">
      <p class="text-fg-muted">Sprint not found.</p>
      <router-link :to="`/workspace/${route.params.key}/backlog`" class="text-brand-500 text-sm hover:underline">
        ← Back to backlog
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import VueApexCharts from "vue3-apexcharts";
import { Skeleton } from "@/ui";
import { getSprintHealth } from "@/utils/api";

const route = useRoute();
const apexchart = VueApexCharts;

const loading = ref(true);
const data = ref(null);
const error = ref(null);

const projectName = computed(() => {
  const p = route.params.key;
  // Route param may be the project key (e.g. "BIM") or a sprint name
  // We resolve it from the sprint data
  return data.value?.project || p;
});

function fmtDate(v) {
  if (!v) return "";
  try {
    return new Date(v).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch { return v; }
}

function statusBadgeClass(status) {
  const map = {
    "Planning": "bg-default text-muted",
    "Active": "bg-accent-soft text-accent-soft-foreground",
    "Completed": "bg-success-soft text-success-soft-foreground",
  };
  return map[status] || "bg-default text-muted";
}

// ── Burndown chart ──────────────────────────────────────────────────────────
const burndownOptions = computed(() => {
  const bd = data.value?.burndown;
  if (!bd || !bd.dates || !bd.dates.length) return null;
  return {
    chart: {
      type: "line",
      toolbar: { show: false },
      fontFamily: "inherit",
      background: "transparent",
    },
    stroke: { width: [3, 2], dashArray: [0, 8] },
    colors: ["#3b82f6", "#9ca3af"],
    xaxis: {
      categories: bd.dates.map(d => fmtDate(d)),
      labels: { style: { fontSize: "11px" } },
    },
    yaxis: {
      title: { text: labels.value.effortLabel + " Remaining", style: { fontSize: "11px" } },
      min: 0,
      labels: { style: { fontSize: "11px" } },
    },
    tooltip: { theme: "dark" },
    legend: { show: true, position: "top", fontSize: "12px" },
    grid: { borderColor: "rgba(128,128,128,0.15)", strokeDashArray: 5 },
  };
});
const burndownSeries = computed(() => {
  const bd = data.value?.burndown;
  if (!bd) return [];
  return [
    { name: "Actual", data: bd.actual_effort || [] },
    { name: "Ideal", data: bd.ideal_line || [] },
  ];
});

// ── Burnup chart ────────────────────────────────────────────────────────────
const burnupOptions = computed(() => {
  const bu = data.value?.burnup;
  if (!bu || !bu.dates || !bu.dates.length) return null;
  return {
    chart: {
      type: "line",
      toolbar: { show: false },
      fontFamily: "inherit",
      background: "transparent",
    },
    stroke: { width: [3, 3, 2], dashArray: [0, 0, 8] },
    colors: ["#10b981", "#f59e0b", "#9ca3af"],
    xaxis: {
      categories: bu.dates.map(d => fmtDate(d)),
      labels: { style: { fontSize: "11px" } },
    },
    yaxis: {
      title: { text: labels.value.effortLabel, style: { fontSize: "11px" } },
      min: 0,
      labels: { style: { fontSize: "11px" } },
    },
    tooltip: { theme: "dark" },
    legend: { show: true, position: "top", fontSize: "12px" },
    grid: { borderColor: "rgba(128,128,128,0.15)", strokeDashArray: 5 },
  };
});
const burnupSeries = computed(() => {
  const bu = data.value?.burnup;
  if (!bu) return [];
  return [
    { name: "Completed", data: bu.completed_line || [] },
    { name: "Total Scope", data: bu.scope_line || [] },
    { name: "Ideal", data: bu.ideal_line || [] },
  ];
});

// ── Velocity chart ──────────────────────────────────────────────────────────
const velocityOptions = computed(() => {
  const v = data.value?.velocity;
  if (!v || !v.sprints) return null;
  return {
    chart: {
      type: "bar",
      toolbar: { show: false },
      fontFamily: "inherit",
      background: "transparent",
    },
    colors: ["#3b82f6"],
    plotOptions: { bar: { borderRadius: 6, columnWidth: "60%" } },
    xaxis: {
      categories: v.sprints.map(s => s.sprint_name || s.name),
      labels: { style: { fontSize: "11px" } },
    },
    yaxis: {
      title: { text: labels.value.effortLabel + " Completed", style: { fontSize: "11px" } },
      labels: { style: { fontSize: "11px" } },
    },
    tooltip: { theme: "dark" },
    grid: { borderColor: "rgba(128,128,128,0.15)", strokeDashArray: 5 },
    annotations: v.average_effort > 0 ? {
      yaxis: [{
        y: v.average_effort,
        borderColor: "#f59e0b",
        borderWidth: 2,
        strokeDashArray: 6,
        label: {
          text: `Avg: ${v.average_effort}`,
          style: { color: "#f59e0b", fontSize: "11px" },
          position: "right",
        },
      }],
    } : undefined,
  };
});
const velocitySeries = computed(() => {
  const v = data.value?.velocity;
  if (!v) return [];
  return [{ name: "Completed", data: v.sprints.map(s => s.completed_effort) }];
});

// ── Cycle time chart ────────────────────────────────────────────────────────
const cycleTimeOptions = computed(() => {
  const ct = data.value?.cycle_time;
  if (!ct || !ct.histogram_cycle) return null;
  return {
    chart: {
      type: "bar",
      toolbar: { show: false },
      fontFamily: "inherit",
      background: "transparent",
    },
    colors: ["#8b5cf6"],
    plotOptions: { bar: { borderRadius: 6, columnWidth: "70%" } },
    xaxis: {
      categories: ct.histogram_cycle.map(h => h.bucket),
      labels: { style: { fontSize: "11px" } },
    },
    yaxis: {
      title: { text: "Tasks", style: { fontSize: "11px" } },
      labels: { style: { fontSize: "11px" } },
    },
    tooltip: { theme: "dark" },
    grid: { borderColor: "rgba(128,128,128,0.15)", strokeDashArray: 5 },
  };
});
const cycleTimeSeries = computed(() => {
  const ct = data.value?.cycle_time;
  if (!ct) return [];
  return [{ name: "Cycle Time Distribution", data: ct.histogram_cycle.map(h => h.count) }];
});

// ── Data fetching ───────────────────────────────────────────────────────────
const sprintName = computed(() => route.params.sprintId);

const labels = computed(() => {
  const bd = data.value?.burndown;
  return {
    cycleLabel: bd?.cycle_label || "Sprint",
    effortLabel: bd?.effort_label || "Story Points",
    effortAbbr: bd?.effort_label_abbr || "pts",
  };
});

async function refresh() {
  loading.value = true;
  error.value = null;
  try {
    data.value = await getSprintHealth(sprintName.value);
  } catch (e) {
    error.value = e.message || "Failed to load sprint data";
    data.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(refresh);
watch(() => route.params.key, refresh);
</script>

<style scoped>
.sprint-detail-root {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 8px 64px;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
}

.stat-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.stat-value {
  display: block;
  font-size: 22px;
  font-weight: 700;
  color: var(--foreground);
  line-height: 1.1;
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

.stat-bar {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
}
.stat-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  transition: width 0.5s ease;
}

.chart-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 20px 12px;
}

:global(.dark) .chart-card {
  background: rgba(255,255,255,0.04);
  border-color: rgba(255,255,255,0.08);
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--foreground);
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

/* --color-edge/--color-surface/--color-fg/--color-hoverbg never existed in
   tokens.css, so every one of these resolved to its hardcoded Tailwind-gray
   fallback — a white/#e5e7eb/#111827 button that ignored the theme entirely
   and went unreadable in dark mode. Retoken; 6px radius per the control band. */
.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-secondary);
  background: var(--surface);
  color: var(--foreground);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 140ms var(--ease-out), border-color 140ms var(--ease-out);
}
.btn-secondary:hover {
  background: var(--surface-hover);
  border-color: var(--border-tertiary);
}
</style>
