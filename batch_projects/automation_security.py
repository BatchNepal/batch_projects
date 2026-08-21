"""Delegated-authority boundary for BatchProjects automation.

The gateway callback authenticates as a System Manager service account. That
identity proves *who the caller is*, not what a saved rule is authorized to do.
Rules are durable project/workspace-owned capabilities and must be scoped again
at save time and immediately before execution.
"""

from __future__ import annotations

import json
import re

import frappe

from batch_projects import access
from batch_projects.notification_delivery import (
    can_receive_project_delivery,
    resolve_system_user,
)

_TASK_TOKEN = re.compile(r"\{\{\s*task\.([A-Za-z0-9_]+)\s*\}\}")

# Mirrors task_reads.py's _INTERNAL_TASK_FIELDS / _MONEY_TASK_FIELDS (not yet
# landed on develop-15 as of this PR — inlined here rather than importing a
# module this one doesn't otherwise need, to keep this fix self-contained).
# Reconcile into a single shared definition once task_reads.py merges.
_INTERNAL_TASK_FIELDS = {
    "sequence_no",
    "bridge_job_id",
}
_MONEY_TASK_FIELDS = {"billable", "sales_order"}


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


def _actions(doc) -> list[dict]:
    actions = _parse(doc.get("actions"), [])
    if isinstance(actions, list) and actions:
        return [a for a in actions if isinstance(a, dict)]
    if doc.get("action_type"):
        return [{"type": doc.action_type, "config": _parse(doc.get("action_config"), {})}]
    return []


def _require_rule_admin(doc) -> None:
    if access.is_instance_admin():
        return
    if doc.scope == "workspace":
        if not access.is_workspace_admin():
            frappe.throw(
                "Workspace automations require workspace admin access.",
                frappe.PermissionError,
            )
        return
    if not doc.project or not access.has_at_least(doc.project, "Admin"):
        frappe.throw(
            "Project automations require Admin access on that project.",
            frappe.PermissionError,
        )


def _validate_project_filter(doc) -> None:
    values = _parse(doc.get("project_filter"), [])
    if not isinstance(values, list):
        frappe.throw("Automation project_filter must be a list.", frappe.ValidationError)
    if doc.scope != "workspace" and values:
        frappe.throw(
            "Project-scope automations cannot carry a workspace project filter.",
            frappe.ValidationError,
        )
    for project in values:
        if project and not frappe.db.exists("BP Project", project):
            frappe.throw("Automation project filter contains an unknown project.")


def _validate_outbound_tokens(text: str | None) -> None:
    """Never allow message templates to bypass field-level read policy.

    Dynamic recipients (assignees/watchers/reporter) can have different project
    roles, so a project rule cannot prove at save time that every future
    recipient may read money fields. Internal fields are never public output.
    """
    fields = set(_TASK_TOKEN.findall(text or ""))
    denied = sorted(fields & (_INTERNAL_TASK_FIELDS | _MONEY_TASK_FIELDS))
    if denied:
        frappe.throw(
            "Automation messages cannot expose restricted task fields: "
            + ", ".join(denied),
            frappe.PermissionError,
            title="Restricted automation template field",
        )


def _validate_project_email_recipients(project: str, recipients) -> None:
    for recipient in recipients or []:
        user = resolve_system_user(recipient)
        if not user or not can_receive_project_delivery(user, project, "Viewer"):
            frappe.throw(
                "Project automations may email only current project-visible System Users. "
                "Use a workspace-admin automation for external recipients.",
                frappe.PermissionError,
            )


def _validate_action_authority(doc, action: dict) -> None:
    action_type = action.get("type")
    config = action.get("config") or {}
    if not isinstance(config, dict):
        frappe.throw("Automation action config must be an object.")

    if action_type == "Update ERPNext Document":
        # This action executes with the bridge service identity and can change
        # financial/operational ERP records. A per-project Admin is not an ERP
        # superuser. Workspace scope is the explicit enterprise trust boundary;
        # project_filter may still narrow the rule to one project.
        if doc.scope != "workspace":
            frappe.throw(
                "ERP document mutation is allowed only in workspace-scope automations "
                "managed by a workspace admin.",
                frappe.PermissionError,
            )

    if action_type == "Send Email":
        _validate_outbound_tokens(config.get("subject"))
        _validate_outbound_tokens(config.get("message"))
        if doc.scope == "project":
            _validate_project_email_recipients(doc.project, config.get("to") or [])

    if action_type in ("Notify", "Add Comment"):
        _validate_outbound_tokens(config.get("message") or config.get("comment"))

    if action_type == "Notify" and doc.scope == "project":
        for recipient in config.get("users") or []:
            user = resolve_system_user(recipient)
            if not user or not can_receive_project_delivery(user, doc.project, "Viewer"):
                frappe.throw(
                    "Static notification recipients must currently have project visibility.",
                    frappe.PermissionError,
                )

    if action_type in ("Assign Issue", "Create Issue"):
        # Deferred: requires task_invariants.py (a separate, not-yet-merged
        # PR). Lazy import so this module loads fine without it — this one
        # action-type check is a no-op ImportError-safe skip until that PR
        # lands, not a functioning check yet. Tracked as a residual.
        from batch_projects.task_invariants import _assert_assignable_user
        for user in config.get("assignees") or []:
            _assert_assignable_user(user)


def validate_rule_authority(doc, method=None) -> None:
    """Doc-event save boundary for every automation rule write path."""
    _require_rule_admin(doc)
    _validate_project_filter(doc)
    for action in _actions(doc):
        _validate_action_authority(doc, action)


def _rule_projects(doc) -> set[str]:
    values = _parse(doc.get("project_filter"), [])
    return {v for v in values if v} if isinstance(values, list) else set()


def validate_dispatch(rule_doc, payload: dict) -> dict:
    """Fail closed when a gateway/scheduler payload escapes the saved scope."""
    payload = dict(payload or {})
    project = payload.get("project")
    task = payload.get("task")

    task_row = None
    if task:
        task_row = frappe.db.get_value(
            "BP Task", task, ["name", "project", "is_deleted"], as_dict=True
        )
        # Physical deletion events may legitimately outlive the row. In that
        # case the event's project is still the only resource authority. A live
        # row, however, must agree with the payload exactly.
        if task_row:
            if not project or task_row.project != project:
                frappe.throw("Automation task/project scope mismatch.", frappe.PermissionError)

    if rule_doc.scope == "project":
        if not rule_doc.project or project != rule_doc.project:
            frappe.throw("Automation event is outside the rule's project.", frappe.PermissionError)
        if task_row and task_row.project != rule_doc.project:
            frappe.throw("Automation task is outside the rule's project.", frappe.PermissionError)
    elif rule_doc.scope == "workspace":
        allowed = _rule_projects(rule_doc)
        if allowed and project not in allowed:
            frappe.throw("Automation event is outside the workspace rule filter.", frappe.PermissionError)
        if project and not frappe.db.exists("BP Project", project):
            frappe.throw("Automation event references an unknown project.", frappe.PermissionError)
    else:
        frappe.throw("Automation rule has an invalid scope.", frappe.PermissionError)

    # Revalidate high-risk saved actions at runtime too. This protects legacy
    # rows created before the save hook and direct DB tampering.
    for action in _actions(rule_doc):
        if action.get("type") == "Update ERPNext Document" and rule_doc.scope != "workspace":
            frappe.throw("Project rules cannot mutate ERP documents.", frappe.PermissionError)
        if action.get("type") in ("Notify", "Send Email", "Add Comment"):
            config = action.get("config") or {}
            _validate_outbound_tokens(config.get("subject"))
            _validate_outbound_tokens(config.get("message") or config.get("comment"))

    return payload


@frappe.whitelist()
def apply_action(rule=None, payload=None, **kwargs):
    from batch_projects.api import automation

    automation._assert_service_caller()
    data = automation._as_dict(payload)
    if not rule or not frappe.db.exists("BP Automation Rule", rule):
        return {"status": "skipped", "message": f"rule {rule!r} not found"}
    rule_doc = frappe.get_doc("BP Automation Rule", rule)
    if not rule_doc.is_active:
        return {"status": "skipped", "message": "rule inactive"}
    validate_dispatch(rule_doc, data)
    return automation.apply_action(rule=rule, payload=data, **kwargs)


@frappe.whitelist()
def run_scheduled_event(job_id=None, tenant=None, kind=None, event=None, payload=None, **kwargs):
    from batch_projects.api import automation

    automation._assert_service_caller()
    data = automation._as_dict(payload)
    if kind in ("automation.scheduled", "automation.sla", "automation.deferred"):
        rule = data.get("rule")
        if not rule or not frappe.db.exists("BP Automation Rule", rule):
            return {"status": "skipped", "reason": "rule not found"}
        rule_doc = frappe.get_doc("BP Automation Rule", rule)
        if not rule_doc.is_active:
            return {"status": "skipped", "reason": "rule inactive"}
        # Registration payload carries the rule's project for project scope.
        # Workspace scheduled rules may legitimately have no single project.
        if rule_doc.scope == "project":
            data.setdefault("project", rule_doc.project)
        validate_dispatch(rule_doc, data)
    return automation.run_scheduled_event(
        job_id=job_id, tenant=tenant, kind=kind, event=event, payload=data, **kwargs
    )
