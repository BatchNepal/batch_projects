<template>
  <div class="contents">
    <!-- ══════════════════════ DESKTOP SIDEBAR ══════════════════════ -->
    <aside
      class="hidden lg:flex flex-col shrink-0 h-full bg-[var(--sidebar-bg)] select-none z-10 border-r border-white/[0.07] overflow-hidden relative"
      :class="resizing ? '' : 'transition-[width] duration-200 ease-in-out'"
      :style="{ width: collapsed ? '52px' : sidebarWidth + 'px' }"
    >
      <!-- Resize handle — drag to resize, min/max clamped, persisted to localStorage. -->
      <div
        v-if="!collapsed"
        class="absolute top-0 right-0 h-full w-1 cursor-col-resize z-20 hover:bg-white/[0.12] active:bg-white/20 transition-colors"
        :class="resizing ? 'bg-white/20' : ''"
        @mousedown="startResize"
      />
      <!-- ── Workspace header ──────────────────────────────────────── -->
      <div
        class="shrink-0 flex items-center h-[52px]"
        :class="collapsed ? 'justify-center' : 'px-3 gap-1'"
      > 
        <template v-if="!collapsed">
          <button
            class="flex-1 flex items-center gap-2 min-w-0 px-2 h-8 rounded-md hover:bg-white/[0.07] transition-colors text-left"
            @click="wsMenuOpen = !wsMenuOpen"
          >
            <div
              class="w-5 h-5 rounded-[4px] flex items-center justify-center shrink-0 overflow-hidden"
            >
              <img :src="entitlements.branding.logo_url || '/assets/batch_projects/images/bp-logo-new.svg'" class="w-full h-full object-cover" alt="" />
            </div>
            <span
              class="flex-1 text-[13px] font-semibold text-[var(--sidebar-text-active)] truncate"
              >{{ workspaceName }}</span
            >
            <ChevronsUpDown
              :size="12"
              :stroke-width="2"
              class="text-[var(--sidebar-text)] shrink-0"
            />
          </button>
          <button
            class="sb-hdr-btn"
            @click="store.showCreateTask = true"
            title="New task (C)"
          >
            <PenLine :size="14" :stroke-width="1.5" />
          </button>
          <button
            class="sb-hdr-btn"
            @click="collapsed = true"
            title="Collapse sidebar"
          >
            <PanelLeftClose :size="14" :stroke-width="1.5" />
          </button>
        </template>
        <template v-else>
          <button
            class="sb-col-btn"
            @click="collapsed = false"
            title="Expand sidebar"
          >
            <PanelLeftOpen :size="14" :stroke-width="1.5" />
          </button>
        </template>
      </div>

      <!-- ── Search trigger ───────────────────────────────────────── -->
      <div v-if="!collapsed" class="px-3 pb-6">
        <button
          @click="$emit('search')"
          class="w-full flex items-center gap-2 h-[30px] px-2.5 rounded-sm bg-white/[0.07] hover:bg-white/[0.1] transition-colors"
        >
          <Search
            :size="13"
            :stroke-width="1.75"
            class="text-[var(--sidebar-text)] shrink-0"
          />
          <span class="flex-1 text-[12px] text-[var(--sidebar-text)] text-left"
            >Search or jump to…</span
          >
          <kbd
            class="text-[10px] font-semibold text-[var(--sidebar-text)] bg-white/[0.1] border border-white/[0.12] rounded px-1 py-px leading-none shrink-0"
            >⌘K</kbd
          >
        </button>
      </div>
      <!-- ── Nav ──────────────────────────────────────────────────── -->
      <nav
        class="flex-1 min-h-0 overflow-y-auto overflow-x-hidden sb-scroll"
        :class="collapsed ? 'px-1.5 pt-1 pb-3' : 'px-2 pb-6'"
      >
        <!-- ── Collapsed ──────────────────────────────────────────── -->
        <template v-if="collapsed">
          <div class="flex flex-col items-center gap-px">
            <button
              class="sb-col-btn"
              @click="$emit('search')"
              title="Search (⌘K)"
            >
              <Search :size="16" :stroke-width="1.5" />
            </button>
            <button
              class="sb-col-btn"
              :class="exactActive('/workspace') && 'sb-col-active'"
              @click="go('/workspace')"
              title="Home"
            >
              <House :size="16" :stroke-width="1.5" />
            </button>
            <button
              class="sb-col-btn"
              :class="exactActive('/workspace/my-tasks') && 'sb-col-active'"
              @click="go('/workspace/my-tasks')"
              title="My Tasks"
            >
              <CircleCheckBig :size="16" :stroke-width="1.5" />
            </button>
            <button
              class="sb-col-btn relative"
              :class="
                exactActive('/workspace/notifications') && 'sb-col-active'
              "
              @click="store.toggleNotifDrawer(true)"
              title="Inbox"
            >
              <Inbox :size="16" :stroke-width="1.5" />
              <span
                v-if="unreadCount > 0"
                class="absolute top-1.5 right-1.5 w-[5px] h-[5px] rounded-full bg-[var(--accent)]"
              />
            </button>
            <button
              v-if="entitlements.canWorkspace('timesheets')"
              class="sb-col-btn"
              :class="exactActive('/workspace/timesheets') && 'sb-col-active'"
              @click="go('/workspace/timesheets')"
              title="Timesheets"
            >
              <Timer :size="16" :stroke-width="1.5" />
            </button>
            <div class="w-6 h-px bg-[var(--sidebar-hover-bg)] my-2" />
            <button
              v-for="p in visibleProjects"
              :key="p.name"
              class="w-8 h-8 rounded-[7px] overflow-hidden mb-1 transition-[opacity,box-shadow] hover:opacity-90"
              :class="isProjectActive(p.key) ? 'ring-2 ring-white/70 ring-offset-2 ring-offset-[var(--sidebar-bg)]' : 'opacity-90'"
              :title="p.project_name || p.name"
              @click="go(store.projectLanding(p))"
            >
              <ProjectAvatar :theme="p.theme" :seed="p.key" size="md" />
            </button>
          </div>
        </template>

        <!-- ── Expanded ───────────────────────────────────────────── -->
        <template v-else>
          
          <!-- ── FAVORITES ──────────────────────────────────────── -->
          <div class="px-2 mt-5 mb-1.5" v-if="favoriteProjects.length > 0">
            <span
              class="text-[10.5px] font-semibold uppercase tracking-widest text-[var(--sidebar-text)]"
              >Favorites</span
            >
          </div>
          <div
            v-for="p in favoriteProjects"
            :key="'fav-'+p.name"
            class="relative group/pr mb-px"
          >
            <button
              class="w-full flex items-center gap-2 h-[33px] px-2.5 rounded-md text-left transition-colors"
              :class="
                isProjectActive(p.key)
                  ? 'bg-[var(--sidebar-active-bg)] text-white'
                  : 'text-[var(--sidebar-text)] hover:bg-white/[0.07] hover:text-white'
              "
              @click="go(store.projectLanding(p))"
            >
              <ProjectAvatar :theme="p.theme" :seed="p.key" size="xs" />
              <span class="flex-1 text-[13px] font-medium truncate">{{
                p.project_name || p.name
              }}</span>

              <span
                role="button"
                tabindex="0"
                class="w-5 h-5 flex items-center justify-center rounded text-warning opacity-0 group-hover/pr:opacity-100 hover:bg-white/[0.12] transition-[background-color,opacity] cursor-pointer"
                @click.stop="store.toggleFavorite(p.name)"
                @keydown.enter.stop.prevent="store.toggleFavorite(p.name)"
                title="Unpin"
              >
                <PinOff :size="12" :stroke-width="2" />
              </span>
            </button>
          </div>

          <!-- Personal section -->
          <NavItem
            :active="exactActive('/workspace')"
            @click="go('/workspace')"
          >
            <template #icon><House :size="15" :stroke-width="1.5" /></template>
            Home
          </NavItem>
          <NavItem
            :active="exactActive('/workspace/my-tasks')"
            @click="go('/workspace/my-tasks')"
          >
            <template #icon
              ><CircleCheckBig :size="15" :stroke-width="1.5"
            /></template>
            <span class="flex-1">My Tasks</span>
          </NavItem>
          <NavItem
            :active="store.showNotifDrawer"
            @click="store.toggleNotifDrawer(true)"
          >
            <template #icon>
              <div class="relative">
                <Inbox :size="15" :stroke-width="1.5" />
                <span
                  v-if="unreadCount > 0"
                  class="absolute -top-px -right-px w-[5px] h-[5px] rounded-full bg-[var(--accent)]"
                />
              </div>
            </template>
            <span class="flex-1">Inbox</span>
            <span v-if="unreadCount > 0" class="sb-badge">{{
              unreadCount
            }}</span>
          </NavItem>
          <NavItem
            :active="exactActive('/workspace/triage')"
            @click="go('/workspace/triage')"
          >
            <template #icon><ListTodo :size="15" :stroke-width="1.5" /></template>
            Triage
          </NavItem>
          <NavItem
            v-if="entitlements.canWorkspace('timesheets')"
            :active="exactActive('/workspace/timesheets')"
            @click="go('/workspace/timesheets')"
          >
            <template #icon><Timer :size="15" :stroke-width="1.5" /></template>
            Timesheets
          </NavItem>

          <!-- ── PROJECTS ───────────────────────────────────────── -->
          <div class="flex items-center px-2 mt-5 mb-1.5">
            <span
              class="flex-1 text-[10.5px] font-semibold uppercase tracking-widest text-[var(--sidebar-text)]"
              >Projects</span
            >
            <button
              class="w-5 h-5 flex items-center justify-center rounded text-[var(--sidebar-text)] hover:text-[var(--sidebar-text)] hover:bg-white/[0.07] transition-colors"
              @click="$router.push(`/workspace/new-project`)"
              title="New project"
            >
              <Plus :size="13" :stroke-width="2" />
            </button>
          </div>

          <div
            v-for="(p, idx) in visibleProjects"
            :key="p.name"
            class="relative group/pr mb-px sb-proj-row"
            :class="[
              dragIndex === idx ? 'opacity-40' : '',
              dragOverIndex === idx ? 'sb-drop-target' : '',
            ]"
            data-proj-menu
            draggable="true"
            @dragstart="onProjDragStart(idx, $event)"
            @dragenter.prevent="onProjDragEnter(idx)"
            @dragover.prevent
            @drop="onProjDrop(idx)"
            @dragend="onProjDragEnd"
          >
            <button
              class="w-full flex items-center gap-2 h-[33px] px-2.5 rounded-md text-left transition-colors"
              :class="
                isProjectActive(p.key)
                  ? 'bg-[var(--sidebar-active-bg)] text-white'
                  : 'text-[var(--sidebar-text)] hover:bg-white/[0.07] hover:text-white'
              "
              @click="go(store.projectLanding(p))"
            >
              <ProjectAvatar :theme="p.theme" :seed="p.key" size="xs" />
              <span class="flex-1 text-[13px] font-medium truncate">{{
                p.project_name || p.name
              }}</span>
              <!-- spacer so name doesn't slide under the 3-dot -->
              <span class="w-4 shrink-0" />
            </button>

            <!-- 3-dot menu button — hover-reveal -->
            <button
              class="absolute right-1.5 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center rounded text-[var(--sidebar-text)] opacity-0 group-hover/pr:opacity-100 hover:bg-white/[0.12] hover:text-white transition-[background-color,color,opacity] duration-100"
              :class="projectMenuOpen === p.name ? '!opacity-100 bg-white/[0.12] text-white' : ''"
              @click.stop="toggleProjectMenu(p.name)"
              data-proj-menu
            >
              <MoreHorizontal :size="13" :stroke-width="2" />
            </button>

            <!-- Dropdown -->
            <Transition name="sb-dd">
              <div
                v-if="projectMenuOpen === p.name"
                class="absolute right-0 top-[calc(100%+6px)] w-52 z-[60] sb-pop sb-pop--down"
                data-proj-menu
              >
                <div class="p-1">
                  <button class="sb-menu-item" @click.stop="goProject(p, 'board')">
                    <Kanban :size="13" :stroke-width="1.5" class="text-muted" />
                    Open Board
                  </button>
                  <button class="sb-menu-item" @click.stop="goProject(p, 'settings')">
                    <Settings :size="13" :stroke-width="1.5" class="text-muted" />
                    Settings
                  </button>
                  <button class="sb-menu-item" @click.stop="store.toggleFavorite(p.name); projectMenuOpen = null;">
                    <component :is="p.is_favorite ? PinOff : Pin" :size="13" :stroke-width="1.5" class="text-muted" />
                    {{ p.is_favorite ? 'Unpin Project' : 'Pin Project' }}
                  </button>
                  <div class="h-px bg-separator mx-1 my-1" />
                  <button class="sb-menu-item" @click.stop="copyProjectLink(p)">
                    <Link2 :size="13" :stroke-width="1.5" class="text-muted" />
                    Copy link
                  </button>
                  <button class="sb-menu-item" @click.stop="openProjectNewTab(p)">
                    <ExternalLink :size="13" :stroke-width="1.5" class="text-muted" />
                    Open in new tab
                  </button>
                </div>
              </div>
            </Transition>
          </div>

          <button
            v-if="store.projects.length > MAX_VISIBLE"
            class="w-full flex items-center gap-1.5 h-7 px-2.5 text-[12px] text-[var(--sidebar-text)] hover:text-[var(--sidebar-text)] transition-colors"
            @click="showAll = !showAll"
          >
            <component
              :is="showAll ? ChevronUp : ChevronDown"
              :size="11"
              :stroke-width="2"
              class="shrink-0"
            />
            {{ showAll ? 'Show less' : `Show all (${store.projects.length})` }}
          </button>

          <button
            v-if="!store.projects.length"
            class="w-full flex items-center gap-2 h-[33px] px-2.5 text-[13px] text-[var(--sidebar-text)] hover:text-[var(--sidebar-text)] hover:bg-white/[0.06] rounded-md transition-colors"
            @click="$router.push(`/workspace/new-project`)"
          >
            <Plus :size="14" :stroke-width="1.5" />
            Create first project
          </button>

          <!-- ── REPORTS (hidden when a workspace admin switched it off) ── -->
          <template v-if="entitlements.canWorkspace('reports')">
          <div class="px-2 mt-5 mb-1.5">
            <span
              class="text-[10.5px] font-semibold uppercase tracking-widest text-[var(--sidebar-text)]"
              >Dashboards</span
            >
          </div>
          <NavItem
            :active="reportsActive"
            @click="go('/workspace/reports/dashboard')"
          >
            <template #icon
              ><FileBarChart2 :size="15" :stroke-width="1.5"
            /></template>
            Dashboards
          </NavItem>

          <!-- Pinned (featured) reports -->
          <button
            v-for="r in pinnedReports"
            :key="'rpt-' + r.id"
            class="group/rpt relative w-full flex items-center gap-2.5 rounded-md cursor-pointer transition-colors h-[31px] pl-2.5 pr-2 mb-px text-left text-[var(--sidebar-text)] hover:bg-white/[0.06] hover:text-white"
            :class="route.path === `/workspace/reports/${r.id}` ? 'bg-[var(--sidebar-active-bg)] text-white' : ''"
            @click="go(`/workspace/reports/${r.id}`)"
          >
            <span class="shrink-0 size-[18px] rounded-[5px] grid place-items-center"
              :style="{ background: `color-mix(in oklab, ${r.color || 'var(--accent)'} 20%, transparent)`, color: r.color || 'var(--accent)' }">
              <component :is="iconFor(r.icon)" :size="11" :stroke-width="2" />
            </span>
            <span class="flex-1 text-[13px] truncate">{{ r.name }}</span>
            <span
              role="button"
              tabindex="0"
              class="w-5 h-5 flex items-center justify-center rounded text-[var(--sidebar-text)] opacity-0 group-hover/rpt:opacity-100 hover:bg-white/[0.12] hover:text-white transition-[background-color,color,opacity] cursor-pointer shrink-0"
              title="Unpin from sidebar"
              @click.stop="reportsStore.togglePinned(r.id)"
              @keydown.enter.stop.prevent="reportsStore.togglePinned(r.id)"
            >
              <PinOff :size="11" :stroke-width="2" />
            </span>
          </button>
          </template>

          <!-- ── INSIGHTS ───────────────────────────────────────── -->
          <div class="px-2 mt-5 mb-1.5">
            <span
              class="text-[10.5px] font-semibold uppercase tracking-widest text-[var(--sidebar-text)]"
              >Insights</span
            >
          </div>
          <NavItem
            :active="exactActive('/workspace/goals')"
            @click="go('/workspace/goals')"
          >
            <template #icon
              ><Target :size="15" :stroke-width="1.5"
            /></template>
            Goals
          </NavItem>
          <NavItem
            :active="exactActive('/workspace/portfolio')"
            @click="go('/workspace/portfolio')"
          >
            <template #icon
              ><Briefcase :size="15" :stroke-width="1.5"
            /></template>
            Portfolio
          </NavItem>
          <NavItem
            :active="exactActive('/workspace/projects/tree')"
            @click="go('/workspace/projects/tree')"
          >
            <template #icon><FolderTree :size="15" :stroke-width="1.5" /></template>
            Project Tree
          </NavItem>
          <NavItem
            :active="exactActive('/workspace/workload')"
            @click="go('/workspace/workload')"
          >
            <template #icon
              ><BarChart3 :size="15" :stroke-width="1.5"
            /></template>
            Workload
          </NavItem>
          <!-- Capability off = hide outright (cross-project surface,
               so gated by the pre-resolved view_money_anywhere, not a
               per-project lookup). -->
          <NavItem
            v-if="entitlements.viewMoneyAnywhere"
            :active="exactActive('/workspace/margin')"
            @click="go('/workspace/margin')"
          >
            <template #icon
              ><TrendingUp :size="15" :stroke-width="1.5"
            /></template>
            Margin Report
          </NavItem>
          <NavItem
            :active="exactActive('/workspace/utilization')"
            @click="go('/workspace/utilization')"
          >
            <template #icon
              ><PieChart :size="15" :stroke-width="1.5"
            /></template>
            Utilization
          </NavItem>

          <!-- ── TEAM ───────────────────────────────────────────── -->
          <div class="px-2 mt-5 mb-1.5">
            <span
              class="text-[10.5px] font-semibold uppercase tracking-widest text-[var(--sidebar-text)]"
              >Team</span
            >
          </div>
          <NavItem
            :active="exactActive('/workspace/people')"
            @click="go('/workspace/people')"
          >
            <template #icon
              ><UsersRound :size="15" :stroke-width="1.5"
            /></template>
            People
          </NavItem>
          <NavItem
            :active="exactActive('/workspace/teams')"
            @click="go('/workspace/teams')"
          >
            <template #icon
              ><Building2 :size="15" :stroke-width="1.5"
            /></template>
            Teams
          </NavItem>

          <!-- Pinned teams -->
          <div
            v-for="t in store.pinnedTeams"
            :key="t.team_key"
            class="relative group/tm mb-px"
            data-team-menu
          >
            <button
              class="w-full flex items-center gap-2 h-[33px] px-2.5 rounded-md text-left transition-colors"
              :class="route.path.startsWith('/workspace/team/' + t.team_key)
                ? 'bg-[var(--sidebar-active-bg)] text-white font-semibold'
                : 'text-[var(--sidebar-text)] font-medium hover:bg-white/[0.06] hover:text-white'"
              @click="go('/workspace/team/' + t.team_key)"
            >
              <span
                class="w-5 h-5 rounded-[4px] flex items-center justify-center text-[8.5px] font-bold shrink-0"
                :style="{ background: t.team_color || 'var(--accent)' }"
              >{{ (t.team_name || '?').slice(0, 2).toUpperCase() }}</span>
              <span class="flex-1 text-[13px] truncate">{{ t.team_name }}</span>
              <span class="w-4 shrink-0" />
            </button>

            <!-- 3-dot trigger -->
            <button
              class="absolute right-1.5 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center rounded text-[var(--sidebar-text)] opacity-0 group-hover/tm:opacity-100 hover:bg-white/[0.12] hover:text-white transition-[background-color,color,opacity] duration-100"
              :class="teamMenuOpen === t.team_key ? '!opacity-100 bg-white/[0.12] text-white' : ''"
              data-team-menu
              @click.stop="toggleTeamMenu(t.team_key)"
            >
              <MoreHorizontal :size="13" :stroke-width="2" />
            </button>

            <!-- Dropdown -->
            <Transition name="sb-dd">
              <div
                v-if="teamMenuOpen === t.team_key"
                class="absolute right-0 top-[calc(100%+6px)] w-52 z-[60] sb-pop sb-pop--down"
                data-team-menu
              >
                <div class="p-1">
                  <button class="sb-menu-item" @click.stop="goTeam(t.team_key, '')">
                    <UsersRound :size="13" :stroke-width="1.5" class="text-muted" />
                    Overview
                  </button>
                  <div class="h-px bg-separator mx-1 my-1" />
                  <button class="sb-menu-item" @click.stop="goTeam(t.team_key, 'settings')">
                    <Settings :size="13" :stroke-width="1.5" class="text-muted" />
                    Settings
                  </button>
                  <button class="sb-menu-item text-muted" @click.stop="store.togglePinnedTeam(t); teamMenuOpen = null">
                    <PinOff :size="13" :stroke-width="1.5" class="text-muted" />
                    Unpin
                  </button>
                </div>
              </div>
            </Transition>
          </div>
        </template>
      </nav>

      <!-- ── Footer ────────────────────────────────────────────────── -->
      <div class="shrink-0">
        <!-- User -->
        <div class="relative" ref="userMenuRef">
          <button
            class="w-full flex items-center gap-2.5 hover:bg-white/[0.06] transition-colors"
            :class="collapsed ? 'justify-center p-3' : 'px-3 py-2.5'"
            @click="userMenuOpen = !userMenuOpen"
            :title="collapsed ? userName : ''"
          >
            <div class="sb-avatar shrink-0">{{ userInitials }}</div>
            <template v-if="!collapsed">
              <div class="flex-1 min-w-0 text-left">
                <p
                  class="text-[13px] font-semibold text-[var(--sidebar-text-active)] truncate leading-none"
                >
                  {{ userName }}
                </p>
                <p
                  class="text-[11px] text-[var(--sidebar-text)] truncate mt-0.5 leading-none"
                >
                  {{ userEmail }}
                </p>
              </div>
              <ChevronsUpDown
                :size="12"
                :stroke-width="2"
                class="text-[var(--sidebar-text)] shrink-0"
              />
            </template>
          </button>

          <Transition name="sb-dd">
            <div
              v-if="userMenuOpen"
              class="absolute bottom-full left-2 right-2 mb-2 z-50 sb-pop sb-pop--up"
            >
              <div class="px-3 py-2.5 border-b border-separator">
                <p class="text-[12.5px] font-semibold text-foreground truncate">
                  {{ userName }}
                </p>
                <p class="text-[11px] text-muted truncate mt-0.5">
                  {{ userEmail }}
                </p>
              </div>
              <div class="p-1">
                <button
                  v-if="entitlements.isWorkspaceAdmin"
                  class="sb-menu-item"
                  @click="go('/workspace/settings'); userMenuOpen = false"
                >
                  <SlidersHorizontal
                    :size="14"
                    :stroke-width="1.5"
                    class="text-muted"
                  />
                  Workspace settings
                </button>
                <button
                  class="sb-menu-item"
                  @click="go('/workspace/account'); userMenuOpen = false"
                >
                  <Settings
                    :size="14"
                    :stroke-width="1.5"
                    class="text-muted"
                  />
                  Account settings
                </button>
                <button
                  class="sb-menu-item"
                  @click="go('/workspace/pricing'); userMenuOpen = false"
                >
                  <CreditCard
                    :size="14"
                    :stroke-width="1.5"
                    class="text-muted"
                  />
                  Billing &amp; plan
                </button>
                <div class="h-px bg-separator mx-1 my-1" />
                <button class="sb-menu-item sb-menu-danger" @click="logout">
                  <LogOut :size="14" :stroke-width="1.5" />
                  Sign out
                </button>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </aside>

    <!-- ══════════════════════ MOBILE BOTTOM NAV ══════════════════════ -->
    <nav
      class="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-overlay border-t border-border"
      style="padding-bottom: env(safe-area-inset-bottom, 0px)"
    >
      <div class="flex items-center justify-around px-1 py-1">
        <MobileTab
          :active="exactActive('/workspace')"
          @click="go('/workspace')"
        >
          <House :size="20" :stroke-width="1.5" />
          <span>Home</span>
        </MobileTab>
        <MobileTab
          :active="$route.path.includes('/board')"
          @click="
            currentProjectKey
              ? go(`/workspace/${currentProjectKey}/board`)
              : go('/workspace')
          "
        >
          <Kanban :size="20" :stroke-width="1.5" />
          <span>Board</span>
        </MobileTab>
        <button
          @click="store.showCreateTask = true"
          class="flex items-center justify-center -mt-5 rounded-full text-white active:scale-95 transition-transform"
          style="
            width: 48px;
            height: 48px;
            background: var(--accent);
            box-shadow: 0 4px 14px color-mix(in oklab, var(--accent) 40%, transparent);
          "
        >
          <Plus :size="20" :stroke-width="2.5" />
        </button>
        <MobileTab
          :active="exactActive('/workspace/my-tasks')"
          @click="go('/workspace/my-tasks')"
        >
          <CircleCheckBig :size="20" :stroke-width="1.5" />
          <span>Tasks</span>
        </MobileTab>
        <MobileTab
          :active="mobileDrawerOpen"
          @click="mobileDrawerOpen = !mobileDrawerOpen"
        >
          <Menu :size="20" :stroke-width="1.5" />
          <span>More</span>
        </MobileTab>
      </div>
    </nav>

    <!-- Mobile drawer -->
    <Transition name="drawer">
      <div
        v-if="mobileDrawerOpen"
        class="lg:hidden fixed inset-0 z-30 flex flex-col justify-end"
      >
        <div
          class="absolute inset-0 bg-black/40"
          @click="mobileDrawerOpen = false"
        />
        <div
          class="relative bg-overlay rounded-t-2xl max-h-[80vh] flex flex-col"
          style="box-shadow: 0 -4px 32px rgba(0, 0, 0, 0.15)"
        >
          <div class="flex justify-center pt-3 pb-2 shrink-0">
            <div class="w-8 h-1 rounded-full bg-border" />
          </div>
          <div
            class="flex items-center px-4 pb-3 pt-1 shrink-0 border-b border-separator"
          >
            <div
              class="w-7 h-7 rounded-[6px] flex items-center justify-center mr-2.5 overflow-hidden shrink-0"
            >
              <img :src="entitlements.branding.logo_url || '/assets/batch_projects/images/bp-logo-new.svg'" class="w-full h-full object-cover" alt="" />
            </div>
            <span class="text-[13px] font-semibold text-foreground">{{
              workspaceName
            }}</span>
            <button
              @click="mobileDrawerOpen = false"
              class="ml-auto w-7 h-7 flex items-center justify-center rounded-md text-muted hover:bg-surface-secondary transition-colors"
            >
              <X :size="16" :stroke-width="1.5" />
            </button>
          </div>
          <div class="flex-1 overflow-y-auto px-3 py-2">
            <div
              v-for="p in store.projects"
              :key="'m-' + p.name"
              class="flex items-center gap-3 px-2.5 py-2.5 rounded-md cursor-pointer hover:bg-surface-secondary transition-colors"
              @click="go('/workspace/' + p.key + '/board'); mobileDrawerOpen = false"
            >
              <ProjectAvatar :theme="p.theme" :seed="p.key" size="md" class="shrink-0" />
              <div class="flex-1 min-w-0">
                <p class="text-[13px] font-semibold text-foreground truncate">
                  {{ p.project_name || p.name }}
                </p>
                <p class="text-[10.5px] text-muted font-mono mt-0.5">
                  {{ p.key }}
                </p>
              </div>
              <ChevronRight
                :size="14"
                :stroke-width="1.5"
                class="text-muted shrink-0"
              />
            </div>
          </div>
          <div
            class="shrink-0 px-4 py-3 border-t border-separator flex items-center gap-2.5"
            style="padding-bottom: env(safe-area-inset-bottom, 12px)"
          >
            <div class="sb-avatar shrink-0">{{ userInitials }}</div>
            <div class="flex-1 min-w-0">
              <p class="text-[13px] font-semibold text-foreground truncate">
                {{ userName }}
              </p>
              <p class="text-[11px] text-muted truncate">{{ userEmail }}</p>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, h, defineComponent, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useReportsStore } from '@/stores/reports'
import { useEntitlementsStore } from '@/stores/entitlements'
import { reportIcon } from '@/utils/reportIcons'
import { getNotificationCount, bridgeLogout } from '@/utils/api'
import {
  Building2,
  ChevronsUpDown,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  PanelLeftClose,
  PanelLeftOpen,
  Kanban,
  Menu,
  X,
  BarChart3,
  TrendingUp,
  PieChart,
  LayoutGrid,
  LayoutDashboard,
  FileBarChart2,
  SlidersHorizontal, Target, ListTodo, FolderTree,
} from 'lucide-vue-next'
// Untitled UI free icons for the sidebar's prominent nav items — see
// icons/untitledui.js for the license note. First-pass swap covering the
// most visible icons; secondary/structural chrome above stays Lucide.
import {
  House,
  CircleCheckBig,
  Inbox,
  Timer,
  UsersRound,
  Search,
  Plus,
  PenLine,
  Settings,
  LogOut,
  Briefcase,
  MoreHorizontal,
  Link2,
  ExternalLink,
  PinOff,
  Pin,
  CreditCard,
} from '@/icons/untitledui'
import { ProjectAvatar } from '@/ui'

const store = useProjectStore()
const reportsStore = useReportsStore()
const entitlements = useEntitlementsStore()
const route = useRoute()
const router = useRouter()

// Featured reports pinned to the sidebar.
const pinnedReports = computed(() => reportsStore.reports.filter(r => r.pinned))
function iconFor(name) { return reportIcon(name) }

// "Reports Dashboard" is active on the dashboard/list, or on a report that
// isn't pinned (a pinned report highlights its own row instead — so exactly
// one entry is ever active).
const reportsActive = computed(() => {
  const p = route.path
  if (!p.startsWith('/workspace/reports')) return false
  const id = route.params.reportId
  if (id && pinnedReports.value.some(r => r.id === id)) return false
  return true
})

// ── State ─────────────────────────────────────────────────────────────
const collapsed = ref(false)

// ── Resizable width (drag handle at the right edge, persisted) ─────────
const SIDEBAR_WIDTH_KEY = 'bp_sidebar_width'
const SIDEBAR_MIN = 220
const SIDEBAR_MAX = 420
const sidebarWidth = ref((() => {
  const saved = Number(localStorage.getItem(SIDEBAR_WIDTH_KEY))
  return saved >= SIDEBAR_MIN && saved <= SIDEBAR_MAX ? saved : 280
})())
const resizing = ref(false)

function startResize(e) {
  e.preventDefault()
  resizing.value = true
  const startX = e.clientX
  const startW = sidebarWidth.value
  // html{zoom} density scaling means on-screen pixels moved by the pointer
  // don't map 1:1 to CSS width units — measure the actual rendered rect
  // against the CSS width we set it to, and divide pointer deltas by that
  // ratio (see memory: bp-ui-zoom-pointer-trap; same fix as Gantt's drag math).
  const asideEl = e.currentTarget.closest('aside')
  const scale = asideEl ? asideEl.getBoundingClientRect().width / startW : 1
  function onMove(ev) {
    const next = startW + (ev.clientX - startX) / scale
    sidebarWidth.value = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, next))
  }
  function onUp() {
    resizing.value = false
    localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth.value))
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}
const mobileDrawerOpen = ref(false)
const wsMenuOpen = ref(false)
const userMenuOpen = ref(false)
const userMenuRef = ref(null)
const showAll = ref(false)
const projectMenuOpen = ref(null)
const teamMenuOpen    = ref(null)

const MAX_VISIBLE = 6

defineEmits(['search'])
defineExpose({ collapsed })

// ── Notification badge ────────────────────────────────────────────────
const unreadCount = computed(() => store.notificationCount || 0)

// ── Workspace name ────────────────────────────────────────────────────
const workspaceName = computed(
  () =>
    entitlements.branding.brand_name ||
    window.frappe?.boot?.sysdefaults?.company ||
    window.frappe?.sitename?.split('.')[0] ||
    'BatchProjects'
)

// ── User info (reactive — sourced from the store, not window.frappe) ─────
const userName = computed(
  () =>
    store.currentUser?.fullname ||
    store.currentUser?.user ||
    'User'
)
const userEmail = computed(() => store.currentUser?.user || '')
const userInitials = computed(() =>
  userName.value
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
)

// ── Projects ──────────────────────────────────────────────────────────
const currentProjectKey = computed(() => route.params.key || null)

const favoriteProjects = computed(() => store.projects.filter(p => p.is_favorite))

const visibleProjects = computed(() => {
  const all = store.sortedProjects || []
  return showAll.value ? all : all.slice(0, MAX_VISIBLE)
})

// ── Drag-to-reorder projects ──────────────────────────────────────────────
// Native HTML5 DnD. The visible list is a prefix of the full sorted order, so a
// visible index maps 1:1 to the full-order index in both collapsed & expanded
// states. Persists to the store (localStorage).
const dragIndex = ref(null)
const dragOverIndex = ref(null)

function onProjDragStart(idx, e) {
  dragIndex.value = idx
  try { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(idx)) } catch {}
}
function onProjDragEnter(idx) {
  if (dragIndex.value === null || idx === dragIndex.value) return
  dragOverIndex.value = idx
}
function onProjDrop(idx) {
  if (dragIndex.value === null) return
  const names = store.sortedProjects.map(p => p.name)
  const [moved] = names.splice(dragIndex.value, 1)
  names.splice(idx, 0, moved)
  store.setProjectOrder(names)
  onProjDragEnd()
}
function onProjDragEnd() {
  dragIndex.value = null
  dragOverIndex.value = null
}

// ── Route helpers ─────────────────────────────────────────────────────
function exactActive (path) {
  return route.path === path
}
function isProjectActive (key) {
  return route.path.startsWith(`/workspace/${key}`)
}

// ── Margin indicator ──────────────────────────────────────────────────
// Shows `—` until ERP bridge provides real margin_pct on project objects.
function marginText (project) {
  if (project.margin_pct != null) return `${Math.round(project.margin_pct)}%`
  return '—'
}
function marginColorClass (project) {
  if (project.margin_pct == null) return 'text-muted'
  if (project.margin_pct >= 70) return 'text-success'
  if (project.margin_pct >= 50) return 'text-warning'
  return 'text-danger'
}

// ── Project 3-dot menu ────────────────────────────────────────────────
function toggleProjectMenu (name) {
  projectMenuOpen.value = projectMenuOpen.value === name ? null : name
}
function goProject (p, section) {
  go('/workspace/' + p.key + '/' + section)
  projectMenuOpen.value = null
}
function copyProjectLink (p) {
  const url = window.location.origin + '/workspace/' + p.key + '/board'
  navigator.clipboard?.writeText(url).catch(() => {})
  projectMenuOpen.value = null
}
function openProjectNewTab (p) {
  window.open('/workspace/' + p.key + '/board', '_blank')
  projectMenuOpen.value = null
}
function onDocProjectMenu (e) {
  if (!e.target.closest('[data-proj-menu]')) projectMenuOpen.value = null
}

// ── Team 3-dot menu ───────────────────────────────────────────────────
function toggleTeamMenu (key) {
  teamMenuOpen.value = teamMenuOpen.value === key ? null : key
}
function goTeam (key, section) {
  go('/workspace/team/' + key + (section ? '/' + section : ''))
  teamMenuOpen.value = null
}
function onDocTeamMenu (e) {
  if (!e.target.closest('[data-team-menu]')) teamMenuOpen.value = null
}

// ── Actions ───────────────────────────────────────────────────────────
function go (path) {
  router.push(path)
  mobileDrawerOpen.value = false
  projectMenuOpen.value = null
}
async function logout () {
  userMenuOpen.value = false
  await bridgeLogout()  // best-effort: drop the gateway session before Frappe logout
  window.location.href = '/logout'
}

function onOutsideUserMenu (e) {
  if (!userMenuRef.value?.contains(e.target)) userMenuOpen.value = false
}


// ── Lifecycle ─────────────────────────────────────────────────────────
onMounted(async () => {
  document.addEventListener('mousedown', onOutsideUserMenu)
  document.addEventListener('mousedown', onDocProjectMenu)
  document.addEventListener('mousedown', onDocTeamMenu)
  reportsStore.load().catch(() => {})
  try {
    const res = await getNotificationCount()
    store.notificationCount = res?.unread_count ?? 0
  } catch {}
  if (window.frappe?.realtime) {
    window.frappe.realtime.on('bp_notification_count', data => {
      store.notificationCount = data?.unread_count ?? store.notificationCount
    })
  }
})
onUnmounted(() => {
  document.removeEventListener('mousedown', onOutsideUserMenu)
  document.removeEventListener('mousedown', onDocProjectMenu)
  document.removeEventListener('mousedown', onDocTeamMenu)
})

// ── Sub-components ────────────────────────────────────────────────────

const NavItem = defineComponent({
  props: ['active'],
  emits: ['click'],
  setup (props, { slots, emit }) {
    return () =>
      h(
        'button',
        {
          onClick: () => emit('click'),
          class: [
            'w-full flex items-center gap-2.5 rounded-md cursor-pointer transition-colors h-[33px] pl-2.5 pr-2 mb-px text-left',
            props.active
              ? 'bg-[var(--sidebar-active-bg)] text-white font-semibold'
              : 'text-[var(--sidebar-text)] font-medium hover:bg-white/[0.06] hover:text-white'
          ].join(' ')
        },
        [
          h(
            'span',
            {
              class: [
                'shrink-0 flex items-center',
                props.active ? 'text-white' : 'text-[var(--sidebar-text)]'
              ].join(' ')
            },
            slots.icon?.()
          ),
          h(
            'span',
            {
              class: 'flex-1 flex items-center gap-1.5 text-[13px] truncate'
            },
            slots.default?.()
          )
        ]
      )
  }
})

const MobileTab = defineComponent({
  props: ['active'],
  emits: ['click'],
  setup (props, { slots, emit }) {
    return () =>
      h(
        'button',
        {
          onClick: () => emit('click'),
          class: [
            'flex flex-col items-center justify-center gap-0.5 py-1.5 px-3 rounded-md flex-1 text-[10px] font-medium transition-colors',
            props.active ? 'text-[var(--accent)]' : 'text-muted'
          ].join(' ')
        },
        slots.default?.()
      )
  }
})
</script>

<style scoped>
/* Drag-to-reorder projects */
.sb-proj-row { cursor: grab; }
.sb-proj-row:active { cursor: grabbing; }
/* Reorder drop indicator — a floating rounded bar with a leading dot,
   sitting just above the row (not flush/inset with its edge) so it reads as
   its own "insert here" affordance rather than a flat border line. */
.sb-drop-target::before {
  content: '';
  position: absolute;
  left: 12px;
  right: 4px;
  top: -1.5px;
  height: 2px;
  border-radius: 9999px;
  background: var(--accent);
}
.sb-drop-target::after {
  content: '';
  position: absolute;
  left: 6px;
  top: -3.5px;
  width: 5px;
  height: 5px;
  border-radius: 9999px;
  background: var(--accent);
}

/* Header icon buttons */
.sb-hdr-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--sidebar-text);
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.1s, background 0.1s;
  flex-shrink: 0;
}
.sb-hdr-btn:hover {
  color: var(--sidebar-text-active);
  background: rgba(255, 255, 255, 0.08);
}

/* HeroUI-style popover surface (floats above the dark sidebar) */
.sb-pop {
  background: var(--overlay);
  border-radius: 11px;
  box-shadow: var(--overlay-shadow);
  overflow: hidden;
}
.sb-pop--down { transform-origin: top right; }
.sb-pop--up   { transform-origin: bottom center; }

/* Collapsed icon buttons */
.sb-col-btn {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--sidebar-text);
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.12s, background 0.12s, transform 0.12s;
}
.sb-col-btn:active { transform: scale(0.92); }
.sb-col-btn:hover {
  color: var(--sidebar-text-active);
  background: rgba(255, 255, 255, 0.08);
}
.sb-col-btn.sb-col-active {
  color: var(--sidebar-text-active);
  background: var(--sidebar-active-bg);
}

/* Unread badge */
.sb-badge {
  font-size: 10px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--accent);
  background: color-mix(in oklab, var(--accent) 15%, transparent);
  padding: 1px 5px;
  border-radius: 20px;
  flex-shrink: 0;
}

/* User avatar */
.sb-avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in oklab, var(--accent) 20%, transparent);
  color: var(--accent);
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  border: 1.5px solid rgba(255, 255, 255, 0.18);
}

/* Dropdown menu items — HeroUI menu rows (float above the dark sidebar) */
.sb-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 32px;
  padding: 6px 10px;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  color: var(--foreground);
  background: none;
  border: none;
  text-align: left;
  cursor: pointer;
  border-radius: 8px;
  transition: background-color 0.1s var(--ease-out, ease);
}
.sb-menu-item:hover {
  background: var(--default);
}
.sb-menu-item:active { background: var(--default-hover, var(--default)); }
.sb-menu-danger {
  color: var(--danger);
}
.sb-menu-danger:hover {
  background: var(--danger-soft);
}

/* Scrollbar */
.sb-scroll {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}
.sb-scroll::-webkit-scrollbar {
  width: 3px;
}
.sb-scroll::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

/* Popover open/close — HeroUI-style fade + zoom from the trigger edge */
.sb-dd-enter-active {
  transition: opacity 0.15s var(--ease-out, ease),
    transform 0.15s cubic-bezier(0.16, 1, 0.3, 1);
}
.sb-dd-leave-active {
  transition: opacity 0.1s ease, transform 0.1s ease;
}
.sb-dd-enter-from,
.sb-dd-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(4px);
}

/* Mobile drawer */
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.18s ease;
}
.drawer-enter-active .relative,
.drawer-leave-active .relative {
  transition: transform 0.22s cubic-bezier(0.32, 0.72, 0, 1);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .relative,
.drawer-leave-to .relative {
  transform: translateY(100%);
}
</style>
