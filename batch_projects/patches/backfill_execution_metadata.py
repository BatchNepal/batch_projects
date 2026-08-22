"""Backfill execution metadata defaults on existing BP Automation Run rows.

Existing run rows predate the execution_id/correlation_id/source/attempt/
started_at/finished_at/duration_ms/error_code columns. We can't reconstruct
the original execution IDs (they're generated at dispatch time), so:

- execution_id, correlation_id: left NULL (no fabricated trace IDs)
- source: defaulted to 'event' (the most common path)
- attempt: defaulted to 1 (first try)
- started_at, finished_at: copied from run_at (best available timestamp)
- duration_ms, error_code, retry_at: left NULL (can't reconstruct)

Also backfills source='user' on existing BP Activity rows and source='system'
on existing BP Audit Log rows — the safest defaults for historical data.

Idempotent: only touches rows where the new columns are NULL/empty.
"""
import frappe


def execute():
    # ── BP Automation Run ─────────────────────────────────────────────
    frappe.db.sql(
        "UPDATE `tabBP Automation Run` SET source = 'event' "
        "WHERE (source IS NULL OR source = '')"
    )
    frappe.db.sql(
        "UPDATE `tabBP Automation Run` SET attempt = 1 "
        "WHERE attempt IS NULL OR attempt = 0"
    )
    frappe.db.sql(
        "UPDATE `tabBP Automation Run` SET started_at = run_at "
        "WHERE started_at IS NULL AND run_at IS NOT NULL"
    )
    frappe.db.sql(
        "UPDATE `tabBP Automation Run` SET finished_at = run_at "
        "WHERE finished_at IS NULL AND run_at IS NOT NULL"
    )

    # ── BP Workflow Run ───────────────────────────────────────────────
    # Historical workflow rows predate the callback contract. Preserve their
    # real run_id while filling only facts derivable from run_at.
    frappe.db.sql(
        "UPDATE `tabBP Workflow Run` SET source = 'event' "
        "WHERE (source IS NULL OR source = '')"
    )
    frappe.db.sql(
        "UPDATE `tabBP Workflow Run` SET attempt = 1 "
        "WHERE attempt IS NULL OR attempt = 0"
    )
    frappe.db.sql(
        "UPDATE `tabBP Workflow Run` SET started_at = run_at "
        "WHERE started_at IS NULL AND run_at IS NOT NULL"
    )
    frappe.db.sql(
        "UPDATE `tabBP Workflow Run` SET finished_at = run_at "
        "WHERE finished_at IS NULL AND run_at IS NOT NULL"
    )

    # ── BP Activity ───────────────────────────────────────────────────
    frappe.db.sql(
        "UPDATE `tabBP Activity` SET source = 'user' "
        "WHERE (source IS NULL OR source = '')"
    )

    # ── BP Audit Log ──────────────────────────────────────────────────
    frappe.db.sql(
        "UPDATE `tabBP Audit Log` SET source = 'system' "
        "WHERE (source IS NULL OR source = '')"
    )

    frappe.db.commit()
