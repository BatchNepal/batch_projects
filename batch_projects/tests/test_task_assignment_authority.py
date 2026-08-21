"""Authorization contracts for task assignment and cross-project moves.

Run with:
    bench run-tests --module batch_projects.tests.test_task_assignment_authority
"""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import task_invariants as inv


class _Task:
    def __init__(self, project="P-A"):
        self.project = project


class _OldTask:
    def __init__(self, project="P-A"):
        self.project = project


class TestAssignmentAuthority(FrappeTestCase):
    @patch("batch_projects.access.has_at_least")
    @patch("batch_projects.access.is_instance_admin", return_value=False)
    def test_member_may_assign_existing_project_viewer(self, _is_admin, has_at_least):
        # actor: Manager? false; actor: Member? true; target: Viewer? true
        has_at_least.side_effect = [False, True, True]
        inv._validate_assignment_authority(
            _Task(), None, ["viewer@example.com"], []
        )

    @patch("batch_projects.access.has_at_least")
    @patch("batch_projects.access.is_instance_admin", return_value=False)
    def test_member_cannot_grant_task_only_access_to_outsider(self, _is_admin, has_at_least):
        # actor: Manager? false; actor: Member? true; target: Viewer? false
        has_at_least.side_effect = [False, True, False]
        with self.assertRaises(frappe.PermissionError):
            inv._validate_assignment_authority(
                _Task(), None, ["outside@example.com"], []
            )

    @patch("batch_projects.access.has_at_least")
    @patch("batch_projects.access.is_instance_admin", return_value=False)
    def test_manager_may_assign_outsider(self, _is_admin, has_at_least):
        has_at_least.return_value = True
        inv._validate_assignment_authority(
            _Task(), None, ["outside@example.com"], []
        )
        has_at_least.assert_called_once_with("P-A", "Manager", frappe.session.user)

    @patch("batch_projects.access.has_at_least")
    @patch("batch_projects.access.is_instance_admin", return_value=False)
    def test_task_only_assignee_cannot_rewrite_assignment_list(self, _is_admin, has_at_least):
        has_at_least.side_effect = [False, False]
        with self.assertRaises(frappe.PermissionError):
            inv._validate_assignment_authority(
                _Task(), _OldTask(), ["me@example.com", "other@example.com"], ["me@example.com"]
            )


class TestProjectMoveAuthority(FrappeTestCase):
    @patch("batch_projects.access.require")
    def test_cross_project_move_requires_manager_on_both_projects(self, require):
        inv._validate_project_move_authority(_Task("P-B"), _OldTask("P-A"))
        self.assertEqual(
            require.call_args_list,
            [
                __import__("unittest.mock").mock.call("P-A", "Manager"),
                __import__("unittest.mock").mock.call("P-B", "Manager"),
            ],
        )

    @patch("batch_projects.access.require")
    def test_same_project_edit_does_not_invoke_move_permission(self, require):
        inv._validate_project_move_authority(_Task("P-A"), _OldTask("P-A"))
        require.assert_not_called()


if __name__ == "__main__":
    import unittest

    unittest.main()
