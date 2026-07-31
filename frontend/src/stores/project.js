import { defineStore } from "pinia";
import { ref, computed } from "vue";
import * as api from "@/utils/api";
import { onRealtimeEvent } from "@/utils/realtime";
import { toast } from "vue-sonner";

export const useProjectStore = defineStore("project", () => {
  // ─── State ────────────────────────────────────────────────────────────────

  const projects = ref([]);
  const currentProject = ref(null); // full project object from get_project
  const boardData = ref(null); // board-specific data (columns, board map)
  // Broadcast of the latest single-field task edit — views that keep their
  // own task list (Gantt's get_gantt payload) watch this to stay in sync
  // with edits made in the TaskDetail drawer without a refetch.
  const taskPatch = ref(null);
  const loading = ref(false);
  const selectedTask = ref(null);
  // Set when a status change is blocked by unfinished dependencies, awaiting confirm.
  // { kind:'move'|'field', name, newStatus|value, newIndex?, field?, blockers:[], statusLabel }
  const pendingBlock = ref(null);
  const showTaskDetail = ref(false);
  const showNotifDrawer = ref(false);
  const showCreateTask = ref(false);
  const createTaskDefaults = ref(null);
  const projectMembers = ref([]);
  // the caller's effective role + resolved capability set for
  // currentProject, fetched fresh per project switch (get_board's payload
  // IS cached per-project with no user dimension, so a per-user role can't
  // live there — see api.getMyCapabilities). Covers the workspace-Viewer
  // fallback case too (a non-member on a workspace-visibility project has a
  // real role, just not an entry in `members` above).
  const myRole = ref(null);
  const myCapabilities = ref({});
  const sprints = ref([]);
  const teams = ref([]);
  const currentTeam = ref(null);
  const sidebarCollapsed = ref(false);

  // Backlog view state — shared so TaskDetail edits reflect in Backlog rows immediately
  const backlogIssues = ref([]);
  // Increments on every actual issue creation — Backlog watches this, not showCreateTask
  const issueCreatedCount = ref(0);

  // Board view state
  const boardGroupBy = ref("status");
  const boardSortBy = ref("board_order"); // board_order = manual drag, creation, priority, due_date, title
  const showChildIssues = ref(false);
  const boardSprintFilter = ref("all"); // 'all' | 'active_sprint'

  // Shared view state — consumed by ProjectHeader toolbar
  const boardViewState = ref({
    search: "",
    filterAssignee: null,
    filterPriority: null,
    filterType: null,
    filterLabel: null,
  });
  const boardFilters = ref({
    status: [],
    assignee: [],
    priority: [],
    labels: [],
    task_type: [],
    search: "",
  });

  // Saved views — per-project, keyed by projectKey (migrates to BP View doctype in Sprint 6)
  // Schema: { id, name, project_key, view_type, group_by, sort_by, sprint_filter, filters }
  const savedViews = ref([]);
  const activeViewId = ref(null);
  const svTick = ref(0); // increments on any save/delete — lets Sidebar react
  let _defaultAppliedFor = null; // project whose default view was auto-applied (once per project)

  // Notification badge count — written by Sidebar on mount, updated by Notifications.vue
  const notificationCount = ref(0);

  // Reactive current-user info (populated by bootstrapSession). Components must
  // read this rather than window.frappe.session — that plain object is mutated
  // asynchronously and Vue can't track it, so the UI would be stuck on "User".
  const currentUser = ref({
    user: window?.frappe?.session?.user || "",
    fullname: window?.frappe?.session?.user_fullname || "",
  });

  function _svKey(projectKey) { return `bp_sv_${projectKey}` }
  async function loadSavedViews(projectKey) {
    const projectName = currentProject.value?.name
    if (projectName) {
      try {
        savedViews.value = await api.getViews(projectName)
        return
      } catch { /* fall through to localStorage */ }
    }
    if (!projectKey) return
    try { savedViews.value = JSON.parse(localStorage.getItem(_svKey(projectKey)) || '[]') }
    catch { savedViews.value = [] }
  }
  function _persistViews(projectKey) {
    try { localStorage.setItem(_svKey(projectKey), JSON.stringify(savedViews.value)) }
    catch {}
  }

  // Favourites
  const favourites = ref(
    JSON.parse(localStorage.getItem("bp_favourites") || "[]"),
  );

  // Manual sidebar ordering — a personal preference (per browser). Holds an
  // ordered list of project names; projects not listed fall to the end in their
  // default order. Drag-to-reorder in the sidebar writes this.
  const projectOrder = ref(
    JSON.parse(localStorage.getItem("bp_project_order") || "[]"),
  );

  /** Projects in the user's manual order, with any unordered ones appended in
   *  their original (creation-desc) order. */
  const sortedProjects = computed(() => {
    const order = projectOrder.value;
    if (!order.length) return projects.value;
    const pos = new Map(order.map((n, i) => [n, i]));
    return [...projects.value].sort((a, b) => {
      const ia = pos.has(a.name) ? pos.get(a.name) : Infinity;
      const ib = pos.has(b.name) ? pos.get(b.name) : Infinity;
      return ia - ib; // Array.sort is stable → unordered keep their order
    });
  });

  function setProjectOrder(names) {
    projectOrder.value = [...names];
    localStorage.setItem("bp_project_order", JSON.stringify(projectOrder.value));
  }

  /** The route a project should open on, honouring its configured default_view.
   *  Accepts a project object or a key string. Falls back to summary, and never
   *  returns a view the project doesn't expose. Single source of truth so every
   *  nav entry point (sidebar, lists, portfolio) enforces the default view. */
  function projectLanding(p) {
    const proj = typeof p === "string" ? projects.value.find((x) => x.key === p) : p;
    const key = typeof p === "string" ? p : p?.key;
    let view = proj?.default_view || "summary";
    const enabled = Array.isArray(proj?.enabled_views) ? proj.enabled_views : [];
    if (view !== "summary" && view !== "files" && enabled.length && !enabled.includes(view)) {
      view = "summary";
    }
    return `/workspace/${key}/${view}`;
  }

  // ─── Getters ──────────────────────────────────────────────────────────────

  // Board
  const columns = computed(() => boardData.value?.columns || []);
  const board = computed(() => boardData.value?.board || {});
  const epics = computed(() => boardData.value?.epics || {});

  // Project config — sourced from currentProject (full object)
  const workflowStates = computed(
    () => currentProject.value?.workflow_states || [],
  );
  const taskTypes = computed(() => currentProject.value?.issue_types || []);
  const customFieldsSchema = computed(
    () => currentProject.value?.custom_fields || [],
  );
  const projectLabels = computed(() => currentProject.value?.labels || []);

  // Maps for O(1) lookup
  const workflowStateMap = computed(() => {
    const map = {};
    for (const s of workflowStates.value) map[s.name] = s;
    return map;
  });

  const taskTypeMap = computed(() => {
    const map = {};
    for (const t of taskTypes.value) map[t.name] = t;
    return map;
  });

  const labelMap = computed(() => {
    const map = {};
    for (const l of projectLabels.value) map[l.id] = l;
    return map;
  });

  // Active sprints only (for CreateTask picker)
  const activeSprints = computed(() =>
    sprints.value.filter((s) => s.status === "Active"),
  );

  // Currently open issue
  const activeIssue = computed(() =>
    showTaskDetail.value ? selectedTask.value : null,
  );

  // ─── Project loading ──────────────────────────────────────────────────────

  
  async function toggleFavorite(projectName) {
    const p = projects.value.find(p => p.name === projectName)
    if (!p) return
    const newVal = p.is_favorite ? 0 : 1
    p.is_favorite = newVal
    
    // Attempt backend update if it exists
    if (window.frappe) {
       frappe.call({
         method: "frappe.client.set_value",
         args: {
           doctype: "Project",
           name: projectName,
           fieldname: "is_favorite",
           value: newVal
         }
       }).catch(() => {})
    }
  }

  async function fetchProjects() {
    loading.value = true;
    try {
      projects.value = await api.getProjects();
    } finally {
      loading.value = false;
    }
  }

  async function fetchTeams() {
    try {
      teams.value = await api.getTeams();
    } catch (e) {
      console.error("fetchTeams:", e);
    }
  }

  /**
   * Load everything needed for a project workspace:
   * full project config, board data, members, sprints.
   */
  async function fetchBoard(projectName) {
    loading.value = true;
    try {
      // Single parallel pair: projects list (if needed) + board data
      // get_board now bundles: project config + workflow states + task types
      //                        + members + board issues + epics
      // Eliminates separate get_project and get_members calls.
      if (!projects.value.length) await fetchProjects();

      const board = await api.getBoard(projectName, showChildIssues.value);

      // Extract project config from board response
      currentProject.value = {
        ...board.project,
        workflow_states: board.workflow_states,
        issue_types: board.issue_types,
        custom_fields: board.custom_fields,
        project_custom_fields: board.project_custom_fields,
        labels: board.labels,
        members: board.project_members || [],
      };
      boardData.value = board;

      // Members bundled in board response — no extra API call needed
      projectMembers.value = board.members || [];

      // role + capabilities, loaded in parallel (not blocking
      // render); never cached, unlike the board payload above.
      api
        .getMyCapabilities(projectName)
        .then((res) => {
          myRole.value = res.role || null;
          myCapabilities.value = res.capabilities || {};
        })
        .catch(() => {
          myRole.value = null;
          myCapabilities.value = {};
        });

      // Sprints loaded in parallel (not blocking render)
      api
        .getSprints(projectName)
        .then((list) => {
          sprints.value = list;
        })
        .catch(() => {});

      // Saved views loaded in parallel; apply the default view once per project
      const projectKey = board.project?.key;
      api
        .getViews(projectName)
        .then((views) => {
          savedViews.value = views;
          const def = views.find((v) => v.is_default);
          if (def && _defaultAppliedFor !== projectName) {
            _defaultAppliedFor = projectName;
            applyView(def);
          }
        })
        .catch(() => {
          if (projectKey) loadSavedViews(projectKey);
        });

      // Session bootstrap (dev only — skipped in prod when Jinja sets user)
      await bootstrapSession();
    } finally {
      loading.value = false;
    }
  }

  /**
   * Refresh only the board data (after issue create/update).
   * Faster than full fetchBoard — doesn't reload project config.
   */
  async function refreshBoard() {
    if (!currentProject.value?.name) return;
    const board = await api.getBoard(
      currentProject.value.name,
      showChildIssues.value,
    );
    boardData.value = board;
  }

  async function fetchMembers(projectName) {
    try {
      const res = await api.getMembers(
        projectName || currentProject.value?.name,
      );
      projectMembers.value = Array.isArray(res)
        ? res
        : res?.members || res?.user_list || [];
    } catch (e) {
      console.error("Failed to fetch members:", e);
    }
  }

  async function fetchSprints(projectName) {
    try {
      sprints.value = await api.getSprints(
        projectName || currentProject.value?.name,
      );
    } catch (e) {
      console.error("Failed to fetch sprints:", e);
    }
  }

  // ─── Issue actions ────────────────────────────────────────────────────────

  async function moveIssue(issue, newStatus, newIndex, force = false) {
    if (!boardData.value?.board) return;

    const oldStatus = issue.status;

    // Optimistic update
    const oldCol = boardData.value.board[oldStatus];
    if (oldCol) {
      const idx = oldCol.findIndex((i) => i.name === issue.name);
      if (idx > -1) oldCol.splice(idx, 1);
    }

    if (!boardData.value.board[newStatus]) {
      boardData.value.board[newStatus] = [];
    }

    issue.status = newStatus;
    const col = boardData.value.board[newStatus];
    const clampedIndex = Math.min(newIndex, col.length);
    col.splice(clampedIndex, 0, issue);

    // Neighbours at the drop position — the backend places the task between
    // them with a fractional rank (single-row write, no column renumber).
    const prev = col[clampedIndex - 1]?.name || null;
    const next = col[clampedIndex + 1]?.name || null;

    try {
      const res = await api.moveTask(issue.name, newStatus, prev, next, force);
      if (res?.blocked) {
        await refreshBoard(); // revert the optimistic move
        pendingBlock.value = {
          kind: "move", name: issue.name, newStatus, newIndex: clampedIndex,
          blockers: res.blockers || [], statusLabel: res.status,
        };
        return;
      }
      // Reconcile optimistic position with the server-assigned fractional rank
      if (res?.board_rank) issue.board_rank = res.board_rank;
    } catch (e) {
      console.error("Failed to move issue:", e);
      toast.error(e.message || "Failed to move task");
      await refreshBoard();
    }
  }

  /**
   * Optimistically update a single field on an issue across all views.
   */
  async function updateTaskField(issueName, field, value, force = false) {
    // Update in board
    for (const col of Object.values(boardData.value?.board || {})) {
      const issue = col.find((i) => i.name === issueName);
      if (issue) {
        issue[field] = value;
        break;
      }
    }
    // Update in detail panel
    if (selectedTask.value?.name === issueName) {
      selectedTask.value[field] = value;
    }
    // Update in backlog view
    const bl = backlogIssues.value.find((i) => i.name === issueName);
    if (bl) bl[field] = value;

    taskPatch.value = { name: issueName, field, value, ts: Date.now() };

    try {
      const res = await api.updateTask(issueName, { [field]: value }, force);
      if (res?.blocked) {
        // Revert optimistic change and stage the confirmation.
        await refreshBoard();
        if (selectedTask.value?.name === issueName) await refreshTaskDetail();
        pendingBlock.value = {
          kind: "field", name: issueName, field, value,
          blockers: res.blockers || [], statusLabel: res.status,
        };
      }
      return res;
    } catch (e) {
      console.error("Failed to update field:", e);
      await refreshBoard();
      if (selectedTask.value?.name === issueName) await refreshTaskDetail();
      throw e;
    }
  }

  function _findBoardIssue(name) {
    for (const col of Object.values(boardData.value?.board || {})) {
      const f = col.find((i) => i.name === name);
      if (f) return f;
    }
    return null;
  }

  // Re-run the blocked status change, this time forcing it through.
  async function confirmBlockedStatus() {
    const p = pendingBlock.value;
    pendingBlock.value = null;
    if (!p) return;
    try {
      if (p.kind === "move") {
        const issue = _findBoardIssue(p.name);
        if (issue) await moveIssue(issue, p.newStatus, p.newIndex, true);
        else { await api.updateTaskStatus(p.name, p.newStatus, p.newIndex, true); await refreshBoard(); }
      } else {
        await updateTaskField(p.name, p.field, p.value, true);
      }
    } catch (e) {
      console.error("Failed to confirm status change:", e);
      toast.error(e.message || "Failed to update status");
      await refreshBoard();
    }
  }

  function cancelBlockedStatus() {
    pendingBlock.value = null;
  }

  /**
   * Update multiple fields at once (used by TaskDetail save).
   */
  async function updateIssueFields(issueName, fields) {
    // Optimistic update on selectedTask
    if (selectedTask.value?.name === issueName) {
      Object.assign(selectedTask.value, fields);
    }
    // Optimistic update in backlog view
    const bl = backlogIssues.value.find((i) => i.name === issueName);
    if (bl) Object.assign(bl, fields);

    try {
      const updated = await api.updateTask(issueName, fields);
      // Sync back the server response (has computed fields like task_key)
      if (selectedTask.value?.name === issueName) {
        Object.assign(selectedTask.value, updated);
      }
      if (bl) Object.assign(bl, updated);
      return updated;
    } catch (e) {
      console.error("Failed to update issue:", e);
      // Revert optimistic update
      if (selectedTask.value?.name === issueName) {
        selectedTask.value = await api.getTask(issueName);
      }
      throw e;
    }
  }

  async function createNewIssue(params) {
    const issue = await api.createTask(params);
    await refreshBoard();
    issueCreatedCount.value += 1; // signals Backlog.vue to reload
    return issue;
  }

  function setBacklogIssues(issues) {
    backlogIssues.value = issues;
  }

  async function deleteCurrentIssue(issueName) {
    await api.deleteTask(issueName);
    closeTaskDetail();
    await refreshBoard();
  }

  // ─── Realtime ─────────────────────────────────────────────────────────────

  // ── Session bootstrap ─────────────────────────────────────────────────────
  // In dev (Vite), batch-projects.html Jinja is never rendered so
  // window.frappe.session.user and window.csrf_token are empty.
  // Fetch them from Frappe's API once on startup.
  async function bootstrapSession() {
    // In production, batch-projects.html Jinja sets window.frappe.session.user.
    // csrf_token is available in every API response cookie — no extra call needed.
    // In dev (Vite), neither is set — call get_session_info once.
    if (window.frappe?.session?.user && window.frappe.session.user !== "Guest") {
      // Prod path: workspace.html already injected the session — mirror it
      // into the reactive ref so the sidebar shows the real name.
      currentUser.value = {
        user: window.frappe.session.user,
        fullname: window.frappe.session.user_fullname || currentUser.value.fullname || "",
      };
      // Fullname isn't in the Jinja boot — fetch it once in the background.
      if (!currentUser.value.fullname) {
        try {
          const r = await fetch("/api/method/batch_projects.api.board.get_session_info", { credentials: "include" })
          const d = (await r.json())?.message || {}
          if (d.user_fullname) currentUser.value = { user: d.user || currentUser.value.user, fullname: d.user_fullname }
        } catch {}
      }
      return;
    }
    try {
      window.frappe = window.frappe || {};

      // Single call to our whitelisted endpoint — returns user + csrf_token together
      const res = await fetch(
        "/api/method/batch_projects.api.board.get_session_info",
        {
          credentials: "include",
        },
      );
      const data = await res.json();
      const info = data.message || {};
      window.frappe.session = { user: info.user || "", user_fullname: info.user_fullname || "" };
      currentUser.value = { user: info.user || "", fullname: info.user_fullname || "" };
      window.frappe.csrf_token = info.csrf_token || "";
      window.csrf_token = info.csrf_token || "";
      window.frappe.sitename = info.sitename || "";

      console.log(
        "[BP] Session bootstrapped — user:",
        info.user,
        "site:",
        info.sitename,
        "csrf:",
        info.csrf_token ? "present" : "MISSING",
      );
    } catch (e) {
      console.warn("[BP] Session bootstrap failed:", e);
    }
  }

  // ── Realtime (single always-on gateway SSE connection — see utils/realtime.js) ──
  // Subscribed once, for the store's whole lifetime (App.vue owns
  // connect/disconnect at mount/unmount). _routeRealtimeEvent itself already
  // filters by currentProject, so one connection covers every project the
  // user navigates to without reopening per switch.
  //
  // Every event is coalesced (COALESCE_WINDOW_MS), ordering-guarded, and
  // drag-protected before it ever reaches _applyRealtimeEvent — see that
  // trio below. This whole pipeline patches the normalized store in place;
  // nothing here does a full board refetch except task.created, which needs
  // a single-task GET (the create payload doesn't carry the full task shape).
  onRealtimeEvent((payload) => _queueRealtimeEvent(payload));

  const COALESCE_WINDOW_MS = 80;
  let _eventQueue = [];
  let _flushTimer = null;

  function _queueRealtimeEvent(payload) {
    _eventQueue.push(payload);
    if (_flushTimer) return;
    _flushTimer = setTimeout(() => {
      const batch = _eventQueue;
      _eventQueue = [];
      _flushTimer = null;
      // One flush per window, not one Vue reactivity pass per event — a
      // bulk update (20 tasks moved at once) settles as a single re-render
      // instead of 20 back-to-back TransitionGroup flickers.
      for (const p of batch) _routeRealtimeEvent(p);
    }, COALESCE_WINDOW_MS);
  }

  // Cards currently under a local, in-flight native HTML5 drag can't be
  // mutated by a remote event without breaking the drag gesture (the
  // dragged DOM node moving out from under the cursor mid-gesture kills
  // native drag/drop). Queued here, flushed by flushDeferredRealtimeEvent
  // once the drag ends (KanbanColumn's onDrop on a successful drop; the
  // window "dragend" listener below as the safety net for a drag cancelled
  // outside any valid drop zone, which onDrop never sees).
  const _deferredRealtimeEvents = new Map(); // task name -> payload

  function _routeRealtimeEvent(payload) {
    const taskName = payload.task;
    if (taskName && window.__dragIssue?.issue?.name === taskName) {
      _deferredRealtimeEvents.set(taskName, payload);
      return;
    }
    _applyRealtimeEvent(payload);
  }

  function flushDeferredRealtimeEvent(taskName) {
    const payload = _deferredRealtimeEvents.get(taskName);
    if (!payload) return;
    _deferredRealtimeEvents.delete(taskName);
    _applyRealtimeEvent(payload);
  }

  if (typeof window !== "undefined") {
    // Capture phase: TaskCard's own @dragend.stop stops this from bubbling,
    // so a bubble-phase listener here would never see it. Capture fires on
    // the way DOWN to the target, before that stopPropagation takes effect.
    window.addEventListener(
      "dragend",
      () => {
        const dragged = window.__dragIssue;
        if (dragged?.issue?.name) {
          window.__dragIssue = null;
          flushDeferredRealtimeEvent(dragged.issue.name);
        }
      },
      true,
    );
  }

  // Ordering guard: every events.py payload carries a "timestamp"
  // (frappe.utils.now(), fixed-width and string-sortable). A single SSE
  // connection reads its Redis Stream in order, so out-of-order delivery is
  // rare, but a reconnect replay could still redeliver a stale event — this
  // stops it from regressing a task to an older state after a newer event
  // already landed.
  const _lastAppliedTs = new Map(); // task name -> last-applied event timestamp

  function _applyRealtimeEvent(payload) {
    const {
      event,
      project,
      task: issueName,
      parent_task: parentIssue,
      changes,
      title,
      timestamp,
    } = payload;

    // Ignore events for other projects
    if (project !== currentProject.value?.name) return;

    if (issueName && timestamp) {
      const last = _lastAppliedTs.get(issueName);
      if (last && timestamp < last) return;
      _lastAppliedTs.set(issueName, timestamp);
    }

    // If this is a subtask update, patch the parent's sub_tasks array in boardData
    if (event === "task.updated" && parentIssue && changes?.length) {
      const allBoardIssues = Object.values(boardData.value?.board || {}).flat();
      const parent = allBoardIssues.find((i) => i.name === parentIssue);
      if (parent?.sub_tasks) {
        const st = parent.sub_tasks.find((s) => s.name === issueName);
        if (st) {
          for (const { field, to } of changes) {
            if (field !== "description") st[field] = to;
          }
        }
      }
      // Also update in open TaskDetail subtasks list
      if (
        selectedTask.value?.name === parentIssue &&
        selectedTask.value.subtasks
      ) {
        const st = selectedTask.value.subtasks.find(
          (s) => s.name === issueName,
        );
        if (st) {
          for (const { field, to } of changes) {
            if (field !== "description") st[field] = to;
          }
        }
      }
      return;
    }

    // Drag-and-drop from another connected client — reposition
    // this one card in place, never a full refreshBoard(). Fires for EVERY
    // successful move including a pure same-column reorder (see events.py's
    // TASK_MOVED payload doc): previously invisible to other clients since
    // task.status_changed only fires when status actually changes.
    if (event === "task.moved") {
      if (!issueName || !boardData.value?.board) return;
      const newStatus = payload.new_status;
      const newRank = payload.board_rank;

      let task = null;
      for (const col of Object.values(boardData.value.board)) {
        const idx = col.findIndex((i) => i.name === issueName);
        if (idx > -1) {
          task = col.splice(idx, 1)[0];
          break;
        }
      }
      if (!task) return; // not loaded on this client (different filter/board) — nothing to patch

      task.status = newStatus;
      task.board_rank = newRank;

      if (!boardData.value.board[newStatus]) boardData.value.board[newStatus] = [];
      const target = boardData.value.board[newStatus];
      // board_rank is a fixed-width zero-padded string (rank.py) — plain
      // string comparison sorts the same as the numeric rank it encodes.
      let insertAt = target.findIndex((i) => (i.board_rank || "") > newRank);
      if (insertAt === -1) insertAt = target.length;
      target.splice(insertAt, 0, task);

      if (selectedTask.value?.name === issueName) {
        selectedTask.value.status = newStatus;
      }
      const bl = backlogIssues.value.find((i) => i.name === issueName);
      if (bl) bl.status = newStatus;
      return;
    }

    if (event === "task.created") {
      // Surgical insert, not a board refetch — the create payload only
      // carries {task, task_key, title, status}, not the full task shape
      // TaskCard needs, so fetch just this one task and splice it in.
      if (issueName) {
        api
          .getTask(issueName)
          .then((full) => {
            if (!boardData.value?.board) return;
            const already = Object.values(boardData.value.board)
              .flat()
              .some((i) => i.name === issueName);
            if (already) return; // e.g. the creator's own optimistic insert
            const col = full.status;
            if (!boardData.value.board[col]) boardData.value.board[col] = [];
            boardData.value.board[col].push(full);
          })
          .catch(() => {});
      }
      if (backlogIssues.value.length > 0) {
        api
          .getBacklog(project)
          .then((issues) => {
            backlogIssues.value = issues;
          })
          .catch(() => {});
      }
      return;
    }

    if (event === "task.deleted") {
      for (const col of Object.values(boardData.value?.board || {})) {
        const idx = col.findIndex((i) => i.name === issueName);
        if (idx > -1) {
          col.splice(idx, 1);
          break;
        }
      }
      const bIdx = backlogIssues.value.findIndex((i) => i.name === issueName);
      if (bIdx > -1) backlogIssues.value.splice(bIdx, 1);
      if (selectedTask.value?.name === issueName) closeTaskDetail();
      return;
    }

    if (event === "task.updated" && changes?.length) {
      const boardIssue = Object.values(boardData.value?.board || {})
        .flat()
        .find((i) => i.name === issueName);
      const backlogIssue = backlogIssues.value.find(
        (i) => i.name === issueName,
      );
      const detailIssue =
        selectedTask.value?.name === issueName ? selectedTask.value : null;

      // Description changes: content is not in the payload (too large).
      // Always re-fetch the full issue and patch all stores.
      const needsRefetch = changes.some((c) => c.field === "description");
      if (needsRefetch) {
        api
          .getTask(issueName)
          .then((updated) => {
            // Patch board data
            for (const col of Object.values(boardData.value?.board || {})) {
              const bi = col.find((i) => i.name === issueName);
              if (bi) {
                bi.description = updated.description;
                break;
              }
            }
            // Patch backlog
            const bl = backlogIssues.value.find((i) => i.name === issueName);
            if (bl) bl.description = updated.description;
            // Patch open TaskDetail
            if (selectedTask.value?.name === issueName) {
              selectedTask.value.description = updated.description;
            }
          })
          .catch(() => {});
      }

      for (const { field, to } of changes) {
        if (field === "description") continue; // handled by refetch above

        if (field === "status") {
          if (boardIssue && boardData.value?.board) {
            const oldCol = Object.values(boardData.value.board).find((col) =>
              col.some((i) => i.name === issueName),
            );
            if (oldCol) {
              const idx = oldCol.findIndex((i) => i.name === issueName);
              if (idx > -1) {
                const [moved] = oldCol.splice(idx, 1);
                moved.status = to;
                if (!boardData.value.board[to]) boardData.value.board[to] = [];
                boardData.value.board[to].push(moved);
              }
            }
          }
          if (backlogIssue) backlogIssue.status = to;
          if (detailIssue) detailIssue.status = to;
        } else {
          if (boardIssue) boardIssue[field] = to;
          if (backlogIssue) backlogIssue[field] = to;
          if (detailIssue) detailIssue[field] = to;
        }
      }

      if (title && boardIssue) boardIssue.title = title;
      if (title && backlogIssue) backlogIssue.title = title;
      if (title && detailIssue) detailIssue.title = title;
      return;
    }

    if (event === "task.assigned" || event === "task.unassigned") {
      const boardIssue = Object.values(boardData.value?.board || {})
        .flat()
        .find((i) => i.name === issueName);
      if (boardIssue || backlogIssues.value.find((i) => i.name === issueName)) {
        api
          .getTask(issueName)
          .then((updated) => {
            if (boardIssue)
              Object.assign(boardIssue, { assignees: updated.assignees });
            const bl = backlogIssues.value.find((i) => i.name === issueName);
            if (bl) bl.assignees = updated.assignees;
            if (selectedTask.value?.name === issueName) {
              selectedTask.value.assignees = updated.assignees;
            }
          })
          .catch(() => {});
      }
      return;
    }

    if (event === "comment.added") {
      if (selectedTask.value?.name === issueName) {
        api
          .getTask(issueName)
          .then((updated) => {
            if (selectedTask.value?.name === issueName) {
              selectedTask.value = updated;
            }
          })
          .catch(() => {});
      }
    }
  }

  async function openTaskDetail(issueName) {
    showTaskDetail.value = true;
    selectedTask.value = null; // show loading state
    try {
      selectedTask.value = await api.getTask(issueName);
    } catch (e) {
      console.error("Failed to load issue:", e);
      showTaskDetail.value = false;
    }
  }

  // Refresh TaskDetail data without the null→loading flash.
  // Use this for in-panel actions (comments, links, subtasks) that don't
  // need to reset the panel — only update the data silently.
  async function refreshTaskDetail() {
    if (!selectedTask.value?.name) return;
    const issueName = selectedTask.value.name;
    try {
      const updated = await api.getTask(issueName);
      // Only apply if the same issue is still open
      if (selectedTask.value?.name === issueName) {
        selectedTask.value = updated;
      }
    } catch (e) {
      console.error("Failed to refresh issue:", e);
    }
  }

  function toggleNotifDrawer(val) { showNotifDrawer.value = val !== undefined ? val : !showNotifDrawer.value; }

  function closeTaskDetail() {
    showTaskDetail.value = false;
    selectedTask.value = null;
  }

  // ─── Board filters ────────────────────────────────────────────────────────

  function setFilter(key, value) {
    boardFilters.value[key] = value;
  }

  function clearFilters() {
    boardFilters.value = {
      status: [],
      assignee: [],
      priority: [],
      labels: [],
      task_type: [],
      search: "",
    };
  }

  const hasActiveFilters = computed(() => {
    const f = boardFilters.value;
    return (
      f.status.length ||
      f.assignee.length ||
      f.priority.length ||
      f.labels.length ||
      f.task_type.length ||
      f.search
    );
  });

  /**
   * Build a query_tasks-compatible filters object from boardFilters.
   */
  const activeQueryFilters = computed(() => {
    const f = boardFilters.value;
    const out = {};
    if (f.status?.length) out.status = f.status;
    if (f.assignee?.length) out.assignee = f.assignee;
    if (f.priority?.length) out.priority = f.priority;
    if (f.labels?.length) out.labels = f.labels;
    if (f.task_type?.length) out.task_type = f.task_type;
    if (f.search?.trim()) out.search = f.search.trim();
    return out;
  });

  // ─── Saved views ──────────────────────────────────────────────────────────

  async function saveCurrentView(name, projectKey, viewType = 'board') {
    const config = {
      group_by:      boardGroupBy.value,
      sort_by:       boardSortBy.value,
      sprint_filter: boardSprintFilter.value,
      filters: {
        filterAssignee: boardViewState.value.filterAssignee,
        filterPriority: boardViewState.value.filterPriority,
        filterType:     boardViewState.value.filterType,
        filterLabel:    boardViewState.value.filterLabel,
        search:         boardViewState.value.search || '',
      },
    };
    const projectName = currentProject.value?.name
    if (projectName) {
      try {
        const view = await api.saveView(projectName, name, config, viewType, 0)
        savedViews.value = [...savedViews.value, view]
        svTick.value++
        return view
      } catch { /* fall through to localStorage */ }
    }
    const view = { id: Date.now().toString(), name, project_key: projectKey, view_type: viewType, ...config };
    savedViews.value = [...savedViews.value, view];
    _persistViews(projectKey);
    svTick.value++;
    return view;
  }

  function applyView(view) {
    activeViewId.value     = view.id;
    boardGroupBy.value     = view.group_by      || 'status';
    boardSortBy.value      = view.sort_by       || 'board_order';
    boardSprintFilter.value = view.sprint_filter || 'all';
    boardViewState.value = {
      ...boardViewState.value,
      filterAssignee: view.filters?.filterAssignee || null,
      filterPriority: view.filters?.filterPriority || null,
      filterType:     view.filters?.filterType     || null,
      filterLabel:    view.filters?.filterLabel    || null,
      search:         view.filters?.search         || '',
    };
  }

  async function removeView(id, projectKey) {
    savedViews.value = savedViews.value.filter((v) => v.id !== id);
    if (activeViewId.value === id) activeViewId.value = null;
    // Server-side views have a VIEW-xxxx id; localStorage ones use a numeric timestamp.
    if (typeof id === 'string' && id.startsWith('VIEW-')) {
      try { await api.deleteView(id); } catch { /* ignore */ }
    } else {
      _persistViews(projectKey);
    }
    svTick.value++;
  }

  // ─── Favourites ───────────────────────────────────────────────────────────

  function toggleFavourite(projectName) {
    const idx = favourites.value.indexOf(projectName);
    if (idx > -1) favourites.value.splice(idx, 1);
    else favourites.value.push(projectName);
    localStorage.setItem("bp_favourites", JSON.stringify(favourites.value));
  }

  function isFavourite(projectName) {
    return favourites.value.includes(projectName);
  }

  // ─── Pinned teams ─────────────────────────────────────────────────────────

  const pinnedTeams = ref(
    JSON.parse(localStorage.getItem("bp_pinned_teams") || "[]"),
  );

  function togglePinnedTeam(team) {
    const idx = pinnedTeams.value.findIndex(t => t.team_key === team.team_key);
    if (idx > -1) pinnedTeams.value.splice(idx, 1);
    else pinnedTeams.value.push({
      name: team.name,
      team_name: team.team_name,
      team_key: team.team_key,
      team_color: team.team_color,
    });
    try { localStorage.setItem("bp_pinned_teams", JSON.stringify(pinnedTeams.value)); } catch {}
  }

  function isTeamPinned(teamKey) {
    return pinnedTeams.value.some(t => t.team_key === teamKey);
  }

  // ─── UI helpers ───────────────────────────────────────────────────────────

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  }

  // capability check for currentProject. Defaults true (fail
  // open) before myCapabilities has loaded or for an unrecognized key —
  // cosmetic only, every gated endpoint re-checks server-side regardless.
  function hasCapability(cap) {
    return myCapabilities.value[cap] !== false;
  }

  // ─── Expose ───────────────────────────────────────────────────────────────

  return {
    // State
    projects,
    currentUser,
    bootstrapSession,
    currentProject,
    boardData,
    myRole,
    myCapabilities,
    hasCapability,
    loading,
    selectedTask,
    pendingBlock,
    showTaskDetail,
    showNotifDrawer,
    toggleNotifDrawer,
    showCreateTask,
    createTaskDefaults,
    projectMembers,
    sprints,
    sidebarCollapsed,
    boardGroupBy,
    boardSortBy,
    showChildIssues,
    boardSprintFilter,
    boardViewState,
    boardFilters,
    savedViews,
    activeViewId,
    svTick,
    loadSavedViews,
    favourites,
    sortedProjects,
    setProjectOrder,
    projectLanding,
    backlogIssues,
    issueCreatedCount,
    setBacklogIssues,

    // Getters
    columns,
    board,
    epics,
    workflowStates,
    workflowStateMap,
    taskTypes,
    taskTypeMap,
    customFieldsSchema,
    projectLabels,
    labelMap,
    activeSprints,
    activeIssue,
    hasActiveFilters,
    activeQueryFilters,

    // Actions
    fetchProjects,
    toggleFavorite,
    fetchTeams,
    teams,
    currentTeam,
    fetchBoard,
    refreshBoard,
    flushDeferredRealtimeEvent,
    fetchMembers,
    fetchSprints,
    moveIssue,
    updateTaskField,
    taskPatch,
    confirmBlockedStatus,
    cancelBlockedStatus,
    updateIssueFields,
    createNewIssue,
    deleteCurrentIssue,
    openTaskDetail,
    refreshTaskDetail,
    closeTaskDetail,
    setFilter,
    clearFilters,
    saveCurrentView,
    applyView,
    removeView,
    toggleFavourite,
    isFavourite,
    pinnedTeams,
    togglePinnedTeam,
    isTeamPinned,
    toggleSidebar,
    notificationCount,
  };
});
