<template>
<Teleport to="body">
<div v-if="open" class="jv-root">
  <div class="jv-backdrop" @click="close"/>

  <div class="jv-panel">

    <!-- Header -->
    <header class="jv-header">
      <div class="jv-crumb">
        <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" style="color:var(--muted);flex-shrink:0"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
        <span class="jv-crumb-project">{{ store.currentProject?.project_name }}</span>
        <span class="jv-crumb-sep">/</span>
        <span class="jv-crumb-key">New Task</span>
      </div>
      <div class="jv-header-actions">
        <button class="jv-hbtn" @click="close" title="Close">
          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>
    </header>

    <!-- Two-column body -->
    <div class="jv-body">

      <!-- LEFT: main content -->
      <div class="jv-main">

        <!-- Start from template (not offered for subtasks — create_task_from_template
             has no parent_task param, it always stamps a top-level task) -->
        <div v-if="templates.length && !form.parent_task" class="jv-section">
          <div class="flex items-center gap-2 mb-2">
            <span class="jv-section-title" style="margin-bottom:0">Start from template</span>
            <span v-if="!templatesUnlocked"
              class="inline-flex items-center gap-1 text-xs font-semibold px-1.5 py-0.5 rounded
                     bg-[var(--surface-secondary)] text-muted uppercase tracking-wider">
              <Icon :icon="Lock" class="size-3" /> {{ templatesRequiredPlan }}
            </span>
          </div>
          <Select v-model="selectedTemplate" size="sm" fullWidth placeholder="Choose a template…"
            :isDisabled="!templatesUnlocked" @update:modelValue="applyTemplate">
            <SelectItem v-for="t in templates" :key="t.name" :value="t.name">{{ t.template_name }}</SelectItem>
          </Select>
        </div>

        <!-- Type row + title -->
        <div class="jv-title-block">
          <div class="jv-section-title">Task title</div>
          <textarea
            ref="titleRef"
            v-model="form.title"
            :placeholder="`${taskWord} title`"
            class="jv-title--input"
            rows="1"
            @keydown.enter.prevent.exact="submit"
            @keydown.meta.enter.prevent="submit"
            @input="autoResize"
          />
        </div>

        <!-- Description -->
        <div class="jv-section">
          <div class="jv-section-title">Description</div>
          <RichTextEditor :modelValue="form.description" placeholder="Add a description…" min-height="80px" :always-toolbar="true" @update:modelValue="v => form.description = v" />
        </div>

        <!-- Parent task/issue -->
        <div class="jv-section" ref="parentSectionRef">
          <div class="jv-section-title">Parent {{ taskWord.toLowerCase() }}</div>

          <!-- Selected parent chip -->
          <div v-if="form.parent_task" class="jv-parent-chip">
            <span class="jv-st-key">{{ form.parent_task_key }}</span>
            <span class="jv-parent-chip-title">{{ form.parent_issue_resolved }}</span>
            <button class="jv-assignee-rm" @click="clearParent">×</button>
          </div>

          <!-- Search input -->
          <div v-else class="jv-add-row jv-add-row--link" style="flex-wrap:nowrap" @click.stop>
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" style="color:var(--muted);flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            <input
              v-model="parentQ"
              class="jv-add-input"
              :placeholder="`Search ${taskWord.toLowerCase()}s…`"
              autocomplete="off"
              @focus="onParentFocus"
              @input="debouncedParentSearch"
              @keydown.escape="showParentResults = false"
            />
          </div>

          <!-- Results dropdown -->
          <div v-if="showParentResults && parentResults.length" class="jv-parent-results">
            <div
              v-for="r in parentResults" :key="r.name"
              class="jv-parent-result"
              @mousedown.prevent="selectParent(r)"
            >
              <span class="jv-st-key">{{ r.task_key }}</span>
              <span class="jv-parent-result-title">{{ r.title }}</span>
              <span class="jv-st-status" :style="{ background: wfColor(r.status)+'1A', color: wfColor(r.status) }">{{ r.status }}</span>
            </div>
          </div>
          <div v-else-if="showParentResults && parentLoading" class="jv-parent-empty">Searching…</div>
          <div v-else-if="showParentResults && parentQ && !parentResults.length" class="jv-parent-empty">No tasks found</div>
        </div>
<!-- Attachments -->
    <div style="padding-top: 20px; background:var(--overlay);">
      <div class="jv-section-title" style="font-weight:600;color:var(--foreground);font-size:var(--text-base);margin-bottom:8px;border:none;padding-bottom:0;text-transform:none;letter-spacing:normal;">Attachments</div>
      <TaskAttachments
        :modelValue="pendingAttachments"
        :issue-name="null"
        @update:modelValue="v => pendingAttachments = v"
        @queued="f => queuedFiles.push(f)"
      />
    </div>
      </div><!-- /jv-main -->

      <!-- RIGHT: sidebar -->
      <aside class="jv-sidebar">

        <!-- STATUS -->
        <div class="jv-sb-field jv-sb-field--status">
          <div class="jv-sb-label">Status</div>
          <div class="jv-sb-val">
            <div class="jv-sb-pill-wrap">
              <FieldDropdown width="w-44">
                <template #trigger>
                  <button class="jv-sb-inline-btn">
                    <div class="jv-sb-inline-btn-content">
                      <span class="w-2 h-2 rounded-full flex-shrink-0" :style="{ background: statusColor }"/>
                      <span :class="form.status ? 'text-[var(--foreground)]' : 'jv-sb-unset'">{{ form.status || 'Status' }}</span>
                    </div>
                    <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                  </button>
                </template>
                <DropdownItem v-for="s in store.workflowStates" :key="s.name" :active="form.status === s.name" @click="form.status = s.name">
                  <span class="w-2 h-2 rounded-sm shrink-0" :style="{ background: s.color }"/>{{ s.name }}
                </DropdownItem>
                <div class="jv-dd-sep"/>
                <template v-if="!showNewStatus">
                  <div @click.stop="showNewStatus=true">
                    <DropdownItem>
                      <svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
                      <span style="color:var(--muted)">Create status</span>
                    </DropdownItem>
                  </div>
                </template>
                <template v-else>
                  <div class="jv-inline-create" @click.stop>
                    <input v-model="newStatusName" class="jv-ic-input" placeholder="Status name" autofocus @keydown.enter.prevent="ciCreateStatus" @keydown.escape="showNewStatus=false"/>
                    <div class="jv-ic-colors">
                      <button v-for="c in STATUS_COLORS" :key="c" class="jv-ic-swatch" :class="{ active: newStatusColor===c }" :style="{ background: c }" @click.stop="newStatusColor=c"/>
                    </div>
                    <div class="jv-ic-row">
                      <select v-model="newStatusCategory" class="jv-ic-select">
                        <option value="unstarted">Unstarted</option>
                        <option value="started">Started</option>
                        <option value="completed">Completed</option>
                        <option value="cancelled">Cancelled</option>
                      </select>
                      <button class="jv-ic-save" :disabled="!newStatusName.trim()" @click.stop="ciCreateStatus">Add</button>
                    </div>
                  </div>
                </template>
              </FieldDropdown>
            </div>
          </div>
        </div>

        <!-- ASSIGNEE -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Assignee</div>
          <div class="jv-sb-val">
            <div class="jv-sb-pill-wrap">
              <FieldDropdown width="w-52" :close-on-select="false">
                <template #trigger>
                  <button class="jv-sb-inline-btn">
                    <div class="jv-sb-inline-btn-content">
                      <template v-if="form.assignees?.length">
                        <div class="jv-av-stack">
                          <span
                            v-for="(a, i) in form.assignees.slice(0, 3)"
                            :key="a.user"
                            class="jv-av jv-av-sm jv-av-stacked"
                            :style="{ background: aColor(a.user), zIndex: 3 - i }"
                          >{{ ini(a.full_name) }}</span>
                        </div>
                        <span class="jv-av-trigger-label">
                          {{ form.assignees[0].full_name?.split(' ')[0] }}<span v-if="form.assignees.length > 1" class="jv-av-extra">+{{ form.assignees.length - 1 }}</span>
                        </span>
                      </template>
                      <span v-else class="jv-sb-unset">Unassigned</span>
                    </div>
                    <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                  </button>
                </template>
                <template #search>
                  <div class="jv-dd-search"><input v-model="assigneeQ" autofocus placeholder="Search members…" class="jv-dd-input"/></div>
                </template>
                <DropdownItem @click="form.assignees = []"><div class="jv-av-empty"/>Unassigned</DropdownItem>
                <div class="jv-dd-sep"/>
                <DropdownItem v-for="m in filteredMembers" :key="m.user" :active="isAssigned(m.user)" @click="toggleAssignee(m)">
                  <span class="jv-av jv-av-sm" :style="{ background: aColor(m.user) }">{{ ini(m.full_name) }}</span>
                  <span class="flex-1 truncate">{{ m.full_name }}</span>
                </DropdownItem>
                <p v-if="!filteredMembers.length" class="jv-dd-empty">No members</p>
              </FieldDropdown>
            </div>
          </div>
        </div>

        <!-- TEAM -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Team</div>
          <div class="jv-sb-val">
            <div class="jv-sb-pill-wrap">
              <FieldDropdown width="w-48">
                <template #trigger>
                  <button class="jv-sb-inline-btn">
                    <div class="jv-sb-inline-btn-content">
                      <template v-if="selectedTeam">
                        <span class="jv-team-dot" :style="{ background: selectedTeam.team_color }"/>
                        <span class="text-[var(--foreground)] tracking-tight">{{ selectedTeam.team_name }}</span>
                      </template>
                      <span v-else class="jv-sb-unset">No team</span>
                    </div>
                    <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                  </button>
                </template>
                <DropdownItem :active="!form.team" @click="form.team = null">No team</DropdownItem>
                <DropdownItem v-for="t in store.teams" :key="t.name" :active="form.team === t.name" @click="form.team = t.name">
                  <span class="jv-team-dot" :style="{ background: t.team_color }"/>{{ t.team_name }}
                </DropdownItem>
                <p v-if="!store.teams.length" class="jv-dd-empty">No teams yet</p>
              </FieldDropdown>
            </div>
          </div>
        </div>

        <!-- PRIORITY -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Priority</div>
          <div class="jv-sb-val">
            <div class="jv-sb-pill-wrap">
              <FieldDropdown width="w-36">
                <template #trigger>
                  <button class="jv-sb-inline-btn">
                    <div class="jv-sb-inline-btn-content">
                      <PriorityIcon :priority="form.priority"/>
                      <span :class="form.priority ? 'text-[var(--foreground)] font-medium' : 'text-[var(--muted)] font-normal'">{{ form.priority || 'None' }}</span>
                    </div>
                    <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                  </button>
                </template>
                <DropdownItem v-for="p in PRIORITIES" :key="p.value" :active="form.priority === p.value" @click="form.priority = p.value">
                  <PriorityIcon :priority="p.value"/><span class="text-foreground">{{ p.label }}</span>
                </DropdownItem>
              </FieldDropdown>
            </div>
          </div>
        </div>

        <!-- ISSUE TYPE -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Task Type</div>
          <div class="jv-sb-val">
            <div class="jv-sb-pill-wrap">
              <FieldDropdown width="w-44">
                <template #trigger>
                  <button class="jv-sb-inline-btn">
                    <div class="jv-sb-inline-btn-content">
                      <span class="jv-type-badge rounded-md w-5 h-5 flex-shrink-0" :style="{ background: taskTypeColor }">{{ form.task_type?.charAt(0) }}</span>
                      <span class="text-[var(--foreground)] tracking-tight">{{ form.task_type || 'Task' }}</span>
                    </div>
                    <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                  </button>
                </template>
                <DropdownItem v-for="t in store.taskTypes" :key="t.name" :active="form.task_type === t.name" @click="form.task_type = t.name">
                  <span class="jv-type-badge" :style="{ background: t.color }">{{ t.name.charAt(0) }}</span>{{ t.name }}
                </DropdownItem>
                <div class="jv-dd-sep"/>
                <template v-if="!showNewType">
                  <div @click.stop="showNewType=true">
                    <DropdownItem>
                      <svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
                      <span style="color:var(--muted)">Create task type</span>
                    </DropdownItem>
                  </div>
                </template>
                <template v-else>
                  <div class="jv-inline-create" @click.stop>
                    <input v-model="newTypeName" class="jv-ic-input" placeholder="Type name" autofocus @keydown.enter.prevent="ciCreateTaskType" @keydown.escape="showNewType=false"/>
                    <div class="jv-ic-colors">
                      <button v-for="c in STATUS_COLORS" :key="c" class="jv-ic-swatch" :class="{ active: newTypeColor===c }" :style="{ background: c }" @click.stop="newTypeColor=c"/>
                    </div>
                    <div class="jv-ic-row">
                      <button class="jv-ic-save" :disabled="!newTypeName.trim()" @click.stop="ciCreateTaskType">Add</button>
                    </div>
                  </div>
                </template>
              </FieldDropdown>
            </div>
          </div>
        </div>

        <!-- SPRINT -->
        <div v-if="store.sprints?.length" class="jv-sb-field">
          <div class="jv-sb-label">Sprint</div>
          <div class="jv-sb-val">
            <div class="jv-sb-pill-wrap">
              <FieldDropdown width="w-44">
                <template #trigger>
                  <button class="jv-sb-inline-btn">
                    <div class="jv-sb-inline-btn-content">
                      <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" class="text-[var(--muted)] flex-shrink-0"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                      <span :class="form.sprint ? 'text-[var(--foreground)]' : 'text-[var(--muted)] font-normal'">{{ form.sprint ? sprintLabel(form.sprint) : 'No sprint' }}</span>
                    </div>
                    <svg class="jv-sb-inline-btn-chevron" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                  </button>
                </template>
                <DropdownItem :active="!form.sprint" @click="form.sprint = null"><span style="color:var(--muted)">No sprint</span></DropdownItem>
                <div class="jv-dd-sep"/>
                <DropdownItem v-for="s in store.activeSprints" :key="s.name" :active="form.sprint === s.name" @click="form.sprint = s.name">{{ s.sprint_name }}</DropdownItem>
              </FieldDropdown>
            </div>
          </div>
        </div>

        <!-- START DATE -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Start date</div>
          <div class="jv-sb-val jv-sb-val--date">
            <DatePicker :modelValue="form.start_date || null" placeholder="None" @update:modelValue="v => form.start_date = v || null"/>
          </div>
        </div>

        <!-- DUE DATE -->
        <div class="jv-sb-field">
          <div class="jv-sb-label">Due date</div>
          <div class="jv-sb-val jv-sb-val--date">
            <DatePicker :modelValue="form.due_date || null" placeholder="None" @update:modelValue="v => form.due_date = v || null"/>
          </div>
        </div>

        <!-- LABELS -->
        <div v-if="store.projectLabels?.length" class="jv-sb-field">
          <div class="jv-sb-label">Labels</div>
          <div class="jv-sb-val">
            <div class="jv-labels-wrap">
              <span v-for="lbl in form.labels" :key="lbl" class="jv-lbl-tag" :style="getLabelStyle(lbl)">
                {{ lbl }}
              </span>
              <FieldDropdown width="w-44" :close-on-select="false">
                <template #trigger>
                  <button class="jv-add-label-btn">
                    <svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
                    {{ form.labels.length ? '' : 'Add label' }}
                  </button>
                </template>
                <DropdownItem v-for="l in store.projectLabels" :key="l.id || l.label" :active="form.labels.includes(l.label)" @click="toggleLabel(l.label)">
                  <span class="jv-lbl-dot" :style="{ background: l.color }"/>{{ l.label }}
                </DropdownItem>
                <div class="jv-dd-sep"/>
                <template v-if="!showNewLabel">
                  <DropdownItem @click="showNewLabel=true">
                    <svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
                    <span style="color:var(--muted)">Create label</span>
                  </DropdownItem>
                </template>
                <template v-else>
                  <div class="jv-inline-create" @click.stop>
                    <input v-model="newLabelName" class="jv-ic-input" placeholder="Label name" autofocus @keydown.enter.prevent="ciCreateLabel" @keydown.escape="showNewLabel=false"/>
                    <div class="jv-ic-colors">
                      <button v-for="c in LABEL_COLORS" :key="c" class="jv-ic-swatch" :class="{ active: newLabelColor===c }" :style="{ background: c }" @click.stop="newLabelColor=c"/>
                    </div>
                    <div class="jv-ic-row">
                      <button class="jv-ic-save" :disabled="!newLabelName.trim()" @click.stop="ciCreateLabel">Add</button>
                    </div>
                  </div>
                </template>
              </FieldDropdown>
            </div>
          </div>
        </div>

        <!-- CUSTOM FIELDS -->
        <template v-if="activeCustomFields.length">
          <div class="jv-sb-divider"/>
          <div v-for="field in activeCustomFields" :key="field.id" class="jv-sb-field">
            <div class="jv-sb-label">{{ field.label }}<span v-if="field.required" style="color:var(--danger);margin-left:2px">*</span></div>
            <div class="jv-sb-val jv-sb-val--cf">
              <CustomFieldInput :field="field" :modelValue="customValues[field.id] ?? null" :members="store.projectMembers || []" :project-name="store.currentProject?.name" :show-label="false" @update:modelValue="val => customValues[field.id] = val"/>
            </div>
          </div>
        </template>

      </aside>
    </div><!-- /jv-body -->

    

    <!-- Footer -->
    <div class="ci-footer">
      <button class="jv-btn-cancel" @click="close">Cancel</button>
      <button class="jv-btn-save" @click="submit" :disabled="!form.title?.trim() || submitting">
        <svg v-if="submitting" class="jv-spin" width="12" height="12" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2.5" opacity=".2"/>
          <path d="M12 3a9 9 0 019 9" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
        </svg>
        Create task
      </button>
    </div>

  </div><!-- /jv-panel -->
</div><!-- /jv-root -->
</Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useProjectStore } from '@/stores/project'
import { getTaskWord } from '@/constants/project-templates'
import { PRIORITIES, PRIORITY_MAP, avatarColor, initials } from '@/utils/constants.js'
import { getActiveFields } from '@/utils/customFields.js'
import FieldDropdown   from '@/components/FieldDropdown.vue'
import DropdownItem    from '@/components/DropdownItem.vue'
import PriorityIcon    from '@/components/PriorityIcon.vue'
import DatePicker      from '@/components/DatePicker.vue'
import RichTextEditor  from '@/components/RichTextEditor.vue'
import CustomFieldInput  from '@/components/CustomFieldInput.vue'
import TaskAttachments  from '@/components/TaskAttachments.vue'
import { Input, Select, SelectItem, Icon } from '@/ui'
import { Lock } from 'lucide-vue-next'
import { createTask, createTaskFromTemplate, updateProjectWorkflow, updateProjectLabels, updateProjectIssueTypes, searchTasks, listTaskTemplates } from '@/utils/api.js'
import { useEntitlementsStore } from '@/stores/entitlements'
import { debounce } from 'lodash'
import { toast } from 'vue-sonner'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit  = defineEmits(['update:modelValue', 'created'])

const store      = useProjectStore()
const ent        = useEntitlementsStore()
const open       = computed(() => props.modelValue)
const titleRef   = ref(null)
const submitting  = ref(false)
const taskWord = computed(() => getTaskWord(store.currentProject?.template_used))

// ── Start from template ──────────────────────────────────────────────────────
const templates = ref([])
const selectedTemplate = ref('')
const templatesUnlocked = computed(() => ent.can('templates'))
const templatesRequiredPlan = computed(() => ent.requiredPlanFor('templates'))

async function loadTemplates() {
  selectedTemplate.value = ''
  try { templates.value = await listTaskTemplates(store.currentProject?.name) }
  catch { templates.value = [] }
}

function applyTemplate(name) {
  const t = templates.value.find(x => x.name === name)
  if (!t) return
  form.value.title       = t.title_template || form.value.title
  form.value.task_type   = t.task_type || form.value.task_type
  form.value.priority    = t.priority || form.value.priority
  form.value.description = t.description || form.value.description
  if (t.labels?.length) form.value.labels = [...t.labels]
}

// ── Form ─────────────────────────────────────────────────────────────────────
const defaultForm = () => ({
  title: '',
  description: '',
  status:     store.workflowStates?.[0]?.name || '',
  priority:   'Medium',
  task_type: store.taskTypes?.[0]?.name || 'Task',
  assignees:  [],
  team:       null,
  sprint:     store.activeSprints?.[0]?.name || null,
  due_date:   null,
  start_date: null,
  labels:     [],
  parent_task: null,
  parent_task_key: null,
  parent_issue_resolved: null,
})
const form         = ref(defaultForm())
const customValues        = ref({})
const pendingAttachments  = ref([])
const queuedFiles         = ref([])

watch(open, async (v) => {
  if (v) {
    form.value = defaultForm()
    customValues.value = {}
    pendingAttachments.value = []
    queuedFiles.value = []
    const defaults = store.createTaskDefaults || {}
    if (defaults.status)     form.value.status     = defaults.status
    if (defaults.priority)   form.value.priority   = defaults.priority
    if (defaults.task_type) form.value.task_type = defaults.task_type
    if (defaults.label)      form.value.labels     = [defaults.label]
    if (defaults.parent_task) {
      form.value.parent_task     = defaults.parent_task
      form.value.parent_task_key = defaults.parent_task_key
    }
    if (defaults.assignee) {
      // find the member by full_name and pre-assign
      const m = (store.projectMembers || []).find(m => m.full_name === defaults.assignee)
      if (m) form.value.assignees = [{ user: m.user, full_name: m.full_name }]
    }
    store.createTaskDefaults = null
    if (!store.teams.length) store.fetchTeams()
    await nextTick()
    titleRef.value?.focus()
    loadTemplates()
  }
})

// ── Computed ─────────────────────────────────────────────────────────────────
const statusColor    = computed(() => store.workflowStateMap?.[form.value.status]?.color || 'var(--muted)')
const taskTypeColor = computed(() => store.taskTypeMap?.[form.value.task_type]?.color || 'var(--accent)')
const selectedTeam   = computed(() => store.teams.find(t => t.name === form.value.team) || null)
const aColor = avatarColor
const ini    = initials

const activeCustomFields = computed(() => getActiveFields(store.currentProject?.custom_fields || []))

const assigneeQ = ref('')
const filteredMembers = computed(() => {
  const q = assigneeQ.value.toLowerCase()
  return (store.projectMembers || []).filter(m => !q || m.full_name?.toLowerCase().includes(q))
})
function isAssigned(user) { return form.value.assignees.some(a => a.user === user) }
function toggleAssignee(m) {
  if (isAssigned(m.user)) form.value.assignees = form.value.assignees.filter(a => a.user !== m.user)
  else form.value.assignees.push({ user: m.user, full_name: m.full_name })
}
function removeAssignee(user) { form.value.assignees = form.value.assignees.filter(a => a.user !== user) }

function sprintLabel(n) { return store.sprints?.find(s => s.name === n)?.sprint_name || n }

function getLabelStyle(lbl) {
  const found = (store.currentProject?.labels || []).find(l => l.label === lbl)
  if (!found) return {}
  return { background: found.color + '18', color: found.color, borderColor: found.color + '40' }
}
function toggleLabel(lbl) {
  const idx = form.value.labels.indexOf(lbl)
  if (idx >= 0) form.value.labels.splice(idx, 1)
  else form.value.labels.push(lbl)
}

// On-spot creation
const showNewStatus     = ref(false)
const newStatusName     = ref('')
const newStatusColor    = ref('#3b82f6')
const newStatusCategory = ref('unstarted')
const showNewLabel      = ref(false)
const newLabelName      = ref('')
const newLabelColor     = ref('#0052CC')
const showNewType       = ref(false)
const newTypeName       = ref('')
const newTypeColor      = ref('#3b82f6')

const STATUS_COLORS = ['#94a3b8','#3b82f6','#f59e0b','#22c55e','#ef4444','#8b5cf6','#ec4899','#06b6d4','#f97316']
const LABEL_COLORS  = ['#0052CC','#00875A','#DE350B','#FF8B00','#6554C0','#00B8D9','#FF5630','#36B37E','#FFAB00']

async function ciCreateStatus() {
  if (!newStatusName.value.trim()) return
  const newState = { name: newStatusName.value.trim(), color: newStatusColor.value, category: newStatusCategory.value }
  const updated  = [...(store.workflowStates || []), newState]
  try {
    await updateProjectWorkflow(store.currentProject.name, updated)
    store.currentProject.workflow_states = updated
    form.value.status = newState.name
    showNewStatus.value = false; newStatusName.value = ''
  } catch { toast.error('Failed to create status') }
}

async function ciCreateTaskType() {
  if (!newTypeName.value.trim()) return
  const newType = { name: newTypeName.value.trim(), color: newTypeColor.value }
  const updated = [...(store.taskTypes || []), newType]
  try {
    await updateProjectIssueTypes(store.currentProject.name, updated)
    store.currentProject.issue_types = updated
    form.value.task_type = newType.name
    showNewType.value = false; newTypeName.value = ''
  } catch { toast.error('Failed to create task type') }
}

async function ciCreateLabel() {
  if (!newLabelName.value.trim()) return
  const newLbl = { id: 'lbl_' + Math.random().toString(36).slice(2, 10), label: newLabelName.value.trim(), color: newLabelColor.value }
  const updated = [...(store.projectLabels || []), newLbl]
  try {
    await updateProjectLabels(store.currentProject.name, updated)
    store.currentProject.labels = updated
    form.value.labels.push(newLbl.label)
    showNewLabel.value = false; newLabelName.value = ''
  } catch { toast.error('Failed to create label') }
}

// Parent issue search
const parentQ           = ref('')
const parentResults     = ref([])
const parentLoading     = ref(false)
const showParentResults = ref(false)
const parentSectionRef  = ref(null)

async function onParentFocus() {
  showParentResults.value = true
  if (!parentResults.value.length) await doParentSearch()
}

const debouncedParentSearch = debounce(doParentSearch, 250)

async function doParentSearch() {
  parentLoading.value = true
  try {
    parentResults.value = await searchTasks(
      parentQ.value || '',
      store.currentProject?.name,
      null
    )
  } catch {} finally {
    parentLoading.value = false
  }
}

function selectParent(r) {
  form.value.parent_task          = r.name
  form.value.parent_task_key      = r.task_key
  form.value.parent_issue_resolved = r.title
  showParentResults.value = false
  parentQ.value = ''
}

function clearParent() {
  form.value.parent_task          = null
  form.value.parent_task_key      = null
  form.value.parent_issue_resolved = null
  parentQ.value = ''
}

function onOutsideParent(e) {
  if (!parentSectionRef.value?.contains(e.target)) showParentResults.value = false
}

function autoResize(e) {
  e.target.style.height = 'auto'
  e.target.style.height = e.target.scrollHeight + 'px'
}

// ── Submit ────────────────────────────────────────────────────────────────────
async function submit() {
  if (!form.value.title?.trim() || submitting.value) return
  submitting.value = true
  try {
    let issue
    if (selectedTemplate.value) {
      // Round-trips through the real backend endpoint so subtask-stamping and
      // the server-side templates-tier gate both apply (was previously a
      // client-side field copy that silently skipped both — see applyTemplate).
      // labels isn't accepted as an override here: task_templates.py always
      // uses the template's own labels, so it isn't passed.
      issue = await createTaskFromTemplate(selectedTemplate.value, {
        title:        form.value.title.trim(),
        description:  form.value.description || '',
        status:       form.value.status,
        priority:     form.value.priority,
        task_type:   form.value.task_type,
        assignees:    form.value.assignees,
        sprint:       form.value.sprint || null,
        due_date:     form.value.due_date || null,
        start_date:   form.value.start_date || null,
      })
    } else {
      issue = await createTask({
        project:      store.currentProject?.name,
        title:        form.value.title.trim(),
        description:  form.value.description || '',
        status:       form.value.status,
        priority:     form.value.priority,
        task_type:   form.value.task_type,
        assignees:    form.value.assignees,
        team:         form.value.team || null,
        sprint:       form.value.sprint || null,
        due_date:     form.value.due_date || null,
        start_date:   form.value.start_date || null,
        labels:       form.value.labels,
        parent_task: form.value.parent_task || null,
        custom_field_values: Object.keys(customValues.value).length ? customValues.value : null,
      })
    }

    // Upload any queued attachments
    if (queuedFiles.value.length) {
      const { uploadAttachment } = await import('@/utils/api.js')
      await Promise.allSettled(
        queuedFiles.value.map(f => uploadAttachment(f, 'BP Task', issue.name))
      )
    }

    await store.refreshBoard()
    emit('created', issue)
    close()
    toast.success(`${taskWord.value} created`, { description: issue.task_key })
  } catch (e) {
    toast.error(e.message || 'Failed to create task')
  } finally {
    submitting.value = false
  }
}

function close() { emit('update:modelValue', false) }

function wfColor(s) { return store.workflowStateMap?.[s]?.color || 'var(--muted)' }

onMounted(() => document.addEventListener('mousedown', onOutsideParent))
onUnmounted(() => document.removeEventListener('mousedown', onOutsideParent))
</script>

<style scoped>
/* Inherit all jv-* base styles inline — exact copy from TaskDetail */
.jv-root {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  font-size:var(--text-md); color: var(--foreground); -webkit-font-smoothing: antialiased;
}
.jv-backdrop {
  position: fixed; inset: 0; z-index: 48;
  background: rgba(9, 30, 66, 0.54);
  animation: jv-bd 0.2s ease;
}
@keyframes jv-bd { from { opacity: 0 } }
.jv-panel {
  position: fixed; top: 0; right: 0; bottom: 0; z-index: 49;
  width: 900px; max-width: 95vw;
  display: flex; flex-direction: column;
  background: var(--surface-secondary);
  border-left: 1px solid var(--border);
  box-shadow: -4px 0 20px rgba(9, 30, 66, 0.25);
  animation: jv-in 0.2s ease;
}
@keyframes jv-in { from { transform: translateX(20px); opacity: 0 } }

/* Header */
.jv-header { display: flex; align-items: center; justify-content: space-between; height: 50px; padding: 0 16px; background: var(--overlay); border-bottom: 1px solid var(--border); flex-shrink: 0; }
.jv-crumb { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
.jv-crumb-project { font-size:var(--text-base); font-weight: 500; color: var(--muted); }
.jv-crumb-sep { color: var(--border); font-size:var(--text-md); }
.jv-crumb-key { font-size:var(--text-base); font-weight: 500; color: var(--foreground); }
.jv-header-actions { display: flex; align-items: center; gap: 4px; }
.jv-hbtn { display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border: none; background: none; cursor: pointer; color: var(--muted); border-radius: 6px; transition: background 0.1s, color 0.1s; }
.jv-hbtn:hover { background: var(--surface-secondary); color: var(--foreground); }
.jv-spin { animation: jv-spin 0.8s linear infinite; }
@keyframes jv-spin { to { transform: rotate(360deg) } }

/* Body */
.jv-body { flex: 1; min-height: 0; display: grid; grid-template-columns: 1fr 280px; overflow: hidden; }

/* Main */
.jv-main { overflow-y: auto; padding: 20px 24px 48px; background: var(--overlay); border-right: 1px solid var(--border); scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
.jv-title-block { margin-bottom: 16px; }
.jv-type-row { display: flex; align-items: center; gap: 7px; margin-bottom: 8px; }
.jv-type-badge { width: 14px; height: 14px; border-radius: 2px; display: inline-flex; align-items: center; justify-content: center; color: var(--accent-foreground); font-size:var(--text-micro); font-weight: 700; flex-shrink: 0; }
.jv-type-label { font-size:var(--text-xs); font-weight: 500; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
.jv-team-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

/* Title as textarea */
.jv-title--input {
  width: 100%; font-size:var(--text-md); font-weight: 600; color: var(--foreground);
  letter-spacing: -0.02em; line-height: 1.35;
  background: var(--surface-secondary); border: none;
  outline: none; resize: none; overflow: hidden;
  font-family: inherit; padding: 8px 12px; margin: 0; border-radius: 6px;
  transition: border-color 0.15s, background 0.15s;
}
.jv-title--input::placeholder { color: var(--muted); font-weight: 400; }
.jv-title--input:focus { background: var(--surface-secondary); }

/* Section */
.jv-section { margin-bottom: 24px; }
.jv-section-title { font-size:var(--text-base); font-weight: 600; color: var(--foreground); margin-bottom: 8px; }
.jv-desc-wrap { min-height: 40px; padding: 10px 12px; border-radius: 6px; background: var(--surface-secondary); cursor: text; transition: background 0.1s; border: none; }
.jv-desc-wrap:hover { background: var(--border); }
.jv-desc-wrap:has(.ql-editor) { background: transparent; cursor: default; padding: 0; }
.jv-desc-placeholder { font-size:var(--text-md); color: var(--muted); }
.jv-desc-preview { font-size:var(--text-md); color: var(--foreground); line-height: 1.6; }
.jv-desc-preview :deep(p) { margin: 0 0 8px; }
.jv-desc-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }

.jv-add-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 0 12px; height: 36px; background: var(--surface-secondary); border-radius: 6px; margin-bottom: 8px; transition: background 0.1s; }
.jv-add-row--link { background: var(--surface-secondary); }
.jv-add-row--link:hover { background: var(--border); }
.jv-add-row--link:focus-within { background: var(--border); }
.jv-add-input { flex: 1; min-width: 160px; font-size:var(--text-base); font-family: inherit; color: var(--foreground); background: transparent; border: none; outline: none; }
.jv-add-input::placeholder { color: var(--muted); }
.jv-parent-resolved { display: flex; align-items: center; gap: 5px; font-size:var(--text-sm); color: var(--success); margin-top: 6px; font-weight: 500; }

/* Sidebar */
.jv-sidebar { background: var(--overlay); overflow-y: auto; padding: 0 0 32px; scrollbar-width: thin; scrollbar-color: var(--border) transparent; display: flex; flex-direction: column; }
.jv-sb-field { padding: 9px 16px; border: none; }
.jv-sb-field--status { padding-top: 12px; }
.jv-sb-label { font-size:var(--text-sm); font-weight: 500; color: var(--foreground); margin-bottom: 6px; }
.jv-sb-val { display: flex; flex-direction: column; }
.jv-sb-val--date { display: flex; width: 100%; }
.jv-sb-pill-wrap { display: block; width: 100%; }
.jv-sb-pill-wrap :deep(.relative) { display: block !important; width: 100% !important; }
.jv-sb-pill-wrap :deep(.relative > div) { display: block !important; width: 100% !important; }
.jv-sb-inline-btn { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; padding: 0 10px; height: 34px; font-size:var(--text-base); font-family: 'Inter', sans-serif; font-weight: 500; color: var(--foreground); background: var(--surface-secondary); border: none; border-radius: 6px; cursor: pointer; text-align: left; transition: background 0.15s; outline: none; }
.jv-sb-inline-btn:hover { background: var(--surface-secondary); }
.jv-sb-inline-btn-content { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.jv-sb-inline-btn-chevron { width: 13px; height: 13px; flex-shrink: 0; opacity: 0.35; color: var(--muted); transition: opacity 0.15s; }
.jv-sb-inline-btn:hover .jv-sb-inline-btn-chevron { opacity: 0.7; }
.jv-sb-unset { color: var(--muted); font-size:var(--text-base); font-weight: 400; }
.jv-status-btn { display: flex; align-items: center; gap: 7px; width: 100%; padding: 7px 11px; min-height: 32px; font-size:var(--text-sm); font-weight: 700; font-family: inherit; border: 1px solid; border-radius: 4px; cursor: pointer; text-transform: uppercase; letter-spacing: 0.05em; transition: opacity 0.1s; }
.jv-status-btn:hover { opacity: 0.9; }
.jv-status-btn svg { margin-left: auto; opacity: 0.6; }
.jv-status-dot { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }
.jv-sb-divider { height: 1px; background: var(--border); margin: 8px 16px; }
.jv-av-stack { display: flex; align-items: center; flex-shrink: 0; }
.jv-av-stacked { border: 1.5px solid var(--surface); margin-left: -5px; }
.jv-av-stacked:first-child { margin-left: 0; }
.jv-av-trigger-label { font-size:var(--text-base); color: var(--foreground); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.jv-av-extra { font-size:var(--text-xs); color: var(--muted); font-weight: 400; margin-left: 2px; }
.jv-av { display: inline-flex; align-items: center; justify-content: center; color: var(--accent-foreground); font-weight: 600; border-radius: 50%; flex-shrink: 0; }
.jv-av-sm { width: 22px; height: 22px; font-size:var(--text-xs); }
.jv-av-empty { width: 18px; height: 18px; border-radius: 50%; border: 2px dashed var(--border); flex-shrink: 0; }
.jv-labels-wrap { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.jv-lbl-tag { display: inline-flex; align-items: center; padding: 2px 8px; border: 1px solid; border-radius: 6px; font-size:var(--text-sm); font-weight: 500; }
.jv-lbl-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.jv-add-label-btn { display: inline-flex; align-items: center; gap: 4px; height: 22px; padding: 0 7px; font-size:var(--text-sm); font-family: inherit; color: var(--muted); background: transparent; border: 1px dashed var(--border); border-radius: 6px; cursor: pointer; transition: background 0.1s; }
.jv-add-label-btn:hover { background: var(--surface-secondary); }
.jv-dd-search { padding: 8px 11px; border-bottom: 1px solid var(--border); }
.jv-dd-input { width: 100%; font-size:var(--text-base); font-family: inherit; color: var(--foreground); background: transparent; border: none; outline: none; }
.jv-dd-input::placeholder { color: var(--muted); }
.jv-dd-sep { height: 1px; background: var(--border); margin: 4px 8px; }
.jv-dd-empty { padding: 8px 12px; font-size:var(--text-base); color: var(--muted); text-align: center; }

/* On-spot creation */
.jv-inline-create { padding: 8px 12px 12px; display: flex; flex-direction: column; gap: 8px; }
.jv-ic-input { width: 100%; height: 32px; padding: 0 10px; font-size:var(--text-base); font-family: inherit; color: var(--foreground); background: transparent; border: 1px solid var(--border); border-radius: 6px; outline: none; transition: border-color 0.1s; }
.jv-ic-input:focus { background: var(--surface); border-color: var(--muted); }
.jv-ic-colors { display: flex; gap: 6px; flex-wrap: wrap; }
.jv-ic-swatch { width: 18px; height: 18px; border-radius: 50%; border: 2px solid transparent; cursor: pointer; transition: transform .1s; }
.jv-ic-swatch:hover { transform: scale(1.15); }
.jv-ic-swatch.active { border-color: var(--foreground); }
.jv-ic-row { display: flex; align-items: center; gap: 6px; }
.jv-ic-select { flex: 1; height: 32px; padding: 0 8px; font-size:var(--text-base); font-family: inherit; background: transparent; border: 1px solid var(--border); border-radius: 6px; outline: none; }
.jv-ic-save { height: 30px; padding: 0 12px; font-size:var(--text-sm); font-weight: 500; font-family: inherit; color: var(--background); background: var(--foreground); border: none; border-radius: 6px; cursor: pointer; transition: opacity 0.1s; }
.jv-ic-save:hover { opacity: 0.85; }
.jv-ic-save:disabled { opacity: .45; cursor: not-allowed; }

/* Footer */
.ci-footer {
  display: flex; align-items: center; justify-content: flex-end; gap: 8px;
  padding: 16px 24px;
  border-top: 1px solid var(--border);
  background: var(--surface-secondary);
  flex-shrink: 0;
}
.jv-btn-save { display: inline-flex; align-items: center; gap: 6px; height: 36px; padding: 0 16px; font-size:var(--text-base); font-weight: 500; font-family: inherit; background: var(--accent); color: var(--accent-foreground); border: none; border-radius: 6px; cursor: pointer; transition: opacity 0.1s; }
.jv-btn-save:hover { opacity: 0.85; background: var(--accent); }
.jv-btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.jv-btn-cancel { display: inline-flex; align-items: center; height: 36px; padding: 0 16px; font-size:var(--text-base); font-weight: 500; font-family: inherit; background: transparent; color: var(--foreground); border: none; border-radius: 6px; cursor: pointer; transition: background 0.1s; }
.jv-btn-cancel:hover { background: var(--surface-secondary); }

/* Parent issue */
.jv-parent-chip { display: flex; align-items: center; gap: 7px; height: 36px; padding: 0 12px; background: var(--surface-secondary); border: none; border-radius: 6px; }
.jv-parent-chip-title { font-size:var(--text-sm); color: var(--foreground); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.jv-parent-results { border: 1px solid var(--border); border-radius: 8px; background: var(--overlay); overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,.08); margin-top: 4px; }
.jv-parent-result { display: flex; align-items: center; gap: 8px; padding: 8px 12px; cursor: pointer; transition: background .08s; }
.jv-parent-result:hover { background: var(--surface-secondary); }
.jv-parent-result-title { flex: 1; font-size:var(--text-base); color: var(--foreground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.jv-parent-empty { padding: 10px 12px; font-size:var(--text-base); color: var(--muted); }
.jv-st-key { font-size:var(--text-sm); font-weight: 500; color: var(--muted); white-space: nowrap; font-family: monospace; }
.jv-st-status { display: inline-flex; align-items: center; padding: 1px 6px; border-radius: 4px; font-size:var(--text-xs); font-weight: 600; white-space: nowrap; flex-shrink: 0; }

</style>