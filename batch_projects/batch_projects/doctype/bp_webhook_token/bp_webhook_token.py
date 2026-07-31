"""
BP Webhook Token
────────────────
Registry mapping an opaque, unguessable token to a scope (one project, or the
whole workspace) so bp-gateway's `POST /v1/hooks/<token>` ingress
(internal/premium/premium.go — HMAC-verified, replay-guarded, license-gated
before it ever reaches here) knows which BP Automation Rules an incoming
external event is even allowed to reach.

This doctype holds no secrets bp-gateway needs — the HMAC signing secret and
license check happen entirely on the gateway side. `token` here is just an
unguessable routing key, equivalent in spirit to a webhook path segment.
"""

import secrets

import frappe
from frappe.model.document import Document


class BPWebhookToken(Document):
    def before_insert(self):
        if not self.token:
            self.token = secrets.token_urlsafe(24)

    def validate(self):
        if self.scope == "project" and not self.project:
            frappe.throw("Project is required when scope is 'project'.")
        if self.scope == "workspace":
            self.project = None
