import { defineStore } from "pinia";
import { ref, reactive } from "vue";
import { getMirrorSchema, getMirrorValues, getViewPrefs, saveViewPrefs } from "@/utils/api";
import { formatMirrorValue } from "@/utils/mirrorFormat.js";
import { useProjectStore } from "@/stores/project";

// Kanban board's ERP mirror-field chips (view fixed to "board" — ListView has
// its own separate, pre-existing mirror-column mechanism built directly into
// ListView.vue, and Gantt has none at all; unifying those is bigger, separate
// work). A Pinia store, not a per-component composable, so ProjectHeader's
// <ErpMirrorFieldsButton> and Board.vue's card chips share ONE reactive
// instance — two independent useMirrorColumns() calls (the previous shape)
// could drift out of sync, and ProjectHeader's copy never triggered
// loadSchema()/loadPrefs() at all, rendering an empty, non-functional
// duplicate of Board.vue's own button.
export const useMirrorColumnsStore = defineStore("mirrorColumns", () => {
  const view = "board";
  const mirrorCols = ref([]); // [{doctype, field}]
  const mirrorSchema = ref({}); // {doctype: [{fieldname,label,fieldtype}]}
  const mirrorData = reactive({}); // {doctype: {ref_name: {field: value}}}

  function _project() {
    return useProjectStore().currentProject?.name;
  }

  async function loadPrefs() {
    const project = _project();
    if (!project) return;
    try {
      const p = await getViewPrefs(project, view);
      mirrorCols.value = Array.isArray(p?.mirrorCols) ? p.mirrorCols : [];
    } catch {
      mirrorCols.value = [];
    }
  }

  async function loadSchema() {
    const project = _project();
    if (!project) return;
    try {
      mirrorSchema.value = (await getMirrorSchema(project)) || {};
    } catch {
      mirrorSchema.value = {};
    }
  }

  async function loadValues(issues) {
    const dts = [...new Set(mirrorCols.value.map((m) => m.doctype))];
    for (const dt of dts) {
      const want = new Set();
      for (const issue of issues)
        for (const r of issue.references || []) if (r.ref_doctype === dt) want.add(r.ref_name);
      const have = mirrorData[dt] || {};
      const missing = [...want].filter((n) => !(n in have));
      if (missing.length) {
        try {
          const got = await getMirrorValues(dt, missing, _project());
          mirrorData[dt] = { ...have, ...got };
        } catch {
          /* leave have as-is */
        }
      }
    }
  }

  function mirrorFieldMeta(dt, field) {
    return (mirrorSchema.value[dt] || []).find((f) => f.fieldname === field);
  }

  function mirrorChips(issue) {
    const chips = [];
    for (const col of mirrorCols.value) {
      const meta = mirrorFieldMeta(col.doctype, col.field);
      for (const r of issue.references || []) {
        if (r.ref_doctype !== col.doctype) continue;
        const rec = mirrorData[col.doctype]?.[r.ref_name];
        const val = rec?.[col.field];
        if (val == null || val === "") continue;
        chips.push({
          key: `${col.doctype}:${col.field}:${r.ref_name}`,
          label: meta?.label || col.field,
          text: formatMirrorValue(val, meta?.fieldtype, rec),
          doctype: col.doctype,
          name: r.ref_name,
        });
      }
    }
    return chips;
  }

  async function persist() {
    const project = _project();
    if (!project) return;
    try {
      await saveViewPrefs(project, { mirrorCols: mirrorCols.value }, view);
    } catch {
      /* best-effort */
    }
  }

  async function addMirrorField(doctype, field) {
    if (!mirrorCols.value.find((m) => m.doctype === doctype && m.field === field)) {
      mirrorCols.value = [...mirrorCols.value, { doctype, field }];
      await persist();
    }
  }

  async function removeMirrorField(doctype, field) {
    mirrorCols.value = mirrorCols.value.filter((m) => !(m.doctype === doctype && m.field === field));
    await persist();
  }

  return {
    mirrorCols,
    mirrorSchema,
    mirrorData,
    loadPrefs,
    loadSchema,
    loadValues,
    mirrorFieldMeta,
    mirrorChips,
    addMirrorField,
    removeMirrorField,
  };
});
