# Copyright (c) 2026, Batch Nepal and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BPAuditLog(Document):
    def before_insert(self):
        """Guarantee a durable audit-source classification.

        Existing callers may supply one of the DocType's explicit source
        values. The gateway's current audit writer predates that field, so
        classify its older payloads deterministically from the business-event
        namespace instead of persisting an empty source.
        """
        if self.source:
            return

        event = (self.event or "").strip().lower()
        if event.startswith("billing."):
            self.source = "billing"
        elif event.startswith("automation."):
            self.source = "automation"
        elif event.startswith("system."):
            self.source = "system"
        else:
            self.source = "gateway"
