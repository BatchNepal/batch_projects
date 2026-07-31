"""
batch_projects/api/notifications_admin.py
───────────────────────────────────────────
notification templates + custom notification rules. Workspace-
admin-only (access.is_workspace_admin), mirroring how BP Workspace Settings
itself is gated. Rules are additionally Team+ (entitlements.require_feature
"notification_rules") — deliberately a SEPARATE flag from "automations" (the
Go-binary, document-mutating tier); rules here are routing only.

Templates are not tier-gated — WORKPLAN only calls out custom RULES as
Team+; overriding an email's wording is treated the same as any other
workspace-admin content customization.
"""

import frappe
import json

from batch_projects import access
from batch_projects.entitlements import require_feature


def _guard():
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()


def _require_admin():
    _guard()
    if not access.is_workspace_admin():
        frappe.throw("You need workspace admin access for this.", frappe.PermissionError)


def _parse_json(value, default):
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


# ─── EVENT / VARIABLE REGISTRY ───────────────────────────────────────────────
# The event_key list mirrors BP Notification Template's Select options
# exactly (events.py's notification_type vocabulary + "Rule" for rule-
# triggered sends, which fall through email_templates.py's generic branch).
EVENT_KEYS = [
    "Assignment", "Unassigned", "Comment", "Mention", "Status Change",
    "Update", "Due Soon", "Overdue", "Sprint", "Rule",
]

# Which variables are actually populated for each event — the "whitelisted
# variable context" the plan doc promises; also drives the Edit drawer's
# variable chips.
EVENT_VARIABLES = {
    "Assignment":    ["actor_name", "task_key", "task_title", "url", "priority", "due_date"],
    "Unassigned":    ["actor_name", "task_key", "task_title", "url"],
    "Comment":       ["actor_name", "task_key", "task_title", "url", "comment_text"],
    "Mention":       ["actor_name", "task_key", "task_title", "url", "comment_text"],
    "Status Change": ["actor_name", "task_key", "task_title", "url", "from_status", "to_status"],
    "Update":        ["actor_name", "task_key", "task_title", "url"],
    "Due Soon":      ["task_key", "task_title", "url", "due_date"],
    "Overdue":       ["task_key", "task_title", "url"],
    "Sprint":        ["actor_name", "task_key", "task_title", "url", "message"],
    "Rule":          ["actor_name", "task_key", "task_title", "url", "message"],
}

# Sample values for the live preview endpoint — NEVER a real task/user.
_SAMPLE_CONTEXT = {
    "actor_name": "Jordan Rivera", "task_key": "FWD-42",
    "task_title": "Fix the checkout timeout bug", "url": "#",
    "priority": "High", "due_date": "2026-08-01",
    "comment_text": "Can we get eyes on this before the release?",
    "from_status": "In Progress", "to_status": "Done",
    "message": "Sprint “August Cycle” started",
}


@frappe.whitelist()
def get_notification_templates():
    _require_admin()
    rows = {
        r.name: r for r in frappe.get_all(
            "BP Notification Template",
            fields=["name as event_key", "subject", "body", "enabled"],
        )
    }
    return [
        {**(rows.get(k) or {"event_key": k, "subject": "", "body": "", "enabled": 0}),
         "variables": EVENT_VARIABLES.get(k, [])}
        for k in EVENT_KEYS
    ]


@frappe.whitelist()
def update_notification_template(event_key, subject="", body="", enabled=0):
    _require_admin()
    if event_key not in EVENT_KEYS:
        frappe.throw(f"Unknown event '{event_key}'.")

    if frappe.db.exists("BP Notification Template", event_key):
        doc = frappe.get_doc("BP Notification Template", event_key)
    else:
        doc = frappe.new_doc("BP Notification Template")
        doc.event_key = event_key

    doc.subject = subject or ""
    doc.body = body or ""
    doc.enabled = 1 if enabled else 0
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def preview_notification_template(event_key, subject="", body=""):
    """Render against FAKE sample values — never a real task or user — so
    admins can iterate without notifying anyone."""
    _require_admin()
    if event_key not in EVENT_KEYS:
        frappe.throw(f"Unknown event '{event_key}'.")

    ctx = {k: _SAMPLE_CONTEXT.get(k, "") for k in EVENT_VARIABLES.get(event_key, [])}
    try:
        rendered_subject = frappe.render_template(subject or "", ctx)
        rendered_body = frappe.render_template(body or "", ctx)
    except Exception as e:
        frappe.throw(f"Template error: {e}")

    from batch_projects.email_templates import build_custom_notification_email
    html = build_custom_notification_email(
        event_key, ctx.get("task_key", ""), rendered_body,
        frappe.utils.get_url("/workspace/account"),
    )
    return {"subject": rendered_subject, "html": html}


# ─── RULES ───────────────────────────────────────────────────────────────────

_RULE_FIELDS = ["name", "rule_name", "event", "project", "enabled", "mute",
                "conditions_json", "recipients_json", "channels_json"]


def _rule_dict(doc) -> dict:
    return {
        "name": doc.name,
        "rule_name": doc.rule_name,
        "event": doc.event,
        "project": doc.project or "",
        "enabled": bool(doc.enabled),
        "mute": bool(doc.mute),
        "conditions": _parse_json(doc.conditions_json, []),
        "recipients": _parse_json(doc.recipients_json, []),
        "channels": _parse_json(doc.channels_json, ["in_app", "email", "desktop"]),
    }


@frappe.whitelist()
def get_notification_rules():
    _require_admin()
    require_feature("notification_rules")
    names = frappe.get_all("BP Notification Rule", pluck="name", order_by="modified desc")
    return [_rule_dict(frappe.get_doc("BP Notification Rule", n)) for n in names]


@frappe.whitelist()
def create_notification_rule(rule_name, event, project=None, conditions=None,
                              recipients=None, channels=None, mute=0, enabled=1):
    _require_admin()
    require_feature("notification_rules")

    doc = frappe.new_doc("BP Notification Rule")
    doc.rule_name = rule_name
    doc.event = event
    doc.project = project or None
    doc.conditions_json = json.dumps(_parse_json(conditions, []))
    doc.recipients_json = json.dumps(_parse_json(recipients, []))
    doc.channels_json = json.dumps(_parse_json(channels, ["in_app", "email", "desktop"]))
    doc.mute = 1 if mute else 0
    doc.enabled = 1 if enabled else 0
    doc.flags.ignore_permissions = True
    doc.insert()
    frappe.db.commit()
    return _rule_dict(doc)


@frappe.whitelist()
def update_notification_rule(name, rule_name=None, event=None, project=None,
                              conditions=None, recipients=None, channels=None,
                              mute=None, enabled=None):
    _require_admin()
    require_feature("notification_rules")

    doc = frappe.get_doc("BP Notification Rule", name)
    if rule_name is not None:
        doc.rule_name = rule_name
    if event is not None:
        doc.event = event
    if project is not None:
        doc.project = project or None
    if conditions is not None:
        doc.conditions_json = json.dumps(_parse_json(conditions, []))
    if recipients is not None:
        doc.recipients_json = json.dumps(_parse_json(recipients, []))
    if channels is not None:
        doc.channels_json = json.dumps(_parse_json(channels, ["in_app", "email", "desktop"]))
    if mute is not None:
        doc.mute = 1 if mute else 0
    if enabled is not None:
        doc.enabled = 1 if enabled else 0
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return _rule_dict(doc)


@frappe.whitelist()
def delete_notification_rule(name):
    _require_admin()
    require_feature("notification_rules")
    frappe.delete_doc("BP Notification Rule", name, ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}
