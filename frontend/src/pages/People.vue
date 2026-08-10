<template>
  <div class="min-h-full bg-background">
    <div class="px-6 py-5">

      <!-- ── Header ─────────────────────────────────────────────────── -->
      <header class="flex items-center justify-between mb-6 gap-4">
        <div>
          <h1 class="text-xl font-semibold text-foreground leading-7">People</h1>
          <p class="mt-0.5 text-sm text-muted">Capacity, workload and active projects</p>
        </div>
      </header>

      <!-- ── Loading ───────────────────────────────────────────────── -->
      <div v-if="loading" class="flex items-center justify-center py-20 gap-2 text-sm text-muted">
        <Spinner class="w-5 h-5 text-primary-400" />
      </div>

      <template v-else>
        <!-- ── KPI Strip ─────────────────────────────────────────────── -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
          <KpiTile
            label="People"
            :value="String(totals.count)"
            subline="active members"
          />
          <KpiTile
            label="Avg Utilization"
            :value="totals.avg_utilization + '%'"
            subline="last 30 days"
            :progress="totals.avg_utilization"
          />
          <KpiTile
            label="Available Hours"
            :value="totals.available_hours + 'h'"
            subline="this week"
          />
          <KpiTile
            label="Overloaded"
            :value="String(totals.overloaded)"
            subline="≥ 95% utilization"
          />
          <!-- Seat consumption — only when max_users is set (not unlimited) -->
          <KpiTile
            v-if="ent.seatsTotal > 0"
            label="Seats Used"
            :value="`${ent.seatsUsed} / ${ent.seatsTotal}`"
            :subline="ent.isAtCapacity ? 'All seats in use — Upgrade' : `${ent.seatsRemaining} remaining`"
          />
        </div>

        <!-- ── Empty ─────────────────────────────────────────────────── -->
        <div v-if="!people.length" class="bg-surface rounded-lg shadow-surface overflow-hidden">
          <EmptyState
            :icon="Users"
            title="No people found"
            description="Add members to a project or team to see them here."
          />
        </div>

        <!-- ── Table ──────────────────────────────────────────────────── -->
        <div v-else class="bg-surface rounded-lg shadow-surface overflow-hidden">
          <table class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-separator bg-surface-secondary">
                <th class="text-left px-5 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                  Person
                </th>
                <th class="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                  Role
                </th>
                <th class="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                  Active Projects
                </th>
                <th class="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                  This Week
                </th>
                <th class="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                  Util (30D)
                </th>
                <th class="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-muted w-44">
                  <!-- bar -->
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="p in people"
                :key="p.user"
                class="border-b border-separator last:border-0 hover:bg-surface-secondary/60 transition-colors group"
              >
                <!-- Person -->
                <td class="px-5 py-3">
                  <div class="flex items-center gap-2.5">
                    <span class="relative shrink-0">
                      <Avatar
                        :name="p.full_name"
                        :src="p.user_image ? (p.user_image.startsWith('/') ? p.user_image : '/files/' + p.user_image) : ''"
                        size="sm"
                      />
                      <span v-if="isOnline(p.user)" title="Online"
                        class="absolute -bottom-px -right-px size-[7px] rounded-full bg-success"
                        style="border: 1.5px solid var(--surface)" />
                    </span>
                    <div class="min-w-0 flex-1">
                      <p class="text-base font-medium text-foreground truncate leading-none">
                        {{ p.full_name }}
                      </p>
                      <p class="text-xs text-muted mt-0.5 leading-none truncate">
                        {{ p.user }}
                      </p>
                    </div>
                    <button
                      v-if="p.projects.length"
                      class="opacity-0 group-hover:opacity-100 transition-opacity shrink-0 inline-flex items-center gap-1 h-6 px-2 text-xs font-medium text-muted bg-default hover:bg-default hover:text-foreground rounded-md"
                      @click.stop="openFirstProject(p)">
                      Tasks
                      <svg class="size-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
                    </button>
                  </div>
                </td>

                <!-- Role / Designation -->
                <td class="px-4 py-3">
                  <div v-if="p.designation || p.department" class="min-w-0">
                    <p v-if="p.designation" class="text-base text-foreground truncate leading-none">
                      {{ p.designation }}
                    </p>
                    <p v-if="p.department" class="text-xs text-muted mt-0.5 leading-none truncate">
                      {{ p.department }}
                    </p>
                  </div>
                  <span v-else class="text-base text-muted">—</span>
                </td>

                <!-- Active Projects -->
                <td class="px-4 py-3">
                  <div v-if="p.projects.length" class="flex flex-wrap gap-1">
                    <span
                      v-for="proj in p.projects.slice(0, 3)"
                      :key="proj.name"
                      class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-xs font-medium bg-default text-muted"
                    >
                      <span
                        class="w-1.5 h-1.5 rounded-full shrink-0"
                        :style="{ background: proj.color }"
                      />
                      {{ proj.title }}
                    </span>
                    <span
                      v-if="p.projects.length > 3"
                      class="px-1.5 py-0.5 text-xs text-muted"
                    >
                      +{{ p.projects.length - 3 }}
                    </span>
                  </div>
                  <span v-else class="text-base text-muted">—</span>
                </td>

                <!-- This Week allocation -->
                <td class="px-4 py-3 text-right">
                  <span class="text-base font-medium tabular-nums text-foreground">
                    {{ p.week_allocation }}h
                  </span>
                  <span class="text-xs text-muted ml-1">/ {{ p.week_capacity }}h</span>
                </td>

                <!-- Util % -->
                <td class="px-4 py-3 text-right">
                  <span
                    class="text-base font-semibold tabular-nums"
                    :class="utilColor(p.utilization_pct)"
                  >
                    {{ p.utilization_pct }}%
                  </span>
                </td>

                <!-- Utilization bar -->
                <td class="px-5 py-3">
                  <div class="h-2 bg-default rounded-full overflow-hidden">
                    <div
                      :class="utilBarColor(p.utilization_pct)"
                      class="h-full rounded-full transition-[width] duration-400 ease-out"
                      :style="{ width: Math.min(p.utilization_pct, 100) + '%' }"
                    />
                  </div>
                  <p class="text-xs text-muted mt-0.5 tabular-nums text-right">
                    {{ Math.min(p.utilization_pct, 100) }}% of capacity
                  </p>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- Footer legend -->
          <div class="flex items-center gap-4 px-5 py-3 border-t border-separator bg-surface-secondary">
            <div class="flex items-center gap-1.5 text-xs text-muted">
              <span class="w-3 h-1.5 rounded-full bg-accent" />Under 70%
            </div>
            <div class="flex items-center gap-1.5 text-xs text-muted">
              <span class="w-3 h-1.5 rounded-full bg-success" />Healthy 70–95%
            </div>
            <div class="flex items-center gap-1.5 text-xs text-muted">
              <span class="w-3 h-1.5 rounded-full bg-warning" />At capacity 95–110%
            </div>
            <div class="flex items-center gap-1.5 text-xs text-muted">
              <span class="w-3 h-1.5 rounded-full bg-danger" />Overloaded
            </div>
          </div>
        </div>
      </template>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { getPeople } from '@/utils/api'
import { useEntitlementsStore } from '@/stores/entitlements'
import Avatar from '@/ui/Avatar.vue'
import { usePresence } from '@/composables/usePresence'
import EmptyState from '@/ui/EmptyState.vue'
import KpiTile from '@/ui/KpiTile.vue'
import Spinner from '@/ui/Spinner.vue'

const ent = useEntitlementsStore()
import { Users } from 'lucide-vue-next'

const router = useRouter()
const { isOnline, stop: stopPresence } = usePresence()
onUnmounted(stopPresence)

// ── Data ──────────────────────────────────────────────────────────────
const loading = ref(false)
const people  = ref([])
const totals  = ref({ count: 0, avg_utilization: 0, available_hours: 0, overloaded: 0 })

async function load() {
  loading.value = true
  try {
    const res    = await getPeople()
    people.value = res.people || []
    totals.value = res.totals || { count: 0, avg_utilization: 0, available_hours: 0, overloaded: 0 }
  } catch (e) {
    console.error('People error', e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── Color helpers — same bands as Workload / Utilization ──────────────
function utilColor(pct) {
  if (!pct)       return 'text-muted'
  if (pct >= 110) return 'text-danger'
  if (pct >= 95)  return 'text-warning'
  if (pct >= 70)  return 'text-success'
  return 'text-accent'
}

function utilBarColor(pct) {
  if (!pct)       return 'bg-default'
  if (pct >= 110) return 'bg-danger'
  if (pct >= 95)  return 'bg-warning'
  if (pct >= 70)  return 'bg-success'
  return 'bg-accent'
}

function openFirstProject(person) {
  if (!person.projects.length) return
  const proj = person.projects[0]
  router.push(`/workspace/${proj.key || proj.name}/list`)
}
</script>
