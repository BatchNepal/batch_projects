# Copyright (c) 2026, BatchNepal and contributors
# Regression coverage for membership_invariants.py — watcher-subscription
# cleanup when a user's project membership is revoked (create/role-escalation
# authority lives in bp_project.py's _validate_members_mutation_authority
# instead; this module owns the delete-side cleanup only).
# Run: bench --site <site> run-tests --app batch_projects

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks, membership_invariants
from batch_projects.api.board import create_project

TEST_KEY = "TMBRSH"


def _ensure_user(email):
    """Throwaway System User fixture for Link-field validity only — never a
    real signup, never a real email (send_welcome_email=0, plus-addressed
    testN+info@batchnepal.com addresses are used — SES bounce protection).
    IANA-reserved, matches this test suite's existing convention)."""
    if frappe.db.exists("User", email):
        return email
    frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": email.split("@")[0],
        "user_type": "System User",
        "enabled": 1,
        "send_welcome_email": 0,
    }).insert(ignore_permissions=True)
    return email


def _delete_project(key):
    name = frappe.db.get_value("BP Project", {"key": key})
    if not name:
        return
    for task in frappe.get_all("BP Task", filters={"project": name}, pluck="name"):
        frappe.delete_doc("BP Task", task, ignore_permissions=True, force=True)
    for watcher in frappe.get_all("BP Task Watcher", filters={"project": name}, pluck="name"):
        frappe.delete_doc("BP Task Watcher", watcher, ignore_permissions=True, force=True)
    frappe.delete_doc("BP Project", name, ignore_permissions=True, force=True)
    frappe.db.commit()


class TestHooksWiring(FrappeTestCase):
    def test_update_project_members_override_registered(self):
        self.assertEqual(
            hooks.override_whitelisted_methods["batch_projects.api.board.update_project_members"],
            "batch_projects.membership_invariants.update_project_members",
        )

    def test_after_delete_hook_registered(self):
        self.assertEqual(
            hooks.doc_events["BP Project Member"]["after_delete"],
            "batch_projects.membership_invariants.after_project_member_delete",
        )


class TestUserCanViewTask(FrappeTestCase):
    def test_instance_admin_always_sees_task(self):
        self.assertTrue(
            membership_invariants._user_can_view_task("P", "T", "Administrator")
        )

    def test_disabled_user_never_sees_task(self):
        with patch.object(
            membership_invariants, "_user_row",
            return_value=frappe._dict(enabled=0, user_type="System User"),
        ):
            self.assertFalse(
                membership_invariants._user_can_view_task("P", "T", "test64+info@batchnepal.com")
            )

    def test_project_viewer_role_grants_visibility(self):
        with (
            patch.object(
                membership_invariants, "_user_row",
                return_value=frappe._dict(enabled=1, user_type="System User"),
            ),
            patch("batch_projects.access.is_instance_admin", return_value=False),
            patch("batch_projects.access.has_at_least", return_value=True),
        ):
            self.assertTrue(
                membership_invariants._user_can_view_task("P", "T", "test64+info@batchnepal.com")
            )

    def test_plain_assignee_without_project_role_still_sees_task(self):
        with (
            patch.object(
                membership_invariants, "_user_row",
                return_value=frappe._dict(enabled=1, user_type="System User"),
            ),
            patch("batch_projects.access.is_instance_admin", return_value=False),
            patch("batch_projects.access.has_at_least", return_value=False),
            patch("batch_projects.access.is_task_assignee", return_value=True),
        ):
            self.assertTrue(
                membership_invariants._user_can_view_task("P", "T", "test64+info@batchnepal.com")
            )

    def test_no_role_no_assignment_denies_visibility(self):
        with (
            patch.object(
                membership_invariants, "_user_row",
                return_value=frappe._dict(enabled=1, user_type="System User"),
            ),
            patch("batch_projects.access.is_instance_admin", return_value=False),
            patch("batch_projects.access.has_at_least", return_value=False),
            patch("batch_projects.access.is_task_assignee", return_value=False),
        ):
            self.assertFalse(
                membership_invariants._user_can_view_task("P", "T", "test64+info@batchnepal.com")
            )


class TestPruneStaleWatchersAndDelegation(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        _delete_project(TEST_KEY)
        self.project = create_project(
            project_name="Membership Invariants Test",
            key=TEST_KEY,
            workflow_states=json.dumps([{"name": "To Do", "color": "#6B7280", "category": "open"}]),
            issue_types=json.dumps([{"name": "Task", "color": "#0B6BCB", "icon": "CheckSquare"}]),
        )["name"]
        self.task = frappe.get_doc({
            "doctype": "BP Task",
            "project": self.project,
            "title": "watched task",
            "task_type": "Task",
            "status": "To Do",
        }).insert(ignore_permissions=True).name

    def tearDown(self):
        _delete_project(TEST_KEY)
        for email in (
            "test39+info@batchnepal.com", "test73+info@batchnepal.com", "test65+info@batchnepal.com",
            "test43+info@batchnepal.com", "test18+info@batchnepal.com", "test62+info@batchnepal.com",
            "test75+info@batchnepal.com",
        ):
            if frappe.db.exists("User", email):
                frappe.delete_doc("User", email, ignore_permissions=True, force=True)
        frappe.db.commit()

    def _watch(self, user):
        _ensure_user(user)
        # BPTaskWatcher.validate() (added alongside notification_permissions.py)
        # requires the watcher's own user to currently be able to view the
        # task at creation time — a separate, later-added concern from the
        # revocation-pruning behavior this test class exercises. Bypass just
        # the creation-time gate here; test bodies still patch
        # _user_can_view_task themselves to control pruning behavior.
        with patch("batch_projects.task_invariants._user_can_view_task", return_value=True):
            return frappe.get_doc({
                "doctype": "BP Task Watcher",
                "task": self.task,
                "project": self.project,
                "user": user,
                "watch_reason": "manual",
            }).insert(ignore_permissions=True)

    def test_watcher_removed_when_user_has_no_remaining_access(self):
        watcher = self._watch("test18+info@batchnepal.com")
        with patch.object(membership_invariants, "_user_can_view_task", return_value=False):
            removed = membership_invariants.prune_stale_watchers(self.project, {"test18+info@batchnepal.com"})
        self.assertEqual(removed, [watcher.name])
        self.assertFalse(frappe.db.exists("BP Task Watcher", watcher.name))

    def test_watcher_kept_when_user_still_has_access(self):
        watcher = self._watch("test65+info@batchnepal.com")
        with patch.object(membership_invariants, "_user_can_view_task", return_value=True):
            removed = membership_invariants.prune_stale_watchers(
                self.project, {"test65+info@batchnepal.com"}
            )
        self.assertEqual(removed, [])
        self.assertTrue(frappe.db.exists("BP Task Watcher", watcher.name))

    def test_watcher_kept_across_soft_trash_regardless_of_access(self):
        watcher = self._watch("test73+info@batchnepal.com")
        frappe.db.set_value("BP Task", self.task, "is_deleted", 1)
        with patch.object(membership_invariants, "_user_can_view_task", return_value=False):
            removed = membership_invariants.prune_stale_watchers(self.project, {"test73+info@batchnepal.com"})
        self.assertEqual(removed, [])
        self.assertTrue(frappe.db.exists("BP Task Watcher", watcher.name))

    def test_watcher_removed_when_task_row_gone(self):
        watcher = self._watch("test43+info@batchnepal.com")
        frappe.db.set_value("BP Task Watcher", watcher.name, "task", "does-not-exist")
        removed = membership_invariants.prune_stale_watchers(self.project, {"test43+info@batchnepal.com"})
        self.assertEqual(removed, [watcher.name])

    def test_update_project_members_prunes_only_removed_users(self):
        watcher = self._watch("test39+info@batchnepal.com")
        with (
            patch("batch_projects.api.board.update_project_members") as real_update,
            patch.object(membership_invariants, "prune_stale_watchers") as prune,
        ):
            def fake_update(project, members):
                # Simulate the real function's own membership DB effect.
                frappe.db.sql("DELETE FROM `tabBP Project Member` WHERE parent=%s", project)
                return {"ok": True}
            real_update.side_effect = fake_update
            frappe.db.sql(
                """INSERT INTO `tabBP Project Member`
                   (name, parent, parenttype, parentfield, idx, user, role, creation, modified, owner, modified_by)
                   VALUES (%s, %s, 'BP Project', 'members', 1, %s, 'Member', NOW(), NOW(), %s, %s)""",
                (frappe.generate_hash(length=10), self.project, "test39+info@batchnepal.com",
                 "Administrator", "Administrator"),
            )
            membership_invariants.update_project_members(self.project, "[]")
        # create_project already auto-adds Administrator as a member, so the
        # real before/after diff (fake_update deletes ALL members) includes it.
        prune.assert_called_once_with(self.project, {"test39+info@batchnepal.com", "Administrator"})

    def test_after_project_member_delete_prunes_that_users_watchers(self):
        watcher = self._watch("test62+info@batchnepal.com")
        doc = frappe._dict(parent=self.project, user="test62+info@batchnepal.com")
        with patch.object(membership_invariants, "_user_can_view_task", return_value=False):
            membership_invariants.after_project_member_delete(doc)
        self.assertFalse(frappe.db.exists("BP Task Watcher", watcher.name))

    def test_after_project_member_delete_logs_and_reraises_on_failure(self):
        doc = frappe._dict(parent=self.project, user="test75+info@batchnepal.com")
        with (
            patch.object(
                membership_invariants, "prune_stale_watchers", side_effect=RuntimeError("boom")
            ),
            patch("frappe.log_error") as log_error,
        ):
            with self.assertRaises(RuntimeError):
                membership_invariants.after_project_member_delete(doc)
        log_error.assert_called_once()
