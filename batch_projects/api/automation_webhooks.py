"""Webhook configuration/data adapter.

Frappe stores webhook configuration and usage facts. bp-gateway exclusively
owns signature verification, replay protection, trigger matching and workflow
execution.
"""

import secrets

import frappe

from batch_projects.api.automation_data import _assert_gateway_service_caller


def _require_webhook_admin():
    from batch_projects.entitlements import require_feature
    from batch_projects.gateway_guard import verify_gateway_request
    from batch_projects import access

    require_feature("webhooks")
    verify_gateway_request()
    if frappe.session.user != "Administrator" and not access.is_workspace_admin():
        frappe.throw("You need workspace admin access for this.", frappe.PermissionError)


@frappe.whitelist()
def resolve(token=None, **_):
    """Service-only resolution of one opaque routing token."""
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
        # Pre-migration row: the gateway can temporarily use its legacy shared
        # secret until this hook is rotated.
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
    """Service-only usage facts after a gateway-verified delivery."""
    _assert_gateway_service_caller()
    if not token:
        return {"updated": False}
    name = frappe.db.get_value("BP Webhook Token", {"token": token}, "name")
    if not name:
        return {"updated": False}
    # Atomic increment: concurrent verified deliveries must not lose usage
    # counts. This is observability data, but there is no reason to race it.
    frappe.db.sql(
        """
        UPDATE `tabBP Webhook Token`
        SET call_count = COALESCE(call_count, 0) + 1,
            last_used = %s,
            last_event = %s
        WHERE name = %s
        """,
        (frappe.utils.now_datetime(), (event or "")[:140], name),
    )
    return {"updated": True}


@frappe.whitelist()
def create_webhook_token(label, scope="project", project=None):
    """Create a hook and return routing token + signing secret exactly once."""
    _require_webhook_admin()
    if scope not in ("workspace", "project"):
        frappe.throw("scope must be 'workspace' or 'project'.")
    if scope == "project":
        if not project or not frappe.db.exists("BP Project", project):
            frappe.throw("An existing project is required for a project webhook.")
    else:
        project = None
    label = (label or "").strip()
    if not label or len(label) > 140:
        frappe.throw("Webhook label is required and must be at most 140 characters.")

    token = secrets.token_urlsafe(24)
    signing_secret = secrets.token_urlsafe(48)
    doc = frappe.get_doc({
        "doctype": "BP Webhook Token",
        "label": label,
        "token": token,
        "signing_secret": signing_secret,
        "scope": scope,
        "project": project,
        "is_active": 1,
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    return {
        "name": doc.name,
        "token": token,
        "signing_secret": signing_secret,
        "label": doc.label,
        "scope": doc.scope,
        "project": doc.project,
        "webhook_path": f"/v1/hooks/{token}",
        "signature_version": "v2",
    }


@frappe.whitelist()
def list_webhook_tokens(project=None):
    """List metadata only. Signing secrets are deliberately never returned."""
    _require_webhook_admin()
    filters = {}
    if project:
        filters = {"project": ["in", [project, ""]]}
    return frappe.get_all(
        "BP Webhook Token",
        filters=filters,
        fields=[
            "name", "label", "token", "scope", "project", "is_active",
            "call_count", "last_used", "last_event", "creation",
        ],
        order_by="creation desc",
    )


@frappe.whitelist()
def rotate_webhook_secret(name):
    """Rotate only the HMAC secret; the webhook URL/token remains stable."""
    _require_webhook_admin()
    if not frappe.db.exists("BP Webhook Token", name):
        frappe.throw("Webhook not found.")
    signing_secret = secrets.token_urlsafe(48)
    doc = frappe.get_doc("BP Webhook Token", name)
    doc.signing_secret = signing_secret
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {
        "name": doc.name,
        "token": doc.token,
        "signing_secret": signing_secret,
        "signature_version": "v2",
    }


@frappe.whitelist()
def revoke_webhook_token(name):
    _require_webhook_admin()
    if not frappe.db.exists("BP Webhook Token", name):
        frappe.throw("Webhook not found.")
    frappe.db.set_value("BP Webhook Token", name, "is_active", 0)
    frappe.db.commit()
    return {"status": "revoked"}
