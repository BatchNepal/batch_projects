<template>
  <section class="h-full">
  <div class="flex flex-col h-full">
        <!-- Loading: column skeletons mirror the REAL board chrome (KanbanColumn's
             dot+uppercase-label+pill-count header, TaskCard's rounded-[7px]
             layered-shadow card with title/description/type-badge/due-pill/avatar
             rows) — a generic bars-in-boxes skeleton reads as a different, lesser
             product for the half-second before real data lands. -->
    <div v-if="loading" class="board-area">
      <div class="board-cols">
        <div v-for="c in 4" :key="'sk' + c" class="w-[280px] shrink-0 px-1.5">
          <div class="flex items-center gap-2.5 px-1.5 pb-3 pt-1">
            <Skeleton class="size-2 rounded-full shrink-0" />
            <Skeleton class="h-2.5 rounded-full" :style="{ width: (48 + c * 12) + 'px' }" />
            <Skeleton class="h-4 w-6 rounded-full ml-auto" />
          </div>
          <div class="space-y-3">
            <div v-for="r in (c % 2 ? 3 : 2)" :key="r"
              class="rounded-[7px] border border-border bg-overlay py-4 px-3.5 space-y-2.5"
              style="box-shadow:var(--card-shadow)">
              <Skeleton class="h-3" :style="{ width: (55 + ((c + r) % 3) * 18) + '%' }" />
              <Skeleton class="h-2.5" :style="{ width: (30 + ((c * r) % 4) * 10) + '%' }" />
              <div class="flex items-center justify-between pt-1.5">
                <div class="flex items-center gap-1.5">
                  <Skeleton class="size-3 rounded" />
                  <Skeleton class="h-2 w-10 rounded-full" />
                </div>
                <div class="flex items-center gap-2">
                  <Skeleton class="h-4 w-12 rounded-full" />
                  <Skeleton class="size-5 rounded-full" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Each KanbanColumn already shows its own
         "No tasks" box when filtered/individually empty (correct, unchanged
         below) — but a brand-new project with zero tasks at all rendered as
         N of those side by side with no single "you're set up, now what"
         message anywhere. This is the one welcome banner for that specific
         case; it never appears once any task exists. -->
    <div v-else-if="!loadFailed && !allIssues.length && !searchQuery && !filterAssignee && !filterPriority && !filterType && !filterLabel"
      class="board-area flex items-center justify-center">
      <EmptyState :icon="LayoutGrid" title="This board is empty" description="Create your first task to get the board moving.">
        <template #action>
          <Button color="primary" size="sm" @click="openCreateForStatus(store.columns?.[0])">
            Create task
          </Button>
        </template>
      </EmptyState>
    </div>

    <!-- Board -->
    <div v-else class="board-area">
      <div class="board-cols">
        <KanbanColumn
          v-for="col in groupKeys" :key="col"
          :title="col"
          :issues="groupedBoard[col] || []"
          :mirror-chips="mirror.mirrorChips"
          :color="store.boardGroupBy === 'label'
            ? (store.currentProject?.labels?.find(l => l.label === col)?.color || null)
            : store.boardGroupBy === 'status'
              ? (store.workflowStateMap?.[col]?.color || null)
              : null"
          @move="handleMove"
          @click-issue="store.openTaskDetail"
          @add="(status) => openCreateForStatus(status)"
          @context-action="handleContextAction"
          @context-menu="({ issue, x, y }) => { ctxIssue = issue; ctxX = x; ctxY = y }"
          @open-erp-doc="openErpDoc"
        />
      </div>
    </div>
  </div>
  <!-- Context menu -->
  <TaskContextMenu
    :issue="ctxIssue"
    :x="ctxX" :y="ctxY"
    @close="ctxIssue = null"
  />
  <MoneyDrawer v-model:open="moneyDrawerOpen" :project="store.currentProject?.name"
    :doctype="moneyDrawerDoctype" :name="moneyDrawerName" />
 </section>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Skeleton, EmptyState, Button } from "@/ui";
import { LayoutGrid } from "lucide-vue-next";
import { useProjectStore } from "@/stores/project";
import { getTaskWord } from "@/constants/project-templates";
import { toast } from "vue-sonner";
import * as api from "@/utils/api.js";
import KanbanColumn from "@/components/KanbanColumn.vue";
import TaskContextMenu from "@/components/TaskContextMenu.vue";
import MoneyDrawer from "@/components/MoneyDrawer.vue";
import { useErpDocOpener } from "@/composables/useErpDocOpener.js";
import { useMirrorColumnsStore } from "@/stores/mirrorColumns.js";

const route = useRoute();
const router = useRouter();
const store = useProjectStore();
const loading = ref(true);
const loadFailed = ref(false); // see loadBoard's catch block
const { moneyDrawerOpen, moneyDrawerDoctype, moneyDrawerName, openErpDoc } = useErpDocOpener();
const searchQuery    = computed({ get: () => store.boardViewState.search,         set: v => store.boardViewState.search = v })
const filterAssignee = computed({ get: () => store.boardViewState.filterAssignee, set: v => store.boardViewState.filterAssignee = v })
const ctxIssue = ref(null)
const ctxX     = ref(0)
const ctxY     = ref(0)
const filterPriority = computed({ get: () => store.boardViewState.filterPriority, set: v => store.boardViewState.filterPriority = v })
const filterType     = computed({ get: () => store.boardViewState.filterType,     set: v => store.boardViewState.filterType = v })
const filterLabel    = computed({ get: () => store.boardViewState.filterLabel,    set: v => store.boardViewState.filterLabel = v })


const projectKey = computed(() => route.params.key);

const allIssues = computed(() => Object.values(store.board).flat());

// mirror-field chips on cards (own view="board" slice of the
// mechanism ListView.vue already persists per user+project+view). Shared
// Pinia store (not a local composable instance) so ProjectHeader's
// <ErpMirrorFieldsButton> reads/writes this same state — see mirrorColumns.js.
const mirror = useMirrorColumnsStore()
watch(allIssues, (issues) => { if (issues.length) mirror.loadValues(issues) })



async function handleMove({ issue, newStatus, newIndex }) {
  if (store.boardGroupBy === "status") {
    const sameColumn = issue.status === newStatus
    if (sameColumn && store.boardSortBy !== 'board_order') return

    const oldStatus = issue.status  // capture before moveIssue mutates it
    await store.moveIssue(issue, newStatus, newIndex)

  } else if (store.boardGroupBy === "priority") {
    const newPriority = newStatus;
    if (issue.priority !== newPriority) {
      await store.updateTaskField(issue.name, "priority", newPriority);
      toast.success("Priority updated", { description: `${issue.task_key} → ${newPriority}` });
    }

  } else if (store.boardGroupBy === "type") {
    const newType = newStatus;
    if (issue.task_type !== newType) {
      await store.updateTaskField(issue.name, "task_type", newType);
      toast.success("Type updated", { description: `${issue.task_key} → ${newType}` });
    }

  } else if (store.boardGroupBy === "label") {
    const newLabel = newStatus;
    if (newLabel === "No Label") {
      if (issue.labels?.length) {
        await store.updateTaskField(issue.name, "labels", []);
        toast.success("Label cleared", { description: issue.task_key });
      }
    } else {
      const current = Array.isArray(issue.labels) ? issue.labels : [];
      if (!current.includes(newLabel)) {
        await store.updateTaskField(issue.name, "labels", [...current, newLabel]);
        toast.success("Label added", { description: `${issue.task_key} → ${newLabel}` });
      }
    }

  } else if (store.boardGroupBy === "assignee") {
    const newAssignee = newStatus
    const currentAssignee = issue.assignees?.[0]?.full_name || "Unassigned"
    if (newAssignee === currentAssignee) return
    if (newAssignee === "Unassigned") {
      await store.updateTaskField(issue.name, "assignees", [])
      toast.success("Assignee removed", { description: issue.task_key })
    } else {
      const member = store.projectMembers?.find(m => m.full_name === newAssignee)
      if (member) {
        await store.updateTaskField(issue.name, "assignees", [{ user: member.user, full_name: member.full_name }])
        toast.success("Assignee updated", { description: `${issue.task_key} → ${newAssignee}` })
      }
    }
  }
}


const filteredIssues = computed(() => {
  let issues = allIssues.value;

  // Sprint filter — only when active sprint exists and filter is set to active_sprint
  if (store.boardSprintFilter === 'active_sprint') {
    const activeSprint = store.sprints.find(s => s.status === 'Active')
    if (activeSprint) {
      issues = issues.filter(i => i.sprint === activeSprint.name)
    }
  }

  const q = searchQuery.value.toLowerCase();
  if (q) issues = issues.filter(i =>
    i.title?.toLowerCase().includes(q) ||
    i.task_key?.toLowerCase().includes(q) ||
    (i.assignees || []).some(a => a.full_name?.toLowerCase().includes(q))
  );
  if (filterAssignee.value) issues = issues.filter(i =>
    (i.assignees || []).some(a => a.full_name === filterAssignee.value)
  );
  if (filterPriority.value) issues = issues.filter(i => i.priority === filterPriority.value);
  if (filterType.value) issues = issues.filter(i => i.task_type === filterType.value);
  if (filterLabel.value) issues = issues.filter(i => (Array.isArray(i.labels) ? i.labels : []).includes(filterLabel.value));

  // Client-side sort (non-manual)
  const s = store.boardSortBy
  if (s && s !== 'board_order') {
    issues = [...issues].sort((a, b) => {
      if (s === 'priority') {
        const ORDER = { Highest: 0, High: 1, Medium: 2, Low: 3, Lowest: 4 }
        return (ORDER[a.priority] ?? 5) - (ORDER[b.priority] ?? 5)
      }
      if (s === 'due_date') {
        if (!a.due_date && !b.due_date) return 0
        if (!a.due_date) return 1; if (!b.due_date) return -1
        return new Date(a.due_date) - new Date(b.due_date)
      }
      if (s === 'title')    return (a.title || '').localeCompare(b.title || '')
      if (s === 'creation') return new Date(b.creation) - new Date(a.creation)
      return 0
    })
  }

  return issues;
});

const groupKeys = computed(() => {
  const g = store.boardGroupBy;
  if (g === "status") return store.columns;
  if (g === "priority") return ["Highest", "High", "Medium", "Low", "Lowest"];
  if (g === "assignee") {
    const names = [...new Set(filteredIssues.value.map(i =>
      i.assignees?.[0]?.full_name || "Unassigned"
    ))].sort();
    return names.includes("Unassigned") ? names : [...names, "Unassigned"];
  }
  if (g === "type")  return store.taskTypes?.map(t => t.name) || ["Task", "Bug", "Story"];
  if (g === "label") {
    const projectLabels = (store.currentProject?.labels || []).map(l => l.label);
    const usedLabels = [...new Set(filteredIssues.value.flatMap(i =>
      Array.isArray(i.labels) ? i.labels : []
    ))];
    const all = [...new Set([...projectLabels, ...usedLabels])].filter(Boolean);
    return all.length ? [...all, "No Label"] : ["No Label"];
  }
  return store.columns;
});

const groupedBoard = computed(() => {
  const g = store.boardGroupBy;
  const result = {};
  for (const key of groupKeys.value) result[key] = [];

  for (const issue of filteredIssues.value) {
    if (!issue) continue;
    let bucket;
    if (g === "status") bucket = issue.status;
    else if (g === "priority") bucket = issue.priority || "Medium";
    else if (g === "assignee") bucket = issue.assignees?.[0]?.full_name || "Unassigned";
    else if (g === "type")  bucket = issue.task_type || store.taskTypes?.[0]?.name || "Task";
    else if (g === "label") {
      // Issues with multiple labels appear in each label's column
      const issueLabels = Array.isArray(issue.labels) ? issue.labels : [];
      if (!issueLabels.length) { if (result["No Label"] !== undefined) result["No Label"].push(issue); continue; }
      let placed = false;
      for (const lbl of issueLabels) {
        if (result[lbl] !== undefined) { result[lbl].push(issue); placed = true; }
      }
      if (!placed && result["No Label"] !== undefined) result["No Label"].push(issue);
      continue;
    }
    else bucket = issue.status;

    if (result[bucket] !== undefined) result[bucket].push(issue);
  }
  return result;
});


function openCreateForStatus(columnTitle) {
  const g = store.boardGroupBy
  const defaults = {}
  if (g === 'status')        defaults.status     = columnTitle
  else if (g === 'priority') defaults.priority   = columnTitle
  else if (g === 'type')     defaults.task_type = columnTitle
  else if (g === 'label')    defaults.label      = columnTitle === 'No Label' ? null : columnTitle
  else if (g === 'assignee') defaults.assignee   = columnTitle === 'Unassigned' ? null : columnTitle
  if (!defaults.status) defaults.status = store.workflowStates?.[0]?.name || ''
  store.createTaskDefaults = defaults
  store.showCreateTask = true
}

async function handleContextAction({ action, issue }) {
  if (action === 'delete') {
    if (!confirm(`Delete "${issue.title}"?`)) return
    try {
      await api.deleteTask(issue.name)
      await store.refreshBoard()
      toast.success(`${getTaskWord(store.currentProject?.template_used)} deleted`)
    } catch (e) { toast.error('Failed to delete') }
  } else if (action === 'assign') {
    const sessionUser = window.frappe?.session?.user
    const me = store.projectMembers?.find(m => m.user === sessionUser)
    if (me) {
      await store.updateTaskField(issue.name, 'assignees', [{ user: me.user, full_name: me.full_name }])
      toast.success('Assigned to you', { description: issue.task_key })
    }
  } else if (action === 'change-status') {
    store.openTaskDetail(issue.name)
  }
}

// ── View state persistence (URL params + localStorage) ────────────────────
// Priority: URL params > localStorage > store defaults
// On any state change → sync URL + localStorage

const LS_KEY = computed(() => `bp_board_prefs_${projectKey.value}`)

const STATE_KEYS = [
  { store: () => store.boardGroupBy,              set: v => { store.boardGroupBy = v },              param: 'group',    ls: 'group'    },
  { store: () => store.boardSortBy,               set: v => { store.boardSortBy = v },               param: 'sort',     ls: 'sort'     },
  { store: () => store.boardViewState.filterAssignee, set: v => { store.boardViewState.filterAssignee = v }, param: 'assignee', ls: 'assignee' },
  { store: () => store.boardViewState.filterPriority, set: v => { store.boardViewState.filterPriority = v }, param: 'priority', ls: 'priority' },
  { store: () => store.boardViewState.filterType,     set: v => { store.boardViewState.filterType = v },     param: 'type',     ls: 'type'     },
  { store: () => store.boardViewState.filterLabel,    set: v => { store.boardViewState.filterLabel = v },    param: 'label',    ls: 'label'    },
  { store: () => store.showChildIssues,           set: v => { store.showChildIssues = v === 'true' || v === true }, param: 'subtasks', ls: 'subtasks' },
  { store: () => store.boardSprintFilter,         set: v => { store.boardSprintFilter = v },                        param: 'sprint',   ls: 'sprint'   },
]

function readPersistedState() {
  const q = route.query
  const hasUrlParams = STATE_KEYS.some(k => q[k.param] !== undefined)

  if (hasUrlParams) {
    // URL is source of truth
    STATE_KEYS.forEach(k => {
      if (q[k.param] !== undefined) k.set(q[k.param])
    })
  } else {
    // Fall back to localStorage
    try {
      const saved = JSON.parse(localStorage.getItem(LS_KEY.value) || '{}')
      STATE_KEYS.forEach(k => {
        if (saved[k.ls] !== undefined) k.set(saved[k.ls])
      })
    } catch {}
  }
}

function persistState() {
  const query = {}
  const ls = {}
  STATE_KEYS.forEach(k => {
    const v = k.store()
    // Only include non-default values in URL to keep it clean
    const isDefault =
      (k.param === 'group'    && v === 'status') ||
      (k.param === 'sort'     && v === 'board_order') ||
      (k.param === 'subtasks' && !v)
    if (v && !isDefault) query[k.param] = String(v)
    if (v !== null && v !== undefined && v !== '' && !isDefault) ls[k.ls] = v
  })

  // Update URL without pushing to history
  router.replace({ query })

  // Save to localStorage
  try {
    if (Object.keys(ls).length) localStorage.setItem(LS_KEY.value, JSON.stringify(ls))
    else localStorage.removeItem(LS_KEY.value)
  } catch {}
}

// Watch all relevant state and persist on change
watch(
  () => [
    store.boardGroupBy,
    store.boardSortBy,
    store.showChildIssues,
    store.boardSprintFilter,
    store.boardViewState.filterAssignee,
    store.boardViewState.filterPriority,
    store.boardViewState.filterType,
    store.boardViewState.filterLabel,
  ],
  persistState,
  { deep: true }
)

async function loadBoard() {
  loading.value = true;
  loadFailed.value = false;
  try {
    if (!store.projects.length) await store.fetchProjects();
    const proj = store.projects.find(p => p.key === projectKey.value);
    if (proj) {
      readPersistedState() // apply saved state before fetching
      await store.fetchBoard(proj.name);
      await mirror.loadSchema()
      await mirror.loadPrefs()
      await mirror.loadValues(allIssues.value)
      // Deep-link from email/notification: ?task=KEY opens the task panel
      const taskParam = route.query.task
      if (taskParam) store.openTaskDetail(taskParam)
    }
  } catch (e) {
    // fetchBoard failing (network/session drop)
    // used to leave store.board empty with no signal — the "board is empty,
    // create your first task" welcome banner would then
    // show for a project that actually has tasks, just failed to load them.
    // Wrong guidance is worse than no guidance; loadFailed suppresses it.
    loadFailed.value = true;
    toast.error('Failed to load board', { description: String(e?.message || e) });
  } finally {
    loading.value = false;
  }
}

onMounted(loadBoard);
watch(projectKey, () => {
  // Reset filters when switching projects
  store.boardViewState.filterAssignee = null
  store.boardViewState.filterPriority = null
  store.boardViewState.filterType     = null
  store.boardViewState.filterLabel    = null
  store.boardViewState.search         = ''
  store.boardSprintFilter             = 'all'
  loadBoard()
})
</script>

<style scoped>
.board-area {
  flex: 1;
  overflow-x: auto;
  overflow-y: auto;
  padding: 16px 20px;
  background: var(--surface);
  min-height: 0;
  /* Hide the scrollbars but keep scrolling (wheel/trackpad/drag) */
  scrollbar-width: none;        /* Firefox */
  -ms-overflow-style: none;     /* old Edge/IE */
}
.board-area::-webkit-scrollbar { /* Chrome/Safari/Edge */
  width: 0;
  height: 0;
  display: none;
}
.board-cols {
  display: flex;
  gap: 16px;
  min-width: max-content;
  align-items: stretch; /* all columns match tallest */
}

</style>