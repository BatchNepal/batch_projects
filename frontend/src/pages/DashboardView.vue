<template>
  <div ref="rootEl" class="flex flex-col h-full overflow-hidden bg-surface">
    <!-- Header — two tiers: identity+authorship (row 1), then ONE toolbar of
         same-weight action pills (row 2). No back arrow — nothing else in
         this app uses one (Board.vue/ProjectSummary.vue/ListView.vue all
         rely on the persistent sidebar for navigation); a browser-style
         back button doesn't answer "back to where?" in a rail-nav SPA. -->
    <header class="shrink-0 flex flex-col border-b bg-surface">
      <!-- Row 1: identity + authorship + freshness -->
      <div class=" px-4 pt-3">
      <div class="flex items-center gap-1.5 ">
        <input v-if="titleEditing" ref="titleInput" v-model="titleVal"
          class="text-[18px] font-semibold text-[--foreground] bg-transparent outline-none border-b border-accent min-w-[140px] max-w-[320px]"
          @blur="commitTitle" @keydown.enter="commitTitle" @keydown.esc="titleEditing = false" />
        <h1 v-else
          class="text-[18px] font-semibold text-[--foreground] tracking-tight truncate max-w-[320px] cursor-pointer rounded-md px-1.5 py-0.5 -mx-1.5 hover:bg-default transition-colors"
          title="Click to rename"
          @click="startTitleEdit"
        >{{ dashboard?.name || 'Dashboard' }}</h1>
        <!-- Authorship is metadata, not a control — plain text, no pill/border,
             so it reads as read-only next to the real action buttons below. -->
        <IconButton
          variant="light" size="sm"
          :class="dashboard?.starred ? 'text-warning' : 'text-muted'"
          title="Star dashboard"
          @click="toggleStar"
        >
          <Star :size="14" :fill="dashboard?.starred ? 'currentColor' : 'none'" />
        </IconButton>

      
      </div>
      
    </div>


      <!-- Row 2: ONE toolbar — every control here shares the same bordered-
           pill recipe (same Button variant="bordered" props) so nothing looks like it wandered
           in from a different design system. "+ Widget" is bordered, not a
           solid/primary CTA — authoring the dashboard isn't the #1 thing a
           user does on a board they're here to READ. -->
      <div class="flex items-center gap-1.5 h-10 px-4 pb-3">
        <!-- Done is the one legitimate solid/primary button here — unlike
             "+ Widget", exiting edit mode is a real, time-boxed action the
             user must take once they've entered it (there's no other way
             back: the ⋯ menu's "Edit Dashboard" only ever turns edit mode
             ON, see below — this was previously missing entirely, leaving
             edit mode with no visible exit once you entered it). -->
        <Button v-if="editMode" color="primary" size="xs" @click="editMode = false">
          <template #startContent><Icon :icon="Check" :size="13" /></template>Done editing
        </Button>
        <Button variant="bordered" size="xs" @click="openAddWidget">
          <template #startContent><Icon :icon="Plus" :size="13" /></template>Widget
        </Button>

        <Button variant="bordered" size="xs" @click="toggleShare">
          <template #startContent><Icon :icon="dashboard?.visibility === 'workspace' ? Users : Lock" :size="13" /></template>
          {{ dashboard?.visibility === 'workspace' ? 'Shared' : 'Private' }}
        </Button>

        <!-- Filters — hidden when every widget reads workspace-scoped data
             (Leads/Deals/...): a project picker that filters nothing reads
             as "mixed up", not a genuine workspace/company overview. Labeled
             "Project" explicitly (not a bare funnel icon) — this dashboard
             can mix Task and Lead/Deal widgets, so it must be clear this
             filter only scopes the project-backed ones, not everything on
             the page. -->
        <div v-if="hasProjectScopedWidgets" class="flex items-center gap-1.5 shrink-0" title="Scopes project-backed widgets only — filters cascade to widgets set to Inherit">
          <ProjectScopeSelect :model-value="dashboardScope" :projects="store.projects" @update:model-value="setScope" />
        </div>

        <!-- ⋯ more — divider anchors it to the toolbar instead of floating
             in empty space at the far edge. Edit Dashboard, present, rename,
             duplicate, pin, export, delete. -->
        <div class="ml-auto  shrink-0 flex items-center mb-8 gap-1.5">
            <!-- Freshness lives ONLY here, as a tooltip on the refresh trigger —
             not as standing text under the title. -->
        <Button
          class="ml-auto shrink-0"
          variant="light" size="sm"
          :title="`Updated ${lastUpdatedLabel} — click to refresh`"
          @click="refreshAll"
        >
        <span>Refresh</span>
          <Icon :icon="RefreshCw" :size="11" :class="refreshing ? 'animate-spin text-[--accent]' : 'text-[--muted]'" />
        </Button>
          <Dropdown placement="bottom-end" :side-offset="6">
            <template #trigger="{ open: isOpen }">
              <IconButton
                variant="outline"
                size="sm"
                :class="{ 'bg-surface-secondary text-foreground': isOpen }"
                title="More"
              >
                <Icon :icon="MoreHorizontal" :size="16" />
              </IconButton>
            </template>

            <!-- class="dv-more-item" below gives this ONE menu extra
                 breathing room (see .dv-more-item in <style>) without
                 touching the shared DropdownItem.vue used by every other
                 dropdown in the app. -->
            <DropdownItem v-if="!editMode" class="dv-more-item" @click="editMode = true">
              <template #startContent><Icon :icon="Edit3" :size="14" class="text-muted shrink-0" /></template>
              Edit Dashboard
            </DropdownItem>
            <DropdownItem class="dv-more-item" @click="present">
              <template #startContent><Icon :icon="Maximize2" :size="14" class="text-muted shrink-0" /></template>
              Present
            </DropdownItem>

            <DropdownSeparator />
            <DropdownLabel>Auto-refresh</DropdownLabel>
            <DropdownItem v-for="o in AUTO_OPTS" :key="o.v" class="dv-more-item" :close-on-click="false" @click="setAuto(o.v)">
              {{ o.l }}
              <template #endContent>
                <Icon v-if="autoMs === o.v" :icon="Check" :size="13" class="text-[--accent] shrink-0" />
              </template>
            </DropdownItem>

            <DropdownSeparator />
            <DropdownItem class="dv-more-item" @click="startTitleEdit">
              <template #startContent><Icon :icon="Edit3" :size="14" class="text-muted shrink-0" /></template>
              Rename
            </DropdownItem>
            <DropdownItem class="dv-more-item" @click="duplicate">
              <template #startContent><Icon :icon="Copy" :size="14" class="text-muted shrink-0" /></template>
              Duplicate
            </DropdownItem>
            <DropdownItem class="dv-more-item" @click="togglePin">
              <template #startContent><Icon :icon="dashboard?.pinned ? PinOff : Pin" :size="14" class="text-muted shrink-0" /></template>
              {{ dashboard?.pinned ? 'Unpin from sidebar' : 'Pin to sidebar' }}
            </DropdownItem>
            <DropdownItem class="dv-more-item" @click="printDashboard">
              <template #startContent><Icon :icon="Printer" :size="14" class="text-muted shrink-0" /></template>
              Export / Print
            </DropdownItem>

            <DropdownSeparator />
            <DropdownItem class="dv-more-item" color="danger" @click="deleting = true">
              <template #startContent><Icon :icon="Trash2" :size="14" class="shrink-0" /></template>
              Delete dashboard
            </DropdownItem>
          </Dropdown>
        </div>
      </div>
    </header>

    <!-- Canvas -->
    <div class="flex-1 overflow-y-auto px-5 pt-3 pb-5 bg-background">
      <div v-if="renderError" class="mb-4 rounded-lg border border-[--danger-soft] bg-[--danger-soft] px-4 py-3 text-[13px] text-[--danger-soft-foreground]">
        <p class="font-semibold mb-0.5">This dashboard hit an error while rendering</p>
        <p class="text-[12px] opacity-90 break-words">{{ renderError }}</p>
      </div>

      <!-- Loading skeleton — prevents the "Empty dashboard" flash before the
           dashboard and its widgets resolve. -->
      <div v-if="initializing && !renderError" class="grid grid-cols-2 gap-3">
        <div
          v-for="(s, i) in skeletonTiles" :key="i"
          class="bg-surface border border-border shadow-sm rounded-lg p-4 flex flex-col gap-3"
          :class="s.span"
        >
          <div class="flex items-center justify-between">
            <Skeleton class="h-3 w-32 rounded-md" />
            <Skeleton class="h-7 w-7 rounded-lg" />
          </div>
          <Skeleton class="flex-1 rounded-lg" :style="{ minHeight: s.h }" />
        </div>
      </div>

      <EmptyState
        v-else-if="!widgets.length && !renderError"
        :icon="LayoutDashboard"
        title="Empty dashboard"
        description="Add a column, chart, or table widget to build a live view of your project data."
      >
        <template #action>
          <Button color="primary" size="sm" @click="catalogOpen = true">
            <template #startContent><Icon :icon="Plus" :size="15" /></template>
            Add your first widget
          </Button>
        </template>
      </EmptyState>

      <GridLayout
        v-else
        v-model:layout="localLayout"
        :col-num="12" :row-height="10" :margin="[12, 12]"
        :is-draggable="editMode" :is-resizable="editMode"
        :is-bounded="false" :vertical-compact="true" :use-css-transforms="true"
        :responsive="true"
        :cols="{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }"
        :breakpoints="{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }"
        @layout-updated="onLayoutUpdated"
        @breakpoint-changed="onBreakpoint"
      >
        <GridItem
          v-for="item in localLayout" :key="item.i"
          :x="item.x" :y="item.y" :w="item.w" :h="item.h" :i="item.i"
          :min-w="item.minW" :min-h="item.minH" drag-allow-from=".drag-handle"
        >
          <div
            v-if="wmap[item.i]"
            class="widget-card group relative h-full flex flex-col overflow-hidden transition-[border-color] duration-200"
            :class="[
              wmap[item.i].borderless ? 'bg-transparent' : (wmap[item.i].type === 'column' ? 'bg-surface border rounded-lg widget-card-column' : 'bg-surface border border-border shadow-sm rounded-lg'),
              editMode ? 'edit-ring' : (wmap[item.i].borderless ? '' : 'hover:border-border-secondary'),
            ]"
            :style="wmap[item.i].color ? { background: wmap[item.i].color } : {}"
          >
            <!-- drag handle -->
            <div
              class="drag-handle absolute top-3 left-3 z-10 text-[--muted] transition-opacity"
              :class="editMode ? 'opacity-40 hover:opacity-80 cursor-grab active:cursor-grabbing' : 'opacity-0 pointer-events-none'"
            >
              <Icon :icon="GripVertical" :size="14" />
            </div>
            <!-- kebab -->
            <div class="absolute top-2.5 right-2.5 z-20" @click.stop>
              <Dropdown placement="bottom-end">
                <template #trigger="{ toggle, open }">
                  <button
                    class="w-7 h-7 rounded-md bg-surface border border-border flex items-center justify-center text-muted hover:text-foreground hover:bg-surface-secondary hover:border-border opacity-0 group-hover:opacity-100 transition-[background-color,color,border-color,opacity] cursor-pointer shadow-xs outline-none focus-visible:shadow-focus"
                    :class="{ '!opacity-100 bg-surface-secondary border-border text-foreground': open }"
                    @click="toggle"
                  >
                    <Icon :icon="MoreHorizontal" :size="15" />
                  </button>
                </template>
                <DropdownItem @click="loadWidget(wmap[item.i])"><template #startContent><Icon :icon="RefreshCw" :size="14" class="text-muted" /></template>Refresh</DropdownItem>
                <DropdownItem @click="openConfigure(item.i)"><template #startContent><Icon :icon="Settings" :size="14" class="text-muted" /></template>Configure</DropdownItem>
                <DropdownItem @click="openWidgetPage(item.i)"><template #startContent><Icon :icon="ExternalLink" :size="14" class="text-muted" /></template>Open as page</DropdownItem>
                <DropdownSeparator />
                <DropdownItem color="danger" @click="removeWidget(item.i)"><template #startContent><Icon :icon="X" :size="14" /></template>Remove widget</DropdownItem>
              </Dropdown>
            </div>
            <!-- body -->
            <div class="flex-1 min-h-0 overflow-hidden" :style="bodyPadding(wmap[item.i])">
              <WidgetView :widget="merged(item.i)" :height="bodyH(item)" :scope-label="scopeLabel" :fmt="fmtNum" :pill="PILL" :report-scope="dashboardScope" :refresh-key="refreshKey" @bql-change="(bql) => onWidgetBqlChange(item.i, bql)" @text-change="(t) => onWidgetTextChange(item.i, t)" @configure="openConfigure(item.i)" />
            </div>
          </div>
        </GridItem>
      </GridLayout>
    </div>

    <!-- Add-widget catalog -->
    <Modal :open="catalogOpen" @update:open="v => !v && (catalogOpen = false)" size="md" radius="lg" hideCloseButton>
      <ModalHeader class="px-5 pt-5">
        <div>
          <p class="text-[15px] font-semibold text-[--foreground]">Add widget</p>
          <p class="text-[12px] text-[--muted] mt-0.5">Choose a widget type to add</p>
        </div>
      </ModalHeader>
      <ModalBody class="px-5 py-3 max-h-[60vh] overflow-y-auto">
        <div class="flex flex-col gap-1.5">
          <button v-for="c in CATALOGUE" :key="c.type" class="flex items-center gap-3 p-3 border rounded-lg text-left hover:bg-[--surface-secondary] transition-colors" @click="addWidget(c.type)">
            <Icon :icon="c.icon" :size="18" class="shrink-0 text-[--muted]" />
            <span class="flex-1 min-w-0">
              <span class="block text-[13px] font-semibold text-[--foreground]">{{ c.label }}</span>
              <span class="block text-[12px] text-[--muted] mt-0.5 leading-snug">{{ c.desc }}</span>
            </span>
            <Icon :icon="Plus" :size="14" class="text-[--muted] shrink-0" />
          </button>
        </div>
      </ModalBody>
      <ModalFooter class="px-5 pb-5 justify-end">
        <Button variant="light" size="sm" @click="catalogOpen = false">Cancel</Button>
      </ModalFooter>
    </Modal>

    <!-- Configure -->
    <Modal :open="!!configuringId" @update:open="v => !v && (configuringId = null)" size="md" radius="lg" hideCloseButton>
      <template v-if="cfg">
        <ModalHeader class="px-5 pt-5">
          <div>
            <p class="text-[15px] font-semibold text-[--foreground]">Configure widget</p>
            <p class="text-[12px] text-[--muted] mt-0.5 capitalize">{{ configTypeLabel }}</p>
          </div>
        </ModalHeader>
        <ModalBody class="px-5 py-4">
          <div class="grid grid-cols-2 gap-3">
            <Input class="col-span-2" v-model="cfg.title" label="Title" placeholder="Optional" />
            <Input class="col-span-2" v-model="cfg.description" label="Description" placeholder="Optional context" />

            <div class="col-span-2 flex items-center justify-between gap-3 pt-1">
              <div class="min-w-0">
                <p class="text-[13px] font-medium text-[--foreground]">Borderless</p>
                <p class="text-[11.5px] text-[--muted] mt-0.5">Hide the border and shadow so it reads as part of the page.</p>
              </div>
              <Switch v-model="cfg.borderless" />
            </div>

            <!-- padding — every widget type, not just column/header. Default
                 (unset) is 16px unless borderless, matching what every
                 widget already looked like before this control existed;
                 "Reset" clears back to that automatic default rather than
                 pinning a number. -->
            <div class="col-span-2 grid grid-cols-2 gap-3">
              <div>
                <div class="flex items-center justify-between mb-1.5">
                  <label class="text-[12px] font-medium text-[--foreground]">Horizontal padding</label>
                  <button v-if="cfg.padding_x !== null && cfg.padding_x !== undefined" type="button" class="text-[11px] text-[--muted] hover:text-[--foreground]" @click="cfg.padding_x = null">Reset</button>
                </div>
                <div class="flex items-center gap-2">
                  <button type="button" class="pad-stepper" :disabled="effPadding(cfg, 'padding_x') <= 0" @click="adjustPadding('padding_x', -4)"><Icon :icon="Minus" :size="13" /></button>
                  <span class="text-[13px] font-medium tabular-nums w-7 text-center">{{ effPadding(cfg, 'padding_x') }}</span>
                  <button type="button" class="pad-stepper" :disabled="effPadding(cfg, 'padding_x') >= 32" @click="adjustPadding('padding_x', 4)"><Icon :icon="Plus" :size="13" /></button>
                </div>
              </div>
              <div>
                <div class="flex items-center justify-between mb-1.5">
                  <label class="text-[12px] font-medium text-[--foreground]">Vertical padding</label>
                  <button v-if="cfg.padding_y !== null && cfg.padding_y !== undefined" type="button" class="text-[11px] text-[--muted] hover:text-[--foreground]" @click="cfg.padding_y = null">Reset</button>
                </div>
                <div class="flex items-center gap-2">
                  <button type="button" class="pad-stepper" :disabled="effPadding(cfg, 'padding_y') <= 0" @click="adjustPadding('padding_y', -4)"><Icon :icon="Minus" :size="13" /></button>
                  <span class="text-[13px] font-medium tabular-nums w-7 text-center">{{ effPadding(cfg, 'padding_y') }}</span>
                  <button type="button" class="pad-stepper" :disabled="effPadding(cfg, 'padding_y') >= 32" @click="adjustPadding('padding_y', 4)"><Icon :icon="Plus" :size="13" /></button>
                </div>
              </div>
            </div>

            <!-- column background color — a real picker (any color), not a
                 fixed preset palette. -->
            <div v-if="cfg.type === 'column'" class="col-span-2 flex items-center justify-between gap-3">
              <div class="min-w-0">
                <p class="text-[13px] font-medium text-[--foreground]">Background color</p>
                <p class="text-[11.5px] text-[--muted] mt-0.5">Optional — leave unset for the default surface.</p>
              </div>
              <div class="flex items-center gap-1.5 shrink-0">
                <button v-if="cfg.color" type="button" class="text-[11px] text-[--muted] hover:text-[--foreground]" @click="cfg.color = null">Reset</button>
                <label class="relative size-7 rounded-md border border-[--border-secondary] cursor-pointer overflow-hidden shrink-0" :style="{ background: cfg.color || 'var(--surface-secondary)' }" title="Pick a color">
                  <input type="color" :value="cfg.color || '#ffffff'" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full" @input="e => cfg.color = e.target.value" />
                </label>
              </div>
            </div>

            <!-- chart / metric data source -->
            <Select v-if="cfg.type === 'chart'" v-model="cfg.chartType" label="Chart type">
              <SelectItem v-for="t in CHART_TYPES" :key="t.v" :value="t.v">{{ t.l }}</SelectItem>
            </Select>
            <Select v-if="cfg.type === 'chart' || cfg.type === 'metric'" v-model="cfg.group_by" label="Group by">
              <SelectItem v-for="g in GROUP_BYS" :key="g.v" :value="g.v">{{ g.l }}</SelectItem>
            </Select>
            <Select v-if="cfg.type === 'chart' || cfg.type === 'metric'" v-model="cfg.metric" label="Metric">
              <SelectItem v-for="m in METRICS" :key="m.v" :value="m.v">{{ m.l }}</SelectItem>
            </Select>

            <!-- doctype picker — 'column' and 'kanban' widgets can source from
                 any whitelisted doctype the user can actually read (the
                 backend filters the list by real Frappe read permission).
                 Sectioned by domain: a flat list of ~28 sources is a wall. -->
            <Select v-if="cfg.type === 'column' || cfg.type === 'kanban'" v-model="cfg.doctype" class="col-span-2" label="Source">
              <SelectSection v-for="g in groupedSources" :key="g.group" :label="g.group">
                <SelectItem v-for="d in g.items" :key="d.doctype" :value="d.doctype">{{ d.label }}</SelectItem>
              </SelectSection>
            </Select>

            <!-- BP Task column — the original, familiar one-person/status/
                 priority/project glance picker, unchanged. -->
            <template v-if="cfg.type === 'column' && isTaskDoctype(cfg.doctype)">
              <Select v-model="cfg.filterBy" label="Shows">
                <SelectItem v-for="g in COLUMN_BYS" :key="g.v" :value="g.v">{{ g.l }}</SelectItem>
              </Select>
              <!-- filterValue: a real picker per filterBy, not a freeform text
                   field a typo could silently break (e.g. "In Progres" would
                   just show an empty column with no error). -->
              <Select v-if="cfg.filterBy === 'assignee'" v-model="cfg.filterValue"
                :label="columnPeopleLoading ? 'Person (loading…)' : 'Person'">
                <SelectItem value="">Unassigned</SelectItem>
                <SelectItem v-for="m in columnPeople" :key="m.user" :value="m.user">{{ m.full_name || m.user }}</SelectItem>
              </Select>
              <Select v-if="cfg.filterBy === 'status'" v-model="cfg.filterValue" label="Status">
                <SelectItem v-for="s in columnStatusOptions" :key="s" :value="s">{{ s }}</SelectItem>
              </Select>
              <Select v-if="cfg.filterBy === 'priority'" v-model="cfg.filterValue" label="Priority">
                <SelectItem v-for="p in PRIORITIES" :key="p.value" :value="p.value">{{ p.label }}</SelectItem>
              </Select>
              <Select v-if="cfg.filterBy === 'project'" v-model="cfg.filterValue" label="Project">
                <SelectItem v-for="p in store.projects" :key="p.name" :value="p.name">{{ p.project_name }}</SelectItem>
              </Select>
              <Select v-model="cfg.statusFilter" label="Status filter">
                <SelectItem v-for="s in STATUS_FILTERS" :key="s.v" :value="s.v">{{ s.l }}</SelectItem>
              </Select>
            </template>

            <!-- Rich per-field filter builder. Available for EVERY source
                 now, including BP Task: the four quick pickers above stay as
                 the fast path, and these stack on top of them (AND). Before,
                 Task columns were the only source that couldn't express
                 "due in the next 7 days". -->
            <div v-if="cfg.type === 'column'" class="col-span-2">
              <label class="text-[12px] font-medium text-[--foreground] mb-1.5 block">
                {{ isTaskDoctype(cfg.doctype) ? 'More filters' : 'Filters' }}
              </label>
              <FilterBuilder :doctype="cfg.doctype || 'BP Task'" v-model="cfg.filters" />
            </div>

            <!-- kanban — group-by drives the auto-generated columns, plus
                 optional filters scoping which records appear at all. -->
            <template v-if="cfg.type === 'kanban' && !isTaskDoctype(cfg.doctype)">
              <Select v-model="cfg.group_by" class="col-span-2" label="Group columns by">
                <SelectItem v-for="f in kanbanGroupByFields" :key="f.fieldname" :value="f.fieldname">{{ f.label }}</SelectItem>
              </Select>
              <div class="col-span-2">
                <label class="text-[12px] font-medium text-[--foreground] mb-1.5 block">Filters</label>
                <FilterBuilder :doctype="cfg.doctype" v-model="cfg.filters" />
              </div>
            </template>

            <!-- row config — shared by kanban's cards and column's rows: up
                 to 3 label chips + one optional right-aligned date field
                 ("None" IS the hide-date option). -->
            <template v-if="(cfg.type === 'kanban' || cfg.type === 'column') && !isTaskDoctype(cfg.doctype)">
              <div class="col-span-2">
                <label class="text-[12px] font-medium text-[--foreground] mb-1.5 block">Row labels <span class="text-[11px] text-[--muted] font-normal">— up to 3</span></label>
                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="f in sourceFields" :key="f.fieldname" type="button"
                    class="h-7 px-2.5 rounded-md text-[12px] font-medium border transition-colors"
                    :class="(cfg.label_fields || []).includes(f.fieldname)
                      ? 'bg-[--accent-soft] border-[--accent-soft] text-[--accent-soft-foreground]'
                      : 'bg-[--surface] text-[--muted] hover:bg-[--surface-secondary]'"
                    @click="toggleLabelField(f.fieldname)"
                  >{{ f.label }}</button>
                </div>
              </div>
              <Select v-model="cfg.date_field" class="col-span-2" label="Date field">
                <SelectItem value="">None (hide date)</SelectItem>
                <SelectItem v-for="f in dateFieldOptions" :key="f.fieldname" :value="f.fieldname">{{ f.label }}</SelectItem>
              </Select>
            </template>

            <!-- table options -->
            <Select v-if="cfg.type === 'table'" v-model="cfg.statusFilter" label="Status filter">
              <SelectItem v-for="s in STATUS_FILTERS" :key="s.v" :value="s.v">{{ s.l }}</SelectItem>
            </Select>
            <Select v-if="cfg.type === 'table'" v-model="cfg.sortBy" label="Sort by">
              <SelectItem v-for="s in SORT_FIELDS" :key="s.v" :value="s.v">{{ s.l }}</SelectItem>
            </Select>
            <Select v-if="cfg.type === 'table'" v-model="cfg.sortOrder" label="Order">
              <SelectItem v-for="s in SORT_ORDERS" :key="s.v" :value="s.v">{{ s.l }}</SelectItem>
            </Select>
            <Select v-if="cfg.type === 'table'" v-model="cfg.pageSize" label="Rows per page">
              <SelectItem v-for="n in PAGE_SIZES" :key="n" :value="n">{{ n }}</SelectItem>
            </Select>
            <Select v-if="cfg.type === 'table'" v-model="cfg.limit" label="Max rows fetched">
              <SelectItem v-for="n in FETCH_LIMITS" :key="n" :value="n">{{ n }}</SelectItem>
            </Select>

            <!-- scope: all types except query (uses BQL project= clause) and text
                 (no data) — and except kanban/column widgets sourced from a
                 workspace-scoped doctype (Lead, Opportunity, ...), which have
                 no project dimension to scope by at all. -->
            <div v-if="cfg.type !== 'query' && cfg.type !== 'text' && cfg.type !== 'header' && isProjectScopedSource(cfg.doctype)" class="col-span-2 flex flex-col gap-1">
              <label class="text-[12px] font-medium text-[--foreground]">
                Scope
                <span class="ml-1 text-[11px] text-[--muted] font-normal">— select one, multiple, or inherit from dashboard</span>
              </label>
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  class="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-lg border text-xs font-medium transition-colors cursor-pointer outline-none"
                  :class="cfg.scope === 'inherit'
                    ? 'bg-primary border-primary text-white'
                    : 'bg-[--surface-secondary]  text-[--foreground] hover:bg-[--surface-hover]'"
                  @click="cfg.scope = 'inherit'"
                >Inherit</button>
                <ProjectScopeSelect
                  :model-value="cfg.scope === 'inherit' ? 'all' : cfg.scope"
                  :projects="store.projects"
                  @update:model-value="v => { cfg.scope = v }"
                />
              </div>
            </div>
            <p v-else-if="cfg.type !== 'query' && cfg.type !== 'text' && cfg.type !== 'header'" class="col-span-2 text-[12px] text-[--muted]">
              {{ widgetSourceLabel(cfg.doctype) }} isn't project-scoped — this widget shows workspace-wide data.
            </p>

            <!-- BQL query editor -->
            <div v-if="cfg.type === 'query'" class="col-span-2">
              <div class="flex items-center justify-between mb-1.5">
                <p class="text-[12px] font-medium text-[--foreground]">Batch Query Language (BQL)</p>
                <button class="flex items-center gap-1 text-[11px] text-[--accent] hover:opacity-80 transition-opacity" @click.prevent="bqlDocsOpen = !bqlDocsOpen">
                  <Icon :icon="BookOpen" :size="12" />{{ bqlDocsOpen ? 'Hide' : 'Field reference' }}
                </button>
              </div>
              <textarea
                v-model="cfg.bql"
                rows="4"
                class="w-full text-[12px] font-mono leading-relaxed rounded-md border px-3 py-2.5 outline-none resize-none transition-colors bg-[--surface-secondary] text-[--foreground]"
                :class="bqlError ? 'border-[--danger]' : ' focus:border-[--accent]'"
                placeholder='project = "PROJ" AND status = "Open" AND assignee = "me"'
                @input="bqlError = ''"
              />
              <p v-if="bqlError" class="text-[11px] text-[--danger] mt-1">{{ bqlError }}</p>
              <p v-else class="text-[11px] text-[--muted] mt-1">Combine filters with AND. Use quotes around values.</p>

              <!-- BQL quick examples -->
              <div class="flex flex-wrap gap-1.5 mt-2">
                <button
                  v-for="ex in BQL_EXAMPLES" :key="ex.label"
                  type="button"
                  class="h-6 px-2 rounded text-[11px] border bg-[--surface] text-[--muted] hover:bg-[--surface-secondary] transition-colors"
                  @click="cfg.bql = ex.bql; bqlError = ''"
                >{{ ex.label }}</button>
              </div>

              <!-- field reference -->
              <div v-if="bqlDocsOpen" class="mt-3 rounded-md border overflow-hidden">
                <table class="w-full text-[11px]">
                  <thead><tr class="bg-[--surface-secondary]"><th class="px-3 py-1.5 text-left font-semibold text-[--muted] border-b ">Field</th><th class="px-3 py-1.5 text-left font-semibold text-[--muted] border-b ">Example</th></tr></thead>
                  <tbody>
                    <tr v-for="f in BQL_FIELD_DOCS" :key="f.field" class="border-b last:border-0 hover:bg-[--surface-secondary]">
                      <td class="px-3 py-1.5 font-mono text-[--accent] font-medium whitespace-nowrap">{{ f.field }}</td>
                      <td class="px-3 py-1.5 font-mono text-[--muted]">{{ f.example }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- text / note content -->
            <div v-if="cfg.type === 'text'" class="col-span-2">
              <p class="text-[12px] font-medium text-[--foreground] mb-1.5">Content</p>
              <textarea
                v-model="cfg.text"
                rows="6"
                class="w-full text-[13px] leading-relaxed rounded-md border bg-[--surface-secondary] text-[--foreground] px-3 py-2.5 outline-none resize-none focus:border-[--accent] transition-colors"
                placeholder="Write your note or annotation here…"
              />
            </div>

            <!-- header widget — optional link shown on the right -->
            <template v-if="cfg.type === 'header'">
              <Input class="col-span-2" v-model="cfg.link_url" label="Link URL" placeholder="https://… (optional)" />
              <Input v-if="cfg.link_url" class="col-span-2" v-model="cfg.link_label" label="Link label" placeholder="View" />
            </template>

            <!-- table columns -->
            <div v-if="cfg.type === 'table' || cfg.type === 'query'" class="col-span-2">
              <p class="text-[12px] font-medium text-[--foreground] mb-1.5">Columns</p>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="c in COLUMN_OPTIONS" :key="c.v" type="button"
                  class="h-7 px-2.5 rounded-md text-[12px] font-medium border transition-colors"
                  :class="(cfg.columns || []).includes(c.v)
                    ? 'bg-[--accent-soft] border-[--accent-soft] text-[--accent-soft-foreground]'
                    : 'bg-[--surface]  text-[--muted] hover:bg-[--surface-secondary]'"
                  @click="toggleColumn(c.v)"
                >{{ c.l }}</button>
              </div>
            </div>
            <div v-if="cfg.type === 'metric'" class="col-span-2">
              <p class="text-[12px] font-medium text-[--foreground] mb-1.5">Accent</p>
              <div class="flex gap-2">
                <button v-for="(p, k) in PILL" :key="k" class="w-6 h-6 rounded-md border-2 transition-colors" :class="cfg.colorScheme === k ? 'border-[--foreground]' : 'border-transparent'" :style="{ background: p.color }" @click="cfg.colorScheme = k" />
              </div>
            </div>
          </div>
        </ModalBody>
        <ModalFooter class="px-5 pb-5 justify-end gap-2">
          <Button variant="bordered" size="sm" @click="configuringId = null">Cancel</Button>
          <Button color="primary" size="sm" @click="saveConfigure">Save</Button>
        </ModalFooter>
      </template>
    </Modal>

    <!-- Delete confirm -->
    <Modal :open="deleting" @update:open="v => !v && (deleting = false)" size="sm" radius="lg" hideCloseButton>
      <ModalHeader class="px-5 pt-5"><p class="text-[15px] font-semibold text-[--foreground]">Delete dashboard?</p></ModalHeader>
      <ModalBody class="px-5 py-4">
        <p class="text-[13px] text-[--muted]">"{{ dashboard?.name }}" and its {{ widgets.length }} widget{{ widgets.length === 1 ? '' : 's' }} will be permanently removed.</p>
      </ModalBody>
      <ModalFooter class="px-5 pb-5 justify-end gap-2">
        <Button variant="bordered" size="sm" @click="deleting = false">Cancel</Button>
        <Button color="danger" size="sm" @click="confirmDelete">Delete</Button>
      </ModalFooter>
    </Modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, onErrorCaptured, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { GridLayout, GridItem } from 'grid-layout-plus'
import { useProjectStore } from '@/stores/project'
import { useDashboardsStore, WIDGET_DEFAULTS, DEFAULT_STATUSES } from '@/stores/dashboards'
import { getWidgetData, getMembers, getWidgetSourceDoctypes, getWidgetSourceFields } from '@/utils/api'
import { fmtNum } from '@/components/charts/apex/apexTheme.js'
import { PRESET_LIST, PRESETS } from '@/components/dashboard/presets.js'
import { PRIORITIES } from '@/utils/constants.js'
import { validateBQL, BQL_FIELD_DOCS, BQL_EXAMPLES } from '@/utils/bql'
import { toast } from 'vue-sonner'
import WidgetView from '@/components/dashboard/WidgetView.vue'
import FilterBuilder from '@/components/dashboard/FilterBuilder.vue'
import { Button, IconButton, Input, Select, SelectItem, SelectSection, Icon, EmptyState, Skeleton, Modal, ModalHeader, ModalBody, ModalFooter, Dropdown, DropdownItem, DropdownSeparator, DropdownLabel, ProjectScopeSelect, Switch } from '@/ui'
import {
  GripVertical, MoreHorizontal, RefreshCw, Settings, Edit3, X, Plus,
  TrendingUp, BarChart3, LayoutDashboard, Table2, Columns3,
  Star, Copy, Trash2, Printer, Maximize2, Check,
  TerminalSquare, BookOpen, Pin, PinOff, Kanban, Heading, ExternalLink, Minus, Lock, Users,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const dashboardsStore = useDashboardsStore()

// Error boundary: a single broken widget must never blank the whole dashboard.
const renderError = ref(null)
onErrorCaptured((err) => {
  renderError.value = err?.message || String(err)
  console.error('[DashboardView] render error:', err)
  try { toast.error('Dashboard error', { description: renderError.value }) } catch {}
  return false
})

const dashboardId = computed(() => route.params.dashboardId)
const dashboard = computed(() => dashboardsStore.getDashboard(dashboardId.value))
const widgets = computed(() => dashboard.value?.widgets || [])
const wmap = computed(() => Object.fromEntries(widgets.value.map(w => [w.id, w])))

// "By {name}" in the header — dashboard.owner is a bare user id/email;
// resolve it against the workspace member list (same source
// loadColumnPeople already uses) rather than showing the raw email.
const workspaceMembers = ref([])
getMembers(null).then(res => { workspaceMembers.value = Array.isArray(res) ? res : (res.members || []) }).catch(() => {})
const ownerLabel = computed(() => {
  const owner = dashboard.value?.owner
  if (!owner) return '—'
  return workspaceMembers.value.find(m => m.user === owner)?.full_name || owner
})

const GROUP_BYS = [
  { v: 'status', l: 'Status' }, { v: 'assignee', l: 'Assignee' }, { v: 'priority', l: 'Priority' },
  { v: 'task_type', l: 'Type' }, { v: 'epic', l: 'Epic' }, { v: 'project', l: 'Project' },
]
const COLUMN_BYS = [
  { v: 'assignee', l: 'One person' }, { v: 'status', l: 'One status' }, { v: 'priority', l: 'One priority' }, { v: 'project', l: 'One project' },
]
const METRICS = [
  { v: 'count', l: 'Task count' }, { v: 'story_points', l: 'Story points' },
  { v: 'estimated_hours', l: 'Estimated hours' }, { v: 'actual_hours', l: 'Logged hours' },
]
const CHART_TYPES = [
  { v: 'bar', l: 'Bar' }, { v: 'hbar', l: 'Bar (horizontal)' }, { v: 'stacked', l: 'Stacked bar' },
  { v: 'line', l: 'Line' }, { v: 'area', l: 'Area' }, { v: 'donut', l: 'Donut' }, { v: 'gauge', l: 'Gauge' },
]
const STATUS_FILTERS = [{ v: 'open', l: 'Open' }, { v: 'all', l: 'All' }, { v: 'done', l: 'Completed' }]
const PAGE_SIZES = ['10', '15', '25', '50']
const FETCH_LIMITS = ['50', '100', '200', '500']
const SORT_FIELDS = [
  { v: 'modified', l: 'Updated' }, { v: 'creation', l: 'Created' }, { v: 'due_date', l: 'Due date' },
  { v: 'priority', l: 'Priority' }, { v: 'title', l: 'Title' }, { v: 'story_points', l: 'Story points' },
]
const SORT_ORDERS = [{ v: 'desc', l: 'Descending' }, { v: 'asc', l: 'Ascending' }]
const COLUMN_OPTIONS = [
  { v: 'task_key', l: 'Key' }, { v: 'title', l: 'Title' }, { v: 'status', l: 'Status' }, { v: 'priority', l: 'Priority' },
  { v: 'project_name', l: 'Project' }, { v: 'assignees', l: 'Assignee' }, { v: 'task_type', l: 'Type' },
  { v: 'epic', l: 'Epic' }, { v: 'sprint', l: 'Sprint' }, { v: 'due_date', l: 'Due date' }, { v: 'start_date', l: 'Start date' },
  { v: 'story_points', l: 'Story points' }, { v: 'estimated_hours', l: 'Est. hours' }, { v: 'actual_hours', l: 'Logged hours' },
  { v: 'reporter', l: 'Reporter' }, { v: 'modified', l: 'Updated' },
]
const PILL = {
  blue:  { bg: 'var(--accent-soft)',       color: 'var(--accent-soft-foreground)' },
  green: { bg: 'var(--success-soft)',      color: 'var(--success-soft-foreground)' },
  amber: { bg: 'var(--warning-soft)',      color: 'var(--warning-soft-foreground)' },
  red:   { bg: 'var(--danger-soft)',       color: 'var(--danger-soft-foreground)' },
  cyan:  { bg: 'var(--accent-soft)',       color: 'var(--accent-soft-foreground)' },
  teal:  { bg: 'var(--success-soft)',      color: 'var(--success-soft-foreground)' },
  gray:  { bg: 'var(--surface-secondary)', color: 'var(--muted)' },
}
const CATALOGUE = [
  { type: 'kanban', label: 'Kanban board', desc: 'A full board — auto-generated columns for any doctype (tasks, leads, deals, ...), looks and behaves like your project board.', icon: Kanban, pill: 'blue' },
  { type: 'column', label: 'Column', desc: 'One glance/monitoring column — a person, status, or priority. Add several side by side to build a board. Click through to act.', icon: Columns3, pill: 'blue' },
  { type: 'metric', label: 'Metric', desc: 'A live KPI — a single number from your project data', icon: TrendingUp, pill: 'blue' },
  { type: 'chart', label: 'Chart', desc: 'Bar, line, area, donut, gauge — grouped project data', icon: BarChart3, pill: 'cyan' },
  { type: 'table', label: 'Table', desc: 'Sortable, searchable, paginated list of issues with CSV export', icon: Table2, pill: 'green' },
  { type: 'query', label: 'BQL Query', desc: 'Write Batch Query Language to filter and display any tasks from your ERP data', icon: TerminalSquare, pill: 'teal' },
  { type: 'header', label: 'Header', desc: 'A title, description, and optional link — a plain section divider for organizing a dashboard into blocks', icon: Heading, pill: 'gray' },
]

// ── live data, kept separate from persisted widget defs ──
const dataMap = reactive({}) // { [widgetId]: { data, loading } }
function merged(id) { const w = wmap.value[id]; const d = dataMap[id] || {}; return { ...w, data: d.data, loading: d.loading } }

// Self-loading widget types fetch their own data — never orchestrated here.
const SELF_LOADING = new Set(['table', 'query', 'text', 'header', 'column', 'kanban'])

function normScope(s) {
  if (Array.isArray(s)) {
    if (s.length === 0) return 'all'
    if (s.length === 1) return s[0]
    return s
  }
  return s || 'all'
}

const dashboardScope = computed(() => normScope(dashboard.value?.scope))
function effScope(w) { return w.scope && w.scope !== 'inherit' ? w.scope : dashboardScope.value }
function serialiseScope(s) {
  if (Array.isArray(s)) {
    if (s.length === 0) return 'all'
    if (s.length === 1) return s[0]
    return JSON.stringify(s)
  }
  return s || 'all'
}

async function loadWidget(w) {
  if (!w) return
  if (SELF_LOADING.has(w.type)) return
  dataMap[w.id] = { data: dataMap[w.id]?.data || null, loading: true }
  try {
    let data
    if (w.type === 'preset') data = await PRESETS[w.preset].fetch({
      ...w,
      scope: serialiseScope(effScope(w)),
      period: 'last_30_days',
      milestone: dashboard.value?.milestone || null,
    })
    else data = await getWidgetData({ scope: serialiseScope(effScope(w)), group_by: w.group_by, metric: w.metric })
    dataMap[w.id] = { data, loading: false }
  } catch (e) {
    dataMap[w.id] = { data: dataMap[w.id]?.data || null, loading: false }
    toast.error('Widget failed', { description: String(e.message || e) })
  }
}

const refreshing = ref(false)
const lastRefreshed = ref(Date.now())
async function refreshAll() {
  refreshing.value = true
  refreshKey.value++ // bump → self-loading widgets reload via :key
  try { await Promise.all(widgets.value.map(loadWidget)) } finally {
    refreshing.value = false
    lastRefreshed.value = Date.now()
  }
}
const refreshKey = ref(0)

// ── grid layout (local working copy synced to the store) ──
const localLayout = ref([])
const currentBp = ref('lg')
function syncLayout() {
  const existing = dashboard.value?.layout || []
  const byId = new Map(existing.map(l => [l.i, l]))
  let y = existing.reduce((m, l) => Math.max(m, (l.y || 0) + (l.h || 0)), 0)
  let changed = false
  const out = []
  widgets.value.forEach((w, i) => {
    if (byId.has(w.id)) {
      out.push({ ...byId.get(w.id) })
    } else {
      const d = WIDGET_DEFAULTS[w.type] || WIDGET_DEFAULTS.chart
      out.push({ i: w.id, x: (i * 6) % 12, y, w: d.w, h: d.h, minW: d.minW, minH: d.minH })
      y += d.h
      changed = true
    }
  })
  localLayout.value = out
  if (changed) dashboardsStore.updateLayout(dashboardId.value, out)
}
function onBreakpoint(bp) {
  currentBp.value = bp
  if (bp === 'lg') syncLayout()
}
function onLayoutUpdated(l) {
  if (!dashboard.value || currentBp.value !== 'lg') return
  if ((!l || !l.length) && widgets.value.length) return
  dashboard.value.layout = l.map(x => ({ ...x }))
  dashboardsStore.persist()
}

const editMode = ref(false)
const catalogOpen = ref(false)

const initializing = ref(true)
const skeletonTiles = [
  { span: 'col-span-1', h: '120px' },
  { span: 'col-span-1', h: '120px' },
  { span: 'col-span-2', h: '200px' },
  { span: 'col-span-1', h: '160px' },
  { span: 'col-span-1', h: '160px' },
]

function scopeLabel(s) {
  if (!s || s === 'inherit') s = dashboardScope.value
  if (s === 'all') return 'All projects'
  if (Array.isArray(s)) {
    if (s.length === 0) return 'All projects'
    if (s.length === 1) return store.projects.find(p => p.name === s[0])?.project_name || s[0]
    return `${s.length} projects`
  }
  return store.projects.find(p => p.name === s)?.project_name || s
}
function bodyH(item) { return Math.max(70, (item.h * 10 + (item.h - 1) * 12) - 30) }

// Per-widget x/y padding — unset (null/undefined) keeps the original
// automatic default (16px, or 0 when borderless) so every pre-existing
// widget looks exactly the same until someone explicitly dials it.
function effPadding(w, key) {
  const v = w?.[key]
  if (v === null || v === undefined) return w?.borderless ? 0 : 16
  return v
}
function bodyPadding(w) {
  if (!w) return {}
  const px = effPadding(w, 'padding_x')
  const py = effPadding(w, 'padding_y')
  return { paddingLeft: px + 'px', paddingRight: px + 'px', paddingTop: py + 'px', paddingBottom: py + 'px' }
}
function adjustPadding(key, delta) {
  const next = Math.min(32, Math.max(0, effPadding(cfg.value, key) + delta))
  cfg.value[key] = next
}

function addWidget(type, extra = {}) {
  const w = dashboardsStore.addWidget(dashboardId.value, type, extra)
  catalogOpen.value = false
  editMode.value = true // so drag handles are visible to position the new widget right away
  syncLayout()
  loadWidget(w)
}
// "+ Widget" is always visible now (was hidden behind Edit layout) — Wrike
// doesn't gate adding a widget behind an edit-mode toggle either.
function openAddWidget() { catalogOpen.value = true }
function removeWidget(id) {
  dashboardsStore.removeWidget(dashboardId.value, id)
  delete dataMap[id]
  syncLayout()
}

// ── configure ──
const configuringId = ref(null)
const cfg = ref(null)
const configTypeLabel = computed(() => {
  const c = cfg.value
  if (!c) return ''
  if (c.type === 'metric') return 'Live KPI'
  if (c.type === 'chart') return 'Chart'
  if (c.type === 'table') return 'Table'
  if (c.type === 'query') return 'BQL Query'
  if (c.type === 'column') return 'Column'
  if (c.type === 'kanban') return 'Kanban board'
  if (c.type === 'header') return 'Header'
  return ''
})
const bqlError = ref('')

// Column widget's filterValue picker — dynamic per filterBy, resolved
// against the widget's own (possibly cross-project) scope rather than a
// freeform text field a typo could silently break. See columnFilterValues.
const columnPeople = ref([])
const columnPeopleLoading = ref(false)
async function loadColumnPeople(scope) {
  columnPeopleLoading.value = true
  try {
    const res = await getMembers(scope === 'all' || !scope ? null : scope)
    columnPeople.value = (Array.isArray(res) ? res : (res.members || [])).filter(m => m.user)
  } catch { columnPeople.value = [] }
  finally { columnPeopleLoading.value = false }
}
const columnStatusOptions = computed(() => {
  const s = cfg.value?.scope
  const eff = (!s || s === 'inherit') ? dashboardScope.value : s
  if (eff && eff !== 'all' && !Array.isArray(eff)) {
    const proj = store.projects.find(p => p.name === eff)
    const ws = (proj?.workflow_states || []).map(st => st.name || st).filter(Boolean)
    if (ws.length) return ws
  }
  return DEFAULT_STATUSES
})
watch(() => cfg.value?.filterBy, (fb) => {
  if (cfg.value?.type === 'column' && fb === 'assignee') loadColumnPeople(cfg.value.scope)
})

// Doctype-agnostic source picker + kanban group-by fields — shared by the
// 'column' and 'kanban' configure panels. BP Task is the default/back-compat
// doctype; isTaskDoctype() gates whether the original Task-only pickers or
// the generic FilterBuilder render.
function isTaskDoctype(dt) { return !dt || dt === 'BP Task' }
const widgetSourceDoctypes = ref([])
getWidgetSourceDoctypes().then(rows => { widgetSourceDoctypes.value = rows || [] }).catch(() => {})

// Sectioned source picker. Group order follows the backend's own insertion
// order (Work first, then Sales, Buying, ...) rather than an alphabetical
// re-sort, so the most-reached-for sources stay at the top of the list.
const groupedSources = computed(() => {
  const out = []
  for (const d of widgetSourceDoctypes.value) {
    const key = d.group || 'Other'
    let g = out.find(x => x.group === key)
    if (!g) { g = { group: key, items: [] }; out.push(g) }
    g.items.push(d)
  }
  return out
})

// A widget's scope control only makes sense for project-scoped sources
// (BP Task). Workspace-scoped doctypes (Lead, Opportunity, CRM Lead/Deal —
// genuine cross-project master data, same posture as board.py's
// search_erp_documents) have no project dimension to select at all.
function isProjectScopedSource(dt) {
  if (isTaskDoctype(dt)) return true
  const entry = widgetSourceDoctypes.value.find(d => d.doctype === dt)
  return entry ? entry.scope_kind === 'project' : true
}
function widgetSourceLabel(dt) {
  return widgetSourceDoctypes.value.find(d => d.doctype === dt)?.label || dt
}
// The dashboard-level Scope control (project filter, header) only matters
// if at least one widget actually reads project-scoped data — a dashboard
// built entirely from Leads/Deals is a genuine workspace/company overview,
// not "mixed up" with a project picker that filters nothing.
const SCOPELESS_TYPES = new Set(['header', 'text'])
const hasProjectScopedWidgets = computed(() =>
  widgets.value.some(w => {
    if (SCOPELESS_TYPES.has(w.type)) return false
    return (w.type !== 'kanban' && w.type !== 'column') || isProjectScopedSource(w.doctype)
  })
)

// Full field list for the chosen non-Task doctype — feeds kanban's group-by
// picker (Select/Link subset), the row-config's date-field picker
// (Date/Datetime subset), and the row-config's label-field chip toggles
// (any type). One fetch, three views into it — shared by both 'kanban' and
// 'column' since "the ability to configure the row" applies to both.
const sourceFields = ref([])
const kanbanGroupByFields = computed(() => sourceFields.value.filter(f => f.fieldtype === 'Select' || f.fieldtype === 'Link'))
const dateFieldOptions = computed(() => sourceFields.value.filter(f => f.fieldtype === 'Date' || f.fieldtype === 'Datetime'))
async function loadSourceFields(doctype) {
  if (isTaskDoctype(doctype)) { sourceFields.value = []; return }
  sourceFields.value = await getWidgetSourceFields(doctype).catch(() => [])
}
watch(() => cfg.value?.doctype, (dt) => {
  if (cfg.value?.type === 'kanban' || cfg.value?.type === 'column') loadSourceFields(dt)
})
function toggleLabelField(fieldname) {
  const cur = cfg.value.label_fields || (cfg.value.label_fields = [])
  const i = cur.indexOf(fieldname)
  if (i >= 0) cur.splice(i, 1)
  else if (cur.length < 3) cur.push(fieldname)
}

function openConfigure(id) {
  const w = wmap.value[id]
  if (!w) return
  cfg.value = reactive({
    ...w, columns: [...(w.columns || [])], pageSize: String(w.pageSize ?? '10'), limit: String(w.limit ?? '200'), bql: w.bql || '',
    doctype: w.doctype || 'BP Task', filters: [...(w.filters || [])],
    label_fields: [...(w.label_fields || [])], date_field: w.date_field || '',
  })
  bqlError.value = ''
  configuringId.value = id
  if (w.type === 'column' && w.filterBy === 'assignee') loadColumnPeople(w.scope)
  if (w.type === 'kanban' || w.type === 'column') loadSourceFields(cfg.value.doctype)
}
function toggleColumn(key) {
  const cols = cfg.value.columns || (cfg.value.columns = [])
  const i = cols.indexOf(key)
  if (i >= 0) cols.splice(i, 1); else cols.push(key)
}
const bqlDocsOpen = ref(false)

function saveConfigure() {
  const c = cfg.value
  if (c.type === 'query' && c.bql) {
    const { ok, error } = validateBQL(c.bql)
    if (!ok) { bqlError.value = error; return }
  }
  bqlError.value = ''
  const patch = {
    title: c.title, description: c.description, scope: c.scope,
    chartType: c.chartType, group_by: c.group_by, metric: c.metric, colorScheme: c.colorScheme,
    statusFilter: c.statusFilter, priority: c.priority, sortBy: c.sortBy, sortOrder: c.sortOrder,
    columns: [...(c.columns || [])], pageSize: c.pageSize, limit: c.limit,
    bql: c.bql,
    filterBy: c.filterBy, filterValue: c.filterValue,
    doctype: c.doctype, filters: [...(c.filters || [])],
    borderless: !!c.borderless,
    padding_x: c.padding_x ?? null, padding_y: c.padding_y ?? null,
    link_url: c.link_url, link_label: c.link_label,
    label_fields: [...(c.label_fields || [])], date_field: c.date_field || null,
    color: c.color || null,
  }
  dashboardsStore.updateWidgetConfig(dashboardId.value, configuringId.value, patch)
  if (c.type === 'header') fitHeaderHeight(configuringId.value, patch)
  loadWidget(wmap.value[configuringId.value])
  configuringId.value = null
}

// Header widgets have no data to size around — their content is just a
// title (+ optional description), so its height can be computed exactly
// instead of leaving a manually-resized box to guess at. Recomputed every
// save so it stays correct as title/description/padding change. Uses the
// same rowHeight(10)/margin(12) the GridLayout itself is configured with
// (:row-height="10" :margin="[12, 12]" above) — grid-layout-plus derives
// px = h*rowHeight + (h-1)*margin, solved here for h.
const HW_TITLE_PX = 24, HW_DESC_PX = 22
function fitHeaderHeight(id, w) {
  const py = w.padding_y ?? (w.borderless ? 0 : 16)
  const contentPx = HW_TITLE_PX + (w.description ? HW_DESC_PX : 0)
  const totalPx = contentPx + 2 * py
  const h = Math.max(3, Math.ceil((totalPx + 12) / 22))
  const entry = localLayout.value.find(l => l.i === id)
  if (entry && entry.h !== h) {
    entry.h = h
    dashboardsStore.updateLayout(dashboardId.value, localLayout.value)
  }
}

function onWidgetBqlChange(widgetId, bql) {
  dashboardsStore.updateWidgetConfig(dashboardId.value, widgetId, { bql })
}
function onWidgetTextChange(widgetId, text) {
  dashboardsStore.updateWidgetConfig(dashboardId.value, widgetId, { text })
}

function openWidgetPage(id) { router.push(`/workspace/dashboards/${dashboardId.value}/widget/${id}`) }

const rootEl = ref(null)

const titleEditing = ref(false)
const titleVal = ref('')
const titleInput = ref(null)
function startTitleEdit() {
  titleVal.value = dashboard.value?.name || ''
  titleEditing.value = true
  nextTick(() => titleInput.value?.focus())
}
function commitTitle() {
  if (!titleEditing.value) return
  dashboardsStore.renameDashboard(dashboardId.value, titleVal.value)
  titleEditing.value = false
}

function toggleStar() { dashboardsStore.updateDashboard(dashboardId.value, { starred: !dashboard.value?.starred }) }

function toggleShare() {
  const next = dashboard.value?.visibility === 'workspace' ? 'private' : 'workspace'
  dashboardsStore.updateDashboard(dashboardId.value, { visibility: next })
  toast.success(next === 'workspace' ? 'Shared with your workspace' : 'Made private')
}

function setScope(v) {
  const n = normScope(v)
  if (JSON.stringify(n) === JSON.stringify(dashboardScope.value)) return
  dashboardsStore.updateDashboard(dashboardId.value, { scope: n })
  refreshAll()
}

const now = ref(Date.now())
let nowTimer
const lastUpdatedLabel = computed(() => {
  const s = Math.floor((now.value - lastRefreshed.value) / 1000)
  if (s < 5) return 'just now'
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
})

const AUTO_OPTS = [{ v: 0, l: 'Off' }, { v: 30000, l: '30s' }, { v: 60000, l: '1m' }, { v: 300000, l: '5m' }]
const autoMs = ref(0)
let autoTimer
function setAuto(v) {
  autoMs.value = v
  if (autoTimer) clearInterval(autoTimer)
  if (v > 0) autoTimer = setInterval(refreshAll, v)
}

function present() { rootEl.value?.requestFullscreen?.().catch(() => {}) }
function printDashboard() { window.print() }
async function duplicate() {
  const id = await dashboardsStore.duplicateDashboard(dashboardId.value)
  if (id) router.push(`/workspace/dashboards/${id}`)
}
function togglePin() { dashboardsStore.togglePinned(dashboardId.value) }

const deleting = ref(false)
async function confirmDelete() {
  await dashboardsStore.deleteDashboard(dashboardId.value)
  deleting.value = false
  router.replace('/workspace/dashboards/dashboard')
}

async function init() {
  initializing.value = true
  await dashboardsStore.load()
  await dashboardsStore.ensureDashboard(dashboardId.value)
  if (!dashboard.value) { router.replace('/workspace/dashboards/dashboard'); return }
  if (!store.projects.length) { try { await store.fetchProjects() } catch {} }
  for (const w of widgets.value) {
    if (!SELF_LOADING.has(w.type)) {
      dataMap[w.id] = { data: dataMap[w.id]?.data ?? null, loading: true }
    }
  }
  syncLayout()
  initializing.value = false
  await Promise.all(widgets.value.map(loadWidget))
  lastRefreshed.value = Date.now()
}
onMounted(() => {
  init()
  nowTimer = setInterval(() => { now.value = Date.now() }, 15000)
})
onUnmounted(() => { if (autoTimer) clearInterval(autoTimer); if (nowTimer) clearInterval(nowTimer) })
watch(dashboardId, init)
</script>

<style scoped>
.edit-ring {
  box-shadow: 0 0 0 2px color-mix(in oklab, var(--accent) 35%, transparent);
}
/* grid-layout-plus's own item wrapper is draggable and can pick up the
   browser's raw default focus outline (a bold solid blue box) on click —
   that's a separate, uglier ring stacking on top of the intentional,
   subtle .edit-ring above, not a design choice. :deep() reaches into it
   since .vgl-item is rendered by the library, not this component. */
:deep(.vgl-item) {
  outline: none;
}
/* Roomier rows for the dashboard-level "More" menu specifically — scoped
   here (not DropdownItem.vue, shared by every dropdown app-wide) so no
   other menu's density changes. */
:deep(.dv-more-item) {
  padding-top: 9px;
  padding-bottom: 9px;
}
/* Column widgets specifically: flat, no elevation, an explicit border
   color per design direction — kept scoped to .widget-card-column (applied
   only when type==='column') rather than changed for every widget type. */
.widget-card-column {
  border-color: #dbe0eb;
  box-shadow: none;
}
:global(.dark) .widget-card-column,
:global([data-theme="dark"]) .widget-card-column {
  border-color: var(--border);
}
.pad-stepper {
  width: 24px; height: 24px; border-radius: 6px; flex-shrink: 0;
  display: grid; place-items: center; color: var(--muted);
  border: 1px solid var(--border); background: transparent;
  transition: background-color .12s, color .12s;
}
.pad-stepper:hover:not(:disabled) { background: var(--surface-secondary); color: var(--foreground); }
.pad-stepper:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
