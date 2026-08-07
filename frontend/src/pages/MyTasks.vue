<template>
  <!-- Outer wrapper — `relative` so the Customize panel can overlay -->
  <div class="flex flex-col h-full bg-overlay overflow-hidden relative" :style="{ '--row-h': rowHeight }">

    <!-- ── Page header ─────────────────────────────────────────────── -->
    <div class="px-6 pt-5 pb-0 border-b border-border flex-shrink-0">
      <div class="flex items-center justify-between mb-3">

        <!-- Left: avatar + title -->
        <div class="flex items-center gap-3">
          <Avatar :name="userLabel" size="sm" :color="avatarColor" class="ring-1 ring-border" />
          <div>
            <h1 class="text-[15px] font-semibold text-foreground leading-tight">My Tasks</h1>
            <p v-if="!loading" class="text-xs text-muted mt-0.5 tabular-nums">
              {{ counts.open }} open
              <template v-if="counts.completed"> · {{ counts.completed }} done</template>
            </p>
          </div>
        </div>

        <!-- Right: tabs + customize button -->
        <div class="flex items-center gap-2">
          <Tabs v-model="statusFilter" variant="solid" size="sm" :items="STATUS_FILTERS" />
          <button
            @click="showCustomize = !showCustomize"
            class="inline-flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md border transition-colors whitespace-nowrap"
            :class="showCustomize
              ? 'bg-accent-soft text-accent border-accent'
              : 'bg-overlay text-muted border-border hover:bg-surface-secondary hover:text-foreground'"
            title="Customize view">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
            Customize
          </button>
        </div>
      </div>
    </div>

    <!-- ── Toolbar — FilterChip style ──────────────────────────────── -->
    <div class="flex items-center gap-2 px-4 py-2 border-b border-separator flex-shrink-0 bg-overlay">

      <!-- Group by -->
      <FieldDropdown width="w-44">
        <template #trigger>
          <button class="h-7 px-2 inline-flex items-center gap-1.5 text-[11px] bg-overlay border border-border rounded text-muted hover:bg-surface-secondary transition-colors whitespace-nowrap">
            Group:
            <span class="font-semibold text-foreground">{{ GROUP_OPTIONS.find(g => g.v === groupBy)?.label }}</span>
            <svg class="w-3 h-3 text-muted" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>
          </button>
        </template>
        <DropdownItem v-for="g in GROUP_OPTIONS" :key="g.v" :active="groupBy === g.v" @click="groupBy = g.v">
          {{ g.label }}
        </DropdownItem>
      </FieldDropdown>

      <!-- Sort by -->
      <FieldDropdown width="w-44">
        <template #trigger>
          <button class="h-7 px-2 inline-flex items-center gap-1.5 text-[11px] bg-overlay border border-border rounded text-muted hover:bg-surface-secondary transition-colors whitespace-nowrap">
            Sort:
            <span class="font-semibold text-foreground">{{ SORT_OPTIONS.find(s => s.v === sortBy)?.label }}</span>
            <svg class="w-3 h-3 text-muted" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>
          </button>
        </template>
        <DropdownItem v-for="s in SORT_OPTIONS" :key="s.v" :active="sortBy === s.v" @click="sortBy = s.v">
          {{ s.label }}
        </DropdownItem>
      </FieldDropdown>

      <!-- Project filter (multi-project only) -->
      <FieldDropdown v-if="allProjects.length > 1" width="w-52">
        <template #trigger>
          <button class="h-7 px-2 inline-flex items-center gap-1.5 text-[11px] bg-overlay border border-border rounded text-muted hover:bg-surface-secondary transition-colors whitespace-nowrap">
            <span v-if="!projectFilter" class="font-semibold text-foreground">All projects</span>
            <span v-else class="font-semibold text-foreground">{{ allProjects.find(p => p.name === projectFilter)?.project_name }}</span>
            <svg class="w-3 h-3 text-muted" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>
          </button>
        </template>
        <DropdownItem :active="!projectFilter" @click="projectFilter = ''">All projects</DropdownItem>
        <DropdownItem v-for="p in allProjects" :key="p.name" :active="projectFilter === p.name" @click="projectFilter = p.name">
          <ProjectAvatar :theme="projectByName(p.name)?.theme" :seed="projectByName(p.name)?.key || p.name" size="xs" />
          {{ p.project_name }}
        </DropdownItem>
      </FieldDropdown>

      <!-- Right: task count -->
      <div class="ml-auto text-[11px] text-muted tabular-nums pr-1">
        {{ counts.open + counts.completed }} tasks
      </div>
    </div>

    <!-- ── Body: table + customize panel side-by-side ─────────────── -->
    <div class="flex flex-1 min-h-0 overflow-hidden">

      <!-- ── Table area ──────────────────────────────────────────────── -->
      <div class="flex-1 overflow-auto px-6 py-4">
        <div class="shadow-surface rounded-lg overflow-hidden bg-surface">
        <table class="w-full border-collapse table-fixed">

          <colgroup>
            <col v-if="cols.id"       :style="{ width: cw.id + 'px' }" />
            <col />
            <col v-if="cols.status"   :style="{ width: cw.status + 'px' }" />
            <col v-if="showProjectCol" :style="{ width: cw.project + 'px' }" />
            <col v-if="cols.due_date" :style="{ width: cw.due + 'px' }" />
            <col v-if="cols.priority" :style="{ width: cw.priority + 'px' }" />
          </colgroup>

          <!-- Sticky column headers -->
          <thead class="sticky top-0 z-10">
            <tr>
              <th v-if="cols.id"       class="th th-resz text-right pr-4">ID<span class="th-rh" @mousedown.stop.prevent="startResize($event,'id')"/></th>

              <th class="th">Task name</th>

              <th v-if="cols.status"   class="th th-resz">Status<span class="th-rh" @mousedown.stop.prevent="startResize($event,'status')"/></th>
              <th v-if="showProjectCol" class="th th-resz">Project<span class="th-rh" @mousedown.stop.prevent="startResize($event,'project')"/></th>
              <th v-if="cols.due_date" class="th th-resz">Due date<span class="th-rh" @mousedown.stop.prevent="startResize($event,'due')"/></th>
              <th v-if="cols.priority" class="th text-center">Priority</th>
            </tr>
          </thead>

          <tbody>
            <!-- Loading skeleton -->
            <template v-if="loading">
              <tr v-for="n in 8" :key="n" class="bg-overlay border-b border-separator" style="height: var(--row-h)">
                <td class="px-3"><div class="h-2.5 rounded animate-pulse bg-surface-secondary" :style="{ width: skW(n,0) }"/></td>
                <td v-if="cols.status"    class="px-3"><div class="h-2.5 rounded animate-pulse bg-surface-secondary" :style="{ width: skW(n,1) }"/></td>
                <td v-if="showProjectCol" class="px-3"><div class="h-2.5 rounded animate-pulse bg-surface-secondary" :style="{ width: skW(n,2) }"/></td>
                <td v-if="cols.due_date"  class="px-3"><div class="h-2.5 rounded animate-pulse bg-surface-secondary" :style="{ width: skW(n,3) }"/></td>
                <td v-if="cols.priority"/><td v-if="cols.id"/>
              </tr>
            </template>

            <!-- Empty state -->
            <template v-else-if="totalCount === 0">
              <tr>
                <td :colspan="colCount" class="py-16 text-center">
                  <EmptyState
                    :icon="CheckCircle"
                    :title="statusFilter === 'open' ? 'All clear' : 'No tasks'"
                    :description="statusFilter === 'open'
                      ? 'No open tasks assigned to you right now.'
                      : 'Tasks matching these filters appear here.'"
                  />
                </td>
              </tr>
            </template>

            <!-- Grouped rows -->
            <template v-else>
              <template v-for="(group, gkey) in grouped" :key="gkey">

                <!-- Group header row -->
                <tr
                  class="bg-background border-b border-border cursor-pointer hover:bg-surface-secondary transition-colors sticky top-[33px] z-[5]"
                  style="height: 36px"
                  @click="toggleGroup(gkey)">
                  <td :colspan="colCount" class="px-3">
                    <div class="flex items-center gap-2">
                      <svg
                        class="w-3 h-3 text-muted transition-transform shrink-0"
                        :class="{ 'rotate-90': !collapsed.has(gkey) }"
                        fill="none" stroke="currentColor" stroke-width="2.5"
                        stroke-linecap="round" stroke-linejoin="round"
                        viewBox="0 0 24 24">
                        <path d="M9 18l6-6-6-6"/>
                      </svg>
                      <span v-if="groupBy === 'status'"  class="w-1.5 h-1.5 rounded-full shrink-0" :style="{ background: sectionStatusColor(gkey) }" />
                      <span v-if="groupBy === 'project'" class="w-1.5 h-1.5 rounded-full shrink-0" :style="{ background: projectColor(gkey) }" />
                      <PriorityIndicator v-if="groupBy === 'priority'" :priority="gkey" />
                      <span class="text-[11px] font-medium uppercase tracking-wider text-muted">{{ gkey }}</span>
                      <span v-if="groupBy === 'due_date' && gkey === 'Overdue'"
                        class="text-[10px] font-semibold text-danger-soft-foreground bg-danger-soft px-1.5 py-px rounded">
                        Overdue
                      </span>
                      <span class="text-[10px] text-muted tabular-nums">({{ group.length }})</span>
                    </div>
                  </td>
                </tr>

                <!-- Task rows -->
                <template v-if="!collapsed.has(gkey)">
                  <tr
                    v-for="(task, idx) in group" :key="task.name"
                    class="bg-overlay border-b border-separator cursor-pointer transition-colors duration-75"
                    style="height: var(--row-h)"
                    :class="{
                      'hover:bg-surface-secondary':           !isOverdue(task),
                      'bg-danger-soft hover:bg-danger-soft-hover': isOverdue(task),
                      'opacity-50':                  task.status_category === 'completed',
                    }"
                    @click="openTask(task)">

                     <!-- Task key -->
                    <td v-if="cols.id" class="px-3 w-[76px] text-right pr-4">
                      <span class="font-mono text-[11px] text-muted hover:text-muted transition-colors tabular-nums">
                        {{ task.task_key }}
                      </span>
                    </td>

                    <!-- Task name -->
                    <td class="px-3 max-w-0">
                      <div class="flex items-center gap-2 overflow-hidden">
                        <span
                          class="shrink-0 w-[18px] h-[18px] rounded flex items-center justify-center text-[9px] font-bold"
                          :style="{ background: typeColor(task) + '1C', color: typeColor(task) }"
                          :title="task.task_type">
                          {{ (task.task_type || 'T').charAt(0).toUpperCase() }}
                        </span>
                        <span
                          class="text-[13px] font-medium text-foreground truncate leading-none"
                          :class="{ 'line-through text-muted font-normal': task.status_category === 'completed' }">
                          {{ task.title }}
                        </span>
                        <span v-if="task.is_reporter && !task.is_assigned"
                          class="shrink-0 text-[10px] text-muted bg-surface-secondary px-1.5 py-px rounded whitespace-nowrap">
                          reported
                        </span>
                        <button
                          v-for="g in erpBadges(task)" :key="g.doctype"
                          class="shrink-0 inline-flex items-center h-[16px] px-1.5 rounded text-[9.5px] font-bold text-accent-soft-foreground bg-accent-soft"
                          :title="g.items.map(r => r.ref_label || r.ref_name).join(', ')"
                          @click.stop="openTaskErpDoc(task, g.items[0].ref_doctype, g.items[0].ref_name)"
                        >{{ g.abbr }}<template v-if="g.n > 1">×{{ g.n }}</template></button>
                        <span
                          v-if="task.billable && task.estimated_hours"
                          class="shrink-0 inline-flex items-center justify-center w-[16px] h-[16px] rounded text-[9.5px] font-extrabold text-success-soft-foreground bg-success-soft"
                          :title="`${task.estimated_hours}h billable`"
                        >$</span>
                      </div>
                    </td>

                    <!-- Status -->
                    <td v-if="cols.status" class="px-3 w-[148px]" @click.stop>
                      <FieldDropdown width="w-52">
                        <template #trigger>
                          <button
                            class="inline-flex items-center gap-2 h-6 px-1.5 -ml-1 rounded-md text-[12px] font-medium text-foreground max-w-[140px] hover:bg-surface-secondary transition-colors">
                            <span class="w-2.5 h-2.5 rounded-[3px] shrink-0" :style="{ background: task.status_color || 'var(--muted)' }" />
                            <span class="truncate">{{ task.status }}</span>
                          </button>
                        </template>
                        <DropdownItem
                          v-for="s in workflowFor(task)" :key="s.name"
                          :active="task.status === s.name"
                          @click="setStatus(task, s)">
                          <span class="w-2.5 h-2.5 rounded-[3px] shrink-0" :style="{ background: s.color }" />
                          {{ s.name }}
                        </DropdownItem>
                      </FieldDropdown>
                    </td>

                    <!-- Project pill -->
                    <td v-if="showProjectCol" class="px-3 w-32">
                      <span
                        class="text-[11px] font-medium px-2 py-0.5 rounded truncate block max-w-[116px]"
                        :style="{
                          background: projectColor(task.project_name) + '18',
                          color: projectColor(task.project_name),
                        }">
                        {{ task.project_name }}
                      </span>
                    </td>

                    <!-- Due date -->
                    <td v-if="cols.due_date" class="px-3 w-24 [&_.text-muted]:text-muted">
                      <DueDateChip :date="task.due_date" absolute />
                    </td>

                    <!-- Priority -->
                    <td v-if="cols.priority" class="px-3 w-16 text-center" @click.stop>
                      <FieldDropdown width="w-36">
                        <template #trigger>
                          <button class="p-1 rounded hover:bg-surface-secondary transition-colors" :title="task.priority">
                            <PriorityIndicator :priority="task.priority || 'Medium'" />
                          </button>
                        </template>
                        <DropdownItem
                          v-for="p in PRIORITIES" :key="p.value"
                          :active="task.priority === p.value"
                          @click="setPriority(task, p.value)">
                          <PriorityIndicator :priority="p.value" />
                          {{ p.label }}
                        </DropdownItem>
                      </FieldDropdown>
                    </td>

                   

                  </tr>
                </template>
              </template>
            </template>
          </tbody>
        </table>
        </div><!-- /box -->
      </div>

      <!-- ── Customize panel ──────────────────────────────────────────── -->
      <Transition name="panel-slide">
        <div
          v-if="showCustomize"
          class="w-[272px] flex-shrink-0 border-l border-border bg-overlay overflow-y-auto flex flex-col">

          <!-- Panel header -->
          <div class="flex items-center justify-between px-4 py-3 border-b border-separator flex-shrink-0">
            <span class="text-[13px] font-semibold text-foreground">Customize</span>
            <button
              @click="showCustomize = false"
              class="w-6 h-6 flex items-center justify-center rounded hover:bg-surface-secondary text-muted hover:text-muted transition-colors">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <!-- Panel body -->
          <div class="px-4 py-4 flex flex-col gap-5 flex-1">

            <!-- ── Fields ─────────────────────────────────── -->
            <section>
              <p class="text-[10px] font-semibold uppercase tracking-widest text-muted mb-2">Fields</p>
              <div class="flex flex-col gap-0.5">
                <div
                  v-for="field in FIELD_DEFS" :key="field.key"
                  class="flex items-center justify-between py-2 px-2 rounded-md hover:bg-surface-secondary transition-colors">
                  <div class="flex items-center gap-2.5">
                    <!-- Field icon -->
                    <span class="w-5 h-5 flex items-center justify-center text-muted">
                      <component :is="field.icon" class="w-3.5 h-3.5" />
                    </span>
                    <span class="text-[13px] text-muted">{{ field.label }}</span>
                    <span v-if="field.note" class="text-[10px] text-muted">({{ field.note }})</span>
                  </div>
                  <!-- Toggle -->
                  <button
                    @click="toggleCol(field.key)"
                    :disabled="field.key === 'name'"
                    class="relative flex-shrink-0 w-8 h-[18px] rounded-full transition-colors duration-200 focus:outline-none disabled:opacity-40 disabled:cursor-not-allowed"
                    :class="cols[field.key] ? 'bg-primary' : 'bg-border'">
                    <span
                      class="block w-3.5 h-3.5 bg-overlay rounded-full shadow transition-transform duration-200 absolute top-[2px]"
                      :class="cols[field.key] ? 'translate-x-[14px]' : 'translate-x-[2px]'" />
                  </button>
                </div>
              </div>
            </section>

            <!-- ── Group by ────────────────────────────────── -->
            <section>
              <p class="text-[10px] font-semibold uppercase tracking-widest text-muted mb-2">Group by</p>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="g in GROUP_OPTIONS" :key="g.v"
                  @click="groupBy = g.v"
                  class="px-2.5 py-1 text-[12px] font-medium rounded-full border transition-colors"
                  :class="groupBy === g.v
                    ? 'bg-primary text-white border-primary'
                    : 'bg-overlay text-muted border-border hover:border-border-secondary hover:bg-surface-secondary'">
                  {{ g.label }}
                </button>
              </div>
            </section>

            <!-- ── Sort ──────────────────────────────────────── -->
            <section>
              <p class="text-[10px] font-semibold uppercase tracking-widest text-muted mb-2">Sort by</p>
              <div class="flex flex-wrap gap-1.5 mb-3">
                <button
                  v-for="s in SORT_OPTIONS" :key="s.v"
                  @click="sortBy = s.v"
                  class="px-2.5 py-1 text-[12px] font-medium rounded-full border transition-colors"
                  :class="sortBy === s.v
                    ? 'bg-primary text-white border-primary'
                    : 'bg-overlay text-muted border-border hover:border-border-secondary hover:bg-surface-secondary'">
                  {{ s.label }}
                </button>
              </div>
              <!-- Sort direction segmented -->
              <div class="flex rounded-lg border border-border overflow-hidden">
                <button
                  @click="sortOrder = 'asc'"
                  class="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[12px] font-medium transition-colors"
                  :class="sortOrder === 'asc'
                    ? 'bg-primary text-white'
                    : 'bg-overlay text-muted hover:bg-surface-secondary'">
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12"/>
                  </svg>
                  Ascending
                </button>
                <button
                  @click="sortOrder = 'desc'"
                  class="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[12px] font-medium transition-colors border-l border-border"
                  :class="sortOrder === 'desc'
                    ? 'bg-primary text-white'
                    : 'bg-overlay text-muted hover:bg-surface-secondary'">
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4"/>
                  </svg>
                  Descending
                </button>
              </div>
            </section>

            <!-- ── Row density ─────────────────────────────── -->
            <section>
              <p class="text-[10px] font-semibold uppercase tracking-widest text-muted mb-2">Row density</p>
              <div class="flex rounded-lg border border-border overflow-hidden">
                <button
                  v-for="(d, i) in DENSITIES" :key="d.v"
                  @click="density = d.v"
                  class="flex-1 py-1.5 text-[12px] font-medium transition-colors"
                  :class="[
                    density === d.v
                      ? 'bg-primary text-white'
                      : 'bg-overlay text-muted hover:bg-surface-secondary',
                    i > 0 ? 'border-l border-border' : '',
                  ]">
                  {{ d.label }}
                </button>
              </div>
              <!-- Visual preview of density -->
              <div class="mt-2 rounded-md border border-separator overflow-hidden">
                <div
                  v-for="n in 3" :key="n"
                  class="flex items-center gap-2 px-3 border-b border-separator last:border-0 bg-overlay transition-[height] duration-200"
                  :style="{ height: rowHeight }">
                  <div class="w-3 h-3 rounded-sm bg-border shrink-0" />
                  <div class="h-2 bg-surface-secondary rounded flex-1" :style="{ width: `${55 + n * 12}%` }" />
                </div>
              </div>
            </section>

            <!-- ── Reset ──────────────────────────────────────── -->
            <div class="pt-1 border-t border-separator">
              <button
                @click="resetPrefs"
                class="w-full py-2 text-[12px] text-muted hover:text-muted hover:bg-surface-secondary rounded-md transition-colors">
                Reset to defaults
              </button>
            </div>

          </div>
        </div>
      </Transition>

    </div><!-- /body flex -->

    <MoneyDrawer v-model:open="moneyDrawerOpen" :project="moneyDrawerProject" :doctype="moneyDrawerDoctype" :name="moneyDrawerName" />

  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, markRaw } from 'vue'
import { CheckCircle, Hash, Calendar, Flag, Layers, AlignLeft } from 'lucide-vue-next'
import { getMyTasks, updateTaskStatus, updateTask } from '@/utils/api'
import { useProjectStore } from '@/stores/project'
import { PRIORITIES }      from '@/utils/constants'

// ── @/ui components ──────────────────────────────────────────────────
import Avatar            from '@/ui/Avatar.vue'
import DueDateChip       from '@/ui/DueDateChip.vue'
import PriorityIndicator from '@/ui/PriorityIndicator.vue'
import EmptyState        from '@/ui/EmptyState.vue'
import Tabs              from '@/ui/Tabs.vue'
import ProjectAvatar     from '@/ui/ProjectAvatar.vue'

// ── @/components ─────────────────────────────────────────────────────
import FieldDropdown from '@/components/FieldDropdown.vue'
import DropdownItem  from '@/components/DropdownItem.vue'
import MoneyDrawer   from '@/components/MoneyDrawer.vue'
import { useErpDocOpener } from '@/composables/useErpDocOpener.js'

const store = useProjectStore()
const { moneyDrawerOpen, moneyDrawerDoctype, moneyDrawerName, openErpDoc } = useErpDocOpener()
// MyTasks spans projects, unlike ListView/Board/Backlog which are project-scoped —
// the drawer needs the owning project to gate Currency fields (view_money).
const moneyDrawerProject = ref('')
function openTaskErpDoc(task, doctype, name) {
  moneyDrawerProject.value = task.project
  openErpDoc(doctype, name)
}

// same doctype-grouping shape as ListView's ConnectCell summary.
function erpBadges(task) {
  const m = {}
  for (const r of (task.references || [])) (m[r.ref_doctype] ||= []).push(r)
  return Object.entries(m).map(([doctype, items]) => ({
    doctype, items, n: items.length,
    abbr: doctype.split(' ').map(w => w[0]).join('').toUpperCase(),
  }))
}

// ── State ────────────────────────────────────────────────────────────
const tasks       = ref([])
const grouped     = ref({})
const counts      = ref({ open: 0, completed: 0 })
const totalCount  = ref(0)
const loading     = ref(true)
const allProjects = ref([])
const collapsed   = ref(new Set())

const statusFilter  = ref('open')
const groupBy       = ref('project')
const sortBy        = ref('due_date')
const sortOrder     = ref('asc')
const projectFilter = ref('')

// ── Customize state ───────────────────────────────────────────────────
const showCustomize = ref(false)

const cols = ref({
  status:   true,
  project:  true,
  due_date: true,
  priority: true,
  id:       true,
})

const density = ref('default')

const DENSITIES = [
  { v: 'compact',     label: 'Compact',  height: '32px' },
  { v: 'default',     label: 'Default',  height: '40px' },
  { v: 'comfortable', label: 'Cozy',     height: '48px' },
]

const rowHeight = computed(() =>
  DENSITIES.find(d => d.v === density.value)?.height || '40px'
)

// ── Resizable column widths (persisted with prefs) ────────────────────
const COL_DEFAULTS = { id: 76, title: 320, status: 148, project: 140, due: 110, priority: 72 }
const cw = reactive({ ...COL_DEFAULTS })

// Visible columns in render order → exact table width (no w-full redistribution,
// so a resize drag moves only that column, 1:1 with the cursor).
const visibleColKeys = computed(() => {
  const k = []
  if (cols.value.id) k.push('id')
  k.push('title')
  if (cols.value.status) k.push('status')
  if (showProjectCol.value) k.push('project')
  if (cols.value.due_date) k.push('due')
  if (cols.value.priority) k.push('priority')
  return k
})
const tableWidth = computed(() =>
  visibleColKeys.value.reduce((s, k) => s + (cw[k] || 0), 0)
)

function startResize(e, key) {
  const x0 = e.clientX, w0 = cw[key]
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  const move = ev => { cw[key] = Math.max(56, w0 + ev.clientX - x0) }
  const up = () => {
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', move)
    window.removeEventListener('mouseup', up)
    savePrefs()
  }
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', up)
}

// ── Persist prefs to localStorage ─────────────────────────────────────
const PREFS_KEY = 'bp_mytasks_prefs'

function loadPrefs() {
  try {
    const saved = JSON.parse(localStorage.getItem(PREFS_KEY) || 'null')
    if (!saved) return
    if (saved.cols)       Object.assign(cols.value, saved.cols)
    if (saved.cw)         Object.assign(cw, saved.cw)
    if (saved.groupBy)    groupBy.value    = saved.groupBy
    if (saved.sortBy)     sortBy.value     = saved.sortBy
    if (saved.sortOrder)  sortOrder.value  = saved.sortOrder
    if (saved.density)    density.value    = saved.density
  } catch {}
}

function savePrefs() {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify({
      cols:      cols.value,
      cw:        { ...cw },
      groupBy:   groupBy.value,
      sortBy:    sortBy.value,
      sortOrder: sortOrder.value,
      density:   density.value,
    }))
  } catch {}
}

function resetPrefs() {
  cols.value     = { status: true, project: true, due_date: true, priority: true, id: true }
  groupBy.value  = 'project'
  sortBy.value   = 'due_date'
  sortOrder.value = 'asc'
  density.value  = 'default'
}

function toggleCol(key) {
  cols.value = { ...cols.value, [key]: !cols.value[key] }
}

// ── Computed column helpers ───────────────────────────────────────────
const showProjectCol = computed(() => cols.value.project && groupBy.value !== 'project')

const colCount = computed(() => {
  let n = 1 // task name always
  if (cols.value.status)   n++
  if (showProjectCol.value) n++
  if (cols.value.due_date) n++
  if (cols.value.priority) n++
  if (cols.value.id)       n++
  return n
})

// ── Constants ────────────────────────────────────────────────────────
const STATUS_FILTERS = [
  { value: 'open',      label: 'Open' },
  { value: 'all',       label: 'All'  },
  { value: 'completed', label: 'Done' },
]
const GROUP_OPTIONS = [
  { v: 'project',  label: 'Project'  },
  { v: 'status',   label: 'Status'   },
  { v: 'priority', label: 'Priority' },
  { v: 'due_date', label: 'Due date' },
]
const SORT_OPTIONS = [
  { v: 'due_date', label: 'Due date' },
  { v: 'priority', label: 'Priority' },
  { v: 'creation', label: 'Created'  },
  { v: 'modified', label: 'Updated'  },
]

// Field definitions for Customize panel
const FIELD_DEFS = [
  { key: 'status',   label: 'Status',   icon: markRaw(Layers),    note: ''       },
  { key: 'project',  label: 'Project',  icon: markRaw(AlignLeft), note: 'when not grouped' },
  { key: 'due_date', label: 'Due date', icon: markRaw(Calendar),  note: ''       },
  { key: 'priority', label: 'Priority', icon: markRaw(Flag),      note: ''       },
  { key: 'id',       label: 'Task ID',  icon: markRaw(Hash),      note: ''       },
]

// Skeleton widths
const SK = ['62%','78%','45%','68%','54%','82%','38%','71%']
const skW = (row, col) => SK[(row * 3 + col) % SK.length]

// ── User identity ─────────────────────────────────────────────────────
const me       = computed(() => window.frappe?.session?.user || '')
const userLabel = computed(() => {
  const local = me.value.split('@')[0]
  return local.replace(/[._-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
})
const avatarColor = computed(() => {
  const p = ['#5E6AD2','#26B5CE','#4CB782','#F2994A','#E57373','#9B59B6','#00BCD4','#FF9800']
  let h = 0; for (const c of me.value) h = (h << 5) - h + c.charCodeAt(0)
  return p[Math.abs(h) % p.length]
})

const workflows  = ref({})
const colorCache = ref({})

// ── Data fetch ────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const res = await getMyTasks({
      statusFilter: statusFilter.value,
      project:      projectFilter.value || null,
      groupBy:      groupBy.value,
      sortBy:       sortBy.value,
      sortOrder:    sortOrder.value,
    })
    tasks.value      = res.tasks   || []
    grouped.value    = res.grouped || {}
    counts.value     = res.counts  || { open: 0, completed: 0 }
    totalCount.value = res.total   || 0

    const seen = new Set()
    allProjects.value = []
    for (const t of tasks.value) {
      if (!seen.has(t.project)) {
        seen.add(t.project)
        allProjects.value.push({ name: t.project, project_name: t.project_name })
      }
    }

    for (const p of store.projects || []) {
      const c = p.project_color || 'var(--accent)'
      colorCache.value[p.project_name] = c
      colorCache.value[p.name]         = c
      let states = p.workflow_states
      if (typeof states === 'string') { try { states = JSON.parse(states) } catch { states = [] } }
      if (Array.isArray(states)) workflows.value[p.name] = states
    }
  } catch (e) {
    console.error('MyTasks load:', e)
  } finally {
    loading.value = false
  }
}

// Watch data filters → reload; watch prefs → save
watch([statusFilter, groupBy, sortBy, sortOrder, projectFilter], () => {
  allProjects.value = []
  load()
})

// TaskDetail edits go through the store's own board state, not this page's
// independently-fetched `tasks` array — reload once the panel closes so
// edits (status, priority, due date, assignee, ...) show up in the table.
watch(() => store.showTaskDetail, (open, wasOpen) => {
  if (!open && wasOpen) load()
})

watch([cols, density, groupBy, sortBy, sortOrder], savePrefs, { deep: true })

onMounted(async () => {
  loadPrefs()
  if (!store.projects?.length) await store.fetchProjects()
  await load()
})

// ── Actions ───────────────────────────────────────────────────────────
function toggleGroup(key) {
  const s = new Set(collapsed.value)
  s.has(key) ? s.delete(key) : s.add(key)
  collapsed.value = s
}

async function openTask(task) {
  if (store.currentProject?.name !== task.project) {
    store.fetchBoard(task.project).catch(console.error)
  }
  await store.openTaskDetail(task.name)
}

async function setStatus(task, state) {
  const prev = { status: task.status, status_color: task.status_color, status_category: task.status_category }
  task.status = state.name; task.status_color = state.color || 'var(--muted)'; task.status_category = state.category || 'unstarted'
  try { await updateTaskStatus(task.name, state.name); await load() }
  catch (e) { Object.assign(task, prev); console.error(e) }
}

async function setPriority(task, priority) {
  const prev = task.priority; task.priority = priority
  try { await updateTask(task.name, { priority }) }
  catch (e) { task.priority = prev; console.error(e) }
}

// ── Helpers ───────────────────────────────────────────────────────────
const TODAY    = new Date().toISOString().slice(0, 10)
const isOverdue = t => t.due_date && String(t.due_date) < TODAY && t.status_category !== 'completed'

function workflowFor(task)  { return workflows.value[task.project] || [] }
function projectColor(name) { return colorCache.value[name] || 'var(--accent)' }
function projectByName(name) { return store.projects.find(p => p.name === name || p.key === name) }

function typeColor(task) {
  const types = store.projects?.find(p => p.name === task.project)?.issue_types || []
  return types.find(t => t.name === task.task_type)?.color || 'var(--accent)'
}

function sectionStatusColor(name) {
  for (const wf of Object.values(workflows.value)) {
    const s = wf.find(st => st.name === name)
    if (s?.color) return s.color
  }
  return 'var(--muted)'
}
</script>

<style scoped>
.th {
  @apply px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider
         text-muted border-b border-border bg-overlay;
  border-right: 1px solid var(--separator);
}
.th:last-child { border-right: none; }

/* Resizable header cell + drag handle */
.th-resz { position: relative; }
.th-rh {
  position: absolute; top: 0; right: -3px;
  width: 7px; height: 100%;
  cursor: col-resize; z-index: 4; user-select: none;
}
.th-rh::after {
  content: ''; position: absolute; left: 3px; top: 50%;
  transform: translateY(-50%);
  width: 2px; height: 0; background: var(--accent); border-radius: 1px;
  transition: height .1s ease;
}
.th-rh:hover::after { height: 60%; }

:deep(tbody td) {
  @apply text-[13px];
  border-right: 1px solid var(--separator);
}
:deep(tbody td:last-child) { border-right: none; }

/* Row height driven by CSS variable (set by density) */
:deep(tbody tr) {
  height: var(--row-h, 40px);
}

/* Customize panel slide-in from right */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: transform 0.22s cubic-bezier(0.4, 0, 0.2, 1),
              opacity   0.18s ease;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
