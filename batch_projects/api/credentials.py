"""
BP Integration Credential — admin-facing mint/list/revoke + OAuth flow.

OAuth providers supported: Slack, Discord, Microsoft Teams, Google, GitHub.
The credential stores the access+refresh tokens; the bp-gateway engine uses
them when firing webhook actions.
"""

import json
import frappe
from frappe import _
from frappe.utils import get_url

from batch_projects.entitlements import require_feature


OAUTH_PROVIDERS = {
    "slack_oauth": {
        "label": "Slack",
        "authorize_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "scopes": ["channels:read", "chat:write", "users:read"],
        "icon": "Slack",
    },
    "discord_oauth": {
        "label": "Discord",
        "authorize_url": "https://discord.com/api/oauth2/authorize",
        "token_url": "https://discord.com/api/oauth2/token",
        "scopes": ["bot", "messages.read"],
        "icon": "MessageCircle",
    },
    "teams_oauth": {
        "label": "Microsoft Teams",
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": ["https://graph.microsoft.com/ChannelMessage.Send", "offline_access"],
        "icon": "MessageSquare",
    },
    "google_oauth": {
        "label": "Google",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/gmail.send"],
        "icon": "Mail",
    },
    "github_oauth": {
        "label": "GitHub",
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scopes": ["repo", "issues:write"],
        "icon": "GitHub",
    },
}


def _require_credential_admin():
    from batch_projects import access
    if frappe.session.user == "Administrator":
        return
    if not access.is_workspace_admin():
        frappe.throw(_("You need workspace admin access to manage integration credentials."), frappe.PermissionError)


@frappe.whitelist()
def get_oauth_providers():
    """Return available OAuth providers with their config (no secrets)."""
    return [
        {"key": k, "label": v["label"], "scopes": v["scopes"], "icon": v["icon"]}
        for k, v in OAUTH_PROVIDERS.items()
    ]


@frappe.whitelist()
def get_oauth_authorize_url(provider, owner_project=None):
    """Generate the OAuth authorize URL for a provider.
    The client_id and redirect_uri are read from site_config or environment.
    """
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    _require_credential_admin()

    if provider not in OAUTH_PROVIDERS:
        frappe.throw(f"Unknown OAuth provider: {provider}")

    prov = OAUTH_PROVIDERS[provider]
    conf = frappe.local.conf
    client_id = conf.get(f"bp_oauth_{provider}_client_id") or ""
    if not client_id:
        frappe.throw(f"{prov['label']} OAuth is not configured. Set bp_oauth_{provider}_client_id in site_config.json")

    state = frappe.generate_hash(length=24)
    # Store state temporarily for callback verification
    frappe.cache().set_value(f"oauth_state:{state}", {
        "provider": provider,
        "owner_project": owner_project or None,
        "user": frappe.session.user,
    }, expires_in_sec=600)

    params = {
        "client_id": client_id,
        "redirect_uri": get_url(f"/api/method/batch_projects.api.credentials.oauth_callback"),
        "response_type": "code",
        "scope": " ".join(prov["scopes"]),
        "state": state,
    }
    from urllib.parse import urlencode
    url = f"{prov['authorize_url']}?{urlencode(params)}"
    return {"authorize_url": url, "state": state}


@frappe.whitelist(allow_guest=True)
def oauth_callback():
    """OAuth callback endpoint — handles the redirect from the provider.
    Exchanges the code for tokens and stores them in a BP Integration Credential.
    """
    code = frappe.form_dict.get("code")
    state = frappe.form_dict.get("state")
    error = frappe.form_dict.get("error")

    if error:
        frappe.throw(f"OAuth authorization denied: {error}")

    if not code or not state:
        frappe.throw("Missing code or state parameter.")

    # Verify state
    state_data = frappe.cache().get_value(f"oauth_state:{state}")
    if not state_data:
        frappe.throw("Invalid or expired state. Please try again.")
    frappe.cache().delete_value(f"oauth_state:{state}")

    provider = state_data["provider"]
    owner_project = state_data.get("owner_project")
    user = state_data["user"]

    if provider not in OAUTH_PROVIDERS:
        frappe.throw(f"Unknown OAuth provider: {provider}")

    prov = OAUTH_PROVIDERS[provider]
    conf = frappe.local.conf
    client_id = conf.get(f"bp_oauth_{provider}_client_id") or ""
    client_secret = conf.get(f"bp_oauth_{provider}_client_secret") or ""

    if not client_id or not client_secret:
        frappe.throw(f"{prov['label']} OAuth is not properly configured.")

    # Exchange code for token
    import requests
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": get_url("/api/method/batch_projects.api.credentials.oauth_callback"),
        "grant_type": "authorization_code",
    }
    headers = {"Accept": "application/json"}
    try:
        resp = requests.post(prov["token_url"], data=token_data, headers=headers, timeout=30)
        resp.raise_for_status()
        token_json = resp.json()
    except Exception as e:
        frappe.throw(f"Failed to exchange OAuth code: {str(e)}")

    access_token = token_json.get("access_token") or token_json.get("token") or ""
    refresh_token = token_json.get("refresh_token") or ""
    expires_in = token_json.get("expires_in") or 0

    from frappe.utils import now_datetime, add_to_date
    expiry = add_to_date(now_datetime(), seconds=int(expires_in)) if expires_in else None

    # Create credential
    label = f"{prov['label']} ({user})"
    doc = frappe.get_doc({
        "doctype": "BP Integration Credential",
        "label": label,
        "credential_type": provider,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expiry": expiry,
        "oauth_scopes": json.dumps(token_json.get("scope", prov["scopes"])),
        "owner_project": owner_project or None,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    # Redirect to integrations page with success
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = get_url("/workspace/settings/integrations?oauth=success")


@frappe.whitelist()
def list_credentials(project=None):
    """Never returns `value` — the picker only needs label/type/scope to let
    a user choose one; the Go engine is the only reader of the actual secret
    (via a separate, not-yet-built gateway-facing lookup, same "Frappe holds
    the write, Go does the call" boundary as everything else in the automation engine)."""
    require_feature("automations")
    _require_credential_admin()
    filters = {}
    if project:
        filters = {"owner_project": ["in", [project, ""]]}
    return frappe.get_all(
        "BP Integration Credential",
        filters=filters,
        fields=["name", "label", "credential_type", "owner_project", "creation"],
        order_by="creation desc",
        ignore_permissions=True,
    )


@frappe.whitelist()
def create_credential(label, credential_type="bearer_token", value=None, extra_headers=None, owner_project=None):
    require_feature("automations")
    _require_credential_admin()
    doc = frappe.get_doc({
        "doctype": "BP Integration Credential",
        "label": label,
        "credential_type": credential_type,
        "value": value,
        "extra_headers": extra_headers or "{}",
        "owner_project": owner_project or None,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "label": doc.label, "credential_type": doc.credential_type}


@frappe.whitelist()
def delete_credential(name):
    require_feature("automations")
    _require_credential_admin()
    if not frappe.db.exists("BP Integration Credential", name):
        frappe.throw(_("Credential not found."))
    frappe.delete_doc("BP Integration Credential", name, ignore_permissions=True)
    frappe.db.commit()
    return {"status": "deleted"}


@frappe.whitelist()
def get_credential_secret(name):
    """The gateway-facing lookup list_credentials' own docstring flagged as
    'not-yet-built' — WORKPLAN-PHASE25 C3. Service-account ONLY (never
    _require_credential_admin/workspace-admin — a browser session, even an
    admin one, must never see a decrypted secret; only the Go engine calling
    server-to-server does). Mirrors automation.py's _assert_service_caller
    exactly rather than importing across modules for one one-line check."""
    user = frappe.session.user
    if user != "Administrator" and "System Manager" not in frappe.get_roles(user):
        frappe.throw("Not permitted", frappe.PermissionError)
    if not frappe.db.exists("BP Integration Credential", name):
        frappe.throw(_("Credential not found."))
    doc = frappe.get_doc("BP Integration Credential", name)
    return {
        "credential_type": doc.credential_type,
        "value": doc.get_password("value", raise_exception=False) or "",
        "extra_headers": doc.extra_headers or "{}",
    }
