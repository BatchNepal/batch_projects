<template>
  <div class="bl-root">

    <!-- Loading: sprint-section skeletons mirror the real layout -->
    <div v-if="loading" class="space-y-5 p-1">
      <div v-for="s in 2" :key="'sk' + s" class="rounded-lg border bg-overlay">
        <div class="flex items-center gap-3 px-4 py-3 border-b ">
          <Skeleton class="h-4 w-14 rounded-full" />
          <Skeleton class="h-3" :style="{ width: (90 + s * 30) + 'px' }" />
          <Skeleton class="h-2.5 w-24 ml-auto" />
        </div>
        <div class="px-4 py-2 space-y-2.5">
          <div v-for="r in (s === 1 ? 4 : 3)" :key="r" class="flex items-center gap-3 h-7">
            <Skeleton class="h-3.5 w-3.5 rounded-sm" />
            <Skeleton class="h-2.5 w-12" />
            <Skeleton class="h-2.5" :style="{ width: (30 + ((s + r) % 4) * 12) + '%' }" />
            <Skeleton class="h-5 w-5 rounded-full ml-auto" />
          </div>
        </div>
      </div>
    </div>

    <template v-else>

      <div class="flex justify-end items-center gap-2 px-1 pb-2">
        <router-link :to="`/workspace/${route.params.key}/sprints-overview`" class="bl-btn bl-btn--ghost">
          <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
          Sprints overview
        </router-link>
        <FieldDropdown width="w-56" align="right" :close-on-select="false">
          <template #trigger>
            <button class="bl-btn bl-btn--ghost">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h7"/></svg>
              Columns
            </button>
          </template>
          <p class="bl-col-menu-label">Sprint header</p>
          <DropdownItem v-for="c in SPRINT_HEADER_CATALOG" :key="c.key" @click="toggleSprintColumn(c.key)">
            <span class="bl-col-check" :class="{ 'bl-col-check--on': sprintColumns[c.key] }">
              <svg v-if="sprintColumns[c.key]" width="9" height="9" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
            </span>
            {{ c.label }}
          </DropdownItem>
          <p class="bl-col-menu-label">Task columns</p>
          <DropdownItem v-for="c in SPRINT_TASK_COLUMN_CATALOG" :key="c.key" @click="toggleSprintColumn(c.key)">
            <span class="bl-col-check" :class="{ 'bl-col-check--on': sprintColumns[c.key] }">
              <svg v-if="sprintColumns[c.key]" width="9" height="9" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
            </span>
            {{ c.label }}
          </DropdownItem>
        </FieldDropdown>
        <ErpMirrorFieldsButton
          :schema="mirror.mirrorSchema.value" :cols="mirror.mirrorCols.value"
          @add="mirror.addMirrorField" @remove="mirror.removeMirrorField"
        />
      </div>

      <!-- ── ACTIVE SPRINT ── -->
      <div v-if="activeSprint" class="bl-section bl-section--active">
        <div class="bl-section-head" @click="toggleCollapse('__active__')">
          <button class="bl-chevron" :class="{ 'bl-chevron--open': !collapsed['__active__'] }">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
          </button>
          <span class="bl-sprint-badge bl-badge-active">Active</span>
          <span class="bl-sprint-name-static">{{ activeSprint.sprint_name }}</span>
          <div v-if="activeSprint.start_date || activeSprint.end_date" class="bl-sprint-dates-static">
            <svg width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
            {{ formatDate(activeSprint.start_date) }} → {{ formatDate(activeSprint.end_date) }}
          </div>
          <div class="bl-progress">
            <div class="bl-progress-bar">
              <div class="bl-progress-fill" :style="{ width: progressPct(activeSprint) + '%' }" :class="{ 'bl-fill-done': progressPct(activeSprint) === 100 }" />
            </div>
            <span class="bl-progress-label">{{ sprintLabel(activeSprint) }}</span>
          </div>
          <span v-if="sprintColumns.connected" class="bl-col-badge" title="Connected tasks">{{ activeSprint.issue_count || 0 }} tasks</span>
          <span v-if="sprintColumns.effort" class="bl-col-badge" title="Total estimated effort">Σ {{ activeSprint.total_points || 0 }} pts</span>
          <div class="bl-sprint-actions" @click.stop>
            <button class="bl-btn bl-btn--sprint-detail" @click="openStandup(activeSprint)">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 12h8m-8 4h5M7 4h10a2 2 0 012 2v13l-3-2H7a2 2 0 01-2-2V6a2 2 0 012-2z"/></svg>
              Daily standup
            </button>
            <button class="bl-btn bl-btn--sprint-detail" @click="openCapacity(activeSprint)">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v6H5a2 2 0 01-2-2v-4a2 2 0 012-2h4zm0-6v6m6-12v18m0-18h4a2 2 0 012 2v14a2 2 0 01-2 2h-4m0-18v18"/></svg>
              Capacity
            </button>
            <router-link :to="`/workspace/${route.params.key}/sprint/${activeSprint.name}`" class="bl-btn bl-btn--sprint-detail">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
              Sprint detail
            </router-link>
            <router-link :to="`/workspace/${route.params.key}/board`" class="bl-btn bl-btn--board-link">
              View on Board
              <svg width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
            </router-link>
            <button class="bl-btn bl-btn--complete" @click="openCompleteModal(activeSprint)">Complete sprint</button>
          </div>
        </div>

        <div v-if="activeSprint.goal && !collapsed['__active__']" class="bl-sprint-goal">
          <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          {{ activeSprint.goal }}
        </div>

        <div
          v-if="!collapsed['__active__']"
          class="bl-drop-zone"
          @dragover.prevent="onDragOverSection($event, activeSprint.name)"
          @drop.prevent="onDrop($event, activeSprint.name)"
          @dragleave="onDragLeave"
          :class="{ 'bl-drop-zone--over': dragTarget === activeSprint.name }"
        >
          <template v-if="issuesBySprint[activeSprint.name] && issuesBySprint[activeSprint.name].length">
            <BacklogColumnBar :columns="sprintColumns" mode="header" />
            <BacklogTaskRow
              v-for="issue in issuesBySprint[activeSprint.name]" :key="issue.name"
              :issue="issue" :columns="sprintColumns" :mirror-chips="mirror.mirrorChips" :open-erp-doc="openErpDoc"
              @dragstart="onDragStart" @contextmenu="onContextMenu"
            />
            <BacklogColumnBar :columns="sprintColumns" :issues="issuesBySprint[activeSprint.name]" mode="footer" />
          </template>
          <div v-else class="bl-drop-hint">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3"/></svg>
            Drag tasks here to add to the active sprint
          </div>
        </div>
      </div>

      <!-- ── PLANNING SPRINTS ── -->
      <div
        v-for="sprint in planningSprints"
        :key="sprint.name"
        class="bl-section"
        @dragover.prevent="onDragOverSection($event, sprint.name)"
        @drop.prevent="onDrop($event, sprint.name)"
        @dragleave="onDragLeave"
        :class="{ 'bl-section--dragover': dragTarget === sprint.name }"
      >
        <div class="bl-section-head" @click="toggleCollapse(sprint.name)">
          <button class="bl-chevron" :class="{ 'bl-chevron--open': !collapsed[sprint.name] }">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
          </button>
          <span class="bl-sprint-badge bl-badge-planning">Planning</span>
          <input
            class="bl-sprint-name"
            :value="sprint.sprint_name"
            @click.stop
            @blur="(e) => saveSprint(sprint, { sprint_name: (e.target).value })"
            @keydown.enter.stop="(e) => (e.target).blur()"
          />
          <div class="bl-sprint-dates" @click.stop>
            <DatePicker :modelValue="sprint.start_date || null" placeholder="Start" @update:modelValue="(v) => saveSprint(sprint, { start_date: v || '' })" />
            <span class="bl-date-sep">→</span>
            <DatePicker :modelValue="sprint.end_date || null" placeholder="End" @update:modelValue="(v) => saveSprint(sprint, { end_date: v || '' })" />
          </div>
          <div class="bl-progress">
            <div class="bl-progress-bar"><div class="bl-progress-fill" :style="{ width: progressPct(sprint) + '%' }" :class="{ 'bl-fill-done': progressPct(sprint) === 100 }" /></div>
            <span class="bl-progress-label">{{ sprintLabel(sprint) }}</span>
          </div>
          <span v-if="sprintColumns.connected" class="bl-col-badge" title="Connected tasks">{{ sprint.issue_count || 0 }} tasks</span>
          <span v-if="sprintColumns.effort" class="bl-col-badge" title="Total estimated effort">Σ {{ sprint.total_points || 0 }} pts</span>
          <div class="bl-sprint-actions" @click.stop>
            <button class="bl-btn bl-btn--sprint-detail" title="Capacity" @click="openCapacity(sprint)">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v6H5a2 2 0 01-2-2v-4a2 2 0 012-2h4zm0-6v6m6-12v18m0-18h4a2 2 0 012 2v14a2 2 0 01-2 2h-4m0-18v18"/></svg>
            </button>
            <router-link :to="`/workspace/${route.params.key}/sprint/${sprint.name}`" class="bl-btn bl-btn--sprint-detail" title="Sprint detail">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
            </router-link>
            <button class="bl-btn bl-btn--start" :disabled="!!activeSprint" :title="activeSprint ? `Complete '${activeSprint.sprint_name}' first` : ''" @click="handleStartSprint(sprint)">Start sprint</button>
            <FieldDropdown align="right" width="w-44">
              <template #trigger>
                <button class="bl-kebab"><svg width="14" height="14" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="4" r="1.5"/><circle cx="10" cy="10" r="1.5"/><circle cx="10" cy="16" r="1.5"/></svg></button>
              </template>
              <DropdownItem @click="openGoalEdit(sprint)">
                <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
                Edit goal
              </DropdownItem>
              <DropdownItem @click="handleDeleteSprint(sprint)">
                <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" style="color:var(--danger)"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                <span style="color:var(--danger)">Delete sprint</span>
              </DropdownItem>
            </FieldDropdown>
          </div>
        </div>

        <div v-if="sprint.goal && !collapsed[sprint.name]" class="bl-sprint-goal">
          <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          {{ sprint.goal }}
        </div>

        <div v-if="!collapsed[sprint.name]">
          <div v-if="issuesBySprint[sprint.name] && issuesBySprint[sprint.name].length">
            <BacklogColumnBar :columns="sprintColumns" mode="header" />
            <BacklogTaskRow
              v-for="issue in issuesBySprint[sprint.name]" :key="issue.name"
              :issue="issue" :columns="sprintColumns" :mirror-chips="mirror.mirrorChips" :open-erp-doc="openErpDoc"
              @dragstart="onDragStart" @contextmenu="onContextMenu"
            />
            <BacklogColumnBar :columns="sprintColumns" :issues="issuesBySprint[sprint.name]" mode="footer" />
          </div>
          <div v-else class="bl-empty-sprint">
            No tasks — drag tasks here or <button class="bl-inline-link" @click="openCreateInSprint(sprint)">create one</button>
          </div>
          <button class="bl-add-row" @click="openCreateInSprint(sprint)">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
            Add task
          </button>
        </div>
      </div>

      <!-- ── BACKLOG ── -->
      <div
        class="bl-section"
        @dragover.prevent="onDragOverSection($event, '__backlog__')"
        @drop.prevent="onDrop($event, '__backlog__')"
        @dragleave="onDragLeave"
        :class="{ 'bl-section--dragover': dragTarget === '__backlog__' }"
      >
        <div class="bl-section-head" @click="toggleCollapse('__backlog__')">
          <button class="bl-chevron" :class="{ 'bl-chevron--open': !collapsed['__backlog__'] }">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
          </button>
          <span class="bl-section-title">Backlog</span>
          <span class="bl-count">{{ noSprintIssues.length }}</span>
          <div class="bl-sprint-actions" @click.stop>
            <button class="bl-btn bl-btn--ghost" @click="openCreateInBacklog">+ Add task</button>
          </div>
        </div>
        <div v-if="!collapsed['__backlog__']">
          <div v-if="noSprintIssues.length">
            <BacklogColumnBar :columns="sprintColumns" mode="header" />
            <BacklogTaskRow
              v-for="issue in noSprintIssues" :key="issue.name"
              :issue="issue" :columns="sprintColumns" :mirror-chips="mirror.mirrorChips" :open-erp-doc="openErpDoc"
              @dragstart="onDragStart" @contextmenu="onContextMenu"
            />
            <BacklogColumnBar :columns="sprintColumns" :issues="noSprintIssues" mode="footer" />
          </div>
          <div v-else class="bl-empty-sprint">
            Backlog is empty. <button class="bl-inline-link" @click="openCreateInBacklog">Create a task</button>
          </div>
          <button class="bl-add-row" @click="openCreateInBacklog">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
            Add task
          </button>
        </div>
      </div>

      <!-- ── COMPLETED SPRINTS TOGGLE ── -->
      <div v-if="completedSprints.length" class="bl-completed-toggle">
        <button class="bl-toggle-completed" @click="showCompleted = !showCompleted">
          <svg width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5" :style="{ transform: showCompleted ? 'rotate(90deg)' : 'none', transition: 'transform .15s' }">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
          </svg>
          {{ showCompleted ? 'Hide' : 'Show' }} {{ completedSprints.length }} completed sprint{{ completedSprints.length !== 1 ? 's' : '' }}
        </button>
      </div>

      <!-- ── COMPLETED SPRINTS ── -->
      <template v-if="showCompleted">
        <div
          v-for="sprint in completedSprints"
          :key="sprint.name"
          class="bl-section bl-section--completed"
          @dragover.prevent="onDragOverSection($event, sprint.name)"
          @drop.prevent="onDrop($event, sprint.name)"
          @dragleave="onDragLeave"
          :class="{ 'bl-section--dragover': dragTarget === sprint.name }"
        >
          <div class="bl-section-head" @click="toggleCollapse(sprint.name)">
            <button class="bl-chevron" :class="{ 'bl-chevron--open': !collapsed[sprint.name] }">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
            </button>
            <span class="bl-sprint-badge bl-badge-completed">Completed</span>
            <span class="bl-sprint-name-static">{{ sprint.sprint_name }}</span>
            <div v-if="sprint.start_date || sprint.end_date" class="bl-sprint-dates-static">
              <svg width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
              {{ formatDate(sprint.start_date) }} → {{ formatDate(sprint.end_date) }}
            </div>
            <div class="bl-progress">
              <div class="bl-progress-bar"><div class="bl-progress-fill" :style="{ width: progressPct(sprint) + '%' }" :class="{ 'bl-fill-done': progressPct(sprint) === 100 }" /></div>
              <span class="bl-progress-label">{{ sprintLabel(sprint) }}</span>
            </div>
          </div>
          <div v-if="!collapsed[sprint.name]">
            <div v-if="issuesBySprint[sprint.name] && issuesBySprint[sprint.name].length">
              <BacklogColumnBar :columns="sprintColumns" mode="header" />
              <BacklogTaskRow
                v-for="issue in issuesBySprint[sprint.name]" :key="issue.name"
                :issue="issue" muted :columns="sprintColumns" :mirror-chips="mirror.mirrorChips" :open-erp-doc="openErpDoc"
                @dragstart="onDragStart" @contextmenu="onContextMenu"
              />
              <BacklogColumnBar :columns="sprintColumns" :issues="issuesBySprint[sprint.name]" mode="footer" />
            </div>
            <div v-else class="bl-empty-sprint">No tasks recorded for this sprint.</div>
          </div>
        </div>
      </template>

      <!-- ── CREATE SPRINT ── -->
      <div class="bl-create-sprint">
        <button v-if="!showCreateForm" class="bl-btn bl-btn--ghost" @click="showCreateForm = true">
          <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
          Create sprint
        </button>
        <div v-else class="bl-create-form">
          <input v-model="newSprintName" class="bl-create-input" placeholder="Sprint name…" autofocus @keydown.enter="submitCreateSprint" @keydown.esc="showCreateForm = false" />
          <div class="bl-create-dates">
            <DatePicker v-model="newSprintStart" placeholder="Start date" />
            <span class="bl-date-sep">→</span>
            <DatePicker v-model="newSprintEnd" placeholder="End date" />
          </div>
          <div class="bl-create-actions">
            <button class="bl-btn bl-btn--primary" :disabled="!newSprintName.trim() || creating" @click="submitCreateSprint">
              <div v-if="creating" class="bl-spinner bl-spinner--sm" />
              Create
            </button>
            <button class="bl-btn bl-btn--ghost" @click="showCreateForm = false">Cancel</button>
          </div>
        </div>
      </div>

    </template>

    <!-- ── COMPLETE SPRINT MODAL ── -->
    <Transition name="bl-modal">
      <div v-if="completeModal.open" class="bl-modal-backdrop" @click.self="completeModal.open = false">
        <div class="bl-modal">
          <div class="bl-modal-head">
            <h2 class="bl-modal-title">Complete sprint</h2>
            <button class="bl-kebab" @click="completeModal.open = false"><svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg></button>
          </div>
          <div class="bl-modal-body">
            <p class="bl-modal-text">
              <strong>{{ completeModal.sprint?.sprint_name }}</strong> has
              <strong>{{ completeModal.incomplete }}</strong> incomplete {{ taskWord.toLowerCase() }}{{ completeModal.incomplete !== 1 ? 's' : '' }}.
            </p>
            <p class="bl-modal-label">Move incomplete {{ taskWord.toLowerCase() }}s to:</p>
            <div class="bl-radio-group">
              <label class="bl-radio">
                <input type="radio" v-model="completeModal.moveTo" value="__backlog__" />
                <span>Backlog</span>
              </label>
              <label v-for="s in moveTargetSprints" :key="s.name" class="bl-radio">
                <input type="radio" v-model="completeModal.moveTo" :value="s.name" />
                <span>{{ s.sprint_name }} <span class="bl-radio-sub">(Planning)</span></span>
              </label>
            </div>
          </div>
          <div class="bl-modal-foot">
            <button class="bl-btn bl-btn--ghost" @click="completeModal.open = false">Cancel</button>
            <button class="bl-btn bl-btn--complete" :disabled="completing" @click="submitCompleteSprint">
              <div v-if="completing" class="bl-spinner bl-spinner--sm" />
              Complete sprint
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ── GOAL MODAL ── -->
    <Transition name="bl-modal">
      <div v-if="goalModal.open" class="bl-modal-backdrop" @click.self="goalModal.open = false">
        <div class="bl-modal bl-modal--sm">
          <div class="bl-modal-head">
            <h2 class="bl-modal-title">Sprint goal</h2>
            <button class="bl-kebab" @click="goalModal.open = false"><svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg></button>
          </div>
          <div class="bl-modal-body">
            <textarea v-model="goalModal.value" class="bl-goal-textarea" placeholder="What is the goal of this sprint?" rows="3" autofocus />
          </div>
          <div class="bl-modal-foot">
            <button class="bl-btn bl-btn--ghost" @click="goalModal.open = false">Cancel</button>
            <button class="bl-btn bl-btn--primary" @click="submitGoal">Save</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ── CONTEXT MENU ── -->
    <TaskContextMenu :issue="ctxIssue" :x="ctxX" :y="ctxY" @close="ctxIssue = null" />

    <MoneyDrawer v-model:open="moneyDrawerOpen" :project="store.currentProject?.name"
      :doctype="moneyDrawerDoctype" :name="moneyDrawerName" />

    <SprintCapacityModal v-model:open="capacityModal.open" :sprint="capacityModal.sprint" />
    <SprintStandupModal v-model:open="standupModal.open" :sprint="standupModal.sprint" :sprint-name="standupModal.sprintName" />

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Skeleton } from '@/ui'
import { useProjectStore } from '@/stores/project'
import * as api from '@/utils/api.js'
import DatePicker       from '@/components/DatePicker.vue'
import FieldDropdown    from '@/components/FieldDropdown.vue'
import DropdownItem     from '@/components/DropdownItem.vue'
import BacklogTaskRow   from '@/components/BacklogTaskRow.vue'
import BacklogColumnBar from '@/components/BacklogColumnBar.vue'
import SprintCapacityModal from '@/components/SprintCapacityModal.vue'
import SprintStandupModal from '@/components/SprintStandupModal.vue'
import TaskContextMenu from '@/components/TaskContextMenu.vue'
import MoneyDrawer from '@/components/MoneyDrawer.vue'
import ErpMirrorFieldsButton from '@/components/ErpMirrorFieldsButton.vue'
import { useErpDocOpener } from '@/composables/useErpDocOpener.js'
import { useMirrorColumns } from '@/composables/useMirrorColumns.js'
import { getTaskWord } from '@/constants/project-templates'

const route = useRoute()
const store = useProjectStore()
const { moneyDrawerOpen, moneyDrawerDoctype, moneyDrawerName, openErpDoc } = useErpDocOpener()
const projectName = computed(() => store.currentProject?.name)
const taskWord = computed(() => getTaskWord(store.currentProject?.template_used))
const mirror = useMirrorColumns(projectName, 'backlog')

// ── State ─────────────────────────────────────────────────────────────────────
const loading        = ref(true)
const sprints        = ref([])
const collapsed      = ref({})
const creating       = ref(false)
const completing     = ref(false)
const showCompleted  = ref(false)
const showCreateForm = ref(false)

// ── Sprint column catalog (Monday-style "column center") — which optional
// badges/columns show per sprint, personal + persisted, not project data.
// Progress/dates/goal stay always-on (core, already compact). Two groups:
// header badges (summary, shown once per sprint) and task columns (shown
// on every row + aggregated in the footer — the actual "column center").
const SPRINT_HEADER_CATALOG = [
  { key: 'connected', label: 'Connected tasks' },
  { key: 'effort',    label: 'Total estimated effort' },
]
const SPRINT_TASK_COLUMN_CATALOG = [
  { key: 'points',       label: 'Estimated SP' },
  { key: 'actualPoints', label: 'Actual SP' },
  { key: 'unplanned',    label: 'Unplanned?' },
  { key: 'epic',         label: 'Epic' },
]
const DEFAULT_SPRINT_COLUMNS = { connected: false, effort: false, points: false, actualPoints: false, unplanned: false, epic: false }
const SPRINT_COLUMNS_KEY = 'bp_sprint_columns'
const sprintColumns = ref((() => {
  try {
    const saved = JSON.parse(localStorage.getItem(SPRINT_COLUMNS_KEY) || 'null')
    return saved && typeof saved === 'object' ? { ...DEFAULT_SPRINT_COLUMNS, ...saved } : { ...DEFAULT_SPRINT_COLUMNS }
  } catch { return { ...DEFAULT_SPRINT_COLUMNS } }
})())
function toggleSprintColumn(key) {
  sprintColumns.value = { ...sprintColumns.value, [key]: !sprintColumns.value[key] }
  localStorage.setItem(SPRINT_COLUMNS_KEY, JSON.stringify(sprintColumns.value))
}
// Any task-level column active → sections render a header/footer row.
const hasTaskColumns = computed(() => SPRINT_TASK_COLUMN_CATALOG.some(c => sprintColumns.value[c.key]))
const newSprintName  = ref('')
const newSprintStart = ref(null)
const newSprintEnd   = ref(null)
const dragIssue      = ref(null)
const dragTarget     = ref(null)
const completeModal  = ref({ open: false, sprint: null, incomplete: 0, moveTo: '__backlog__' })
const goalModal      = ref({ open: false, sprint: null, value: '' })
const capacityModal  = ref({ open: false, sprint: null })
function openCapacity(sprint) { capacityModal.value = { open: true, sprint: sprint.name } }
const standupModal   = ref({ open: false, sprint: null, sprintName: '' })
function openStandup(sprint) { standupModal.value = { open: true, sprint: sprint.name, sprintName: sprint.sprint_name } }
const ctxIssue       = ref(null)
const ctxX           = ref(0)
const ctxY           = ref(0)

// ── Computed ──────────────────────────────────────────────────────────────────
const activeSprint     = computed(() => sprints.value.find(s => s.status === 'Active') || null)
const planningSprints  = computed(() => sprints.value.filter(s => s.status === 'Planning'))
const completedSprints = computed(() => sprints.value.filter(s => s.status === 'Completed'))

// All issues proxied from store — TaskDetail mutations reflect here immediately
const allIssues = computed(() => store.backlogIssues || [])

// Issues grouped by sprint name
const issuesBySprint = computed(() => {
  const map = {}
  for (const s of sprints.value) map[s.name] = []
  for (const issue of allIssues.value) {
    if (issue.sprint && map[issue.sprint] !== undefined) {
      map[issue.sprint].push(issue)
    }
  }
  return map
})

// Issues with no sprint assigned
const noSprintIssues = computed(() => allIssues.value.filter(i => !i.sprint))

// Live counts derived from allIssues — updates immediately on status change
const sprintCounts = computed(() => {
  const doneSet = new Set(
    store.workflowStates
      .filter(s => s.category === 'completed' || s.category === 'cancelled')
      .map(s => s.name)
  )
  const map = {}
  for (const issue of allIssues.value) {
    if (!issue.sprint) continue
    if (!map[issue.sprint]) map[issue.sprint] = { total: 0, done: 0 }
    map[issue.sprint].total++
    if (doneSet.has(issue.status)) map[issue.sprint].done++
  }
  return map
})

const moveTargetSprints = computed(() =>
  planningSprints.value.filter(s => s.name !== completeModal.value.sprint?.name)
)

function progressPct(sprint) {
  const c = sprintCounts.value[sprint.name]
  if (!c || !c.total) return 0
  return Math.round((c.done / c.total) * 100)
}

function sprintLabel(sprint) {
  const c = sprintCounts.value[sprint.name]
  return c ? `${c.done}/${c.total}` : '0/0'
}

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    if (!store.projects.length) await store.fetchProjects()
    const proj = store.projects.find(p => p.key === route.params.key)
    if (!proj) return

    if (!store.currentProject || store.currentProject.key !== route.params.key) {
      await store.fetchBoard(proj.name)
    }

    const [sprintList, issues] = await Promise.all([
      api.getSprints(proj.name).catch(() => []),
      api.getBacklog(proj.name),
    ])

    sprints.value = sprintList || []
    store.setBacklogIssues(issues || [])

    await mirror.loadSchema().catch(() => {})
    await mirror.loadPrefs().catch(() => {})
    await mirror.loadValues(issues).catch(() => {})

    for (const s of (sprintList || [])) {
      if (!(s.name in collapsed.value)) {
        collapsed.value[s.name] = s.status === 'Completed'
      }
    }
    if (!('__backlog__' in collapsed.value)) collapsed.value['__backlog__'] = false
    if (!('__active__'  in collapsed.value)) collapsed.value['__active__']  = false
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => route.params.key, () => { collapsed.value = {}; load() })
watch(() => store.issueCreatedCount, () => load())

// ── Sprint actions ────────────────────────────────────────────────────────────
async function submitCreateSprint() {
  if (!newSprintName.value.trim() || creating.value) return
  creating.value = true
  try {
    const proj = store.projects.find(p => p.key === route.params.key)
    const s = await api.createSprint(proj.name, newSprintName.value.trim(), '', newSprintStart.value || '', newSprintEnd.value || '')
    sprints.value.push({ ...s, issue_count: 0, completed_count: 0 })
    collapsed.value[s.name] = false
    showCreateForm.value = false
    newSprintName.value = ''
    newSprintStart.value = null
    newSprintEnd.value = null
  } catch (e) {
    alert(e.message || 'Failed to create sprint')
  } finally {
    creating.value = false
  }
}

async function saveSprint(sprint, fields) {
  Object.assign(sprint, fields)
  try {
    await api.updateSprint(sprint.name, fields)
  } catch (e) {
    console.error('Failed to save sprint', e)
    await load()
  }
}

async function handleStartSprint(sprint) {
  if (activeSprint.value) return
  try {
    await api.startSprint(sprint.name)
    collapsed.value = {}
    await load()
    collapsed.value['__active__'] = false
  } catch (e) {
    alert(e.message || 'Failed to start sprint')
  }
}

function openCompleteModal(sprint) {
  const c = sprintCounts.value[sprint.name] || { total: 0, done: 0 }
  completeModal.value = { open: true, sprint, incomplete: c.total - c.done, moveTo: '__backlog__' }
}

async function submitCompleteSprint() {
  if (completing.value) return
  completing.value = true
  try {
    const target = completeModal.value.moveTo === '__backlog__' ? '' : completeModal.value.moveTo
    await api.completeSprint(completeModal.value.sprint.name, target)
    completeModal.value.open = false
    collapsed.value = {}
    await load()
  } catch (e) {
    alert(e.message || 'Failed to complete sprint')
  } finally {
    completing.value = false
  }
}

async function handleDeleteSprint(sprint) {
  if (!confirm(`Delete "${sprint.sprint_name}"? Issues will be moved to the backlog.`)) return
  try {
    await api.deleteSprint(sprint.name)
    await load()
  } catch (e) {
    alert(e.message || 'Failed to delete sprint')
  }
}

function openGoalEdit(sprint) {
  goalModal.value = { open: true, sprint, value: sprint.goal || '' }
}
async function submitGoal() {
  await saveSprint(goalModal.value.sprint, { goal: goalModal.value.value })
  goalModal.value.open = false
}

function openCreateInSprint(sprint) {
  store.createTaskDefaults = { sprint: sprint.name }
  store.showCreateTask = true
}
function openCreateInBacklog() {
  store.createTaskDefaults = { sprint: null }
  store.showCreateTask = true
}

// ── Drag and drop ─────────────────────────────────────────────────────────────
function onDragStart(e, issue) {
  dragIssue.value = issue
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', issue.name)
}

function onDragOverSection(e, targetId) {
  if (!dragIssue.value) return
  e.dataTransfer.dropEffect = 'move'
  dragTarget.value = targetId
}

function onDragLeave(e) {
  if (!e.currentTarget.contains(e.relatedTarget)) dragTarget.value = null
}

async function onDrop(e, targetId) {
  dragTarget.value = null
  if (!dragIssue.value) return
  const issue = dragIssue.value
  dragIssue.value = null

  const targetSprint  = targetId === '__backlog__' ? null : targetId
  const currentSprint = issue.sprint || null
  if (currentSprint === targetSprint) return

  issue.sprint = targetSprint

  try {
    await api.moveTaskToSprint(issue.name, targetSprint || '')
    const proj = store.projects.find(p => p.key === route.params.key)
    const updated = await api.getSprints(proj.name)
    for (const us of updated) {
      const local = sprints.value.find(s => s.name === us.name)
      if (local) Object.assign(local, { issue_count: us.issue_count, completed_count: us.completed_count })
    }
  } catch (e) {
    console.error('Failed to move issue', e)
    await load()
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function toggleCollapse(id) {
  collapsed.value[id] = !collapsed.value[id]
}

function onContextMenu(e, issue) {
  ctxIssue.value = issue
  ctxX.value = e.clientX
  ctxY.value = e.clientY
}
</script>

<style scoped>
.bl-root { height: 100%; overflow-y: auto; padding: 20px 24px 60px; background: var(--background); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; color: var(--foreground); -webkit-font-smoothing: antialiased; }
.bl-loading { display: flex; align-items: center; justify-content: center; height: 200px; gap: 10px; color: var(--muted); }

.bl-section { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; margin-bottom: 10px; overflow: hidden; transition: border-color .15s; }
.bl-section--active    { border-color: var(--success-soft); }
.bl-section--completed { opacity: .8; }
.bl-section--dragover  { border-color: var(--accent); box-shadow: var(--shadow-focus); }

.bl-section-head { display: flex; align-items: center; gap: 10px; padding: 10px 14px; cursor: pointer; user-select: none; border-bottom: 1px solid var(--surface-secondary); transition: background .08s; }
.bl-section-head:hover { background: var(--background); }

.bl-chevron { color: var(--muted); background: none; border: none; padding: 2px; cursor: pointer; flex-shrink: 0; transition: transform .15s; display: flex; align-items: center; }
.bl-chevron--open { transform: rotate(90deg); }

.bl-sprint-badge { flex-shrink: 0; padding: 2px 7px; border-radius: 3px; font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
.bl-badge-planning  { background: var(--surface-secondary); color: var(--foreground); }
.bl-badge-active    { background: var(--success-soft); color: var(--success-soft-foreground); }
.bl-badge-completed { background: var(--accent-soft); color: var(--accent-soft-foreground); }

.bl-sprint-name { font-size: 13.5px; font-weight: 700; color: var(--foreground); background: none; border: 1px solid transparent; border-radius: 3px; padding: 2px 6px; outline: none; flex-shrink: 0; min-width: 80px; max-width: 260px; transition: border-color .1s, background .1s; }
.bl-sprint-name:hover { border-color: var(--border); background: var(--surface-secondary); }
.bl-sprint-name:focus { border-color: var(--accent); background: var(--surface); }
.bl-sprint-name-static { font-size: 13.5px; font-weight: 700; color: var(--foreground); flex-shrink: 0; }
.bl-sprint-dates-static { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--muted); flex-shrink: 0; }
.bl-sprint-dates { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.bl-date-sep { font-size: 11px; color: var(--muted); }

.bl-progress { display: flex; align-items: center; gap: 7px; flex-shrink: 0; }
.bl-progress-bar { width: 72px; height: 5px; background: var(--border); border-radius: 99px; overflow: hidden; }
.bl-progress-fill { height: 100%; background: var(--accent); border-radius: 99px; transition: width .3s; }
.bl-fill-done { background: var(--success); }
.bl-progress-label { font-size: 11px; color: var(--muted); white-space: nowrap; }

.bl-col-badge {
  flex-shrink: 0; padding: 2px 7px; border-radius: 3px;
  font-size: 10.5px; font-weight: 600; white-space: nowrap;
  background: var(--surface-secondary); color: var(--muted);
}

.bl-col-menu-label {
  font-size: 10px; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.06em;
  padding: 5px 11px 3px;
}
.bl-col-check {
  width: 14px; height: 14px; border-radius: 3px; flex-shrink: 0;
  border: 1px solid var(--border-secondary); display: flex; align-items: center; justify-content: center;
  color: var(--accent-foreground); transition: background-color .1s, border-color .1s;
}
.bl-col-check--on { background: var(--accent); border-color: var(--accent); }

.bl-sprint-actions { display: flex; align-items: center; gap: 6px; margin-left: auto; flex-shrink: 0; }
.bl-section-title { font-size: 13.5px; font-weight: 700; color: var(--foreground); }
.bl-count { font-size: 12px; color: var(--muted); background: var(--surface-secondary); padding: 1px 7px; border-radius: 99px; }

.bl-btn { display: inline-flex; align-items: center; gap: 5px; height: 28px; padding: 0 11px; font-size: 12px; font-weight: 600; font-family: inherit; border-radius: 3px; cursor: pointer; white-space: nowrap; transition: background .1s, border-color .1s; border: 1.5px solid transparent; text-decoration: none; }
.bl-btn--primary  { color: var(--accent-foreground); background: var(--accent); border-color: var(--accent); }
.bl-btn--primary:hover  { background: var(--accent-hover); }
.bl-btn--primary:disabled { opacity: .5; cursor: not-allowed; }
.bl-btn--start    { color: var(--success-soft-foreground); background: var(--success-soft); border-color: var(--success-soft); }
.bl-btn--start:hover:not(:disabled) { background: var(--success-soft-hover); }
.bl-btn--start:disabled { opacity: .4; cursor: not-allowed; }
.bl-btn--complete { color: var(--accent-soft-foreground); background: var(--accent-soft); border-color: var(--accent-soft); }
.bl-btn--complete:hover { background: var(--accent-soft-hover); }
.bl-btn--complete:disabled { opacity: .5; cursor: not-allowed; }
.bl-btn--ghost    { color: var(--foreground); background: var(--surface); border-color: var(--border); }
.bl-btn--ghost:hover { background: var(--surface-secondary); }
.bl-btn--board-link { color: var(--accent); background: var(--accent-soft); border-color: var(--accent-soft); }
.bl-btn--board-link:hover { background: var(--accent-soft-hover); }
.bl-btn--sprint-detail { color: var(--foreground); background: var(--surface); border-color: var(--border); }
.bl-btn--sprint-detail:hover { background: var(--surface-secondary); }

.bl-kebab { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: none; border: 1px solid transparent; border-radius: 3px; color: var(--muted); cursor: pointer; flex-shrink: 0; transition: background .08s; }
.bl-kebab:hover { background: var(--surface-secondary); border-color: var(--border); color: var(--foreground); }

.bl-sprint-goal { display: flex; align-items: center; gap: 6px; padding: 7px 14px; font-size: 12px; color: var(--muted); font-style: italic; border-bottom: 1px solid var(--surface-secondary); }

.bl-drop-zone { min-height: 48px; transition: background .12s; }
.bl-drop-zone--over { background: var(--accent-soft); }
.bl-drop-hint { display: flex; align-items: center; justify-content: center; gap: 7px; padding: 18px; font-size: 12.5px; color: var(--muted); font-style: italic; }

/* Task row styling now lives in BacklogTaskRow.vue (extracted so the same
   row + its optional columns render consistently across all 4 sections). */

.bl-add-row { display: flex; align-items: center; gap: 7px; width: 100%; padding: 8px 14px; font-size: 12.5px; font-weight: 500; font-family: inherit; color: var(--muted); background: none; border: none; border-top: 1px solid var(--surface-secondary); cursor: pointer; text-align: left; transition: color .1s, background .1s; }
.bl-add-row:hover { color: var(--accent); background: var(--accent-soft); }

.bl-empty-sprint { padding: 20px 14px; text-align: center; font-size: 13px; color: var(--muted); }
.bl-inline-link { color: var(--accent); background: none; border: none; font: inherit; cursor: pointer; text-decoration: underline; }

.bl-completed-toggle { margin: 4px 0 8px; }
.bl-toggle-completed { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600; color: var(--muted); background: none; border: none; cursor: pointer; padding: 4px 6px; border-radius: 3px; transition: color .1s, background .1s; }
.bl-toggle-completed:hover { color: var(--foreground); background: var(--surface-secondary); }

.bl-create-sprint { margin-top: 12px; }
.bl-create-form { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.bl-create-input { height: 34px; padding: 0 10px; width: 100%; font-size: 13px; font-family: inherit; color: var(--foreground); background: var(--surface-secondary); border: 1.5px solid var(--border); border-radius: 4px; outline: none; transition: border-color .1s, background .1s; }
.bl-create-input:focus { background: var(--surface); border-color: var(--accent); }
.bl-create-dates { display: flex; align-items: center; gap: 8px; }
.bl-create-actions { display: flex; align-items: center; gap: 8px; }

.bl-spinner { width: 16px; height: 16px; border-radius: 50%; border: 2.5px solid rgba(255,255,255,.3); border-top-color: var(--accent-foreground); animation: bl-spin .7s linear infinite; flex-shrink: 0; }
.bl-spinner--sm { width: 12px; height: 12px; border-width: 2px; }
@keyframes bl-spin { to { transform: rotate(360deg); } }

.bl-modal-backdrop { position: fixed; inset: 0; z-index: 1000; background: var(--backdrop); display: flex; align-items: center; justify-content: center; }
.bl-modal { background: var(--overlay); border-radius: 6px; width: 440px; max-width: calc(100vw - 32px); box-shadow: var(--overlay-shadow); }
.bl-modal--sm { width: 380px; }
.bl-modal-head { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px 14px; border-bottom: 1px solid var(--border); }
.bl-modal-title { font-size: 15px; font-weight: 700; color: var(--foreground); }
.bl-modal-body  { padding: 18px 20px; }
.bl-modal-foot  { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 20px; border-top: 1px solid var(--border); }
.bl-modal-text  { font-size: 13.5px; color: var(--foreground); margin: 0 0 14px; line-height: 1.5; }
.bl-modal-label { font-size: 12px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; margin-bottom: 10px; }
.bl-radio-group { display: flex; flex-direction: column; gap: 8px; }
.bl-radio { display: flex; align-items: center; gap: 9px; font-size: 13.5px; color: var(--foreground); cursor: pointer; }
.bl-radio input { accent-color: var(--accent); cursor: pointer; }
.bl-radio-sub { font-size: 11.5px; color: var(--muted); }
.bl-goal-textarea { width: 100%; resize: vertical; min-height: 76px; padding: 9px 10px; font-size: 13px; font-family: inherit; color: var(--foreground); background: var(--surface-secondary); border: 1.5px solid var(--border); border-radius: 4px; outline: none; line-height: 1.5; transition: border-color .1s, background .1s; }
.bl-goal-textarea:focus { background: var(--surface); border-color: var(--accent); }

.bl-modal-enter-active { transition: opacity .15s, transform .15s; }
.bl-modal-leave-active { transition: opacity .1s, transform .1s; }
.bl-modal-enter-from, .bl-modal-leave-to { opacity: 0; }
.bl-modal-enter-from .bl-modal, .bl-modal-leave-to .bl-modal { transform: scale(.97) translateY(-6px); }
</style>