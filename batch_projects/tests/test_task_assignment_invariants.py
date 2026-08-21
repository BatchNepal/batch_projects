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
        epic=None,
        milestone=None,
        parent_task=None,
        sprint=None,
    ):
        self.project = project
        self.name = name
        self.task_key = name
        self.title = "Invariant test"
        self.description = description
        self.epic = epic
        self.milestone = milestone
        self.parent_task = parent_task
        self.sprint = sprint
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
            "batch_projects.task_invariants.validate_task_assignees",
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
            name="alice@example.com",
            full_name="Alice",
            enabled=1,
            user_type="System User",
        )
        task = _FakeTask(
            [
                SimpleNamespace(user="alice@example.com", full_name="Alice"),
                SimpleNamespace(user="alice@example.com", full_name="Alice"),
            ]
        )

        with self.assertRaises(frappe.ValidationError):
            inv.validate_task_assignees(task)

    @patch.object(inv.frappe.db, "get_value")
    def test_unchanged_legacy_assignment_does_not_revalidate_identity(self, get_value):
        legacy = [SimpleNamespace(user="disabled@example.com", full_name="Legacy")]
        old = _FakeTask(legacy)
        task = _FakeTask(
            [SimpleNamespace(user="disabled@example.com", full_name="Legacy")],
            old=old,
        )

        inv.validate_task_assignees(task)
        get_value.assert_not_called()

    @patch("batch_projects.events.emit")
    @patch.object(inv.frappe, "get_doc")
    @patch.object(inv.frappe.db, "get_value")
    def test_initial_assignee_emits_normal_assignment_event(
        self, get_value, get_doc, emit
    ):
        get_value.return_value = "Creator Name"
        activity = MagicMock()
        get_doc.return_value = activity
        task = _FakeTask(
            [SimpleNamespace(user="alice@example.com", full_name="Alice Example")]
        )

        inv.after_task_insert(task)

        activity.insert.assert_called_once_with(ignore_permissions=True)
        emit.assert_called_once()
        event_name, payload = emit.call_args.args
        self.assertEqual(event_name, "task.assigned")
        self.assertEqual(payload["task"], "BP-1")
        self.assertEqual(payload["assignee"], "alice@example.com")
        self.assertTrue(payload["initial_assignment"])


class TestTaskRelationshipInvariants(FrappeTestCase):
    @patch.object(inv.frappe.db, "get_value")
    def test_cross_project_epic_is_rejected(self, get_value):
        get_value.return_value = "BP-PROJ-2"
        task = _FakeTask(epic="EPIC-OTHER")

        with self.assertRaises(frappe.ValidationError):
            inv._validate_project_relations(task)

    @patch.object(inv.frappe.db, "get_value")
    def test_same_project_epic_is_allowed(self, get_value):
        get_value.return_value = "BP-PROJ-1"
        task = _FakeTask(epic="EPIC-OK")

        inv._validate_project_relations(task)

    @patch.object(inv.frappe.db, "get_value")
    def test_cross_project_parent_is_rejected(self, get_value):
        get_value.return_value = frappe._dict(
            project="BP-PROJ-2", parent_task=None, is_deleted=0
        )
        task = _FakeTask(parent_task="BP-PARENT")

        with self.assertRaises(frappe.ValidationError):
            inv._validate_project_relations(task)

    @patch.object(inv.frappe.db, "get_value")
    def test_parent_cycle_is_rejected(self, get_value):
        get_value.side_effect = [
            frappe._dict(project="BP-PROJ-1", parent_task="BP-GRAND", is_deleted=0),
            "BP-1",  # BP-GRAND.parent_task points back to current task
        ]
        task = _FakeTask(parent_task="BP-PARENT")

        with self.assertRaises(frappe.ValidationError):
            inv._validate_project_relations(task)

    @patch.object(inv.frappe.db, "get_value")
    def test_team_sprint_requires_same_project_team(self, get_value):
        task = _FakeTask(sprint="SPRINT-TEAM")
        get_value.side_effect = [
            frappe._dict(project=None, team="TEAM-A", sprint_type="Team"),
            "TEAM-B",
        ]

        with self.assertRaises(frappe.ValidationError):
            inv._validate_project_relations(task)

    @patch.object(inv.frappe.db, "get_value")
    def test_team_sprint_on_same_team_is_allowed(self, get_value):
        task = _FakeTask(sprint="SPRINT-TEAM")
        get_value.side_effect = [
            frappe._dict(project=None, team="TEAM-A", sprint_type="Team"),
            "TEAM-A",
        ]

        inv._validate_project_relations(task)


class TestMentionAuthorization(FrappeTestCase):
    @patch.object(inv, "_user_can_view_task", return_value=False)
    def test_new_mention_without_access_is_rejected(self, can_view):
        with self.assertRaises(frappe.PermissionError):
            inv._assert_new_mentions_authorized(
                project="BP-PROJ-1",
                task="BP-1",
                before="hello",
                after="hello @[External](external@example.com)",
            )
        can_view.assert_called_once()

    @patch.object(inv, "_user_can_view_task", return_value=True)
    def test_existing_mention_is_not_revalidated_on_unrelated_edit(self, can_view):
        token = "@[Alice](alice@example.com)"
        inv._assert_new_mentions_authorized(
            project="BP-PROJ-1",
            task="BP-1",
            before=f"hello {token}",
            after=f"updated text {token}",
        )
        can_view.assert_not_called()

    @patch.object(inv, "_user_can_view_task", return_value=True)
    def test_new_authorized_mention_is_allowed(self, can_view):
        inv._assert_new_mentions_authorized(
            project="BP-PROJ-1",
            task="BP-1",
            before="",
            after="@[Alice](alice@example.com)",
        )
        can_view.assert_called_once()


if __name__ == "__main__":
    unittest.main()
