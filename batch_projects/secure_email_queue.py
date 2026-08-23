"""Last-mile authorization for BP Task email.

frappe.email.queue.flush() (Frappe core) is the actual SMTP delivery
boundary — it runs independently of and in unpredictable order relative to
any BatchProjects scheduled job (Frappe v15 shuffles "all"-cadence jobs and
enqueues each independently), so a separate recheck job can never reliably
run "immediately before" delivery. The only point that IS immediately before
delivery is EmailQueue.send() itself.

Scoped via hooks.py's override_doctype_class to Email Queue only — every
other email on the site (ERPNext, HR, core Frappe) goes through this same
subclass but is a plain no-op passthrough for anything not referencing a
BP Task, so its behavior is unchanged.
"""

from __future__ import annotations

import frappe
from frappe.email.doctype.email_queue.email_queue import EmailQueue

from batch_projects.notification_delivery import can_receive_task_delivery


class BPEmailQueue(EmailQueue):
    def _is_bp_task_mail(self) -> bool:
        return self.reference_doctype == "BP Task" and bool(self.reference_name)

    def validate(self):
        parent_validate = getattr(super(), "validate", None)
        if callable(parent_validate):
            parent_validate()

        if not self._is_bp_task_mail():
            return

        # Enqueue-time gate: a recipient with zero access to the task right
        # now would just be denied again at send() — dropping them here
        # keeps a doomed row from ever reaching the queue. This does NOT
        # replace the send()-time recheck below: access can still change
        # between now and actual delivery, which is exactly the race this
        # module exists to close.
        kept = []
        for row in self.recipients or []:
            if row.is_mail_sent() or can_receive_task_delivery(row.recipient, self.reference_name):
                kept.append(row)
        self.recipients = kept
        if not kept:
            frappe.throw(
                "No email recipient currently has access to this task.",
                frappe.PermissionError,
                title="Task email blocked",
            )

    def send(self, *args, **kwargs):
        if not self._is_bp_task_mail():
            return super().send(*args, **kwargs)

        kept = []
        blocked = []
        for row in self.recipients or []:
            if row.is_mail_sent():
                kept.append(row)
                continue
            try:
                allowed = can_receive_task_delivery(row.recipient, self.reference_name)
            except Exception:
                # Authorization/backend failure must never become an allow.
                frappe.log_error(frappe.get_traceback(), "bp task email authorization failed")
                allowed = False
            (kept if allowed else blocked).append(row)

        for row in blocked:
            # Email Queue Recipient.status only has "" / "Not Sent" / "Sent"
            # (see its doctype JSON) — there is no truthful "blocked" value,
            # so a denied recipient is removed from the row set rather than
            # marked Sent (would corrupt delivery history) or left Not Sent
            # (would just be retried forever by Frappe's own
            # retry_sending_emails).
            if row.name:
                frappe.db.delete("Email Queue Recipient", {"name": row.name})
        self.recipients = kept

        if not any(not row.is_mail_sent() for row in kept):
            # Every still-pending recipient was denied (or there were none
            # to begin with) — a deliberately denied queue must not retry
            # forever, but it must also never claim a send that never
            # happened for a purely empty queue's own sake; "Sent" here
            # reflects that every recipient this queue could still act on
            # has been resolved (already-sent history preserved, denied
            # rows durably removed above), not that new mail went out.
            self.update_status(status="Sent", commit=True)
            return None

        return super().send(*args, **kwargs)
