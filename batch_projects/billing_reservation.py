"""Concurrency-safe reservation of ERPNext Timesheet Detail billing sources.

A submitted Timesheet Detail is the financial source being invoiced.

ERPNext only stamps Timesheet Detail.sales_invoice when a Sales Invoice is
submitted. Draft Sales Invoices therefore need their own concurrency guard:
without serialization, two transactions can both observe an unbilled source
and create two draft claimants.

The source row itself is the transaction mutex:

1. lock exact Timesheet Detail rows in deterministic name order;
2. perform current-state billed/live-draft checks;
3. keep those locks until the surrounding transaction inserts/commits the
   Sales Invoice.

No persistent BP reservation table is required. A live draft's native
Sales Invoice Timesheet rows become the durable reservation after commit.
"""

from collections import Counter

import frappe


def _validation_error(message):
    raise frappe.ValidationError(message)


def _clean_detail_names(detail_names):
    """Return non-empty normalized names while preserving multiplicity."""
    cleaned = []

    for raw in detail_names or []:
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            cleaned.append(value)

    return cleaned


def _duplicate_detail_names(cleaned):
    return sorted(
        name
        for name, count in Counter(cleaned).items()
        if count > 1
    )


def _raise_duplicate_sources(duplicates):
    if duplicates:
        _validation_error(
            "The same Timesheet Detail appears more than once on this "
            "Sales Invoice: " + ", ".join(duplicates)
        )


def _normalize_detail_names(detail_names):
    """Strict deterministic normalization for BP-owned billing sources."""
    cleaned = _clean_detail_names(detail_names)
    _raise_duplicate_sources(
        _duplicate_detail_names(cleaned)
    )
    return sorted(cleaned)


def _lock_source_rows(db, names):
    """Lock source rows using a current read in deterministic order."""
    if not names:
        return [], []

    rows = db.sql(
        """
        SELECT
            tsd.name,
            tsd.parent,
            tsd.project,
            tsd.custom_bp_task,
            tsd.sales_invoice
        FROM `tabTimesheet Detail` tsd
        WHERE tsd.name IN %(details)s
        ORDER BY tsd.name ASC
        FOR UPDATE
        """,
        {"details": tuple(names)},
        as_dict=True,
    )

    by_name = {row.name: row for row in rows}
    ordered = [by_name[name] for name in names if name in by_name]
    missing = [name for name in names if name not in by_name]

    return ordered, missing


def _bp_linked_source_names(db, rows):
    """Return rows owned by BatchProjects without affecting unrelated SI rows.

    A row is BP-owned when:
    - it explicitly carries custom_bp_task, or
    - its ERPNext Project is linked from a BP Project.

    The task path deliberately avoids a second lookup.
    """
    linked = {
        row.name
        for row in rows
        if (row.custom_bp_task or "").strip()
    }

    unresolved_projects = sorted({
        row.project
        for row in rows
        if row.name not in linked and row.project
    })

    if unresolved_projects:
        project_rows = db.sql(
            """
            SELECT DISTINCT erpnext_project
            FROM `tabBP Project`
            WHERE erpnext_project IN %(projects)s
            """,
            {"projects": tuple(unresolved_projects)},
            as_dict=True,
        )

        bp_projects = {
            row.erpnext_project
            for row in project_rows
            if row.erpnext_project
        }

        linked.update(
            row.name
            for row in rows
            if row.project in bp_projects
        )

    return linked


def _live_claims(db, detail_names, current_invoice=None):
    """Current/locking read of native live Sales Invoice claimants.

    A normal repeatable-read SELECT is insufficient after waiting for a
    Timesheet Detail row lock: it could keep using an older transaction
    snapshot and miss a draft that committed while this transaction waited.

    FOR UPDATE forces a current read. The migration shipped with this feature
    indexes timesheet_detail so the lock/read remains narrow.
    """
    if not detail_names:
        return []

    params = {
        "details": tuple(detail_names),
        "current_invoice": (current_invoice or "").strip(),
    }

    self_clause = ""
    if params["current_invoice"]:
        self_clause = "AND sit.parent != %(current_invoice)s"

    claims = db.sql(
        f"""
        SELECT
            sit.timesheet_detail,
            sit.parent,
            si.docstatus
        FROM `tabSales Invoice Timesheet` sit
        INNER JOIN `tabSales Invoice` si
            ON si.name = sit.parent
        WHERE sit.timesheet_detail IN %(details)s
          AND si.docstatus IN (0, 1)
          {self_clause}
        ORDER BY sit.timesheet_detail ASC, sit.parent ASC
        FOR UPDATE
        """,
        params,
        as_dict=True,
    )

    # Defence in depth if a mocked/custom database adapter ignores the SQL
    # self-exclusion condition.
    if params["current_invoice"]:
        claims = [
            row
            for row in claims
            if row.parent != params["current_invoice"]
        ]

    return claims


def _guard_timesheet_details_with_db(
    db,
    detail_names,
    *,
    current_invoice=None,
    enforce_all_sources=False,
):
    """Authoritative implementation using the supplied DB transaction.

    `enforce_all_sources=True` is used by BatchProjects' generate_invoice(),
    where every selected source is known to belong to the BP billing flow.

    The Sales Invoice hook leaves it False so unrelated native ERPNext
    Timesheet invoicing remains untouched.
    """
    cleaned = _clean_detail_names(detail_names)
    if not cleaned:
        return []

    # BatchProjects' own generate_invoice() knows every source is BP-owned,
    # so duplicate claims are invalid immediately. The native Sales Invoice
    # hook must first determine BP ownership: unrelated ERPNext invoices must
    # remain behaviorally untouched.
    if enforce_all_sources:
        _raise_duplicate_sources(
            _duplicate_detail_names(cleaned)
        )

    names = sorted(set(cleaned))
    rows, missing = _lock_source_rows(db, names)

    if missing and enforce_all_sources:
        _validation_error(
            "These Timesheet Detail sources no longer exist: "
            + ", ".join(missing)
            + ". Refresh the billing screen and try again."
        )

    if enforce_all_sources:
        guarded_rows = rows
    else:
        bp_names = _bp_linked_source_names(db, rows)

        # Duplicate protection belongs only to BP-owned sources on the
        # site-wide Sales Invoice hook. A duplicate ERPNext-only source is
        # ERPNext's concern and must not become a BatchProjects validation
        # failure merely because this app is installed.
        bp_duplicates = [
            name
            for name in _duplicate_detail_names(cleaned)
            if name in bp_names
        ]
        _raise_duplicate_sources(bp_duplicates)

        guarded_rows = [
            row
            for row in rows
            if row.name in bp_names
        ]

    if not guarded_rows:
        return []

    current = (current_invoice or "").strip()

    already_billed = []
    for row in guarded_rows:
        invoice = (row.sales_invoice or "").strip()
        if invoice and invoice != current:
            already_billed.append((row.name, invoice))

    if already_billed:
        details = ", ".join(
            f"{detail} → {invoice}"
            for detail, invoice in already_billed
        )
        _validation_error(
            "These Timesheet Detail sources are already billed: "
            + details
            + ". Refresh before creating another invoice."
        )

    guarded_names = sorted(row.name for row in guarded_rows)

    claims = _live_claims(
        db,
        guarded_names,
        current_invoice=current,
    )

    if claims:
        drafts = sorted({
            row.parent
            for row in claims
            if int(row.docstatus or 0) == 0
        })
        submitted = sorted({
            row.parent
            for row in claims
            if int(row.docstatus or 0) == 1
        })

        parts = []
        if drafts:
            label = (
                "Draft Sales Invoice"
                if len(drafts) == 1
                else "Draft Sales Invoices"
            )
            parts.append(f"{label} {', '.join(drafts)}")
        if submitted:
            label = (
                "Submitted Sales Invoice"
                if len(submitted) == 1
                else "Submitted Sales Invoices"
            )
            parts.append(f"{label} {', '.join(submitted)}")

        _validation_error(
            "; ".join(parts)
            + " already covers these hours — submit/delete the competing "
              "draft, or refresh the billing screen before trying again."
        )

    return guarded_names


def guard_timesheet_details(
    detail_names,
    *,
    current_invoice=None,
    enforce_all_sources=False,
):
    """Reserve/validate Timesheet Detail sources in the current transaction."""
    return _guard_timesheet_details_with_db(
        frappe.db,
        detail_names,
        current_invoice=current_invoice,
        enforce_all_sources=enforce_all_sources,
    )


def validate_sales_invoice_sources(doc, method=None):
    """Sales Invoice validate hook.

    This is the final enforcement point for:
    - BatchProjects-created invoices;
    - invoices created/edited directly in ERPNext.

    Non-BP Sales Invoice Timesheet rows are intentionally ignored.
    """
    details = [
        getattr(row, "timesheet_detail", None)
        for row in (doc.get("timesheets") or [])
        if getattr(row, "timesheet_detail", None)
    ]

    if not details:
        return

    guard_timesheet_details(
        details,
        current_invoice=getattr(doc, "name", None),
        enforce_all_sources=False,
    )
