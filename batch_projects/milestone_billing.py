"""Authoritative BP Milestone ↔ ERPNext Sales Invoice lifecycle.

The milestone is delivery state; ERPNext Sales Invoice docstatus is financial
authority.

Persisted BP Milestone.invoice_status means:

    Not Invoiced
        no live draft/submitted Sales Invoice currently claims the milestone

    Draft
        the linked Sales Invoice exists with docstatus = 0

    Invoiced
        the linked Sales Invoice exists with docstatus = 1

Cancelled Sales Invoices reopen the milestone but remain linked so ERPNext's
amendment lineage can be followed. Deleted drafts clear the pointer unless
they were amendments, in which case the cancelled predecessor is restored.

Credit notes / Sales Invoice Returns are deliberately outside this model:
ERPNext supports partial returns, so "Credited" requires amount-aware
semantics rather than another boolean-like flag.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt


NOT_INVOICED = "Not Invoiced"
DRAFT = "Draft"
INVOICED = "Invoiced"

ACTIVE_STATUSES = frozenset({DRAFT, INVOICED})

# Tolerate machine-level floating-point noise only. Material over-reservation
# must still fail closed.
PERCENT_CAPACITY_EPSILON = 1e-9


def _database(db=None):
    return db or frappe.db


def _lock_project(db, project):
    rows = db.sql(
        """
        SELECT
            name,
            project_name,
            erpnext_project,
            client,
            company,
            currency,
            budget_amount
        FROM `tabBP Project`
        WHERE name = %(name)s
        FOR UPDATE
        """,
        {"name": project},
        as_dict=True,
    )

    if not rows:
        frappe.throw(
            f"Batch Project '{project}' no longer exists. Refresh and try again."
        )

    return rows[0]


def _lock_milestone(db, milestone, project=None):
    params = {"name": milestone}
    project_clause = ""

    if project:
        params["project"] = project
        project_clause = "AND project = %(project)s"

    rows = db.sql(
        f"""
        SELECT
            name,
            project,
            title,
            status,
            billing_type,
            invoice_amount,
            invoice_percent,
            invoice_status,
            sales_invoice
        FROM `tabBP Milestone`
        WHERE name = %(name)s
          {project_clause}
        FOR UPDATE
        """,
        params,
        as_dict=True,
    )

    if not rows:
        frappe.throw(
            f"Milestone '{milestone}' changed or no longer exists. "
            "Refresh and try again."
        )

    return rows[0]


def lock_generation_scope(project, milestone, db=None):
    """Serialize milestone invoice generation in deterministic order.

    The project lock is intentionally first. Different percentage milestones
    on the same project must serialize around the shared 100%-budget invariant.

    Lock order everywhere in this generation path:

        BP Project → BP Milestone
    """
    db = _database(db)

    project_row = _lock_project(
        db,
        project,
    )
    milestone_row = _lock_milestone(
        db,
        milestone,
        project=project,
    )

    return project_row, milestone_row


def reserved_percent(project, exclude_milestone=None, db=None):
    """Return the project's current live percentage reservation.

    `invoice_status` is the transactionally-maintained projection of ERPNext
    Sales Invoice lifecycle. This query deliberately uses FOR UPDATE rather
    than a plain aggregate so a transaction that waited behind another
    generator sees the newly committed Draft/Invoiced milestone instead of
    its older repeatable-read snapshot.

    Caller owns the BP Project row first, so different generation/amendment
    transactions serialize before these sibling milestone locks are taken.
    """
    db = _database(db)

    params = {
        "project": project,
        "exclude": exclude_milestone or "",
    }

    rows = db.sql(
        """
        SELECT
            name,
            invoice_percent
        FROM `tabBP Milestone`
        WHERE project = %(project)s
          AND billing_type = 'Percent of Budget'
          AND invoice_status IN ('Draft', 'Invoiced')
          AND (%(exclude)s = '' OR name != %(exclude)s)
        ORDER BY name ASC
        FOR UPDATE
        """,
        params,
        as_dict=True,
    )

    return sum(
        flt(row.invoice_percent)
        for row in rows
    )


def assert_percent_capacity(
    project,
    milestone,
    invoice_percent,
    db=None,
):
    """Refuse a percentage reservation above the project's 100% ceiling.

    Caller must already own the BP Project row lock.
    """
    already = reserved_percent(
        project,
        exclude_milestone=milestone,
        db=db,
    )

    requested = flt(invoice_percent)
    total = already + requested

    if total > 100 + PERCENT_CAPACITY_EPSILON:
        frappe.throw(
            f"Invoicing this milestone at {requested}% would bring this "
            f"project's live milestone invoice reservations to {total}%, "
            f"over its 100% budget ({already}% already reserved by Draft "
            "or Invoiced milestones)."
        )

    return already


def assert_milestone_deletable(milestone, db=None):
    """Refuse deletion while the current locked milestone has a live invoice."""
    db = _database(db)

    row = _lock_milestone(
        db,
        milestone,
    )

    if row.invoice_status in ACTIVE_STATUSES:
        frappe.throw(
            f"Milestone '{row.title}' cannot be deleted while "
            f"Sales Invoice {row.sales_invoice} is {row.invoice_status}. "
            "Delete the draft or cancel the submitted invoice first."
        )

    return row


def invoice_state(invoice, db=None):
    """Derive canonical milestone state from ERPNext Sales Invoice docstatus."""
    db = _database(db)

    invoice = (invoice or "").strip()
    if not invoice:
        return NOT_INVOICED, None

    docstatus = db.get_value(
        "Sales Invoice",
        invoice,
        "docstatus",
    )

    # Deleted / dangling pointer.
    if docstatus is None:
        return NOT_INVOICED, None

    docstatus = int(docstatus)

    if docstatus == 0:
        return DRAFT, invoice

    if docstatus == 1:
        return INVOICED, invoice

    # Cancelled invoice remains the audit/amendment predecessor.
    return NOT_INVOICED, invoice


def _set_milestone_state(
    db,
    milestone,
    status,
    invoice,
):
    db.set_value(
        "BP Milestone",
        milestone,
        {
            "invoice_status": status,
            "sales_invoice": invoice,
        },
        update_modified=False,
    )


def reconcile_milestone(milestone, db=None):
    """Repair one milestone from ERPNext's current authoritative state.

    Idempotent. Locks the exact milestone row before inspecting/updating it.
    """
    db = _database(db)
    row = _lock_milestone(db, milestone)

    status, invoice = invoice_state(
        row.sales_invoice,
        db=db,
    )

    if (
        row.invoice_status != status
        or (row.sales_invoice or None) != invoice
    ):
        _set_milestone_state(
            db,
            row.name,
            status,
            invoice,
        )

    return frappe._dict({
        "name": row.name,
        "invoice_status": status,
        "sales_invoice": invoice,
    })


def reconcile_all_milestones(db=None):
    """Migration/recovery reconciler for existing milestone rows."""
    db = _database(db)

    names = db.get_all(
        "BP Milestone",
        pluck="name",
        order_by="name asc",
    )

    for name in names:
        reconcile_milestone(
            name,
            db=db,
        )

    return len(names)


def _locked_current_milestone(
    db,
    invoice,
):
    """Find milestone by invoice, then lock exact row and re-check pointer.

    The first lookup is only discovery. The post-lock pointer equality is the
    authority, preventing a stale ERPNext lifecycle event from overwriting a
    newer milestone invoice claim.
    """
    invoice = (invoice or "").strip()
    if not invoice:
        return None

    milestone = db.get_value(
        "BP Milestone",
        {"sales_invoice": invoice},
        "name",
    )
    if not milestone:
        return None

    rows = db.sql(
        """
        SELECT
            name,
            invoice_status,
            sales_invoice
        FROM `tabBP Milestone`
        WHERE name = %(name)s
        FOR UPDATE
        """,
        {"name": milestone},
        as_dict=True,
    )

    if not rows:
        return None

    row = rows[0]

    # Discovery may have raced a newer invoice assignment.
    if (row.sales_invoice or "").strip() != invoice:
        return None

    return row


def _on_sales_invoice_submit_with_db(doc, db):
    row = _locked_current_milestone(
        db,
        doc.name,
    )
    if not row:
        return False

    _set_milestone_state(
        db,
        row.name,
        INVOICED,
        doc.name,
    )
    return True


def _on_sales_invoice_cancel_with_db(doc, db):
    row = _locked_current_milestone(
        db,
        doc.name,
    )
    if not row:
        return False

    # Keep the cancelled invoice pointer. ERPNext's amendment will carry
    # amended_from=<this invoice>, allowing after_insert below to move the
    # milestone to the new draft.
    _set_milestone_state(
        db,
        row.name,
        NOT_INVOICED,
        doc.name,
    )
    return True


def _on_sales_invoice_trash_with_db(doc, db):
    row = _locked_current_milestone(
        db,
        doc.name,
    )
    if not row:
        return False

    predecessor = (
        (getattr(doc, "amended_from", None) or "").strip()
        or None
    )

    _set_milestone_state(
        db,
        row.name,
        NOT_INVOICED,
        predecessor,
    )
    return True


def _on_sales_invoice_after_insert_with_db(doc, db):
    predecessor = (
        (getattr(doc, "amended_from", None) or "").strip()
    )
    if not predecessor:
        return False

    # Discovery only. The exact pointer is re-verified after the same
    # deterministic lock order used by generate_milestone_invoice:
    #
    #     BP Project -> BP Milestone
    #
    # This matters because cancellation releases percentage capacity. An
    # amendment is allowed to reclaim it only if capacity still exists after
    # any other milestone reservations that committed in the meantime.
    discovery = db.get_value(
        "BP Milestone",
        {"sales_invoice": predecessor},
        ["name", "project"],
        as_dict=True,
    )
    if not discovery:
        return False

    _lock_project(
        db,
        discovery.project,
    )

    row = _lock_milestone(
        db,
        discovery.name,
        project=discovery.project,
    )

    # Discovery may have raced a fresh BP-generated invoice or another
    # amendment. A stale amendment event may never steal the pointer.
    if (row.sales_invoice or "").strip() != predecessor:
        return False

    if row.billing_type == "Percent of Budget":
        assert_percent_capacity(
            row.project,
            row.name,
            row.invoice_percent,
            db=db,
        )

    _set_milestone_state(
        db,
        row.name,
        DRAFT,
        doc.name,
    )
    return True


def on_sales_invoice_after_insert(doc, method=None):
    _on_sales_invoice_after_insert_with_db(
        doc,
        frappe.db,
    )


def on_sales_invoice_submit(doc, method=None):
    # Financial milestone state first, then preserve the existing automation
    # event behavior behind the same Sales Invoice hook.
    _on_sales_invoice_submit_with_db(
        doc,
        frappe.db,
    )

    from batch_projects.erp_triggers import (
        on_sales_invoice_submit as emit_invoice_submitted,
    )

    emit_invoice_submitted(
        doc,
        method,
    )


def on_sales_invoice_cancel(doc, method=None):
    _on_sales_invoice_cancel_with_db(
        doc,
        frappe.db,
    )


def on_sales_invoice_trash(doc, method=None):
    _on_sales_invoice_trash_with_db(
        doc,
        frappe.db,
    )
