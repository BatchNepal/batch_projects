"""Regression coverage for task collaboration authorization invariants.

These tests pin the non-obvious rule shared by mentions, watchers and
notification routing: collaboration metadata may only be delivered to a user
who can already view the task/project. A subscription or notification is never
an access grant.

Note: the doc under test must be constructed BEFORE frappe.db.get_value is
patched — Frappe's own Meta/DocType loading uses frappe.db.get_value
internally, so patching it globally before frappe.get_doc() runs corrupts the
doc's own construction, not just the validator logic being exercised.

Run with:
    bench run-tests --module batch_projects.tests.test_task_collaboration_invariants
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestTaskWatcherInvariant(FrappeTestCase):
    def test_watcher_cannot_create_task_access(self):
        watcher = frappe.get_doc({
            "doctype": "BP Task Watcher",
            "name": "NEW-WATCH",
            "task": "TASK-1",
            "project": "PROJ-A",
            "user": "test5+info@batchnepal.com",
        })

        with (
            patch("batch_projects.task_invariants._user_can_view_task", return_value=False) as can_view,
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(project="PROJ-A", is_deleted=0),
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            watcher.validate()

        can_view.assert_called_once_with("PROJ-A", "TASK-1", "test5+info@batchnepal.com")

    def test_watcher_project_is_normalized_from_task(self):
        watcher = frappe.get_doc({
            "doctype": "BP Task Watcher",
            "name": "NEW-WATCH",
            "task": "TASK-1",
            "project": None,
            "user": "test14+info@batchnepal.com",
        })

        with (
            patch("batch_projects.task_invariants._user_can_view_task", return_value=True) as can_view,
            patch.object(frappe.db, "exists", return_value=None),
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(project="PROJ-B", is_deleted=0),
            ),
        ):
            watcher.validate()

        self.assertEqual(watcher.project, "PROJ-B")
        can_view.assert_called_once_with("PROJ-B", "TASK-1", "test14+info@batchnepal.com")

    def test_trashed_task_cannot_be_watched(self):
        watcher = frappe.get_doc({
            "doctype": "BP Task Watcher",
            "name": "NEW-WATCH",
            "task": "TASK-1",
            "project": "PROJ-A",
            "user": "test14+info@batchnepal.com",
        })

        with (
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(project="PROJ-A", is_deleted=1),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            watcher.validate()


class TestNotificationRuleRecipientInvariant(FrappeTestCase):
    def test_project_rule_rejects_static_user_without_access(self):
        rule = frappe.get_doc({
            "doctype": "BP Notification Rule",
            "project": "PROJ-A",
            "recipients_json": '[{"type":"user","value":"test5+info@batchnepal.com"}]',
        })

        with (
            patch("batch_projects.access.has_at_least", return_value=False) as has_access,
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(enabled=1, user_type="System User"),
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            rule.validate()

        has_access.assert_called_once_with("PROJ-A", "Viewer", "test5+info@batchnepal.com")

    def test_global_rule_rejects_non_admin_static_user(self):
        rule = frappe.get_doc({
            "doctype": "BP Notification Rule",
            "project": None,
            "recipients_json": '[{"type":"user","value":"test48+info@batchnepal.com"}]',
        })

        with (
            patch("batch_projects.access.is_instance_admin", return_value=False),
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(enabled=1, user_type="System User"),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            rule.validate()

    def test_authorized_project_static_user_is_allowed(self):
        rule = frappe.get_doc({
            "doctype": "BP Notification Rule",
            "project": "PROJ-A",
            "recipients_json": '[{"type":"user","value":"test14+info@batchnepal.com"}]',
        })

        with (
            patch("batch_projects.access.has_at_least", return_value=True) as has_access,
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(enabled=1, user_type="System User"),
            ),
        ):
            rule.validate()

        has_access.assert_called_once_with("PROJ-A", "Viewer", "test14+info@batchnepal.com")


if __name__ == "__main__":
    import unittest
    unittest.main()
