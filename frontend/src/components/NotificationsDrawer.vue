<template>
  <Drawer :open="showNotifDrawer" @update:open="store.toggleNotifDrawer($event)" size="xl" placement="right">
    <DrawerHeader class="border-b" @close="store.toggleNotifDrawer(false)">
      <div class="flex items-center justify-between w-full pr-1">
        <div class="flex items-baseline gap-2 min-w-0">
          <h2 class="text-sm font-semibold">Notifications</h2>
          <span v-if="unreadCount > 0" class="text-sm text-muted tabular-nums shrink-0">{{ unreadCount }} unread</span>
        </div>
        <div class="flex items-center gap-1 shrink-0">
          <button
            v-if="unreadCount > 0 && !searchOpen"
            class="text-sm font-medium text-muted hover:text-foreground px-2 py-1 rounded-md hover:bg-surface-hover transition-colors"
            @click="markAllRead"
          >
            Mark all read
          </button>
          <div v-if="searchOpen" class="flex items-center gap-1">
            <input
              ref="searchInputRef"
              v-model="searchQuery"
              class="nd-search-input"
              placeholder="Search notifications…"
              @keydown.escape="closeSearchBox"
            />
            <IconButton variant="ghost" size="sm" title="Close search" @click="closeSearchBox">
              <X class="size-3.5" />
            </IconButton>
          </div>
          <IconButton v-else variant="ghost" size="sm" title="Search notifications" @click="openSearchBox">
            <Search class="size-4" />
          </IconButton>
          <IconButton variant="ghost" size="sm" title="Notification settings" @click="showPrefs = true">
            <Settings class="size-4" />
          </IconButton>
        </div>
      </div>
    </DrawerHeader>

    <!-- Tabs + date filter. One hairline under the whole block. -->
    <div class="bg-overlay border-b border-separator shrink-0">
      <div class="px-4 py-3 flex items-center gap-2 overflow-x-auto">
        <div class="nd-seg shrink-0">
          <button
            v-for="f in FILTERS"
            :key="f.value"
            class="nd-seg-btn"
            :class="{ on: activeFilter === f.value }"
            @click="activeFilter = f.value"
          >
            {{ f.label }}<span v-if="tabCounts[f.value]" class="tabular-nums text-muted">&nbsp;·&nbsp;{{ tabCounts[f.value] }}</span>
          </button>
        </div>
        <div class="flex-1"></div>
        <DatePicker :model-value="dateFilter" class="shrink-0" @update:model-value="onDateSelected">
          <template #trigger="{ open: pOpen }">
            <button type="button" class="nd-icon-btn" :class="{ on: pOpen, active: dateFilter }">
              <CalendarDays class="size-3.5" />
              <template v-if="dateFilter">
                <span>{{ dateFilterLabel }}</span>
                <span class="nd-date-chip-x" @click.stop.prevent="clearDateFilter">
                  <X class="size-3" />
                </span>
              </template>
            </button>
          </template>
        </DatePicker>
      </div>
    </div>

    <DrawerBody class="p-0 bg-background">
      <!-- Loading skeleton cards -->
      <div v-if="loading && !notifications.length" class="flex flex-col p-1">
        <div v-for="i in 5" :key="i" class="flex gap-3 p-3">
          <Skeleton class="size-8 rounded-full shrink-0" />
          <div class="flex flex-col gap-1.5 flex-1 pt-0.5">
            <Skeleton class="h-3 rounded" :style="{ width: i % 2 ? '75%' : '55%' }" />
            <Skeleton class="h-3 rounded" :style="{ width: i % 3 ? '40%' : '30%' }" />
          </div>
        </div>
      </div>

      <EmptyState
        v-else-if="filtered.length === 0"
        :icon="BellOff"
        :title="emptyCopy.title"
        :description="emptyCopy.description"
      />

      <div v-else class="flex flex-col p-1">
        <template v-for="group in groupedFiltered" :key="group.label">
          <div class="px-3 pt-3 pb-1 text-xs font-semibold uppercase tracking-wider text-muted opacity-80">
            {{ group.label }}
          </div>
          <div
            v-for="n in group.items"
            :key="n.name"
            class="nd-row group relative cursor-pointer"
            @click="openNotification(n)"
          >
            <div class="flex gap-3 p-3">
              <span class="nd-dot shrink-0" :class="{ on: !n.is_read }" />
              <Avatar :name="n.actor_name || n.actor || 'System'" size="md" class="shrink-0 self-start" />

              <div class="flex flex-col min-w-0 flex-1">
                <div class="flex items-start justify-between gap-2">
                  <p class="text-base leading-snug text-muted">
                    <span class="font-semibold" :class="n.is_read ? 'text-muted' : 'text-foreground'">{{ n.actor_name || n.actor || 'System' }}</span>
                    {{ ' ' }}{{ getActionText(n) }}
                    <span v-if="n.task_title" class="font-medium" :class="n.is_read ? 'text-muted' : 'text-foreground'">{{ n.task_title }}</span>
                  </p>
                  <Dropdown placement="bottom-end" :side-offset="4">
                    <template #trigger="{ toggle }">
                      <IconButton variant="ghost" size="xs" title="More" class="shrink-0" @click.stop="toggle">
                        <MoreVertical class="size-3.5" />
                      </IconButton>
                    </template>
                    <DropdownItem v-if="actionsByName[n.name].kebabUnread" @click="n.is_read ? markUnread(n) : markRead(n)">
                      {{ n.is_read ? 'Mark unread' : 'Mark read' }}
                    </DropdownItem>
                    <DropdownItem v-if="actionsByName[n.name].kebabReadOnly && !n.is_read" @click="markRead(n)">
                      Mark read
                    </DropdownItem>
                    <DropdownItem v-if="actionsByName[n.name].kebabProject && n.project" @click="openProjectFor(n)">
                      Open project
                    </DropdownItem>
                  </Dropdown>
                </div>

                <p v-if="messageSnippet(n)" class="text-sm text-muted mt-0.5 line-clamp-2">{{ messageSnippet(n) }}</p>

                <div class="flex items-center gap-2 mt-1.5">
                  <span class="text-xs text-muted tabular-nums">{{ fmtRel(n.creation) }}</span>
                  <span v-if="n.task_key" class="text-xs font-mono text-muted">{{ n.task_key }}</span>
                  <span v-else-if="n.project" class="inline-flex items-center gap-1.5 text-xs text-muted">
                    <span class="size-1.5 rounded-full shrink-0" :style="{ background: projectColor(n.project) }" />
                    {{ projectLabel(n.project) }}
                  </span>
                  <span v-if="dueChip(n)" class="text-xs font-medium px-1.5 py-px rounded-md" :class="dueChip(n).cls">
                    {{ dueChip(n).label }}
                  </span>
                </div>

                <template v-if="showActionRow(n)">
                  <div class="nd-sep" />
                  <div class="flex items-center gap-1.5 mt-2">
                    <button class="nd-btn nd-btn-primary" @click.stop="runAction(n, actionsByName[n.name].primary)">
                      {{ actionLabel(actionsByName[n.name].primary) }}
                    </button>
                    <button v-if="actionsByName[n.name].secondary" class="nd-btn nd-btn-ghost" @click.stop="runAction(n, actionsByName[n.name].secondary)">
                      {{ actionLabel(actionsByName[n.name].secondary) }}
                    </button>
                  </div>
                  <div v-if="replyOpenFor === n.name" class="mt-2" @click.stop>
                    <input
                      ref="replyInputRef"
                      v-model="replyText"
                      class="nd-reply-input"
                      :disabled="replyLoading"
                      placeholder="Write a reply…"
                      @keydown.enter="submitReply(n)"
                      @keydown.escape="closeReply"
                    />
                  </div>
                </template>
              </div>
            </div>
          </div>
        </template>
      </div>
    </DrawerBody>

    <DrawerFooter v-if="hasMore" class="justify-center">
      <button class="nd-footer-btn" :disabled="loading" @click="loadMore">
        <Loader2 v-if="loading" class="size-3.5 animate-spin" />
        <span>{{ loading ? 'Loading…' : 'See past notifications' }}</span>
      </button>
    </DrawerFooter>
  </Drawer>

  <!-- Notification preferences modal -->
  <NotifPrefsModal v-if="showPrefs" @close="showPrefs = false" />
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Settings, Search, Loader2, BellOff, CalendarDays, X, MoreVertical } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Drawer, DrawerHeader, DrawerBody, DrawerFooter, IconButton, Avatar, Skeleton, EmptyState, Dropdown, DropdownItem } from '@/ui'
import DatePicker from './DatePicker.vue'
import {
  getNotifications,
  markNotificationRead,
  markNotificationUnread,
  markAllNotificationsRead,
  addComment,
} from '@/utils/api'
import { useProjectStore } from '@/stores/project'
import { storeToRefs } from 'pinia'
import NotifPrefsModal from './NotifPrefsModal.vue'

const router = useRouter()
const store  = useProjectStore()
const { showNotifDrawer } = storeToRefs(store)

const notifications = ref([])
const unreadCount   = ref(0)
const total         = ref(0)
const loading       = ref(false)
const activeFilter  = ref('all')
const searchQuery   = ref('')
const searchOpen    = ref(false)
const searchInputRef = ref(null)
const showPrefs     = ref(false)
const dateFilter    = ref(null)
const replyOpenFor  = ref(null)
const replyText     = ref('')
const replyLoading  = ref(false)
const replyInputRef = ref(null)
const PAGE_SIZE     = 30

const FILTERS = [
  { value: 'all',        label: 'All' },
  { value: 'comment',    label: 'Comments' },
  { value: 'mention',    label: 'Mentions' },
  { value: 'assignment', label: 'Assigned' },
  { value: 'due',        label: 'Due' },
]

function normalizeType(type) {
  const t = (type || '').toLowerCase()
  if (t === 'due soon' || t === 'overdue') return 'due'
  if (t === 'status change') return 'status'
  if (t === 'unassigned') return 'unassigned'
  if (t === 'update') return 'update'
  if (t === 'rule') return 'rule'
  if (t === 'summary') return 'summary'
  return t
}

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return notifications.value.filter((n) => {
    if (activeFilter.value === 'comment'    && normalizeType(n.notification_type) !== 'comment')    return false
    if (activeFilter.value === 'mention'    && normalizeType(n.notification_type) !== 'mention')    return false
    if (activeFilter.value === 'assignment' && !['assignment','unassigned'].includes(normalizeType(n.notification_type))) return false
    if (activeFilter.value === 'due'        && normalizeType(n.notification_type) !== 'due')        return false
    if (q) {
      const haystack = [n.message, n.task_key, n.task_title, n.project, n.actor_name, n.actor]
        .filter(Boolean).join(' ').toLowerCase()
      if (!haystack.includes(q)) return false
    }
    return true
  })
})

const hasMore = computed(() => notifications.value.length < total.value)

// Unread counts per filter tab.
const tabCounts = computed(() => {
  const c = { all: 0, comment: 0, mention: 0, assignment: 0, due: 0 }
  for (const n of notifications.value) {
    if (n.is_read) continue
    const t = normalizeType(n.notification_type)
    // unassigned rolls up into the assignment tab counter
    const bucket = t === 'unassigned' ? 'assignment' : t
    if (c[bucket] != null) c[bucket]++
  }
  return c
})

const EMPTY_LABELS = {
  all: 'All caught up', comment: 'No comments', mention: 'No mentions',
  assignment: 'Nothing assigned', due: 'Nothing due',
}
const emptyCopy = computed(() => {
  if (searchQuery.value.trim()) return { title: 'No matching notifications', description: 'Try a different search term.' }
  if (dateFilter.value) return { title: 'Nothing on this day', description: 'Try a different date.' }
  return {
    title: EMPTY_LABELS[activeFilter.value] || 'All caught up',
    description: 'Nothing new to see here.',
  }
})

// Group the filtered list into Today / Yesterday / This week / Earlier.
function timeBucket(d) {
  if (!d) return 'Earlier'
  const now = new Date(); const dt = new Date(d)
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diffDays = Math.floor((startToday - new Date(dt.getFullYear(), dt.getMonth(), dt.getDate())) / 86400000)
  if (diffDays <= 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return 'This week'
  return 'Earlier'
}
const groupedFiltered = computed(() => {
  const order = ['Today', 'Yesterday', 'This week', 'Earlier']
  const map = {}
  for (const n of filtered.value) {
    const b = timeBucket(n.creation)
    ;(map[b] || (map[b] = [])).push(n)
  }
  return order.filter((l) => map[l]?.length).map((l) => ({ label: l, items: map[l] }))
})

// Deterministic color for a project dot (matches sidebar fallback palette).
// NOTE: not yet routed through utils/palette.js — that module is spec 01's
// scope (unifies 3 duplicate fallback palettes) and hasn't been built yet.
const PROJECT_COLORS = ['#1e96eb', '#26B5CE', '#4CB782', '#F2994A', '#E57373', '#7C3AED', '#059669', '#E91E63', '#0891B2', '#D97706']
function projectColor(projectName) {
  const p = store.projects.find(x => x.name === projectName)
  if (p?.project_color) return p.project_color
  let h = 0; const k = p?.key || projectName || ''
  for (let i = 0; i < k.length; i++) h = k.charCodeAt(i) + ((h << 5) - h)
  return PROJECT_COLORS[Math.abs(h) % PROJECT_COLORS.length]
}

// Raw backend type, NOT normalizeType()'s output — normalizeType collapses
// "Due Soon"/"Overdue" into one 'due' bucket for tab filtering, which made
// the checks below unreachable (every reminder silently fell to 'updated').
function getActionText(n) {
  const t = (n.notification_type || '').toLowerCase()
  if (t === 'mention')       return 'mentioned you in'
  if (t === 'assignment')    return 'assigned you to'
  if (t === 'unassigned')    return 'unassigned you from'
  if (t === 'comment')       return 'commented on'
  if (t === 'status change') return 'changed status on'
  if (t === 'due soon')      return 'is due soon:'
  if (t === 'overdue')       return 'is overdue:'
  if (t === 'sprint')        return 'sprint update'
  if (t === 'rule')          return 'ran an automation on'
  if (t === 'summary')       return 'sent you a summary'
  return 'updated'
}

// Due state is the one colored element a row may carry (it's data, not
// chrome). Raw type keys, same reason as getActionText: the tab-filter
// buckets collapse due-soon/overdue together, but the chip must not.
function dueChip(n) {
  const t = (n.notification_type || '').toLowerCase()
  if (t === 'due soon') return { label: 'Due soon', cls: 'bg-warning-soft text-warning-soft-foreground' }
  if (t === 'overdue')  return { label: 'Overdue',  cls: 'bg-danger-soft text-danger-soft-foreground' }
  return null
}

function stripHtml(text) {
  if (!text) return ''
  return text.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
}

// Show the message only when it adds info beyond the title line.
function messageSnippet(n) {
  const msg = stripHtml(n.message).trim()
  if (!msg) return ''
  const title = (n.task_title || '').trim()
  if (!title) return msg
  const idx = msg.toLowerCase().indexOf(title.toLowerCase())
  if (idx === -1) return msg              // no overlap — show as-is
  if (idx === 0) return ''                // msg IS just the title — pure duplicate
  // Due/overdue reminders compose "<key> is overdue (due <date>): <title>" —
  // the title trails the real new information (key + date), not the whole
  // string, so an exact-match check missed it and printed the title twice.
  // Keep the part before the title, drop the redundant tail.
  return msg.slice(0, idx).replace(/[:\-–]\s*$/, '').trim()
}

function projectLabel(projectName) {
  if (!projectName) return ''
  return store.projects.find(p => p.name === projectName)?.project_name || projectName
}

function fmtRel(d) {
  if (!d) return ''
  const m = Math.floor((Date.now() - new Date(d)) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const days = Math.floor(h / 24)
  if (days < 7) return `${days}d ago`
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// ─── Per-type action matrix (§3 of the spec — be honest about capabilities:
// no approval workflow exists in BP, so only real actions are ever offered).
function actionsFor(n) {
  const t = (n.notification_type || '').toLowerCase()
  if (t === 'comment' || t === 'mention') {
    return { primary: 'reply', secondary: 'view', kebabUnread: true, kebabReadOnly: false, kebabProject: true }
  }
  if (['assignment', 'unassigned', 'status change', 'due soon', 'overdue'].includes(t)) {
    return { primary: 'view', secondary: null, kebabUnread: true, kebabReadOnly: false, kebabProject: true }
  }
  // rule / summary / sprint / other — no per-type capability beyond navigation
  return {
    primary: n.task ? 'view' : 'project',
    secondary: null,
    kebabUnread: false,
    kebabReadOnly: true,
    kebabProject: false,
  }
}
const actionsByName = computed(() => {
  const map = {}
  for (const n of notifications.value) map[n.name] = actionsFor(n)
  return map
})
function actionLabel(key) {
  if (key === 'reply')   return 'Reply'
  if (key === 'view')    return 'View task'
  if (key === 'project') return 'Open project'
  return ''
}
function runAction(n, key) {
  if (key === 'reply')   { openReply(n); return }
  if (key === 'view')    { openNotification(n); return }
  if (key === 'project') { openProjectFor(n); return }
}

// Read+old(>7d) notifications drop their action row — keeps "Earlier" compact.
// The kebab menu stays reachable regardless.
function showActionRow(n) {
  if (!n.is_read) return true
  const days = (Date.now() - new Date(n.creation).getTime()) / 86400000
  return days <= 7
}

async function fetchNotifications(append = false) {
  loading.value = true
  try {
    const offset = append ? notifications.value.length : 0
    const res = await getNotifications(PAGE_SIZE, offset, false, dateFilter.value)
    const incoming = res.notifications || []
    if (append) {
      notifications.value.push(...incoming)
    } else {
      notifications.value = incoming
    }
    unreadCount.value   = res.unread_count || 0
    total.value         = res.total || 0
    store.notificationCount = unreadCount.value
  } catch (e) {
    console.error('fetchNotifications:', e)
  } finally {
    loading.value = false
  }
}

function loadMore() {
  fetchNotifications(true)
}

function onDateSelected(v) {
  dateFilter.value = v
  fetchNotifications(false)
}
function clearDateFilter() {
  dateFilter.value = null
  fetchNotifications(false)
}
const dateFilterLabel = computed(() => {
  if (!dateFilter.value) return ''
  const [y, mo, d] = dateFilter.value.split('-').map(Number)
  return new Date(y, mo - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
})

function openSearchBox() {
  searchOpen.value = true
  nextTick(() => searchInputRef.value?.focus())
}
function closeSearchBox() {
  searchOpen.value = false
  searchQuery.value = ''
}

async function markRead(n) {
  try {
    const res = await markNotificationRead(n.name)
    n.is_read = 1
    unreadCount.value = res.unread_count ?? Math.max(0, unreadCount.value - 1)
    store.notificationCount = unreadCount.value
  } catch (e) {
    console.error('markRead:', e)
  }
}

async function markUnread(n) {
  try {
    const res = await markNotificationUnread(n.name)
    n.is_read = 0
    n.read_at = null
    unreadCount.value = res.unread_count ?? unreadCount.value + 1
    store.notificationCount = unreadCount.value
  } catch (e) {
    console.error('markUnread:', e)
  }
}

async function markAllRead() {
  try {
    await markAllNotificationsRead()
    notifications.value.forEach(n => { n.is_read = 1 })
    unreadCount.value = 0
    store.notificationCount = 0
  } catch (e) {
    console.error('markAllRead:', e)
  }
}

function openReply(n) {
  replyOpenFor.value = n.name
  replyText.value = ''
  nextTick(() => replyInputRef.value?.focus())
}
function closeReply() {
  replyOpenFor.value = null
  replyText.value = ''
}
async function submitReply(n) {
  const text = replyText.value.trim()
  if (!text || !n.task || replyLoading.value) return
  replyLoading.value = true
  try {
    await addComment(n.task, text)
    toast.success('Reply posted')
    closeReply()
    if (!n.is_read) await markRead(n)
  } catch (e) {
    console.error('submitReply:', e)
    toast.error('Failed to post reply')
    // input stays populated so the user doesn't lose the draft
  } finally {
    replyLoading.value = false
  }
}

function openProjectFor(n) {
  const project = n.project ? store.projects.find(p => p.name === n.project) : null
  if (!project) return
  store.toggleNotifDrawer(false)
  router.push(store.projectLanding(project.key))
}

async function openNotification(n) {
  if (!n.is_read) await markRead(n)
  const project = n.project ? store.projects.find(p => p.name === n.project) : null
  if (n.task && project) {
    // Open the task in its project board.
    store.toggleNotifDrawer(false)
    if (!router.currentRoute.value.path.includes(`/workspace/${project.key}`)) {
      await router.push(store.projectLanding(project.key))
    }
    setTimeout(() => store.openTaskDetail(n.task), 80)
  } else if (project) {
    // No task — fall back to the project's default view so the click always lands somewhere.
    store.toggleNotifDrawer(false)
    router.push(store.projectLanding(project.key))
  }
}

watch(showNotifDrawer, (open) => {
  if (open) {
    if (!store.projects.length) store.fetchProjects().catch(() => {})
    searchQuery.value = ''
    searchOpen.value = false
    activeFilter.value = 'all'
    dateFilter.value = null
    replyOpenFor.value = null
    fetchNotifications(false)
  }
})
</script>

<style scoped>
/* Segmented filter — the composition-law recipe (reference: Gantt toolbar
   .gt-seg): filled track, lifted active segment, no borders. */
.nd-seg {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: var(--surface-secondary);
  border-radius: var(--radius-lg);
  padding: 2px;
}
.nd-seg-btn {
  height: 24px;
  padding: 0 10px;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--muted);
  background: transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: background .12s, color .12s;
}
.nd-seg-btn:hover { color: var(--foreground); }
.nd-seg-btn.on {
  background: var(--surface);
  color: var(--foreground);
  font-weight: var(--font-semibold);
  box-shadow: var(--shadow-xs);
}

/* Date filter trigger — ghost icon button that grows a clearable chip label. */
.nd-icon-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 8px;
  border-radius: var(--radius-md);
  font-size:var(--text-sm);
  font-weight: 500;
  color: var(--muted);
  background: transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: background-color .12s, color .12s;
}
.nd-icon-btn:hover,
.nd-icon-btn.on { background: var(--surface-secondary); color: var(--foreground); }
.nd-icon-btn.active { background: var(--accent-soft); color: var(--accent-soft-foreground); }
.nd-date-chip-x {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  margin-left: 1px;
}
.nd-date-chip-x:hover { color: var(--danger); }

.nd-search-input {
  height: 28px;
  width: 160px;
  padding: 0 10px;
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
  border: 1px solid transparent;
  font-size:var(--text-sm);
  color: var(--foreground);
  outline: none;
}
.nd-search-input:focus { border-color: var(--accent); background: var(--surface); }
.nd-search-input::placeholder { color: var(--muted); }

/* Flat list rows, not stacked bordered cards (that reads as a Bootstrap
   list-group). Separation is a hairline between consecutive rows within a
   date group — never a border wrapping each row — plus a background tint on
   hover; unread is carried by the dot + full-strength ink only. */
.nd-row {
  border-radius: var(--radius-md);
  transition: background-color .12s ease-out;
}
.nd-row:hover { background: var(--surface-hover); }
.nd-row + .nd-row { border-top: 1px solid var(--separator); }

.nd-dot {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  margin-top: 7px;
  background: transparent;
}
.nd-dot.on { background: var(--accent); }

.nd-sep {
  height: 1px;
  background: var(--separator);
  margin-top: 10px;
}

.nd-btn {
  height: 26px;
  padding: 0 10px;
  border-radius: var(--radius-md);
  font-size:var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: background-color .12s, color .12s;
}
.nd-btn-primary { background: var(--accent-soft); color: var(--accent-soft-foreground); }
.nd-btn-primary:hover { background: var(--accent-soft-hover); }
.nd-btn-ghost { background: transparent; color: var(--muted); }
.nd-btn-ghost:hover { background: var(--surface-secondary); color: var(--foreground); }

.nd-reply-input {
  width: 100%;
  height: 30px;
  padding: 0 10px;
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
  border: 1px solid transparent;
  font-size:var(--text-sm);
  color: var(--foreground);
  outline: none;
}
.nd-reply-input:focus { border-color: var(--accent); background: var(--surface); }
.nd-reply-input:disabled { opacity: 0.6; }

.nd-footer-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 32px;
  border-radius: var(--radius-md);
  font-size:var(--text-sm);
  font-weight: 500;
  color: var(--muted);
  transition: background-color .12s, color .12s;
}
.nd-footer-btn:hover { background: var(--surface-secondary); color: var(--foreground); }
.nd-footer-btn:disabled { pointer-events: none; }
</style>
