"""Composite BP Task validation entrypoint.

Keeps the existing high-blast-radius invariants in task_invariants.py while
allowing additional schema/security checks to be composed without growing
api/board.py or relying on one write path.
"""

from __future__ import annotations

import json

import frappe

from batch_projects import task_invariants


def _labels(raw) -> list[str]:
    if not raw:
        return []
    value = raw
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            frappe.throw("Task labels must be valid JSON.", frappe.ValidationError)
    if not isinstance(value, list):
        frappe.throw("Task labels must be a list.", frappe.ValidationError)
    return [str(v) for v in value if v not in (None, "")]


def validate_task_labels(doc, old=None) -> None:
    if old and old.project == doc.project and _labels(old.labels) == _labels(doc.labels):
        return
    labels = _labels(doc.labels)
    if len(labels) != len(set(labels)):
        frappe.throw("A task cannot contain the same label more than once.", frappe.ValidationError)
    if not labels:
        return
    raw_catalog = frappe.db.get_value("BP Project", doc.project, "labels") or "[]"
    try:
        catalog = json.loads(raw_catalog) if isinstance(raw_catalog, str) else raw_catalog
    except (TypeError, ValueError):
        frappe.throw(
            "Project labels contain invalid JSON. Repair the project label schema first.",
            frappe.ValidationError,
        )
    if not isinstance(catalog, list):
        frappe.throw("Project label schema must be a list.", frappe.ValidationError)
    valid_names = {
        str(row.get("label") or "").strip()
        for row in catalog
        if isinstance(row, dict) and row.get("label")
    }
    unknown = sorted(set(labels) - valid_names)
    if unknown:
        frappe.throw(
            "Unknown project label(s): " + ", ".join(unknown) +
            ". Create the label in project settings before assigning it to a task.",
            frappe.ValidationError,
            title="Invalid task label",
        )


def validate_link_visibility(doc, old=None) -> None:
    old_signatures = {
        task_invariants._link_signature(row)
        for row in (old.get("links") or [])
    } if old else set()
    for row in (doc.get("links") or []):
        signature = task_invariants._link_signature(row)
        changed = not old or old.project != doc.project or signature not in old_signatures
        if not changed or not row.linked_task:
            continue
        target = frappe.db.get_value(
            "BP Task", row.linked_task, ["name", "project", "is_deleted"], as_dict=True
        )
        if not target or target.is_deleted:
            continue
        if not task_invariants._user_can_view_task(
            target.project, target.name, frappe.session.user
        ):
            frappe.throw(
                "You cannot link this task because you do not have access to the linked task.",
                frappe.PermissionError,
                title="Linked task is not visible",
            )


def _force_dependency_override(doc) -> bool:
    if getattr(doc, "flags", None) and doc.flags.get("ignore_dependency_blockers"):
        return True
    value = getattr(frappe, "form_dict", {}).get("force") if getattr(frappe, "form_dict", None) else None
    if value not in (True, 1, "1", "true", "True", "yes"):
        return False
    # A request-supplied override is only honored for a project Manager+ —
    # otherwise any caller who can save the task at all could set this flag
    # and bypass the completion-dependency block it's meant to enforce.
    from batch_projects import access
    return access.has_at_least(doc.project, "Manager")


def validate_completion_dependencies(doc, old=None) -> None:
    if not old or old.project != doc.project or old.status == doc.status:
        return
    project = frappe.get_cached_doc("BP Project", doc.project)
    completed = set(project.get_completed_statuses())
    if doc.status not in completed or old.status in completed or _force_dependency_override(doc):
        return
    blocker_names = {
        row.linked_task
        for row in (doc.get("links") or [])
        if row.link_type == "is blocked by" and row.linked_task
    }
    if not blocker_names:
        return
    blockers = [
        row for row in frappe.get_all(
            "BP Task",
            filters={"name": ["in", list(blocker_names)], "is_deleted": 0},
            fields=["name", "task_key", "title", "status"],
        )
        if row.status not in completed
    ]
    if not blockers:
        return
    keys = ", ".join(row.task_key or row.name for row in blockers[:5])
    if len(blockers) > 5:
        keys += f" and {len(blockers) - 5} more"
    frappe.throw(
        f"This task cannot be completed while it is blocked by unfinished task(s): {keys}.",
        frappe.ValidationError,
        title="Task is still blocked",
    )


def validate_trash_state(doc, old=None) -> None:
    """Trash is a lifecycle operation, not an ordinary editable task field."""
    new_deleted = int(doc.get("is_deleted") or 0)
    if not old:
        if new_deleted:
            frappe.throw("Create the task first, then use the trash action.", frappe.ValidationError)
        return
    old_deleted = int(old.get("is_deleted") or 0)
    if old_deleted != new_deleted:
        frappe.throw(
            "Task trash state can only be changed through the trash/restore actions.",
            frappe.ValidationError,
            title="Use task lifecycle action",
        )


def validate_task(doc, method=None):
    """One durable validation boundary for BP Task mutations."""
    # A configured project default is a manager-authored assignment policy,
    # not a discretionary access grant by the Member creating this task. It
    # therefore gets one narrowly-scoped insert validator that proves the
    # complete assignee set equals the configured default. Every other write
    # uses the ordinary actor-authority invariant unchanged.
    from batch_projects.task_defaults import validate_materialized_default
    if not validate_materialized_default(doc):
        task_invariants.validate_task_assignees(doc, method=method)

    old = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None

    # Field-level authorization is deliberately before the remaining semantic
    # validators: a caller who is not allowed to mutate a field should learn
    # only that fact, not receive validation details about data they had no
    # authority to change in the first place.
    from batch_projects.task_field_security import validate_task_field_authority
    validate_task_field_authority(doc, old)

    validate_task_labels(doc, old)
    validate_link_visibility(doc, old)
    validate_completion_dependencies(doc, old)
    validate_trash_state(doc, old)
    validate_live_task_edits(doc, old)


def validate_live_task_edits(doc, old=None) -> None:
    """Reject ordinary saves when BOTH old and new rows are deleted, unless
    explicitly allowed. Restore itself is a lifecycle operation handled by
    task_lifecycle.restore_task, which flags the save accordingly."""
    if not old:
        return
    old_deleted = int(old.get("is_deleted") or 0)
    new_deleted = int(doc.get("is_deleted") or 0)
    if old_deleted and new_deleted:
        if not (getattr(doc, "flags", None) and doc.flags.get("allow_trash_edit")):
            frappe.throw(
                "Cannot edit a trashed task. Restore it first.",
                frappe.ValidationError,
                title="Task is trashed",
            )


def require_live_task(name: str, for_update: bool = False):
    """Load a BP Task and reject it if trashed — the common live-task guard
    for task-facing API boundaries. Returns the task doc.

    for_update=True additionally takes a row lock (SELECT ... FOR UPDATE) so a
    read-modify-write boundary holds the row across the mutation."""
    if for_update:
        row = frappe.db.sql(
            "SELECT name, is_deleted FROM `tabBP Task` WHERE name = %s FOR UPDATE",
            name,
            as_dict=True,
        )
        if not row:
            frappe.throw("Task not found.", frappe.DoesNotExistError)
        if row[0].is_deleted:
            frappe.throw("Task has been trashed.", frappe.PermissionError)
        return frappe.get_doc("BP Task", name)
    doc = frappe.get_doc("BP Task", name)
    if doc.is_deleted:
        frappe.throw("Task has been trashed.", frappe.PermissionError)
    return doc
