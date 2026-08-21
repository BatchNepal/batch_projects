"""Safe project schema mutation helpers.

Workflow states, task types and labels are referenced by durable BP Task rows.
They are schemas, not free-form JSON settings. Destructive schema edits must
not silently orphan live task state.
"""

from __future__ import annotations

import json

import frappe


_WORKFLOW_CATEGORIES = {"unstarted", "started", "completed", "cancelled"}


def parse_list(raw, label: str) -> list:
    value = raw
    for _ in range(5):
        if not isinstance(value, str):
            break
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            frappe.throw(f"{label} must be valid JSON.", frappe.ValidationError)
    if not isinstance(value, list):
        frappe.throw(f"{label} must be a list.", frappe.ValidationError)
    return value


def require_admin(project: str) -> None:
    from batch_projects import access
    access.require(project, "Admin")


def active_task_values(project: str, field: str) -> set[str]:
    rows = frappe.get_all(
        "BP Task",
        filters={"project": project, "is_deleted": 0, field: ["is", "set"]},
        pluck=field,
    )
    return {str(v) for v in rows if v not in (None, "")}


def unique_named_rows(rows, label: str) -> list[dict]:
    clean = []
    seen = set()
    for raw in rows:
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                frappe.throw(f"Each {label} must be an object.", frappe.ValidationError)
        if not isinstance(raw, dict):
            frappe.throw(f"Each {label} must be an object.", frappe.ValidationError)
        row = dict(raw)
        name = str(row.get("name") or "").strip()
        if not name:
            frappe.throw(f"Each {label} requires a name.", frappe.ValidationError)
        if name in seen:
            frappe.throw(f"Duplicate {label} name: {name}.", frappe.ValidationError)
        seen.add(name)
        row["name"] = name
        clean.append(row)
    return clean


def assert_referenced_names_survive(
    project: str, field: str, old_names: set, new_names: set, label: str
) -> None:
    removed = old_names - new_names
    if not removed:
        return
    blocked = sorted(removed & active_task_values(project, field))
    if blocked:
        frappe.throw(
            f"Cannot remove or rename {label} {', '.join(repr(v) for v in blocked)} "
            "while active tasks still use it. Move those tasks to a replacement "
            "value first, then retry.",
            frappe.ValidationError,
            title=f"{label.title()} is still in use",
        )
