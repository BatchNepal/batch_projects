<template>
  <div class="min-h-full bg-[var(--background)]">
    <div class="px-6 py-5">

      <!-- ── Header ─────────────────────────────────────────────────── -->
      <header class="flex items-center justify-between mb-6 gap-4">
        <div>
          <h1 class="text-xl font-semibold text-foreground leading-7">Workload</h1>
          <p class="mt-0.5 text-sm text-muted">
            Capacity vs allocation — {{ weeksLabel }}
          </p>
        </div>
        <div class="flex items-center gap-2">
          <!-- Period tabs -->
          <div class="flex items-center p-0.5 bg-surface-secondary rounded-md gap-0.5">
            <button
              v-for="w in WEEK_OPTIONS" :key="w.value"
              type="button"
              class="px-3 h-7 text-xs font-medium rounded-sm transition-[background-color,color] duration-150 whitespace-nowrap"
              :class="weeks === w.value
                ? 'bg-overlay text-foreground shadow-sm'
                : 'text-muted hover:text-muted'"
              @click="setWeeks(w.value)"
            >
              {{ w.label }}
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

      <!-- ── Legend ────────────────────────────────────────────────── -->
      <div class="flex items-center gap-4 mb-4">
        <div class="flex items-center gap-1.5 text-[11px] text-muted">
          <span class="w-3 h-3 rounded-sm bg-surface-secondary border border-border" />
          No tasks
        </div>
        <div class="flex items-center gap-1.5 text-[11px] text-muted">
          <span class="w-3 h-3 rounded-sm bg-accent-soft border border-accent" />
          Under &lt;70%
        </div>
        <div class="flex items-center gap-1.5 text-[11px] text-muted">
          <span class="w-3 h-3 rounded-sm bg-success-soft border border-success" />
          Healthy 70–95%
        </div>
        <div class="flex items-center gap-1.5 text-[11px] text-muted">
          <span class="w-3 h-3 rounded-sm bg-warning-soft border border-warning" />
          At capacity 95–110%
        </div>
        <div class="flex items-center gap-1.5 text-[11px] text-muted">
          <span class="w-3 h-3 rounded-sm bg-danger-soft border border-danger" />
          Overloaded &gt;110%
        </div>
      </div>

      <!-- ── Loading ───────────────────────────────────────────────── -->
      <div v-if="loading" class="flex items-center justify-center py-20 gap-2 text-sm text-muted">
        <Spinner class="w-5 h-5 text-primary-400" />
      </div>

      <!-- ── Empty ─────────────────────────────────────────────────── -->
      <div v-else-if="!members.length" class="bg-overlay rounded-md overflow-hidden"
        style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
        <EmptyState
          image="/images/projs/bp-team.png"
          title="No members found"
          description="Add members to a project or team to see workload data."
        />
      </div>

      <!-- ── Members: callout + grid ─────────────────────────────── -->
      <template v-else>
        <!-- No allocation callout (members exist but 0 tasks with hours) -->
        <div
          v-if="noAllocationData"
          class="flex items-start gap-3 mb-4 px-4 py-3 rounded-md bg-warning-soft border border-warning text-warning-soft-foreground text-[13px]"
        >
          <span class="text-warning mt-0.5 shrink-0">⚠</span>
          <span>
            No estimated hours found for the next {{ weeks }}W. Workload cells appear when tasks have
            <strong class="font-semibold">estimated hours</strong> and at least one assignee with a due date in this window.
          </span>
        </div>

      <!-- ── Grid ──────────────────────────────────────────────────── -->
      <div class="bg-overlay rounded-md overflow-hidden"
        style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
        <div class="overflow-x-auto">
          <table class="w-full border-collapse text-sm">
            <thead>
              <tr class="border-b border-separator bg-surface-secondary">
                <th
                  class="sticky left-0 z-10 bg-surface-secondary text-left px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted w-52 min-w-52"
                >
                  Member
                </th>
                <th
                  v-for="(wb, wi) in weekBuckets" :key="wi"
                  class="px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-wider text-muted min-w-[120px]"
                >
                  {{ wb.label }}
                </th>
                <th class="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-muted min-w-[80px]">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="m in members"
                :key="m.user"
                class="border-b border-separator last:border-0 hover:bg-surface-secondary transition-colors"
              >
                <!-- Member cell (sticky) -->
                <td class="sticky left-0 bg-overlay px-4 py-3 hover:bg-surface-secondary">
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

                <!-- Week cells -->
                <td
                  v-for="(wk, wi) in m.weekly"
                  :key="wi"
                  class="px-3 py-2.5 text-center cursor-pointer group/cell"
                  @click="openDrawer(m, wi)"
                >
                  <div
                    :class="cellBg(wk.load_pct)"
                    class="rounded-md px-2 py-2 transition-[box-shadow] duration-100 group-hover/cell:ring-2 group-hover/cell:ring-accent/40"
                  >
                    <!-- Hours — always shown; grey when 0 -->
                    <p
                      :class="wk.allocated > 0 ? cellText(wk.load_pct) : 'text-muted'"
                      class="text-[13px] font-semibold tabular-nums leading-none"
                    >
                      {{ wk.allocated > 0 ? wk.allocated + 'h' : '0h' }}
                    </p>
                    <p class="text-[10.5px] text-muted mt-0.5 leading-none">
                      / {{ wk.capacity }}h
                    </p>
                    <!-- Project color dots (up to 4 distinct projects) -->
                    <div v-if="cellProjects(wk.tasks).length" class="flex items-center justify-center gap-0.5 mt-1">
                      <span
                        v-for="(proj, pi) in cellProjects(wk.tasks)"
                        :key="pi"
                        class="w-1.5 h-1.5 rounded-full"
                        :style="{ background: proj.color }"
                      />
                    </div>
                    <!-- Mini load bar — always rendered, empty when 0 -->
                    <div class="mt-1 h-1 bg-black/5 rounded-full overflow-hidden">
                      <div
                        :class="barColor(wk.load_pct)"
                        class="h-full rounded-full transition-[width] duration-400 ease-out"
                        :style="{ width: Math.min(wk.load_pct, 100) + '%' }"
                      />
                    </div>
                  </div>
                </td>

                <!-- Total -->
                <td class="px-4 py-3 text-right">
                  <p class="text-[13px] font-semibold tabular-nums text-muted">
                    {{ m.total_allocated }}h
                  </p>
                  <p class="text-[10.5px] text-muted mt-0.5">
                    / {{ m.total_capacity }}h
                  </p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      </template>

    </div>

    <!-- ── Right Drawer ───────────────────────────────────────────── -->
    <Transition name="drawer-right">
      <div
        v-if="drawer.open"
        class="fixed inset-0 z-40 flex"
        @mousedown.self="closeDrawer"
      >
        <div class="flex-1" @mousedown="closeDrawer" />
        <aside
          class="relative w-[340px] bg-overlay border-l border-border flex flex-col h-full overflow-hidden"
          style="box-shadow: -4px 0 24px rgba(0,0,0,0.08)"
        >
          <!-- Drawer header -->
          <div class="flex items-center gap-3 px-4 py-3.5 border-b border-separator shrink-0">
            <Avatar
              v-if="drawer.member"
              :name="drawer.member.full_name"
              :src="drawer.member.user_image ? (drawer.member.user_image.startsWith('/') ? drawer.member.user_image : `/files/${drawer.member.user_image}`) : ''"
              size="sm"
            />
            <div class="flex-1 min-w-0">
              <p class="text-[13px] font-semibold text-foreground leading-none truncate">
                {{ drawer.member?.full_name }}
              </p>
              <p class="text-[11px] text-muted mt-0.5 leading-none">
                {{ weekBuckets[drawer.weekIndex]?.label }}
                — {{ drawerWeek?.allocated || 0 }}h / {{ drawerWeek?.capacity || 40 }}h
              </p>
            </div>
            <button
              class="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:bg-surface-hover transition-colors"
              @click="closeDrawer"
            >
              <X :size="15" :stroke-width="1.75" />
            </button>
          </div>

          <!-- Drawer body -->
          <div class="flex-1 overflow-y-auto px-4 py-3">
            <template v-if="drawerTasks.length">
              <!-- Group by project -->
              <div
                v-for="(grp, proj) in drawerTasksByProject"
                :key="proj"
                class="mb-5"
              >
                <div class="flex items-center gap-2 mb-2">
                  <span
                    class="w-2.5 h-2.5 rounded-full shrink-0"
                    :style="{ background: grp.color || '#888' }"
                  />
                  <p class="text-[11px] font-semibold uppercase tracking-wider text-muted truncate">
                    {{ grp.title }}
                  </p>
                </div>
                <div class="space-y-1">
                  <div
                    v-for="t in grp.tasks"
                    :key="t.name"
                    class="flex items-start gap-2.5 px-3 py-2.5 rounded-md bg-surface-secondary hover:bg-surface-hover transition-colors cursor-pointer group"
                    @click="openTask(t)"
                  >
                    <div class="flex-1 min-w-0">
                      <p class="text-[13px] font-medium text-foreground truncate leading-snug group-hover:text-foreground">
                        {{ t.title || t.name }}
                      </p>
                      <div class="flex items-center gap-2 mt-1">
                        <span
                          v-if="t.due_date"
                          class="text-[11px] text-muted"
                        >Due {{ formatDate(t.due_date) }}</span>
                        <span
                          v-if="t.estimated_hours"
                          class="text-[11px] tabular-nums text-muted"
                        >{{ t.estimated_hours }}h est.</span>
                      </div>
                    </div>
                    <ArrowUpRight
                      :size="13"
                      :stroke-width="1.75"
                      class="text-muted group-hover:text-muted mt-0.5 shrink-0 transition-colors"
                    />
                  </div>
                </div>
              </div>
            </template>
            <EmptyState
              v-else
              :icon="CalendarCheck"
              title="No tasks this week"
              description="No tasks are due in this period."
            />
          </div>
        </aside>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useProjectStore } from '@/stores/project'
import { getWorkload, getTeams } from '@/utils/api'
import Avatar from '@/ui/Avatar.vue'
import EmptyState from '@/ui/EmptyState.vue'
import Spinner from '@/ui/Spinner.vue'
import { UsersRound, X, ArrowUpRight, CalendarCheck } from 'lucide-vue-next'

const store = useProjectStore()

// ── Periods ───────────────────────────────────────────────────────────
const WEEK_OPTIONS = [
  { value: 2, label: '2W' },
  { value: 4, label: '4W' },
  { value: 6, label: '6W' },
]

const weeks        = ref(4)
const selectedTeam = ref('')
const teams        = ref([])

const weeksLabel = computed(() => {
  const wb = weekBuckets.value
  if (!wb.length) return ''
  return `${wb[0].label} – ${wb[wb.length - 1].label}`
})

function setWeeks(w) {
  weeks.value = w
  load()
}

// ── Data ──────────────────────────────────────────────────────────────
const loading     = ref(false)
const weekBuckets = ref([])
const members     = ref([])

async function load() {
  loading.value = true
  try {
    const res = await getWorkload(weeks.value, selectedTeam.value || null)
    weekBuckets.value = res.weeks    || []
    members.value     = res.members  || []
  } catch (e) {
    console.error('Workload error', e)
  } finally {
    loading.value = false
  }
}

watch(selectedTeam, load)

onMounted(async () => {
  // Fetch teams for filter
  try {
    const res = await getTeams()
    teams.value = res || []
  } catch {}
  await load()
})

// ── Cell styling — 4-band thresholds: 70 / 95 / 110 ─────────────────
function cellBg(load_pct) {
  if (!load_pct) return 'bg-overlay border border-separator'
  if (load_pct < 70)   return 'bg-accent-soft border border-accent'
  if (load_pct < 95)   return 'bg-success-soft border border-success'
  if (load_pct <= 110) return 'bg-warning-soft border border-warning'
  return 'bg-danger-soft border border-danger'
}
function cellText(load_pct) {
  if (!load_pct) return 'text-muted'
  if (load_pct < 70)   return 'text-accent-soft-foreground'
  if (load_pct < 95)   return 'text-success-soft-foreground'
  if (load_pct <= 110) return 'text-warning-soft-foreground'
  return 'text-danger-soft-foreground'
}
function barColor(load_pct) {
  if (!load_pct) return 'bg-default'
  if (load_pct < 70)   return 'bg-accent'
  if (load_pct < 95)   return 'bg-success'
  if (load_pct <= 110) return 'bg-warning'
  return 'bg-danger'
}

// ── Project color dots helper ─────────────────────────────────────────
function cellProjects(tasks) {
  const seen = new Set()
  const out  = []
  for (const t of (tasks || [])) {
    if (!t.project || seen.has(t.project)) continue
    seen.add(t.project)
    out.push({ color: t.project_color || 'var(--muted)' })
    if (out.length >= 4) break
  }
  return out
}

// ── No-allocation computed ────────────────────────────────────────────
const noAllocationData = computed(() =>
  members.value.length > 0 && members.value.every(m => m.total_allocated === 0)
)

// ── Drawer ────────────────────────────────────────────────────────────
const drawer = ref({ open: false, member: null, weekIndex: 0 })

const drawerWeek = computed(() => {
  if (!drawer.value.member) return null
  return drawer.value.member.weekly[drawer.value.weekIndex] || null
})

const drawerTasks = computed(() => drawerWeek.value?.tasks || [])

const drawerTasksByProject = computed(() => {
  const groups = {}
  for (const t of drawerTasks.value) {
    const key = t.project || '__no_project__'
    if (!groups[key]) {
      groups[key] = {
        title: t.project_title || t.project || 'No project',
        color: t.project_color || '#888',
        tasks: [],
      }
    }
    groups[key].tasks.push(t)
  }
  return groups
})

function openDrawer(member, weekIndex) {
  const wk = member.weekly[weekIndex]
  if (!wk || !wk.tasks.length) return
  drawer.value = { open: true, member, weekIndex }
}
function closeDrawer() {
  drawer.value = { ...drawer.value, open: false }
}

function openTask(t) {
  if (!t.name) return
  store.openTaskDetail(t.name)
  closeDrawer()
}

function formatDate(d) {
  if (!d) return ''
  const dt = new Date(d)
  return dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
</script>

<style scoped>
.drawer-right-enter-active,
.drawer-right-leave-active {
  transition: opacity 0.18s ease;
}
.drawer-right-enter-active aside,
.drawer-right-leave-active aside {
  transition: transform 0.22s cubic-bezier(0.32, 0.72, 0, 1);
}
.drawer-right-enter-from,
.drawer-right-leave-to {
  opacity: 0;
}
.drawer-right-enter-from aside,
.drawer-right-leave-to aside {
  transform: translateX(100%);
}
</style>
