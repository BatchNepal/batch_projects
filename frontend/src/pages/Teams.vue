<template>
  <div class="min-h-full font-sans text-[var(--foreground)]">
    <div class="max-w-[1600px] mx-auto px-6 py-6">

      <!-- ── Header ─────────────────────────────────────────────────── -->
      <header class="flex items-center justify-between mb-6 gap-4">
        <div>
          <h1 class="text-3xl font-bold text-foreground leading-7">Teams</h1>
          <p class="mt-0.5 text-sm text-muted">
            Manage teams, members, and projects in one place.
          </p>
          <!-- <p class="mt-0.5 text-sm text-muted">
            {{ teams.length }} team{{ teams.length !== 1 ? 's' : '' }}
            <template v-if="totalMembers">
              · {{ totalMembers }} member{{ totalMembers !== 1 ? 's' : '' }}
            </template>
          </p> -->
        </div>
        <button
          type="button"
          class="flex items-center gap-1.5 h-8 px-3.5 rounded-md bg-accent hover:bg-accent-hover active:scale-[0.97] text-white text-xs font-semibold transition-colors duration-100"
          @click="showCreate = true"
        >
          <Plus :size="13" :stroke-width="2.5" class="-ml-0.5" />
          Create team
        </button>
      </header>

      <!-- ── KPI strip ──────────────────────────────────────────────── -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <KpiTile
          label="Teams"
          :value="teams.length"
          subline="active groups"
        />
        <KpiTile
          label="Members"
          :value="totalMembers"
          subline="across all teams"
        />
        <KpiTile
          label="Projects"
          :value="totalProjects"
          subline="team-assigned"
        />
        <KpiTile
          label="Departments"
          :value="departmentCount"
          subline="represented"
        />
      </div>

      <!-- ── Toolbar ────────────────────────────────────────────────── -->
      <div class="flex items-center justify-between mb-4">
        <!-- List / Grid toggle -->
        <div class="flex items-center p-0.5 border border-border bg-surface-secondary rounded-md gap-0.5">
          <button
            v-for="v in VIEWS" :key="v.id"
            type="button"
            :class="[
              'flex items-center gap-1.5 px-3 h-7 text-xs font-medium rounded-sm transition-[background-color,color] duration-150',
              viewMode === v.id
                ? 'bg-overlay text-foreground shadow-sm'
                : 'text-muted hover:text-muted',
            ]"
            @click="viewMode = v.id"
          >
            <component :is="v.icon" :size="12" :stroke-width="2" />
            {{ v.label }}
          </button>
        </div>

        <!-- Search -->
        <div class="relative">
          <Search :size="13" :stroke-width="1.75" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
          <input
            v-model="query"
            type="text"
            placeholder="Filter teams…"
            class="h-8 pl-8 pr-3 text-xs bg-overlay border border-border rounded-md shadow-sm text-muted placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/40 w-44 transition-[background-color,box-shadow]"
          />
        </div>
      </div>

      <!-- ── Loading ───────────────────────────────────────────────── -->
      <div v-if="loading" class="flex items-center justify-center py-20">
        <div class="w-6 h-6 rounded-full border-2 border-accent border-t-transparent animate-spin" />
      </div>

      <!-- ── Empty ─────────────────────────────────────────────────── -->
      <div v-else-if="!teams.length" class="bg-overlay rounded-lg border border-border overflow-hidden">
        <EmptyState
          image="/images/projs/bp-team.png"
          title="No teams yet"
          description="Create a team to group projects and members and track workload together."
        >
          <template #action>
            <button
              type="button"
              class="flex items-center gap-1.5 h-8 px-3.5 rounded-full bg-accent hover:bg-accent-hover text-white text-xs font-semibold transition-colors"
              @click="showCreate = true"
            >
              <Plus :size="13" :stroke-width="2.5" />
              Create first team
            </button>
          </template>
        </EmptyState>
      </div>

      <!-- ── No results ─────────────────────────────────────────────── -->
      <div v-else-if="!filteredTeams.length" class="bg-overlay rounded-lg border border-border overflow-hidden">
        <EmptyState
          :icon="SearchIcon"
          title="No teams match"
          :description="'No teams matching \'' + query + '\' were found.'"
        />
      </div>

      <!-- ── LIST VIEW ──────────────────────────────────────────────── -->
      <div v-else-if="viewMode === 'list'" class="bg-overlay rounded-lg border border-border overflow-hidden">
        <table class="w-full border-collapse text-sm">
          <thead>
            <tr class="border-b border-separator bg-surface-secondary">
              <th class="text-left px-5 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                Team
              </th>
              <th class="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                Members
              </th>
              <th class="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                Projects
              </th>
              <th class="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                Open tasks
              </th>
              <th class="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted">
                Department
              </th>
              <th class="w-24" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="team in filteredTeams"
              :key="team.name"
              class="border-b border-separator last:border-0 hover:bg-surface-secondary transition-colors cursor-pointer group"
              @click="$router.push('/workspace/team/' + team.team_key)"
            >
              <!-- Name -->
              <td class="px-5 py-3.5">
                <div class="flex items-center gap-3">
                  <div
                    class="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0"
                    :style="{ background: team.team_color || 'var(--accent)' }"
                  >
                    <span v-if="team.team_icon">{{ team.team_icon }}</span>
                    <span v-else>{{ (team.team_name || '').slice(0, 2).toUpperCase() }}</span>
                  </div>
                  <div>
                    <p class="text-base font-semibold text-foreground leading-none">{{ team.team_name }}</p>
                    <p class="text-xs font-mono text-muted mt-0.5">{{ team.team_key }}</p>
                  </div>
                </div>
              </td>

              <!-- Members -->
              <td class="px-4 py-3.5">
                <div class="flex items-center gap-2">
                  <div class="flex items-center">
                    <Avatar
                      v-for="m in (team.members || []).slice(0, 4)"
                      :key="m.user"
                      :name="m.full_name"
                      size="xs"
                      class="-ml-1.5 first:ml-0 ring-2 ring-overlay"
                    />
                    <span
                      v-if="(team.member_count || 0) > 4"
                      class="-ml-1.5 w-5 h-5 rounded-full bg-surface-secondary text-muted text-micro font-bold flex items-center justify-center ring-2 ring-overlay"
                    >+{{ (team.member_count || 0) - 4 }}</span>
                  </div>
                  <span class="text-sm text-muted tabular-nums">{{ team.member_count || 0 }}</span>
                </div>
              </td>

              <!-- Projects -->
              <td class="px-4 py-3.5">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span
                    v-for="p in (team.projects || []).slice(0, 2)"
                    :key="p.name"
                    class="inline-flex h-5 items-center px-2 rounded text-xs font-medium cursor-pointer hover:opacity-80"
                    :style="{ background: `color-mix(in oklab, ${p.project_color || 'var(--accent)'} 9%, transparent)`, color: p.project_color || 'var(--accent)' }"
                    @click.stop="$router.push('/workspace/' + p.key + '/board')"
                  >{{ p.project_name }}</span>
                  <span
                    v-if="(team.projects || []).length > 2"
                    class="inline-flex h-5 items-center px-1.5 rounded text-xs text-muted bg-surface-secondary"
                  >+{{ team.projects.length - 2 }}</span>
                  <span v-if="!(team.projects || []).length" class="text-sm text-muted">—</span>
                </div>
              </td>

              <!-- Open tasks — the load signal the index ranks by -->
              <td class="px-4 py-3.5">
                <span class="text-sm tabular-nums" :class="loadScore(team) > 8 ? 'text-danger font-semibold' : 'text-foreground'">
                  {{ team.open_task_count || 0 }}
                </span>
              </td>

              <!-- Department -->
              <td class="px-4 py-3.5">
                <span
                  v-if="team.department"
                  class="inline-flex items-center h-5 px-2 rounded text-xs font-medium text-muted bg-surface-secondary"
                >{{ team.department }}</span>
                <span v-else class="text-sm text-muted">—</span>
              </td>

              <!-- Actions -->
              <td class="px-4 py-3.5" data-team-ctx>
                <div class="relative flex justify-end">
                  <button
                    class="w-6 h-6 flex items-center justify-center rounded-md text-muted hover:text-muted hover:bg-surface-hover transition-colors opacity-0 group-hover:opacity-100"
                    :class="openMenuName === team.name ? '!opacity-100 bg-surface-secondary text-muted' : ''"
                    data-team-ctx
                    @click.stop="toggleMenu(team.name)"
                  >
                    <MoreHorizontal :size="14" :stroke-width="1.75" />
                  </button>
                  <Transition name="dd-fade">
                    <div
                      v-if="openMenuName === team.name"
                      class="absolute right-0 top-[calc(100%+4px)] w-48 bg-overlay border border-border rounded-lg overflow-hidden z-50"
                      style="box-shadow:0 4px 16px rgba(0,0,0,0.10)"
                      data-team-ctx
                    >
                      <div class="p-1">
                        <button class="teams-menu-item" @click.stop="$router.push('/workspace/team/' + team.team_key); closeMenu()">
                          <UsersRound :size="13" class="text-muted" />Overview
                        </button>
                        <div class="h-px bg-surface-secondary my-1 mx-1" />
                        <button class="teams-menu-item" @click.stop="$router.push('/workspace/team/' + team.team_key + '/settings'); closeMenu()">
                          <Settings :size="13" class="text-muted" />Settings
                        </button>
                        <button class="teams-menu-item" @click.stop="store.togglePinnedTeam(team); closeMenu()">
                          <component :is="store.isTeamPinned(team.team_key) ? PinOff : Pin" :size="13" class="text-muted" />
                          {{ store.isTeamPinned(team.team_key) ? 'Unpin' : 'Pin to sidebar' }}
                        </button>
                      </div>
                    </div>
                  </Transition>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── GRID VIEW ──────────────────────────────────────────────── -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div
          v-for="team in filteredTeams"
          :key="team.name"
          class="bg-overlay rounded-lg border border-border overflow-hidden cursor-pointer hover:shadow-md hover:border-border-secondary transition-[border-color,box-shadow] group flex flex-col"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)"
          @click="$router.push('/workspace/team/' + team.team_key)"
        >
          <div class="p-4 flex-1">
            <!-- Card header -->
            <div class="flex items-start gap-3 mb-3">
              <div
                class="w-9 h-9 rounded-lg flex items-center justify-center text-white shrink-0"
                :style="{ background: team.team_color || 'var(--accent)' }"
              >
                <span v-if="team.team_icon" class="text-base leading-none">{{ team.team_icon }}</span>
                <span v-else class="text-xs font-bold">{{ (team.team_name || '').slice(0, 2).toUpperCase() }}</span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-base font-semibold text-foreground truncate leading-none">{{ team.team_name }}</p>
                <p class="text-xs font-mono text-muted mt-0.5">{{ team.team_key }}</p>
              </div>
              <div class="relative shrink-0" data-team-ctx>
                <button
                  class="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md hover:bg-surface-hover text-muted hover:text-muted"
                  :class="openMenuName === team.name ? '!opacity-100 bg-surface-secondary text-muted' : ''"
                  data-team-ctx
                  @click.stop="toggleMenu(team.name)"
                >
                  <MoreHorizontal :size="14" :stroke-width="1.75" />
                </button>
                <Transition name="dd-fade">
                  <div
                    v-if="openMenuName === team.name"
                    class="absolute right-0 top-[calc(100%+4px)] w-48 bg-overlay border border-border rounded-lg overflow-hidden z-50"
                    style="box-shadow:0 4px 16px rgba(0,0,0,0.10)"
                    data-team-ctx
                  >
                    <div class="p-1">
                      <button class="teams-menu-item" @click.stop="$router.push('/workspace/team/' + team.team_key); closeMenu()">
                        <UsersRound :size="13" class="text-muted" />Overview
                      </button>
                      <div class="h-px bg-surface-secondary my-1 mx-1" />
                      <button class="teams-menu-item" @click.stop="$router.push('/workspace/team/' + team.team_key + '/settings'); closeMenu()">
                        <Settings :size="13" class="text-muted" />Settings
                      </button>
                      <button class="teams-menu-item" @click.stop="store.togglePinnedTeam(team); closeMenu()">
                        <component :is="store.isTeamPinned(team.team_key) ? PinOff : Pin" :size="13" class="text-muted" />
                        {{ store.isTeamPinned(team.team_key) ? 'Unpin' : 'Pin to sidebar' }}
                      </button>
                    </div>
                  </div>
                </Transition>
              </div>
            </div>

            <!-- Description -->
            <p v-if="team.description" class="text-sm text-muted leading-relaxed mb-3 line-clamp-2">
              {{ team.description }}
            </p>

            <!-- Stats row -->
            <div class="flex items-center gap-3 text-sm text-muted mb-3">
              <span>
                <strong class="text-foreground font-semibold">{{ team.project_count || 0 }}</strong>
                project{{ (team.project_count || 0) !== 1 ? 's' : '' }}
              </span>
              <span class="w-px h-3 bg-border shrink-0" />
              <span>
                <strong class="text-foreground font-semibold">{{ team.member_count || 0 }}</strong>
                member{{ (team.member_count || 0) !== 1 ? 's' : '' }}
              </span>
              <span class="w-px h-3 bg-border shrink-0" />
              <span :class="loadScore(team) > 8 ? 'text-danger' : ''">
                <strong :class="loadScore(team) > 8 ? 'text-danger' : 'text-foreground'" class="font-semibold">{{ team.open_task_count || 0 }}</strong>
                open
              </span>
              <span v-if="team.department" class="ml-auto inline-flex h-5 items-center px-2 rounded bg-surface-secondary text-xs font-medium text-muted">
                {{ team.department }}
              </span>
            </div>

            <!-- Member avatars -->
            <div v-if="(team.members || []).length" class="flex items-center mb-3">
              <Avatar
                v-for="m in (team.members || []).slice(0, 5)"
                :key="m.user"
                :name="m.full_name"
                size="sm"
                class="-ml-2 first:ml-0 ring-2 ring-overlay"
              />
              <span
                v-if="(team.members || []).length > 5"
                class="-ml-2 w-7 h-7 rounded-full bg-surface-secondary text-muted text-xs font-bold flex items-center justify-center ring-2 ring-overlay"
              >+{{ team.members.length - 5 }}</span>
            </div>

            <!-- Project tags -->
            <div v-if="(team.projects || []).length" class="flex flex-wrap gap-1">
              <span
                v-for="p in (team.projects || []).slice(0, 3)"
                :key="p.name"
                class="inline-flex h-5 items-center px-2 rounded text-xs font-medium cursor-pointer hover:opacity-80 transition-opacity"
                :style="{ background: `color-mix(in oklab, ${p.project_color || 'var(--accent)'} 9%, transparent)`, color: p.project_color || 'var(--accent)' }"
                @click.stop="$router.push('/workspace/' + p.key + '/board')"
              >{{ p.project_name }}</span>
              <span
                v-if="(team.projects || []).length > 3"
                class="inline-flex h-5 items-center px-1.5 rounded text-xs text-muted bg-surface-secondary"
              >+{{ team.projects.length - 3 }}</span>
            </div>
          </div>

        </div>
      </div>

    </div>

    <CreateTeam v-if="showCreate" @close="showCreate = false" @created="onCreated" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import Avatar from '@/ui/Avatar.vue'
import EmptyState from '@/ui/EmptyState.vue'
import KpiTile from '@/ui/KpiTile.vue'
import CreateTeam from '@/components/CreateTeam.vue'
import { Plus, Search, UsersRound, List, LayoutGrid, Search as SearchIcon, MoreHorizontal, Pin, PinOff, Settings } from 'lucide-vue-next'

const store  = useProjectStore()
const router = useRouter()

const loading      = ref(true)
const showCreate   = ref(false)
const teams        = ref([])
const viewMode     = ref(localStorage.getItem('bp-teams-view') || 'list')
const query        = ref('')
const openMenuName = ref(null)

function toggleMenu(name) {
  openMenuName.value = openMenuName.value === name ? null : name
}
function closeMenu() { openMenuName.value = null }
function onDocMenu(e) {
  if (!e.target.closest('[data-team-ctx]')) openMenuName.value = null
}
onMounted(() => document.addEventListener('mousedown', onDocMenu))
onUnmounted(() => document.removeEventListener('mousedown', onDocMenu))

const VIEWS = [
  { id: 'list', label: 'List', icon: List },
  { id: 'grid', label: 'Grid', icon: LayoutGrid },
]

// Persist view mode
import { watch } from 'vue'
watch(viewMode, v => localStorage.setItem('bp-teams-view', v))

// ── Computed stats ────────────────────────────────────────────────────
const totalMembers   = computed(() => teams.value.reduce((s, t) => s + (t.member_count || 0), 0))
const totalProjects  = computed(() => teams.value.reduce((s, t) => s + (t.project_count || 0), 0))
const departmentCount = computed(() => new Set(teams.value.map(t => t.department).filter(Boolean)).size)

// rank by load (open tasks per member), not alphabet. A team
// with 40 open tasks and 2 members is under more strain than one with 40
// tasks and 20 members — normalize before ranking, don't just sort by the
// raw count.
function loadScore(t) {
  const members = t.member_count || 1
  return (t.open_task_count || 0) / members
}
const filteredTeams = computed(() => {
  let out = teams.value
  if (query.value.trim()) {
    const q = query.value.toLowerCase()
    out = out.filter(t =>
      (t.team_name || '').toLowerCase().includes(q) ||
      (t.team_key  || '').toLowerCase().includes(q) ||
      (t.department || '').toLowerCase().includes(q)
    )
  }
  return [...out].sort((a, b) => loadScore(b) - loadScore(a))
})

// ── Data ──────────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    await store.fetchTeams()
    teams.value = store.teams || []
  } finally {
    loading.value = false
  }
}

async function onCreated(team) {
  showCreate.value = false
  await load()
  router.push('/workspace/team/' + team.team_key + '/settings')
}

onMounted(load)
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.teams-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 5px 8px;
  border-radius: 6px;
  font-size:var(--text-sm);
  font-weight: 500;
  color: var(--foreground);
  text-align: left;
  transition: background 0.1s;
  white-space: nowrap;
}
.teams-menu-item:hover { background: var(--surface-secondary); }

.dd-fade-enter-active, .dd-fade-leave-active { transition: opacity 0.12s, transform 0.12s; }
.dd-fade-enter-from, .dd-fade-leave-to { opacity: 0; transform: scale(0.96) translateY(-4px); }
</style>
