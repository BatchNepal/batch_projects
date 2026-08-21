"""Regression coverage for watcher subscriptions across access revocation."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import membership_invariants as inv


class TestWatcherRevocationRoutes(FrappeTestCase):
    def test_membership_api_and_child_delete_are_covered(self):
        self.assertEqual(
            hooks.override_whitelisted_methods["batch_projects.api.board.update_project_members"],
            "batch_projects.membership_invariants.update_project_members",
        )
        self.assertEqual(
            hooks.doc_events["BP Project Member"]["on_trash"],
            "batch_projects.membership_invariants.on_project_member_trash",
        )


class TestWatcherRevocation(FrappeTestCase):
    @patch.object(inv.frappe.db, "delete")
    @patch.object(inv, "_user_can_view_task", create=True)
    @patch.object(inv.frappe.db, "get_value")
    @patch.object(inv.frappe, "get_all")
    def test_revoked_user_watcher_is_deleted_when_no_access_remains(
        self, get_all, get_value, can_view, delete
    ):
        # membership_invariants imports _user_can_view_task inside the function,
        # so patch the source module instead below.
        pass

    @patch("batch_projects.task_invariants._user_can_view_task", return_value=False)
    @patch.object(inv.frappe.db, "delete")
    @patch.object(inv.frappe.db, "get_value")
    @patch.object(inv.frappe, "get_all")
    def test_live_task_stale_watcher_is_pruned(self, get_all, get_value, delete, can_view):
        get_all.return_value = [frappe._dict(name="WATCH-1", task="TASK-1", user="old@example.com")]
        get_value.return_value = frappe._dict(
            name="TASK-1", project="PROJ-1", is_deleted=0
        )

        removed = inv.prune_stale_watchers("PROJ-1", {"old@example.com"})

        self.assertEqual(removed, ["WATCH-1"])
        delete.assert_called_once_with("BP Task Watcher", {"name": "WATCH-1"})
        can_view.assert_called_once_with("PROJ-1", "TASK-1", "old@example.com")

    @patch("batch_projects.task_invariants._user_can_view_task", return_value=True)
    @patch.object(inv.frappe.db, "delete")
    @patch.object(inv.frappe.db, "get_value")
    @patch.object(inv.frappe, "get_all")
    def test_watcher_survives_when_direct_assignment_still_grants_access(
        self, get_all, get_value, delete, can_view
    ):
        get_all.return_value = [frappe._dict(name="WATCH-1", task="TASK-1", user="kept@example.com")]
        get_value.return_value = frappe._dict(
            name="TASK-1", project="PROJ-1", is_deleted=0
        )

        self.assertEqual(inv.prune_stale_watchers("PROJ-1", {"kept@example.com"}), [])
        delete.assert_not_called()

    @patch("batch_projects.task_invariants._user_can_view_task")
    @patch.object(inv.frappe.db, "delete")
    @patch.object(inv.frappe.db, "get_value")
    @patch.object(inv.frappe, "get_all")
    def test_trash_preserves_subscription_for_restore(self, get_all, get_value, delete, can_view):
        get_all.return_value = [frappe._dict(name="WATCH-1", task="TASK-1", user="user@example.com")]
        get_value.return_value = frappe._dict(
            name="TASK-1", project="PROJ-1", is_deleted=1
        )

        self.assertEqual(inv.prune_stale_watchers("PROJ-1", {"user@example.com"}), [])
        delete.assert_not_called()
        can_view.assert_not_called()

    @patch.object(inv.frappe.db, "delete")
    @patch.object(inv.frappe.db, "get_value", return_value=None)
    @patch.object(inv.frappe, "get_all")
    def test_orphan_watcher_is_removed(self, get_all, get_value, delete):
        get_all.return_value = [frappe._dict(name="WATCH-1", task="MISSING", user="user@example.com")]

        removed = inv.prune_stale_watchers("PROJ-1")

        self.assertEqual(removed, ["WATCH-1"])
        delete.assert_called_once_with("BP Task Watcher", {"name": "WATCH-1"})
