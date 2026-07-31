"""
batch_projects/api/audit.py
────────────────────────────
Business-event audit trail. record() is the write side, called by
bp-gateway's internal/audit.Writer (service-account-authed, same pattern as
automation.py's apply_action/list_active_rules) — writes stay transactional
inside Frappe rather than the gateway owning its own SQL store. list_events()
is the read side for the admin-facing audit log panel, gated on the
"audit_log" (Enterprise-tier) feature — reuses the existing
entitlements.require_feature() gate, same as every other paid feature.
"""

from __future__ import annotations

import json

import frappe
from frappe import _


def _assert_service_caller():
    """Only the bridge service account (System Manager / Administrator) may call."""
    user = frappe.session.user
    if user == "Administrator":
        return
    if "System Manager" in frappe.get_roles(user):
        return
    frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def record(event=None, actor=None, project=None, outcome="success", detail=None):
    """Create one BP Audit Log row. Service-caller only — see gateway's
    internal/audit.Writer.Log(). Never raises into a caller that's already
    fire-and-forget on its side; a failure here is just a dropped audit
    entry, not a broken operation."""
    _assert_service_caller()
    if not event or not actor:
        frappe.throw(_("event and actor are required"))

    if isinstance(detail, dict):
        detail = json.dumps(detail)
    elif detail is not None and not isinstance(detail, str):
        detail = json.dumps(detail, default=str)

    doc = frappe.get_doc({
        "doctype": "BP Audit Log",
        "event": event,
        "actor": actor,
        "project": project if project and frappe.db.exists("BP Project", project) else None,
        "outcome": outcome or "success",
        "detail": detail,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "ok", "name": doc.name}


@frappe.whitelist()
def list_events(project=None, event=None, limit=50, start=0):
    """Read the audit trail — Enterprise-tier gated. System Manager only
    (same as the doctype's own permission), regardless of tier, so a lower
    tier can never see this even via a direct API call."""
    if "System Manager" not in frappe.get_roles(frappe.session.user) and frappe.session.user != "Administrator":
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    from batch_projects.entitlements import require_feature
    require_feature("audit_log")

    filters = {}
    if project:
        filters["project"] = project
    if event:
        filters["event"] = ["like", f"%{event}%"]

    rows = frappe.get_all(
        "BP Audit Log",
        filters=filters,
        fields=["name", "event", "actor", "project", "outcome", "detail", "creation"],
        order_by="creation desc",
        limit_page_length=min(int(limit or 50), 200),
        limit_start=int(start or 0),
    )
    return rows
