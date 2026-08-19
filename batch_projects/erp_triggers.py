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
from frappe.utils import flt

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
#     This is the intended extension point: "when anything of type
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


def _row_value(row, field, default=None):
    if isinstance(row, dict):
        return row.get(field, default)
    return getattr(row, field, default)


def _sales_invoice_project_weights(name, header_project, items=None):
    """Return stable (ERP Project, net-share) pairs for one Sales Invoice.

    Sales Invoice Item.project is authoritative; blank item project inherits
    the header for legacy/single-project invoices. Net-line share is the only
    defensible basis for allocating invoice-level totals such as grand total,
    outstanding and a later Payment Entry allocation across projects.
    """
    if items is None:
        items = frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": name},
            fields=["project", "net_amount"],
            order_by="idx asc",
        )

    totals = {}
    order = []

    for item in items or []:
        erp_project = _row_value(item, "project") or header_project
        if not erp_project:
            continue
        if erp_project not in totals:
            totals[erp_project] = 0.0
            order.append(erp_project)
        totals[erp_project] += flt(_row_value(item, "net_amount") or 0)

    if not totals:
        return [(header_project, 1.0)] if header_project else []

    denominator = sum(totals.values())
    if abs(denominator) <= 1e-12:
        # A zero-net mixed invoice has no financially meaningful denominator
        # for fan-out. Preserve the historical header attribution rather than
        # inventing an arbitrary split or duplicating the whole amount.
        return [(header_project, 1.0)] if header_project else []

    return [
        (erp_project, totals[erp_project] / denominator)
        for erp_project in order
    ]


def _apportion(total, project_weights):
    """Allocate a currency total while preserving its rounded sum exactly."""
    total = round(flt(total), 2)
    if not project_weights:
        return {}

    allocated = {}
    remaining = total

    for idx, (erp_project, weight) in enumerate(project_weights):
        if idx == len(project_weights) - 1:
            value = remaining
        else:
            value = round(total * weight, 2)
            remaining = round(remaining - value, 2)
        allocated[erp_project] = value

    return allocated


def on_sales_invoice_submit(doc, method=None):
    project_weights = _sales_invoice_project_weights(
        doc.name,
        doc.project,
        items=doc.items,
    )
    if not project_weights:
        return

    amounts = _apportion(doc.grand_total, project_weights)
    outstanding = _apportion(doc.outstanding_amount, project_weights)

    from batch_projects.events import emit
    for erp_project, _weight in project_weights:
        bp_project = _bp_project_for(
            "Sales Invoice",
            doc.name,
            erp_project,
        )
        if not bp_project:
            continue

        emit("erp.invoice_submitted", {
            "project": bp_project,
            "invoice": doc.name,
            "customer": doc.customer,
            "amount": amounts.get(erp_project, 0.0),
            "outstanding": outstanding.get(erp_project, 0.0),
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
    """Fan each Sales Invoice allocation out to its contributing BP Projects.

    A shared invoice is one legal document but several project financial
    claims. Payment Entry.references carries only the invoice-level allocation,
    so use the same Sales Invoice Item net-share model as invoice submission to
    avoid assigning the whole payment to the arbitrary header project.
    """
    invoice_refs = [
        r for r in (doc.references or [])
        if r.reference_doctype == "Sales Invoice"
    ]
    if not invoice_refs:
        return

    from batch_projects.events import emit

    for ref in invoice_refs:
        si = frappe.db.get_value(
            "Sales Invoice",
            ref.reference_name,
            [
                "project",
                "customer",
                "currency",
                "outstanding_amount",
            ],
            as_dict=True,
        )
        if not si:
            continue

        project_weights = _sales_invoice_project_weights(
            ref.reference_name,
            si.project,
        )
        if not project_weights:
            continue

        amounts = _apportion(
            ref.allocated_amount,
            project_weights,
        )
        outstanding = _apportion(
            si.outstanding_amount,
            project_weights,
        )

        for erp_project, _weight in project_weights:
            bp_project = _bp_project_for(
                "Sales Invoice",
                ref.reference_name,
                erp_project,
            )
            if not bp_project:
                continue

            emit("erp.payment_received", {
                "project": bp_project,
                "invoice": ref.reference_name,
                "payment_entry": doc.name,
                "customer": si.customer,
                "amount": amounts.get(erp_project, 0.0),
                "outstanding": outstanding.get(erp_project, 0.0),
                "currency": si.currency,
            })
