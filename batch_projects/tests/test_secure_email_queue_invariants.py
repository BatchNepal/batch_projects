"""Focused regression coverage for the Frappe v15 Email Queue override."""

from unittest.mock import MagicMock, patch

import frappe
from frappe.email.doctype.email_queue.email_queue import EmailQueue
from frappe.tests.utils import FrappeTestCase

from batch_projects.secure_email_queue import BPEmailQueue


class _Recipient:
    def __init__(self, recipient, name, sent=False):
        self.recipient = recipient
        self.name = name
        self._sent = sent

    def is_mail_sent(self):
        return self._sent


class TestSecureEmailQueue(FrappeTestCase):
    @patch("batch_projects.secure_email_queue.can_receive_task_delivery", return_value=False)
    def test_validate_preserves_already_sent_history(self, can_receive):
        sent = _Recipient("former@example.com", "R-SENT", sent=True)
        pending = _Recipient("revoked@example.com", "R-PENDING", sent=False)
        doc = BPEmailQueue({
            "doctype": "Email Queue",
            "reference_doctype": "BP Task",
            "reference_name": "TASK-1",
        })
        doc.recipients = [sent, pending]

        doc.validate()

        self.assertEqual(doc.recipients, [sent])
        can_receive.assert_called_once_with("revoked@example.com", "TASK-1")

    @patch("batch_projects.secure_email_queue.can_receive_task_delivery")
    def test_validate_does_not_touch_non_task_email(self, can_receive):
        recipient = _Recipient("customer@example.com", "R-1")
        doc = BPEmailQueue({
            "doctype": "Email Queue",
            "reference_doctype": "Sales Invoice",
            "reference_name": "SINV-1",
        })
        doc.recipients = [recipient]

        doc.validate()

        self.assertEqual(doc.recipients, [recipient])
        can_receive.assert_not_called()

    @patch("batch_projects.secure_email_queue.can_receive_task_delivery", return_value=False)
    @patch.object(frappe.db, "delete")
    @patch.object(EmailQueue, "send")
    def test_send_drops_only_pending_revoked_recipient(self, base_send, db_delete, can_receive):
        sent = _Recipient("former@example.com", "R-SENT", sent=True)
        blocked = _Recipient("revoked@example.com", "R-BLOCKED", sent=False)
        doc = BPEmailQueue({
            "doctype": "Email Queue",
            "reference_doctype": "BP Task",
            "reference_name": "TASK-1",
        })
        doc.recipients = [sent, blocked]
        doc.update_status = MagicMock()

        with patch.object(frappe, "logger", return_value=MagicMock()):
            result = doc.send()

        self.assertIsNone(result)
        self.assertEqual(doc.recipients, [sent])
        db_delete.assert_called_once_with(
            "Email Queue Recipient", {"name": "R-BLOCKED"}
        )
        base_send.assert_not_called()
        doc.update_status.assert_called_once_with(status="Sent", commit=True)
