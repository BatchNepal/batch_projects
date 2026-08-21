"""Regression coverage for notification_delivery.py's task-visibility policy.

Split out of a larger source file that also covered push.py and
secure_email_queue.py — those belong to the separate "delivery authorization"
PR, not this one.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import notification_delivery as delivery


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


if __name__ == "__main__":
    import unittest
    unittest.main()
