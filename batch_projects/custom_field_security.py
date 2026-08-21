"""Security adapters for custom-field schema and ERP link values."""

from __future__ import annotations

import json

import frappe

from batch_projects import access


def _parse(value, default):
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        parsed = json.loads(value)
        return parsed
    except (TypeError, ValueError):
        return default


def _guard():
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()


def _validate_role_order(view_role: str, edit_role: str) -> None:
    """Editing a field can never require less authority than viewing it."""
    if access.rank(edit_role) < access.rank(view_role):
        frappe.throw(
            "A custom field's edit role cannot be lower than its view role.",
            frappe.ValidationError,
            title="Invalid custom-field permission",
        )


@frappe.whitelist()
def create_field(field_label, field_type, description="", options=None,
                 applies_to="Tasks", view_role="Viewer", edit_role="Member",
                 conditional_rules=None, show_in_list=0, owner_project=None):
    _guard()
    _validate_role_order(view_role or "Viewer", edit_role or "Member")
    from batch_projects.api.custom_fields import create_field as original
    return original(
        field_label, field_type, description=description, options=options,
        applies_to=applies_to, view_role=view_role, edit_role=edit_role,
        conditional_rules=conditional_rules, show_in_list=show_in_list,
        owner_project=owner_project,
    )


@frappe.whitelist()
def update_field(name, field_label=None, description=None, field_type=None, options=None,
                 applies_to=None, view_role=None, edit_role=None,
                 conditional_rules=None, show_in_list=None, enabled=None):
    _guard()
    current = frappe.db.get_value(
        "BP Custom Field", name, ["view_role", "edit_role"], as_dict=True
    )
    if not current:
        frappe.throw("Custom field not found.")
    effective_view = view_role if view_role is not None else (current.view_role or "Viewer")
    effective_edit = edit_role if edit_role is not None else (current.edit_role or "Member")
    _validate_role_order(effective_view, effective_edit)

    from batch_projects.api.custom_fields import update_field as original
    return original(
        name, field_label=field_label, description=description,
        field_type=field_type, options=options, applies_to=applies_to,
        view_role=view_role, edit_role=edit_role,
        conditional_rules=conditional_rules, show_in_list=show_in_list,
        enabled=enabled,
    )


@frappe.whitelist()
def search_field_link_options(project, field, txt=""):
    """Permission-aware ERP record picker for a link-type custom field.

    A BP project role is not an ERPNext data-read grant. The target DocType,
    document-level user permissions and permlevel field restrictions all remain
    authoritative. Sites that want broader integration access should grant it
    explicitly rather than route around ERPNext through BatchProjects.
    """
    _guard()
    access.require(project, "Viewer")

    from batch_projects.api.custom_fields import _LINK_DOCTYPES, _attached_fields

    attached = {cf.name: cf for _, cf in _attached_fields(project, "all")}
    cf = attached.get(field)
    if not cf:
        frappe.throw(
            "This field is not available on this project.", frappe.PermissionError
        )
    if cf.field_type != "link":
        frappe.throw("Not a linked-record field.")

    # Never let edit permission exceed visibility, including legacy malformed
    # definitions created before the save-time role-order guard existed.
    if not access.has_at_least(project, cf.view_role or "Viewer") or not access.has_at_least(
        project, cf.edit_role or "Member"
    ):
        frappe.throw(
            "You don't have permission to use this field.", frappe.PermissionError
        )

    options = _parse(cf.options_json, {})
    link_doctype = options.get("link_doctype") if isinstance(options, dict) else None
    if not link_doctype or link_doctype not in _LINK_DOCTYPES:
        return []
    if not frappe.db.exists("DocType", link_doctype):
        return []
    if not frappe.has_permission(
        link_doctype, "read", user=frappe.session.user, raise_exception=False
    ):
        return []

    # Respect field-level (permlevel) permissions too. A title field the user
    # cannot read is neither selected nor searched; the stable document name
    # remains the only label in that case.
    from frappe.model import get_permitted_fields

    permitted = set(
        get_permitted_fields(link_doctype, user=frappe.session.user, permission_type="read")
    )
    title_field = frappe.db.get_value("DocType", link_doctype, "title_field") or "name"
    can_read_title = title_field == "name" or title_field in permitted
    fields = ["name"] + ([title_field] if title_field != "name" and can_read_title else [])

    or_filters = [["name", "like", f"%{txt}%"]] if txt else None
    if txt and title_field != "name" and can_read_title:
        or_filters.append([title_field, "like", f"%{txt}%"])

    try:
        rows = frappe.get_list(
            link_doctype,
            or_filters=or_filters,
            fields=fields,
            limit_page_length=20,
            order_by="modified desc",
        )
    except frappe.PermissionError:
        return []

    return [
        {
            "name": row["name"],
            "label": row.get(title_field) if can_read_title else row["name"],
        }
        for row in rows
    ]
