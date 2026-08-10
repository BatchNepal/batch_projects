<template>
  <div class="min-h-full bg-background font-sans text-foreground">
    <div class="max-w-[1600px] mx-auto px-6 py-6">

      <!-- ── Page Header ─────────────────────────────────────────────── -->
      <header class="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 class="text-3xl font-semibold text-foreground leading-8 tracking-tight">{{ greeting }}, {{ firstName }}</h1>
          <p class="mt-1 text-sm text-muted leading-none">
            <template v-for="(seg, i) in smartContext" :key="i">
              <a href="#" class="hover:text-muted transition-colors" @click.prevent="scrollTo(seg.anchor)">{{ seg.text }}</a>
              <span v-if="i < smartContext.length - 1" class="mx-1.5 text-muted">·</span>
            </template>
          </p>
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <div class="flex items-center p-0.5 bg-surface-secondary border border-border rounded-lg">
            <button v-for="m in modes" :key="m.value" type="button"
              :class="[
                'px-3 h-7 text-xs font-medium rounded-md transition-[background-color,color,box-shadow,transform] duration-150 active:scale-[0.97]',
                mode === m.value ? 'bg-overlay text-foreground shadow-sm border border-border' : 'text-muted hover:text-muted',
              ]"
              @click="mode = m.value">{{ m.label }}</button>
          </div>
        </div>
      </header>

      <!-- ── KPI Strip ───────────────────────────────────────────────── -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <KpiTile v-for="kpi in activeKpis" :key="kpi.label" v-bind="kpi" />
      </div>

      <!-- Loading: section skeletons mirror the 8/4 grid -->
      <div v-if="loading" class="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div class="lg:col-span-8 flex flex-col gap-4">
          <div v-for="s in 2" :key="'skl' + s" class="bg-overlay rounded-lg border p-5">
            <Skeleton class="h-3 mb-4" :style="{ width: (110 + s * 30) + 'px' }" />
            <div class="space-y-3">
              <div v-for="r in 3" :key="r" class="flex items-center gap-3">
                <Skeleton class="h-3.5 w-3.5 rounded-sm" />
                <Skeleton class="h-2.5" :style="{ width: (35 + ((s + r) % 4) * 12) + '%' }" />
                <Skeleton class="h-5 w-5 rounded-full ml-auto" />
              </div>
            </div>
          </div>
        </div>
        <div class="lg:col-span-4 flex flex-col gap-4">
          <div v-for="s in 2" :key="'skr' + s" class="bg-overlay rounded-lg border p-5">
            <Skeleton class="h-3 mb-4" :style="{ width: (90 + s * 20) + 'px' }" />
            <Skeleton class="h-2.5 mb-2.5" :style="{ width: (60 + s * 8) + '%' }" />
            <Skeleton class="h-2.5" :style="{ width: (40 + s * 12) + '%' }" />
          </div>
        </div>
      </div>

      <!-- ── Main Grid 8/4 ───────────────────────────────────────────── -->
      <div v-else class="grid grid-cols-1 lg:grid-cols-12 gap-4">

        <!-- ════════ PERSONAL ════════ -->
        <div v-if="mode === 'personal'" class="lg:col-span-8 flex flex-col gap-4">

          <!-- My Day -->
          <section class="bg-overlay rounded-lg border border-border shadow-sm overflow-hidden">
            <div class="flex items-center justify-between px-5 py-4 border-b border-separator">
              <div class="flex items-center gap-3">
                <h2 class="text-base font-semibold text-foreground">My Day</h2>
                <span class="text-sm text-muted">{{ todayFormatted }}</span>
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-5 divide-y md:divide-y-0 md:divide-x divide-separator">
              <div class="md:col-span-3 px-5 py-4">
                <div class="flex items-center gap-2 mb-3">
                  <span class="text-xs font-bold text-muted uppercase tracking-widest shrink-0">Today</span>
                  <div class="h-px flex-1 bg-surface-secondary"></div>
                </div>
                <div v-if="!myDay.today.length" class="flex flex-col items-center py-8 text-center gap-2">
                  <svg class="size-8 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                  <p class="text-sm text-muted">Nothing due today</p>
                </div>
                <div v-else class="space-y-0.5">
                  <div v-for="item in myDay.today" :key="item.id"
                    class="group flex items-center gap-3 py-2.5 px-2 rounded-md hover:bg-surface-secondary transition-colors cursor-pointer"
                    @click="openTask(item.id)">
                    <span class="shrink-0 size-2.5 rounded-full" :style="{ backgroundColor: item.projectColor }"></span>
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-medium text-foreground truncate leading-5">{{ item.title }}</p>
                      <p class="text-xs text-muted mt-0.5">{{ item.project }}<span v-if="item.estimatedHours"> · {{ item.estimatedHours }}h est.</span></p>
                    </div>
                  </div>
                </div>
              </div>
              <div class="md:col-span-2 px-5 py-4">
                <div class="flex items-center gap-2 mb-3">
                  <span class="text-xs font-bold text-muted uppercase tracking-widest shrink-0">Up next</span>
                  <div class="h-px flex-1 bg-surface-secondary"></div>
                  <span class="text-xs text-muted tabular-nums shrink-0">{{ myDay.upNext.length }}</span>
                </div>
                <div class="space-y-1">
                  <div v-for="item in myDay.upNext.slice(0, 5)" :key="item.id"
                    class="flex items-center gap-2.5 py-2 px-1.5 rounded-md hover:bg-surface-secondary transition-colors cursor-pointer"
                    @click="openTask(item.id)">
                    <span class="shrink-0 px-2 py-0.5 rounded-md text-xs font-semibold tabular-nums whitespace-nowrap min-w-[60px] text-center"
                      :class="item.dueLabel === 'Tomorrow' ? 'bg-warning-soft text-warning-soft-foreground' : 'bg-surface-secondary text-muted'">{{ item.dueLabel }}</span>
                    <p class="text-sm text-muted truncate">{{ item.title }}</p>
                  </div>
                </div>
                <router-link to="/workspace/my-tasks" class="mt-3 block text-xs text-accent hover:underline">See all upcoming →</router-link>
              </div>
            </div>
          </section>

          <!-- Inbox -->
          <section id="inbox" class="bg-overlay rounded-lg shadow-sm overflow-hidden">
            <div class="flex items-center justify-between px-5 py-4 border-b border-separator">
              <div class="flex items-center gap-2">
                <h2 class="text-base font-semibold text-foreground">Inbox</h2>
                <span v-if="unreadCount"
                  class="inline-flex items-center justify-center min-w-[1.125rem] h-[1.125rem] px-1 rounded-full bg-accent text-white text-xs font-bold tabular-nums">
                  {{ unreadCount }}
                </span>
              </div>
              <div class="flex items-center gap-3">
                <div class="flex gap-0.5">
                  <button v-for="t in inboxTabs" :key="t" type="button"
                    :class="['px-2.5 h-6 text-xs rounded-md transition-[background-color,color,transform] active:scale-[0.97]', inboxTab === t ? 'bg-surface-secondary text-foreground font-medium' : 'text-muted hover:text-foreground']"
                    @click="inboxTab = t">{{ t }}</button>
                </div>
                <button v-if="unreadCount" type="button" class="text-xs text-muted hover:text-foreground transition-colors" @click="markAllInboxRead">Mark all read</button>
              </div>
            </div>
            <div v-if="!filteredInbox.length" class="flex flex-col items-center gap-2 py-10">
              <svg class="size-8 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
              <p class="text-sm text-muted">You're all caught up</p>
            </div>
            <div v-else>
              <InboxRow v-for="item in filteredInbox.slice(0, showInboxCount)" :key="item.id" :item="item"
                @click="openInboxItem(item)" @menu="markInboxItemRead(item)" />
              <div v-if="filteredInbox.length > showInboxCount" class="px-5 py-2 border-t border-separator">
                <button type="button" class="text-xs text-accent hover:underline" @click="showInboxCount += 5">Show 5 more</button>
              </div>
              <div class="px-5 py-2.5 border-t border-separator">
                <router-link to="/workspace/notifications" class="text-xs text-accent hover:underline">View all →</router-link>
              </div>
            </div>
          </section>

          <!-- My Active Work -->
          <section id="active-work" class="bg-overlay rounded-lg border border-border shadow-sm overflow-hidden">
            <div class="flex items-center justify-between px-5 py-4 border-b border-separator">
              <h2 class="text-base font-semibold text-foreground">My Active Work</h2>
              <div class="flex gap-0.5">
                <button v-for="g in groupByOptions" :key="g.value" type="button"
                  :class="['px-2 h-6 text-xs rounded-md transition-[background-color,color,transform] active:scale-[0.97]', groupBy === g.value ? 'bg-surface-secondary text-foreground font-medium' : 'text-muted hover:text-muted']"
                  @click="groupBy = g.value">{{ g.label }}</button>
              </div>
            </div>
            <div v-if="!myIssues.length" class="flex flex-col items-center gap-1 py-10">
              <p class="text-sm text-muted">No active tasks.</p>
              <router-link to="/workspace/my-tasks" class="text-xs text-accent hover:underline">Pick something up →</router-link>
            </div>
            <div v-else>
              <div v-for="group in groupedWork" :key="group.label">
                <button type="button"
                  class="w-full flex items-center gap-2 px-5 py-2.5 bg-surface-secondary hover:bg-surface-hover transition-colors border-b border-separator"
                  @click="toggleGroup(group.label)">
                  <svg class="size-3 text-muted transition-transform duration-150 shrink-0"
                    :class="collapsedGroups.has(group.label) ? '' : 'rotate-90'"
                    fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
                  </svg>
                  <span class="size-2.5 rounded-full shrink-0" :style="{ backgroundColor: group.color }"></span>
                  <span class="text-sm font-semibold text-muted">{{ group.label }}</span>
                  <span class="text-xs font-medium text-muted tabular-nums bg-surface-secondary px-1.5 py-0.5 rounded-full leading-none">{{ group.tasks.length }}</span>
                </button>
                <div v-if="!collapsedGroups.has(group.label)" class="divide-y divide-separator">
                  <TaskRow v-for="task in group.tasks" :key="task.name" :task="task" />
                </div>
              </div>
            </div>
            <div class="px-5 py-2.5 border-t border-separator">
              <router-link to="/workspace/my-tasks" class="text-xs text-accent hover:underline">Open my tasks page →</router-link>
            </div>
          </section>

          <!-- Blocked / Waiting -->
          <section v-if="hasBlockedContent" id="blocked" class="bg-overlay rounded-lg border border-border shadow-sm overflow-hidden">
            <div class="px-5 py-4 border-b border-separator">
              <h2 class="text-base font-semibold text-foreground">Blocked / Waiting</h2>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-separator">
              <div class="px-5 py-4">
                <div class="flex items-center gap-2 mb-3.5">
                  <span class="text-xs font-bold text-muted uppercase tracking-widest shrink-0">Blocked</span>
                  <div class="h-px flex-1 bg-surface-secondary"></div>
                </div>
                <div v-if="!blockedTasks.length" class="text-xs text-muted text-center py-4">No blocked tasks</div>
                <div v-else class="space-y-3">
                  <div v-for="t in blockedTasks" :key="t.name" class="flex items-center gap-3 cursor-pointer" @click="openTask(t.name)">
                    <span class="shrink-0 size-2 rounded-full bg-danger mt-0.5"></span>
                    <p class="flex-1 text-sm font-medium text-muted truncate">{{ t.title }}</p>
                    <span class="shrink-0 text-xs font-semibold px-1.5 py-0.5 rounded bg-surface-secondary text-muted">{{ t.project }}</span>
                  </div>
                </div>
              </div>
              <div class="px-5 py-4">
                <div class="flex items-center gap-2 mb-3.5">
                  <span class="text-xs font-bold text-muted uppercase tracking-widest shrink-0">In Review</span>
                  <div class="h-px flex-1 bg-surface-secondary"></div>
                </div>
                <div v-if="!reviewTasks.length" class="text-xs text-muted text-center py-4">Nothing in review</div>
                <div v-else class="space-y-3">
                  <div v-for="t in reviewTasks" :key="t.name" class="flex items-center gap-3 cursor-pointer" @click="openTask(t.name)">
                    <span class="shrink-0 size-2 rounded-full bg-warning mt-0.5"></span>
                    <p class="flex-1 text-sm font-medium text-muted truncate">{{ t.title }}</p>
                    <span class="shrink-0 text-xs font-semibold px-1.5 py-0.5 rounded bg-surface-secondary text-muted">{{ t.project }}</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- Stale tasks -->
          <section v-if="staleTasks.length" id="stale" class="bg-overlay rounded-lg border border-border shadow-sm overflow-hidden">
            <div class="flex items-center gap-2 px-5 py-4 border-b border-separator">
              <h2 class="text-base font-semibold text-foreground">Stale</h2>
              <span class="text-sm text-muted">— not updated in 7+ days</span>
            </div>
            <div class="divide-y divide-separator">
              <div v-for="task in staleTasks.slice(0, 5)" :key="task.name"
                class="group flex items-center gap-3 px-5 h-11 hover:bg-surface-secondary transition-colors cursor-pointer"
                @click="openTask(task.name)">
                <p class="flex-1 text-sm font-medium text-muted truncate">{{ task.title }}</p>
                <span class="shrink-0 text-xs font-medium text-muted tabular-nums">{{ staleDays(task) }}d stale</span>
                <span class="shrink-0 text-xs text-muted">{{ task.project }}</span>
              </div>
            </div>
          </section>

        </div>

        <!-- ════════ WORKSPACE ════════ -->
        <div v-else class="lg:col-span-8 flex flex-col gap-4">

          <!-- Project Health Grid -->
          <section>
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-base font-semibold text-foreground">Project Health</h2>
              <router-link to="/workspace/all" class="text-sm text-accent hover:underline">View all →</router-link>
            </div>
            <div v-if="wsLoading" class="flex justify-center py-10">
              <div class="size-5 border-2 border-border border-t-blue-600 rounded-full animate-spin"></div>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div v-for="proj in projectHealth" :key="proj.key"
                class="group relative bg-overlay rounded-lg border border-border shadow-sm p-4 cursor-pointer transition-shadow hover:shadow-md flex flex-col gap-3 overflow-hidden"
                               @click="$router.push(`/workspace/${proj.key}`)">
                <div class="flex items-start justify-between gap-2">
                  <div class="flex items-center gap-2.5 min-w-0">
                    <div class="shrink-0 size-9 rounded-[10px] overflow-hidden">
                      <img :src="projectTheme(proj).icon" :alt="projectTheme(proj).label" class="w-full h-full object-cover" />
                    </div>
                    <div class="min-w-0">
                      <p class="text-sm font-semibold text-foreground leading-snug line-clamp-2" :title="proj.name">{{ proj.name }}</p>
                      <p class="text-xs text-muted mt-0.5">{{ proj.key }}</p>
                    </div>
                  </div>
                  <span :class="['shrink-0 inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold rounded-md border', healthPillClass(proj.health)]">
                    <span class="size-1.5 rounded-full" :class="healthDotClass(proj.health)"></span>
                    {{ healthLabel(proj.health) }}
                  </span>
                </div>
                <div>
                  <InlineProgress :value="proj.completion" size="sm" :auto-color="false" color="blue" :show-label="false" class="mb-2" />
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-1.5 text-xs text-muted">
                      <span class="tabular-nums font-semibold text-muted">{{ proj.completion }}%</span>
                      <span class="text-muted">·</span>
                      <span class="tabular-nums">{{ proj.done_tasks }}/{{ proj.total_tasks }} done</span>
                      <span v-if="proj.days_left !== null && proj.days_left !== undefined" class="text-muted">·</span>
                      <span v-if="proj.days_left !== null && proj.days_left !== undefined"
                        class="tabular-nums font-medium"
                        :class="proj.days_left <= 0 ? 'text-danger' : proj.days_left <= 7 ? 'text-warning-soft-foreground' : 'text-muted'">
                        {{ proj.days_left <= 0 ? 'Overdue' : proj.days_left + 'd left' }}
                      </span>
                    </div>
                    <AvatarStack :avatars="avatarProps(proj.members)" :max="3" size="xs" />
                  </div>
                </div>
                <div class="absolute inset-x-0 bottom-0 flex items-center justify-center h-8 text-xs font-medium text-accent border-t border-transparent opacity-0 group-hover:opacity-100 group-hover:border-separator group-hover:bg-surface-secondary transition-[opacity,background-color,border-color]">Open board →</div>
              </div>
            </div>
          </section>

          <!-- Profitability table -->
          <section class="bg-overlay rounded-lg border border-border shadow-sm overflow-hidden">
            <div class="flex items-center justify-between px-5 py-4 border-b border-separator">
              <h2 class="text-base font-semibold text-foreground">Profitability</h2>
              <div class="flex gap-0.5">
                <button v-for="f in profitFilters" :key="f" type="button"
                  :class="['px-2 h-6 text-xs rounded-md transition-[background-color,color,transform] active:scale-[0.97]', profitFilter === f ? 'bg-surface-secondary text-foreground font-medium' : 'text-muted hover:text-muted']"
                  @click="profitFilter = f">{{ f }}</button>
              </div>
            </div>
            <div v-if="wsLoading" class="flex justify-center py-8">
              <div class="size-4 border-2 border-border border-t-blue-600 rounded-full animate-spin"></div>
            </div>
            <div v-else-if="!filteredProfitability.length" class="flex items-center justify-center py-8 text-sm text-muted">
              No billable projects
            </div>
            <div v-else class="overflow-x-auto" style="scrollbar-width:thin">
              <table class="w-full">
                <thead class="bg-[var(--surface-secondary)] border-b border-separator">
                  <tr class="text-xs">
                    <th class="px-5 py-3 text-left font-semibold text-muted uppercase tracking-wider">Project</th>
                    <th class="px-3 py-3 text-right font-semibold text-muted uppercase tracking-wider">Type</th>
                    <th class="px-3 py-3 text-right font-semibold text-muted uppercase tracking-wider">Budget</th>
                    <th class="px-3 py-3 text-right font-semibold text-muted uppercase tracking-wider">Billed</th>
                    <th class="px-3 py-3 text-right font-semibold text-muted uppercase tracking-wider">Unbilled</th>
                    <th class="px-3 py-3 text-right font-semibold text-muted uppercase tracking-wider">Remaining</th>
                    <th class="px-3 py-3 text-left font-semibold text-muted uppercase tracking-wider">Burn</th>
                    <th class="px-3 py-3 text-right font-semibold text-muted uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-separator">
                  <tr v-for="row in filteredProfitability" :key="row.key"
                    class="hover:bg-surface-secondary transition-colors cursor-pointer"
                    @click="$router.push(`/workspace/${row.key}/settings/billing`)">
                    <td class="px-5 py-3.5">
                      <div class="flex items-center gap-2">
                        <span class="size-2 rounded-full shrink-0" :style="{ backgroundColor: row.color }"></span>
                        <span class="text-sm font-semibold text-foreground">{{ row.project }}</span>
                      </div>
                    </td>
                    <td class="px-3 py-3.5 text-right">
                      <span class="text-xs font-medium text-muted uppercase">{{ row.project_type }}</span>
                    </td>
                    <td class="px-3 py-3.5 text-right text-sm text-muted tabular-nums">{{ row.budget ? formatCurrency(row.budget, row.currency) : '—' }}</td>
                    <td class="px-3 py-3.5 text-right text-sm text-muted tabular-nums">{{ formatCurrency(row.billed, row.currency) }}</td>
                    <td class="px-3 py-3.5 text-right text-sm text-muted tabular-nums">{{ formatCurrency(row.unbilled, row.currency) }}</td>
                    <td class="px-3 py-3.5 text-right text-sm tabular-nums font-semibold"
                      :class="row.remaining !== null && row.remaining < 0 ? 'text-danger' : 'text-muted'">
                      {{ row.remaining !== null ? formatCurrency(row.remaining, row.currency) : '—' }}
                    </td>
                    <td class="px-3 py-3.5">
                      <div v-if="row.burn_pct !== null" class="flex items-center gap-2">
                        <div class="w-16 h-1.5 rounded-full bg-surface-secondary overflow-hidden">
                          <div class="h-full rounded-full transition-colors duration-500" :class="row.burn_pct > 100 ? 'bg-danger' : row.burn_pct > 85 ? 'bg-warning' : 'bg-accent'" :style="{ width: Math.min(row.burn_pct, 100) + '%' }"></div>
                        </div>
                        <span class="text-xs tabular-nums font-semibold" :class="row.burn_pct > 100 ? 'text-danger' : 'text-muted'">{{ row.burn_pct }}%</span>
                      </div>
                      <span v-else class="text-xs text-muted">T&M</span>
                    </td>
                    <td class="px-3 py-3.5 text-right">
                      <span :class="['inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold', profitStatusClass(row.status)]">{{ row.status }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- Invoice-Ready -->
          <section v-if="invoiceReady.length" class="bg-overlay rounded-lg border border-border shadow-sm overflow-hidden">
            <div class="flex items-center justify-between px-5 py-4 border-b border-separator">
              <div class="flex items-center gap-2">
                <h2 class="text-base font-semibold text-foreground">Ready to Invoice</h2>
                <span class="text-sm font-semibold text-success-soft-foreground tabular-nums">{{ formatCurrency(invoiceTotal) }}</span>
                <span class="text-xs text-muted">from {{ invoiceReady.length }} client{{ invoiceReady.length !== 1 ? 's' : '' }}</span>
              </div>
            </div>
            <div class="divide-y divide-separator">
              <div v-for="group in invoiceReady" :key="group.client" class="px-5 py-5">
                <div class="flex items-center justify-between mb-3">
                  <p class="text-sm font-semibold text-foreground">{{ group.client }}</p>
                  <span class="text-sm font-semibold text-foreground tabular-nums">{{ formatCurrency(group.total) }}</span>
                </div>
                <div class="space-y-2.5">
                  <div v-for="item in group.items" :key="item.key" class="flex items-center gap-3">
                    <p class="flex-1 text-sm text-muted truncate">{{ item.project }}</p>
                    <span v-if="item.hours" class="text-xs font-medium text-muted tabular-nums">{{ item.hours }}h</span>
                    <span class="text-sm font-semibold text-muted tabular-nums">{{ formatCurrency(item.amount) }}</span>
                    <router-link :to="`/workspace/${item.key}/money`"
                      class="px-2.5 h-6 inline-flex items-center text-xs font-semibold text-accent-soft-foreground bg-accent-soft hover:bg-accent-soft-hover rounded-md transition-colors active:scale-[0.97] whitespace-nowrap">
                      {{ item.action }}
                    </router-link>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- Activity stream -->
          <section class="bg-overlay rounded-lg border border-border shadow-sm overflow-hidden">
            <div class="flex items-center justify-between px-5 py-4 border-b border-separator">
              <h2 class="text-base font-semibold text-foreground">Activity</h2>
              <div class="flex gap-0.5">
                <button v-for="t in activityTabs" :key="t" type="button"
                  :class="['px-2.5 h-6 text-xs rounded-md transition-[background-color,color,transform] active:scale-[0.97]', activityTab === t ? 'bg-surface-secondary text-foreground font-medium' : 'text-muted hover:text-muted']"
                  @click="activityTab = t">{{ t }}</button>
              </div>
            </div>
            <div v-if="wsLoading" class="flex justify-center py-8">
              <div class="size-4 border-2 border-border border-t-blue-600 rounded-full animate-spin"></div>
            </div>
            <div v-else-if="!filteredActivity.length" class="flex items-center justify-center py-8 text-sm text-muted">
              No recent activity
            </div>
            <div v-else class="divide-y divide-separator">
              <div v-for="event in filteredActivity.slice(0, 10)" :key="event.id"
                class="flex items-center gap-3 px-5 py-3 hover:bg-surface-secondary transition-colors cursor-pointer"
                @click="event.task && openTask(event.task)">
                <div class="size-8 rounded-full shrink-0 flex items-center justify-center text-white text-xs font-bold" :style="{ backgroundColor: event.actor_color }">{{ event.actor_initial }}</div>
                <p class="flex-1 text-sm text-muted truncate">
                  <span class="font-semibold text-foreground">{{ event.actor }}</span>
                  {{ ' ' + event.text }}
                  <span v-if="event.project" class="text-muted text-xs"> · {{ event.project }}</span>
                </p>
                <span class="shrink-0 text-xs font-medium text-muted tabular-nums">{{ event.time }}</span>
              </div>
            </div>
            <div v-if="activityStream.length > 10" class="px-5 py-3 border-t border-separator">
              <button type="button" class="text-sm text-accent hover:underline">Load more</button>
            </div>
          </section>

        </div>

        <!-- ════════ RIGHT RAIL ════════ -->
        <div class="lg:col-span-4 flex flex-col gap-4 lg:sticky lg:top-6 lg:self-start">

          <!-- Personal right rail -->
          <template v-if="mode === 'personal'">

            <!-- Last 14 days stats -->
            <div class="bg-overlay rounded-lg border border-border shadow-sm p-5">
              <h2 class="text-base font-semibold text-foreground mb-4">Last 14 days</h2>
              <div class="space-y-5">
                <div>
                  <div class="flex items-center justify-between mb-2">
                    <p class="text-sm font-medium text-muted">Tasks completed</p>
                    <span class="text-base font-semibold text-foreground tabular-nums">{{ personalStats.total_completed || 0 }}</span>
                  </div>
                  <Sparkline :data="personalStats.sparkline || Array(14).fill(0)" :width="260" :height="32" />
                </div>
                <div v-if="personalStats.total_hours > 0">
                  <div class="flex items-center justify-between mb-1">
                    <p class="text-sm font-medium text-muted">Hours logged</p>
                    <span class="text-base font-semibold text-foreground tabular-nums">{{ personalStats.total_hours }}h</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Upcoming deadlines -->
            <div class="bg-overlay rounded-lg border border-border shadow-sm p-5">
              <h2 class="text-base font-semibold text-foreground mb-4">Upcoming Deadlines</h2>
              <div v-if="!upcomingDeadlines.length" class="text-sm text-muted text-center py-4">No upcoming deadlines</div>
              <div v-else class="space-y-0.5">
                <div v-for="item in upcomingDeadlines.slice(0, 8)" :key="item.name"
                  class="flex items-center gap-3 py-2 cursor-pointer hover:bg-surface-secondary rounded-md px-2 -mx-2"
                  @click="openTask(item.name)">
                  <span class="shrink-0 text-xs font-semibold text-muted tabular-nums w-14 text-right">{{ dueLabelShort(item.due_date) }}</span>
                  <div class="w-px h-3.5 bg-border shrink-0"></div>
                  <p class="flex-1 text-sm text-muted truncate">{{ item.title }}</p>
                </div>
              </div>
            </div>

            <!-- Recently Active (Watching) -->
            <div class="bg-overlay rounded-lg border border-border shadow-sm p-5">
              <h2 class="text-base font-semibold text-foreground mb-3">Recently Active</h2>
              <div v-if="!recentlyActive.length" class="text-sm text-muted text-center py-4">No recent activity</div>
              <div v-else class="space-y-0.5">
                <div v-for="item in recentlyActive" :key="item.name"
                  class="flex items-center gap-2.5 cursor-pointer hover:bg-surface-secondary px-2 py-2.5 rounded-md -mx-2 transition-colors"
                  @click="openTask(item.name)">
                  <span class="size-2.5 rounded-full shrink-0" :style="{ backgroundColor: item.color }"></span>
                  <p class="flex-1 text-sm font-medium text-muted truncate">{{ item.title }}</p>
                  <span class="shrink-0 text-xs text-muted tabular-nums">{{ item.last_activity }}</span>
                </div>
              </div>
            </div>

          </template>

          <!-- Workspace right rail -->
          <template v-else>

            <!-- Risk Register -->
            <div class="bg-overlay rounded-lg border border-border shadow-sm p-5">
              <div class="flex items-center justify-between mb-4">
                <h2 class="text-base font-semibold text-foreground">Risk Register</h2>
                <button type="button" class="text-xs text-accent hover:underline" @click="showAddRisk = true">+ Flag risk</button>
              </div>
              <!-- Add risk form -->
              <div v-if="showAddRisk" class="mb-4 flex flex-col gap-2">
                <input v-model="newRisk.title" type="text" placeholder="Risk description…"
                  class="w-full h-8 px-3 text-sm bg-background border border-border rounded-md outline-none transition-colors focus:border-accent focus:bg-overlay focus:shadow-focus" />
                <div class="flex gap-2">
                  <select v-model="newRisk.project" class="flex-1 h-8 px-2 text-xs bg-background border border-border rounded-md outline-none transition-colors focus:border-accent focus:bg-overlay focus:shadow-focus">
                    <option value="">Project…</option>
                    <option v-for="p in projects" :key="p.name" :value="p.name">{{ p.project_name }}</option>
                  </select>
                  <select v-model="newRisk.severity" class="w-24 h-8 px-2 text-xs bg-background border border-border rounded-md outline-none transition-colors focus:border-accent focus:bg-overlay focus:shadow-focus">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
                <div class="flex gap-2">
                  <button type="button" class="flex-1 h-7 text-xs font-medium bg-accent text-white rounded-md shadow-sm hover:bg-[var(--accent-hover)] active:scale-[0.97] transition-colors" @click="submitRisk">Save</button>
                  <button type="button" class="h-7 px-3 text-xs font-medium text-muted border border-border hover:bg-surface-secondary rounded-md active:scale-[0.97] transition-[background-color,transform]" @click="showAddRisk = false; newRisk = { title: '', project: '', severity: 'medium' }">Cancel</button>
                </div>
              </div>
              <div v-if="wsLoading" class="flex justify-center py-4">
                <div class="size-4 border-2 border-border border-t-blue-600 rounded-full animate-spin"></div>
              </div>
              <div v-else-if="!risks.length" class="flex flex-col items-center gap-1 py-6 text-center">
                <p class="text-xs text-muted">No active risks</p>
              </div>
              <div v-else class="space-y-2">
                <div v-for="risk in risks" :key="risk.name"
                  class="flex items-start gap-2.5 px-2 py-2.5 rounded-md hover:bg-surface-secondary transition-colors cursor-pointer -mx-2">
                  <span class="mt-1 shrink-0 size-2 rounded-full" :class="riskDotClass(risk.severity)"></span>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-foreground leading-5">{{ risk.title }}</p>
                    <div class="flex items-center gap-1.5 mt-1">
                      <div v-if="risk.owner" class="size-5 rounded-full flex items-center justify-center text-white text-micro font-bold shrink-0" :style="{ backgroundColor: risk.owner_color }">{{ risk.owner_initial }}</div>
                      <span class="text-xs font-medium text-muted capitalize">{{ risk.severity }}</span>
                      <span class="text-xs text-muted">· {{ risk.project_name }}</span>
                    </div>
                  </div>
                  <button type="button" class="shrink-0 text-xs font-medium text-muted hover:text-danger transition-colors" @click.stop="resolveRisk(risk.name)">✓</button>
                </div>
              </div>
            </div>

            <!-- Milestones -->
            <div class="bg-overlay rounded-lg border border-border shadow-sm p-5">
              <div class="flex items-center justify-between mb-4">
                <h2 class="text-base font-semibold text-foreground">Upcoming Milestones</h2>
                <button type="button" class="text-xs text-accent hover:underline" @click="showAddMilestone = true">+ Add</button>
              </div>
              <!-- Add milestone form -->
              <div v-if="showAddMilestone" class="mb-4 flex flex-col gap-2">
                <input v-model="newMilestone.title" type="text" placeholder="Milestone title…"
                  class="w-full h-8 px-3 text-sm bg-background border border-border rounded-md outline-none transition-colors focus:border-accent focus:bg-overlay focus:shadow-focus" />
                <div class="flex gap-2">
                  <select v-model="newMilestone.project" class="flex-1 h-8 px-2 text-xs bg-background border border-border rounded-md outline-none transition-colors focus:border-accent focus:bg-overlay focus:shadow-focus">
                    <option value="">Project…</option>
                    <option v-for="p in projects" :key="p.name" :value="p.name">{{ p.project_name }}</option>
                  </select>
                  <input v-model="newMilestone.due_date" type="date"
                    class="w-32 h-8 px-2 text-xs bg-background border border-border rounded-md outline-none transition-colors focus:border-accent focus:bg-overlay focus:shadow-focus" />
                </div>
                <div class="flex gap-2">
                  <button type="button" class="flex-1 h-7 text-xs font-medium bg-accent text-white rounded-md shadow-sm hover:bg-[var(--accent-hover)] active:scale-[0.97] transition-colors" @click="submitMilestone">Save</button>
                  <button type="button" class="h-7 px-3 text-xs font-medium text-muted border border-border hover:bg-surface-secondary rounded-md active:scale-[0.97] transition-[background-color,transform]" @click="showAddMilestone = false; newMilestone = { title: '', project: '', due_date: '' }">Cancel</button>
                </div>
              </div>
              <div v-if="wsLoading" class="flex justify-center py-4">
                <div class="size-4 border-2 border-border border-t-blue-600 rounded-full animate-spin"></div>
              </div>
              <div v-else-if="!milestones.length" class="text-xs text-muted text-center py-3">No upcoming milestones</div>
              <div v-else class="space-y-4">
                <div v-for="m in milestones" :key="m.name" class="flex items-start gap-3">
                  <span class="shrink-0 text-xs font-semibold text-muted tabular-nums w-12 text-right pt-0.5">{{ m.date_label }}</span>
                  <div class="w-px h-4 bg-border shrink-0 mt-0.5"></div>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-foreground truncate">{{ m.title }}</p>
                    <div class="flex items-center gap-1.5 mt-0.5">
                      <span class="size-1.5 rounded-full" :style="{ backgroundColor: m.project_color }"></span>
                      <span class="text-xs text-muted">{{ m.project_name }} · {{ m.tasks_left }} tasks left</span>
                    </div>
                  </div>
                  <button type="button" class="shrink-0 text-xs text-muted hover:text-success transition-colors" @click.stop="completeMilestone(m.name)">✓</button>
                </div>
              </div>
            </div>

            <!-- Stale Projects -->
            <div class="bg-overlay rounded-lg border border-border shadow-sm p-5">
              <h2 class="text-base font-semibold text-foreground mb-3">Stale Projects</h2>
              <div v-if="wsLoading" class="flex justify-center py-4">
                <div class="size-4 border-2 border-border border-t-blue-600 rounded-full animate-spin"></div>
              </div>
              <div v-else-if="!staleProjects.length" class="text-xs text-muted text-center py-3">All projects active</div>
              <div v-else class="space-y-2">
                <div v-for="p in staleProjects" :key="p.key"
                  class="flex items-center gap-2.5 cursor-pointer hover:bg-surface-secondary px-2 py-2.5 rounded-md -mx-2 transition-colors"
                  @click="$router.push(`/workspace/${p.key}`)">
                  <span class="size-2.5 rounded-full shrink-0" :style="{ backgroundColor: p.color }"></span>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-foreground truncate">{{ p.name }}</p>
                    <p class="text-xs text-muted">Last activity {{ p.last_activity }}</p>
                  </div>
                </div>
              </div>
            </div>

            <!-- Recently Delivered -->
            <div v-if="recentlyDelivered.length" class="bg-overlay rounded-lg border border-border shadow-sm p-5">
              <h2 class="text-base font-semibold text-foreground mb-3">Recently Delivered</h2>
              <div class="space-y-2.5">
                <div v-for="item in recentlyDelivered.slice(0, 6)" :key="item.name"
                  class="flex items-center gap-2.5 cursor-pointer hover:bg-surface-secondary rounded-md px-2 py-1.5 -mx-2"
                  @click="openTask(item.name)">
                  <svg class="size-4 text-success shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                  <p class="flex-1 text-sm text-muted truncate">{{ item.title }}</p>
                  <span class="shrink-0 text-xs font-medium text-muted tabular-nums">{{ item.date }}</span>
                </div>
              </div>
            </div>

          </template>
        </div>

      </div>
    </div>

    <NudgeCard
      :model-value="showKbdNudge"
      :icon="Keyboard"
      title="Keyboard shortcuts"
      description="Press ? anywhere to see the full list — C creates a task, A assigns it to you."
      @dismiss="dismissKbdNudge"
    >
      <template #actions>
        <button type="button" class="text-xs font-medium text-accent hover:underline" @click="openShortcuts">Show me</button>
      </template>
    </NudgeCard>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  getDashboard, getMyTasks, getNotifications,
  markNotificationRead, markAllNotificationsRead,
  getWorkspaceSummary, createMilestone, updateMilestone,
  createRisk, updateRisk, getViewPrefs,
} from '@/utils/api'
import { useProjectStore } from '@/stores/project'
import { useEntitlementsStore } from '@/stores/entitlements'
import KpiTile        from '@/ui/KpiTile.vue'
import Skeleton       from '@/ui/Skeleton.vue'
import Sparkline      from '@/ui/Sparkline.vue'
import InlineProgress from '@/ui/InlineProgress.vue'
import AvatarStack    from '@/ui/AvatarStack.vue'
import TaskRow        from '@/ui/TaskRow.vue'
import InboxRow       from '@/ui/InboxRow.vue'
import NudgeCard      from '@/ui/NudgeCard.vue'
import { Keyboard } from 'lucide-vue-next'
import { resolveProjectTheme } from '@/constants/project-themes'

const store  = useProjectStore()
const router = useRouter()
const entitlements = useEntitlementsStore()

// First-run discovery nudge — see ui/NudgeCard.vue. Dismissal persists
// server-side (batch_projects.entitlements.dismiss_nudge) so it never
// reappears once seen, on any device.
const KBD_NUDGE_ID = 'kbd-shortcuts'
const showKbdNudge = computed(() => entitlements.loaded && !entitlements.isNudgeDismissed(KBD_NUDGE_ID))
function dismissKbdNudge() { entitlements.dismissNudge(KBD_NUDGE_ID) }
function openShortcuts() {
  // Reuses the existing global "?" listener (App.vue/useGlobalShortcuts)
  // rather than adding a second cross-component way to open the same overlay.
  window.dispatchEvent(new KeyboardEvent('keydown', { key: '?' }))
  dismissKbdNudge()
}

// ── State ──────────────────────────────────────────────────────────────────
const loading   = ref(true)
const wsLoading = ref(false)
const projects  = ref([])
const myIssues  = ref([])
const overdue   = ref([])

// Personal tab data
const staleTasks       = ref([])
const upcomingDeadlines = ref([])
const personalStats    = ref({ sparkline: Array(14).fill(0), total_completed: 0, total_hours: 0 })
const recentlyActive   = ref([])
const inbox            = ref([])

// Workspace tab data
const projectHealth    = ref([])
const profitability    = ref([])
const invoiceReady     = ref([])
const activityStream   = ref([])
const staleProjects    = ref([])
const recentlyDelivered = ref([])
const milestones       = ref([])
const risks            = ref([])

// Forms
const showAddRisk      = ref(false)
const newRisk          = ref({ title: '', project: '', severity: 'medium' })
const showAddMilestone = ref(false)
const newMilestone     = ref({ title: '', project: '', due_date: '' })

// ── Notification helpers ────────────────────────────────────────────────────
// Real backend values (board.py get_notifications / events.py), Title Case
// with spaces — this widget previously keyed off invented lowercase/
// underscore strings ("status_change") that never matched, so every action
// silently fell through to "updated" and every item landed in the same tab.
function _notifAction(type) {
  return {
    'Comment': 'commented on', 'Assignment': 'assigned you to',
    'Unassigned': 'unassigned you from', 'Mention': 'mentioned you in',
    'Status Change': 'changed status of', 'Update': 'updated',
    'Due Soon': 'flagged as due soon', 'Overdue': 'flagged as overdue',
    'Rule': 'ran an automation on', 'Summary': 'sent you a summary',
  }[type] || 'updated'
}
function _notifType(type) {
  if (type === 'Mention') return 'mention'
  if (type === 'Assignment' || type === 'Unassigned') return 'assigned'
  return 'review'
}
function _stripHtml(text) {
  if (!text) return ''
  return text.replace(/<[^>]*>/g, '').trim()
}
function _timeAgo(dateStr) {
  if (!dateStr) return ''
  const mins = Math.floor((Date.now() - new Date(dateStr).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return mins + 'm ago'
  const h = Math.floor(mins / 60)
  if (h < 24) return h + 'h ago'
  return Math.floor(h / 24) + 'd ago'
}

onMounted(async () => {
  // "set as home": a per-user, workspace-level view preference
  // (project omitted — see get_view_prefs' own doc comment for why that's
  // a real, deliberate case, not a bug). Stock Dashboard stays both the
  // default AND the fallback: any failure here just proceeds to load the
  // normal dashboard below, same as if no preference were ever set.
  try {
    const homePref = await getViewPrefs(null, 'home_dashboard')
    if (homePref?.dashboard_id) {
      await router.replace(`/workspace/reports/${homePref.dashboard_id}`)
      return
    }
  } catch { /* fall through to the stock dashboard */ }

  // 1. Core dashboard data
  try {
    const data = await getDashboard()
    projects.value         = data.projects || []
    myIssues.value         = data.my_issues || []
    overdue.value          = data.overdue || []
    staleTasks.value       = data.stale_tasks || []
    upcomingDeadlines.value = data.upcoming_deadlines || []
    personalStats.value    = data.personal_stats || personalStats.value
    recentlyActive.value   = data.recently_active || []
    store.projects         = projects.value
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }

  // 2. My Day — real tasks with due dates
  try {
    const raw = await getMyTasks({ statusFilter: 'open', sortBy: 'due_date', sortOrder: 'asc', limit: 30 })
    const flat = Array.isArray(raw) ? raw : Object.values(raw || {}).flat()
    const todayStr = new Date().toISOString().slice(0, 10)
    myDay.value.today = flat
      .filter(t => t.due_date === todayStr)
      .slice(0, 6)
      .map(t => ({
        id: t.name,
        title: t.title || t.name,
        project: t.project || '',
        projectColor: getAvatarColor(t.project || ''),
        estimatedHours: t.estimated_hours || null,
      }))
    myDay.value.upNext = flat
      .filter(t => t.due_date && t.due_date > todayStr)
      .slice(0, 8)
      .map(t => ({
        id: t.name,
        title: t.title || t.name,
        dueLabel: dueLabelShort(t.due_date),
      }))
  } catch {}

  // 3. Inbox — real notifications. get_notifications returns
  // {notifications, unread_count, total}, never a bare array — this
  // previously did Array.isArray(res) (always false) so inbox.value never
  // populated at all, regardless of how many unread notifications existed.
  try {
    const res = await getNotifications(15, 0)
    const notifs = res?.notifications || []
    inbox.value = notifs.map((n, i) => ({
      id: n.name || i,
      actor: n.actor_name || n.actor || 'System',
      actorInitial: (n.actor_name || n.actor || 'SY').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2),
      actorColor: getAvatarColor(n.actor || String(i)),
      action: _notifAction(n.notification_type),
      context: n.task_title || _stripHtml(n.message) || '',
      type: _notifType(n.notification_type),
      time: _timeAgo(n.creation),
      unread: !n.is_read,
      task: n.task,
      project: n.project,
    }))
  } catch {}

  // 4. Workspace summary (lazy — only if workspace mode or after personal loads)
  loadWorkspaceSummary()
})

async function loadWorkspaceSummary() {
  wsLoading.value = true
  try {
    const ws = await getWorkspaceSummary()
    projectHealth.value    = ws.project_health || []
    profitability.value    = ws.profitability || []
    invoiceReady.value     = ws.invoice_ready || []
    activityStream.value   = ws.activity_stream || []
    staleProjects.value    = ws.stale_projects || []
    recentlyDelivered.value = ws.recently_delivered || []
    milestones.value       = ws.milestones || []
    risks.value            = ws.risks || []
  } catch (e) {
    console.error(e)
  } finally {
    wsLoading.value = false
  }
}

// ── Mode ───────────────────────────────────────────────────────────────────
const _savedMode = localStorage.getItem('bp-dashboard-mode')
const _isOwner   = (window?.frappe?.boot?.user?.roles || []).some(
  r => ['System Manager', 'Administrator'].includes(r)
)
const mode  = ref(_savedMode || (_isOwner ? 'workspace' : 'personal'))
watch(mode, v => localStorage.setItem('bp-dashboard-mode', v))
const modes = [{ value: 'personal', label: 'Personal' }, { value: 'workspace', label: 'Workspace' }]

// ── Greeting ───────────────────────────────────────────────────────────────
const now   = new Date()
const hour  = now.getHours()
const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
const todayFormatted = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

const firstName = computed(() => {
  const full = window?.frappe?.session?.user_fullname || ''
  return full.split(' ')[0] || store.currentUser?.first_name || 'there'
})

function scrollTo(anchor) {
  if (!anchor) return
  document.getElementById(anchor)?.scrollIntoView({ behavior: 'smooth' })
}

const smartContext = computed(() => {
  const segs = []
  const todayCount = myDay.value.today.length
  if (todayCount) segs.push({ text: `${todayCount} task${todayCount !== 1 ? 's' : ''} due today`, anchor: 'active-work' })
  const unread = inbox.value.filter(i => i.unread).length
  if (unread) segs.push({ text: `${unread} mention${unread !== 1 ? 's' : ''} awaiting reply`, anchor: 'inbox' })
  const atRisk = projectHealth.value.filter(p => p.health === 'at_risk').length
  if (atRisk) segs.push({ text: `${atRisk} project${atRisk !== 1 ? 's' : ''} at risk`, anchor: 'blocked' })
  if (!segs.length) segs.push({ text: 'All clear — nothing urgent today', anchor: '' })
  return segs
})

// ── KPI tiles ──────────────────────────────────────────────────────────────
const totalOpen = computed(() => projects.value.reduce((s, p) => s + (p.open_count || 0), 0))
const totalDone = computed(() => projects.value.reduce((s, p) => s + ((p.total_count || 0) - (p.open_count || 0)), 0))

const personalKpis = computed(() => [
  { label: 'My Open Tasks',   value: myIssues.value.length, subline: `${overdue.value.length} overdue` },
  { label: 'Due Today',       value: myDay.value.today.length, subline: overdue.value.length ? `${overdue.value.length} overdue` : 'On schedule' },
  { label: 'In Review',       value: myIssues.value.filter(i => (i.status || '').toLowerCase().includes('review')).length, subline: 'Waiting for review' },
  { label: 'Completed (14d)', value: personalStats.value.total_completed, subline: 'Last 14 days' },
])

const workspaceKpis = computed(() => [
  { label: 'Active Projects', value: projects.value.length, subline: `${projectHealth.value.filter(p => p.health === 'at_risk').length} at risk · ${projectHealth.value.filter(p => p.health === 'blocked').length} blocked` },
  { label: 'Open Tasks',      value: totalOpen.value, subline: `${overdue.value.length} overdue` },
  { label: 'Invoice Ready',   value: invoiceReady.value.length ? `${invoiceReady.value.length} clients` : '—', subline: invoiceTotal.value > 0 ? formatCurrency(invoiceTotal.value) : 'No pending invoices' },
  { label: 'Risks',           value: risks.value.length, subline: risks.value.filter(r => r.severity === 'critical' || r.severity === 'high').length + ' high priority' },
])

const activeKpis = computed(() => mode.value === 'personal' ? personalKpis.value : workspaceKpis.value)

// ── My Day ─────────────────────────────────────────────────────────────────
const myDay = ref({ today: [], upNext: [] })

// ── Derived: blocked / review ──────────────────────────────────────────────
const blockedTasks = computed(() =>
  myIssues.value.filter(i => (i.status || '').toLowerCase().includes('blocked') || (i.status || '').toLowerCase().includes('block'))
)
const reviewTasks = computed(() =>
  myIssues.value.filter(i => (i.status || '').toLowerCase().includes('review') || (i.status || '').toLowerCase().includes('testing'))
)
const hasBlockedContent = computed(() => blockedTasks.value.length > 0 || reviewTasks.value.length > 0)

// ── Inbox ──────────────────────────────────────────────────────────────────
const inboxTabs      = ['All', 'Mentions', 'Assigned', 'Reviewed']
const inboxTab       = ref('All')
const showInboxCount = ref(5)
const unreadCount    = computed(() => inbox.value.filter(i => i.unread).length)
const filteredInbox  = computed(() => {
  if (inboxTab.value === 'All') return inbox.value
  const map = { Mentions: 'mention', Assigned: 'assigned', Reviewed: 'review' }
  return inbox.value.filter(i => i.type === map[inboxTab.value])
})

async function openInboxItem(item) {
  if (item.unread) {
    try { await markNotificationRead(item.id); item.unread = false } catch {}
  }
  const project = item.project ? store.projects.find(p => p.name === item.project) : null
  if (!project) return
  if (item.task) {
    if (!router.currentRoute.value.path.includes(`/workspace/${project.key}`)) {
      await router.push(`/workspace/${project.key}/board`)
    }
    setTimeout(() => store.openTaskDetail(item.task), 80)
  } else {
    router.push(`/workspace/${project.key}/board`)
  }
}
async function markInboxItemRead(item) {
  if (!item.unread) return
  try { await markNotificationRead(item.id); item.unread = false } catch {}
}
async function markAllInboxRead() {
  try {
    await markAllNotificationsRead()
    inbox.value.forEach(i => { i.unread = false })
  } catch {}
}

// ── Active work grouping ───────────────────────────────────────────────────
const groupByOptions = [
  { value: 'project',  label: 'Project' },
  { value: 'status',   label: 'Status' },
  { value: 'priority', label: 'Priority' },
]
const groupBy         = ref('project')
const collapsedGroups = ref(new Set())

function toggleGroup(label) {
  const next = new Set(collapsedGroups.value)
  next.has(label) ? next.delete(label) : next.add(label)
  collapsedGroups.value = next
}

const groupedWork = computed(() => {
  if (!myIssues.value.length) return []
  const map = {}
  for (const issue of myIssues.value) {
    let key, color
    if (groupBy.value === 'project')       { key = issue.project || 'No Project'; color = getAvatarColor(key) }
    else if (groupBy.value === 'status')   { key = issue.status || 'No Status'; color = 'var(--muted)' }
    else                                   { key = issue.priority || 'Medium'; color = priorityColor(key) }
    if (!map[key]) map[key] = { label: key, color, tasks: [] }
    map[key].tasks.push(issue)
  }
  return Object.values(map)
})

// ── Profitability filters ──────────────────────────────────────────────────
const profitFilters = ['All', 'T&M', 'Fixed', 'Retainer']
const profitFilter  = ref('All')
const filteredProfitability = computed(() => {
  if (profitFilter.value === 'All') return profitability.value
  const map = { 'T&M': 'tm', 'Fixed': 'fixed', 'Retainer': 'retainer' }
  return profitability.value.filter(r => r.project_type === map[profitFilter.value])
})
const invoiceTotal = computed(() => invoiceReady.value.reduce((s, g) => s + g.total, 0))

// ── Activity ───────────────────────────────────────────────────────────────
const activityTabs = ['All', 'Status Changes', 'Comments']
const activityTab  = ref('All')
const filteredActivity = computed(() => {
  if (activityTab.value === 'All') return activityStream.value
  if (activityTab.value === 'Status Changes') return activityStream.value.filter(e => e.action_type === 'Status Change')
  return activityStream.value.filter(e => e.action_type === 'Comment')
})

// ── Stale days helper ──────────────────────────────────────────────────────
function staleDays(task) {
  if (!task.modified) return '?'
  const d = Math.floor((Date.now() - new Date(task.modified).getTime()) / 86400000)
  return d
}

// ── Risk / Milestone actions ───────────────────────────────────────────────
async function submitRisk() {
  if (!newRisk.value.title || !newRisk.value.project) return
  try {
    const r = await createRisk(newRisk.value.project, newRisk.value.title, newRisk.value.severity)
    risks.value.unshift({
      name: r.name, title: r.title, project: r.project,
      project_name: projects.value.find(p => p.name === r.project)?.project_name || r.project,
      severity: r.severity, owner: '', owner_initial: '?', owner_color: '#94a3b8',
    })
    showAddRisk.value = false
    newRisk.value = { title: '', project: '', severity: 'medium' }
  } catch (e) { console.error(e) }
}

async function resolveRisk(name) {
  try {
    await updateRisk(name, { status: 'Mitigated' })
    risks.value = risks.value.filter(r => r.name !== name)
  } catch (e) { console.error('resolveRisk failed', e) }
}

async function submitMilestone() {
  if (!newMilestone.value.title || !newMilestone.value.project) return
  try {
    const m = await createMilestone(
      newMilestone.value.project, newMilestone.value.title,
      newMilestone.value.due_date || null
    )
    const proj = projects.value.find(p => p.name === m.project) || {}
    milestones.value.push({
      name: m.name, title: m.title, project: m.project,
      project_name: proj.project_name || m.project,
      project_color: proj.project_color || 'var(--muted)',
      due_date: m.due_date,
      date_label: m.due_date ? new Date(m.due_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'TBD',
      tasks_left: 0,
    })
    showAddMilestone.value = false
    newMilestone.value = { title: '', project: '', due_date: '' }
  } catch (e) { console.error(e) }
}

async function completeMilestone(name) {
  try {
    await updateMilestone(name, { status: 'Completed' })
    milestones.value = milestones.value.filter(m => m.name !== name)
  } catch (e) { console.error('completeMilestone failed', e) }
}

// ── Navigation ─────────────────────────────────────────────────────────────
function openTask(name) {
  store.openTask(name)
}

// ── Helpers ────────────────────────────────────────────────────────────────
function dueLabelShort(dateStr) {
  if (!dateStr) return ''
  const today = new Date(); today.setHours(0,0,0,0)
  const d = new Date(dateStr + 'T00:00:00')
  const diff = Math.round((d - today) / 86400000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatCurrency(amount, currency = 'USD') {
  if (amount === undefined || amount === null) return '—'
  if (currency === 'NPR' || currency === 'INR') return '₹' + Number(amount).toLocaleString('en-IN')
  return '$' + Number(amount).toLocaleString('en-US')
}

function getAvatarColor(key) {
  const colors = ['#2563EB', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4']
  if (!key) return colors[0]
  let h = 0
  for (let i = 0; i < key.length; i++) h = key.charCodeAt(i) + ((h << 5) - h)
  return colors[Math.abs(h) % colors.length]
}

function priorityColor(priority) {
  const p = (priority || '').toLowerCase()
  if (p === 'high' || p === 'highest' || p === 'blocker') return '#EF4444'
  if (p === 'medium') return '#F59E0B'
  return '#3B82F6'
}

function healthLabel(health) {
  return { on_track: 'On Track', at_risk: 'At Risk', blocked: 'Blocked', on_hold: 'On Hold' }[health] ?? health
}
// get_workspace_summary's member rows use full_name/user_image (matching
// the rest of the API); AvatarStack/Avatar expect name/src — mapping here
// rather than renaming the shared component's contract, since other
// callers already pass it correctly-shaped data. Without this every
// avatar silently falls back to a bare "?" (Avatar.vue's own fallback for
// a missing name), regardless of project.
// No `theme` field on BP Project yet — every card resolves through the
// deterministic key-hash fallback for now (stable per project, no schema
// change needed). Wrapped so wiring up a real per-project picker later is
// a one-line change (pass proj.theme once that field exists).
function projectTheme(proj) {
  return resolveProjectTheme(proj.theme, proj.key)
}

function avatarProps(members) {
  return (members || []).map(m => ({ name: m.full_name, src: m.user_image, color: m.color }))
}

function healthPillClass(health) {
  if (health === 'on_track') return 'text-success-soft-foreground border-success bg-success-soft'
  if (health === 'at_risk')  return 'text-warning-soft-foreground border-warning bg-warning-soft'
  if (health === 'blocked')  return 'text-danger-soft-foreground  border-danger  bg-danger-soft'
  return 'text-muted border-border bg-surface-secondary'
}
function healthDotClass(health) {
  if (health === 'on_track') return 'bg-success'
  if (health === 'at_risk')  return 'bg-warning'
  if (health === 'blocked')  return 'bg-danger'
  return 'bg-muted'
}
function profitStatusClass(status) {
  if (status === 'Healthy')     return 'bg-success-soft text-success-soft-foreground'
  if (status === 'Watch')       return 'bg-warning-soft text-warning-soft-foreground'
  if (status === 'Over budget') return 'bg-danger-soft text-danger-soft-foreground'
  return 'bg-surface-secondary text-muted'
}
function riskDotClass(severity) {
  if (severity === 'critical') return 'bg-danger'
  if (severity === 'high')     return 'bg-[var(--danger-hover)]'
  if (severity === 'medium')   return 'bg-warning'
  return 'bg-muted'
}
</script>
