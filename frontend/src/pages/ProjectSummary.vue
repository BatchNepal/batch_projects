<template>
  <div
    class="h-full overflow-y-auto bg-background"
    style="scrollbar-width:thin;scrollbar-color:var(--border) transparent"
  >
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center h-64">
      <Spinner size="md" />
    </div>

    <template v-else>
      <div class="px-6 py-6 space-y-6">

        <!-- ── Page header ── -->
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-center gap-3 min-w-0">
            <ProjectAvatar v-if="project" :theme="project.theme" :seed="project.key" size="md" />
            <div class="min-w-0">
              <h1 class="text-2xl font-semibold text-foreground leading-tight">
                {{ project?.project_name || project?.name || 'Project Summary' }}
              </h1>
              <p v-if="project?.description" class="text-sm text-muted mt-1 line-clamp-2">
                {{ project.description }}
              </p>
            </div>
          </div>

          <!-- Health pulse: manual override, falls back to auto-derived when unset -->
          <div v-if="project" class="shrink-0 flex items-center gap-2">
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11.5px] font-medium border" :class="healthChipClass">
              <span class="size-1.5 rounded-full shrink-0" :class="healthDotClass" />
              {{ healthLabel }}
            </span>
            <Select :modelValue="project.health_override || ''" size="sm" class="w-28" @update:modelValue="setHealthOverride">
              <SelectItem value="">Auto</SelectItem>
              <SelectItem value="On track">On track</SelectItem>
              <SelectItem value="At risk">At risk</SelectItem>
              <SelectItem value="Off track">Off track</SelectItem>
            </Select>
          </div>
        </div>

        <!-- ── KPI row ── -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KpiTile
            label="Open Tasks" :value="metrics[0].value"
            :icon="LayoutList" iconColor="default"
          />
          <KpiTile
            label="Completed This Week" :value="metrics[1].value"
            :delta="metrics[1].trend?.delta" :deltaGood="true" :subline="metrics[1].trend ? 'vs last week' : ''"
            :icon="CheckCircle2" iconColor="success"
          />
          <KpiTile
            label="Overdue" :value="metrics[2].value"
            :delta="metrics[2].trend?.delta" :deltaGood="false" :subline="metrics[2].trend ? 'vs last week' : ''"
            :icon="ShieldAlert" iconColor="danger"
          />
          <KpiTile
            label="Due This Week" :value="metrics[3].value"
            :icon="Flag" iconColor="warning"
          />
        </div>

        <!-- ── Engagement meta (non-internal projects) ── -->
        <div v-if="project?.project_type && project.project_type !== 'internal'" class="flex flex-wrap items-center gap-3">
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11.5px] font-medium border"
            :class="projectTypeBadgeClass(project.project_type)">
            {{ projectTypeLabel(project.project_type) }}
          </span>
          <span v-if="project.client" class="text-[12.5px] text-muted">
            <span class="text-muted mr-1">Client:</span>{{ project.client }}
          </span>
          <span v-if="project.hourly_rate" class="text-[12.5px] text-muted">
            <span class="text-muted mr-1">Rate:</span>{{ project.currency || 'USD' }} {{ project.hourly_rate }}/hr
          </span>
          <span v-if="project.budget_amount" class="text-[12.5px] text-muted">
            <span class="text-muted mr-1">Budget:</span>{{ project.currency || 'USD' }} {{ Number(project.budget_amount).toLocaleString() }}
          </span>
          <router-link :to="`/workspace/${projectKey}/settings/billing`" class="ml-auto text-[11.5px] text-muted hover:text-accent transition-colors">
            Edit billing →
          </router-link>
        </div>

        <!-- ── Budget utilization (billable projects with a budget set) ── -->
        <SectionCard v-if="budgetSummary?.budget > 0" title="Budget utilization" class="max-w-sm">
          <div class="flex items-center gap-4">
            <ApexGauge :value="budgetSummary.cost" :max="budgetSummary.budget" label="Used" :height="140" class="w-[140px] shrink-0" />
            <div class="text-xs text-muted space-y-1">
              <p><span class="font-semibold text-foreground tabular-nums">{{ budgetSummary.currency || 'USD' }} {{ Number(budgetSummary.cost).toLocaleString() }}</span> spent (est.)</p>
              <p>of <span class="font-medium text-foreground tabular-nums">{{ budgetSummary.currency || 'USD' }} {{ Number(budgetSummary.budget).toLocaleString() }}</span> budget</p>
              <p class="tabular-nums">{{ budgetSummary.actual_hours }}h logged</p>
            </div>
          </div>
        </SectionCard>

        <!-- ── Widget grid — every card here holds a fixed WIDGET_H content
             area (chart height or a capped/scrollable list), so every card
             in every row matches height regardless of how much content it
             has. Grid rows use default stretch (no items-start) as a second
             safety net for any header-height drift between cards. ── -->
        <div v-if="totalIssues >= 3" class="grid grid-cols-2 gap-6">

          <!-- Status overview -->
          <SectionCard
            title="Status overview"
            :to="`/workspace/${projectKey}/board`"
            view-all-label="View board →"
          >
            <!-- 3+ statuses: donut reads better than proportional bars -->
            <ApexDonut v-if="statusBreakdown.length >= 3" :items="statusChartItems" :height="WIDGET_H" />

            <!-- 1–2 statuses: list only (a donut of one slice is meaningless) -->
            <div v-else-if="statusBreakdown.length" class="space-y-2" :style="{ height: WIDGET_H + 'px' }">
              <div
                v-for="s in statusBreakdown"
                :key="s.name"
                class="flex items-center justify-between"
              >
                <StatusPill :label="s.name" :hex-color="s.color" />
                <span class="text-xs font-semibold text-muted tabular-nums">{{ s.count }}</span>
              </div>
            </div>

            <EmptyState
              v-else
              :icon="LayoutList"
              title="No tasks yet"
              description="Add tasks to see status distribution."
              :style="{ height: WIDGET_H + 'px' }"
            />
          </SectionCard>

          <!-- Priority breakdown -->
          <SectionCard title="Priority breakdown">
            <ApexBar v-if="priorityChartItems.length" :items="priorityChartItems" :height="WIDGET_H" />
            <EmptyState v-else :icon="Flag" title="No priorities set" description="Set task priorities to see the breakdown." :style="{ height: WIDGET_H + 'px' }" />
          </SectionCard>

        </div>

        <div v-if="totalIssues >= 3" class="grid grid-cols-2 gap-6">

          <!-- Types of work -->
          <SectionCard title="Types of work">
            <div v-if="workTypeItems.length" class="space-y-3 overflow-y-auto pr-1" :style="{ height: WIDGET_H + 'px' }">
              <div v-for="t in workTypeItems" :key="t.label">
                <div class="flex items-center justify-between text-xs mb-1">
                  <span class="font-medium text-foreground">{{ t.label }}</span>
                  <span class="text-muted tabular-nums">{{ t.pct }}%</span>
                </div>
                <InlineProgress :value="t.pct" :auto-color="false" color="blue" :show-label="false" />
              </div>
            </div>
            <EmptyState v-else :icon="LayoutList" title="No task types" description="Assign task types to see the mix." :style="{ height: WIDGET_H + 'px' }" />
          </SectionCard>

          <!-- Team workload -->
          <SectionCard title="Team workload" subtitle="Open tasks per assignee">
            <ApexBar v-if="workloadItems.length" :items="workloadItems" :height="WIDGET_H" horizontal />
            <EmptyState v-else :icon="User" title="No open tasks" description="Assign tasks to see workload distribution." :style="{ height: WIDGET_H + 'px' }" />
          </SectionCard>

        </div>

        <div v-if="totalIssues >= 3" class="grid grid-cols-2 gap-6">

          <!-- Epic progress -->
          <SectionCard title="Epic progress" :to="`/workspace/${projectKey}/settings/epics`" view-all-label="View epics →">
            <div v-if="epics.length" class="space-y-3 overflow-y-auto pr-1" :style="{ height: WIDGET_H + 'px' }">
              <div v-for="e in epics" :key="e.name">
                <div class="flex items-center justify-between text-xs mb-1">
                  <span class="font-medium text-foreground truncate">{{ e.title }}</span>
                  <span class="text-muted tabular-nums shrink-0 ml-2">{{ e.done_issues }}/{{ e.total_issues }}</span>
                </div>
                <InlineProgress :value="e.progress" :auto-color="false" :color="e.progress >= 100 ? 'green' : 'blue'" :show-label="false" />
              </div>
            </div>
            <EmptyState v-else :icon="Flag" title="No epics" description="Group related tasks into epics to track delivery." :style="{ height: WIDGET_H + 'px' }" />
          </SectionCard>

          <!-- Recent activity -->
          <SectionCard title="Recent activity">
            <div v-if="activity.length" class="space-y-3 overflow-y-auto pr-1" :style="{ height: WIDGET_H + 'px' }">
              <div
                v-for="item in activity.slice(0, 10)"
                :key="item.name"
                class="flex items-start gap-2.5"
              >
                <component
                  :is="activityIcon(item.action_type)"
                  :size="14"
                  :stroke-width="1.5"
                  class="text-muted mt-0.5 shrink-0"
                />
                <div class="flex-1 min-w-0">
                  <div class="text-xs leading-relaxed">
                    <span class="font-medium text-foreground">{{ shortUser(item.user) }}</span>
                    <span class="text-muted"> {{ item.action_text }} </span>
                    <button
                      class="font-medium text-primary hover:underline"
                      @click="store.openTaskDetail(item.issue)"
                    >
                      {{ item.task_key }}
                    </button>
                    <span
                      v-if="item.new_value"
                      class="ml-1 text-[10.5px] font-medium px-1 py-0.5 rounded-sm"
                      :style="statusBadgeStyle(item.new_value)"
                    >
                      {{ item.new_value }}
                    </span>
                  </div>
                  <div class="text-[11px] text-muted mt-0.5">{{ relTime(item.creation) }}</div>
                </div>
              </div>
            </div>
            <EmptyState
              v-else
              :icon="Activity"
              title="No activity yet"
              description="Actions taken in this project will appear here."
              :style="{ height: WIDGET_H + 'px' }"
            />
          </SectionCard>

        </div>

        <!-- ── Trends over time — creation trend + cycle time, replacing the
             old fixed-460px hand-rolled SVG chart (which sat half-empty on
             wide screens). Apex charts fill their container responsively. ── -->
        <div v-if="weeklyChart" class="grid grid-cols-2 gap-6">

          <SectionCard title="Work item creation trend"
            :subtitle="scopeCreepWarning ? 'Scope is growing faster than delivery — more created than completed' : 'Tasks created per week — past 8 weeks'">
            <ApexArea :items="creationTrendItems" :height="WIDGET_H" />
          </SectionCard>

          <SectionCard title="Work item cycle time" subtitle="Avg. days from creation to completion, per week">
            <ApexArea :items="cycleTimeTrendItems" :height="WIDGET_H" :format="fmtDays" />
          </SectionCard>

        </div>

        <!-- Sparse project: activity full-width, status breakdown omitted -->
        <div v-if="totalIssues < 3">
          <SectionCard title="Recent activity">
            <div v-if="activity.length" class="space-y-3">
              <div v-for="item in activity.slice(0, 10)" :key="item.name" class="flex items-start gap-2.5">
                <component :is="activityIcon(item.action_type)" :size="14" :stroke-width="1.5" class="text-muted mt-0.5 shrink-0" />
                <div class="flex-1 min-w-0">
                  <div class="text-xs leading-relaxed">
                    <span class="font-medium text-foreground">{{ shortUser(item.user) }}</span>
                    <span class="text-muted"> {{ item.action_text }} </span>
                    <button class="font-medium text-primary hover:underline" @click="store.openTaskDetail(item.issue)">{{ item.task_key }}</button>
                  </div>
                  <div class="text-[11px] text-muted mt-0.5">{{ relTime(item.creation) }}</div>
                </div>
              </div>
            </div>
            <EmptyState v-else :icon="Activity" title="No activity yet" description="Actions taken in this project will appear here." />
          </SectionCard>
        </div>


        <!-- ── Needs attention — full width ── -->
        <SectionCard
          title="Needs attention"
          subtitle="Overdue, due soon, or high-priority tasks"
          :to="`/workspace/${projectKey}/list`"
          view-all-label="View all →"
        >
          <DataTable :columns="attentionColumns" :rows="attentionTasks">
            <template #cell-priority="{ row }">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold leading-none"
                :style="{ backgroundColor: priorityPill(row.priority).bg, color: priorityPill(row.priority).color }"
              >
                {{ priorityPill(row.priority).label }}
              </span>
            </template>

            <template #cell-title="{ row }">
              <button
                class="text-sm text-foreground hover:text-primary hover:underline text-left line-clamp-1 max-w-[320px]"
                @click="store.openTaskDetail(row.name)"
              >
                {{ row.title }}
              </button>
            </template>

            <template #cell-assignee="{ row }">
              <div v-if="row.assignees?.length" class="flex items-center gap-1.5">
                <Avatar :name="row.assignees[0].full_name" size="xs" />
                <span class="text-xs text-muted truncate max-w-[80px]">
                  {{ row.assignees[0].full_name?.split(' ')[0] }}
                </span>
              </div>
              <span v-else class="text-xs text-muted">—</span>
            </template>

            <template #cell-status="{ row }">
              <StatusPill
                :label="row.status"
                :hex-color="store.workflowStateMap?.[row.status]?.color"
              />
            </template>

            <template #cell-due="{ row }">
              <span
                v-if="row.due_date"
                class="text-xs"
                :class="isOverdue(row) ? 'text-red-500 font-medium' : 'text-muted'"
              >
                {{ formatDate(row.due_date) }}
              </span>
              <span v-else class="text-xs text-muted">—</span>
            </template>

            <template #empty>
              <EmptyState
                :icon="CheckCircle2"
                title="Nothing needs immediate attention"
                description="Tasks that are overdue, due soon, or high-priority will appear here."
              />
            </template>
          </DataTable>
        </SectionCard>

        <!-- ── Milestones & Risks ── -->
        <div class="grid grid-cols-2 gap-6 items-start">

          <SectionCard
            title="Milestones"
            :subtitle="completedMilestonesCount ? `${completedMilestonesCount} completed` : ''"
          >
            <template #trailing>
              <button
                type="button"
                class="text-xs text-primary hover:underline whitespace-nowrap"
                @click="showAddMilestone = !showAddMilestone"
              >+ Add</button>
            </template>

            <div v-if="showAddMilestone" class="mb-4 space-y-2">
              <Input
                v-model="newMilestone.title"
                size="sm"
                placeholder="Milestone title…"
                @keyup.enter="submitMilestone"
              />
              <div class="flex items-center gap-2">
                <Input v-model="newMilestone.due_date" type="date" size="sm" class="w-36" />
                <Select v-model="newMilestone.billing_type" size="sm" class="w-40">
                  <SelectItem value="None">No billing</SelectItem>
                  <SelectItem value="Fixed Amount">Fixed amount</SelectItem>
                  <SelectItem value="Percent of Budget">% of budget</SelectItem>
                </Select>
                <Input
                  v-if="newMilestone.billing_type === 'Fixed Amount'"
                  v-model.number="newMilestone.invoice_amount"
                  type="number" size="sm" class="w-28" placeholder="Amount"
                />
                <Input
                  v-if="newMilestone.billing_type === 'Percent of Budget'"
                  v-model.number="newMilestone.invoice_percent"
                  type="number" size="sm" class="w-24" placeholder="%"
                />
              </div>
              <div class="flex items-center gap-2">
                <Button
                  size="sm" color="primary"
                  :isLoading="savingMilestone"
                  :isDisabled="!newMilestone.title.trim()"
                  @click="submitMilestone"
                >Add</Button>
                <Button size="sm" variant="light" color="default" @click="cancelAddMilestone">Cancel</Button>
              </div>
            </div>

            <div v-if="visibleMilestones.length" class="space-y-3">
              <div v-for="m in visibleMilestones" :key="m.name" class="flex items-start gap-3 group">
                <span
                  class="shrink-0 w-12 text-right text-xs font-semibold tabular-nums pt-0.5"
                  :class="milestoneOverdue(m) ? 'text-red-500' : 'text-muted'"
                >
                  {{ m.due_date ? formatDate(m.due_date) : '—' }}
                </span>
                <div class="w-px h-4 bg-border shrink-0 mt-0.5" />
                <p class="flex-1 min-w-0 text-sm font-medium truncate"
                  :class="m.status === 'Completed' ? 'text-muted line-through' : 'text-foreground'">{{ m.title }}</p>
                <button
                  v-if="m.status === 'Completed'"
                  type="button"
                  class="shrink-0 text-[11px] font-medium text-primary hover:underline whitespace-nowrap"
                  title="Generate Sales Invoice"
                  :disabled="invoicingMilestone === m.name"
                  @click="generateMilestoneInvoiceRow(m)"
                >{{ invoicingMilestone === m.name ? 'Invoicing…' : 'Invoice' }}</button>
                <button
                  v-else
                  type="button"
                  class="shrink-0 text-xs text-muted hover:text-green-600 transition-colors opacity-0 group-hover:opacity-100"
                  title="Mark completed"
                  @click="completeMilestone(m)"
                >✓</button>
                <button
                  type="button"
                  class="shrink-0 text-xs text-muted hover:text-red-600 transition-colors opacity-0 group-hover:opacity-100"
                  title="Delete milestone"
                  @click="deleteMilestoneRow(m)"
                >✕</button>
              </div>
            </div>
            <EmptyState
              v-else
              :icon="Flag"
              title="No milestones"
              description="Add delivery checkpoints to track this project against dates."
            />
          </SectionCard>

          <SectionCard title="Risks" subtitle="Open risks for this project">
            <template #trailing>
              <button
                type="button"
                class="text-xs text-primary hover:underline whitespace-nowrap"
                @click="showAddRisk = !showAddRisk"
              >+ Flag risk</button>
            </template>

            <div v-if="showAddRisk" class="mb-4 space-y-2">
              <Input
                v-model="newRisk.title"
                size="sm"
                placeholder="Risk description…"
                @keyup.enter="submitRisk"
              />
              <div class="flex items-center gap-2">
                <Select v-model="newRisk.severity" size="sm" class="w-28">
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                </Select>
                <Button
                  size="sm" color="primary"
                  :isLoading="savingRisk"
                  :isDisabled="!newRisk.title.trim()"
                  @click="submitRisk"
                >Add</Button>
                <Button size="sm" variant="light" color="default" @click="cancelAddRisk">Cancel</Button>
              </div>
            </div>

            <div v-if="risks.length" class="space-y-3">
              <div v-for="r in risks" :key="r.name" class="flex items-start gap-2.5 group">
                <span class="mt-1.5 shrink-0 size-2 rounded-full" :class="riskDotClass(r.severity)" />
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-foreground leading-5">{{ r.title }}</p>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <span class="text-xs font-medium text-muted capitalize">{{ r.severity }}</span>
                    <span v-if="r.owner" class="text-xs text-muted">· {{ r.owner }}</span>
                  </div>
                </div>
                <button
                  type="button"
                  class="shrink-0 text-xs text-muted hover:text-green-600 transition-colors opacity-0 group-hover:opacity-100"
                  title="Mark mitigated"
                  @click="resolveRisk(r)"
                >✓</button>
                <button
                  type="button"
                  class="shrink-0 text-xs text-muted hover:text-red-600 transition-colors opacity-0 group-hover:opacity-100"
                  title="Delete risk"
                  @click="deleteRiskRow(r)"
                >✕</button>
              </div>
            </div>
            <EmptyState
              v-else
              :icon="ShieldAlert"
              title="No open risks"
              description="Flag anything that threatens scope, schedule, or budget."
            />
          </SectionCard>

        </div>

      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import {
  queryTasks,
  getMilestones, createMilestone, updateMilestone, deleteMilestone, generateMilestoneInvoice,
  getRisks, createRisk, updateRisk, deleteRisk,
  updateProjectGeneral, getEpics, getProjectBudgetSummary,
  UpgradeRequiredError,
} from '@/utils/api.js'
import { toast } from 'vue-sonner'
import {
  Activity, FilePlus2, RefreshCw, User, MessageSquare,
  CheckCircle2, LayoutList, Flag, ShieldAlert,
} from 'lucide-vue-next'
import {
  Spinner, Avatar, Input, Button, Select, SelectItem,
  MetricRow, SectionCard, EmptyState, DataTable,
  StatusPill, KpiTile, ProjectAvatar, InlineProgress,
} from '@/ui'
import { ApexDonut, ApexBar, ApexGauge, ApexArea } from '@/components/charts/apex'

// Shared content height for every widget card in the grid below — chart
// heights and capped/scrollable list heights all use this same number so
// cards stay visually consistent regardless of how much content they hold.
const WIDGET_H = 220

const route = useRoute()
const store = useProjectStore()

const loading    = ref(true)
const allIssues  = ref([])
const activity   = ref([])

const milestones       = ref([])
const risks            = ref([])
const showAddMilestone = ref(false)
const showAddRisk      = ref(false)
const savingMilestone  = ref(false)
const savingRisk       = ref(false)
const newMilestone     = ref({ title: '', due_date: '', billing_type: 'None', invoice_amount: null, invoice_percent: null })
const newRisk          = ref({ title: '', severity: 'medium' })

const projectKey = computed(() => route.params.key)
const project    = computed(() => store.currentProject)

// ── Health pulse ────────────────────────────────────────────────────────────
// project.health is server-resolved (manual health_override if set, else
// derived from overdue/completion — see _project_health_label in board.py).
const healthLabel = computed(() => project.value?.health || 'On track')
const HEALTH_CHIP = {
  'On track': 'text-success-soft-foreground border-success bg-success-soft',
  'At risk':  'text-warning-soft-foreground border-warning bg-warning-soft',
  'Off track':'text-danger-soft-foreground  border-danger  bg-danger-soft',
}
const HEALTH_DOT = { 'On track': 'bg-success', 'At risk': 'bg-warning', 'Off track': 'bg-danger' }
const healthChipClass = computed(() => HEALTH_CHIP[healthLabel.value] || 'text-muted border-border bg-surface-secondary')
const healthDotClass  = computed(() => HEALTH_DOT[healthLabel.value] || 'bg-muted')

async function setHealthOverride(value) {
  if (!project.value) return
  try {
    await updateProjectGeneral(project.value.name, { health_override: value || null })
    // Re-resolved `health` (auto vs override) only exists on get_board's
    // payload, not on update_project_general's return — refetch so the
    // chip reflects the server-computed value instead of going stale.
    await store.fetchBoard(project.value.name)
    toast.success(value ? `Health set to ${value}` : 'Health set to auto')
  } catch (e) {
    toast.error(e.message || 'Failed to update health')
  }
}

onMounted(() => loadData())
watch(projectKey, () => loadData())

async function loadData() {
  loading.value = true
  try {
    if (store.currentProject?.key !== projectKey.value) {
      if (!store.projects.length) await store.fetchProjects()
      const p = store.projects.find(x => x.key === projectKey.value)
      if (p) await store.fetchBoard(p.name)
    }
    const proj = store.currentProject
    if (!proj) return

    const res = await queryTasks(proj.name, {}, null, 'creation', 'desc', 200)
    if (Array.isArray(res?.issues))      allIssues.value = res.issues
    else if (Array.isArray(res?.groups)) allIssues.value = res.groups.flatMap(g => g.issues || [])
    else if (Array.isArray(res))         allIssues.value = res
    else                                 allIssues.value = []

    try {
      const acts = await frappe.db.get_list('BP Activity', {
        filters: [['task', 'in', allIssues.value.map(i => i.name)]],
        fields:  ['name', 'task', 'task_key', 'action_type', 'old_value', 'new_value', 'user', 'creation'],
        order_by: 'creation desc',
        limit: 30,
      })
      const issueMap = Object.fromEntries(allIssues.value.map(i => [i.name, i]))
      activity.value = acts.map(a => ({
        ...a,
        issue: a.task,
        task_key: a.task_key || issueMap[a.task]?.task_key || a.task,
        action_text: actionText(a),
      }))
    } catch { /* activity is non-critical */ }

    loadMilestonesAndRisks(proj.name)
    loadEpics(proj.name)
    if (proj.project_type && proj.project_type !== 'internal') loadBudgetSummary(proj.name)
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

// ── Milestones & Risks ─────────────────────────────────────────────────────

async function loadMilestonesAndRisks(projectName) {
  try {
    const [ms, rs] = await Promise.all([getMilestones(projectName), getRisks(projectName)])
    milestones.value = Array.isArray(ms) ? ms : []
    risks.value      = Array.isArray(rs) ? rs : []
  } catch { /* non-critical — cards fall back to empty states */ }
}

// Open milestones always show; completed ones only surface here if they're
// still awaiting an invoice — otherwise they'd clutter this overview widget
// and are already reflected in completedMilestonesCount below.
const visibleMilestones = computed(() =>
  milestones.value
    .filter(m => m.status === 'Open' || (m.billing_type && m.billing_type !== 'None' && m.invoice_status !== 'Invoiced'))
    .slice()
    .sort((a, b) => (a.due_date || '9999') < (b.due_date || '9999') ? -1 : 1)
)

const completedMilestonesCount = computed(() =>
  milestones.value.filter(m => m.status === 'Completed').length
)

function milestoneOverdue(m) {
  return m.due_date && new Date(m.due_date) < new Date(new Date().toDateString())
}

function riskDotClass(severity) {
  return {
    low:      'bg-blue-400',
    medium:   'bg-amber-400',
    high:     'bg-orange-500',
    critical: 'bg-red-500',
  }[severity] || 'bg-muted'
}

async function submitMilestone() {
  const title = newMilestone.value.title.trim()
  if (!title || savingMilestone.value) return
  savingMilestone.value = true
  try {
    const doc = await createMilestone(project.value.name, title, newMilestone.value.due_date || null)
    // create_milestone has no billing params — a second call sets them via
    // the same update_milestone path the settings UI would use.
    const billingType = newMilestone.value.billing_type
    if (billingType && billingType !== 'None') {
      const fields = { billing_type: billingType }
      if (billingType === 'Fixed Amount') fields.invoice_amount = newMilestone.value.invoice_amount || 0
      else fields.invoice_percent = newMilestone.value.invoice_percent || 0
      await updateMilestone(doc.name, fields)
      Object.assign(doc, fields)
    }
    milestones.value.push(doc)
    newMilestone.value = { title: '', due_date: '', billing_type: 'None', invoice_amount: null, invoice_percent: null }
    showAddMilestone.value = false
  } catch (e) {
    toast.error("Couldn't add milestone", { description: String(e.message || e) })
  } finally { savingMilestone.value = false }
}

function cancelAddMilestone() {
  showAddMilestone.value = false
  newMilestone.value = { title: '', due_date: '', billing_type: 'None', invoice_amount: null, invoice_percent: null }
}

async function completeMilestone(m) {
  const prev = m.status
  m.status = 'Completed'
  try {
    await updateMilestone(m.name, { status: 'Completed' })
  } catch (e) {
    m.status = prev
    toast.error("Couldn't update milestone", { description: String(e.message || e) })
  }
}

const invoicingMilestone = ref(null)
async function generateMilestoneInvoiceRow(m) {
  if (invoicingMilestone.value) return
  invoicingMilestone.value = m.name
  try {
    const res = await generateMilestoneInvoice(m.name)
    m.invoice_status = 'Invoiced'
    m.sales_invoice = res.sales_invoice
    toast.success(`Draft Sales Invoice ${res.sales_invoice} created`, {
      description: 'Review and submit it in ERPNext.',
      action: { label: 'Open', onClick: () => window.open(`/app/sales-invoice/${encodeURIComponent(res.sales_invoice)}`, '_blank') },
    })
  } catch (e) {
    if (!(e instanceof UpgradeRequiredError)) {
      toast.error("Couldn't generate invoice", { description: String(e.message || e) })
    }
  } finally {
    invoicingMilestone.value = null
  }
}

async function deleteMilestoneRow(m) {
  if (!window.confirm(`Delete "${m.title}"? This can't be undone.`)) return
  const idx = milestones.value.indexOf(m)
  milestones.value = milestones.value.filter(x => x !== m)
  try {
    await deleteMilestone(m.name)
  } catch (e) {
    milestones.value.splice(idx, 0, m)
    toast.error("Couldn't delete milestone", { description: String(e.message || e) })
  }
}

async function submitRisk() {
  const title = newRisk.value.title.trim()
  if (!title || savingRisk.value) return
  savingRisk.value = true
  try {
    const doc = await createRisk(project.value.name, title, newRisk.value.severity)
    risks.value.unshift(doc)
    newRisk.value = { title: '', severity: 'medium' }
    showAddRisk.value = false
  } catch (e) {
    toast.error("Couldn't add risk", { description: String(e.message || e) })
  } finally { savingRisk.value = false }
}

function cancelAddRisk() {
  showAddRisk.value = false
  newRisk.value = { title: '', severity: 'medium' }
}

async function resolveRisk(r) {
  const idx = risks.value.indexOf(r)
  risks.value = risks.value.filter(x => x !== r)
  try {
    await updateRisk(r.name, { status: 'Mitigated' })
  } catch (e) {
    risks.value.splice(idx, 0, r)
    toast.error("Couldn't update risk", { description: String(e.message || e) })
  }
}

async function deleteRiskRow(r) {
  if (!window.confirm(`Delete "${r.title}"? This can't be undone.`)) return
  const idx = risks.value.indexOf(r)
  risks.value = risks.value.filter(x => x !== r)
  try {
    await deleteRisk(r.name)
  } catch (e) {
    risks.value.splice(idx, 0, r)
    toast.error("Couldn't delete risk", { description: String(e.message || e) })
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────

function projectTypeLabel(t) {
  return { internal: 'Internal', fixed: 'Fixed Price', retainer: 'Retainer', tm: 'T&M' }[t] || t
}

function projectTypeBadgeClass(t) {
  return {
    internal: 'bg-surface-secondary border-border text-muted',
    fixed:    'bg-blue-50 border-blue-200 text-blue-700',
    retainer: 'bg-violet-50 border-violet-200 text-violet-700',
    tm:       'bg-amber-50 border-amber-200 text-amber-700',
  }[t] || 'bg-surface-secondary border-border text-muted'
}

function actionText(a) {
  if (a.action_type === 'Created')       return 'created'
  if (a.action_type === 'Status Change') return 'changed status to'
  if (a.action_type === 'Assignment')    return 'was assigned on'
  if (a.action_type === 'Comment')       return 'commented on'
  return 'updated'
}

function activityIcon(type) {
  if (type === 'Created')       return FilePlus2
  if (type === 'Status Change') return RefreshCw
  if (type === 'Assignment')    return User
  if (type === 'Comment')       return MessageSquare
  return Activity
}

function shortUser(user) {
  if (!user) return 'Someone'
  const name = user.split('@')[0].replace(/[._]/g, ' ')
  return name.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

function relTime(ts) {
  const diff = Date.now() - new Date(ts).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1)  return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function statusBadgeStyle(status) {
  const s = store.workflowStateMap?.[status]
  if (!s) return { background: 'var(--surface-secondary)', color: 'var(--muted)' }
  return { background: s.color + '18', color: s.color, border: `1px solid ${s.color}30` }
}

// ── Computed data ──────────────────────────────────────────────────────────

const now             = new Date()
const sevenDaysAgo    = new Date(now - 7 * 86400000)
const fourteenDaysAgo = new Date(now - 14 * 86400000)
const sevenDaysAhead  = new Date(now.getTime() + 7 * 86400000)

const completedStatuses = computed(() =>
  (store.workflowStates || []).filter(s => s.category === 'completed').map(s => s.name)
)

const openIssues = computed(() =>
  allIssues.value.filter(i => !completedStatuses.value.includes(i.status))
)

const stats = computed(() => {
  const issues = allIssues.value
  const completedThisWeek = issues.filter(i =>
    completedStatuses.value.includes(i.status) && new Date(i.modified) >= sevenDaysAgo
  ).length
  const completedPriorWeek = issues.filter(i =>
    completedStatuses.value.includes(i.status) &&
    new Date(i.modified) >= fourteenDaysAgo && new Date(i.modified) < sevenDaysAgo
  ).length
  const overdue = openIssues.value.filter(i =>
    i.due_date && new Date(i.due_date) < now
  ).length
  const overduePrior = issues.filter(i =>
    !completedStatuses.value.includes(i.status) &&
    i.due_date && new Date(i.due_date) < sevenDaysAgo
  ).length
  return {
    open:             openIssues.value.length,
    completed:        completedThisWeek,
    completedPrior:   completedPriorWeek,
    overdue,
    overduePrior,
    dueSoon: openIssues.value.filter(i =>
      i.due_date && new Date(i.due_date) <= sevenDaysAhead && new Date(i.due_date) >= now
    ).length,
  }
})

function trendDelta(current, prior) {
  if (prior === 0) return current > 0 ? current : null
  return current - prior
}

const metrics = computed(() => [
  {
    label: 'Open Tasks',
    value: stats.value.open,
  },
  {
    label: 'Completed This Week',
    value: stats.value.completed,
    trend: stats.value.completedPrior !== undefined
      ? { delta: trendDelta(stats.value.completed, stats.value.completedPrior), period: 'vs last week' }
      : undefined,
  },
  {
    label: 'Overdue',
    value: stats.value.overdue,
    trend: { delta: trendDelta(stats.value.overdue, stats.value.overduePrior), period: 'vs last week' },
  },
  {
    label: 'Due This Week',
    value: stats.value.dueSoon,
  },
].map(m => ({ ...m, trend: m.trend?.delta != null ? m.trend : undefined })))

const totalIssues = computed(() => allIssues.value.length)

const statusBreakdown = computed(() => {
  const counts = {}
  for (const i of allIssues.value) counts[i.status] = (counts[i.status] || 0) + 1
  return (store.workflowStates || [])
    .filter(s => counts[s.name])
    .map(s => ({ name: s.name, color: s.color, count: counts[s.name] }))
})

const statusChartItems = computed(() =>
  statusBreakdown.value.map(s => ({ label: s.name, value: s.count, color: s.color }))
)

// ── Priority breakdown (reuses PRIORITY_PILL's colors — same priority,
// same color everywhere on this page, see the "Needs attention" table) ──
const PRIORITY_ORDER = ['highest', 'high', 'medium', 'low', 'lowest']
const priorityChartItems = computed(() => {
  const counts = {}
  for (const i of allIssues.value) {
    const k = (i.priority || '').toLowerCase()
    if (PRIORITY_PILL[k]) counts[k] = (counts[k] || 0) + 1
  }
  return PRIORITY_ORDER
    .filter(k => counts[k])
    .map(k => ({ label: PRIORITY_PILL[k].label, value: counts[k], color: PRIORITY_PILL[k].color }))
})

// ── Types of work — plain % list (InlineProgress), matching how Jira
// itself renders this (no chart needed for 2-4 categories) ──────────────
const workTypeItems = computed(() => {
  const counts = {}
  for (const i of allIssues.value) {
    const t = i.task_type || 'Task'
    counts[t] = (counts[t] || 0) + 1
  }
  const total = totalIssues.value || 1
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([label, n]) => ({ label, pct: Math.round((n / total) * 100) }))
})

// ── Team workload — open tasks per assignee, explicit "Unassigned" bucket ──
const workloadItems = computed(() => {
  const counts = {}
  for (const i of openIssues.value) {
    const names = (i.assignees || []).map(a => a.full_name || a.user)
    if (!names.length) { counts['Unassigned'] = (counts['Unassigned'] || 0) + 1; continue }
    for (const n of names) counts[n] = (counts[n] || 0) + 1
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([label, value]) => ({ label, value, color: label === 'Unassigned' ? 'var(--muted)' : undefined }))
})

// ── Epic progress ──────────────────────────────────────────────────────────
const epics = ref([])
async function loadEpics(projectName) {
  try {
    const res = await getEpics(projectName)
    epics.value = Array.isArray(res) ? res : []
  } catch { /* non-critical — card falls back to empty state */ }
}

// ── Budget utilization (billable projects only) ─────────────────────────────
const budgetSummary = ref(null)
async function loadBudgetSummary(projectName) {
  try {
    budgetSummary.value = await getProjectBudgetSummary(projectName)
  } catch { /* non-critical — card falls back to empty state */ }
}

// ── Weekly created vs completed bins (past 8 weeks) — feeds the scope-creep
// signal and the two Apex trend widgets below (creation trend, cycle time).
const CHART_WEEKS = 8

const weeklyChart = computed(() => {
  const bins = []
  for (let w = CHART_WEEKS - 1; w >= 0; w--) {
    const start = new Date(now - (w + 1) * 7 * 86400000)
    const end   = new Date(now - w * 7 * 86400000)
    bins.push({
      label:     fmtWeekLabel(start),
      created:   allIssues.value.filter(i => {
        const d = new Date(i.creation)
        return d >= start && d < end
      }).length,
      completed: allIssues.value.filter(i => {
        const d = new Date(i.modified)
        return completedStatuses.value.includes(i.status) && d >= start && d < end
      }).length,
    })
  }

  const weeksWithData = bins.filter(b => b.created > 0 || b.completed > 0).length
  if (weeksWithData < 3) return null

  return { bins }
})

// Scope creep signal: created meaningfully outpacing completed over the window.
const scopeCreepWarning = computed(() => {
  const wc = weeklyChart.value
  if (!wc) return false
  const totalCreated   = wc.bins.reduce((s, b) => s + b.created, 0)
  const totalCompleted = wc.bins.reduce((s, b) => s + b.completed, 0)
  return totalCreated > totalCompleted * 1.3 && totalCreated - totalCompleted >= 3
})

function fmtWeekLabel(d) {
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// ── Work item creation trend — reuses weeklyChart's already-computed bins ──
const creationTrendItems = computed(() =>
  (weeklyChart.value?.bins || []).map(b => ({ label: b.label, value: b.created }))
)

// ── Work item cycle time — avg days from creation to completion, per week.
// Uses `modified` as the completion timestamp, same proxy already used by
// `stats`/`weeklyChart` above (completed_on isn't reliably populated across
// the app; modified-on-a-completed-status task is the established signal
// this file already relies on). ──────────────────────────────────────────
const cycleTimeTrendItems = computed(() => {
  const bins = []
  for (let w = CHART_WEEKS - 1; w >= 0; w--) {
    const start = new Date(now - (w + 1) * 7 * 86400000)
    const end   = new Date(now - w * 7 * 86400000)
    const completedInWeek = allIssues.value.filter(i => {
      const d = new Date(i.modified)
      return completedStatuses.value.includes(i.status) && d >= start && d < end
    })
    const avgDays = completedInWeek.length
      ? completedInWeek.reduce((sum, i) => sum + (new Date(i.modified) - new Date(i.creation)) / 86400000, 0) / completedInWeek.length
      : 0
    bins.push({ label: fmtWeekLabel(start), value: Math.round(avgDays * 10) / 10 })
  }
  return bins
})
function fmtDays(n) { return `${n}d` }

// ── Needs attention ────────────────────────────────────────────────────────

const HIGH_PRIORITIES = new Set(['highest', 'high'])

function isOverdue(issue) {
  return issue.due_date && new Date(issue.due_date) < now &&
    !completedStatuses.value.includes(issue.status)
}

const attentionTasks = computed(() => {
  const seen = new Set()
  const result = []

  const add = (issue) => {
    if (!seen.has(issue.name)) {
      seen.add(issue.name)
      result.push(issue)
    }
  }

  // Overdue first
  for (const i of openIssues.value) {
    if (i.due_date && new Date(i.due_date) < now) add(i)
  }
  // Due in next 7 days
  for (const i of openIssues.value) {
    if (i.due_date && new Date(i.due_date) <= sevenDaysAhead && new Date(i.due_date) >= now) add(i)
  }
  // High / Highest priority not already added
  for (const i of openIssues.value) {
    if (HIGH_PRIORITIES.has((i.priority || '').toLowerCase())) add(i)
  }

  return result.slice(0, 10)
})

const attentionColumns = [
  { key: 'priority', label: 'Priority', width: '90px'  },
  { key: 'title',    label: 'Task'                     },
  { key: 'assignee', label: 'Assignee', width: '130px' },
  { key: 'status',   label: 'Status',   width: '140px' },
  { key: 'due',      label: 'Due',      width: '80px'  },
]

const PRIORITY_PILL = {
  highest: { label: 'Highest', bg: '#FEE2E2', color: '#DC2626' },
  high:    { label: 'High',    bg: '#FFEDD5', color: '#EA580C' },
  medium:  { label: 'Medium',  bg: '#FEF9C3', color: '#CA8A04' },
  low:     { label: 'Low',     bg: '#DBEAFE', color: '#2563EB' },
  lowest:  { label: 'Lowest',  bg: '#F3F4F6', color: '#6B7280' },
}

function priorityPill(priority) {
  return PRIORITY_PILL[(priority || '').toLowerCase()] || PRIORITY_PILL.lowest
}
</script>
