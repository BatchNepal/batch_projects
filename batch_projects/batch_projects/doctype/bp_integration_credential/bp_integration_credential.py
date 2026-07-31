"""BP Integration Credential — see bp_workflow.py module docstring for context.
No custom logic needed: Frappe's Password fieldtype already encrypts at rest
and redacts on read for any caller without System Manager (this doctype's
own read permission, so that's the only class of caller anyway)."""

from frappe.model.document import Document


class BPIntegrationCredential(Document):
    pass
