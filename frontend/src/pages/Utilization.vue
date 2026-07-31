<template>
  <div class="min-h-full bg-[var(--background)]">
    <div class="px-6 py-5">

      <!-- ── Header ─────────────────────────────────────────────────── -->
      <header class="flex items-center justify-between mb-6 gap-4">
        <div>
          <h1 class="text-xl font-semibold text-foreground leading-7">Utilization</h1>
          <p class="mt-0.5 text-sm text-muted">
            {{ fromLabel }} – {{ toLabel }}
            <span v-if="!hasTimesheetData" class="ml-2 text-xs font-medium text-warning">
              · No timesheet data —
              <a
                href="/app/timesheet"
                target="_blank"
                class="font-semibold text-warning hover:underline underline-offset-2"
              >connect ERPNext Timesheets ↗</a>
            </span>
          </p>
        </div>
        <div class="flex items-center gap-2">
          <!-- Period tabs -->
          <div class="flex items-center p-0.5 bg-surface-secondary rounded-md gap-0.5">
            <button
              v-for="p in PERIOD_OPTIONS" :key="p.value"
              type="button"
              class="px-3 h-7 text-xs font-medium rounded-sm transition-[background-color,color] duration-150 whitespace-nowrap"
              :class="period === p.value
                ? 'bg-overlay text-foreground shadow-sm'
                : 'text-muted hover:text-muted'"
              @click="setPeriod(p.value)"
            >
              {{ p.label }}
            </button>
          </div>
          <!-- Team filter -->
          <select
            v-model="selectedTeam"
            class="h-8 px-2.5 text-xs font-medium bg-overlay border border-border rounded-md shadow-sm text-muted focus:outline-none focus:ring-2 focus:ring-accent/40 cursor-pointer"
          >
            <option value="">All members</option>
            <option v-for="t in teams" :key="t.name" :value="t.name">
              {{ t.team_name || t.name }}
            </option>
          </select>
        </div>
      </header>

      <!-- ── Loading ───────────────────────────────────────────────── -->
      <div v-if="loading" class="flex items-center justify-center py-20 gap-2 text-sm text-muted">
        <Spinner class="w-5 h-5 text-primary-400" />
      </div>

      <template v-else>
        <!-- ── KPI Strip ─────────────────────────────────────────────── -->
        <div class="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-5">
          <KpiTile
            label="Utilization"
            :value="totals.utilization_pct + '%'"
            subline="logged / capacity"
            :progress="totals.utilization_pct"
          />
          <KpiTile
            label="Capacity"
            :value="fmt(totals.capacity) + 'h'"
            subline="total available"
          />
          <KpiTile
            label="Logged"
            :value="fmt(totals.logged) + 'h'"
            subline="from timesheets"
          />
          <KpiTile
            label="Billable"
            :value="fmt(totals.billable) + 'h'"
            :subline="totals.billable_pct + '% of logged'"
            :progress="totals.billable_pct"
          />
          <KpiTile
            label="Realization"
            value="—"
            subline="invoiced / billable"
          />
        </div>

        <!-- ── Empty ─────────────────────────────────────────────────── -->
        <div v-if="!members.length" class="bg-overlay rounded-md overflow-hidden"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
          <EmptyState
            :icon="Users"
            title="No utilization data"
            description="Add members to a project or connect ERPNext Timesheets."
          />
        </div>

        <!-- ── Table ──────────────────────────────────────────────────── -->
        <div v-else class="bg-overlay rounded-md overflow-hidden"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
          <table class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-separator bg-surface-secondary">
                <th class="text-left px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Member
                </th>
                <th class="text-right px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Capacity
                </th>
                <th class="text-right px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Logged
                </th>
                <th class="text-right px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Billable
                </th>
                <th class="text-right px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Util %
                </th>
                <th class="text-right px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Realized
                </th>
                <th class="px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted w-48">
                  <!-- bar -->
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="m in members"
                :key="m.user"
                class="border-b border-separator last:border-0 hover:bg-surface-secondary transition-colors"
              >
                <!-- Member -->
                <td class="px-5 py-3">
                  <div class="flex items-center gap-2.5">
                    <Avatar
                      :name="m.full_name"
                      :src="m.user_image ? (m.user_image.startsWith('/') ? m.user_image : `/files/${m.user_image}`) : ''"
                      size="sm"
                    />
                    <div class="min-w-0">
                      <p class="text-[13px] font-medium text-foreground truncate leading-none">
                        {{ m.full_name }}
                      </p>
                      <p class="text-[10.5px] text-muted mt-0.5 leading-none truncate">
                        {{ m.user }}
                      </p>
                    </div>
                  </div>
                </td>

                <!-- Capacity -->
                <td class="px-4 py-3 text-right tabular-nums">
                  <span class="text-[13px] text-muted">{{ fmt(m.capacity_hours) }}h</span>
                </td>

                <!-- Logged -->
                <td class="px-4 py-3 text-right tabular-nums">
                  <span class="text-[13px] font-medium text-foreground">{{ fmt(m.logged_hours) }}h</span>
                </td>

                <!-- Billable -->
                <td class="px-4 py-3 text-right">
                  <div>
                    <span class="text-[13px] font-medium text-foreground tabular-nums">{{ fmt(m.billable_hours) }}h</span>
                    <span v-if="m.logged_hours > 0" class="ml-1.5 text-[11px] text-muted tabular-nums">
                      {{ m.billable_pct }}%
                    </span>
                  </div>
                </td>

                <!-- Util % -->
                <td class="px-4 py-3 text-right">
                  <span
                    class="text-[13px] font-semibold tabular-nums"
                    :class="utilColor(m.utilization_pct)"
                  >
                    {{ m.utilization_pct }}%
                  </span>
                </td>

                <!-- Realization (stub until ERPNext invoices connected) -->
                <td class="px-4 py-3 text-right">
                  <span class="text-[13px] text-muted tabular-nums">—</span>
                </td>

                <!-- Utilization bar — full-width, colored by band -->
                <td class="px-5 py-3">
                  <div class="h-2 bg-surface-secondary rounded-full overflow-hidden w-full">
                    <div
                      :class="utilBarColor(m.utilization_pct)"
                      class="h-full rounded-full transition-[width] duration-400 ease-out"
                      :style="{ width: Math.min(m.utilization_pct, 100) + '%' }"
                    />
                  </div>
                  <p class="text-[10px] text-muted mt-0.5 tabular-nums text-right">
                    {{ Math.min(m.utilization_pct, 100) }}% of capacity
                  </p>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- Table footer legend — utilization bands -->
          <div class="flex items-center gap-4 px-5 py-3 border-t border-separator bg-surface-secondary">
            <div class="flex items-center gap-1.5 text-[11px] text-muted">
              <span class="w-3 h-1.5 rounded-full bg-accent" />Under 70%
            </div>
            <div class="flex items-center gap-1.5 text-[11px] text-muted">
              <span class="w-3 h-1.5 rounded-full bg-success" />Healthy 70–95%
            </div>
            <div class="flex items-center gap-1.5 text-[11px] text-muted">
              <span class="w-3 h-1.5 rounded-full bg-warning" />At capacity 95–110%
            </div>
            <div class="flex items-center gap-1.5 text-[11px] text-muted">
              <span class="w-3 h-1.5 rounded-full bg-danger" />Overloaded
            </div>
          </div>
        </div>
      </template>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getUtilization, getTeams } from '@/utils/api'
import Avatar from '@/ui/Avatar.vue'
import EmptyState from '@/ui/EmptyState.vue'
import KpiTile from '@/ui/KpiTile.vue'
import Spinner from '@/ui/Spinner.vue'
import { Users } from 'lucide-vue-next'

// ── Periods ───────────────────────────────────────────────────────────
const PERIOD_OPTIONS = [
  { value: 'last_7_days',  label: '7D'  },
  { value: 'last_30_days', label: '30D' },
  { value: 'last_90_days', label: '90D' },
]

const period       = ref('last_30_days')
const selectedTeam = ref('')
const teams        = ref([])

function setPeriod(p) {
  period.value = p
  load()
}

// ── Data ──────────────────────────────────────────────────────────────
const loading           = ref(false)
const members           = ref([])
const totals            = ref({ capacity: 0, logged: 0, billable: 0, utilization_pct: 0, billable_pct: 0 })
const fromLabel         = ref('')
const toLabel           = ref('')
const hasTimesheetData  = computed(() => members.value.some(m => m.logged_hours > 0))

async function load() {
  loading.value = true
  try {
    const res = await getUtilization(period.value, selectedTeam.value || null)
    members.value = res.members || []
    totals.value  = res.totals  || { capacity: 0, logged: 0, billable: 0, utilization_pct: 0, billable_pct: 0 }
    fromLabel.value = formatDate(res.from_date)
    toLabel.value   = formatDate(res.to_date)
  } catch (e) {
    console.error('Utilization error', e)
  } finally {
    loading.value = false
  }
}

watch(selectedTeam, load)

onMounted(async () => {
  try {
    const res = await getTeams()
    teams.value = res || []
  } catch {}
  await load()
})

// ── Helpers ───────────────────────────────────────────────────────────
function fmt(n) {
  return Math.round(n)
}
function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}
// Color text by utilization band (thresholds match Workload: 70/95/110)
function utilColor(pct) {
  if (!pct)        return 'text-muted'
  if (pct >= 110)  return 'text-danger'
  if (pct >= 95)   return 'text-warning'
  if (pct >= 70)   return 'text-success'
  return 'text-accent'
}

// Bar fill color by same bands
function utilBarColor(pct) {
  if (!pct)        return 'bg-default'
  if (pct >= 110)  return 'bg-danger'
  if (pct >= 95)   return 'bg-warning'
  if (pct >= 70)   return 'bg-success'
  return 'bg-accent'
}
</script>
