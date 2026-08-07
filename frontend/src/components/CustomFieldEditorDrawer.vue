<template>
  <Drawer :open="open" @update:open="$emit('update:open', $event)" size="lg">
    <DrawerHeader @close="$emit('update:open', false)">
      <span class="text-[14px] font-semibold text-foreground">
        {{ field ? 'Edit field' : 'New field' }}
      </span>
    </DrawerHeader>
    <DrawerBody class="space-y-5">
      <div>
        <p class="text-[12px] font-medium text-muted mb-1.5">Field name</p>
        <Input v-model="fieldDraft.field_label" size="md" placeholder="e.g. Risk score" />
      </div>
      <div>
        <p class="text-[12px] font-medium text-muted mb-1.5">Description <span class="text-[11px]">(optional)</span></p>
        <Input v-model="fieldDraft.description" size="md" placeholder="What is this field for?" />
      </div>
      <div>
        <p class="text-[12px] font-medium text-muted mb-1.5">Type</p>
        <Select v-model="fieldDraft.field_type" size="md" :isDisabled="!!field">
          <SelectItem v-for="t in FIELD_TYPES" :key="t.value" :value="t.value">{{ t.label }}</SelectItem>
        </Select>
        <p v-if="field" class="text-[11px] text-muted mt-1">Type can't change once a field has values — create a new field instead.</p>
      </div>

      <div v-if="['select', 'multiselect'].includes(fieldDraft.field_type)">
        <p class="text-[12px] font-medium text-muted mb-1.5">Options</p>
        <div class="space-y-1.5">
          <div v-for="(opt, oi) in fieldDraft.options" :key="opt.id" class="flex items-center gap-2">
            <Input v-model="opt.label" size="sm" :placeholder="`Option ${oi + 1}`" class="flex-1" />
            <IconButton size="sm" variant="light" color="danger" :isDisabled="fieldDraft.options.length <= 1"
              @click="fieldDraft.options.splice(oi, 1)">
              <Icon :icon="X" />
            </IconButton>
          </div>
          <Button size="sm" variant="light" color="primary" @click="addFieldOption">
            <Icon :icon="Plus" class="mr-1" /> Add option
          </Button>
        </div>
      </div>

      <div v-else-if="fieldDraft.field_type === 'link'">
        <p class="text-[12px] font-medium text-muted mb-1.5">ERPNext document type</p>
        <Input v-model="fieldDraft.link_doctype" size="md" placeholder="e.g. Customer" />
        <p class="text-[11px] text-muted mt-1">The exact ERPNext doctype name this field links to.</p>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <p class="text-[12px] font-medium text-muted mb-1.5">Applies to</p>
          <Select v-model="fieldDraft.applies_to" size="md">
            <SelectItem value="Tasks">Tasks</SelectItem>
            <SelectItem value="Projects">Projects</SelectItem>
            <SelectItem value="Both">Both</SelectItem>
          </Select>
        </div>
        <div>
          <p class="text-[12px] font-medium text-muted mb-1.5">Show in list view</p>
          <div class="h-9 flex items-center">
            <Switch v-model="fieldDraft.show_in_list" />
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <p class="text-[12px] font-medium text-muted mb-1.5">Can view (minimum role)</p>
          <Select v-model="fieldDraft.view_role" size="md">
            <SelectItem v-for="r in ROLE_OPTIONS" :key="r" :value="r">{{ r }}</SelectItem>
          </Select>
        </div>
        <div>
          <p class="text-[12px] font-medium text-muted mb-1.5">Can edit (minimum role)</p>
          <Select v-model="fieldDraft.edit_role" size="md">
            <SelectItem v-for="r in ROLE_OPTIONS" :key="r" :value="r">{{ r }}</SelectItem>
          </Select>
        </div>
      </div>

      <!-- Conditional marker -->
      <div v-if="NUMERIC_FIELD_TYPES.has(fieldDraft.field_type)" class="pt-2 border-t border-separator">
        <p class="text-[13px] font-semibold text-foreground mt-4 mb-1">Conditional marker</p>
        <p class="text-[12px] text-muted mb-3">Show a colored dot when the value matches a rule.</p>

        <div class="space-y-2">
          <div v-for="(rule, ri) in fieldDraft.conditional_rules" :key="ri"
            class="flex items-center gap-2 rounded-[8px] bg-surface-secondary p-2">
            <Select v-model="rule.op" size="sm" class="w-[120px] shrink-0">
              <SelectItem value="lte">≤</SelectItem>
              <SelectItem value="between">is between</SelectItem>
              <SelectItem value="gte">≥</SelectItem>
            </Select>
            <Input v-model.number="rule.value" type="number" size="sm" class="w-[90px]" />
            <template v-if="rule.op === 'between'">
              <span class="text-[12px] text-muted">&amp;</span>
              <Input v-model.number="rule.value2" type="number" size="sm" class="w-[90px]" />
            </template>
            <div class="flex-1" />
            <button v-for="c in MARKER_COLORS" :key="c" type="button"
              class="size-5 rounded-full shrink-0 transition-transform"
              :style="{ background: c, transform: rule.color === c ? 'scale(1.15)' : 'scale(1)', boxShadow: rule.color === c ? `0 0 0 2px var(--surface), 0 0 0 3.5px ${c}` : 'none' }"
              @click="rule.color = c" />
            <IconButton size="sm" variant="light" color="danger" @click="fieldDraft.conditional_rules.splice(ri, 1)">
              <Icon :icon="X" />
            </IconButton>
          </div>
        </div>
        <Button size="sm" variant="light" color="primary" class="mt-2" @click="addMarkerRule">
          <Icon :icon="Plus" class="mr-1" /> Add another rule
        </Button>
      </div>

      <div class="pt-2 border-t border-separator">
        <div class="flex items-center justify-between py-2">
          <div>
            <p class="text-[13px] text-foreground">Field status</p>
            <p class="text-[12px] text-muted mt-0.5">Disabled fields are hidden everywhere without losing data.</p>
          </div>
          <Switch v-model="fieldDraft.enabled" />
        </div>
      </div>
    </DrawerBody>
    <DrawerFooter class="justify-between">
      <Button v-if="field" variant="light" color="danger" size="sm" :isLoading="deletingField"
        @click="removeField">
        Delete
      </Button>
      <div v-else />
      <div class="flex items-center gap-2">
        <Button variant="bordered" color="default" size="sm" @click="$emit('update:open', false)">Cancel</Button>
        <Button variant="solid" color="primary" size="sm" :isLoading="savingField" @click="saveField">Save</Button>
      </div>
    </DrawerFooter>
  </Drawer>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import {
  Button, Select, SelectItem, Switch, Icon, IconButton, Input,
  Drawer, DrawerHeader, DrawerBody, DrawerFooter,
} from '@/ui'
import { Plus, X } from 'lucide-vue-next'
import { createLibraryField, updateLibraryField, deleteLibraryField } from '@/utils/api'
import { FIELD_TYPES, NUMERIC_FIELD_TYPES } from '@/utils/customFields'
import { confirmDialog, alertDialog } from '@/composables/useConfirmDialog'

const props = defineProps({
  open: { type: Boolean, default: false },
  /** Existing field row to edit (library-dict shape), or null for "New field". */
  field: { type: Object, default: null },
  /** null = workspace-shared field (workspace-admin gated); a project name =
   *  private field owned by that project (project-Admin gated). Immutable
   *  after creation — never sent on update. */
  ownerProject: { type: String, default: null },
})
const emit = defineEmits(['update:open', 'saved', 'deleted'])

const ROLE_OPTIONS = ['Admin', 'Manager', 'Member', 'Viewer']
const MARKER_COLORS = ['#22c55e', '#f97316', '#ef4444', '#0ea5e9', '#a855f7', '#64748b']

function blankDraft() {
  return {
    field_label: '', description: '', field_type: 'text', options: [], link_doctype: '',
    applies_to: 'Tasks', view_role: 'Viewer', edit_role: 'Member',
    show_in_list: false, enabled: true, conditional_rules: [],
  }
}
const fieldDraft = reactive(blankDraft())
const savingField = ref(false)
const deletingField = ref(false)

// Data-driven instead of imperative open*() methods: the parent just sets
// `open`/`field` props, and the drawer initializes its own draft whenever
// it transitions to open — mirrors the controlled-component pattern Drawer
// itself already uses.
watch(() => props.open, (isOpen) => {
  if (!isOpen) return
  if (props.field) {
    const row = props.field
    Object.assign(fieldDraft, {
      field_label: row.field_label, description: row.description || '',
      field_type: row.field_type,
      options: row.field_type === 'link' ? [] : (row.options || []).map(o => ({ ...o })),
      link_doctype: row.field_type === 'link' ? (row.options || {}).link_doctype || '' : '',
      applies_to: row.applies_to, view_role: row.view_role, edit_role: row.edit_role,
      show_in_list: row.show_in_list, enabled: row.enabled,
      conditional_rules: (row.conditional_rules || []).map(r => ({ ...r })),
    })
  } else {
    Object.assign(fieldDraft, blankDraft())
  }
}, { immediate: true })

function addFieldOption() {
  fieldDraft.options.push({ id: 'opt_' + Math.random().toString(16).slice(2, 10), label: '' })
}
function addMarkerRule() {
  fieldDraft.conditional_rules.push({ op: 'lte', value: 0, color: MARKER_COLORS[0] })
}

async function saveField() {
  if (!fieldDraft.field_label.trim()) return
  savingField.value = true
  try {
    const options = fieldDraft.field_type === 'link'
      ? { link_doctype: fieldDraft.link_doctype.trim() }
      : fieldDraft.options
    const payload = {
      field_label: fieldDraft.field_label.trim(),
      description: fieldDraft.description,
      options,
      applies_to: fieldDraft.applies_to,
      view_role: fieldDraft.view_role,
      edit_role: fieldDraft.edit_role,
      show_in_list: fieldDraft.show_in_list ? 1 : 0,
      conditional_rules: fieldDraft.conditional_rules,
    }
    let result
    if (props.field) {
      payload.enabled = fieldDraft.enabled ? 1 : 0
      result = await updateLibraryField(props.field.name, payload)
    } else {
      payload.field_type = fieldDraft.field_type
      payload.owner_project = props.ownerProject || undefined
      result = await createLibraryField(payload)
    }
    emit('saved', result)
    emit('update:open', false)
  } catch (e) {
    console.error('saveField error', e)
  } finally {
    savingField.value = false
  }
}

async function removeField() {
  if (!props.field) return
  if (!await confirmDialog(`Delete "${props.field.field_label}"? This can't be undone.`, { danger: true })) return
  deletingField.value = true
  try {
    await deleteLibraryField(props.field.name)
    emit('deleted', props.field.name)
    emit('update:open', false)
  } catch (e) {
    alertDialog(e.message || 'Could not delete this field.')
  } finally {
    deletingField.value = false
  }
}
</script>
