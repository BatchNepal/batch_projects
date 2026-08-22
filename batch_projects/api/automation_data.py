"""Narrow business-data adapter for the bp-gateway automation runtime.

This module deliberately exposes current business facts and shared service/
idempotency helpers only. Workflow interpretation and orchestration remain in
bp-gateway; action execution remains behind stored ``run_workflow_node`` /
``run_rule_node`` resolution so Frappe continues to enforce definition authority.
"""

import json

import frappe


def _assert_gateway_service_caller():
    """Require a privileged API-token service identity, never a browser session."""
    auth = frappe.get_request_header("Authorization") or ""
    if not auth.lower().startswith("token "):
        frappe.throw("Gateway service token authentication required", frappe.PermissionError)
    user = frappe.session.user
    if user == "Administrator":
        return
    if "System Manager" not in frappe.get_roles(user):
        frappe.throw("Gateway service account requires System Manager", frappe.PermissionError)


def _parse_labels(raw):
    if isinstance(raw, list):
        return [value for value in raw if isinstance(value, str) and value]
    if not isinstance(raw, str) or not raw:
        return []
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return [value for value in decoded if isinstance(value, str) and value] if isinstance(decoded, list) else []


@frappe.whitelist()
def get_context(kind=None, project=None, task=None, **_):
    """Return raw current business facts; the gateway decides what they mean."""
    _assert_gateway_service_caller()

    if kind == "site":
        return {"timezone": frappe.utils.get_system_timezone()}

    if kind == "project":
        if not project or not frappe.db.exists("BP Project", project):
            frappe.throw("Project not found")
        from batch_projects.api.board import _normalize_workflow_states

        doc = frappe.get_cached_doc("BP Project", project)
        states = _normalize_workflow_states(doc.get_workflow_states())
        return {
            "workflow_states": [
                state.get("name")
                for state in states
                if isinstance(state, dict) and state.get("name")
            ]
        }

    if kind == "task":
        if not task or not frappe.db.exists("BP Task", task):
            frappe.throw("Task not found")
        from batch_projects.events import _get_watchers

        doc = frappe.get_doc("BP Task", task)
        reporter_user = ""
        if doc.reporter:
            reporter_user = frappe.db.get_value("Employee", doc.reporter, "user_id") or ""
        return {
            "assignees": [row.user for row in (doc.assignees or []) if row.user],
            "labels": _parse_labels(doc.labels),
            "watchers": list(_get_watchers(doc.name)),
            "reporter_user": reporter_user,
        }

    frappe.throw(f"Unsupported automation data context {kind!r}")


def _duplicate_result(key):
    name = frappe.db.exists("BP Gateway Mutation Receipt", {"idempotency_key": key})
    if not name:
        return None
    raw = frappe.db.get_value("BP Gateway Mutation Receipt", name, "result_json") or "{}"
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        frappe.throw("Existing gateway mutation receipt is corrupt")
    return {"status": "duplicate", "result": result}


def _new_receipt(mutation):
    return frappe.get_doc(
        {
            "doctype": "BP Gateway Mutation Receipt",
            "idempotency_key": mutation["idempotency_key"],
            "operation": mutation["operation"],
            "target_doctype": mutation.get("target_doctype") or "",
            "target_name": mutation.get("target_name") or "",
        }
    ).insert(ignore_permissions=True)
