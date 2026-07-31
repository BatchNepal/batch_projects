<template>
  <div class="h-full flex flex-col font-[Inter] overflow-hidden bg-background">

    <!-- ── Top bar: breadcrumb ─────────────────────────────────────────── -->
    <header class="shrink-0 h-12 flex items-center justify-between gap-4 px-6 bg-surface border-b border-separator">
      <nav class="flex items-center gap-1 text-[13px] min-w-0">
        <button type="button"
          class="flex items-center gap-1.5 text-muted hover:text-foreground transition-colors shrink-0 -ml-1.5 px-1.5 py-1 rounded-md hover:bg-[var(--surface-hover)]"
          @click="router.push('/workspace')">
          <Icon :icon="ArrowLeft" class="size-3.5" />
          Back to workspace
        </button>
        <span class="text-[var(--border-secondary)] px-0.5">/</span>
        <span class="text-foreground font-medium">Workspace Settings</span>
      </nav>
      <Transition name="fade">
        <span v-if="saving" key="saving" class="flex items-center gap-1.5 text-[12px] text-muted shrink-0">
          <Spinner size="sm" /> Saving…
        </span>
        <span v-else-if="savedFlash" key="saved" class="flex items-center gap-1.5 text-[12px] text-[var(--success-soft-foreground)] shrink-0">
          <Icon :icon="Check" class="size-3.5" /> Saved
        </span>
      </Transition>
    </header>

    <div v-if="loading" class="flex-1 flex items-center justify-center text-sm text-muted">
      <Spinner size="sm" class="mr-2" /> Loading…
    </div>

    <!-- ── Non-admin: no access to this hub at all ────────────────────── -->
    <div v-else-if="!isAdmin" class="flex-1 flex items-center justify-center">
      <EmptyState :icon="ShieldAlert" title="Workspace admin access required"
        description="Ask a workspace admin — someone holding the BP Admin role, or a System Manager — to change these settings." />
    </div>

    <!-- ── Two-pane: settings nav + content ────────────────────────────── -->
    <div v-else class="flex-1 flex min-h-0 overflow-hidden">

      <aside class="hidden md:flex flex-col w-[228px] shrink-0 bg-surface border-r border-separator overflow-y-auto py-5 px-3">
        <p class="px-3 mb-2 text-[11px] font-semibold text-muted uppercase tracking-wider">Settings</p>
        <button v-for="tab in TABS" :key="tab.id" type="button" class="set-nav-item"
          :class="activeTab === tab.id ? 'set-nav-item--active' : ''" @click="setTab(tab.id)">
          <Icon :icon="tab.icon" :size="15" :stroke-width="1.75" class="shrink-0" />
          <span class="flex-1 text-left">{{ tab.label }}</span>
        </button>
      </aside>

      <div class="flex-1 overflow-y-auto">
        <div class="px-6 sm:px-8 lg:px-12 py-9">

          <nav class="md:hidden tabs-scroll flex items-center gap-1 mb-7 overflow-x-auto pb-3 border-b border-separator">
            <button v-for="tab in TABS" :key="tab.id" type="button"
              class="flex items-center gap-1.5 h-8 px-3 rounded-lg text-[13px] font-medium whitespace-nowrap shrink-0 transition-colors"
              :class="activeTab === tab.id ? 'bg-accent-soft text-[var(--accent-soft-foreground)]' : 'text-muted hover:text-foreground'"
              @click="setTab(tab.id)">
              <Icon :icon="tab.icon" :size="13" /> {{ tab.label }}
            </button>
          </nav>

          <!-- ══ GENERAL ══ -->
          <template v-if="activeTab === 'general'">
            <div class="max-w-[760px]">
              <div class="mb-4">
                <h1 class="text-[17px] font-semibold text-foreground tracking-[-0.01em]">General</h1>
                <p class="text-[13px] text-muted mt-1">Overview for this workspace's plan and access.</p>
              </div>

              <div class="bp-set-card">
                <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-center">
                  <div>
                    <p class="text-[13px] font-medium text-foreground">Plan</p>
                    <p class="text-[12px] text-muted mt-0.5">Current subscription tier.</p>
                  </div>
                  <div class="flex items-center gap-3">
                    <Chip size="sm" color="accent" variant="soft">{{ ent.tierLabel }}</Chip>
                    <RouterLink to="/workspace/pricing" class="text-[12.5px] text-primary hover:underline">
                      View plans
                    </RouterLink>
                  </div>
                </div>
                <div v-if="ent.seatsTotal" class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-center">
                  <div>
                    <p class="text-[13px] font-medium text-foreground">Seats</p>
                    <p class="text-[12px] text-muted mt-0.5">Licensed seat cap for this install.</p>
                  </div>
                  <p class="text-[13px] text-foreground tabular-nums">
                    {{ ent.seatsUsed }} of {{ ent.seatsTotal }} used
                    <span v-if="ent.isAtCapacity" class="text-danger font-medium">— at capacity</span>
                  </p>
                </div>
                <div class="grid grid-cols-[minmax(0,1fr),minmax(0,1.4fr)] gap-x-12 py-6 items-center border-t border-separator">
                  <div>
                    <p class="text-[13px] font-medium text-foreground">Billing</p>
                    <p class="text-[12px] text-muted mt-0.5">Manage subscription and payment methods.</p>
                  </div>
                  <div class="flex items-center gap-3">
                    <RouterLink to="/workspace/pricing" class="text-[12.5px] text-primary hover:underline">
                      Upgrade plan
                    </RouterLink>
                    <span class="text-[12px] text-muted">·</span>
                    <button type="button" class="text-[12.5px] text-primary hover:underline" @click="openBillingPortal">
                      Invoices &amp; payment method
                    </button>
                  </div>
                </div>
                <div class="py-6">
                  <p class="text-[12px] text-muted leading-relaxed">
                    Only users holding the <span class="font-medium text-foreground">BP Admin</span> role, or a
                    System Manager, can change workspace settings. Per-project settings stay with each project's
                    own Settings page.
                  </p>
                </div>
              </div>
            </div>
          </template>

          <!-- ══ FEATURES ══ -->
          <template v-else-if="activeTab === 'features'">
            <div class="max-w-[760px]">
              <div class="mb-4">
                <h1 class="text-[17px] font-semibold text-foreground tracking-[-0.01em]">Features</h1>
                <p class="text-[13px] text-muted mt-1">Turn workspace-wide surfaces on or off for everyone.</p>
              </div>

              <div class="bp-set-card">
                <FeatureRow v-for="f in FEATURE_ROWS" :key="f.key"
                  :label="f.label" :description="f.description" :comingSoon="f.comingSoon"
                  :value="features[f.key]" @toggle="features[f.key] = features[f.key] ? 0 : 1" />
              </div>

              <div class="flex items-center gap-3 mt-4">
                <Button variant="solid" color="primary" size="sm" :isLoading="savingFeatures" @click="saveFeatures">
                  Save
                </Button>
              </div>
            </div>
          </template>

          <!-- ══ CUSTOM FIELDS ══ -->
          <template v-else-if="activeTab === 'customFields'">
            <div class="mb-4 flex items-center justify-between gap-4">
              <div>
                <h1 class="text-[17px] font-semibold text-foreground tracking-[-0.01em]">Custom Fields</h1>
                <p class="text-[13px] text-muted mt-1">Define fields once, reuse them across projects.</p>
              </div>
              <Button variant="solid" color="primary" size="sm" @click="openNewField">
                <Icon :icon="Plus" class="size-3.5 mr-1" /> New field
              </Button>
            </div>

            <div class="bg-surface shadow-surface rounded-[12px] overflow-hidden">
              <DataTable :columns="CF_COLUMNS" :rows="libraryFields" :loading="loadingFields"
                :on-row-click="openEditField">
                <template #cell-field_type="{ value }">
                  <span class="inline-flex items-center gap-1.5">
                    <Icon :icon="cfIcon(value)" :size="13" :style="{ color: cfMeta(value)?.color }" />
                    {{ cfMeta(value)?.label || value }}
                  </span>
                </template>
                <template #cell-applies_to="{ value }">
                  <span class="text-muted">{{ value }}</span>
                </template>
                <template #cell-assigned_projects="{ value }">
                  <span class="text-muted tabular-nums">{{ value }} project{{ value === 1 ? '' : 's' }}</span>
                </template>
                <template #cell-enabled="{ value }">
                  <Chip size="sm" :color="value ? 'success' : 'default'" variant="soft">
                    {{ value ? 'Enabled' : 'Disabled' }}
                  </Chip>
                </template>
                <template #cell-owner_name="{ value }">
                  <span class="text-muted">{{ value }}</span>
                </template>
                <template #empty>
                  <div class="py-4">
                    <EmptyState :icon="Rows3" title="No custom fields yet"
                      description="Fields you create here become reusable across every project." />
                  </div>
                </template>
              </DataTable>
            </div>
          </template>

          <!-- ══ ROLES & PERMISSIONS ══ -->
          <template v-else-if="activeTab === 'roles'">
            <div class="max-w-[860px]">
              <div class="mb-4">
                <h1 class="text-[17px] font-semibold text-foreground tracking-[-0.01em]">Roles &amp; Permissions</h1>
                <p class="text-[13px] text-muted mt-1">
                  What each project role can do. Money and Files are switchable per role — everything
                  else is inherent to the role itself.
                </p>
              </div>

              <div class="bp-set-card bp-matrix-card">
                <table class="rp-matrix">
                  <thead>
                    <tr>
                      <th class="rp-cap-col">Capability</th>
                      <th class="rp-role-col">
                        <span class="rp-role-head"><Icon :icon="Lock" class="size-3" /> Admin</span>
                      </th>
                      <th class="rp-role-col">Manager</th>
                      <th class="rp-role-col">Member</th>
                      <th class="rp-role-col">Viewer</th>
                    </tr>
                  </thead>
                  <tbody>
                    <template v-for="group in capabilityGroups" :key="group">
                      <tr class="rp-group-row"><td colspan="5">{{ group }}</td></tr>
                      <tr v-for="cap in capsInGroup(group)" :key="cap.key">
                        <td class="rp-cap-label">
                          {{ cap.label }}
                          <span v-if="!cap.overridable" class="rp-fixed-badge">Fixed by role</span>
                        </td>
                        <td class="rp-role-col">
                          <Icon :icon="Check" class="size-4 text-success" />
                        </td>
                        <td v-for="role in ['Manager', 'Member', 'Viewer']" :key="role" class="rp-role-col">
                          <Switch v-if="cap.overridable" size="sm"
                            :modelValue="isOn(role, cap.key)"
                            @update:modelValue="v => setOverride(role, cap.key, v)" />
                          <Icon v-else :icon="isOn(role, cap.key) ? Check : Minus"
                            class="size-4"
                            :class="isOn(role, cap.key) ? 'text-success' : 'text-muted'" />
                        </td>
                      </tr>
                    </template>
                  </tbody>
                </table>
              </div>

              <div class="flex items-center gap-3 mt-4">
                <Button variant="solid" color="primary" size="sm" :isLoading="savingRoles" @click="saveRoles">
                  Save
                </Button>
              </div>
            </div>
          </template>

          <!-- ══ PROJECT TEMPLATES ══ -->
          <template v-else-if="activeTab === 'templates'">
            <div class="max-w-[860px]">
              <div class="mb-4">
                <h1 class="text-[17px] font-semibold text-foreground tracking-[-0.01em]">Templates</h1>
                <p class="text-[13px] text-muted mt-1">
                  User-saved project templates. Save one from any project's Settings → General.
                </p>
              </div>

              <div class="bp-set-card">
                <div v-if="!allTemplates.length" class="py-8">
                  <EmptyState :icon="FileText" title="No templates yet" description="Loading…" />
                </div>
                <div v-for="t in allTemplates" :key="(t.is_built_in ? 'builtin:' : 'user:') + t.name" class="ptpl-row">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="text-[13px] font-medium text-foreground">{{ t.template_name }}</span>
                      <Chip v-if="t.is_built_in" size="sm" variant="soft" color="default">Built-in</Chip>
                      <Chip v-else-if="t.category" size="sm" variant="soft">{{ t.category }}</Chip>
                    </div>
                    <p class="text-[12px] text-muted mt-0.5">
                      <template v-if="t.is_built_in">{{ t.description }}</template>
                      <template v-else>
                        {{ t.task_count }} task{{ t.task_count === 1 ? '' : 's' }} ·
                        {{ t.custom_field_count }} field{{ t.custom_field_count === 1 ? '' : 's' }} ·
                        {{ t.automation_count }} automation{{ t.automation_count === 1 ? '' : 's' }}
                        <template v-if="t.usage_count"> · used {{ t.usage_count }}×</template>
                        <template v-if="t.source_project"> · from {{ t.source_project }}</template>
                        <template v-if="t.owner"> · by {{ t.owner }}</template>
                      </template>
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" @click="useTemplate(t)">Use</Button>
                  <template v-if="!t.is_built_in">
                    <Button variant="ghost" size="sm" @click="openTemplatePreview(t)">Preview</Button>
                    <Button variant="ghost" size="sm" @click="renameProjectTemplate(t)"><Icon :icon="Pencil" class="size-3.5" /></Button>
                    <Button variant="ghost" size="sm" @click="removeProjectTemplate(t)"><Icon :icon="Trash2" class="size-3.5" /></Button>
                  </template>
                </div>
              </div>
            </div>

            <!-- Preview drawer -->
            <Drawer :open="tplPreviewOpen" @update:open="tplPreviewOpen = $event" size="lg" placement="right">
              <DrawerHeader @close="tplPreviewOpen = false">
                <span class="text-[14px] font-semibold text-foreground">{{ tplPreview?.template_name }}</span>
              </DrawerHeader>
              <DrawerBody v-if="tplPreview">
                <div class="flex flex-col gap-5">
                  <p v-if="tplPreview.description" class="text-[13px] text-muted">{{ tplPreview.description }}</p>

                  <div>
                    <p class="text-[11px] font-semibold text-muted uppercase tracking-wider mb-2">Workflow states</p>
                    <div class="flex flex-wrap gap-1.5">
                      <Chip v-for="s in tplPreview.workflow_states" :key="s.name" size="sm" variant="soft">{{ s.name }}</Chip>
                    </div>
                  </div>

                  <div>
                    <p class="text-[11px] font-semibold text-muted uppercase tracking-wider mb-2">Task types</p>
                    <div class="flex flex-wrap gap-1.5">
                      <Chip v-for="it in tplPreview.issue_types" :key="it.name" size="sm" variant="soft">{{ it.name }}</Chip>
                    </div>
                  </div>

                  <div v-if="tplPreview.billing">
                    <p class="text-[11px] font-semibold text-muted uppercase tracking-wider mb-2">Billing</p>
                    <div class="flex items-center gap-2 flex-wrap text-[12.5px] text-foreground">
                      <Chip size="sm" variant="soft">{{ tplPreview.billing.project_type || 'internal' }}</Chip>
                      <span v-if="tplPreview.billing.hourly_rate">{{ tplPreview.billing.hourly_rate }}/hr</span>
                      <span v-if="tplPreview.billing.retainer_hours">{{ tplPreview.billing.retainer_hours }}h retainer</span>
                      <span v-if="tplPreview.billing.budget_amount">Budget {{ tplPreview.billing.budget_amount }}</span>
                    </div>
                  </div>

                  <div v-if="tplPreview.custom_fields && (tplPreview.custom_fields.global_ids?.length || tplPreview.custom_fields.owner_fields?.length)">
                    <p class="text-[11px] font-semibold text-muted uppercase tracking-wider mb-2">
                      Custom fields ({{ (tplPreview.custom_fields.global_ids?.length || 0) + (tplPreview.custom_fields.owner_fields?.length || 0) }})
                    </p>
                    <div class="flex flex-wrap gap-1.5">
                      <Chip v-for="(f, i) in tplPreview.custom_fields.owner_fields" :key="'own'+i" size="sm" variant="soft">
                        {{ f.field_label }}{{ f.required ? ' *' : '' }}
                      </Chip>
                      <Chip v-if="tplPreview.custom_fields.global_ids?.length" size="sm" variant="soft" color="default">
                        {{ tplPreview.custom_fields.global_ids.length }} workspace field{{ tplPreview.custom_fields.global_ids.length === 1 ? '' : 's' }}
                      </Chip>
                    </div>
                  </div>

                  <div v-if="tplPreview.tasks?.length">
                    <p class="text-[11px] font-semibold text-muted uppercase tracking-wider mb-2">
                      Tasks ({{ tplPreview.tasks.length }})
                    </p>
                    <div class="ptpl-task-tree">
                      <div v-for="(t, i) in tplPreview.tasks" :key="i" class="ptpl-task-row"
                        :class="{ 'ptpl-task-row--sub': t.parent_idx !== null && t.parent_idx !== undefined }">
                        <span class="text-[12.5px] text-foreground">{{ t.title }}</span>
                        <span class="text-[11px] text-muted ml-1.5">{{ t.task_type }}</span>
                        <Chip v-if="t.depends_on?.length" size="sm" variant="soft" class="ml-1.5">
                          depends on {{ t.depends_on.length }}
                        </Chip>
                      </div>
                    </div>
                  </div>

                  <div v-if="tplPreview.automations?.length">
                    <p class="text-[11px] font-semibold text-muted uppercase tracking-wider mb-2">
                      Automations ({{ tplPreview.automations.length }})
                    </p>
                    <div class="flex flex-col gap-1">
                      <p v-for="(a, i) in tplPreview.automations" :key="i" class="text-[12.5px] text-foreground">
                        {{ a.rule_name }}
                        <span class="text-muted">— {{ a.trigger_event }} → {{ (a.actions || []).map(x => x.type).join(' + ') || a.action_type }}</span>
                      </p>
                    </div>
                  </div>
                </div>
              </DrawerBody>
            </Drawer>
          </template>

          <!-- ══ AUTOMATIONS ══ -->
          <template v-else-if="activeTab === 'automations'">
            <div class="max-w-[900px]">
              <AutomationRules mode="workspace" :project="null" />
            </div>
          </template>

          <!-- ══ BRANDING ══ -->
          <template v-else-if="activeTab === 'branding'">
            <div class="max-w-[760px]">
              <div class="mb-4">
                <h1 class="text-[17px] font-semibold text-foreground tracking-[-0.01em] flex items-center gap-2">
                  Branding
                  <span v-if="!ent.can('custom_branding')"
                    class="inline-flex items-center gap-1 text-[10.5px] font-semibold px-1.5 py-0.5 rounded
                           bg-[var(--surface-secondary)] text-muted uppercase tracking-wider">
                    <Icon :icon="Lock" class="size-3" /> {{ ent.requiredPlanFor('custom_branding') }}
                  </span>
                </h1>
                <p class="text-[13px] text-muted mt-1">Put your own name, logo and favicon on the app shell.</p>
              </div>

              <!-- Premium lock banner -->
              <div v-if="!ent.can('custom_branding')"
                class="mb-5 rounded-lg border border-[var(--border-secondary)] overflow-hidden">
                <div class="px-5 py-5 flex items-start gap-4 bg-accent-soft">
                  <span class="size-10 rounded-lg bg-overlay border border-border flex items-center justify-center shrink-0 shadow-sm">
                    <Icon :icon="Image" class="size-5 text-accent" />
                  </span>
                  <div class="min-w-0 flex-1">
                    <p class="text-[14px] font-semibold text-foreground">Make it yours</p>
                    <p class="text-[13px] text-muted mt-1 leading-relaxed">
                      Replace the BatchProjects name, sidebar logo, and browser tab icon with your own —
                      what your team and clients see stays fully white-labeled. Available on the
                      <span class="font-semibold text-foreground">{{ ent.requiredPlanFor('custom_branding') }}</span> plan and above.
                    </p>
                    <div class="flex items-center gap-2 mt-3">
                      <Button size="sm" color="primary" @click="goUpgradeBranding">
                        <Icon :icon="Sparkles" class="size-3.5 mr-1" /> Upgrade to {{ ent.requiredPlanFor('custom_branding') }}
                      </Button>
                      <span class="text-[12px] text-muted">You're on the {{ ent.tierLabel }} plan</span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="bp-set-card" :class="{ 'opacity-50 pointer-events-none': !ent.can('custom_branding') }">
                <div class="py-6">
                  <p class="text-[13px] font-medium text-foreground mb-1">Brand name</p>
                  <p class="text-[12px] text-muted mb-3">Replaces "BatchProjects" in the sidebar and browser tab title.</p>
                  <Input v-model="branding.brand_name" size="md" placeholder="BatchProjects" class="max-w-[360px]" />
                </div>

                <div class="py-6 border-t border-separator">
                  <p class="text-[13px] font-medium text-foreground mb-1">Logo</p>
                  <p class="text-[12px] text-muted mb-3">Replaces the "BP" mark in the sidebar. Square image recommended.</p>
                  <div class="flex items-center gap-3">
                    <div class="size-11 rounded-[10px] flex items-center justify-center overflow-hidden shrink-0"
                      :class="branding.logo_url ? '' : 'bg-accent'">
                      <img v-if="branding.logo_url" :src="branding.logo_url" class="w-full h-full object-cover" alt="Logo" />
                      <span v-else class="text-white text-[13px] font-black">BP</span>
                    </div>
                    <label class="bp-upload-btn">
                      <Spinner v-if="uploadingLogo" size="sm" />
                      <template v-else>{{ branding.logo_url ? 'Replace' : 'Upload' }}</template>
                      <input type="file" accept="image/*" class="hidden" :disabled="uploadingLogo" @change="onUploadLogo" />
                    </label>
                    <button v-if="branding.logo_url" type="button" class="bp-upload-btn" @click="branding.logo_url = ''">
                      <Icon :icon="X" class="size-3.5" /> Remove
                    </button>
                  </div>
                </div>

                <div class="py-6 border-t border-separator">
                  <p class="text-[13px] font-medium text-foreground mb-1">Favicon</p>
                  <p class="text-[12px] text-muted mb-3">Replaces the browser tab icon.</p>
                  <div class="flex items-center gap-3">
                    <div class="size-8 rounded-md flex items-center justify-center overflow-hidden shrink-0 bg-surface-secondary border border-border">
                      <img v-if="branding.favicon_url" :src="branding.favicon_url" class="w-full h-full object-cover" alt="Favicon" />
                      <Icon v-else :icon="Image" class="size-4 text-muted" />
                    </div>
                    <label class="bp-upload-btn">
                      <Spinner v-if="uploadingFavicon" size="sm" />
                      <template v-else>{{ branding.favicon_url ? 'Replace' : 'Upload' }}</template>
                      <input type="file" accept="image/*" class="hidden" :disabled="uploadingFavicon" @change="onUploadFavicon" />
                    </label>
                    <button v-if="branding.favicon_url" type="button" class="bp-upload-btn" @click="branding.favicon_url = ''">
                      <Icon :icon="X" class="size-3.5" /> Remove
                    </button>
                  </div>
                </div>
              </div>

              <div class="flex items-center gap-3 mt-4">
                <Button variant="solid" color="primary" size="sm" :isLoading="savingBranding"
                  :isDisabled="!ent.can('custom_branding')" @click="saveBranding">
                  Save
                </Button>
              </div>
            </div>
          </template>

          <!-- ══ TIMESHEET ══ -->
          <template v-else-if="activeTab === 'timesheet'">
            <div class="max-w-[760px]">
              <div class="mb-4">
                <h1 class="text-[17px] font-semibold text-foreground tracking-[-0.01em]">Timesheet</h1>
                <p class="text-[13px] text-muted mt-1">Configure how timesheets get approved.</p>
              </div>

              <div class="rounded-[10px] bg-accent-soft px-4 py-3 mb-4 flex items-start gap-2.5">
                <Icon :icon="Info" :size="15" class="text-[var(--accent-soft-foreground)] mt-0.5 shrink-0" />
                <p class="text-[12.5px] text-[var(--accent-soft-foreground)] leading-relaxed">
                  This saves your approval configuration now. The gate itself — blocking submission until an
                  approver acts — is enforced by the approval workflow engine.
                </p>
              </div>

              <div class="bp-set-card">
                <div class="py-6">
                  <p class="text-[13px] font-medium text-foreground mb-3">Approval mode</p>
                  <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <button v-for="mode in APPROVAL_MODES" :key="mode.value" type="button"
                      class="text-left rounded-[10px] p-4 transition-colors duration-150"
                      :class="timesheet.approval_mode === mode.value
                        ? 'bg-accent-soft ring-1 ring-accent'
                        : 'bg-surface-secondary hover:bg-[var(--surface-hover)]'"
                      @click="timesheet.approval_mode = mode.value">
                      <div class="flex items-center justify-between mb-2">
                        <Icon :icon="mode.icon" :size="16"
                          :class="timesheet.approval_mode === mode.value ? 'text-accent' : 'text-muted'" />
                        <Icon v-if="timesheet.approval_mode === mode.value" :icon="Check" :size="14" class="text-accent" />
                      </div>
                      <p class="text-[13px] font-semibold text-foreground">{{ mode.label }}</p>
                      <p class="text-[12px] text-muted mt-1 leading-relaxed">{{ mode.description }}</p>
                    </button>
                  </div>
                </div>

                <div v-if="timesheet.approval_mode === 'Manager Approval'" class="py-6">
                  <p class="text-[13px] font-medium text-foreground">Approvers</p>
                  <p class="text-[12px] text-muted mt-0.5 mb-3">Anyone here can approve a submitted timesheet.</p>

                  <div class="flex flex-wrap gap-2 mb-3" v-if="timesheet.approvers.length">
                    <Chip v-for="a in timesheet.approvers" :key="a.user" size="sm" variant="soft" isCloseable
                      @close="removeApprover(a.user)">
                      {{ userLabel(a.user) }}
                    </Chip>
                  </div>

                  <div class="flex items-end gap-2 max-w-[420px]">
                    <div class="flex-1">
                      <Select v-model="newApprover" size="sm" placeholder="Select person…">
                        <SelectItem v-for="u in availableApprovers" :key="u.user" :value="u.user">
                          {{ u.full_name }}
                        </SelectItem>
                      </Select>
                    </div>
                    <Button color="primary" size="sm" :isDisabled="!newApprover" @click="addApprover" class="shrink-0">
                      Add
                    </Button>
                  </div>
                </div>

                <FeatureRow label="Notify approvers on submission"
                  description="Email the approvers named above the moment a timesheet is submitted."
                  :value="timesheet.notify_approvers_on_submission"
                  @toggle="timesheet.notify_approvers_on_submission = timesheet.notify_approvers_on_submission ? 0 : 1" />
                <FeatureRow label="Notify submitter on decision"
                  description="Email the person who submitted once their timesheet is approved or rejected."
                  :value="timesheet.notify_submitter_on_decision"
                  @toggle="timesheet.notify_submitter_on_decision = timesheet.notify_submitter_on_decision ? 0 : 1" />
              </div>

              <div class="flex items-center gap-3 mt-4">
                <Button variant="solid" color="primary" size="sm" :isLoading="savingTimesheet" @click="saveTimesheet">
                  Save
                </Button>
              </div>
            </div>
          </template>

          <!-- ══ NOTIFICATIONS ══ -->
          <template v-else-if="activeTab === 'notifications'">
            <div class="max-w-[860px]">
              <div class="mb-4">
                <h1 class="text-[17px] font-semibold text-foreground tracking-[-0.01em]">Notifications</h1>
                <p class="text-[13px] text-muted mt-1">Override email wording per event, and route events to extra recipients.</p>
              </div>

              <!-- Templates -->
              <p class="text-[13px] font-semibold text-foreground mb-2">Email templates</p>
              <div class="bp-set-card mb-6">
                <div v-for="t in templates" :key="t.event_key" class="ntf-tpl-row">
                  <div class="flex items-center gap-3 flex-1 min-w-0">
                    <Switch size="sm" :modelValue="!!t.enabled" @update:modelValue="v => toggleTemplate(t, v)" />
                    <span class="text-[13px] font-medium text-foreground">{{ t.event_key }}</span>
                    <Chip v-if="!t.subject && !t.body" size="sm" variant="soft">Using default</Chip>
                  </div>
                  <Button variant="ghost" size="sm" @click="openTemplateEditor(t)">Edit</Button>
                </div>
              </div>

              <!-- Rules -->
              <div class="flex items-center justify-between mb-2">
                <p class="text-[13px] font-semibold text-foreground flex items-center gap-1.5">
                  Custom rules
                  <span v-if="!ent.can('notification_rules')"
                    class="inline-flex items-center gap-1 text-[10.5px] font-semibold px-1.5 py-0.5 rounded
                           bg-[var(--surface-secondary)] text-muted uppercase tracking-wider">
                    <Icon :icon="Lock" class="size-3" /> {{ ent.requiredPlanFor('notification_rules') }}
                  </span>
                </p>
                <Button variant="solid" color="primary" size="sm" :disabled="!ent.can('notification_rules')" @click="openNewRule">
                  <Icon :icon="Plus" class="size-3.5 mr-1" /> New rule
                </Button>
              </div>

              <!-- Premium lock banner — same paper-cut fix as Automations: a
                   free-tier admin used to see a live "New rule" button that
                   only errored on save; now it's disabled up front. -->
              <div v-if="!ent.can('notification_rules')"
                class="mb-4 rounded-lg border border-[var(--border-secondary)] overflow-hidden">
                <div class="px-5 py-4 flex items-start gap-4 bg-accent-soft">
                  <span class="size-9 rounded-lg bg-overlay border border-border flex items-center justify-center shrink-0 shadow-sm">
                    <Icon :icon="Zap" class="size-4 text-accent" />
                  </span>
                  <div class="min-w-0 flex-1">
                    <p class="text-[13px] font-semibold text-foreground">Route events to extra recipients</p>
                    <p class="text-[12.5px] text-muted mt-1 leading-relaxed">
                      Custom notification rules are available on the
                      <span class="font-semibold text-foreground">{{ ent.requiredPlanFor('notification_rules') }}</span> plan and above.
                    </p>
                  </div>
                </div>
              </div>

              <div class="bp-set-card" :class="!ent.can('notification_rules') && 'opacity-60'">
                <div v-if="!rules.length" class="py-6">
                  <EmptyState :icon="Bell" title="No custom rules yet"
                    description="Route an event to extra recipients, or mute one entirely." />
                </div>
                <div v-for="r in rules" :key="r.name" class="ntf-rule-row">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="text-[13px] font-medium text-foreground">{{ r.rule_name }}</span>
                      <Chip size="sm" variant="soft">{{ r.event }}</Chip>
                      <Chip v-if="r.mute" size="sm" color="danger" variant="soft">Mute</Chip>
                      <Chip v-if="!r.enabled" size="sm" variant="soft">Disabled</Chip>
                    </div>
                    <p class="text-[12px] text-muted mt-0.5">
                      {{ r.project || 'All projects' }} · {{ r.conditions.length }} condition{{ r.conditions.length === 1 ? '' : 's' }}
                      · {{ r.recipients.length }} recipient{{ r.recipients.length === 1 ? '' : 's' }}
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" @click="openEditRule(r)">Edit</Button>
                  <Button variant="ghost" size="sm" @click="removeRule(r)"><Icon :icon="Trash2" class="size-3.5" /></Button>
                </div>
              </div>
            </div>

            <!-- Template editor drawer -->
            <Drawer :open="tplDrawerOpen" @update:open="tplDrawerOpen = $event" size="lg" placement="right">
              <DrawerHeader @close="tplDrawerOpen = false">
                <span class="text-[14px] font-semibold text-foreground">{{ editingTpl?.event_key }} email</span>
              </DrawerHeader>
              <DrawerBody>
                <div class="flex flex-col gap-4" v-if="editingTpl">
                  <div class="flex flex-wrap gap-1.5">
                    <span class="text-[11px] text-muted mr-1 self-center">Variables:</span>
                    <button v-for="v in editingTpl.variables" :key="v" type="button" class="ntf-var-chip"
                      @click="insertVariable(v)">{{ variableToken(v) }}</button>
                  </div>
                  <Input v-model="editingTpl.subject" label="Subject" placeholder="Leave blank to use the default" />
                  <div>
                    <label class="text-[13px] font-medium text-foreground mb-1.5 block">Body (HTML)</label>
                    <textarea ref="bodyRef" v-model="editingTpl.body" rows="10" class="ntf-body-input"
                      placeholder="Leave blank to use the default" />
                  </div>
                  <Button variant="ghost" size="sm" :isLoading="previewing" @click="doPreview">Preview</Button>
                  <div v-if="previewHtml" class="ntf-preview-frame">
                    <p class="text-[11px] text-muted mb-2">Subject: {{ previewSubject }}</p>
                    <iframe :srcdoc="previewHtml" class="ntf-iframe" />
                  </div>
                </div>
              </DrawerBody>
              <DrawerFooter>
                <Button variant="ghost" size="sm" @click="tplDrawerOpen = false">Cancel</Button>
                <Button color="primary" size="sm" :isLoading="savingTpl" @click="saveTemplate">Save</Button>
              </DrawerFooter>
            </Drawer>

            <!-- Rule editor drawer -->
            <Drawer :open="ruleDrawerOpen" @update:open="ruleDrawerOpen = $event" size="lg" placement="right">
              <DrawerHeader @close="ruleDrawerOpen = false">
                <span class="text-[14px] font-semibold text-foreground">{{ editingRule?.name ? 'Edit rule' : 'New rule' }}</span>
              </DrawerHeader>
              <DrawerBody v-if="editingRule">
                <div class="flex flex-col gap-4">
                  <Input v-model="editingRule.rule_name" label="Rule name" placeholder="e.g. Urgent task -> manager" />

                  <div>
                    <label class="text-[13px] font-medium text-foreground mb-1.5 block">Event</label>
                    <Select v-model="editingRule.event" size="sm">
                      <SelectItem v-for="e in RULE_EVENTS" :key="e" :value="e">{{ e }}</SelectItem>
                    </Select>
                  </div>

                  <div>
                    <label class="text-[13px] font-medium text-foreground mb-1.5 block">Project</label>
                    <Select v-model="editingRule.project" size="sm" placeholder="All projects">
                      <SelectItem value="">All projects</SelectItem>
                      <SelectItem v-for="p in allProjects" :key="p.name" :value="p.name">{{ p.project_name }}</SelectItem>
                    </Select>
                  </div>

                  <div>
                    <div class="flex items-center justify-between mb-1.5">
                      <label class="text-[13px] font-medium text-foreground">Conditions (all must match)</label>
                      <button type="button" class="ntf-add-link" @click="editingRule.conditions.push({ field: '', op: '=', value: '' })">+ Add</button>
                    </div>
                    <div v-for="(c, i) in editingRule.conditions" :key="i" class="ntf-cond-row">
                      <Input v-model="c.field" size="sm" placeholder="field (e.g. priority)" class="flex-1" />
                      <Select v-model="c.op" size="sm" class="ntf-op-select">
                        <SelectItem v-for="op in ['=', '!=', 'in', 'not in', 'contains']" :key="op" :value="op">{{ op }}</SelectItem>
                      </Select>
                      <Input v-model="c.value" size="sm" placeholder="value" class="flex-1" />
                      <button type="button" class="ntf-remove" @click="editingRule.conditions.splice(i, 1)"><Icon :icon="Trash2" class="size-3.5" /></button>
                    </div>
                  </div>

                  <div>
                    <div class="flex items-center justify-between mb-1.5">
                      <label class="text-[13px] font-medium text-foreground">Recipients</label>
                      <button type="button" class="ntf-add-link" @click="editingRule.recipients.push({ type: 'assignee', value: '' })">+ Add</button>
                    </div>
                    <div v-for="(r, i) in editingRule.recipients" :key="i" class="ntf-cond-row">
                      <Select v-model="r.type" size="sm" class="flex-1">
                        <SelectItem value="assignee">Assignee</SelectItem>
                        <SelectItem value="watchers">Watchers</SelectItem>
                        <SelectItem value="project_role">Project role</SelectItem>
                        <SelectItem value="user">Specific user</SelectItem>
                      </Select>
                      <Select v-if="r.type === 'project_role'" v-model="r.value" size="sm" class="flex-1">
                        <SelectItem value="Admin">Admin</SelectItem>
                        <SelectItem value="Manager">Manager</SelectItem>
                        <SelectItem value="Member">Member</SelectItem>
                        <SelectItem value="Viewer">Viewer</SelectItem>
                      </Select>
                      <Input v-else-if="r.type === 'user'" v-model="r.value" size="sm" placeholder="user email" class="flex-1" />
                      <button type="button" class="ntf-remove" @click="editingRule.recipients.splice(i, 1)"><Icon :icon="Trash2" class="size-3.5" /></button>
                    </div>
                  </div>

                  <div>
                    <label class="text-[13px] font-medium text-foreground mb-1.5 block">Channels</label>
                    <div class="flex gap-4">
                      <Checkbox v-for="ch in ['in_app', 'email', 'desktop']" :key="ch"
                        :isSelected="editingRule.channels.includes(ch)"
                        @update:isSelected="v => toggleChannel(ch, v)">
                        {{ ch === 'in_app' ? 'In-app' : ch === 'email' ? 'Email' : 'Desktop' }}
                      </Checkbox>
                    </div>
                  </div>

                  <FeatureRow label="Mute" description="Suppress the built-in notification for this event entirely, instead of adding recipients."
                    :value="editingRule.mute" @toggle="editingRule.mute = editingRule.mute ? 0 : 1" />
                  <FeatureRow label="Enabled" description="Turn this rule off without deleting it."
                    :value="editingRule.enabled" @toggle="editingRule.enabled = editingRule.enabled ? 0 : 1" />
                </div>
              </DrawerBody>
              <DrawerFooter>
                <Button variant="ghost" size="sm" @click="ruleDrawerOpen = false">Cancel</Button>
                <Button color="primary" size="sm" :isLoading="savingRule" @click="saveRule">Save</Button>
              </DrawerFooter>
            </Drawer>
          </template>

        </div>
      </div>
    </div>

    <CustomFieldEditorDrawer :open="fieldDrawerOpen" :field="editingField" :owner-project="null"
      @update:open="fieldDrawerOpen = $event"
      @saved="onFieldSaved" @deleted="onFieldDeleted" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, defineComponent, h } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { toast } from 'vue-sonner'
import {
  Button, Select, SelectItem, Switch, Icon, Spinner, Chip, EmptyState, DataTable,
  Drawer, DrawerHeader, DrawerBody, DrawerFooter, Input, Checkbox,
} from '@/ui'
import CustomFieldEditorDrawer from '@/components/CustomFieldEditorDrawer.vue'
import AutomationRules from '@/components/AutomationRules.vue'
import {
  Settings2, SlidersHorizontal, Lock, Clock, Bell, ArrowLeft, Check, Minus,
  ShieldAlert, Info, Zap, UserCheck, Users, Rows3, Plus, Trash2, FileText, Pencil,
  Type, AlignLeft, Hash, Calendar, CheckSquare, ChevronDownSquare, ListChecks,
  Banknote, Percent, Star, Mail, Phone, Link2, UserCircle2, Database,
  Image, Sparkles, X,
} from 'lucide-vue-next'
import {
  getWorkspaceSettings, updateWorkspaceSettings, getMembers, listLibraryFields,
  uploadAttachment,
  getNotificationTemplates, updateNotificationTemplate, previewNotificationTemplate,
  getNotificationRules, createNotificationRule, updateNotificationRule, deleteNotificationRule,
  getProjects,
  listProjectTemplates, updateProjectTemplate, deleteProjectTemplate, getProjectTemplate,
  getProjectTemplates,
  getBillingPortal,
} from '@/utils/api'
import { useEntitlementsStore } from '@/stores/entitlements'
import { fieldMeta } from '@/utils/customFields'

const route  = useRoute()
const router = useRouter()
const ent    = useEntitlementsStore()

const activeTab = ref(route.params.tab || 'general')
watch(() => route.params.tab, (tab) => { activeTab.value = tab || 'general' })
function setTab(id) {
  activeTab.value = id
  router.replace({ name: 'WorkspaceSettings', params: { tab: id } })
}

const TABS = [
  { id: 'general',       label: 'General',              icon: Settings2 },
  { id: 'features',      label: 'Features',             icon: SlidersHorizontal },
  { id: 'customFields',  label: 'Custom Fields',        icon: Rows3 },
  { id: 'roles',         label: 'Roles & Permissions',  icon: Lock },
  { id: 'templates',     label: 'Templates',            icon: FileText },
  { id: 'automations',   label: 'Automations',          icon: Zap },
  { id: 'branding',      label: 'Branding',             icon: Image },
  { id: 'timesheet',     label: 'Timesheet',            icon: Clock },
  { id: 'notifications', label: 'Notifications',        icon: Bell },
]

const APPROVAL_MODES = [
  { value: 'Auto-Approve',    label: 'Auto-approve',     icon: Zap,
    description: 'Timesheets post with no review step.' },
  { value: 'Self-Submit',     label: 'Self-submit',      icon: UserCheck,
    description: "Anyone submits their own — today's behavior, no approval step." },
  { value: 'Manager Approval', label: 'Manager approval', icon: Users,
    description: 'Submissions wait for one of the approvers below.' },
]

const FEATURE_ROWS = [
  { key: 'gantt',      label: 'Gantt',      description: 'The Gantt schedule view on every project.' },
  { key: 'money_tab',  label: 'Money tab',  description: 'ERP-linked revenue, cost and invoicing on every project.' },
  { key: 'timesheets', label: 'Timesheets', description: 'Timesheet submission and the workspace Timesheets page.' },
  { key: 'reports',    label: 'Reports',    description: 'The Reports hub and saved report dashboards.' },
  { key: 'notes',      label: 'Notes',      description: 'Project-level team notes.' },
  { key: 'draw',       label: 'Draw',       description: 'Excalidraw whiteboard tab.' },
]

// ── Load ─────────────────────────────────────────────────────────────────────
const loading = ref(true)
const isAdmin = ref(false)
const saving  = computed(() => savingFeatures.value || savingTimesheet.value)
const savedFlash = ref(false)
let savedFlashTimer = null

const features = reactive({ notes: 1, draw: 1, gantt: 1, money_tab: 1, timesheets: 1, reports: 1 })
const branding = reactive({ brand_name: '', logo_url: '', favicon_url: '' })
const timesheet = reactive({
  approval_mode: 'Self-Submit',
  approvers: [],
  notify_approvers_on_submission: 1,
  notify_submitter_on_decision: 1,
})
const allUsers = ref([])

// ── Roles & Permissions tab ───────────────────────────────────────
const capabilityRegistry = ref([])   // [{key, min_role, group, label, overridable}, ...]
const capabilityGroups   = ref([])   // ordered group names
const matrix              = ref({})  // RESOLVED {role: {cap: bool}} as of last load/save
const overrides           = reactive({}) // local, pending {role: {cap: 0/1}} — starts as a copy of the raw stored value
const savingRoles = ref(false)

function capsInGroup(group) {
  return capabilityRegistry.value.filter(c => c.group === group)
}
// Single source of truth for every cell: local pending override first, else
// the last-resolved matrix. Works for both editable rows (where `overrides`
// may hold a pending edit) and the read-only rows (which never appear in
// `overrides`, so this always falls through to the resolved rank truth).
function isOn(role, capKey) {
  const pending = overrides[role]?.[capKey]
  if (pending !== undefined) return !!pending
  return !!matrix.value[role]?.[capKey]
}
function setOverride(role, capKey, value) {
  overrides[role] = { ...(overrides[role] || {}), [capKey]: value ? 1 : 0 }
}

async function saveRoles() {
  savingRoles.value = true
  try {
    const data = await updateWorkspaceSettings({ role_overrides_json: JSON.stringify(overrides) })
    matrix.value = data.capability_matrix || {}
    Object.keys(overrides).forEach(k => delete overrides[k])
    Object.assign(overrides, data.role_overrides || {})
    await ent.load() // refresh the bootstrap capability_matrix everyone else reads
    flashSaved()
  } finally {
    savingRoles.value = false
  }
}

onMounted(async () => {
  try {
    const data = await getWorkspaceSettings()
    isAdmin.value = !!data.is_admin
    if (data.features) Object.assign(features, data.features)
    if (data.is_admin) {
      timesheet.approval_mode = data.approval_mode || 'Self-Submit'
      timesheet.approvers = data.approvers || []
      timesheet.notify_approvers_on_submission = data.notify_approvers_on_submission ? 1 : 0
      timesheet.notify_submitter_on_decision = data.notify_submitter_on_decision ? 1 : 0
      branding.brand_name = data.brand_name || ''
      branding.logo_url = data.logo_url || ''
      branding.favicon_url = data.favicon_url || ''
      capabilityRegistry.value = data.capability_registry || []
      capabilityGroups.value = data.capability_groups || []
      matrix.value = data.capability_matrix || {}
      Object.assign(overrides, data.role_overrides || {})
      try { allUsers.value = await getMembers() } catch { allUsers.value = [] }
    }
  } catch {
    isAdmin.value = false
  } finally {
    loading.value = false
  }
})

function flashSaved() {
  savedFlash.value = true
  clearTimeout(savedFlashTimer)
  savedFlashTimer = setTimeout(() => { savedFlash.value = false }, 2500)
}

async function openBillingPortal() {
  try {
    const res = await getBillingPortal()
    if (res.portal_url) window.open(res.portal_url, '_blank')
    else toast.error(res.detail || 'No billing portal available yet')
  } catch (e) {
    toast.error(e.message || 'Could not open billing portal')
  }
}

// ── Features tab ─────────────────────────────────────────────────────────────
const savingFeatures = ref(false)
async function saveFeatures() {
  savingFeatures.value = true
  try {
    await updateWorkspaceSettings({ features_json: JSON.stringify({ ...features }) })
    await ent.load()
    flashSaved()
  } finally {
    savingFeatures.value = false
  }
}

// ── Branding tab ──────────────────────────────────────────────────────────────
const savingBranding = ref(false)
const uploadingLogo = ref(false)
const uploadingFavicon = ref(false)

async function saveBranding() {
  savingBranding.value = true
  try {
    await updateWorkspaceSettings({
      brand_name: branding.brand_name,
      logo_url: branding.logo_url,
      favicon_url: branding.favicon_url,
    })
    await ent.load() // refresh entitlements.branding so Sidebar/favicon update immediately
    flashSaved()
  } catch (e) {
    toast.error(e.message || 'Failed to save branding')
  } finally {
    savingBranding.value = false
  }
}

async function onUploadLogo(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  uploadingLogo.value = true
  try {
    const doc = await uploadAttachment(file, 'BP Workspace Settings', 'BP Workspace Settings', false)
    branding.logo_url = doc.file_url
  } catch (err) {
    toast.error(err.message || 'Upload failed')
  } finally {
    uploadingLogo.value = false
  }
}

async function onUploadFavicon(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  uploadingFavicon.value = true
  try {
    const doc = await uploadAttachment(file, 'BP Workspace Settings', 'BP Workspace Settings', false)
    branding.favicon_url = doc.file_url
  } catch (err) {
    toast.error(err.message || 'Upload failed')
  } finally {
    uploadingFavicon.value = false
  }
}

function goUpgradeBranding() {
  router.push('/workspace/pricing')
}

// ── Timesheet tab ─────────────────────────────────────────────────────────────
const savingTimesheet = ref(false)
const newApprover = ref(null)

const userLabel = (user) => allUsers.value.find(u => u.user === user)?.full_name || user
const availableApprovers = computed(() => {
  const existing = new Set(timesheet.approvers.map(a => a.user))
  return allUsers.value.filter(u => !existing.has(u.user))
})
function addApprover() {
  if (!newApprover.value) return
  timesheet.approvers.push({ user: newApprover.value })
  newApprover.value = null
}
function removeApprover(user) {
  timesheet.approvers = timesheet.approvers.filter(a => a.user !== user)
}

async function saveTimesheet() {
  savingTimesheet.value = true
  try {
    await updateWorkspaceSettings({
      approval_mode: timesheet.approval_mode,
      approvers: timesheet.approvers.map(a => ({ user: a.user })),
      notify_approvers_on_submission: timesheet.notify_approvers_on_submission,
      notify_submitter_on_decision: timesheet.notify_submitter_on_decision,
    })
    flashSaved()
  } finally {
    savingTimesheet.value = false
  }
}

// ── Notifications tab ─────────────────────────────────────────────
const RULE_EVENTS = [
  'task.created', 'task.updated', 'task.status_changed', 'task.assigned',
  'task.unassigned', 'comment.added', 'sprint.started', 'sprint.completed',
]

const templates = ref([])
const rules = ref([])
const allProjects = ref([])
let notificationsLoaded = false

async function loadNotifications() {
  try {
    templates.value = await getNotificationTemplates()
    rules.value = await getNotificationRules()
    if (!allProjects.value.length) allProjects.value = await getProjects()
  } catch { /* Team+ gate or not-yet-migrated — tab just shows empty */ }
  notificationsLoaded = true
}
watch(activeTab, (tab) => { if (tab === 'notifications' && !notificationsLoaded) loadNotifications() })

// Templates
const tplDrawerOpen = ref(false)
const editingTpl = ref(null)
const savingTpl = ref(false)
const previewing = ref(false)
const previewHtml = ref('')
const previewSubject = ref('')
const bodyRef = ref(null)

function openTemplateEditor(t) {
  editingTpl.value = { ...t }
  previewHtml.value = ''
  previewSubject.value = ''
  tplDrawerOpen.value = true
}
async function toggleTemplate(t, enabled) {
  try {
    await updateNotificationTemplate(t.event_key, t.subject, t.body, enabled ? 1 : 0)
    t.enabled = enabled ? 1 : 0
  } catch (e) { toast.error(e.message || 'Failed to update template') }
}
// Kept out of the <template> block — the SFC compiler tokenizes literal
// double-braces inside a `{{ }}` interpolation too, so a Jinja-looking token
// written directly in the markup breaks parsing (moved here instead).
function variableToken(v) { return `{{ ${v} }}` }
function insertVariable(v) {
  const token = variableToken(v)
  const el = bodyRef.value
  if (!el) { editingTpl.value.body += token; return }
  const start = el.selectionStart ?? editingTpl.value.body.length
  const end = el.selectionEnd ?? editingTpl.value.body.length
  editingTpl.value.body = editingTpl.value.body.slice(0, start) + token + editingTpl.value.body.slice(end)
}
async function doPreview() {
  previewing.value = true
  try {
    const res = await previewNotificationTemplate(editingTpl.value.event_key, editingTpl.value.subject, editingTpl.value.body)
    previewSubject.value = res.subject
    previewHtml.value = res.html
  } catch (e) {
    toast.error(e.message || 'Preview failed')
  } finally {
    previewing.value = false
  }
}
async function saveTemplate() {
  savingTpl.value = true
  try {
    await updateNotificationTemplate(
      editingTpl.value.event_key, editingTpl.value.subject, editingTpl.value.body, editingTpl.value.enabled ? 1 : 0
    )
    const i = templates.value.findIndex(t => t.event_key === editingTpl.value.event_key)
    if (i !== -1) templates.value[i] = { ...editingTpl.value }
    flashSaved()
    tplDrawerOpen.value = false
  } catch (e) {
    toast.error(e.message || 'Failed to save template')
  } finally {
    savingTpl.value = false
  }
}

// Rules
const ruleDrawerOpen = ref(false)
const editingRule = ref(null)
const savingRule = ref(false)

function openNewRule() {
  editingRule.value = {
    name: null, rule_name: '', event: RULE_EVENTS[0], project: '',
    conditions: [], recipients: [], channels: ['in_app', 'email', 'desktop'],
    mute: 0, enabled: 1,
  }
  ruleDrawerOpen.value = true
}
function openEditRule(r) {
  editingRule.value = {
    ...r,
    conditions: r.conditions.map(c => ({ ...c })),
    recipients: r.recipients.map(x => ({ ...x })),
    channels: [...r.channels],
  }
  ruleDrawerOpen.value = true
}
function toggleChannel(ch, on) {
  const set = new Set(editingRule.value.channels)
  if (on) set.add(ch); else set.delete(ch)
  editingRule.value.channels = [...set]
}
async function saveRule() {
  savingRule.value = true
  try {
    const payload = {
      rule_name: editingRule.value.rule_name,
      event: editingRule.value.event,
      project: editingRule.value.project || null,
      conditions: editingRule.value.conditions.filter(c => c.field),
      recipients: editingRule.value.recipients,
      channels: editingRule.value.channels,
      mute: editingRule.value.mute,
      enabled: editingRule.value.enabled,
    }
    const saved = editingRule.value.name
      ? await updateNotificationRule(editingRule.value.name, payload)
      : await createNotificationRule(payload)
    const i = rules.value.findIndex(r => r.name === saved.name)
    if (i !== -1) rules.value[i] = saved
    else rules.value.unshift(saved)
    flashSaved()
    ruleDrawerOpen.value = false
  } catch (e) {
    toast.error(e.message || 'Failed to save rule')
  } finally {
    savingRule.value = false
  }
}
async function removeRule(r) {
  if (!confirm(`Delete rule "${r.rule_name}"?`)) return
  try {
    await deleteNotificationRule(r.name)
    rules.value = rules.value.filter(x => x.name !== r.name)
  } catch (e) {
    toast.error(e.message || 'Failed to delete rule')
  }
}

// ── Project Templates tab ────────────────────────────────────────────────────
// Built-ins (setup/project_templates.py, read-only) + user-saved templates,
// normalized into ONE shape/list — one management center, not two.
const builtInTemplates = ref([])
const projectTemplates = ref([])
let projectTemplatesLoaded = false

function normalizeBuiltIn(t) {
  return {
    name: t.id, template_name: t.label, description: t.description || '',
    category: t.category || '', icon: t.icon || 'FilePlus',
    is_built_in: true, task_count: 0, automation_count: 0, custom_field_count: 0,
    usage_count: null, owner: null, modified: null,
  }
}
const allTemplates = computed(() => [
  ...builtInTemplates.value.map(normalizeBuiltIn),
  ...projectTemplates.value.map(t => ({ ...t, is_built_in: false })),
])

async function loadProjectTemplates() {
  try {
    const [builtinsResp, mine] = await Promise.all([getProjectTemplates(), listProjectTemplates()])
    // get_project_templates() returns {templates, categories, issue_type_catalog,
    // ...} — NOT a bare array (confirmed by reading setup/project_templates.py;
    // this endpoint has no other frontend consumer today, CreateProjectFlow.vue
    // uses its own separate hardcoded TEMPLATES constant for built-ins).
    builtInTemplates.value = builtinsResp?.templates || []
    projectTemplates.value = mine || []
  } catch { projectTemplates.value = []; builtInTemplates.value = [] }
  projectTemplatesLoaded = true
}
watch(activeTab, (tab) => { if (tab === 'templates' && !projectTemplatesLoaded) loadProjectTemplates() })

function useTemplate(t) {
  const templateParam = t.is_built_in ? t.name : `user:${t.name}`
  router.push({ name: 'NewProject', query: { template: templateParam } })
}

async function renameProjectTemplate(t) {
  const name = window.prompt('Rename template', t.template_name)
  if (!name || !name.trim() || name.trim() === t.template_name) return
  try {
    const saved = await updateProjectTemplate({ template: t.name, template_name: name.trim() })
    const i = projectTemplates.value.findIndex(x => x.name === t.name)
    if (i !== -1) projectTemplates.value[i] = saved
  } catch (e) {
    toast.error(e.message || 'Failed to rename template')
  }
}
async function removeProjectTemplate(t) {
  if (!confirm(`Delete template "${t.template_name}"? This can't be undone.`)) return
  try {
    await deleteProjectTemplate(t.name)
    projectTemplates.value = projectTemplates.value.filter(x => x.name !== t.name)
  } catch (e) {
    toast.error(e.message || 'Failed to delete template')
  }
}

const tplPreviewOpen = ref(false)
const tplPreview = ref(null)
async function openTemplatePreview(t) {
  tplPreviewOpen.value = true
  tplPreview.value = null
  try { tplPreview.value = await getProjectTemplate(t.name) }
  catch (e) { toast.error(e.message || 'Failed to load template'); tplPreviewOpen.value = false }
}

// ── Custom Fields tab ────────────────────────────────────────────────────────
const ICON_MAP = {
  type: Type, 'align-left': AlignLeft, hash: Hash, calendar: Calendar,
  'check-square': CheckSquare, 'chevron-down-square': ChevronDownSquare, 'list-checks': ListChecks,
  banknote: Banknote, percent: Percent, star: Star, mail: Mail, phone: Phone,
  'link-2': Link2, 'user-circle-2': UserCircle2, database: Database,
}
const cfMeta = (type) => fieldMeta(type)
const cfIcon = (type) => ICON_MAP[fieldMeta(type)?.icon] || Rows3

const CF_COLUMNS = [
  { key: 'field_label', label: 'Name' },
  { key: 'field_type', label: 'Type' },
  { key: 'applies_to', label: 'Applies to' },
  { key: 'assigned_projects', label: 'Added to' },
  { key: 'owner_name', label: 'Author' },
  { key: 'enabled', label: 'Status' },
]

const libraryFields = ref([])
const loadingFields = ref(false)
let fieldsLoaded = false

async function loadLibraryFields() {
  loadingFields.value = true
  try { libraryFields.value = await listLibraryFields() }
  catch { libraryFields.value = [] }
  finally { loadingFields.value = false; fieldsLoaded = true }
}
watch(activeTab, (tab) => { if (tab === 'customFields' && !fieldsLoaded) loadLibraryFields() })

const fieldDrawerOpen = ref(false)
const editingField = ref(null)
function openNewField() {
  editingField.value = null
  fieldDrawerOpen.value = true
}
function openEditField(row) {
  editingField.value = row
  fieldDrawerOpen.value = true
}
function onFieldSaved(row) {
  const i = libraryFields.value.findIndex(f => f.name === row.name)
  if (i !== -1) libraryFields.value[i] = row
  else libraryFields.value.unshift(row)
}
function onFieldDeleted(name) {
  libraryFields.value = libraryFields.value.filter(f => f.name !== name)
}

// ── FeatureRow sub-component (label + description + Switch, PrefRow shape) ───
const FeatureRow = defineComponent({
  props: ['label', 'description', 'value', 'comingSoon'],
  emits: ['toggle'],
  setup(props, { emit }) {
    return () =>
      h('div', { class: 'flex items-start justify-between gap-4 py-4' }, [
        h('div', { class: 'flex-1' }, [
          h('div', { class: 'flex items-center gap-2' }, [
            h('p', { class: 'text-[13px] text-foreground' }, props.label),
            props.comingSoon
              ? h(Chip, { size: 'sm', variant: 'soft', color: 'default' }, () => props.comingSoon)
              : null,
          ]),
          props.description
            ? h('p', { class: 'text-[12px] text-muted mt-0.5' }, props.description)
            : null,
        ]),
        h(Switch, {
          modelValue: !!props.value,
          isDisabled: !!props.comingSoon,
          'onUpdate:modelValue': () => emit('toggle'),
        }),
      ])
  },
})
</script>

<style scoped>
.tabs-scroll { -ms-overflow-style: none; scrollbar-width: none; }
.tabs-scroll::-webkit-scrollbar { display: none; width: 0; height: 0; }

.bp-set-card {
  background: var(--surface);
  box-shadow: var(--surface-shadow);
  border-radius: 12px;
  padding: 2px 24px;
}
.bp-set-card > * + * { border-top: 1px solid var(--separator); }

.bp-upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 12px;
  border-radius: 6px;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--foreground);
  background: var(--default);
  cursor: pointer;
  transition: background-color 0.12s var(--ease-out, ease);
}
.bp-upload-btn:hover { background: var(--default-hover); }

.set-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 34px;
  padding: 0 10px;
  border-radius: 9px;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--muted);
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

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ── Roles & Permissions matrix ─────────────────────────────── */
.bp-matrix-card { padding: 0; overflow-x: auto; }
.rp-matrix { width: 100%; border-collapse: collapse; font-size: 13px; }
.rp-matrix thead th {
  text-align: left; font-size: 11px; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.02em;
  padding: 10px 16px; border-bottom: 1px solid var(--separator);
  white-space: nowrap;
}
.rp-cap-col { min-width: 260px; }
.rp-role-col { width: 100px; text-align: center !important; }
.rp-role-head { display: inline-flex; align-items: center; gap: 4px; }
.rp-group-row td {
  padding: 8px 16px 4px; font-size: 11px; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.02em;
  background: var(--surface-secondary);
}
.rp-matrix tbody tr:not(.rp-group-row) { border-top: 1px solid var(--separator); }
.rp-matrix tbody td { padding: 10px 16px; vertical-align: middle; }
.rp-cap-label { color: var(--foreground); display: flex; align-items: center; gap: 8px; }
.rp-fixed-badge {
  font-size: 10px; font-weight: 600; color: var(--muted);
  background: var(--surface-secondary); border-radius: 999px; padding: 2px 8px;
  white-space: nowrap;
}
.rp-matrix td.rp-role-col { text-align: center; }
.rp-matrix td.rp-role-col :deep(button) { margin: 0 auto; }

/* ── Notifications tab ──────────────────────────────────────── */
.ntf-tpl-row, .ntf-rule-row {
  display: flex; align-items: center; gap: 10px; padding: 12px 20px;
}
.ntf-var-chip {
  font-size: 11px; font-family: monospace; color: var(--accent);
  background: var(--accent-soft); border: none; border-radius: 999px;
  padding: 3px 9px; cursor: pointer;
}
.ntf-var-chip:hover { opacity: 0.85; }
.ntf-body-input {
  width: 100%; min-height: 160px; border-radius: 8px; padding: 10px 12px;
  font-family: monospace; font-size: 12.5px; line-height: 1.5;
  background: var(--surface-secondary); border: 1px solid var(--border-secondary);
  color: var(--foreground); resize: vertical;
}
.ntf-body-input:focus { outline: none; border-color: var(--accent); }
.ntf-preview-frame {
  border: 1px solid var(--border-secondary); border-radius: 8px; padding: 12px;
  background: var(--surface-secondary);
}
.ntf-iframe { width: 100%; height: 420px; border: none; border-radius: 6px; background: white; }
.ntf-add-link {
  font-size: 12px; font-weight: 600; color: var(--accent);
  background: none; border: none; cursor: pointer; padding: 0;
}
.ntf-add-link:hover { text-decoration: underline; }
.ntf-cond-row { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.ntf-op-select { width: 110px; flex-shrink: 0; }
.ntf-remove {
  width: 30px; height: 30px; flex-shrink: 0; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  color: var(--muted); background: none; border: none; cursor: pointer;
}
.ntf-remove:hover { color: var(--danger); background: var(--surface-secondary); }

/* ── Project Templates tab ────────────────────────────────────── */
.ptpl-row {
  display: flex; align-items: center; gap: 10px; padding: 12px 20px;
}
.ptpl-task-tree { display: flex; flex-direction: column; gap: 2px; }
.ptpl-task-row {
  display: flex; align-items: center; padding: 6px 10px; border-radius: 6px;
}
.ptpl-task-row:hover { background: var(--surface-secondary); }
.ptpl-task-row--sub { margin-left: 20px; }
.ptpl-task-row--sub::before {
  content: '↳'; color: var(--muted); margin-right: 6px; font-size: 12px;
}
</style>
