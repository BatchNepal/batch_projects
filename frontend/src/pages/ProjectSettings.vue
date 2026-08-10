<template>
  <div class="h-full flex flex-col font-[Inter] overflow-hidden bg-background">

    <!-- ── Top bar: breadcrumb + save state ─────────────────────────── -->
    <header class="shrink-0 h-12 flex items-center justify-between gap-4 px-6 bg-surface border-b border-separator">
      <nav class="flex items-center gap-1 text-base min-w-0">
        <button type="button"
          class="flex items-center gap-1.5 text-muted hover:text-foreground transition-colors shrink-0 -ml-1.5 px-1.5 py-1 rounded-md hover:bg-[var(--surface-hover)]"
          @click="goBack">
          <Icon :icon="ArrowLeft" class="size-3.5" />
          Back to project
        </button>
        <span class="text-[var(--border-secondary)] px-0.5">/</span>
        <span class="text-muted truncate max-w-[220px]">{{ store.currentProject?.project_name || store.currentProject?.key || 'Project' }}</span>
        <span class="text-[var(--border-secondary)] px-0.5">/</span>
        <span class="text-foreground font-medium">Settings</span>
      </nav>
      <Transition name="fade">
        <span v-if="isSaving" key="saving" class="flex items-center gap-1.5 text-sm text-muted shrink-0">
          <Spinner size="sm" /> Saving…
        </span>
        <span v-else-if="savedFlash" key="saved" class="flex items-center gap-1.5 text-sm text-[var(--success-soft-foreground)] shrink-0">
          <Icon :icon="Check" class="size-3.5" /> Saved
        </span>
      </Transition>
    </header>

    <!-- ── Two-pane: settings nav + content ─────────────────────────── -->
    <div class="flex-1 flex min-h-0 overflow-hidden">

      <!-- Settings nav (desktop) -->
      <aside class="hidden md:flex flex-col w-[228px] shrink-0 bg-surface border-r border-separator overflow-y-auto py-5 px-3">
        <p class="px-3 mb-2 text-xs font-semibold text-muted uppercase tracking-wider">Settings</p>
        <button
          v-for="tab in TABS" :key="tab.id"
          type="button"
          class="set-nav-item"
          :class="activeTab === tab.id ? 'set-nav-item--active' : ''"
          @click="setTab(tab.id)">
          <Icon :icon="tab.icon" :size="15" :stroke-width="1.75" class="shrink-0" />
          <span class="flex-1 text-left">{{ tab.label }}</span>
        </button>
      </aside>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="loading" class="flex items-center justify-center h-48 text-sm text-muted">
          <Spinner size="sm" class="mr-2" /> Loading…
        </div>
        <div v-else class="max-w-[960px] px-6 sm:px-8 lg:px-12 py-9">

          <!-- Settings nav (mobile) -->
          <nav class="md:hidden tabs-scroll flex items-center gap-1 mb-7 overflow-x-auto pb-3 border-b border-separator">
            <button v-for="tab in TABS" :key="tab.id" type="button"
              class="flex items-center gap-1.5 h-8 px-3 rounded-lg text-base font-medium whitespace-nowrap shrink-0 transition-colors"
              :class="activeTab === tab.id ? 'bg-accent-soft text-[var(--accent-soft-foreground)]' : 'text-muted hover:text-foreground'"
              @click="setTab(tab.id)">
              <Icon :icon="tab.icon" :size="13" /> {{ tab.label }}
            </button>
          </nav>


          <!-- ══ GENERAL ══ -->
          <template v-if="activeTab === 'general'">
            <div class="mb-4">
              <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">General</h1>
              <p class="text-base text-muted mt-1">Manage project profile and metadata.</p>
            </div>

            <div class="bp-set-card">

              <!-- Name -->
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                <div class="pt-1">
                  <p class="text-base font-medium text-foreground">Name</p>
                  <p class="text-sm text-muted mt-0.5 leading-relaxed">The display name for this project.</p>
                </div>
                <Input v-model="generalDraft.project_name" size="sm"
                  placeholder="My project" @blur="autoSave" />
              </div>

              <!-- Identifier -->
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                <div class="pt-1">
                  <p class="text-base font-medium text-foreground">Identifier</p>
                  <p class="text-sm text-muted mt-0.5 leading-relaxed">Prefix for {{ taskWord.toLowerCase() }} IDs ({{ generalDraft.key || 'KEY' }}-123).</p>
                </div>
                <div class="max-w-[110px]">
                  <Input v-model="generalDraft.key" size="sm" placeholder="KEY" maxlength="6"
                    class="font-mono uppercase"
                    @input="generalDraft.key = generalDraft.key.toUpperCase()"
                    @blur="autoSave" />
                </div>
              </div>

              <!-- Avatar -->
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                <div class="pt-1">
                  <p class="text-base font-medium text-foreground">Avatar</p>
                  <p class="text-sm text-muted mt-0.5 leading-relaxed">Shown in the sidebar and project cards.</p>
                </div>
                <ThemePicker :theme="generalDraft.theme" @update:theme="generalDraft.theme = $event; autoSave()" />
              </div>

              <!-- Color -->
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                <div class="pt-1">
                  <p class="text-base font-medium text-foreground">Color</p>
                  <p class="text-sm text-muted mt-0.5 leading-relaxed">Accent color in the sidebar and boards.</p>
                </div>
                <div class="flex flex-wrap items-center gap-2 pt-0.5">
                  <button v-for="c in PRESET_COLORS" :key="c" type="button"
                    class="size-6 rounded-md relative transition-transform hover:scale-110 outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-[var(--accent)]"
                    :style="{ background: c }"
                    :title="c"
                    @click="generalDraft.project_color = c; autoSave()">
                    <Icon v-if="generalDraft.project_color === c" :icon="Check"
                      class="size-3.5 text-white absolute inset-0 m-auto drop-shadow" :stroke-width="3" />
                  </button>
                  <label
                    class="size-6 rounded-md border border-dashed border-[var(--border-secondary)] flex items-center justify-center cursor-pointer hover:border-[var(--accent)] hover:text-[var(--accent)] text-muted transition-colors relative overflow-hidden"
                    title="Custom color">
                    <input type="color" v-model="generalDraft.project_color" @change="autoSave()"
                      class="absolute inset-0 opacity-0 cursor-pointer" />
                    <Icon :icon="Plus" class="size-3.5" />
                  </label>
                </div>
              </div>

              <!-- Description -->
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                <div class="pt-1">
                  <p class="text-base font-medium text-foreground">Description</p>
                  <p class="text-sm text-muted mt-0.5 leading-relaxed">A short summary shown in project listings.</p>
                </div>
                <Textarea v-model="generalDraft.description" rows="3"
                  placeholder="What this project is about…" @blur="autoSave" />
              </div>

            </div>

            <!-- Team section -->
            <p class="text-xs font-semibold text-muted uppercase tracking-wider mt-12 mb-3">Team</p>
            <div class="bp-set-card">

              <!-- Lead -->
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-center">
                <div>
                  <p class="text-base font-medium text-foreground">Lead</p>
                  <p class="text-sm text-muted mt-0.5">Primary person responsible for this project.</p>
                </div>
                <Select v-model="generalDraft.lead" size="sm" placeholder="No lead" @update:modelValue="autoSave">
                  <SelectItem value="__none__">No lead</SelectItem>
                  <SelectItem v-for="e in allUsers" :key="e.user" :value="e.user">{{ e.full_name }}</SelectItem>
                </Select>
              </div>

              <!-- Default assignee -->
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-center">
                <div>
                  <p class="text-base font-medium text-foreground">Default assignee</p>
                  <p class="text-sm text-muted mt-0.5">Auto-assigned to new tasks without an owner.</p>
                </div>
                <Select v-model="generalDraft.default_assignee" size="sm" placeholder="Unassigned" @update:modelValue="autoSave">
                  <SelectItem value="__none__">Unassigned</SelectItem>
                  <SelectItem v-for="e in allUsers" :key="e.user" :value="e.user">{{ e.full_name }}</SelectItem>
                </Select>
              </div>

              <!-- Status -->
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-center">
                <div>
                  <p class="text-base font-medium text-foreground">Status</p>
                  <p class="text-sm text-muted mt-0.5">Lifecycle state visible in project listings.</p>
                </div>
                <Select v-model="generalDraft.status" size="sm" @update:modelValue="autoSave">
                  <SelectItem v-for="s in STATUS_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</SelectItem>
                </Select>
              </div>

              <!-- Default view -->
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-center">
                <div>
                  <p class="text-base font-medium text-foreground">Default view</p>
                  <p class="text-sm text-muted mt-0.5">The tab opened when anyone enters this project.</p>
                </div>
                <Select v-model="generalDraft.default_view" size="sm" @update:modelValue="autoSave">
                  <SelectItem v-for="v in defaultViewOptions" :key="v.value" :value="v.value">{{ v.label }}</SelectItem>
                </Select>
              </div>

            </div>

            <!-- Project-level custom fields (task-level fields live in the Custom fields tab) -->
            <template v-if="projectLevelFields.length">
              <p class="text-xs font-semibold text-muted uppercase tracking-wider mt-10 mb-2">Custom fields</p>
              <div class="bp-set-card">
                <div v-for="field in projectLevelFields" :key="field.id"
                  class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                  <div class="pt-1">
                    <p class="text-base font-medium text-foreground">{{ field.label }}</p>
                    <p v-if="field.description" class="text-sm text-muted mt-0.5 leading-relaxed">{{ field.description }}</p>
                  </div>
                  <CustomFieldInput :field="field" :model-value="projectFieldValues[field.id]"
                    :members="allUsers" :project-name="store.currentProject?.name" :disabled="!field.can_edit"
                    @update:modelValue="val => saveProjectFieldValue(field.id, val)" />
                </div>
              </div>
            </template>

            <!-- Save as template -->
            <p class="text-xs font-semibold text-muted uppercase tracking-wider mt-10 mb-2">Template</p>
            <div class="bp-set-card">
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-center">
                <div>
                  <p class="text-base font-medium text-foreground flex items-center gap-2">
                    Save as template
                    <span v-if="!templatesUnlocked"
                      class="inline-flex items-center gap-1 text-xs font-semibold px-1.5 py-0.5 rounded
                             bg-[var(--surface-secondary)] text-muted uppercase tracking-wider">
                      <Icon :icon="Lock" class="size-3" /> {{ templatesRequiredPlan }}
                    </span>
                  </p>
                  <p class="text-sm text-muted mt-0.5">
                    Snapshot this project's shape (states, types, labels, custom fields, tasks,
                    automations) to reuse for the next similar project. Members, client and ERP
                    links never carry over.
                  </p>
                </div>
                <div>
                  <Button size="sm" @click="openSaveAsTemplate">
                    <Icon :icon="FileText" class="size-3.5 mr-1" /> Save as template…
                  </Button>
                </div>
              </div>
            </div>

            <!-- Danger section -->
            <p class="text-xs font-semibold text-muted uppercase tracking-wider mt-10 mb-2">Danger</p>
            <div class="bp-set-card">
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-center">
                <div>
                  <p class="text-base font-medium text-foreground">Archive project</p>
                  <p class="text-sm text-muted mt-0.5">Hides from sidebar. All data is preserved.</p>
                </div>
                <div>
                  <Button color="danger" size="sm" @click="archiveProject">Archive</Button>
                </div>
              </div>
            </div>
          </template>

          <!-- ══ VIEWS ══ -->
          <template v-else-if="activeTab === 'views'">
            <div class="mb-4">
              <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">Views</h1>
              <p class="text-base text-muted mt-1">
                Drag to reorder. The first {{ MAX_INLINE_VIEWS }} show inline in the header; the rest live behind "More views".
              </p>
            </div>

            <div class="bp-set-card">
              <template v-for="(v, i) in viewsDraft" :key="v.key">
                <div
                  class="flex items-center gap-3 py-2.5 -mx-2 px-2 rounded-md transition-colors duration-150"
                  :draggable="i !== 0"
                  @dragstart="viewsDragStart(i)" @dragover.prevent="viewsDragOver(i)"
                  @drop.prevent="viewsDropOn(i)" @dragend="viewsDragEnd"
                  :class="viewsDragState.toIdx === i && viewsDragState.fromIdx !== i
                    ? 'bg-[var(--accent-soft)]'
                    : (viewsDragState.fromIdx === i ? 'opacity-30' : 'hover:bg-[var(--surface-secondary)]')">
                  <Icon :icon="GripVertical" class="size-4 shrink-0" :class="i === 0 ? 'text-transparent' : 'text-[var(--border-secondary)] cursor-grab active:cursor-grabbing'" />
                  <span class="flex items-center justify-center size-7 rounded-md bg-[var(--surface-secondary)] text-muted shrink-0">
                    <Icon :icon="v.icon" class="size-4" />
                  </span>
                  <span class="flex-1 text-base font-medium text-foreground">{{ v.label }}</span>
                  <span v-if="i === 0" class="text-xs text-muted mr-1">Always shown</span>
                  <div class="flex items-center shrink-0">
                    <IconButton size="sm" variant="ghost" :isDisabled="i <= 1" @click="moveView(i, -1)">
                      <Icon :icon="ChevronUp" />
                    </IconButton>
                    <IconButton size="sm" variant="ghost" :isDisabled="i === 0 || i === viewsDraft.length - 1" @click="moveView(i, 1)">
                      <Icon :icon="ChevronDown" />
                    </IconButton>
                  </div>
                </div>
                <div v-if="i === MAX_INLINE_VIEWS - 1 && i < viewsDraft.length - 1" class="flex items-center gap-2 py-1">
                  <div class="flex-1 h-px bg-[var(--separator)]" />
                  <span class="text-xs font-semibold text-muted uppercase tracking-wider shrink-0">Behind "More views"</span>
                  <div class="flex-1 h-px bg-[var(--separator)]" />
                </div>
              </template>
            </div>
          </template>

          <!-- ══ INTAKE ══ -->
          <template v-else-if="activeTab === 'intake'">
            <div class="mb-4 flex items-center gap-2">
              <div>
                <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">Intake Forms</h1>
                <p class="text-base text-muted mt-1">Create public forms that submit tasks to this project.</p>
              </div>
              <span v-if="!intakeFormsUnlocked"
                class="inline-flex items-center gap-1 text-xs font-semibold px-1.5 py-0.5 rounded
                       bg-[var(--surface-secondary)] text-muted uppercase tracking-wider">
                <Icon :icon="Lock" class="size-3" /> {{ intakeFormsRequiredPlan }}
              </span>
            </div>

            <EmptyState v-if="!intakeFormsUnlocked" :icon="Lock" title="Intake forms need a plan upgrade"
              :description="`Available on the ${intakeFormsRequiredPlan} plan and up. Upgrade to let clients submit tasks through a public form.`"
              class="bp-set-card mb-4">
              <template #action>
                <Button size="sm" color="primary" @click="ent.showUpgradePrompt('feature', 'Intake forms are available on any paid plan.')">See plans</Button>
              </template>
            </EmptyState>

            <template v-else>
            <div v-if="intakeForms.length" class="space-y-2 mb-4">
              <div v-for="f in intakeForms" :key="f.name" class="bp-set-card">
                <div class="flex items-center justify-between py-1">
                  <div>
                    <p class="text-base font-medium text-foreground">{{ f.form_title }}</p>
                    <p class="text-xs text-muted mt-0.5">
                      Active · {{ f.task_type || 'Task' }}
                      <span v-if="f.default_status">→ {{ f.default_status }}</span>
                    </p>
                  </div>
                  <div class="flex items-center gap-2">
                    <Button size="sm" variant="ghost" @click="editIntakeForm(f)">Edit fields</Button>
                    <Button size="sm" variant="ghost" @click="copyIntakeLink(f)">
                      <template #prefix><Link class="size-3.5" /></template>
                      Copy link
                    </Button>
                    <Button size="sm" variant="ghost" class="text-danger" @click="confirmDeleteIntakeForm(f)">Delete</Button>
                  </div>
                </div>
              </div>
            </div>

            <EmptyState v-else :icon="FormInput" title="No intake forms yet"
              image="/images/projs/intake-forms.png"
              description="Create a public form below to start collecting task submissions." class="bp-set-card mb-4" />

            <!-- Create form -->
            <div class="bp-set-card">
              <p class="text-base font-medium text-foreground mb-3">New intake form</p>
              <div class="flex items-center gap-2 mb-4">
                <Input v-model="newFormTitle" placeholder="Form title…" size="sm" class="flex-1" />
                <Select v-model="newFormTaskType" size="sm" class="w-28">
                  <SelectItem value="Task">Task</SelectItem>
                  <SelectItem value="Bug">Bug</SelectItem>
                  <SelectItem value="Story">Story</SelectItem>
                  <SelectItem value="Request">Request</SelectItem>
                </Select>
              </div>

              <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Fields</p>
              <div class="space-y-2 mb-3">
                <div v-for="(field, i) in newFormFieldsList" :key="field._id" class="flex flex-col gap-1.5">
                  <div class="flex items-center gap-2">
                    <Input v-model="field.label" size="sm" class="flex-1" placeholder="Field label" />
                    <Select v-model="field.type" size="sm" :fullWidth="false" class="w-32 shrink-0">
                      <SelectItem v-for="t in INTAKE_FIELD_TYPES" :key="t.value" :value="t.value">{{ t.label }}</SelectItem>
                    </Select>
                    <Checkbox :is-selected="field.required" @update:is-selected="v => field.required = v" class="shrink-0">Req.</Checkbox>
                    <div class="flex items-center shrink-0">
                      <IconButton size="sm" variant="light" :isDisabled="i === 0" @click="moveIntakeField(newFormFieldsList, i, -1)">
                        <Icon :icon="ChevronUp" />
                      </IconButton>
                      <IconButton size="sm" variant="light" :isDisabled="i === newFormFieldsList.length - 1" @click="moveIntakeField(newFormFieldsList, i, 1)">
                        <Icon :icon="ChevronDown" />
                      </IconButton>
                    </div>
                    <IconButton size="sm" variant="light" color="danger" :isDisabled="newFormFieldsList.length <= 1" @click="removeIntakeField(newFormFieldsList, i)">
                      <Icon :icon="Trash2" />
                    </IconButton>
                  </div>
                  <Input v-if="field.type === 'select'" v-model="field.optionsText" size="sm" placeholder="Options, comma separated" />
                </div>
              </div>
              <Button size="sm" variant="ghost" @click="addIntakeField(newFormFieldsList)">
                <template #prefix><Plus class="size-3.5" /></template>
                Add field
              </Button>

              <div class="flex justify-end mt-4">
                <Button size="sm" color="primary" :isLoading="creatingForm" :disabled="!newFormTitle.trim()" @click="doCreateIntakeForm">Create form</Button>
              </div>
            </div>

            <!-- Edit form modal -->
            <Modal :open="!!editingForm" @update:open="v => !v && (editingForm = null)" size="md" hideCloseButton>
              <ModalHeader class="px-5 pt-5">
                <p class="text-md font-semibold text-foreground">Edit form fields</p>
              </ModalHeader>
              <ModalBody>
                <div class="space-y-2 mb-3">
                  <div v-for="(field, i) in editingFormFieldsList" :key="field._id" class="flex flex-col gap-1.5">
                    <div class="flex items-center gap-2">
                      <Input v-model="field.label" size="sm" class="flex-1" placeholder="Field label" />
                      <Select v-model="field.type" size="sm" :fullWidth="false" class="w-32 shrink-0">
                        <SelectItem v-for="t in INTAKE_FIELD_TYPES" :key="t.value" :value="t.value">{{ t.label }}</SelectItem>
                      </Select>
                      <Checkbox :is-selected="field.required" @update:is-selected="v => field.required = v" class="shrink-0">Req.</Checkbox>
                      <div class="flex items-center shrink-0">
                        <IconButton size="sm" variant="light" :isDisabled="i === 0" @click="moveIntakeField(editingFormFieldsList, i, -1)">
                          <Icon :icon="ChevronUp" />
                        </IconButton>
                        <IconButton size="sm" variant="light" :isDisabled="i === editingFormFieldsList.length - 1" @click="moveIntakeField(editingFormFieldsList, i, 1)">
                          <Icon :icon="ChevronDown" />
                        </IconButton>
                      </div>
                      <IconButton size="sm" variant="light" color="danger" :isDisabled="editingFormFieldsList.length <= 1" @click="removeIntakeField(editingFormFieldsList, i)">
                        <Icon :icon="Trash2" />
                      </IconButton>
                    </div>
                    <Input v-if="field.type === 'select'" v-model="field.optionsText" size="sm" placeholder="Options, comma separated" />
                  </div>
                </div>
                <Button size="sm" variant="ghost" @click="addIntakeField(editingFormFieldsList)">
                  <template #prefix><Plus class="size-3.5" /></template>
                  Add field
                </Button>
              </ModalBody>
              <ModalFooter>
                <Button size="sm" variant="ghost" @click="editingForm = null">Cancel</Button>
                <Button size="sm" color="primary" :isLoading="savingForm" @click="saveIntakeForm">Save</Button>
              </ModalFooter>
            </Modal>
            </template>
          </template>

          <!-- ══ BILLING ══ -->
          <template v-else-if="activeTab === 'billing'">
            <div class="mb-4">
              <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">Billing</h1>
              <p class="text-base text-muted mt-1">Configure engagement type, rates, and client information.</p>
            </div>

            <div class="bp-set-card">

              <!-- Engagement type -->
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-center">
                <div>
                  <p class="text-base font-medium text-foreground">Engagement type</p>
                  <p class="text-sm text-muted mt-0.5">Controls billing structures and reporting formats.</p>
                </div>
                <Select v-model="generalDraft.project_type" size="sm" @update:modelValue="autoSave">
                  <SelectItem v-for="pt in PROJECT_TYPES" :key="pt.value" :value="pt.value">{{ pt.label }}</SelectItem>
                </Select>
              </div>

              <template v-if="generalDraft.project_type !== 'internal'">

                <!-- Client — BP Project.client is a Link to Customer at the DB
                     layer; this used to render as free text, so a typo (or an
                     honest "Acme Corp" vs the real record "Acme Corp Pvt Ltd")
                     produced a string matching zero actual Customer records.
                     generate_invoice's customer resolution and Money tab
                     rollups key off this field, so a mistyped client silently
                     broke billing rather than erroring — a real typeahead
                     against actual records is the fix, not just a UI nicety. -->
                <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                  <div class="pt-1">
                    <p class="text-base font-medium text-foreground">Client</p>
                    <p class="text-sm text-muted mt-0.5">Shown on invoices and reports.</p>
                  </div>
                  <!-- Explicit :model-value/@update:model-value, not v-model —
                       v-model here PLUS this @update:model-value handler both
                       compile to the same onUpdate:modelValue prop; Vue merges
                       duplicate listeners into an array and fires both, which
                       intermittently left `query` set from the wrong render
                       pass and threw "n.value.trim is not a function" inside
                       Combobox — caught live while exercising this exact field.
                       Matches ErpFieldValueInput's existing convention, which
                       never mixes the two for this reason. -->
                  <Combobox
                    :model-value="generalDraft.client" :model-label="clientLabel"
                    size="sm" :loader="searchClients" :min-chars="1"
                    placeholder="Search customers…"
                    @update:model-value="v => { generalDraft.client = v; autoSave() }"
                    @update:model-label="v => { clientLabel = v }"
                  />
                </div>

                <!-- Currency — was a hand-typed 3-char Data field with no
                     validation against real ISO codes, so "USDD"→"USD" (via
                     maxlength) was fine but "XYZ" saved silently and every
                     downstream fmtMoney() call rendered an Intl.NumberFormat
                     fallback for a currency that doesn't exist. Curated list
                     covers the currencies this app's client base actually
                     bills in; allow-create keeps the field's real type (free
                     Data, not a Link) for anything exotic outside the list. -->
                <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                  <div class="pt-1">
                    <p class="text-base font-medium text-foreground">Currency</p>
                    <p class="text-sm text-muted mt-0.5">Used for all rates, budgets and invoices on this project.</p>
                  </div>
                  <div class="max-w-[220px]">
                    <Combobox
                      :model-value="generalDraft.currency" size="sm"
                      :options="CURRENCY_OPTIONS" allow-create
                      placeholder="Search currencies…"
                      @update:model-value="v => { generalDraft.currency = (v || '').toUpperCase(); autoSave() }"
                    />
                  </div>
                </div>

                <!-- Hourly rate -->
                <div v-if="['tm','retainer'].includes(generalDraft.project_type)"
                  class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                  <div class="pt-1">
                    <p class="text-base font-medium text-foreground">Hourly rate</p>
                    <p class="text-sm text-muted mt-0.5">Per-hour billing rate for tracked time.</p>
                  </div>
                  <div class="max-w-[160px]">
                    <Input v-model.number="generalDraft.hourly_rate" size="sm"
                      type="number" placeholder="0.00" @blur="autoSave" />
                  </div>
                </div>

                <!-- Budget -->
                <div v-if="['fixed','tm'].includes(generalDraft.project_type)"
                  class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                  <div class="pt-1">
                    <p class="text-base font-medium text-foreground">
                      {{ generalDraft.project_type === 'fixed' ? 'Fixed budget' : 'Budget cap' }}
                    </p>
                    <p class="text-sm text-muted mt-0.5">
                      {{ generalDraft.project_type === 'fixed' ? 'Total agreed contract value.' : 'Optional spend ceiling.' }}
                    </p>
                  </div>
                  <div class="max-w-[160px]">
                    <Input v-model.number="generalDraft.budget_amount" size="sm"
                      type="number" placeholder="0.00" @blur="autoSave" />
                  </div>
                </div>

                <!-- Retainer hours -->
                <div v-if="generalDraft.project_type === 'retainer'"
                  class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                  <div class="pt-1">
                    <p class="text-base font-medium text-foreground">Monthly hours</p>
                    <p class="text-sm text-muted mt-0.5">Contracted hours included per billing cycle.</p>
                  </div>
                  <div class="max-w-[100px]">
                    <Input v-model.number="generalDraft.retainer_hours" size="sm"
                      type="number" placeholder="0" @blur="autoSave" />
                  </div>
                </div>

              </template>

              <template v-else>
                <div class="py-4">
                  <p class="text-base text-muted leading-relaxed">
                    Internal projects do not bill to clients. Time tracking and hour logging are available regardless of type.
                  </p>
                </div>
              </template>

            </div>
          </template>

          <!-- ══ MEMBERS ══ -->
          <template v-else-if="activeTab === 'members'">
            <div class="mb-4">
              <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">Members</h1>
              <p class="text-base text-muted mt-1">Grant workspace access to team members.</p>
            </div>

            <div class="bp-set-card">
              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start">
                <div class="pt-1">
                  <p class="text-base font-medium text-foreground">Add member</p>
                  <p class="text-sm text-muted mt-0.5">Invite an org member to this project.</p>
                </div>
                <div class="flex items-end gap-2">
                  <div class="flex-1">
                    <Select v-model="newMember" size="sm" placeholder="Select person…">
                      <SelectItem v-for="e in availableEmployees" :key="e.user" :value="e.user">
                        {{ e.full_name }}
                      </SelectItem>
                    </Select>
                  </div>
                  <div class="w-[120px] shrink-0">
                    <Select v-model="newRole" size="sm">
                      <SelectItem v-for="r in ROLES" :key="r" :value="r">{{ r }}</SelectItem>
                    </Select>
                  </div>
                  <Button color="primary" size="sm" :isDisabled="!newMember" :isLoading="memberSaving"
                    @click="addMember" class="shrink-0">
                    Add
                  </Button>
                </div>
              </div>

              <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-start border-t border-separator">
                <div class="pt-1">
                  <p class="text-base font-medium text-foreground">Invite by email</p>
                  <p class="text-sm text-muted mt-0.5">Send an invitation to anyone — they'll get a link to join.</p>
                </div>
                <div class="flex items-end gap-2">
                  <div class="flex-1">
                    <Input v-model="inviteEmail" size="sm" type="email" placeholder="name@company.com"
                      @keyup.enter="sendInvite" />
                  </div>
                  <div class="w-[120px] shrink-0">
                    <Select v-model="inviteRole" size="sm">
                      <SelectItem v-for="r in ROLES" :key="r" :value="r">{{ r }}</SelectItem>
                    </Select>
                  </div>
                  <Button color="primary" variant="flat" size="sm" :isDisabled="!inviteEmail"
                    :isLoading="inviteSending" @click="sendInvite" class="shrink-0">
                    Invite
                  </Button>
                </div>
              </div>
            </div>

            <!-- Pending invitations -->
            <template v-if="pendingInvitations.length">
              <p class="text-xs font-semibold text-muted uppercase tracking-wider mt-12 mb-3">
                {{ pendingInvitations.length }} pending {{ pendingInvitations.length === 1 ? 'invitation' : 'invitations' }}
              </p>
              <div class="bp-set-card">
                <div v-for="inv in pendingInvitations" :key="inv.name"
                  class="flex items-center justify-between gap-3 py-3 group">
                  <div class="flex items-center gap-3 min-w-0">
                    <span class="size-6 shrink-0 rounded-full bg-default flex items-center justify-center">
                      <Icon :icon="Mail" :size="12" class="text-muted" />
                    </span>
                    <div class="min-w-0">
                      <p class="text-base font-medium text-foreground truncate">{{ inv.email }}</p>
                      <p class="text-xs text-muted">Invited as {{ inv.role }}</p>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 shrink-0">
                    <Chip size="sm" variant="soft" :color="inviteStatusColor(inv.status)">
                      {{ inv.status }}
                    </Chip>
                    <Button variant="light" size="sm" :isLoading="inv._busy"
                      @click="resendInvite(inv)">Resend</Button>
                    <IconButton variant="light" color="danger" size="sm"
                      class="opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                      @click="revokeInvite(inv)">
                      <Icon :icon="X" :size="15" />
                    </IconButton>
                  </div>
                </div>
              </div>
            </template>

            <p class="text-xs font-semibold text-muted uppercase tracking-wider mt-12 mb-3">
              {{ projectMembers.length }} {{ projectMembers.length === 1 ? 'member' : 'members' }}
            </p>

            <div class="bp-set-card">
              <EmptyState v-if="!projectMembers.length" image="/images/projs/bp-team.png"
                title="No members yet"
                description="Add an org member or invite someone by email to start collaborating." />
              <div v-for="m in projectMembers" :key="m.user"
                class="flex items-center justify-between gap-3 py-3 group">
                <div class="flex items-center gap-3 min-w-0">
                  <Avatar :name="m.full_name" :color="avatarColor(m.user)" size="sm" />
                  <div class="min-w-0">
                    <p class="text-base font-medium text-foreground truncate">{{ m.full_name }}</p>
                    <p class="text-xs text-muted truncate">{{ m.user }}</p>
                  </div>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                  <Select :model-value="m.role" size="sm" :fullWidth="false" class="w-[120px]"
                    @update:model-value="v => updateMemberRole(m, v)">
                    <SelectItem v-for="r in ROLES" :key="r" :value="r">{{ r }}</SelectItem>
                  </Select>
                  <IconButton variant="light" color="danger" size="sm"
                    class="opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                    @click="removeMember(m)">
                    <Icon :icon="Trash2" :size="15" />
                  </IconButton>
                </div>
              </div>
            </div>
          </template>

          <!-- ══ WORKFLOW ══ -->
          <template v-else-if="activeTab === 'workflow'">
            <div class="flex items-start justify-between gap-4 mb-5">
              <div>
                <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">Project Workflow</h1>
                <p class="text-base text-muted mt-1">Define board columns and state categories. Drag to reorder.</p>
              </div>
              <div class="flex items-center gap-2 shrink-0">
                <div class="w-44">
                  <Select
                  placeholder="Load template…" size="sm" @update:modelValue="loadWorkflowTemplate">
                    <SelectItem v-for="(tpl, key) in workflowTemplates" :key="key" :value="key">{{ key }}</SelectItem>
                  </Select>
                </div>
                <Button size="sm" color="primary" @click="addWorkflowState">
                  <Icon :icon="Plus" class="mr-1" /> Add status
                </Button>
              </div>
            </div>

            <div v-if="!workflowDraft.length"
              class="flex flex-col items-center justify-center py-16 text-center rounded-md border border-dashed border-[var(--border-secondary)]">
              <span class="size-11 rounded-md bg-[var(--surface-secondary)] flex items-center justify-center mb-3">
                <Icon :icon="GitBranch" class="size-5 text-muted" />
              </span>
              <p class="text-base font-medium text-foreground">No statuses yet</p>
            </div>

            <div v-else class="bp-set-card">
              <div v-for="(s, i) in workflowDraft" :key="s._id ?? i"
                class="flex items-center gap-3 py-2.5 -mx-2 px-2 rounded-md transition-colors duration-150"
                draggable="true"
                @dragstart="dragStart(i)" @dragover.prevent="dragOver(i)"
                @drop.prevent="dropOn(i)" @dragend="dragEnd"
                :class="dragState.toIdx === i && dragState.fromIdx !== i
                  ? 'bg-[var(--accent-soft)]'
                  : (dragState.fromIdx === i ? 'opacity-30' : 'hover:bg-[var(--surface-secondary)]')">
                <Icon :icon="GripVertical" class="size-4 text-[var(--border-secondary)] cursor-grab active:cursor-grabbing shrink-0" />
                <div class="relative size-6 shrink-0 cursor-pointer">
                  <div class="size-6 rounded-md border border-black/10" :style="{ background: s.color }" />
                  <input type="color" :value="s.color" class="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                    @input="e => s.color = e.target.value" @change="saveWorkflow" />
                </div>
                <Input v-model="s.name" size="sm" class="flex-1"
                  placeholder="Status name" @blur="saveWorkflow" />
                <Select v-model="s.category" size="sm" :fullWidth="false" class="w-[140px] shrink-0"
                  @update:model-value="saveWorkflow">
                  <SelectItem v-for="c in STATE_CATEGORIES" :key="c.value" :value="c.value">{{ c.label }}</SelectItem>
                </Select>
                <Dropdown placement="bottom-start" :side-offset="4" :min-width="220">
                  <template #trigger="{ toggle }">
                    <button
                      class="h-[26px] px-2 inline-flex items-center gap-1 rounded-md text-xs font-medium border border-border text-muted hover:text-foreground hover:bg-default transition-colors shrink-0"
                      title="Allowed transitions"
                      @click="toggle"
                    >
                      {{ transitionLabel(s) }}
                      <Icon :icon="ChevronDown" class="size-3" />
                    </button>
                  </template>
                  <DropdownLabel>Can move to</DropdownLabel>
                  <DropdownItem :active="!Array.isArray(s.allowed_to)" @click="clearTransitionRestriction(s)">
                    Any status
                  </DropdownItem>
                  <DropdownSeparator />
                  <DropdownItem
                    v-for="other in workflowDraft.filter(o => o !== s)" :key="other._id ?? other.name"
                    :active="isAllowedTarget(s, other.name)"
                    :close-on-click="false"
                    @click="toggleAllowedTransition(s, other.name)"
                  >
                    {{ other.name || 'Untitled' }}
                    <template v-if="isAllowedTarget(s, other.name)" #endContent>
                      <button
                        class="text-xs font-semibold px-1.5 py-0.5 rounded border border-border text-muted hover:text-foreground hover:border-foreground transition-colors"
                        title="Click to require a minimum role for this move"
                        @click.stop="cycleTransitionRole(s, other.name)"
                      >{{ minRoleFor(s, other.name) || 'Any role' }}</button>
                    </template>
                  </DropdownItem>
                </Dropdown>
                <div class="flex items-center shrink-0">
                  <IconButton size="sm" variant="light" :isDisabled="i === 0" @click="moveState(i, -1)">
                    <Icon :icon="ChevronUp" />
                  </IconButton>
                  <IconButton size="sm" variant="light" :isDisabled="i === workflowDraft.length - 1" @click="moveState(i, 1)">
                    <Icon :icon="ChevronDown" />
                  </IconButton>
                </div>
                <IconButton size="sm" variant="light" color="danger" :isDisabled="workflowDraft.length <= 1" @click="removeState(i)">
                  <Icon :icon="Trash2" />
                </IconButton>
              </div>
            </div>
 <div v-if="workflowDraft.length" class="mt-5 flex items-center gap-2 flex-wrap">
              <span class="text-xs font-semibold text-muted uppercase tracking-wider shrink-0 mr-1">Preview</span>
              <span v-for="s in workflowDraft" :key="s.name"
                class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-sm text-xs font-medium border"
                :style="{ background: s.color + '15', color: s.color, borderColor: s.color + '25' }">
                <span class="size-1.5 rounded-full" :style="{ background: s.color }" />
                {{ s.name || 'Untitled' }}
              </span>
            </div>
           
          </template>

          <!-- ══ TASK TYPES ══ -->
          <template v-else-if="activeTab === 'types'">
            <div class="flex items-start justify-between gap-4 mb-5">
              <div>
                <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">Task types</h1>
                <p class="text-base text-muted mt-1">Categorize work items by kind. Drag to reorder.</p>
              </div>
              <Button size="sm" color="primary" class="shrink-0" @click="addIssueType">
                <Icon :icon="Plus" class="mr-1" /> Add type
              </Button>
            </div>

            <div v-if="!typesDraft.length"
              class="flex flex-col items-center justify-center py-16 text-center rounded-md border border-dashed border-[var(--border-secondary)]">
              <span class="size-11 rounded-md bg-[var(--surface-secondary)] flex items-center justify-center mb-3">
                <Icon :icon="Layers" class="size-5 text-muted" />
              </span>
              <p class="text-base font-medium text-foreground">No types defined yet</p>
            </div>

            <div v-else class="bp-set-card">
              <div v-for="(t, i) in typesDraft" :key="t._id ?? i"
                class="flex items-center gap-3 py-2.5 -mx-2 px-2 rounded-md hover:bg-[var(--surface-secondary)] transition-colors duration-150">
                <div class="relative size-6 shrink-0 cursor-pointer">
                  <div class="size-6 rounded-md border border-black/10" :style="{ background: t.color }" />
                  <input type="color" :value="t.color" class="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                    @input="e => t.color = e.target.value" @change="saveTypes" />
                </div>
                <Input v-model="t.name" size="sm" class="flex-1"
                  placeholder="Type name" @blur="saveTypes" />
                <div class="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border shrink-0"
                  :style="{ background: t.color + '15', color: t.color, borderColor: t.color + '25' }">
                  <span class="size-3.5 rounded-sm flex items-center justify-center text-white text-micro font-bold"
                    :style="{ background: t.color }">
                    {{ t.name?.charAt(0)?.toUpperCase() || '?' }}
                  </span>
                  {{ t.name || 'Type' }}
                </div>
                <div class="flex items-center shrink-0">
                  <IconButton size="sm" variant="light" :isDisabled="i === 0" @click="moveType(i, -1)">
                    <Icon :icon="ChevronUp" />
                  </IconButton>
                  <IconButton size="sm" variant="light" :isDisabled="i === typesDraft.length - 1" @click="moveType(i, 1)">
                    <Icon :icon="ChevronDown" />
                  </IconButton>
                </div>
                <IconButton size="sm" variant="light" color="danger" :isDisabled="typesDraft.length <= 1" @click="removeType(i)">
                  <Icon :icon="Trash2" />
                </IconButton>
              </div>
            </div>
          </template>

          <!-- ══ LABELS ══ -->
          <!-- ══ EPICS ══ -->
          <template v-else-if="activeTab === 'epics'">
            <div class="flex items-start justify-between gap-4 mb-5">
              <div>
                <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">Epics</h1>
                <p class="text-base text-muted mt-1">Group related tasks under a larger initiative.</p>
              </div>
              <Button size="sm" color="primary" class="shrink-0" @click="addEpic">
                <Icon :icon="Plus" class="mr-1" /> Add epic
              </Button>
            </div>
            <EmptyState v-if="!epics.length" title="No epics yet"
                        image="/images/projs/epics.png"
                        description="Create an epic below to start organizing your tasks." class="bp-set-card mb-4" />

            <div v-else class="bp-set-card">
              <div v-for="ep in epics" :key="ep.name"
                class="flex items-center gap-3 py-2.5 -mx-2 px-2 rounded-md hover:bg-[var(--surface-secondary)] transition-colors duration-150">
                <div class="relative size-6 shrink-0 cursor-pointer">
                  <div class="size-6 rounded-md border border-black/10" :style="{ background: ep.color || 'var(--muted)' }" />
                  <input type="color" :value="ep.color || '#8993A4'" class="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                    @change="e => saveEpicField(ep, 'color', e.target.value)" />
                </div>
                <Input v-model="ep.title" size="sm" class="flex-1"
                  placeholder="Epic title" @blur="saveEpicField(ep, 'title', ep.title)" />
                <span class="text-sm text-muted shrink-0 tabular-nums">{{ ep.done_issues }}/{{ ep.total_issues }}</span>
                <IconButton size="sm" variant="light" color="danger" class="shrink-0" @click="askRemoveEpic(ep)">
                  <Icon :icon="Trash2" />
                </IconButton>
              </div>
            </div>
          </template>

          <template v-else-if="activeTab === 'labels'">
            <div class="flex items-start justify-between gap-4 mb-5">
              <div>
                <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">Labels</h1>
                <p class="text-base text-muted mt-1">Tag tasks with quick classification markers.</p>
              </div>
              <Button size="sm" color="primary" class="shrink-0" @click="addLabel">
                <Icon :icon="Plus" class="mr-1" /> Add label
              </Button>
            </div>

            <div v-if="!labelsDraft.length"
              class="flex flex-col items-center justify-center py-16 text-center rounded-md border border-dashed border-[var(--border-secondary)]">
              <span class="size-11 rounded-md bg-[var(--surface-secondary)] flex items-center justify-center mb-3">
                <Icon :icon="Tag" class="size-5 text-muted" />
              </span>
              <p class="text-base font-medium text-foreground">No labels yet</p>
            </div>

            <div v-else class="bp-set-card">
              <div v-for="(lbl, i) in labelsDraft" :key="lbl.id"
                class="flex items-center gap-3 py-2.5 -mx-2 px-2 rounded-md hover:bg-[var(--surface-secondary)] transition-colors duration-150">
                <div class="relative size-6 shrink-0 cursor-pointer">
                  <div class="size-6 rounded-md border border-black/10" :style="{ background: lbl.color }" />
                  <input type="color" :value="lbl.color" class="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
                    @input="e => lbl.color = e.target.value" @change="saveLabels" />
                </div>
                <Input v-model="lbl.label" size="sm" class="flex-1"
                  placeholder="Label name" @blur="saveLabels" />
                <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border shrink-0"
                  :style="{ background: lbl.color + '15', color: lbl.color, borderColor: lbl.color + '25' }">
                  <span class="size-1.5 rounded-full" :style="{ background: lbl.color }" />
                  {{ lbl.label || 'Preview' }}
                </span>
                <IconButton size="sm" variant="light" color="danger" class="shrink-0" @click="removeLabel(i)">
                  <Icon :icon="Trash2" />
                </IconButton>
              </div>
            </div>
          </template>

          <!-- ══ CUSTOM FIELDS ══ -->
          <template v-else-if="activeTab === 'fields'">
            <div class="flex items-start justify-between mb-5">
              <div>
                <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em]">Custom fields</h1>
                <p class="text-base text-muted mt-1">
                  Fields private to this project, or attached from the
                  <RouterLink to="/workspace/settings/customFields" class="text-primary hover:underline">
                    workspace library
                  </RouterLink>.
                </p>
              </div>
              <div class="flex items-center gap-2 shrink-0">
                <Button size="sm" variant="bordered" @click="openNewProjectField">
                  <Icon :icon="Plus" class="size-3.5 mr-1" /> New field
                </Button>
                <div class="relative">
                  <Button size="sm" color="primary" @click="openFieldPicker">
                    <Icon :icon="Plus" class="size-3.5 mr-1" /> Attach field
                  </Button>
                  <div v-if="fieldPickerOpen" class="fixed inset-0 z-40" @click="fieldPickerOpen = false" />
                  <Transition name="pop">
                    <div v-if="fieldPickerOpen"
                      class="absolute right-0 top-10 z-50 w-[300px] bg-overlay rounded-lg shadow-overlay p-2 max-h-[360px] overflow-y-auto">
                      <p v-if="!attachableFields.length" class="px-2 py-3 text-sm text-muted italic">
                        No library fields yet — create one in Workspace Settings.
                      </p>
                      <button v-for="ft in attachableFields" :key="ft.name" type="button"
                        class="w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md hover:bg-[var(--surface-secondary)] transition-colors text-left"
                        @click="attachField(ft.name)">
                        <span class="size-7 rounded-md flex items-center justify-center shrink-0"
                          :style="{ background: `color-mix(in oklab, ${fieldMeta(ft.field_type)?.color || 'var(--muted)'} 12%, transparent)`, color: fieldMeta(ft.field_type)?.color || 'var(--muted)' }">
                          <component :is="cfIcon(ft.field_type)" class="size-4" :stroke-width="1.8" />
                        </span>
                        <span class="min-w-0">
                          <span class="block text-base font-medium text-foreground truncate">{{ ft.field_label }}</span>
                          <span class="block text-sm text-muted truncate">{{ fieldMeta(ft.field_type)?.label }} · {{ ft.applies_to }}</span>
                        </span>
                      </button>
                    </div>
                  </Transition>
                </div>
              </div>
            </div>

            <!-- Empty -->
            <div v-if="!projectFields.length"
              class="flex flex-col items-center justify-center py-16 text-center rounded-md border border-dashed border-[var(--border-secondary)]">
              <span class="size-11 rounded-md bg-[var(--surface-secondary)] flex items-center justify-center mb-3">
                <Icon :icon="SlidersHorizontal" class="size-5 text-muted" />
              </span>
              <p class="text-base font-medium text-foreground">No fields yet</p>
              <p class="text-sm text-muted mt-1 max-w-[260px] leading-relaxed">Create a field private to this project, or attach one from the workspace library.</p>
            </div>

            <!-- Fields (private + attached-shared) -->
            <div v-else class="bp-set-card">
              <div v-for="field in projectFields" :key="field.id"
                class="py-3 -mx-2 px-2 rounded-md transition-colors hover:bg-[var(--surface-secondary)]">
                <div class="flex items-center gap-3">
                  <span class="size-8 rounded-md flex items-center justify-center shrink-0"
                    :style="{ background: `color-mix(in oklab, ${fieldMeta(field.type)?.color || 'var(--muted)'} 12%, transparent)`, color: fieldMeta(field.type)?.color || 'var(--muted)' }">
                    <component :is="cfIcon(field.type)" class="size-4" :stroke-width="1.8" />
                  </span>
                  <div class="flex-1 min-w-0">
                    <p class="text-base font-semibold text-foreground truncate">{{ field.label }}</p>
                    <p class="text-sm text-muted truncate">{{ field.description || '—' }}</p>
                  </div>
                  <span v-if="!field.is_shared" class="inline-flex items-center px-2 py-0.5 bg-accent-soft rounded text-xs font-semibold text-[var(--accent-soft-foreground)] uppercase tracking-wider shrink-0">
                    Private
                  </span>
                  <span class="inline-flex items-center px-2 py-0.5 bg-[var(--surface-secondary)] rounded text-xs font-semibold text-muted uppercase tracking-wider shrink-0">
                    {{ fieldMeta(field.type)?.label || field.type }}
                  </span>
                  <label class="flex items-center gap-1.5 shrink-0 cursor-pointer">
                    <span class="text-sm text-muted">Required</span>
                    <Switch :isSelected="field.required"
                      @update:isSelected="val => setFieldRequired(field, val)" />
                  </label>
                  <template v-if="field.is_shared">
                    <IconButton size="sm" variant="light" color="danger" @click="askDetachField(field)">
                      <Icon :icon="Trash2" />
                    </IconButton>
                  </template>
                  <template v-else>
                    <IconButton size="sm" variant="light" @click="openEditProjectField(field)">
                      <Icon :icon="Pencil" />
                    </IconButton>
                    <IconButton size="sm" variant="light" color="danger" @click="askDeleteProjectField(field)">
                      <Icon :icon="Trash2" />
                    </IconButton>
                  </template>
                </div>
              </div>
            </div>
          </template>

          <!-- ── Automations (premium) ──────────────────────────────────── -->
          <template v-else-if="activeTab === 'automations'">
            <AutomationRules :project="store.currentProject?.name" />
          </template>

          <!-- ══ TASK TEMPLATES ══ -->
          <template v-else-if="activeTab === 'templates'">
            <div class="mb-4">
              <h1 class="text-xl font-semibold text-foreground tracking-[-0.01em] flex items-center gap-2">
                Task templates
                <span v-if="!templatesUnlocked"
                  class="inline-flex items-center gap-1 text-xs font-semibold px-1.5 py-0.5 rounded
                         bg-[var(--surface-secondary)] text-muted uppercase tracking-wider">
                  <Icon :icon="Lock" class="size-3" /> {{ templatesRequiredPlan }}
                </span>
              </h1>
              <p class="text-base text-muted mt-1">
                Reusable task blueprints. Save one from a task's context menu, then start new tasks from it.
              </p>
            </div>

            <div v-if="!taskTemplates.length"
              class="flex flex-col items-center justify-center py-16 text-center rounded-md border border-dashed border-[var(--border-secondary)]">
              <span class="size-11 rounded-md bg-[var(--surface-secondary)] flex items-center justify-center mb-3">
                <Icon :icon="FileText" class="size-5 text-muted" />
              </span>
              <p class="text-base font-medium text-foreground">No templates yet</p>
              <p class="text-sm text-muted mt-1 max-w-sm">
                Right-click any task and choose "Save as template…" to see it here.
              </p>
            </div>

            <div v-else class="divide-y divide-[var(--border-secondary)] rounded-md border border-border overflow-hidden">
              <div v-for="t in taskTemplates" :key="t.name" class="flex items-center gap-3 px-4 py-3 bg-overlay">
                <span class="size-8 rounded-md bg-[var(--surface-secondary)] flex items-center justify-center shrink-0">
                  <Icon :icon="FileText" class="size-4 text-foreground" />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="text-base font-medium text-foreground truncate">{{ t.template_name }}</p>
                  <p class="text-sm text-muted truncate">
                    {{ t.task_type || 'Task' }}<span v-if="t.items?.length"> · {{ t.items.length }} subtask{{ t.items.length === 1 ? '' : 's' }}</span>
                  </p>
                </div>
                <IconButton size="sm" variant="light" @click="renameTemplate(t)" aria-label="Rename">
                  <Icon :icon="Pencil" class="size-3.5" />
                </IconButton>
                <IconButton size="sm" variant="light" @click="askRemoveTemplate(t)" aria-label="Delete">
                  <Icon :icon="Trash2" class="size-3.5 text-muted" />
                </IconButton>
              </div>
            </div>
          </template>

        </div>
      </div>
    </div>

    <CustomFieldEditorDrawer :open="projectFieldDrawerOpen" :field="editingProjectField"
      :owner-project="store.currentProject?.name"
      @update:open="projectFieldDrawerOpen = $event"
      @saved="onProjectFieldSaved" @deleted="onProjectFieldDeleted" />

    <!-- Save as template drawer -->
    <Drawer :open="saveTplOpen" @update:open="saveTplOpen = $event" size="md" placement="right">
      <DrawerHeader @close="saveTplOpen = false">
        <span class="text-md font-semibold text-foreground">Save as template</span>
      </DrawerHeader>
      <DrawerBody>
        <div class="flex flex-col gap-4">
          <Input v-model="saveTplForm.template_name" label="Template name" placeholder="e.g. Client onboarding" />
          <Input v-model="saveTplForm.category" label="Category" placeholder="e.g. Services" />
          <Textarea v-model="saveTplForm.description" label="Description" rows="2" placeholder="What this template is for…" />
          <div class="flex flex-col gap-2.5 pt-1">
            <label class="flex items-center gap-2 text-base text-foreground">
              <Switch size="sm" v-model="saveTplForm.include_tasks" /> Include tasks (with dates as offsets, subtasks, dependencies)
            </label>
            <label class="flex items-center gap-2 text-base text-foreground">
              <Switch size="sm" v-model="saveTplForm.include_custom_fields" /> Include custom fields
            </label>
            <label class="flex items-center gap-2 text-base text-foreground">
              <Switch size="sm" v-model="saveTplForm.include_automations" /> Include automation rules
            </label>
          </div>
        </div>
      </DrawerBody>
      <DrawerFooter>
        <Button variant="ghost" size="sm" @click="saveTplOpen = false">Cancel</Button>
        <Button color="primary" size="sm" :isDisabled="!saveTplForm.template_name.trim()"
          :isLoading="savingTpl" @click="doSaveAsTemplate">Save template</Button>
      </DrawerFooter>
    </Drawer>

    <!-- Confirm Dialog -->
    <Modal :open="confirmModal.show" @update:open="confirmModal.show = $event">
      <ModalHeader>{{ confirmModal.title }}</ModalHeader>
      <ModalBody>
        <p class="text-sm text-muted leading-relaxed">{{ confirmModal.message }}</p>
      </ModalBody>
      <ModalFooter>
        <Button size="sm" @click="confirmModal.show = false">Cancel</Button>
        <Button :color="confirmModal.confirmColor || 'danger'" size="sm" :isLoading="confirmModal.loading"
          @click="confirmModal.onConfirm">
          {{ confirmModal.confirmText || 'Confirm' }}
        </Button>
      </ModalFooter>
    </Modal>

    <!-- Toast -->
    <Transition name="toast">
      <div v-if="toast.show"
        class="fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-2.5 px-4 py-2.5 rounded-md text-base font-medium text-white z-50"
        :class="toast.type === 'success' ? 'bg-foreground' : 'bg-danger'"
        style="box-shadow:0 4px 20px rgba(0,0,0,0.18)">
        <Icon v-if="toast.type === 'success'" :icon="Check" class="size-4" />
        <Icon v-else :icon="TriangleAlert" class="size-4" />
        {{ toast.message }}
      </div>
    </Transition>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { debounce } from 'lodash'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { avatarColor, initials } from '@/utils/constants.js'
import {
  updateProjectWorkflow, updateProjectIssueTypes,
  updateProjectLabels,
  updateProjectMembers, updateProjectGeneral,
  getMembers, getWorkflowTemplates,
  inviteMember, listInvitations, revokeInvitation, resendInvitation,
  listTaskTemplates, updateTaskTemplate, deleteTaskTemplate,
  getEpics, createEpic, updateEpic, deleteEpic,
  getProjectFields, listAttachableFields, attachFieldToProject, detachFieldFromProject,
  updateProjectCustomFieldValues, deleteLibraryField,
  saveProjectAsTemplate,
  listIntakeForms, createIntakeForm, updateIntakeForm, deleteIntakeForm, getIntakeFormDetail,
} from '@/utils/api.js'
import { fieldMeta } from '@/utils/customFields.js'
import { searchErpDocuments, getErpDocumentLabel } from '@/utils/api'
import ThemePicker from '@/components/create-project/ThemePicker.vue'
import CustomFieldInput from '@/components/CustomFieldInput.vue'
import CustomFieldEditorDrawer from '@/components/CustomFieldEditorDrawer.vue'

import {
  Button, Input, Select, SelectItem, Textarea, Switch, Checkbox, Avatar, Icon, IconButton,
  Modal, ModalHeader, ModalBody, ModalFooter, Spinner, Chip, EmptyState, Combobox,
  Drawer, DrawerHeader, DrawerBody, DrawerFooter,
  Dropdown, DropdownItem, DropdownSeparator, DropdownLabel,
} from '@/ui'

import {
  Settings2, Users, GitBranch, Layers, Tag, SlidersHorizontal, CreditCard,
  ChevronRight, ChevronDown, ChevronUp,
  X, Plus, Trash2, GripVertical, Pencil, Lock, FileText,
  Check, TriangleAlert, ArrowLeft,
  Type, Hash, Calendar, ChevronDownSquare, ListChecks, CheckSquare,
  Link2 as LinkIcon, Link, UserCircle2, AlignLeft,
  Banknote, Percent, Star, Mail, Phone, Database, Zap,
  LayoutGrid, LayoutDashboard, Kanban, List, ListTodo,
  GanttChart, NotebookText,  Paperclip,
  FormInput, PenTool,
} from 'lucide-vue-next'
import { Boxes } from 'lucide-vue-next'

import AutomationRules from '@/components/AutomationRules.vue'
import { useEntitlementsStore } from '@/stores/entitlements'
import { getTaskWord } from '@/constants/project-templates'
import { confirmDialog, promptDialog } from '@/composables/useConfirmDialog'

// ── Setup ──────────────────────────────────────────────────────────────────────
const route  = useRoute()
const router = useRouter()
const store  = useProjectStore()
const ent    = useEntitlementsStore()
const taskWord = computed(() => getTaskWord(store.currentProject?.template_used))

const activeTab = ref(route.params.tab || 'general')
watch(() => route.params.tab, (tab) => { activeTab.value = tab || 'general' })

function setTab(id) {
  activeTab.value = id
  router.replace({ name: 'ProjectSettings', params: { key: route.params.key, tab: id } })
}

// ── Epics ──────────────────────────────────────────────────────────────────
const epics = ref([])

async function loadEpics() {
  if (!store.currentProject?.name) return
  try { epics.value = await getEpics(store.currentProject.name) }
  catch { epics.value = [] }
}

async function addEpic() {
  try {
    const created = await createEpic(store.currentProject.name, {
      title: 'New epic',
      color: DEFAULT_COLORS[epics.value.length % DEFAULT_COLORS.length],
    })
    epics.value.push({ ...created, total_issues: 0, done_issues: 0, progress: 0 })
  } catch (e) {
    showToast(e.message || 'Failed to create epic', 'error')
  }
}

async function saveEpicField(ep, field, value) {
  if (field === 'title' && !value?.trim()) return
  try {
    await updateEpic(ep.name, { [field]: value })
    ep[field] = value
  } catch (e) {
    showToast(e.message || 'Failed to update epic', 'error')
  }
}

function askRemoveEpic(ep) {
  triggerConfirm({
    title: 'Delete epic',
    message: `Delete "${ep.title}"? Tasks in it won't be deleted, just unassigned from it.`,
    confirmText: 'Delete',
    confirmColor: 'danger',
    action: async () => {
      await deleteEpic(ep.name)
      epics.value = epics.value.filter(x => x.name !== ep.name)
      showToast('Epic deleted')
    },
  })
}

// ── Task templates ──────────────────────────────────────────────────────────
const taskTemplates = ref([])
const templatesUnlocked = computed(() => ent.can('templates'))
const templatesRequiredPlan = computed(() => ent.requiredPlanFor('templates'))
const intakeFormsUnlocked = computed(() => ent.can('intake_forms'))
const intakeFormsRequiredPlan = computed(() => ent.requiredPlanFor('intake_forms'))

async function loadTaskTemplates() {
  if (!store.currentProject?.name) return
  try { taskTemplates.value = await listTaskTemplates(store.currentProject.name) }
  catch { taskTemplates.value = [] }
}

watch([activeTab, () => store.currentProject?.name], ([tab]) => {
  if (tab === 'templates') loadTaskTemplates()
  if (tab === 'epics') loadEpics()
}, { immediate: true })

async function renameTemplate(t) {
  const name = await promptDialog({ title: 'Template name', inputLabel: 'Name', defaultValue: t.template_name })
  if (!name || !name.trim() || name.trim() === t.template_name) return
  try {
    await updateTaskTemplate({ template: t.name, template_name: name.trim() })
    t.template_name = name.trim()
    showToast('Template renamed')
  } catch (e) {
    showToast(e.message || 'Failed to rename template', 'error')
  }
}

function askRemoveTemplate(t) {
  triggerConfirm({
    title: 'Delete template',
    message: `Delete "${t.template_name}"? This can't be undone.`,
    confirmText: 'Delete',
    confirmColor: 'danger',
    action: async () => {
      await deleteTaskTemplate(t.name)
      taskTemplates.value = taskTemplates.value.filter(x => x.name !== t.name)
      showToast('Template deleted')
    },
  })
}

// ── Save project as template ──────────────────────────────────────
const saveTplOpen = ref(false)
const savingTpl   = ref(false)
const saveTplForm = ref({
  template_name: '', category: '', description: '',
  include_tasks: true, include_custom_fields: true, include_automations: true,
})

function openSaveAsTemplate() {
  saveTplForm.value = {
    template_name: store.currentProject?.project_name ? `${store.currentProject.project_name} template` : '',
    category: '', description: '',
    include_tasks: true, include_custom_fields: true, include_automations: true,
  }
  saveTplOpen.value = true
}

async function doSaveAsTemplate() {
  if (!saveTplForm.value.template_name.trim() || savingTpl.value) return
  savingTpl.value = true
  try {
    await saveProjectAsTemplate({
      project: store.currentProject.name,
      template_name: saveTplForm.value.template_name.trim(),
      category: saveTplForm.value.category,
      description: saveTplForm.value.description,
      include_tasks: saveTplForm.value.include_tasks ? 1 : 0,
      include_custom_fields: saveTplForm.value.include_custom_fields ? 1 : 0,
      include_automations: saveTplForm.value.include_automations ? 1 : 0,
    })
    showToast('Saved as template')
    saveTplOpen.value = false
  } catch (e) {
    showToast(e.message || 'Failed to save template', 'error')
  } finally {
    savingTpl.value = false
  }
}

const loading     = ref(true)
const isSaving    = ref(false)
const savedFlash  = ref(false)
let   savedFlashTimer = null

const memberSaving    = ref(false)
const colorPickerOpen = ref(false)

const generalDraft = ref({
  project_name: '', key: '', description: '',
  project_color: 'var(--accent)', project_icon: '', theme: '',
  lead: null, default_assignee: null, status: 'Active',
  project_type: 'internal', client: '', currency: 'USD',
  hourly_rate: null, budget_amount: null, retainer_hours: null,
  default_view: 'summary',
})

// The Combobox needs a human label to show for the currently-set client, but
// BP Project only stores the raw Customer docname — resolved once on load
// (initDrafts) and again whenever a user picks a new one (searchClients'
// results already carry the label, no extra round trip there).
const clientLabel = ref('')

function searchClients(q) {
  return searchErpDocuments('Customer', q, store.currentProject?.name)
    .then(rows => rows.map(r => ({ value: r.name, label: r.label })))
}

// Common billing currencies first (this workspace's real client base spans
// NPR/INR/USD per the erp_link.py billing work), then the rest of ISO 4217's
// actively-circulating codes so the field never feels like a locked list —
// it's still a free Data field underneath (allow-create), this is a curated
// shortcut, not a constraint.
const CURRENCY_OPTIONS = [
  'NPR', 'INR', 'USD', 'EUR', 'GBP', 'AUD', 'CAD', 'SGD', 'AED', 'JPY',
  'CNY', 'CHF', 'HKD', 'NZD', 'THB', 'MYR', 'PKR', 'BDT', 'LKR', 'ZAR',
  'SAR', 'QAR', 'KWD', 'BHD', 'OMR', 'PHP', 'IDR', 'VND', 'KRW', 'BRL',
  'MXN', 'SEK', 'NOK', 'DKK', 'PLN', 'TRY', 'RUB', 'EGP', 'NGN', 'KES',
].map(c => ({ value: c, label: c }))

const newMember     = ref(null)
const newRole       = ref('Member')
const memberSearchQ = ref('')
const allUsers      = ref([])

// Invitations
const inviteEmail        = ref('')
const inviteRole         = ref('Member')
const inviteSending      = ref(false)
const pendingInvitations = ref([])
const workflowTemplates = ref({})

const workflowDraft = ref([])
const typesDraft    = ref([])
const labelsDraft   = ref([])

const dragState = ref({ dragging: false, fromIdx: null, toIdx: null })
const toast     = ref({ show: false, type: 'success', message: '' })
let   toastTimer = null

const confirmModal = ref({
  show: false, title: '', message: '', confirmText: '',
  confirmColor: 'danger', loading: false, onConfirm: () => {},
})

function triggerConfirm({ title, message, confirmText, confirmColor, action }) {
  confirmModal.value = {
    show: true, title, message, confirmText, confirmColor, loading: false,
    onConfirm: async () => {
      confirmModal.value.loading = true
      try {
        await action()
        confirmModal.value.show = false
      } catch (e) {
        showToast(e.message || 'Operation failed', 'error')
      } finally {
        confirmModal.value.loading = false
      }
    }
  }
}

function watchDraft(source, saveFn, delay = 800) {
  const save = debounce(saveFn, delay)
  let armed = false
  watch(source, () => { if (armed) save() })
  return () => { armed = true }
}

const armWorkflow = watchDraft(
  () => workflowDraft.value.map(s => s.name + s.color + s.category).join('|'),
  saveWorkflow,
)
const armTypes = watchDraft(
  () => typesDraft.value.map(t => t.name + t.color).join('|'),
  saveTypes,
)
const armLabels = watchDraft(
  () => labelsDraft.value.map(l => l.label + l.color).join('|'),
  saveLabels,
)

// ── Constants ──────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'general',  label: 'General',      icon: Settings2 },
  { id: 'views',    label: 'Views',        icon: LayoutGrid },
  { id: 'intake',   label: 'Intake',       icon: FormInput },
  { id: 'billing',  label: 'Billing',      icon: CreditCard },
  { id: 'members',  label: 'Members',      icon: Users },
  { id: 'workflow', label: 'Workflow',     icon: GitBranch },
  { id: 'types',    label: 'Task types',   icon: Layers },
  { id: 'epics',    label: 'Epics',        icon: Boxes },
  { id: 'labels',   label: 'Labels',       icon: Tag },
  { id: 'fields',   label: 'Custom fields', icon: SlidersHorizontal },
  { id: 'automations', label: 'Automations', icon: Zap },
  { id: 'templates', label: 'Task templates', icon: FileText },
]

const ROLES = ['Admin', 'Manager', 'Member', 'Viewer']

const PROJECT_TYPES = [
  { value: 'internal', label: 'Internal' },
  { value: 'fixed',    label: 'Fixed price' },
  { value: 'retainer', label: 'Retainer' },
  { value: 'tm',       label: 'T&M' },
]

const STATUS_OPTIONS = [
  { value: 'Active',   label: 'Active'   },
  { value: 'On Hold',  label: 'On Hold'  },
  { value: 'Archived', label: 'Archived' },
]

const PRESET_COLORS = [
  'var(--accent)', '#0ea5e9', '#6366f1', '#8b5cf6', '#ec4899',
  '#10b981', '#f59e0b', '#ef4444', '#f97316', '#14b8a6',
]

const STATE_CATEGORIES = [
  { value: 'unstarted', label: 'Unstarted'   },
  { value: 'started',   label: 'In Progress' },
  { value: 'completed', label: 'Completed'   },
  { value: 'cancelled', label: 'Cancelled'   },
]

const DEFAULT_COLORS = ['var(--muted)','var(--accent)','#36B37E','#FF5630','#FFAB00','#6554C0','#00B8D9','var(--accent-soft-foreground)']

// Field type catalog now lives in utils/customFields.js (fieldMeta, imported
// above) — this file only maps its string icon ids to the lucide components
// it already imports for everything else.
const CF_ICON_MAP = {
  type: Type, 'align-left': AlignLeft, hash: Hash, calendar: Calendar,
  'check-square': CheckSquare, 'chevron-down-square': ChevronDownSquare, 'list-checks': ListChecks,
  banknote: Banknote, percent: Percent, star: Star, mail: Mail, phone: Phone,
  'link-2': LinkIcon, 'user-circle-2': UserCircle2,
}
function cfIcon(type) { return CF_ICON_MAP[fieldMeta(type)?.icon] || Type }
const fieldPickerOpen = ref(false)

// ── onMounted ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  loading.value = true
  try {
    if (store.projects.length === 0) await store.fetchProjects()
    const projKey = route.params.key
    if (projKey && store.currentProject?.key !== projKey) {
      const proj = store.projects.find(p => p.key === projKey)
      if (proj) await store.fetchBoard(proj.name)
    }

    try {
      const key  = route.params.key
      const proj = store.projects.find(p => p.key === key)
      if (proj) {
        const res = await getMembers(proj.name)
        allUsers.value = res.user_list || res.employees || (Array.isArray(res) ? res : [])
        if (res.members) {
          store.currentProject = store.currentProject || {}
          store.currentProject.members = res.members
        }
        await loadInvitations()
      } else {
        const res = await getMembers()
        allUsers.value = Array.isArray(res) ? res : (res.employees || [])
      }
    } catch (e) { console.error('getMembers:', e) }

    try {
      const tpls = await getWorkflowTemplates()
      workflowTemplates.value = tpls.workflow_templates || {}
    } catch (e) { console.error('getWorkflowTemplates:', e) }

    initDrafts()
    loadProjectFields()
    loadIntakeForms()
  } finally {
    loading.value = false
  }
})

// ── Init ───────────────────────────────────────────────────────────────────────
function normalizeStates(raw) {
  const states = typeof raw === 'string' ? JSON.parse(raw) : (raw || [])
  return states.map((s, i) => {
    if (s && typeof s === 'object' && s.name)
      return { ...s, _id: s._id ?? i }
    return { name: String(s), color: DEFAULT_COLORS[i % DEFAULT_COLORS.length], category: 'unstarted', _id: i }
  })
}

function initDrafts() {
  const p = store.currentProject
  if (!p) return
  generalDraft.value = {
    project_name:     p.project_name     || '',
    key:              p.key              || '',
    description:      p.description      || '',
    project_color:    p.project_color    || 'var(--accent)',
    project_icon:     p.project_icon     || '',
    theme:            p.theme            || '',
    lead:             p.lead             || '__none__',
    default_assignee: p.default_assignee || '__none__',
    status:           p.status           || 'Active',
    project_type:     p.project_type     || 'internal',
    client:           p.client           || '',
    currency:         p.currency         || 'USD',
    hourly_rate:      p.hourly_rate      || null,
    budget_amount:    p.budget_amount    || null,
    retainer_hours:   p.retainer_hours   || null,
    default_view:     p.default_view     || 'summary',
  }

  // Resolve the Combobox's display label for whatever client is already set
  // — the draft only carries the raw Customer docname. Cleared first so a
  // stale label from a previously-open project never flashes while this
  // resolves (initDrafts can re-run on project switch).
  clientLabel.value = ''
  if (p.client) {
    // getErpDocumentLabel resolves {name,label,doctype} — NOT a bare string.
    // Assigning the raw response into clientLabel (a String-typed prop)
    // corrupted Combobox's internal `query` ref the moment it read
    // props.modelLabel, throwing "n.value.trim is not a function" on first
    // focus. Caught live while verifying this exact field — extract `.label`.
    getErpDocumentLabel('Customer', p.client)
      .then(res => { if (generalDraft.value.client === p.client) clientLabel.value = res?.label || p.client })
      .catch(() => { clientLabel.value = p.client })
  }

  // Seed the autosave baseline so the first real edit is what triggers a save.
  lastSavedJson = JSON.stringify(generalPayload())

  workflowDraft.value = normalizeStates(p.workflow_states)
  typesDraft.value    = (p.issue_types  || []).map((t, i) => ({ ...t, _id: i }))
  labelsDraft.value   = (p.labels       || []).map(l => ({ ...l }))
  armViews(p)

  nextTick(() => { armWorkflow(); armTypes(); armLabels() })
}

// ── Computed ───────────────────────────────────────────────────────────────────
const projectMembers = computed(() =>
  (store.currentProject?.members || []).map(m => ({
    ...m,
    full_name: allUsers.value.find(e => e.user === m.user)?.full_name || m.user,
  }))
)
const availableEmployees = computed(() => {
  const existing = new Set(projectMembers.value.map(m => m.user))
  const q = memberSearchQ.value.toLowerCase()
  return allUsers.value
    .filter(e => !existing.has(e.user))
    .filter(e => !q || e.full_name?.toLowerCase().includes(q) || e.user.toLowerCase().includes(q))
})
// Default-view picker: Summary + whatever data views the project exposes + Files
const VIEW_LABELS = { summary: 'Summary', board: 'Board', list: 'List', backlog: 'Backlog', gantt: 'Gantt', files: 'Files' }
const VIEW_SEQ = ['summary', 'board', 'list', 'backlog', 'gantt', 'files']
const defaultViewOptions = computed(() => {
  const enabled = store.currentProject?.enabled_views || ['board', 'list', 'backlog', 'gantt']
  const allowed = new Set(['summary', 'files', ...enabled])
  return VIEW_SEQ.filter(v => allowed.has(v)).map(v => ({ value: v, label: VIEW_LABELS[v] }))
})

// ── General — autosave ─────────────────────────────────────────────────────────
const autoSave = debounce(saveGeneral, 600)

// Normalised payload from the current draft (so dirty-checks and saves agree).
function generalPayload() {
  const p = { ...generalDraft.value }
  if (p.lead === '__none__')             p.lead = ''
  if (p.default_assignee === '__none__') p.default_assignee = ''
  return p
}
// JSON of the last persisted state — autosave skips the API when unchanged.
let lastSavedJson = ''

async function saveGeneral() {
  if (!store.currentProject) return
  const payload = generalPayload()
  const json = JSON.stringify(payload)
  if (json === lastSavedJson) return          // nothing actually changed — no-op
  isSaving.value   = true
  savedFlash.value = false
  try {
    const updated = await updateProjectGeneral(store.currentProject.name, payload)
    lastSavedJson = json
    Object.assign(store.currentProject, updated)
    // store.projects (the sidebar's list) is a separate array fetched once at
    // boot, not a reference into currentProject — without this the sidebar
    // avatar/name/color keeps showing whatever it last fetched until a full
    // reload, even though the "open" project reflects the save immediately.
    const listEntry = store.projects.find(p => p.name === store.currentProject.name)
    if (listEntry) Object.assign(listEntry, updated)
    flashSaved()
  } catch (e) {
    showToast(e.message || 'Failed to save', 'error')
  } finally { isSaving.value = false }
}

function flashSaved() {
  if (savedFlashTimer) clearTimeout(savedFlashTimer)
  savedFlash.value  = true
  savedFlashTimer   = setTimeout(() => { savedFlash.value = false }, 2000)
}

function archiveProject() {
  triggerConfirm({
    title: 'Archive project',
    message: 'Are you sure? The project will be hidden from the sidebar but all data is preserved.',
    confirmText: 'Archive',
    confirmColor: 'danger',
    action: async () => {
      generalDraft.value.status = 'Archived'
      await saveGeneral()
    }
  })
}

// ── Members ────────────────────────────────────────────────────────────────────
async function addMember() {
  if (!newMember.value) return
  const usr = allUsers.value.find(e => e.user === newMember.value)
  if (!usr) return
  memberSaving.value = true
  const updated = [...(store.currentProject?.members || []), { user: usr.user, role: newRole.value }]
  try {
    await saveMembersToDoc(updated)
    store.currentProject.members = updated
    newMember.value = null
    newRole.value   = 'Member'
    showToast('Member added')
  } catch (e) { showToast('Failed to add member', 'error') }
  finally { memberSaving.value = false }
}

function removeMember(m) {
  triggerConfirm({
    title: 'Remove member',
    message: `Remove ${m.full_name || m.user} from this project?`,
    confirmText: 'Remove',
    confirmColor: 'danger',
    action: async () => {
      const updated = (store.currentProject?.members || []).filter(x => x.user !== m.user)
      await saveMembersToDoc(updated)
      store.currentProject.members = updated
      showToast('Member removed')
    }
  })
}

async function updateMemberRole(m, role) {
  const updated = (store.currentProject?.members || []).map(x => x.user === m.user ? { ...x, role } : x)
  try {
    await saveMembersToDoc(updated)
    store.currentProject.members = updated
    showToast('Role updated')
  } catch (e) { showToast('Failed to update role', 'error') }
}

async function saveMembersToDoc(members) {
  const result = await updateProjectMembers(
    store.currentProject.name,
    members.map(m => ({ user: m.user, role: m.role }))
  )
  store.currentProject.members = result
}

// ── Invitations ──────────────────────────────────────────────────────────────
async function loadInvitations() {
  if (!store.currentProject?.name) return
  try {
    pendingInvitations.value = await listInvitations(store.currentProject.name)
  } catch (e) { /* manager+ only; ignore for non-managers */ }
}

async function sendInvite() {
  const email = (inviteEmail.value || '').trim()
  if (!email) return
  inviteSending.value = true
  try {
    const res = await inviteMember(store.currentProject.name, email, inviteRole.value)
    inviteEmail.value = ''
    inviteRole.value  = 'Member'
    showToast(res.email_sent ? `Invitation sent to ${res.email}`
                             : `Invitation created (email could not be sent)`,
              res.email_sent ? 'success' : 'error')
    await loadInvitations()
  } catch (e) {
    if (e.upgradeRequired) {
      const ent = useEntitlementsStore()
      ent.showUpgradePrompt('seat_limit', e.message)
    } else {
      showToast(e.message || 'Failed to invite', 'error')
    }
  }
  finally { inviteSending.value = false }
}

async function revokeInvite(inv) {
  triggerConfirm({
    title: 'Revoke invitation',
    message: `Revoke the invitation sent to ${inv.email}?`,
    confirmText: 'Revoke',
    confirmColor: 'danger',
    action: async () => {
      await revokeInvitation(inv.name)
      pendingInvitations.value = pendingInvitations.value.filter(x => x.name !== inv.name)
      showToast('Invitation revoked')
    }
  })
}

async function resendInvite(inv) {
  inv._busy = true
  try {
    await resendInvitation(inv.name)
    showToast(`Invitation resent to ${inv.email}`)
  } catch (e) { showToast(e.message || 'Failed to resend', 'error') }
  finally { inv._busy = false }
}

function inviteStatusColor(status) {
  return ({
    Pending:  'warning',
    Accepted: 'success',
    Revoked:  'danger',
    Expired:  'default',
  })[status] || 'default'
}

// ── Workflow ───────────────────────────────────────────────────────────────────
function dragStart(idx) { dragState.value = { dragging: true, fromIdx: idx, toIdx: idx } }
function dragOver(idx)  { if (dragState.value.dragging) dragState.value.toIdx = idx }
function dragEnd()      { dragState.value = { dragging: false, fromIdx: null, toIdx: null } }
function dropOn(toIdx) {
  const fromIdx = dragState.value.fromIdx
  if (fromIdx === null || fromIdx === toIdx) return dragEnd()
  const arr = [...workflowDraft.value]
  const [item] = arr.splice(fromIdx, 1)
  arr.splice(toIdx, 0, item)
  workflowDraft.value = arr
  dragEnd()
  saveWorkflow()
}

function addWorkflowState() {
  workflowDraft.value.push({
    name: '', color: DEFAULT_COLORS[workflowDraft.value.length % DEFAULT_COLORS.length],
    category: 'unstarted', _id: Date.now(),
  })
}
function removeState(i) {
  if (workflowDraft.value.length <= 1) return
  workflowDraft.value.splice(i, 1)
  saveWorkflow()
}
function moveState(i, dir) {
  const arr = [...workflowDraft.value]
  const j = i + dir
  if (j < 0 || j >= arr.length) return
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
  workflowDraft.value = arr
  saveWorkflow()
}
async function saveWorkflow() {
  if (!store.currentProject) return
  try {
    await updateProjectWorkflow(store.currentProject.name, workflowDraft.value)
    store.currentProject.workflow_states = workflowDraft.value
  } catch (e) { showToast('Failed to save workflow', 'error') }
}

// Restricting a status's outgoing transitions (undefined/absent = unrestricted,
// the default) blocks users from jumping e.g. straight from To Do to Done —
// enforced server-side in BP Project.check_transition. Each entry is either a
// plain status name or {name, min_role} when also role-gated.
function _transitionName(entry) { return (entry && typeof entry === 'object') ? entry.name : entry }
function transitionLabel(s) {
  if (!Array.isArray(s.allowed_to)) return 'Any'
  return s.allowed_to.length ? String(s.allowed_to.length) : 'None'
}
function isAllowedTarget(s, name) {
  return Array.isArray(s.allowed_to) && s.allowed_to.some(e => _transitionName(e) === name)
}
function minRoleFor(s, name) {
  if (!Array.isArray(s.allowed_to)) return null
  const entry = s.allowed_to.find(e => _transitionName(e) === name)
  return (entry && typeof entry === 'object') ? entry.min_role : null
}
function clearTransitionRestriction(s) {
  delete s.allowed_to
  saveWorkflow()
}
function toggleAllowedTransition(s, name) {
  if (!Array.isArray(s.allowed_to)) s.allowed_to = []
  const idx = s.allowed_to.findIndex(e => _transitionName(e) === name)
  if (idx >= 0) s.allowed_to.splice(idx, 1)
  else s.allowed_to.push(name)
  saveWorkflow()
}
const TRANSITION_ROLE_CYCLE = [null, 'Manager', 'Admin']
function cycleTransitionRole(s, name) {
  if (!Array.isArray(s.allowed_to)) return
  const idx = s.allowed_to.findIndex(e => _transitionName(e) === name)
  if (idx < 0) return
  const current = minRoleFor(s, name)
  const next = TRANSITION_ROLE_CYCLE[(TRANSITION_ROLE_CYCLE.indexOf(current) + 1) % TRANSITION_ROLE_CYCLE.length]
  s.allowed_to.splice(idx, 1, next ? { name, min_role: next } : name)
  saveWorkflow()
}

// ── Views (header tab strip order — position, not a separate pin flag: the
// first MAX_INLINE_VIEWS show inline, the rest live behind "More views") ───────
const VIEW_META = {
  summary: { label: 'Summary', icon: LayoutDashboard },
  board:   { label: 'Board',   icon: Kanban },
  list:    { label: 'List',    icon: List },
  backlog: { label: 'Backlog', icon: ListTodo },
  gantt:   { label: 'Gantt',   icon: GanttChart },
  notes:   { label: 'Notes',   icon: NotebookText },
  draw:    { label: 'Draw',    icon: PenTool },
  files:   { label: 'Files',   icon: Paperclip },
  money:   { label: 'Money',   icon: Banknote },
}
const MAX_INLINE_VIEWS = 6
const viewsDraft = ref([]) // [{ key, label, icon }], summary always first

// Unset pinned_views (nothing customized yet) means the header shows every
// view in its natural order, capped at MAX_INLINE_VIEWS inline — matches
// ProjectHeader's own default so this list never shows a state that
// contradicts what's actually on screen.
function armViews(p) {
  const enabled = Array.isArray(p.enabled_views) && p.enabled_views.length ? p.enabled_views : ['board', 'list', 'backlog', 'gantt']
  const avail = ['summary', ...enabled.filter(v => VIEW_META[v])]
  if (store.hasCapability?.('view_files')) avail.push('files')
  if (ent.canWorkspace?.('money_tab') && store.hasCapability?.('view_money')) avail.push('money')

  const explicit = Array.isArray(p.pinned_views) && p.pinned_views.length ? p.pinned_views : null
  const order = explicit ? [...explicit.filter(k => avail.includes(k)), ...avail.filter(k => !explicit.includes(k))] : avail
  viewsDraft.value = order.map(key => ({ key, ...VIEW_META[key] }))
}

const viewsDragState = ref({ dragging: false, fromIdx: null, toIdx: null })
function viewsDragStart(idx) { if (idx === 0) return; viewsDragState.value = { dragging: true, fromIdx: idx, toIdx: idx } }
function viewsDragOver(idx)  { if (viewsDragState.value.dragging && idx !== 0) viewsDragState.value.toIdx = idx }
function viewsDragEnd()      { viewsDragState.value = { dragging: false, fromIdx: null, toIdx: null } }
function viewsDropOn(toIdx) {
  const fromIdx = viewsDragState.value.fromIdx
  if (fromIdx === null || fromIdx === toIdx || toIdx === 0) return viewsDragEnd()
  const arr = [...viewsDraft.value]
  const [item] = arr.splice(fromIdx, 1)
  arr.splice(toIdx, 0, item)
  viewsDraft.value = arr
  viewsDragEnd()
  saveViews()
}
function moveView(i, dir) {
  if (i === 0) return
  const j = i + dir
  if (j < 1 || j >= viewsDraft.value.length) return
  const arr = [...viewsDraft.value]
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
  viewsDraft.value = arr
  saveViews()
}
async function saveViews() {
  if (!store.currentProject) return
  const order = viewsDraft.value.map(v => v.key)
  try {
    await updateProjectGeneral(store.currentProject.name, { pinned_views: order })
    store.currentProject.pinned_views = order
  } catch (e) { showToast('Failed to save views', 'error') }
}
function loadWorkflowTemplate(key) {
  const tpl = workflowTemplates.value[key]
  if (!tpl) return
  workflowDraft.value = (Array.isArray(tpl) ? tpl : tpl.states || []).map((s, i) => ({
    ...s, _id: Date.now() + i,
  }))
  saveWorkflow()
}

// ── Types ──────────────────────────────────────────────────────────────────────
function addIssueType() {
  typesDraft.value.push({
    name: '', color: DEFAULT_COLORS[typesDraft.value.length % DEFAULT_COLORS.length], _id: Date.now(),
  })
}
function removeType(i) {
  if (typesDraft.value.length <= 1) return
  typesDraft.value.splice(i, 1)
  saveTypes()
}
function moveType(i, dir) {
  const arr = [...typesDraft.value]
  const j = i + dir
  if (j < 0 || j >= arr.length) return
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
  typesDraft.value = arr
  saveTypes()
}
async function saveTypes() {
  if (!store.currentProject) return
  isSaving.value = true
  try {
    const result = await updateProjectIssueTypes(store.currentProject.name, typesDraft.value)
    store.currentProject.issue_types = result
  } catch (e) { showToast(e.message || 'Failed to save types', 'error') }
  finally { isSaving.value = false }
}

// ── Intake forms ──────────────────────────────────────────────────────────────
const intakeForms     = ref([])
const newFormTitle    = ref('')

function copyIntakeLink(f) {
  const url = `${window.location.origin}/intake/${f.name}`
  navigator.clipboard.writeText(url).then(() => {
    showToast('Link copied to clipboard')
  }).catch(() => {
    showToast('Failed to copy link', 'error')
  })
}
const newFormTaskType = ref('Task')
const creatingForm    = ref(false)
const editingForm     = ref(null)
const savingForm      = ref(false)

const INTAKE_FIELD_TYPES = [
  { value: 'text',     label: 'Text' },
  { value: 'email',    label: 'Email' },
  { value: 'textarea', label: 'Textarea' },
  { value: 'select',   label: 'Select' },
]
function _blankIntakeField() {
  return { _id: Date.now() + Math.random(), label: '', type: 'text', required: true, optionsText: '' }
}
const newFormFieldsList = ref([_blankIntakeField()])
const editingFormFieldsList = ref([])

function addIntakeField(list) { list.push(_blankIntakeField()) }
function removeIntakeField(list, i) {
  if (list.length <= 1) return
  list.splice(i, 1)
}
function moveIntakeField(list, i, dir) {
  const j = i + dir
  if (j < 0 || j >= list.length) return
  ;[list[i], list[j]] = [list[j], list[i]]
}
// Structured rows -> the {label,type,required,options?} shape IntakeForm.vue
// (the public submission page) actually reads.
function _intakeFieldsPayload(list) {
  return list.filter(f => f.label.trim()).map(f => {
    const out = { label: f.label.trim(), type: f.type, required: !!f.required }
    if (f.type === 'select') {
      out.options = (f.optionsText || '').split(',').map(s => s.trim()).filter(Boolean)
    }
    return out
  })
}

async function loadIntakeForms() {
  if (!store.currentProject?.name || !intakeFormsUnlocked.value) return
  try { intakeForms.value = await listIntakeForms(store.currentProject.name) }
  catch (e) { intakeForms.value = [] }
}

async function doCreateIntakeForm() {
  if (!newFormTitle.value.trim() || !store.currentProject?.name) return
  creatingForm.value = true
  try {
    const fields = _intakeFieldsPayload(newFormFieldsList.value)
    await createIntakeForm(store.currentProject.name, newFormTitle.value.trim(),
      JSON.stringify(fields.length ? fields : [{ label: 'Title', type: 'text', required: true }]),
      newFormTaskType.value, '')
    newFormTitle.value = ''
    newFormFieldsList.value = [_blankIntakeField()]
    await loadIntakeForms()
    showToast('Intake form created')
  } catch (e) { showToast(e.message || 'Failed', 'error') }
  finally { creatingForm.value = false }
}

async function editIntakeForm(f) {
  editingForm.value = f
  editingFormFieldsList.value = [_blankIntakeField()]
  try {
    const detail = await getIntakeFormDetail(f.name)
    const fields = detail.fields || []
    editingFormFieldsList.value = (fields.length ? fields : [{}]).map(field => ({
      _id: Date.now() + Math.random(),
      label: field.label || '',
      type: field.type || 'text',
      required: field.required !== false,
      optionsText: (field.options || []).join(', '),
    }))
  } catch (e) { showToast(e.message || 'Failed to load form', 'error') }
}

async function saveIntakeForm() {
  if (!editingForm.value) return
  savingForm.value = true
  try {
    const fields = _intakeFieldsPayload(editingFormFieldsList.value)
    await updateIntakeForm(editingForm.value.name, { fields_json: JSON.stringify(fields) })
    editingForm.value = null
    await loadIntakeForms()
    showToast('Form updated')
  } catch (e) { showToast(e.message || 'Failed to save', 'error') }
  finally { savingForm.value = false }
}

async function confirmDeleteIntakeForm(f) {
  if (!await confirmDialog(`Delete "${f.form_title}"?`, { danger: true })) return
  try {
    await deleteIntakeForm(f.name)
    intakeForms.value = intakeForms.value.filter(x => x.name !== f.name)
    showToast('Form deleted')
  } catch (e) { showToast(e.message || 'Failed', 'error') }
}

// ── Labels ─────────────────────────────────────────────────────────────────────
function addLabel() {
  labelsDraft.value.push({
    id: 'lbl_' + Date.now(), label: '', color: DEFAULT_COLORS[labelsDraft.value.length % DEFAULT_COLORS.length],
  })
}
function removeLabel(i) {
  labelsDraft.value.splice(i, 1)
  saveLabels()
}
async function saveLabels() {
  if (!store.currentProject) return
  isSaving.value = true
  try {
    const result = await updateProjectLabels(store.currentProject.name, labelsDraft.value)
    store.currentProject.labels = result
  } catch (e) { showToast(e.message || 'Failed to save labels', 'error') }
  finally { isSaving.value = false }
}

// ── Custom Fields (attach-from-library, Phase: workspace field library) ────────
const projectFields    = ref([])   // this project's attached fields, task-scoped
const attachableFields  = ref([])  // enabled library fields not yet filtered by attachment

async function loadProjectFields() {
  if (!store.currentProject?.name) return
  try { projectFields.value = await getProjectFields(store.currentProject.name, 'tasks') }
  catch { projectFields.value = [] }
}

// Project-level fields (applies_to Projects/Both) ship straight in the board
// payload (store.currentProject.project_custom_fields / .custom_field_values)
// — no separate load call needed, same as how task-scoped fields used to.
const projectLevelFields = computed(() => store.currentProject?.project_custom_fields || [])
const projectFieldValues = computed(() => store.currentProject?.custom_field_values || {})

async function saveProjectFieldValue(fieldId, value) {
  if (!store.currentProject) return
  try {
    const result = await updateProjectCustomFieldValues(store.currentProject.name, { [fieldId]: value })
    store.currentProject.custom_field_values = result
  } catch (e) {
    showToast(e.message || 'Failed to save field', 'error')
  }
}

async function openFieldPicker() {
  fieldPickerOpen.value = !fieldPickerOpen.value
  if (!fieldPickerOpen.value) return
  try {
    const all = await listAttachableFields()
    const attached = new Set(projectFields.value.map(f => f.id))
    attachableFields.value = all.filter(f => !attached.has(f.name))
  } catch { attachableFields.value = [] }
}

async function attachField(fieldName) {
  if (!store.currentProject) return
  fieldPickerOpen.value = false
  try {
    await attachFieldToProject(store.currentProject.name, fieldName, 0)
    await loadProjectFields()
    showToast('Field attached')
  } catch (e) { showToast(e.message || 'Failed to attach field', 'error') }
}

async function setFieldRequired(field, required) {
  if (!store.currentProject) return
  field.required = required // optimistic
  try {
    await attachFieldToProject(store.currentProject.name, field.id, required ? 1 : 0)
  } catch (e) {
    field.required = !required
    showToast(e.message || 'Failed to update field', 'error')
  }
}

function askDetachField(field) {
  triggerConfirm({
    title: 'Detach field',
    message: `Detach "${field.label}" from this project? Its values on existing tasks are kept, and you can re-attach it later.`,
    confirmText: 'Detach',
    confirmColor: 'danger',
    action: async () => {
      await detachFieldFromProject(store.currentProject.name, field.id)
      projectFields.value = projectFields.value.filter(f => f.id !== field.id)
      showToast('Field detached')
    },
  })
}

// ── Custom Fields (project-owned/private, Custom Fields v3) ────────────────
const projectFieldDrawerOpen = ref(false)
const editingProjectField    = ref(null) // library-dict-shaped row, or null for "New field"

function openNewProjectField() {
  editingProjectField.value = null
  projectFieldDrawerOpen.value = true
}
function openEditProjectField(field) {
  // CustomFieldEditorDrawer expects the library-dict shape (field_label/
  // field_type/options/...), while projectFields rows are in the older
  // _schema_dict shape (label/type/...) — map the handful of keys it needs.
  editingProjectField.value = {
    name: field.id,
    field_label: field.label,
    description: field.description,
    field_type: field.type,
    options: field.options,
    applies_to: field.applies_to || 'Tasks',
    view_role: field.view_role,
    edit_role: field.edit_role,
    show_in_list: field.show_in_list,
    enabled: !field.archived,
    conditional_rules: field.conditional_rules,
  }
  projectFieldDrawerOpen.value = true
}
function onProjectFieldSaved() {
  loadProjectFields()
}
function onProjectFieldDeleted(name) {
  projectFields.value = projectFields.value.filter(f => f.id !== name)
}
function askDeleteProjectField(field) {
  triggerConfirm({
    title: 'Delete field',
    message: `Delete "${field.label}"? This can't be undone, and any values already stored on tasks will be lost.`,
    confirmText: 'Delete',
    confirmColor: 'danger',
    action: async () => {
      await deleteLibraryField(field.id)
      projectFields.value = projectFields.value.filter(f => f.id !== field.id)
      showToast('Field deleted')
    },
  })
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function showToast(message, type = 'success') {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { show: true, type, message }
  toastTimer = setTimeout(() => { toast.value.show = false }, 2500)
}

function goBack() {
  const key = route.params.key
  router.push(key ? store.projectLanding(key) : '/workspace')
}
</script>

<style scoped>
/* Tab strip stays horizontally scrollable on narrow viewports but never shows
   the generic OS scrollbar — matches the HeroUI Tabs underline strip. */
.tabs-scroll { -ms-overflow-style: none; scrollbar-width: none; }
.tabs-scroll::-webkit-scrollbar { display: none; width: 0; height: 0; }

/* Settings row group → bordered card, inset rows.
   Rows inside keep their py-4; the card supplies the frame + h-padding. */
/* Settings sections = airy divided lists. NO container box, NO gray panel —
   structure from whitespace + hairline rows; only the form controls carry an
   edge. A focused document register, not an admin-template card grid. */
.bp-set-card {
  background: var(--surface);
  box-shadow: var(--surface-shadow);
  border-radius: 12px;
  padding: 14px 24px;
}

/* Left settings nav items */
.set-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 34px;
  padding: 0 10px;
  border-radius: 6px;
  font-size:var(--text-base);
  font-weight: 500;
  color: #505258;
  background: none;
  border: none;
  cursor: pointer;
  transition: background-color 0.12s var(--ease-out, ease),
    color 0.12s var(--ease-out, ease);
}
.set-nav-item + .set-nav-item { margin-top: 2px; }
.set-nav-item:hover {
  background: var(--surface-hover);
  color: var(--foreground);
}
.set-nav-item--active,
.set-nav-item--active:hover {
  background: var(--accent-soft);
  color: var(--accent-soft-foreground);
  font-weight: 600;
}
/* Settings transitions: one calm timing everywhere */
.bp-set-card :deep(input),
.bp-set-card :deep(button) { transition: background-color .15s ease, border-color .15s ease, color .15s ease; }

.toast-enter-active { transition: all 0.2s cubic-bezier(0.16,1,0.3,1); }
.toast-leave-active { transition: all 0.15s ease-in; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }

.fade-enter-active, .fade-leave-active { transition: opacity 0.18s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.pop-enter-active { transition: all 0.15s cubic-bezier(0.16,1,0.3,1); }
.pop-leave-active { transition: all 0.1s ease-in; }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(-4px) scale(0.97); }
</style>
