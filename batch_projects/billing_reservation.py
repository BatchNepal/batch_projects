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
import math

import frappe
from frappe.utils import flt


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


def _read_source_rows(db, names):
    """Read source identity/state without taking financial row locks.

    Used only by the site-wide Sales Invoice hook to determine which supplied
    Timesheet Details belong to BatchProjects. ERPNext-only sources should not
    acquire BP reservation locks merely because this app is installed.
    """
    if not names:
        return [], []

    rows = db.sql(
        """
        SELECT
            tsd.name,
            tsd.parent,
            tsd.project,
            tsd.custom_bp_task,
            tsd.sales_invoice,
            tsd.docstatus AS source_docstatus,
            tsd.is_billable
        FROM `tabTimesheet Detail` tsd
        WHERE tsd.name IN %(details)s
        ORDER BY tsd.name ASC
        """,
        {"details": tuple(names)},
        as_dict=True,
    )

    by_name = {row.name: row for row in rows}
    ordered = [by_name[name] for name in names if name in by_name]
    missing = [name for name in names if name not in by_name]

    return ordered, missing


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
            tsd.sales_invoice,
            tsd.docstatus AS source_docstatus,
            tsd.is_billable
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


def _validate_locked_source_state(rows):
    """Fail if a locked source ceased to be invoiceable.

    Frappe propagates the parent Timesheet docstatus onto its child rows.
    Therefore Timesheet Detail.docstatus is the state we can safely re-check
    while holding the Timesheet Detail row lock: a concurrent Timesheet cancel
    either completes first and leaves docstatus=2 for us to observe, or waits
    behind our reservation transaction.

    is_billable is checked for the same reason. Candidate selection happened
    earlier; reservation must prove that eligibility is still true now.
    """
    invalid = []

    for row in rows:
        if int(row.source_docstatus or 0) != 1:
            invalid.append(
                f"{row.name} (Timesheet is no longer submitted)"
            )
        elif int(row.is_billable or 0) != 1:
            invalid.append(
                f"{row.name} (time is no longer billable)"
            )

    if invalid:
        _validation_error(
            "These Timesheet Detail sources are no longer invoiceable: "
            + ", ".join(invalid)
            + ". Refresh the billing screen before creating the invoice."
        )


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

    if enforce_all_sources:
        guarded_rows, missing = _lock_source_rows(
            db,
            names,
        )

        if missing:
            _validation_error(
                "These Timesheet Detail sources no longer exist: "
                + ", ".join(missing)
                + ". Refresh the billing screen and try again."
            )

    else:
        # Site-wide hook: discover BP ownership without locks first. This
        # prevents an ordinary ERPNext-only Sales Invoice from taking BP
        # financial row locks merely because BatchProjects is installed.
        scope_rows, _scope_missing = _read_source_rows(
            db,
            names,
        )

        bp_names = _bp_linked_source_names(
            db,
            scope_rows,
        )

        bp_duplicates = [
            name
            for name in _duplicate_detail_names(cleaned)
            if name in bp_names
        ]
        _raise_duplicate_sources(bp_duplicates)

        if not bp_names:
            return []

        guarded_names = sorted(bp_names)
        guarded_rows, missing = _lock_source_rows(
            db,
            guarded_names,
        )

        # A source classified as BP-owned disappeared between scope-read and
        # row-lock acquisition. Do not silently turn that race into success.
        if missing:
            _validation_error(
                "These BatchProjects Timesheet Detail sources changed while "
                "the invoice was being validated: "
                + ", ".join(missing)
                + ". Refresh the invoice and try again."
            )

    _validate_locked_source_state(
        guarded_rows
    )

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


def _payment_first_total_field(doc):
    """Return ERPNext's authoritative customer-payable total field.

    ERPNext itself treats rounded_total as the payable document amount when
    rounding is enabled and grand_total as authoritative when rounded totals
    are disabled.
    """
    if doc.is_rounded_total_disabled():
        return "grand_total"

    return "rounded_total"


def _validate_payment_first_final_total(doc):
    """Enforce BatchProjects' payment-first contract after ERPNext validate.

    `generate_invoice()` stores the caller's already-received amount only in
    `doc.flags`. Frappe doc-event hooks execute AFTER the Sales Invoice
    controller's validate() method, so at this point ERPNext has already run
    its own item precision, taxes, charges and rounded-total calculations.

    This hook still runs BEFORE Document.insert() reaches db_insert(), so a
    mismatch cannot create even a transient committed Draft Sales Invoice.
    """
    # A normal ERPNext Sales Invoice has no BatchProjects payment-first
    # contract. Be defensive here because this is a site-wide validate hook:
    # lightweight test doubles/custom callers may not expose a flags mapping
    # at all. No contract means an immediate no-op.
    flags = getattr(
        doc,
        "flags",
        None,
    )

    if not flags:
        return

    expected = flags.get(
        "bp_expected_received_amount"
    )

    if expected is None:
        return

    if (
        isinstance(expected, bool)
        or not isinstance(
            expected,
            (int, float),
        )
        or not math.isfinite(
            float(expected)
        )
    ):
        _validation_error(
            "Expected received amount must be a finite number."
        )

    expected_currency = (
        flags.get(
            "bp_expected_received_currency"
        )
        or ""
    ).strip()

    actual_currency = (
        doc.get("currency")
        or ""
    ).strip()

    if (
        expected_currency
        and actual_currency != expected_currency
    ):
        _validation_error(
            "ERPNext changed the invoice currency during validation "
            f"from {expected_currency} to {actual_currency or '(blank)'}. "
            "Nothing was created. Refresh the billing screen and try again."
        )

    total_field = (
        _payment_first_total_field(doc)
    )

    raw_total = doc.get(
        total_field
    )

    if raw_total is None:
        _validation_error(
            "ERPNext did not calculate the final Sales Invoice total. "
            "Nothing was created."
        )

    precision = doc.precision(
        total_field
    )

    if precision is None:
        precision = 2

    actual = flt(
        raw_total,
        precision,
    )

    expected_final = flt(
        expected,
        precision,
    )

    if actual != expected_final:
        label = (
            "rounded total"
            if total_field == "rounded_total"
            else "grand total"
        )

        _validation_error(
            f"ERPNext final {label} {actual} "
            f"{actual_currency or expected_currency} does not match the "
            f"expected received amount {expected_final} "
            f"{expected_currency or actual_currency}. Nothing was created. "
            "Adjust the invoice inputs so ERPNext's final payable total "
            "matches the amount actually received."
        )


def validate_sales_invoice_sources(doc, method=None):
    """Sales Invoice validate hook.

    Frappe executes this doc-event hook after ERPNext's Sales Invoice
    controller validate() method and before db_insert(). Two independent
    BatchProjects invariants therefore meet here:

    1. payment-first invoices must match ERPNext's FINAL payable total;
    2. BP-owned Timesheet Detail sources must remain exclusively reserved.

    Native ERPNext invoices pay only an O(1) transient-flag check for the first
    invariant, then retain the existing BP-source fast path below.
    """
    _validate_payment_first_final_total(
        doc
    )

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
