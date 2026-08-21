"""Read-only automation definition data for the proprietary gateway runtime.

This module returns configuration records only. It never evaluates triggers,
conditions, branches, actions, schedules, or workflow state. Those semantics
belong exclusively to bp-gateway.
"""

import frappe

from batch_projects.api.automation_data import _assert_gateway_service_caller


_WORKSPACE_BUCKET = "__workspace__"

_RULE_FIELDS = [
    "name", "rule_name", "scope", "project", "project_filter", "is_active",
    "trigger_event", "trigger_config", "conditions", "actions",
    "action_type", "action_config", "interval_seconds", "bridge_job_id",
]

_WORKFLOW_FIELDS = [
    "name", "title", "scope", "project", "project_filter", "is_active",
    "nodes", "edges", "automation_revision", "automation_definition_hash",
    "bridge_job_id",
]


def _scope_filters(doctype, bucket):
    if bucket == _WORKSPACE_BUCKET:
        return {"scope": "workspace", "is_active": 1}
    if not bucket:
        return None
    return {"scope": "project", "project": bucket, "is_active": 1}


@frappe.whitelist()
def get_active(bucket=None, **_):
    """Return raw active rule/workflow configuration for one scope bucket.

    Scheduled definitions are intentionally included. The gateway decides
    whether a definition belongs to event admission or its scheduler plane.
    """
    _assert_gateway_service_caller()
    rule_filters = _scope_filters("BP Automation Rule", bucket)
    workflow_filters = _scope_filters("BP Workflow", bucket)
    if rule_filters is None or workflow_filters is None:
        return {"rules": [], "workflows": []}

    rules = frappe.get_all(
        "BP Automation Rule",
        filters=rule_filters,
        fields=_RULE_FIELDS,
        order_by="name asc",
    )
    workflows = frappe.get_all(
        "BP Workflow",
        filters=workflow_filters,
        fields=_WORKFLOW_FIELDS,
        order_by="name asc",
    )
    return {"rules": rules, "workflows": workflows}
