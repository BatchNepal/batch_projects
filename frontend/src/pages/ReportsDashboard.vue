<template>
  <div class="h-full overflow-y-auto bg-[--surface]">
    <!-- Header band -->
    <div class="border-b border-[--border] bg-[--surface]">
      <div class="max-w-[1600px] mx-auto px-4 sm:px-6 pt-6 pb-4">
        <header class="flex items-start justify-between gap-3">
          <div class="flex items-start gap-3 min-w-0">
            <span class="size-10 rounded-lg grid place-items-center shrink-0"
                  style="background: var(--accent-soft); color: var(--accent-soft-foreground);">
              <Icon :icon="BarChart3" :size="20" />
            </span>
            <div class="min-w-0">
              <h1 class="text-[19px] font-semibold text-[--foreground] leading-7 tracking-[-0.01em]">Report Builder</h1>
              <p class="hidden sm:block text-[13px] text-[--muted] mt-0.5 max-w-xl">
                Build custom reports from your project <span class="text-[--foreground] font-medium">and ERP</span> data —
                scoped by project, milestone, or time period.
              </p>
            </div>
          </div>
          <Button color="primary" size="sm" class="shrink-0" @click="openCreate()">
            <template #startContent><Icon :icon="Plus" :size="16" /></template>
            <span class="hidden sm:inline">New report</span>
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
      <!-- Create a report: template tiles (Wrike-style, collapsible) -->
      <section class="mb-7">
        <button type="button" class="flex items-center gap-1.5 text-[13px] font-semibold text-[--foreground] mb-3"
          @click="showTemplates = !showTemplates">
          <Icon :icon="showTemplates ? ChevronDown : ChevronRight" :size="16" class="text-[--muted]" />
          Create a report
        </button>
        <div v-if="showTemplates" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3 items-stretch">
          <!-- Import tile -->
          <button type="button"
            class="group flex flex-col h-full text-left bg-[--surface] border border-dashed border-[--border] rounded-lg p-3.5 shadow-sm transform-gpu transition-[transform,box-shadow,border-color] duration-150 hover:shadow-md hover:-translate-y-0.5 hover:border-[--accent]"
            @click="openImport()">
            <span class="size-9 rounded-lg grid place-items-center mb-2.5 bg-[--surface-secondary] text-[--muted]">
              <Upload :size="18" />
            </span>
            <p class="text-[12.5px] font-semibold text-[--foreground] leading-tight">Import template</p>
            <p class="text-[11px] text-[--muted] mt-1 leading-snug line-clamp-2 min-h-[30px]">Paste a report definition exported from another workspace.</p>
            <span class="mt-auto pt-2 h-[22px]" />
          </button>

          <button v-for="t in TEMPLATES" :key="t.key" type="button"
            class="group flex flex-col h-full text-left bg-[--surface] border border-[--border] rounded-lg p-3.5 shadow-sm transform-gpu transition-[transform,box-shadow,border-color] duration-150 hover:shadow-md hover:-translate-y-0.5 hover:border-[--accent]"
            @click="openCreate(t)">
            <span class="size-9 rounded-lg grid place-items-center mb-2.5 shrink-0" :style="{ background: t.color + '1F', color: t.color }">
              <component :is="t.icon" :size="18" />
            </span>
            <p class="text-[12.5px] font-semibold text-[--foreground] leading-tight">{{ t.label }}</p>
            <p class="text-[11px] text-[--muted] mt-1 leading-snug line-clamp-2 min-h-[30px]">{{ t.desc }}</p>
            <span class="mt-auto pt-2 h-[22px] flex items-center">
              <span v-if="t.moat" class="inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded"
                    :style="{ background: CAT.green + '1F', color: CAT.dkgreen }">
                <Icon :icon="Sparkles" :size="10" /> ERP
              </span>
            </span>
          </button>
        </div>
      </section>

      <!-- Saved reports table -->
      <section>
        <div class="flex items-center gap-2 mb-2.5">
          <p class="text-[13px] font-semibold text-[--foreground]">{{ tabHeading }}</p>
          <span class="text-[11px] text-[--muted] tabular-nums">{{ tableReports.length }}</span>
        </div>

        <div v-if="loading" class="py-12 text-center text-[13px] text-[--muted]">Loading…</div>

        <div v-else-if="!tableReports.length" class="bg-[--surface] border border-[--border] rounded-lg p-10 flex flex-col items-center text-center shadow-sm">
          <span class="size-12 rounded-lg grid place-items-center mb-4" :style="{ background: CAT.blue + '1F', color: CAT.blue }">
            <BarChart3 :size="24" />
          </span>
          <p class="text-[14px] font-semibold text-[--foreground] mb-1">{{ emptyHeading }}</p>
          <p class="text-[13px] text-[--muted] max-w-sm leading-relaxed mb-5">Pick a template above, or build one from scratch.</p>
          <Button color="primary" size="sm" @click="openCreate()">
            <template #startContent><Icon :icon="Plus" :size="16" /></template>Create report
          </Button>
        </div>

        <div v-else class="border border-[--border] rounded-lg overflow-hidden bg-[--surface] shadow-sm">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="text-[11px] font-semibold uppercase tracking-wide text-[--muted] bg-[--surface-secondary]/40 border-b border-[--border]">
                <th class="px-4 py-2.5">Name</th>
                <th class="px-3 py-2.5 hidden sm:table-cell">Scope</th>
                <th class="px-3 py-2.5 hidden md:table-cell">Period</th>
                <th class="px-3 py-2.5 hidden lg:table-cell">Last updated</th>
                <th class="px-3 py-2.5 w-12"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in tableReports" :key="r.id"
                class="group border-b border-[--border] last:border-0 cursor-pointer hover:bg-[--surface-secondary] transition-colors"
                @click="open(r.id)">
                <td class="px-4 py-2.5">
                  <div class="flex items-center gap-2.5 min-w-0">
                    <span class="size-7 rounded-md grid place-items-center shrink-0" :style="{ background: scopeColor(r) + '1F', color: scopeColor(r) }">
                      <component :is="iconFor(r.icon)" :size="14" />
                    </span>
                    <div class="min-w-0">
                      <p class="text-[13px] font-medium text-[--foreground] flex items-center gap-1.5 min-w-0">
                        <span class="truncate">{{ r.name }}</span>
                        <Star v-if="r.starred" :size="11" class="text-warning shrink-0" fill="currentColor" />
                        <Pin v-if="r.pinned" :size="11" class="text-[--accent] shrink-0" title="Pinned to sidebar" />
                        <CalendarClock v-if="r.schedule_enabled" :size="11" class="text-[--success] shrink-0" title="Scheduled delivery on" />
                        <Home v-if="homeId === r.id" :size="11" class="text-[--accent] shrink-0" title="Your home dashboard" />
                        <Users v-if="r.visibility === 'workspace'" :size="11" class="text-[--muted] shrink-0" title="Shared with the workspace" />
                        <!-- A private report belonging to someone else never reaches
                             this list at all (filtered server-side in get_saved_reports)
                             — so "private" here always means "private and mine." -->
                        <Lock v-else :size="11" class="text-[--muted] shrink-0" title="Private — only you can see this" />
                      </p>
                      <p class="text-[11px] text-[--muted]">{{ (r.widgets || []).length }} widget{{ (r.widgets || []).length !== 1 ? 's' : '' }}</p>
                    </div>
                  </div>
                </td>
                <td class="px-3 py-2.5 hidden sm:table-cell">
                  <span class="inline-flex items-center gap-1.5 text-[12px] text-[--foreground]">
                    <span class="size-1.5 rounded-full shrink-0" :style="{ background: scopeColor(r) }" />{{ scopeLabel(r) }}
                  </span>
                </td>
                <td class="px-3 py-2.5 hidden md:table-cell text-[12px] text-[--muted]">{{ periodLabel(r.period) }}</td>
                <td class="px-3 py-2.5 hidden lg:table-cell text-[12px] text-[--muted] tabular-nums">{{ fmtDate(r.modified) }}</td>
                <td class="px-3 py-2.5" @click.stop @keydown.stop>
                  <div class="flex items-center justify-end gap-0.5">
                    <button class="w-7 h-7 grid place-items-center rounded-md transition-colors hover:text-warning hover:bg-[--default]"
                      :class="r.starred ? 'text-warning' : 'text-[--muted] opacity-0 group-hover:opacity-100'" title="Star" @click.stop="toggleStar(r)">
                      <Star :size="13" :fill="r.starred ? 'currentColor' : 'none'" />
                    </button>
                    <Dropdown placement="bottom-end" :side-offset="4">
                      <template #trigger="{ open: isOpen, toggle }">
                        <button class="w-7 h-7 grid place-items-center rounded-md transition-colors text-[--muted] hover:bg-[--default] hover:text-[--foreground] opacity-0 group-hover:opacity-100"
                          :class="{ '!opacity-100 bg-[--default] text-[--foreground]': isOpen }" title="More" @click.stop="toggle">
                          <MoreHorizontal :size="14" />
                        </button>
                      </template>
                      <DropdownItem @click="open(r.id)"><template #startContent><ExternalLink :size="14" class="text-[--muted]" /></template>Open</DropdownItem>
                      <DropdownItem @click="openRename(r)"><template #startContent><Pencil :size="14" class="text-[--muted]" /></template>Rename</DropdownItem>
                      <DropdownItem @click="togglePin(r)"><template #startContent><component :is="r.pinned ? PinOff : Pin" :size="14" class="text-[--muted]" /></template>{{ r.pinned ? 'Unpin from sidebar' : 'Pin to sidebar' }}</DropdownItem>
                      <DropdownItem @click="duplicate(r.id)"><template #startContent><Copy :size="14" class="text-[--muted]" /></template>Duplicate</DropdownItem>
                      <DropdownItem @click="setAsHome(r)"><template #startContent><Home :size="14" class="text-[--muted]" /></template>{{ homeId === r.id ? 'Unset as home' : 'Set as home' }}</DropdownItem>
                      <DropdownSeparator />
                      <DropdownItem color="danger" @click="askDelete(r)"><template #startContent><Trash2 :size="14" /></template>Delete</DropdownItem>
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
        <p class="text-[15px] font-semibold text-[--foreground]">{{ editingId ? 'Rename report' : (formTemplate ? formTemplate.label : 'New report') }}</p>
      </ModalHeader>
      <ModalBody class="px-5 py-4 flex flex-col gap-3.5">
        <!-- Icon + color identity (Wrike-style) -->
        <div class="flex items-center gap-3">
          <span class="size-12 rounded-lg grid place-items-center shrink-0 shadow-sm transition-colors"
            :style="{ background: formColor + '24', color: formColor }">
            <component :is="iconFor(formIcon)" :size="22" />
          </span>
          <div class="flex-1 min-w-0">
            <Input v-model="formName" label="Report name" placeholder="e.g. Q3 Delivery Overview" autofocus @keydown.enter="submitForm" />
          </div>
        </div>

        <!-- Color row -->
        <div>
          <p class="text-[12px] font-medium text-[--foreground] mb-1.5">Color</p>
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
          <p class="text-[12px] font-medium text-[--foreground] mb-1.5">Icon</p>
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
            <p class="text-[12px] font-medium text-[--foreground] mb-1.5">Project scope</p>
            <Select v-model="formProject" size="sm" fullWidth @update:modelValue="onProjectChange">
              <SelectItem value="all">All projects (workspace)</SelectItem>
              <SelectItem v-for="p in projects" :key="p.name" :value="p.name">{{ p.project_name }}</SelectItem>
            </Select>
          </div>
          <!-- Scope: milestone (only when a project is chosen) -->
          <div v-if="formProject !== 'all'">
            <p class="text-[12px] font-medium text-[--foreground] mb-1.5">Milestone <span class="text-[--muted] font-normal">(optional)</span></p>
            <Select v-model="formMilestone" size="sm" fullWidth>
              <SelectItem value="">No milestone</SelectItem>
              <SelectItem v-for="m in milestones" :key="m.name" :value="m.name">{{ m.title }}</SelectItem>
            </Select>
          </div>
          <!-- Scope: period -->
          <div>
            <p class="text-[12px] font-medium text-[--foreground] mb-1.5">Time period</p>
            <Select v-model="formPeriod" size="sm" fullWidth>
              <SelectItem v-for="p in PERIODS" :key="p.value" :value="p.value">{{ p.label }}</SelectItem>
            </Select>
          </div>
          <!-- visibility. Private is the free default; sharing
               with the workspace is gated (dashboards flag, Team+) — the
               Switch stays enabled either way so a free-tier user can SEE
               the option and hit the upgrade prompt on save, same pattern
               as every other gated toggle in the app. -->
          <div class="flex items-center justify-between gap-3 pt-1">
            <div class="min-w-0">
              <p class="text-[13px] font-medium text-[--foreground]">Share with workspace</p>
              <p class="text-[11.5px] text-[--muted] mt-0.5">Every member can view it. {{ ent.can('dashboards') ? '' : `Requires the ${ent.requiredPlanFor('dashboards')} plan.` }}</p>
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
      <ModalHeader class="px-5 pt-5"><p class="text-[15px] font-semibold text-[--foreground]">Delete report?</p></ModalHeader>
      <ModalBody class="px-5 py-4">
        <p class="text-[13px] text-[--muted]">"{{ deleting?.name }}" will be permanently removed.</p>
      </ModalBody>
      <ModalFooter class="px-5 pb-5 justify-end gap-2">
        <Button variant="bordered" size="sm" @click="deleting = null">Cancel</Button>
        <Button color="danger" size="sm" @click="confirmDelete">Delete</Button>
      </ModalFooter>
    </Modal>

    <!-- Import template -->
    <Modal :open="importOpen" @update:open="v => !v && (importOpen = false)" size="md" radius="lg" hideCloseButton>
      <ModalHeader class="px-5 pt-5">
        <div>
          <p class="text-[15px] font-semibold text-[--foreground]">Import a report template</p>
          <p class="text-[12px] text-[--muted] mt-0.5">Paste a definition exported from a report's ⋯ menu (“Export as template”).</p>
        </div>
      </ModalHeader>
      <ModalBody class="px-5 py-4">
        <textarea v-model="importText" rows="9" spellcheck="false"
          class="w-full rounded-lg border border-[--border] bg-[--surface-secondary] p-3 text-[12px] font-mono text-[--foreground] outline-none focus:border-[--accent] resize-none"
          placeholder='{ "report_name": "...", "scope": "all", "widgets": [ ... ], "layout": [ ... ] }'></textarea>
        <p v-if="importErr" class="text-[12px] text-danger mt-2">{{ importErr }}</p>
      </ModalBody>
      <ModalFooter class="px-5 pb-5 justify-end gap-2">
        <Button variant="bordered" size="sm" @click="importOpen = false">Cancel</Button>
        <Button color="primary" size="sm" :isDisabled="!importText.trim() || importing" @click="doImport">
          {{ importing ? 'Importing…' : 'Import' }}
        </Button>
      </ModalFooter>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useReportsStore } from '@/stores/reports'
import { useProjectStore } from '@/stores/project'
import { getMilestones, UpgradeRequiredError, getViewPrefs, saveViewPrefs } from '@/utils/api'
import { toast } from 'vue-sonner'
import { Button, Input, Icon, Select, SelectItem, Switch, Tabs, Modal, ModalHeader, ModalBody, ModalFooter, Dropdown, DropdownItem, DropdownSeparator } from '@/ui'
import { useEntitlementsStore } from '@/stores/entitlements'
import { reportIcon, REPORT_ICON_NAMES, REPORT_COLORS } from '@/utils/reportIcons'
import {
  Plus, MoreHorizontal, ExternalLink, Pencil, Copy, Trash2, Star, Sparkles, Pin, PinOff, CalendarClock,
  BarChart3, LayoutDashboard, PieChart, Gauge, GitBranch, Activity, TrendingDown, Users, Flag,
  ChevronDown, ChevronRight, Upload, Check, Home, Lock,
} from 'lucide-vue-next'

// Category accents for template tiles / scope chips — pulled from the same
// swatch palette used for user-picked report colors (REPORT_COLORS), not a
// separate hardcoded set, so there's exactly one source of truth for hex here.
const CAT = {
  blue: REPORT_COLORS[0], ltblue: REPORT_COLORS[1], green: REPORT_COLORS[2],
  dkgreen: REPORT_COLORS[3], orange: REPORT_COLORS[4], red: REPORT_COLORS[6],
  purple: REPORT_COLORS[7],
}

const PERIODS = [
  { value: 'all_time',     label: 'All time' },
  { value: 'last_7_days',  label: 'Last 7 days' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'last_90_days', label: 'Last 90 days' },
  { value: 'this_quarter', label: 'This quarter' },
  { value: 'this_year',    label: 'This year' },
]

// Report templates — each builds its widgets after creation.
const TEMPLATES = [
  { key: 'blank', label: 'Blank report', desc: 'Start from scratch and add your own widgets.', icon: LayoutDashboard, color: CAT.blue,
    build: () => [] },
  { key: 'delivery', label: 'Delivery overview', desc: 'A full dashboard: totals, status & priority mix, assignee load and open work.', icon: PieChart, color: CAT.ltblue,
    build: (id, s) => {
      const m1 = s.addWidget(id, 'metric'); s.updateWidgetConfig(id, m1.id, { title: 'Total tasks', group_by: 'status', metric: 'count', colorScheme: 'blue' })
      const m2 = s.addWidget(id, 'metric'); s.updateWidgetConfig(id, m2.id, { title: 'Story points', group_by: 'status', metric: 'story_points', colorScheme: 'green' })
      const a = s.addWidget(id, 'chart'); s.updateWidgetConfig(id, a.id, { title: 'Tasks by status', group_by: 'status', metric: 'count', chartType: 'donut' })
      const b = s.addWidget(id, 'chart'); s.updateWidgetConfig(id, b.id, { title: 'Tasks by priority', group_by: 'priority', metric: 'count', chartType: 'bar' })
      const c = s.addWidget(id, 'chart'); s.updateWidgetConfig(id, c.id, { title: 'Workload by assignee', group_by: 'assignee', metric: 'count', chartType: 'hbar' })
      const t = s.addWidget(id, 'table'); s.updateWidgetConfig(id, t.id, { title: 'Open tasks', statusFilter: 'open', sortBy: 'due_date', sortOrder: 'asc' })
    } },
  { key: 'agile', label: 'Agile / sprint', desc: 'Sprint report, velocity and burndown for scrum teams.', icon: GitBranch, color: CAT.purple,
    build: (id, s) => {
      s.addWidget(id, 'preset', { preset: 'sprint_report' })
      s.addWidget(id, 'preset', { preset: 'velocity' })
      s.addWidget(id, 'preset', { preset: 'burndown' })
    } },
  { key: 'workload', label: 'Team workload', desc: 'Who is loaded, capacity vs allocation, utilization.', icon: Users, color: CAT.orange,
    build: (id, s) => {
      s.addWidget(id, 'preset', { preset: 'workload' })
      s.addWidget(id, 'preset', { preset: 'utilization' })
    } },
  { key: 'flow', label: 'Flow & throughput', desc: 'Created vs resolved, cumulative flow, cycle time.', icon: TrendingDown, color: CAT.dkgreen,
    build: (id, s) => {
      s.addWidget(id, 'preset', { preset: 'throughput' })
      s.addWidget(id, 'preset', { preset: 'cumulative_flow' })
      s.addWidget(id, 'preset', { preset: 'cycle_time_control' })
    } },
  { key: 'milestone', label: 'Milestone health', desc: 'Delivery % plus hours, billable value and budget burn per milestone.', icon: Flag, color: CAT.green, moat: true, needsMilestone: true,
    build: (id, s) => {
      s.addWidget(id, 'preset', { preset: 'milestone_finance' })
      const a = s.addWidget(id, 'chart'); s.updateWidgetConfig(id, a.id, { title: 'Milestone tasks by status', group_by: 'status', metric: 'count', chartType: 'donut' })
    } },
]

// ── Icon registry for saved reports (shared catalog) ───────────────────────
function iconFor(name) { return reportIcon(name) }

const TYPE_LABELS = { metric: 'Metric', chart: 'Chart', table: 'Table', preset: 'Template', query: 'BQL', text: 'Note' }
function widgetBadges(r) { return [...new Set((r.widgets || []).map(w => TYPE_LABELS[w.type] || w.type))].slice(0, 4) }

const PERIOD_LABEL = Object.fromEntries(PERIODS.map(p => [p.value, p.label]))
function periodLabel(v) { return PERIOD_LABEL[v] || 'Last 30 days' }
function fmtDate(s) {
  if (!s) return '—'
  const d = new Date(s.replace(' ', 'T'))
  if (isNaN(d)) return '—'
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

// ── Stores ──────────────────────────────────────────────────────────────────
const router = useRouter()
const store = useReportsStore()
const projectStore = useProjectStore()
const ent = useEntitlementsStore()
const { reports } = storeToRefs(store)
const { projects } = storeToRefs(projectStore)
const loading = ref(true)
const showTemplates = ref(true)

const homeId = ref(null)

onMounted(async () => {
  await Promise.all([store.load(), projectStore.projects.length ? null : projectStore.fetchProjects().catch(() => {})])
  loading.value = false
  try {
    const pref = await getViewPrefs(null, 'home_dashboard')
    homeId.value = pref?.dashboard_id || null
  } catch { /* no preference yet */ }
})

// "set as home"; toggling off just clears the preference so
// Dashboard.vue falls back to the stock dashboard again.
async function setAsHome(r) {
  const next = homeId.value === r.id ? null : r.id
  try {
    await saveViewPrefs(null, { dashboard_id: next }, 'home_dashboard')
    homeId.value = next
    toast.success(next ? `"${r.name}" set as your home dashboard` : 'Home dashboard cleared')
  } catch (e) {
    toast.error(e?.message || 'Could not update your home dashboard')
  }
}

// ── Tabs ──────────────────────────────────────────────────────────────────
const activeTab = ref('all')
const starredReports = computed(() => reports.value.filter(r => r.starred))
// My / Shared split, using is_mine/visibility from the backend.
const myReports = computed(() => reports.value.filter(r => r.is_mine))
const sharedReports = computed(() => reports.value.filter(r => !r.is_mine || r.visibility === 'workspace'))
const TABS = computed(() => [
  { value: 'all',     label: 'All dashboards' },
  { value: 'mine',    label: `My dashboards${myReports.value.length ? ' · ' + myReports.value.length : ''}` },
  { value: 'shared',  label: `Shared${sharedReports.value.length ? ' · ' + sharedReports.value.length : ''}` },
  { value: 'starred', label: `Starred${starredReports.value.length ? ' · ' + starredReports.value.length : ''}` },
])

const projName = (name) => projects.value.find(p => p.name === name)?.project_name || name
function scopeLabel(r) {
  const s = r.scope
  if (!s || s === 'all') return 'Workspace'
  if (Array.isArray(s)) return s.length === 1 ? projName(s[0]) : `${s.length} projects`
  return projName(s)
}
function scopeColor(r) {
  const s = r.scope
  if (!s || s === 'all') return CAT.blue
  if (Array.isArray(s)) return s.length === 1 ? (projects.value.find(p => p.name === s[0])?.project_color || CAT.ltblue) : CAT.purple
  return projects.value.find(p => p.name === s)?.project_color || CAT.ltblue
}

const tabHeading = computed(() => ({
  starred: 'Starred dashboards', mine: 'My dashboards', shared: 'Shared dashboards',
}[activeTab.value] || 'All dashboards'))
const emptyHeading = computed(() => ({
  starred: 'No starred dashboards', mine: 'No dashboards yet', shared: 'No shared dashboards yet',
}[activeTab.value] || 'No dashboards yet'))

// Reports shown in the table, newest first.
const tableReports = computed(() => {
  const src = activeTab.value === 'starred' ? starredReports.value
    : activeTab.value === 'mine' ? myReports.value
    : activeTab.value === 'shared' ? sharedReports.value
    : reports.value
  return [...src].sort((a, b) => String(b.modified || '').localeCompare(String(a.modified || '')))
})

function open(id) { router.push(`/workspace/reports/${id}`) }
function toggleStar(r) { store.updateReport(r.id, { starred: !r.starred }) }
function togglePin(r) { store.togglePinned(r.id) }

// Icon + color picker palette
const ICON_NAMES = REPORT_ICON_NAMES
const COLORS = REPORT_COLORS

// ── Create / rename ─────────────────────────────────────────────────────────
const formOpen = ref(false)
const formName = ref('')
const editingId = ref(null)
const formTemplate = ref(null)
const formProject = ref('all')
const formMilestone = ref('')
const formPeriod = ref('last_30_days')
const formIcon = ref('FileBarChart2')
const formColor = ref(CAT.blue)
const formVisibility = ref('private')
const milestones = ref([])
const busy = ref(false)

const TEMPLATE_ICON = { milestone: 'Flag', agile: 'GitBranch', workload: 'Users', flow: 'GitCompareArrows', delivery: 'ChartPie', blank: 'FileBarChart2' }

function openCreate(template = null) {
  editingId.value = null
  formTemplate.value = template
  formName.value = template && template.key !== 'blank' ? template.label : ''
  formProject.value = 'all'
  formMilestone.value = ''
  formPeriod.value = 'last_30_days'
  formVisibility.value = 'private'
  formIcon.value = template ? (TEMPLATE_ICON[template.key] || 'FileBarChart2') : 'FileBarChart2'
  formColor.value = template?.color || CAT.blue
  milestones.value = []
  formOpen.value = true
}
function openRename(r) {
  editingId.value = r.id; formTemplate.value = null; formName.value = r.name
  formIcon.value = r.icon || 'FileBarChart2'
  formColor.value = r.color || CAT.blue
  formOpen.value = true
}

async function onProjectChange(v) {
  formMilestone.value = ''
  milestones.value = []
  if (v && v !== 'all') {
    try { milestones.value = await getMilestones(v) } catch {}
  }
}

async function submitForm() {
  const name = formName.value.trim()
  if (!name || busy.value) return
  if (editingId.value) {
    store.renameReport(editingId.value, name)
    store.updateReport(editingId.value, { icon: formIcon.value, color: formColor.value })
    formOpen.value = false
    return
  }
  busy.value = true
  try {
    const scope = formProject.value === 'all' ? 'all' : formProject.value
    const id = await store.createReport(name, formIcon.value, {
      scope, period: formPeriod.value, milestone: formMilestone.value || null,
      visibility: formVisibility.value,
    })
    store.updateReport(id, { color: formColor.value })
    if (formTemplate.value?.build) formTemplate.value.build(id, store)
    formOpen.value = false
    router.push(`/workspace/reports/${id}`)
  } catch (e) {
    if (e instanceof UpgradeRequiredError) {
      toast.error(e.message, { action: { label: 'Upgrade', onClick: () => router.push({ name: 'Pricing' }).catch(() => { window.location.hash = '#/pricing' }) } })
    } else {
      toast.error(e?.message || 'Something went wrong')
    }
  } finally { busy.value = false }
}

function duplicate(id) { store.duplicateReport(id) }

// ── Import a report definition (real template support) ──────────────────────
const importOpen = ref(false)
const importText = ref('')
const importErr = ref('')
const importing = ref(false)
function openImport() { importText.value = ''; importErr.value = ''; importOpen.value = true }
async function doImport() {
  importErr.value = ''
  let def
  try { def = JSON.parse(importText.value) } catch { importErr.value = 'That doesn’t look like valid JSON.'; return }
  if (!def || (!Array.isArray(def.widgets) && !def.report_name)) {
    importErr.value = 'Missing a report definition (expected report_name / widgets).'; return
  }
  importing.value = true
  try {
    const id = await store.importReport(def)
    importOpen.value = false
    router.push(`/workspace/reports/${id}`)
  } catch (e) { importErr.value = e?.message || 'Import failed.' }
  finally { importing.value = false }
}

const deleting = ref(null)
function askDelete(r) { deleting.value = r }
function confirmDelete() {
  const r = deleting.value
  deleting.value = null              // close instantly — removal is optimistic
  if (r) store.deleteReport(r.id)
}
</script>
