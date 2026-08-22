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


def _allowed(definition, mode, user):
    if not definition:
        return False
    from batch_projects import access

    if definition["scope"] == "workspace":
        return bool(access.is_workspace_admin(user))

    project = definition["project"]
    if not project or not frappe.db.exists("BP Project", project):
        return False
    if mode == "admin":
        return bool(access.has_at_least(project, "Admin", user))
    return bool(access.has_at_least(project, "Viewer", user))


@frappe.whitelist()
def check(user=None, workflow_ids=None, mode="view", **_):
    """Batch-check execution visibility/admin authority for one authenticated user.

    This endpoint itself is authenticated as the gateway service account, so it
    deliberately does not invoke browser-request gateway guards. It asks the
    shared access model directly about the named browser user instead of
    mutating frappe.session.user inside a privileged service request.
    """
    _assert_gateway_service_caller()
    if mode not in ("view", "admin"):
        frappe.throw("mode must be 'view' or 'admin'.")
    workflow_ids = _as_list(workflow_ids)
    if len(workflow_ids) > 200:
        frappe.throw("At most 200 workflow ids may be checked at once.")
    if not user or user == "Guest" or not frappe.db.exists("User", user):
        return {wid: False for wid in workflow_ids}

    result = {}
    for workflow_id in workflow_ids:
        try:
            result[workflow_id] = bool(_allowed(_definition(workflow_id), mode, user))
        except Exception:
            # Permission lookup is fail-closed. A deleted/corrupt definition
            # must not leak historical execution metadata merely because its
            # runtime row still exists.
            result[workflow_id] = False
    return result
