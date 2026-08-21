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


def _finish(project: str) -> None:
    frappe.db.commit()
    from batch_projects.cache import invalidate_project
    invalidate_project(project)


@frappe.whitelist()
def update_project_workflow(project, workflow_states):
    require_admin(project)
    rows = unique_named_rows(parse_list(workflow_states, "workflow_states"), "workflow state")
    if not rows:
        frappe.throw("A project must have at least one workflow state.", frappe.ValidationError)

    names = {row["name"] for row in rows}
    for row in rows:
        category = str(row.get("category") or "unstarted").strip().lower()
        if category not in _WORKFLOW_CATEGORIES:
            frappe.throw(
                f"Workflow state '{row['name']}' has invalid category '{category}'.",
                frappe.ValidationError,
            )
        row["category"] = category

        allowed = row.get("allowed_to")
        if allowed is None:
            continue
        if not isinstance(allowed, list):
            frappe.throw(
                f"Workflow state '{row['name']}' has invalid transition rules.",
                frappe.ValidationError,
            )
        normalized = []
        seen_targets = set()
        for entry in allowed:
            if isinstance(entry, str):
                target = entry.strip()
                min_role = None
            elif isinstance(entry, dict):
                target = str(entry.get("name") or "").strip()
                min_role = entry.get("min_role") or None
            else:
                frappe.throw("Workflow transitions must be names or objects.", frappe.ValidationError)
            if not target or target not in names:
                frappe.throw(
                    f"Workflow state '{row['name']}' points to unknown state '{target}'.",
                    frappe.ValidationError,
                )
            if target in seen_targets:
                continue
            seen_targets.add(target)
            if min_role:
                from batch_projects import access
                role = access.normalize_role(min_role)
                if role not in {"Manager", "Admin"}:
                    frappe.throw(
                        f"Transition to '{target}' has invalid minimum role '{min_role}'.",
                        frappe.ValidationError,
                    )
                normalized.append({"name": target, "min_role": role})
            else:
                normalized.append(target)
        row["allowed_to"] = normalized

    current = frappe.get_cached_doc("BP Project", project).get_workflow_states()
    old_names = {row.get("name") for row in current if row.get("name")}
    assert_referenced_names_survive(project, "status", old_names, names, "workflow state")

    frappe.db.set_value(
        "BP Project",
        project,
        {
            "workflow_states": json.dumps(rows),
            "schema_version": (frappe.db.get_value("BP Project", project, "schema_version") or 0) + 1,
            "modified": frappe.utils.now(),
        },
    )
    _finish(project)
    return rows


@frappe.whitelist()
def update_project_issue_types(project, issue_types):
    require_admin(project)
    rows = unique_named_rows(parse_list(issue_types, "issue_types"), "task type")
    if not rows:
        frappe.throw("At least one task type is required.", frappe.ValidationError)

    names = {row["name"] for row in rows}
    current = frappe.get_cached_doc("BP Project", project).get_issue_types() or []
    old_names = {
        row.get("name") for row in current
        if isinstance(row, dict) and row.get("name")
    }
    assert_referenced_names_survive(project, "task_type", old_names, names, "task type")

    frappe.db.set_value(
        "BP Project",
        project,
        {"issue_types": json.dumps(rows), "modified": frappe.utils.now()},
    )
    _finish(project)
    return rows
