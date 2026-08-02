"""
batch_projects/api/gateway.py
──────────────────────────────
Frappe-side of the bp-gateway installer handshake. install.sh's
configure_frappe_side() POSTs here with the four values it would otherwise
print as manual `bench set-config` commands — this is what lets a
self-hosted install (and Frappe Cloud, which has no shell at all) finish
configuring itself with zero manual steps.
"""

import frappe
from frappe.installer import update_site_config


_SITE_CONFIG_KEYS = {
    "gateway_shared_secret": "bp_gateway_shared_secret",
    "bridge_bootstrap_secret": "bp_bridge_bootstrap_secret",
    "scheduler_ingest_token": "bp_scheduler_ingest_token",
    "bridge_url": "bp_bridge_url",
}


@frappe.whitelist()
def configure(gateway_shared_secret=None, bridge_bootstrap_secret=None,
              scheduler_ingest_token=None, bridge_url=None, gateway_domain=None):
    """Write the gateway trust secrets + bridge URL into site_config.

    Same auth bar as credentials.get_credential_secret: System Manager or
    Administrator only. install.sh authenticates with the admin API
    key/secret it already validated in preflight, which Frappe's own token
    auth resolves to a real frappe.session.user before this ever runs.

    The three trust secrets are write-once: a second caller swapping a live
    secret out from under a running gateway must never happen through an
    API a browser session (even an admin one) can reach. Reconfiguring
    those on an already-set-up site is a deliberate `bench set-config`, not
    an installer re-run.

    bridge_url is the one exception — it's not a secret at all (it's
    already sitting in every page's own HTML source as
    window.__BP_BRIDGE_URL__), and it's exactly the kind of thing that
    legitimately changes: the gateway's local port drifting on a re-run
    that found its own prior container "in use" (confirmed live —
    install.sh now avoids that specific case, but a domain change or a
    redeploy to a new server are still real reasons this value moves), a
    --update --domain switching to a permanent domain, etc. Left stale,
    every /v1/* call the SPA makes from a different origin than the
    gateway's (batch_projects/frontend's realtime.js, api.js's
    bridgeCall()) points at a dead address and silently hangs — confirmed
    live as a workspace page stuck forever at "Initializing realtime
    connection...". So this field alone self-heals on every install.sh
    run instead of requiring someone to notice and fix it by hand.

    gateway_domain is accepted (install.sh always sends it) but unused —
    the manual bench-set-config fallback doesn't set it either, and nothing
    in this app reads a bp_gateway_domain config key.
    """
    user = frappe.session.user
    if user != "Administrator" and "System Manager" not in frappe.get_roles(user):
        frappe.throw("Not permitted", frappe.PermissionError)

    values = {
        "gateway_shared_secret": gateway_shared_secret,
        "bridge_bootstrap_secret": bridge_bootstrap_secret,
        "scheduler_ingest_token": scheduler_ingest_token,
        "bridge_url": bridge_url,
    }
    missing = [k for k, v in values.items() if not v]
    if missing:
        frappe.throw(f"Missing required value(s): {', '.join(missing)}")
    if not (bridge_url.startswith("http://") or bridge_url.startswith("https://")):
        frappe.throw("bridge_url must be a full http(s) URL.")

    if frappe.conf.get("bp_gateway_shared_secret"):
        # Already configured: only bridge_url is allowed to move. The
        # three real secrets stay exactly as they are, no matter what was
        # submitted alongside it.
        if frappe.conf.get("bp_bridge_url") != bridge_url:
            update_site_config("bp_bridge_url", bridge_url)
            return {"ok": True, "updated": ["bridge_url"]}
        return {"ok": True, "updated": []}

    for payload_key, config_key in _SITE_CONFIG_KEYS.items():
        update_site_config(config_key, values[payload_key])

    return {"ok": True, "updated": list(_SITE_CONFIG_KEYS.values())}
