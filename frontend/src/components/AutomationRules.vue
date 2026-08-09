<template>
  <div>
    <!-- Header -->
    <div class="flex items-start justify-between mb-4">
      <div>
        <h1 class="text-[15px] font-semibold text-foreground tracking-[-0.01em] flex items-center gap-2">
          Automations
          <span v-if="!unlocked"
            class="inline-flex items-center gap-1 text-[10.5px] font-semibold px-1.5 py-0.5 rounded
                   bg-[var(--surface-secondary)] text-muted uppercase tracking-wider">
            <Icon :icon="Lock" class="size-3" /> {{ requiredPlan }}
          </span>
        </h1>
        <p class="text-[13px] text-muted mt-1">
          When something happens, automatically do something else — no clicks required.
        </p>
      </div>
      <Button v-if="unlocked && activeTab === 'manage'" size="sm" color="primary" @click="openEditor()">
        <Icon :icon="Plus" class="size-3.5 mr-1" /> New rule
      </Button>
    </div>

    <!-- Premium lock banner -->
    <div v-if="!unlocked"
      class="mb-5 rounded-lg border border-[var(--border-secondary)] overflow-hidden">
      <div class="px-5 py-5 flex items-start gap-4 bg-accent-soft">
        <span class="size-10 rounded-lg bg-overlay border border-border flex items-center justify-center shrink-0 shadow-sm">
          <Icon :icon="Zap" class="size-5 text-accent" />
        </span>
        <div class="min-w-0 flex-1">
          <p class="text-[14px] font-semibold text-foreground">Put your busywork on autopilot</p>
          <p class="text-[13px] text-muted mt-1 leading-relaxed">
            Auto-assign incoming work, move tasks across columns, notify the right people, and
            spin up follow-up tasks — all without lifting a finger. Available on the
            <span class="font-semibold text-foreground">{{ requiredPlan }}</span> plan and above.
          </p>
          <div class="flex items-center gap-2 mt-3">
            <Button size="sm" color="primary" @click="goUpgrade">
              <Icon :icon="Sparkles" class="size-3.5 mr-1" /> Upgrade to {{ requiredPlan }}
            </Button>
            <span class="text-[12px] text-muted">You're on the {{ ent.tierLabel }} plan</span>
          </div>
        </div>
      </div>
    </div>

    <Tabs v-model="activeTab" variant="underline" class="mb-4"
      :tabs="[{value:'create',label:'Create'},{value:'manage',label:`Manage${rules.length ? ' ('+rules.length+')' : ''}`},{value:'runs',label:'Run history'},{value:'workflows',label:`Workflows${workflows.length ? ' ('+workflows.length+')' : ''}`}]" />

    <!-- ══════════════ CREATE TAB — recipe gallery ══════════════ -->
    <TabsPanel v-if="unlocked" :model-value="activeTab" value="create">
      <div class="flex gap-5">
        <!-- Category rail -->
        <div class="w-40 shrink-0 space-y-0.5">
          <button v-for="c in visibleCategories" :key="c.id" type="button"
            class="w-full text-left px-2.5 py-1.5 rounded-md text-[13px] transition-colors"
            :class="activeCategory === c.id ? 'bg-accent-soft text-accent font-medium' : 'text-muted hover:bg-default hover:text-foreground'"
            @click="activeCategory = c.id">
            {{ c.label }}
          </button>
        </div>

        <div class="flex-1 min-w-0">
          <Input v-model="recipeQuery" size="md" is-clearable placeholder="Tell us what you're trying to automate…" full-width>
            <template #startContent><Icon :icon="Search" class="size-4 text-muted" /></template>
          </Input>

          <template v-if="!recipeQuery">
            <p class="text-[11px] font-semibold text-muted uppercase tracking-wider mt-5 mb-2">Start with the basics</p>
            <div class="grid grid-cols-2 gap-2.5">
              <button v-for="r in featuredRecipes" :key="r.id" type="button"
                class="text-left rounded-lg border border-border bg-overlay p-3.5 hover:border-accent hover:shadow-xs transition-all"
                @click="pickRecipe(r)">
                <p class="text-[13px] font-medium text-foreground">{{ r.label }}</p>
                <p class="text-[12px] text-muted mt-1 leading-snug">{{ recipeSentenceText(r) }}</p>
              </button>
              <button type="button"
                class="text-left rounded-lg border border-dashed border-border bg-transparent p-3.5 hover:border-accent transition-all flex items-center gap-2.5"
                @click="openEditor()">
                <span class="size-8 rounded-md bg-[var(--surface-secondary)] flex items-center justify-center shrink-0">
                  <Icon :icon="Plus" class="size-4 text-muted" />
                </span>
                <span>
                  <p class="text-[13px] font-medium text-foreground">Create from scratch</p>
                  <p class="text-[12px] text-muted">Build a custom rule step by step</p>
                </span>
              </button>
            </div>
          </template>

          <template v-else>
            <p class="text-[11px] font-semibold text-muted uppercase tracking-wider mt-5 mb-2">
              {{ searchedRecipes.length }} result{{ searchedRecipes.length === 1 ? '' : 's' }}
            </p>
            <div v-if="searchedRecipes.length" class="grid grid-cols-2 gap-2.5">
              <button v-for="r in searchedRecipes" :key="r.id" type="button"
                class="text-left rounded-lg border border-border bg-overlay p-3.5 hover:border-accent hover:shadow-xs transition-all"
                @click="pickRecipe(r)">
                <p class="text-[13px] font-medium text-foreground">{{ r.label }}</p>
                <p class="text-[12px] text-muted mt-1 leading-snug">{{ recipeSentenceText(r) }}</p>
              </button>
            </div>
            <EmptyState v-else :icon="Search" title="No matching recipes"
              description="Try a different search, or build the rule yourself.">
              <template #action>
                <Button size="sm" variant="bordered" @click="openEditor()">Create from scratch</Button>
              </template>
            </EmptyState>
          </template>

          <template v-if="!recipeQuery && activeCategory !== 'all'">
            <p class="text-[11px] font-semibold text-muted uppercase tracking-wider mt-6 mb-2">
              {{ RECIPE_CATEGORIES.find(c => c.id === activeCategory)?.label }}
            </p>
            <div class="grid grid-cols-2 gap-2.5">
              <button v-for="r in categoryRecipes" :key="r.id" type="button"
                class="text-left rounded-lg border border-border bg-overlay p-3.5 hover:border-accent hover:shadow-xs transition-all"
                @click="pickRecipe(r)">
                <p class="text-[13px] font-medium text-foreground">{{ r.label }}</p>
                <p class="text-[12px] text-muted mt-1 leading-snug">{{ recipeSentenceText(r) }}</p>
              </button>
            </div>
          </template>
        </div>
      </div>
    </TabsPanel>

    <!-- ══════════════ MANAGE TAB ══════════════ -->
    <TabsPanel :model-value="activeTab" value="manage">
      <div v-if="unlocked" class="flex items-center gap-2 mb-3">
        <Input v-model="manageQuery" size="sm" is-clearable placeholder="Search rules…" class="max-w-[260px]">
          <template #startContent><Icon :icon="Search" class="size-3.5 text-muted" /></template>
        </Input>
        <Select v-model="manageStatusFilter" size="sm" class="w-[130px]">
          <SelectItem value="all">All rules</SelectItem>
          <SelectItem value="active">Active</SelectItem>
          <SelectItem value="paused">Paused</SelectItem>
        </Select>
      </div>

      <EmptyState v-if="unlocked && !rules.length" :icon="Zap" title="No automations yet"
        description="Create your first rule to save your team from repetitive clicks.">
        <template #action>
          <Button size="sm" color="primary" @click="activeTab = 'create'">Browse recipes</Button>
        </template>
      </EmptyState>

      <EmptyState v-else-if="unlocked && !filteredRules.length" :icon="Search" title="No matching rules"
        description="Try a different search or filter." />

      <div v-if="rules.length" class="divide-y divide-[var(--border-secondary)] rounded-md border border-border overflow-hidden"
        :class="!unlocked && 'opacity-60'">
        <div v-for="r in filteredRules" :key="r.name"
          class="flex items-start gap-3 px-4 py-3 bg-overlay">
          <span class="size-8 rounded-md bg-[var(--surface-secondary)] flex items-center justify-center shrink-0 relative mt-0.5">
            <Icon :icon="actionIcon(r.actions?.[0]?.type)" class="size-4 text-foreground" />
            <span v-if="r.last_run_status" class="absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full border-2 border-overlay"
              :class="runDotClass(r.last_run_status)" />
          </span>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5 flex-wrap">
              <p class="text-[13px] font-medium text-foreground">{{ r.rule_name }}</p>
              <Chip size="sm" variant="soft">{{ r.scope === 'workspace' ? 'All projects' : (r.project === project ? 'This project' : r.project) }}</Chip>
            </div>
            <!-- Bold-token sentence — the SAME renderer the builder's own hero uses. -->
            <p class="text-[12.5px] text-muted mt-0.5 leading-snug">
              <span v-for="(s, i) in ruleSentence(r, options)" :key="i" :class="s.bold ? 'ars-token' : ''">{{ s.text }}</span>
            </p>
            <p class="text-[11.5px] text-muted mt-1 flex items-center gap-1.5 flex-wrap">
              <span>Updated {{ relativeTime(r.modified) }}</span>
              <span class="opacity-50">·</span>
              <Avatar :name="r.owner" size="xs" />
              <span>{{ r.owner }}</span>
              <template v-if="r.description">
                <span class="opacity-50">·</span>
                <span class="truncate max-w-[220px]">{{ r.description }}</span>
              </template>
            </p>
          </div>
          <Switch :isSelected="!!r.is_active" :isDisabled="!unlocked" @update:isSelected="v => toggle(r, v)" />
          <Dropdown placement="bottom-end">
            <template #trigger>
              <IconButton size="sm" variant="light" aria-label="More">
                <Icon :icon="MoreHorizontal" class="size-3.5 text-muted" />
              </IconButton>
            </template>
            <DropdownItem :disabled="!unlocked" @click="openEditor(r)">
              <template #startContent><Icon :icon="Pencil" class="size-3.5" /></template>
              Edit
            </DropdownItem>
            <DropdownItem :disabled="!unlocked" @click="doDuplicate(r)">
              <template #startContent><Icon :icon="Copy" class="size-3.5" /></template>
              Duplicate
            </DropdownItem>
            <DropdownItem @click="openRuns(r)">
              <template #startContent><Icon :icon="History" class="size-3.5" /></template>
              View runs
            </DropdownItem>
            <DropdownItem :disabled="!unlocked" @click="askConvert(r)">
              <template #startContent><Icon :icon="GitBranch" class="size-3.5" /></template>
              Convert to advanced workflow
            </DropdownItem>
            <DropdownItem color="danger" @click="askRemove(r)">
              <template #startContent><Icon :icon="Trash2" class="size-3.5" /></template>
              Delete
            </DropdownItem>
          </Dropdown>
        </div>
      </div>
    </TabsPanel>

    <!-- ══════════════ RUN HISTORY TAB ══════════════ -->
    <TabsPanel :model-value="activeTab" value="runs">
      <div v-if="rules.length" class="flex items-center gap-2 mb-3">
        <Select v-model="runsFilterRuleName" size="sm" class="w-[240px]">
          <SelectItem value="">All rules</SelectItem>
          <SelectItem v-for="r in rules" :key="r.name" :value="r.name">{{ r.rule_name }}</SelectItem>
        </Select>
      </div>
      <div v-if="runsLoading" class="py-10 text-center text-[13px] text-muted">Loading…</div>
      <EmptyState v-else-if="!runs.length" :icon="History" title="No runs yet"
        description="Rule activity will appear here once your automations fire." />
      <div v-else class="divide-y divide-separator rounded-md border border-border overflow-hidden">
        <div v-for="run in runs" :key="run.name" class="flex items-start gap-3 px-4 py-2.5 bg-overlay">
          <Icon :icon="(runStatusMeta[run.status] || runStatusMeta.Skipped).icon"
            class="size-4 mt-0.5 shrink-0" :class="(runStatusMeta[run.status] || runStatusMeta.Skipped).cls" />
          <div class="min-w-0 flex-1">
            <p class="text-[13px] text-foreground truncate">
              <span class="font-medium">{{ run.rule_name }}</span>
              <span v-if="run.action_type" class="text-muted"> · #{{ (run.action_index ?? 0) + 1 }} {{ run.action_type }}</span>
            </p>
            <p class="text-[12px] text-muted truncate">{{ run.message }}</p>
          </div>
          <div class="text-right shrink-0">
            <Chip v-if="run.task_key" size="sm" variant="soft" color="accent" class="font-mono">{{ run.task_key }}</Chip>
            <p class="text-[11px] text-muted mt-1 tabular-nums">{{ fmtRunTime(run.run_at) }}</p>
          </div>
        </div>
      </div>
    </TabsPanel>

    <!-- ══════════════ WORKFLOWS TAB — graph canvas ═══════════════ -->
    <TabsPanel :model-value="activeTab" value="workflows">
      <div v-if="unlocked" class="flex items-center justify-between mb-3">
        <p class="text-[13px] text-muted">
          Multi-step, branching automations with external integrations — the visual builder.
        </p>
        <Button size="sm" variant="bordered" @click="newWorkflow">
          <Icon :icon="Plus" class="size-3.5 mr-1" /> New workflow
        </Button>
      </div>

      <EmptyState v-if="unlocked && !workflows.length" :icon="GitBranch" title="No workflows yet"
        description="Build a multi-step automation with branches, retries, and external HTTP calls.">
        <template #action>
          <Button size="sm" color="primary" @click="newWorkflow">Open the workflow builder</Button>
        </template>
      </EmptyState>

      <div v-else-if="workflows.length" class="divide-y divide-[var(--border-secondary)] rounded-md border border-border overflow-hidden"
        :class="!unlocked && 'opacity-60'">
        <div v-for="wf in workflows" :key="wf.name"
          class="w-full flex items-start gap-3 px-4 py-3 bg-overlay hover:bg-surface-hover transition-colors">
          <button type="button" class="flex-1 min-w-0 flex items-start gap-3 text-left" @click="openWorkflow(wf)">
            <span class="size-8 rounded-md bg-[var(--surface-secondary)] flex items-center justify-center shrink-0 relative mt-0.5">
              <Icon :icon="GitBranch" class="size-4 text-foreground" />
              <span v-if="wf.last_run_status" class="absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full border-2 border-overlay"
                :class="runDotClass(wf.last_run_status)" />
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5 flex-wrap">
                <p class="text-[13px] font-medium text-foreground">{{ wf.title }}</p>
                <Chip size="sm" variant="soft">{{ wf.scope === 'workspace' ? 'All projects' : (wf.project === project ? 'This project' : wf.project) }}</Chip>
              </div>
              <p class="text-[11.5px] text-muted mt-1">
                <span v-if="wf.last_run_at">Last ran {{ relativeTime(wf.last_run_at) }} · {{ wf.last_run_status }}</span>
                <span v-else>Never run yet</span>
              </p>
            </div>
          </button>
          <IconButton size="sm" variant="light" :isDisabled="!unlocked" aria-label="Delete" @click="askRemoveWorkflow(wf)">
            <Icon :icon="Trash2" class="size-3.5 text-muted" />
          </IconButton>
        </div>
      </div>
    </TabsPanel>

    <AutomationRuleEditor v-model:open="editorOpen" :rule="editingRule" :options="options"
      :mode="mode" :project="project" :recipe-draft="pendingRecipeDraft" @saved="onSaved" />

    <!-- Delete confirm -->
    <Modal :open="!!deleting" size="sm" @update:open="v => !v && (deleting = null)">
      <ModalHeader @close="deleting = null">Delete rule?</ModalHeader>
      <ModalBody>
        <p class="text-[13px] text-muted">"{{ deleting?.rule_name }}" will be permanently removed. This can't be undone.</p>
      </ModalBody>
      <ModalFooter>
        <Button size="sm" variant="light" @click="deleting = null">Cancel</Button>
        <Button size="sm" color="danger" @click="confirmRemove">Delete</Button>
      </ModalFooter>
    </Modal>

    <!-- Delete workflow confirm -->
    <Modal :open="!!deletingWorkflow" size="sm" @update:open="v => !v && (deletingWorkflow = null)">
      <ModalHeader @close="deletingWorkflow = null">Delete workflow?</ModalHeader>
      <ModalBody>
        <p class="text-[13px] text-muted">"{{ deletingWorkflow?.title }}" will be permanently removed. This can't be undone.</p>
      </ModalBody>
      <ModalFooter>
        <Button size="sm" variant="light" @click="deletingWorkflow = null">Cancel</Button>
        <Button size="sm" color="danger" @click="confirmRemoveWorkflow">Delete</Button>
      </ModalFooter>
    </Modal>

    <!-- Convert to workflow confirm (WORKPLAN-PHASE25 A5) -->
    <Modal :open="!!converting" size="sm" @update:open="v => !v && (converting = null)">
      <ModalHeader @close="converting = null">Convert to advanced workflow?</ModalHeader>
      <ModalBody>
        <p class="text-[13px] text-muted">
          Creates a draft workflow you can extend with branches and integrations. Your rule keeps
          running until you activate the workflow and pause the rule.
        </p>
      </ModalBody>
      <ModalFooter>
        <Button size="sm" variant="light" :is-disabled="convertBusy" @click="converting = null">Cancel</Button>
        <Button size="sm" color="primary" :is-loading="convertBusy" @click="confirmConvert">Convert</Button>
      </ModalFooter>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import {
  Button, IconButton, Icon, Modal, ModalHeader, ModalBody, ModalFooter, Switch, Chip,
  Tabs, TabsPanel, Input, Select, SelectItem, EmptyState, Dropdown, DropdownItem, Avatar,
} from '@/ui'
import {
  Plus, Lock, Zap, Sparkles, Pencil, Trash2, Copy, Search, MoreHorizontal,
  ArrowRightCircle, UserPlus, Bell, FilePlus,
  Flag, CalendarClock, Tag, MessageSquare, History, CheckCircle2, MinusCircle, AlertCircle,
  FilePenLine, GitBranch, Mail,
} from 'lucide-vue-next'
import { useEntitlementsStore } from '@/stores/entitlements'
import { UpgradeRequiredError } from '@/utils/api'
import AutomationRuleEditor from '@/components/AutomationRuleEditor.vue'
import { ruleSentence, ruleSentenceText } from '@/utils/automationSentence'
import { AUTOMATION_RECIPES, RECIPE_CATEGORIES, filterRecipes } from '@/constants/automation-recipes'
import * as api from '@/utils/api'

const props = defineProps({
  project: { type: String, default: null },
  /** 'project' (default) — Project Settings' own automations list, scoped to
   * `project` plus every workspace-scope rule whose project_filter matches
   * it. 'workspace' — Workspace Settings' "Automations" tab: every rule
   * across the workspace, `project=null`. */
  mode: { type: String, default: 'project' },
})
const project = props.project
const router = useRouter()
const ent = useEntitlementsStore()

const unlocked = computed(() => ent.can('automations'))
const requiredPlan = computed(() => ent.requiredPlanFor('automations'))

const activeTab = ref('manage')
const rules = ref([])
const options = ref({
  triggers: [], actions: [], operators: [], condition_fields: [], statuses: [], task_types: [],
  members: [], labels: [], priorities: [], gateway_engine: false, erpnext_update_doctypes: [],
  projects: [], field_changed_fields: [], relative_date_fields: [],
})
const editorOpen = ref(false)
const editingRule = ref(null)
const pendingRecipeDraft = ref(null)

onMounted(load)
watch(() => props.project, load)
// Land on Create the first time an unlocked workspace has zero rules — the
// gallery IS the empty state, not a dead-end "no rules" card.
watch([unlocked, rules], ([u, rs]) => {
  if (u && !rs.length) activeTab.value = 'create'
}, { immediate: true })

async function load() {
  // Project mode with no project: nothing to load.
  if (props.mode === 'project' && !props.project) return
  // Workspace mode with no project: can't call project-scoped endpoints;
  // keep the default options (triggers/actions from constants are fine)
  // so the recipe gallery still works. Workspace-scoped rules would need
  // a separate backend endpoint.
  if (!props.project) { rules.value = []; return }
  try {
    const [opts, rs] = await Promise.all([
      api.getAutomationOptions(props.project),
      api.getAutomationRules(props.project),
    ])
    options.value = opts
    rules.value = rs
  } catch (e) { /* viewer with no access — leave empty */ }
}

// ── Workflows tab — the node-graph canvas builder, lives
// alongside the flat rules above rather than replacing them ──
const workflows = ref([])
async function loadWorkflows() {
  if (!unlocked.value) return
  try { workflows.value = await api.listWorkflows(props.project) }
  catch (e) { workflows.value = [] /* workspace-scope call needs admin, project-scope needs viewer — 403 just leaves it empty */ }
}
watch([unlocked, () => props.project], loadWorkflows, { immediate: true })

function newWorkflow() {
  router.push({ name: 'AutomationCanvas', query: props.mode === 'project' && project ? { project } : {} })
}
function openWorkflow(wf) {
  router.push({ name: 'AutomationCanvas', params: { workflowId: wf.name } })
}

function openEditor(rule = null) {
  pendingRecipeDraft.value = null
  editingRule.value = rule
  editorOpen.value = true
}
function pickRecipe(recipe) {
  editingRule.value = null
  pendingRecipeDraft.value = { rule_name: recipe.label, ...recipe.draft }
  editorOpen.value = true
}
function onSaved() {
  load()
  activeTab.value = 'manage'
}

async function toggle(rule, val) {
  try {
    await api.toggleAutomationRule(rule.name, val)
    rule.is_active = val ? 1 : 0
  } catch (e) { handleErr(e); await load() }
}

async function doDuplicate(rule) {
  try {
    await api.duplicateAutomationRule(rule.name)
    toast.success('Rule duplicated', { description: 'The copy starts paused — review and enable it.' })
    await load()
  } catch (e) { handleErr(e) }
}

const deleting = ref(null)
function askRemove(rule) { deleting.value = rule }
async function confirmRemove() {
  const rule = deleting.value
  deleting.value = null
  if (!rule) return
  try { await api.deleteAutomationRule(rule.name); await load() }
  catch (e) { handleErr(e) }
}

const deletingWorkflow = ref(null)
function askRemoveWorkflow(wf) { deletingWorkflow.value = wf }
async function confirmRemoveWorkflow() {
  const wf = deletingWorkflow.value
  deletingWorkflow.value = null
  if (!wf) return
  try { await api.deleteWorkflow(wf.name); await loadWorkflows() }
  catch (e) { handleErr(e) }
}

// A5: rule -> workflow conversion — deterministic, lossless (see
// convert_rule_to_workflow's own docstring). The source rule is left
// completely untouched and still running; only navigation + a toast here.
const converting = ref(null)
const convertBusy = ref(false)
function askConvert(rule) { converting.value = rule }
async function confirmConvert() {
  const rule = converting.value
  if (!rule) return
  convertBusy.value = true
  const returnTo = router.currentRoute.value.fullPath
  try {
    const res = await api.convertRuleToWorkflow(rule.name)
    converting.value = null
    toast.success('Draft workflow created', {
      description: `"${rule.rule_name}" keeps running until you activate the workflow and pause it.`,
      action: { label: 'Open original rule', onClick: () => router.push(returnTo) },
    })
    router.push({ name: 'AutomationCanvas', params: { workflowId: res.name } })
  } catch (e) {
    handleErr(e)
  } finally {
    convertBusy.value = false
  }
}

// ── Manage tab: search + status filter ──
const manageQuery = ref('')
const manageStatusFilter = ref('all')
const filteredRules = computed(() => {
  let out = rules.value
  if (manageStatusFilter.value === 'active') out = out.filter(r => r.is_active)
  else if (manageStatusFilter.value === 'paused') out = out.filter(r => !r.is_active)
  const q = manageQuery.value.trim().toLowerCase()
  if (q) {
    out = out.filter(r =>
      r.rule_name.toLowerCase().includes(q) ||
      (r.description || '').toLowerCase().includes(q) ||
      ruleSentenceText(r, options.value).toLowerCase().includes(q)
    )
  }
  return out
})

// ── Create tab: recipe gallery ──
const hasErpTriggers = computed(() => (options.value.triggers || []).some(t => t.value?.startsWith('erp.')))
const visibleCategories = computed(() => [
  { id: 'all', label: 'All' },
  ...RECIPE_CATEGORIES.filter(c => c.id !== 'erp' || hasErpTriggers.value),
])
const activeCategory = ref('all')
const recipeQuery = ref('')
const featuredRecipes = computed(() =>
  AUTOMATION_RECIPES.filter(r => r.featured && (!r.erpOnly || hasErpTriggers.value)))
const searchedRecipes = computed(() => filterRecipes(AUTOMATION_RECIPES, recipeQuery.value, hasErpTriggers.value))
const categoryRecipes = computed(() =>
  AUTOMATION_RECIPES.filter(r => r.category === activeCategory.value && (!r.erpOnly || hasErpTriggers.value)))
function recipeSentenceText(recipe) {
  // Recipes carry a loose draft (partial trig/action cfg) — pad just
  // enough for the shared renderer to read trigger/conditions/actions
  // without needing the full editor-side blankAction() expansion.
  const d = recipe.draft
  return ruleSentenceText({
    trigger_event: d.trigger_event,
    conditions: d.conditions || [],
    actions: (d.actions || []).map(a => ({ type: a.type, config: a.cfg || {} })),
  }, options.value)
}

// ── run history ──
const runsFilterRuleName = ref('')
const runs = ref([])
const runsLoading = ref(false)
async function loadRuns() {
  runsLoading.value = true
  try {
    runs.value = runsFilterRuleName.value
      ? await api.getAutomationRuns({ rule: runsFilterRuleName.value, limit: 20 })
      : await api.getAutomationRuns({ project: props.project, limit: props.mode === 'workspace' ? 100 : 40 })
  } catch { runs.value = [] }
  finally { runsLoading.value = false }
}
watch(runsFilterRuleName, loadRuns)
watch(activeTab, (t) => { if (t === 'runs') loadRuns() })
function openRuns(rule) {
  runsFilterRuleName.value = rule.name
  activeTab.value = 'runs'
}
const runStatusMeta = {
  Success: { icon: CheckCircle2, cls: 'text-success' },
  Skipped: { icon: MinusCircle, cls: 'text-muted' },
  Failed:  { icon: AlertCircle, cls: 'text-danger' },
}
function runDotClass(status) {
  return { Success: 'bg-success', Skipped: 'bg-muted', Failed: 'bg-danger' }[status] || 'bg-muted'
}
function fmtRunTime(s) {
  if (!s) return ''
  try { return new Date(String(s).replace(' ', 'T')).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) }
  catch { return s }
}
function relativeTime(s) {
  if (!s) return ''
  const then = new Date(String(s).replace(' ', 'T')).getTime()
  const diffMin = Math.round((Date.now() - then) / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.round(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  const diffD = Math.round(diffH / 24)
  if (diffD < 30) return `${diffD}d ago`
  return new Date(then).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function handleErr(e) {
  if (e instanceof UpgradeRequiredError) {
    toast.error(e.message, { action: { label: `Upgrade`, onClick: goUpgrade } })
  } else {
    toast.error(e.message || 'Something went wrong')
  }
}

function goUpgrade() {
  router.push({ name: 'Pricing' }).catch(() => { window.location.hash = '#/pricing' })
}

function actionIcon(a) {
  return {
    'Change Status': ArrowRightCircle, 'Assign Issue': UserPlus, 'Set Priority': Flag,
    'Set Due Date': CalendarClock, 'Add Label': Tag, 'Add Comment': MessageSquare,
    'Notify': Bell, 'Create Issue': FilePlus, 'Update ERPNext Document': FilePenLine,
    'Send Email': Mail,
  }[a] || Zap
}
</script>

<style scoped>
.ars-token { font-weight: 600; color: var(--foreground); }
</style>
