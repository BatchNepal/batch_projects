"""
batch_projects/erp_triggers.py
───────────────────────────────
closes the one-way street: automations could WRITE to ERPNext
("Update ERPNext Document") but never HEAR from it. These doc_events fire
`erp.*` events onto the SAME bus every task/comment/schedule trigger already
rides (`events.emit()`) so automations/notifications/realtime pick them up
for free — no parallel dispatch mechanism.

Tenancy is the whole security model here: an ERPNext doc that doesn't
resolve to a BP Project is a silent no-op, never an error, never a chance to
leak into an unrelated project's rules. Resolution reuses erp_link.py's own
`_tenant_ok` verbatim rather than re-deriving a second, subtly different
check (see erp_link.py module docstring for why that boundary is sacred).
"""

import frappe

from batch_projects.api.erp_link import _tenant_ok

# ─── Generic doc-event trigger ──────────────────────────────────────────────
#
# The 4 handlers below this block are hand-wired to one specific ERPNext
# doctype each — real, but narrow: any doctype not on that list (Purchase
# Order, Quotation, a customer's own custom doctype, anything) had no path
# onto the automation event bus at all. `on_any_doctype_event` widens this
# via a "*" wildcard doc_events hook (hooks.py) instead of hand-wiring more
# doctypes one at a time.
#
# Two deliberate boundaries, matching how workspace-vs-project scope already
# works everywhere else in this app:
#   - WORKSPACE-scope rules can match ANY doctype's lifecycle event — no
#     project resolution needed (payload carries project=None, same as an
#     external.webhook event — see run_for_event's project=None handling).
#     This is the intended n8n-style extension point: "when anything of type
#     X happens anywhere, do Y."
#   - PROJECT-scope rules only apply to the 4 hand-wired doctypes above,
#     which already know how to resolve a BP Project via _tenant_ok. Generic
#     project resolution for an ARBITRARY doctype (which field even points
#     at a project?) is a per-doctype problem this hook doesn't try to solve
#     — a project-scoped automation for a 5th ERPNext doctype still wants a
#     purpose-built handler like the ones below, not a guess.
#
# Performance: this fires on every after_insert/on_update/on_submit/
# on_cancel/on_trash for EVERY doctype site-wide. _any_doc_event_rules_exist
# is a single short-TTL cached boolean — the overwhelming common case (zero
# erp.doc_event rules configured) costs one cache read and returns, no DB
# query, no event build, no condition evaluation.
_DOC_EVENT_CACHE_KEY = "bp_any_doc_event_rules_exist"
_DOC_EVENT_CACHE_TTL = 60  # seconds — acceptable staleness for "did an admin just add a rule"

# Never fire for batch_projects' own doctypes (already have dedicated,
# richer event emission — this would just be noisy duplication) or for a
# short list of pathologically high-frequency Frappe system doctypes where
# firing on every write would be pure overhead with no plausible automation
# use case.
_SKIP_DOCTYPES = frozenset({
    "BP Task", "BP Project", "BP Automation Rule", "BP Automation Run",
    "BP Webhook Token", "BP Activity", "BP Task Watcher",
    "Error Log", "Activity Log", "Access Log", "Version", "DocShare",
    "Notification Log", "Email Queue", "RQ Job", "Route History",
})


def _any_doc_event_rules_exist() -> bool:
    cached = frappe.cache().get_value(_DOC_EVENT_CACHE_KEY)
    if cached is not None:
        return cached == "1"
    exists = bool(frappe.db.exists(
        "BP Automation Rule", {"trigger_event": "erp.doc_event", "is_active": 1}
    ))
    frappe.cache().set_value(_DOC_EVENT_CACHE_KEY, "1" if exists else "0", expires_in_sec=_DOC_EVENT_CACHE_TTL)
    return exists


def on_any_doctype_event(doc, method=None):
    """Wildcard doc_events handler — see module docstring above."""
    if doc.doctype in _SKIP_DOCTYPES:
        return
    if not _any_doc_event_rules_exist():
        return

    from batch_projects.events import emit
    emit("erp.doc_event", {
        "project": None,  # see module docstring — no generic project resolution
        "doctype": doc.doctype,
        "docname": doc.name,
        "erp_event": method,  # after_insert | on_update | on_submit | on_cancel | on_trash
    })


def _bp_project_for(doctype: str, name: str, erp_project: str):
    """ERPNext doc's own `project` field -> the BP Project claiming it, or
    None (never throws) if either isn't linked. `erp_project` is the value
    already read off the doc by the caller; re-verified here via the same
    `_tenant_ok` the Money drawer uses, so there is exactly one tenancy
    implementation in the codebase, not two."""
    if not erp_project:
        return None
    bp_project = frappe.db.get_value("BP Project", {"erpnext_project": erp_project}, "name")
    if not bp_project:
        return None
    if not _tenant_ok(doctype, name, erp_project):
        return None
    return bp_project


def on_sales_invoice_submit(doc, method=None):
    bp_project = _bp_project_for("Sales Invoice", doc.name, doc.project)
    if not bp_project:
        return

    from batch_projects.events import emit
    emit("erp.invoice_submitted", {
        "project": bp_project,
        "invoice": doc.name,
        "customer": doc.customer,
        "amount": doc.grand_total,
        "outstanding": doc.outstanding_amount,
        "currency": doc.currency,
    })


def on_sales_order_submit(doc, method=None):
    bp_project = _bp_project_for("Sales Order", doc.name, doc.project)
    if not bp_project:
        return

    from batch_projects.events import emit
    emit("erp.so_confirmed", {
        "project": bp_project,
        "sales_order": doc.name,
        "customer": doc.customer,
        "amount": doc.grand_total,
        "currency": doc.currency,
    })


def on_payment_entry_submit(doc, method=None):
    """Fires once per referenced Sales Invoice that resolves to a BP Project
    (a payment can be allocated across several invoices/customers). Payload
    carries the invoice's post-payment `outstanding` so a rule condition can
    express "if outstanding = 0" with the existing matcher — no new op, no
    separate "invoice_paid" event needed."""
    invoice_refs = [r for r in (doc.references or []) if r.reference_doctype == "Sales Invoice"]
    if not invoice_refs:
        return

    from batch_projects.events import emit
    for ref in invoice_refs:
        si = frappe.db.get_value(
            "Sales Invoice", ref.reference_name,
            ["project", "customer", "currency", "outstanding_amount"], as_dict=True,
        )
        if not si:
            continue
        bp_project = _bp_project_for("Sales Invoice", ref.reference_name, si.project)
        if not bp_project:
            continue
        emit("erp.payment_received", {
            "project": bp_project,
            "invoice": ref.reference_name,
            "payment_entry": doc.name,
            "customer": si.customer,
            "amount": ref.allocated_amount,
            "outstanding": si.outstanding_amount,
            "currency": si.currency,
        })
