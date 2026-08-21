"""Permission-aware task read adapters.

Legacy board.py contains several read paths that predate the shared task query
engine and use ``frappe.get_all`` directly. These adapters keep public method
names stable while applying task visibility/trash invariants at the boundary.
"""

from __future__ import annotations

import frappe


def _visible_link_names(links) -> set[str]:
    names = {row.get("linked_task") for row in (links or []) if row.get("linked_task")}
    if not names:
        return set()
    rows = frappe.get_all(
        "BP Task",
        filters={"name": ["in", list(names)]},
        fields=["name", "project", "is_deleted"],
    )
    from batch_projects.task_invariants import _user_can_view_task
    user = frappe.session.user
    visible = set()
    for row in rows:
        if row.is_deleted:
            continue
        if _user_can_view_task(row.project, row.name, user):
            visible.add(row.name)
    return visible


def _live_subtask_names(subtasks) -> set[str]:
    names = {row.get("name") for row in (subtasks or []) if row.get("name")}
    if not names:
        return set()
    return set(
        frappe.get_all(
            "BP Task",
            filters={"name": ["in", list(names)], "is_deleted": 0},
            pluck="name",
        )
    )


@frappe.whitelist()
def get_task(issue):
    """Return task detail without leaking inaccessible linked-task metadata."""
    from batch_projects.api import board
    data = board.get_task(issue)

    links = data.get("links") or []
    visible = _visible_link_names(links)
    data["links"] = [row for row in links if row.get("linked_task") in visible]

    subtasks = data.get("subtasks") or []
    live = _live_subtask_names(subtasks)
    data["subtasks"] = [row for row in subtasks if row.get("name") in live]
    return data


@frappe.whitelist()
def get_export_data(project, view=None):
    """Preserve the gateway export shape while excluding soft-deleted tasks."""
    from batch_projects.api import board
    rows = board.get_export_data(project, view=view)
    if not rows:
        return rows

    live_keys = set(
        frappe.get_all(
            "BP Task",
            filters={"project": project, "is_deleted": 0},
            pluck="task_key",
        )
    )
    return [row for row in rows if row.get("key") in live_keys]
