"""Narrow webhook configuration/data adapter for bp-gateway.

No trigger matching, signature verification, replay handling, or workflow
execution belongs here. The public Frappe app stores webhook configuration and
usage facts; the proprietary gateway owns the runtime semantics.
"""

import frappe

from batch_projects.api.automation_data import _assert_gateway_service_caller


@frappe.whitelist()
def resolve(token=None, **_):
    """Resolve one opaque webhook routing token for the gateway runtime.

    Existing pre-migration rows can have no signing_secret. The gateway may
    temporarily use its legacy deployment-wide secret for those rows and logs
    that compatibility path; rotating the token/secret removes that fallback.
    """
    _assert_gateway_service_caller()
    if not token:
        return {"found": False}
    name = frappe.db.get_value("BP Webhook Token", {"token": token}, "name")
    if not name:
        return {"found": False}
    doc = frappe.get_doc("BP Webhook Token", name)
    secret = ""
    try:
        secret = doc.get_password("signing_secret", raise_exception=False) or ""
    except Exception:
        # Old rows before the Password field existed are a supported migration
        # case; the caller decides whether its legacy secret is available.
        secret = ""
    return {
        "found": True,
        "name": doc.name,
        "scope": doc.scope,
        "project": doc.project,
        "is_active": bool(doc.is_active),
        "signing_secret": secret,
        "legacy_shared_secret": not bool(secret),
    }


@frappe.whitelist()
def record_verified_delivery(token=None, event=None, **_):
    """Record observability facts after the gateway verified a delivery."""
    _assert_gateway_service_caller()
    if not token:
        return {"updated": False}
    name = frappe.db.get_value("BP Webhook Token", {"token": token}, "name")
    if not name:
        return {"updated": False}
    current = int(frappe.db.get_value("BP Webhook Token", name, "call_count") or 0)
    frappe.db.set_value(
        "BP Webhook Token",
        name,
        {
            "call_count": current + 1,
            "last_used": frappe.utils.now_datetime(),
            "last_event": (event or "")[:140],
        },
        update_modified=False,
    )
    return {"updated": True}
