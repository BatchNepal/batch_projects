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
    """Bulk variant: resync every task in a BP Project. The live path is the
    Timesheet submit/cancel doc_events below; this is the manual/backfill
    entry point, and reconcile_actual_hours() is the scheduled safety net."""
    for task_name in frappe.get_all("BP Task", filters={"project": bp_project}, pluck="name"):
        sync_task_actual_hours(task_name)


# Float tolerance: sync_task_actual_hours stores round(x, 2), so anything
# smaller than half a cent of an hour is representation noise, not drift.
_DRIFT_EPSILON = 0.005

# Cap per run so one nightly job can't exceed the scheduler timeout on a big
# site. Drift is rare; if a run hits the cap the next one picks up the rest.
_RECONCILE_CAP = 500


def reconcile_actual_hours():
    """Daily safety net for BP Task.actual_hours.

    The live rollup only fires on Timesheet submit/cancel. Anything that moves
    hours outside that path — a failed hook, a patch, a data import, a direct
    edit of a Timesheet Detail row — leaves actual_hours silently disagreeing
    with the timesheets, and actual_hours feeds billing and margin. Nothing
    repaired that: sync_project_actual_hours existed but was never wired to a
    trigger (audit 03 §C4).

    One query finds every task whose stored value disagrees with the truth,
    in both directions (stale non-zero with no rows left, and missing hours),
    rather than recomputing every task in the install.
    """
    rows = frappe.db.sql(
        """
        SELECT t.name AS task,
               COALESCE(t.actual_hours, 0) AS stored,
               COALESCE(x.h, 0)            AS truth
        FROM `tabBP Task` t
        LEFT JOIN (
            SELECT tsd.custom_bp_task AS task, SUM(tsd.hours) AS h
            FROM `tabTimesheet Detail` tsd
            JOIN `tabTimesheet` ts ON ts.name = tsd.parent AND ts.docstatus = 1
            WHERE tsd.custom_bp_task IS NOT NULL AND tsd.custom_bp_task != ''
            GROUP BY tsd.custom_bp_task
        ) x ON x.task = t.name
        WHERE ABS(COALESCE(t.actual_hours, 0) - COALESCE(x.h, 0)) > %(eps)s
        LIMIT %(cap)s
        """,
        {"eps": _DRIFT_EPSILON, "cap": _RECONCILE_CAP},
        as_dict=True,
    )
    if not rows:
        return 0

    for r in rows:
        # Same write the live path uses — a system recompute, so it must not
        # bump `modified` or fire task events.
        frappe.db.set_value(
            "BP Task", r.task, "actual_hours", round(float(r.truth or 0), 2),
            update_modified=False,
        )
    frappe.db.commit()

    frappe.logger("bp_timesheet").warning(
        f"reconcile_actual_hours corrected {len(rows)} task(s); "
        f"worst drift {max(abs(r.stored - r.truth) for r in rows):.2f}h"
        + (f" (capped at {_RECONCILE_CAP}, more may remain)" if len(rows) == _RECONCILE_CAP else "")
    )
    return len(rows)


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
