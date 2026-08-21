"""Live-task boundary for timers and manual time entry.

Soft-deleted tasks remain physical rows for restore/audit, so the legacy timer
API could still start a new timer or log new time against a task in Trash. A
running timer that survived deletion was worse: stopping it later used ``now``
and could turn hidden elapsed time into inflated billable hours.

The task trash lifecycle now stops timers transactionally at ``deleted_on``.
These adapters close the remaining API/scheduler paths and repair any legacy
active timer that still points at a soft-deleted task by capping its elapsed
span at that same deletion timestamp.
"""

from __future__ import annotations

import frappe


def _task_state(task: str):
    return frappe.db.get_value(
        "BP Task",
        task,
        ["name", "task_key", "title", "project", "is_deleted", "deleted_on"],
        as_dict=True,
    )


def _require_live_task(task: str):
    row = _task_state(task)
    if not row:
        frappe.throw("Task not found.", frappe.DoesNotExistError)
    if int(row.is_deleted or 0):
        frappe.throw(
            "This task is in Trash. Restore it before tracking new time.",
            frappe.ValidationError,
            title="Task is in Trash",
        )
    return row


def _active_timer_for_user(user: str):
    return frappe.db.get_value(
        "BP Active Timer",
        {"user": user},
        ["name", "user", "task", "started_at"],
        as_dict=True,
    )


def _close_deleted_timer(active, task_state):
    """Close a legacy ghost timer at the task's durable deletion timestamp."""
    if not active or not task_state or not int(task_state.is_deleted or 0):
        return None
    if not task_state.deleted_on:
        # There is no defensible elapsed duration without a deletion timestamp.
        # Do not use `now` and silently overstate worked/billable time.
        frappe.throw(
            "A running timer belongs to a trashed task whose deletion time is missing. "
            "Restore the task or correct the timer before continuing.",
            frappe.ValidationError,
            title="Timer requires repair",
        )

    started_at = frappe.utils.get_datetime(active.started_at)
    ended_at = frappe.utils.get_datetime(task_state.deleted_on)
    hours = round(frappe.utils.time_diff_in_hours(ended_at, started_at), 4)

    frappe.delete_doc("BP Active Timer", active.name, ignore_permissions=True)
    if hours <= 0:
        return None

    from batch_projects.api.timers import _append_time_log

    task_doc = frappe.get_doc("BP Task", task_state.name)
    return _append_time_log(
        task_doc,
        active.user,
        started_at,
        ended_at,
        hours,
        description=f"Auto-stopped when {task_state.task_key} was moved to Trash",
    )


def _repair_current_user_deleted_timer():
    active = _active_timer_for_user(frappe.session.user)
    if not active:
        return None
    state = _task_state(active.task)
    if not state:
        # Same self-heal behavior the original get_active_timer already used for
        # a physically deleted task: no task exists against which time can be
        # reconstructed safely.
        frappe.delete_doc("BP Active Timer", active.name, ignore_permissions=True)
        return None
    if int(state.is_deleted or 0):
        return _close_deleted_timer(active, state)
    return None


@frappe.whitelist()
def get_active_timer():
    from batch_projects.api.timers import _require_system_user

    _require_system_user()
    active = _active_timer_for_user(frappe.session.user)
    if not active:
        return None

    state = _task_state(active.task)
    if not state:
        frappe.delete_doc("BP Active Timer", active.name, ignore_permissions=True)
        frappe.db.commit()
        return None
    if int(state.is_deleted or 0):
        _close_deleted_timer(active, state)
        frappe.db.commit()
        return None

    return {
        "task": state.name,
        "task_key": state.task_key,
        "title": state.title,
        "project": state.project,
        "started_at": str(active.started_at),
    }


@frappe.whitelist()
def start_timer(task):
    from batch_projects.api.timers import (
        _require_system_user,
        require_feature,
        start_timer as original_start_timer,
    )

    # Authenticate and entitlement-gate before probing task existence/state.
    _require_system_user()
    require_feature("time_tracking")
    _require_live_task(task)

    # If this user carries a legacy ghost timer, close it at deleted_on before
    # the original start path can call its `_stop(existing)` helper with `now`.
    _repair_current_user_deleted_timer()
    return original_start_timer(task)


@frappe.whitelist()
def stop_timer():
    from batch_projects.api.timers import _require_system_user, require_feature

    _require_system_user()
    require_feature("time_tracking")

    active = _active_timer_for_user(frappe.session.user)
    if not active:
        frappe.throw("No timer is running.")

    state = _task_state(active.task)
    if not state:
        frappe.delete_doc("BP Active Timer", active.name, ignore_permissions=True)
        frappe.db.commit()
        return {"ok": True, "logged": False, "reason": "Task no longer exists."}

    if int(state.is_deleted or 0):
        result = _close_deleted_timer(active, state)
        frappe.db.commit()
        if result is None:
            return {
                "ok": True,
                "logged": False,
                "reason": "Timer stopped when the task entered Trash.",
            }
        return {"ok": True, "logged": True, **result}

    from batch_projects.api.timers import stop_timer as original_stop_timer

    return original_stop_timer()


@frappe.whitelist()
def log_time(task, hours, date=None, description=None):
    from batch_projects.api.timers import (
        _require_system_user,
        log_time as original_log_time,
        require_feature,
    )

    _require_system_user()
    require_feature("time_tracking")
    _require_live_task(task)
    return original_log_time(task, hours, date=date, description=description)


def send_timer_reminders():
    """Hourly reminder for live-task timers only; repair legacy ghost timers."""
    from batch_projects.events import (
        _create_notification,
        _push_notification_badge,
        _reminder_sent_today,
    )
    from batch_projects.api.timers import now_datetime, get_datetime, time_diff_in_hours

    threshold_hours = 8
    cutoff = frappe.utils.add_to_date(now_datetime(), hours=-threshold_hours)
    rows = frappe.get_all(
        "BP Active Timer",
        filters={"started_at": ["<", cutoff]},
        fields=["name", "user", "task", "started_at"],
    )

    changed = False
    for active in rows:
        if not active.task:
            continue
        state = _task_state(active.task)
        if not state:
            frappe.delete_doc("BP Active Timer", active.name, ignore_permissions=True)
            changed = True
            continue
        if int(state.is_deleted or 0):
            try:
                _close_deleted_timer(active, state)
                changed = True
            except Exception:
                # A bad legacy timer must not prevent reminders for every other
                # user. Fail this row closed and leave it for explicit repair.
                frappe.log_error(
                    frappe.get_traceback(),
                    f"BP ghost timer repair failed: {active.name}",
                )
            continue
        if _reminder_sent_today(active.user, active.task, "Timer Reminder"):
            continue

        elapsed = round(
            time_diff_in_hours(now_datetime(), get_datetime(active.started_at)), 1
        )
        message = (
            f"Your timer on {state.task_key} has been running for {elapsed}h — "
            "still working, or did you forget to stop it?"
        )
        _create_notification(
            active.user,
            "Timer Reminder",
            active.task,
            state.project,
            None,
            message,
        )
        _push_notification_badge({active.user}, state.project)

    if changed:
        frappe.db.commit()
