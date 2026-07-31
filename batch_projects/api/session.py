"""
batch_projects/api/session.py
─────────────────────────────
Cross-origin bridge bootstrap.

On Frappe Cloud the SPA is served from the FC origin while the bp-gateway runs on
a different origin, so the httpOnly `sid` cookie can't reach the bridge. This
endpoint — called same-origin by the logged-in SPA — mints a short-lived bearer
the SPA hands to the bridge's /v1/session/bootstrap. The bridge verifies it
locally against the shared secret (no callback) and issues its own session JWT.

The token is an HS256 JWS signed with `bp_bridge_bootstrap_secret` (site_config),
which MUST equal the gateway's `auth.bootstrap_secret`. We hand-roll the compact
JWS with hmac/base64 so there is no dependency on PyJWT being installed — keeping
to the "two artifacts only" rule (no extra packages).

Security: this is NOT allow_guest. A real logged-in Frappe session is required —
that session is the authorization. The minted token only ever carries the
caller's own identity (no privilege escalation), is valid ~120s, and is scoped by
`purpose:"bootstrap"` so the gateway only accepts it to start a session.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import frappe
from frappe import _

# Short lifetime: the SPA exchanges it for a gateway session JWT immediately.
_TOKEN_TTL_SECONDS = 120
_MIN_SECRET_LEN = 32


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign_hs256(payload: dict, secret: str) -> str:
    """Encode a standard compact JWS (HS256) the Go gateway (golang-jwt) parses."""
    header = {"alg": "HS256", "typ": "JWT"}
    segments = [
        _b64url(json.dumps(header, separators=(",", ":")).encode()),
        _b64url(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode("ascii")
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64url(sig))
    return ".".join(segments)


@frappe.whitelist()
def mint_bridge_token() -> dict:
    """Mint a short-lived bearer for the logged-in user to bootstrap the bridge.

    Returns {token, expires_in}. Raises if no session or the site isn't
    configured for the bridge.
    """
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Authentication required."), frappe.AuthenticationError)

    secret = frappe.conf.get("bp_bridge_bootstrap_secret")
    if not secret:
        # Same-origin / self-host-fronted deployments don't need this (the sid
        # cookie reaches the bridge directly); only Frappe Cloud does.
        frappe.throw(_("Bridge bootstrap is not configured on this site."))
    if len(secret) < _MIN_SECRET_LEN:
        frappe.throw(_("bp_bridge_bootstrap_secret must be at least 32 characters."))

    now = int(time.time())
    payload = {
        "sub": user,
        # The gateway's identity handoff (gateway_guard.apply_gateway_identity)
        # calls frappe.set_user() with this value, so it MUST be the actual
        # login identity (frappe.session.user) — NOT the User doctype's
        # separate, editable "email" profile field, which can (and, for the
        # special "Administrator" account on this bench, does) differ from
        # the login name. Using the profile field here silently asserted a
        # different, sometimes-nonexistent user on every cross-origin call.
        "email": user,
        # Single-site convention (matches the gateway's session default); multi-site
        # tenancy is a later concern.
        "tenant_id": "default",
        "purpose": "bootstrap",
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
    }
    return {"token": _sign_hs256(payload, secret), "expires_in": _TOKEN_TTL_SECONDS}
