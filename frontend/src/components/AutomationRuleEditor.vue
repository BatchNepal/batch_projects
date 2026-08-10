<template>
  <Drawer :open="open" size="xl" @update:open="v => emit('update:open', v)">
    <DrawerHeader @close="emit('update:open', false)">
      <p class="text-md font-semibold text-foreground">{{ draft.name ? 'Edit rule' : 'New automation rule' }}</p>
    </DrawerHeader>
    <DrawerBody class="space-y-6">
      <!-- Sentence hero. Bold tokens click-scroll to their
           section below (a real, if lighter-weight, interaction than a
           floating per-token popover — the sections ARE the pickers). -->
      <div class="are-sentence rounded-lg border border-border bg-[var(--surface-secondary)] px-4 py-3.5">
        <p class="text-md leading-relaxed text-foreground">
          <span
            v-for="(s, i) in sentence" :key="i"
            :class="s.bold ? 'are-token' : ''"
            @click="s.bold && scrollTo(s.key)"
          >{{ s.text }}</span>
        </p>
      </div>

      <Input v-model="draft.rule_name" label="Rule name" size="sm" placeholder="e.g. Auto-assign new bugs" fullWidth />
      <Input v-model="draft.description" label="Description" size="sm" placeholder="Optional — what is this rule for?" fullWidth />

      <!-- Scope (workspace surface only — project surface always scope=project) -->
      <div v-if="mode === 'workspace'">
        <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">Applies to</p>
        <div class="flex rounded border border-border overflow-hidden text-sm font-medium w-fit">
          <button type="button" class="px-3 py-1 transition-colors"
            :class="draft.scope === 'workspace' ? 'bg-primary text-white' : 'text-muted hover:text-foreground'"
            @click="draft.scope = 'workspace'">Every project</button>
          <button type="button" class="px-3 py-1 transition-colors border-l border-border"
            :class="draft.scope === 'project' ? 'bg-primary text-white' : 'text-muted hover:text-foreground'"
            @click="draft.scope = 'project'">One project</button>
        </div>
        <Combobox v-if="draft.scope === 'project'" v-model="draft.project" size="sm" class="mt-2"
          :options="options.projects" placeholder="Search projects…" />
        <template v-else>
          <p class="text-sm text-muted mt-2 mb-1">Limit to specific projects (optional — blank = all)</p>
          <Combobox v-model="draft.project_filter" multiple size="sm" :options="options.projects" placeholder="Search projects…" />
        </template>
      </div>

      <!-- WHEN -->
      <div ref="triggerSecRef">
        <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">When</p>
        <Combobox v-model="draft.trigger_event" size="sm" fullWidth
          :options="options.triggers" placeholder="Search triggers…" @update:modelValue="onTriggerChange" />

        <!-- task.field_changed config — from/to are prefilled Comboboxes
             fed by the chosen field's own enumerable option list when one
             exists (status/priority/type/labels); genuinely open fields
             (story_points/due_date/start_date/sprint — no fixed value
             domain) stay free Input. This IS the sin the phase exists to
             kill: no more raw Input for an enumerable field. -->
        <div v-if="triggerNeedsConfig === 'field_changed'" class="mt-2 flex items-center gap-2">
          <Combobox v-model="draft.trig.field" size="sm" class="flex-1"
            :options="taskFieldOptions" placeholder="Field…" />
          <span class="text-sm text-muted shrink-0">from</span>
          <Combobox v-if="fieldChangedOptions(draft.trig.field).length" v-model="draft.trig.from" size="sm" class="w-[130px]"
            :options="fieldChangedOptions(draft.trig.field)" placeholder="any" allow-create />
          <Input v-else v-model="draft.trig.from" size="sm" class="w-[110px]" placeholder="any" />
          <span class="text-sm text-muted shrink-0">to</span>
          <Combobox v-if="fieldChangedOptions(draft.trig.field).length" v-model="draft.trig.to" size="sm" class="w-[130px]"
            :options="fieldChangedOptions(draft.trig.field)" placeholder="any" allow-create />
          <Input v-else v-model="draft.trig.to" size="sm" class="w-[110px]" placeholder="any" />
        </div>

        <!-- schedule.relative config -->
        <div v-if="triggerNeedsConfig === 'relative_schedule'" class="mt-2 flex items-center gap-2">
          <Input v-model="draft.trig.offset_days" type="number" size="sm" class="w-[80px]" placeholder="3" />
          <span class="text-sm text-muted shrink-0">day(s)</span>
          <Select v-model="draft.trig.direction" size="sm" class="w-[110px]">
            <SelectItem value="before">before</SelectItem>
            <SelectItem value="after">after</SelectItem>
          </Select>
          <Combobox v-model="draft.trig.field" size="sm" class="flex-1"
            :options="(options.relative_date_fields || []).map(f => ({value: f, label: f}))" placeholder="Date field…" />
        </div>
      </div>

      <!-- IF -->
      <div ref="condSecRef">
        <div class="flex items-center justify-between mb-1.5">
          <div class="flex items-center gap-2">
            <p class="text-xs font-semibold text-muted uppercase tracking-wider">If</p>
            <div class="flex rounded border border-border overflow-hidden text-xs font-semibold">
              <button type="button" class="px-2 py-0.5 transition-colors"
                :class="draft.matchMode === 'all' ? 'bg-primary text-white' : 'text-muted hover:text-foreground'"
                @click="draft.matchMode = 'all'">ALL</button>
              <button type="button" class="px-2 py-0.5 transition-colors border-l border-border"
                :class="draft.matchMode === 'any' ? 'bg-primary text-white' : 'text-muted hover:text-foreground'"
                @click="draft.matchMode = 'any'">ANY</button>
            </div>
            <p class="text-xs text-muted">match</p>
          </div>
          <button type="button" class="text-sm text-primary font-medium hover:underline" @click="addCondition">
            + Add condition
          </button>
        </div>
        <p v-if="!draft.conditions.length" class="text-sm text-muted italic">
          No conditions — runs every time the trigger fires.
        </p>
        <div v-for="(c, i) in draft.conditions" :key="i" class="flex items-center gap-2 mb-2">
          <Combobox v-model="c.field" size="sm" class="flex-1" allowCreate
            :options="activeConditionFields.map(f => ({value: f.value, label: f.label}))"
            placeholder="Field…" @update:modelValue="onFieldChange(c)" />
          <Select v-model="c.op" size="sm" class="w-[140px]">
            <SelectItem v-for="o in options.operators" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
          </Select>
          <template v-if="needsValue(c.op)">
            <Combobox v-if="fieldType(c.field) === 'select'" v-model="c.value" size="sm" class="flex-1" allowCreate
              :options="fieldOptions(c.field).map(o => ({value: o, label: o}))" placeholder="Value…" />
            <Combobox v-else-if="fieldType(c.field) === 'user'" v-model="c.value" size="sm" class="flex-1"
              :options="options.members.map(m => ({value: m.user, label: m.full_name}))" placeholder="Person…" />
            <Combobox v-else-if="fieldType(c.field) === 'label'" v-model="c.value" size="sm" class="flex-1"
              :options="(options.labels || []).map(l => ({value: l, label: l}))" placeholder="Label…" />
            <Input v-else v-model="c.value" size="sm" class="flex-1"
              :type="fieldType(c.field) === 'number' ? 'number' : 'text'" placeholder="value" />
          </template>
          <IconButton size="sm" variant="light" @click="draft.conditions.splice(i, 1)" aria-label="Remove">
            <Icon :icon="X" class="size-3.5 text-muted" />
          </IconButton>
        </div>
      </div>

      <!-- THEN — ordered, multi-action -->
      <div ref="actionSecRef">
        <div class="flex items-center justify-between mb-1.5">
          <p class="text-xs font-semibold text-muted uppercase tracking-wider">Then</p>
          <button type="button" class="text-sm text-primary font-medium hover:underline" @click="addAction">
            + Add action
          </button>
        </div>

        <div v-for="(act, ai) in draft.actions" :key="ai"
          class="mb-3 rounded-md border border-[var(--border-secondary)] p-3">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-xs font-semibold text-muted w-5 shrink-0">{{ ai + 1 }}.</span>
            <!-- Select, not Combobox: a short fixed enum (9 action types).
                 Combobox pre-fills its search query with the CURRENT
                 selection's label on open, which then filters the listbox
                 down to just that one match — live-verified hiding every
                 other action type the moment this dropdown was opened
                 (WORKPLAN-PHASE25 follow-up), the identical bug already
                 fixed on the canvas side for the same reason (see
                 NodeConfigPanel.vue). -->
            <Select v-model="act.type" size="sm" class="flex-1" @update:modelValue="onActionTypeChange(act)">
              <SelectItem v-for="a in options.actions" :key="a.value" :value="a.value">{{ a.label }}</SelectItem>
            </Select>
            <IconButton size="sm" variant="light" :disabled="ai === 0" @click="moveAction(ai, -1)" aria-label="Move up">
              <Icon :icon="ChevronUp" class="size-3.5" :class="ai === 0 ? 'text-muted opacity-40' : 'text-muted'" />
            </IconButton>
            <IconButton size="sm" variant="light" :disabled="ai === draft.actions.length - 1" @click="moveAction(ai, 1)" aria-label="Move down">
              <Icon :icon="ChevronDown" class="size-3.5" :class="ai === draft.actions.length - 1 ? 'text-muted opacity-40' : 'text-muted'" />
            </IconButton>
            <IconButton size="sm" variant="light" @click="draft.actions.splice(ai, 1)" aria-label="Remove action">
              <Icon :icon="Trash2" class="size-3.5 text-muted" />
            </IconButton>
          </div>

          <div class="space-y-3 pl-3 border-l-2 border-[var(--border-secondary)]">
            <Combobox v-if="act.type === 'Change Status'" v-model="act.cfg.status" size="sm" label="New status" fullWidth allowCreate
              :options="(options.statuses || []).map(s => ({value: s, label: s}))" placeholder="Status…" />

            <template v-else-if="act.type === 'Assign Issue'">
              <p class="text-sm text-muted mb-1">Assign to</p>
              <Combobox v-model="act.cfg.assignees" multiple size="sm" fullWidth
                :options="options.members.map(m => ({value: m.user, label: m.full_name}))" placeholder="Search people…" />
              <Select v-model="act.cfg.mode" size="sm" label="Mode" fullWidth>
                <SelectItem value="set">Replace assignees</SelectItem>
                <SelectItem value="add">Add to assignees</SelectItem>
              </Select>
            </template>

            <Combobox v-else-if="act.type === 'Set Priority'" v-model="act.cfg.priority" size="sm" label="Priority" fullWidth
              :options="(options.priorities || []).map(p => ({value: p, label: p}))" placeholder="Priority…" />

            <template v-else-if="act.type === 'Set Due Date'">
              <Select v-model="act.cfg.dueMode" size="sm" label="Set due date" fullWidth>
                <SelectItem value="in_days">Days from trigger</SelectItem>
                <SelectItem value="on_date">A specific date</SelectItem>
              </Select>
              <Input v-if="act.cfg.dueMode === 'in_days'" v-model="act.cfg.dueDays" type="number" size="sm" label="Days from now" fullWidth placeholder="3" />
              <Input v-else v-model="act.cfg.dueDate" type="date" size="sm" label="Due date" fullWidth />
            </template>

            <template v-else-if="act.type === 'Add Label'">
              <p class="text-sm text-muted mb-1">Labels to add</p>
              <Combobox v-if="options.labels.length" v-model="act.cfg.labels" multiple size="sm" fullWidth
                :options="options.labels.map(l => ({value: l, label: l}))" placeholder="Search labels…" />
              <Input v-else v-model="act.cfg.labelsFreeText" size="sm" fullWidth placeholder="comma separated, e.g. bug, urgent" />
            </template>

            <Textarea v-else-if="act.type === 'Add Comment'" v-model="act.cfg.comment" rows="2" label="Comment" placeholder="Text to post on the task" />

            <template v-else-if="act.type === 'Notify'">
              <Select v-model="act.cfg.to" size="sm" label="Notify" fullWidth>
                <SelectItem value="assignees">Assignees</SelectItem>
                <SelectItem value="watchers">Watchers</SelectItem>
                <SelectItem value="reporter">Reporter</SelectItem>
                <SelectItem value="">Specific people only</SelectItem>
              </Select>
              <div class="mt-2">
                <p class="text-sm text-muted mb-1">{{ act.cfg.to ? 'Also notify' : 'Notify' }}</p>
                <Combobox v-model="act.cfg.notifyUsers" multiple size="sm" fullWidth
                  :options="options.members.map(m => ({value: m.user, label: m.full_name}))" placeholder="Search people…" />
              </div>
              <Textarea v-model="act.cfg.message" rows="2" label="Message" placeholder="What should the notification say?" />
            </template>

            <template v-else-if="act.type === 'Create Issue'">
              <Input v-model="act.cfg.title" size="sm" label="New task title" fullWidth placeholder="e.g. QA review" />
              <div class="grid grid-cols-2 gap-3">
                <Combobox v-model="act.cfg.task_type" size="sm" label="Type" fullWidth allowCreate
                  :options="(options.task_types || []).map(t => ({value: t, label: t}))" placeholder="Type…" />
                <Combobox v-model="act.cfg.priority" size="sm" label="Priority" fullWidth
                  :options="(options.priorities || []).map(p => ({value: p, label: p}))" placeholder="Priority…" />
                <Combobox v-model="act.cfg.status" size="sm" label="Status" fullWidth allowCreate
                  :options="[{value:'',label:'First status (default)'}, ...(options.statuses || []).map(s => ({value: s, label: s}))]" placeholder="Status…" />
                <Combobox v-model="act.cfg.assignee" size="sm" label="Assign to" fullWidth
                  :options="[{value:'',label:'Unassigned'}, ...options.members.map(m => ({value: m.user, label: m.full_name}))]" placeholder="Person…" />
              </div>
              <Checkbox v-model:isSelected="act.cfg.link_to_trigger">
                Link the new task to the one that triggered this
              </Checkbox>
            </template>

            <template v-else-if="act.type === 'Update ERPNext Document'">
              <Combobox v-model="act.cfg.doctype" size="sm" label="Document type" fullWidth
                :options="(options.erpnext_update_doctypes || []).map(dt => ({value: dt, label: dt}))"
                placeholder="Document type…" @update:modelValue="onErpDoctypeChange(act)" />
              <Select v-model="act.cfg.name_from" size="sm" label="Which document" fullWidth>
                <SelectItem value="fixed">A specific document</SelectItem>
                <SelectItem value="task_field">From a task field</SelectItem>
              </Select>
              <Combobox v-if="act.cfg.name_from === 'fixed'" v-model="act.cfg.name" size="sm" fullWidth label="Document name"
                :model-label="erpDocLabel(act.cfg.doctype, act.cfg.name)"
                :loader="q => searchErpDocuments(act.cfg.doctype, q, props.project)" :min-chars="1"
                placeholder="Search by name…" :is-disabled="!act.cfg.doctype" />
              <Combobox v-else v-model="act.cfg.field" size="sm" fullWidth label="Task field"
                :options="taskFieldOptions" placeholder="Field…" />
              <div>
                <div class="flex items-center justify-between mb-1.5">
                  <p class="text-sm text-muted">Fields to set</p>
                  <button type="button" class="text-sm text-primary font-medium hover:underline"
                    :disabled="!act.cfg.doctype"
                    @click="act.cfg.fieldRows.push({ key: '', value: '' })">
                    + Add field
                  </button>
                </div>
                <div v-for="(row, i) in act.cfg.fieldRows" :key="i" class="flex items-center gap-2 mb-2">
                  <Combobox v-model="row.key" size="sm" class="flex-1"
                    :options="erpFieldsFor(act.cfg.doctype).map(f => ({value: f.fieldname, label: f.label}))"
                    placeholder="Field…" @update:modelValue="row.value = ''" />
                  <!-- Value input TYPED by the picked field's fieldtype — the
                       ONE shared adaptive editor (Select/Check/Date/number/
                       Link-with-search), also used by the canvas builder. -->
                  <ErpFieldValueInput
                    v-model="row.value"
                    :field-meta="erpFieldMeta(act.cfg.doctype, row.key)"
                    :project="props.project"
                  />
                  <IconButton size="sm" variant="light" @click="act.cfg.fieldRows.splice(i, 1)" aria-label="Remove">
                    <Icon :icon="X" class="size-3.5 text-muted" />
                  </IconButton>
                </div>
                <p v-if="!act.cfg.fieldRows.length" class="text-sm text-muted italic">
                  {{ act.cfg.doctype ? 'No fields configured yet.' : 'Pick a document type first.' }}
                </p>
              </div>
            </template>

            <template v-else-if="act.type === 'Send Email'">
              <p class="text-sm text-muted mb-1">To</p>
              <Combobox v-model="act.cfg.emailTo" multiple allowCreate size="sm" fullWidth
                :options="options.members.map(m => ({value: m.user, label: m.full_name}))"
                placeholder="Search people, or type an email…" />
              <Input v-model="act.cfg.emailSubject" size="sm" fullWidth label="Subject" placeholder="e.g. Task update: {{task.title}}" />
              <Textarea v-model="act.cfg.message" rows="3" label="Body" placeholder="Supports {{task.title}}, {{task.task_key}}, etc." />
            </template>
          </div>
        </div>
        <p v-if="!draft.actions.length" class="text-sm text-muted italic">
          No actions yet — add at least one.
        </p>
      </div>
    </DrawerBody>
    <div class="shrink-0 flex items-center justify-end gap-2 px-5 py-3 border-t border-separator">
      <Button size="sm" variant="light" @click="emit('update:open', false)">Cancel</Button>
      <Button size="sm" color="primary" :disabled="!canSave || saving" @click="save">
        {{ saving ? 'Saving…' : 'Save rule' }}
      </Button>
    </div>
  </Drawer>
</template>

<script setup>
// A re-skin, not a rewrite: buildConditions/
// buildActionConfig/buildTriggerConfig and the edit-hydration watch below
// must stay UNCHANGED in output shape regardless of UI changes around them
// (trigger UI moving between Select/Input/Combobox, the surface moving
// between Modal/Drawer, etc.) — saved rules and the server contract don't move.
import { reactive, computed, watch, ref, nextTick } from 'vue'
import { toast } from 'vue-sonner'
import {
  Button, IconButton, Icon, Drawer, DrawerHeader, DrawerBody,
  Select, SelectItem, Combobox, Input, Textarea, Checkbox, Switch,
} from '@/ui'
import { X, ChevronUp, ChevronDown, Trash2 } from 'lucide-vue-next'
import { createAutomationRule, updateAutomationRule, searchErpDocuments as apiSearchErpDocuments } from '@/utils/api'
import { ruleSentence } from '@/utils/automationSentence'
import { useErpDoctypeFields, searchableLinkDoctype } from '@/composables/useErpDoctypeFields'
import ErpFieldValueInput from '@/components/ErpFieldValueInput.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  rule: { type: Object, default: null },
  options: { type: Object, required: true },
  /** 'project' — scope is fixed to `project`, no scope toggle shown (Project
   * Settings → Automations). 'workspace' — scope defaults to workspace, with
   * a toggle to narrow to one project instead (Workspace Settings →
   * Automations). */
  mode: { type: String, default: 'project' },
  project: { type: String, default: null },
  /** A recipe gallery card's pre-filled draft (trigger +
   * condition/action skeletons, variable tokens left blank). Applied on
   * open in place of blankDraft() when `rule` isn't also set (editing an
   * existing rule always wins). */
  recipeDraft: { type: Object, default: null },
})
const emit = defineEmits(['update:open', 'saved'])

function searchErpDocuments(doctype, q, project) {
  if (!doctype) return Promise.resolve([])
  return apiSearchErpDocuments(doctype, q, project).then(rows => rows.map(r => ({ value: r.name, label: r.label })))
}

// Task-field catalog for "from a task field" / field_changed's own field
// picker — built from what get_automation_options ALREADY ships
// (condition_fields + relative_date_fields), per the hard rule against a
// second, separately-maintained field list.
const taskFieldOptions = computed(() => {
  const seen = new Map()
  for (const f of (props.options.condition_fields || [])) seen.set(f.value, f.label)
  for (const f of (props.options.field_changed_fields || [])) if (!seen.has(f)) seen.set(f, f)
  for (const f of (props.options.relative_date_fields || [])) if (!seen.has(f)) seen.set(f, f)
  return [...seen.entries()].map(([value, label]) => ({ value, label }))
})

// Enumerable option list for a field_changed from/to picker — only for
// fields whose value domain is genuinely fixed; story_points/dates/sprint
// stay free-text (open domains, not a guess-field in the sense this phase
// targets).
function fieldChangedOptions(field) {
  if (field === 'status') return (props.options.statuses || []).map(s => ({ value: s, label: s }))
  if (field === 'priority') return (props.options.priorities || []).map(p => ({ value: p, label: p }))
  if (field === 'task_type') return (props.options.task_types || []).map(t => ({ value: t, label: t }))
  if (field === 'labels') return (props.options.labels || []).map(l => ({ value: l, label: l }))
  return []
}

// ERP doctype field metadata + Link-label resolution — the ONE shared
// implementation (useErpDoctypeFields), reused by NodeConfigPanel.vue too.
const { erpFieldsFor, erpFieldMeta, erpDocLabel } = useErpDoctypeFields()
function onErpDoctypeChange(act) {
  act.cfg.name = ''
  act.cfg.field = ''
  act.cfg.fieldRows = []
  if (act.cfg.doctype) erpFieldsFor(act.cfg.doctype) // prime the cache
}

function blankAction(type = 'Change Status') {
  return {
    type,
    cfg: {
      mode: 'set', to: 'assignees', dueMode: 'in_days', dueDays: 3, priority: 'Medium',
      assignees: [], notifyUsers: [], labels: [], labelsFreeText: '',
      doctype: '', name_from: 'fixed', name: '', field: '', fieldRows: [],
      emailTo: [], emailSubject: '',
    },
  }
}

function blankDraft() {
  return {
    name: null,
    rule_name: '',
    description: '',
    scope: props.mode === 'workspace' ? 'workspace' : 'project',
    project: props.mode === 'project' ? props.project : null,
    project_filter: [],
    trigger_event: 'task.status_changed',
    trig: { field: '', from: '', to: '', offset_days: 3, direction: 'before' },
    conditions: [],
    matchMode: 'all',
    actions: [blankAction()],
  }
}
const draft = reactive(blankDraft())
const saving = ref(false)

const sentence = computed(() => ruleSentence(
  { trigger_event: draft.trigger_event, conditions: draft.matchMode === 'any' ? { all: [], any: draft.conditions } : { all: draft.conditions, any: [] }, actions: draft.actions },
  props.options,
))

const triggerSecRef = ref(null)
const condSecRef = ref(null)
const actionSecRef = ref(null)
function scrollTo(key) {
  const target = key === 'trigger' ? triggerSecRef.value : key.startsWith('cond') ? condSecRef.value : actionSecRef.value
  target?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  target?.classList.add('are-flash')
  setTimeout(() => target?.classList.remove('are-flash'), 700)
}

const triggerNeedsConfig = computed(() =>
  props.options.triggers?.find(t => t.value === draft.trigger_event)?.needs_config || null)

function onTriggerChange() {
  draft.trig = { field: '', from: '', to: '', offset_days: 3, direction: 'before' }
}

function toggleInList(list, value) {
  const idx = list.indexOf(value)
  if (idx === -1) list.push(value)
  else list.splice(idx, 1)
}

// The erp.* triggers (erp.invoice_submitted/payment_received/so_confirmed)
// carry no task — their events' actual payload is invoice/customer/amount/...
// (see events.py's emit() call sites), not status/priority/assignees. Before
// this, the condition-field picker showed the task list regardless of
// trigger, so every erp.* condition had to be free-typed against options
// that were all wrong. Mirrors the same condition_fields_source fix on the
// canvas side (NodeConfigPanel.vue).
const activeConditionFields = computed(() => {
  if (draft.trigger_event?.startsWith('erp.')) return props.options.erp_finance_condition_fields || []
  return props.options.condition_fields || []
})
const fieldMeta = (f) => activeConditionFields.value.find(x => x.value === f)
const fieldType = (f) => fieldMeta(f)?.type || 'text'
const fieldOptions = (f) => fieldMeta(f)?.options || []
const needsValue = (op) => !['changed', 'is_set', 'is_not_set'].includes(op)
function onFieldChange(c) { c.value = '' }
function addCondition() {
  const first = activeConditionFields.value[0]
  draft.conditions.push({ field: first?.value || 'to_status', op: 'eq', value: '' })
}
function addAction() { draft.actions.push(blankAction()) }
function moveAction(i, dir) {
  const j = i + dir
  if (j < 0 || j >= draft.actions.length) return
  const [a] = draft.actions.splice(i, 1)
  draft.actions.splice(j, 0, a)
}
function onActionTypeChange(act) {
  Object.assign(act, blankAction(act.type))
}

const canSave = computed(() =>
  draft.rule_name.trim() && draft.trigger_event && draft.actions.length &&
  (draft.scope !== 'project' || draft.project))

watch(() => props.open, (isOpen) => {
  if (!isOpen) return
  Object.assign(draft, blankDraft())
  const r = props.rule
  if (r) {
    draft.name = r.name
    draft.rule_name = r.rule_name
    draft.description = r.description || ''
    draft.scope = r.scope || 'project'
    draft.project = r.project || null
    draft.project_filter = Array.isArray(r.project_filter) ? [...r.project_filter] : []
    draft.trigger_event = r.trigger_event
    const tc = r.trigger_config || {}
    draft.trig = {
      field: tc.field || '', from: tc.from ?? '', to: tc.to ?? '',
      offset_days: tc.offset_days ?? 3, direction: tc.direction || 'before',
    }

    const rawConds = r.conditions
    if (Array.isArray(rawConds)) {
      draft.conditions = rawConds.map(c => ({ field: c.field, op: c.op || 'eq', value: c.value ?? '' }))
      draft.matchMode = 'all'
    } else if (rawConds && typeof rawConds === 'object') {
      const clauses = rawConds.any?.length ? rawConds.any : (rawConds.all || [])
      draft.conditions = clauses.map(c => ({ field: c.field, op: c.op || 'eq', value: c.value ?? '' }))
      draft.matchMode = rawConds.any?.length ? 'any' : 'all'
    }

    draft.actions = (r.actions || []).map(a => {
      const base = blankAction(a.type)
      const ac = a.config || {}
      base.cfg = {
        ...base.cfg, ...ac,
        assignees: Array.isArray(ac.assignees) ? [...ac.assignees] : [],
        notifyUsers: Array.isArray(ac.users) ? [...ac.users] : [],
        labels: a.type === 'Add Label' && Array.isArray(ac.labels) ? [...ac.labels] : [],
        labelsFreeText: a.type === 'Add Label' && Array.isArray(ac.labels) ? ac.labels.join(', ') : '',
        // Send Email is saved as {to, subject, message} (buildActionConfig's
        // literal output) but the form binds act.cfg.emailTo/emailSubject —
        // "to" would otherwise collide with Notify's own act.cfg.to (a role
        // STRING, not a recipient array); remapped here same as
        // notifyUsers/assignees above.
        emailTo: a.type === 'Send Email' && Array.isArray(ac.to) ? [...ac.to] : [],
        emailSubject: a.type === 'Send Email' ? (ac.subject || '') : '',
      }
      if (a.type === 'Set Due Date') {
        base.cfg.dueMode = ac.mode || (ac.date ? 'on_date' : 'in_days')
        base.cfg.dueDays = ac.days ?? 3
        base.cfg.dueDate = ac.date || ''
      }
      if (a.type === 'Update ERPNext Document') {
        base.cfg.name_from = ac.name_from || 'fixed'
        base.cfg.fieldRows = Object.entries(ac.fields || {}).map(([key, value]) => ({ key, value }))
        if (ac.doctype) erpFieldsFor(ac.doctype)
      }
      return base
    })
    if (!draft.actions.length) draft.actions = [blankAction()]
  } else if (props.recipeDraft) {
    // a recipe card's pre-filled skeleton. A plain
    // Object.assign over blankDraft() would be a SHALLOW merge — a
    // recipe's partial `trig`/action `cfg` overrides would replace
    // blankAction()'s whole cfg object instead of filling gaps in it,
    // leaving fields the template reads unconditionally (e.g.
    // act.cfg.assignees) undefined. Merge one level deeper for trig and
    // per-action cfg specifically.
    const rd = props.recipeDraft
    Object.assign(draft, blankDraft(), rd, {
      trig: { ...blankDraft().trig, ...(rd.trig || {}) },
      actions: (rd.actions && rd.actions.length ? rd.actions : [{ type: 'Change Status' }]).map(a => {
        const base = blankAction(a.type)
        base.cfg = { ...base.cfg, ...(a.cfg || {}) }
        return base
      }),
    })
    nextTick(() => scrollTo(draft.conditions.length ? 'cond:0' : 'action:0'))
  }
}, { immediate: true })

function buildConditions() {
  const clauses = draft.conditions.filter(c => c.field)
  if (!clauses.length) return []
  return draft.matchMode === 'any' ? { all: [], any: clauses } : { all: clauses, any: [] }
}

function buildActionConfig(act) {
  const c = act.cfg
  switch (act.type) {
    case 'Change Status': return { status: c.status }
    case 'Assign Issue':  return { assignees: c.assignees || [], mode: c.mode || 'set' }
    case 'Set Priority':  return { priority: c.priority }
    case 'Set Due Date':  return c.dueMode === 'on_date'
      ? { mode: 'on_date', date: c.dueDate || '' }
      : { mode: 'in_days', days: Number(c.dueDays) || 0 }
    case 'Add Label': {
      const lbls = props.options.labels.length
        ? (c.labels || [])
        : String(c.labelsFreeText || '').split(',').map(s => s.trim()).filter(Boolean)
      return { labels: lbls }
    }
    case 'Add Comment':   return { comment: c.comment || '' }
    case 'Notify':        return { to: c.to || '', users: c.notifyUsers || [], message: c.message || '' }
    case 'Send Email':    return { to: c.emailTo || [], subject: c.emailSubject || '', message: c.message || '' }
    case 'Create Issue':  return {
      title: c.title, task_type: c.task_type, status: c.status || null,
      priority: c.priority || 'Medium', assignees: c.assignee ? [c.assignee] : [],
      link_to_trigger: !!c.link_to_trigger,
    }
    case 'Update ERPNext Document': {
      const fields = {}
      for (const row of (c.fieldRows || [])) if (row.key) fields[row.key] = row.value
      const cfg = { doctype: c.doctype, name_from: c.name_from || 'fixed', fields }
      if (cfg.name_from === 'fixed') cfg.name = c.name || ''
      else cfg.field = c.field || ''
      return cfg
    }
    default: return {}
  }
}

function buildTriggerConfig() {
  if (triggerNeedsConfig.value === 'field_changed') {
    const cfg = { field: draft.trig.field }
    if (draft.trig.from !== '') cfg.from = draft.trig.from
    if (draft.trig.to !== '') cfg.to = draft.trig.to
    return cfg
  }
  if (triggerNeedsConfig.value === 'relative_schedule') {
    return { field: draft.trig.field, offset_days: Number(draft.trig.offset_days) || 0, direction: draft.trig.direction }
  }
  return {}
}

async function save() {
  saving.value = true
  const payload = {
    rule_name: draft.rule_name.trim(),
    description: draft.description?.trim() || '',
    scope: draft.scope,
    project: draft.scope === 'project' ? draft.project : null,
    project_filter: draft.scope === 'workspace' ? draft.project_filter : [],
    trigger_event: draft.trigger_event,
    trigger_config: buildTriggerConfig(),
    conditions: buildConditions(),
    actions: draft.actions.map(a => ({ type: a.type, config: buildActionConfig(a) })),
  }
  try {
    const saved = draft.name
      ? await updateAutomationRule({ rule: draft.name, ...payload })
      : await createAutomationRule(payload)
    emit('update:open', false)
    emit('saved', saved)
    toast.success('Automation saved')
  } catch (e) {
    toast.error(e.message || 'Something went wrong')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.are-token {
  font-weight: 600;
  color: var(--accent);
  cursor: pointer;
  border-radius: 3px;
  padding: 0 2px;
  margin: 0 -2px;
}
.are-token:hover { background: var(--accent-soft); text-decoration: underline; }
.are-flash { animation: are-flash-kf 700ms ease-out; }
@keyframes are-flash-kf {
  0%   { background: var(--accent-soft); }
  100% { background: transparent; }
}
</style>
