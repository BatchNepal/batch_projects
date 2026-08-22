"""
BP Integration Credential — admin-facing mint/list/revoke + OAuth flow.

OAuth providers supported: Slack, Discord, Microsoft Teams, Google, GitHub.
The credential stores the access+refresh tokens; the bp-gateway engine uses
them when firing webhook actions.
"""

import hashlib
import hmac
import json
import re
import time

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


_GATEWAY_CREDENTIAL_TIMESTAMP_HEADER = "X-BP-Gateway-Timestamp"
_GATEWAY_CREDENTIAL_NONCE_HEADER = "X-BP-Gateway-Nonce"
_GATEWAY_CREDENTIAL_SIGNATURE_HEADER = "X-BP-Gateway-Signature"
_GATEWAY_CREDENTIAL_PATH = "/api/method/batch_projects.api.credentials.get_credential_secret"
_GATEWAY_CREDENTIAL_MAX_SKEW_SECONDS = 300
_GATEWAY_CREDENTIAL_NONCE_RE = re.compile(r"^[0-9a-f]{32,128}$")
_GATEWAY_CREDENTIAL_SIGNATURE_RE = re.compile(r"^v1=([0-9a-f]{64})$")


def _gateway_credential_signature_message(method, path, timestamp, nonce, body):
    body_hash = hashlib.sha256(body).hexdigest()
    return "\n".join((method.upper(), path, timestamp, nonce, body_hash))


def _claim_gateway_credential_nonce(nonce):
    key = f"bp:gateway:credential-secret:nonce:{nonce}"
    return bool(frappe.cache().set(
        key, "1", ex=_GATEWAY_CREDENTIAL_MAX_SKEW_SECONDS, nx=True
    ))


def _verify_gateway_credential_signature(
    secret, method, path, body, headers, now=None, claim_nonce=None
):
    """Verify the endpoint-scoped Gateway identity proof.

    This deliberately does not inspect frappe.session.user or roles. API-token
    authentication identifies the Frappe user; only this fresh HMAC proves the
    request came from the configured Gateway service. Therefore Administrator
    and System Manager browser/API sessions fail exactly like every other
    human session when the proof is absent.
    """
    deny = lambda: frappe.throw(_("Not permitted"), frappe.PermissionError)
    secret = str(secret or "").strip()
    if not secret or method.upper() != "POST" or path != _GATEWAY_CREDENTIAL_PATH:
        deny()

    timestamp = str(headers.get(_GATEWAY_CREDENTIAL_TIMESTAMP_HEADER, "")).strip()
    nonce = str(headers.get(_GATEWAY_CREDENTIAL_NONCE_HEADER, "")).strip()
    supplied = str(headers.get(_GATEWAY_CREDENTIAL_SIGNATURE_HEADER, "")).strip()
    match = _GATEWAY_CREDENTIAL_SIGNATURE_RE.fullmatch(supplied)
    if not timestamp.isdigit() or not _GATEWAY_CREDENTIAL_NONCE_RE.fullmatch(nonce) or not match:
        deny()

    current = int(time.time() if now is None else now)
    if abs(current - int(timestamp)) > _GATEWAY_CREDENTIAL_MAX_SKEW_SECONDS:
        deny()

    message = _gateway_credential_signature_message(method, path, timestamp, nonce, body)
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, match.group(1)):
        deny()

    claim = claim_nonce or _claim_gateway_credential_nonce
    if not claim(nonce):
        deny()


def _verify_gateway_credential_request():
    request = getattr(frappe.local, "request", None)
    if request is None:
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    body = request.get_data(cache=True) or b""
    _verify_gateway_credential_signature(
        frappe.conf.get("bp_gateway_shared_secret"),
        request.method,
        request.path,
        body,
        request.headers,
    )


@frappe.whitelist()
def get_credential_secret(name):
    """Return a decrypted integration credential only to the signed Gateway.

    Human administrators remain able to create, rotate, list, and delete
    credentials through the metadata APIs above. Administrator/System Manager
    roles alone never authorize this plaintext response.
    """
    _verify_gateway_credential_request()
    if not frappe.db.exists("BP Integration Credential", name):
        frappe.throw(_("Credential not found."))
    doc = frappe.get_doc("BP Integration Credential", name)
    return {
        "credential_type": doc.credential_type,
        "value": doc.get_password("value", raise_exception=False) or "",
        "extra_headers": doc.extra_headers or "{}",
    }
