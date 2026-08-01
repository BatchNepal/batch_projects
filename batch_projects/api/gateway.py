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
    """Write the gateway trust secrets + bridge URL into site_config, once.

    Same auth bar as credentials.get_credential_secret: System Manager or
    Administrator only. install.sh authenticates with the admin API
    key/secret it already validated in preflight, which Frappe's own token
    auth resolves to a real frappe.session.user before this ever runs.

    Write-once by design. Three of these four values are shared secrets the
    gateway and Frappe use to authenticate requests to each other; a second
    caller silently re-pointing bp_bridge_url or swapping a live secret out
    from under a running gateway must never happen through an API a browser
    session (even an admin one) can reach. Reconfiguring an already-set-up
    site is a deliberate `bench set-config`, not an installer re-run.

    gateway_domain is accepted (install.sh always sends it) but unused —
    the manual bench-set-config fallback doesn't set it either, and nothing
    in this app reads a bp_gateway_domain config key.
    """
    user = frappe.session.user
    if user != "Administrator" and "System Manager" not in frappe.get_roles(user):
        frappe.throw("Not permitted", frappe.PermissionError)

    if frappe.conf.get("bp_gateway_shared_secret"):
        frappe.throw("This site already has a gateway configured. Use `bench set-config` to change it.")

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

    for payload_key, config_key in _SITE_CONFIG_KEYS.items():
        update_site_config(config_key, values[payload_key])

    return {"ok": True}
