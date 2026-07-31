/**
 * utils/customFields.js
 * ─────────────────────
 * All custom field logic. No Vue dependencies — pure JS.
 * Imported by CustomFieldInput.vue, TaskDetail.vue, CreateTask.vue,
 * ListView.vue, and ProjectSettings.vue.
 */

// ─── ID GENERATION ───────────────────────────────────────────────────────────

export function generateFieldId() {
  return "cf_" + Math.random().toString(16).slice(2, 10);
}

export function generateOptionId() {
  return "opt_" + Math.random().toString(16).slice(2, 10);
}

export function generateLabelId() {
  return "lbl_" + Math.random().toString(16).slice(2, 10);
}

// ─── FIELD TYPES ─────────────────────────────────────────────────────────────
// Single source of truth for the type catalog — was previously duplicated
// (and had drifted, 9 vs 14 types) between here and ProjectSettings.vue.
// No Vue deps in this file by design, so `icon` is a string key, not a
// component — ProjectSettings.vue's ICON_MAP resolves it to a lucide-vue-next
// component for display.

export const FIELD_CATS = ["Basic", "Rich"];

export const FIELD_TYPES = [
  // Basic
  { value: "text", label: "Text", icon: "type", cat: "Basic", color: "#64748B", desc: "Single line of text." },
  { value: "textarea", label: "Long text", icon: "align-left", cat: "Basic", color: "#64748B", desc: "Multi-line notes." },
  { value: "number", label: "Number", icon: "hash", cat: "Basic", color: "#2684FF", desc: "Numeric value." },
  { value: "date", label: "Date", icon: "calendar", cat: "Basic", color: "#8B5CF6", desc: "A calendar date." },
  { value: "checkbox", label: "Checkbox", icon: "check-square", cat: "Basic", color: "#16A34A", desc: "A yes / no toggle." },
  { value: "select", label: "Dropdown", icon: "chevron-down-square", cat: "Basic", color: "#0EA5E9", desc: "Pick one option." },
  { value: "multiselect", label: "Multi-select", icon: "list-checks", cat: "Basic", color: "#0EA5E9", desc: "Pick several options." },
  // Rich
  { value: "currency", label: "Currency", icon: "banknote", cat: "Rich", color: "#16A34A", desc: "Money, with symbol." },
  { value: "percent", label: "Percent", icon: "percent", cat: "Rich", color: "#F59E0B", desc: "0–100% value." },
  { value: "rating", label: "Rating", icon: "star", cat: "Rich", color: "#F59E0B", desc: "1–5 star rating." },
  { value: "email", label: "Email", icon: "mail", cat: "Rich", color: "#EC4899", desc: "An email address." },
  { value: "phone", label: "Phone", icon: "phone", cat: "Rich", color: "#14B8A6", desc: "A phone number." },
  { value: "url", label: "URL", icon: "link-2", cat: "Rich", color: "#6366F1", desc: "A web link." },
  { value: "user", label: "Person", icon: "user-circle-2", cat: "Rich", color: "#0B6BCB", desc: "A workspace member." },
  { value: "link", label: "Linked record", icon: "database", cat: "Rich", color: "#DC2626", desc: "A record from an ERPNext document." },
];

export const FIELD_TYPE_MAP = Object.fromEntries(
  FIELD_TYPES.map((t) => [t.value, t]),
);

/** Numeric-valued types — the only ones a conditional marker rule applies to. */
export const NUMERIC_FIELD_TYPES = new Set(["number", "currency", "percent", "rating"]);

/** icon/color/label lookup for a field type — mirrors what ProjectSettings.vue
 *  used to compute locally as fieldMeta(). */
export function fieldMeta(type) {
  return FIELD_TYPE_MAP[type] ?? null;
}

// ─── SCHEMA LOOKUPS ──────────────────────────────────────────────────────────

/**
 * Get field schema by ID from a project's custom_fields array.
 * Returns null if not found or archived.
 */
export function getFieldById(customFields, fieldId) {
  if (!Array.isArray(customFields)) return null;
  return customFields.find((f) => f.id === fieldId && !f.archived) ?? null;
}

/**
 * Get all active (non-archived) fields, sorted by order.
 */
export function getActiveFields(customFields) {
  if (!Array.isArray(customFields)) return [];
  return customFields
    .filter((f) => !f.archived)
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
}

/**
 * Get fields that should appear on Kanban cards.
 */
export function getCardFields(customFields) {
  return getActiveFields(customFields).filter((f) => f.show_in_card);
}

/**
 * Get fields that should appear as ListView columns.
 */
export function getListFields(customFields) {
  return getActiveFields(customFields).filter((f) => f.show_in_list);
}

// ─── OPTION RESOLUTION ───────────────────────────────────────────────────────

/**
 * Resolve a single option ID → label.
 * Falls back to the raw ID if not found (graceful degradation).
 */
export function resolveOptionLabel(field, optionId) {
  if (!field?.options || optionId === null || optionId === undefined) return "";
  return (
    field.options.find((o) => o.id === optionId)?.label ?? String(optionId)
  );
}

/**
 * Resolve an array of option IDs → labels.
 */
export function resolveOptionLabels(field, optionIds) {
  if (!Array.isArray(optionIds)) return [];
  return optionIds.map((id) => resolveOptionLabel(field, id));
}

// ─── DISPLAY VALUE ───────────────────────────────────────────────────────────

/**
 * Get human-readable display value for any field type.
 * Used in ListView cells and activity feed rendering.
 */
export function getDisplayValue(field, rawValue) {
  if (rawValue === null || rawValue === undefined || rawValue === "")
    return "—";

  switch (field.type) {
    case "select":
      return resolveOptionLabel(field, rawValue);

    case "multiselect":
      if (!Array.isArray(rawValue) || rawValue.length === 0) return "—";
      return resolveOptionLabels(field, rawValue).join(", ");

    case "checkbox":
      return rawValue ? "Yes" : "No";

    case "number": {
      const num = Number(rawValue);
      if (isNaN(num)) return String(rawValue);
      const formatted = num.toLocaleString();
      if (field.unit) return `${field.unit}${formatted}`;
      return formatted;
    }

    case "date":
      // Convert YYYY-MM-DD to locale display
      if (!rawValue) return "—";
      try {
        return new Date(rawValue + "T00:00:00").toLocaleDateString(undefined, {
          year: "numeric",
          month: "short",
          day: "numeric",
        });
      } catch {
        return rawValue;
      }

    case "url":
      return rawValue;

    default:
      return String(rawValue);
  }
}

// ─── CONDITIONAL MARKERS ─────────────────────────────────────────────────────

/**
 * Evaluate a field's conditional_rules against a value, in order — first
 * match wins (mirrors the top-to-bottom rule list in the editor UI).
 * Returns a hex color string, or null if no rule matches / not applicable.
 * Rule shape: { op: 'lte'|'between'|'gte', value, value2?, color }.
 */
export function resolveMarkerColor(field, rawValue) {
  if (!field || !NUMERIC_FIELD_TYPES.has(field.type)) return null;
  const rules = field.conditional_rules;
  if (!Array.isArray(rules) || !rules.length) return null;
  if (rawValue === null || rawValue === undefined || rawValue === "") return null;

  const num = Number(rawValue);
  if (Number.isNaN(num)) return null;

  for (const rule of rules) {
    const v = Number(rule.value);
    switch (rule.op) {
      case "lte":
        if (num <= v) return rule.color;
        break;
      case "gte":
        if (num >= v) return rule.color;
        break;
      case "between": {
        const v2 = Number(rule.value2);
        if (num >= v && num <= v2) return rule.color;
        break;
      }
    }
  }
  return null;
}

// ─── ACTIVITY FEED PARSING ───────────────────────────────────────────────────

/**
 * Parse a custom field change from activity log.
 * Activity old_value/new_value format: "cf:cf_xxxxxxxx:serialized_value"
 *
 * Returns { fieldId, rawValue } or null if not a custom field entry.
 */
export function parseCfActivityValue(value) {
  if (!value || !value.startsWith("cf:")) return null;
  const parts = value.split(":");
  // parts = ['cf', 'cf_xxxxxxxx', 'value_part', ...]
  // value may contain colons (e.g. URLs), so rejoin from index 2
  const fieldId = parts[1];
  const rawValue = parts.slice(2).join(":");
  return { fieldId, rawValue };
}

/**
 * Render a custom field activity entry as human-readable text.
 * e.g. "Phase changed from Planning to Design"
 */
export function renderCfActivity(customFields, oldEntry, newEntry) {
  const parsed =
    parseCfActivityValue(newEntry) ?? parseCfActivityValue(oldEntry);
  if (!parsed) return null;

  const field = getFieldById(customFields, parsed.fieldId);
  const fieldLabel = field?.label ?? parsed.fieldId;

  const renderVal = (entry) => {
    if (!entry) return "—";
    const p = parseCfActivityValue(entry);
    if (!p || !field) return p?.rawValue ?? "—";

    // Deserialize stored value back to typed value
    const raw = p.rawValue;
    if (field.type === "multiselect") {
      const ids = raw ? raw.split(",") : [];
      return resolveOptionLabels(field, ids).join(", ") || "—";
    }
    if (field.type === "select") return resolveOptionLabel(field, raw) || "—";
    if (field.type === "checkbox") return raw === "true" ? "Yes" : "No";
    return raw || "—";
  };

  return {
    field: fieldLabel,
    from: renderVal(oldEntry),
    to: renderVal(newEntry),
  };
}

// ─── VALIDATION ──────────────────────────────────────────────────────────────

/**
 * Client-side validation for a single custom field value.
 * Returns error string or null.
 * Mirrors the backend _validate_custom_field_values logic.
 */
export function validateFieldValue(field, value) {
  const isEmpty =
    value === null ||
    value === undefined ||
    value === "" ||
    (Array.isArray(value) && value.length === 0);

  if (field.required && isEmpty) {
    return `${field.label} is required`;
  }

  if (isEmpty) return null; // optional + empty = valid

  switch (field.type) {
    case "number": {
      const num = Number(value);
      if (isNaN(num)) return `${field.label} must be a number`;
      if (field.min !== null && field.min !== undefined && num < field.min)
        return `${field.label} must be at least ${field.min}`;
      if (field.max !== null && field.max !== undefined && num > field.max)
        return `${field.label} must be at most ${field.max}`;
      break;
    }

    case "date":
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value))
        return `${field.label} must be a valid date`;
      break;

    case "url":
      try {
        new URL(value);
      } catch {
        return `${field.label} must be a valid URL`;
      }
      break;

    case "select": {
      const validIds = (field.options ?? []).map((o) => o.id);
      if (!validIds.includes(value))
        return `${field.label}: invalid option selected`;
      break;
    }

    case "multiselect": {
      if (!Array.isArray(value)) return `${field.label} must be a list`;
      const validIds = new Set((field.options ?? []).map((o) => o.id));
      for (const v of value) {
        if (!validIds.has(v)) return `${field.label}: invalid option '${v}'`;
      }
      break;
    }
  }

  return null;
}

/**
 * Validate all custom field values against schema.
 * Returns { valid: bool, errors: { fieldId: errorString } }
 */
export function validateAllFields(customFields, values) {
  const errors = {};
  const activeFields = getActiveFields(customFields);

  for (const field of activeFields) {
    const error = validateFieldValue(field, values[field.id] ?? null);
    if (error) errors[field.id] = error;
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  };
}

// ─── DEFAULT VALUES ───────────────────────────────────────────────────────────

/**
 * Build a default custom_field_values object from project schema.
 * Used when creating a new issue.
 */
export function buildDefaultValues(customFields) {
  const values = {};
  for (const field of getActiveFields(customFields)) {
    if (field.default !== null && field.default !== undefined) {
      values[field.id] = field.default;
    }
  }
  return values;
}

// ─── SCHEMA MUTATION HELPERS ─────────────────────────────────────────────────

/**
 * Create a new field with safe defaults.
 */
export function createNewField(type = "text", order = 0) {
  return {
    id: generateFieldId(),
    label: "",
    type,
    required: false,
    placeholder: "",
    default: null,
    show_in_card: false,
    show_in_list: true,
    order,
    ...(type === "select" || type === "multiselect" ? { options: [] } : {}),
    ...(type === "number" ? { min: null, max: null, unit: "" } : {}),
  };
}

/**
 * Create a new select/multiselect option.
 */
export function createNewOption(label = "") {
  return { id: generateOptionId(), label };
}

/**
 * Reorder fields by dragging. Updates `order` property on each field.
 */
export function reorderFields(fields) {
  return fields.map((f, i) => ({ ...f, order: i }));
}

/**
 * Soft-delete a field (set archived: true).
 * Hard delete is never done — orphan cleanup handles value cleanup.
 */
export function archiveField(customFields, fieldId) {
  return customFields.map((f) =>
    f.id === fieldId ? { ...f, archived: true } : f,
  );
}
