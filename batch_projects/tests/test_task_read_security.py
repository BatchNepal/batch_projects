"""Task-detail relationship visibility and hook regression coverage."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import task_reads
from batch_projects import task_validation


class TestHookContracts(FrappeTestCase):
    def test_task_detail_is_routed_through_permission_filter(self):
        self.assertEqual(
            hooks.override_whitelisted_methods["batch_projects.api.board.get_task"],
            "batch_projects.task_reads.get_task",
        )


class TestLinkedTaskReadSecurity(FrappeTestCase):
    @patch("batch_projects.task_invariants._user_can_view_task")
    @patch.object(task_reads.frappe, "get_all")
    def test_inaccessible_cross_project_link_is_filtered(self, get_all, can_view):
        get_all.return_value = [
            frappe._dict(name="TASK-PUBLIC", project="PROJ-A", is_deleted=0),
            frappe._dict(name="TASK-PRIVATE", project="PROJ-B", is_deleted=0),
            frappe._dict(name="TASK-TRASH", project="PROJ-A", is_deleted=1),
        ]
        can_view.side_effect = [True, False]

        visible = task_reads._visible_link_names([
            {"linked_task": "TASK-PUBLIC"},
            {"linked_task": "TASK-PRIVATE"},
            {"linked_task": "TASK-TRASH"},
        ])

        self.assertEqual(visible, {"TASK-PUBLIC"})

    @patch("batch_projects.task_invariants._user_can_view_task")
    @patch.object(task_reads.frappe, "get_all")
    def test_subtask_requires_its_own_task_visibility(self, get_all, can_view):
        get_all.return_value = [
            frappe._dict(name="SUB-LIVE", project="PROJ-A"),
            frappe._dict(name="SUB-HIDDEN", project="PROJ-A"),
        ]
        can_view.side_effect = [True, False]
        visible = task_reads._visible_subtask_names([
            {"name": "SUB-LIVE"}, {"name": "SUB-HIDDEN"}, {"name": "SUB-TRASH"}
        ])
        self.assertEqual(visible, {"SUB-LIVE"})
        self.assertEqual(get_all.call_args.kwargs["filters"]["is_deleted"], 0)


class _LinkRow:
    def __init__(self, linked_task, link_type="relates to"):
        self.linked_task = linked_task
        self.link_type = link_type
        self.linked_task_project = None

    def get(self, key):
        return getattr(self, key, None)


class _Task:
    def __init__(self, links, project="PROJ-A"):
        self.links = links
        self.project = project

    def get(self, key):
        return getattr(self, key, None)


class TestLinkCreationVisibility(FrappeTestCase):
    @patch("batch_projects.task_invariants._user_can_view_task", return_value=False)
    @patch.object(task_validation.frappe.db, "get_value")
    def test_new_link_to_inaccessible_task_is_rejected(self, get_value, can_view):
        get_value.return_value = frappe._dict(
            name="PRIVATE-1", project="PRIVATE-PROJ", is_deleted=0
        )
        with self.assertRaises(frappe.PermissionError):
            task_validation.validate_link_visibility(
                _Task([_LinkRow("PRIVATE-1")]), old=None
            )

    @patch("batch_projects.task_invariants._user_can_view_task")
    @patch.object(task_validation.frappe.db, "get_value")
    def test_unchanged_legacy_link_is_not_revalidated(self, get_value, can_view):
        old = _Task([_LinkRow("PRIVATE-1")])
        task_validation.validate_link_visibility(
            _Task([_LinkRow("PRIVATE-1")]), old=old
        )
        get_value.assert_not_called()
        can_view.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
