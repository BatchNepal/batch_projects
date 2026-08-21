"""Regression coverage for BP Task relationship-edge integrity.

Run with:
    bench run-tests --module batch_projects.tests.test_task_link_invariants
"""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import task_invariants as inv


class _Link:
    def __init__(self, link_type, linked_task, dep_type="FS", lag_days=0):
        self.link_type = link_type
        self.linked_task = linked_task
        self.dep_type = dep_type
        self.lag_days = lag_days
        self.linked_task_project = None

    def get(self, field):
        return getattr(self, field, None)


class _Task:
    def __init__(self, name="A-1", project="P-A", links=None):
        self.name = name
        self.project = project
        self.links = list(links or [])

    def get(self, field):
        return getattr(self, field, None)


class TestTaskLinkIntegrity(FrappeTestCase):
    def test_self_link_is_rejected(self):
        task = _Task(links=[_Link("relates to", "A-1")])
        with self.assertRaises(frappe.ValidationError):
            inv._validate_task_links(task)

    def test_duplicate_relationship_is_rejected(self):
        task = _Task(
            links=[
                _Link("relates to", "B-1"),
                _Link("relates to", "B-1"),
            ]
        )
        with self.assertRaises(frappe.ValidationError):
            inv._validate_task_links(task)

    @patch.object(inv.frappe.db, "get_value")
    def test_link_to_trashed_task_is_rejected(self, get_value):
        get_value.return_value = frappe._dict(name="B-1", project="P-B", is_deleted=1)
        with self.assertRaises(frappe.ValidationError):
            inv._validate_task_links(_Task(links=[_Link("relates to", "B-1")]))

    @patch.object(inv, "_dependency_reaches", return_value=True)
    @patch.object(inv.frappe.db, "get_value")
    def test_new_blocking_cycle_is_rejected(self, get_value, reaches):
        get_value.return_value = frappe._dict(name="B-1", project="P-B", is_deleted=0)
        with self.assertRaises(frappe.ValidationError):
            inv._validate_task_links(_Task(links=[_Link("blocks", "B-1")]))
        reaches.assert_called_once_with("B-1", "A-1")

    @patch.object(inv, "_dependency_reaches", return_value=False)
    @patch.object(inv.frappe.db, "get_value")
    def test_cross_project_non_cyclic_dependency_is_allowed(self, get_value, reaches):
        get_value.return_value = frappe._dict(name="B-1", project="P-B", is_deleted=0)
        link = _Link("blocks", "B-1")
        inv._validate_task_links(_Task(links=[link]))
        self.assertEqual(link.linked_task_project, "P-B")
        reaches.assert_called_once_with("B-1", "A-1")

    @patch.object(inv.frappe.db, "get_value")
    def test_unchanged_legacy_link_is_grandfathered(self, get_value):
        old_link = _Link("blocks", "B-1")
        new_link = _Link("blocks", "B-1")
        old = _Task(links=[old_link])
        task = _Task(links=[new_link])
        inv._validate_task_links(task, old)
        get_value.assert_not_called()


if __name__ == "__main__":
    import unittest

    unittest.main()
