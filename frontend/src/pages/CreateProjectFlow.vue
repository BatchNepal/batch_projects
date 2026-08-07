<template>
  <div class="fixed inset-0 z-overlay bg-gray-50 flex flex-col overflow-hidden">

    <!-- ── Top bar ──────────────────────────────────────────────────── -->
    <div class="shrink-0 border-b border-separator shadow-sm bg-surface">
      <div class="max-w-[1980px] w-[90%] mx-auto px-8 h-16 flex items-center justify-between">
        <div class="min-w-0 flex items-center gap-2">
          <div>
            <img src="/images/bp-logo-new.svg" class="w-8 h-8 mr-2 inline-block" />
          </div>
         <div>
           <h2 class="text-lg font-bold text-foreground whitespace-nowrap leading-tight">Create New Project</h2>
          <p class="text-[12.5px] text-muted truncate">{{ STEP_SUBTITLES[step - 1] }}</p>
         </div>
        </div>

        <div class="flex items-center gap-5  shrink-0">
       

          <Button isIconOnly variant="light" color="default" size="sm" aria-label="Close" @click="cancel">
            <X :size="16" :stroke-width="2" />
          </Button>
        </div>
      </div>
    </div>

    <!-- ── Content: left = step, right = live preview ──────────────────
         scrollbar-gutter:stable — steps differ in height, so without it the
         scrollbar pops in/out and shifts the preview pane horizontally. -->
    <div class="flex-1 overflow-y-auto" style="scrollbar-gutter: stable">
      <div class="max-w-7xl mx-auto w-full px-8 py-8 lg:grid lg:grid-cols-[440px_1fr] lg:gap-16 items-start">

        <!-- LEFT — step content -->
        <div class="min-w-0">
          <Transition name="step" mode="out-in">

            <!-- ════ STEP 1 — Template list (full-width rows) ════ -->
            <div v-if="step === 1" key="s1">
              <div v-for="group in templateGroups" :key="group.label" class="mb-6">
                <p class="flex items-center gap-1.5 text-[11px] font-bold text-foreground uppercase tracking-wider mb-2.5">
                  {{ group.label }}
                </p>
                <div class="flex flex-col gap-3">
                  <button
                    v-for="t in group.templates"
                    :key="t.id"
                    type="button"
                    class="cp-row group relative flex items-center gap-3.5 text-left rounded-md bg-surface px-4 py-3 outline-none"
                    :class="{ 'cp-row--selected': form.template === t.id }"
                    @click="form.template = t.id"
                    @dblclick="form.template = t.id; next()"
                  >
                    <div
                      class="w-10 h-10 rounded-md flex items-center justify-center shrink-0 transition-transform duration-150 group-hover:scale-105"
                      :style="{ background: tileColor(t) + '1F', color: tileColor(t) }"
                    >
                      <component :is="t.icon" :size="19" :stroke-width="1.9" />
                    </div>

                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2">
                        <p class="text-[13.5px] font-semibold text-foreground leading-snug">{{ t.label }}</p>
                        <Chip v-if="t.defaultProjectType" size="sm" color="warning" variant="soft">Billable</Chip>
                        <Chip v-if="group.label === 'Your templates' && !ent.can('templates')" size="sm" variant="soft">
                          <Lock :size="10" class="inline -mt-0.5 mr-0.5" /> {{ ent.requiredPlanFor('templates') }}
                        </Chip>
                      </div>
                      <p class="text-[12.5px] text-muted mt-0.5 leading-relaxed truncate">{{ t.description }}</p>
                    </div>

                    <span
                      v-if="form.template === t.id"
                      class="cp-row-check w-5 h-5 rounded-full bg-accent text-accent-foreground flex items-center justify-center shrink-0"
                    >
                      <Check :size="11" :stroke-width="3" />
                    </span>
                    <!-- Was a ChevronRight, which promises navigation — these
                         rows pick one of a set, they don't drill in. An empty
                         ring opposite the filled check reads as the radio
                         group this actually is, and gives every row the same
                         affordance instead of two different ones. -->
                    <span v-else class="cp-row-dot w-5 h-5 rounded-full shrink-0" />
                  </button>
                </div>
              </div>
            </div>

            <!-- ════ STEP 2 — Details ════ -->
            <div v-else-if="step === 2" key="s2">
              <div class="space-y-6">
                <div>
                  <label class="cp-label">Project name <span class="text-danger">*</span></label>
                  <Input
                    v-model="form.name"
                    placeholder="e.g. Website Redesign"
                    size="md"
                    class="bg-white"
                    autofocus
                    @update:modelValue="onNameInput"
                    @keyup.enter="canContinue && next()"
                  />
                </div>

                <div class="flex items-start gap-4">
                  <div class="shrink-0">
                    <label class="cp-label">Avatar</label>
                    <ThemePicker :theme="form.theme" @update:theme="form.theme = $event" />
                  </div>
                  <div class="flex-1 min-w-0 grid grid-cols-2 gap-4">
                    <div>
                      <div class="flex items-center gap-1.5 mb-1.5">
                        <label class="cp-label" style="margin:0">Key <span class="text-danger">*</span></label>
                        <Chip v-if="keyAutoMode" size="sm" color="default" variant="soft">Auto</Chip>
                      </div>
                      <Input
                        v-model="form.key"
                        :isInvalid="!!keyError"
                        :errorMessage="keyError"
                        placeholder="WEB"
                        size="md"
                        class="font-mono uppercase"
                        @update:modelValue="onKeyInput"
                        @focus="onKeyFocus"
                        @blur="onKeyBlur"
                      />
                    </div>
                    <div>
                      <label class="cp-label">Visibility</label>
                      <Select v-model="form.visibility" size="md" :fullWidth="true">
                        <SelectItem v-for="opt in VISIBILITY_OPTIONS" :key="opt.value" :value="opt.value">
                          {{ opt.label }}
                        </SelectItem>
                      </Select>
                    </div>
                  </div>
                </div>

                <div class="pt-5 border-t border-separator">
                  <div class="flex items-center gap-2 mb-4">
                    <label class="cp-label" style="margin:0">Engagement</label>
                    <span class="text-[12px] text-muted">How is this work paid for?</span>
                  </div>
                  <SegmentedRadio v-model="form.type" :options="PROJECT_TYPES" />
                  <Transition name="fade">
                    <BillingFields v-if="billingRequired" :type="form.type" v-model="form.billing" class="mt-5" />
                  </Transition>
                </div>
              </div>
            </div>

            <!-- ════ STEP 3 — Customize ════ -->
            <div v-else key="s3">
              <div class="space-y-7">
                <div>
                  <label class="cp-label">Workflow columns</label>
                  <WorkflowStatesEditor v-model="form.workflowStates" />
                </div>
                <div>
                  <label class="cp-label">Task types</label>
                  <IssueTypesEditor v-model="form.issueTypes" :pool="form.issueTypePool" />
                </div>
              </div>
            </div>

          </Transition>
        </div>

        <!-- RIGHT — live preview (Asana-style) -->
        <aside class="hidden lg:block sticky top-12" aria-hidden="true">
          <div class="pv rounded-md overflow-hidden">
            <!-- Mock project header -->
            <div class="px-5 pt-4 pb-0 bg-surface">
              <div class="flex items-center gap-2.5">
                <ProjectAvatar :theme="form.theme" size="md" />
                <p class="text-[14px] font-semibold text-foreground truncate">{{ form.name || 'Untitled project' }}</p>
                <span v-if="form.key" class="text-[11px] font-semibold text-muted bg-[var(--field-background)] rounded-md px-1.5 py-0.5 font-mono">{{ form.key }}</span>
                <Chip v-if="form.type !== 'internal'" size="sm" color="warning" variant="soft" class="ml-auto">
                  {{ PROJECT_TYPES.find(t => t.value === form.type)?.label || form.type }}
                </Chip>
              </div>

              <!-- Mock tabs -->
              <div class="flex items-center gap-5 mt-3.5">
                <span
                  v-for="tab in ['Summary', 'Board', 'List', 'Backlog', 'Money']"
                  :key="tab"
                  class="pv-tab text-[12px] pb-2"
                  :class="tab === 'Board' ? 'pv-tab--active' : 'text-muted'"
                >{{ tab }}</span>
              </div>
            </div>

            <!-- Mock board -->
            <div class="pv-board px-4 py-4 flex gap-3 overflow-hidden">
              <div
                v-for="(s, ci) in previewStates"
                :key="s.name"
                class="pv-col flex-1 min-w-0"
              >
                <div class="flex items-center gap-1.5 px-1 mb-2">
                  <span class="text-[11px] font-semibold text-foreground uppercase tracking-wide truncate">{{ s.name }}</span>
                  <span class="text-[10px] text-muted tabular-nums">{{ PREVIEW_COUNTS[ci % 4] }}</span>
                </div>
                <div class="flex flex-col gap-2">
                  <div v-for="r in PREVIEW_COUNTS[ci % 4]" :key="r" class="pv-card rounded-md bg-surface p-2.5">
                    <p class="text-[11.5px] font-medium text-foreground leading-snug truncate">{{ previewTaskTitle(ci, r) }}</p>
                    <div class="flex items-center justify-between mt-2.5">
                      <span
                        class="w-3 h-3 rounded-[4px] transition-colors duration-200"
                        :style="{ background: typeColor(ci + r) }"
                      />
                      <span
                        class="w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold text-white shrink-0"
                        :style="{ background: previewAvatarColor(ci + r) }"
                      >{{ previewInitial(ci + r) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Issue types strip -->
            <div class="px-5 py-3 bg-surface border-t border-separator flex items-center gap-2 flex-wrap">
              <span class="text-[11px] text-muted mr-1">Task types:</span>
              <span
                v-for="name in form.issueTypes.slice(0, 5)"
                :key="name"
                class="inline-flex items-center gap-1.5 text-[11px] font-medium text-foreground bg-[var(--field-background)] rounded-full px-2 py-0.5"
              >
                <span class="w-1.5 h-1.5 rounded-full" :style="{ background: typeColorByName(name) }" />
                {{ name }}
              </span>
            </div>
          </div>

          <p class="text-[11px] text-muted text-center mt-3">Live preview — updates as you configure</p>
        </aside>

      </div>
    </div>

    <!-- ── Bottom nav ───────────────────────────────────────────────── -->
    <div class="shrink-0 border-t border-separator bg-surface">
      <div class="max-w-7xl mx-auto w-full px-8 h-[68px] flex items-center justify-between gap-4">
        
   <!-- Step indicators -->
          <div class="flex items-center gap-2 mr-6 ">
            <template v-for="i in TOTAL_STEPS" :key="i">
              <button
                type="button"
                :disabled="i >= step"
                :aria-label="`Go to step ${i}: ${STEP_LABELS[i - 1]}`"
                class="flex items-center gap-1.5 group"
                @click="i < step && (step = i)"
              >
                <span
                  class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold transition-colors duration-200 shrink-0"
                  :class="[
                    i === step ? 'bg-accent text-white' : i < step ? 'bg-accent-soft text-accent cursor-pointer' : 'bg-default text-muted',
                  ]"
                >
                  <Check v-if="i < step" :size="11" :stroke-width="3" />
                  <template v-else>{{ i }}</template>
                </span>
                <span
                  class="text-[12.5px] font-medium transition-colors duration-200 hidden sm:inline"
                  :class="i === step ? 'text-foreground' : i < step ? 'text-muted cursor-pointer group-hover:text-foreground' : 'text-muted'"
                >{{ STEP_LABELS[i - 1] }}</span>
              </button>
              <span v-if="i < TOTAL_STEPS" class="w-4 h-px shrink-0" :class="i < step ? 'bg-accent-soft-hover' : 'bg-border'" />
            </template>
          </div>
        <div class="flex items-center gap-3 shrink-0">
          
          <Button
            v-if="step < TOTAL_STEPS"
            color="accent" size="md"
            :isDisabled="!canContinue"
            @click="next"
          >
            {{ NEXT_LABELS[step - 1] }}
            <template #endContent><ArrowRight class="size-3.5" /></template>
          </Button>
          <Button
            v-else
            color="accent" size="md"
            :isDisabled="!canCreate"
            :isLoading="saving"
            @click="submit"
          >
            {{ saving ? 'Creating…' : 'Create project' }}
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeft, ArrowRight, Check, X, Lock } from 'lucide-vue-next'
import { resolveProjectIcon } from '@/constants/project-icons'
import { Button, Input, Select, SelectItem, Chip, ProjectAvatar } from '@/ui'
import ThemePicker from '@/components/create-project/ThemePicker.vue'
import SegmentedRadio from '@/components/create-project/SegmentedRadio.vue'
import BillingFields from '@/components/create-project/BillingFields.vue'
import IssueTypesEditor from '@/components/create-project/IssueTypesEditor.vue'
import WorkflowStatesEditor from '@/components/create-project/WorkflowStatesEditor.vue'
import { useCreateProject, isUserTemplateId, userTemplateName } from '@/composables/useCreateProject'
import { PROJECT_TYPES, VISIBILITY_OPTIONS } from '@/constants/project-types'
import { TEMPLATES, TEMPLATE_CATEGORIES, CATEGORY_COLORS } from '@/constants/project-templates'
import { WORKFLOW_PRESETS } from '@/constants/workflow-presets'
import { ISSUE_TYPES } from '@/constants/issue-types'
import { listProjectTemplates } from '@/utils/api'
import { useEntitlementsStore } from '@/stores/entitlements'

const router = useRouter()
const TOTAL_STEPS = 3
const STEP_SUBTITLES = [
  // No emoji: the app's font stack has no colour-emoji fallback in the
  // headless/Linux render path, so this shipped as a tofu box (□) sitting in
  // the very first line a new user reads. Verified in a browser screenshot.
  "Let's start by selecting project template.",
  'Give it a name — the preview updates as you type',
  'Fine-tune the workflow — changes preview instantly',
]
const NEXT_LABELS = ['Use This Template', 'Next: Customize Workflow']
const STEP_LABELS = ['Template', 'Details', 'Customize']
const step = ref(1)

function groupColor(label) { return CATEGORY_COLORS[label] || CATEGORY_COLORS.General }
function tileColor(t) { return CATEGORY_COLORS[t.category] || CATEGORY_COLORS['Start fresh'] }

// Deterministic fake card counts per column, so the preview feels real
const PREVIEW_COUNTS = [2, 3, 1, 2]

// Deterministic fake task titles/assignees — real-looking text instead of
// shimmer bars, so the preview reads as "here's your board" not "loading".
const PREVIEW_TASKS = [
  'Kick off discovery call', 'Draft project brief', 'Set up shared workspace',
  'Review wireframes', 'Collect stakeholder feedback', 'Finalize scope doc',
  'Build first milestone', 'QA pass on core flow', 'Ship to staging',
]
const PREVIEW_PEOPLE = [
  { initial: 'A', color: 'oklch(0.6 0.19 254)' },
  { initial: 'M', color: 'oklch(0.62 0.18 151)' },
  { initial: 'S', color: 'oklch(0.68 0.17 26)' },
  { initial: 'J', color: 'oklch(0.62 0.16 300)' },
]
function previewTaskTitle(ci, r) { return PREVIEW_TASKS[(ci * 3 + r) % PREVIEW_TASKS.length] }
function previewAvatarColor(seed) { return PREVIEW_PEOPLE[seed % PREVIEW_PEOPLE.length].color }
function previewInitial(seed) { return PREVIEW_PEOPLE[seed % PREVIEW_PEOPLE.length].initial }

const {
  form, saving, keyAutoMode, keyError,
  canCreate, billingRequired,
  onNameInput, onKeyFocus, onKeyInput, onKeyBlur,
  submit, reset,
} = useCreateProject()

// "Use template" from the Templates management center arrives
// here as ?template=<id|user:name>, pre-seeding the SAME field the
// gallery's own template-tile click sets (works for built-ins and user
// templates alike — isUserTemplateId's prefix check already generalizes).
const route = useRoute()
onMounted(() => {
  reset()
  const t = route.query.template
  if (t && typeof t === 'string') {
    form.value.template = t
    step.value = 2
  }
})

// ── User (saved) templates ─────────────────────────────────────────────
const ent = useEntitlementsStore()
const userTemplatesRaw = ref([])
onMounted(async () => {
  try { userTemplatesRaw.value = await listProjectTemplates() }
  catch { userTemplatesRaw.value = [] }
})

// Normalized into the EXACT card shape the existing gallery already
// renders (id/label/icon-component/category/description/defaultProjectType)
// — no separate markup needed, they render through the same v-for.
const userTemplateCards = computed(() => userTemplatesRaw.value.map(t => ({
  id: `user:${t.name}`,
  label: t.template_name,
  icon: resolveProjectIcon(t.icon),
  category: 'Your templates',
  description: t.description || `${t.task_count} task${t.task_count === 1 ? '' : 's'}${t.automation_count ? ` · ${t.automation_count} automation${t.automation_count === 1 ? '' : 's'}` : ''}`,
  defaultProjectType: t.billing?.project_type !== 'internal' ? t.billing?.project_type : null,
  _raw: t,
})))

// ── Template gallery data ────────────────────────────────────────────

const templateGroups = computed(() => {
  const groups = []
  if (userTemplateCards.value.length) {
    groups.push({ label: 'Your templates', templates: userTemplateCards.value })
  }
  groups.push({
    label: 'Start fresh',
    templates: TEMPLATES.filter(t => !t.category || t.category === 'General'),
  })
  for (const cat of TEMPLATE_CATEGORIES) {
    if (cat === 'General') continue
    const templates = TEMPLATES.filter(t => t.category === cat)
    if (templates.length) groups.push({ label: cat, templates })
  }
  return groups
})

const selectedTemplate = computed(() =>
  userTemplateCards.value.find(t => t.id === form.value.template) ||
  TEMPLATES.find(t => t.id === form.value.template) || TEMPLATES[0]
)

// A user template's own shape drives the preview + billing gate — the
// composable's built-in watcher deliberately skips "user:" ids (it only
// knows the 11 built-ins), so this fills the same role for saved ones.
watch(() => form.value.template, (templateId) => {
  if (!isUserTemplateId(templateId)) return
  const name = userTemplateName(templateId)
  const tpl = userTemplatesRaw.value.find(t => t.name === name)
  if (!tpl) return
  form.value.workflowStates = (tpl.workflow_states || []).length ? [...tpl.workflow_states] : [...WORKFLOW_PRESETS.blank]
  form.value.issueTypes = (tpl.issue_types || []).map(it => it.name)
  form.value.issueTypePool = [...new Set(form.value.issueTypes)]
  if (tpl.billing?.project_type) form.value.type = tpl.billing.project_type
  // Prefill the billing inputs from the template's defaults so what the
  // user sees in BillingFields is what create_project_from_template gets —
  // they can override any of it (client is always theirs to pick).
  if (tpl.billing?.hourly_rate) form.value.billing.hourlyRate = tpl.billing.hourly_rate
  if (tpl.billing?.retainer_hours) form.value.billing.retainerHours = tpl.billing.retainer_hours
  if (tpl.billing?.budget_amount) form.value.billing.totalBudget = tpl.billing.budget_amount
  if (tpl.billing?.currency) form.value.billing.currency = tpl.billing.currency
})

// ── Live preview data (driven by the same reactive form) ────────────

const previewStates = computed(() => (form.value.workflowStates || []).slice(0, 4))

const _typeColorMap = Object.fromEntries(ISSUE_TYPES.map(t => [t.name, t.color]))
function typeColorByName(name) { return _typeColorMap[name] || 'var(--accent)' }
function typeColor(seed) {
  const types = form.value.issueTypes
  if (!types.length) return 'var(--accent)'
  return typeColorByName(types[seed % types.length])
}

// ── Navigation ───────────────────────────────────────────────────────

const canContinue = computed(() => {
  if (step.value === 1) return true
  return canCreate.value
})

const footerHint = computed(() => {
  // Was "— double-click a row to continue". Double-click is a hidden
  // accelerator, not an instruction: it's undiscoverable, unavailable on
  // touch, and it pointed people away from the primary button sitting six
  // inches to the right. The shortcut still works; it just isn't the
  // advertised path any more.
  if (step.value === 1) return `${selectedTemplate.value.label} template selected`
  if (step.value === 2) return 'Everything stays editable after creation'
  return form.value.key ? `${form.value.key}-1 will be your first task` : ''
})

function next() {
  if (step.value < TOTAL_STEPS && canContinue.value) step.value += 1
}
function back() {
  if (step.value > 1) step.value -= 1
}
function cancel() {
  if (window.history.length > 1) router.back()
  else router.push('/workspace')
}
</script>

<style scoped>
.step-enter-active, .step-leave-active { transition: opacity 0.14s var(--ease-out), transform 0.14s var(--ease-out); }
.step-enter-from { opacity: 0; transform: translateX(16px); }
.step-leave-to   { opacity: 0; transform: translateX(-16px); }

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.cp-label { display: block; font-size: 13px; font-weight: 500; color: var(--foreground); margin-bottom: 6px; line-height: 1.3; }

/* ── Template rows ( full-width rows, HeroUI v2 skin) ──────
   Dense list → shadow-small at rest, shadow-medium only on hover. */
.cp-row {
  box-shadow: var(--surface-shadow-sm);
  transition:
    transform 250ms var(--ease-smooth),
    box-shadow 150ms var(--ease-out),
    background-color 100ms var(--ease-out);
  -webkit-tap-highlight-color: transparent;
  cursor: pointer;
}
@media (hover: hover) {
  .cp-row:hover {
    transform: translateY(-1px);
    box-shadow: var(--surface-shadow);
  }
}
.cp-row:active { transform: scale(0.99); transition: transform 40ms ease-out; }
.cp-row:focus-visible {
  box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--focus), var(--surface-shadow-sm);
}
/* Selection = tinted surface + a hairline accent edge + the check badge.
   The previous `0 0 0 1.5px var(--accent)` drew a 1.5px ring around the whole
   card, which reads as a browser focus outline rather than a chosen item —
   and it was indistinguishable from the :focus-visible state directly above.
 */
.cp-row--selected,
.cp-row--selected:hover {
  background: var(--accent-soft);
  box-shadow: 0 0 0 1.5px var(--accent), var(--surface-shadow-sm);
}
.cp-row-check { animation: row-check-in 200ms var(--ease-smooth); }
.cp-row-dot {
  border: 1.5px solid var(--border-secondary);
  transition: border-color 140ms var(--ease-out);
}
.cp-row:hover .cp-row-dot { border-color: var(--border-tertiary); }
@keyframes row-check-in {
  from { transform: scale(0.4); opacity: 0; }
  to   { transform: scale(1); opacity: 1; }
}

/* ── Live preview pane ─────────────────────────────────────────────── */
.pv {
  box-shadow: var(--surface-shadow-sm);
  background: var(--surface);
}
.pv-tab { position: relative; }
.pv-tab--active { color: var(--accent); font-weight: 600; }
.pv-tab--active::after {
  content: ''; position: absolute; left: 0; right: 0; bottom: 0;
  height: 2px; border-radius: 2px; background: var(--accent);
}
.pv-board { background: var(--background); min-height: 300px; }
.pv-card { box-shadow: var(--surface-shadow-sm); }

@media (prefers-reduced-motion: reduce) {
  .cp-row, .cp-row-check, .step-enter-active, .step-leave-active { transition: none; animation: none; }
}
</style>
