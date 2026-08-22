"""Authorization boundary for BP Workflow (the graph-canvas automation
surface) — the workflow-graph counterpart of automation_security.py.

BP Workflow's action nodes reuse bp_automation_rule._execute() UNCHANGED
(api/automation.py's own docstring: "zero new code") — a node's {type,
config} is exactly the same action-dict shape a BP Automation Rule action
already carries. automation_security.py's per-action-type authority checks
(ERP-mutation scope, outbound token/money-field restriction, assignee
validity, task/project dispatch-scope matching) are therefore reused
directly here rather than reimplemented — a BP Workflow document exposes
the same .scope/.project/.get("project_filter") shape validate_rule_authority
and validate_dispatch already operate on.

Two independent problems, two independent fixes:
  - list_workflows/test_workflow (api/workflows.py, the frontend CRUD
    surface) had their own bugs — an unsafe OR-filter cross-project leak and
    a confused-deputy test-fire — unrelated to the action-authority gap
    below. Fixed by list_workflows/test_workflow here.
  - Nothing validated a workflow's own action nodes at all, at save time or
    execution time, the way automation_security.py does for BP Automation
    Rule. Closed by validate_workflow_authority (doc_events validate) and
    validate_workflow_dispatch (execution-time re-check), both below.
"""

from __future__ import annotations

import json

import frappe


_FIELDS = [
    "name", "title", "scope", "project", "is_active",
    "last_run_at", "last_run_status", "modified",
]


def _parse(value, default):
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _action_dicts(doc) -> list[dict]:
    """Every action-type node in doc.nodes, translated to the {type, config}
    shape automation_security._validate_action_authority expects. Non-action
    nodes (triggers, conditions, delays) map to nothing and are skipped."""
    from batch_projects.api.automation import _NODE_TYPE_TO_ACTION_TYPE

    nodes = _parse(doc.get("nodes"), [])
    if not isinstance(nodes, list):
        return []
    result = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        action_type = _NODE_TYPE_TO_ACTION_TYPE.get(node.get("type"))
        if not action_type:
            continue
        result.append({"type": action_type, "config": node.get("config") or {}})
    return result


def _guard():
    from batch_projects.entitlements import require_feature
    from batch_projects.gateway_guard import verify_gateway_request

    require_feature("automations")
    verify_gateway_request()


def _workspace_admin_required():
    from batch_projects import access

    if not access.is_workspace_admin():
        frappe.throw(
            "You need workspace admin access for workspace-scope automations.",
            frappe.PermissionError,
        )


# ─── CREATE/UPDATE BOUNDARY ─────────────────────────────────────────────────


def validate_workflow_authority(doc, method=None) -> None:
    """doc_events validate hook — the save-time counterpart of
    automation_security.validate_rule_authority. api/workflows.py's
    save_workflow already gates WHO may create/edit a workflow
    (_require_workflow_admin); this hook gates WHAT the saved node graph is
    allowed to contain, for every write path (REST, desk, script), not just
    save_workflow. Reuses automation_security's per-action-type checks
    unchanged — see module docstring."""
    from batch_projects import automation_security

    automation_security._validate_project_filter(doc)
    for action in _action_dicts(doc):
        automation_security._validate_action_authority(doc, action)


# ─── EXECUTION BOUNDARY ─────────────────────────────────────────────────────


def validate_workflow_dispatch(workflow_doc, payload: dict) -> dict:
    """Execution-time re-check for run_workflow_node/run_local_workflow_step
    — protects a definition saved before this hook existed, and a stale or
    tampered row, exactly as automation_security.validate_dispatch does for
    BP Automation Rule. automation_security.validate_dispatch itself is
    reused for the scope/project match (it only touches .scope/.project, and
    its own action-list re-validation loop is a harmless no-op here — BP
    Workflow has no "actions"/"action_type" field for _actions() to find);
    the node-graph action re-validation below is BP Workflow's own on top of
    that, since that's where its real action nodes live."""
    if not workflow_doc.is_active:
        frappe.throw("Workflow is not active.", frappe.PermissionError)

    from batch_projects import automation_security

    payload = automation_security.validate_dispatch(workflow_doc, payload)
    for action in _action_dicts(workflow_doc):
        automation_security._validate_action_authority(workflow_doc, action)
    return payload


@frappe.whitelist()
def run_workflow_node(workflow=None, node=None, payload=None, **kwargs):
    """node_type/config are not accepted here (or by api.automation.
    run_workflow_node below it) — both resolve the node's actual type/config
    from workflow_doc.nodes by `node` id, so the graph this validates and the
    graph that executes are the same read of the same document, not two
    independently-supplied copies that could disagree. Resolving here too
    (not just relying on validate_workflow_dispatch's whole-graph pass) means
    an unknown node is rejected before automation.run_workflow_node is even
    called, with a clear error rather than falling through to its own
    (identical) resolution failure."""
    from batch_projects.api import automation

    automation._assert_service_caller()
    if not workflow or not frappe.db.exists("BP Workflow", workflow):
        return {"status": "Failed", "json": {
            "message": f"workflow {workflow!r} not found",
            "error_code": "workflow_not_found",
        }}
    workflow_doc = frappe.get_doc("BP Workflow", workflow)
    data = automation._as_dict(payload)
    validate_workflow_dispatch(workflow_doc, data)

    action_type, _config = automation._resolve_workflow_node_action(workflow_doc, node)
    if not action_type:
        return {"status": "Failed", "json": {
            "message": f"node {node!r} is not a known action node in workflow {workflow!r}",
            "error_code": "unknown_action_node",
        }}

    return automation.run_workflow_node(workflow=workflow, node=node, payload=payload, **kwargs)


@frappe.whitelist()
def run_local_workflow_step(execution_id=None, node_id=None, payload=None, owner=None,
                            lease_generation=None, **kwargs):
    """Same reasoning as run_workflow_node above — node_type/config are not
    accepted; the workflow and node are resolved from execution_id/node_id
    and validated and executed from that same resolution."""
    from batch_projects.api import automation

    automation._assert_service_caller()
    workflow_name = (
        frappe.db.get_value("BP Workflow Execution", execution_id, "workflow") if execution_id else None
    )
    if not workflow_name or not frappe.db.exists("BP Workflow", workflow_name):
        frappe.throw("Workflow execution has no resolvable workflow.", frappe.PermissionError)
    workflow_doc = frappe.get_doc("BP Workflow", workflow_name)
    data = automation._as_dict(payload)
    validate_workflow_dispatch(workflow_doc, data)

    action_type, _config = automation._resolve_workflow_node_action(workflow_doc, node_id)
    if action_type not in automation._LOCAL_WORKFLOW_ACTIONS:
        frappe.throw("Workflow action is not local-atomic")

    return automation.run_local_workflow_step(
        execution_id=execution_id, node_id=node_id, payload=payload,
        owner=owner, lease_generation=lease_generation, **kwargs
    )


# ─── FRONTEND CRUD SURFACE (api/workflows.py wrappers) ──────────────────────


@frappe.whitelist()
def list_workflows(project=None):
    """Return only workspace rows plus this exact project's rows.

    The original mixed workspace-scope and project-scope rows through a
    single frappe.get_all(or_filters=[...]) call. Frappe's flat or_filters
    cannot express "workspace OR (project AND project=X)" — with filters
    dropped to None on the project-scoped path, the three OR clauses
    ("scope=workspace", "scope=project", "project=X") each match
    independently, so scope="project" alone (with no project match) returned
    every OTHER project's workflows too. Two explicit queries avoid that."""
    _guard()

    rows = []
    if project:
        from batch_projects.api.board import _check_permission

        _check_permission(project, "BP Viewer")
        rows.extend(
            frappe.get_all(
                "BP Workflow",
                filters={"is_active": 1, "scope": "project", "project": project},
                fields=_FIELDS,
                ignore_permissions=True,
            )
        )
        # Workspace rules affect every project, so their metadata remains
        # visible in the project automation list exactly as the existing API
        # intended. Their full graph still requires workspace-admin access in
        # get_workflow().
        rows.extend(
            frappe.get_all(
                "BP Workflow",
                filters={"is_active": 1, "scope": "workspace"},
                fields=_FIELDS,
                ignore_permissions=True,
            )
        )
    else:
        _workspace_admin_required()
        rows = frappe.get_all(
            "BP Workflow",
            filters={"is_active": 1, "scope": "workspace"},
            fields=_FIELDS,
            ignore_permissions=True,
        )

    # Dedupe defensively in case legacy malformed data has contradictory
    # scope/project values.
    by_name = {row.name: row for row in rows}
    return sorted(
        by_name.values(),
        key=lambda row: frappe.utils.get_datetime(row.modified),
        reverse=True,
    )


@frappe.whitelist()
def test_workflow(name, task=None):
    """Bind a project-scoped workflow test fixture to that same project.

    The original accepted an arbitrary task from any project and fired the
    real gateway pipeline using the TASK's project in place of the
    workflow's own — a project-A admin could supply a project-B task and
    have project A's workflow execute its action nodes against project B's
    data. This adapter binds the resource before delegating."""
    _guard()
    if not frappe.db.exists("BP Workflow", name):
        frappe.throw("Workflow not found.")

    workflow = frappe.get_doc("BP Workflow", name)
    from batch_projects.api.workflows import _require_workflow_admin

    _require_workflow_admin(workflow.scope, workflow.project)

    if task:
        task_row = frappe.db.get_value(
            "BP Task", task, ["name", "project", "is_deleted"], as_dict=True
        )
        if not task_row or task_row.is_deleted:
            # Do not reveal whether a guessed task exists in Trash/elsewhere.
            frappe.throw("Task is not available for this workflow test.", frappe.PermissionError)
        if workflow.scope == "project" and task_row.project != workflow.project:
            frappe.throw(
                "The test task must belong to the workflow's project.",
                frappe.PermissionError,
                title="Workflow scope mismatch",
            )
        if workflow.scope == "workspace":
            _workspace_admin_required()

    # The original function re-checks feature, gateway and workflow admin and
    # executes the established gateway path. This adapter adds the missing
    # resource binding without duplicating execution semantics.
    from batch_projects.api.workflows import test_workflow as original

    return original(name, task=task)
