<template>
  <Modal :open="open" size="lg" @update:open="onClose">
    <ModalHeader>
      <template #title>
        <div class="flex items-center gap-2.5">
          <span class="flex items-center justify-center size-8 rounded-md bg-surface-tertiary shrink-0">
            <Icon :icon="meta?.icon" :size="16" class="text-foreground" />
          </span>
          <div class="min-w-0 flex-1">
            <input
              v-model="localLabel"
              class="text-[15px] font-semibold text-foreground bg-transparent outline-none w-full truncate rounded px-1 -mx-1 focus:bg-surface-secondary"
            />
            <p class="text-xs text-muted mt-0.5 truncate">{{ categoryLabel }} · {{ meta?.label }}</p>
          </div>
        </div>
      </template>
    </ModalHeader>

    <Tabs
      v-if="showSettingsTab"
      v-model="activeTab" variant="underline" class="px-5 -mt-1"
      :tabs="[{ value: 'configure', label: 'Configure' }, { value: 'settings', label: 'Settings' }]"
    />

    <ModalBody class="flex flex-col gap-4">
      <template v-if="activeTab === 'configure'">
        <template v-for="field in visibleFields" :key="field.name">
          <!-- credential fields are configured via the small chip UNDER the
               node (sub_ports), not duplicated here — avoids two conflicting
               ways to set the same value. -->
          <div v-if="field.type === 'credential'" class="text-xs text-muted bg-surface-secondary rounded-md px-3 py-2">
            <span class="font-medium text-foreground">{{ fieldLabel(field) }}:</span>
            attach a credential using the chip below this node on the canvas.
          </div>

          <!-- trigger.webhook's full lifecycle (WORKPLAN-PHASE25 B3): token
               select/create, copyable URL, usage stats, revoke — bespoke UI
               (not the generic Select/Combobox machinery below) because
               nothing else in this form loads its own async list, creates a
               record inline, AND shows live usage stats. Mirrors
               ShareDialog.vue's existing create/list/revoke shape rather
               than inventing a new one. -->
          <div v-else-if="field.type === 'webhook_lifecycle'" class="flex flex-col gap-2.5">
            <p class="text-xs font-medium text-foreground">{{ fieldLabel(field) }}<span v-if="field.required" class="text-danger">*</span></p>

            <div v-if="webhookTokensLoading" class="flex justify-center py-3">
              <Icon :icon="Loader2" :size="16" class="animate-spin text-muted" />
            </div>
            <p v-else-if="webhookTokensError" class="text-[12px] text-danger">{{ webhookTokensError }}</p>

            <template v-else>
              <Select v-model="localConfig[field.name]" size="sm" placeholder="Choose a token…">
                <SelectItem v-for="tok in webhookTokens" :key="tok.name" :value="tok.name">
                  {{ tok.label }}{{ tok.is_active ? '' : ' (revoked)' }}
                </SelectItem>
              </Select>

              <template v-if="selectedWebhookToken">
                <div class="flex items-center gap-1.5">
                  <span class="flex-1 min-w-0 h-8 px-2.5 rounded-md bg-surface-secondary text-[12px] font-mono text-foreground truncate flex items-center">
                    {{ webhookUrl }}
                  </span>
                  <Button size="sm" :variant="webhookUrlCopied ? 'outline' : 'light'" @click="copyWebhookUrl">
                    {{ webhookUrlCopied ? 'Copied' : 'Copy' }}
                  </Button>
                </div>
                <p v-if="options.gateway_public_url_is_internal" class="text-[11px] text-warning">
                  Internal URL — set bp_gateway_public_url in site_config for a shareable address.
                </p>
                <div class="flex items-center justify-between text-[11px] text-muted px-0.5">
                  <span>{{ selectedWebhookToken.call_count || 0 }} call{{ selectedWebhookToken.call_count === 1 ? '' : 's' }}
                    <template v-if="selectedWebhookToken.last_used"> · last {{ fmtRelative(selectedWebhookToken.last_used) }}</template>
                    <template v-if="selectedWebhookToken.last_event"> · {{ selectedWebhookToken.last_event }}</template>
                  </span>
                  <button
                    v-if="selectedWebhookToken.is_active" type="button"
                    class="text-danger hover:underline" @click="revokeSelectedWebhookToken"
                  >Revoke</button>
                </div>
              </template>

              <div class="flex items-center gap-1.5 pt-1 border-t border-border">
                <Input v-model="webhookCreateLabel" placeholder="New token label" size="sm" class="flex-1" />
                <Button size="sm" variant="outline" :is-disabled="!webhookCreateLabel" :is-loading="webhookCreating" @click="createNewWebhookToken">
                  Create
                </Button>
              </div>
            </template>
          </div>

          <Input
            v-else-if="field.type === 'text'"
            v-model="localConfig[field.name]" :label="fieldLabel(field)" size="sm"
            :is-required="field.required"
          />
          <Input
            v-else-if="field.type === 'int'"
            v-model.number="localConfig[field.name]" type="number" :label="fieldLabel(field)" size="sm"
            :is-required="field.required"
          />
          <Input
            v-else-if="field.type === 'date'"
            v-model="localConfig[field.name]" type="date" :label="fieldLabel(field)" size="sm"
            :is-required="field.required"
          />

          <!-- Real ERPNext document search (e.g. "Update ERPNext Document"'s
               "Document name") — doctype comes from the sibling field named
               in doctype_field, resolved against the live draft. -->
          <Combobox
            v-else-if="field.type === 'erp_link_search'"
            v-model="localConfig[field.name]" :label="fieldLabel(field)"
            :model-label="erpDocLabel(doctypeFor(field.doctype_field), localConfig[field.name])"
            :loader="q => erpSearch(doctypeFor(field.doctype_field), q)" :min-chars="1"
            :is-disabled="!doctypeFor(field.doctype_field)"
            :placeholder="doctypeFor(field.doctype_field) ? `Search ${doctypeFor(field.doctype_field)}…` : 'Pick a document type first'"
            size="sm" :is-required="field.required"
          />

          <div v-else-if="field.type === 'boolean'" class="flex items-center justify-between py-1">
            <label class="text-sm text-foreground">{{ fieldLabel(field) }}</label>
            <Switch v-model="localConfig[field.name]" size="sm" />
          </div>

          <!-- Combobox pre-fills its search text with the CURRENT selection's
               label, so opening it immediately filters the list down to just
               that one match — great for a searchable long list (members,
               doctypes), actively broken for a short fixed enum (you'd have
               to clear the text before seeing any other option). Live-
               verified this hiding every option but the selected one on the
               "Notify" field, which has neither options_source nor
               allow_custom — that's exactly the signal to use a plain Select
               instead. Combobox is reserved for options_source/allow_custom/
               multi fields, where the search genuinely earns its keep. -->
          <Select
            v-else-if="field.type === 'select' && !field.multi && !field.options_source && !field.allow_custom"
            v-model="localConfig[field.name]" :label="fieldLabel(field)" size="sm"
          >
            <SelectItem v-for="opt in optionsFor(field)" :key="opt.value" :value="opt.value">{{ opt.label }}</SelectItem>
          </Select>
          <Combobox
            v-else-if="field.type === 'select' && !field.multi"
            v-model="localConfig[field.name]" :label="fieldLabel(field)"
            :options="optionsFor(field)" :allow-create="!!field.allow_custom"
            size="sm" :is-required="field.required"
          />
          <Combobox
            v-else-if="(field.type === 'select' && field.multi) || field.type === 'member'"
            v-model="localConfig[field.name]" :label="fieldLabel(field)"
            :options="optionsFor(field)" multiple :allow-create="!!field.allow_custom"
            size="sm" :is-required="field.required"
          />

          <div v-else-if="field.type === 'keyvalue'" class="flex flex-col gap-1.5">
            <div class="flex items-center justify-between">
              <p class="text-xs font-medium text-foreground">{{ fieldLabel(field) }}<span v-if="field.required" class="text-danger">*</span></p>
              <button
                type="button" class="text-[12px] text-accent font-medium hover:underline disabled:opacity-40 disabled:pointer-events-none"
                :disabled="!!field.keyvalue_doctype_field && !doctypeFor(field.keyvalue_doctype_field)"
                @click="addKeyValueRow(field.name)"
              >
                + Add field
              </button>
            </div>
            <p v-if="field.keyvalue_doctype_field && !doctypeFor(field.keyvalue_doctype_field)" class="text-[12px] text-muted italic">
              Pick a document type above first.
            </p>
            <p v-else-if="!keyValueRows(field.name).length" class="text-[12px] text-muted italic">No fields configured.</p>
            <div v-for="(row, i) in keyValueRows(field.name)" :key="i" class="flex items-center gap-1.5">
              <!-- Real doctype fieldnames (typed, Select/Link-aware value
                   editor below) when this keyvalue field points at a
                   doctype; plain free-text key=value otherwise. -->
              <Combobox
                v-if="field.keyvalue_doctype_field"
                :model-value="row.key" size="sm" class="flex-1" placeholder="field name"
                :options="erpFieldsFor(doctypeFor(field.keyvalue_doctype_field)).map(f => ({ value: f.fieldname, label: f.label }))"
                @update:model-value="v => { row.key = v; row.value = ''; syncKeyValue(field.name) }"
              />
              <Input v-else v-model="row.key" placeholder="field name" size="sm" class="flex-1" @update:model-value="syncKeyValue(field.name)" />

              <ErpFieldValueInput
                v-if="field.keyvalue_doctype_field"
                :model-value="row.value" class="flex-1"
                :field-meta="erpFieldMeta(doctypeFor(field.keyvalue_doctype_field), row.key)"
                :project="props.project"
                @update:model-value="v => { row.value = v; syncKeyValue(field.name) }"
              />
              <Input v-else v-model="row.value" placeholder="value" size="sm" class="flex-1" @update:model-value="syncKeyValue(field.name)" />

              <IconButton size="sm" variant="light" aria-label="Remove" @click="removeKeyValueRow(field.name, i)">
                <Icon :icon="Trash2" class="size-3.5" />
              </IconButton>
            </div>
          </div>

          <div v-else-if="field.type === 'template'" class="flex flex-col gap-1">
            <label class="text-xs font-medium text-foreground">{{ fieldLabel(field) }}<span v-if="field.required" class="text-danger">*</span></label>
            <Textarea v-model="localConfig[field.name]" :rows="3" />
          </div>

          <div v-else-if="field.type === 'case_list'" class="flex flex-col gap-1.5">
            <div class="flex items-center justify-between">
              <p class="text-xs font-medium text-foreground">{{ fieldLabel(field) }}<span v-if="field.required" class="text-danger">*</span></p>
              <button
                type="button" class="text-[12px] text-accent font-medium hover:underline disabled:opacity-40 disabled:pointer-events-none"
                :disabled="casesFor(field.name).length >= 5" @click="addCase(field.name)"
              >+ Add case</button>
            </div>
            <p v-if="!casesFor(field.name).length" class="text-[12px] text-muted italic">No cases — everything falls through to Default.</p>
            <div v-for="(c, i) in casesFor(field.name)" :key="i" class="flex items-center gap-1.5">
              <span class="text-[11px] text-muted w-11 shrink-0">Case {{ i + 1 }}</span>
              <Input v-model="casesFor(field.name)[i]" placeholder="value" size="sm" class="flex-1" />
              <IconButton size="sm" variant="light" aria-label="Remove case" @click="casesFor(field.name).splice(i, 1)">
                <Icon :icon="Trash2" class="size-3.5" />
              </IconButton>
            </div>
            <p class="text-[11px] text-muted">Anything not matching a case above routes to Default. Cap of 5 in v1.</p>
          </div>

          <div v-else-if="field.type === 'conditions'" class="flex flex-col gap-1.5">
            <div class="flex items-center justify-between">
              <p class="text-xs font-medium text-foreground">{{ fieldLabel(field) }}</p>
              <button type="button" class="text-[12px] text-accent font-medium hover:underline" @click="addCondition(field.name)">
                + Add condition
              </button>
            </div>
            <p v-if="!conditionsFor(field.name).length" class="text-[12px] text-muted italic">
              No conditions — always matches.
            </p>
            <p v-if="field.condition_fields_dynamic_doctype_field && !doctypeFor(field.condition_fields_dynamic_doctype_field)"
              class="text-[12px] text-muted italic">
              Pick a document type above to get real field options here.
            </p>
            <div v-for="(c, i) in conditionsFor(field.name)" :key="i" class="flex items-center gap-1.5">
              <Combobox
                v-model="c.field" :options="conditionFieldOptionsResolved(field)" allow-create
                placeholder="field" size="sm" class="flex-1"
              />
              <Select v-model="c.op" size="sm" class="w-[140px]">
                <SelectItem v-for="op in CONDITION_OPS" :key="op.value" :value="op.value">{{ op.label }}</SelectItem>
              </Select>
              <!-- Dynamic (doc_event) context: the real ERPNext fieldtype
                   drives Select/Check/Date/Link editors, same as any other
                   ERP field value. Static context: the legacy options/plain
                   text split. -->
              <ErpFieldValueInput
                v-if="field.condition_fields_dynamic_doctype_field && conditionValueMetaResolved(field, c.field)"
                v-model="c.value"
                :field-meta="conditionValueMetaResolved(field, c.field)"
                :project="props.project"
                :class="{ 'opacity-45 pointer-events-none': c.op === 'is_set' || c.op === 'is_not_set' }"
              />
              <Combobox
                v-else-if="!field.condition_fields_dynamic_doctype_field && conditionValueOptions(c.field, field.condition_fields_source)"
                v-model="c.value" :options="conditionValueOptions(c.field, field.condition_fields_source)" allow-create
                placeholder="value" size="sm" class="flex-1"
                :is-disabled="c.op === 'is_set' || c.op === 'is_not_set'"
              />
              <Input
                v-else
                v-model="c.value" placeholder="value" size="sm" class="flex-1"
                :is-disabled="c.op === 'is_set' || c.op === 'is_not_set'"
              />
              <IconButton size="sm" variant="light" aria-label="Remove" @click="conditionsFor(field.name).splice(i, 1)">
                <Icon :icon="Trash2" class="size-3.5" />
              </IconButton>
            </div>
          </div>

          <p v-if="field.description" class="text-[11px] text-muted -mt-3">{{ field.description }}</p>
        </template>

        <p v-if="!schema.length" class="text-xs text-muted italic">This node has no configurable fields.</p>

        <!-- Advanced/raw-JSON — never the primary path (WORKPLAN-PHASE25 A2:
             "no raw JSON visible by default anywhere"), only for fields the
             schema itself marks as type=json (today: integration.http_request
             headers, not touched by this pass — kept generic for when it is). -->
        <template v-if="advancedFields.length">
          <button type="button" class="text-xs text-muted hover:text-foreground text-left" @click="showAdvanced = !showAdvanced">
            {{ showAdvanced ? 'Hide' : 'Show' }} advanced
          </button>
          <template v-if="showAdvanced">
            <div v-for="field in advancedFields" :key="field.name" class="flex flex-col gap-1">
              <label class="text-xs font-medium text-foreground">{{ fieldLabel(field) }}</label>
              <Textarea v-model="jsonDrafts[field.name]" :rows="4" class="font-mono text-xs" @blur="commitJson(field.name)" />
              <p v-if="jsonErrors[field.name]" class="text-[11px] text-danger">{{ jsonErrors[field.name] }}</p>
              <p v-if="field.description" class="text-[11px] text-muted">{{ field.description }}</p>
            </div>
          </template>
        </template>
      </template>

      <template v-else>
        <div class="flex flex-col gap-4">
          <div>
            <p class="text-sm font-medium text-foreground mb-2">Retry on failure</p>
            <div class="flex items-center gap-2">
              <Input v-model.number="retryAttempts" type="number" label="Attempts" size="sm" class="w-28" />
              <Input v-model.number="retryWaitSeconds" type="number" label="Wait between tries (sec)" size="sm" class="w-40" />
            </div>
            <p class="text-[11px] text-muted mt-1">1 attempt = no retry.</p>
          </div>
          <div>
            <p class="text-sm font-medium text-foreground mb-2">If this step fails</p>
            <Select v-model="onError" size="sm">
              <SelectItem v-for="opt in ON_ERROR_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</SelectItem>
            </Select>
            <p v-if="onError === 'error_branch'" class="text-[11px] text-muted mt-1">
              An "error" output appeared on this node — connect it to whatever should run instead.
            </p>
          </div>
          <div class="flex items-center justify-between py-1">
            <div class="min-w-0 pr-3">
              <p class="text-sm text-foreground">Disable this node</p>
              <p class="text-[11px] text-muted">Skipped — the workflow passes straight through to what's connected next.</p>
            </div>
            <Switch v-model="disabled" size="sm" />
          </div>
        </div>
      </template>
    </ModalBody>
    <ModalFooter>
      <Button variant="ghost" size="sm" color="danger" @click="onDelete">Delete node</Button>
      <div class="flex-1" />
      <Button variant="light" size="sm" @click="onClose">Cancel</Button>
      <Button color="accent" size="sm" :is-disabled="hasJsonErrors" @click="onSave">Apply</Button>
    </ModalFooter>
  </Modal>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Trash2, Loader2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { listWebhookTokens, createWebhookToken, revokeWebhookToken, searchErpDocuments } from '@/utils/api'
import { useErpDoctypeFields } from '@/composables/useErpDoctypeFields'
import ErpFieldValueInput from '@/components/ErpFieldValueInput.vue'
import Modal from '@/ui/Modal.vue'
import ModalHeader from '@/ui/ModalHeader.vue'
import ModalBody from '@/ui/ModalBody.vue'
import ModalFooter from '@/ui/ModalFooter.vue'
import Tabs from '@/ui/Tabs.vue'
import Input from '@/ui/Input.vue'
import Select from '@/ui/Select.vue'
import SelectItem from '@/ui/SelectItem.vue'
import Combobox from '@/ui/Combobox.vue'
import Textarea from '@/ui/Textarea.vue'
import Switch from '@/ui/Switch.vue'
import Button from '@/ui/Button.vue'
import IconButton from '@/ui/IconButton.vue'
import Icon from '@/ui/Icon.vue'
import { nodeMeta } from '@/constants/automation-node-registry'
import { confirmDialog } from '@/composables/useConfirmDialog'

// Generic, schema-driven config editor for ANY node type — reads
// config_schema straight from the node registry (automation.py::
// get_node_registry) instead of a hand-written form per node type.
// WORKPLAN-PHASE25 A2: rebuilt from a Drawer showing mostly raw JSON into
// this Modal with typed, human fields — the raw-JSON drawer was itself a
// real gap (technically "configurable" but unusable by a non-technical PM).
const props = defineProps({
  open:    { type: Boolean, default: false },
  node:    { type: Object, default: null }, // Vue Flow canvas node (id, data.{typeKey,label,config,retry,onError,disabled})
  options: { type: Object, default: () => ({}) }, // get_automation_options(project) response
  scope:   { type: String, default: 'workspace' }, // the WORKFLOW's own scope — trigger.webhook creates tokens matching it
  project: { type: String, default: null },
})
const emit = defineEmits(['update:open', 'save', 'delete'])

const CONDITION_OPS = [
  { value: 'eq', label: 'equals' }, { value: 'ne', label: 'not equals' },
  { value: 'in', label: 'in' }, { value: 'nin', label: 'not in' },
  { value: 'contains', label: 'contains' }, { value: 'changed', label: 'changed' },
  { value: 'gt', label: '>' }, { value: 'gte', label: '>=' },
  { value: 'lt', label: '<' }, { value: 'lte', label: '<=' },
  { value: 'is_set', label: 'is set' }, { value: 'is_not_set', label: 'is empty' },
]
const ON_ERROR_OPTIONS = [
  { value: 'stop', label: 'Stop the workflow' },
  { value: 'continue', label: 'Continue to the next step' },
  { value: 'error_branch', label: 'Route to a separate error path' },
]

const meta = computed(() => (props.node ? nodeMeta(props.node.data.typeKey) : null))
const categoryLabel = computed(() => meta.value?.category ? `${meta.value.category[0].toUpperCase()}${meta.value.category.slice(1)}` : '')
const schema = computed(() => meta.value?.config_schema ?? [])
const showSettingsTab = computed(() => meta.value?.supports_retry === true)

function fieldLabel(field) {
  return field.label ?? field.name.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}
function showIfMatches(field) {
  if (!field.show_if) return true
  return localConfig[field.show_if.field] === field.show_if.eq
}
const visibleFields = computed(() => schema.value.filter((f) => f.type !== 'json' && showIfMatches(f)))
const advancedFields = computed(() => schema.value.filter((f) => f.type === 'json'))

// options_source resolution — normalizes get_automation_options()'s mixed
// shapes (plain string lists for statuses/labels/etc, {user,full_name} for
// members, already-{value,label} for condition_fields/actions/...) into ONE
// [{value,label}] shape every Combobox consumes the same way.
function normalizeOptions(raw) {
  if (!Array.isArray(raw)) return []
  return raw.map((item) => {
    if (typeof item === 'string') return { value: item, label: item }
    if (item && typeof item === 'object') {
      if ('value' in item && 'label' in item) return item
      if ('user' in item) return { value: item.user, label: item.full_name || item.user }
    }
    return { value: item, label: String(item) }
  })
}
function optionsFor(field) {
  if (field.options_source) return normalizeOptions(props.options?.[field.options_source])
  if (Array.isArray(field.options)) return normalizeOptions(field.options)
  return []
}
// condition_fields_source lets each trigger's own `conditions` schema field
// point at the option list that actually matches its payload shape (e.g.
// erp_finance_condition_fields, not the task-oriented default) — without it
// every trigger's condition-field picker showed the same status/priority/
// assignees list even for triggers whose events carry no task at all.
function conditionFieldOptions(field) {
  return normalizeOptions(props.options?.[field?.condition_fields_source || 'condition_fields'])
}
function conditionValueOptions(fieldValue, sourceKey) {
  const entry = (props.options?.[sourceKey || 'condition_fields'] || []).find((f) => f.value === fieldValue)
  if (!entry) return null
  if (entry.type === 'select') return normalizeOptions(entry.options)
  if (entry.type === 'user') return normalizeOptions(props.options?.members)
  return null // number/label/unknown types: plain text input
}

// ERPNext doctype-field integration (Link search+clear, Select/Check/Date
// typing, doc_event's per-doctype condition fields) — the ONE shared
// implementation, also used by AutomationRuleEditor.vue.
const { erpFieldsFor, erpFieldsForRead, erpFieldMeta, erpDocLabel } = useErpDoctypeFields()

// A schema field can point at a SIBLING field holding the doctype to scope
// against (erp_link_search's doctype_field, keyvalue's keyvalue_doctype_field,
// conditions' condition_fields_dynamic_doctype_field) — this resolves that
// pointer against the live draft, not the schema.
function doctypeFor(pointerFieldName) {
  return pointerFieldName ? (localConfig[pointerFieldName] || '') : ''
}

function erpSearch(doctype, q) {
  if (!doctype) return Promise.resolve([])
  return searchErpDocuments(doctype, q, props.project).then(rows => rows.map(r => ({ value: r.name, label: r.label })))
}

// trigger.doc_event's conditions field has no static option list (the
// doctype is only known once the sibling "doctype" field is set) — resolve
// live from get_erp_doctype_fields_readonly instead of a fixed
// options-source lookup. Falls back to the normal static path for every
// other trigger's conditions field.
function dynamicConditionFields(field) {
  const doctype = doctypeFor(field?.condition_fields_dynamic_doctype_field)
  if (!doctype) return []
  return erpFieldsForRead(doctype).map((f) => ({ value: f.fieldname, label: f.label, _meta: f }))
}
function conditionFieldOptionsResolved(field) {
  if (field?.condition_fields_dynamic_doctype_field) return dynamicConditionFields(field)
  return conditionFieldOptions(field)
}
function conditionValueMetaResolved(field, fieldValue) {
  if (field?.condition_fields_dynamic_doctype_field) {
    return dynamicConditionFields(field).find((f) => f.value === fieldValue)?._meta || null
  }
  return null
}

const localLabel = ref('')
const localConfig = reactive({})
const jsonDrafts = reactive({})
const jsonErrors = reactive({})
const hasJsonErrors = computed(() => Object.values(jsonErrors).some(Boolean))
const showAdvanced = ref(false)
const activeTab = ref('configure')

const retryAttempts = ref(1)
const retryWaitSeconds = ref(0)
const onError = ref('stop')
const disabled = ref(false)

function conditionsFor(fieldName) {
  if (!Array.isArray(localConfig[fieldName])) localConfig[fieldName] = []
  return localConfig[fieldName]
}
function addCondition(fieldName) {
  conditionsFor(fieldName).push({ field: '', op: 'eq', value: '' })
}

// logic.switch's cases[] — a plain string list, each becoming its own
// output port (WorkflowNode's switchOutputPorts derives ports from this
// exact array on Apply). Capped at 5, matching the backend schema's
// description and the Go engine's "route to first pyStr-equal case" logic.
function casesFor(fieldName) {
  if (!Array.isArray(localConfig[fieldName])) localConfig[fieldName] = []
  return localConfig[fieldName]
}
function addCase(fieldName) {
  if (casesFor(fieldName).length >= 5) return
  casesFor(fieldName).push('')
}

// trigger.webhook's full lifecycle (WORKPLAN-PHASE25 B3) — loaded lazily
// (only when this node type's panel is actually open) rather than every
// panel open, since it's the one field type that hits the network on its
// own instead of just reading props.options.
const webhookTokens = ref([])
const webhookTokensLoading = ref(false)
const webhookTokensError = ref('')
const webhookCreateLabel = ref('')
const webhookCreating = ref(false)
const webhookUrlCopied = ref(false)

async function loadWebhookTokens() {
  webhookTokensLoading.value = true
  webhookTokensError.value = ''
  try {
    webhookTokens.value = await listWebhookTokens(props.project)
  } catch (e) {
    // Token management is workspace-admin-only (_require_workspace_admin_for_tokens)
    // regardless of this workflow's own scope — a project-scope BP Admin who
    // isn't a workspace admin hits this. Surfaced readably per spec, not a
    // silent empty list that looks like "no tokens exist yet".
    webhookTokensError.value = e?.message || 'You need workspace admin access to manage webhook tokens.'
  } finally {
    webhookTokensLoading.value = false
  }
}
const selectedWebhookToken = computed(() =>
  webhookTokens.value.find((t) => t.name === localConfig.webhook_token) || null)
const webhookUrl = computed(() => {
  if (!selectedWebhookToken.value) return ''
  const base = (props.options?.gateway_public_url || '').replace(/\/$/, '')
  return `${base}/v1/hooks/${selectedWebhookToken.value.token}`
})
async function copyWebhookUrl() {
  try { await navigator.clipboard.writeText(webhookUrl.value) } catch { /* clipboard unavailable */ }
  webhookUrlCopied.value = true
  setTimeout(() => { webhookUrlCopied.value = false }, 1800)
}
async function createNewWebhookToken() {
  webhookCreating.value = true
  try {
    const res = await createWebhookToken({
      label: webhookCreateLabel.value, scope: props.scope, project: props.project,
    })
    webhookTokens.value.unshift({ ...res, is_active: 1, call_count: 0, last_used: null, last_event: null })
    localConfig.webhook_token = res.name
    webhookCreateLabel.value = ''
    toast.success('Webhook token created')
  } catch (e) {
    toast.error(e?.message || 'Could not create webhook token')
  } finally {
    webhookCreating.value = false
  }
}
async function revokeSelectedWebhookToken() {
  const tok = selectedWebhookToken.value
  if (!tok || !await confirmDialog(`Revoke "${tok.label}"? Any external service still calling it will start getting rejected.`, { danger: true })) return
  try {
    await revokeWebhookToken(tok.name)
    tok.is_active = 0
    toast.success('Webhook token revoked')
  } catch (e) {
    toast.error(e?.message || 'Could not revoke webhook token')
  }
}
function fmtRelative(dt) {
  try {
    const diffMs = Date.now() - new Date(dt).getTime()
    const mins = Math.round(diffMs / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.round(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    return `${Math.round(hrs / 24)}d ago`
  } catch { return dt }
}

// keyvalue fields store as a plain {key: value} object in config (matching
// _update_erpnext_document's cfg.get("fields") shape exactly) — rows[] here
// is just the editable array form, synced back into that object on change.
const keyValueDrafts = reactive({})
function keyValueRows(fieldName) {
  if (!keyValueDrafts[fieldName]) keyValueDrafts[fieldName] = []
  return keyValueDrafts[fieldName]
}
function addKeyValueRow(fieldName) {
  keyValueRows(fieldName).push({ key: '', value: '' })
  syncKeyValue(fieldName)
}
function removeKeyValueRow(fieldName, i) {
  keyValueRows(fieldName).splice(i, 1)
  syncKeyValue(fieldName)
}
function syncKeyValue(fieldName) {
  const obj = {}
  for (const row of keyValueRows(fieldName)) {
    if (row.key) obj[row.key] = row.value
  }
  localConfig[fieldName] = obj
}

function commitJson(fieldName) {
  try {
    localConfig[fieldName] = jsonDrafts[fieldName].trim() ? JSON.parse(jsonDrafts[fieldName]) : {}
    jsonErrors[fieldName] = ''
  } catch (e) {
    jsonErrors[fieldName] = 'Invalid JSON — ' + e.message
  }
}

// Re-seed the local draft every time a DIFFERENT node opens (or the same
// node re-opens) — never mutate props.node.data directly until Apply, so
// Cancel genuinely discards edits instead of leaving partial changes live
// on the canvas.
watch(() => [props.open, props.node?.id], () => {
  if (!props.open || !props.node) return
  activeTab.value = 'configure'
  showAdvanced.value = false
  localLabel.value = props.node.data.label ?? ''
  const cfg = props.node.data.config ?? {}
  Object.keys(localConfig).forEach((k) => delete localConfig[k])
  Object.keys(jsonDrafts).forEach((k) => delete jsonDrafts[k])
  Object.keys(jsonErrors).forEach((k) => delete jsonErrors[k])
  Object.keys(keyValueDrafts).forEach((k) => delete keyValueDrafts[k])
  for (const field of schema.value) {
    if (field.type === 'json') {
      jsonDrafts[field.name] = JSON.stringify(cfg[field.name] ?? {}, null, 2)
      localConfig[field.name] = cfg[field.name] ?? {}
    } else if (field.type === 'conditions') {
      localConfig[field.name] = Array.isArray(cfg[field.name]) ? cfg[field.name].map((c) => ({ ...c })) : []
    } else if (field.type === 'case_list') {
      localConfig[field.name] = Array.isArray(cfg[field.name]) ? [...cfg[field.name]] : []
    } else if (field.type === 'keyvalue') {
      const obj = cfg[field.name] ?? {}
      keyValueDrafts[field.name] = Object.entries(obj).map(([key, value]) => ({ key, value }))
      localConfig[field.name] = { ...obj }
    } else if (field.type === 'member' || (field.type === 'select' && field.multi)) {
      localConfig[field.name] = Array.isArray(cfg[field.name]) ? [...cfg[field.name]] : []
    } else if (field.type === 'boolean') {
      localConfig[field.name] = cfg[field.name] ?? field.default ?? false
    } else {
      localConfig[field.name] = cfg[field.name] ?? field.default ?? ''
    }
  }
  const retry = props.node.data.retry
  retryAttempts.value = retry?.max_attempts ?? 1
  retryWaitSeconds.value = retry?.wait_seconds ?? 0
  onError.value = props.node.data.onError ?? 'stop'
  disabled.value = props.node.data.disabled ?? false

  webhookCreateLabel.value = ''
  webhookUrlCopied.value = false
  if (schema.value.some((f) => f.type === 'webhook_lifecycle')) loadWebhookTokens()
}, { immediate: true })

function onClose() { emit('update:open', false) }
function onSave() {
  for (const name of Object.keys(jsonDrafts)) commitJson(name)
  if (hasJsonErrors.value) return
  emit('save', {
    nodeId: props.node.id,
    label: localLabel.value,
    config: { ...localConfig },
    retry: retryAttempts.value > 1 ? { max_attempts: retryAttempts.value, wait_seconds: retryWaitSeconds.value || 0 } : null,
    onError: onError.value,
    disabled: disabled.value,
  })
  onClose()
}
function onDelete() {
  emit('delete', props.node.id)
  onClose()
}
</script>
