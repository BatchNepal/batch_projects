"""Task label catalog regression coverage."""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import task_validation as validation


class _Task:
    def __init__(self, labels="[]", project="PROJ-A", old=None):
        self.labels = labels
        self.project = project
        self._old = old

    def get_doc_before_save(self):
        return self._old


class TestTaskLabelInvariant(FrappeTestCase):
    @patch.object(validation.frappe.db, "get_value")
    def test_unknown_label_is_rejected(self, get_value):
        get_value.return_value = '[{"id":"lbl_1","label":"Urgent"}]'
        with self.assertRaises(frappe.ValidationError):
            validation.validate_task_labels(_Task('["Unknown"]'))

    @patch.object(validation.frappe.db, "get_value")
    def test_known_labels_are_allowed(self, get_value):
        get_value.return_value = '[{"id":"lbl_1","label":"Urgent"},{"id":"lbl_2","label":"Backend"}]'
        validation.validate_task_labels(_Task('["Urgent","Backend"]'))

    @patch.object(validation.frappe.db, "get_value")
    def test_duplicate_label_is_rejected(self, get_value):
        get_value.return_value = '[{"id":"lbl_1","label":"Urgent"}]'
        with self.assertRaises(frappe.ValidationError):
            validation.validate_task_labels(_Task('["Urgent","Urgent"]'))

    @patch.object(validation.frappe.db, "get_value")
    def test_unchanged_legacy_unknown_label_is_grandfathered(self, get_value):
        old = _Task('["Legacy"]')
        validation.validate_task_labels(_Task('["Legacy"]', old=old), old)
        get_value.assert_not_called()

    @patch.object(validation.frappe.db, "get_value")
    def test_project_move_revalidates_existing_labels(self, get_value):
        old = _Task('["Urgent"]', project="PROJ-A")
        get_value.return_value = '[{"id":"lbl_x","label":"Different"}]'
        with self.assertRaises(frappe.ValidationError):
            validation.validate_task_labels(
                _Task('["Urgent"]', project="PROJ-B", old=old), old
            )


if __name__ == "__main__":
    import unittest
    unittest.main()
