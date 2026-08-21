"""Workflow lifecycle-category mutation regression coverage."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import project_schema as schema


class TestWorkflowCategoryInvariant(FrappeTestCase):
    @patch.object(schema, "active_task_values", return_value={"Done"})
    def test_in_use_status_category_cannot_change(self, active_values):
        current = [
            {"name": "To Do", "category": "unstarted"},
            {"name": "Done", "category": "completed"},
        ]
        incoming = [
            {"name": "To Do", "category": "unstarted"},
            {"name": "Done", "category": "started"},
        ]
        with self.assertRaises(frappe.ValidationError):
            schema.assert_workflow_categories_safe("PROJ-A", current, incoming)

    @patch.object(schema, "active_task_values", return_value=set())
    def test_unused_status_category_can_change(self, active_values):
        current = [{"name": "Review", "category": "started"}]
        incoming = [{"name": "Review", "category": "completed"}]
        schema.assert_workflow_categories_safe("PROJ-A", current, incoming)

    @patch.object(schema, "active_task_values")
    def test_color_or_transition_change_is_not_a_category_migration(self, active_values):
        current = [{"name": "Done", "category": "completed", "color": "#111"}]
        incoming = [{"name": "Done", "category": "completed", "color": "#222", "allowed_to": []}]
        schema.assert_workflow_categories_safe("PROJ-A", current, incoming)
        active_values.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
