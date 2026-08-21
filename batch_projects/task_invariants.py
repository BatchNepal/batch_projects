"""Task mutation invariants that must hold across every creation path.

This module is wired through Frappe ``doc_events`` rather than a single API
endpoint so REST inserts, imports, automations and the BatchProjects SPA all
obey the same assignment contract.
"""

from __future__ import annotations

import frappe


_RESERVED_ASSIGNEES = {"Guest", "Administrator"}


def _user_row(user: str):
    if not user:
        return None
    return frappe.db.get_value(
        "User", user, ["name", "full_name", "enabled", "user_type"], as_dict=True
    )


def _assert_assignable_user(user: str):
    """Return the User row or fail closed when ``user`` cannot own task work.

    Task-scoped access deliberately allows a non-project-member to be assigned
    one task, so membership is not an eligibility requirement here. Identity
    validity is: the target must be a real, enabled System User and must not be
    one of Frappe's reserved accounts.
    """
    row = _user_row(user)
    if (
        not row
        or user in _RESERVED_ASSIGNEES
        or not row.enabled
        or row.user_type != "System User"
    ):
        frappe.throw(
            f"{user or 'This user'} cannot be assigned this task. "
            "Assignees must be enabled System Users.",
            frappe.ValidationError,
            title="User is not assignable",
        )
    return row


def before_task_insert(doc, method=None):
    """Materialize the project's default assignee before the task is inserted.

    Previously ``task.created`` sent an Assignment notification to the project
    default assignee without actually assigning that user. Materializing the
    child row here makes the stored state and its side effects agree.
    """
    if doc.get("assignees"):
        return
    default_assignee = frappe.db.get_value("BP Project", doc.project, "default_assignee")
    if not default_assignee:
        return
    row = _assert_assignable_user(default_assignee)
    doc.append(
        "assignees",
        {"user": default_assignee, "full_name": row.full_name or default_assignee},
    )


def validate_task_assignees(doc, method=None):
    """Validate and normalize every assignee on every BP Task save.

    API allowlists are not sufficient protection: tasks can also be created or
    modified through ORM/import/REST paths. Keeping this at the DocType event
    boundary prevents disabled, Website, Guest and duplicate users from
    entering the assignment graph regardless of caller.
    """
    seen = set()
    for assignee in doc.get("assignees") or []:
        user = assignee.user
        if user in seen:
            frappe.throw(
                f"{user} is assigned more than once.",
                frappe.ValidationError,
                title="Duplicate assignee",
            )
        seen.add(user)
        row = _assert_assignable_user(user)
        assignee.full_name = row.full_name or user


def after_task_insert(doc, method=None):
    """Emit normal assignment lifecycle events for assignees present at birth.

    ``BPTask.on_update`` already emits ``task.assigned`` for later assignment
    changes, but there is no old document to diff during insert. Without this
    hook, creating an already-assigned task skips assignment notification,
    watcher subscription, automation and the gateway ReBAC assignee edge.
    """
    if not doc.get("assignees"):
        return

    from batch_projects.events import TASK_ASSIGNED, emit

    actor_name = (
        frappe.db.get_value("User", frappe.session.user, "full_name")
        or frappe.session.user
    )

    for assignee in doc.assignees:
        full_name = assignee.full_name or assignee.user
        frappe.get_doc(
            {
                "doctype": "BP Activity",
                "task": doc.name,
                "project": doc.project,
                "task_key": doc.task_key,
                "action_type": "Assignment",
                "field_name": "",
                "old_value": "",
                "new_value": full_name,
                "user": frappe.session.user,
            }
        ).insert(ignore_permissions=True)
        emit(
            TASK_ASSIGNED,
            {
                "project": doc.project,
                "task": doc.name,
                "task_key": doc.task_key,
                "assignee": assignee.user,
                "full_name": full_name,
                "title": doc.title,
                "actor_name": actor_name,
                "initial_assignment": True,
            },
        )
