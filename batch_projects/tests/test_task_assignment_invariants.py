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
    def __init__(self, assignees=None, project="BP-PROJ-1", old=None):
        self.project = project
        self.name = "BP-1"
        self.task_key = "BP-1"
        self.title = "Invariant test"
        self.assignees = list(assignees or [])
        self._old = old

    def get(self, field):
        return getattr(self, field, None)

    def get_doc_before_save(self):
        return self._old


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
    def test_unchanged_legacy_assignment_does_not_block_unrelated_edit(self, get_value):
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


if __name__ == "__main__":
    unittest.main()
