<template>
  <div class="lv-root px-5">

    <!-- ── Subbar ── -->
    <div class="lv-subbar">
      <div class="lv-subbar-left">
        <!-- Active-filter chips live in ProjectHeader's row 3 now (single
             source of truth across Board/List/Gantt) — this just shows the
             resulting count, filtered vs total. -->
        <span v-if="allIssues.length" class="lv-sb-count">
          {{ hasActiveFilters ? `${flatIssues.length} of ${allIssues.length}` : allIssues.length }} {{ allIssues.length === 1 ? 'task' : 'tasks' }}
        </span>
      </div>

      <div class="lv-subbar-right">
        <div class="lv-density">
          <Tooltip v-for="d in DENSITIES" :key="d.v" :content="d.label" placement="bottom">
            <template #trigger>
              <button :class="['lv-d-btn',{active:density===d.v}]" @click="density=d.v">
                <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" :d="d.icon"/></svg>
              </button>
            </template>
          </Tooltip>
        </div>
        <Tooltip content="ERP columns" placement="bottom">
          <template #trigger>
            <button class="lv-subbar-btn" @click="showErpModal=true">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
            </button>
          </template>
        </Tooltip>
      </div>
    </div>

    <!-- Floating bulk-action bar — fixed to the viewport bottom, not inline
         in the toolbar, so it reads as an overlay affordance (genuine
         elevation: shadow allowed here) rather than another toolbar row. -->
    <Teleport to="body">
      <Transition name="lv-bulk-pop">
        <div v-if="selected.size > 0" class="lv-bulk-wrap">
          <div class="lv-bulk">
            <span class="lv-bulk-n">{{ selected.size }} selected</span>
            <FieldDropdown width="w-40">
              <template #trigger><button class="lv-bulk-btn">Status</button></template>
              <DropdownItem v-for="s in store.workflowStates" :key="s.name" @click="bulkStatus(s.name)">
                <span class="lv-dot" :style="{background:s.color}"/>{{ s.name }}
              </DropdownItem>
            </FieldDropdown>
            <FieldDropdown width="w-36">
              <template #trigger><button class="lv-bulk-btn">Priority</button></template>
              <DropdownItem v-for="p in PRIORITIES" :key="p.value" @click="bulkPriority(p.value)">
                <PriorityIcon :priority="p.value"/><span :style="{color:p.color}">{{ p.label }}</span>
              </DropdownItem>
            </FieldDropdown>
            <FieldDropdown width="w-44">
              <template #trigger><button class="lv-bulk-btn">Assign</button></template>
              <DropdownItem v-for="m in (store.projectMembers||[])" :key="m.user" @click="bulkAssign(m.user)">
                {{ m.full_name }}
              </DropdownItem>
            </FieldDropdown>
            <FieldDropdown width="w-40">
              <template #trigger><button class="lv-bulk-btn">Sprint</button></template>
              <DropdownItem v-for="s in (store.sprints||[])" :key="s.name" @click="bulkMoveSprint(s.name)">
                {{ s.sprint_name }}
              </DropdownItem>
            </FieldDropdown>
            <FieldDropdown width="w-40">
              <template #trigger><button class="lv-bulk-btn">Epic</button></template>
              <DropdownItem v-for="e in epicOptions" :key="e.name" @click="bulkMoveEpic(e.name)">
                {{ e.title }}
              </DropdownItem>
            </FieldDropdown>
            <div class="lv-bulk-sep"/>
            <button class="lv-bulk-btn lv-bulk-btn--danger" @click="bulkDelete">Delete</button>
            <Tooltip content="Clear selection" placement="top">
              <template #trigger>
                <button class="lv-bulk-x" @click="selected.clear()">✕</button>
              </template>
            </Tooltip>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ── Table ── -->
    <div class="lv-scroll" :data-density="density">
      <table class="lv-table">
        <colgroup>
          <col :style="{width: cw.cb + 'px'}"/>
          <col :style="{width: cw.title + 'px'}"/>
          <col v-for="col in visibleCols" :key="col.key" :style="{width: (cw[col.key]||col.defaultWidth||160) + 'px'}"/>
          <col style="width:150px"/>
        </colgroup>

        <thead v-if="!store.boardGroupBy || store.boardGroupBy==='none'">
          <tr>
            <th class="lv-th lv-th-cb lv-sticky lv-sticky-cb">
              <div class="lv-cb" :class="{checked:allSel,partial:someSel&&!allSel}" @click="toggleAll">
                <svg v-if="allSel" width="9" height="9" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                <svg v-else-if="someSel" width="9" height="9" fill="currentColor" viewBox="0 0 24 24"><rect x="4" y="11" width="16" height="2" rx="1"/></svg>
              </div>
            </th>
            <th class="lv-th lv-th-s lv-sticky lv-sticky-title" @click="setSort('title')">
              ISSUE<span v-if="sortBy==='title'" class="lv-arr">{{ sortDir==='asc'?'↑':'↓' }}</span>
              <div class="lv-rh" @mousedown.stop="armResize();startResize($event,'title')"/>
            </th>
            <th v-for="(col, ci) in visibleCols" :key="col.key" draggable="true"
                @dragstart="onColDragStart($event, col.key)" @dragover.prevent="onColDragOver($event, col.key)"
                @drop="onColDrop(col.key)" @dragend="onColDragEnd"
                class="lv-th" :class="[{'lv-th-s': col.sortField}, colDragClass(col.key)]"
                @click="col.sortField && setSort(col.sortField)">
              <div class="lv-th-inner">
                {{ col.label }}
                <span v-if="sortBy===col.sortField" class="lv-arr">{{ sortDir==='asc'?'↑':'↓' }}</span>
                <button class="lv-col-menu-btn" :class="{'is-open':colMenu.open&&colMenu.col?.key===col.key}" @click.stop="openColMenu($event, col, ci)">
                  <svg width="10" height="10" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="4" r="1.5"/><circle cx="10" cy="10" r="1.5"/><circle cx="10" cy="16" r="1.5"/></svg>
                </button>
              </div>
              <div class="lv-rh" @mousedown.stop="armResize();startResize($event, col.key)"/>
            </th>
            <th class="lv-th lv-th-plus">
              <FieldDropdown width="w-60" align="right">
                <template #trigger>
                  <button class="lv-plus-btn" title="Add column">
                    <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
                  </button>
                </template>
                <button class="lv-addcol-item" @click.stop="showErpModal=true">
                  <span class="lv-erp-ic" style="width:26px;height:26px">
                    <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>
                  </span>
                  <span class="lv-addcol-txt">
                    <span class="lv-addcol-title">Connect ERPNext data</span>
                    <span class="lv-addcol-sub">Sales Order, Item, Customer…</span>
                  </span>
                </button>
                <div class="lv-ddsep"/>
                <p class="lv-dd-hdr">Show / hide columns</p>
                <div v-for="col in colDefs" :key="col.key" class="lv-col-row" @click.stop="toggleCol(col.key)">
                  <div class="lv-col-cb" :class="{on:isVisible(col.key)}">
                    <svg v-if="isVisible(col.key)" width="9" height="9" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                  </div>
                  {{ col.label }}
                </div>
              </FieldDropdown>
            </th>
          </tr>
        </thead>

        <!-- ── Loading: row skeletons ── -->
        <tbody v-if="store.loading">
          <tr v-for="r in 8" :key="'sk' + r" class="lv-row">
            <td :colspan="totalCols" class="lv-td">
              <div class="flex items-center gap-3 h-7 px-2">
                <Skeleton class="h-3.5 w-3.5 rounded-sm" />
                <Skeleton class="h-2.5 w-14" />
                <Skeleton class="h-2.5" :style="{ width: (25 + (r % 5) * 11) + '%' }" />
                <Skeleton class="h-5 w-16 rounded-full ml-auto" />
                <Skeleton class="h-5 w-5 rounded-full" />
              </div>
            </td>
          </tr>
        </tbody>

        <!-- ── Flat view ── -->
        <tbody v-else-if="!store.boardGroupBy || store.boardGroupBy==='none'">
          <tr v-if="!flatIssues.length">
            <td :colspan="totalCols" class="lv-empty">
              <EmptyState :icon="LayoutList" title="No tasks match" description="Adjust filters or create a task to get started." />
            </td>
          </tr>
          <template v-for="issue in sortedIssues" :key="issue.name">
            <tr class="lv-row" :class="{sel:selected.has(issue.name)}"
                @click="store.openTaskDetail(issue.name)"
                @contextmenu.prevent="openCtx($event,issue)">
              <td class="lv-td lv-cb-td lv-sticky lv-sticky-cb" @click.stop="toggleSelect(issue.name)">
                <div class="lv-cb" :class="{checked:selected.has(issue.name)}">
                  <svg v-if="selected.has(issue.name)" width="9" height="9" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                </div>
              </td>
              <td class="lv-td lv-title-td lv-sticky lv-sticky-title">
                <button v-if="issue.sub_tasks?.length" class="lv-expand-btn" @click.stop="toggleExpand(issue.name)">
                  <svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5" :style="{transform:expanded.has(issue.name)?'rotate(90deg)':'',transition:'transform .15s'}"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
                </button>
                <span v-else class="lv-expand-spacer"/>
                <span class="lv-title">{{ issue.title }}</span>
                <span v-if="issue.sub_tasks?.length" class="lv-child-count">{{ issue.sub_tasks.length }}</span>
                <Tooltip content="Actions" placement="top">
                  <template #trigger>
                    <button class="lv-row-menu" @click.stop="openCtx($event,issue)">
                      <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>
                    </button>
                  </template>
                </Tooltip>
              </td>
              <td v-for="col in visibleCols" :key="col.key" :class="['lv-td',col.key==='timeline'?'':'lv-td-edit',{'lv-td-center':col.key==='due'||col.key==='timeline'}]" @click.stop>
                <template v-if="col.key==='status'">
                  <FieldDropdown width="w-44">
                    <template #trigger>
                      <button class="lv-status-pill" :style="statusStyle(issue.status)">
                        {{ issue.status }}</button>
                    </template>
                    <DropdownItem v-for="s in store.workflowStates" :key="s.name" :active="issue.status===s.name" @click="save(issue,'status',s.name)">
                      <span class="lv-dot" :style="{background:s.color}"/>{{ s.name }}
                    </DropdownItem>
                  </FieldDropdown>
                </template>
                <template v-else-if="col.key==='priority'">
                  <FieldDropdown width="w-36">
                    <template #trigger>
                      <button class="lv-prio-pill" :title="issue.priority||'No priority'"><PriorityIcon v-if="issue.priority" :priority="issue.priority"/><span v-else class="lv-unset">—</span></button>
                    </template>
                    <DropdownItem v-for="p in PRIORITIES" :key="p.value" :active="issue.priority===p.value" @click="save(issue,'priority',p.value)">
                      <PriorityIcon :priority="p.value"/><span :style="{color:p.color}">{{ p.label }}</span>
                    </DropdownItem>
                  </FieldDropdown>
                </template>
                <template v-else-if="col.key==='type'">
                  <FieldDropdown v-if="store.taskTypes?.length>1" width="w-40">
                    <template #trigger>
                      <button class="lv-field-btn">
                        <span class="lv-type-badge" :style="{background:typeColor(issue.task_type)}">{{ (issue.task_type||'T').charAt(0) }}</span>
                        <span>{{ issue.task_type||'—' }}</span>
                      </button>
                    </template>
                    <DropdownItem v-for="t in store.taskTypes" :key="t.name" :active="issue.task_type===t.name" @click="save(issue,'task_type',t.name)">
                      <span class="lv-type-badge" :style="{background:t.color}">{{ t.name.charAt(0) }}</span>{{ t.name }}
                    </DropdownItem>
                  </FieldDropdown>
                  <span v-else class="lv-field-plain">
                    <span class="lv-type-badge" :style="{background:typeColor(issue.task_type)}">{{ (issue.task_type||'T').charAt(0) }}</span>
                    <span>{{ issue.task_type||'—' }}</span>
                  </span>
                </template>
                <template v-else-if="col.key==='assignee'">
                  <FieldDropdown width="w-52" :close-on-select="false">
                    <template #trigger>
                      <button class="lv-field-btn">
                        <template v-if="issue.assignees?.length">
                          <span style="display:inline-flex;align-items:center">
                            <span v-for="(a,ai) in issue.assignees.slice(0,3)" :key="a.user"
                              class="lv-av" :style="{background:avatarColor(a.user),marginLeft:ai>0?'-5px':'0'}" :title="a.full_name">
                              {{ initials(a.full_name) }}
                            </span>
                          </span>
                        </template>
                        <span v-else class="lv-av-empty" title="Assign"/>
                      </button>
                    </template>
                    <template #search><div class="lv-ddsearch"><input v-model="aQ" autofocus placeholder="Search…" class="lv-ddinput"/></div></template>
                    <DropdownItem @click="save(issue,'assignees',[])"><span class="lv-av-empty"/>Unassigned</DropdownItem>
                    <div class="lv-ddsep"/>
                    <DropdownItem v-for="m in filteredMembers" :key="m.user" :active="hasA(issue,m.user)" @click="togA(issue,m)">
                      <span class="lv-av" :style="{background:avatarColor(m.user)}">{{ initials(m.full_name) }}</span>
                      <span class="flex-1 truncate">{{ m.full_name }}</span>
                    </DropdownItem>
                  </FieldDropdown>
                </template>
                <template v-else-if="col.key==='timeline'">
                  <FieldDropdown width="w-64" :close-on-select="false">
                    <template #trigger>
                      <button class="lv-tl-pill" :class="{empty:!issue.start_date&&!issue.due_date}" :style="timelineStyle(issue)">
                        {{ timelineLabel(issue) }}
                      </button>
                    </template>
                    <div class="lv-tl-pop" @click.stop>
                      <div class="lv-tl-row"><span class="lv-tl-lbl">Start</span><DatePicker :modelValue="issue.start_date||null" placeholder="None" @update:modelValue="v=>save(issue,'start_date',v||null)"/></div>
                      <div class="lv-tl-row"><span class="lv-tl-lbl">Due</span><DatePicker :modelValue="issue.due_date||null" placeholder="None" @update:modelValue="v=>save(issue,'due_date',v||null)"/></div>
                    </div>
                  </FieldDropdown>
                </template>
                <template v-else-if="col.key==='due'">
                  <div class="lv-date-td" :class="{overdue:isOverdue(issue),today:isDueToday(issue),soon:isDueSoon(issue)}">
                    <DatePicker :modelValue="issue.due_date||null" placeholder="—" @update:modelValue="v=>save(issue,'due_date',v||null)"/>
                  </div>
                </template>
                <template v-else-if="col.key==='blocked'">
                  <BlockedCell :issue="issue"/>
                </template>
                <template v-else-if="col.key==='connected'">
                  <ConnectCell :issue="issue" :open-doc="openMirrorDoc"/>
                </template>
                <template v-else-if="col.key==='relations'">
                  <ConnectorCell :issue="issue"/>
                </template>
                <template v-else-if="col.key.startsWith('erp:')">
                  <ConnectCell :issue="issue" :doctype="col.label" :two-way="erpTwoWay(col.label)" :open-doc="openMirrorDoc"/>
                </template>
                <template v-else-if="col.key.startsWith('mirror:')">
                  <template v-if="mirrorDisplay(issue, col).length">
                    <button v-for="(v,vi) in mirrorDisplay(issue, col).slice(0,2)" :key="vi"
                      class="lv-mirror-val lv-mirror-link" :class="{'lv-mirror-status': col.mirror && mirrorFieldMeta(col.mirror.doctype,col.mirror.field)?.fieldtype==='Status'}"
                      :title="v.name" @click.stop="openMirrorDoc(col.mirror.doctype, v.name)">
                      {{ v.text }}
                    </button>
                    <span v-if="mirrorDisplay(issue, col).length>2" class="lv-lbl-more">+{{ mirrorDisplay(issue, col).length-2 }}</span>
                  </template>
                  <span v-else class="lv-unset">—</span>
                </template>
                <template v-else-if="col.key.startsWith('cf:')">
                  <template v-if="col.cf.type==='select'">
                    <FieldDropdown width="w-44">
                      <template #trigger>
                        <button class="lv-field-btn">
                          <span v-if="cfValue(issue,col.cf)">{{ cfOptionLabel(col.cf, cfValue(issue,col.cf)) }}</span>
                          <span v-else class="lv-unset">—</span>
                        </button>
                      </template>
                      <DropdownItem :active="!cfValue(issue,col.cf)" @click="saveCf(issue,col.cf,null)">—</DropdownItem>
                      <DropdownItem v-for="o in col.cf.options||[]" :key="o.id" :active="cfValue(issue,col.cf)===o.id" @click="saveCf(issue,col.cf,o.id)">{{ o.label }}</DropdownItem>
                    </FieldDropdown>
                  </template>
                  <template v-else-if="col.cf.type==='multiselect'">
                    <FieldDropdown width="w-48" :close-on-select="false">
                      <template #trigger>
                        <button class="lv-field-btn">
                          <template v-if="cfMulti(issue,col.cf).length">
                            <span v-for="id in cfMulti(issue,col.cf).slice(0,2)" :key="id" class="lv-cf-tag">{{ cfOptionLabel(col.cf,id) }}</span>
                            <span v-if="cfMulti(issue,col.cf).length>2" class="lv-lbl-more">+{{ cfMulti(issue,col.cf).length-2 }}</span>
                          </template>
                          <span v-else class="lv-unset">—</span>
                        </button>
                      </template>
                      <DropdownItem v-for="o in col.cf.options||[]" :key="o.id" :active="cfMulti(issue,col.cf).includes(o.id)" @click="cfMultiToggle(issue,col.cf,o.id)">{{ o.label }}</DropdownItem>
                    </FieldDropdown>
                  </template>
                  <template v-else-if="col.cf.type==='date'">
                    <div class="lv-date-td">
                      <DatePicker :modelValue="cfValue(issue,col.cf)||null" placeholder="—" @update:modelValue="v=>saveCf(issue,col.cf,v||null)"/>
                    </div>
                  </template>
                  <template v-else-if="col.cf.type==='number'">
                    <span class="inline-flex items-center gap-1.5">
                      <input class="lv-pts-input" style="width:84px;text-align:left" type="number" :value="cfValue(issue,col.cf)??''" placeholder="—"
                        @change="e=>saveCf(issue,col.cf,e.target.value===''?null:Number(e.target.value))" @click.stop/>
                      <span v-if="cfMarker(issue,col.cf)" class="inline-block size-1.5 rounded-full shrink-0"
                        :style="{ background: cfMarker(issue,col.cf) }" />
                    </span>
                  </template>
                  <template v-else>
                    <input class="lv-cf-input" :value="cfValue(issue,col.cf)||''" placeholder="—"
                      @change="e=>saveCf(issue,col.cf,e.target.value||null)" @click.stop/>
                  </template>
                </template>
                <template v-else-if="col.key==='sprint'">
                  <FieldDropdown width="w-56">
                    <template #trigger>
                      <button class="lv-field-btn">
                        <span v-if="issue.sprint" class="lv-sprint-chip">{{ sprintName(issue.sprint) }}</span>
                        <span v-else class="lv-unset">—</span>
                      </button>
                    </template>
                    <CreatablePicker
                      :options="(store.sprints||[]).map(s => ({ key: s.name, label: s.sprint_name }))"
                      :model-value="issue.sprint"
                      noun="sprint" empty-label="No sprint" search-placeholder="Search or create sprint…"
                      @select="v => save(issue,'sprint',v)"
                      @create="name => createSprintInline(issue, name)"
                    />
                  </FieldDropdown>
                </template>
                <template v-else-if="col.key==='epic'">
                  <FieldDropdown width="w-56">
                    <template #trigger>
                      <button class="lv-field-btn">
                        <span v-if="issue.epic" class="lv-epic-chip">{{ epicName(issue.epic) }}</span>
                        <span v-else class="lv-unset">—</span>
                      </button>
                    </template>
                    <CreatablePicker
                      :options="epicOptions.map(e => ({ key: e.name, label: e.title }))"
                      :model-value="issue.epic"
                      noun="epic" empty-label="No epic" search-placeholder="Search or create epic…"
                      @select="v => save(issue,'epic',v)"
                      @create="title => createEpicInline(issue, title)"
                    />
                  </FieldDropdown>
                </template>
                <template v-else-if="col.key==='points'">
                  <input class="lv-pts-input" type="number" min="0"
                    :value="issue.story_points||''" placeholder="—"
                    @change="e=>save(issue,'story_points',e.target.value===''?null:Number(e.target.value))"
                    @click.stop/>
                </template>
                <template v-else-if="col.key==='labels'">
                  <FieldDropdown width="w-52" :close-on-select="false">
                    <template #trigger>
                      <button class="lv-field-btn">
                        <span v-if="issueLabels(issue).length" class="lv-label-row">
                          <span v-for="lbl in issueLabels(issue).slice(0,2)" :key="lbl" class="lv-lbl-chip" :style="labelStyle(lbl)">{{ lbl }}</span>
                          <span v-if="issueLabels(issue).length>2" class="lv-lbl-more">+{{ issueLabels(issue).length-2 }}</span>
                        </span>
                        <span v-else class="lv-unset">—</span>
                      </button>
                    </template>
                    <CreatablePicker
                      :options="(store.projectLabels||[]).map(l => ({ key: l.label, label: l.label, color: l.color }))"
                      :model-value="issueLabels(issue)" multiple :allow-empty="false"
                      noun="label" search-placeholder="Search or create label…"
                      @select="key => togLabel(issue, key)"
                      @create="name => createLabelInline(issue, name)"
                    />
                  </FieldDropdown>
                </template>
              </td>
              <td class="lv-td lv-td-ghost"/>
            </tr>
            <!-- Child rows -->
            <template v-if="expanded.has(issue.name) && issue.sub_tasks?.length">
              <tr v-for="(child,ci) in issue.sub_tasks" :key="child.name"
                  class="lv-row lv-child-row"
                  @click="store.openTaskDetail(child.name)"
                  @contextmenu.prevent="openCtx($event,child)">
                <td class="lv-td lv-cb-td lv-sticky lv-sticky-cb"/>
                <td class="lv-td lv-title-td lv-child-title-td lv-sticky lv-sticky-title">
                  <span class="lv-child-indent" :class="{'is-last':ci===issue.sub_tasks.length-1}"/>
                  <span class="lv-type-badge" :style="{background:typeColor(child.task_type)}">{{ (child.task_type||'T').charAt(0) }}</span>
                  <span class="lv-title lv-title-child">{{ child.title }}</span>
                </td>
                <td v-for="col in visibleCols" :key="col.key" :class="['lv-td',col.key==='timeline'?'':'lv-td-edit',{'lv-td-center':col.key==='due'||col.key==='timeline'}]" @click.stop>
                  <template v-if="col.key==='status'">
                    <FieldDropdown width="w-44">
                      <template #trigger>
                        <button class="lv-status-pill" :style="statusStyle(child.status)">{{ child.status }}</button>
                      </template>
                      <DropdownItem v-for="s in store.workflowStates" :key="s.name" :active="child.status===s.name" @click="save(child,'status',s.name)">
                        <span class="lv-dot" :style="{background:s.color}"/>{{ s.name }}
                      </DropdownItem>
                    </FieldDropdown>
                  </template>
                  <template v-else-if="col.key==='priority'">
                    <FieldDropdown width="w-36">
                      <template #trigger>
                        <button class="lv-prio-pill" :title="child.priority||'No priority'"><PriorityIcon v-if="child.priority" :priority="child.priority"/><span v-else class="lv-unset">—</span></button>
                      </template>
                      <DropdownItem v-for="p in PRIORITIES" :key="p.value" :active="child.priority===p.value" @click="save(child,'priority',p.value)">
                        <PriorityIcon :priority="p.value"/><span :style="{color:p.color}">{{ p.label }}</span>
                      </DropdownItem>
                    </FieldDropdown>
                  </template>
                  <template v-else-if="col.key==='type'">
                    <span class="lv-field-plain">
                      <span class="lv-type-badge" :style="{background:typeColor(child.task_type)}">{{ (child.task_type||'T').charAt(0) }}</span>
                      <span>{{ child.task_type||'—' }}</span>
                    </span>
                  </template>
                  <template v-else-if="col.key==='assignee'">
                    <span v-if="child.assignees?.length" style="display:inline-flex;align-items:center;gap:6px;padding:0 8px">
                      <span class="lv-av" :style="{background:avatarColor(child.assignees[0].user)}" :title="child.assignees[0].full_name">{{ initials(child.assignees[0].full_name) }}</span>
                    </span>
                    <span v-else class="lv-av-empty" title="Assign"/>
                  </template>
                  <template v-else-if="col.key==='timeline'">
                    <span class="lv-unset">{{ timelineLabel(child)==='Set dates'?'—':timelineLabel(child) }}</span>
                  </template>
                  <template v-else-if="col.key==='due'">
                    <div class="lv-date-td" :class="{overdue:isOverdue(child),today:isDueToday(child),soon:isDueSoon(child)}">
                      <DatePicker :modelValue="child.due_date||null" placeholder="—" @update:modelValue="v=>save(child,'due_date',v||null)"/>
                    </div>
                  </template>
                  <template v-else-if="col.key==='sprint'">
                    <span v-if="child.sprint" class="lv-sprint-chip">{{ sprintName(child.sprint) }}</span>
                    <span v-else class="lv-unset">—</span>
                  </template>
                  <template v-else-if="col.key==='epic'">
                    <span v-if="child.epic" class="lv-epic-chip">{{ epicName(child.epic) }}</span>
                    <span v-else class="lv-unset">—</span>
                  </template>
                  <template v-else-if="col.key==='points'">
                    <span class="lv-unset" style="padding:0 8px">{{ child.story_points||'—' }}</span>
                  </template>
                  <template v-else-if="col.key==='labels'">
                    <div class="lv-label-row">
                      <span v-for="lbl in issueLabels(child).slice(0,2)" :key="lbl" class="lv-lbl-chip" :style="labelStyle(lbl)">{{ lbl }}</span>
                    </div>
                  </template>
                </td>
                <td class="lv-td lv-td-ghost"/>
              </tr>
            </template>
          </template>
          <tr class="lv-qc-row"><td :colspan="totalCols" class="lv-qc" @click="quickCreate(null)">
            <svg width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg> Add task
          </td></tr>
        </tbody>

        <!-- ── Grouped view ── -->
        <template v-else>
          <tbody v-if="!flatIssues.length">
            <tr>
              <td :colspan="totalCols" class="lv-empty">
                <EmptyState :icon="LayoutList" title="No tasks match" description="Adjust filters or create a task to get started." />
              </td>
            </tr>
          </tbody>
          <template v-for="group in groups" :key="group.key">
          <tbody class="lv-grp-title" :style="{'--grp': group.color|| 'var(--muted)'}">
            <tr class="lv-group-tr" @click="toggleGroup(group.key)">
              <td :colspan="totalCols" class="lv-group-td">
                <div class="lv-group-inner">
                  <svg class="lv-chevron" :class="{collapsed:collapsedGroups.has(group.key)}" width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                  <span class="lv-gdot" :style="{background:group.color||'var(--muted)'}"/>
                  <span class="lv-glabel">{{ group.key }}</span>
                  <span class="lv-gcount">{{ group.issues.length }} {{ group.issues.length===1?'task':'tasks' }}</span>
                  <span v-for="s in groupSummaries(group)" :key="s.key" class="lv-gsum" :class="{danger:s.danger}">{{ s.text }}</span>
                </div>
              </td>
            </tr>
          </tbody>
          <tbody v-if="!collapsedGroups.has(group.key)" class="lv-grp" :style="{'--grp': group.color|| 'var(--muted)'}">
              <tr class="lv-ghead">
                <td class="lv-gh lv-gh-cb lv-sticky lv-sticky-cb lv-gh-sticky">
                  <div class="lv-cb" :class="{checked:groupAllSel(group),partial:groupSomeSel(group)&&!groupAllSel(group)}" @click.stop="toggleGroupSel(group)">
                    <svg v-if="groupAllSel(group)" width="9" height="9" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                    <svg v-else-if="groupSomeSel(group)" width="9" height="9" fill="currentColor" viewBox="0 0 24 24"><rect x="4" y="11" width="16" height="2" rx="1"/></svg>
                  </div>
                </td>
                <td class="lv-gh lv-gh-title lv-sticky lv-sticky-title lv-gh-sticky">Task
                  <div class="lv-rh" @mousedown.stop="armResize();startResize($event,'title')"/>
                </td>
                <td v-for="(col,ci) in visibleCols" :key="col.key" draggable="true"
                    @dragstart="onColDragStart($event,col.key)" @dragover.prevent="onColDragOver($event,col.key)"
                    @drop="onColDrop(col.key)" @dragend="onColDragEnd"
                    class="lv-gh" :class="colDragClass(col.key)">
                  <div class="lv-th-inner">
                    {{ col.label }}
                    <button class="lv-col-menu-btn" :class="{'is-open':colMenu.open&&colMenu.col?.key===col.key}" @click.stop="openColMenu($event, col, ci)">
                      <svg width="10" height="10" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="4" r="1.5"/><circle cx="10" cy="10" r="1.5"/><circle cx="10" cy="16" r="1.5"/></svg>
                    </button>
                  </div>
                  <div class="lv-rh" @mousedown.stop="armResize();startResize($event, col.key)"/>
                </td>
                <td class="lv-gh lv-gh-plus">
                  <FieldDropdown width="w-60" align="right">
                    <template #trigger>
                      <button class="lv-plus-btn" title="Add column">
                        <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
                      </button>
                    </template>
                    <button class="lv-addcol-item" @click.stop="showErpModal=true">
                      <span class="lv-erp-ic" style="width:26px;height:26px">
                        <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>
                      </span>
                      <span class="lv-addcol-txt">
                        <span class="lv-addcol-title">Connect ERPNext data</span>
                        <span class="lv-addcol-sub">Sales Order, Item, Customer…</span>
                      </span>
                    </button>
                    <div class="lv-ddsep"/>
                    <p class="lv-dd-hdr">Show / hide columns</p>
                    <div v-for="col in colDefs" :key="col.key" class="lv-col-row" @click.stop="toggleCol(col.key)">
                      <div class="lv-col-cb" :class="{on:isVisible(col.key)}">
                        <svg v-if="isVisible(col.key)" width="9" height="9" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                      </div>
                      {{ col.label }}
                    </div>
                  </FieldDropdown>
                </td>
              </tr>
              <template v-for="issue in group.issues" :key="issue.name">
                <tr class="lv-row" :class="{sel:selected.has(issue.name)}"
                    @click="store.openTaskDetail(issue.name)"
                    @contextmenu.prevent="openCtx($event,issue)">
                  <td class="lv-td lv-cb-td lv-sticky lv-sticky-cb" @click.stop="toggleSelect(issue.name)">
                    <div class="lv-cb" :class="{checked:selected.has(issue.name)}">
                      <svg v-if="selected.has(issue.name)" width="9" height="9" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
                    </div>
                  </td>
                  <td class="lv-td lv-title-td lv-sticky lv-sticky-title">
                    <button v-if="issue.sub_tasks?.length" class="lv-expand-btn" @click.stop="toggleExpand(issue.name)">
                      <svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5" :style="{transform:expanded.has(issue.name)?'rotate(90deg)':'',transition:'transform .15s'}"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
                    </button>
                    <span v-else class="lv-expand-spacer"/>
                        <span class="lv-title">{{ issue.title }}</span>
                    <span v-if="issue.sub_tasks?.length" class="lv-child-count">{{ issue.sub_tasks.length }}</span>
                    <Tooltip content="Actions" placement="top">
                      <template #trigger>
                        <button class="lv-row-menu" @click.stop="openCtx($event,issue)">
                          <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>
                        </button>
                      </template>
                    </Tooltip>
                  </td>
                  <td v-for="col in visibleCols" :key="col.key" :class="['lv-td',col.key==='timeline'?'':'lv-td-edit',{'lv-td-center':col.key==='due'||col.key==='timeline'}]" @click.stop>
                    <template v-if="col.key==='status'">
                      <FieldDropdown width="w-44">
                        <template #trigger>
                          <button class="lv-status-pill" :style="statusStyle(issue.status)">
                            {{ issue.status }}</button>
                        </template>
                        <DropdownItem v-for="s in store.workflowStates" :key="s.name" :active="issue.status===s.name" @click="save(issue,'status',s.name)">
                          <span class="lv-dot" :style="{background:s.color}"/>{{ s.name }}
                        </DropdownItem>
                      </FieldDropdown>
                    </template>
                    <template v-else-if="col.key==='priority'">
                      <FieldDropdown width="w-36">
                        <template #trigger>
                          <button class="lv-prio-pill" :title="issue.priority||'No priority'"><PriorityIcon v-if="issue.priority" :priority="issue.priority"/><span v-else class="lv-unset">—</span></button>
                        </template>
                        <DropdownItem v-for="p in PRIORITIES" :key="p.value" :active="issue.priority===p.value" @click="save(issue,'priority',p.value)">
                          <PriorityIcon :priority="p.value"/><span :style="{color:p.color}">{{ p.label }}</span>
                        </DropdownItem>
                      </FieldDropdown>
                    </template>
                    <template v-else-if="col.key==='type'">
                      <FieldDropdown v-if="store.taskTypes?.length>1" width="w-40">
                        <template #trigger>
                          <button class="lv-field-btn">
                            <span class="lv-type-badge" :style="{background:typeColor(issue.task_type)}">{{ (issue.task_type||'T').charAt(0) }}</span>
                            <span>{{ issue.task_type||'—' }}</span>
                          </button>
                        </template>
                        <DropdownItem v-for="t in store.taskTypes" :key="t.name" :active="issue.task_type===t.name" @click="save(issue,'task_type',t.name)">
                          <span class="lv-type-badge" :style="{background:t.color}">{{ t.name.charAt(0) }}</span>{{ t.name }}
                        </DropdownItem>
                      </FieldDropdown>
                      <span v-else class="lv-field-plain">
                        <span class="lv-type-badge" :style="{background:typeColor(issue.task_type)}">{{ (issue.task_type||'T').charAt(0) }}</span>
                        <span>{{ issue.task_type||'—' }}</span>
                      </span>
                    </template>
                    <template v-else-if="col.key==='assignee'">
                      <FieldDropdown width="w-52" :close-on-select="false">
                        <template #trigger>
                          <button class="lv-field-btn">
                            <template v-if="issue.assignees?.length">
                              <span style="display:inline-flex;align-items:center">
                                <span v-for="(a,ai) in issue.assignees.slice(0,3)" :key="a.user"
                                  class="lv-av" :style="{background:avatarColor(a.user),marginLeft:ai>0?'-5px':'0'}" :title="a.full_name">
                                  {{ initials(a.full_name) }}
                                </span>
                              </span>
                            </template>
                            <span v-else class="lv-av-empty" title="Assign"/>
                          </button>
                        </template>
                        <template #search><div class="lv-ddsearch"><input v-model="aQ" autofocus placeholder="Search…" class="lv-ddinput"/></div></template>
                        <DropdownItem @click="save(issue,'assignees',[])"><span class="lv-av-empty"/>Unassigned</DropdownItem>
                        <div class="lv-ddsep"/>
                        <DropdownItem v-for="m in filteredMembers" :key="m.user" :active="hasA(issue,m.user)" @click="togA(issue,m)">
                          <span class="lv-av" :style="{background:avatarColor(m.user)}">{{ initials(m.full_name) }}</span>
                          <span class="flex-1 truncate">{{ m.full_name }}</span>
                        </DropdownItem>
                      </FieldDropdown>
                    </template>
                    <template v-else-if="col.key==='timeline'">
                  <FieldDropdown width="w-64" :close-on-select="false">
                    <template #trigger>
                      <button class="lv-tl-pill" :class="{empty:!issue.start_date&&!issue.due_date}" :style="timelineStyle(issue)">
                        {{ timelineLabel(issue) }}
                      </button>
                    </template>
                    <div class="lv-tl-pop" @click.stop>
                      <div class="lv-tl-row"><span class="lv-tl-lbl">Start</span><DatePicker :modelValue="issue.start_date||null" placeholder="None" @update:modelValue="v=>save(issue,'start_date',v||null)"/></div>
                      <div class="lv-tl-row"><span class="lv-tl-lbl">Due</span><DatePicker :modelValue="issue.due_date||null" placeholder="None" @update:modelValue="v=>save(issue,'due_date',v||null)"/></div>
                    </div>
                  </FieldDropdown>
                </template>
                <template v-else-if="col.key==='due'">
                      <div class="lv-date-td" :class="{overdue:isOverdue(issue),today:isDueToday(issue),soon:isDueSoon(issue)}">
                        <DatePicker :modelValue="issue.due_date||null" placeholder="—" @update:modelValue="v=>save(issue,'due_date',v||null)"/>
                      </div>
                    </template>
                    <template v-else-if="col.key==='blocked'">
                  <BlockedCell :issue="issue"/>
                </template>
                <template v-else-if="col.key==='connected'">
                  <ConnectCell :issue="issue" :open-doc="openMirrorDoc"/>
                </template>
                <template v-else-if="col.key==='relations'">
                  <ConnectorCell :issue="issue"/>
                </template>
                <template v-else-if="col.key.startsWith('erp:')">
                  <ConnectCell :issue="issue" :doctype="col.label" :two-way="erpTwoWay(col.label)" :open-doc="openMirrorDoc"/>
                </template>
                <template v-else-if="col.key.startsWith('mirror:')">
                  <template v-if="mirrorDisplay(issue, col).length">
                    <button v-for="(v,vi) in mirrorDisplay(issue, col).slice(0,2)" :key="vi"
                      class="lv-mirror-val lv-mirror-link" :class="{'lv-mirror-status': col.mirror && mirrorFieldMeta(col.mirror.doctype,col.mirror.field)?.fieldtype==='Status'}"
                      :title="v.name" @click.stop="openMirrorDoc(col.mirror.doctype, v.name)">
                      {{ v.text }}
                    </button>
                    <span v-if="mirrorDisplay(issue, col).length>2" class="lv-lbl-more">+{{ mirrorDisplay(issue, col).length-2 }}</span>
                  </template>
                  <span v-else class="lv-unset">—</span>
                </template>
                <template v-else-if="col.key.startsWith('cf:')">
                  <template v-if="col.cf.type==='select'">
                    <FieldDropdown width="w-44">
                      <template #trigger>
                        <button class="lv-field-btn">
                          <span v-if="cfValue(issue,col.cf)">{{ cfOptionLabel(col.cf, cfValue(issue,col.cf)) }}</span>
                          <span v-else class="lv-unset">—</span>
                        </button>
                      </template>
                      <DropdownItem :active="!cfValue(issue,col.cf)" @click="saveCf(issue,col.cf,null)">—</DropdownItem>
                      <DropdownItem v-for="o in col.cf.options||[]" :key="o.id" :active="cfValue(issue,col.cf)===o.id" @click="saveCf(issue,col.cf,o.id)">{{ o.label }}</DropdownItem>
                    </FieldDropdown>
                  </template>
                  <template v-else-if="col.cf.type==='multiselect'">
                    <FieldDropdown width="w-48" :close-on-select="false">
                      <template #trigger>
                        <button class="lv-field-btn">
                          <template v-if="cfMulti(issue,col.cf).length">
                            <span v-for="id in cfMulti(issue,col.cf).slice(0,2)" :key="id" class="lv-cf-tag">{{ cfOptionLabel(col.cf,id) }}</span>
                            <span v-if="cfMulti(issue,col.cf).length>2" class="lv-lbl-more">+{{ cfMulti(issue,col.cf).length-2 }}</span>
                          </template>
                          <span v-else class="lv-unset">—</span>
                        </button>
                      </template>
                      <DropdownItem v-for="o in col.cf.options||[]" :key="o.id" :active="cfMulti(issue,col.cf).includes(o.id)" @click="cfMultiToggle(issue,col.cf,o.id)">{{ o.label }}</DropdownItem>
                    </FieldDropdown>
                  </template>
                  <template v-else-if="col.cf.type==='date'">
                    <div class="lv-date-td">
                      <DatePicker :modelValue="cfValue(issue,col.cf)||null" placeholder="—" @update:modelValue="v=>saveCf(issue,col.cf,v||null)"/>
                    </div>
                  </template>
                  <template v-else-if="col.cf.type==='number'">
                    <span class="inline-flex items-center gap-1.5">
                      <input class="lv-pts-input" style="width:84px;text-align:left" type="number" :value="cfValue(issue,col.cf)??''" placeholder="—"
                        @change="e=>saveCf(issue,col.cf,e.target.value===''?null:Number(e.target.value))" @click.stop/>
                      <span v-if="cfMarker(issue,col.cf)" class="inline-block size-1.5 rounded-full shrink-0"
                        :style="{ background: cfMarker(issue,col.cf) }" />
                    </span>
                  </template>
                  <template v-else>
                    <input class="lv-cf-input" :value="cfValue(issue,col.cf)||''" placeholder="—"
                      @change="e=>saveCf(issue,col.cf,e.target.value||null)" @click.stop/>
                  </template>
                </template>
                <template v-else-if="col.key==='sprint'">
                      <FieldDropdown width="w-56">
                        <template #trigger>
                          <button class="lv-field-btn">
                            <span v-if="issue.sprint" class="lv-sprint-chip">{{ sprintName(issue.sprint) }}</span>
                            <span v-else class="lv-unset">—</span>
                          </button>
                        </template>
                        <CreatablePicker
                          :options="(store.sprints||[]).map(s => ({ key: s.name, label: s.sprint_name }))"
                          :model-value="issue.sprint"
                          noun="sprint" empty-label="No sprint" search-placeholder="Search or create sprint…"
                          @select="v => save(issue,'sprint',v)"
                          @create="name => createSprintInline(issue, name)"
                        />
                      </FieldDropdown>
                    </template>
                    <template v-else-if="col.key==='epic'">
                      <FieldDropdown width="w-56">
                        <template #trigger>
                          <button class="lv-field-btn">
                            <span v-if="issue.epic" class="lv-epic-chip">{{ epicName(issue.epic) }}</span>
                            <span v-else class="lv-unset">—</span>
                          </button>
                        </template>
                        <CreatablePicker
                          :options="epicOptions.map(e => ({ key: e.name, label: e.title }))"
                          :model-value="issue.epic"
                          noun="epic" empty-label="No epic" search-placeholder="Search or create epic…"
                          @select="v => save(issue,'epic',v)"
                          @create="title => createEpicInline(issue, title)"
                        />
                      </FieldDropdown>
                    </template>
                    <template v-else-if="col.key==='points'">
                      <input class="lv-pts-input" type="number" min="0"
                        :value="issue.story_points||''" placeholder="—"
                        @change="e=>save(issue,'story_points',e.target.value===''?null:Number(e.target.value))"
                        @click.stop/>
                    </template>
                    <template v-else-if="col.key==='labels'">
                      <FieldDropdown width="w-52" :close-on-select="false">
                        <template #trigger>
                          <button class="lv-field-btn">
                            <span v-if="issueLabels(issue).length" class="lv-label-row">
                              <span v-for="lbl in issueLabels(issue).slice(0,2)" :key="lbl" class="lv-lbl-chip" :style="labelStyle(lbl)">{{ lbl }}</span>
                              <span v-if="issueLabels(issue).length>2" class="lv-lbl-more">+{{ issueLabels(issue).length-2 }}</span>
                            </span>
                            <span v-else class="lv-unset">—</span>
                          </button>
                        </template>
                        <CreatablePicker
                          :options="(store.projectLabels||[]).map(l => ({ key: l.label, label: l.label, color: l.color }))"
                          :model-value="issueLabels(issue)" multiple :allow-empty="false"
                          noun="label" search-placeholder="Search or create label…"
                          @select="key => togLabel(issue, key)"
                          @create="name => createLabelInline(issue, name)"
                        />
                      </FieldDropdown>
                    </template>
                  </td>
                  <td class="lv-td lv-td-ghost"/>
                </tr>
                <!-- Child rows in grouped view -->
                <template v-if="expanded.has(issue.name) && issue.sub_tasks?.length">
                  <tr v-for="(child,ci) in issue.sub_tasks" :key="child.name"
                      class="lv-row lv-child-row"
                      @click="store.openTaskDetail(child.name)"
                      @contextmenu.prevent="openCtx($event,child)">
                    <td class="lv-td lv-cb-td lv-sticky lv-sticky-cb"/>
                    <td class="lv-td lv-title-td lv-child-title-td lv-sticky lv-sticky-title">
                      <span class="lv-child-indent" :class="{'is-last':ci===issue.sub_tasks.length-1}"/>
                          <span class="lv-title lv-title-child">{{ child.title }}</span>
                    </td>
                    <td v-for="col in visibleCols" :key="col.key" :class="['lv-td',col.key==='timeline'?'':'lv-td-edit',{'lv-td-center':col.key==='due'||col.key==='timeline'}]" @click.stop>
                      <template v-if="col.key==='status'">
                        <FieldDropdown width="w-40">
                          <template #trigger>
                            <button class="lv-status-pill" :style="statusStyle(child.status)">
                              {{ child.status }}</button>
                          </template>
                          <DropdownItem v-for="s in store.workflowStates" :key="s.name" :active="child.status===s.name" @click="save(child,'status',s.name)">
                            <span class="lv-dot" :style="{background:s.color}"/>{{ s.name }}
                          </DropdownItem>
                        </FieldDropdown>
                      </template>
                      <template v-else-if="col.key==='priority'">
                        <button class="lv-prio-pill" :title="child.priority||'No priority'"><PriorityIcon v-if="child.priority" :priority="child.priority"/><span v-else class="lv-unset">—</span></button>
                      </template>
                      <template v-else-if="col.key==='type'">
                        <span class="lv-field-plain">
                          <span class="lv-type-badge" :style="{background:typeColor(child.task_type)}">{{ (child.task_type||'T').charAt(0) }}</span>
                          <span>{{ child.task_type||'—' }}</span>
                        </span>
                      </template>
                      <template v-else-if="col.key==='assignee'">
                        <span v-if="child.assignees?.length" style="display:inline-flex;align-items:center;gap:6px;padding:0 8px">
                          <span class="lv-av" :style="{background:avatarColor(child.assignees[0].user)}" :title="child.assignees[0].full_name">{{ initials(child.assignees[0].full_name) }}</span>
                        </span>
                        <span v-else class="lv-av-empty" title="Assign"/>
                      </template>
                      <template v-else-if="col.key==='timeline'">
                    <span class="lv-unset">{{ timelineLabel(child)==='Set dates'?'—':timelineLabel(child) }}</span>
                  </template>
                  <template v-else-if="col.key==='due'">
                        <div class="lv-date-td" :class="{overdue:isOverdue(child),today:isDueToday(child),soon:isDueSoon(child)}">
                          <DatePicker :modelValue="child.due_date||null" placeholder="—" @update:modelValue="v=>save(child,'due_date',v||null)"/>
                        </div>
                      </template>
                      <template v-else-if="col.key==='sprint'">
                        <span v-if="child.sprint" class="lv-sprint-chip">{{ sprintName(child.sprint) }}</span>
                        <span v-else class="lv-unset">—</span>
                      </template>
                      <template v-else-if="col.key==='epic'">
                        <span v-if="child.epic" class="lv-epic-chip">{{ epicName(child.epic) }}</span>
                        <span v-else class="lv-unset">—</span>
                      </template>
                      <template v-else-if="col.key==='points'">
                        <span class="lv-unset" style="padding:0 8px">{{ child.story_points||'—' }}</span>
                      </template>
                      <template v-else-if="col.key==='labels'">
                        <div class="lv-label-row">
                          <span v-for="lbl in issueLabels(child).slice(0,2)" :key="lbl" class="lv-lbl-chip" :style="labelStyle(lbl)">{{ lbl }}</span>
                        </div>
                      </template>
                    </td>
                    <td class="lv-td lv-td-ghost"/>
                  </tr>
                </template>
              </template>
              <tr class="lv-add-row">
                <td class="lv-td lv-cb-td lv-sticky lv-sticky-cb"/>
                <td :colspan="totalCols" class="lv-add-td" @click.stop>
                  <button class="lv-add-btn" @click="quickCreate(group)">+ Add task</button>
                </td>
              </tr>
          </tbody>
          </template>
        </template>
      </table>
    </div>

    <!-- Column context menu -->
    <template v-if="colMenu.open">
      <div class="fixed inset-0 z-[1998]" @click="colMenu.open=false" @contextmenu.prevent="colMenu.open=false"/>
      <div class="lv-col-ctx" :style="{top:colMenu.y+'px',left:colMenu.x+'px'}">
        <button class="lv-ctx-item" :disabled="colMenu.idx===0" @click="moveCol(colMenu.idx,-1)">
          <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg> Move left
        </button>
        <button class="lv-ctx-item" :disabled="colMenu.idx===visibleCols.length-1" @click="moveCol(colMenu.idx,1)">
          <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg> Move right
        </button>
        <button class="lv-ctx-item" @click="moveColTo(colMenu.idx,0)">Move to start</button>
        <button class="lv-ctx-item lv-ctx-sep" @click="moveColTo(colMenu.idx,visibleCols.length-1)">Move to end</button>
        <button class="lv-ctx-item lv-ctx-danger" @click="colMenu.col&&toggleCol(colMenu.col.key)">Hide column</button>
      </div>
    </template>

    <!-- ERPNext "Connect data" modal -->
    <div v-if="showErpModal" class="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40" @click.self="closeErpModal">
      <div class="bg-surface rounded-xl shadow-overlay w-[480px] max-w-[92vw] p-5">
        <h3 class="text-[15px] font-semibold text-foreground mb-1">Connect ERPNext data</h3>
        <p class="text-[12px] text-muted mb-3">Pick a document type to link to your tasks.</p>

        <!-- Bordered doctype cards -->
        <div class="grid grid-cols-2 gap-2 max-h-[260px] overflow-auto">
          <button
            v-for="d in ERP_DOCTYPES" :key="d.name"
            class="flex items-center gap-2.5 p-3 rounded-lg border text-left transition-colors"
            :class="erpPick===d.name ? 'border-accent bg-accent-soft' : 'border-[var(--field-border)] hover:bg-default'"
            @click="pickErpDoctype(d.name)"
          >
            <span class="lv-erp-ic">{{ dtAbbr(d.name) }}</span>
            <span class="text-[13px] font-medium text-foreground truncate">{{ d.name }}</span>
          </button>
        </div>

        <!-- Inline config for the selected doctype -->
        <div v-if="erpPick" class="mt-4 pt-4 border-t border-separator">
          <p class="text-[12px] font-semibold text-muted mb-2">Mirror fields · {{ erpPick }}</p>
          <div class="grid grid-cols-2 gap-x-3 gap-y-0.5 max-h-[200px] overflow-auto">
            <label v-for="f in (mirrorSchema[erpPick]||[])" :key="f.fieldname" class="flex items-center gap-2 px-2 py-1.5 rounded-lg text-[13px] hover:bg-default cursor-pointer">
              <input type="checkbox" :checked="erpFieldSel.has(f.fieldname)" @change="toggleErpField(f.fieldname)"/>
              <span class="flex-1 truncate">{{ f.label }}</span>
            </label>
            <p v-if="!(mirrorSchema[erpPick]||[]).length" class="col-span-2 text-[12px] text-muted px-2 py-3">No mirrorable fields configured for this doctype.</p>
          </div>
          <label class="flex items-center justify-between gap-2 mt-3 text-[13px] text-foreground">
            <span>Two-way link (back-link the ERP document)</span>
            <Switch :model-value="erpTwoWaySel" @update:model-value="v=>erpTwoWaySel=v"/>
          </label>
        </div>

        <div class="flex justify-end gap-2 mt-4">
          <button class="px-3 h-8 rounded-lg text-[13px] text-muted hover:bg-default" @click="closeErpModal">Cancel</button>
          <button class="px-3 h-8 rounded-lg text-[13px] bg-accent text-white hover:bg-[var(--accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed" :disabled="!erpPick" @click="addErpColumn(erpPick,[...erpFieldSel],erpTwoWaySel)">Add column</button>
        </div>
      </div>
    </div>

    <TaskContextMenu v-if="ctxIssue" :issue="ctxIssue" :x="ctxX" :y="ctxY" @close="ctxIssue=null"/>

    <MoneyDrawer v-model:open="moneyDrawerOpen" :project="store.currentProject?.name"
      :doctype="moneyDrawerDoctype" :name="moneyDrawerName" @submitted="refreshMirrors"/>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { PRIORITIES, PRIORITY_MAP, avatarColor, initials } from '@/utils/constants.js'
import { toast } from 'vue-sonner'
import { createTask, getMirrorSchema, getMirrorValues, getViewPrefs, saveViewPrefs, deleteTask, createEpic, updateProjectLabels, createSprint } from '@/utils/api'
import CreatablePicker from '@/components/CreatablePicker.vue'
import { formatMirrorValue } from '@/utils/mirrorFormat.js'
import { resolveMarkerColor } from '@/utils/customFields.js'
import { ERP_DOCTYPES, MONEY_DRAWER_DOCTYPES } from '@/constants/erp-doctypes'
import { EmptyState, Switch, Skeleton, Tooltip } from '@/ui'
import { LayoutList } from 'lucide-vue-next'
import FieldDropdown    from '@/components/FieldDropdown.vue'
import DropdownItem     from '@/components/DropdownItem.vue'
import PriorityIcon     from '@/components/PriorityIcon.vue'
import DatePicker       from '@/components/DatePicker.vue'
import TaskContextMenu  from '@/components/TaskContextMenu.vue'
import ConnectCell      from '@/components/list/ConnectCell.vue'
import MoneyDrawer      from '@/components/MoneyDrawer.vue'
import ConnectorCell    from '@/components/list/ConnectorCell.vue'
import BlockedCell      from '@/components/list/BlockedCell.vue'
import { confirmDialog } from '@/composables/useConfirmDialog'

const route      = useRoute()
const store      = useProjectStore()
const projectKey = computed(() => route.params.key)

const ALL_COLS = [
  { key:'status',   label:'Status',       sortField: null,           defaultWidth: 160 },
  { key:'priority', label:'Priority',     sortField: 'priority',     defaultWidth: 120 },
  { key:'type',     label:'Type',         sortField: null,           defaultWidth: 120 },
  { key:'assignee', label:'Assignee',     sortField: null,           defaultWidth: 180 },
  { key:'timeline', label:'Timeline',     sortField: 'start_date',   defaultWidth: 170 },
  { key:'blocked',  label:'Blocked by',   sortField: null,           defaultWidth: 150 },
  { key:'connected',label:'Connected',    sortField: null,           defaultWidth: 150 },
  { key:'relations',label:'Connections',  sortField: null,           defaultWidth: 170 },
  { key:'due',      label:'Due Date',     sortField: 'due_date',     defaultWidth: 130 },
  { key:'sprint',   label:'Sprint',       sortField: null,           defaultWidth: 140 },
  { key:'epic',     label:'Epic',         sortField: null,           defaultWidth: 140 },
  { key:'points',   label:'Points',       sortField: 'story_points', defaultWidth: 80  },
  { key:'labels',   label:'Labels',       sortField: null,           defaultWidth: 180 },
]

// persisted state
const colOrder   = ref(ALL_COLS.map(c => c.key))
// Clean by default — power columns live behind the "+" header button
const DEFAULT_HIDDEN = new Set(['due', 'blocked', 'connected', 'sprint', 'epic', 'labels'])
const hiddenCols = ref(new Set(DEFAULT_HIDDEN))
const cw         = reactive({ cb:36, title:400, ...Object.fromEntries(ALL_COLS.map(c=>[c.key,c.defaultWidth])) })
const density    = ref('default')

// ERPNext data columns ( user-added, persisted.
// Entries: { doctype, twoWay } — twoWay also backlinks the ERP document.
const erpCols = ref([])
// Mirror columns project whitelisted fields of connected docs: {doctype, field}
const mirrorCols = ref([])
const mirrorSchema = ref({})   // {doctype: [{fieldname,label,fieldtype}]}
const mirrorData = reactive({}) // {doctype: {ref_name: {field: value}}}

function dtAbbr(dt){ return dt.split(' ').map(w => w[0]).join('').toUpperCase() }
function mirrorFieldMeta(dt, field){ return (mirrorSchema.value[dt] || []).find(f => f.fieldname === field) }

// Custom fields → first-class columns
const CF_WIDTHS = { number: 100, date: 130, select: 150, multiselect: 190, textarea: 200 }
const cfDefs = computed(() => (store.customFieldsSchema || []).map(f => ({
  key: 'cf:' + f.id, label: f.label, sortField: null,
  defaultWidth: CF_WIDTHS[f.type] || 160, cf: f,
})))

const colDefs = computed(() => [
  ...ALL_COLS,
  ...cfDefs.value,
  ...erpCols.value.map(e => ({ key: 'erp:' + e.doctype, label: e.doctype, sortField: null, defaultWidth: 170 })),
  ...mirrorCols.value.map(m => ({
    key: `mirror:${m.doctype}:${m.field}`,
    label: `${dtAbbr(m.doctype)} · ${mirrorFieldMeta(m.doctype, m.field)?.label || m.field}`,
    sortField: `mirror:${m.doctype}:${m.field}`, defaultWidth: 130,
    mirror: m,
  })),
])
function erpTwoWay(dt){ return !!erpCols.value.find(e => e.doctype === dt)?.twoWay }

watch(cfDefs, (defs) => {
  if (!defs.length) return
  const hid = new Set(hiddenCols.value)
  let changed = false
  for (const d of defs) {
    if (!colOrder.value.includes(d.key)) {
      colOrder.value = [...colOrder.value, d.key]
      hid.add(d.key)            // opt-in via "+", keep the table clean
      changed = true
    }
    if (!(d.key in cw)) cw[d.key] = d.defaultWidth
  }
  if (changed) hiddenCols.value = hid
}, { immediate: true })
const visibleCols = computed(() =>
  colOrder.value
    .map(k => colDefs.value.find(c => c.key === k))
    .filter(Boolean)
    .filter(c => !hiddenCols.value.has(c.key))
)

// ── ERPNext "Connect data" modal state ──────────────────────────────────────
const showErpModal = ref(false)
const erpPick = ref(null)         // selected doctype card
const erpFieldSel = ref(new Set())
const erpTwoWaySel = ref(false)
function pickErpDoctype(dt){ erpPick.value = dt; erpFieldSel.value = new Set(); erpTwoWaySel.value = false }
function resetErpModal(){ erpPick.value = null; erpFieldSel.value = new Set(); erpTwoWaySel.value = false }
function closeErpModal(){ showErpModal.value = false; resetErpModal() }
function toggleErpField(f){ const sset = new Set(erpFieldSel.value); sset.has(f) ? sset.delete(f) : sset.add(f); erpFieldSel.value = sset }

function addErpColumn(dt, fields = [], twoWay = false) {
  const existing = erpCols.value.find(e => e.doctype === dt)
  if (existing) existing.twoWay = twoWay
  else erpCols.value = [...erpCols.value, { doctype: dt, twoWay }]
  const hid = new Set(hiddenCols.value)
  const keys = ['erp:' + dt, ...fields.map(f => `mirror:${dt}:${f}`)]
  for (const f of fields) {
    if (!mirrorCols.value.find(m => m.doctype === dt && m.field === f))
      mirrorCols.value = [...mirrorCols.value, { doctype: dt, field: f }]
  }
  for (const key of keys) {
    if (!colOrder.value.includes(key)) colOrder.value = [...colOrder.value, key]
    if (!(key in cw)) cw[key] = key.startsWith('mirror:') ? 130 : 170
    hid.delete(key)
  }
  hiddenCols.value = hid
  showErpModal.value = false
  resetErpModal()
  savePrefs()
  loadMirrorValues()
}
const totalCols  = computed(() => 2 + visibleCols.value.length)
function isVisible(key) { return !hiddenCols.value.has(key) }

// ── Persistence (per-user, server-side — follows the user across devices) ──────
// Column layout / widths / density / ERP columns live in BP View Preference keyed
// by (user, project, "list"), not browser localStorage. `prefsLoaded` guards the
// initial default state from saving over server prefs before the first fetch;
// saves are debounced so dragging/resizing doesn't spam the API.
let prefsLoaded = false
let _saveTimer = null

function savePrefs() {
  if (!prefsLoaded) return
  if (_saveTimer) clearTimeout(_saveTimer)
  _saveTimer = setTimeout(flushPrefs, 500)
}

function flushPrefs() {
  _saveTimer = null
  const key = projectKey.value
  if (!key) return
  saveViewPrefs(key, {
    colOrder: colOrder.value,
    hidden:   [...hiddenCols.value],
    widths:   {...cw},
    density:  density.value,
    erpCols:  erpCols.value,
    mirrorCols: mirrorCols.value,
  }).catch(() => {})
}

function applyPrefs(s) {
  s = s && typeof s === 'object' ? s : {}
  if (Array.isArray(s.erpCols))
    erpCols.value = s.erpCols.map(e => typeof e === 'string' ? { doctype: e, twoWay: false } : e)
  if (Array.isArray(s.mirrorCols)) mirrorCols.value = s.mirrorCols
  if (s.colOrder?.length) {
    const known = new Set([
      ...ALL_COLS.map(c => c.key),
      ...(erpCols.value).map(e => 'erp:' + e.doctype),
      ...(mirrorCols.value).map(m => `mirror:${m.doctype}:${m.field}`),
    ])
    const saved = s.colOrder.filter(k => known.has(k) || k.includes(':'))
    const missing = ALL_COLS.map(c => c.key).filter(k => !saved.includes(k))
    colOrder.value = [...saved, ...missing]
    const hid = new Set(s.hidden || [])
    missing.forEach(k => { if (DEFAULT_HIDDEN.has(k)) hid.add(k) })
    hiddenCols.value = hid
  }
  if (s.hidden && !s.colOrder?.length) hiddenCols.value = new Set(s.hidden)
  if (s.widths)  Object.assign(cw, s.widths)
  if (s.density) density.value = s.density
}

async function loadPrefs() {
  prefsLoaded = false
  const key = projectKey.value
  if (!key) { prefsLoaded = true; return }
  try { applyPrefs(await getViewPrefs(key)) } catch {}
  prefsLoaded = true
}

watch(density, savePrefs)

// ── Column actions ────────────────────────────────────────────────────────────
function toggleCol(key) {
  const s = new Set(hiddenCols.value)
  s.has(key) ? s.delete(key) : s.add(key)
  hiddenCols.value = s
  colMenu.open = false
  savePrefs()
}

function moveCol(fromIdx, dir) {
  const vis  = visibleCols.value.map(c => c.key)
  const from = vis[fromIdx], to = vis[fromIdx + dir]
  const arr  = [...colOrder.value]
  const a = arr.indexOf(from), b = arr.indexOf(to)
  ;[arr[a], arr[b]] = [arr[b], arr[a]]
  colOrder.value = arr
  colMenu.open = false
  savePrefs()
}

function moveColTo(fromIdx, toIdx) {
  const vis     = visibleCols.value.map(c => c.key)
  const fromKey = vis[fromIdx], toKey = vis[toIdx]
  const arr     = [...colOrder.value]
  arr.splice(arr.indexOf(fromKey), 1)
  const b = arr.indexOf(toKey)
  arr.splice(toIdx === 0 ? b : b + 1, 0, fromKey)
  colOrder.value = arr
  colMenu.open = false
  savePrefs()
}

// ── Column drag-reorder (drag a header onto another) ──
const _dragCol = ref(null)
const _dropKey  = ref(null)
const _dropSide = ref('left')
let _resizeArm = false
function armResize(){ _resizeArm = true; window.addEventListener('mouseup', () => { _resizeArm = false }, { once: true }) }
function onColDragStart(e, key) {
  if (_resizeArm) { e.preventDefault(); return }
  _dragCol.value = key
  e.dataTransfer.effectAllowed = 'move'
}
function onColDragOver(e, key) {
  if (!_dragCol.value || key === _dragCol.value) { _dropKey.value = null; return }
  const r = e.currentTarget.getBoundingClientRect()
  _dropSide.value = (e.clientX - r.left) < r.width / 2 ? 'left' : 'right'
  _dropKey.value = key
}
function onColDragEnd() { _dragCol.value = null; _dropKey.value = null }
function onColDrop(key) {
  const from = _dragCol.value, side = _dropSide.value
  onColDragEnd()
  if (!from || from === key) return
  const arr = [...colOrder.value]
  arr.splice(arr.indexOf(from), 1)
  const idx = arr.indexOf(key)
  arr.splice(side === 'left' ? idx : idx + 1, 0, from)
  colOrder.value = arr
  savePrefs()
}
function colDragClass(key) {
  return {
    'lv-col-dragging': _dragCol.value === key,
    'lv-drop-left':  _dropKey.value === key && _dropSide.value === 'left',
    'lv-drop-right': _dropKey.value === key && _dropSide.value === 'right',
  }
}

// ── Column resize ───────────────────────────────────────────────────────────
function startResize(e, col) {
  e.preventDefault()
  const x0 = e.clientX, w0 = cw[col]
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  const move = ev => { cw[col] = Math.max(60, w0 + ev.clientX - x0) }
  const up   = () => {
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', move)
    window.removeEventListener('mouseup', up)
    savePrefs()
  }
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', up)
}

// ── Column context menu ───────────────────────────────────────────────────────
const colMenu = reactive({ open:false, x:0, y:0, col:null, idx:0 })
function openColMenu(e, col, idx) {
  // Anchor to the 3-dots button itself, right-aligned, clamped to the viewport.
  const btn = (e.currentTarget || e.target)?.getBoundingClientRect?.()
  if (!btn) return
  const W = 184
  // Anchor the menu's left edge to the dots button, opening downward; only
  // shift left if it would overflow the right edge of the viewport.
  colMenu.x = Math.max(8, Math.min(btn.left - 160, window.innerWidth - W - 8))
  colMenu.y = btn.bottom - 16
  colMenu.col = col; colMenu.idx = idx; colMenu.open = true
}

// ── Density / sort / select ───────────────────────────────────────────────────
const DENSITIES = [
  { v:'compact',     label:'Compact',     icon:'M4 5h16M4 8h16M4 11h16M4 14h16M4 17h16' },
  { v:'default',     label:'Default',     icon:'M4 6h16M4 12h16M4 18h16' },
  { v:'comfortable', label:'Comfortable', icon:'M4 7h16M4 17h16' },
]

const sortBy=ref('title'), sortDir=ref('asc')
function setSort(col){if(!col)return;if(sortBy.value===col)sortDir.value=sortDir.value==='asc'?'desc':'asc';else{sortBy.value=col;sortDir.value='asc'}}

const selected=reactive(new Set())
const allSel=computed(()=>flatIssues.value.length>0&&flatIssues.value.every(i=>selected.has(i.name)))
const someSel=computed(()=>flatIssues.value.some(i=>selected.has(i.name)))
function groupAllSel(g){return g.issues.length>0&&g.issues.every(i=>selected.has(i.name))}
function groupSomeSel(g){return g.issues.some(i=>selected.has(i.name))}
function toggleGroupSel(g){const all=groupAllSel(g);g.issues.forEach(i=>all?selected.delete(i.name):selected.add(i.name))}
function toggleSelect(n){selected.has(n)?selected.delete(n):selected.add(n)}
function toggleAll(){if(allSel.value)flatIssues.value.forEach(i=>selected.delete(i.name));else flatIssues.value.forEach(i=>selected.add(i.name))}
async function bulkStatus(status){const names=[...selected];await Promise.allSettled(names.map(n=>store.updateTaskField(n,'status',status)));toast.success(`${names.length} tasks → ${status}`);selected.clear()}
async function bulkPriority(priority){const names=[...selected];await Promise.allSettled(names.map(n=>store.updateTaskField(n,'priority',priority)));toast.success(`${names.length} tasks → ${priority}`);selected.clear()}
async function bulkAssign(user){const names=[...selected];await Promise.allSettled(names.map(n=>store.updateTaskField(n,'assignees',[{user}])));toast.success(`${names.length} tasks assigned`);selected.clear()}
async function bulkMoveSprint(sprint){const names=[...selected];await Promise.allSettled(names.map(n=>store.updateTaskField(n,'sprint',sprint)));toast.success(`${names.length} tasks → ${sprint}`);selected.clear()}
async function bulkMoveEpic(epic){const names=[...selected];await Promise.allSettled(names.map(n=>store.updateTaskField(n,'epic',epic)));toast.success(`${names.length} tasks → ${epic}`);selected.clear()}
async function bulkDelete(){const names=[...selected];if(!await confirmDialog(`Delete ${names.length} tasks? This cannot be undone.`,{danger:true}))return;await Promise.allSettled(names.map(n=>deleteTask(n)));selected.clear();store.refreshBoard();toast.success(`${names.length} tasks deleted`)}

const ctxIssue=ref(null),ctxX=ref(0),ctxY=ref(0)
function openCtx(e,issue){ctxIssue.value=issue;ctxX.value=e.clientX;ctxY.value=e.clientY}

const aQ=ref('')
const filteredMembers=computed(()=>{const q=aQ.value.toLowerCase();return(store.projectMembers||[]).filter(m=>!q||m.full_name?.toLowerCase().includes(q))})
function hasA(issue,usr){return(issue.assignees||[]).some(a=>a.user===usr)}
function togA(issue,m){const cur=issue.assignees||[];save(issue,'assignees',hasA(issue,m.user)?cur.filter(a=>a.user!==m.user):[...cur,{user:m.user,full_name:m.full_name}])}

// ── Issues ────────────────────────────────────────────────────────────────────
const allIssues=computed(()=>Object.values(store.board).flat())
const flatIssues=computed(()=>{
  let issues=allIssues.value
  if(store.boardSprintFilter==='active_sprint'){
    const activeSprint=store.sprints.find(s=>s.status==='Active')
    if(activeSprint) issues=issues.filter(i=>i.sprint===activeSprint.name)
  }
  const q=store.boardViewState.search?.toLowerCase()
  if(q)issues=issues.filter(i=>i.title?.toLowerCase().includes(q)||i.task_key?.toLowerCase().includes(q))
  if(store.boardViewState.filterAssignee)issues=issues.filter(i=>(i.assignees||[]).some(a=>a.full_name===store.boardViewState.filterAssignee))
  if(store.boardViewState.filterPriority)issues=issues.filter(i=>i.priority===store.boardViewState.filterPriority)
  if(store.boardViewState.filterType)    issues=issues.filter(i=>i.task_type===store.boardViewState.filterType)
  if(store.boardViewState.filterLabel)   issues=issues.filter(i=>issueLabels(i).includes(store.boardViewState.filterLabel))
  return issues
})
const PORD={Highest:0,High:1,Medium:2,Low:3,Lowest:4}
const sortedIssues=computed(()=>{
  const as=(store.boardSortBy&&store.boardSortBy!=='board_order')?store.boardSortBy:sortBy.value
  const dir=(store.boardSortBy&&store.boardSortBy!=='board_order')?'asc':sortDir.value
  return[...flatIssues.value].sort((a,b)=>{
    let av,bv
    if(as.startsWith('mirror:')){av=mirrorSortVal(a,as);bv=mirrorSortVal(b,as)}
    else{av=a[as]??'';bv=b[as]??''}
    if(as==='priority'){av=PORD[av]??99;bv=PORD[bv]??99}
    if(as==='story_points'){av=Number(av)||0;bv=Number(bv)||0}
    return av<bv?(dir==='asc'?-1:1):av>bv?(dir==='asc'?1:-1):0
  })
})

const collapsedGroups=ref(new Set())
const expanded=ref(new Set())
function toggleGroup(k){const s=new Set(collapsedGroups.value);s.has(k)?s.delete(k):s.add(k);collapsedGroups.value=s}
function toggleExpand(n){const s=new Set(expanded.value);s.has(n)?s.delete(n):s.add(n);expanded.value=s}

const groups=computed(()=>{
  const g=store.boardGroupBy;if(!g||g==='none')return[]
  let keys=[]
  if(g==='status')keys=store.columns||[]
  else if(g==='priority')keys=['Highest','High','Medium','Low','Lowest']
  else if(g==='assignee'){const n=[...new Set(flatIssues.value.map(i=>i.assignees?.[0]?.full_name||'Unassigned'))].sort();keys=n.includes('Unassigned')?n:[...n,'Unassigned']}
  else if(g==='type')keys=store.taskTypes?.map(t=>t.name)||[]
  else if(g==='label'){const pl=(store.currentProject?.labels||[]).map(l=>l.label);const u=[...new Set(flatIssues.value.flatMap(i=>issueLabels(i)))];const a=[...new Set([...pl,...u])].filter(Boolean);keys=a.length?[...a,'No Label']:['No Label']}
  const map=new Map();for(const k of keys)map.set(k,{key:k,color:groupColor(g,k),issues:[]})
  for(const issue of sortedIssues.value){
    let b
    if(g==='status')b=issue.status
    else if(g==='priority')b=issue.priority||'Medium'
    else if(g==='assignee')b=issue.assignees?.[0]?.full_name||'Unassigned'
    else if(g==='type')b=issue.task_type||store.taskTypes?.[0]?.name||'Task'
    else if(g==='label'){const lbls=issueLabels(issue);if(!lbls.length){map.get('No Label')?.issues.push(issue);continue}let p=false;for(const l of lbls){if(map.has(l)){map.get(l).issues.push(issue);p=true}}if(!p)map.get('No Label')?.issues.push(issue);continue}
    if(map.has(b))map.get(b).issues.push(issue);else map.set(b,{key:b,color:groupColor(g,b),issues:[issue]})
  }
  return[...map.values()].filter(gr=>gr.issues.length>0)
})
function groupColor(g,k){
  if(g==='status')  return store.workflowStateMap?.[k]?.color||null
  if(g==='priority')return PRIORITY_MAP[k]?.color||null
  if(g==='type')    return store.taskTypeMap?.[k]?.color||null
  if(g==='label')   return store.currentProject?.labels?.find(l=>l.label===k)?.color||null
  return null
}

// Group summaries (sum / counts) shown inline in the group heading.
// Only surfaces aggregates for columns that are currently visible.
function groupSummaries(group){
  const items = group.issues || []
  const out = []
  if(!items.length) return out
  for(const col of visibleCols.value){
    if(col.key==='points'){
      const s = items.reduce((a,i)=>a+(Number(i.story_points)||0),0)
      if(s) out.push({ key:'points', text:'Σ '+s+' pts' })
    } else if(col.key==='due'){
      const n = items.filter(isOverdue).length
      if(n) out.push({ key:'due', text:n+' overdue', danger:true })
    } else if(col.key==='assignee'){
      const u = new Set(); items.forEach(i=>(i.assignees||[]).forEach(a=>u.add(a.user)))
      if(u.size) out.push({ key:'assignee', text:u.size+(u.size===1?' person':' people') })
    } else if(col.key.startsWith('cf:') && col.cf?.type==='number'){
      const s = items.reduce((a,i)=>a+(Number(cfValue(i,col.cf))||0),0)
      if(s) out.push({ key:col.key, text:col.label+' Σ '+s })
    }
  }
  return out
}

// ── Cell helpers ──────────────────────────────────────────────────────────────
// Status colors are arbitrary hex the user picks in Project Settings — a
// fixed white label  fails on light picks (yellow,
// mint), so pick white/near-black by relative luminance instead of assuming.
function _readableOn(hex){
  const m=/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex||'')
  if(!m) return '#fff'
  const [r,g,b]=[m[1],m[2],m[3]].map(h=>parseInt(h,16)/255)
  const lin=c=>c<=0.03928?c/12.92:Math.pow((c+0.055)/1.055,2.4)
  const L=0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b)
  return L>0.55?'#1a1a1a':'#fff'
}
function statusStyle(status){
  const c=store.workflowStateMap?.[status]?.color|| 'var(--muted)'
  return{'--sc':c,'--st':_readableOn(c)}
}
function priorityStyle(p){return{background:PRIORITY_MAP[p]?.color|| 'var(--muted)',color:'var(--accent-foreground)'}}
function typeColor(t){return store.taskTypeMap?.[t]?.color|| 'var(--accent)'}
function isOverdue(i){return i.due_date&&new Date(i.due_date)<new Date(new Date().setHours(0,0,0,0))}
function isDueToday(i){if(!i.due_date)return false;const d=new Date(i.due_date),t=new Date();return d.toDateString()===t.toDateString()}
function isDueSoon(i){if(!i.due_date||isOverdue(i)||isDueToday(i))return false;return(new Date(i.due_date)-new Date())/(1000*60*60*24)<=3}

// ── Blocked / connected (BP Task Link + references) ─────────────────────────────
function blockers(i){return(i.links||[]).filter(a=>a.link_type==='is blocked by')}
function refsOf(issue,dt){return(issue.references||[]).filter(r=>r.ref_doctype===dt)}
function refSummary(issue){const a={};for(const r of issue.references||[])a[r.ref_doctype]=(a[r.ref_doctype]||0)+1;return Object.entries(a).map(([doctype,n])=>({doctype,n,abbr:doctype.split(' ').map(w=>w[0]).join('').toUpperCase()}))}

// ── Mirror columns (project whitelisted fields of connected docs) ───────────────
async function loadMirrorSchema(){try{mirrorSchema.value=(await getMirrorSchema(store.currentProject?.name))||{}}catch(e){}}
async function loadMirrorValues(){
  const dts=[...new Set(mirrorCols.value.map(m=>m.doctype))]
  for(const dt of dts){
    const want=new Set()
    for(const issue of allIssues.value)for(const r of issue.references||[])if(r.ref_doctype===dt)want.add(r.ref_name)
    const have=mirrorData[dt]||{}
    const missing=[...want].filter(n=>!(n in have))
    if(missing.length)try{const got=await getMirrorValues(dt,missing,store.currentProject?.name);mirrorData[dt]={...have,...got}}catch(e){}
  }
}
function mirrorDisplay(issue,col){
  const {doctype,field}=col.mirror
  const meta=mirrorFieldMeta(doctype,field)
  const out=[]
  for(const r of issue.references||[]){
    if(r.ref_doctype!==doctype)continue
    const rec=mirrorData[doctype]?.[r.ref_name]
    const val=rec?.[field]
    if(val==null||val==='')continue
    out.push({text:formatMirrorValue(val,meta?.fieldtype,rec),name:r.ref_name})
  }
  return out
}
const MIRROR_NUMERIC=new Set(['Currency','Float','Int','Percent'])
function mirrorSortVal(issue,key){
  const[,doctype,field]=key.split(':')
  const numeric=MIRROR_NUMERIC.has(mirrorFieldMeta(doctype,field)?.fieldtype)
  let sum=0,first=''
  for(const r of issue.references||[]){
    if(r.ref_doctype!==doctype)continue
    const val=mirrorData[doctype]?.[r.ref_name]?.[field]
    if(val==null||val==='')continue
    if(numeric)sum+=Number(val)||0
    else if(!first)first=String(val)
  }
  return numeric?sum:first
}

// mirror/reference cells deep-link via the Money drawer (8E), not
// raw /app links; doctypes the drawer can't summarize fall back to ERPNext.
const moneyDrawerOpen    = ref(false)
const moneyDrawerDoctype = ref('')
const moneyDrawerName    = ref('')
function openMirrorDoc(doctype,name){
  if(MONEY_DRAWER_DOCTYPES.has(doctype)){
    moneyDrawerDoctype.value=doctype
    moneyDrawerName.value=name
    moneyDrawerOpen.value=true
  }else{
    window.open(`/app/${doctype.toLowerCase().replace(/ /g,'-')}/${encodeURIComponent(name)}`,'_blank','noopener')
  }
}
function refreshMirrors(){
  for(const dt of Object.keys(mirrorData))delete mirrorData[dt]
  loadMirrorValues()
}
function cfValue(issue, f){ const v = issue.custom_field_values?.[f.id]; return v === undefined ? null : v }
function cfOptionLabel(f, id){ return (f.options || []).find(o => o.id === id)?.label || id }
function cfMarker(issue, f){ return resolveMarkerColor(f, cfValue(issue, f)) }
function saveCf(issue, f, val){
  issue.custom_field_values = { ...(issue.custom_field_values || {}), [f.id]: val }
  save(issue, 'custom_field_values', { [f.id]: val })
}
function cfMulti(issue, f){ const v = cfValue(issue, f); return Array.isArray(v) ? v : [] }
function cfMultiToggle(issue, f, id){
  const cur = cfMulti(issue, f)
  saveCf(issue, f, cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id])
}
function timelineLabel(i){
  const f=d=>{if(!d)return null;const[y,m,dd]=d.split('-').map(Number);const dt=new Date(y,m-1,dd);return dt.toLocaleDateString('en-US',{month:'short',day:'numeric'})}
  const a=f(i.start_date),b=f(i.due_date)
  if(a&&b)return`${a} – ${b}`
  if(b)return`→ ${b}`
  if(a)return`${a} →`
  return'Set dates'
} 
function isDone(i){return store.workflowStateMap?.[i.status]?.category==='completed'}
function timelineStyle(i){
  if(!i.start_date&&!i.due_date)return null
  // Past its end date but not yet completed → orange (warning).
  if(isOverdue(i)&&!isDone(i)){
    return{background:'var(--warning)',color:'var(--warning-foreground)'}
  }
  // Otherwise one accent hue — elapsed share fills with the deeper accent.
  let p=isDone(i)?100:0
  if(!p&&i.start_date&&i.due_date){
    const s0=new Date(i.start_date).getTime(),e0=new Date(i.due_date).getTime(),now=Date.now()
    p=e0>s0?Math.round(Math.min(100,Math.max(0,(now-s0)/(e0-s0)*100))):0
  }
  return{background:`linear-gradient(90deg, var(--accent-hover) ${p}%, var(--accent) ${p}%)`}
}
const hiddenColsList=computed(()=>colDefs.value.filter(c=>hiddenCols.value.has(c.key)))
function sprintName(id){return store.sprints?.find(s=>s.name===id)?.sprint_name||id}
function epicName(id){const ep=store.epics;if(Array.isArray(ep))return ep.find(e=>e.name===id)?.title||id;if(ep&&typeof ep==='object'){for(const arr of Object.values(ep)){const f=(Array.isArray(arr)?arr:[]).find(e=>e.name===id);if(f)return f.title||id}}return id}
function issueLabels(issue){const raw=issue.labels;if(!raw)return[];if(Array.isArray(raw))return raw;try{return JSON.parse(raw)}catch{return[]}}
function togLabel(issue,name){const cur=issueLabels(issue);const next=cur.includes(name)?cur.filter(l=>l!==name):[...cur,name];issue.labels=next;save(issue,'labels',next)}
const epicOptions=computed(()=>{const ep=store.epics;return Array.isArray(ep)?ep:(ep&&typeof ep==='object'?Object.values(ep).flat():[])})
function labelStyle(name){const l=(store.projectLabels||[]).find(l=>l.label===name);if(!l)return{background:'var(--surface-secondary)',color:'var(--muted)',borderColor:'var(--border)'};return{background:l.color+'18',color:l.color,borderColor:l.color+'40'}}
async function save(issue,field,value){try{await store.updateTaskField(issue.name,field,value)}catch(e){console.error(e)}}

// Inline "create if it doesn't exist" from the Epic picker — store.epics is
// only populated via a board fetch (no standalone fetchEpics action exists),
// so picking up the new one means a refresh, same as every other
// create-then-select flow already in this codebase.
async function createEpicInline(issue, title) {
  try {
    const epic = await createEpic(store.currentProject.name, { title })
    await store.refreshBoard()
    await save(issue, 'epic', epic.name)
    toast.success(`Epic "${title}" created`)
  } catch (e) {
    toast.error(e.message || 'Failed to create epic')
  }
}

const LABEL_COLOR_CYCLE = ['#0052CC','#36B37E','#FF5630','#FFAB00','#6554C0','#00B8D9','#DE350B','#00875A']
async function createLabelInline(issue, name) {
  const current = store.projectLabels || []
  if (current.some(l => l.label.toLowerCase() === name.toLowerCase())) {
    togLabel(issue, current.find(l => l.label.toLowerCase() === name.toLowerCase()).label)
    return
  }
  const color = LABEL_COLOR_CYCLE[current.length % LABEL_COLOR_CYCLE.length]
  try {
    const result = await updateProjectLabels(store.currentProject.name, [...current, { label: name, color }])
    store.currentProject.labels = result
    togLabel(issue, name)
    toast.success(`Label "${name}" created`)
  } catch (e) {
    toast.error(e.message || 'Failed to create label')
  }
}

async function createSprintInline(issue, name) {
  try {
    const sprint = await createSprint(store.currentProject.name, name)
    await store.fetchSprints(store.currentProject.name)
    await save(issue, 'sprint', sprint.name)
    toast.success(`Sprint "${name}" created`)
  } catch (e) {
    toast.error(e.message || 'Failed to create sprint')
  }
}

// ──  inline add + group summaries ───────────────────────────────
const addingIn=ref(null), newTitle=ref('')
async function addInline(group){
  const t=newTitle.value.trim(); if(!t) return
  const params={project:store.currentProject?.name, title:t, status:store.workflowStates?.[0]?.name||''}
  const g=store.boardGroupBy
  if(g==='status')params.status=group.key
  else if(g==='priority')params.priority=group.key
  else if(g==='type')params.task_type=group.key
  try{ await createTask(params); newTitle.value=''; await store.refreshBoard() }
  catch(e){ toast.error("Couldn't add task",{description:String(e.message||e)}) }
}
function groupSummary(group, by='status'){
  const total=group.issues.length||1
  const counts={}
  for(const issue of group.issues){const key=by==='priority'?(issue.priority||'Medium'):issue.status;counts[key]=(counts[key]||0)+1}
  const colorOf=key=>by==='priority'?(PRIORITY_MAP[key]?.color|| 'var(--muted)'):(store.workflowStateMap?.[key]?.color|| 'var(--muted)')
  const segs=Object.entries(counts).map(([key,n])=>({color:colorOf(key),pct:n/total*100}))
  const pts=group.issues.reduce((s,i)=>s+(Number(i.story_points)||0),0)
  return{segs,pts}
}
function quickCreate(group){const d={status:store.workflowStates?.[0]?.name||''};if(group){const g=store.boardGroupBy;if(g==='status')d.status=group.key;else if(g==='priority')d.priority=group.key;else if(g==='type')d.task_type=group.key;else if(g==='assignee')d.assignee=group.key==='Unassigned'?null:group.key};store.createTaskDefaults=d;store.showCreateTask=true}
const hasActiveFilters=computed(()=>!!(store.boardViewState.filterAssignee||store.boardViewState.filterPriority||store.boardViewState.filterType||store.boardViewState.filterLabel||(store.boardGroupBy&&store.boardGroupBy!=='status')))

// Export moved to ProjectHeader's "…" menu (project-level action now,
// reachable from any view, not just List) — see that component.

async function load(){
  await loadPrefs()
  if(!store.projects.length)await store.fetchProjects()
  const proj=store.projects.find(p=>p.key===projectKey.value)
  if(proj&&store.currentProject?.key!==projectKey.value)await store.fetchBoard(proj.name)
  if(store.currentProject)store.fetchSprints(store.currentProject.name)
  loadMirrorValues()
}
onMounted(() => { load(); loadMirrorSchema() })
watch(projectKey,()=>{ load() })
</script>

<style scoped>
.lv-root {
  display:flex;
  flex-direction:column;
  height:100%;
  background:var(--surface);
  overflow:hidden;
}
.lv-scroll {
  flex:1;
  overflow:auto;
  scrollbar-width:none;
  -ms-overflow-style:none;
  padding-bottom:48px;
  background:var(--surface);
}
.lv-scroll::-webkit-scrollbar {
  width:0;
  height:0;
  display:none;
}
.lv-table {
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  table-layout:fixed;
}
.lv-scroll {
  --rowh:40px;
  --cellb:1px solid var(--border);
}
.lv-scroll[data-density=compact] {
  --rowh:34px;
}
.lv-scroll[data-density=comfortable] {
  --rowh:48px;
}
.lv-subbar {
  display:flex;
  align-items:center;
  justify-content:space-between;
  height:42px;
  padding:0 16px 0 0;
  flex-shrink:0;
  gap:8px;
  background:var(--surface);
}
.lv-subbar-right {
  display:flex;
  align-items:center;
  gap:6px;
  flex-shrink:0;
}
.lv-subbar-left {
  display:flex; 
  align-items:center;
  gap:8px;
  flex:1;
  min-width:0;
  overflow:hidden;
}
.lv-sb-count {
  font-size:12.5px;
  font-weight:400;
  color:var(--muted);
  white-space:nowrap;
  margin-right:2px;
}
.lv-sb-divider {
  width:1px;
  height:18px;
  background:var(--separator);
  flex-shrink:0;
}
.lv-subbar-btn {
  display:inline-flex;
  align-items:center;
  gap:5px;
  height:28px;
  padding:0 10px;
  font-size:13px;
  font-weight:500;
  font-family:inherit;
  color:var(--foreground);
  background:none;
  border:none;
  border-radius:var(--radius-md);
  cursor:pointer;
  white-space:nowrap;
  transition:background .15s;
}
.lv-subbar-btn:hover {
  background:var(--surface-secondary);
}
.lv-density {
  display:flex;
  gap:2px;
  background:var(--surface-secondary);
  border-radius:var(--radius-md);
  padding:2px;
}
.lv-d-btn {
  display:flex;
  align-items:center;
  justify-content:center;
  width:24px;
  height:24px;
  background:none;
  border:none;
  border-radius:4px;
  cursor:pointer;
  color:var(--muted);
  transition:background .1s,color .1s;
}
.lv-d-btn.active {
  background:var(--segment);
  color:var(--foreground);
  box-shadow:0 1px 2px #0000000f;
}
.lv-bulk-wrap {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 22px;
  display: flex;
  justify-content: center;
  z-index: var(--z-popover);
  pointer-events: none;
}
.lv-bulk {
  pointer-events: auto;
  display:flex;
  align-items:center;
  gap:2px;
  padding:0 8px 0 14px;
  height:44px;
  background:var(--overlay);
  border-radius: var(--radius-xl);
  box-shadow: var(--overlay-shadow);
}
.lv-bulk-n {
  font-size:13px;
  font-weight:600;
  color:var(--overlay-foreground);
  white-space:nowrap;
  padding-right: 10px;
  margin-right: 4px;
  border-right: 1px solid var(--separator);
}
.lv-bulk-sep {
  width: 1px;
  height: 20px;
  background: var(--separator);
  margin: 0 4px;
}
.lv-bulk-btn {
  font-size:12.5px;
  font-weight:500;
  font-family:inherit;
  color:var(--muted);
  background:none;
  border:none;
  height: 30px;
  padding:0 10px;
  border-radius: var(--radius-md);
  cursor:pointer;
  display:inline-flex;
  align-items:center;
  transition: background-color .12s, color .12s;
}
.lv-bulk-btn:hover {
  background: var(--surface-hover);
  color: var(--overlay-foreground);
}
.lv-bulk-btn--danger {
  color: var(--danger);
}
.lv-bulk-btn--danger:hover {
  background: var(--danger-soft);
  color: var(--danger);
}
.lv-bulk-x {
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size:13px;
  color:var(--muted);
  background:none;
  border:none;
  border-radius: var(--radius-md);
  cursor:pointer;
  margin-left:4px;
  transition: background-color .12s, color .12s;
}
.lv-bulk-x:hover {
  background: var(--surface-hover);
  color: var(--overlay-foreground);
}
.lv-bulk-pop-enter-active {
  transition: opacity .16s ease-out, transform .16s ease-out;
}
.lv-bulk-pop-leave-active {
  transition: opacity .1s ease-in, transform .1s ease-in;
}
.lv-bulk-pop-enter-from, .lv-bulk-pop-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
.lv-th {
  position:sticky;
  top:0;
  z-index:5;
  padding:0 12px;
  height:36px;
  font-size:11px;
  font-weight:500;
  color:var(--muted);
  text-transform:uppercase;
  letter-spacing:.05em;
  background:var(--surface);
  border-bottom:1px solid var(--border);
  text-align:center;
  white-space:nowrap;
  -webkit-user-select:none;
  -moz-user-select:none;
  user-select:none;
}
.lv-th-cb {
  cursor:default;
  text-align:center;
  padding:0;
}
.lv-th-s {
  cursor:pointer;
  transition:color .1s;
}
.lv-th-s:hover {
  color:var(--foreground);
}
.lv-arr {
  font-size:9px;
  margin-left:3px;
  color:var(--muted);
}
.lv-th-inner {
  display:flex;
  align-items:center;
  justify-content:center;
  gap:4px;
  min-width:0;
  position:relative;
  color: var(--muted);
  font-weight: 500;
}
.lv-col-menu-btn {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  width:18px;
  height:18px;
  position:absolute;
  right:-6px;
  flex-shrink:0;
  border:none;
  background:none;
  border-radius:4px;
  color:var(--muted);
  cursor:pointer;
  opacity:0;
  transition:opacity .1s, background .1s, color .1s;
}
.lv-th:hover .lv-col-menu-btn,
.lv-gh:hover .lv-col-menu-btn,
.lv-col-menu-btn.is-open {
  opacity:1;
}
.lv-col-menu-btn.is-open {
  background:var(--surface-secondary);
  color:var(--foreground);
}
.lv-col-menu-btn:hover {
  background:var(--surface-secondary);
  color:var(--foreground);
}
thead .lv-sticky {
  z-index:6;
}
.lv-rh {
  position:absolute;
  right:-2px;
  top:0;
  width:5px;
  height:100%;
  cursor:col-resize;
  z-index:2;
}
.lv-rh:hover:after {
  content:"";
  position:absolute;
  left:1px;
  top:20%;
  width:2px;
  height:60%;
  background:var(--accent);
  border-radius:1px;
}
.lv-sticky {
  position:sticky;
  z-index:2;
  background:var(--surface);
}
.lv-sticky-cb {
  left:0;
}
.lv-sticky-title {
  left:36px;
}
.lv-group-td {
  padding:0px 0 10px 2px;
  background:transparent;
  border:none;
}
/* Breathing room above every group after the first (each group is a card). */
.lv-grp-title:not(:first-of-type) .lv-group-td {
  padding-top:22px;
}
/* Each group renders as its own HeroUI surface card. */
.lv-grp {
  border-radius:var(--radius-md);
  box-shadow:var(--surface-shadow-sm);
}
.lv-group-tr {
  cursor:pointer;
}
.lv-group-inner {
  display:flex;
  align-items:center;
  gap:8px;
}
.lv-chevron {
  /* --grp is already set on the wrapping <tbody> per group (its status/
     priority color) but was never actually consumed anywhere — the arrow
     rendered flat gray regardless of which group it belonged to. */
  color: var(--grp, var(--muted));
  transition:transform .15s;
  flex-shrink:0;
}
.lv-chevron.collapsed {
  transform:rotate(-90deg);
}
.lv-gdot {
  width:9px;
  height:9px;
  border-radius:50%;
  flex-shrink:0;
}
.lv-glabel {
  font-size:13.5px;
  font-weight:600;
  color:var(--foreground);
}
.lv-gcount {
  font-size:12px;
  color:var(--muted);
  margin-left:2px;
}
.lv-gh {
  height:32px;
  background:var(--surface-secondary);
  color:var(--muted);
  font-size:11px;
  font-weight:500;
  text-transform:uppercase;
  letter-spacing:.05em;
  text-align:center;
  padding:0 12px;
  position:relative;
  white-space:nowrap;
  border-top:var(--cellb);
  border-bottom:var(--cellb);
  border-right:var(--cellb);
}
.lv-gh-cb {
  padding:0;
  text-align:center;
}
.lv-grp .lv-ghead td:first-child {
  border-left:var(--cellb);
  border-top-left-radius:var(--radius-md);
}
.lv-grp .lv-ghead td:last-child {
  border-top-right-radius:var(--radius-md);
}
.lv-grp .lv-row td:first-child, .lv-grp .lv-add-row td:first-child {
  border-left:var(--cellb);
}
.lv-grp .lv-add-row td:first-child {
  border-bottom-left-radius:var(--radius-md);
}
.lv-grp .lv-add-row td:last-child {
  border-bottom-right-radius:var(--radius-md);
  border-right:var(--cellb);
}
.lv-row {
  cursor:pointer;
}
.lv-td {
  padding:0 12px;
  height:var(--rowh);
  font-size:13px;
  color:var(--foreground);
  vertical-align:middle;
  overflow:hidden;
  white-space:nowrap;
  max-width:0;
  background:var(--surface);
  border-bottom:var(--cellb);
  border-right:var(--cellb);
  transition:background .08s;
}
.lv-td-center {
  text-align:center;
}
.lv-cb-td {
  text-align:center;
  padding:0;
  cursor:default;
  max-width:none;
}
.lv-row:hover .lv-td {
  background:var(--surface-hover);
}
.lv-row.sel .lv-td {
  background:var(--accent-soft);
}
.lv-child-row:hover .lv-td {
  background:var(--surface-hover);
}
.lv-title-td {
  display:flex;
  align-items:center;
  gap:7px;
  max-width:none;
  overflow:hidden;
  padding-right:12px;
}
.lv-child-title-td {
  padding-left:8px;
}
.lv-cb {
  width:15px;
  height:15px;
  border-radius:4px;
  border:1.5px solid var(--field-border);
  display:inline-flex;
  align-items:center;
  justify-content:center;
  cursor:pointer;
  flex-shrink:0;
  transition:background .1s,border-color .1s,opacity .12s;
  background:var(--surface);
}
.lv-row .lv-cb {
  opacity:.35;
}
.lv-row:hover .lv-cb, .lv-row .lv-cb.checked, .lv-row .lv-cb.partial {
  opacity:1;
}
.lv-cb:hover {
  border-color:var(--accent);
}
.lv-cb.checked, .lv-cb.partial {
  background:var(--accent);
  border-color:var(--accent);
  color:var(--accent-foreground);
}
.lv-issue-key {
  font-family:var(--font-mono);
  font-size:11px;
  font-weight:500;
  color:var(--muted);
  white-space:nowrap;
  flex-shrink:0;
  transition:color .12s;
  letter-spacing:-.01em;
}
.lv-row:hover .lv-issue-key {
  color:var(--accent);
}
.lv-child-key {
  color:var(--muted);
}
.lv-title {
  font-size:13px;
  font-weight:500;
  color:var(--foreground);
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  flex:1;
  min-width:0;
}
.lv-title-child {
  color:var(--foreground);
}
.lv-child-count {
  font-size:11px;
  font-weight:600;
  color:var(--muted);
  background:var(--surface-secondary);
  border-radius:4px;
  padding:1px 6px;
  flex-shrink:0;
}
.lv-expand-btn {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  width:18px;
  height:18px;
  border:none;
  background:none;
  border-radius:4px;
  cursor:pointer;
  color:var(--muted);
  flex-shrink:0;
  transition:background .1s,color .1s;
}
.lv-expand-btn:hover {
  background:var(--surface-secondary);
  color:var(--foreground);
}
.lv-expand-spacer {
  width:18px;
  flex-shrink:0;
}
.lv-row-menu {
  display:none;
  align-items:center;
  justify-content:center;
  width:24px;
  height:24px;
  border:none;
  background:none;
  border-radius:4px;
  cursor:pointer;
  color:var(--muted);
  flex-shrink:0;
  transition:background .1s;
  margin-left:auto;
}
.lv-row-menu:hover {
  background:var(--surface-secondary);
  color:var(--foreground);
}
.lv-row:hover .lv-row-menu {
  display:inline-flex;
}
.lv-child-indent {
  width:32px;
  flex-shrink:0;
  position:relative;
  align-self:stretch;
  overflow:hidden;
}
.lv-child-indent:before {
  content:"";
  position:absolute;
  left:14px;
  top:-1px;
  bottom:50%;
  width:1.5px;
  background:var(--separator);
}
.lv-child-indent:after {
  content:"";
  position:absolute;
  left:14px;
  top:50%;
  width:14px;
  height:1.5px;
  background:var(--separator);
}
.lv-td-fill {
  padding:0!important;
  position:relative;
}
.lv-td-fill :deep(.relative) {
  display:block!important;
  width:100%;
  height:100%;
}
.lv-td-fill :deep(.relative>div:first-child) {
  display:block!important;
  width:100%;
  height:100%;
}
/* Status — full-bleed color fill across the whole cell,
   text color picked for contrast per-status (see _readableOn). */
.lv-status-pill {
  display:flex;
  align-items:center;
  justify-content: center;
  width:100%;
  height:100%;
  padding:0 12px;
  border:none;
  border-radius:0;
  background: var(--sc,var(--muted));
  font-size:12.5px;
  font-weight:600;
  font-family:inherit;
  color: var(--st,#fff);
  cursor:pointer;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  transition: filter .1s;
}
.lv-status-pill:hover {
  filter: brightness(0.93);
}
/* Priority — icon only (signal bars already encode the level; the text
   label was redundant next to it). Title attr carries the label instead. */
.lv-prio-pill {
  display:flex;
  align-items:center;
  justify-content:center;
  width:100%;
  height:100%;
  padding:0 12px;
  border:none;
  background:none;
  cursor:pointer;
}
.lv-prio-pill:hover {
  background: var(--surface-hover);
}
.lv-field-btn {
  display:inline-flex;
  align-items:center;
  gap:6px;
  height:26px;
  padding:0 6px;
  font-size:13px;
  font-family:inherit;
  color:var(--foreground);
  background:none;
  border:none;
  border-radius:var(--radius-md);
  cursor:pointer;
  white-space:nowrap;
  transition:background .1s;
  max-width:100%;
}
.lv-field-btn:hover {
  background:var(--surface-secondary);
}

/* ── Full-cell editing  ──────────────────────────────────────
   The whole cell is the click/edit target: the field control fills the cell,
   left-aligned with a consistent inset, and the cell shows a subtle ring on
   hover so it reads as editable. */
.lv-td-edit {
  padding:0;
}
.lv-td-edit :deep(.relative),
.lv-td-edit :deep(.relative) > div:first-child {
  width:100%;
  height:100%;
}
.lv-td-edit .lv-field-btn {
  width:100%;
  height:100%;
  justify-content:flex-start;
  padding:0 12px;
  border-radius:0;
}
.lv-td-edit .lv-field-btn:hover {
  background:transparent;
}
.lv-td-edit .lv-pts-input,
.lv-td-edit .lv-cf-input {
  width:100%;
  height:100%;
  padding:0 12px;
  border-radius:0;
  background:transparent;
}
.lv-td-edit .lv-date-td {
  width:100%;
  height:100%;
}
.lv-td-edit .lv-date-td :deep(button) {
  width:100%;
  height:100%;
  justify-content:flex-start;
  padding:0 12px;
}
/* editable affordance — subtle inset ring on hover, accent ring while focused
   (skip the solid-colour status/priority pills) */
.lv-row:hover .lv-td-edit:not(.lv-td-fill):hover {
  box-shadow:inset 0 0 0 1.5px var(--field-border);
}
.lv-td-edit:not(.lv-td-fill):focus-within {
  box-shadow:inset 0 0 0 1.5px var(--accent);
}
/* keep the cell full-bleed, but pad the field CONTENT (incl. plain display cells) */
.lv-td-edit:not(.lv-td-fill) .lv-field-plain,
.lv-td-edit:not(.lv-td-fill) .lv-label-row,
.lv-td-edit:not(.lv-td-fill) > .lv-unset {
  padding-left:12px;
  padding-right:12px;
}
/* chips carry a background — offset with margin so the pill keeps its own size */
.lv-td-edit:not(.lv-td-fill) > .lv-sprint-chip,
.lv-td-edit:not(.lv-td-fill) > .lv-epic-chip {
  margin-left:12px;
}
.lv-field-plain {
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding:0 8px;
  font-size:13px;
  color:var(--foreground);
}
.lv-dot {
  width:8px;
  height:8px;
  border-radius:50%;
  flex-shrink:0;
}
.lv-type-badge {
  width:18px;
  height:18px;
  border-radius:4px;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  color:var(--accent-foreground);
  font-size:10px;
  font-weight:700;
  flex-shrink:0;
}
.lv-av {
  width:24px;
  height:24px;
  border-radius:50%;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  color:var(--accent-foreground);
  font-size:9px;
  font-weight:700;
  flex-shrink:0;
  border:2px solid var(--surface);
}
.lv-av-empty {
  width:24px;
  height:24px;
  border-radius:50%;
  border:2px dashed var(--border-secondary);
  flex-shrink:0;
  display:inline-block;
}
.lv-unset {
  color:var(--muted);
  font-size:13px;
}
.lv-date-td {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  max-width:100%;
}
.lv-date-td :deep(button) {
  height:26px;
  padding:0 8px;
  font-size:13px;
  background:transparent!important;
  border:none!important;
  box-shadow:none!important;
  border-radius:var(--radius-md);
  color:var(--foreground);
  cursor:pointer;
  transition:background .1s;
}
.lv-date-td :deep(button:hover) {
  background:var(--surface-secondary);
}
.lv-date-td :deep(button>div:last-child) {
  opacity:0;
  transition:opacity .1s;
}
.lv-date-td :deep(button:hover>div:last-child) {
  opacity:1;
}
.lv-date-td.overdue :deep(button) {
  color:var(--danger-soft-foreground);
  font-weight:500;
}
.lv-date-td.today :deep(button) {
  color:var(--warning-soft-foreground);
  font-weight:500;
}
.lv-sprint-chip {
  display:inline-flex;
  align-items:center;
  height:20px;
  padding:0 8px;
  background:var(--accent-soft);
  color:var(--accent-soft-foreground);
  border-radius:2px;
  font-size:12px;
  font-weight:500;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  max-width:130px;
}
.lv-epic-chip {
  display:inline-flex;
  align-items:center;
  height:20px;
  padding:0 8px;
  background:var(--surface-secondary);
  color:var(--foreground);
  border-radius:2px;
  font-size:12px;
  font-weight:500;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  max-width:130px;
}
.lv-label-row {
  display:flex;
  align-items:center;
  gap:4px;
  overflow:hidden;
}
.lv-lbl-chip {
  display:inline-flex;
  align-items:center;
  height:20px;
  padding:0 7px;
  border-radius:2px;
  font-size:11.5px;
  font-weight:500;
  border:1px solid transparent;
  white-space:nowrap;
}
.lv-lbl-more {
  font-size:11px;
  color:var(--muted);
}
.lv-pts-input {
  width:52px;
  text-align:right;
  padding:0 6px;
  height:26px;
  font-size:13px;
  font-family:inherit;
  color:var(--foreground);
  background:transparent;
  border:1px solid transparent;
  border-radius:var(--radius-md);
  outline:none;
  -moz-appearance:textfield;
}
.lv-pts-input::-webkit-inner-spin-button, .lv-pts-input::-webkit-outer-spin-button {
  -webkit-appearance:none;
}
.lv-pts-input:hover {
  border-color:var(--border);
}
.lv-pts-input:focus {
  border-color:var(--accent);
  background:var(--surface);
}
.lv-pts-input::-moz-placeholder {
  color:var(--muted);
}
.lv-pts-input::placeholder {
  color:var(--muted);
}
.lv-gsum {
  display:inline-flex;
  align-items:center;
  height:18px;
  padding:0 7px;
  margin-left:6px;
  font-size:10.5px;
  font-weight:600;
  color:var(--muted);
  background:var(--surface);
  border:var(--cellb);
  border-radius:2px;
  text-transform:none;
  letter-spacing:0;
}
.lv-gsum.danger {
  color:var(--danger);
  border-color:var(--danger);
  background:var(--danger-soft);
}
.lv-add-row td {
  border-bottom:var(--cellb);
  border-right:var(--cellb);
  background:var(--surface);
}
.lv-add-row td:last-child {
  border-bottom-right-radius:var(--radius-md);
}
.lv-add-td {
  padding:0 8px;
  height:36px;
}
.lv-add-btn {
  width:100%;
  text-align:left;
  font-size:13px;
  color:var(--muted);
  background:none;
  border:none;
  height:32px;
  padding:0 6px;
  cursor:pointer;
  font-family:inherit;
  border-radius:var(--radius-md);
  transition:background .1s,color .1s;
}
.lv-add-btn:hover {
  background:var(--surface-secondary);
  color:var(--foreground);
}
.lv-add-input {
  width:100%;
  height:30px;
  font-size:13px;
  font-family:inherit;
  color:var(--foreground);
  background:var(--surface);
  border:1px solid var(--accent);
  border-radius:var(--radius-md);
  outline:none;
  padding:0 8px;
}
.lv-sum-row td {
  height:26px;
  border:none;
  background:var(--surface);
  vertical-align:middle;
}
.lv-sum-td {
  padding:6px 12px 0;
}
.lv-sumbar {
  display:flex;
  height:6px;
  border-radius:999px;
  overflow:hidden;
  width:100%;
  background:var(--surface-secondary);
}
.lv-sumbar span {
  height:100%;
}
.lv-sum-pts {
  display:block;
  text-align:center;
  font-size:11.5px;
  font-weight:600;
  color:var(--muted);
  padding-top:2px;
}
.lv-qc {
  padding:8px 20px;
  font-size:13px;
  color:var(--muted);
  cursor:pointer;
  display:flex;
  align-items:center;
  gap:8px;
  white-space:nowrap;
  transition:background .1s,color .1s;
  border-bottom:1px solid var(--separator);
}
.lv-qc:hover {
  background:var(--surface-secondary);
  color:var(--foreground);
}
.lv-empty {
  padding:56px 0;
  text-align:center;
  font-size:14px;
  color:var(--muted);
  background:var(--surface);
}
.lv-dd-hdr {
  padding:6px 14px 2px;
  font-size:11px;
  font-weight:600;
  color:var(--muted);
  text-transform:uppercase;
  letter-spacing:.05em;
  margin:0;
}
.lv-col-row {
  display:flex;
  align-items:center;
  gap:10px;
  padding:6px 14px;
  cursor:pointer;
  font-size:13px;
  color:var(--foreground);
  transition:background .1s;
}
.lv-col-row:hover {
  background:var(--surface-secondary);
}
.lv-col-cb {
  width:14px;
  height:14px;
  border-radius:4px;
  border:1.5px solid var(--field-border);
  display:flex;
  align-items:center;
  justify-content:center;
  flex-shrink:0;
  transition:all .15s;
}
.lv-col-cb.on {
  background:var(--accent);
  border-color:var(--accent);
  color:var(--accent-foreground);
}
.lv-ddsearch {
  padding:8px 12px;
  border-bottom:1px solid var(--separator);
}
.lv-ddinput {
  width:100%;
  font-size:13px;
  font-family:inherit;
  color:var(--foreground);
  background:none;
  border:none;
  outline:none;
}
.lv-ddinput::-moz-placeholder {
  color:var(--muted);
}
.lv-ddinput::placeholder {
  color:var(--muted);
}
.lv-ddsep {
  height:1px;
  background:var(--separator);
  margin:3px 0;
}
.lv-dd-empty {
  padding:8px 12px;
  font-size:12px;
  color:var(--muted);
}
.lv-td :deep(.relative) {
  display:inline-flex;
  max-width:100%;
  vertical-align:middle;
}
.lv-td :deep(.relative>div:first-child) {
  display:inline-flex;
  max-width:100%;
}
.lv-tl-pill {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  height:24px;
  min-width:110px;
  max-width:100%;
  padding:0 12px;
  font-size:11.5px;
  font-weight:600;
  font-family:inherit;
  letter-spacing:.01em;
  border:none;
  border-radius:999px;
  cursor:pointer;
  white-space:nowrap;
  background:var(--accent);
  color:var(--accent-foreground);
  transition:filter .1s,transform .25s var(--ease-smooth);
}
.lv-tl-pill:hover {
  filter:brightness(1.08);
}
.lv-tl-pill:active {
  transform:scale(.97);
}
.lv-tl-pill.empty {
  background:transparent;
  color:var(--muted);
  border:1.5px dashed var(--border-secondary);
  font-weight:500;
}
.lv-tl-pill.empty:hover {
  color:var(--foreground);
  border-color:var(--muted);
  filter:none;
}
.lv-tl-pop {
  padding:8px;
  display:flex;
  flex-direction:column;
  gap:8px;
  min-width:230px;
}
.lv-tl-row {
  display:flex;
  align-items:center;
  gap:10px;
}
.lv-tl-lbl {
  font-size:12px;
  font-weight:500;
  color:var(--muted);
  width:36px;
  flex-shrink:0;
}
.lv-gh-sticky {
  position:sticky;
  z-index:4;
  background: var(--surface-secondary);
}
.lv-gh-cb.lv-gh-sticky {
  left:0;
}
.lv-gh-title.lv-gh-sticky {
  left:35px;
}
.lv-group-inner {
  position:sticky;
  left:2px;
  width:-moz-max-content;
  width:max-content;
  max-width:60vw;
}
.lv-td-ghost {
  background:var(--surface);
  max-width:none;
}
.lv-col-dragging {
  background:var(--accent-soft)!important;
}
.lv-drop-left {
  box-shadow:inset 3px 0 0 var(--accent)!important;
}
.lv-drop-right {
  box-shadow:inset -3px 0 0 var(--accent)!important;
}
.lv-plus-ic {
  color:var(--muted);
  flex-shrink:0;
}
.lv-plus-ic--erp {
  color:var(--accent);
}
/* "+" add-column menu */
.lv-addcol-item {
  display:flex;
  align-items:center;
  gap:10px;
  width:100%;
  padding:8px 10px;
  border:none;
  background:none;
  border-radius:var(--radius-md);
  cursor:pointer;
  text-align:left;
  font-family:inherit;
  transition:background .1s;
}
.lv-addcol-item:hover {
  background:var(--accent-soft);
}
.lv-addcol-txt {
  display:flex;
  flex-direction:column;
  min-width:0;
}
.lv-addcol-title {
  font-size:13px;
  font-weight:500;
  color:var(--foreground);
}
.lv-addcol-sub {
  font-size:11.5px;
  color:var(--muted);
}
.lv-erp-opt {
  display:flex;
  align-items:center;
  gap:10px;
  text-align:left;
  padding:10px 12px;
  border:1px solid var(--field-border);
  border-radius:var(--radius-md);
  background:var(--surface);
  cursor:pointer;
  transition:border-color .12s,background .12s;
  font-family:inherit;
  min-width:0;
}
.lv-erp-opt:hover {
  border-color:var(--accent);
  background:var(--accent-soft);
}
.lv-erp-ic {
  display:grid;
  place-items:center;
  width:32px;
  height:32px;
  border-radius:var(--radius-md);
  background:var(--accent-soft);
  color:var(--accent);
  flex-shrink:0;
}
.lv-cf-input {
  width:100%;
  padding:0 6px;
  height:26px;
  font-size:13px;
  font-family:inherit;
  color:var(--foreground);
  background:transparent;
  border:1px solid transparent;
  border-radius:var(--radius-md);
  outline:none;
}
.lv-cf-input:hover {
  border-color:var(--border);
}
.lv-cf-input:focus {
  border-color:var(--accent);
  background:var(--surface);
}
.lv-cf-input::-moz-placeholder {
  color:var(--muted);
}
.lv-cf-input::placeholder {
  color:var(--muted);
}
.lv-cf-tag {
  display:inline-flex;
  align-items:center;
  height:20px;
  padding:0 7px;
  border-radius:2px;
  background:var(--surface-secondary);
  color:var(--foreground);
  font-size:11.5px;
  font-weight:500;
  white-space:nowrap;
}
.lv-mirror-val {
  font-size:12.5px;
  color:var(--foreground);
  margin-right:6px;
  white-space:nowrap;
}
.lv-mirror-link { cursor:pointer; }
.lv-mirror-link:hover {
  color:var(--accent);
  text-decoration:underline;
  text-underline-offset:2px;
}
.lv-mirror-status {
  display:inline-flex;
  align-items:center;
  height:20px;
  padding:0 8px;
  border-radius:2px;
  background:var(--surface-secondary);
  font-size:11.5px;
  font-weight:600;
}
.lv-link-chip {
  display:inline-flex;
  align-items:center;
  gap:5px;
  height:22px;
  padding:0 8px;
  margin-right:4px;
  font-size:11.5px;
  font-weight:500;
  font-family:var(--font-mono);
  color:var(--foreground);
  background:var(--surface-secondary);
  border:none;
  border-radius:var(--radius-md);
  cursor:pointer;
  white-space:nowrap;
  transition:background .1s;
}
.lv-link-chip:hover {
  background:var(--default);
}
.lv-ref-chip {
  font-family:inherit;
  font-weight:600;
  color:var(--accent-soft-foreground);
  background:var(--accent-soft);
}
.lv-ref-chip:hover {
  background:var(--accent-soft-hover);
}
.lv-gh[draggable=true], .lv-th[draggable=true] {
  cursor:grab;
}
.lv-gh[draggable=true]:active, .lv-th[draggable=true]:active {
  cursor:grabbing;
}
.lv-th-plus, .lv-gh-plus {
  padding:0;
  text-align:center;
  vertical-align:middle;
}
.lv-plus-btn {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  width:26px;
  height:26px;
  border:none;
  background:none;
  border-radius:var(--radius-md);
  cursor:pointer;
  color:var(--muted);
  transition:background .1s,color .1s;
}
.lv-plus-btn:hover {
  background:var(--surface-secondary);
  color:var(--foreground);
}
.lv-plus-none {
  padding:6px 12px;
  font-size:12px;
  color:var(--muted);
  line-height:1.5;
  margin:0;
}
.lv-ctx-backdrop {
  position:fixed;
  inset:0;
  z-index:499;
}
.lv-col-ctx {
  position:fixed;
  z-index:1999;
  width:184px;
  background:var(--overlay);
  border-radius:var(--radius-lg);
  box-shadow:var(--overlay-shadow);
  padding:5px;
}
.lv-ctx-item {
  display:flex;
  align-items:center;
  gap:8px;
  width:100%;
  padding:6px 10px;
  font-size:13px;
  font-family:inherit;
  color:var(--foreground);
  background:none;
  border:none;
  border-radius:5px;
  cursor:pointer;
  text-align:left;
  transition:background .1s;
}
.lv-ctx-item:hover {
  background:var(--surface-secondary);
}
.lv-ctx-item:disabled {
  opacity:.4;
  pointer-events:none;
}
.lv-ctx-sep {
  border-bottom:1px solid var(--separator);
  border-radius:5px 5px 0 0;
  margin-bottom:4px;
  padding-bottom:8px;
}
.lv-ctx-danger {
  color:var(--danger);
}
.lv-ctx-danger:hover {
  background:var(--danger-soft);
}
</style>
