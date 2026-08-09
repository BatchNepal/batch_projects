<template>
  <div ref="rootEl" class="flex flex-col h-full overflow-hidden bg-surface">
    <!-- Header — two tiers: identity+authorship (row 1), then ONE toolbar of
         same-weight action pills (row 2). No back arrow — nothing else in
         this app uses one (Board.vue/ProjectSummary.vue/ListView.vue all
         rely on the persistent sidebar for navigation); a browser-style
         back button doesn't answer "back to where?" in a rail-nav SPA. -->
    <header class="shrink-0  flex flex-col border-b bg-surface">
      <!-- Row 1: identity + authorship + freshness -->
      <div class=" pt-3  px-6">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-1 ">
            <div class="mb-3" >
              <svg stroke="currentColor" fill="#fd9038" 
              stroke-width="0" viewBox="0 0 24 24" 
              height="18px" width="18px" 
              xmlns="http://www.w3.org/2000/svg"><path d="M4 13h6a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1zm-1 7a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v4zm10 0a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-7a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v7zm1-10h6a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v5a1 1 0 0 0 1 1z"></path></svg>
            </div>
            <div class="grid">
              <div>
              <input v-if="titleEditing" ref="titleInput" v-model="titleVal"
              class="text-[16px] font-medium text-[--foreground] bg-transparent outline-none border-b border-accent min-w-[140px] max-w-[420px]"
              @blur="commitTitle" @keydown.enter="commitTitle" @keydown.esc="titleEditing = false" />
               <h1 v-else
              class="text-[16px] font-medium text-[--foreground] tracking-tight truncate max-w-[420px] cursor-pointer rounded-md px-1.5 py-0.5 -mx-1.5 hover:bg-default transition-colors"
              title="Click to rename" @click="startTitleEdit">{{ dashboard?.name || 'Dashboard' }}</h1>
            </div> 
            <span class="text-[10px] text-[--muted] font-medium  -ml-5 -mt-0.5">
              Last Updated At: {{ lastUpdatedLabel }}
            </span>
            </div>
           
            <!-- Authorship is metadata, not a control — plain text, no pill/border,
                so it reads as read-only next to the real action buttons below. -->
            <IconButton variant="light" class="mb-[12px]" size="xs" :class="dashboard?.starred ? 'text-warning' : 'text-muted'"
              title="Star dashboard" @click="toggleStar">
              <Star :size="14" :fill="dashboard?.starred ? 'currentColor' : 'none'" />
            </IconButton>
          </div>
          <div>
            <Dropdown placement="bottom-end" :side-offset="6">
              <template #trigger="{ open: isOpen }">
                <IconButton variant="outline" size="sm" :class="{ 'bg-surface-secondary text-foreground': isOpen }"
                  title="More">
                  <Icon :icon="MoreHorizontal" :size="16" />
                </IconButton>
              </template>

              <!-- class="dv-more-item" below gives this ONE menu extra
                 breathing room (see .dv-more-item in <style>) without
                 touching the shared DropdownItem.vue used by every other
                 dropdown in the app. -->
              <DropdownItem v-if="!editMode" class="dv-more-item" @click="editMode = true">
                <template #startContent>
                  <Icon :icon="Edit3" :size="14" class="text-gray-800 shrink-0" />
                </template>
                Edit Dashboard
              </DropdownItem>
              <DropdownItem class="dv-more-item" @click="present">
                <template #startContent>
                  <Icon :icon="Maximize2" :size="14" class="text-gray-800 shrink-0" />
                </template>
                Present
              </DropdownItem>

              <DropdownSeparator />
              <DropdownLabel>Auto-refresh</DropdownLabel>
              <DropdownItem v-for="o in AUTO_OPTS" :key="o.v" class="dv-more-item" :close-on-click="false"
                @click="setAuto(o.v)">
                {{ o.l }}
                <template #endContent>
                  <Icon v-if="autoMs === o.v" :icon="Check" :size="13" class="text-[--accent] shrink-0" />
                </template>
              </DropdownItem>

              <DropdownSeparator />
              <DropdownItem class="dv-more-item" @click="startTitleEdit">
                <template #startContent>
                  <Icon :icon="Edit3" :size="14" class="text-gray-800 shrink-0" />
                </template>
                Rename
              </DropdownItem>
              <DropdownItem class="dv-more-item" @click="duplicate">
                <template #startContent>
                  <Icon :icon="Copy" :size="14" class="text-gray-800 shrink-0" />
                </template>
                Duplicate
              </DropdownItem>
              <DropdownItem class="dv-more-item" @click="togglePin">
                <template #startContent>
                  <Icon :icon="dashboard?.pinned ? PinOff : Pin" :size="14" class="text-gray-800 shrink-0" />
                </template>
                {{ dashboard?.pinned ? 'Unpin from sidebar' : 'Pin to sidebar' }}
              </DropdownItem>
              <DropdownItem class="dv-more-item" @click="printDashboard">
                <template #startContent>
                  <Icon :icon="Printer" :size="14" class="text-gray-800 shrink-0" />
                </template>
                Export / Print
              </DropdownItem>

              <DropdownSeparator />
              <DropdownItem class="dv-more-item" color="danger" @click="deleting = true">
                <template #startContent>
                  <Icon :icon="Trash2" :size="14" class="text-red-600 shrink-0" />
                </template>
                Delete dashboard
              </DropdownItem>
            </Dropdown>
          </div>
        </div>

      </div>

      


      <!-- Row 2: ONE toolbar — every control here shares the same bordered-
           pill recipe (same Button variant="bordered" props) so nothing looks like it wandered
           in from a different design system. "+ Widget" is bordered, not a
           solid/primary CTA — authoring the dashboard isn't the #1 thing a
           user does on a board they're here to READ. -->
      <div class="flex border h-fit py-2 mt-2.5 px-6 items-center gap-1.5 ">
        <!-- By text -->
        <div class="text-[12px] border px-3 py-1 rounded-md shadow-sm flex  gap-1 items-center text-[--muted]">
          <svg stroke="currentColor" class="mb-[2px]" fill="#101112" stroke-width="0" viewBox="0 0 24 24" height="14px" width="14px"
            xmlns="http://www.w3.org/2000/svg">
            <path fill="none" d="M0 0h24v24H0z"></path>
            <path
              d="M12 5.9a2.1 2.1 0 1 1 0 4.2 2.1 2.1 0 0 1 0-4.2m0 9c2.97 0 6.1 1.46 6.1 2.1v1.1H5.9V17c0-.64 3.13-2.1 6.1-2.1M12 4C9.79 4 8 5.79 8 8s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4m0 9c-2.67 0-8 1.34-8 4v3h16v-3c0-2.66-5.33-4-8-4">
            </path>
          </svg>
          <p class="font-medium text-gray-600">
            By {{ dashboard?.owner_full_name || dashboard?.owner }}
          </p>
        </div>
        <Button variant="outline" size="sm"  @click="toggleShare">
          <template #startContent>
            <Icon :icon="dashboard?.visibility === 'workspace' ? Users : Lock" :size="13" />
          </template>
          {{ dashboard?.visibility === 'workspace' ? 'Shared' : 'Private' }}
        </Button>

        <!-- Filters — hidden when every widget reads workspace-scoped data
             (Leads/Deals/...): a project picker that filters nothing reads
             as "mixed up", not a genuine workspace/company overview. Labeled
             "Project" explicitly (not a bare funnel icon) — this dashboard
             can mix Task and Lead/Deal widgets, so it must be clear this
             filter only scopes the project-backed ones, not everything on
             the page. -->
        <div v-if="hasProjectScopedWidgets" class="flex items-center gap-1.5 shrink-0"
          title="Scopes project-backed widgets only — filters cascade to widgets set to Inherit">
          <ProjectScopeSelect :model-value="dashboardScope" :projects="store.projects" @update:model-value="setScope" />
        </div>
       

        <!-- ⋯ more — divider anchors it to the toolbar instead of floating
             in empty space at the far edge. Edit Dashboard, present, rename,
             duplicate, pin, export, delete. -->
        <div class="ml-auto  shrink-0 flex items-center gap-1.5">
          <!-- Freshness lives ONLY here, as a tooltip on the refresh trigger —
             not as standing text under the title. -->
          <!-- Done is the one legitimate solid/primary button here — unlike
             "+ Widget", exiting edit mode is a real, time-boxed action the
             user must take once they've entered it (there's no other way
             back: the ⋯ menu's "Edit Dashboard" only ever turns edit mode
             ON, see below — this was previously missing entirely, leaving
             edit mode with no visible exit once you entered it). -->
          <Button v-if="editMode" color="primary" size="xs" @click="editMode = false">
            <template #startContent>
              <Icon :icon="Check" :size="13" />
            </template>Done editing
          </Button>
          <Button variant="bordered" class="bg-[#266df0] hover:bg-[#215bc4] text-white" size="xs" @click="openAddWidget">
            <template #startContent>
              <Icon :icon="Plus" :size="13" />
            </template>Widget
          </Button>
          <Button class="ml-auto shrink-0" variant="outline" size="sm"
            :title="`Updated ${lastUpdatedLabel} — click to refresh`" @click="refreshAll">
            <Icon :icon="RefreshCw" :size="11"
              :class="refreshing ? 'animate-spin text-[--accent]' : 'text-gray-600 font-medium'" />
          </Button>
        </div>
      </div>
    </header>

    <!-- Canvas — horizontal scroll, not clip, not squeeze: a row of Column
         widgets whose total width exceeds the viewport used to just get cut
         off at the edge (no overflow-x at all). Now the grid's own pixel
         canvas GROWS past the viewport (gridWrapperStyle below) instead of
         re-quantizing colWidth smaller to force everything into one screen
         — 10 full-height Column widgets stay exactly as wide as 3 do, you
         scroll sideways for the rest, real Kanban-board behavior. ref=
         canvasEl measures THIS element (the flex-sized, viewport-driven
         outer box) — never the grid wrapper inside it, which is
         deliberately allowed to grow wider than its parent. -->
    <div ref="canvasEl" class="flex-1 overflow-auto px-5 pt-3 pb-5 bg-[#f9f9f9df]">
      <div v-if="renderError"
        class="mb-4 rounded-lg border border-[--danger-soft] bg-[--danger-soft] px-4 py-3 text-[13px] text-[--danger-soft-foreground]">
        <p class="font-semibold mb-0.5">This dashboard hit an error while rendering</p>
        <p class="text-[12px] opacity-90 break-words">{{ renderError }}</p>
      </div>

      <!-- Loading — prevents the "Empty dashboard" flash before the dashboard
           and its widget list resolve. Used to be a hardcoded 5-tile fake
           grid (fixed spans/heights bearing no relation to the real saved
           layout) that got swapped for the REAL grid the instant this
           resolved — since by then localLayout/widgets are already fully
           known (syncLayout() runs right before initializing flips false,
           a few lines below), that swap was a guaranteed reflow on almost
           every load: the boxes themselves visibly jumped to different
           positions/sizes. A neutral spinner never has a "shape" to clash
           with the real grid — initializing's own window is brief (just the
           dashboard+widget-list fetch, not widget DATA), so there's nothing
           here to preview anyway. Each widget's own internal skeleton
           (ColumnWidget/KanbanWidget/etc, already fixed to track real
           content shape) takes over from here for the actual data fetch,
           inside boxes that never move again. -->
      <div v-if="initializing && !renderError" class="h-64 flex items-center justify-center">
        <Icon :icon="Loader2" :size="20" class="animate-spin text-muted" />
      </div>

      <EmptyState v-else-if="!widgets.length && !renderError" :icon="LayoutDashboard" title="Empty dashboard"
        description="Add a column, chart, or table widget to build a live view of your project data.">
        <template #action>
          <Button color="primary" size="sm" @click="catalogOpen = true">
            <template #startContent>
              <Icon :icon="Plus" :size="15" />
            </template>
            Add your first widget
          </Button>
        </template>
      </EmptyState>

      <!-- col-num 48 base unit (was 12): grid-layout-plus has no freeform/
           pixel-position mode — its whole engine is snap-to-grid + auto-
           collision — so the closest a config change gets to "free like
           Excalidraw" is a much finer grid (~10-15px steps instead of
           ~110px) plus prevent-collision so widgets stop shoving each other
           around. 4x was chosen to stay safely clear of colWidth =
           (containerWidth - margin*(cols+1))/cols going negative at this
           margin (12px) down to quite narrow containers — see
           stores/dashboards.js' WIDGET_DEFAULTS comment for the full
           picture (defaults authored directly at this new scale, and a
           one-time patch rescales existing saved dashboards to match). -->
      <!-- responsive/cols/breakpoints REMOVED — this was silently dropping
           to `cols: 10` (then 6, 4, 2) any time the CANVAS's own measured
           width fell under 1200px (not the window — the canvas, which is
           already narrower than the window once you subtract the sidebar),
           which is nearly always. Below that col-num=10 threshold every
           widget's real width (authored in 48-col units, e.g. w=16) exceeds
           the entire available column count on its own, so nothing could
           sit side-by-side — everything got forced to fill-width and stack.
           effectiveColNum/gridWrapperStyle below now handle screen-width
           adaptation instead: real Kanban-board behavior — colWidth (pixel
           size of one grid unit) is pinned to what 1/48th of the CANVAS
           naturally measures, and stays that size no matter how many
           widgets you place; content past 48 units' worth grows the grid's
           OWN pixel width past the canvas's, which scrolls (overflow-auto
           above) instead of either clipping or re-quantizing itself to
           fewer, coarser columns. -->
      <!-- prevent-collision is now false — is-resizable is false too (see
           the custom resize handle below), so this prop only ever governs
           DRAG/move now. Reading grid-layout-plus's own move handler (bn()):
           with preventCollision true it doesn't push on collision, it hard-
           REVERTS the entire drag back to its start position the instant it
           would overlap anything — zero visual feedback, a drop "does
           nothing". False makes it push the occupied widget down instead
           (the vertical-compact already on below then pulls things back up
           to close any gap left behind) — the expected canvas behaviour of
           "drop a small widget onto a big one, it makes room". -->
      <div v-else :style="gridWrapperStyle">
      <GridLayout ref="gridLayoutRef" v-model:layout="localLayout" :col-num="effectiveColNum" :row-height="10" :margin="[12, 12]"
        :is-draggable="editMode" :is-resizable="false" :is-bounded="false" :vertical-compact="true"
        :prevent-collision="false"
        :use-css-transforms="true" @layout-updated="onLayoutUpdated"
        :class="{ 'dv-editing': editMode }">
        <GridItem v-for="item in localLayout" :key="item.i" :x="item.x" :y="item.y" :w="item.w" :h="item.h" :i="item.i"
          :min-w="item.minW" :min-h="item.minH" drag-allow-from=".drag-handle"
          :class="{ 'dv-resizing-item': customResizing === item.i }">
          <div v-if="wmap[item.i]"
            class="widget-card group hide-scrollbar rounded-xl  shadow-sm relative h-full flex flex-col overflow-hidden transition-[border-color] duration-200"
            :class="[
              wmap[item.i].borderless ? 'bg-transparent' : (wmap[item.i].type === 'column' ? 'bg-surface border rounded-lg  widget-card-column' : 'bg-surface border border-border shadow-sm rounded-lg'),
              editMode ? 'edit-ring' : (wmap[item.i].borderless ? '' : 'hover:border-border-secondary'),
            ]" :style="wmap[item.i].color ? { background: wmap[item.i].color } : {}">
            <!-- drag handle -->
            <div class="drag-handle absolute top-4  right-12  z-10  cursor-grab active:cursor-grabbing text-[--muted] transition-opacity"
              :class="editMode ? 'opacity-60 hover:opacity-80 ' : 'opacity-0 pointer-events-none'">
              <Icon :icon="GripVertical" :size="18" />
            </div>
            <!-- Free resize handle — replaces grid-layout-plus's own
                 is-resizable (now off). Reading its source: prevent-
                 collision doesn't reject a resize, it CLAMPS growth to
                 stop exactly at the first blocking neighbor's edge — so
                 growing past one always meant pre-moving it first, the
                 exact friction reported. The alternative (prevent-
                 collision off) cascades a push-down through the compact
                 step on every resize instead. Neither is real freedom.
                 This handle mutates localLayout directly: no clamp, no
                 forced push — temporary overlap is fine (z-index bump via
                 dv-resizing-item above), you just drag the other widget
                 clear afterward if you don't like where it landed. -->
            <div v-if="editMode" class="dv-resize-handle" @pointerdown.stop="onCustomResizeStart($event, item)" />
            <!-- kebab -->
            <div class="absolute top-2.5 right-2.5 z-20" @click.stop>
              <Dropdown placement="bottom-end">
                <template #trigger="{ toggle, open }">
                  <button
                    class="w-7 h-7 rounded-md bg-surface border border-border flex items-center justify-center text-muted hover:text-foreground hover:bg-surface-secondary hover:border-border opacity-0 group-hover:opacity-100 transition-[background-color,color,border-color,opacity] cursor-pointer shadow-xs outline-none focus-visible:shadow-focus"
                    :class="{ '!opacity-100 bg-surface-secondary border-border text-foreground': open }"
                    @click="toggle">
                    <Icon :icon="MoreHorizontal" :size="15" />
                  </button>
                </template>
                <DropdownItem class="font-medium" @click="loadWidget(wmap[item.i])"><template #startContent>
                    <Icon :icon="RefreshCw" :size="14" class="text-gray-700" />
                  </template>Refresh</DropdownItem>
                <DropdownItem class="font-medium" @click="openConfigure(item.i)"><template #startContent>
                    <Icon :icon="Settings" :size="14" class="text-gray-700" />
                  </template>Configure</DropdownItem>
                <DropdownItem v-if="wmap[item.i].type === 'column'" class="font-medium" @click="openRowDesigner(item.i)"><template #startContent>
                    <Icon :icon="Rows3" :size="14" class="text-gray-700" />
                  </template>Customize row</DropdownItem>
                <DropdownItem class="font-medium" @click="openWidgetPage(item.i)"><template #startContent>
                    <Icon :icon="ExternalLink" :size="14" class="text-gray-700" />
                  </template>Open as page
                </DropdownItem>
                <DropdownSeparator />
                <DropdownItem class="font-medium" color="danger" @click="removeWidget(item.i)"><template #startContent>
                    <Icon :icon="X" :size="14" class="text-red-600" />
                  </template>Remove widget</DropdownItem>
              </Dropdown>
            </div>
            <!-- body — column owns its own internal spacing (see
                 ColumnWidget.vue), every other type expects this wrapper's
                 padding, same as before padding became per-widget
                 configurable (now removed, see bodyPadding()'s comment). -->
            <div class="flex-1 min-h-0 overflow-hidden hide-scrollbar"
              :style="wmap[item.i]?.type === 'column' ? {} : bodyPadding(merged(item.i))">
              <WidgetView :widget="merged(item.i)" :height="bodyH(item)" :scope-label="scopeLabel" :fmt="fmtNum"
                :pill="PILL" :report-scope="dashboardScope" :refresh-key="refreshKey"
                @bql-change="(bql) => onWidgetBqlChange(item.i, bql)"
                @text-change="(t) => onWidgetTextChange(item.i, t)" @configure="openConfigure(item.i)" />
            </div>
          </div>
        </GridItem>
      </GridLayout>
      </div>
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
          <button v-for="c in CATALOGUE" :key="c.type"
            class="flex items-center gap-3 p-3 border rounded-lg text-left hover:bg-[--surface-secondary] transition-colors"
            @click="addWidget(c.type)">
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
    <Modal :open="!!configuringId" @update:open="v => !v && (configuringId = null)" size="md" radius="lg"
      hideCloseButton>
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
                <p class="text-[11.5px] text-[--muted] mt-0.5">Hide the border and shadow so it reads as part of the
                  page.</p>
              </div>
              <Switch v-model="cfg.borderless" />
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

            <!-- metric multi-source mode — an alternative to the task
                 group_by/metric rollup above: sum FILTERED RECORD COUNTS
                 across one or more doctypes (e.g. open Leads + active Deals
                 as one KPI). Adding at least one source here takes over the
                 widget's number; group_by/metric above stay untouched, not
                 deleted, so removing every source falls straight back to
                 the original behavior with nothing lost. -->
            <div v-if="cfg.type === 'metric'" class="col-span-2 flex flex-col gap-2 pt-1">
              <div class="flex items-center justify-between">
                <label class="text-[12px] font-medium text-[--foreground]">Sources
                  <span class="text-[11px] text-[--muted] font-normal">— optional, counts records instead of the task metric above</span>
                </label>
                <button type="button" class="text-[11px] font-semibold text-[--accent] hover:underline shrink-0"
                  @click="addMetricSource">+ Add source</button>
              </div>
              <div v-for="(src, i) in (cfg.sources || [])" :key="i"
                class="border border-[--border] rounded-lg p-2.5 flex flex-col gap-2">
                <div class="flex items-center gap-2">
                  <Select :model-value="src.doctype" class="flex-1" size="sm" label="Doctype"
                    @update:model-value="v => onMetricSourceDoctype(src, v)">
                    <SelectSection v-for="g in groupedSources" :key="g.group" :label="g.group">
                      <SelectItem v-for="d in g.items" :key="d.doctype" :value="d.doctype">{{ d.label }}</SelectItem>
                    </SelectSection>
                  </Select>
                  <button type="button"
                    class="w-8 h-8 mt-4 shrink-0 rounded-md grid place-items-center text-[--muted] hover:text-danger hover:bg-[--surface-secondary] transition-colors"
                    title="Remove source" @click="removeMetricSource(i)">
                    <Icon :icon="X" :size="14" />
                  </button>
                </div>
                <FilterBuilder v-if="src.doctype" :doctype="src.doctype" v-model="src.filters" />
              </div>
            </div>

            <!-- doctype picker — 'column' and 'kanban' widgets can source from
                 any whitelisted doctype the user can actually read (the
                 backend filters the list by real Frappe read permission).
                 Sectioned by domain: a flat list of ~28 sources is a wall. -->
            <Select v-if="cfg.type === 'column' || cfg.type === 'kanban'" v-model="cfg.doctype" class="col-span-2"
              label="Source">
              <SelectSection v-for="g in groupedSources" :key="g.group" :label="g.group">
                <SelectItem v-for="d in g.items" :key="d.doctype" :value="d.doctype">{{ d.label }}</SelectItem>
              </SelectSection>
            </Select>

            <!-- One filtering surface for every source. The Task-only quick
                 picker (three bespoke Selects for assignee/status/priority)
                 is gone: it could only ever express those three things, only
                 on BP Task, and sat next to a filter builder that could
                 express all three plus everything else — two systems for one
                 job with no hint which took precedence. `assignee` became a
                 synthetic filter field (BP Task keeps assignees in a child
                 table, so introspection can't see it), which is what makes
                 the builder a complete replacement rather than a regression.
                 Widgets saved with a quick filter are converted on open —
                 see openConfigure. -->
            <Select v-if="cfg.type === 'column' && isTaskDoctype(cfg.doctype)"
              v-model="cfg.statusFilter" class="col-span-2" label="Lifecycle">
              <SelectItem v-for="s in STATUS_FILTERS" :key="s.v" :value="s.v">{{ s.l }}</SelectItem>
            </Select>

            <div v-if="cfg.type === 'column'" class="col-span-2">
              <label class="text-[12px] font-medium text-[--foreground] mb-1 block">
                Filters
                <span class="text-[11px] text-[--muted] font-normal">— any field on {{ widgetSourceLabel(cfg.doctype) }}</span>
              </label>
              <FilterBuilder :doctype="cfg.doctype || 'BP Task'" v-model="cfg.filters" />
              <p v-if="quickFilterConverted" class="mt-1.5 text-[11px] text-[--accent]">
                This widget's old quick filter was converted into the filter above.
              </p>
            </div>

            <!-- Group by — what the sticky sub-headers inside the column
                 actually are. This was hardcoded to the due-date time rail
                 with no way to change it, so grouping by status, epic,
                 assignee, project or any other field was simply impossible. -->
            <Select v-if="cfg.type === 'column'" v-model="cfg.group_by" class="col-span-2" label="Group rows by">
              <SelectItem value="date">{{ dateGroupLabel }}</SelectItem>
              <SelectItem value="none">No grouping — one flat list</SelectItem>
              <SelectSection label="By field">
                <SelectItem v-for="f in groupableFields" :key="f.fieldname" :value="f.fieldname">{{ f.label }}</SelectItem>
              </SelectSection>
            </Select>

            <!-- kanban — group-by drives the auto-generated columns, plus
                 optional filters scoping which records appear at all. BP Task
                 boards were excluded from this picker and hardwired to
                 status, so a Task kanban by priority/epic/assignee simply
                 wasn't expressible; they get the same field-driven picker as
                 every other source now. Dragging still only writes when
                 grouping by status — see KanbanWidget's canDrag. -->
            <template v-if="cfg.type === 'kanban'">
              <Select v-model="cfg.group_by" class="col-span-2" label="Group columns by">
                <SelectItem v-for="f in kanbanGroupByFields" :key="f.fieldname" :value="f.fieldname">{{ f.label }}
                </SelectItem>
              </Select>
              <div class="col-span-2">
                <label class="text-[12px] font-medium text-[--foreground] mb-1.5 block">Filters</label>
                <FilterBuilder :doctype="cfg.doctype || 'BP Task'" v-model="cfg.filters" />
              </div>
            </template>

            <!-- Kanban keeps the simple label-chip picker. A column widget's
                 row content is owned by the much richer row designer
                 ("Customize row" in the widget's own menu), so the old
                 "Row labels — up to 3" chips are gone from here: two
                 settings competing over the same line, one of them silently
                 capped at three, is worse than one that isn't. -->
            <div v-if="cfg.type === 'kanban' && !isTaskDoctype(cfg.doctype)" class="col-span-2">
              <label class="text-[12px] font-medium text-[--foreground] mb-1.5 block">Card labels</label>
              <div class="flex flex-wrap gap-1.5">
                <button v-for="f in sourceFields" :key="f.fieldname" type="button"
                  class="h-7 px-2.5 rounded-md text-[12px] font-medium border transition-colors" :class="(cfg.label_fields || []).includes(f.fieldname)
                    ? 'bg-[--accent-soft] border-[--accent-soft] text-[--accent-soft-foreground]'
                    : 'bg-[--surface] text-[--muted] hover:bg-[--surface-secondary]'"
                  @click="toggleLabelField(f.fieldname)">{{ f.label }}</button>
              </div>
            </div>
            <!-- Which date the row's right-aligned date column shows. Still
                 relevant for a column widget even without the label chips —
                 and it's what "Group by date" groups on. -->
            <Select v-if="(cfg.type === 'kanban' || cfg.type === 'column') && !isTaskDoctype(cfg.doctype)"
              v-model="cfg.date_field" class="col-span-2" label="Date field">
              <SelectItem value="">None (hide date)</SelectItem>
              <SelectItem v-for="f in dateFieldOptions" :key="f.fieldname" :value="f.fieldname">{{ f.label }}
              </SelectItem>
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

            <!-- scope: all types except query (uses BQL project= clause) and text
                 (no data) — and except kanban/column widgets sourced from a
                 workspace-scoped doctype (Lead, Opportunity, ...), which have
                 no project dimension to scope by at all. -->
            <div
              v-if="cfg.type !== 'query' && cfg.type !== 'text' && cfg.type !== 'header' && isProjectScopedSource(cfg.doctype)"
              class="col-span-2 flex flex-col gap-1">
              <!-- "Projects", not "Scope": this is THE place a widget's
                   project boundary is set, and naming it after the thing it
                   selects makes that obvious next to the field-level
                   filters above. -->
              <label class="text-[12px] font-medium text-[--foreground]">
                Projects
                <span class="ml-1 text-[11px] text-[--muted] font-normal">— which projects this widget reads: one,
                  several, or inherit from the dashboard</span>
              </label>
              <div class="flex items-center gap-2">
                <button type="button"
                  class="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-lg border text-xs font-medium transition-colors cursor-pointer outline-none"
                  :class="cfg.scope === 'inherit'
                    ? 'bg-primary border-primary text-white'
                    : 'bg-[--surface-secondary]  text-[--foreground] hover:bg-[--surface-hover]'"
                  @click="cfg.scope = 'inherit'">Inherit</button>
                <ProjectScopeSelect :model-value="cfg.scope === 'inherit' ? 'all' : cfg.scope"
                  :projects="store.projects" @update:model-value="v => { cfg.scope = v }" />
              </div>
            </div>
            <p v-else-if="cfg.type !== 'query' && cfg.type !== 'text' && cfg.type !== 'header'"
              class="col-span-2 text-[12px] text-[--muted]">
              {{ widgetSourceLabel(cfg.doctype) }} isn't project-scoped — this widget shows workspace-wide data.
            </p>

            <!-- BQL query editor -->
            <div v-if="cfg.type === 'query'" class="col-span-2">
              <div class="flex items-center justify-between mb-1.5">
                <p class="text-[12px] font-medium text-[--foreground]">Batch Query Language (BQL)</p>
                <button class="flex items-center gap-1 text-[11px] text-[--accent] hover:opacity-80 transition-opacity"
                  @click.prevent="bqlDocsOpen = !bqlDocsOpen">
                  <Icon :icon="BookOpen" :size="12" />{{ bqlDocsOpen ? 'Hide' : 'Field reference' }}
                </button>
              </div>
              <textarea v-model="cfg.bql" rows="4"
                class="w-full text-[12px] font-mono leading-relaxed rounded-md border px-3 py-2.5 outline-none resize-none transition-colors bg-[--surface-secondary] text-[--foreground]"
                :class="bqlError ? 'border-[--danger]' : ' focus:border-[--accent]'"
                placeholder='project = "PROJ" AND status = "Open" AND assignee = "me"' @input="bqlError = ''" />
              <p v-if="bqlError" class="text-[11px] text-[--danger] mt-1">{{ bqlError }}</p>
              <p v-else class="text-[11px] text-[--muted] mt-1">Combine filters with AND. Use quotes around values.</p>

              <!-- BQL quick examples -->
              <div class="flex flex-wrap gap-1.5 mt-2">
                <button v-for="ex in BQL_EXAMPLES" :key="ex.label" type="button"
                  class="h-6 px-2 rounded text-[11px] border bg-[--surface] text-[--muted] hover:bg-[--surface-secondary] transition-colors"
                  @click="cfg.bql = ex.bql; bqlError = ''">{{ ex.label }}</button>
              </div>

              <!-- field reference -->
              <div v-if="bqlDocsOpen" class="mt-3 rounded-md border overflow-hidden">
                <table class="w-full text-[11px]">
                  <thead>
                    <tr class="bg-[--surface-secondary]">
                      <th class="px-3 py-1.5 text-left font-semibold text-[--muted] border-b ">Field</th>
                      <th class="px-3 py-1.5 text-left font-semibold text-[--muted] border-b ">Example</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="f in BQL_FIELD_DOCS" :key="f.field"
                      class="border-b last:border-0 hover:bg-[--surface-secondary]">
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
              <textarea v-model="cfg.text" rows="6"
                class="w-full text-[13px] leading-relaxed rounded-md border bg-[--surface-secondary] text-[--foreground] px-3 py-2.5 outline-none resize-none focus:border-[--accent] transition-colors"
                placeholder="Write your note or annotation here…" />
            </div>

            <!-- header widget — optional link shown on the right -->
            <template v-if="cfg.type === 'header'">
              <Input class="col-span-2" v-model="cfg.link_url" label="Link URL" placeholder="https://… (optional)" />
              <Input v-if="cfg.link_url" class="col-span-2" v-model="cfg.link_label" label="Link label"
                placeholder="View" />
            </template>

            <!-- table columns -->
            <div v-if="cfg.type === 'table' || cfg.type === 'query'" class="col-span-2">
              <p class="text-[12px] font-medium text-[--foreground] mb-1.5">Columns</p>
              <div class="flex flex-wrap gap-1.5">
                <button v-for="c in COLUMN_OPTIONS" :key="c.v" type="button"
                  class="h-7 px-2.5 rounded-md text-[12px] font-medium border transition-colors" :class="(cfg.columns || []).includes(c.v)
                    ? 'bg-[--accent-soft] border-[--accent-soft] text-[--accent-soft-foreground]'
                    : 'bg-[--surface]  text-[--muted] hover:bg-[--surface-secondary]'" @click="toggleColumn(c.v)">{{
                  c.l }}</button>
              </div>
            </div>
            <div v-if="cfg.type === 'metric'" class="col-span-2">
              <p class="text-[12px] font-medium text-[--foreground] mb-1.5">Accent</p>
              <div class="flex gap-2">
                <button v-for="(p, k) in PILL" :key="k" class="w-6 h-6 rounded-md border-2 transition-colors"
                  :class="cfg.colorScheme === k ? 'border-[--foreground]' : 'border-transparent'"
                  :style="{ background: p.color }" @click="cfg.colorScheme = k" />
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

    <!-- Customize row (Column widgets only) — sample row comes from a fresh
         fetch mirroring ColumnWidget.vue's own query (same scope/filters),
         not the live widget instance, so it works even for a widget that
         hasn't finished loading (or has no rows loaded at all) yet. -->
    <RowDesignerModal
      v-if="rowDesignerId" :open="!!rowDesignerId" :doctype="rowDesignerDoctype" :is-task="rowDesignerIsTask"
      :project="rowDesignerProject"
      :template="wmap[rowDesignerId]?.row_template || null" :sample-rows="rowDesignerSamples"
      @update:open="v => !v && (rowDesignerId = null)" @save="saveRowTemplate"
    />

    <!-- Delete confirm -->
    <Modal :open="deleting" @update:open="v => !v && (deleting = false)" size="sm" radius="lg" hideCloseButton>
      <ModalHeader class="px-5 pt-5">
        <p class="text-[15px] font-semibold text-[--foreground]">Delete dashboard?</p>
      </ModalHeader>
      <ModalBody class="px-5 py-4">
        <p class="text-[13px] text-[--muted]">"{{ dashboard?.name }}" and its {{ widgets.length }} widget{{
          widgets.length
            === 1 ? '' : 's' }} will be permanently removed.</p>
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
import { getWidgetData, getMembers, getWidgetSourceDoctypes, getWidgetSourceFields, getMultiSourceCount, getColumnWidgetData, getDoctypeColumnData } from '@/utils/api'
import { fmtNum } from '@/components/charts/apex/apexTheme.js'
import { PRESET_LIST, PRESETS } from '@/components/dashboard/presets.js'
import { PRIORITIES } from '@/utils/constants.js'
import { validateBQL, BQL_FIELD_DOCS, BQL_EXAMPLES } from '@/utils/bql'
import { toast } from 'vue-sonner'
import WidgetView from '@/components/dashboard/WidgetView.vue'
import FilterBuilder from '@/components/dashboard/FilterBuilder.vue'
import RowDesignerModal from '@/components/dashboard/RowDesignerModal.vue'
import { Button, IconButton, Input, Select, SelectItem, SelectSection, Icon, EmptyState, Modal, ModalHeader, ModalBody, ModalFooter, Dropdown, DropdownItem, DropdownSeparator, DropdownLabel, ProjectScopeSelect, Switch } from '@/ui'
import {
  GripVertical, MoreHorizontal, RefreshCw, Settings, Edit3, X, Plus,
  TrendingUp, BarChart3, LayoutDashboard, Table2, Columns3,
  Star, Copy, Trash2, Printer, Maximize2, Check, Loader2,
  TerminalSquare, BookOpen, Pin, PinOff, Kanban, Heading, ExternalLink, Lock, Users, Rows3,
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
  try { toast.error('Dashboard error', { description: renderError.value }) } catch { }
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
getMembers(null).then(res => { workspaceMembers.value = Array.isArray(res) ? res : (res.members || []) }).catch(() => { })
const ownerLabel = computed(() => {
  const owner = dashboard.value?.owner
  if (!owner) return '—'
  return workspaceMembers.value.find(m => m.user === owner)?.full_name || owner
})

const GROUP_BYS = [
  { v: 'status', l: 'Status' }, { v: 'assignee', l: 'Assignee' }, { v: 'priority', l: 'Priority' },
  { v: 'task_type', l: 'Type' }, { v: 'epic', l: 'Epic' }, { v: 'project', l: 'Project' },
]
// No 'project' entry: which projects a widget reads is the Projects control,
// which does it better anyway (several projects, or inherit from the
// dashboard). get_column_widget_data still understands filter_by='project'
// so dashboards saved before this keep working — openConfigure migrates them
// onto Projects the first time they're edited.
const COLUMN_BYS = [
  { v: 'assignee', l: 'One person' }, { v: 'status', l: 'One status' }, { v: 'priority', l: 'One priority' },
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
  blue: { bg: 'var(--accent-soft)', color: 'var(--accent-soft-foreground)' },
  green: { bg: 'var(--success-soft)', color: 'var(--success-soft-foreground)' },
  amber: { bg: 'var(--warning-soft)', color: 'var(--warning-soft-foreground)' },
  red: { bg: 'var(--danger-soft)', color: 'var(--danger-soft-foreground)' },
  cyan: { bg: 'var(--accent-soft)', color: 'var(--accent-soft-foreground)' },
  teal: { bg: 'var(--success-soft)', color: 'var(--success-soft-foreground)' },
  gray: { bg: 'var(--surface-secondary)', color: 'var(--muted)' },
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
    else if (w.type === 'metric' && w.sources?.length) data = await getMultiSourceCount(w.sources, serialiseScope(effScope(w)))
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
function onLayoutUpdated(l) {
  if (!dashboard.value || currentBp.value !== 'lg') return
  if ((!l || !l.length) && widgets.value.length) return
  // grid-layout-plus fires this off its OWN watch on the bound `layout`
  // array — including reacting to the direct mutations the free-resize
  // handler below makes, not just its own internal drag/resize handlers.
  // Its recomputed `l` reflects ITS internal (collision-resolved) view,
  // which would silently overwrite a freeform resize the instant it lands.
  // suppressLayoutSync (set for the duration of a custom resize + a short
  // trailing window, since this event can arrive a tick after pointerup)
  // is what makes the two coexist.
  if (suppressLayoutSync.value) return
  dashboard.value.layout = l.map(x => ({ ...x }))
  dashboardsStore.persist()
}

// ── Free resize — see the handle's own template comment for why this
// bypasses grid-layout-plus's own is-resizable entirely instead of tuning
// its prevent-collision prop (neither of that prop's two states gives real
// freeform growth — confirmed by reading the library's own resize/compact
// source, not guessed). Grid-unit math (rowHeight=10, margin=12, cols=48)
// matches the <GridLayout> config above exactly; colWidth is read from the
// library's OWN measured container width (gridLayoutRef.state.width) so it
// can never drift from what grid-layout-plus itself is using.
const gridLayoutRef = ref(null)
const customResizing = ref(null) // item.i mid-resize, or null — also drives the z-index bump so an overlapped widget doesn't hide the one you're actively growing
const suppressLayoutSync = ref(false) // see onLayoutUpdated's own comment
let suppressTimer = null
let resizeStart = null

// ── Dynamic canvas width — real Kanban-board horizontal scroll ─────────────
// grid-layout-plus's own colWidth is always (measuredContainerWidth - margin
// *(cols+1))/cols — "1 column unit = 1/48th of however wide the DOM element
// I'm mounted in happens to be". Left alone, adding widgets side by side has
// nowhere to go but to make that same 48-unit span host MORE of them by
// squeezing each one — never "scroll for more".
//
// The fix: measure canvasEl (the outer, viewport-driven, non-scrolling-
// content box, NOT the grid wrapper inside it) once for its "natural"
// 1/48th width, then feed GridLayout a col-num that grows with actual
// content (effectiveColNum) alongside a wrapper div sized so that col-num's
// resulting colWidth still comes out to that same natural pixel size —
// never smaller, no matter how many widgets exist. canvasEl's own
// overflow-auto then scrolls to reveal whatever doesn't fit, same as any
// real Kanban board's column row.
const canvasEl = ref(null)
const canvasWidth = ref(0)
let canvasRO = null
onMounted(() => {
  canvasRO = new ResizeObserver((entries) => {
    canvasWidth.value = entries[0]?.contentRect?.width || canvasEl.value?.clientWidth || 0
  })
  if (canvasEl.value) canvasRO.observe(canvasEl.value)
})
onUnmounted(() => canvasRO?.disconnect())

const BASE_COLS = 48, GRID_MARGIN = 12
// The fixed reference every column unit keeps regardless of how many total
// columns end up in use — measured BEFORE any dynamic widening.
const naturalColWidth = computed(() => {
  const w = canvasWidth.value
  if (!w) return 0
  return (w - GRID_MARGIN * (BASE_COLS + 1)) / BASE_COLS
})
// Grows past 48 only when real placed content actually needs it — an
// ordinary dashboard with everything inside 48 units is unaffected, still
// exactly fills the canvas like before.
//
// EDIT_RUNWAY is the fix for "you can't drag a widget right when there's
// nothing to its right": grid-layout-plus clamps every coordinate to
// col-num, so with col-num pinned to exactly the current content extent
// there is, by construction, never anywhere to the right to drop into. In
// edit mode we hand it a screen's worth of empty columns to move and grow
// into; in view mode the canvas hugs the content exactly, so nobody scrolls
// through blank space they can't use.
// Declared here, above the computeds that read it: a lazy computed would
// tolerate a later declaration, but this file has already been bitten once
// by a temporal-dead-zone reference to a `const` further down the file.
const editMode = ref(false)
const EDIT_RUNWAY = 24
const contentExtent = computed(() =>
  localLayout.value.reduce((m, l) => Math.max(m, l.x + l.w), 0)
)
const effectiveColNum = computed(() =>
  Math.max(BASE_COLS, contentExtent.value + (editMode.value ? EDIT_RUNWAY : 0))
)
const gridWrapperStyle = computed(() => {
  const cw = naturalColWidth.value
  if (!cw) return {}
  const cols = effectiveColNum.value
  const px = cols * cw + GRID_MARGIN * (cols + 1)
  return { width: px + 'px', minWidth: '100%' }
})

function gridColWidth() {
  const containerWidth = gridLayoutRef.value?.state?.width ?? 0
  if (!containerWidth) return 0
  const margin = GRID_MARGIN, cols = effectiveColNum.value
  return (containerWidth - margin * (cols + 1)) / cols
}
function onCustomResizeStart(e, item) {
  // Without this, a pointerdown+move the browser can also read as a text-
  // selection drag does exactly that — the light-blue multi-widget text
  // highlight this was built to stop. Belt-and-suspenders with the
  // .dv-editing user-select:none rule below (that rule alone isn't reliably
  // enough in every browser once a drag is already mid-flight).
  e.preventDefault()
  const colWidth = gridColWidth()
  if (!colWidth) return
  clearTimeout(suppressTimer)
  suppressLayoutSync.value = true
  customResizing.value = item.i
  resizeStart = { x: e.clientX, y: e.clientY, w: item.w, h: item.h, itemX: item.x, colWidth }
  window.addEventListener('pointermove', onCustomResizeMove)
  window.addEventListener('pointerup', onCustomResizeEnd, { once: true })
}
function onCustomResizeMove(e) {
  if (!resizeStart) return
  const entry = localLayout.value.find(l => l.i === customResizing.value)
  if (!entry) return
  const margin = 12, rowHeight = 10
  const deltaCols = Math.round((e.clientX - resizeStart.x) / (resizeStart.colWidth + margin))
  const deltaRows = Math.round((e.clientY - resizeStart.y) / (rowHeight + margin))
  const prevW = entry.w
  // No upper clamp on width: the old "can't push past the right grid edge"
  // ceiling was really "can't push past col-num", which used to be a fixed
  // 48 — now effectiveColNum (see gridWrapperStyle's own comment) reacts to
  // localLayout automatically, so growing a widget past the current edge
  // just grows the canvas to match on the next tick instead of hard-
  // stopping. Same as height, which never had a ceiling either.
  entry.w = Math.max(entry.minW || 4, resizeStart.w + deltaCols)
  entry.h = Math.max(entry.minH || 3, resizeStart.h + deltaRows)
  pushNeighboursRight(entry, entry.w - prevW)
}
// Widening a widget used to shove its right-hand neighbours DOWN (the grid's
// vertical compaction is the only push it knows). On a board you scroll
// sideways that's exactly wrong — the neighbours belong beside it, not under
// it. Push them RIGHT by the same amount instead, which the grid has no
// concept of, so it's done here where the resize is already owned.
function pushNeighboursRight(entry, deltaW) {
  if (deltaW <= 0) return
  const rowOverlaps = (l) => l.y < entry.y + entry.h && entry.y < l.y + l.h
  localLayout.value
    .filter((l) => l.i !== entry.i && rowOverlaps(l) && l.x >= entry.x + entry.w - deltaW)
    .sort((a, b) => a.x - b.x)
    .forEach((l) => { l.x += deltaW })
}

function onCustomResizeEnd() {
  window.removeEventListener('pointermove', onCustomResizeMove)
  customResizing.value = null
  resizeStart = null
  if (dashboardId.value) dashboardsStore.updateLayout(dashboardId.value, localLayout.value)
  // grid-layout-plus's own layout-updated can still land a tick after
  // pointerup (its watcher fires on nextTick, not synchronously with the
  // mutation) — keep suppressing until well past that.
  clearTimeout(suppressTimer)
  suppressTimer = setTimeout(() => { suppressLayoutSync.value = false }, 400)
}
onUnmounted(() => {
  window.removeEventListener('pointermove', onCustomResizeMove)
  clearTimeout(suppressTimer)
})

const catalogOpen = ref(false)

const initializing = ref(true)

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

// Fixed body padding — 16px, or 0 when borderless (a borderless widget reads
// as part of the page, so it shouldn't inset its own content either). Used
// to be a per-widget configurable pair of steppers (padding_x/padding_y);
// removed per-widget control was pure surface area for a widget to end up
// looking subtly different from its siblings for no reason, and every
// widget type here (Metric/Chart/Table/Query/Text/Header/Preset) was
// designed assuming ITS content sits inside a padded box, not managing its
// own — column/kanban are the deliberate exception (ColumnWidget.vue owns
// its own internal spacing; see the wrapper div's :style skip below).
function bodyPadding(w) {
  if (!w) return {}
  const p = w.borderless ? 0 : 16
  return { padding: p + 'px' }
}

function addWidget(type, extra = {}) {
  const w = dashboardsStore.addWidget(dashboardId.value, type, extra)
  catalogOpen.value = false
  editMode.value = true // so drag handles are visible to position the new widget right away
  syncLayout()
  loadWidget(w)
}
// "+ Widget" is always visible now (was hidden behind Edit layout):
// adding a widget is a primary action, not something to gate behind an
// edit-mode toggle first.
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
getWidgetSourceDoctypes().then(rows => { widgetSourceDoctypes.value = rows || [] }).catch(() => { })

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
// Select/Link are the naturally bounded types a board can have one column
// per. BP Task's `status` is a Data field (validated against each project's
// workflow_states rather than a schema enum — see BP Task.status), so a
// plain fieldtype test would have excluded the single most important
// grouping on the app's own primary doctype.
const KANBAN_EXTRA_GROUPABLE = new Set(['status'])
const kanbanGroupByFields = computed(() => sourceFields.value.filter(
  (f) => f.fieldtype === 'Select' || f.fieldtype === 'Link' || KANBAN_EXTRA_GROUPABLE.has(f.fieldname)
))
const dateFieldOptions = computed(() => sourceFields.value.filter(f => f.fieldtype === 'Date' || f.fieldtype === 'Datetime'))
// BP Task used to be excluded here (its config was all hardcoded pickers).
// Now that filtering and grouping are field-driven for every source, Task
// needs its real field list like everything else.
async function loadSourceFields(doctype) {
  sourceFields.value = doctype ? await getWidgetSourceFields(doctype).catch(() => []) : []
}
watch(() => cfg.value?.doctype, async (dt, prev) => {
  if (cfg.value?.type !== 'kanban' && cfg.value?.type !== 'column') return
  await loadSourceFields(dt)
  // Only prune on a real user-driven SOURCE CHANGE, never on the initial
  // open (prev === undefined) — pruning then would quietly delete a valid
  // saved config just because the field list hadn't loaded yet.
  if (prev === undefined || dt === prev) return
  const dropped = pruneForDoctype(dt, sourceFields.value)
  if (dropped > 0) {
    toast('Source changed', { description: `${dropped} filter${dropped === 1 ? '' : 's'} removed — they referenced fields ${widgetSourceLabel(prev)} had but ${widgetSourceLabel(dt)} doesn't.` })
  }
})
// Fields worth grouping a column by. Free text (a title, a description) has
// one group per record — technically valid, useless in practice — so only
// genuinely categorical types are offered, plus the synthetic ones.
const GROUPABLE_TYPES = new Set(['Select', 'Link', 'Data', 'Check', 'Int'])
const groupableFields = computed(() =>
  sourceFields.value.filter((f) => GROUPABLE_TYPES.has(f.fieldtype) && f.fieldname !== 'name')
)
// The date-grouping option names the field it will actually bucket on, so
// "Due date timeline" vs "Delivery date timeline" is visible before saving.
const dateGroupLabel = computed(() => {
  if (!cfg.value) return 'Date timeline'
  if (isTaskDoctype(cfg.value.doctype)) return 'Due date — Overdue / Today / This week'
  const f = sourceFields.value.find((x) => x.fieldname === cfg.value.date_field)
  return f ? `${f.label} — Overdue / Today / This week` : 'Date — Overdue / Today / This week'
})

const quickFilterConverted = ref(false)

// Changing the SOURCE invalidates everything keyed to the old doctype's
// fields. Silently keeping them meant a filter on a field that no longer
// exists (a hard backend throw: "Unknown filter field"), a group-by that
// throws the same way, and a row template rendering blank blocks forever.
// Prune to exactly what the new doctype really has.
function pruneForDoctype(newDoctype, fields) {
  const c = cfg.value
  if (!c) return
  const valid = new Set(fields.map((f) => f.fieldname))
  const before = (c.filters || []).length
  c.filters = (c.filters || []).filter((f) => valid.has(f.fieldname))
  c.label_fields = (c.label_fields || []).filter((f) => valid.has(f))
  if (c.date_field && !valid.has(c.date_field)) c.date_field = ''
  if (c.group_by && !['date', 'none'].includes(c.group_by) && !valid.has(c.group_by)) c.group_by = 'date'
  if (c.row_template) {
    const keep = (b) => !b || b.kind !== 'field' || valid.has(b.field)
    const t = c.row_template
    const next = {
      line1: (t.line1 || []).filter(keep),
      line2: (t.line2 || []).filter(keep),
      solo: keep(t.solo) ? t.solo : null,
    }
    c.row_template = (next.line1.length || next.line2.length || next.solo) ? next : null
  }
  // A Task-only quick filter is meaningless on any other doctype.
  if (!isTaskDoctype(newDoctype)) { c.filterBy = null; c.filterValue = null }
  return before - c.filters.length
}

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
    group_by: w.group_by || (w.type === 'column' ? 'date' : w.group_by),
    sources: (w.sources || []).map(s => ({ doctype: s.doctype, filters: [...(s.filters || [])] })),
  })
  // Convert the retired quick filter into its exact filter-builder
  // equivalent. Draft-only — nothing is rewritten unless the user saves —
  // and the widget renders identically either way, because both resolve to
  // the same query server-side. 'project' becomes a Projects selection
  // rather than a filter row: that control does the same job better
  // (several projects, or inherit from the dashboard).
  quickFilterConverted.value = false
  if (cfg.value.type === 'column' && cfg.value.filterBy) {
    const by = cfg.value.filterBy
    const val = cfg.value.filterValue
    if (by === 'project') {
      if (val) cfg.value.scope = val
    } else if (by === 'assignee' && !val) {
      // filter_by='assignee' with no value has always meant "unassigned".
      cfg.value.filters = [...(cfg.value.filters || []), { fieldname: 'assignee', operator: 'is_not_set', value: '' }]
      quickFilterConverted.value = true
    } else if (val) {
      cfg.value.filters = [...(cfg.value.filters || []), { fieldname: by, operator: '=', value: val }]
      quickFilterConverted.value = true
    }
    cfg.value.filterBy = null
    cfg.value.filterValue = null
  }
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

// Metric widget's multi-source mode — see get_multi_source_count's own
// docstring for the full picture. Each row is independent (own doctype, own
// filters); an empty/half-added row is allowed in the editor (saveConfigure
// drops it) so adding a source doesn't force an immediate doctype pick.
function addMetricSource() {
  if (!cfg.value.sources) cfg.value.sources = []
  cfg.value.sources.push({ doctype: '', filters: [] })
}
function removeMetricSource(i) { cfg.value.sources.splice(i, 1) }
function onMetricSourceDoctype(src, doctype) {
  src.doctype = doctype
  src.filters = [] // stale filters from the PREVIOUS doctype don't carry over — different field set entirely
}

// ── Row designer (Column widgets) ──────────────────────────────────────────
// Same doctype/isTask rule ColumnWidget.vue itself uses — a widget saved
// before `doctype` existed (filterBy but no doctype) still means Task, never
// a silent default applied to a fresh one.
const rowDesignerId = ref(null)
// Several real rows, not one — the designer lets you page through them, so
// you can confirm a layout holds up against a record with a long title, one
// with no assignee, one with a different status, instead of trusting that
// whatever happened to be first is representative.
const rowDesignerSamples = ref([])
const rowDesignerIsTask = computed(() => {
  const w = wmap.value[rowDesignerId.value]
  return !!w && (w.doctype === 'BP Task' || (!w.doctype && !!w.filterBy))
})
const rowDesignerDoctype = computed(() => (rowDesignerIsTask.value ? 'BP Task' : wmap.value[rowDesignerId.value]?.doctype))
// A single project the widget is actually scoped to, if any — passed down
// so BP Task.status color choices resolve THAT project's own
// workflow_states rather than the workspace-wide union of every project's.
const rowDesignerProject = computed(() => {
  const w = wmap.value[rowDesignerId.value]
  if (!w) return null
  const s = effScope(w)
  if (!s || s === 'all' || Array.isArray(s)) return null
  return s
})

async function openRowDesigner(id) {
  rowDesignerId.value = id
  rowDesignerSamples.value = []
  const w = wmap.value[id]
  if (!w) return
  try {
    // Ask for EVERY field the designer can offer, not just the ones the
    // saved template already uses: the preview has to stay truthful the
    // instant a field is added, and re-fetching on every add would make the
    // designer feel laggy for no reason. Eight rows of one doctype's fields
    // is a trivial payload, and the backend validates each name against the
    // real schema before it reaches the query.
    const dt = rowDesignerIsTask.value ? 'BP Task' : w.doctype
    const allFields = (await getWidgetSourceFields(dt).catch(() => [])).map((f) => f.fieldname)

    if (rowDesignerIsTask.value) {
      const res = await getColumnWidgetData({
        scope: serialiseScope(effScope(w)), filter_by: w.filterBy || null, filter_value: w.filterValue || null,
        status_filter: w.statusFilter || 'open', filters: w.filters || [],
        group_by: 'none', extra_fields: allFields,
      })
      rowDesignerSamples.value = (res?.buckets || []).flatMap((b) => b.tasks).slice(0, 8)
    } else {
      const res = await getDoctypeColumnData({
        doctype: w.doctype, filters: w.filters || [], label_fields: w.label_fields || [],
        date_field: w.date_field === undefined ? undefined : w.date_field, limit: 8,
        group_by: 'none', extra_fields: allFields,
      })
      rowDesignerSamples.value = (res?.rows || []).slice(0, 8)
    }
  } catch { rowDesignerSamples.value = [] }
}
function saveRowTemplate(tpl) {
  dashboardsStore.updateWidgetConfig(dashboardId.value, rowDesignerId.value, { row_template: tpl })
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
    // Half-added rows (doctype not yet picked) are dropped rather than
    // persisted — a Metric widget with an empty-doctype source would throw
    // server-side on every load instead of falling back to the group_by/
    // metric rollup.
    sources: (c.sources || []).filter(s => s.doctype).map(s => ({ doctype: s.doctype, filters: [...(s.filters || [])] })),
    borderless: !!c.borderless,
    link_url: c.link_url, link_label: c.link_label,
    label_fields: [...(c.label_fields || [])], date_field: c.date_field || null,
    group_by: c.group_by || 'date',
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
  const py = w.borderless ? 0 : 16
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

function present() { rootEl.value?.requestFullscreen?.().catch(() => { }) }
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
  if (!store.projects.length) { try { await store.fetchProjects() } catch { } }
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

/* Free resize handle (see onCustomResizeStart's own comment for why this
   replaces grid-layout-plus's own is-resizable) — classic 3-diagonal-line
   grip via a repeating gradient, no icon asset needed. Hidden until the
   card is hovered in edit mode, matching the drag-handle's own reveal
   pattern right above it in the template. */
.dv-resize-handle {
  position: absolute; right: 2px; bottom: 2px; width: 16px; height: 16px;
  cursor: nwse-resize; z-index: 6; opacity: 0; transition: opacity .15s;
  background: linear-gradient(135deg,
    transparent 0 40%, var(--muted) 40% 46%, transparent 46% 60%,
    var(--muted) 60% 66%, transparent 66% 80%, var(--muted) 80% 86%, transparent 86%);
}
.widget-card:hover .dv-resize-handle { opacity: .6; }
.dv-resize-handle:hover { opacity: 1 !important; }

/* Mid-resize, the actively-grown widget renders above whatever it's
   temporarily overlapping — true freeform means overlap can happen, this
   just keeps the one you're LOOKING at on top while it happens. */
:deep(.dv-resizing-item) {
  z-index: 30;
}

/* Belt-and-suspenders for the same text-selection bug the resize handle's
   own preventDefault() targets — grid-layout-plus's own drag-move can hit
   the same "browser reads this as a text-selection drag" issue. Scoped to
   the grid itself (via :deep, since GridLayout renders its own subtree),
   not the whole page, so widget text stays selectable outside edit mode. */
.dv-editing :deep(.vgl-item) {
  user-select: none;
  -webkit-user-select: none;
}

/* Roomier rows for the dashboard-level "More" menu specifically — scoped
   here (not DropdownItem.vue, shared by every dropdown app-wide) so no
   other menu's density changes. */
:deep(.dv-more-item) {
  padding-top: 9px;
  padding-bottom: 9px;
}
.dv-more-item{
  font-weight: 600 !important;
  font-size: 12px !important;
}
/* Column widgets specifically: flat, no elevation, an explicit border
   color per design direction — kept scoped to .widget-card-column (applied
   only when type==='column') rather than changed for every widget type. */
.widget-card-column {
  border-color: #e8eaee;
}

:global(.dark) .widget-card-column,
:global([data-theme="dark"]) .widget-card-column {
  border-color: var(--border);
}

</style>
