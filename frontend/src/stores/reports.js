import { defineStore } from "pinia";
import { ref } from "vue";
import * as api from "@/utils/api";

// Grid defaults per widget type (12-col, row-height 10, margin 12).
export const WIDGET_DEFAULTS = {
  metric: { w: 3, h: 13, minW: 2, minH: 5 },
  chart: { w: 6, h: 21, minW: 3, minH: 8 },
  table: { w: 8, h: 20, minW: 4, minH: 7 },
  preset: { w: 6, h: 21, minW: 3, minH: 8 },
  query: { w: 9, h: 24, minW: 4, minH: 10 },
  text:  { w: 4, h: 10, minW: 2, minH: 4 },
};

function uid(prefix = "w") {
  return prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
}

function newWidget(type, extra = {}) {
  const base = { id: uid("w"), type, title: "", description: "", scope: "inherit" };
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
  return base;
}

// Persistable widget fields only (never store live data/loading).
function slimWidget(w) {
  const { id, type, title, description, chartType, group_by, metric, scope, colorScheme, preset, period, statusFilter, priority, sortBy, sortOrder, limit, columns, pageSize, bql, text } = w;
  return { id, type, title, description, chartType, group_by, metric, scope, colorScheme, preset, period, statusFilter, priority, sortBy, sortOrder, limit, columns, pageSize, bql, text };
}

// Single-project scope -> the BP Report.project column (for server filtering).
function scopeProject(scope) {
  if (!scope || scope === "all") return null;
  if (Array.isArray(scope)) return scope.length === 1 ? scope[0] : null;
  return scope;
}

export const useReportsStore = defineStore("reports", () => {
  const reports = ref([]);   // { id, name, icon, color, starred, scope, period, milestone, widgets, layout, _loaded }
  const loaded = ref(false);

  function getReport(id) {
    return reports.value.find((r) => r.id === id) || null;
  }

  // ── persistence (optimistic + debounced) ──────────────────────────────────
  let timer = null;
  function persist() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(flush, 600);
  }
  async function flush() {
    const dirty = reports.value.filter((r) => r._dirty && r._loaded);
    for (const r of dirty) {
      r._dirty = false;
      try {
        await api.saveReport({
          report: r.id,
          report_name: r.name,
          project: scopeProject(r.scope),
          milestone: r.milestone || null,
          period: r.period || "last_30_days",
          icon: r.icon || "BarChart3",
          color: r.color || null,
          starred: r.starred ? 1 : 0,
          pinned: r.pinned ? 1 : 0,
          schedule_enabled: r.schedule_enabled ? 1 : 0,
          schedule_frequency: r.schedule_frequency || "Weekly",
          schedule_day: r.schedule_day || "Monday",
          schedule_hour: r.schedule_hour ?? 8,
          schedule_recipients: r.schedule_recipients || "",
          scope: r.report_scope || "project",
          visibility: r.visibility || "private",
          layout: JSON.stringify({
            scope: r.scope, period: r.period, milestone: r.milestone || null,
            from_date: r.from_date || null, to_date: r.to_date || null,
            widgets: (r.widgets || []).map(slimWidget), layout: r.layout || [],
          }),
        });
      } catch (e) { r._dirty = true; /* retry next flush */ }
    }
  }
  function touch(r) { if (r) { r.updated = Date.now(); r._dirty = true; persist(); } }

  function _mapRow(row) {
    return {
      id: row.id, name: row.report_name, icon: row.icon || "BarChart3",
      color: row.color || null, starred: !!row.starred, pinned: !!row.pinned,
      scope: row.project || "all", period: row.period || "last_30_days",
      milestone: row.milestone || null, modified: row.modified || null,
      // report_scope (project/workspace) and visibility
      // (private/workspace) are separate from the pre-existing `scope`
      // field above (which means "project name or 'all'", a different
      // concept — see api/board.py's own naming-collision note).
      report_scope: row.report_scope || (row.project ? "project" : "workspace"),
      visibility: row.visibility || "private",
      owner: row.owner || null, is_mine: row.is_mine !== false,
      schedule_enabled: !!row.schedule_enabled,
      schedule_frequency: row.schedule_frequency || "Weekly",
      schedule_day: row.schedule_day || "Monday",
      schedule_hour: row.schedule_hour ?? 8,
      schedule_recipients: row.schedule_recipients || "",
      last_sent: row.last_sent || null,
      widgets: [], layout: [], _loaded: false,
    };
  }

  async function load() {
    if (loaded.value) return;
    loaded.value = true;
    try {
      const rows = await api.getSavedReports();
      reports.value = (rows || []).map(_mapRow);
    } catch { reports.value = []; }
  }

  async function reload() { loaded.value = false; await load(); }

  // Ensure a report's full layout is loaded before the builder reads it.
  async function ensureReport(id) {
    let r = getReport(id);
    if (r && r._loaded) return r;
    try {
      const d = await api.getSavedReport(id);
      const data = d.widgets || {};   // backend returns the layout blob under `widgets`
      const merged = {
        id: d.id, name: d.report_name, icon: d.icon || "BarChart3",
        color: d.color || null, starred: !!d.starred, pinned: !!d.pinned,
        scope: data.scope ?? d.scope ?? "all",
        period: data.period ?? d.period ?? "last_30_days",
        milestone: data.milestone ?? d.milestone ?? null,
        schedule_enabled: !!d.schedule_enabled,
        schedule_frequency: d.schedule_frequency || "Weekly",
        schedule_day: d.schedule_day || "Monday",
        schedule_hour: d.schedule_hour ?? 8,
        schedule_recipients: d.schedule_recipients || "",
        last_sent: d.last_sent || null,
        from_date: data.from_date || null, to_date: data.to_date || null,
        widgets: data.widgets || [], layout: data.layout || [],
        _loaded: true, _dirty: false,
      };
      if (r) Object.assign(r, merged);
      else { reports.value.unshift(merged); r = merged; }
      return r;
    } catch { return r; }
  }

  // ── CRUD ──────────────────────────────────────────────────────────────────
  async function createReport(name = "Untitled report", icon = "BarChart3", extra = {}) {
    // report_scope defaults to "workspace" when the widget
    // scope is cross-project ("all"), else "project"; visibility defaults
    // private (the free, ungated shape). Widening either requires the
    // `dashboards` entitlement server-side — this call surfaces that as a
    // normal UpgradeRequiredError, same as every other gated action.
    const reportScope = extra.reportScope || (extra.scope && extra.scope !== "all" ? "project" : "workspace");
    const visibility = extra.visibility || "private";
    const d = await api.saveReport({
      report_name: name.trim() || "Untitled report",
      icon: icon || "BarChart3",
      project: scopeProject(extra.scope),
      milestone: extra.milestone || null,
      period: extra.period || "last_30_days",
      scope: reportScope, visibility,
      layout: JSON.stringify({ scope: extra.scope || "all", period: extra.period || "last_30_days",
        milestone: extra.milestone || null, widgets: [], layout: [] }),
    });
    const r = {
      id: d.id, name: d.report_name, icon: d.icon, color: d.color || null,
      starred: false, scope: extra.scope || "all", period: extra.period || "last_30_days",
      milestone: extra.milestone || null, modified: d.modified || new Date().toISOString(),
      report_scope: reportScope, visibility, owner: d.owner || null, is_mine: true,
      widgets: [], layout: [], _loaded: true, _dirty: false,
    };
    reports.value.unshift(r);
    return r.id;
  }

  // Create a report from an exported definition (import / share-a-template).
  async function importReport(def) {
    const widgets = Array.isArray(def?.widgets) ? def.widgets.map(slimWidget) : []
    // re-key widget ids so an imported report never collides with an existing one
    const idMap = {}
    const newWidgets = widgets.map((w) => {
      const nid = uid("w"); idMap[w.id] = nid; return { ...w, id: nid }
    })
    const layout = Array.isArray(def?.layout)
      ? def.layout.map((l) => ({ ...l, i: idMap[l.i] || l.i })).filter((l) => newWidgets.some((w) => w.id === l.i))
      : []
    const id = await createReport(def?.report_name || def?.name || "Imported report",
      def?.icon || "BarChart3",
      { scope: def?.scope || "all", period: def?.period || "last_30_days", milestone: def?.milestone || null })
    const r = getReport(id)
    if (r) { r.widgets = newWidgets; r.layout = layout; touch(r) }
    return id
  }

  function renameReport(id, name) {
    const r = getReport(id);
    if (r) { r.name = name.trim() || r.name; touch(r); }
  }

  function updateReport(id, patch) {
    const r = getReport(id);
    if (r) { Object.assign(r, patch); touch(r); }
  }

  // Pin / unpin a report to the sidebar (optimistic + persisted).
  function togglePinned(id) {
    const r = getReport(id);
    if (r) { r.pinned = !r.pinned; touch(r); }
  }

  // Update scheduled-delivery config. patch keys: schedule_enabled,
  // schedule_frequency, schedule_day, schedule_hour, schedule_recipients.
  function setSchedule(id, patch) {
    const r = getReport(id);
    if (r) { Object.assign(r, patch); touch(r); }
  }

  async function deleteReport(id) {
    reports.value = reports.value.filter((r) => r.id !== id);
    try { await api.deleteSavedReport(id); } catch {}
  }

  async function duplicateReport(id) {
    const r = await ensureReport(id);
    if (!r) return null;
    const idMap = {};
    const widgets = (r.widgets || []).map((w) => {
      const nw = { ...slimWidget(w), id: uid("w") };
      idMap[w.id] = nw.id;
      return nw;
    });
    const layout = (r.layout || []).map((l) => ({ ...l, i: idMap[l.i] || l.i }));
    const newId = await createReport(`${r.name} (copy)`, r.icon,
      { scope: r.scope, period: r.period, milestone: r.milestone });
    const copy = getReport(newId);
    if (copy) { copy.widgets = widgets; copy.layout = layout; touch(copy); }
    return newId;
  }

  // ── widgets ─────────────────────────────────────────────────────────────
  function nextY(layout) { return layout.reduce((m, l) => Math.max(m, l.y + l.h), 0); }

  function addWidget(reportId, type, extra = {}) {
    const r = getReport(reportId);
    if (!r) return null;
    const w = newWidget(type, extra);
    const d = extra.size || WIDGET_DEFAULTS[type] || WIDGET_DEFAULTS.chart;
    r.widgets.push(w);
    r.layout.push({ i: w.id, x: (r.layout.length * 3) % 12, y: nextY(r.layout), ...d });
    touch(r);
    return w;
  }

  function removeWidget(reportId, widgetId) {
    const r = getReport(reportId);
    if (!r) return;
    r.widgets = r.widgets.filter((w) => w.id !== widgetId);
    r.layout = r.layout.filter((l) => l.i !== widgetId);
    touch(r);
  }

  function updateWidgetConfig(reportId, widgetId, patch) {
    const r = getReport(reportId);
    const w = r?.widgets.find((x) => x.id === widgetId);
    if (w) { Object.assign(w, patch); touch(r); }
  }

  function updateLayout(reportId, layout) {
    const r = getReport(reportId);
    if (r) { r.layout = layout.map((l) => ({ ...l })); touch(r); }
  }

  return {
    reports, loaded,
    load, reload, ensureReport,
    getReport, createReport, importReport, renameReport, updateReport, deleteReport, duplicateReport,
    togglePinned, setSchedule,
    addWidget, removeWidget, updateWidgetConfig, updateLayout,
    persist,
  };
});
