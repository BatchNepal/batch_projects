"""Permission-aware task-detail read adapters.

The legacy board.get_task implementation resolves linked-task metadata with
frappe.get_all(), which intentionally bypasses permission query conditions.
That is fine for the task the caller already opened, but unsafe for links into
other private projects. This adapter is wired through
``override_whitelisted_methods`` and strips linked records the caller cannot
actually view. It also removes trashed subtasks from the normal live detail
surface.
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
