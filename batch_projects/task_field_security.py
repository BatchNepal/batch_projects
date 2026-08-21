"""Field-level authorization for BP Task mutations.

Record-level access answers whether a user may open or generally edit a task.
Enterprise authorization also needs to answer *which fields* that edit may
change. This module is called from the BP Task validate hook so REST, imports,
SPA APIs and ORM saves cannot silently diverge.

Task-only assignment is deliberately narrower than project Member. Assignment
is a grant to collaborate on one task, not an implicit promotion into project
planning, billing, automation or assignment administration.
"""

from __future__ import annotations

import json

import frappe

from batch_projects import access


_TASK_ONLY_WRITABLE = frozenset({
    "title",
    "description",
    "status",
    "priority",
    "due_date",
    "blocked_reason",
})

_SYSTEM_MANAGED = frozenset({
    "task_key",
    "sequence_no",
    "actual_hours",
    "recurrence_source",
    "submitted_via_intake",
    "bridge_job_id",
    "sales_order",
    "timesheet_detail",
    "is_deleted",
    "deleted_on",
    "deleted_by",
})


def _json_map(value) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def changed_fields(doc, old) -> set[str]:
    if not old:
        return set()
    changed = set()
    for field in doc.meta.fields:
        name = field.fieldname
        if not name or field.fieldtype in {
            "Section Break", "Column Break", "Tab Break", "HTML", "Button"
        }:
            continue
        if doc.get(name) != old.get(name):
            changed.add(name)
    return changed


def _allow_controller_derived(changed: set[str], doc, old) -> set[str]:
    allowed = set(changed)
    if old and old.status != doc.status:
        allowed -= {"started_on", "completed_on", "completed_by", "resolution"}
    if old and (old.blocked_reason or "") != (doc.blocked_reason or ""):
        allowed -= {"blocked_since", "blocked_by"}
    return allowed


def _validate_task_only_scope(doc, old, changed: set[str]) -> None:
    if not old or access.is_instance_admin():
        return
    if access.get_effective_role(old.project, frappe.session.user):
        return
    if not access.is_task_assignee(old.name, frappe.session.user):
        return

    user_changes = _allow_controller_derived(changed, doc, old)
    denied = sorted(user_changes - _TASK_ONLY_WRITABLE)
    if denied:
        frappe.throw(
            "Task-only assignees cannot change project planning, assignment, "
            "billing or system fields: " + ", ".join(denied),
            frappe.PermissionError,
            title="Field permission denied",
        )


def _validate_system_managed(changed: set[str]) -> None:
    if access.is_instance_admin():
        return
    denied = sorted(changed & _SYSTEM_MANAGED)
    if denied:
        frappe.throw(
            "These task fields are maintained by lifecycle, ERP or integration "
            "logic and cannot be edited directly: " + ", ".join(denied),
            frappe.PermissionError,
            title="System-managed field",
        )


def _validate_sensitive_project_fields(doc, old, changed: set[str]) -> None:
    if access.is_instance_admin():
        return

    project = doc.project or (old.project if old else None)
    if not project:
        return

    if "billable" in changed:
        if not access.has_at_least(project, "Manager") or not access.has_capability(
            project, "view_money"
        ):
            frappe.throw(
                "You need Manager access with Money permission to change billing status.",
                frappe.PermissionError,
            )

    if changed & {"is_recurring", "recurrence_frequency", "recurrence_end_date"}:
        if not access.has_at_least(project, "Manager"):
            frappe.throw(
                "You need Manager access to configure task recurrence.",
                frappe.PermissionError,
            )

    if "resolution" in changed and (not old or old.status == doc.status):
        frappe.throw(
            "Resolution can only change as part of a status transition.",
            frappe.PermissionError,
        )


def _changed_custom_values(doc, old) -> dict:
    before = _json_map(old.custom_field_values) if old else {}
    after = _json_map(doc.custom_field_values)
    changed = {}
    for key in set(before) | set(after):
        if key.startswith("_"):
            continue
        if before.get(key) != after.get(key):
            changed[key] = after.get(key)
    return changed


def _custom_field_policy(project: str, field_id: str):
    row = frappe.db.get_value(
        "BP Custom Field",
        field_id,
        ["field_label", "view_role", "edit_role", "field_type", "options_json"],
        as_dict=True,
    )
    if not row:
        return None

    if not access.has_at_least(project, row.view_role or "Viewer"):
        frappe.throw(
            "You cannot edit one or more custom fields that are not visible to you.",
            frappe.PermissionError,
            title="Custom-field permission denied",
        )
    if not access.has_at_least(project, row.edit_role or "Member"):
        frappe.throw(
            f"You need at least {row.edit_role or 'Member'} access to edit '{row.field_label}'.",
            frappe.PermissionError,
        )
    return row


def _validate_link_target_readability(project: str, field_id: str, value, row=None) -> None:
    if value in (None, "", []):
        return
    row = row or _custom_field_policy(project, field_id)
    if not row or row.field_type != "link":
        return
    if not isinstance(value, dict) or not value.get("name"):
        return

    try:
        options = json.loads(row.options_json or "{}")
    except (TypeError, ValueError):
        options = {}
    doctype = options.get("link_doctype") if isinstance(options, dict) else None
    if not doctype:
        return

    try:
        permitted = bool(
            frappe.has_permission(
                doctype,
                "read",
                doc=value.get("name"),
                user=frappe.session.user,
                raise_exception=False,
            )
        )
    except Exception:
        permitted = False
    if not permitted:
        frappe.throw(
            f"You cannot use the selected record for '{row.field_label}'.",
            frappe.PermissionError,
            title="Linked record is not accessible",
        )


def validate_custom_field_mutations(doc, old=None) -> None:
    changed = _changed_custom_values(doc, old)
    if not changed:
        return

    for field_id, value in changed.items():
        row = _custom_field_policy(doc.project, field_id)
        if row:
            _validate_link_target_readability(doc.project, field_id, value, row=row)


def validate_task_field_authority(doc, old=None) -> None:
    """Durable field authorization boundary for a BP Task save."""
    if not old:
        if not access.is_instance_admin():
            if doc.billable and (
                not access.has_at_least(doc.project, "Manager")
                or not access.has_capability(doc.project, "view_money")
            ):
                frappe.throw(
                    "You need Manager access with Money permission to create a billable task.",
                    frappe.PermissionError,
                )
            if doc.reporter:
                own_employee = frappe.db.get_value(
                    "Employee", {"user_id": frappe.session.user}, "name"
                )
                # No Employee mapping is not a loophole: a caller may either
                # omit reporter and let the controller derive it, or submit
                # exactly their own Employee. They may never impersonate an
                # arbitrary Employee id through REST/import.
                if not own_employee or doc.reporter != own_employee:
                    frappe.throw(
                        "You cannot create a task on behalf of another reporter.",
                        frappe.PermissionError,
                    )
        validate_custom_field_mutations(doc, old)
        return

    changed = changed_fields(doc, old)
    if not changed:
        return

    _validate_system_managed(changed)
    _validate_task_only_scope(doc, old, changed)
    _validate_sensitive_project_fields(doc, old, changed)
    validate_custom_field_mutations(doc, old)
