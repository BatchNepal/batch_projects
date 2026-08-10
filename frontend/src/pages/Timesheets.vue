<template>
  <div class="min-h-full bg-[var(--background)]">
    <div class="px-6 py-5">

      <!-- Header -->
      <header class="flex items-center justify-between mb-6 gap-4">
        <div>
          <h1 class="text-xl font-semibold text-foreground leading-7">Timesheets</h1>
          <p class="mt-0.5 text-sm text-muted">
            Logged hours — {{ fromLabel }} to {{ toLabel }}
          </p>
        </div>
        <div class="flex items-center gap-2">
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

      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-20 gap-2 text-sm text-muted">
        <Spinner class="w-5 h-5 text-primary-400" />
      </div>

      <template v-else>
        <!-- KPI strip -->
        <div class="grid grid-cols-4 gap-3 mb-5">
          <KpiTile
            label="Total Hours"
            :value="(data.total_hours || 0) + 'h'"
            subline="logged this period"
          />
          <KpiTile
            label="Billable Hours"
            :value="(data.billable_hours || 0) + 'h'"
            :subline="(data.total_hours > 0 ? Math.round(data.billable_hours / data.total_hours * 100) : 0) + '% of total'"
          />
          <KpiTile
            label="Non-Billable"
            :value="(data.non_billable_hours || 0) + 'h'"
            subline="internal / overhead"
          />
          <KpiTile
            label="Billable Rate"
            :value="(data.billable_pct || 0) + '%'"
            subline="of total hours"
            :progress="data.billable_pct || 0"
          />
        </div>

        <!-- Empty -->
        <div
          v-if="!data.members?.length"
          class="bg-overlay rounded-md overflow-hidden"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)"
        >
          <EmptyState
            :icon="Clock"
            title="No timesheet data"
            description="No submitted timesheets found for this period."
          />
        </div>

        <!-- Table -->
        <div
          v-else
          class="bg-overlay rounded-md overflow-hidden"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)"
        >
          <div class="overflow-x-auto">
            <table class="w-full border-collapse text-sm">
              <thead>
                <tr class="border-b border-separator bg-surface-secondary">
                  <th class="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted w-52 min-w-[200px]">
                    Member
                  </th>
                  <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted min-w-[90px]">
                    Total
                  </th>
                  <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted min-w-[90px]">
                    Billable
                  </th>
                  <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted min-w-[100px]">
                    Non-billable
                  </th>
                  <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted min-w-[80px]">
                    Bill %
                  </th>
                  <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted">
                    Projects
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="m in data.members"
                  :key="m.user"
                  class="border-b border-separator last:border-0 hover:bg-surface-secondary transition-colors"
                >
                  <!-- Member -->
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2.5">
                      <Avatar :name="m.full_name" size="sm" />
                      <div class="min-w-0">
                        <p class="text-base font-medium text-foreground truncate leading-none">{{ m.full_name }}</p>
                        <p class="text-xs text-muted mt-0.5 leading-none truncate">{{ m.user }}</p>
                      </div>
                    </div>
                  </td>
                  <!-- Total -->
                  <td class="px-4 py-3 text-right">
                    <p class="text-base font-semibold tabular-nums text-foreground">{{ m.total_hours }}h</p>
                  </td>
                  <!-- Billable -->
                  <td class="px-4 py-3 text-right">
                    <p class="text-base tabular-nums text-success font-medium">{{ m.billable_hours }}h</p>
                  </td>
                  <!-- Non-billable -->
                  <td class="px-4 py-3 text-right">
                    <p class="text-base tabular-nums text-muted">{{ m.non_billable_hours }}h</p>
                  </td>
                  <!-- Billable % -->
                  <td class="px-4 py-3 text-right">
                    <div class="flex flex-col items-end gap-1.5">
                      <p
                        class="text-base font-medium tabular-nums"
                        :class="m.billable_pct >= 70 ? 'text-success' : m.billable_pct >= 40 ? 'text-warning' : 'text-muted'"
                      >
                        {{ m.billable_pct }}%
                      </p>
                      <div class="w-16 h-1 bg-surface-secondary rounded-full overflow-hidden">
                        <div
                          class="h-full rounded-full transition-[width] duration-400 ease-out"
                          :class="m.billable_pct >= 70 ? 'bg-success' : m.billable_pct >= 40 ? 'bg-warning' : 'bg-muted'"
                          :style="{ width: Math.min(m.billable_pct, 100) + '%' }"
                        />
                      </div>
                    </div>
                  </td>
                  <!-- Projects -->
                  <td class="px-4 py-3">
                    <div class="flex flex-wrap gap-1">
                      <span
                        v-for="proj in m.projects.slice(0, 4)"
                        :key="proj.project"
                        class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-surface-secondary text-muted whitespace-nowrap"
                      >
                        <span class="w-1.5 h-1.5 rounded-full shrink-0" :style="{ background: proj.project_color }" />
                        {{ proj.project_name }}
                        <span class="text-muted">{{ proj.hours }}h</span>
                      </span>
                      <span
                        v-if="m.projects.length > 4"
                        class="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-surface-secondary text-muted"
                      >
                        +{{ m.projects.length - 4 }}
                      </span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getTimesheets, getTeams } from '@/utils/api'
import Avatar from '@/ui/Avatar.vue'
import EmptyState from '@/ui/EmptyState.vue'
import Spinner from '@/ui/Spinner.vue'
import KpiTile from '@/ui/KpiTile.vue'
import { Clock } from 'lucide-vue-next'

const PERIOD_OPTIONS = [
  { value: 'last_7_days',  label: '7D'  },
  { value: 'last_30_days', label: '30D' },
  { value: 'last_90_days', label: '90D' },
]

const period       = ref('last_30_days')
const selectedTeam = ref('')
const teams        = ref([])
const loading      = ref(false)
const data         = ref({
  total_hours: 0, billable_hours: 0, non_billable_hours: 0, billable_pct: 0,
  from_date: '', to_date: '', members: [],
})

const fromLabel = computed(() => fmtDate(data.value.from_date))
const toLabel   = computed(() => fmtDate(data.value.to_date))

function fmtDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function setPeriod(p) {
  period.value = p
  load()
}

async function load() {
  loading.value = true
  try {
    data.value = await getTimesheets(period.value, selectedTeam.value || null)
  } catch (e) {
    console.error('Timesheets error', e)
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
</script>
