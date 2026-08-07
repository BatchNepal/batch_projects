import { defineStore } from "pinia";
import { ref } from "vue";
import * as api from "@/utils/api";

// Grid defaults per widget type (12-col, row-height 10, margin 12) — same
// grid shape as reports.js's WIDGET_DEFAULTS, plus "column": a single
// Wrike-dashboard-style glance column (one person/status, date-bucketed,
// read-mostly, click through to the real task). Narrow + tall by design —
// a template composes N of these side by side into a full board, rather
// than one wide widget cramming many columns into itself. See ColumnWidget.vue.
export const WIDGET_DEFAULTS = {
  metric: { w: 3, h: 13, minW: 2, minH: 5 },
  chart: { w: 6, h: 21, minW: 3, minH: 8 },
  table: { w: 8, h: 20, minW: 4, minH: 7 },
  preset: { w: 6, h: 21, minW: 3, minH: 8 },
  query: { w: 9, h: 24, minW: 4, minH: 10 },
  text:  { w: 4, h: 10, minW: 2, minH: 4 },
  // Short by default — a title+description line only needs ~50-70px; the
  // old h:8 (~164px) left a lot of dead space below the text since the grid
  // box height is independent of content height (see HeaderWidget.vue).
  header: { w: 8, h: 4, minW: 3, minH: 3 },
  column: { w: 3, h: 44, minW: 2, minH: 16 },
  // A full board, not a single glance column — wide/tall by default so its
  // auto-generated columns have room, same as the real per-project Board.vue.
  kanban: { w: 12, h: 40, minW: 6, minH: 20 },
};

// A single project's own workflow_states are the real, accurate status
// list; across a whole workspace different projects can define different
// states, so there's no one canonical list — this is the shared fallback
// used both by the "Project status" template and the manual column
// Configure picker.
export const DEFAULT_STATUSES = ['Open', 'In Progress', 'In Review', 'Done']

function uid(prefix = "w") {
  return prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
}

function newWidget(type, extra = {}) {
  const base = {
    id: uid("w"), type, title: "", description: "", scope: "inherit", borderless: extra.borderless || false,
    // Unset (null) keeps the automatic default (16px, 0 if borderless) —
    // see DashboardView.vue's effPadding(). Every widget type gets these,
    // not just column/header.
    padding_x: extra.padding_x ?? null, padding_y: extra.padding_y ?? null,
  };
  if (type === "chart") return { ...base, chartType: "bar", group_by: "status", metric: "count", colorScheme: "blue" };
  if (type === "metric") return { ...base, group_by: "status", metric: "count", colorScheme: "blue" };
  if (type === "table") return {
    ...base,
    statusFilter: "open", priority: "", sortBy: "modified", sortOrder: "desc", limit: "200",
    columns: ["task_key", "title", "status", "priority", "assignees", "due_date"], pageSize: "10",
  };
  if (type === "preset") return { ...base, preset: extra.preset, period: "inherit" };
  if (type === "query") return {
    ...base, bql: extra.bql || "",
    columns: ["task_key", "title", "status", "priority", "assignees", "due_date"], pageSize: "15",
  };
  if (type === "text") return { ...base, text: extra.text || "" };
  if (type === "header") return { ...base, link_url: extra.link_url || "", link_label: extra.link_label || "" };
  if (type === "column") return {
    ...base, filterBy: extra.filterBy || null, filterValue: extra.filterValue ?? null,
    statusFilter: "open", title: extra.title || "",
    // No doctype default — a brand-new column widget starts genuinely
    // unconfigured (ColumnWidget.vue shows a Configure prompt, never
    // silently assumes BP Task). A template that explicitly wants a Task
    // column (e.g. a per-person workload template) passes extra.filterBy
    // itself, which is what ColumnWidget.vue's back-compat check actually
    // keys on — same path pre-existing saved widgets (which predate the
    // `doctype` field) already rely on.
    doctype: extra.doctype || null, filters: extra.filters || [],
    // Wrike-style Overdue/Today/This week rail. On by default — the backend
    // only returns buckets for sources with a real deadline field, so this
    // is a no-op for Customer/Item/Payment Entry style sources.
    bucketed: extra.bucketed !== false,
    color: extra.color || null,
  };
  if (type === "kanban") return {
    ...base, doctype: extra.doctype || "BP Task", group_by: extra.group_by || "status",
    filters: extra.filters || [],
  };
  return base;
}

// Persistable widget fields only (never store live data/loading).
function slimWidget(w) {
  const { id, type, title, description, chartType, group_by, metric, scope, colorScheme, preset, period, statusFilter, priority, sortBy, sortOrder, limit, columns, pageSize, bql, text, filterBy, filterValue, doctype, filters, borderless, bucketed, label_fields, date_field, link_url, link_label, color, padding_x, padding_y } = w;
  return { id, type, title, description, chartType, group_by, metric, scope, colorScheme, preset, period, statusFilter, priority, sortBy, sortOrder, limit, columns, pageSize, bql, text, filterBy, filterValue, doctype, filters, borderless, bucketed, label_fields, date_field, link_url, link_label, color, padding_x, padding_y };
}

// Single-project scope -> the BP Dashboard.project column (for server filtering).
function scopeProject(scope) {
  if (!scope || scope === "all") return null;
  if (Array.isArray(scope)) return scope.length === 1 ? scope[0] : null;
  return scope;
}

export const useDashboardsStore = defineStore("dashboards", () => {
  const dashboards = ref([]);   // { id, name, icon, color, starred, scope, period, milestone, widgets, layout, _loaded }
  const loaded = ref(false);

  function getDashboard(id) {
    return dashboards.value.find((d) => d.id === id) || null;
  }

  // ── persistence (optimistic + debounced) ──────────────────────────────────
  let timer = null;
  function persist() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(flush, 600);
  }
  async function flush() {
    const dirty = dashboards.value.filter((d) => d._dirty && d._loaded);
    for (const d of dirty) {
      d._dirty = false;
      try {
        await api.saveDashboard({
          dashboard: d.id,
          dashboard_name: d.name,
          project: scopeProject(d.scope),
          milestone: d.milestone || null,
          period: d.period || "last_30_days",
          icon: d.icon || "LayoutDashboard",
          color: d.color || null,
          starred: d.starred ? 1 : 0,
          pinned: d.pinned ? 1 : 0,
          visibility: d.visibility || "private",
          layout: JSON.stringify({
            scope: d.scope, period: d.period, milestone: d.milestone || null,
            widgets: (d.widgets || []).map(slimWidget), layout: d.layout || [],
          }),
        });
      } catch (e) { d._dirty = true; /* retry next flush */ }
    }
  }
  function touch(d) { if (d) { d.updated = Date.now(); d._dirty = true; persist(); } }

  function _mapRow(row) {
    return {
      id: row.id, name: row.dashboard_name, icon: row.icon || "LayoutDashboard",
      color: row.color || null, starred: !!row.starred, pinned: !!row.pinned,
      scope: row.project || "all", period: row.period || "last_30_days",
      milestone: row.milestone || null, modified: row.modified || null,
      visibility: row.visibility || "private",
      owner: row.owner || null, is_mine: row.is_mine !== false,
      widgets: [], layout: [], _loaded: false,
    };
  }

  async function load() {
    if (loaded.value) return;
    loaded.value = true;
    try {
      const rows = await api.listDashboards();
      // Merge into any already-loaded entries rather than replacing the
      // array wholesale — Sidebar.vue (pinned-dashboards list) and a
      // DashboardView.vue detail page both call load() on mount now, and
      // whichever resolves second used to stomp the other's already-fetched
      // widgets/layout back to bare listing metadata (visible as the
      // dashboard flashing "Empty dashboard" after it had just rendered
      // correctly). A _loaded entry keeps its real data; only the not-yet-
      // opened ones take the fresh bare metadata.
      const existingById = new Map(dashboards.value.map((d) => [d.id, d]));
      dashboards.value = (rows || []).map((row) => {
        const existing = existingById.get(row.id);
        return existing && existing._loaded ? existing : _mapRow(row);
      });
    } catch { /* keep whatever's already loaded rather than wiping it */ }
  }

  async function reload() { loaded.value = false; await load(); }

  // Ensure a dashboard's full layout is loaded before the builder reads it.
  async function ensureDashboard(id) {
    let d = getDashboard(id);
    if (d && d._loaded) return d;
    try {
      const res = await api.getDashboardRecord(id);
      const data = res.widgets || {};   // backend returns the layout blob under `widgets`
      const merged = {
        id: res.id, name: res.dashboard_name, icon: res.icon || "LayoutDashboard",
        color: res.color || null, starred: !!res.starred, pinned: !!res.pinned,
        scope: data.scope ?? res.scope ?? "all",
        period: data.period ?? res.period ?? "last_30_days",
        milestone: data.milestone ?? res.milestone ?? null,
        visibility: res.visibility || "private",
        // Was missing here (present in _mapRow, used by the bare listing) —
        // a dashboard opened directly (not via the list first) ended up
        // with no owner at all, silently blank wherever it's shown.
        owner: res.owner || null, is_mine: res.is_mine !== false,
        widgets: data.widgets || [], layout: data.layout || [],
        _loaded: true, _dirty: false,
      };
      if (d) Object.assign(d, merged);
      else { dashboards.value.unshift(merged); d = merged; }
      return d;
    } catch { return d; }
  }

  // ── CRUD ──────────────────────────────────────────────────────────────────
  async function createDashboard(name = "Untitled dashboard", icon = "LayoutDashboard", extra = {}) {
    const visibility = extra.visibility || "private";
    const d = await api.saveDashboard({
      dashboard_name: name.trim() || "Untitled dashboard",
      icon: icon || "LayoutDashboard",
      project: scopeProject(extra.scope),
      milestone: extra.milestone || null,
      period: extra.period || "last_30_days",
      visibility,
      layout: JSON.stringify({ scope: extra.scope || "all", period: extra.period || "last_30_days",
        milestone: extra.milestone || null, widgets: [], layout: [] }),
    });
    const r = {
      id: d.id, name: d.dashboard_name, icon: d.icon, color: d.color || null,
      starred: false, scope: extra.scope || "all", period: extra.period || "last_30_days",
      milestone: extra.milestone || null, modified: d.modified || new Date().toISOString(),
      visibility, owner: d.owner || null, is_mine: true,
      widgets: [], layout: [], _loaded: true, _dirty: false,
    };
    dashboards.value.unshift(r);
    return r.id;
  }

  function renameDashboard(id, name) {
    const d = getDashboard(id);
    if (d) { d.name = name.trim() || d.name; touch(d); }
  }

  function updateDashboard(id, patch) {
    const d = getDashboard(id);
    if (d) { Object.assign(d, patch); touch(d); }
  }

  function togglePinned(id) {
    const d = getDashboard(id);
    if (d) { d.pinned = !d.pinned; touch(d); }
  }

  async function deleteDashboard(id) {
    dashboards.value = dashboards.value.filter((d) => d.id !== id);
    try { await api.deleteDashboard(id); } catch {}
  }

  async function duplicateDashboard(id) {
    const d = await ensureDashboard(id);
    if (!d) return null;
    const idMap = {};
    const widgets = (d.widgets || []).map((w) => {
      const nw = { ...slimWidget(w), id: uid("w") };
      idMap[w.id] = nw.id;
      return nw;
    });
    const layout = (d.layout || []).map((l) => ({ ...l, i: idMap[l.i] || l.i }));
    const newId = await createDashboard(`${d.name} (copy)`, d.icon,
      { scope: d.scope, period: d.period, milestone: d.milestone, visibility: d.visibility });
    const copy = getDashboard(newId);
    if (copy) { copy.widgets = widgets; copy.layout = layout; touch(copy); }
    return newId;
  }

  // ── widgets ─────────────────────────────────────────────────────────────
  function nextY(layout) { return layout.reduce((m, l) => Math.max(m, l.y + l.h), 0); }

  // extra.x/extra.y let a template place widgets explicitly (e.g. N column
  // widgets side by side in one row) instead of the default vertical stack —
  // nextY() alone always stacks a new widget below everything else, which is
  // right for one-widget-at-a-time additions but wrong for "add N columns
  // that form one row."
  function addWidget(dashboardId, type, extra = {}) {
    const d = getDashboard(dashboardId);
    if (!d) return null;
    const w = newWidget(type, extra);
    const size = extra.size || WIDGET_DEFAULTS[type] || WIDGET_DEFAULTS.chart;
    const x = extra.x ?? (d.layout.length * 3) % 12;
    const y = extra.y ?? nextY(d.layout);
    d.widgets.push(w);
    d.layout.push({ i: w.id, x, y, ...size });
    touch(d);
    return w;
  }

  function removeWidget(dashboardId, widgetId) {
    const d = getDashboard(dashboardId);
    if (!d) return;
    d.widgets = d.widgets.filter((w) => w.id !== widgetId);
    d.layout = d.layout.filter((l) => l.i !== widgetId);
    touch(d);
  }

  function updateWidgetConfig(dashboardId, widgetId, patch) {
    const d = getDashboard(dashboardId);
    const w = d?.widgets.find((x) => x.id === widgetId);
    if (w) { Object.assign(w, patch); touch(d); }
  }

  function updateLayout(dashboardId, layout) {
    const d = getDashboard(dashboardId);
    if (d) { d.layout = layout.map((l) => ({ ...l })); touch(d); }
  }

  return {
    dashboards, loaded,
    load, reload, ensureDashboard,
    getDashboard, createDashboard, renameDashboard, updateDashboard, deleteDashboard, duplicateDashboard,
    togglePinned,
    addWidget, removeWidget, updateWidgetConfig, updateLayout,
    persist,
  };
});
