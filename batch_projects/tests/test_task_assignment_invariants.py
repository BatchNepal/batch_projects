"""Regression coverage for task-assignment state equivalence.

The invariant under test is deliberately path-independent: creating a task
already assigned to Alice must establish the same assignment lifecycle that
adding Alice one save later does.

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
    def __init__(self, assignees=None, project="BP-PROJ-1"):
        self.project = project
        self.name = "BP-1"
        self.task_key = "BP-1"
        self.title = "Invariant test"
        self.assignees = list(assignees or [])

    def get(self, field):
        return getattr(self, field, None)

    def append(self, field, value):
        assert field == "assignees"
        row = SimpleNamespace(**value)
        self.assignees.append(row)
        return row


class TestTaskAssignmentInvariantHooks(FrappeTestCase):
    def test_hooks_cover_all_document_write_paths(self):
        task_hooks = hooks.doc_events["BP Task"]
        self.assertEqual(
            task_hooks["before_insert"],
            "batch_projects.task_invariants.before_task_insert",
        )
        self.assertEqual(
            task_hooks["validate"],
            "batch_projects.task_invariants.validate_task_assignees",
        )
        self.assertEqual(
            task_hooks["after_insert"],
            "batch_projects.task_invariants.after_task_insert",
        )

    @patch.object(inv.frappe.db, "get_value")
    def test_default_assignee_becomes_real_assignment(self, get_value):
        task = _FakeTask()
        get_value.side_effect = [
            "alice@example.com",  # BP Project.default_assignee
            frappe._dict(
                name="alice@example.com",
                full_name="Alice Example",
                enabled=1,
                user_type="System User",
            ),
        ]

        inv.before_task_insert(task)

        self.assertEqual(len(task.assignees), 1)
        self.assertEqual(task.assignees[0].user, "alice@example.com")
        self.assertEqual(task.assignees[0].full_name, "Alice Example")

    @patch.object(inv.frappe.db, "get_value")
    def test_explicit_assignee_is_not_replaced_by_project_default(self, get_value):
        task = _FakeTask(
            [SimpleNamespace(user="bob@example.com", full_name="Bob Example")]
        )

        inv.before_task_insert(task)

        get_value.assert_not_called()
        self.assertEqual([a.user for a in task.assignees], ["bob@example.com"])

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


if __name__ == "__main__":
    unittest.main()
