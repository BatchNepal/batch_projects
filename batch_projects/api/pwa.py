"""PWA endpoints for BatchProjects.

Serves the service worker and web app manifest with the headers browsers
require for installability:

- The service worker MUST be served with ``Service-Worker-Allowed: /`` so it
  can control ``/workspace`` even though it lives under an API path. It is
  served from the app's ``public/sw.js`` (a static, secret-free asset) with
  ``application/javascript``.
- The manifest is served as ``application/manifest+json``.

Both are ``allow_guest`` because the browser fetches them outside any
authenticated session context. Neither contains session data or secrets.
"""

import frappe
from werkzeug.wrappers import Response


def _read_public_file(name: str) -> bytes:
    path = frappe.get_app_path("batch_projects", "public", name)
    with open(path, "rb") as f:
        return f.read()


@frappe.whitelist(allow_guest=True)
def service_worker():
    """Return the service worker with a scope-wide Service-Worker-Allowed
    header so it can control /workspace (and the whole site origin)."""
    body = _read_public_file("sw.js")
    resp = Response(body, mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@frappe.whitelist(allow_guest=True)
def manifest():
    """Return the web app manifest (installability metadata)."""
    body = _read_public_file("manifest.webmanifest")
    resp = Response(body, mimetype="application/manifest+json")
    resp.headers["Cache-Control"] = "no-cache"
    return resp
