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
    """Restate a BP-Project-denominated rate in company currency.

    Returns the rate unchanged when there's nothing to convert (no rate, no
    project currency, or it already matches the company's). If a conversion IS
    needed and no exchange rate exists, we keep the number as-is rather than
    throwing: a timer stop must never fail — losing someone's tracked time to
    a missing Currency Exchange record is a far worse outcome than a rate that
    needs correcting. generate_invoice() is where money actually gets
    committed, and it refuses loudly there instead."""
    if not rate or not project_currency or not company:
        return rate
    company_currency = frappe.get_cached_value("Company", company, "default_currency")
    if not company_currency or project_currency == company_currency:
        return rate
    from erpnext.setup.utils import get_exchange_rate
    try:
        fx = get_exchange_rate(project_currency, company_currency, frappe.utils.nowdate())
    except Exception:
        fx = None
    return flt(rate) * flt(fx) if fx else rate


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
    filters = {
        "docstatus": 0,
        "start_date": frappe.utils.nowdate(),
        "parent_project": erp_project,
    }
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
        "parent_project": erp_project,
    })


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
    proj = frappe.get_doc("BP Project", task.project)
    if not proj.erpnext_project:
        frappe.throw(
            f"Link '{proj.project_name}' to an ERPNext Project before tracking time on it."
        )

    employee = _resolve_employee(user)
    company = (employee and frappe.db.get_value("Employee", employee, "company")) or proj.company
    ts = _get_or_create_draft_timesheet(user, employee, company, proj.erpnext_project)

    # BP Project.hourly_rate is denominated in BP Project.currency, but
    # Timesheet Detail.billing_rate is ERPNext's field and ERPNext reads it as
    # COMPANY currency everywhere downstream (Timesheet.total_billable_amount,
    # Project.total_billable_amount, every stock report). Storing 50 for a
    # project priced at 50 USD on an NPR-books company therefore recorded
    # 50 NPR of revenue — off by the entire exchange rate. Convert once, here,
    # at capture, so ERPNext's own rollups are right; generate_invoice converts
    # back when it bills in the project's currency.
    rate = _rate_in_company_currency(flt(proj.hourly_rate or 0), proj.currency, company)
    # Real per-employee cost, not the client's billing rate wearing a
    # different field name: ERPNext's own get_activity_cost() (the same
    # lookup its native Timesheet UI uses) checks Activity Cost
    # (employee + activity type) first, then Activity Type's own default
    # rate. Only when NEITHER is configured do we fall back to the
    # project's flat rate as an estimate — same fallback costing.py's
    # labour_cost() already documents for the Money tab/margin report.
    activity_cost = get_activity_cost(employee, TIMER_ACTIVITY_TYPE) if employee else {}
    real_costing_rate = activity_cost.get("costing_rate")
    costing_rate = flt(real_costing_rate) if real_costing_rate is not None else rate
    ts.append("time_logs", {
        "activity_type": TIMER_ACTIVITY_TYPE,
        "from_time": started_at,
        "to_time": now_datetime(),
        "hours": elapsed_hours,
        # Set explicitly, not left for Timesheet.update_billing_hours to
        # backfill: update_cost() runs BEFORE that backfill in validate(),
        # and recomputes billing_amount = billing_rate * billing_hours — if
        # billing_hours is still 0 at that point, the amount is wiped.
        "billing_hours": elapsed_hours,
        "is_billable": 1 if task.billable else 0,
        "billing_rate": rate,
        "costing_rate": costing_rate,
        "project": proj.erpnext_project,
        "custom_bp_task": task.name,
        "description": f"{task.task_key} — {task.title}",
    })
    ts.save(ignore_permissions=True)

    return {
        "task": task.name,
        "task_key": task.task_key,
        "elapsed_hours": elapsed_hours,
        "timesheet": ts.name,
    }
