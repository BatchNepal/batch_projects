"""Regression coverage for final task-notification authorization boundaries."""

from unittest.mock import MagicMock, patch

import frappe
from frappe.email.doctype.email_queue.email_queue import EmailQueue
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import notification_delivery as delivery
from batch_projects import push
from batch_projects.secure_email_queue import BPEmailQueue


class _Recipient:
    def __init__(self, recipient, name="EMAIL-RECIPIENT-1", sent=False):
        self.recipient = recipient
        self.name = name
        self._sent = sent

    def is_mail_sent(self):
        return self._sent


class TestNotificationDeliveryPolicy(FrappeTestCase):
    @patch.object(delivery, "resolve_system_user", return_value="user@example.com")
    @patch.object(delivery.frappe.db, "get_value")
    @patch("batch_projects.task_invariants._user_can_view_task", return_value=True)
    @patch("batch_projects.access.is_instance_admin", return_value=False)
    def test_live_task_uses_current_task_visibility(
        self, is_admin, can_view, get_value, resolve_user
    ):
        get_value.return_value = frappe._dict(
            name="TASK-1", project="PROJ-1", is_deleted=0
        )

        self.assertTrue(
            delivery.can_receive_task_delivery(
                "user@example.com", "TASK-1", "PROJ-1"
            )
        )
        can_view.assert_called_once_with("PROJ-1", "TASK-1", "user@example.com")

    @patch.object(delivery, "resolve_system_user", return_value="user@example.com")
    @patch.object(delivery.frappe.db, "get_value")
    @patch("batch_projects.task_invariants._user_can_view_task")
    def test_stale_project_envelope_fails_closed(self, can_view, get_value, resolve_user):
        get_value.return_value = frappe._dict(
            name="TASK-1", project="PROJ-NEW", is_deleted=0
        )

        self.assertFalse(
            delivery.can_receive_task_delivery(
                "user@example.com", "TASK-1", "PROJ-OLD"
            )
        )
        can_view.assert_not_called()

    @patch.object(delivery, "resolve_system_user", return_value="manager@example.com")
    @patch.object(delivery.frappe.db, "get_value")
    @patch("batch_projects.access.has_at_least", return_value=True)
    @patch("batch_projects.access.is_instance_admin", return_value=False)
    def test_trashed_task_requires_manager_visibility(
        self, is_admin, has_at_least, get_value, resolve_user
    ):
        get_value.return_value = frappe._dict(
            name="TASK-1", project="PROJ-1", is_deleted=1
        )

        self.assertTrue(
            delivery.can_receive_task_delivery(
                "manager@example.com", "TASK-1", "PROJ-1"
            )
        )
        has_at_least.assert_called_once_with(
            "PROJ-1", "Manager", "manager@example.com"
        )

    @patch.object(delivery, "resolve_system_user", return_value="member@example.com")
    @patch.object(delivery.frappe.db, "get_value")
    @patch("batch_projects.access.has_at_least", return_value=False)
    @patch("batch_projects.access.is_instance_admin", return_value=False)
    def test_trashed_task_is_not_delivered_to_member_or_watcher(
        self, is_admin, has_at_least, get_value, resolve_user
    ):
        get_value.return_value = frappe._dict(
            name="TASK-1", project="PROJ-1", is_deleted=1
        )

        self.assertFalse(
            delivery.can_receive_task_delivery(
                "member@example.com", "TASK-1", "PROJ-1"
            )
        )


class TestDesktopDeliveryBoundary(FrappeTestCase):
    @patch(
        "batch_projects.notification_delivery.can_receive_task_delivery",
        return_value=False,
    )
    @patch.object(push.frappe, "log_error")
    def test_desktop_worker_drops_revoked_recipient(self, log_error, can_receive):
        logger = MagicMock()
        with patch.object(push.frappe, "logger", return_value=logger):
            push._deliver(
                recipient="old@example.com",
                ntype="Comment",
                actor="actor@example.com",
                title="Private task",
                body="secret",
                task="TASK-1",
                task_key="PRJ-1",
                project="PROJ-1",
                deep_link="/workspace/PRJ/board?task=PRJ-1",
            )

        can_receive.assert_called_once_with(
            "old@example.com", "TASK-1", "PROJ-1"
        )
        logger.info.assert_called_once()
        log_error.assert_not_called()


class TestEmailDeliveryBoundary(FrappeTestCase):
    def test_v15_email_queue_override_is_registered(self):
        self.assertEqual(
            hooks.override_doctype_class["Email Queue"],
            "batch_projects.secure_email_queue.BPEmailQueue",
        )
        self.assertTrue(issubclass(BPEmailQueue, EmailQueue))

    @patch("batch_projects.secure_email_queue.can_receive_task_delivery", return_value=True)
    @patch.object(EmailQueue, "send", return_value="delegated")
    def test_authorized_task_email_delegates_to_frappe(self, base_send, can_receive):
        doc = BPEmailQueue({
            "doctype": "Email Queue",
            "reference_doctype": "BP Task",
            "reference_name": "TASK-1",
        })
        doc.recipients = [_Recipient("user@example.com")]

        self.assertEqual(doc.send(), "delegated")
        can_receive.assert_called_once_with("user@example.com", "TASK-1")
        base_send.assert_called_once()

    @patch("batch_projects.secure_email_queue.can_receive_task_delivery", return_value=False)
    @patch.object(EmailQueue, "send")
    @patch.object(frappe.db, "delete")
    def test_revoked_recipient_is_removed_before_smtp(self, db_delete, base_send, can_receive):
        doc = BPEmailQueue({
            "doctype": "Email Queue",
            "reference_doctype": "BP Task",
            "reference_name": "TASK-1",
        })
        doc.recipients = [_Recipient("old@example.com", name="REC-1")]
        doc.update_status = MagicMock()

        with patch.object(frappe, "logger", return_value=MagicMock()):
            self.assertIsNone(doc.send())

        can_receive.assert_called_once_with("old@example.com", "TASK-1")
        db_delete.assert_called_once_with(
            "Email Queue Recipient", {"name": "REC-1"}
        )
        base_send.assert_not_called()
        doc.update_status.assert_called_once_with(status="Sent", commit=True)

    @patch("batch_projects.secure_email_queue.can_receive_task_delivery", return_value=True)
    @patch.object(EmailQueue, "send", return_value="normal")
    def test_non_task_email_is_completely_untouched(self, base_send, can_receive):
        doc = BPEmailQueue({
            "doctype": "Email Queue",
            "reference_doctype": "Sales Invoice",
            "reference_name": "SINV-1",
        })
        doc.recipients = [_Recipient("customer@example.com")]

        self.assertEqual(doc.send(), "normal")
        can_receive.assert_not_called()
        base_send.assert_called_once()
