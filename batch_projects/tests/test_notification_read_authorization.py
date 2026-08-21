"""Regression tests for retroactive in-app notification authorization."""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import notification_permissions as perms
from batch_projects import notification_reads as reads


class TestNotificationReadRoutes(FrappeTestCase):
    def test_every_notification_center_read_route_is_overridden(self):
        expected = {
            "batch_projects.api.board.get_notifications":
                "batch_projects.notification_reads.get_notifications",
            "batch_projects.api.board.get_notification_count":
                "batch_projects.notification_reads.get_notification_count",
            "batch_projects.api.board.mark_notification_read":
                "batch_projects.notification_reads.mark_notification_read",
            "batch_projects.api.board.mark_notification_unread":
                "batch_projects.notification_reads.mark_notification_unread",
            "batch_projects.api.board.mark_all_notifications_read":
                "batch_projects.notification_reads.mark_all_notifications_read",
        }
        for source, target in expected.items():
            self.assertEqual(hooks.override_whitelisted_methods[source], target)

    def test_generic_rest_hooks_use_live_notification_permissions(self):
        self.assertEqual(
            hooks.permission_query_conditions["BP Notification"],
            "batch_projects.notification_permissions.query_conditions",
        )
        self.assertEqual(
            hooks.has_permission["BP Notification"],
            "batch_projects.notification_permissions.has_permission",
        )


class TestNotificationVisibility(FrappeTestCase):
    @patch.object(reads, "can_receive_task_delivery")
    def test_revoked_task_notification_is_removed_retroactively(self, can_receive):
        can_receive.return_value = False
        row = frappe._dict(
            name="N-1", notification_type="Comment", task="TASK-1",
            project="PROJ-1", is_read=0,
        )
        self.assertFalse(reads._is_visible(row, "old@example.com"))
        can_receive.assert_called_once_with(
            "old@example.com", "TASK-1", "PROJ-1"
        )

    @patch.object(reads, "can_receive_project_delivery", return_value=False)
    def test_deleted_tombstone_is_hidden_after_project_revocation(self, can_receive):
        row = frappe._dict(
            name="N-1", notification_type="Task Deleted", task=None,
            project="PROJ-1", is_read=0,
        )
        self.assertFalse(reads._is_visible(row, "old@example.com"))
        can_receive.assert_called_once_with(
            "old@example.com", "PROJ-1", "Viewer"
        )

    @patch.object(reads, "can_receive_task_delivery")
    def test_taskless_non_task_notification_keeps_its_own_contract(self, can_receive):
        row = frappe._dict(
            name="N-1", notification_type="Role Changed", task=None,
            project="PROJ-1", is_read=0,
        )
        self.assertTrue(reads._is_visible(row, "user@example.com"))
        can_receive.assert_not_called()

    @patch.object(reads, "_candidate_rows")
    @patch.object(reads, "_is_visible")
    def test_visibility_decision_is_cached_per_task(self, is_visible, candidates):
        candidates.return_value = [
            frappe._dict(name="N-2", notification_type="Comment", task="TASK-1", project="P", is_read=0),
            frappe._dict(name="N-1", notification_type="Update", task="TASK-1", project="P", is_read=1),
        ]
        is_visible.return_value = True

        rows = reads._visible_rows("user@example.com")

        self.assertEqual([r.name for r in rows], ["N-2", "N-1"])
        is_visible.assert_called_once()


class TestNotificationPagination(FrappeTestCase):
    @patch.object(reads, "_require_system_user")
    @patch.object(reads, "_visible_unread_count", return_value=1)
    @patch.object(reads, "_visible_rows")
    @patch.object(reads.frappe.db, "table_exists", return_value=True)
    @patch.object(reads.frappe, "get_all")
    def test_pagination_happens_after_authorization(
        self, get_all, table_exists, visible_rows, unread_count, require_user
    ):
        visible_rows.return_value = [
            frappe._dict(name="N-5"),
            frappe._dict(name="N-3"),
            frappe._dict(name="N-1"),
        ]
        get_all.return_value = [
            frappe._dict(name="N-3", message="second"),
            frappe._dict(name="N-1", message="third"),
        ]

        with patch.object(reads.frappe.session, "user", "user@example.com"):
            result = reads.get_notifications(limit=2, offset=1)

        self.assertEqual(result["total"], 3)
        self.assertEqual(result["unread_count"], 1)
        self.assertEqual([r.name for r in result["notifications"]], ["N-3", "N-1"])
        filters = get_all.call_args.kwargs["filters"]
        self.assertEqual(filters["name"], ["in", ["N-3", "N-1"]])

    @patch.object(reads, "_require_system_user")
    @patch.object(reads, "_visible_unread_count", return_value=4)
    @patch.object(reads.frappe.db, "table_exists", return_value=True)
    def test_badge_uses_only_currently_visible_unread(self, table_exists, count, require_user):
        with patch.object(reads.frappe.session, "user", "user@example.com"):
            self.assertEqual(reads.get_notification_count(), {"unread_count": 4})


class TestNotificationMutationBoundary(FrappeTestCase):
    @patch.object(reads, "_require_system_user")
    @patch.object(reads, "_is_visible", return_value=False)
    @patch.object(reads.frappe.db, "get_value")
    def test_revoked_notification_id_is_not_an_existence_oracle(
        self, get_value, is_visible, require_user
    ):
        get_value.return_value = frappe._dict(
            name="N-SECRET", notification_type="Comment", task="TASK-1",
            project="PRIVATE", is_read=0,
        )
        with self.assertRaises(frappe.DoesNotExistError):
            reads._visible_notification("N-SECRET", "old@example.com")


class TestGenericNotificationPermissions(FrappeTestCase):
    @patch.object(perms, "_is_admin", return_value=False)
    @patch.object(perms, "_scope", return_value=({"VISIBLE"}, {"TASK-DIRECT"}))
    def test_list_query_requires_recipient_and_live_authority(self, scope, is_admin):
        sql = perms.query_conditions("user@example.com")
        self.assertIn("`tabBP Notification`.`recipient`", sql)
        self.assertIn("t.is_deleted = 0", sql)
        self.assertIn("TASK-DIRECT", sql)
        self.assertIn("pm.role in ('Manager', 'Admin')", sql)
        self.assertIn("Task Deleted", sql)

    @patch.object(perms, "_is_admin", return_value=False)
    @patch(
        "batch_projects.notification_delivery.can_receive_task_delivery",
        return_value=False,
    )
    def test_single_doc_permission_is_revoked_with_task_access(self, can_receive, is_admin):
        doc = frappe._dict(
            recipient="user@example.com", task="TASK-1", project="P",
            notification_type="Comment",
        )
        self.assertFalse(
            perms.has_permission(doc, user="user@example.com", permission_type="read")
        )
        can_receive.assert_called_once_with("user@example.com", "TASK-1", "P")
