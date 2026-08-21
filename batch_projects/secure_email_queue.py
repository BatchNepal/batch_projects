"""Frappe v15 Email Queue guard for task-backed BatchProjects mail.

Frappe's normal notification email is delayed. Checking access when the queue
row is created is insufficient because a watcher/member can lose access before
the email worker runs. v15 has no composable pre-send hook; its
``override_email_send`` hook replaces the transport entirely, so the least
invasive final-delivery boundary is a controller subclass that delegates every
non-BP-Task email unchanged and filters only pending recipients of emails whose
reference is a BP Task.
"""

from __future__ import annotations

import frappe
from frappe.email.doctype.email_queue.email_queue import EmailQueue

from batch_projects.notification_delivery import can_receive_task_delivery


class BPEmailQueue(EmailQueue):
    """EmailQueue with a last-mile BP Task authorization check."""

    def validate(self):
        # Prevent knowingly unauthorized task mail from being stored in the
        # queue in the first place. The send() check below is still mandatory:
        # authorization can change after this insert.
        if self.reference_doctype == "BP Task" and self.reference_name:
            allowed = [
                row
                for row in (self.recipients or [])
                if can_receive_task_delivery(row.recipient, self.reference_name)
            ]
            self.recipients = allowed
            if not allowed:
                frappe.throw(
                    "No email recipient currently has access to this task.",
                    frappe.PermissionError,
                    title="Task email blocked",
                )

    def send(self, *args, **kwargs):
        """Re-check every unsent recipient immediately before SMTP delivery."""
        if self.reference_doctype != "BP Task" or not self.reference_name:
            return super().send(*args, **kwargs)

        kept = []
        blocked = []
        for row in (self.recipients or []):
            # Historical recipients already marked Sent are not rewritten; the
            # security boundary can only govern delivery that has not happened.
            if row.is_mail_sent():
                kept.append(row)
                continue
            try:
                allowed = can_receive_task_delivery(row.recipient, self.reference_name)
            except Exception:
                # Permission backend failure is a denial, never an allow.
                frappe.log_error(
                    frappe.get_traceback(),
                    "bp task email authorization failed",
                )
                allowed = False
            if allowed:
                kept.append(row)
            else:
                blocked.append(row)

        if blocked:
            # Remove denied pending recipients durably so retries cannot resurrect
            # a delivery after this worker has already rejected it.
            for row in blocked:
                if row.name:
                    frappe.db.delete("Email Queue Recipient", {"name": row.name})
            self.recipients = kept
            frappe.logger("bp.notification").info(
                "task email recipients dropped after access revocation"
            )

        pending = [row for row in kept if not row.is_mail_sent()]
        if not pending:
            # There is nothing left to deliver. Mark the queue terminal so the
            # scheduler does not retry a deliberately denied recipient forever.
            self.update_status(status="Sent", commit=True)
            return None

        return super().send(*args, **kwargs)
