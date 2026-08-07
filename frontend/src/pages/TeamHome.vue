<template>
  <div v-if="!loading && team" class="min-h-full bg-[var(--background)]">

    <!-- ── Page header ───────────────────────────────────────────────────── -->
    <div class="bg-overlay border-b border-separator">
      <div class="px-6 pt-5 pb-0">

        <!-- Identity + Actions -->
        <div class="flex items-center justify-between gap-4 mb-4">

          <div class="flex items-center gap-3 min-w-0">
            <!-- Team icon — colored initials -->
            <div class="w-10 h-10 rounded-md flex items-center justify-center shrink-0 text-white text-sm font-bold"
              :style="{ background: team.team_color || 'var(--accent)' }">
              {{ (team.team_name || '?').slice(0, 2).toUpperCase() }}
            </div>
            <div class="min-w-0">
              <!-- Name + type badge -->
              <div class="flex items-center gap-2">
                <h1 class="text-xl font-bold text-foreground leading-none truncate">{{ team.team_name }}</h1>
                <span v-if="team.team_type"
                  class="shrink-0 text-xs font-medium text-muted bg-surface-secondary px-1.5 py-0.5 rounded-sm leading-none">
                  {{ team.team_type }}
                </span>
              </div>
              <!-- real header meta instead of a hardcoded line -->
              <p class="text-sm text-muted mt-1 leading-none">{{ headerMeta }}</p>
              <!-- Metadata row -->
              <div class="flex items-center gap-3 flex-wrap">
                <span v-if="team.members?.length" class="text-sm mt-1.5 text-muted">
                  {{ team.members.length }} member{{ team.members.length !== 1 ? 's' : '' }}
                </span>
                <span v-if="team.active_sprint"
                  class="flex items-center gap-1 text-xs font-semibold mt-1.5 text-success-soft-foreground bg-success-soft px-2 py-0.5 rounded-sm leading-none">
                  <Zap class="w-3 h-3 shrink-0" />{{ team.active_sprint.sprint_name }}
                </span>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-2 shrink-0">
            <Button size="sm"
              :variant="store.isTeamPinned(teamKey) ? 'flat' : 'bordered'"
              :color="store.isTeamPinned(teamKey) ? 'primary' : 'default'"
              :title="store.isTeamPinned(teamKey) ? 'Unpin from sidebar' : 'Pin to sidebar'"
              @click="store.togglePinnedTeam(team)">
              <template #startContent>
                <Pin v-if="!store.isTeamPinned(teamKey)" class="w-3.5 h-3.5" />
                <PinOff v-else class="w-3.5 h-3.5" />
              </template>
              {{ store.isTeamPinned(teamKey) ? 'Pinned' : 'Pin' }}
            </Button>
           
          </div>
        </div>

        <!-- Tab bar -->
        <div class="flex items-center">
          <div class="flex items-center p-0.5 bg-[var(--segment)] rounded-md gap-0.5">
            <button v-for="tab in TABS" :key="tab.id"
              class="flex items-center gap-1.5 px-3 h-7 text-sm font-medium rounded-sm transition-[background-color,color] duration-150 whitespace-nowrap"
              :class="activeTab === tab.id ? 'bg-overlay text-foreground shadow-sm' : 'text-muted hover:text-muted'"
              @click="handleTabClick(tab.id)">
              {{ tab.label }}
            </button>
          </div>
        </div>
        <div class="h-4" />

      </div>
    </div>

    <!-- ── Content ───────────────────────────────────────────────────────── -->
    <div class="px-6 py-5">

      <!-- ════════════════════ OVERVIEW ════════════════════════════════════ -->
      <div v-if="activeTab === 'overview'">

        <!-- Skeleton loading -->
        <div v-if="dashLoading">
          <div class="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
            <div v-for="i in 5" :key="i" class="bg-overlay rounded-md px-5 py-4"
              style="box-shadow:0 1px 3px 0 rgba(0,0,0,0.08),0 1px 2px 0 rgba(0,0,0,0.06),0 0 0 1px rgba(0,0,0,0.04)">
              <Skeleton class="h-3 w-20 mb-3" />
              <Skeleton class="h-6 w-14" />
            </div>
          </div>
          <div class="grid grid-cols-[1fr_288px] gap-4 items-start">
            <div class="bg-overlay rounded-md overflow-hidden"
              style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
              <div class="flex items-center gap-2 px-5 py-3 border-b border-separator">
                <Skeleton class="h-4 w-32" />
              </div>
              <div v-for="i in 4" :key="i" class="flex items-center gap-3 px-5 h-11 border-b border-separator last:border-b-0">
                <Skeleton class="w-2 h-2 rounded-full shrink-0" />
                <Skeleton class="h-3 flex-1" />
                <Skeleton class="h-5 w-16 rounded-md" />
                <Skeleton class="h-5 w-20 rounded-md" />
                <Skeleton class="h-5 w-[104px] rounded-md" />
              </div>
            </div>
            <div class="bg-overlay rounded-md overflow-hidden"
              style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
              <div class="flex items-center justify-between px-4 py-3 border-b border-separator">
                <Skeleton class="h-4 w-20" />
              </div>
              <div v-for="i in 5" :key="i" class="flex items-center gap-2.5 px-4 h-10 border-b border-separator last:border-b-0">
                <Skeleton class="w-7 h-7 rounded-full shrink-0" />
                <div class="flex-1 flex flex-col gap-1.5">
                  <Skeleton class="h-3 w-24" />
                  <Skeleton class="h-2.5 w-16" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Error state -->
        <div v-else-if="dashError"
          class="flex flex-col items-center gap-3 py-16 text-center bg-overlay rounded-md"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
          <div class="w-10 h-10 rounded-full bg-danger-soft flex items-center justify-center">
            <svg class="w-5 h-5 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            </svg>
          </div>
          <div>
            <p class="text-sm font-semibold text-foreground">Failed to load dashboard</p>
            <p class="text-xs text-muted mt-0.5">{{ dashError }}</p>
          </div>
          <Button size="sm" variant="bordered" @click="loadDashboard">Retry</Button>
        </div>

        <template v-else>
          <!-- KPI strip — full width above columns -->
          <div class="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
            <KpiTile label="Utilization" :value="dash.metrics.utilization_pct + '%'" subline="last 30 days" :progress="dash.metrics.utilization_pct" />
            <KpiTile label="Hours Logged" :value="dash.metrics.logged_hours + 'h'" subline="last 30 days" />
            <KpiTile label="Billable" :value="dash.metrics.billable_pct + '%'" subline="of logged" :progress="dash.metrics.billable_pct" />
            <KpiTile label="Owned Projects" :value="String(dash.metrics.owned_count)" subline="active" />
            <KpiTile label="Contributing To" :value="String(dash.metrics.contributing_count)" subline="other projects" />
          </div>

          <!-- capacity truth is the HERO: per-member overload +
               sprint health, above the project list (secondary). Additive
               to the existing 30-day aggregate KPIs/Capacity Outlook above
               (team-wide totals) — this answers the question those can't:
               WHICH person is overloaded, right now. -->
          <div class="grid grid-cols-2 gap-4 mb-4 items-start">
            <section class="bg-overlay rounded-md overflow-hidden" style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
              <div class="flex items-center gap-2 px-5 py-3 border-b border-separator">
                <Users class="w-3.5 h-3.5 text-muted shrink-0" />
                <span class="text-sm font-semibold text-foreground">Team capacity</span>
                <span class="text-sm text-muted">This week</span>
              </div>
              <div v-if="(team.capacity || []).length">
                <div v-for="m in team.capacity" :key="m.user"
                  class="flex items-center gap-3 px-5 h-12 border-b border-separator last:border-b-0">
                  <Avatar :src="m.user_image" :name="m.full_name" size="sm" />
                  <div class="min-w-0 flex-1">
                    <p class="text-[13px] font-medium text-foreground truncate leading-snug">{{ m.full_name }}</p>
                    <div class="w-full bg-surface-secondary rounded-sm overflow-hidden mt-1" style="height:5px">
                      <div class="h-full rounded-sm transition-[width,background-color] duration-400 ease-out"
                        :class="m.weekly?.[0]?.load_pct >= 100 ? 'bg-danger' : m.weekly?.[0]?.load_pct >= 80 ? 'bg-warning' : 'bg-success'"
                        :style="{ width: Math.min(m.weekly?.[0]?.load_pct || 0, 100) + '%' }" />
                    </div>
                  </div>
                  <span class="text-xs tabular-nums font-semibold shrink-0"
                    :class="m.weekly?.[0]?.load_pct >= 100 ? 'text-danger' : 'text-muted'">
                    {{ m.weekly?.[0]?.allocated || 0 }}h / {{ m.weekly?.[0]?.capacity || 40 }}h
                  </span>
                  <Chip v-if="m.overdue_count" size="sm" variant="flat" color="danger" class="shrink-0">{{ m.overdue_count }} overdue</Chip>
                </div>
              </div>
              <p v-else class="text-xs text-muted px-5 py-6 text-center">No members to show capacity for yet.</p>
            </section>

            <section class="bg-overlay rounded-md overflow-hidden" style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
              <div class="flex items-center gap-2 px-5 py-3 border-b border-separator">
                <Zap class="w-3.5 h-3.5 text-muted shrink-0" />
                <span class="text-sm font-semibold text-foreground">Sprint health</span>
              </div>
              <div v-if="team.active_sprint" class="px-5 py-4">
                <div class="flex items-center justify-between mb-3">
                  <p class="text-[13px] font-medium text-foreground">{{ team.active_sprint.sprint_name }}</p>
                  <span class="text-xs text-muted tabular-nums">{{ sprintDaysRemaining }} day{{ sprintDaysRemaining === 1 ? '' : 's' }} left</span>
                </div>
                <template v-if="team.sprint_burndown?.burndown">
                  <div class="flex items-center justify-between text-xs text-muted mb-1.5">
                    <span>Completion</span>
                    <span class="tabular-nums font-semibold text-foreground">{{ team.sprint_burndown.completion_rate }}%</span>
                  </div>
                  <div class="w-full bg-surface-secondary rounded-sm overflow-hidden" style="height:6px">
                    <div class="h-full bg-accent rounded-sm transition-[width] duration-400 ease-out" :style="{ width: team.sprint_burndown.completion_rate + '%' }" />
                  </div>
                  <p class="text-xs text-muted mt-3">
                    {{ team.sprint_burndown.burndown.total_points }} story points committed this sprint.
                  </p>
                </template>
                <p v-else class="text-xs text-muted">No burndown data yet — points get tracked as the sprint progresses.</p>
              </div>
              <p v-else class="text-xs text-muted px-5 py-6 text-center">No active sprint for this team.</p>
            </section>
          </div>

          <!-- 2-column body -->
          <div class="grid grid-cols-[1fr_288px] gap-4 items-start">

            <!-- ── LEFT MAIN ── -->
            <div class="flex flex-col gap-4">

              <!-- Owned Projects -->
              <section class="bg-overlay rounded-md overflow-hidden" style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
                <div class="flex items-center justify-between px-5 py-3 border-b border-separator">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-semibold text-foreground">Owned Projects</span>
                    <span class="text-xs font-semibold text-muted tabular-nums bg-surface-secondary px-1.5 py-px rounded-sm">{{ dash.owned_projects.length }}</span>
                  </div>
                  <Button size="sm" variant="light" @click="handleTabClick('projects')">Manage</Button>
                </div>
                <div v-if="dash.owned_projects.length" class="min-h-[220px]">
                  <div class="overflow-x-auto">
                    <!-- Header -->
                    <div class="grid items-center px-5 h-8 bg-surface-secondary border-b border-border text-xs font-semibold text-muted uppercase tracking-wider"
                      style="grid-template-columns:minmax(0,1fr) auto auto auto auto">
                      <span>Project</span>
                      <span class="whitespace-nowrap px-3">Key</span>
                      <span class="whitespace-nowrap px-4 text-right">Open tasks</span>
                      <span class="whitespace-nowrap px-4 text-right">Members</span>
                      <span class="w-[104px]"/>
                    </div>
                    <!-- Rows -->
                    <div>
                      <div v-for="p in dash.owned_projects" :key="p.name"
                        class="grid items-center px-5 h-12 cursor-pointer hover:bg-surface-secondary focus-visible:bg-surface-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/30 transition-colors border-b border-separator last:border-b-0 group"
                        style="grid-template-columns:minmax(0,1fr) auto auto auto auto"
                        tabindex="0"
                        role="button"
                        @click="$router.push('/workspace/' + p.key + '/board')"
                        @keydown.enter="$router.push('/workspace/' + p.key + '/board')">
                        <div class="flex items-center gap-2.5 min-w-0 pr-4">
                          <ProjectAvatar :theme="p.theme" :seed="p.key" size="xs" />
                          <div class="min-w-0">
                            <Tooltip :content="p.project_name" placement="top">
                              <template #trigger>
                                <p class="text-sm font-medium text-foreground truncate leading-snug">{{ p.project_name }}</p>
                              </template>
                            </Tooltip>
                            <p class="text-xs text-muted leading-snug truncate">{{ p.status || 'Active' }}</p>
                          </div>
                        </div>
                        <div class="px-3 whitespace-nowrap">
                          <span class="text-xs font-mono text-muted bg-surface-secondary px-1.5 py-0.5 rounded-sm">{{ p.key }}</span>
                        </div>
                        <div class="px-4 whitespace-nowrap flex justify-end">
                          <Chip v-if="p.open_count" size="sm" variant="flat" color="default">{{ p.open_count }} tasks</Chip>
                          <Chip v-else size="sm" variant="faded" color="default">—</Chip>
                        </div>
                        <div class="px-4 whitespace-nowrap flex justify-end">
                          <Chip v-if="p.team_member_count" size="sm" variant="flat" color="default">
                            {{ p.team_member_count }} / {{ team.members?.length || 0 }}
                          </Chip>
                          <Chip v-else size="sm" variant="dot" color="warning">Unassigned</Chip>
                        </div>
                        <div class="w-[104px] flex gap-1 opacity-0 group-hover:opacity-100 justify-end transition-opacity">
                          <Button size="sm" variant="bordered" class="h-6 px-2.5"
                            @click.stop="$router.push('/workspace/' + p.key + '/board')">Board</Button>
                          <Button size="sm" variant="bordered" class="h-6 px-2.5"
                            @click.stop="$router.push('/workspace/' + p.key + '/list')">List</Button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else class="flex flex-col items-center justify-center gap-3 min-h-[220px] text-center">
                  <div class="w-11 h-11 rounded-full bg-accent-soft flex items-center justify-center">
                    <FolderOpen class="w-5 h-5 text-accent" />
                  </div>
                  <div>
                    <p class="text-sm font-semibold text-foreground">No projects yet</p>
                    <p class="text-xs text-muted mt-0.5">Assign a project to track it here</p>
                  </div>
                  <Button size="sm" color="primary" @click="handleTabClick('projects')">
                    <template #startContent><Plus class="w-3.5 h-3.5" /></template>Assign project
                  </Button>
                </div>
              </section>

              <!-- Contributing To -->
              <section v-if="dash.contributing_to.length" class="bg-overlay rounded-md overflow-hidden" style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
                <div class="flex items-center gap-2 px-5 py-3 border-b border-separator">
                  <span class="text-sm font-semibold text-foreground">Contributing To</span>
                  <span class="text-xs font-semibold text-muted tabular-nums bg-surface-secondary px-1.5 py-px rounded-sm">{{ dash.contributing_to.length }}</span>
                  <span class="text-sm text-muted">Members on external projects</span>
                </div>
                <div class="overflow-x-auto min-h-[220px]">
                  <!-- Header -->
                  <div class="grid items-center px-5 h-8 bg-surface-secondary border-b border-border text-xs font-semibold text-muted uppercase tracking-wider"
                    style="grid-template-columns:minmax(0,1fr) auto auto auto">
                    <span>Project</span>
                    <span class="whitespace-nowrap px-4 text-right">Open tasks</span>
                    <span class="whitespace-nowrap px-4 text-right">Our members</span>
                    <span class="whitespace-nowrap px-4">Owned by</span>
                  </div>
                  <!-- Rows -->
                  <div>
                    <div v-for="p in dash.contributing_to" :key="p.name"
                      class="grid items-center px-5 h-12 cursor-pointer hover:bg-surface-secondary focus-visible:bg-surface-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/30 transition-colors border-b border-separator last:border-b-0"
                      style="grid-template-columns:minmax(0,1fr) auto auto auto"
                      tabindex="0"
                      role="button"
                      @click="$router.push('/workspace/' + p.key + '/board')"
                      @keydown.enter="$router.push('/workspace/' + p.key + '/board')">
                      <div class="flex items-center gap-2.5 min-w-0 pr-4">
                        <ProjectAvatar :theme="p.theme" :seed="p.key" size="xs" class="opacity-60" />
                        <div class="min-w-0">
                          <Tooltip :content="p.project_name" placement="top">
                            <template #trigger>
                              <p class="text-sm text-muted truncate leading-snug">{{ p.project_name }}</p>
                            </template>
                          </Tooltip>
                          <p class="text-xs font-mono text-muted leading-snug">{{ p.key }}</p>
                        </div>
                      </div>
                      <div class="px-4 whitespace-nowrap flex justify-end">
                        <Chip v-if="p.open_count" size="sm" variant="flat" color="default">{{ p.open_count }} tasks</Chip>
                        <Chip v-else size="sm" variant="faded" color="default">—</Chip>
                      </div>
                      <div class="px-4 whitespace-nowrap flex justify-end">
                        <Chip v-if="p.team_member_count" size="sm" variant="flat" color="primary">{{ p.team_member_count }} members</Chip>
                        <Chip v-else size="sm" variant="dot" color="warning">None</Chip>
                      </div>
                      <div class="px-4 whitespace-nowrap">
                        <Chip v-if="p.owning_team_name" size="sm" variant="faded" color="default">
                          <template #startContent><Users class="w-2.5 h-2.5" /></template>
                          {{ p.owning_team_name }}
                        </Chip>
                        <span v-else class="text-xs text-muted">—</span>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <!-- Capacity Outlook -->
              <section class="bg-overlay rounded-md overflow-hidden" style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
                <div class="flex items-center gap-2 px-5 py-3 border-b border-separator">
                  <BarChart2 class="w-3.5 h-3.5 text-muted shrink-0" />
                  <span class="text-sm font-semibold text-foreground">Capacity Outlook</span>
                  <span class="text-sm text-muted">Next 4 weeks</span>
                </div>
                <div v-if="dash.capacity_outlook.length" class="px-6 py-5">
                  <div class="flex items-end gap-3" style="height:140px">
                    <div v-for="w in dash.capacity_outlook" :key="w.week_start"
                      class="flex-1 flex flex-col items-center gap-1.5 min-w-0">
                      <span class="text-xs tabular-nums font-semibold leading-none"
                        :class="w.pct >= 95 ? 'text-warning' : 'text-muted'">{{ w.pct }}%</span>
                      <div class="w-full bg-surface-secondary rounded-sm overflow-hidden flex items-end" style="height:108px">
                        <div class="w-full transition-[height,background-color] duration-700 ease-out rounded-sm"
                          :class="w.pct >= 110 ? 'bg-danger' : w.pct >= 95 ? 'bg-warning' : w.pct >= 70 ? 'bg-success' : 'bg-accent'"
                          :style="{ height: Math.min(w.pct, 100) + '%' }" />
                      </div>
                    </div>
                  </div>
                  <div class="flex gap-3 mt-2">
                    <div v-for="w in dash.capacity_outlook" :key="w.week_start" class="flex-1 text-center">
                      <p class="text-xs font-medium text-muted truncate">{{ w.label }}</p>
                      <p class="text-xs text-muted tabular-nums">{{ w.allocated }}h / {{ w.capacity }}h</p>
                    </div>
                  </div>
                </div>
                <div v-else class="flex flex-col items-center gap-2 py-10 text-center">
                  <BarChart2 class="w-7 h-7 text-muted" />
                  <p class="text-sm text-muted">No tasks with due dates in the next 4 weeks.</p>
                </div>
              </section>

            </div><!-- /left -->

            <!-- ── RIGHT SIDEBAR ── -->
            <div class="flex flex-col gap-3">

              <!-- Active sprint -->
              <section v-if="team.active_sprint" class="bg-overlay rounded-md overflow-hidden" style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
                <div class="flex items-center gap-2 px-4 py-3 border-b border-separator">
                  <Zap class="w-3.5 h-3.5 text-warning shrink-0" />
                  <span class="text-sm font-semibold text-foreground flex-1">Active sprint</span>
                </div>
                <div class="px-4 py-3">
                  <p class="text-sm font-semibold text-muted">{{ team.active_sprint.sprint_name }}</p>
                  <p v-if="team.active_sprint.goal" class="text-sm text-muted mt-1 leading-relaxed italic">{{ team.active_sprint.goal }}</p>
                  <p v-if="team.active_sprint.start_date" class="text-sm text-muted mt-1.5">
                    {{ formatDate(team.active_sprint.start_date) }} → {{ formatDate(team.active_sprint.end_date) }}
                  </p>
                </div>
              </section>

              <!-- Members -->
              <section class="bg-overlay rounded-md overflow-hidden" style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
                <div class="flex items-center justify-between px-4 py-3 border-b border-separator">
                  <div class="flex items-center gap-1.5">
                    <span class="text-sm font-semibold text-foreground">Members</span>
                    <span class="text-xs font-semibold text-muted tabular-nums bg-surface-secondary px-1.5 py-px rounded-sm">{{ team.members?.length || 0 }}</span>
                  </div>
                  <Button size="sm" variant="flat" color="primary" @click="showAddMember = true">
                    <template #startContent><Plus class="w-3.5 h-3.5" /></template>Add
                  </Button>
                </div>
                <div v-if="team.members?.length" class="divide-y divide-separator">
                  <div v-for="m in team.members.slice(0, 7)" :key="m.user"
                    class="flex items-center gap-2.5 px-4 h-10 hover:bg-surface-secondary transition-colors">
                    <Avatar :name="m.full_name" :color="avatarColor(m.user)" size="sm" />
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-medium text-foreground truncate leading-none">{{ m.full_name }}</p>
                      <p class="text-sm text-muted mt-0.5 leading-none truncate">{{ m.role }}</p>
                    </div>
                  </div>
                  <div v-if="team.members.length > 7"
                    class="px-4 py-2 text-sm text-muted cursor-pointer hover:text-accent transition-colors"
                    @click="handleTabClick('members')">
                    +{{ team.members.length - 7 }} more
                  </div>
                </div>
                <div v-else class="flex flex-col items-center gap-3 py-8 text-center">
                  <div class="w-11 h-11 rounded-full bg-primary-50 flex items-center justify-center">
                    <Users class="w-5 h-5 text-primary-400" />
                  </div>
                  <div>
                    <p class="text-sm font-semibold text-foreground">No members yet</p>
                    <p class="text-xs text-muted mt-0.5">Invite someone to join this team</p>
                  </div>
                  <Button size="sm" color="primary" @click="showAddMember = true">
                    <template #startContent><UserPlus class="w-3.5 h-3.5" /></template>Add member
                  </Button>
                </div>
              </section>

              <!-- Details -->
              <section class="bg-overlay rounded-md overflow-hidden" style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
                <div class="flex items-center justify-between px-4 py-3 border-b border-separator">
                  <span class="text-sm font-semibold text-foreground">Details</span>
                  <Button size="sm" variant="light" :isIconOnly="true" @click="editingDesc = !editingDesc">
                    <Pencil class="w-3.5 h-3.5" />
                  </Button>
                </div>
                <!-- Description -->
                <div class="px-4 py-3 border-b border-separator">
                  <p v-if="!editingDesc && team.description" class="text-sm text-muted leading-relaxed">{{ team.description }}</p>
                  <p v-else-if="!editingDesc" class="text-sm text-muted italic">No description</p>
                  <div v-else>
                    <textarea v-model="descDraft" rows="3" autofocus
                      class="w-full px-2 py-1.5 text-xs text-muted bg-surface-secondary border border-border rounded-sm outline-none resize-none focus:border-accent focus:bg-overlay transition-colors" />
                    <div class="flex gap-1.5 mt-2">
                      <Button size="sm" color="primary" @click="saveDescription">Save</Button>
                      <Button size="sm" variant="bordered" @click="editingDesc = false; descDraft = team.description || ''">Cancel</Button>
                    </div>
                  </div>
                </div>
                <!-- Key-value -->
                <div class="divide-y divide-separator">
                  <div v-if="leadName" class="flex items-center justify-between px-4 py-2">
                    <span class="text-sm text-muted">Lead</span>
                    <span class="flex items-center gap-1.5 text-sm font-medium text-foreground">
                      <Avatar :name="leadName" :color="avatarColor(team.lead)" size="xs" />{{ leadName }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between px-4 py-2">
                    <span class="text-sm text-muted">Department</span>
                    <span class="text-sm text-muted">{{ team.department_name || '—' }}</span>
                  </div>
                  <div class="flex items-center justify-between px-4 py-2">
                    <span class="text-sm text-muted">Type</span>
                    <span class="text-sm text-muted">{{ team.team_type || 'Team' }}</span>
                  </div>
                  <div v-if="team.parent_team_info" class="flex items-center justify-between px-4 py-2">
                    <span class="text-sm text-muted">Parent</span>
                    <span class="text-sm font-medium text-accent cursor-pointer hover:underline"
                      @click="$router.push('/workspace/team/' + team.parent_team_info.team_key)">
                      {{ team.parent_team_info.team_name }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between px-4 py-2">
                    <span class="text-sm text-muted">Capacity</span>
                    <span class="text-sm text-muted">{{ team.capacity_hours_per_sprint || 80 }}h/sprint</span>
                  </div>
                </div>
              </section>

              <!-- Links -->
              <section class="bg-overlay rounded-md overflow-hidden" style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
                <div class="flex items-center justify-between px-4 py-3 border-b border-separator">
                  <div class="flex items-center gap-1.5">
                    <span class="text-sm font-semibold text-foreground">Links</span>
                    <span v-if="team.team_links?.length"
                      class="text-xs font-semibold text-muted tabular-nums bg-surface-secondary px-1.5 py-px rounded-sm">
                      {{ team.team_links.length }}
                    </span>
                  </div>
                  <Button size="sm" variant="flat" color="primary" @click="showAddLink = true">
                    <template #startContent><Plus class="w-3.5 h-3.5" /></template>Add
                  </Button>
                </div>
                <div v-if="team.team_links?.length" class="divide-y divide-separator">
                  <div v-for="(link, i) in team.team_links" :key="i"
                    class="flex items-center gap-2 px-4 py-2.5 group/lk hover:bg-surface-secondary transition-colors">
                    <FolderOpen v-if="link.link_type === 'Project'" class="w-3.5 h-3.5 text-muted shrink-0" />
                    <ExternalLink v-else class="w-3.5 h-3.5 text-muted shrink-0" />
                    <span v-if="link.link_type === 'Project'"
                      class="flex-1 text-xs text-accent hover:underline cursor-pointer truncate"
                      @click="$router.push('/workspace/' + link.project + '/board')">
                      {{ link.label || link.project }}
                    </span>
                    <a v-else :href="link.url" target="_blank" class="flex-1 text-xs text-accent hover:underline truncate">
                      {{ link.label || link.url }}
                    </a>
                    <Button size="sm" variant="light" color="danger" :isIconOnly="true"
                      class="opacity-0 group-hover/lk:opacity-100 w-6 h-6"
                      @click="removeLink(i)">
                      <X class="w-3 h-3" />
                    </Button>
                  </div>
                </div>
                <div v-if="showAddLink" class="px-4 py-3 border-t border-separator flex flex-col gap-2">
                  <select v-model="newLink.link_type"
                    class="w-full h-7 px-2 text-xs text-muted bg-surface-secondary border border-border rounded-sm outline-none focus:border-accent transition-colors">
                    <option>Project</option><option>External URL</option>
                  </select>
                  <input v-if="newLink.link_type === 'External URL'" v-model="newLink.url"
                    class="w-full h-7 px-2 text-xs bg-surface-secondary border border-border rounded-sm outline-none focus:border-accent transition-colors"
                    placeholder="https://…" />
                  <select v-else v-model="newLink.project"
                    class="w-full h-7 px-2 text-xs text-muted bg-surface-secondary border border-border rounded-sm outline-none focus:border-accent transition-colors">
                    <option v-for="p in team.projects" :key="p.name" :value="p.key">{{ p.project_name }}</option>
                  </select>
                  <input v-model="newLink.label"
                    class="w-full h-7 px-2 text-xs bg-surface-secondary border border-border rounded-sm outline-none focus:border-accent transition-colors"
                    placeholder="Label (optional)" />
                  <div class="flex gap-1.5">
                    <Button size="sm" color="primary" @click="addLink">Add</Button>
                    <Button size="sm" variant="bordered" @click="showAddLink = false">Cancel</Button>
                  </div>
                </div>
                <div v-if="!team.team_links?.length && !showAddLink" class="flex gap-1.5 px-4 py-3">
                  <Button size="sm" variant="bordered" class="flex-1 border-dashed"
                    @click="newLink.link_type = 'Project'; showAddLink = true">+ Project</Button>
                  <Button size="sm" variant="bordered" class="flex-1 border-dashed"
                    @click="newLink.link_type = 'External URL'; showAddLink = true">+ URL</Button>
                </div>
              </section>

              <!-- Sub-teams -->
              <section v-if="team.sub_teams?.length" class="bg-overlay rounded-md overflow-hidden" style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
                <div class="flex items-center gap-2 px-4 py-3 border-b border-separator">
                  <span class="text-sm font-semibold text-foreground flex-1">Sub-teams</span>
                  <span class="text-xs font-semibold text-muted tabular-nums bg-surface-secondary px-1.5 py-px rounded-sm">{{ team.sub_teams.length }}</span>
                </div>
                <div class="divide-y divide-separator">
                  <div v-for="st in team.sub_teams" :key="st.name"
                    class="flex items-center gap-2.5 px-4 h-10 cursor-pointer hover:bg-surface-secondary transition-colors"
                    @click="$router.push('/workspace/team/' + st.team_key)">
                    <Users class="w-3.5 h-3.5 text-muted shrink-0" />
                    <span class="flex-1 text-sm font-medium text-muted truncate">{{ st.team_name }}</span>
                    <ChevronRight class="w-3.5 h-3.5 text-muted shrink-0" />
                  </div>
                </div>
              </section>

            </div><!-- /sidebar -->
          </div><!-- /2-col -->
        </template>
      </div>

      <!-- ════════════════════ PROJECTS ════════════════════════════════════ -->
      <div v-if="activeTab === 'projects'" class="flex flex-col gap-4">

        <!-- Assigned projects -->
        <div class="bg-overlay rounded-md overflow-hidden"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
          <div class="flex items-center justify-between px-5 py-3 border-b border-separator">
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold text-foreground">Assigned projects</span>
              <span class="text-xs font-semibold text-muted tabular-nums bg-surface-secondary px-1.5 py-px rounded-sm">{{ team.projects?.length || 0 }}</span>
            </div>
            <Button size="sm" variant="bordered" @click="showAssignPanel = !showAssignPanel">
              <template #startContent><Plus class="w-3.5 h-3.5" /></template>Assign project
            </Button>
          </div>
          <div v-if="team.projects?.length" class="min-h-[220px] overflow-x-auto">
            <div class="grid items-center px-5 h-8 bg-[var(--surface-secondary)] border-b border-border/50 text-xs font-semibold text-muted uppercase tracking-wider"
              style="grid-template-columns: minmax(0,1fr) auto auto auto auto">
              <span>Project</span>
              <span class="whitespace-nowrap px-4 text-right">Members</span>
              <span class="whitespace-nowrap px-4 text-right">Open tasks</span>
              <span class="w-[148px]"/>
              <span class="w-8"/>
            </div>
            <div class="divide-y divide-separator">
              <div v-for="p in team.projects" :key="p.name"
                class="grid items-center px-5 h-12 hover:bg-surface-secondary transition-colors group cursor-pointer"
                style="grid-template-columns: minmax(0,1fr) auto auto auto auto"
                @click="$router.push('/workspace/' + p.key + '/board')">
                <div class="flex items-center gap-2.5 min-w-0 pr-4">
                  <ProjectAvatar :theme="p.theme" :seed="p.key" size="xs" />
                  <div class="min-w-0">
                    <p class="text-sm font-medium text-foreground truncate leading-snug">{{ p.project_name }}</p>
                    <p class="text-xs font-mono text-muted leading-snug">{{ p.key }}</p>
                  </div>
                </div>
                <div class="px-4 whitespace-nowrap flex justify-end">
                  <Chip v-if="p.team_member_count" size="sm" variant="flat" color="default">{{ p.team_member_count }} members</Chip>
                  <span v-else class="text-xs text-muted">—</span>
                </div>
                <div class="px-4 whitespace-nowrap flex justify-end">
                  <Chip v-if="p.open_count" size="sm" variant="flat" color="default">{{ p.open_count }} tasks</Chip>
                  <span v-else class="text-xs text-muted">—</span>
                </div>
                <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity w-[148px] justify-end" @click.stop>
                  <Button size="sm" variant="bordered" class="h-6 px-2.5"
                    @click="$router.push('/workspace/' + p.key + '/board')">Board</Button>
                  <Button size="sm" variant="bordered" class="h-6 px-2.5"
                    @click="$router.push('/workspace/' + p.key + '/list')">List</Button>
                  <Button size="sm" variant="bordered" class="h-6 px-2.5"
                    @click="$router.push('/workspace/' + p.key + '/backlog')">Backlog</Button>
                </div>
                <Button size="sm" variant="light" color="danger" :isIconOnly="true"
                  class="opacity-0 group-hover:opacity-100 w-7 h-7 mx-0.5"
                  title="Unassign" @click.stop="toggleProjectAssign(p)">
                  <X class="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          </div>
          <div v-else class="flex flex-col items-center justify-center gap-3 min-h-[220px] text-center">
            <div class="w-12 h-12 rounded-full bg-accent-soft flex items-center justify-center">
              <FolderOpen class="w-6 h-6 text-accent" />
            </div>
            <div>
              <p class="text-sm font-semibold text-foreground">No projects assigned</p>
              <p class="text-xs text-muted mt-0.5">Connect a project to this team to start tracking work</p>
            </div>
            <Button size="sm" color="primary" @click="showAssignPanel = true">
              <template #startContent><Plus class="w-3.5 h-3.5" /></template>Assign project
            </Button>
          </div>
        </div>

        <!-- Assign panel -->
        <div v-if="showAssignPanel"
          class="bg-overlay rounded-md overflow-hidden"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
          <div class="flex items-center justify-between px-5 py-3 border-b border-separator">
            <span class="text-sm font-semibold text-foreground">All projects</span>
            <Button size="sm" variant="light" :isIconOnly="true" @click="showAssignPanel = false">
              <X class="w-4 h-4" />
            </Button>
          </div>
          <div v-if="!settingsLoaded" class="flex items-center justify-center py-8 gap-2 text-sm text-muted">
            <Spinner class="w-4 h-4 text-primary-400" />
          </div>
          <template v-else>
            <div class="divide-y divide-separator">
              <div v-for="p in allProjects" :key="p.name"
                class="flex items-center gap-3 px-5 h-11 hover:bg-surface-secondary transition-colors">
                <ProjectAvatar :theme="p.theme" :seed="p.key" size="xs" />
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-foreground truncate">{{ p.project_name }}</p>
                  <p class="text-xs font-mono text-muted">{{ p.key }}</p>
                </div>
                <Button size="sm" class="h-6 shrink-0"
                  :variant="assignedProjectNames.has(p.name) ? 'flat' : 'bordered'"
                  :color="assignedProjectNames.has(p.name) ? 'primary' : 'default'"
                  @click="toggleProjectAssign(p)">
                  <template #startContent>
                    <Check v-if="assignedProjectNames.has(p.name)" class="w-3 h-3" />
                    <Plus v-else class="w-3 h-3" />
                  </template>
                  {{ assignedProjectNames.has(p.name) ? 'Assigned' : 'Assign' }}
                </Button>
              </div>
            </div>
            <div v-if="!allProjects.length" class="px-5 py-8 text-center text-sm text-muted">No projects available.</div>
          </template>
        </div>
      </div>

      <!-- ════════════════════ MEMBERS ════════════════════════════════════ -->
      <div v-if="activeTab === 'members'">
        <div class="bg-overlay rounded-md overflow-hidden"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
          <div class="flex items-center justify-between px-5 py-3 border-b border-separator">
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold text-foreground">Members</span>
              <span class="text-xs font-semibold text-muted tabular-nums bg-surface-secondary px-1.5 py-px rounded-sm">{{ team.members?.length || 0 }}</span>
            </div>
            <Button size="sm" variant="bordered" @click="showAddMember = true">
              <template #startContent><UserPlus class="w-3.5 h-3.5" /></template>Add member
            </Button>
          </div>
          <div class="grid items-center px-5 h-9 bg-[var(--surface-secondary)] border-b border-border/50"
            style="grid-template-columns: minmax(0,1fr) auto auto auto auto">
            <span class="text-xs font-semibold text-muted uppercase tracking-wider">Member</span>
            <span class="whitespace-nowrap px-4 text-xs font-semibold text-muted uppercase tracking-wider">Role</span>
            <span class="whitespace-nowrap px-4 text-xs font-semibold text-muted uppercase tracking-wider">Capacity</span>
            <span class="whitespace-nowrap px-4 text-xs font-semibold text-muted uppercase tracking-wider">Joined</span>
            <span class="w-8"/>
          </div>
          <div v-if="settingsMembers.length" class="divide-y divide-separator min-h-[220px]">
            <div v-for="(m, i) in settingsMembers" :key="m.user"
              class="grid items-center px-5 h-12 hover:bg-surface-secondary transition-colors"
              style="grid-template-columns: minmax(0,1fr) auto auto auto auto">
              <div class="flex items-center gap-3 min-w-0 pr-4">
                <Avatar :name="m.full_name" :color="avatarColor(m.user)" size="sm" />
                <div class="min-w-0">
                  <p class="text-sm font-medium text-foreground truncate leading-snug">{{ m.full_name }}</p>
                  <p class="text-xs text-muted truncate leading-snug">{{ m.user }}</p>
                </div>
              </div>
              <div class="px-4 flex items-center gap-2 whitespace-nowrap">
                <span :class="roleBadgeClass(m.role)" class="inline-flex items-center px-1.5 py-0.5 rounded-sm text-xs font-medium shrink-0">{{ m.role }}</span>
                <select v-model="m.role"
                  class="h-6 w-[90px] px-1.5 text-xs text-muted bg-surface-secondary border border-border rounded-sm outline-none focus:border-accent transition-colors">
                  <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
                </select>
              </div>
              <div class="px-4 flex items-center gap-1.5 whitespace-nowrap">
                <input v-model.number="m.capacity_hours_per_sprint" type="number" min="0"
                  class="h-6 w-14 px-1.5 text-xs text-muted bg-surface-secondary border border-border rounded-sm outline-none focus:border-accent transition-colors" />
                <span class="text-xs text-muted">h/sprint</span>
              </div>
              <div class="px-4 whitespace-nowrap">
                <span v-if="m.creation" class="text-xs text-muted">{{ formatDate(m.creation) }}</span>
                <span v-else class="text-xs text-muted">—</span>
              </div>
              <Button size="sm" variant="light" color="danger" :isIconOnly="true" class="w-7 h-7"
                @click="removeSettingsMember(i)">
                <Trash2 class="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
          <div v-else class="flex flex-col items-center justify-center gap-3 min-h-[220px] text-center">
            <div class="w-12 h-12 rounded-full bg-primary-50 flex items-center justify-center">
              <Users class="w-6 h-6 text-primary-400" />
            </div>
            <div>
              <p class="text-sm font-semibold text-foreground">No members yet</p>
              <p class="text-xs text-muted mt-0.5">Add your first team member to get started</p>
            </div>
            <Button size="sm" color="primary" @click="showAddMember = true">
              <template #startContent><UserPlus class="w-3.5 h-3.5" /></template>Add member
            </Button>
          </div>
          <div class="flex items-center gap-2 px-5 py-3.5 border-t border-separator bg-surface-secondary/40">
            <Button size="sm" color="primary" :isDisabled="settingsMembersSaving" @click="saveMembersSettings">
              {{ settingsMembersSaving ? 'Saving…' : 'Save changes' }}
            </Button>
            <Button size="sm" variant="bordered" @click="settingsMembers = (team.members || []).map(m => ({ ...m }))">
              Discard
            </Button>
          </div>
        </div>
      </div>

      <!-- ════════════════════ CAPACITY ════════════════════════════════════ -->
      <div v-if="activeTab === 'capacity'">
        <div class="bg-overlay rounded-md overflow-hidden"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
          <div class="flex items-center justify-between px-5 py-4 border-b border-separator">
            <h2 class="text-sm font-semibold text-foreground">Team Capacity — next 2 weeks</h2>
            <button type="button" class="text-xs text-accent hover:underline" @click="loadCapacity">Refresh</button>
          </div>

          <div v-if="capLoading" class="flex items-center justify-center py-16">
            <div class="size-5 border-2 border-border border-t-blue-600 rounded-full animate-spin"></div>
          </div>

          <div v-else-if="!capData.members.length" class="flex flex-col items-center gap-2 py-16 text-center">
            <p class="text-sm font-semibold text-muted">No capacity data</p>
            <p class="text-xs text-muted">Add members and assign tasks with due dates to see allocation.</p>
          </div>

          <div v-else class="p-5">
            <div class="overflow-x-auto" style="scrollbar-width:thin">
              <table class="text-xs min-w-full">
                <thead>
                  <tr>
                    <th class="w-32 text-left pb-3 pr-4 font-medium text-muted">Member</th>
                    <th v-for="dk in capData.days" :key="dk"
                      class="w-8 text-center pb-3 px-0.5 font-medium"
                      :class="dk === todayIso ? 'text-accent' : 'text-muted'">
                      <div>{{ dayName(dk) }}</div>
                      <div class="tabular-nums">{{ dayNum(dk) }}</div>
                    </th>
                    <th class="w-20 text-right pb-3 pl-3 font-medium text-muted">Total</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-separator">
                  <tr v-for="m in capData.members" :key="m.user" class="hover:bg-surface-secondary transition-colors">
                    <td class="pr-4 py-2">
                      <div class="flex items-center gap-2">
                        <div class="size-6 rounded-full flex items-center justify-center text-white text-[9px] font-bold shrink-0"
                          :style="{ backgroundColor: m.color }">{{ m.initials }}</div>
                        <span class="text-sm font-medium text-muted truncate max-w-[80px]">{{ m.full_name.split(' ')[0] }}</span>
                      </div>
                    </td>
                    <td v-for="dk in capData.days" :key="dk" class="px-0.5 py-2">
                      <div class="size-7 rounded-sm cursor-pointer transition-transform hover:scale-110 flex items-center justify-center relative group"
                        :class="heatmapCellClass(m.allocations[dk], m.daily_cap)"
                        :title="`${m.full_name}: ${(m.allocations[dk] || 0).toFixed(1)}h of ${m.daily_cap.toFixed(1)}h capacity`">
                        <span v-if="m.allocations[dk] > 0" class="text-[9px] font-bold opacity-60">{{ Math.round(m.allocations[dk]) }}</span>
                      </div>
                    </td>
                    <td class="pl-3 py-2 text-right">
                      <span class="text-xs font-semibold tabular-nums text-muted">
                        {{ totalAllocated(m) }}h
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Legend -->
            <div class="mt-5 flex flex-wrap items-center gap-4 text-xs font-medium text-muted">
              <div class="flex items-center gap-1.5"><span class="size-3 rounded-sm bg-surface-secondary border border-border"></span>Idle</div>
              <div class="flex items-center gap-1.5"><span class="size-3 rounded-sm bg-success-soft"></span>Healthy (&lt;80%)</div>
              <div class="flex items-center gap-1.5"><span class="size-3 rounded-sm bg-warning-soft"></span>Busy (80–100%)</div>
              <div class="flex items-center gap-1.5"><span class="size-3 rounded-sm bg-danger-soft"></span>Over capacity</div>
              <div class="flex items-center gap-1.5"><span class="size-3 rounded-sm bg-danger"></span>Critical (&gt;130%)</div>
            </div>

            <!-- Summary -->
            <p class="mt-3 text-sm text-muted">{{ capacitySummary }}</p>
          </div>
        </div>
      </div>

      <!-- ════════════════════ ACTIVITY ════════════════════════════════════ -->
      <div v-if="activeTab === 'activity'">
        <div class="bg-overlay rounded-md overflow-hidden"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
          <div class="flex items-center gap-2 px-5 py-3 border-b border-separator">
            <Clock class="w-3.5 h-3.5 text-muted shrink-0" />
            <span class="text-sm font-semibold text-foreground">Recent Activity</span>
            <span v-if="team.recent_activity?.length"
              class="text-xs font-semibold text-muted tabular-nums bg-surface-secondary px-1.5 py-px rounded-sm">
              {{ team.recent_activity.length }}
            </span>
          </div>
          <div v-if="team.recent_activity?.length" class="divide-y divide-separator">
            <div v-for="a in team.recent_activity" :key="a.name"
              class="flex items-start gap-3 px-5 py-3 hover:bg-surface-secondary transition-colors">
              <Avatar :name="a.user_name || a.user" :color="avatarColor(a.user)" size="sm" class="shrink-0 mt-0.5" />
              <div class="flex-1 min-w-0">
                <p class="text-sm text-foreground leading-snug">
                  <span class="font-semibold">{{ a.user_name || a.user }}</span>
                  <span class="text-muted"> {{ activityVerb(a) }} </span>
                  <span class="text-accent cursor-pointer hover:underline font-medium"
                    @click="store.openTaskDetail(a.issue)">{{ a.task_key }}</span>
                </p>
                <p v-if="a.project_name || a.task_title" class="text-xs text-muted mt-0.5 truncate">
                  <span v-if="a.project_name" class="font-medium text-muted">{{ a.project_name }}</span>
                  <span v-if="a.project_name && a.task_title" class="mx-1">·</span>
                  <span v-if="a.task_title">{{ a.task_title }}</span>
                </p>
              </div>
              <div class="shrink-0 flex flex-col items-end gap-1">
                <span class="text-xs text-muted tabular-nums whitespace-nowrap">{{ timeAgo(a.creation) }}</span>
                <span v-if="a.activity_type"
                  class="text-xs font-medium px-1.5 py-px rounded-sm leading-none"
                  :class="{
                    'bg-emerald-50 text-emerald-700': a.activity_type === 'created',
                    'bg-blue-50 text-blue-700': a.activity_type === 'status_changed',
                    'bg-purple-50 text-purple-700': a.activity_type === 'comment',
                    'bg-surface-secondary text-muted': !['created','status_changed','comment'].includes(a.activity_type),
                  }">{{ a.activity_type.replace('_', ' ') }}</span>
              </div>
            </div>
          </div>
          <div v-else class="flex flex-col items-center gap-2 py-16 text-center">
            <div class="w-10 h-10 rounded-full bg-surface-secondary flex items-center justify-center">
              <Clock class="w-5 h-5 text-muted" />
            </div>
            <p class="text-sm font-semibold text-muted">No recent activity</p>
            <p class="text-xs text-muted">Activity will appear here as the team works on tasks</p>
          </div>
        </div>
      </div>

      <!-- ════════════════════ SETTINGS ════════════════════════════════════ -->
      <div v-if="activeTab === 'settings'" class="flex flex-col gap-4">

        <!-- GENERAL -->
        <div
          class="bg-overlay rounded-md overflow-hidden"
          style="box-shadow:0 2px 4px 0 rgba(0,0,0,0.04),0 1px 2px 0 rgba(0,0,0,0.06),0 0 1px 0 rgba(0,0,0,0.06)">
          <div class="px-6 py-5 border-b border-separator grid grid-cols-2 gap-x-8 gap-y-5">
            <!-- Team name -->
            <Input label="Team name" v-model="settingsDraft.team_name" size="sm" />
            <!-- Team type -->
            <Select label="Team type" size="sm" placeholder="General"
              :model-value="selVal(settingsDraft.team_type)"
              @update:model-value="settingsDraft.team_type = draftVal($event)">
              <SelectItem :value="NONE">General</SelectItem>
              <SelectItem value="Squad">Squad</SelectItem>
              <SelectItem value="Chapter">Chapter</SelectItem>
              <SelectItem value="Department">Department</SelectItem>
              <SelectItem value="Cross-functional">Cross-functional</SelectItem>
              <SelectItem value="Guild">Guild</SelectItem>
              <SelectItem value="Tiger team">Tiger team</SelectItem>
            </Select>
            <!-- Color — spans full width -->
            <div class="col-span-2 flex flex-col gap-1.5">
              <span class="text-xs font-semibold text-muted">Color</span>
              <div class="flex items-center gap-2 flex-wrap">
                <button v-for="c in TEAM_COLORS" :key="c"
                  class="w-6 h-6 rounded-full transition-transform hover:scale-110 relative"
                  :style="{ background: c }"
                  @click="settingsDraft.team_color = c">
                  <span v-if="settingsDraft.team_color === c"
                    class="absolute inset-0 flex items-center justify-center">
                    <Check class="w-3.5 h-3.5 text-white drop-shadow" />
                  </span>
                </button>
                <span class="w-5 h-5 rounded-full shrink-0 ml-1" :style="{ background: settingsDraft.team_color || 'var(--accent)' }" />
                <span class="text-xs text-muted font-mono">{{ settingsDraft.team_color || 'var(--accent)' }}</span>
              </div>
            </div>
            <!-- Description — spans full width -->
            <Textarea class="col-span-2" label="Description" v-model="settingsDraft.description" :rows="3" />
          </div>
          <div class="px-6 py-5 border-b border-separator grid grid-cols-2 gap-x-8 gap-y-5">
            <!-- Team lead -->
            <Select label="Team lead" size="sm" placeholder="No lead"
              :model-value="selVal(settingsDraft.lead)"
              @update:model-value="settingsDraft.lead = draftVal($event)">
              <SelectItem :value="NONE">No lead</SelectItem>
              <SelectItem v-for="u in allUsers" :key="u.user" :value="u.user" :text-value="u.full_name || u.user">
                {{ u.full_name || u.user }}
              </SelectItem>
            </Select>
            <!-- Department -->
            <Select label="Department" size="sm" placeholder="No department"
              :model-value="selVal(settingsDraft.department)"
              @update:model-value="settingsDraft.department = draftVal($event)">
              <SelectItem :value="NONE">No department</SelectItem>
              <SelectItem v-for="d in filteredDepartments" :key="d.name" :value="d.name" :text-value="d.department_name || d.name">
                {{ d.department_name || d.name }}
              </SelectItem>
            </Select>
            <!-- Parent team -->
            <Select label="Parent team" size="sm" placeholder="No parent" description="Makes this a sub-team"
              :model-value="selVal(settingsDraft.parent_team)"
              @update:model-value="settingsDraft.parent_team = draftVal($event)">
              <SelectItem :value="NONE">No parent</SelectItem>
              <SelectItem v-for="t in otherTeams" :key="t.name" :value="t.name" :text-value="t.team_name">
                {{ t.team_name }}
              </SelectItem>
            </Select>
            <!-- Sprint capacity -->
            <Input label="Sprint capacity" type="number" min="0" size="sm"
              description="Used in capacity charts"
              :model-value="String(settingsDraft.capacity_hours_per_sprint || '')"
              @update:model-value="settingsDraft.capacity_hours_per_sprint = Number($event) || 0">
              <template #endContent>
                <span class="text-xs text-muted pr-1">h/sprint</span>
              </template>
            </Input>
          </div>

          <!-- ── Info (read-only) ── -->
          <div class="px-6 py-3.5 flex items-center gap-3">
            <span class="text-sm text-muted">Team key:</span>
            <span class="text-sm font-mono text-muted bg-surface-secondary px-2 py-0.5 rounded-sm">{{ team.team_key }}</span>
            <span class="text-xs text-muted">Used in URLs — contact admin to change</span>
          </div>

          <!-- ── Save footer ── -->
          <div class="flex items-center gap-2 px-6 py-3.5 border-t border-separator bg-surface-secondary/40">
            <Button size="sm" color="primary" :isDisabled="settingsSaving" @click="saveGeneralSettings">
              {{ settingsSaving ? 'Saving…' : 'Save changes' }}
            </Button>
            <Button size="sm" variant="bordered" @click="resetSettingsDraft">Discard</Button>
          </div>
        </div>

      </div><!-- /settings -->

    </div><!-- /content -->

    <!-- ── Add member modal ──────────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showAddMember"
        class="fixed inset-0 z-[400] bg-black/40 backdrop-blur-[1px] flex items-center justify-center"
        @click.self="showAddMember = false">
        <div class="bg-overlay rounded-md w-[380px] shadow-xl overflow-hidden">
          <div class="flex items-center justify-between px-5 py-3.5 border-b border-separator">
            <span class="text-sm font-semibold text-foreground">Add member</span>
            <Button size="sm" variant="light" :isIconOnly="true" class="w-7 h-7" @click="showAddMember = false">
              <X class="w-3.5 h-3.5" />
            </Button>
          </div>
          <div class="p-5 flex flex-col gap-3">
            <FieldDropdown width="w-full">
              <template #trigger>
                <button class="w-full h-8 px-3 text-left text-xs text-muted bg-surface-secondary border border-border rounded-md hover:border-border-secondary transition-colors">
                  {{ addMemberUser ? getMemberName(addMemberUser) : 'Select user…' }}
                </button>
              </template>
              <template #search>
                <div class="px-3 py-2 border-b border-separator">
                  <input v-model="memberQ" autofocus placeholder="Search…"
                    class="w-full text-xs outline-none bg-transparent text-foreground placeholder:text-muted" />
                </div>
              </template>
              <DropdownItem v-for="u in availableUsers" :key="u.user" @click="addMemberUser = u.user">
                <Avatar :name="u.full_name" :color="avatarColor(u.user)" size="xs" class="mr-2 shrink-0" />
                {{ u.full_name }}
              </DropdownItem>
            </FieldDropdown>
            <FieldDropdown width="w-full">
              <template #trigger>
                <button class="w-full h-8 px-3 text-left text-xs text-muted bg-surface-secondary border border-border rounded-md hover:border-border-secondary transition-colors">
                  {{ addMemberRole }}
                </button>
              </template>
              <DropdownItem v-for="r in ROLES" :key="r" :active="addMemberRole === r" @click="addMemberRole = r">{{ r }}</DropdownItem>
            </FieldDropdown>
          </div>
          <div class="flex justify-end gap-2 px-5 py-3.5 border-t border-separator">
            <Button size="sm" variant="bordered" @click="showAddMember = false">Cancel</Button>
            <Button size="sm" color="primary" :isDisabled="!addMemberUser" @click="submitAddMember">Add</Button>
          </div>
        </div>
      </div>
    </Teleport>

  </div><!-- /root -->

  <div v-else-if="loading" class="flex items-center justify-center h-48 gap-2 text-muted text-sm">
    <Spinner class="w-4 h-4 text-primary-400" />
  </div>
  <div v-else class="flex items-center justify-center h-48 text-sm text-muted">Team not found.</div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useEntitlementsStore } from '@/stores/entitlements'
import { avatarColor } from '@/utils/constants.js'
import * as api from '@/utils/api.js'
import FieldDropdown from '@/components/FieldDropdown.vue'
import DropdownItem  from '@/components/DropdownItem.vue'
import Avatar    from '@/ui/Avatar.vue'
import Spinner   from '@/ui/Spinner.vue'
import KpiTile   from '@/ui/KpiTile.vue'
import { Input, Textarea, Select, SelectItem, Button, Chip, Skeleton, Tooltip, ProjectAvatar } from '@/ui'
import {
  Users, UserPlus, Building,
  ChevronRight, FolderOpen, ExternalLink,
  X, Plus, Zap, Pencil, Clock, Trash2, Check, BarChart2, Pin, PinOff, CheckSquare,
} from 'lucide-vue-next'
import { alertDialog } from '@/composables/useConfirmDialog'

const route   = useRoute()
const store   = useProjectStore()
const teamKey = computed(() => route.params.key)

const loading       = ref(true)
const team          = ref(null)
// real header meta replacing the hardcoded subtitle.
const headerMeta = computed(() => {
  if (!team.value) return ''
  const parts = []
  if (team.value.lead_full_name || team.value.lead) parts.push(team.value.lead_full_name || team.value.lead)
  if (team.value.department_name) parts.push(team.value.department_name)
  const n = team.value.members?.length || 0
  parts.push(`${n} member${n !== 1 ? 's' : ''}`)
  return parts.join(' · ')
})
const sprintDaysRemaining = computed(() => {
  const end = team.value?.active_sprint?.end_date
  if (!end) return 0
  const diff = Math.ceil((new Date(end + 'T00:00:00') - new Date()) / 86400000)
  return Math.max(diff, 0)
})
const activeTab     = ref('overview')
const editingDesc   = ref(false)
const descDraft     = ref('')
const showAddLink   = ref(false)
const showAddMember = ref(false)
const memberQ       = ref('')
const addMemberUser = ref(null)
const addMemberRole = ref('Member')
const allUsers      = ref([])
const newLink       = ref({ link_type: 'External URL', label: '', url: '', project: '' })

// Dashboard
const dashLoading = ref(false)
const dashError   = ref(null)

// Capacity heatmap
const capLoading  = ref(false)
const capData     = ref({ days: [], members: [] })
const dash = ref({
  metrics:          { utilization_pct: 0, logged_hours: 0, billable_pct: 0, owned_count: 0, contributing_count: 0 },
  owned_projects:   [],
  contributing_to:  [],
  capacity_outlook: [],
})

// Settings / editable state
const settingsDraft         = ref({})
const settingsLoaded        = ref(false)
const settingsSaving        = ref(false)
const departments           = ref([])
const allProjects           = ref([])
const settingsMembers       = ref([])
const settingsMembersSaving = ref(false)
const showAssignPanel       = ref(false)
const assignedProjectNames  = computed(() => new Set((team.value?.projects || []).map(p => p.name)))

const TABS = computed(() => [
  { id: 'overview',  label: 'Overview' },
  { id: 'projects',  label: 'Projects', count: team.value?.projects?.length || 0 },
  { id: 'members',   label: 'Members',  count: team.value?.members?.length  || 0 },
  { id: 'capacity',  label: 'Capacity' },
  { id: 'activity',  label: 'Activity' },
  { id: 'settings',  label: 'Settings' },
])

const ROLES = ['Admin', 'Manager', 'Member', 'Viewer']

const TEAM_COLORS = [
  'var(--accent)', 'var(--accent)', '#26B5CE', '#4CB782',
  '#059669', '#7C3AED', '#E91E63', '#E57373',
  '#F2994A', '#D97706', 'var(--foreground)', 'var(--muted)',
]

const otherTeams = computed(() =>
  (store.teams || []).filter(t => t.name !== team.value?.name)
)

// reka-ui forbids value="" on SelectItem — map '' ↔ '__none__'
const NONE = '__none__'
function selVal(v)   { return v || NONE }
function draftVal(v) { return v === NONE ? '' : v }

// Departments filtered to team's company to avoid cross-company duplicates
const filteredDepartments = computed(() => {
  const company = team.value?.company
  const list = company
    ? departments.value.filter(d => d.company === company)
    : departments.value
  // Fallback: if filtering emptied the list, show all (deduped by display name)
  const source = list.length ? list : departments.value
  const seen = new Set()
  return source.filter(d => {
    const key = d.department_name || d.name
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
})

function handleTabClick(id) {
  activeTab.value = id
  if ((id === 'settings' || id === 'projects') && !settingsLoaded.value) loadSettingsData()
  if (id === 'capacity' && !capData.value.days.length) loadCapacity()
}

async function loadCapacity() {
  if (!team.value?.name) return
  capLoading.value = true
  try {
    capData.value = await api.getTeamCapacityHeatmap(team.value.name)
  } catch (e) {
    console.error('Capacity heatmap error', e)
  } finally {
    capLoading.value = false
  }
}

async function loadDashboard() {
  if (!team.value?.name) return
  dashLoading.value = true
  dashError.value = null
  try {
    dash.value = await api.getTeamDashboard(team.value.name)
  } catch (e) {
    console.error('Team dashboard error', e)
    dashError.value = e?.message || 'Failed to load dashboard data'
  } finally {
    dashLoading.value = false
  }
}

const leadName = computed(() => {
  if (!team.value?.lead) return ''
  return (
    team.value.members?.find(m => m.user === team.value.lead)?.full_name ||
    allUsers.value.find(u => u.user === team.value.lead)?.full_name ||
    team.value.lead
  )
})

const availableUsers = computed(() => {
  const existing = new Set((team.value?.members || []).map(m => m.user))
  const q = memberQ.value.toLowerCase()
  return allUsers.value.filter(u =>
    !existing.has(u.user) &&
    (!q || u.full_name?.toLowerCase().includes(q) || u.user.toLowerCase().includes(q))
  )
})

function getMemberName(u) {
  return allUsers.value.find(x => x.user === u)?.full_name || u
}

function hexAlpha(hex, alpha) {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

function roleBadgeClass(role) {
  const r = (role || '').toLowerCase()
  if (r === 'admin')   return 'bg-blue-50   text-blue-700   border border-blue-200'
  if (r === 'manager') return 'bg-violet-50  text-violet-700 border border-violet-200'
  if (r === 'member')  return 'bg-emerald-50 text-emerald-700 border border-emerald-200'
  return 'bg-surface-secondary text-muted border border-border'
}

function formatDate(d) {
  return d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'
}

function timeAgo(dt) {
  const s = (Date.now() - new Date(dt)) / 1000
  if (s < 60)    return 'just now'
  if (s < 3600)  return Math.round(s / 60) + 'm ago'
  if (s < 86400) return Math.round(s / 3600) + 'h ago'
  return Math.round(s / 86400) + 'd ago'
}

// ── Capacity heatmap helpers ───────────────────────────────────────────────
const todayIso = new Date().toISOString().slice(0, 10)

function dayName(dk) {
  return new Date(dk + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short' }).slice(0, 2)
}
function dayNum(dk) {
  return new Date(dk + 'T00:00:00').getDate()
}
function heatmapCellClass(h, cap) {
  if (!h || h <= 0) return 'bg-surface-secondary'
  const r = h / (cap || 8)
  if (r > 1.3) return 'bg-danger'
  if (r > 1.0) return 'bg-danger-soft'
  if (r > 0.8) return 'bg-warning-soft'
  if (r > 0.0) return 'bg-success-soft'
  return 'bg-surface-secondary'
}
function totalAllocated(m) {
  return Object.values(m.allocations).reduce((s, h) => s + h, 0).toFixed(1)
}
const capacitySummary = computed(() => {
  if (!capData.value.members.length) return ''
  let over = 0, under = 0
  for (const m of capData.value.members) {
    const totalH = Object.values(m.allocations).reduce((s, h) => s + h, 0)
    const totalCap = m.daily_cap * capData.value.days.length
    if (totalH > totalCap * 1.1) over++
    else if (totalH < totalCap * 0.5) under++
  }
  const parts = []
  if (over)  parts.push(`${over} ${over === 1 ? 'person' : 'people'} over capacity`)
  if (under) parts.push(`${under} with available capacity`)
  return parts.length ? parts.join(' · ') : 'Team capacity looks balanced'
})

function activityVerb(a) {
  if (a.activity_type === 'created')        return 'created'
  if (a.activity_type === 'status_changed') return 'changed status to ' + a.new_value + ' on'
  if (a.activity_type === 'comment')        return 'commented on'
  return 'updated ' + (a.field_name || '') + ' on'
}

async function saveDescription() {
  await api.updateTeam(team.value.name, { description: descDraft.value })
  team.value.description = descDraft.value
  editingDesc.value = false
  await store.fetchTeams()
}

async function addLink() {
  const links = [...(team.value.team_links || []), { ...newLink.value }]
  await api.updateTeamLinks(team.value.name, links)
  team.value.team_links = links
  showAddLink.value = false
  newLink.value = { link_type: 'External URL', label: '', url: '', project: '' }
}

async function removeLink(idx) {
  const links = (team.value.team_links || []).filter((_, i) => i !== idx)
  await api.updateTeamLinks(team.value.name, links)
  team.value.team_links = links
}

async function submitAddMember() {
  if (!addMemberUser.value) return
  const u = allUsers.value.find(x => x.user === addMemberUser.value)
  if (!u) return

  // Seat pre-check: block client-side before server call
  const ent = useEntitlementsStore()
  if (ent.isAtCapacity) {
    // The server will also enforce — this is optimistic UX
    ent.showUpgradePrompt?.('seat_limit')
    return
  }

  const members = [
    ...(team.value.members || []),
    { user: u.user, full_name: u.full_name, role: addMemberRole.value, capacity_hours_per_sprint: 40 },
  ]
  await api.updateTeamMembers(team.value.name, members)
  team.value.members  = members
  showAddMember.value = false
  addMemberUser.value = null
  addMemberRole.value = 'Member'
  memberQ.value       = ''
  await store.fetchTeams()
}

function resetSettingsDraft() {
  if (!team.value) return
  settingsDraft.value = {
    team_name:                 team.value.team_name,
    team_color:                team.value.team_color || 'var(--accent)',
    team_type:                 team.value.team_type || '',
    description:               team.value.description || '',
    lead:                      team.value.lead || '',
    department:                team.value.department || '',
    parent_team:               team.value.parent_team || '',
    capacity_hours_per_sprint: team.value.capacity_hours_per_sprint || 80,
  }
  settingsMembers.value = (team.value.members || []).map(m => ({ ...m }))
}

async function loadSettingsData() {
  const [depts, projects] = await Promise.all([api.getErpNextDepartments(), api.getProjects()])
  departments.value  = Array.isArray(depts)    ? depts    : []
  allProjects.value  = Array.isArray(projects) ? projects : []
  settingsLoaded.value = true
}

async function saveGeneralSettings() {
  settingsSaving.value = true
  try {
    await api.updateTeam(team.value.name, settingsDraft.value)
    Object.assign(team.value, settingsDraft.value)
    await store.fetchTeams()
    // Sync color into pinned teams so sidebar icon updates immediately
    const pinned = store.pinnedTeams.find(t => t.team_key === teamKey.value)
    if (pinned && settingsDraft.value.team_color) {
      pinned.team_color = settingsDraft.value.team_color
      try { localStorage.setItem('bp_pinned_teams', JSON.stringify(store.pinnedTeams)) } catch {}
    }
  } finally {
    settingsSaving.value = false
  }
}

async function saveMembersSettings() {
  settingsMembersSaving.value = true
  try {
    await api.updateTeamMembers(team.value.name, settingsMembers.value)
    team.value.members = settingsMembers.value.map(m => ({ ...m }))
    await store.fetchTeams()
  } finally {
    settingsMembersSaving.value = false
  }
}

function removeSettingsMember(i) { settingsMembers.value.splice(i, 1) }

async function toggleProjectAssign(p) {
  const wasAssigned = assignedProjectNames.value.has(p.name)
  try {
    await api.assignProjectToTeam(p.name, wasAssigned ? '' : team.value.name)
    team.value.projects = wasAssigned
      ? (team.value.projects || []).filter(x => x.name !== p.name)
      : [...(team.value.projects || []), p]
    await store.fetchTeams()
  } catch (e) {
    console.error('Failed to assign project', e)
    alertDialog(e.message || 'Failed to update project assignment')
  }
}


async function load() {
  loading.value = true
  try {
    if (!store.teams.length) await store.fetchTeams()
    const t = store.teams.find(t => t.team_key === teamKey.value)
    if (!t) { loading.value = false; return }
    const [td, users] = await Promise.all([api.getTeam(t.name), api.getMembers()])
    team.value      = td
    descDraft.value = td.description || ''
    allUsers.value  = users?.user_list || users?.employees || (Array.isArray(users) ? users : [])
    resetSettingsDraft()
    settingsLoaded.value = false
    // Handle ?tab=settings redirect from old TeamSettings route
    const tabParam = route.query.tab
    if (tabParam && TABS.value.find(t => t.id === tabParam)) {
      handleTabClick(tabParam)
    }
    loadDashboard()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
})
onBeforeUnmount(() => {})
watch(teamKey, load)
watch(showAddMember, val => {
  if (!val) settingsMembers.value = (team.value?.members || []).map(m => ({ ...m }))
})
</script>
