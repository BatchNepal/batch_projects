<template>
  <div class="h-app overflow-hidden">
  <!-- Public, chrome-less surface (share links): no sidebar, no auth shell. -->
  <div v-if="isPublicRoute" class="h-full overflow-auto bg-background">
    <router-view />
    <Toaster position="bottom-right" :duration="4000" :close-button="true" />
  </div>

  <div v-else class="flex h-full overflow-hidden bg-overlay">
    <!-- Nothing below paints until we know whether onboarding/join-state
         is needed — see bootReady's doc comment. -->
    <div v-if="!bootReady" class="flex-1 flex items-center justify-center h-full">
      <Loader2 class="size-5 animate-spin text-muted" />
    </div>
    <template v-else>
    <OrgOnboarding v-if="showOnboarding" @close="onOnboardingClose" />
    <NoProjectsSharedYet v-if="showJoinState" @close="onJoinStateClose" />
    <Sidebar ref="sidebarRef" @search="showSearch = true" />
    <div class="flex flex-col flex-1 min-w-0 overflow-hidden">
      <!-- Mobile topbar -->
      <div class="flex items-center h-[48px] px-4 border-b border-border bg-overlay shrink-0 lg:hidden">
        <div class="w-6 h-6 rounded-[6px] flex items-center justify-center text-white text-[9px] font-bold mr-2 overflow-hidden"
          :class="entitlements.branding.logo_url ? '' : 'bg-accent'">
          <img v-if="entitlements.branding.logo_url" :src="entitlements.branding.logo_url" class="w-full h-full object-cover" alt="" />
          <template v-else>BP</template>
        </div>
        <span class="text-[14px] font-semibold text-foreground flex-1">
          {{ currentPageTitle }}
        </span>
        <button @click="showSearch = true" class="p-1.5 rounded-md text-muted hover:bg-surface-secondary">
          <svg class="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
        </button>
      </div>

      <!-- Subscription status banner -->
      <div v-if="!isPublicRoute && entitlements.isExpired"
           class="shrink-0 bg-red-600 text-white text-[13px] font-medium text-center py-2 px-4">
        Your license has expired.
        <a href="/workspace/pricing" class="underline font-semibold hover:text-red-100">Renew now</a>
        to restore access to paid features.
      </div>
      <div v-else-if="!isPublicRoute && entitlements.isExpiringSoon"
           class="shrink-0 bg-amber-500 text-white text-[13px] font-medium text-center py-2 px-4">
        Your license expires in {{ entitlements.daysRemaining }} day{{ entitlements.daysRemaining === 1 ? '' : 's' }}.
        <a href="/workspace/pricing" class="underline font-semibold hover:text-amber-100">Renew now</a>
        to avoid interruption.
      </div>

      <ProjectHeader v-if="isProjectRoute" @open-search="showSearch = true" />

      <!-- Main content — add pb-16 on mobile for bottom nav -->
      <main class="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
        <div class="h-full pb-[env(safe-area-inset-bottom,0px)] lg:pb-0">
          <router-view />
        </div>
      </main>
    </div>

    <!-- Sits above the mobile bottom nav (Sidebar.vue) on small screens,
         clear of the desktop sidebar rail on the right instead of the left. -->
    <div class="fixed z-30 bottom-16 right-4 lg:bottom-4">
      <GlobalTimerIndicator />
    </div>

    <CreateTask v-model="store.showCreateTask" @created="store.refreshBoard" />
    <NotificationsDrawer />
    <TaskDetail v-if="store.showTaskDetail && store.selectedTask" ref="taskDetailRef" @close="store.closeTaskDetail()" />
    <BlockerConfirmModal />
    <SearchPopup v-model="showSearch"/>
    <ShortcutsOverlay v-model="showCheatSheet"/>
    <Toaster position="bottom-right" :duration="4000" :close-button="true" />
    </template>
  </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useEntitlementsStore } from '@/stores/entitlements'
import { bootstrapBridge } from '@/utils/api'
import { connectRealtime, teardownRealtime } from '@/utils/realtime'
import { Toaster, toast } from 'vue-sonner'
import Sidebar from '@/components/Sidebar.vue'
import ProjectHeader from '@/components/ProjectHeader.vue'
import CreateTask from '@/components/CreateTask.vue'
import TaskDetail from '@/components/TaskDetail.vue'
import NotificationsDrawer from '@/components/NotificationsDrawer.vue'
import GlobalTimerIndicator from '@/components/GlobalTimerIndicator.vue'
import BlockerConfirmModal from '@/components/BlockerConfirmModal.vue'
import SearchPopup from '@/components/SearchPopup.vue'
import ShortcutsOverlay from '@/components/ShortcutsOverlay.vue'
import OrgOnboarding from '@/components/onboarding/OrgOnboarding.vue'
import NoProjectsSharedYet from '@/components/onboarding/NoProjectsSharedYet.vue'
import { Loader2 } from 'lucide-vue-next'
import { useGlobalShortcuts } from '@/composables/useGlobalShortcuts'

const route = useRoute()
const store = useProjectStore()
const entitlements = useEntitlementsStore()
const sidebarRef = ref(null)
const taskDetailRef = ref(null)
const showSearch = ref(false)
const showOnboarding = ref(false)
const showJoinState = ref(false)
const projectsLoaded = ref(false)
const showCheatSheet = ref(false)
// Gates the whole authenticated shell (sidebar + workspace) so it never
// paints before we know whether onboarding/join-state needs to show instead
// — without this, the real workspace flashed for a moment on every fresh
// load before the onboarding decision (see the watcher below) landed.
const bootReady = computed(() => projectsLoaded.value && entitlements.loaded)
const isPublicRoute = computed(() => route.meta?.public === true || route.path.startsWith('/share/'))
const isProjectRoute = computed(() =>
  !!route.params.key &&
  !route.path.includes('/settings') &&
  !route.path.includes('/team/')
)

const currentPageTitle = computed(() => {
  if (route.params.key) return route.params.key.toUpperCase()
  const map = { '/workspace': 'Home', '/workspace/my-tasks': 'My Tasks', '/workspace/notifications': 'Inbox', '/workspace/all': 'Projects' }
  return map[route.path] || 'Batch Projects'
})

// White-label branding (Team plan+) — applies the moment entitlements load
// or change (plan upgrade, admin edit), no reload needed.
watch(() => entitlements.branding, (b) => {
  if (!b) return
  document.title = b.brand_name || 'BatchProjects'
  if (b.favicon_url) {
    let link = document.querySelector('link[rel="icon"]')
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    link.href = b.favicon_url
  }
}, { deep: true, immediate: true })

// Reconnect board when tab becomes visible again after being hidden
// (WebSocket may have dropped while backgrounded)
function onVisibilityChange() {
  if (document.visibilityState === 'visible' && store.currentProject) {
    store.refreshBoard()
  }
}

onMounted(async () => {
  // Public share surface: no authenticated user, skip all workspace bootstrap.
  if (isPublicRoute.value) return
  // Resolve the real session + user name first (self-contained: mirrors the
  // injected prod session, or fetches it on the dev server). This is what makes
  // the user's name appear on every page instead of falling back to "User".
  await store.bootstrapSession()
  // Guest on an allow-guest route (e.g. invite accept): the router guard already
  // redirects guests off authenticated routes, so any guest reaching here is on a
  // public-ish page that does its own thing — don't fire authenticated calls.
  const sessionUser = window?.frappe?.session?.user
  if (!sessionUser || sessionUser === 'Guest') return
  // Handshake with the bridge: establishes the gateway session JWT and returns
  // the authoritative entitlements. On Frappe Cloud (cross-origin) this is the
  // ONLY way the SPA learns its real tier — Frappe-direct can't see the gateway's
  // X-BP-Tier header. If the bridge is absent/unconfigured, fall back to the
  // Frappe entitlements mirror (self-host fronted / dev).
  bootstrapBridge().then((boot) => {
    if (boot?.entitlements) entitlements.applyEntitlements(boot.entitlements)
    else entitlements.load()
    // Gateway JWT is only available once bootstrapBridge resolves — the
    // realtime connection needs it (EventSource can't send the session
    // cookie cross-origin, see utils/realtime.js).
    connectRealtime()
  }).catch(() => entitlements.load())
  // Branding lives in Frappe (BP Workspace Settings), not the bridge's
  // license payload — fetch it independently of which path seeded the rest
  // of entitlements above.
  entitlements.loadBranding()
  // Must not throw past this point: bootReady (App.vue template) gates the
  // entire authenticated shell on projectsLoaded, so an uncaught rejection
  // here (e.g. a transient bridge/network failure) would soft-lock the app
  // behind the boot spinner forever instead of just showing an empty board —
  // strictly worse than the pre-bootReady flash bug it replaced.
  try {
    await store.fetchProjects()
  } catch (e) {
    toast.error('Could not load projects', { description: String(e.message || e) })
  }
  projectsLoaded.value = true
  document.addEventListener('visibilitychange', onVisibilityChange)
})

// The old trigger was purely "do I currently
// see zero projects" — which re-fired on every reload (nothing persisted a
// skip/complete) and, for an invited teammate with no memberships yet,
// showed the full "create your workspace" wizard instead of a lighter
// join/waiting state. Runs as a watcher rather than inline in onMounted
// because entitlements (loadBranding, which carries workspace_has_projects/
// onboarding_dismissed — see that function's doc comment) and
// store.fetchProjects() resolve independently and in no guaranteed order;
// this only decides once both are actually in.
watch(
  () => [entitlements.onboardingDismissed, entitlements.workspaceHasProjects, entitlements.loaded, projectsLoaded.value, store.projects.length],
  () => {
    // entitlements.loaded matters as much as projectsLoaded: fetchProjects()
    // is awaited directly above, but the entitlements/bridge chain is fired
    // via .then()/.catch() and can resolve later. Without this guard,
    // workspaceHasProjects was still sitting at its fail-open default (true)
    // when this fired, so a genuinely empty (zero-project) workspace showed
    // the "nothing shared with you" join state instead of the create wizard
    // — and once shown, the guard below never let it self-correct.
    if (!projectsLoaded.value || !entitlements.loaded) return
    if (entitlements.onboardingDismissed) return
    if (showOnboarding.value || showJoinState.value) return
    if (!entitlements.workspaceHasProjects) {
      showOnboarding.value = true
    } else if (store.projects.length === 0) {
      showJoinState.value = true
    }
  },
  { immediate: true }
)

async function onOnboardingClose() {
  showOnboarding.value = false
  entitlements.dismissOnboarding()
  await store.fetchProjects()
}

async function onJoinStateClose() {
  showJoinState.value = false
  entitlements.dismissOnboarding()
}

// Global single-key shortcuts (C / A / ?) — see composables/useGlobalShortcuts.js.
// No card-focus/hover selection subsystem exists yet on Board/ListView, so `A`
// targets the currently open TaskDetail drawer only — a deliberate scope decision.
useGlobalShortcuts({
  isBlocked: () => isPublicRoute.value || showSearch.value || store.showCreateTask || showOnboarding.value || showJoinState.value || showCheatSheet.value,
  onCreate: () => { store.showCreateTask = true },
  onAssign: () => {
    if (store.showTaskDetail && store.selectedTask) taskDetailRef.value?.openAssigneePicker()
    else toast('Open a task to assign someone')
  },
  onCheatSheet: () => { showCheatSheet.value = true },
})

onUnmounted(() => {
  teardownRealtime()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>