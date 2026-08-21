"""Completion dependency invariant regression coverage."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import task_validation as validation


class _Link:
    def __init__(self, linked_task, link_type="is blocked by"):
        self.linked_task = linked_task
        self.link_type = link_type


class _Task:
    def __init__(self, status, old=None, links=None, project="PROJ-A"):
        self.status = status
        self.project = project
        self.links = list(links or [])
        self._old = old
        self.flags = {}

    def get(self, key):
        return getattr(self, key, None)


class TestCompletionDependencyInvariant(FrappeTestCase):
    @patch.object(validation, "_force_dependency_override", return_value=False)
    @patch.object(validation.frappe, "get_all")
    @patch.object(validation.frappe, "get_cached_doc")
    def test_active_unfinished_blocker_refuses_completion(self, get_project, get_all, force):
        project = MagicMock()
        project.get_completed_statuses.return_value = ["Done"]
        get_project.return_value = project
        get_all.return_value = [
            frappe._dict(name="BLOCK-1", task_key="PRJ-2", title="Blocker", status="In Progress")
        ]
        old = _Task("In Progress")
        doc = _Task("Done", old=old, links=[_Link("BLOCK-1")])

        with self.assertRaises(frappe.ValidationError):
            validation.validate_completion_dependencies(doc, old)

        filters = get_all.call_args.kwargs["filters"]
        self.assertEqual(filters["is_deleted"], 0)

    @patch.object(validation, "_force_dependency_override", return_value=False)
    @patch.object(validation.frappe, "get_all", return_value=[])
    @patch.object(validation.frappe, "get_cached_doc")
    def test_trashed_or_completed_blockers_do_not_block(self, get_project, get_all, force):
        project = MagicMock()
        project.get_completed_statuses.return_value = ["Done"]
        get_project.return_value = project
        old = _Task("In Progress")
        doc = _Task("Done", old=old, links=[_Link("BLOCK-1")])

        validation.validate_completion_dependencies(doc, old)

    @patch.object(validation, "_force_dependency_override", return_value=True)
    @patch.object(validation.frappe, "get_all")
    @patch.object(validation.frappe, "get_cached_doc")
    def test_explicit_force_preserves_existing_override(self, get_project, get_all, force):
        project = MagicMock()
        project.get_completed_statuses.return_value = ["Done"]
        get_project.return_value = project
        old = _Task("In Progress")
        doc = _Task("Done", old=old, links=[_Link("BLOCK-1")])

        validation.validate_completion_dependencies(doc, old)
        get_all.assert_not_called()

    @patch.object(validation.frappe, "get_cached_doc")
    def test_non_status_edit_does_not_recheck_blockers(self, get_project):
        old = _Task("In Progress")
        doc = _Task("In Progress", old=old, links=[_Link("BLOCK-1")])
        validation.validate_completion_dependencies(doc, old)
        get_project.assert_not_called()


class TestForceDependencyOverrideAuthority(FrappeTestCase):
    """_force_dependency_override's actual body, not mocked out — a request-
    supplied `force` param must require Manager+ on the task's project;
    only the internal doc.flags path is unconditionally trusted."""

    def test_internal_flag_bypasses_regardless_of_role(self):
        doc = _Task("Done")
        doc.flags = {"ignore_dependency_blockers": True}
        with patch("batch_projects.access.has_at_least") as has_at_least:
            self.assertTrue(validation._force_dependency_override(doc))
        has_at_least.assert_not_called()

    def test_request_force_denied_for_non_manager(self):
        doc = _Task("Done")
        with (
            patch.object(validation.frappe, "form_dict", {"force": "1"}),
            patch("batch_projects.access.has_at_least", return_value=False) as has_at_least,
        ):
            self.assertFalse(validation._force_dependency_override(doc))
        has_at_least.assert_called_once_with("PROJ-A", "Manager")

    def test_request_force_allowed_for_manager(self):
        doc = _Task("Done")
        with (
            patch.object(validation.frappe, "form_dict", {"force": "1"}),
            patch("batch_projects.access.has_at_least", return_value=True),
        ):
            self.assertTrue(validation._force_dependency_override(doc))

    def test_no_force_param_short_circuits_without_role_check(self):
        doc = _Task("Done")
        with (
            patch.object(validation.frappe, "form_dict", {}),
            patch("batch_projects.access.has_at_least") as has_at_least,
        ):
            self.assertFalse(validation._force_dependency_override(doc))
        has_at_least.assert_not_called()

    def test_non_manager_force_attempt_still_blocks_real_completion(self):
        """End-to-end: the bypass this was written to close, through the
        actual validate_completion_dependencies call, not a mocked override."""
        with (
            patch.object(validation.frappe, "form_dict", {"force": "1"}),
            patch("batch_projects.access.has_at_least", return_value=False),
            patch.object(validation.frappe, "get_all") as get_all,
            patch.object(validation.frappe, "get_cached_doc") as get_project,
        ):
            project = MagicMock()
            project.get_completed_statuses.return_value = ["Done"]
            get_project.return_value = project
            get_all.return_value = [
                frappe._dict(name="BLOCK-1", task_key="PRJ-2", title="Blocker", status="In Progress")
            ]
            old = _Task("In Progress")
            doc = _Task("Done", old=old, links=[_Link("BLOCK-1")])
            with self.assertRaises(frappe.ValidationError):
                validation.validate_completion_dependencies(doc, old)


if __name__ == "__main__":
    import unittest
    unittest.main()
