"""Permission adapter for gateway-owned automation execution history.

The gateway owns execution state; Frappe remains the user/scope authorization
authority. This service-only endpoint answers permission questions only and
never reads or mutates runtime execution state.
"""

import frappe

from batch_projects.api.automation_data import _assert_gateway_service_caller


def _as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = frappe.parse_json(value)
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _definition(workflow_id):
    if not isinstance(workflow_id, str) or ":" not in workflow_id:
        return None
    kind, name = workflow_id.split(":", 1)
    if kind == "rule" and name and frappe.db.exists("BP Automation Rule", name):
        doc = frappe.get_doc("BP Automation Rule", name)
        return {"kind": kind, "name": name, "scope": doc.scope, "project": doc.project}
    if kind == "workflow" and name and frappe.db.exists("BP Workflow", name):
        doc = frappe.get_doc("BP Workflow", name)
        return {"kind": kind, "name": name, "scope": doc.scope, "project": doc.project}
    return None


def _allowed(definition, mode):
    if not definition:
        return False
    scope = definition["scope"]
    project = definition["project"]
    if mode == "admin":
        from batch_projects.api.board import _require_automation_admin
        _require_automation_admin(scope, project)
        return True

    if scope == "project":
        from batch_projects.api.board import _check_permission
        _check_permission(project, "BP Viewer")
        return True

    # Match workflows.py's existing workspace visibility posture: workspace
    # automations are an admin surface because they can span all projects.
    from batch_projects import access
    if frappe.session.user == "Administrator" or access.is_workspace_admin():
        return True
    frappe.throw("Workspace automation access requires workspace admin.", frappe.PermissionError)


@frappe.whitelist()
def check(user=None, workflow_ids=None, mode="view", **_):
    """Batch-check execution visibility/admin authority for one authenticated user."""
    _assert_gateway_service_caller()
    if mode not in ("view", "admin"):
        frappe.throw("mode must be 'view' or 'admin'.")
    workflow_ids = _as_list(workflow_ids)
    if len(workflow_ids) > 200:
        frappe.throw("At most 200 workflow ids may be checked at once.")
    if not user or user == "Guest" or not frappe.db.exists("User", user):
        return {wid: False for wid in workflow_ids}

    original_user = frappe.session.user
    result = {}
    try:
        frappe.set_user(user)
        for workflow_id in workflow_ids:
            allowed = False
            try:
                allowed = _allowed(_definition(workflow_id), mode)
            except (frappe.PermissionError, frappe.ValidationError):
                allowed = False
            result[workflow_id] = bool(allowed)
    finally:
        frappe.set_user(original_user)
    return result
