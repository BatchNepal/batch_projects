"""Permission-aware task read adapters.

Legacy board.py contains several read paths that predate the shared task query
engine and use ``frappe.get_all`` directly. These adapters keep public method
names stable while applying task visibility, field-security and trash
invariants at the boundary.
"""

from __future__ import annotations

import json

import frappe


# Internal/integration bookkeeping has no reason to ride in a general task
# detail response. Keeping these server-only also prevents future UI code from
# accidentally turning an implementation detail into a public contract.
_INTERNAL_TASK_FIELDS = {
    "sequence_no",
    "bridge_job_id",
    "timesheet_detail",
    "submitted_via_intake",
    "recurrence_source",
    "deleted_on",
    "deleted_by",
    "is_deleted",
}

# Task-level values that participate directly in invoicing/ERP money context.
# The project's existing view_money capability is the authoritative read gate.
_MONEY_TASK_FIELDS = {"billable", "sales_order"}


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


def _visible_subtask_names(subtasks) -> set[str]:
    """A task-only grant does not imply access to its children."""
    names = {row.get("name") for row in (subtasks or []) if row.get("name")}
    if not names:
        return set()
    rows = frappe.get_all(
        "BP Task",
        filters={"name": ["in", list(names)], "is_deleted": 0},
        fields=["name", "project"],
    )
    from batch_projects.task_invariants import _user_can_view_task
    user = frappe.session.user
    return {
        row.name for row in rows
        if _user_can_view_task(row.project, row.name, user)
    }


def _visible_custom_values(project: str, values) -> dict:
    """Allowlist current attached+viewable field IDs; never leak internal keys.

    This also removes values belonging to fields that were deleted/detached but
    remain in old JSON until the task's next save.
    """
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except (TypeError, ValueError):
            values = {}
    if not isinstance(values, dict) or not values:
        return {}

    from batch_projects import access
    from batch_projects.api.custom_fields import _attached_fields

    visible_ids = {
        cf.name
        for _, cf in _attached_fields(project, "tasks")
        if access.has_at_least(project, cf.view_role or "Viewer")
    }
    return {
        key: value
        for key, value in values.items()
        if key in visible_ids and not str(key).startswith("_")
    }


def _can_read_reference(row) -> bool:
    doctype = row.get("ref_doctype")
    name = row.get("ref_name")
    if not doctype or not name:
        return False
    try:
        return bool(
            frappe.has_permission(
                doctype,
                "read",
                doc=name,
                user=frappe.session.user,
                raise_exception=False,
            )
        )
    except Exception:
        return False


def _sanitize_task_fields(data: dict) -> dict:
    from batch_projects import access

    project = data.get("project")
    for field in _INTERNAL_TASK_FIELDS:
        data.pop(field, None)

    if project and not access.has_capability(project, "view_money"):
        for field in _MONEY_TASK_FIELDS:
            data.pop(field, None)

    data["custom_field_values"] = _visible_custom_values(
        project, data.get("custom_field_values")
    ) if project else {}

    # ERP references are row-level resources in their own right. Having access
    # to the BP Task is not permission to discover Sales Orders, Invoices,
    # Employees, etc. through their identifiers or generated Desk URLs.
    data["references"] = [
        row for row in (data.get("references") or []) if _can_read_reference(row)
    ]
    return data


@frappe.whitelist()
def get_task(issue):
    """Return task detail with resource and field-level authorization."""
    from batch_projects.api import board
    data = board.get_task(issue)

    links = data.get("links") or []
    visible = _visible_link_names(links)
    data["links"] = [row for row in links if row.get("linked_task") in visible]

    subtasks = data.get("subtasks") or []
    visible_subtasks = _visible_subtask_names(subtasks)
    data["subtasks"] = [
        row for row in subtasks if row.get("name") in visible_subtasks
    ]
    return _sanitize_task_fields(data)


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
