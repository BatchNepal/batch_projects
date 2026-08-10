<template>
  <div class="h-full overflow-y-auto bg-[--surface]">
    <!-- Header band -->
    <div class="border-b border-[--border] bg-[--surface]">
      <div class="max-w-[1600px] mx-auto px-4 sm:px-6 pt-6 pb-4">
        <header class="flex items-start justify-between gap-3">
          <div class="flex items-start gap-3 min-w-0">
            <span class="size-10 rounded-lg grid place-items-center shrink-0"
                  style="background: var(--accent-soft); color: var(--accent-soft-foreground);">
              <Icon :icon="LayoutDashboard" :size="20" />
            </span>
            <div class="min-w-0">
              <h1 class="text-xl font-semibold text-[--foreground] leading-7 tracking-[-0.01em]">Dashboards</h1>
              <p class="hidden sm:block text-base text-[--muted] mt-0.5 max-w-xl">
                Live, glanceable views across your projects — who has what, what's running, at a glance.
              </p>
            </div>
          </div>
          <Button color="primary" size="sm" class="shrink-0" @click="openCreate()">
            <template #startContent><Icon :icon="Plus" :size="16" /></template>
            <span class="hidden sm:inline">New dashboard</span>
            <span class="sm:hidden">New</span>
          </Button>
        </header>

        <!-- HeroUI tabs -->
        <div class="mt-4">
          <Tabs v-model="activeTab" variant="underline" :tabs="TABS" />
        </div>
      </div>
    </div>

    <div class="max-w-[1600px] mx-auto px-4 sm:px-6 py-6">
      <!-- Create a dashboard: template tiles -->
      <section class="mb-7">
        <button type="button" class="flex items-center gap-1.5 text-base font-semibold text-[--foreground] mb-3"
          @click="showTemplates = !showTemplates">
          <Icon :icon="showTemplates ? ChevronDown : ChevronRight" :size="16" class="text-[--muted]" />
          Create a dashboard
        </button>
        <div v-if="showTemplates" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 items-stretch">
          <button v-for="t in TEMPLATES" :key="t.key" type="button"
            class="group flex flex-col h-full text-left bg-[--surface] border border-[--border] rounded-lg p-3.5 shadow-sm transform-gpu transition-[transform,box-shadow,border-color] duration-150 hover:shadow-md hover:-translate-y-0.5 hover:border-[--accent]"
            @click="openCreate(t)">
            <span class="size-9 rounded-lg grid place-items-center mb-2.5 shrink-0" :style="{ background: t.color + '1F', color: t.color }">
              <component :is="t.icon" :size="18" />
            </span>
            <p class="text-sm font-semibold text-[--foreground] leading-tight">{{ t.label }}</p>
            <p class="text-xs text-[--muted] mt-1 leading-snug line-clamp-2 min-h-[30px]">{{ t.desc }}</p>
          </button>
        </div>
      </section>

      <!-- Saved dashboards table -->
      <section>
        <div class="flex items-center gap-2 mb-2.5">
          <p class="text-base font-semibold text-[--foreground]">{{ tabHeading }}</p>
          <span class="text-xs text-[--muted] tabular-nums">{{ tableDashboards.length }}</span>
        </div>

        <div v-if="loading" class="py-12 text-center text-base text-[--muted]">Loading…</div>

        <div v-else-if="!tableDashboards.length" class="bg-[--surface] border border-[--border] rounded-lg p-10 flex flex-col items-center text-center shadow-sm">
          <span class="size-12 rounded-lg grid place-items-center mb-4" style="background: var(--accent-soft); color: var(--accent-soft-foreground);">
            <LayoutDashboard :size="24" />
          </span>
          <p class="text-md font-semibold text-[--foreground] mb-1">{{ emptyHeading }}</p>
          <p class="text-base text-[--muted] max-w-sm leading-relaxed mb-5">Pick a template above, or build one from scratch.</p>
          <Button color="primary" size="sm" @click="openCreate()">
            <template #startContent><Icon :icon="Plus" :size="16" /></template>Create dashboard
          </Button>
        </div>

        <div v-else class="border border-[--border] rounded-lg overflow-hidden bg-[--surface] shadow-sm">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="text-xs font-semibold uppercase tracking-wide text-[--muted] bg-[--surface-secondary]/40 border-b border-[--border]">
                <th class="px-4 py-2.5">Name</th>
                <th class="px-3 py-2.5 hidden sm:table-cell">Scope</th>
                <th class="px-3 py-2.5 hidden lg:table-cell">Last updated</th>
                <th class="px-3 py-2.5 w-12"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in tableDashboards" :key="d.id"
                class="group border-b border-[--border] last:border-0 cursor-pointer hover:bg-[--surface-secondary] transition-colors"
                @click="open(d.id)">
                <td class="px-4 py-2.5">
                  <div class="flex items-center gap-2.5 min-w-0">
                    <span class="size-7 rounded-md grid place-items-center shrink-0" :style="{ background: scopeColor(d) + '1F', color: scopeColor(d) }">
                      <component :is="iconFor(d.icon)" :size="14" />
                    </span>
                    <div class="min-w-0">
                      <p class="text-base font-medium text-[--foreground] flex items-center gap-1.5 min-w-0">
                        <span class="truncate">{{ d.name }}</span>
                        <Star v-if="d.starred" :size="11" class="text-warning shrink-0" fill="currentColor" />
                        <Pin v-if="d.pinned" :size="11" class="text-[--accent] shrink-0" title="Pinned to sidebar" />
                        <Users v-if="d.visibility === 'workspace'" :size="11" class="text-[--muted] shrink-0" title="Shared with the workspace" />
                        <!-- A private dashboard belonging to someone else never reaches
                             this list at all (filtered server-side in list_dashboards)
                             — so "private" here always means "private and mine." -->
                        <Lock v-else :size="11" class="text-[--muted] shrink-0" title="Private — only you can see this" />
                      </p>
                      <p class="text-xs text-[--muted]">{{ (d.widgets || []).length }} widget{{ (d.widgets || []).length !== 1 ? 's' : '' }}</p>
                    </div>
                  </div>
                </td>
                <td class="px-3 py-2.5 hidden sm:table-cell">
                  <span class="inline-flex items-center gap-1.5 text-sm text-[--foreground]">
                    <span class="size-1.5 rounded-full shrink-0" :style="{ background: scopeColor(d) }" />{{ scopeLabel(d) }}
                  </span>
                </td>
                <td class="px-3 py-2.5 hidden lg:table-cell text-sm text-[--muted] tabular-nums">{{ fmtDate(d.modified) }}</td>
                <td class="px-3 py-2.5" @click.stop @keydown.stop>
                  <div class="flex items-center justify-end gap-0.5">
                    <button class="w-7 h-7 grid place-items-center rounded-md transition-colors hover:text-warning hover:bg-[--default]"
                      :class="d.starred ? 'text-warning' : 'text-[--muted] opacity-0 group-hover:opacity-100'" title="Star" @click.stop="toggleStar(d)">
                      <Star :size="13" :fill="d.starred ? 'currentColor' : 'none'" />
                    </button>
                    <Dropdown placement="bottom-end" :side-offset="4">
                      <template #trigger="{ open: isOpen, toggle }">
                        <button class="w-7 h-7 grid place-items-center rounded-md transition-colors text-[--muted] hover:bg-[--default] hover:text-[--foreground] opacity-0 group-hover:opacity-100"
                          :class="{ '!opacity-100 bg-[--default] text-[--foreground]': isOpen }" title="More" @click.stop="toggle">
                          <MoreHorizontal :size="14" />
                        </button>
                      </template>
                      <DropdownItem @click="open(d.id)"><template #startContent><ExternalLink :size="14" class="text-[--muted]" /></template>Open</DropdownItem>
                      <DropdownItem @click="openRename(d)"><template #startContent><Pencil :size="14" class="text-[--muted]" /></template>Rename</DropdownItem>
                      <DropdownItem @click="togglePin(d)"><template #startContent><component :is="d.pinned ? PinOff : Pin" :size="14" class="text-[--muted]" /></template>{{ d.pinned ? 'Unpin from sidebar' : 'Pin to sidebar' }}</DropdownItem>
                      <DropdownItem @click="duplicate(d.id)"><template #startContent><Copy :size="14" class="text-[--muted]" /></template>Duplicate</DropdownItem>
                      <DropdownSeparator />
                      <DropdownItem color="danger" @click="askDelete(d)"><template #startContent><Trash2 :size="14" /></template>Delete</DropdownItem>
                    </Dropdown>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- Create / Rename modal -->
    <Modal :open="formOpen" @update:open="v => !v && (formOpen = false)" size="md" radius="lg" hideCloseButton>
      <ModalHeader class="px-5 pt-5">
        <p class="text-md font-semibold text-[--foreground]">{{ editingId ? 'Rename dashboard' : (formTemplate ? formTemplate.label : 'New dashboard') }}</p>
      </ModalHeader>
      <ModalBody class="px-5 py-4 flex flex-col gap-3.5">
        <!-- Icon + color identity -->
        <div class="flex items-center gap-3">
          <span class="size-12 rounded-lg grid place-items-center shrink-0 shadow-sm transition-colors"
            :style="{ background: formColor + '24', color: formColor }">
            <component :is="iconFor(formIcon)" :size="22" />
          </span>
          <div class="flex-1 min-w-0">
            <Input v-model="formName" label="Dashboard name" placeholder="e.g. Team Workload" autofocus @keydown.enter="submitForm" />
          </div>
        </div>

        <!-- Color row -->
        <div>
          <p class="text-sm font-medium text-[--foreground] mb-1.5">Color</p>
          <div class="flex flex-wrap gap-1.5">
            <button v-for="c in COLORS" :key="c" type="button"
              class="size-6 rounded-full grid place-items-center transition-transform hover:scale-110"
              :style="{ background: c }" :title="c" @click="formColor = c">
              <Check v-if="formColor === c" :size="13" class="text-white" :stroke-width="3" />
            </button>
          </div>
        </div>

        <!-- Icon grid -->
        <div>
          <p class="text-sm font-medium text-[--foreground] mb-1.5">Icon</p>
          <div class="grid grid-cols-9 gap-1 max-h-[132px] overflow-y-auto pr-1">
            <button v-for="n in ICON_NAMES" :key="n" type="button"
              class="aspect-square rounded-lg grid place-items-center border transition-colors"
              :class="formIcon === n ? 'border-transparent' : 'border-[--border] text-[--muted] hover:bg-[--surface-secondary]'"
              :style="formIcon === n ? { background: formColor + '24', color: formColor } : {}"
              :title="n" @click="formIcon = n">
              <component :is="iconFor(n)" :size="15" />
            </button>
          </div>
        </div>

        <template v-if="!editingId">
          <!-- Scope: project -->
          <div>
            <p class="text-sm font-medium text-[--foreground] mb-1.5">Project scope</p>
            <Select v-model="formProject" size="sm" fullWidth>
              <SelectItem value="all">All projects (workspace)</SelectItem>
              <SelectItem v-for="p in projects" :key="p.name" :value="p.name">{{ p.project_name }}</SelectItem>
            </Select>
          </div>
          <!-- visibility: private is the free default; sharing with the
               workspace requires the "dashboards" feature (Team+) — same
               pattern as every other gated toggle in the app. -->
          <div class="flex items-center justify-between gap-3 pt-1">
            <div class="min-w-0">
              <p class="text-base font-medium text-[--foreground]">Share with workspace</p>
              <p class="text-sm text-[--muted] mt-0.5">Every member can view it. {{ ent.can('dashboards') ? '' : `Requires the ${ent.requiredPlanFor('dashboards')} plan.` }}</p>
            </div>
            <Switch :model-value="formVisibility === 'workspace'" @update:model-value="v => formVisibility = v ? 'workspace' : 'private'" />
          </div>
        </template>
      </ModalBody>
      <ModalFooter class="px-5 pb-5 justify-end gap-2">
        <Button variant="bordered" size="sm" @click="formOpen = false">Cancel</Button>
        <Button color="primary" size="sm" :isDisabled="!formName.trim() || busy" @click="submitForm">
          {{ editingId ? 'Save' : 'Create' }}
        </Button>
      </ModalFooter>
    </Modal>

    <!-- Delete confirm -->
    <Modal :open="!!deleting" @update:open="v => !v && (deleting = null)" size="sm" radius="lg" hideCloseButton>
      <ModalHeader class="px-5 pt-5"><p class="text-md font-semibold text-[--foreground]">Delete dashboard?</p></ModalHeader>
      <ModalBody class="px-5 py-4">
        <p class="text-base text-[--muted]">"{{ deleting?.name }}" will be permanently removed.</p>
      </ModalBody>
      <ModalFooter class="px-5 pb-5 justify-end gap-2">
        <Button variant="bordered" size="sm" @click="deleting = null">Cancel</Button>
        <Button color="danger" size="sm" @click="confirmDelete">Delete</Button>
      </ModalFooter>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useDashboardsStore, WIDGET_DEFAULTS, DEFAULT_STATUSES } from '@/stores/dashboards'
import { useProjectStore } from '@/stores/project'
import { UpgradeRequiredError, getMembers } from '@/utils/api'
import { toast } from 'vue-sonner'
import { Button, Input, Icon, Select, SelectItem, Switch, Tabs, Modal, ModalHeader, ModalBody, ModalFooter, Dropdown, DropdownItem, DropdownSeparator } from '@/ui'
import { useEntitlementsStore } from '@/stores/entitlements'
import { reportIcon, REPORT_ICON_NAMES, REPORT_COLORS } from '@/utils/reportIcons'
import {
  Plus, MoreHorizontal, ExternalLink, Pencil, Copy, Trash2, Star, Pin, PinOff,
  LayoutDashboard, Users, ChevronDown, ChevronRight, Check, Lock, Columns3,
} from 'lucide-vue-next'

const CAT = { blue: REPORT_COLORS[0], orange: REPORT_COLORS[4], purple: REPORT_COLORS[7] }

// Dashboard templates — deliberately narrow (unlike Report Builder's 6
// templates): these two map directly to the two things this feature was
// actually built for — "who has what" and "what's running." Each template
// is a well-positioned COLLECTION of dedicated column widgets (one per
// person / per status), placed side by side, not one widget internally
// rendering many columns. See ColumnWidget.vue and stores/dashboards.js'
// addWidget(x, y) support.
const COLUMN_W = WIDGET_DEFAULTS.column.w
// Must match DashboardView.vue's <GridLayout col-num> — was a bare `12`
// hardcoded at both call sites below; harmless while WIDGET_DEFAULTS.column.w
// was also 3 (i.e. exactly 12/4), but the col-num 12->48 rescale (see
// stores/dashboards.js) moved that .w to 12, which made `(i * 12) % 12`
// always 0 — every templated column would have landed at x:0, stacked on
// top of each other instead of laid out side by side.
const GRID_COLS = 48
const TEMPLATES = [
  { key: 'blank', label: 'Blank dashboard', desc: 'Start from scratch and add your own widgets.', icon: LayoutDashboard, color: CAT.blue,
    build: async () => {} },
  { key: 'workload', label: 'Team workload', desc: 'One column per person — who has what, at a glance.', icon: Users, color: CAT.orange,
    build: async (id, s, scope) => {
      // get_members() returns a flat array for the org-wide directory
      // (scope 'all', admin-only) but {members, user_list, can_manage} when
      // scoped to a single project — normalize both shapes.
      let people = []
      try {
        const res = await getMembers(scope === 'all' ? null : scope)
        people = Array.isArray(res) ? res : (res.members || [])
      } catch {}
      people = people.filter(m => m.user).slice(0, 12)
      people.forEach((m, i) => {
        const w = s.addWidget(id, 'column', { x: (i * COLUMN_W) % GRID_COLS, y: Math.floor(i * COLUMN_W / GRID_COLS) * WIDGET_DEFAULTS.column.h })
        s.updateWidgetConfig(id, w.id, { title: m.full_name || m.user, filterBy: 'assignee', filterValue: m.user })
      })
    } },
  { key: 'status', label: 'Project status', desc: 'Every open task, grouped by status, across all projects.', icon: Columns3, color: CAT.purple,
    build: async (id, s, scope) => {
      // A single project's own workflow_states are the real, accurate
      // statuses; across the whole workspace different projects can define
      // different states, so there's no one canonical list — fall back to
      // the common default set rather than guessing at every distinct value.
      let statuses = DEFAULT_STATUSES
      if (scope !== 'all') {
        const proj = projects.value.find(p => p.name === scope)
        const ws = (proj?.workflow_states || []).map(st => st.name || st).filter(Boolean)
        if (ws.length) statuses = ws.slice(0, 6)
      }
      statuses.forEach((status, i) => {
        const w = s.addWidget(id, 'column', { x: (i * COLUMN_W) % GRID_COLS, y: Math.floor(i * COLUMN_W / GRID_COLS) * WIDGET_DEFAULTS.column.h })
        s.updateWidgetConfig(id, w.id, { title: status, filterBy: 'status', filterValue: status, statusFilter: 'all' })
      })
    } },
]

function iconFor(name) { return reportIcon(name) }

function fmtDate(s) {
  if (!s) return '—'
  const d = new Date(s.replace(' ', 'T'))
  if (isNaN(d)) return '—'
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

const router = useRouter()
const store = useDashboardsStore()
const projectStore = useProjectStore()
const ent = useEntitlementsStore()
const { dashboards } = storeToRefs(store)
const { projects } = storeToRefs(projectStore)
const loading = ref(true)
const showTemplates = ref(true)

onMounted(async () => {
  await Promise.all([store.load(), projectStore.projects.length ? null : projectStore.fetchProjects().catch(() => {})])
  loading.value = false
})

const activeTab = ref('all')
const starredDashboards = computed(() => dashboards.value.filter(d => d.starred))
const myDashboards = computed(() => dashboards.value.filter(d => d.is_mine))
const sharedDashboards = computed(() => dashboards.value.filter(d => !d.is_mine || d.visibility === 'workspace'))
const TABS = computed(() => [
  { value: 'all',     label: 'All dashboards' },
  { value: 'mine',    label: `My dashboards${myDashboards.value.length ? ' · ' + myDashboards.value.length : ''}` },
  { value: 'shared',  label: `Shared${sharedDashboards.value.length ? ' · ' + sharedDashboards.value.length : ''}` },
  { value: 'starred', label: `Starred${starredDashboards.value.length ? ' · ' + starredDashboards.value.length : ''}` },
])

const projName = (name) => projects.value.find(p => p.name === name)?.project_name || name
function scopeLabel(d) {
  const s = d.scope
  if (!s || s === 'all') return 'Workspace'
  return projName(s)
}
function scopeColor(d) {
  const s = d.scope
  if (!s || s === 'all') return CAT.blue
  return projects.value.find(p => p.name === s)?.project_color || CAT.blue
}

const tabHeading = computed(() => ({
  starred: 'Starred dashboards', mine: 'My dashboards', shared: 'Shared dashboards',
}[activeTab.value] || 'All dashboards'))
const emptyHeading = computed(() => ({
  starred: 'No starred dashboards', mine: 'No dashboards yet', shared: 'No shared dashboards yet',
}[activeTab.value] || 'No dashboards yet'))

const tableDashboards = computed(() => {
  const src = activeTab.value === 'starred' ? starredDashboards.value
    : activeTab.value === 'mine' ? myDashboards.value
    : activeTab.value === 'shared' ? sharedDashboards.value
    : dashboards.value
  return [...src].sort((a, b) => String(b.modified || '').localeCompare(String(a.modified || '')))
})

function open(id) { router.push(`/workspace/dashboards/${id}`) }
function toggleStar(d) { store.updateDashboard(d.id, { starred: !d.starred }) }
function togglePin(d) { store.togglePinned(d.id) }

const ICON_NAMES = REPORT_ICON_NAMES
const COLORS = REPORT_COLORS

const formOpen = ref(false)
const formName = ref('')
const editingId = ref(null)
const formTemplate = ref(null)
const formProject = ref('all')
const formIcon = ref('LayoutDashboard')
const formColor = ref(CAT.blue)
const formVisibility = ref('private')
const busy = ref(false)

const TEMPLATE_ICON = { workload: 'Users', status: 'Columns3', blank: 'LayoutDashboard' }

function openCreate(template = null) {
  editingId.value = null
  formTemplate.value = template
  formName.value = template && template.key !== 'blank' ? template.label : ''
  formProject.value = 'all'
  formVisibility.value = 'private'
  formIcon.value = template ? (TEMPLATE_ICON[template.key] || 'LayoutDashboard') : 'LayoutDashboard'
  formColor.value = template?.color || CAT.blue
  formOpen.value = true
}
function openRename(d) {
  editingId.value = d.id; formTemplate.value = null; formName.value = d.name
  formIcon.value = d.icon || 'LayoutDashboard'
  formColor.value = d.color || CAT.blue
  formOpen.value = true
}

async function submitForm() {
  const name = formName.value.trim()
  if (!name || busy.value) return
  if (editingId.value) {
    store.renameDashboard(editingId.value, name)
    store.updateDashboard(editingId.value, { icon: formIcon.value, color: formColor.value })
    formOpen.value = false
    return
  }
  busy.value = true
  try {
    const scope = formProject.value === 'all' ? 'all' : formProject.value
    const id = await store.createDashboard(name, formIcon.value, {
      scope, visibility: formVisibility.value,
    })
    store.updateDashboard(id, { color: formColor.value })
    if (formTemplate.value?.build) await formTemplate.value.build(id, store, scope)
    formOpen.value = false
    router.push(`/workspace/dashboards/${id}`)
  } catch (e) {
    if (e instanceof UpgradeRequiredError) {
      toast.error(e.message, { action: { label: 'Upgrade', onClick: () => router.push({ name: 'Pricing' }).catch(() => { window.location.hash = '#/pricing' }) } })
    } else {
      toast.error(e?.message || 'Something went wrong')
    }
  } finally { busy.value = false }
}

function duplicate(id) { store.duplicateDashboard(id) }

const deleting = ref(null)
function askDelete(d) { deleting.value = d }
function confirmDelete() {
  const d = deleting.value
  deleting.value = null
  if (d) store.deleteDashboard(d.id)
}
</script>
