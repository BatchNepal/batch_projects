import { reactive } from 'vue'
import { getErpDoctypeFields, getErpDoctypeFieldsReadonly, getErpDocumentLabel } from '@/utils/api'

// Doctypes search_erp_documents (board.py) actually allows — mirrors
// board.py's _ERP_SEARCH_DOCTYPES exactly. A Link field pointing anywhere
// else falls back to free text rather than a Combobox that will always 400.
export const SEARCHABLE_LINK_DOCTYPES = new Set([
  'Sales Order', 'Purchase Order', 'Sales Invoice', 'Purchase Invoice',
  'Project', 'Customer', 'Supplier', 'Lead', 'Opportunity',
  'Expense Claim', 'Timesheet', 'Delivery Note', 'Stock Entry',
  'Payment Entry', 'Journal Entry', 'Work Order', 'Quotation', 'ToDo',
])
export function searchableLinkDoctype(dt) { return !!dt && SEARCHABLE_LINK_DOCTYPES.has(dt) }

// Module-level (not per-call) caches — a doctype's schema/a document's title
// don't change while the app is open, so every consumer across the whole
// session shares one fetch instead of each component instance re-asking.
// Two separate field-metadata caches since write/read are scoped to
// different backend doctype whitelists (see board.py's write-vs-read
// boundary comment on get_erp_doctype_fields_readonly) — a doctype allowed
// in one isn't necessarily allowed, or even meaningful, in the other.
const writeCache = reactive({}) // doctype -> [{fieldname,label,fieldtype,options}]
const readCache  = reactive({}) // doctype -> [{fieldname,label,fieldtype,options}]
const labelCache = reactive({}) // "doctype:name" -> label

/** The ONE place both automation builders (flat editor + canvas) resolve
 * ERPNext doctype field metadata, Link search-target validity, and Link
 * display labels — was three ad-hoc, drifting copies before this. */
export function useErpDoctypeFields() {
  function erpFieldsFor(doctype) {
    if (!doctype) return []
    if (!writeCache[doctype]) {
      writeCache[doctype] = []
      getErpDoctypeFields(doctype).then(rows => { writeCache[doctype] = rows || [] }).catch(() => {})
    }
    return writeCache[doctype]
  }
  function erpFieldMeta(doctype, fieldname) {
    return erpFieldsFor(doctype).find(f => f.fieldname === fieldname) || null
  }

  // Read-scoped variant (wider doctype whitelist) — condition builders
  // (trigger.doc_event) rather than the "Update ERPNext Document" write
  // path. Degrades to an empty list for a doctype outside even the read
  // whitelist (e.g. a custom doctype typed into doc_event's allow_custom
  // field) — the condition field picker's own allow-create still lets the
  // user type a fieldname by hand in that case.
  function erpFieldsForRead(doctype) {
    if (!doctype) return []
    if (!readCache[doctype]) {
      readCache[doctype] = []
      getErpDoctypeFieldsReadonly(doctype).then(rows => { readCache[doctype] = rows || [] }).catch(() => {})
    }
    return readCache[doctype]
  }

  // Resolves + caches a display label for an ALREADY-KNOWN Link value — the
  // piece search_erp_documents alone can't do (it only labels its own
  // search hits). Returns '' until resolved; feed into Combobox's
  // :model-label so a saved rule's Link value shows its real title
  // immediately instead of the raw docname.
  function erpDocLabel(doctype, name) {
    if (!doctype || !name) return ''
    const key = `${doctype}:${name}`
    if (!(key in labelCache)) {
      labelCache[key] = ''
      getErpDocumentLabel(doctype, name)
        .then(r => { labelCache[key] = r?.label || name })
        .catch(() => { labelCache[key] = name })
    }
    return labelCache[key]
  }

  return { erpFieldsFor, erpFieldMeta, erpFieldsForRead, erpDocLabel, searchableLinkDoctype }
}
