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


def _assignee_users(doc) -> list[str]:
    return [row.user for row in (doc.get("assignees") or []) if row.user]


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
    """Validate every newly-created assignment edge at the DocType boundary.

    Existing legacy rows are deliberately grandfathered when the assignee set
    is unchanged: editing a title must not suddenly fail because an old task
    contains a disabled user from years ago. As soon as the assignment set is
    changed, every *new* edge is required to point at an enabled System User,
    and the final set may not contain duplicates.
    """
    new_users = _assignee_users(doc)
    old = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
    old_users = _assignee_users(old) if old else []

    if old and new_users == old_users:
        return

    if len(new_users) != len(set(new_users)):
        duplicate = next(user for user in new_users if new_users.count(user) > 1)
        frappe.throw(
            f"{duplicate} is assigned more than once.",
            frappe.ValidationError,
            title="Duplicate assignee",
        )

    old_set = set(old_users)
    for assignee in doc.get("assignees") or []:
        user = assignee.user
        if user in old_set:
            continue
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
