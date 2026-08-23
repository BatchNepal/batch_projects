"""Regression coverage for worker-time delivery authorization rechecks.

Recovered gaps (BatchProjects git-audit, P0 #3 and #4): recipient selection
for notifications is advisory and can go stale between when a channel is
enqueued and when a background worker actually delivers it. Desktop push's
_deliver() and the Email Queue recheck job must re-verify access at that
later point, not trust the enqueue-time decision forever.

Run with:
    bench run-tests --module batch_projects.tests.test_worker_time_delivery_authorization
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import push
from batch_projects import notification_delivery as nd


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


class TestEmailQueueDeliveryRecheck(FrappeTestCase):
    def test_removes_only_pending_recipients_who_lost_access(self):
        pending_rows = [
            frappe._dict(recipient_row="ROW-1", email="stays@example.com", task="TASK-1"),
            frappe._dict(recipient_row="ROW-2", email="revoked@example.com", task="TASK-1"),
        ]

        def fake_can_receive(email, task):
            return email == "stays@example.com"

        with (
            patch.object(frappe.db, "sql", return_value=pending_rows),
            patch("batch_projects.notification_delivery.can_receive_task_delivery", side_effect=fake_can_receive),
            patch.object(frappe.db, "delete") as delete,
        ):
            nd.revalidate_pending_task_email_recipients()

        delete.assert_called_once_with("Email Queue Recipient", {"name": "ROW-2"})

    def test_query_only_targets_not_yet_sent_task_referenced_rows(self):
        with (
            patch.object(frappe.db, "sql", return_value=[]) as sql,
            patch.object(frappe.db, "delete") as delete,
        ):
            nd.revalidate_pending_task_email_recipients()

        query = sql.call_args.args[0]
        self.assertIn("reference_doctype = 'BP Task'", query)
        self.assertIn("Not Sent", query)
        self.assertIn("Partially Sent", query)
        delete.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
