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


# Fields a task-only assignee may directly change. Derived lifecycle fields
# caused by status/blocked_reason are handled separately below.
_TASK_ONLY_WRITABLE = frozenset({
    "title",
    "description",
    "status",
    "priority",
    "due_date",
    "blocked_reason",
})

# These fields are integration/accounting/system authority, not ordinary task
# edits. Instance admins and trusted system processes may update them; normal
# project users must use the dedicated semantic action (where one exists).
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
    """Remove lifecycle fields that the controller derives from an allowed edit."""
    allowed = set(changed)
    if old and old.status != doc.status:
        allowed -= {"started_on", "completed_on", "completed_by", "resolution"}
    if old and (old.blocked_reason or "") != (doc.blocked_reason or ""):
        allowed -= {"blocked_since", "blocked_by"}
    return allowed


def _validate_task_only_scope(doc, old, changed: set[str]) -> None:
    if not old or access.is_instance_admin():
        return

    # A real project role uses the project's normal field/action policy. This
    # guard only narrows the exceptional one-task assignment grant.
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
    """Fields whose effect exceeds an ordinary Member task edit."""
    if access.is_instance_admin():
        return

    project = doc.project or (old.project if old else None)
    if not project:
        return

    # Billable classification affects invoicing/money surfaces. Keep the
    # existing view_money capability as a second gate, but require Manager+
    # for the mutation itself until manage_money becomes its own capability.
    if "billable" in changed:
        if not access.has_at_least(project, "Manager") or not access.has_capability(
            project, "view_money"
        ):
            frappe.throw(
                "You need Manager access with Money permission to change billing status.",
                frappe.PermissionError,
            )

    # Recurrence creates future work and scheduler jobs. It is project
    # administration, not a normal content edit.
    if changed & {"is_recurring", "recurrence_frequency", "recurrence_end_date"}:
        if not access.has_at_least(project, "Manager"):
            frappe.throw(
                "You need Manager access to configure task recurrence.",
                frappe.PermissionError,
            )

    # Resolution is lifecycle state. The controller may derive it while status
    # changes; an unrelated save must not rewrite closure history directly.
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
            # Internal namespaces such as _checklist have their own endpoints
            # and permission contract; they are not user-defined fields.
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

    # Edit authority must be a subset of view authority even for legacy field
    # definitions that predate the schema save-time invariant.
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
        return  # type validation reports the clean validation error later

    try:
        options = json.loads(row.options_json or "{}")
    except (TypeError, ValueError):
        options = {}
    doctype = options.get("link_doctype") if isinstance(options, dict) else None
    if not doctype:
        return

    # Never reveal whether a guessed record name exists. Permission failure and
    # non-existence use the same message at this boundary.
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

    # This closes bulk-update / REST / ORM bypasses: every changed custom field
    # is checked at the durable document boundary, not only in board.update_task.
    for field_id, value in changed.items():
        row = _custom_field_policy(doc.project, field_id)
        if row:
            _validate_link_target_readability(doc.project, field_id, value, row=row)


def validate_task_field_authority(doc, old=None) -> None:
    """Durable field authorization boundary for a BP Task save."""
    if not old:
        # A Member may create a task, but billing classification is still a
        # Manager+Money decision. Reporter is controller-derived unless an
        # instance admin/import process intentionally supplies one.
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
                if own_employee and doc.reporter != own_employee:
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
