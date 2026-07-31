"""
batch_projects/gateway_guard.py
────────────────────────────────
Verifies that API requests to batch_projects came through the bp-gateway,
and — for cross-origin browser sessions — re-scopes the effective Frappe
user to whoever the gateway asserts, before any business logic runs.

The gateway signs every proxied request with an HMAC-SHA256 signature:
    X-BP-Gateway-Sig: hex(HMAC-SHA256(shared_secret,
        "bp-gw:" + ts + ":" + method + ":" + path + ":" + acting_user))
    X-BP-Gateway-Ts:          unix timestamp
    X-BP-Acting-User:         "" for same-origin (sid cookie) traffic; the
                               real user's email for cross-origin (bearer
                               JWT) traffic, ALWAYS included in the
                               signature input so it can't be stripped or
                               forged independently of it.

verify_gateway_request() (opt-in, called from selected whitelisted methods)
verifies the signature and rejects the request if it's missing/invalid —
closing the direct-to-Frappe bypass vector for those specific endpoints.

apply_gateway_identity() (wired globally as a before_request hook — see
hooks.py) is the identity handoff: cross-origin browsers can only reach
Frappe by riding on the gateway's service-account credential (Frappe has no
notion of the gateway's own JWTs), so without this hook every such request
would silently execute AS the service account — a real privilege escalation,
since that account holds System Manager rights. This hook re-scopes
frappe.session.user to the REAL asserted user immediately, so every
permission check downstream sees them, never the service account. It is a
no-op whenever X-BP-Gateway-Sig is absent (same-origin traffic, or anything
not proxied by the gateway) or when acting_user is empty (same-origin
sid-cookie traffic already has its own correct user).

Config (site_config.json):
    bp_gateway_shared_secret   — must EQUAL gateway's FRAPPE_SHARED_SECRET

Leave unset ⇒ both checks are skipped (dev without gateway enforcement) —
and, in that mode, apply_gateway_identity() never touches session.user.

IMPORTANT — always raise frappe.PermissionError here, NEVER
frappe.AuthenticationError: Frappe's own core exception handler
(frappe/app.py handle_exception) has a blanket rule — ANY AuthenticationError
raised ANYWHERE during a request, regardless of source, causes
login_manager.clear_cookies(), i.e. a REAL logout, as a side effect. These
two functions reject a specific REQUEST as improperly routed; they are not
asserting the user's actual login is invalid. Using AuthenticationError here
once meant every same-origin call to a gateway-guarded endpoint — which is
completely normal on a topology where Frappe's own domain isn't gateway-
fronted, e.g. this app's own SPA loads and fires a few calls before its
cross-origin bridge session finishes bootstrapping — silently logs the user
out: login succeeds, /app (desk) works, but /workspace (this app's SPA)
logs the user straight back out, every time.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import frappe
from frappe import _

# Clock skew tolerance — generous enough for clock drift between containers.
_MAX_CLOCK_SKEW_SECONDS = 300
_MIN_SECRET_LEN = 32


# Paths that are allowed before the bridge is bootstrapped — these are the
# very first calls the SPA makes to establish a bridge session.
_PRE_BRIDGE_PATHS = {
    "/api/method/batch_projects.api.session.mint_bridge_token",
    "/api/method/batch_projects.api.board.get_session_info",
}


def _requires_gateway(path: str) -> bool:
    """True if this batch_projects API path must be gateway-verified."""
    if not path.startswith("/api/method/batch_projects."):
        return False
    # Pre-bridge endpoints are the SPA's first calls — they must work before
    # the gateway session exists. They're narrow (session info, token mint)
    # and carry no project data, so direct access is safe.
    if path in _PRE_BRIDGE_PATHS:
        return False
    return True


def verify_gateway_request() -> None:
    """Verify the request came through the bp-gateway. Raises if bypassed.

    Call this at the top of every whitelisted method (or from a shared helper
    like _require_system_user) to ensure no direct-to-Frappe calls slip through.

    Skips verification when:
      - The site hasn't configured bp_gateway_shared_secret (dev/no gateway)
      - The request path is NOT a batch_projects API call (let Frappe pages through)
    """
    # `frappe.request` is a Werkzeug LocalProxy — `frappe.request is None` never
    # works (the proxy object itself is never `None`); it would fall through and
    # raise "object is not bound" on `.path` for any caller with no HTTP request
    # bound (bench console, a scheduled job, an RQ worker). Check the underlying
    # context-local storage directly instead.
    if not getattr(frappe.local, "request", None):
        return  # CLI / background job — not an HTTP request

    req = frappe.request
    path = req.path or ""

    # Only gate batch_projects API calls that aren't pre-bridge endpoints.
    # Frappe pages, login, desk, other apps, and pre-bridge calls
    # (session info, token mint) are untouched.
    if not _requires_gateway(path):
        return

    secret = frappe.conf.get("bp_gateway_shared_secret")
    if not secret:
        # Dev / testing without gateway enforcement — log once per request
        # so operators know this site isn't gated.
        frappe.logger("bp.gateway").warning(
            "bp_gateway_shared_secret not set — gateway verification DISABLED. "
            "batch_projects APIs are callable directly without the gateway."
        )
        return

    if len(secret) < _MIN_SECRET_LEN:
        frappe.throw(
            _("bp_gateway_shared_secret must be at least 32 characters."),
            frappe.ValidationError,
        )

    sig = frappe.get_request_header("X-BP-Gateway-Sig") or ""
    ts_raw = frappe.get_request_header("X-BP-Gateway-Ts") or ""

    if not sig or not ts_raw:
        frappe.throw(
            _("Access denied — requests to batch_projects must come through the bp-gateway."),
            frappe.PermissionError,
        )

    # Replay protection: reject if the timestamp is too old.
    try:
        ts = int(ts_raw)
    except ValueError:
        frappe.throw(
            _("Invalid gateway signature timestamp."),
            frappe.PermissionError,
        )

    now = int(time.time())
    if abs(now - ts) > _MAX_CLOCK_SKEW_SECONDS:
        frappe.throw(
            _("Gateway signature expired — clock skew > {}s.").format(_MAX_CLOCK_SKEW_SECONDS),
            frappe.PermissionError,
        )

    # Recompute the expected signature with the same inputs the gateway used.
    acting_user = frappe.get_request_header("X-BP-Acting-User") or ""
    expected = _compute_signature(secret, ts_raw, req.method, path, acting_user)

    if not hmac.compare_digest(sig, expected):
        frappe.throw(
            _("Invalid gateway signature — request did not come through the bp-gateway."),
            frappe.PermissionError,
        )

    # Mark this request as gateway-verified so downstream code (entitlements.py)
    # can reject spoofed X-BP-* headers on unverified requests.
    frappe.local._bp_gateway_verified = True


def apply_gateway_identity() -> None:
    """auth_hooks entry (hooks.py) — runs inside frappe.auth.validate_auth(),
    after the Authorization header has already been checked for an API key.

    Cross-origin browser sessions ride on the gateway's service-account
    Frappe credential to get past core auth at all (Frappe has no notion of
    the gateway's own JWTs) — by the time this runs, frappe.session.user is
    that service account, which holds System Manager rights. Without this
    function every such request would silently execute AS the service
    account: a real privilege escalation. This re-scopes session.user to the
    REAL user the gateway asserts via a signed header, so every permission
    check from here on sees them, never the elevated service account.

    Runs on every request (that's what auth_hooks means), so it must be cheap
    and safe to no-op: nothing to do unless the gateway actually signed this
    request AND asserted a specific acting user.
    """
    if not getattr(frappe.local, "request", None):
        return  # CLI / background job

    sig = frappe.get_request_header("X-BP-Gateway-Sig") or ""
    if not sig:
        return  # not gateway-proxied (same-origin sid-cookie traffic, or no gateway in front)

    secret = frappe.conf.get("bp_gateway_shared_secret")
    if not secret:
        return  # dev / gateway enforcement disabled — matches verify_gateway_request's skip

    ts_raw = frappe.get_request_header("X-BP-Gateway-Ts") or ""
    acting_user = frappe.get_request_header("X-BP-Acting-User") or ""

    try:
        ts = int(ts_raw)
    except ValueError:
        frappe.throw(_("Invalid gateway signature timestamp."), frappe.PermissionError)

    if abs(int(time.time()) - ts) > _MAX_CLOCK_SKEW_SECONDS:
        frappe.throw(
            _("Gateway signature expired — clock skew > {}s.").format(_MAX_CLOCK_SKEW_SECONDS),
            frappe.PermissionError,
        )

    expected = _compute_signature(secret, ts_raw, frappe.request.method, frappe.request.path, acting_user)
    if not hmac.compare_digest(sig, expected):
        # A present-but-wrong signature is either tampering or a misconfigured
        # secret — either way, never fall through running as whatever core
        # auth resolved (the service account). Fail closed.
        frappe.throw(
            _("Invalid gateway signature — request did not come through the bp-gateway."),
            frappe.PermissionError,
        )

    frappe.local._bp_gateway_verified = True

    if not acting_user:
        return  # same-origin traffic through the gateway — session.user is already correct

    if not frappe.db.exists("User", acting_user) or not frappe.db.get_value("User", acting_user, "enabled"):
        frappe.throw(
            _("Gateway asserted an unknown or disabled user: {0!r}").format(acting_user),
            frappe.PermissionError,
        )

    # frappe.set_user() unconditionally does `local.form_dict = _dict()` as
    # part of resetting the user's session/cache state (see frappe/__init__.py).
    # apply_gateway_identity() runs as an auth_hook — inside validate_auth(),
    # BEFORE frappe.form_dict is populated from the request body — so this
    # silently wiped every proxied POST's arguments, e.g.
    # `get_board() missing 1 required positional argument: 'project'`, on
    # every single cross-origin (bearer/acting-user) request, 100% of the
    # time. Same-origin sid-cookie traffic never hit this (acting_user is
    # empty, this whole branch is skipped), which is why it looked like an
    # intermittent/concurrency bug rather than a deterministic one. Frappe's
    # own core `validate_api_key_secret` guards against this exact footgun by
    # saving/restoring form_dict around its own auth side effects — mirror
    # that here.
    form_dict = frappe.local.form_dict
    frappe.set_user(acting_user)
    frappe.local.form_dict = form_dict


def _compute_signature(secret: str, ts: str, method: str, path: str, acting_user: str = "") -> str:
    """Recompute the HMAC-SHA256 exactly as the gateway's signRequest() does."""
    mac = hmac.new(secret.encode(), digestmod=hashlib.sha256)
    mac.update(f"bp-gw:{ts}:{method}:{path}:{acting_user}".encode())
    return mac.hexdigest()
