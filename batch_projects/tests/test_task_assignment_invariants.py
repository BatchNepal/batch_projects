"""Regression coverage for high-blast-radius BP Task mutation invariants.

Run with:
    bench run-tests --module batch_projects.tests.test_task_assignment_invariants
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import task_invariants as inv


class _FakeTask:
    def __init__(
        self,
        assignees=None,
        project="BP-PROJ-1",
        old=None,
        *,
        name="BP-1",
        description="",
        task_type=None,
        epic=None,
        milestone=None,
        parent_task=None,
        sprint=None,
        approval_status="Approval Not Required",
        approver=None,
    ):
        self.project = project
        self.name = name
        self.task_key = name
        self.title = "Invariant test"
        self.description = description
        self.task_type = task_type
        self.epic = epic
        self.milestone = milestone
        self.parent_task = parent_task
        self.sprint = sprint
        self.approval_status = approval_status
        self.approver = approver
        self.assignees = list(assignees or [])
        self._old = old

    def get(self, field):
        return getattr(self, field, None)

    def get_doc_before_save(self):
        return self._old

    def is_new(self):
        return self._old is None


class TestTaskAssignmentInvariantHooks(FrappeTestCase):
    def test_hooks_cover_all_document_write_paths(self):
        task_hooks = hooks.doc_events["BP Task"]
        self.assertEqual(
            task_hooks["validate"],
            "batch_projects.task_validation.validate_task",
        )
        self.assertEqual(
            task_hooks["after_insert"],
            "batch_projects.task_invariants.after_task_insert",
        )

    @patch.object(inv.frappe.db, "get_value")
    def test_disabled_or_website_user_cannot_enter_assignment_graph(self, get_value):
        for row in (
            frappe._dict(name="disabled@example.com", full_name="Disabled", enabled=0, user_type="System User"),
            frappe._dict(name="web@example.com", full_name="Web", enabled=1, user_type="Website User"),
        ):
            get_value.return_value = row
            task = _FakeTask([SimpleNamespace(user=row.name, full_name="")])
            with self.assertRaises(frappe.ValidationError):
                inv.validate_task_assignees(task)

    @patch.object(inv.frappe.db, "get_value")
    def test_duplicate_assignee_is_rejected(self, get_value):
        get_value.return_value = frappe._dict(
            name="alice@example.com", full_name="Alice", enabled=1, user_type="System User"
        )
        task = _FakeTask([
            SimpleNamespace(user="alice@example.com", full_name="Alice"),
            SimpleNamespace(user="alice@example.com", full_name="Alice"),
        ])
        with self.assertRaises(frappe.ValidationError):
            inv.validate_task_assignees(task)

    @patch.object(inv.frappe.db, "get_value")
    def test_unchanged_legacy_assignment_does_not_revalidate_identity(self, get_value):
        legacy = [SimpleNamespace(user="disabled@example.com", full_name="Legacy")]
        old = _FakeTask(legacy)
        task = _FakeTask([SimpleNamespace(user="disabled@example.com", full_name="Legacy")], old=old)
        inv.validate_task_assignees(task)
        get_value.assert_not_called()

    @patch("batch_projects.events.emit")
    @patch.object(inv.frappe, "get_doc")
    @patch.object(inv.frappe.db, "get_value")
    def test_initial_assignee_emits_normal_assignment_event(self, get_value, get_doc, emit):
        get_value.return_value = "Creator Name"
        activity = MagicMock()
        get_doc.return_value = activity
        task = _FakeTask([SimpleNamespace(user="alice@example.com", full_name="Alice Example")])
        inv.after_task_insert(task)
        activity.insert.assert_called_once_with(ignore_permissions=True)
        event_name, payload = emit.call_args.args
        self.assertEqual(event_name, "task.assigned")
        self.assertEqual(payload["assignee"], "alice@example.com")
        self.assertTrue(payload["initial_assignment"])


class TestTaskTypeInvariant(FrappeTestCase):
    @patch.object(inv.frappe, "get_cached_doc")
    def test_changed_invalid_task_type_fails_closed(self, get_project):
        project = MagicMock()
        project.get_issue_types.return_value = [{"name": "Task"}, {"name": "Bug"}]
        get_project.return_value = project
        old = _FakeTask(task_type="Task")
        task = _FakeTask(task_type="Unknown", old=old)
        with self.assertRaises(frappe.ValidationError):
            inv._validate_task_type(task, old)

    @patch.object(inv.frappe, "get_cached_doc")
    def test_unchanged_legacy_task_type_is_grandfathered(self, get_project):
        old = _FakeTask(task_type="Legacy")
        inv._validate_task_type(_FakeTask(task_type="Legacy", old=old), old)
        get_project.assert_not_called()


class TestApprovalInvariant(FrappeTestCase):
    @patch.object(inv, "_user_can_view_task", return_value=False)
    @patch.object(inv, "_assert_assignable_user")
    def test_new_pending_approver_must_be_able_to_view_task(self, assignable, can_view):
        old = _FakeTask()
        task = _FakeTask(
            old=old, approval_status="Pending", approver="approver@example.com"
        )
        with self.assertRaises(frappe.PermissionError):
            inv._validate_pending_approver(task, old, [])
        assignable.assert_called_once_with("approver@example.com")
        can_view.assert_called_once()

    @patch.object(inv, "_user_can_view_task", return_value=True)
    @patch.object(inv, "_assert_assignable_user")
    def test_authorized_pending_approver_is_allowed(self, assignable, can_view):
        old = _FakeTask()
        task = _FakeTask(
            old=old, approval_status="Pending", approver="approver@example.com"
        )
        inv._validate_pending_approver(task, old, [])
        assignable.assert_called_once_with("approver@example.com")
        can_view.assert_called_once()


class TestTaskRelationshipInvariants(FrappeTestCase):
    @patch.object(inv.frappe.db, "get_value")
    def test_cross_project_epic_is_rejected(self, get_value):
        get_value.return_value = "BP-PROJ-2"
        with self.assertRaises(frappe.ValidationError):
            inv._validate_project_relations(_FakeTask(epic="EPIC-OTHER"))

    @patch.object(inv.frappe.db, "get_value")
    def test_same_project_epic_is_allowed(self, get_value):
        get_value.return_value = "BP-PROJ-1"
        inv._validate_project_relations(_FakeTask(epic="EPIC-OK"))

    @patch.object(inv.frappe.db, "get_value")
    def test_unchanged_legacy_cross_project_epic_is_grandfathered(self, get_value):
        old = _FakeTask(epic="EPIC-LEGACY")
        inv._validate_project_relations(_FakeTask(epic="EPIC-LEGACY", old=old), old)
        get_value.assert_not_called()

    @patch.object(inv.frappe.db, "get_value")
    def test_cross_project_parent_is_rejected(self, get_value):
        get_value.return_value = frappe._dict(project="BP-PROJ-2", parent_task=None, is_deleted=0)
        with self.assertRaises(frappe.ValidationError):
            inv._validate_project_relations(_FakeTask(parent_task="BP-PARENT"))

    @patch.object(inv.frappe.db, "get_value")
    def test_parent_cycle_is_rejected(self, get_value):
        get_value.side_effect = [
            frappe._dict(project="BP-PROJ-1", parent_task="BP-GRAND", is_deleted=0),
            "BP-1",
        ]
        with self.assertRaises(frappe.ValidationError):
            inv._validate_project_relations(_FakeTask(parent_task="BP-PARENT"))

    @patch.object(inv.frappe.db, "get_value")
    def test_team_sprint_requires_same_project_team(self, get_value):
        get_value.side_effect = [
            frappe._dict(project=None, team="TEAM-A", sprint_type="Team"), "TEAM-B"
        ]
        with self.assertRaises(frappe.ValidationError):
            inv._validate_project_relations(_FakeTask(sprint="SPRINT-TEAM"))

    @patch.object(inv.frappe.db, "get_value")
    def test_team_sprint_on_same_team_is_allowed(self, get_value):
        get_value.side_effect = [
            frappe._dict(project=None, team="TEAM-A", sprint_type="Team"), "TEAM-A"
        ]
        inv._validate_project_relations(_FakeTask(sprint="SPRINT-TEAM"))


class TestWatcherProjectMove(FrappeTestCase):
    @patch.object(inv, "_user_can_view_task")
    @patch.object(inv.frappe.db, "delete")
    @patch.object(inv.frappe.db, "set_value")
    @patch.object(inv.frappe, "get_all")
    def test_project_move_prunes_old_only_watchers(self, get_all, set_value, delete, can_view):
        get_all.return_value = [
            frappe._dict(name="W-KEEP", user="keep@example.com"),
            frappe._dict(name="W-DROP", user="drop@example.com"),
        ]
        can_view.side_effect = [True, False]
        inv._prune_watchers_for_project_move(_FakeTask(project="BP-PROJ-2"), [])
        set_value.assert_called_once_with(
            "BP Task Watcher", "W-KEEP", "project", "BP-PROJ-2", update_modified=False
        )
        delete.assert_called_once_with("BP Task Watcher", {"name": "W-DROP"})


class TestMentionAuthorization(FrappeTestCase):
    @patch.object(inv, "_user_can_view_task", return_value=False)
    def test_new_mention_without_access_is_rejected(self, can_view):
        with self.assertRaises(frappe.PermissionError):
            inv._assert_new_mentions_authorized(
                project="BP-PROJ-1", task="BP-1", before="hello",
                after="hello @[External](external@example.com)",
            )
        can_view.assert_called_once()

    @patch.object(inv, "_user_can_view_task", return_value=True)
    def test_existing_mention_is_not_revalidated_on_unrelated_edit(self, can_view):
        token = "@[Alice](alice@example.com)"
        inv._assert_new_mentions_authorized(
            project="BP-PROJ-1", task="BP-1", before=f"hello {token}", after=f"updated {token}"
        )
        can_view.assert_not_called()

    @patch.object(inv, "_user_can_view_task", return_value=True)
    def test_new_authorized_mention_is_allowed(self, can_view):
        inv._assert_new_mentions_authorized(
            project="BP-PROJ-1", task="BP-1", before="", after="@[Alice](alice@example.com)"
        )
        can_view.assert_called_once()


if __name__ == "__main__":
    unittest.main()
