"""Webhook routing and signing configuration owned by the Frappe data plane."""

import secrets

import frappe
from frappe.model.document import Document


class BPWebhookToken(Document):
    def before_insert(self):
        if not self.token:
            self.token = secrets.token_urlsafe(24)
        if not self.signing_secret:
            self.signing_secret = secrets.token_urlsafe(48)

    def validate(self):
        if self.scope == "project" and not self.project:
            frappe.throw("Project is required when scope is 'project'.")
        if self.scope == "workspace":
            self.project = None
