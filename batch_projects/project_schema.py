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


def active_task_labels(project: str) -> set[str]:
    used = set()
    rows = frappe.get_all(
        "BP Task",
        filters={"project": project, "is_deleted": 0},
        fields=["labels"],
    )
    for row in rows:
        raw = row.get("labels")
        if not raw:
            continue
        try:
            labels = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            frappe.throw(
                "A task contains malformed label data. Repair it before changing "
                "the project label schema.",
                frappe.ValidationError,
                title="Invalid task label data",
            )
        if isinstance(labels, list):
            used.update(str(v) for v in labels if v not in (None, ""))
    return used


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


def assert_workflow_categories_safe(project: str, current: list[dict], incoming: list[dict]) -> None:
    """A lifecycle-category change is a migration for tasks using that state."""
    old = {
        row.get("name"): str(row.get("category") or "unstarted").lower()
        for row in current if row.get("name")
    }
    new = {
        row.get("name"): str(row.get("category") or "unstarted").lower()
        for row in incoming if row.get("name")
    }
    changed = {name for name in old.keys() & new.keys() if old[name] != new[name]}
    if not changed:
        return
    used = active_task_values(project, "status")
    blocked = sorted(changed & used)
    if blocked:
        frappe.throw(
            "Cannot change the lifecycle category of in-use workflow state(s): "
            + ", ".join(blocked)
            + ". Existing tasks carry lifecycle timestamps/resolution derived from "
              "the old category. Migrate those tasks before changing the category.",
            frappe.ValidationError,
            title="Workflow category migration required",
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
    assert_workflow_categories_safe(project, current, rows)

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


@frappe.whitelist()
def update_project_labels(project, labels):
    """Protect the current name-backed label catalog from orphaning tasks."""
    require_admin(project)
    incoming = parse_list(labels, "labels")

    rows = []
    seen_names = set()
    seen_ids = set()
    for raw in incoming:
        if not isinstance(raw, dict):
            frappe.throw("Each label must be an object.", frappe.ValidationError)
        row = dict(raw)
        name = str(row.get("label") or "").strip()
        if not name:
            frappe.throw("Each label requires a name.", frappe.ValidationError)
        if name in seen_names:
            frappe.throw(f"Duplicate label name: {name}.", frappe.ValidationError)
        seen_names.add(name)

        label_id = str(row.get("id") or "").strip()
        if not label_id:
            label_id = "lbl_" + frappe.generate_hash(length=10)
        if label_id in seen_ids:
            frappe.throw(f"Duplicate label id: {label_id}.", frappe.ValidationError)
        seen_ids.add(label_id)
        row["id"] = label_id
        row["label"] = name
        rows.append(row)

    raw_old = frappe.db.get_value("BP Project", project, "labels") or "[]"
    try:
        old_rows = json.loads(raw_old) if isinstance(raw_old, str) else raw_old
    except (TypeError, ValueError):
        frappe.throw("Current project labels contain invalid JSON.", frappe.ValidationError)
    old_rows = [row for row in (old_rows or []) if isinstance(row, dict)]

    old_by_id = {str(row.get("id")): row for row in old_rows if row.get("id")}
    new_by_id = {row["id"]: row for row in rows}
    used = active_task_labels(project)
    blocked = []

    for label_id, old in old_by_id.items():
        old_name = str(old.get("label") or "").strip()
        if not old_name or old_name not in used:
            continue
        new = new_by_id.get(label_id)
        if new is None:
            blocked.append(f"'{old_name}' (delete)")
        elif str(new.get("label") or "").strip() != old_name:
            blocked.append(f"'{old_name}' (rename)")

    old_legacy_names = {
        str(row.get("label") or "").strip()
        for row in old_rows if not row.get("id") and row.get("label")
    }
    removed_legacy = old_legacy_names - seen_names
    blocked.extend(f"'{name}' (delete/rename)" for name in sorted(removed_legacy & used))

    if blocked:
        frappe.throw(
            "Cannot change these labels while active tasks still reference their "
            f"current names: {', '.join(blocked)}. Detach or migrate those task "
            "labels first.",
            frappe.ValidationError,
            title="Label is still in use",
        )

    frappe.db.set_value(
        "BP Project",
        project,
        {"labels": json.dumps(rows), "modified": frappe.utils.now()},
    )
    _finish(project)
    return rows
