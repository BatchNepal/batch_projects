"""Data-layer permission hooks for BP Notification.

The notification center has dedicated authorization-aware endpoints, but Frappe
also exposes DocTypes through generic REST/ListView/report paths. These hooks
mirror the final-delivery rule there so ``recipient == user`` is necessary but
not sufficient for persisted task metadata after access revocation.
"""

from __future__ import annotations

import frappe


def _is_admin(user: str) -> bool:
    from batch_projects import access
    return access.is_instance_admin(user)


def _sql_values(values) -> str:
    return ", ".join(frappe.db.escape(v) for v in values if v)


def _scope(user: str):
    """Return (visible_projects, direct_tasks), None projects means all."""
    from batch_projects.permissions import _rebac_scope, get_accessible_projects

    rebac = _rebac_scope(user)
    if rebac is not None:
        projects, tasks = rebac
        return set(projects or []), set(tasks or [])
    projects = get_accessible_projects(user)
    if projects is None:
        return None, set()
    direct = set(
        frappe.get_all(
            "BP Task Assignee",
            filters={"user": user, "parenttype": "BP Task"},
            pluck="parent",
        )
    )
    return set(projects), direct


def _project_sql(column: str, projects) -> str:
    if projects is None:
        return "1=1"
    if not projects:
        return "1=0"
    return f"{column} in ({_sql_values(projects)})"


def query_conditions(user=None):
    user = user or frappe.session.user
    if _is_admin(user):
        return ""

    recipient = f"`tabBP Notification`.`recipient` = {frappe.db.escape(user)}"
    projects, direct_tasks = _scope(user)
    visible_project = _project_sql("t.project", projects)
    visible_tombstone_project = _project_sql("`tabBP Notification`.`project`", projects)

    direct_clause = "1=0"
    if direct_tasks:
        direct_clause = f"t.name in ({_sql_values(direct_tasks)})"

    live_task = f"""
        `tabBP Notification`.`task` in (
            select t.name from `tabBP Task` t
            where t.is_deleted = 0
              and (({visible_project}) or ({direct_clause}))
        )
    """

    # Trash is a Manager+ surface. Visibility/team fallback is Viewer only, so
    # deleted task notifications require an explicit Manager/Admin project role.
    deleted_manager = f"""
        `tabBP Notification`.`task` in (
            select t.name from `tabBP Task` t
            where t.is_deleted = 1
              and t.project in (
                  select pm.parent from `tabBP Project Member` pm
                  where pm.user = {frappe.db.escape(user)}
                    and pm.role in ('Manager', 'Admin')
              )
        )
    """

    taskless = f"""
        (
            (`tabBP Notification`.`task` is null or `tabBP Notification`.`task` = '')
            and (
                `tabBP Notification`.`notification_type` != 'Task Deleted'
                or ({visible_tombstone_project})
            )
        )
    """

    return f"({recipient}) and (({taskless}) or ({live_task}) or ({deleted_manager}))"


def has_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if _is_admin(user):
        return True
    if doc.get("recipient") != user:
        return False
    if doc.get("__islocal"):
        # BPNotification.validate() applies the durable insertion check. This
        # permits the normal server-side notification producer to create rows.
        return True

    from batch_projects.notification_delivery import (
        can_receive_project_delivery,
        can_receive_task_delivery,
    )

    if doc.get("task"):
        return can_receive_task_delivery(user, doc.get("task"), doc.get("project"))
    if doc.get("notification_type") == "Task Deleted" and doc.get("project"):
        return can_receive_project_delivery(user, doc.get("project"), "Viewer")
    return True
