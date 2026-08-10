<template>
  <div ref="rootEl" class="flex flex-col h-full overflow-hidden bg-surface">
    <!-- Header -->
    <header class="shrink-0 flex items-center h-[52px] gap-2 px-4 border-b bg-surface">
      <!-- Back to list -->
      <button class="shrink-0 size-8 grid place-items-center rounded-lg text-[--muted] hover:text-[--foreground] hover:bg-default transition-colors" title="Back to reports" @click="goBack">
        <Icon :icon="ArrowLeft" :size="16" />
      </button>
      <!-- Branded report icon -->
      <span class="shrink-0 size-7 rounded-lg grid place-items-center" style="background: var(--accent-soft); color: var(--accent-soft-foreground)">
        <BarChart3 :size="15" />
      </span>
      <!-- Title -->
      <input v-if="titleEditing" ref="titleInput" v-model="titleVal"
        class="text-md font-semibold text-[--foreground] bg-transparent outline-none border-b border-accent min-w-[140px] max-w-[260px]"
        @blur="commitTitle" @keydown.enter="commitTitle" @keydown.esc="titleEditing = false" />
      <h1 v-else
        class="text-md font-semibold text-[--foreground] truncate max-w-[260px] cursor-pointer rounded-md px-2 py-1 -mx-1 hover:bg-default transition-colors"
        title="Click to rename"
        @click="startTitleEdit"
      >{{ report?.name || 'Report' }}</h1>

      <!-- Right section (Filters + Star + Actions) pushed via ml-auto -->
      <div class="ml-auto flex items-center gap-2 shrink-0">
        <!-- Filters -->
        <div class="flex items-center gap-1.5 mr-2">
          <Icon :icon="Filter" :size="12" class="text-muted shrink-0" title="Filters cascade to widgets set to Inherit" />
          <ProjectScopeSelect :model-value="reportScope" :projects="store.projects" @update:model-value="setScope" />
          <Select :model-value="reportPeriod" size="sm" :full-width="false" style="min-width:116px" @update:model-value="setPeriod">
            <SelectItem v-for="p in PERIODS" :key="p.v" :value="p.v">{{ p.l }}</SelectItem>
          </Select>
          <template v-if="reportPeriod === 'custom'">
            <input type="date" :value="reportFromDate" class="rv-date-input" title="From date" @change="setFromDate($event.target.value)" />
            <span class="text-[--muted] text-xs shrink-0">–</span>
            <input type="date" :value="reportToDate" class="rv-date-input" title="To date" @change="setToDate($event.target.value)" />
          </template>
        </div>

        <!-- Freshness + manual refresh -->
        <button
          class="shrink-0 h-8 pl-2 pr-2.5 inline-flex items-center gap-1.5 rounded-lg text-sm text-muted hover:text-foreground hover:bg-default transition-colors cursor-pointer outline-none focus-visible:shadow-focus"
          :title="`Updated ${lastUpdatedLabel} — click to refresh`"
          @click="refreshAll"
        >
          <Icon :icon="RefreshCw" :size="14" :class="refreshing ? 'animate-spin text-[--accent]' : ''" />
          <span class="hidden md:inline tabular-nums">{{ lastUpdatedLabel }}</span>
        </button>

        <button
          class="shrink-0 w-8 h-8 grid place-items-center rounded-lg transition-colors cursor-pointer outline-none focus-visible:shadow-focus"
          :class="report?.starred ? 'text-warning hover:bg-default' : 'text-muted hover:text-warning hover:bg-default'"
          title="Star report"
          @click="toggleStar"
        >
          <Star :size="16" :fill="report?.starred ? 'currentColor' : 'none'" />
        </button>

        <div class="w-px h-5 bg-border mx-1 shrink-0" />

        <!-- Edit mode controls -->
        <template v-if="editMode">
          <Button variant="bordered" size="sm" @click="catalogOpen = true">
            <template #startContent><Icon :icon="Plus" :size="14" /></template>Add widget
          </Button>
          <Button color="primary" size="sm" @click="editMode = false">Done</Button>
        </template>

        <!-- ⋯ more — collapses refresh + edit + report-level actions -->
        <Dropdown placement="bottom-end" :side-offset="6">
          <template #trigger="{ open: isOpen }">
            <IconButton
              variant="light"
              size="sm"
              :class="{ 'bg-surface-secondary text-foreground': isOpen }"
              title="More"
            >
              <Icon :icon="MoreHorizontal" :size="16" />
            </IconButton>
          </template>

          <!-- Edit (only when not already in edit mode) -->
          <DropdownItem v-if="!editMode" @click="editMode = true">
            <template #startContent><Icon :icon="Edit3" :size="14" class="text-muted shrink-0" /></template>
            Edit layout
          </DropdownItem>

          <!-- Refresh -->
          <DropdownItem :close-on-click="false" @click="refreshAll">
            <template #startContent>
              <Icon :icon="RefreshCw" :size="14" class="shrink-0" :class="[refreshing ? 'animate-spin text-[--accent]' : 'text-muted']" />
            </template>
            Refresh now
          </DropdownItem>

          <DropdownSeparator />
          <DropdownLabel>Auto-refresh</DropdownLabel>
          <DropdownItem v-for="o in AUTO_OPTS" :key="o.v" :close-on-click="false" @click="setAuto(o.v)">
            {{ o.l }}
            <template #endContent>
              <Icon v-if="autoMs === o.v" :icon="Check" :size="13" class="text-[--accent] shrink-0" />
            </template>
          </DropdownItem>

          <DropdownSeparator />
          <DropdownItem @click="startTitleEdit">
            <template #startContent><Icon :icon="Edit3" :size="14" class="text-muted shrink-0" /></template>
            Rename
          </DropdownItem>
          <DropdownItem @click="duplicate">
            <template #startContent><Icon :icon="Copy" :size="14" class="text-muted shrink-0" /></template>
            Duplicate
          </DropdownItem>
          <DropdownItem @click="togglePin">
            <template #startContent><Icon :icon="report?.pinned ? PinOff : Pin" :size="14" class="text-muted shrink-0" /></template>
            {{ report?.pinned ? 'Unpin from sidebar' : 'Pin to sidebar' }}
          </DropdownItem>
          <DropdownItem @click="openSchedule">
            <template #startContent><Icon :icon="CalendarClock" :size="14" class="text-muted shrink-0" /></template>
            Schedule delivery
            <template #endContent>
              <span v-if="report?.schedule_enabled" class="text-xs font-semibold text-[--accent]">On</span>
            </template>
          </DropdownItem>
          <DropdownItem @click="exportTemplate">
            <template #startContent><Icon :icon="Download" :size="14" class="text-muted shrink-0" /></template>
            Export as template
          </DropdownItem>
          <DropdownItem @click="present">
            <template #startContent><Icon :icon="Maximize2" :size="14" class="text-muted shrink-0" /></template>
            Present
          </DropdownItem>
          <DropdownItem @click="printReport">
            <template #startContent><Icon :icon="Printer" :size="14" class="text-muted shrink-0" /></template>
            Export / Print
          </DropdownItem>

          <DropdownSeparator />
          <DropdownItem color="danger" @click="deleting = true">
            <template #startContent><Icon :icon="Trash2" :size="14" class="shrink-0" /></template>
            Delete report
          </DropdownItem>
        </Dropdown>
      </div>
    </header>

    <!-- Canvas -->
    <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5 bg-background">
      <div v-if="renderError" class="mb-4 rounded-lg border border-danger/40 bg-danger-soft px-4 py-3 text-base text-danger">
        <p class="font-semibold mb-0.5">This report hit an error while rendering</p>
        <p class="text-sm opacity-90 break-words">{{ renderError }}</p>
      </div>

      <!-- Loading skeleton — prevents the "Empty report" flash before the
           report and its widgets resolve. -->
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
        title="Empty report"
        description="Add metric and chart widgets to build a live view of your project data."
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
            class="widget-card group relative h-full flex flex-col bg-surface border border-border shadow-sm rounded-lg overflow-hidden transition-[border-color] duration-200"
            :class="editMode ? 'edit-ring' : 'hover:border-border-secondary'"
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
                <DropdownSeparator />
                <DropdownItem color="danger" @click="removeWidget(item.i)"><template #startContent><Icon :icon="X" :size="14" /></template>Remove widget</DropdownItem>
              </Dropdown>
            </div>
            <!-- body -->
            <div class="flex-1 min-h-0 p-4 overflow-hidden">
              <WidgetView :widget="merged(item.i)" :height="bodyH(item)" :scope-label="scopeLabel" :fmt="fmtNum" :pill="PILL" :report-scope="reportScope" :refresh-key="refreshKey" @bql-change="(bql) => onWidgetBqlChange(item.i, bql)" @text-change="(t) => onWidgetTextChange(item.i, t)" />
            </div>
          </div>
        </GridItem>
      </GridLayout>
    </div>

    <!-- Add-widget catalog -->
    <Modal :open="catalogOpen" @update:open="v => !v && (catalogOpen = false)" size="md" radius="lg" hideCloseButton>
      <ModalHeader class="px-5 pt-5">
        <div>
          <p class="text-md font-semibold text-[--foreground]">Add widget</p>
          <p class="text-sm text-[--muted] mt-0.5">Choose a widget type to add</p>
        </div>
      </ModalHeader>
      <ModalBody class="px-5 py-3 max-h-[60vh] overflow-y-auto">
        <p class="text-xs font-semibold uppercase tracking-wider text-[--muted] mb-1.5">Basic</p>
        <div class="flex flex-col gap-1.5">
          <button v-for="c in CATALOGUE" :key="c.type" class="flex items-center gap-3 p-3 border rounded-lg text-left hover:bg-[--surface-secondary] transition-colors" @click="addWidget(c.type)">
            <Icon :icon="c.icon" :size="18" class="shrink-0 text-[--muted]" />
            <span class="flex-1 min-w-0">
              <span class="block text-base font-semibold text-[--foreground]">{{ c.label }}</span>
              <span class="block text-sm text-[--muted] mt-0.5 leading-snug">{{ c.desc }}</span>
            </span>
            <Icon :icon="Plus" :size="14" class="text-[--muted] shrink-0" />
          </button>
        </div>
        <p class="text-xs font-semibold uppercase tracking-wider text-[--muted] mt-4 mb-1.5">Report templates</p>
        <div class="flex flex-col gap-1.5">
          <button v-for="p in PRESETS_LIST" :key="p.key" class="flex items-center gap-3 p-3 border rounded-lg text-left hover:bg-[--surface-secondary] transition-colors" @click="addPreset(p)">
            <Icon :icon="p.icon" :size="18" class="shrink-0 text-[--muted]" />
            <span class="flex-1 min-w-0">
              <span class="block text-base font-semibold text-[--foreground]">{{ p.label }}</span>
              <span class="block text-sm text-[--muted] mt-0.5 leading-snug">{{ p.desc }}</span>
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
            <p class="text-md font-semibold text-[--foreground]">Configure widget</p>
            <p class="text-sm text-[--muted] mt-0.5 capitalize">{{ configTypeLabel }}</p>
          </div>
        </ModalHeader>
        <ModalBody class="px-5 py-4">
          <div class="grid grid-cols-2 gap-3">
            <Input class="col-span-2" v-model="cfg.title" label="Title" placeholder="Optional" />
            <Input class="col-span-2" v-model="cfg.description" label="Description" placeholder="Optional context" />
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

            <!-- preset period -->
            <Select v-if="cfg.type === 'preset' && PRESETS[cfg.preset]?.needsPeriod" v-model="cfg.period" label="Period">
              <SelectItem value="inherit">Inherit from report</SelectItem>
              <SelectItem v-for="p in PERIODS" :key="p.v" :value="p.v">{{ p.l }}</SelectItem>
            </Select>

            <!-- scope: all types except query (uses BQL project= clause) and text (no data) -->
            <!-- scope: all types except query (BQL project= clause) and text (no data) -->
            <div v-if="cfg.type !== 'query' && cfg.type !== 'text'" class="col-span-2 flex flex-col gap-1">
              <label class="text-sm font-medium text-[--foreground]">
                Scope
                <span class="ml-1 text-xs text-[--muted] font-normal">— select one, multiple, or inherit from report</span>
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

            <!-- BQL query editor -->
            <div v-if="cfg.type === 'query'" class="col-span-2">
              <div class="flex items-center justify-between mb-1.5">
                <p class="text-sm font-medium text-[--foreground]">Batch Query Language (BQL)</p>
                <button class="flex items-center gap-1 text-xs text-[--accent] hover:opacity-80 transition-opacity" @click.prevent="bqlDocsOpen = !bqlDocsOpen">
                  <Icon :icon="BookOpen" :size="12" />{{ bqlDocsOpen ? 'Hide' : 'Field reference' }}
                </button>
              </div>
              <textarea
                v-model="cfg.bql"
                rows="4"
                class="w-full text-sm font-mono leading-relaxed rounded-md border px-3 py-2.5 outline-none resize-none transition-colors bg-[--surface-secondary] text-[--foreground]"
                :class="bqlError ? 'border-[--danger]' : ' focus:border-[--accent]'"
                placeholder='project = "PROJ" AND status = "Open" AND assignee = "me"'
                @input="bqlError = ''"
              />
              <p v-if="bqlError" class="text-xs text-[--danger] mt-1">{{ bqlError }}</p>
              <p v-else class="text-xs text-[--muted] mt-1">Combine filters with AND. Use quotes around values.</p>

              <!-- BQL quick examples -->
              <div class="flex flex-wrap gap-1.5 mt-2">
                <button
                  v-for="ex in BQL_EXAMPLES" :key="ex.label"
                  type="button"
                  class="h-6 px-2 rounded text-xs border bg-[--surface] text-[--muted] hover:bg-[--surface-secondary] transition-colors"
                  @click="cfg.bql = ex.bql; bqlError = ''"
                >{{ ex.label }}</button>
              </div>

              <!-- field reference -->
              <div v-if="bqlDocsOpen" class="mt-3 rounded-md border overflow-hidden">
                <table class="w-full text-xs">
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
              <p class="text-sm font-medium text-[--foreground] mb-1.5">Content</p>
              <textarea
                v-model="cfg.text"
                rows="6"
                class="w-full text-base leading-relaxed rounded-md border bg-[--surface-secondary] text-[--foreground] px-3 py-2.5 outline-none resize-none focus:border-[--accent] transition-colors"
                placeholder="Write your note or annotation here…"
              />
            </div>

            <!-- table columns -->
            <div v-if="cfg.type === 'table' || cfg.type === 'query'" class="col-span-2">
              <p class="text-sm font-medium text-[--foreground] mb-1.5">Columns</p>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="c in COLUMN_OPTIONS" :key="c.v" type="button"
                  class="h-7 px-2.5 rounded-md text-sm font-medium border transition-colors"
                  :class="(cfg.columns || []).includes(c.v)
                    ? 'bg-[--accent-soft] border-[--accent-soft] text-[--accent-soft-foreground]'
                    : 'bg-[--surface]  text-[--muted] hover:bg-[--surface-secondary]'"
                  @click="toggleColumn(c.v)"
                >{{ c.l }}</button>
              </div>
            </div>
            <div v-if="cfg.type === 'metric'" class="col-span-2">
              <p class="text-sm font-medium text-[--foreground] mb-1.5">Accent</p>
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

    <!-- Schedule delivery -->
    <Modal :open="scheduleOpen" @update:open="v => !v && (scheduleOpen = false)" size="sm" radius="lg" hideCloseButton>
      <ModalHeader class="px-5 pt-5">
        <div class="flex items-center gap-2.5">
          <span class="size-8 rounded-lg grid place-items-center" style="background: var(--accent-soft); color: var(--accent-soft-foreground)">
            <Icon :icon="CalendarClock" :size="16" />
          </span>
          <div>
            <p class="text-md font-semibold text-[--foreground]">Schedule delivery</p>
            <p class="text-sm text-[--muted] mt-0.5">Email a KPI snapshot + link on a recurring schedule.</p>
          </div>
        </div>
      </ModalHeader>
      <ModalBody class="px-5 py-4 flex flex-col gap-3.5">
        <!-- master toggle -->
        <label class="flex items-center justify-between gap-3 cursor-pointer">
          <span class="text-base font-medium text-[--foreground]">Enable scheduled email</span>
          <button type="button" role="switch" :aria-checked="sched.enabled"
            class="relative w-9 h-5 rounded-full transition-colors shrink-0"
            :class="sched.enabled ? 'bg-[--accent]' : 'bg-[--border]'"
            @click="sched.enabled = !sched.enabled">
            <span class="absolute top-0.5 left-0.5 size-4 rounded-full bg-white shadow transition-transform" :class="sched.enabled ? 'translate-x-4' : ''" />
          </button>
        </label>

        <template v-if="sched.enabled">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <p class="text-sm font-medium text-[--foreground] mb-1.5">Frequency</p>
              <Select v-model="sched.frequency" size="sm" fullWidth>
                <SelectItem value="Daily">Daily</SelectItem>
                <SelectItem value="Weekly">Weekly</SelectItem>
                <SelectItem value="Monthly">Monthly (1st)</SelectItem>
              </Select>
            </div>
            <div v-if="sched.frequency === 'Weekly'">
              <p class="text-sm font-medium text-[--foreground] mb-1.5">Day</p>
              <Select v-model="sched.day" size="sm" fullWidth>
                <SelectItem v-for="d in WEEKDAYS" :key="d" :value="d">{{ d }}</SelectItem>
              </Select>
            </div>
            <div>
              <p class="text-sm font-medium text-[--foreground] mb-1.5">Hour (0–23)</p>
              <Select v-model="sched.hour" size="sm" fullWidth>
                <SelectItem v-for="h in 24" :key="h-1" :value="h-1">{{ String(h-1).padStart(2,'0') }}:00</SelectItem>
              </Select>
            </div>
          </div>
          <div>
            <p class="text-sm font-medium text-[--foreground] mb-1.5">Recipients</p>
            <textarea v-model="sched.recipients" rows="3"
              class="w-full text-sm rounded-lg border border-[--border] bg-[--surface-secondary] px-3 py-2 outline-none focus:border-[--accent] resize-none text-[--foreground]"
              placeholder="alice@acme.com, bob@acme.com" />
            <p class="text-xs text-[--muted] mt-1">Comma or newline separated. Delivery runs hourly server-side.</p>
          </div>
          <p v-if="report?.last_sent" class="text-xs text-[--muted]">Last sent: {{ fmtSent(report.last_sent) }}</p>
        </template>
      </ModalBody>
      <ModalFooter class="px-5 pb-5 justify-end gap-2">
        <Button variant="bordered" size="sm" @click="scheduleOpen = false">Cancel</Button>
        <Button color="primary" size="sm" @click="saveSchedule">Save schedule</Button>
      </ModalFooter>
    </Modal>

    <!-- Delete confirm -->
    <Modal :open="deleting" @update:open="v => !v && (deleting = false)" size="sm" radius="lg" hideCloseButton>
      <ModalHeader class="px-5 pt-5"><p class="text-md font-semibold text-[--foreground]">Delete report?</p></ModalHeader>
      <ModalBody class="px-5 py-4">
        <p class="text-base text-[--muted]">"{{ report?.name }}" and its {{ widgets.length }} widget{{ widgets.length === 1 ? '' : 's' }} will be permanently removed.</p>
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
import { useReportsStore, WIDGET_DEFAULTS } from '@/stores/reports'
import { getWidgetData } from '@/utils/api'
import { fmtNum } from '@/components/charts/apex/apexTheme.js'
import { PRESET_LIST, PRESETS } from '@/components/dashboard/presets.js'
import { validateBQL, BQL_FIELD_DOCS, BQL_EXAMPLES } from '@/utils/bql'
import { toast } from 'vue-sonner'
import WidgetView from '@/components/dashboard/WidgetView.vue'
import { Button, IconButton, Input, Select, SelectItem, Icon, EmptyState, Skeleton, Modal, ModalHeader, ModalBody, ModalFooter, Dropdown, DropdownItem, DropdownSeparator, DropdownLabel, ProjectScopeSelect } from '@/ui'
import {
  GripVertical, MoreHorizontal, RefreshCw, Settings, Edit3, X, Plus,
  ArrowLeft, TrendingUp, BarChart3, LayoutDashboard, Table2,
  ChevronRight, Star, Filter, Copy, Trash2, Printer, Maximize2, Clock, Check,
  TerminalSquare, BookOpen, Download, Pin, PinOff, CalendarClock,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const reportsStore = useReportsStore()

// Error boundary: a single broken widget must never blank the whole report.
// Surfaces the message so it's diagnosable instead of a silent white screen.
const renderError = ref(null)
onErrorCaptured((err) => {
  renderError.value = err?.message || String(err)
  console.error('[ReportView] render error:', err)
  try { toast.error('Report error', { description: renderError.value }) } catch {}
  return false
})

const reportId = computed(() => route.params.reportId)
const report = computed(() => reportsStore.getReport(reportId.value))
const widgets = computed(() => report.value?.widgets || [])
const wmap = computed(() => Object.fromEntries(widgets.value.map(w => [w.id, w])))

const GROUP_BYS = [
  { v: 'status', l: 'Status' }, { v: 'assignee', l: 'Assignee' }, { v: 'priority', l: 'Priority' },
  { v: 'task_type', l: 'Type' }, { v: 'epic', l: 'Epic' }, { v: 'project', l: 'Project' },
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
const PERIODS = [
  { v: 'last_7_days', l: 'Last 7 days' },
  { v: 'last_30_days', l: 'Last 30 days' },
  { v: 'last_90_days', l: 'Last 90 days' },
  { v: 'custom', l: 'Custom range' },
]
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
const PRESETS_LIST = PRESET_LIST
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
  { type: 'metric', label: 'Metric', desc: 'A live KPI — a single number from your project data', icon: TrendingUp, pill: 'blue' },
  { type: 'chart', label: 'Chart', desc: 'Bar, line, area, donut, gauge — grouped project data', icon: BarChart3, pill: 'cyan' },
  { type: 'table', label: 'Table', desc: 'Sortable, searchable, paginated list of issues with CSV export', icon: Table2, pill: 'green' },
  { type: 'query', label: 'BQL Query', desc: 'Write Batch Query Language to filter and display any tasks from your ERP data', icon: TerminalSquare, pill: 'teal' },
  { type: 'text',  label: 'Text / Note', desc: 'Free-text annotation — add context, links or headings to your report', icon: BookOpen, pill: 'gray' },
]

// ── live data, kept separate from persisted widget defs ──
const dataMap = reactive({}) // { [widgetId]: { data, loading } }
function merged(id) { const w = wmap.value[id]; const d = dataMap[id] || {}; return { ...w, data: d.data, loading: d.loading } }

// ProjectScopeSelect deals in arrays; normalise so a single-project report
// carries a plain string (not ["X"], which broke widget data fetches + the
// reportScope String prop). 'all' for empty, keep arrays only for true multi.
function normScope(s) {
  if (Array.isArray(s)) {
    if (s.length === 0) return 'all'
    if (s.length === 1) return s[0]
    return s
  }
  return s || 'all'
}

// Report-level context cascades to widgets whose own field is "inherit".
const reportScope = computed(() => normScope(report.value?.scope))
const reportPeriod = computed(() => report.value?.period || 'last_30_days')
// scope can be 'all' | single project name | string[]
function effScope(w) { return w.scope && w.scope !== 'inherit' ? w.scope : reportScope.value }
function effPeriod(w) { return w.period && w.period !== 'inherit' ? w.period : reportPeriod.value }
// Serialise scope for API: arrays must come as a JSON string since the Frappe
// whitelisted endpoint receives all args as strings.
function serialiseScope(s) {
  if (Array.isArray(s)) {
    if (s.length === 0) return 'all'
    if (s.length === 1) return s[0]           // single project → plain name
    return JSON.stringify(s)                  // genuine multi-project list
  }
  return s || 'all'
}

async function loadWidget(w) {
  if (!w) return
  if (w.type === 'table' || w.type === 'query' || w.type === 'text') return // self-loading or no data needed
  dataMap[w.id] = { data: dataMap[w.id]?.data || null, loading: true }
  try {
    let data
    if (w.type === 'preset') data = await PRESETS[w.preset].fetch({
      ...w,
      scope: serialiseScope(effScope(w)),
      period: effPeriod(w),
      milestone: report.value?.milestone || null,
      fromDate: reportFromDate.value || null,
      toDate: reportToDate.value || null,
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
  refreshKey.value++ // bump → TableWidgets reload via :key
  try { await Promise.all(widgets.value.map(loadWidget)) } finally {
    refreshing.value = false
    lastRefreshed.value = Date.now()
  }
}
// Bumped to force self-loading TableWidgets to refetch.
const refreshKey = ref(0)

// ── grid layout (local working copy synced to the store) ──
const localLayout = ref([])
const currentBp = ref('lg')
// Reconcile widgets ↔ layout: every widget MUST have a grid position, else it
// renders nowhere (blank report). Auto-positions any widget missing an entry
// and repairs the stored layout so it's not lost.
function syncLayout() {
  const existing = report.value?.layout || []
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
  if (changed) reportsStore.updateLayout(reportId.value, out)  // persist the repair
}
function onBreakpoint(bp) {
  currentBp.value = bp
  // Re-seed from the authoritative (lg) layout when returning to desktop width.
  if (bp === 'lg') syncLayout()
}
function onLayoutUpdated(l) {
  // Only persist desktop edits so auto-derived responsive layouts never overwrite the source.
  // Never wipe a non-empty report's layout (the grid emits [] before items mount).
  if (!report.value || currentBp.value !== 'lg') return
  if ((!l || !l.length) && widgets.value.length) return
  report.value.layout = l.map(x => ({ ...x }))
  reportsStore.persist()
}

const editMode = ref(false)
const catalogOpen = ref(false)

// True until the report + its widgets have resolved — gates the skeleton so the
// "Empty report" state never flashes during load.
const initializing = ref(true)
const skeletonTiles = [
  { span: 'col-span-1', h: '120px' },
  { span: 'col-span-1', h: '120px' },
  { span: 'col-span-2', h: '200px' },
  { span: 'col-span-1', h: '160px' },
  { span: 'col-span-1', h: '160px' },
]

function pillStyle(k) { const p = PILL[k] || PILL.gray; return { background: p.bg, color: p.color } }
function scopeLabel(s) {
  if (!s || s === 'inherit') s = reportScope.value
  if (s === 'all') return 'All projects'
  if (Array.isArray(s)) {
    if (s.length === 0) return 'All projects'
    if (s.length === 1) return store.projects.find(p => p.name === s[0])?.project_name || s[0]
    return `${s.length} projects`
  }
  return store.projects.find(p => p.name === s)?.project_name || s
}
function bodyH(item) { return Math.max(70, (item.h * 10 + (item.h - 1) * 12) - 30) }

function addWidget(type, extra = {}) {
  const w = reportsStore.addWidget(reportId.value, type, extra)
  catalogOpen.value = false
  syncLayout()
  loadWidget(w)
}
function addPreset(p) { addWidget('preset', { preset: p.key, size: p.defaultSize }) }
function removeWidget(id) {
  reportsStore.removeWidget(reportId.value, id)
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
  if (c.type === 'text') return 'Text / Note'
  if (c.type === 'preset') return PRESETS[c.preset]?.label || 'Report'
  return ''
})
const bqlError = ref('')
function openConfigure(id) {
  const w = wmap.value[id]
  if (!w) return
  // Normalize numeric configs to strings so HeroUI Select (string values) pre-selects them.
  cfg.value = reactive({ ...w, columns: [...(w.columns || [])], pageSize: String(w.pageSize ?? '10'), limit: String(w.limit ?? '200'), bql: w.bql || '', text: w.text || '' })
  bqlError.value = ''
  configuringId.value = id
}
function toggleColumn(key) {
  const cols = cfg.value.columns || (cfg.value.columns = [])
  const i = cols.indexOf(key)
  if (i >= 0) cols.splice(i, 1); else cols.push(key)
}
function showBqlDocs() { bqlDocsOpen.value = true }
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
    statusFilter: c.statusFilter, sortBy: c.sortBy, sortOrder: c.sortOrder,
    columns: [...(c.columns || [])], pageSize: c.pageSize, limit: c.limit, period: c.period,
    bql: c.bql,
    text: c.text,
  }
  reportsStore.updateWidgetConfig(reportId.value, configuringId.value, patch)
  loadWidget(wmap.value[configuringId.value])
  configuringId.value = null
}

// Called by QueryWidget's inline editor via @bql-change
function onWidgetBqlChange(widgetId, bql) {
  reportsStore.updateWidgetConfig(reportId.value, widgetId, { bql })
}

// Called by TextWidget's inline editor via @text-change
function onWidgetTextChange(widgetId, text) {
  reportsStore.updateWidgetConfig(reportId.value, widgetId, { text })
}

function goBack() { router.push('/workspace/reports/dashboard') }

const rootEl = ref(null)

// ── inline title rename ──
const titleEditing = ref(false)
const titleVal = ref('')
const titleInput = ref(null)
function startTitleEdit() {
  titleVal.value = report.value?.name || ''
  titleEditing.value = true
  nextTick(() => titleInput.value?.focus())
}
function commitTitle() {
  if (!titleEditing.value) return
  reportsStore.renameReport(reportId.value, titleVal.value)
  titleEditing.value = false
}

function toggleStar() { reportsStore.updateReport(reportId.value, { starred: !report.value?.starred }) }

// ── report-level filter context (cascades to inherit widgets) ──
function setScope(v) {
  const n = normScope(v)
  if (JSON.stringify(n) === JSON.stringify(reportScope.value)) return  // no-op (avoids mount re-emit loop)
  reportsStore.updateReport(reportId.value, { scope: n })
  refreshAll()
}
function setPeriod(v) { reportsStore.updateReport(reportId.value, { period: v }); refreshAll() }
const reportFromDate = computed(() => report.value?.from_date || '')
const reportToDate   = computed(() => report.value?.to_date   || '')
function setFromDate(v) { reportsStore.updateReport(reportId.value, { from_date: v }); if (reportToDate.value) refreshAll() }
function setToDate(v)   { reportsStore.updateReport(reportId.value, { to_date: v });   if (reportFromDate.value) refreshAll() }

// ── freshness clock ──
const now = ref(Date.now())
let nowTimer
const lastUpdatedLabel = computed(() => {
  const s = Math.floor((now.value - lastRefreshed.value) / 1000)
  if (s < 5) return 'just now'
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
})

// ── auto-refresh ──
const AUTO_OPTS = [{ v: 0, l: 'Off' }, { v: 30000, l: '30s' }, { v: 60000, l: '1m' }, { v: 300000, l: '5m' }]
const autoMs = ref(0)
let autoTimer
function setAuto(v) {
  autoMs.value = v
  if (autoTimer) clearInterval(autoTimer)
  if (v > 0) autoTimer = setInterval(refreshAll, v)
}
const autoLabel = computed(() => AUTO_OPTS.find(o => o.v === autoMs.value)?.l || 'Off')

// ── report actions ──
function present() { rootEl.value?.requestFullscreen?.().catch(() => {}) }
function printReport() { window.print() }
async function duplicate() {
  const id = await reportsStore.duplicateReport(reportId.value)
  if (id) router.push(`/workspace/reports/${id}`)
}
function exportTemplate() {
  const r = report.value
  if (!r) return
  const def = {
    report_name: r.name, icon: r.icon, scope: r.scope, period: r.period,
    milestone: r.milestone || null,
    widgets: (r.widgets || []).map((w) => ({ ...w })),
    layout: (r.layout || []).map((l) => ({ ...l })),
  }
  const blob = new Blob([JSON.stringify(def, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${(r.name || 'report').replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.bpreport.json`
  document.body.appendChild(a); a.click(); a.remove()
  URL.revokeObjectURL(url)
  toast.success('Template exported')
}
// ── pin to sidebar ──
function togglePin() { reportsStore.togglePinned(reportId.value) }

// ── scheduled delivery ──
const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const scheduleOpen = ref(false)
const sched = reactive({ enabled: false, frequency: 'Weekly', day: 'Monday', hour: 8, recipients: '' })
function openSchedule() {
  const r = report.value || {}
  sched.enabled = !!r.schedule_enabled
  sched.frequency = r.schedule_frequency || 'Weekly'
  sched.day = r.schedule_day || 'Monday'
  sched.hour = r.schedule_hour ?? 8
  sched.recipients = r.schedule_recipients || ''
  scheduleOpen.value = true
}
function saveSchedule() {
  reportsStore.setSchedule(reportId.value, {
    schedule_enabled: sched.enabled,
    schedule_frequency: sched.frequency,
    schedule_day: sched.day,
    schedule_hour: Number(sched.hour) || 0,
    schedule_recipients: sched.recipients,
  })
  scheduleOpen.value = false
  toast.success(sched.enabled ? 'Schedule saved' : 'Schedule turned off')
}
function fmtSent(s) {
  try { return new Date(String(s).replace(' ', 'T')).toLocaleString() } catch { return s }
}

const deleting = ref(false)
async function confirmDelete() {
  await reportsStore.deleteReport(reportId.value)
  deleting.value = false
  router.replace('/workspace/reports/dashboard')
}

async function init() {
  initializing.value = true
  await reportsStore.load()
  await reportsStore.ensureReport(reportId.value)
  if (!report.value) { router.replace('/workspace/reports/dashboard'); return }
  if (!store.projects.length) { try { await store.fetchProjects() } catch {} }
  // Pre-seed loading state so widgets render a skeleton immediately, not "No data".
  for (const w of widgets.value) {
    if (w.type !== 'table' && w.type !== 'query' && w.type !== 'text') {
      dataMap[w.id] = { data: dataMap[w.id]?.data ?? null, loading: true }
    }
  }
  syncLayout()
  // Report structure is ready — reveal the grid (widgets show their own
  // skeletons while data streams in) so the "Empty report" state never flashes.
  initializing.value = false
  await Promise.all(widgets.value.map(loadWidget))
  lastRefreshed.value = Date.now()
}
onMounted(() => {
  init()
  nowTimer = setInterval(() => { now.value = Date.now() }, 15000)
})
onUnmounted(() => { if (autoTimer) clearInterval(autoTimer); if (nowTimer) clearInterval(nowTimer) })
watch(reportId, init)
</script>

<style scoped>
.edit-ring {
  box-shadow: 0 0 0 2px color-mix(in oklab, var(--accent) 35%, transparent);
}
.menu-i {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 7px 9px; border-radius: 7px; font-size:var(--text-base); color: var(--foreground); cursor: pointer;
}
.menu-i:hover { background: var(--surface-secondary); }

.rv-date-input {
  height: 30px; padding: 0 8px; border-radius: 8px; font-size:var(--text-sm);
  border: 1px solid var(--border); background: var(--surface); color: var(--foreground);
  cursor: pointer; outline: none; transition: border-color .15s;
}
.rv-date-input:focus { border-color: var(--accent); }
</style>
