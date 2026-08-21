"""Authorization adapters for BP Workflow surfaces.

The workflow API mixes workspace-scope and project-scope rows. Frappe's flat
``or_filters`` cannot express ``workspace OR (project AND project=X)`` safely;
using three independent OR clauses leaks every project-scoped workflow. Test
execution also must bind a supplied task to the workflow's authorized project.
"""

from __future__ import annotations

import frappe


_FIELDS = [
    "name", "title", "scope", "project", "is_active",
    "last_run_at", "last_run_status", "modified",
]


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


@frappe.whitelist()
def list_workflows(project=None):
    """Return only workspace rows plus this exact project's rows."""
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

    # Two explicit queries avoid unsafe OR composition; dedupe defensively in
    # case legacy malformed data has contradictory scope/project values.
    by_name = {row.name: row for row in rows}
    return sorted(
        by_name.values(),
        key=lambda row: frappe.utils.get_datetime(row.modified),
        reverse=True,
    )


@frappe.whitelist()
def test_workflow(name, task=None):
    """Bind a project-scoped workflow test fixture to that same project."""
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
