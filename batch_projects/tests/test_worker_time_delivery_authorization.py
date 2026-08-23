"""Regression coverage for worker-time delivery authorization rechecks.

Recovered gaps (BatchProjects git-audit, P0 #3 and #4): recipient selection
for notifications is advisory and can go stale between when a channel is
enqueued and when a background worker actually delivers it. Desktop push's
_deliver() and BPEmailQueue.send() (secure_email_queue.py) must re-verify
access at that later point, not trust the enqueue-time decision forever.

The original correction here scheduled a separate "all"-cadence job to
recheck pending Email Queue rows. That ran independently of and in
unpredictable order relative to frappe.email.queue.flush — Frappe v15
shuffles "all" jobs and enqueues each independently — so it could not
reliably run "immediately before" delivery. Replaced with an
override_doctype_class subclass of EmailQueue itself, rechecked directly
inside send(), which is the actual delivery boundary.

Run with:
    bench run-tests --module batch_projects.tests.test_worker_time_delivery_authorization
"""

from unittest.mock import patch

import frappe
from frappe.email.doctype.email_queue.email_queue import EmailQueue as EmailQueueBase
from frappe.tests.utils import FrappeTestCase

from batch_projects import push
from batch_projects.secure_email_queue import BPEmailQueue


def _erpdesktop_agent_available():
    try:
        import erpdesktop_agent  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(
    _erpdesktop_agent_available(),
    "requires the proprietary erpdesktop_agent app; not installed in public CI",
)
class TestDesktopPushWorkerRecheck(FrappeTestCase):
    def test_delivery_skipped_when_task_access_was_revoked_since_enqueue(self):
        with (
            patch("batch_projects.notification_delivery.can_receive_task_delivery", return_value=False) as can_deliver,
            patch("erpdesktop_agent.dispatch.fanout.push_notification", create=True) as push_notification,
        ):
            push._deliver(
                recipient="outsider@example.com", ntype="Comment", actor="author@example.com",
                title="t", body="b", task="TASK-1", task_key="BP-1", project="PROJ-A", deep_link=None,
            )

        can_deliver.assert_called_once_with("outsider@example.com", "TASK-1", "PROJ-A")
        push_notification.assert_not_called()

    def test_delivery_proceeds_when_recipient_still_authorized(self):
        with (
            patch("batch_projects.notification_delivery.can_receive_task_delivery", return_value=True),
            patch("erpdesktop_agent.dispatch.fanout.push_notification", create=True) as push_notification,
        ):
            push._deliver(
                recipient="viewer@example.com", ntype="Comment", actor="author@example.com",
                title="t", body="b", task="TASK-1", task_key="BP-1", project="PROJ-A", deep_link=None,
            )

        push_notification.assert_called_once()

    def test_project_only_notification_uses_project_delivery_check(self):
        with (
            patch("batch_projects.notification_delivery.can_receive_project_delivery", return_value=False) as can_deliver,
            patch("erpdesktop_agent.dispatch.fanout.push_notification", create=True) as push_notification,
        ):
            push._deliver(
                recipient="outsider@example.com", ntype="Sprint", actor="author@example.com",
                title="t", body="b", task=None, task_key=None, project="PROJ-A", deep_link=None,
            )

        can_deliver.assert_called_once_with("outsider@example.com", "PROJ-A")
        push_notification.assert_not_called()

    def test_missing_erpdesktop_agent_is_still_a_silent_noop(self):
        """The authorization recheck must not turn a normal "agent not
        installed" no-op into an exception."""
        with patch("batch_projects.notification_delivery.can_receive_task_delivery", return_value=True):
            push._deliver(
                recipient="viewer@example.com", ntype="Comment", actor="author@example.com",
                title="t", body="b", task="TASK-1", task_key="BP-1", project="PROJ-A", deep_link=None,
            )  # must not raise even though erpdesktop_agent isn't installed here


def _bp_task_queue(recipients=()):
    """A real BPEmailQueue with real Email Queue Recipient child rows — the
    controller/send boundary itself, not a mocked stand-in. send() only ever
    runs on an already-persisted doc in production (flush() loads it via
    frappe.get_doc(..., for_update=True)), so its recipient rows always have
    a real .name — set explicitly here since a freshly-appended, never-saved
    child row's .name is None until an actual insert()."""
    doc = BPEmailQueue({"doctype": "Email Queue", "reference_doctype": "BP Task", "reference_name": "TASK-1"})
    for i, (recipient, status) in enumerate(recipients):
        row = doc.append("recipients", {"recipient": recipient, "status": status})
        row.name = f"EQR-{i}"
    return doc


def _other_queue():
    return BPEmailQueue({"doctype": "Email Queue", "reference_doctype": "Sales Order", "reference_name": "SO-1"})


class TestBPEmailQueueControllerResolution(FrappeTestCase):
    def test_email_queue_controller_is_overridden_to_bp_email_queue(self):
        overrides = frappe.get_hooks("override_doctype_class")
        self.assertIn("Email Queue", overrides)
        self.assertEqual(overrides["Email Queue"][-1], "batch_projects.secure_email_queue.BPEmailQueue")
        from frappe.model.base_document import get_controller
        self.assertIs(get_controller("Email Queue"), BPEmailQueue)


class TestBPEmailQueueSendBoundary(FrappeTestCase):
    def test_non_bp_task_mail_delegates_without_filtering(self):
        doc = _other_queue()
        with (
            patch.object(EmailQueueBase, "send", return_value="sent") as parent_send,
            patch("batch_projects.secure_email_queue.can_receive_task_delivery") as can_deliver,
        ):
            result = doc.send()
        parent_send.assert_called_once()
        can_deliver.assert_not_called()
        self.assertEqual(result, "sent")

    def test_allowed_pending_recipient_remains_and_parent_send_is_called(self):
        doc = _bp_task_queue([("stays@example.com", "")])
        with (
            patch("batch_projects.secure_email_queue.can_receive_task_delivery", return_value=True),
            patch.object(EmailQueueBase, "send", return_value="sent") as parent_send,
            patch.object(frappe.db, "delete") as delete,
        ):
            doc.send()
        parent_send.assert_called_once()
        delete.assert_not_called()
        self.assertEqual([r.recipient for r in doc.recipients], ["stays@example.com"])

    def test_denied_pending_recipient_is_deleted_before_parent_transport(self):
        doc = _bp_task_queue([("revoked@example.com", "")])
        with (
            patch("batch_projects.secure_email_queue.can_receive_task_delivery", return_value=False),
            patch.object(EmailQueueBase, "send") as parent_send,
            patch.object(doc, "update_status") as update_status,
            patch.object(frappe.db, "delete") as delete,
        ):
            doc.send()
        delete.assert_called_once()
        self.assertEqual(delete.call_args.args[0], "Email Queue Recipient")
        parent_send.assert_not_called()
        update_status.assert_called_once_with(status="Sent", commit=True)

    def test_mixed_sent_allowed_denied_rows(self):
        doc = _bp_task_queue([
            ("already-sent@example.com", "Sent"),
            ("stays@example.com", ""),
            ("revoked@example.com", ""),
        ])

        def fake_can_receive(recipient, task):
            return recipient == "stays@example.com"

        with (
            patch("batch_projects.secure_email_queue.can_receive_task_delivery", side_effect=fake_can_receive),
            patch.object(EmailQueueBase, "send", return_value="sent") as parent_send,
            patch.object(frappe.db, "delete") as delete,
        ):
            doc.send()

        parent_send.assert_called_once()
        delete.assert_called_once()
        remaining = {r.recipient for r in doc.recipients}
        self.assertEqual(remaining, {"already-sent@example.com", "stays@example.com"})

    def test_all_pending_denied_marks_sent_and_skips_transport(self):
        doc = _bp_task_queue([("revoked-1@example.com", ""), ("revoked-2@example.com", "")])
        with (
            patch("batch_projects.secure_email_queue.can_receive_task_delivery", return_value=False),
            patch.object(EmailQueueBase, "send") as parent_send,
            patch.object(doc, "update_status") as update_status,
            patch.object(frappe.db, "delete"),
        ):
            result = doc.send()
        parent_send.assert_not_called()
        update_status.assert_called_once_with(status="Sent", commit=True)
        self.assertIsNone(result)

    def test_authorization_exception_fails_closed_and_is_logged(self):
        doc = _bp_task_queue([("maybe@example.com", "")])
        with (
            patch("batch_projects.secure_email_queue.can_receive_task_delivery", side_effect=RuntimeError("boom")),
            patch.object(EmailQueueBase, "send") as parent_send,
            patch.object(doc, "update_status") as update_status,
            patch.object(frappe.db, "delete") as delete,
            patch.object(frappe, "log_error") as log_error,
        ):
            doc.send()
        delete.assert_called_once()
        parent_send.assert_not_called()
        update_status.assert_called_once_with(status="Sent", commit=True)
        log_error.assert_called_once()


class TestBPEmailQueueValidateBoundary(FrappeTestCase):
    def test_validate_drops_currently_unauthorized_pending_recipients(self):
        doc = _bp_task_queue([("stays@example.com", ""), ("never-had-access@example.com", "")])

        def fake_can_receive(recipient, task):
            return recipient == "stays@example.com"

        with patch("batch_projects.secure_email_queue.can_receive_task_delivery", side_effect=fake_can_receive):
            doc.validate()
        self.assertEqual([r.recipient for r in doc.recipients], ["stays@example.com"])

    def test_validate_throws_when_no_recipient_is_authorized(self):
        doc = _bp_task_queue([("nobody@example.com", "")])
        with (
            patch("batch_projects.secure_email_queue.can_receive_task_delivery", return_value=False),
            self.assertRaises(frappe.PermissionError),
        ):
            doc.validate()

    def test_validate_is_a_noop_for_non_bp_task_mail(self):
        doc = _other_queue()
        with patch("batch_projects.secure_email_queue.can_receive_task_delivery") as can_deliver:
            doc.validate()  # must not raise, must not touch authorization at all
        can_deliver.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
