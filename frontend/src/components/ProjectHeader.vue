<template>
  <div class="relative shrink-0 bg-overlay border-b border-border font-sans antialiased">

    <div class="flex lg:hidden items-center justify-between h-12 px-4 border-b border-separator">
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <div class="w-5 h-5 rounded flex items-center justify-center text-white text-micro font-bold shrink-0" :style="{ background: projectColor }">
          {{ projectKey?.slice(0,2).toUpperCase() }}
        </div>
        <span class="text-sm font-semibold text-foreground truncate">{{ currentProject?.project_name || projectKey }}</span>
      </div>
      <button
        class="w-8 h-8 flex items-center justify-center rounded-md text-muted hover:bg-default hover:text-foreground transition-colors"
        @click="store.showCreateTask = true"
      >
        <Plus :size="18" :stroke-width="2" />
      </button>
    </div>

    <div class="hidden lg:block">

      <div class="flex items-center justify-between px-5 pt-4 pb-3 gap-4">

        <div class="flex flex-col gap-0.5 min-w-0">
          <div class="flex items-center gap-1.5">
            <button class="text-sm text-muted hover:text-foreground font-medium transition-colors" @click="router.push('/workspace')">Projects</button>
            <ChevronRight :size="12" class="text-muted shrink-0" />
            <span class="text-xs text-muted font-medium truncate">{{ projectKey  }}</span>
          </div>
          <div class="flex items-center gap-2 min-w-0">
            <h1 class="text-md font-semibold text-foreground truncate max-w-[480px]">
              {{ currentProject?.project_name || projectKey }}
            </h1>
            <button
              v-if="pipelineSource"
              type="button"
              @click="openPipelineSource"
              class="inline-flex items-center gap-1 text-xs font-semibold px-1.5 py-0.5 rounded
                     bg-[var(--surface-secondary)] text-muted hover:text-foreground shrink-0 transition-colors"
              :title="`Created from ${pipelineSource.typeLabel} ${pipelineSource.name}`"
            >
              <component :is="pipelineSource.icon" :size="10" :stroke-width="2" /> From {{ pipelineSource.name }}
            </button>
          </div>
        </div>

        <div class="flex items-center gap-1 shrink-0">

          <button class="w-8 h-8 flex items-center justify-center rounded-md text-muted hover:bg-default hover:text-muted transition-colors" title="Search issues (⌘K)" @click="emit('open-search')">
            <Search :size="16" :stroke-width="1.75" />
          </button>

          <div class="w-[1px] h-4 bg-default mx-1 shrink-0"/>

          <button class="w-8 h-8 flex items-center justify-center rounded-md text-muted hover:bg-default hover:text-muted transition-colors" @click="shareOpen = true" title="Share">
            <Share2 :size="16" :stroke-width="1.75" />
          </button>

          <div class="relative" ref="moreWrapRef">
            <button class="w-8 h-8 flex items-center justify-center rounded-md text-muted hover:bg-default hover:text-muted transition-colors" @click="moreOpen = !moreOpen" title="More">
              <MoreHorizontal :size="16" :stroke-width="1.75" />
            </button>

            <Transition
              enter-active-class="transition duration-100 ease-out"
              enter-from-class="transform scale-95 opacity-0"
              enter-to-class="transform scale-100 opacity-100"
              leave-active-class="transition duration-75 ease-in"
              leave-from-class="transform scale-100 opacity-100"
              leave-to-class="transform scale-95 opacity-0"
            >
              <div v-if="moreOpen" class="absolute top-[calc(100%+6px)] right-0 z-50 w-44 bg-overlay border border-border rounded-md shadow-lg p-1.5">
                <button class="flex items-center gap-2.5 w-full px-2.5 py-1.5 text-sm font-medium text-foreground hover:bg-default rounded-md transition-colors" @click="router.push(`/workspace/${projectKey}/settings`); moreOpen=false">
                  <Settings :size="14" class="text-muted" /> Settings
                </button>
                <button class="flex items-center gap-2.5 w-full px-2.5 py-1.5 text-sm font-medium text-foreground hover:bg-default rounded-md transition-colors" @click="copyLink">
                  <Copy :size="14" class="text-muted" /> Copy link
                </button>
                <div class="h-[1px] bg-default my-1"/>
                <button class="flex items-center gap-2.5 w-full px-2.5 py-1.5 text-sm font-medium text-foreground hover:bg-default rounded-md transition-colors" @click="exportCsv">
                  <Download :size="14" class="text-muted" /> Export to CSV
                </button>
                <button class="flex items-center gap-2.5 w-full px-2.5 py-1.5 text-sm font-medium text-foreground hover:bg-default rounded-md transition-colors" :class="{ 'opacity-50': !ent.can('exports') }" @click="exportXlsx">
                  <Download :size="14" class="text-muted" /> Export to Excel
                  <Lock v-if="!ent.can('exports')" :size="11" class="text-muted ml-auto" />
                </button>
                <button class="flex items-center gap-2.5 w-full px-2.5 py-1.5 text-sm font-medium text-foreground hover:bg-default rounded-md transition-colors" :class="{ 'opacity-50': !ent.can('exports') }" @click="exportPdf">
                  <Download :size="14" class="text-muted" /> Export to PDF
                  <Lock v-if="!ent.can('exports')" :size="11" class="text-muted ml-auto" />
                </button>
                <div class="h-[1px] bg-default my-1"/>
                <button class="flex items-center gap-2.5 w-full px-2.5 py-1.5 text-sm font-medium text-foreground hover:bg-default rounded-md transition-colors" @click="quickSaveAsTemplate">
                  <FileText :size="14" class="text-muted" /> Save as template…
                </button>
                <div class="h-[1px] bg-default my-1"/>
                <button class="flex items-center gap-2.5 w-full px-2.5 py-1.5 text-sm font-medium text-danger hover:bg-danger-soft rounded-md transition-colors" @click="archiveProject">
                  <Archive :size="14" class="text-danger" /> Archive project
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </div>

      <div class="flex items-center justify-between gap-3 px-5 pb-3">

        <!-- Scrolls (not clips) when the tabs+avatars don't fit — the
             Filter/Display/Views/+New cluster on the right is shrink-0 and
             must never lose space to this side; New in particular is the
             page's one primary action and can't become unreachable. -->
        <div class="flex items-center gap-4 min-w-0 ">
          <div class="flex items-center gap-1 shrink-0">
            <div class="flex items-center bg-default p-0.5 rounded-lg shrink-0">
              <button
                v-for="tab in visibleTabs" :key="tab.value"
                draggable="true"
                class="flex items-center gap-1.5 px-3 h-[26px] text-sm font-medium rounded-sm transition-colors whitespace-nowrap"
                :class="[
                  isActiveTab(tab) ? 'bg-surface text-foreground shadow-xs' : 'text-muted hover:text-foreground',
                  tab.soon ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
                  tabDragClass(tab.value),
                ]"
                @click="!tab.soon && navigate(tab)"
                @dragstart="onTabDragStart($event, tab.value)"
                @dragover.prevent="onTabDragOver($event, tab.value)"
                @drop.prevent="onTabDrop(tab.value)"
                @dragend="onTabDragEnd"
              >
                <component :is="tab.icon" :size="13" :stroke-width="2" class="shrink-0" />
                {{ tab.label }}
                <span v-if="tab.soon" class="text-micro font-bold uppercase tracking-wide bg-surface-secondary text-muted px-1.5 py-0.5 rounded-sm">Soon</span>
                <Lock v-if="tab.locked" :size="10" :stroke-width="2" class="text-muted shrink-0" />
              </button>
            </div>

            <!-- Manage-views actions — deliberately styled and spaced apart
                 from the tab pill above, not glued onto its bg-default
                 background, so they read as separate actions rather than
                 a phantom extra tab. -->
            <Dropdown v-if="availableToAdd.length" placement="bottom-start" :side-offset="4">
              <template #trigger="{ toggle }">
                <IconButton variant="ghost" size="sm" title="Add view" @click="toggle">
                  <Plus :size="14" :stroke-width="2" />
                </IconButton>
              </template>
              <DropdownItem
                v-for="tab in availableToAdd" :key="tab.value"
                @click="enableView(tab.value)"
              >
                <template #startContent><component :is="tab.icon" :size="14" class="text-muted" /></template>
                {{ tab.label }}
              </DropdownItem>
            </Dropdown>

            <Dropdown v-if="overflowTabs.length" placement="bottom-start" :side-offset="4">
              <template #trigger="{ toggle }">
                <IconButton
                  variant="ghost" size="sm"
                  :class="{ 'text-foreground bg-default': overflowTabs.some(isActiveTab) }"
                  title="More views"
                  @click="toggle"
                >
                  <MoreHorizontal :size="15" :stroke-width="2" />
                </IconButton>
              </template>
              <DropdownItem
                v-for="tab in overflowTabs" :key="tab.value"
                :isDisabled="tab.soon"
                @click="!tab.soon && navigate(tab)"
              >
                <template #startContent><component :is="tab.icon" :size="14" class="text-muted" /></template>
                {{ tab.label }}
                <template v-if="tab.locked" #endContent><Lock :size="11" class="text-muted" /></template>
              </DropdownItem>
              <DropdownSeparator />
              <DropdownItem @click="router.push(`/workspace/${projectKey}/settings/views`)">
                <template #startContent><Settings :size="14" class="text-muted" /></template>
                Rearrange views…
              </DropdownItem>
            </Dropdown>
          </div>

          <div v-if="isDataView && uniqueAssignees.length" class="w-[1px] h-4 bg-[var(--separator)] shrink-0"/>

          <div v-if="isDataView && uniqueAssignees.length" class="flex items-center -space-x-1.5 shrink-0">
            <button
              v-for="name in uniqueAssignees.slice(0, 4)" :key="name"
              class="relative w-[26px] h-[26px] rounded-full ring-2 ring-surface hover:z-10 hover:-translate-y-0.5 transition-transform shadow-sm outline-none"
              :class="{ 'ring-offset-1 ring-foreground': store.boardViewState.filterAssignee === name }"
              :title="name"
              @click="store.boardViewState.filterAssignee = store.boardViewState.filterAssignee === name ? null : name"
            >
              <Avatar :name="name" size="xs" class="w-full h-full" />
            </button>
            <span v-if="uniqueAssignees.length > 4" class="relative flex items-center justify-center w-[26px] h-[26px] rounded-full ring-2 ring-surface bg-default text-muted text-micro font-bold shadow-sm z-0">
              +{{ uniqueAssignees.length - 4 }}
            </span>
          </div>
        </div>

        <div class="flex items-center gap-1 shrink-0">

          <div v-if="(isBoard || isList) && activeSprint" class="flex items-center bg-default p-0.5 rounded-lg shrink-0">
            <button
              class="flex items-center h-7 px-2.5 text-sm font-medium rounded-md transition-colors whitespace-nowrap"
              :class="store.boardSprintFilter === 'all' ? 'bg-surface text-foreground shadow-xs' : 'text-muted hover:text-foreground'"
              @click="store.boardSprintFilter = 'all'"
            >All</button>
            <button
              class="flex items-center gap-1.5 h-7 px-2.5 text-sm font-medium rounded-md transition-colors whitespace-nowrap"
              :class="store.boardSprintFilter === 'active_sprint' ? 'bg-surface text-foreground shadow-xs' : 'text-muted hover:text-foreground'"
              @click="store.boardSprintFilter = 'active_sprint'"
            >
              <Play :size="10" :stroke-width="2.5" />
              {{ activeSprint.sprint_name }}
            </button>
          </div>

          <div v-if="(isBoard || isList) && activeSprint" class="w-px h-4 bg-[var(--separator)] mx-0.5 shrink-0"/>

          <template v-if="usesFilters">
            <FilterDrawer :assignees="uniqueAssignees" />
          </template>

          <template v-if="usesGroupSort">
            <DisplayDrawer />
          </template>

          <template v-if="isBoard">
            <ErpMirrorFieldsButton :schema="mirror.mirrorSchema" :cols="mirror.mirrorCols"
              @add="mirror.addMirrorField" @remove="mirror.removeMirrorField" />
          </template>

          <template v-if="usesSavedViews">
            <SavedViewsDrawer :is-board="isBoard" :has-filters="activeChips.length > 0" />
            <div class="w-px h-4 bg-separator mx-1 shrink-0"/>
          </template>

          <button class="h-[26px] px-2 xl:px-2.5 flex items-center gap-1.5 justify-center rounded-[6px] bg-accent hover:bg-[var(--accent-hover)] text-white transition-colors active:scale-95 shrink-0" @click="store.showCreateTask = true" title="Create task">
            <Plus :size="14" :stroke-width="2.5" />
            <span class="hidden xl:inline text-sm font-medium">New</span>
          </button>
        </div>
      </div>

      <!-- Active-filter chips row — only rendered when a filter is set, so it
           costs nothing on the common empty-filter path. -->
      <div v-if="usesFilters && activeChips.length" class="flex items-center gap-1.5 px-5 pb-2.5 flex-wrap">
        <Chip
          v-for="c in activeChips" :key="c.key"
          color="accent" variant="soft" size="md" is-closeable
          @close="store.boardViewState[c.key] = null"
        >{{ c.label }}</Chip>
        <button class="text-sm font-medium text-muted hover:text-danger transition-colors ml-0.5" @click="clearAll">Clear all</button>
      </div>
    </div>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="transform translate-y-2 opacity-0"
      enter-to-class="transform translate-y-0 opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="transform translate-y-0 opacity-100"
      leave-to-class="transform translate-y-2 opacity-0"
    >
      <div v-if="copyToast" class="absolute -bottom-10 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-3 py-1.5 bg-success text-success-foreground text-sm font-medium rounded-md shadow-lg z-50 whitespace-nowrap">
        <Check :size="14" :stroke-width="2.5" /> Copied
      </div>
    </Transition>
  </div>

  <!-- Share dialog -->
  <ShareDialog v-if="currentProject" v-model="shareOpen" :project="currentProject.name" />
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import ShareDialog from '@/components/ShareDialog.vue'
import FilterDrawer from '@/components/board/FilterDrawer.vue'
import DisplayDrawer from '@/components/board/DisplayDrawer.vue'
import SavedViewsDrawer from '@/components/board/SavedViewsDrawer.vue'
import ErpMirrorFieldsButton from '@/components/ErpMirrorFieldsButton.vue'
import { useMirrorColumnsStore } from '@/stores/mirrorColumns.js'
import { Avatar, Chip, IconButton, Dropdown, DropdownItem, DropdownSeparator } from '@/ui'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useEntitlementsStore } from '@/stores/entitlements'
import { toast } from 'vue-sonner'
import {
  Plus, ChevronRight, Share2, MoreHorizontal,
  Settings, Copy, Archive, Search, Check,
  Play, Download,
  LayoutDashboard, Kanban, List, ListTodo, Paperclip, GanttChart,
  Banknote, Lock, NotebookText, PenTool, FileText, Target, UserPlus,
} from 'lucide-vue-next'
import { saveProjectAsTemplate, updateProjectGeneral, ensureErpDocAccess } from '@/utils/api'
import { promptDialog, confirmDialog } from '@/composables/useConfirmDialog'

const route  = useRoute()
const router = useRouter()
const store  = useProjectStore()
const ent    = useEntitlementsStore()

// ERP mirror fields — Kanban board only (see mirrorColumns.js for why List
// and Gantt don't use this: List has its own separate mirror-column system
// already, Gantt has none). Board.vue's own onMounted loads schema/prefs —
// this button is only ever visible while Board.vue is mounted (v-if="isBoard"
// above), so that load is a reliable precondition here too.
const mirror = useMirrorColumnsStore()
const emit   = defineEmits(['open-search'])

const moreOpen      = ref(false)
const moreWrapRef   = ref(null)
const copyToast     = ref(false)
const shareOpen     = ref(false)

const projectKey     = computed(() => route.params.key)
const currentProject = computed(() => store.projects.find(p => p.key === projectKey.value))

// A project has at most one pipeline origin — checked in pipeline order
// (a Quotation implies the Opportunity/Lead it came from already converted).
const pipelineSource = computed(() => {
  const p = currentProject.value
  if (!p) return null
  if (p.source_sales_order) return { name: p.source_sales_order, typeLabel: 'Sales Order', doctype: 'Sales Order', href: `/app/sales-order/${p.source_sales_order}`, icon: Banknote }
  if (p.source_quotation)   return { name: p.source_quotation,   typeLabel: 'Quotation',   doctype: 'Quotation',   href: `/app/quotation/${p.source_quotation}`,     icon: Banknote }
  if (p.source_opportunity) return { name: p.source_opportunity, typeLabel: 'Opportunity', doctype: 'Opportunity', href: `/app/opportunity/${p.source_opportunity}`, icon: Target }
  if (p.source_lead)        return { name: p.source_lead,        typeLabel: 'Lead',        doctype: 'Lead',        href: `/app/lead/${p.source_lead}`,               icon: UserPlus }
  return null
})

// SPA members hold zero ERPNext DocPerm by design — a raw desk link 403s
// unless the backend first grants a per-document share (tenancy-checked
// against this project's own source_* fields). See useErpDocOpener.js.
async function openPipelineSource() {
  const src = pipelineSource.value
  if (!src) return
  const win = window.open('', '_blank', 'noopener')
  try {
    await ensureErpDocAccess(src.doctype, src.name)
    if (win) win.location = src.href
  } catch (e) {
    if (win) win.close()
    throw e
  }
}

const COLORS = ['#225DFB','#7C3AED','#059669','#DC2626','#D97706','#0891B2','#BE185D','#9333EA']
const projectColor = computed(() => {
  const key = projectKey.value || ''
  let h = 0
  for (let i = 0; i < key.length; i++) h = key.charCodeAt(i) + ((h << 5) - h)
  return COLORS[Math.abs(h) % COLORS.length]
})

const isBoard      = computed(() => route.path.includes('/board'))
const activeSprint = computed(() => store.sprints.find(s => s.status === 'Active') || null)

// Per-view control gating (audited against what each page actually consumes):
//   Board  → filters + group + sort + sprint + saved views
//   List   → filters + group + sort + saved views
//   Gantt  → filters only (no group/sort)
//   Backlog/Summary/Files → none
const isList    = computed(() => route.path.includes('/list'))
const isGantt   = computed(() => route.path.includes('/gantt'))
const usesFilters   = computed(() => isBoard.value || isList.value || isGantt.value)
const usesGroupSort = computed(() => isBoard.value || isList.value)
const usesSavedViews = computed(() => isBoard.value || isList.value)
const isDataView = computed(() => usesFilters.value) // assignee strip / generic gate

const uniqueAssignees = computed(() => {
  const names = new Set()
  Object.values(store.board || {}).flat().forEach(issue =>
    (issue.assignees || []).forEach(a => { if (a.full_name) names.add(a.full_name) })
  )
  return [...names].sort()
})

// Row-3 dismissible chips — one per active filter dimension. Group/Sort
// non-default state is surfaced by the Display button's own badge instead
// (it isn't a "filter" — nothing gets excluded from the list by it).
const activeChips = computed(() => {
  const v = store.boardViewState
  const chips = []
  if (v.filterType)     chips.push({ key: 'filterType',     label: `Type: ${v.filterType}` })
  if (v.filterLabel)    chips.push({ key: 'filterLabel',    label: `Label: ${v.filterLabel}` })
  if (v.filterAssignee) chips.push({ key: 'filterAssignee', label: `Assignee: ${v.filterAssignee.split(' ')[0]}` })
  if (v.filterPriority) chips.push({ key: 'filterPriority', label: `Priority: ${v.filterPriority}` })
  return chips
})

// Quick save — the full drawer (description/category/include
// toggles) lives in Project Settings → General; this is the fast path for
// "just snapshot it now with sensible defaults" from the board itself.
async function quickSaveAsTemplate() {
  moreOpen.value = false
  const name = await promptDialog({ title: 'Template name', inputLabel: 'Name', defaultValue: `${store.currentProject?.project_name || 'Project'} template` })
  if (!name || !name.trim()) return
  try {
    await saveProjectAsTemplate({
      project: store.currentProject.name,
      template_name: name.trim(),
      include_tasks: 1, include_custom_fields: 1, include_automations: 1,
    })
    toast.success(`Saved as template "${name.trim()}"`)
  } catch (e) {
    toast.error(e.message || 'Failed to save template')
  }
}

function clearAll() {
  store.boardViewState.filterAssignee = null
  store.boardViewState.filterPriority = null
  store.boardViewState.filterType     = null
  store.boardViewState.filterLabel    = null
  store.boardViewState.search         = ''
  store.boardSortBy = 'board_order'
}

// View tabs follow the project's enabled_views (set from its template at
// creation). 'summary' and 'files' are structural and always shown.
// Views without a built page yet are flagged `soon` so the tab shows but
// isn't navigable (no broken route).
const VIEW_TAB_DEFS = {
  board:    { value: 'board',    label: 'Board',    icon: Kanban },
  list:     { value: 'list',     label: 'List',     icon: List },
  backlog:  { value: 'backlog',  label: 'Backlog',  icon: ListTodo },
  gantt:    { value: 'gantt',    label: 'Gantt',    icon: GanttChart },
  notes:    { value: 'notes',    label: 'Notes',    icon: NotebookText },
  draw:     { value: 'draw',     label: 'Draw',      icon: PenTool },
}
const VIEW_ORDER = ['board', 'list', 'backlog', 'gantt', 'notes', 'draw']

// Views gated by a workspace admin kill switch — both the
// per-project enabled_views membership AND this flag must pass.
const WORKSPACE_GATED_VIEWS = new Set(['gantt', 'notes', 'draw'])

// Views ALSO gated by a paid tier, on top of the workspace switch above — an
// admin's kill switch hides the tab outright; a tier lock keeps it visible
// with a lock badge so the upsell is discoverable (same treatment as Money).
const TIER_GATED_VIEWS = { draw: 'draw' }

const tabs = computed(() => {
  const enabled = currentProject.value?.enabled_views
  const views = Array.isArray(enabled) && enabled.length ? enabled : ['board', 'list', 'backlog', 'gantt']
  const viewTabs = VIEW_ORDER
    // Workspace admin switched a view off → the tab disappears entirely
    // (an admin's own choice, unlike the tier lock below which upsells).
    .filter(v => views.includes(v) && (!WORKSPACE_GATED_VIEWS.has(v) || ent.canWorkspace(v)))
    .map(v => TIER_GATED_VIEWS[v]
      ? { ...VIEW_TAB_DEFS[v], locked: !ent.can(TIER_GATED_VIEWS[v]) }
      : VIEW_TAB_DEFS[v])
  const out = [
    { value: 'summary', label: 'Summary', icon: LayoutDashboard },
    ...viewTabs,
  ]
  // capability off = hide outright (no lock badge; this isn't a
  // paid-tier upsell, an admin switched it off for this role).
  if (store.hasCapability('view_files'))
    out.push({ value: 'files', label: 'Files', icon: Paperclip })
  if (ent.canWorkspace('money_tab') && store.hasCapability('view_money'))
    out.push({ value: 'money', label: 'Money', icon: Banknote, locked: !ent.can('profitability') })
  return out
})
const isActiveTab = (tab) => route.path.includes(`/${tab.value}`)
const navigate    = (tab) => router.push(`/workspace/${projectKey.value}/${tab.value}`)

// Order is configured in Project Settings → Views. Unset (the common case —
// nothing customized yet) means NO reordering: keep tabs.value's natural
// order (summary, then VIEW_ORDER, then files/money) so a project with e.g.
// Backlog enabled doesn't get it silently shuffled to the end just because
// it wasn't in some hardcoded default list. Hard-capped at 6 inline either
// way — the rest always fall to the overflow dropdown, never clipped.
const MAX_INLINE_TABS = 6
const orderedTabs = computed(() => {
  const pinned = currentProject.value?.pinned_views
  if (!Array.isArray(pinned) || !pinned.length) return tabs.value
  const byValue = Object.fromEntries(tabs.value.map(t => [t.value, t]))
  const pinnedTabs = pinned.map(v => byValue[v]).filter(Boolean)
  const rest = tabs.value.filter(t => !pinned.includes(t.value))
  return [...pinnedTabs, ...rest]
})
const visibleTabs  = computed(() => orderedTabs.value.slice(0, MAX_INLINE_TABS))
const overflowTabs = computed(() => orderedTabs.value.slice(MAX_INLINE_TABS))

function _patchCurrentProject(fields) {
  const p = store.projects.find(p => p.key === projectKey.value)
  if (p) Object.assign(p, fields)
}

// ── Tab drag-reorder (drag directly in the header strip) ──
const _dragTab  = ref(null)
const _dropTab  = ref(null)
const _dropSide = ref('left')
function onTabDragStart(e, value) {
  _dragTab.value = value
  e.dataTransfer.effectAllowed = 'move'
}
function onTabDragOver(e, value) {
  if (!_dragTab.value || value === _dragTab.value) { _dropTab.value = null; return }
  const r = e.currentTarget.getBoundingClientRect()
  _dropSide.value = (e.clientX - r.left) < r.width / 2 ? 'left' : 'right'
  _dropTab.value = value
}
function onTabDragEnd() { _dragTab.value = null; _dropTab.value = null }
async function onTabDrop(value) {
  const from = _dragTab.value, side = _dropSide.value
  onTabDragEnd()
  if (!from || from === value || !currentProject.value) return
  const arr = orderedTabs.value.map(t => t.value)
  arr.splice(arr.indexOf(from), 1)
  const idx = arr.indexOf(value)
  arr.splice(side === 'left' ? idx : idx + 1, 0, from)
  try {
    const data = await updateProjectGeneral(currentProject.value.name, { pinned_views: arr })
    _patchCurrentProject({ pinned_views: data.pinned_views || arr })
  } catch (e) {
    toast.error(e.message || 'Failed to save view order')
  }
}
function tabDragClass(value) {
  return {
    'opacity-40': _dragTab.value === value,
    "shadow-[inset_2px_0_0_var(--accent)]":  _dropTab.value === value && _dropSide.value === 'left',
    "shadow-[inset_-2px_0_0_var(--accent)]": _dropTab.value === value && _dropSide.value === 'right',
  }
}

// ── Add a view not yet enabled on this project ──
const availableToAdd = computed(() => {
  const enabled = new Set(currentProject.value?.enabled_views || [])
  return VIEW_ORDER.filter(v => !enabled.has(v)).map(v => VIEW_TAB_DEFS[v])
})
async function enableView(viewKey) {
  if (!currentProject.value) return
  const next = [...(currentProject.value.enabled_views || []), viewKey]
  try {
    const data = await updateProjectGeneral(currentProject.value.name, { enabled_views: next })
    _patchCurrentProject({ enabled_views: data.enabled_views || next })
    toast.success(`${VIEW_TAB_DEFS[viewKey].label} view added`)
  } catch (e) {
    toast.error(e.message || 'Failed to add view')
  }
}

function copyLink() {
  navigator.clipboard.writeText(window.location.href)
  moreOpen.value = false
  copyToast.value = true
  setTimeout(() => { copyToast.value = false }, 2000)
}

// ── Export (moved here from ListView's own toolbar — project-level action,
// not tied to whichever view you're currently on). Excel/PDF are already
// server-rendered by the gateway from the project as a whole, so they never
// needed ListView's local column/sort state. CSV was the one export that
// used to read that state directly (exactly the columns/order you'd
// customized in List) — pulled from the store's full board instead so it
// works from any view; trades that per-view customization for being
// reachable everywhere, which is what was asked for here.
function sprintNameFor(id) { return store.sprints?.find(s => s.name === id)?.sprint_name || id }
function epicNameFor(id) {
  const ep = store.epics
  if (Array.isArray(ep)) return ep.find(e => e.name === id)?.title || id
  if (ep && typeof ep === 'object') {
    for (const arr of Object.values(ep)) {
      const found = (Array.isArray(arr) ? arr : []).find(e => e.name === id)
      if (found) return found.title || id
    }
  }
  return id
}
function exportCsv() {
  moreOpen.value = false
  const esc = v => `"${String(v ?? '').replace(/"/g, '""')}"`
  const header = ['Key', 'Title', 'Status', 'Priority', 'Type', 'Assignees', 'Due Date', 'Sprint', 'Epic', 'Story Points']
  const rows = [header.map(esc).join(',')]
  for (const issue of Object.values(store.board || {}).flat()) {
    if (!issue) continue
    rows.push([
      issue.task_key, issue.title, issue.status, issue.priority || '', issue.task_type || '',
      (issue.assignees || []).map(a => a.full_name).join('; '),
      issue.due_date || '',
      issue.sprint ? sprintNameFor(issue.sprint) : '',
      issue.epic ? epicNameFor(issue.epic) : '',
      issue.story_points ?? '',
    ].map(esc).join(','))
  }
  const blob = new Blob([rows.join('\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${currentProject.value?.key || 'issues'}_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}
function exportXlsx() {
  moreOpen.value = false
  if (!ent.can('exports')) { toast.error('Excel export is available on any paid plan'); return }
  const base = window.__BP_BRIDGE_URL__ || ''
  if (!base) { toast.error('Export requires the Batch Gateway'); return }
  if (!projectKey.value) return
  window.open(`${base}/v1/exports/${projectKey.value}/xlsx`, '_blank')
}
function exportPdf() {
  moreOpen.value = false
  if (!ent.can('exports')) { toast.error('PDF export is available on any paid plan'); return }
  const base = window.__BP_BRIDGE_URL__ || ''
  if (!base) { toast.error('Export requires the Batch Gateway'); return }
  if (!projectKey.value) return
  window.open(`${base}/v1/exports/${projectKey.value}/pdf`, '_blank')
}

async function archiveProject() {
  if (!await confirmDialog(`Archive "${currentProject.value?.project_name}"?`, { danger: true })) return
  moreOpen.value = false
  try {
    const { updateProjectGeneral } = await import('@/utils/api.js')
    await updateProjectGeneral(currentProject.value.name, { status: 'Archived' })
    router.push('/workspace')
  } catch (e) { console.error(e) }
}

function onOutsideClick(e) {
  if (!moreWrapRef.value?.contains(e.target)) moreOpen.value = false
}
onMounted(() => document.addEventListener('mousedown', onOutsideClick))
onUnmounted(() => document.removeEventListener('mousedown', onOutsideClick))
</script>
