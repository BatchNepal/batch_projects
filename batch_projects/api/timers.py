"""
batch_projects/api/timers.py
─────────────────────────────
the task timer. One running timer per user (state = BP Active
Timer, a single row keyed on `user`); stopping resolves the elapsed time
into a Timesheet Detail row on that user's draft Timesheet for today,
against the task's project's linked ERPNext Project. Draft only — never
submitted; submission stays a deliberate ERPNext act (mirrors the Money
tab's unbilled-timesheet logic in erp_link.py).
"""

import frappe
from frappe.utils import flt, get_datetime, now_datetime, time_diff_in_hours
from erpnext.projects.doctype.timesheet.timesheet import get_activity_cost

from batch_projects.api.board import _check_task_permission, _require_system_user
from batch_projects.entitlements import require_feature
from batch_projects.setup.install import TIMER_ACTIVITY_TYPE


@frappe.whitelist()
def get_active_timer():
    """The current user's running timer, or None. Also self-heals: an
    active-timer row pointing at a since-deleted task is cleaned up rather
    than surfaced as a broken timer."""
    _require_system_user()

    row = frappe.db.get_value(
        "BP Active Timer", {"user": frappe.session.user},
        ["name", "task", "started_at"], as_dict=True,
    )
    if not row:
        return None

    task = frappe.db.get_value(
        "BP Task", row.task, ["name", "task_key", "title", "project"], as_dict=True
    )
    if not task:
        frappe.delete_doc("BP Active Timer", row.name, ignore_permissions=True)
        frappe.db.commit()
        return None

    return {
        "task": task.name,
        "task_key": task.task_key,
        "title": task.title,
        "project": task.project,
        "started_at": str(row.started_at),
    }


@frappe.whitelist()
def start_timer(task):
    """Starts a timer on `task`. If the user already has one running (on
    this task or another), it's stopped first — its elapsed time is still
    logged, exactly like an explicit stop_timer() call."""
    _require_system_user()
    require_feature("time_tracking")

    task_doc = frappe.get_doc("BP Task", task)
    _check_task_permission(task, task_doc.project, "BP Member")

    existing = frappe.db.get_value("BP Active Timer", {"user": frappe.session.user}, "name")
    stopped_previous = _stop(existing) if existing else None

    row = frappe.get_doc({
        "doctype": "BP Active Timer",
        "user": frappe.session.user,
        "task": task,
        "started_at": now_datetime(),
    })
    row.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": True,
        "task": task,
        "task_key": task_doc.task_key,
        "title": task_doc.title,
        "started_at": str(row.started_at),
        "stopped_previous": stopped_previous,
    }


@frappe.whitelist()
def stop_timer():
    _require_system_user()
    require_feature("time_tracking")

    existing = frappe.db.get_value("BP Active Timer", {"user": frappe.session.user}, "name")
    if not existing:
        frappe.throw("No timer is running.")

    result = _stop(existing)
    frappe.db.commit()
    if result is None:
        return {"ok": True, "logged": False, "reason": "Elapsed time rounded to zero."}
    return {"ok": True, "logged": True, **result}


def _rate_in_company_currency(rate, project_currency, company):
    """Restate a BP Project rate into company currency without lying.

    Timer stops must preserve worked time even when FX is unavailable.
    Therefore an unresolvable foreign rate becomes 0/unpriced instead of
    storing the project-currency number in a company-currency field.

    A zero row rate is recoverable: invoice generation can later fall back to
    the typed BP Project rate or ERPNext Item Price once valid FX exists.
    A mislabeled non-zero rate is not recoverable because downstream code has
    no way to discover that its unit was false.
    """
    value = flt(rate)
    if not value:
        return 0.0

    source = (project_currency or "").strip()
    if not source or not company:
        return 0.0

    company_currency = frappe.get_cached_value(
        "Company", company, "default_currency"
    )
    if not company_currency:
        return 0.0

    if source == company_currency:
        return value

    from erpnext.setup.utils import get_exchange_rate

    try:
        fx = flt(
            get_exchange_rate(
                source,
                company_currency,
                frappe.utils.nowdate(),
            )
        )
    except Exception:
        fx = 0.0

    return flt(value * fx) if fx > 0 else 0.0

def _resolve_employee(user):
    """Same Employee.user_id lookup the utilization code reads with
    (board.py's _timesheet_hours_by_user) — here for the write side. No
    Employee record is not an error: Timesheet.employee is optional, and
    the row still lands against `user`."""
    return frappe.db.get_value("Employee", {"user_id": user}, "name")


def _get_or_create_draft_timesheet(user, employee, company, erp_project):
    """Today's draft Timesheet for this user ON THIS PROJECT, creating one
    if absent. Matched by employee when resolved, else by owner (mirrors
    the Employee.user_id -> owner fallback used on the read side).

    Scoped per project (parent_project), not just per user/day: a shared
    multi-project draft would let one project's Money drawer read — and its
    Admin SUBMIT — another project's pending rows (submit is doc-level in
    ERPNext). parent_project also buys core validation for free: ERPNext
    itself rejects any row whose project differs from it."""
    company_currency = (
        frappe.get_cached_value(
            "Company", company, "default_currency"
        )
        if company else None
    )

    filters = {
        "docstatus": 0,
        "start_date": frappe.utils.nowdate(),
        "parent_project": erp_project,
    }

    # A billing_rate is typed by Timesheet.currency in ERPNext. BatchProjects
    # deliberately captures timer rows in company currency, so only reuse a
    # draft that already carries that exact currency model. Older blank- or
    # foreign-currency drafts remain untouched and a new safe draft is made.
    if company_currency:
        filters["currency"] = company_currency
        filters["exchange_rate"] = 1.0
    if employee:
        filters["employee"] = employee
    else:
        filters["employee"] = ["in", ("", None)]
        filters["owner"] = user

    name = frappe.db.get_value("Timesheet", filters, "name", order_by="creation desc")
    if name:
        return frappe.get_doc("Timesheet", name)

    return frappe.get_doc({
        "doctype": "Timesheet",
        "employee": employee,
        "company": company,
        "currency": company_currency,
        "exchange_rate": 1.0,
        "parent_project": erp_project,
    })


def _append_time_log(task, user, from_time, to_time, hours, description=None):
    """Resolve a span of worked time into a Timesheet Detail row on the
    user's draft timesheet. Shared by the running-timer stop path and
    manual time entry (`log_time`) — both need the identical rate/costing
    resolution, and duplicating it was how these two paths would drift."""
    proj = frappe.get_doc("BP Project", task.project)
    if not proj.erpnext_project:
        frappe.throw(
            f"Link '{proj.project_name}' to an ERPNext Project before tracking time on it."
        )

    employee = _resolve_employee(user)
    company = (employee and frappe.db.get_value("Employee", employee, "company")) or proj.company
    ts = _get_or_create_draft_timesheet(user, employee, company, proj.erpnext_project)

    # ERPNext types Timesheet Detail.billing_rate by the parent
    # Timesheet.currency. BatchProjects deliberately creates/reuses its timer
    # Timesheets in company currency, so convert the BP Project rate into that
    # currency before capture. If FX is unavailable the helper returns 0
    # rather than storing a foreign number under the wrong unit; worked hours
    # are still preserved and invoice-time typed fallbacks remain available.
    rate = _rate_in_company_currency(flt(proj.hourly_rate or 0), proj.currency, company)
    # Real per-employee cost, not the client's billing rate wearing a
    # different field name: ERPNext's own get_activity_cost() (the same
    # lookup its native Timesheet UI uses) checks Activity Cost
    # (employee + activity type) first, then Activity Type's own default
    # rate. Only when NEITHER is configured do we fall back to the
    # project's flat rate as an estimate — the write-side counterpart of the
    # same fallback the reports apply when reading these rows back
    # (bp-gateway internal/insights/money.go's labourCost).
    activity_cost = get_activity_cost(employee, TIMER_ACTIVITY_TYPE) if employee else {}
    real_costing_rate = activity_cost.get("costing_rate")
    costing_rate = flt(real_costing_rate) if real_costing_rate is not None else rate
    row = ts.append("time_logs", {
        "activity_type": TIMER_ACTIVITY_TYPE,
        "from_time": from_time,
        "to_time": to_time,
        "hours": hours,
        # Set explicitly, not left for Timesheet.update_billing_hours to
        # backfill: update_cost() runs BEFORE that backfill in validate(),
        # and recomputes billing_amount = billing_rate * billing_hours — if
        # billing_hours is still 0 at that point, the amount is wiped.
        "billing_hours": hours,
        "is_billable": 1 if task.billable else 0,
        "billing_rate": rate,
        "costing_rate": costing_rate,
        "project": proj.erpnext_project,
        "custom_bp_task": task.name,
        "description": description or f"{task.task_key} — {task.title}",
    })
    ts.save(ignore_permissions=True)

    return {
        "task": task.name,
        "task_key": task.task_key,
        "elapsed_hours": hours,
        "timesheet": ts.name,
        "time_log": row.name,
    }


def _stop(active_timer_name):
    """Stop one BP Active Timer row: delete the state row, resolve the
    elapsed time into a Timesheet Detail row. Returns a summary dict, or
    None if the elapsed time rounds to zero (row deleted, nothing logged)."""
    row = frappe.get_doc("BP Active Timer", active_timer_name)
    started_at = get_datetime(row.started_at)
    user = row.user
    task_name = row.task
    elapsed_hours = round(time_diff_in_hours(now_datetime(), started_at), 4)
    frappe.delete_doc("BP Active Timer", active_timer_name, ignore_permissions=True)

    if elapsed_hours <= 0 or not frappe.db.exists("BP Task", task_name):
        return None

    task = frappe.get_doc("BP Task", task_name)
    return _append_time_log(task, user, started_at, now_datetime(), elapsed_hours)


@frappe.whitelist()
def log_time(task, hours, date=None, description=None):
    """Manually log time on a task without running a timer — the "I forgot
    to start the timer" path the audit found missing (audit 03 §C1). Lands
    on the same draft timesheet a running timer would, so it flows through
    the exact same rate/costing/invoicing path.
    """
    _require_system_user()
    require_feature("time_tracking")

    hours = flt(hours)
    if hours <= 0:
        frappe.throw("Hours must be greater than zero.")

    task_doc = frappe.get_doc("BP Task", task)
    _check_task_permission(task, task_doc.project, "BP Member")

    day = frappe.utils.getdate(date) if date else frappe.utils.getdate()
    from_time = get_datetime(f"{day} 09:00:00")
    to_time = frappe.utils.add_to_date(from_time, hours=hours)

    result = _append_time_log(task_doc, frappe.session.user, from_time, to_time, hours, description)
    frappe.db.commit()
    return {"ok": True, **result}


def _get_editable_time_log(time_log_name):
    """Fetch (timesheet_doc, child_row) for a Timesheet Detail row, refusing
    to touch anything already submitted — actual/billed hours must not be
    silently rewritten after ERPNext has invoiced off them — or that doesn't
    belong to the caller."""
    parent = frappe.db.get_value("Timesheet Detail", time_log_name, "parent")
    if not parent:
        frappe.throw("Time entry not found.")
    ts = frappe.get_doc("Timesheet", parent)
    if ts.docstatus != 0:
        frappe.throw("This time entry has already been submitted and can no longer be edited here.")
    row = next((r for r in ts.time_logs if r.name == time_log_name), None)
    if not row:
        frappe.throw("Time entry not found.")

    task_name = row.custom_bp_task
    if task_name:
        task_project = frappe.db.get_value("BP Task", task_name, "project")
        if task_project:
            _check_task_permission(task_name, task_project, "BP Member")
    elif ts.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw("You can only edit your own time entries.")
    return ts, row


@frappe.whitelist()
def list_time_entries(task):
    """Time log rows for a task — the read side of manual correction (edit/
    delete act on the `name` this returns)."""
    _require_system_user()
    task_doc = frappe.get_doc("BP Task", task)
    _check_task_permission(task, task_doc.project, "BP Viewer")

    rows = frappe.get_all(
        "Timesheet Detail",
        filters={"custom_bp_task": task},
        fields=["name", "parent", "from_time", "to_time", "hours",
                "billing_hours", "is_billable", "description"],
        order_by="from_time desc",
    )
    if not rows:
        return rows

    parents = {r["parent"] for r in rows}
    parent_meta = {
        p["name"]: p for p in frappe.get_all(
            "Timesheet", filters={"name": ["in", list(parents)]},
            fields=["name", "docstatus", "owner"],
        )
    }
    for r in rows:
        meta = parent_meta.get(r["parent"], {})
        r["docstatus"] = meta.get("docstatus")
        r["editable"] = meta.get("docstatus") == 0
        r["owner"] = meta.get("owner")
    return rows


@frappe.whitelist()
def update_time_entry(time_log_name, hours=None, description=None):
    """Correct a logged time entry — was impossible from the app entirely
    (audit 03 §C1); only draft (unsubmitted) entries can be touched."""
    _require_system_user()
    require_feature("time_tracking")
    ts, row = _get_editable_time_log(time_log_name)

    if hours is not None:
        hours = flt(hours)
        if hours <= 0:
            frappe.throw("Hours must be greater than zero.")
        row.hours = hours
        row.billing_hours = hours
        row.to_time = frappe.utils.add_to_date(get_datetime(row.from_time), hours=hours)
    if description is not None:
        row.description = description

    ts.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "hours": row.hours, "timesheet": ts.name}


@frappe.whitelist()
def delete_time_entry(time_log_name):
    """Remove a mistaken manual/timer entry — draft only, same guard as
    `update_time_entry`."""
    _require_system_user()
    require_feature("time_tracking")
    ts, row = _get_editable_time_log(time_log_name)
    task_name = row.custom_bp_task
    ts.remove(row)
    if ts.time_logs:
        ts.save(ignore_permissions=True)
    else:
        # Timesheet.time_logs is a mandatory table (reqd=1) — an emptied
        # draft timesheet fails validation on save (confirmed live:
        # MandatoryError "[Timesheet, ...]: time_logs" deleting a task's
        # only logged entry). Delete the now-pointless draft outright.
        ts.delete(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "task": task_name}


def send_timer_reminders():
    """Hourly scheduled job: nag anyone whose timer has been running past a
    sane single-sitting length. Nothing warned about a timer left running for
    hours, and — before `update_time_entry`/`delete_time_entry` above — there
    was no way to fix the resulting bad entry afterwards either; together
    that was a guaranteed wrong invoice (audit 03 §C2). De-duplicated to at
    most one reminder per (user, task) per day, same pattern as
    events.send_due_date_reminders.
    """
    from batch_projects.events import _create_notification, _push_notification_badge, _reminder_sent_today

    threshold_hours = 8
    cutoff = frappe.utils.add_to_date(now_datetime(), hours=-threshold_hours)

    rows = frappe.get_all(
        "BP Active Timer",
        filters={"started_at": ["<", cutoff]},
        fields=["name", "user", "task", "started_at"],
    )
    for row in rows:
        if not row.task or _reminder_sent_today(row.user, row.task, "Timer Reminder"):
            continue
        task = frappe.db.get_value(
            "BP Task", row.task, ["task_key", "title", "project"], as_dict=True
        )
        if not task:
            continue
        elapsed = round(time_diff_in_hours(now_datetime(), get_datetime(row.started_at)), 1)
        message = (
            f"Your timer on {task.task_key} has been running for {elapsed}h — "
            f"still working, or did you forget to stop it?"
        )
        # actor=None → system reminder, same as send_due_date_reminders.
        _create_notification(row.user, "Timer Reminder", row.task, task.project, None, message)
        _push_notification_badge({row.user}, task.project)
