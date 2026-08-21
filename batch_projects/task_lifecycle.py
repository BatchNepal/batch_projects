"""Authoritative soft-trash / restore lifecycle for BP Task.

Soft deletion changes live visibility and the gateway authorization graph, so it
cannot remain a raw ``is_deleted`` flag flip. These endpoints are wired through
``override_whitelisted_methods`` and keep MariaDB, realtime clients, automation,
notification rules, Redis and OpenFGA aligned.

Cascade provenance uses one shared ``deleted_on`` timestamp for the parent and
only the descendants deleted by that same operation. Restore therefore never
resurrects a child that had already been independently trashed.
"""

from __future__ import annotations

import frappe


TASK_TRASHED = "task.trashed"
TASK_RESTORED = "task.restored"


def _manager_task(issue: str):
    doc = frappe.get_doc("BP Task", issue)
    from batch_projects import access
    access.require(doc.project, "Manager")
    return doc


def _assignees(issue: str) -> list[str]:
    return frappe.get_all(
        "BP Task Assignee",
        filters={"parent": issue, "parenttype": "BP Task"},
        pluck="user",
    )


def _dispatch_after_commit(event: str, payload: dict) -> None:
    """Run the durable event pipeline after the lifecycle transaction commits.

    Calling events.emit() from an after_commit callback would schedule its
    realtime broadcast onto after_commit *again*. Drive the same primitives
    directly instead so automation/notification rules see the committed trash
    state immediately and realtime is published in this callback.

    ReBAC is explicit because task.trashed/task.restored carry a list of direct
    assignee tuples and are intentionally outside events.py's compact
    one-user relationship envelope.
    """
    from batch_projects import events

    enriched = events._enrich(event, dict(payload))
    events._invalidate_cache(event, enriched)
    events._broadcast(event, enriched, after_commit=False)
    events._evaluate_automations(event, enriched)
    events._queue_notifications(event, enriched)

    try:
        from batch_projects import bridge
        bridge.publish_rebac_event(enriched)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"bp rebac {event} sync failed",
        )


def _schedule_lifecycle(event: str, doc, users: list[str]) -> None:
    payload = {
        "event": event,
        "project": doc.project,
        "task": doc.name,
        "task_key": doc.task_key,
        "title": doc.title,
        "users": sorted(set(users)),
        "timestamp": frappe.utils.now(),
    }
    frappe.db.after_commit.add(lambda: _dispatch_after_commit(event, payload))


def _stop_active_timers(doc, deleted_on) -> list[str]:
    """Stop every running timer on ``doc`` at the exact trash timestamp.

    A BP Active Timer is operational state, not historical accounting state. If
    it survives soft-delete it keeps accumulating invisible hours and may later
    create a wildly inflated Timesheet row. Preserve the work already done by
    resolving the span through the same `_append_time_log` path as a normal
    stop, then remove the timer inside the SAME transaction as trash.

    Any failure to persist the elapsed work propagates and rolls the trash
    transaction back. Silently deleting a timer, or trashing while losing its
    worked time, would be worse than refusing the delete.
    """
    timers = frappe.get_all(
        "BP Active Timer",
        filters={"task": doc.name},
        fields=["name", "user", "started_at"],
    )
    if not timers:
        return []

    from batch_projects.api.timers import _append_time_log

    stopped = []
    end_time = frappe.utils.get_datetime(deleted_on)
    for timer in timers:
        started_at = frappe.utils.get_datetime(timer.started_at)
        hours = round(frappe.utils.time_diff_in_hours(end_time, started_at), 4)

        # Remove the running-state row even for a sub-minute/clock-skew span;
        # there is no meaningful time row to persist when the duration is <= 0.
        frappe.delete_doc("BP Active Timer", timer.name, ignore_permissions=True)
        if hours > 0:
            _append_time_log(
                doc,
                timer.user,
                started_at,
                end_time,
                hours,
                description=f"Auto-stopped when {doc.task_key} was moved to Trash",
            )
        stopped.append(timer.name)
    return stopped


def _trash_tree(issue: str, deleted_on, actor: str) -> list[str]:
    doc = frappe.get_doc("BP Task", issue)
    if doc.is_deleted:
        return []

    changed = []
    children = frappe.get_all(
        "BP Task",
        filters={"parent_task": issue, "is_deleted": 0},
        pluck="name",
    )
    for child in children:
        changed.extend(_trash_tree(child, deleted_on, actor))

    # A hidden timer must never outlive its task. Use the cascade's shared
    # timestamp so parent/child timers all stop at one deterministic instant.
    _stop_active_timers(doc, deleted_on)

    users = _assignees(doc.name)
    frappe.db.set_value(
        "BP Task",
        doc.name,
        {
            "is_deleted": 1,
            "deleted_on": deleted_on,
            "deleted_by": actor,
        },
        update_modified=False,
    )
    _schedule_lifecycle(TASK_TRASHED, doc, users)
    changed.append(doc.name)
    return changed


def _restore_tree(issue: str, cascade_stamp) -> list[str]:
    doc = frappe.get_doc("BP Task", issue)
    if not doc.is_deleted:
        return []

    changed = []
    # Restore only descendants deleted by the exact same cascade. A child with
    # an older independent deletion timestamp remains in trash.
    children = frappe.get_all(
        "BP Task",
        filters={
            "parent_task": issue,
            "is_deleted": 1,
            "deleted_on": cascade_stamp,
        },
        pluck="name",
    )

    frappe.db.set_value(
        "BP Task",
        doc.name,
        {"is_deleted": 0, "deleted_on": None, "deleted_by": None},
        update_modified=False,
    )
    _schedule_lifecycle(TASK_RESTORED, doc, _assignees(doc.name))
    changed.append(doc.name)

    for child in children:
        changed.extend(_restore_tree(child, cascade_stamp))
    return changed


@frappe.whitelist()
def delete_task(issue):
    """Move one task subtree to trash without destroying history."""
    doc = _manager_task(issue)
    if doc.is_deleted:
        return {"ok": True, "trashed": True, "tasks": []}

    stamp = frappe.utils.now_datetime()
    changed = _trash_tree(doc.name, stamp, frappe.session.user)
    frappe.db.commit()
    return {"ok": True, "trashed": True, "tasks": changed}


@frappe.whitelist()
def restore_task(issue):
    """Restore exactly the subtree removed by this task's trash operation."""
    doc = _manager_task(issue)
    if not doc.is_deleted:
        return {"ok": True, "restored": True, "tasks": []}

    stamp = doc.deleted_on
    changed = _restore_tree(doc.name, stamp)
    frappe.db.commit()
    return {"ok": True, "restored": True, "tasks": changed}


@frappe.whitelist()
def bulk_delete_tasks(issues):
    if isinstance(issues, str):
        issues = frappe.parse_json(issues)
    if not isinstance(issues, list):
        frappe.throw("issues must be a list", frappe.ValidationError)

    deleted, failed = [], []
    for issue in issues:
        try:
            result = delete_task(issue)
            deleted.extend(result.get("tasks") or ([issue] if result.get("trashed") else []))
        except frappe.PermissionError:
            failed.append({"name": issue, "reason": "permission"})
        except Exception as exc:
            frappe.log_error(frappe.get_traceback(), "bulk task trash failed")
            failed.append({"name": issue, "reason": str(exc)[:200]})

    # Preserve one result per requested root even though ``tasks`` above also
    # contains cascade descendants.
    roots = [issue for issue in issues if issue in set(deleted)]
    return {"deleted": roots, "failed": failed}
