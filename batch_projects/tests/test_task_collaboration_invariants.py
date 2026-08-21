"""Regression coverage for task collaboration authorization invariants.

These tests pin the non-obvious rule shared by mentions, watchers and
notification routing: collaboration metadata may only be delivered to a user
who can already view the task/project. A subscription or notification is never
an access grant.

Run with:
    bench run-tests --module batch_projects.tests.test_task_collaboration_invariants
"""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.batch_projects.doctype.bp_task_watcher.bp_task_watcher import (
    BPTaskWatcher,
)
from batch_projects.batch_projects.doctype.bp_notification_rule.bp_notification_rule import (
    BPNotificationRule,
)


class TestTaskWatcherInvariant(FrappeTestCase):
    @patch("batch_projects.task_invariants._user_can_view_task", return_value=False)
    @patch.object(frappe.db, "get_value")
    def test_watcher_cannot_create_task_access(self, get_value, can_view):
        get_value.return_value = frappe._dict(project="PROJ-A", is_deleted=0)
        watcher = BPTaskWatcher({
            "doctype": "BP Task Watcher",
            "name": "NEW-WATCH",
            "task": "TASK-1",
            "project": "PROJ-A",
            "user": "outsider@example.com",
        })

        with self.assertRaises(frappe.PermissionError):
            watcher.validate()

        can_view.assert_called_once_with("PROJ-A", "TASK-1", "outsider@example.com")

    @patch("batch_projects.task_invariants._user_can_view_task", return_value=True)
    @patch.object(frappe.db, "exists", return_value=None)
    @patch.object(frappe.db, "get_value")
    def test_watcher_project_is_normalized_from_task(self, get_value, exists, can_view):
        get_value.return_value = frappe._dict(project="PROJ-B", is_deleted=0)
        watcher = BPTaskWatcher({
            "doctype": "BP Task Watcher",
            "name": "NEW-WATCH",
            "task": "TASK-1",
            "project": None,
            "user": "viewer@example.com",
        })

        watcher.validate()

        self.assertEqual(watcher.project, "PROJ-B")
        can_view.assert_called_once_with("PROJ-B", "TASK-1", "viewer@example.com")

    @patch.object(frappe.db, "get_value")
    def test_trashed_task_cannot_be_watched(self, get_value):
        get_value.return_value = frappe._dict(project="PROJ-A", is_deleted=1)
        watcher = BPTaskWatcher({
            "doctype": "BP Task Watcher",
            "name": "NEW-WATCH",
            "task": "TASK-1",
            "project": "PROJ-A",
            "user": "viewer@example.com",
        })

        with self.assertRaises(frappe.ValidationError):
            watcher.validate()


class TestNotificationRuleRecipientInvariant(FrappeTestCase):
    @patch("batch_projects.access.has_at_least", return_value=False)
    @patch.object(frappe.db, "get_value")
    def test_project_rule_rejects_static_user_without_access(self, get_value, has_access):
        get_value.return_value = frappe._dict(enabled=1, user_type="System User")
        rule = BPNotificationRule({
            "doctype": "BP Notification Rule",
            "project": "PROJ-A",
            "recipients_json": '[{"type":"user","value":"outsider@example.com"}]',
        })

        with self.assertRaises(frappe.PermissionError):
            rule.validate()

        has_access.assert_called_once_with("PROJ-A", "Viewer", "outsider@example.com")

    @patch("batch_projects.access.is_instance_admin", return_value=False)
    @patch.object(frappe.db, "get_value")
    def test_global_rule_rejects_non_admin_static_user(self, get_value, is_admin):
        get_value.return_value = frappe._dict(enabled=1, user_type="System User")
        rule = BPNotificationRule({
            "doctype": "BP Notification Rule",
            "project": None,
            "recipients_json": '[{"type":"user","value":"person@example.com"}]',
        })

        with self.assertRaises(frappe.ValidationError):
            rule.validate()

    @patch("batch_projects.access.has_at_least", return_value=True)
    @patch.object(frappe.db, "get_value")
    def test_authorized_project_static_user_is_allowed(self, get_value, has_access):
        get_value.return_value = frappe._dict(enabled=1, user_type="System User")
        rule = BPNotificationRule({
            "doctype": "BP Notification Rule",
            "project": "PROJ-A",
            "recipients_json": '[{"type":"user","value":"viewer@example.com"}]',
        })

        rule.validate()

        has_access.assert_called_once_with("PROJ-A", "Viewer", "viewer@example.com")


if __name__ == "__main__":
    import unittest
    unittest.main()
