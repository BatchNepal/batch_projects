<template>
  <div class="min-h-full bg-background">
    <div class="px-6 py-5">

      <!-- Header -->
      <header class="flex items-center justify-between mb-6 gap-4">
        <div>
          <h1 class="text-[15px] font-semibold text-foreground leading-6">Margin Report</h1>
          <p class="mt-0.5 text-base text-muted">
            Revenue vs cost — {{ fromLabel }} to {{ toLabel }}
          </p>
        </div>
        <div class="rp-seg">
          <button
            v-for="p in PERIOD_OPTIONS" :key="p.value"
            type="button"
            class="rp-seg-btn"
            :class="period === p.value ? 'on' : ''"
            @click="setPeriod(p.value)"
          >{{ p.label }}</button>
        </div>
      </header>

      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-20 gap-2 text-base text-muted">
        <Spinner class="text-accent" style="width:20px;height:20px" />
      </div>

      <template v-else>
        <!-- KPI strip -->
        <div class="grid grid-cols-4 gap-3 mb-5">
          <KpiTile label="Total Revenue" :value="fmtCurrency(data.summary?.total_revenue)" subline="invoiced this period" />
          <KpiTile label="Total Cost"    :value="fmtCurrency(data.summary?.total_cost)"    subline="timesheet × rate" />
          <KpiTile label="Gross Margin"  :value="fmtCurrency(data.summary?.total_margin)"  :subline="(data.summary?.margin_pct || 0) + '% margin rate'" />
          <KpiTile label="Hours Logged"  :value="(data.summary?.total_hours || 0) + 'h'"   subline="across all projects" />
        </div>

        <!-- Revenue note -->
        <div v-if="!hasRevenue" class="flex items-start gap-3 mb-4 px-4 py-3 rounded-md bg-accent-soft border border-accent text-accent-soft-foreground text-base">
          <svg class="w-4 h-4 shrink-0 mt-0.5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <span>
            Revenue figures come from ERPNext <strong class="font-semibold">Sales Invoices</strong> linked to projects.
            Set an <strong class="font-semibold">Hourly Rate</strong> on each project to see cost calculations.
          </span>
        </div>

        <!-- Empty -->
        <div v-if="!data.projects?.length" class="bg-surface rounded-lg shadow-surface overflow-hidden">
          <EmptyState :icon="TrendingUp" title="No project data" description="No active projects found." />
        </div>

        <!-- Table -->
        <div v-else class="bg-surface rounded-lg shadow-surface overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full border-collapse text-base">
              <thead>
                <tr class="border-b border-separator bg-surface-secondary">
                  <th class="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted min-w-[200px]">Project</th>
                  <th class="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted min-w-[90px]">Type</th>
                  <th class="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-muted min-w-[100px]">Budget</th>
                  <th class="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-muted min-w-[100px]">Revenue</th>
                  <th class="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-muted min-w-[80px]">Hours</th>
                  <th class="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-muted min-w-[100px]">Cost</th>
                  <th class="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-muted min-w-[110px]">Margin</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="p in data.projects"
                  :key="p.project"
                  class="border-b border-separator last:border-0 hover:bg-surface-secondary transition-colors duration-90"
                >
                  <!-- Project -->
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2.5">
                      <ProjectAvatar :theme="p.theme" :seed="p.key" size="xs" />
                      <div class="min-w-0">
                        <p class="text-base font-medium text-foreground truncate leading-none">{{ p.project_name }}</p>
                        <p class="text-xs text-muted mt-0.5 leading-none">{{ p.client || p.key }}</p>
                      </div>
                    </div>
                  </td>
                  <!-- Type -->
                  <td class="px-4 py-3">
                    <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium" :class="typeClass(p.project_type)">
                      {{ typeLabelMap[p.project_type] || p.project_type || 'Internal' }}
                    </span>
                  </td>
                  <!-- Budget -->
                  <td class="px-4 py-3 text-right">
                    <p class="text-base tabular-nums text-muted">{{ p.budget > 0 ? fmtCurrency(p.budget) : '—' }}</p>
                    <p v-if="p.budget > 0" class="text-xs mt-0.5 tabular-nums font-medium"
                       :class="p.budget_used_pct > 100 ? 'text-danger' : p.budget_used_pct >= 85 ? 'text-warning' : 'text-muted'">
                      {{ p.budget_used_pct }}% used
                    </p>
                  </td>
                  <!-- Revenue -->
                  <td class="px-4 py-3 text-right">
                    <p class="text-base tabular-nums" :class="p.revenue > 0 ? 'text-foreground font-medium' : 'text-muted'">
                      {{ p.revenue > 0 ? fmtCurrency(p.revenue) : '—' }}
                    </p>
                  </td>
                  <!-- Hours -->
                  <td class="px-4 py-3 text-right">
                    <p class="text-base tabular-nums text-muted">{{ p.hours > 0 ? p.hours + 'h' : '—' }}</p>
                    <p v-if="p.hourly_rate > 0" class="text-xs text-muted mt-0.5">@ {{ fmtCurrency(p.hourly_rate) }}/h</p>
                  </td>
                  <!-- Cost -->
                  <td class="px-4 py-3 text-right" :title="costParts(p)">
                    <p class="text-base tabular-nums text-muted">{{ p.cost > 0 ? fmtCurrency(p.cost) : '—' }}</p>
                    <p v-if="hasNonLabor(p)" class="text-xs text-muted mt-0.5">incl. materials/expenses</p>
                  </td>
                  <!-- Margin -->
                  <td class="px-4 py-3 text-right">
                    <template v-if="p.revenue > 0 || p.cost > 0">
                      <p class="text-base font-semibold tabular-nums"
                         :class="p.margin > 0 ? 'text-success-soft-foreground' : p.margin < 0 ? 'text-danger-soft-foreground' : 'text-muted'">
                        {{ fmtCurrency(p.margin) }}
                      </p>
                      <p v-if="p.revenue > 0" class="text-xs tabular-nums mt-0.5"
                         :class="p.margin_pct >= 20 ? 'text-success-soft-foreground' : p.margin_pct >= 0 ? 'text-muted' : 'text-danger'">
                        {{ p.margin_pct }}%
                      </p>
                    </template>
                    <span v-else class="text-base text-muted">—</span>
                  </td>
                </tr>
              </tbody>

              <!-- Totals -->
              <tfoot v-if="data.projects?.length">
                <tr class="border-t-2 border-border bg-surface-secondary">
                  <td class="px-4 py-3 text-sm font-semibold text-foreground" colspan="3">
                    Total ({{ data.projects.length }} project{{ data.projects.length !== 1 ? 's' : '' }})
                  </td>
                  <td class="px-4 py-3 text-right text-base font-semibold tabular-nums text-foreground">
                    {{ data.summary?.total_revenue > 0 ? fmtCurrency(data.summary.total_revenue) : '—' }}
                  </td>
                  <td class="px-4 py-3 text-right text-base font-semibold tabular-nums text-muted">
                    {{ (data.summary?.total_hours || 0) + 'h' }}
                  </td>
                  <td class="px-4 py-3 text-right text-base font-semibold tabular-nums text-muted">
                    {{ data.summary?.total_cost > 0 ? fmtCurrency(data.summary.total_cost) : '—' }}
                  </td>
                  <td class="px-4 py-3 text-right">
                    <p class="text-base font-semibold tabular-nums"
                       :class="(data.summary?.total_margin || 0) > 0 ? 'text-success-soft-foreground' : (data.summary?.total_margin || 0) < 0 ? 'text-danger-soft-foreground' : 'text-muted'">
                      {{ data.summary?.total_revenue > 0 || data.summary?.total_cost > 0
                          ? fmtCurrency(data.summary.total_margin) : '—' }}
                    </p>
                    <p v-if="data.summary?.total_revenue > 0" class="text-xs text-muted mt-0.5 tabular-nums">
                      {{ data.summary.margin_pct }}%
                    </p>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </template>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getMarginReport } from '@/utils/api'
import { toast } from 'vue-sonner'
import EmptyState from '@/ui/EmptyState.vue'
import Spinner from '@/ui/Spinner.vue'
import ProjectAvatar from '@/ui/ProjectAvatar.vue'
import KpiTile from '@/ui/KpiTile.vue'
import { TrendingUp } from 'lucide-vue-next'

const PERIOD_OPTIONS = [
  { value: 'last_7_days',  label: '7D'  },
  { value: 'last_30_days', label: '30D' },
  { value: 'last_90_days', label: '90D' },
]

const typeLabelMap = {
  internal: 'Internal',
  fixed:    'Fixed',
  retainer: 'Retainer',
  tm:       'T&M',
}

const period  = ref('last_30_days')
const loading = ref(true)
const data    = ref({ summary: {}, projects: [], from_date: '', to_date: '' })

const fromLabel  = computed(() => fmtDate(data.value.from_date))
const toLabel    = computed(() => fmtDate(data.value.to_date))
const hasRevenue = computed(() => (data.value.summary?.total_revenue || 0) > 0)

function fmtDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function fmtCurrency(n) {
  if (n == null) return '0'
  const abs = Math.abs(n)
  let str
  if (abs >= 1_000_000)  str = (Math.abs(n) / 1_000_000).toFixed(1) + 'M'
  else if (abs >= 1_000) str = (Math.abs(n) / 1_000).toFixed(1) + 'K'
  else                   str = Math.abs(n).toFixed(0)
  return n < 0 ? '−' + str : str
}

function hasNonLabor(p) {
  const b = p.cost_breakdown || {}
  return (b.materials || 0) > 0 || (b.expenses || 0) > 0
}
function costParts(p) {
  const b = p.cost_breakdown || {}
  const parts = []
  if ((b.labor || 0) > 0) parts.push('Labor ' + fmtCurrency(b.labor))
  if ((b.materials || 0) > 0) parts.push('Materials ' + fmtCurrency(b.materials))
  if ((b.expenses || 0) > 0) parts.push('Expenses ' + fmtCurrency(b.expenses))
  return parts.join('  ·  ') || 'No cost recorded'
}

function typeClass(t) {
  if (t === 'internal') return 'bg-default text-muted'
  if (t === 'fixed')    return 'bg-accent-soft text-accent-soft-foreground'
  if (t === 'retainer') return 'bg-success-soft text-success-soft-foreground'
  if (t === 'tm')       return 'bg-warning-soft text-warning-soft-foreground'
  return 'bg-default text-muted'
}

function setPeriod(p) {
  period.value = p
  load()
}

async function load() {
  loading.value = true
  try {
    data.value = await getMarginReport(period.value)
  } catch (e) {
    toast.error("Couldn't load margin report", { description: String(e.message || e) })
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.rp-seg { display: flex; align-items: center; background: var(--surface); border: 1px solid var(--border); border-radius: 7px; overflow: hidden; }
.rp-seg-btn { height: 28px; padding: 0 11px; font-size: 12px; font-weight: 500; color: var(--muted); background: transparent; cursor: pointer; transition: all .12s; white-space: nowrap; }
.rp-seg-btn.on { background: var(--surface-secondary); color: var(--foreground); font-weight: 600; }
.rp-seg-btn + .rp-seg-btn { border-left: 1px solid var(--border); }
</style>
