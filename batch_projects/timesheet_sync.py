"""
batch_projects/timesheet_sync.py
─────────────────────────────────
BP Task.actual_hours becomes a rollup instead of a dead field nobody
writes. Source of truth: SUM of submitted Timesheet Detail rows joined via
the custom_bp_task fixture field (fixtures/custom_field.json).

Written with frappe.db.set_value, not doc.save() — this is a system
recompute triggered by ERPNext's own Timesheet submit/cancel, not a user
edit, so it deliberately skips BP Task's save-side activity log / events.emit.
"""

import frappe


def sync_task_actual_hours(task_name: str):
    """Recompute one BP Task's actual_hours. Safe to call for a task that
    doesn't exist or has no timesheet rows (resolves to 0)."""
    if not task_name or not frappe.db.exists("BP Task", task_name):
        return

    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(tsd.hours), 0) AS h
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
        WHERE tsd.custom_bp_task = %(task)s
        """,
        {"task": task_name},
        as_dict=True,
    )
    hours = round(float(rows[0].h or 0), 2) if rows else 0.0
    frappe.db.set_value("BP Task", task_name, "actual_hours", hours, update_modified=False)


def sync_project_actual_hours(bp_project: str):
    """Bulk variant: resync every task in a BP Project. Not wired to an
    automatic trigger — the doc_events hooks below cover the live path.
    Available for a manual resync / backfill action in a later phase."""
    for task_name in frappe.get_all("BP Task", filters={"project": bp_project}, pluck="name"):
        sync_task_actual_hours(task_name)


def task_has_timesheet_rows(task_name: str) -> bool:
    """True if any submitted Timesheet has logged time against this task —
    used by get_task to report hours_source: 'timesheet' vs 'manual'."""
    if not task_name:
        return False
    return bool(frappe.db.sql(
        """
        SELECT 1
        FROM `tabTimesheet Detail` tsd
        JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
        WHERE tsd.custom_bp_task = %(task)s
        LIMIT 1
        """,
        {"task": task_name},
    ))


# ─── doc_events (hooks.py) ───────────────────────────────────────────────────

def _resync_tasks_on(doc):
    tasks = {row.custom_bp_task for row in (doc.time_logs or []) if row.custom_bp_task}
    for task_name in tasks:
        sync_task_actual_hours(task_name)


def on_timesheet_submit(doc, method=None):
    _resync_tasks_on(doc)


def on_timesheet_cancel(doc, method=None):
    _resync_tasks_on(doc)
