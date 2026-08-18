import frappe
from frappe.model.document import Document

from batch_projects.milestone_billing import (
    ACTIVE_STATUSES,
    invoice_state,
)


class BPMilestone(Document):
    def on_trash(self):
        # Derive from ERPNext rather than trusting the possibly-stale persisted
        # status. A live Draft/Submitted invoice must never be orphaned by
        # deleting its BP Milestone.
        status, invoice = invoice_state(
            self.sales_invoice
        )

        if status in ACTIVE_STATUSES:
            frappe.throw(
                f"Milestone '{self.title}' cannot be deleted while "
                f"Sales Invoice {invoice} is {status}. "
                "Delete the draft or cancel the submitted invoice first."
            )
