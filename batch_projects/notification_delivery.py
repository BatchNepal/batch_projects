"""Final authorization boundary for task-backed notification delivery.

Recipient selection is advisory. Watcher rows, mentions, notification rules and
automations can all become stale after membership changes, assignment removal or
a project move. Every delivery channel must therefore re-check the durable task
and the recipient's *current* access immediately before exposing task metadata.

This module intentionally knows nothing about notification preferences or
routing. It answers one question only: may this identity receive information
about this task/project right now?
"""

from __future__ import annotations

import frappe


def resolve_system_user(identity: str | None) -> str | None:
    """Resolve a Frappe User name or email address to an enabled System User.

    Email Queue recipients are email addresses while in-app/desktop recipients
    are normally User names. Resolve both without assuming that User.name is
    always the email address. Administrator is handled by the access layer and
    remains a valid internal recipient; Guest/Website Users never are.
    """
    value = (identity or "").strip()
    if not value or value == "Guest":
        return None

    row = frappe.db.get_value(
        "User", value, ["name", "enabled", "user_type"], as_dict=True
    )
    if not row and "@" in value:
        row = frappe.db.get_value(
            "User", {"email": value}, ["name", "enabled", "user_type"], as_dict=True
        )
    if not row or not row.enabled:
        return None
    if row.name == "Administrator":
        return row.name
    if row.user_type != "System User":
        return None
    return row.name


def can_receive_project_delivery(
    recipient: str | None, project: str | None, minimum_role: str = "Viewer"
) -> bool:
    """Current project visibility for task-less/tombstone delivery."""
    if not project:
        return False
    user = resolve_system_user(recipient)
    if not user:
        return False

    from batch_projects import access

    if access.is_instance_admin(user):
        return True
    return bool(access.has_at_least(project, minimum_role, user))


def can_receive_task_delivery(
    recipient: str | None, task: str | None, project: str | None = None
) -> bool:
    """Return True only when ``recipient`` can open the referenced task now.

    Live tasks use the same project-or-direct-assignee model as task reads.
    Trashed tasks are different: the normal task surfaces deliberately hide
    them and the Trash view is Manager+, so only Manager+ (or instance admin)
    may receive task-backed trash lifecycle metadata.

    A supplied project must match the task's durable project. That fail-closed
    check catches stale envelopes after cross-project moves instead of routing
    a notification under the old project's authority.
    """
    if not task:
        return False
    user = resolve_system_user(recipient)
    if not user:
        return False

    row = frappe.db.get_value(
        "BP Task", task, ["name", "project", "is_deleted"], as_dict=True
    )
    if not row or not row.project:
        return False
    if project and project != row.project:
        return False

    from batch_projects import access

    if access.is_instance_admin(user):
        return True

    if int(row.is_deleted or 0):
        # list_deleted_tasks is Manager+; a recipient who cannot open Trash
        # must not learn the task's key/title/comment through a side channel.
        return bool(access.has_at_least(row.project, "Manager", user))

    from batch_projects.task_invariants import _user_can_view_task

    return bool(_user_can_view_task(row.project, row.name, user))
