"""Concurrency-safe reservation of Expense Claim Detail invoice sources.

A billable Expense Claim Detail is a financial source. BatchProjects may
create at most one live Sales Invoice claimant for that source.

Lock order for this path is intentionally explicit:

    Expense Claim parent(s)
        -> Expense Claim Detail source row(s)
        -> Expense Claim Type row(s)
        -> referenced Sales Invoice row(s)

Parent rows are locked first to avoid opposing the normal Frappe document
lifecycle, which operates from the parent document into its child rows.

The pre-lock candidate query in generate_expense_invoice() is discovery only.
After a wait on FOR UPDATE, this module returns authoritative current rows and
the caller MUST bill from those returned rows rather than its older snapshot.
"""

import frappe


def _validation_error(message):
    raise frappe.ValidationError(message)


def _clean_detail_names(detail_names):
    return sorted({
        str(value).strip()
        for value in (detail_names or [])
        if value is not None and str(value).strip()
    })


def _discover_parent_names(db, detail_names):
    """Non-locking discovery used only to establish parent-first lock order."""
    if not detail_names:
        return {}

    rows = db.sql(
        """
        SELECT
            name,
            parent
        FROM `tabExpense Claim Detail`
        WHERE name IN %(details)s
        ORDER BY name ASC
        """,
        {"details": tuple(detail_names)},
        as_dict=True,
    )

    return {
        row.name: row.parent
        for row in rows
    }


def _lock_parent_rows(db, parent_names):
    if not parent_names:
        return []

    return db.sql(
        """
        SELECT
            name,
            project,
            docstatus,
            posting_date
        FROM `tabExpense Claim`
        WHERE name IN %(parents)s
        ORDER BY name ASC
        FOR UPDATE
        """,
        {"parents": tuple(sorted(parent_names))},
        as_dict=True,
    )


def _lock_detail_rows(db, detail_names):
    if not detail_names:
        return []

    return db.sql(
        """
        SELECT
            name,
            parent,
            docstatus AS source_docstatus,
            expense_type,
            sanctioned_amount,
            description,
            custom_is_billable,
            custom_sales_invoice
        FROM `tabExpense Claim Detail`
        WHERE name IN %(details)s
        ORDER BY name ASC
        FOR UPDATE
        """,
        {"details": tuple(sorted(detail_names))},
        as_dict=True,
    )


def _lock_type_rows(db, expense_types):
    if not expense_types:
        return []

    return db.sql(
        """
        SELECT
            name,
            IFNULL(custom_reinvoice_policy, 'At Cost') AS policy,
            custom_markup_percent AS markup_percent
        FROM `tabExpense Claim Type`
        WHERE name IN %(types)s
        ORDER BY name ASC
        FOR UPDATE
        """,
        {"types": tuple(sorted(expense_types))},
        as_dict=True,
    )


def _lock_invoice_rows(db, invoices):
    if not invoices:
        return []

    return db.sql(
        """
        SELECT
            name,
            docstatus
        FROM `tabSales Invoice`
        WHERE name IN %(invoices)s
        ORDER BY name ASC
        FOR UPDATE
        """,
        {"invoices": tuple(sorted(invoices))},
        as_dict=True,
    )


def _guard_expense_claim_details_with_db(
    db,
    detail_names,
    erp_project,
):
    """Lock and return authoritative currently-invoiceable expense rows.

    `erp_project` is the ERPNext Project expected by the BP Project that is
    generating the invoice.

    Returned rows deliberately contain every financial field consumed by
    generate_expense_invoice(), so the caller never has to fall back to the
    pre-lock candidate snapshot after waiting for a source mutex.
    """
    names = _clean_detail_names(detail_names)

    if not names:
        return []

    discovered_parent_by_detail = (
        _discover_parent_names(
            db,
            names,
        )
    )

    parent_names = sorted({
        parent
        for parent in discovered_parent_by_detail.values()
        if parent
    })

    parent_rows = _lock_parent_rows(
        db,
        parent_names,
    )

    parent_by_name = {
        row.name: row
        for row in parent_rows
    }

    detail_rows = _lock_detail_rows(
        db,
        names,
    )

    detail_by_name = {
        row.name: row
        for row in detail_rows
    }

    missing = [
        name
        for name in names
        if name not in detail_by_name
    ]

    if missing:
        _validation_error(
            "These Expense Claim Detail sources no longer exist: "
            + ", ".join(missing)
            + ". Refresh the Money tab and try again."
        )

    changed_parent = []

    for name in names:
        row = detail_by_name[name]
        discovered_parent = (
            discovered_parent_by_detail.get(name)
        )

        if (
            not discovered_parent
            or row.parent != discovered_parent
            or row.parent not in parent_by_name
        ):
            changed_parent.append(name)

    if changed_parent:
        _validation_error(
            "These expense sources changed while the invoice was being "
            "prepared: "
            + ", ".join(changed_parent)
            + ". Refresh the Money tab and try again."
        )

    invalid = []

    for name in names:
        row = detail_by_name[name]
        parent = parent_by_name[row.parent]

        if int(parent.docstatus or 0) != 1:
            invalid.append(
                f"{name} (Expense Claim is no longer submitted)"
            )
            continue

        if int(row.source_docstatus or 0) != 1:
            invalid.append(
                f"{name} (expense source is no longer submitted)"
            )
            continue

        if parent.project != erp_project:
            invalid.append(
                f"{name} (expense source moved to another project)"
            )
            continue

        if int(row.custom_is_billable or 0) != 1:
            invalid.append(
                f"{name} (expense is no longer marked billable)"
            )

    if invalid:
        _validation_error(
            "These Expense Claim Detail sources are no longer invoiceable: "
            + ", ".join(invalid)
            + ". Refresh the Money tab before creating the invoice."
        )

    expense_types = sorted({
        row.expense_type
        for row in detail_rows
        if row.expense_type
    })

    type_rows = _lock_type_rows(
        db,
        expense_types,
    )

    type_by_name = {
        row.name: row
        for row in type_rows
    }

    blocked_policy = []

    for row in detail_rows:
        policy = (
            type_by_name.get(row.expense_type)
            if row.expense_type
            else None
        )

        resolved_policy = (
            policy.policy
            if policy
            else "At Cost"
        )

        if resolved_policy == "Not Billable":
            blocked_policy.append(row.name)

    if blocked_policy:
        _validation_error(
            "These expense sources are now configured as Not Billable: "
            + ", ".join(sorted(blocked_policy))
            + ". Refresh the Money tab before creating the invoice."
        )

    pointers = sorted({
        (row.custom_sales_invoice or "").strip()
        for row in detail_rows
        if (row.custom_sales_invoice or "").strip()
    })

    invoice_rows = _lock_invoice_rows(
        db,
        pointers,
    )

    invoice_by_name = {
        row.name: row
        for row in invoice_rows
    }

    live_claims = []

    for row in detail_rows:
        pointer = (
            row.custom_sales_invoice or ""
        ).strip()

        if not pointer:
            continue

        invoice = invoice_by_name.get(pointer)

        # A missing invoice or a cancelled invoice releases the source, which
        # preserves the existing reinvoicing policy.
        if (
            invoice is not None
            and int(invoice.docstatus or 0) < 2
        ):
            live_claims.append(
                (row.name, pointer)
            )

    if live_claims:
        details = ", ".join(
            f"{detail} → {invoice}"
            for detail, invoice in live_claims
        )

        _validation_error(
            "These expense sources are already reserved by a live "
            "Sales Invoice: "
            + details
            + ". Delete/cancel that invoice or refresh before trying again."
        )

    authoritative = []

    for name in names:
        row = detail_by_name[name]
        parent = parent_by_name[row.parent]
        type_row = (
            type_by_name.get(row.expense_type)
            if row.expense_type
            else None
        )

        authoritative.append(
            frappe._dict({
                "name": row.name,
                "expense_claim": row.parent,
                "expense_type": row.expense_type,
                "sanctioned_amount": row.sanctioned_amount,
                "description": row.description,
                "posting_date": parent.posting_date,
                "policy": (
                    type_row.policy
                    if type_row
                    else "At Cost"
                ),
                "markup_percent": (
                    type_row.markup_percent
                    if type_row
                    else 0
                ),
            })
        )

    return authoritative


def guard_expense_claim_details(
    detail_names,
    erp_project,
):
    """Reserve expense sources in the current Frappe transaction."""
    return _guard_expense_claim_details_with_db(
        frappe.db,
        detail_names,
        erp_project,
    )
