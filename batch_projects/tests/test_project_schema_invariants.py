"""Regression coverage for project schema mutation invariants.

Run with:
    bench run-tests --module batch_projects.tests.test_project_schema_invariants
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import project_schema as schema


class TestSchemaRouting(FrappeTestCase):
    def test_high_risk_board_methods_are_overridden(self):
        self.assertEqual(
            hooks.override_whitelisted_methods[
                "batch_projects.api.board.update_project_workflow"
            ],
            "batch_projects.project_schema.update_project_workflow",
        )
        self.assertEqual(
            hooks.override_whitelisted_methods[
                "batch_projects.api.board.update_project_issue_types"
            ],
            "batch_projects.project_schema.update_project_issue_types",
        )
        self.assertEqual(
            hooks.override_whitelisted_methods[
                "batch_projects.api.board.update_project_labels"
            ],
            "batch_projects.project_schema.update_project_labels",
        )


class TestReferencedSchemaValues(FrappeTestCase):
    @patch.object(schema, "active_task_values", return_value={"In Progress"})
    def test_used_status_cannot_disappear(self, active_values):
        with self.assertRaises(frappe.ValidationError):
            schema.assert_referenced_names_survive(
                "PROJ-A",
                "status",
                {"To Do", "In Progress", "Done"},
                {"To Do", "Done"},
                "workflow state",
            )

    @patch.object(schema, "active_task_values", return_value=set())
    def test_unused_status_can_be_removed(self, active_values):
        schema.assert_referenced_names_survive(
            "PROJ-A",
            "status",
            {"To Do", "Unused", "Done"},
            {"To Do", "Done"},
            "workflow state",
        )

    @patch.object(schema, "active_task_values", return_value={"Bug"})
    def test_used_task_type_cannot_be_renamed_by_remove_add(self, active_values):
        with self.assertRaises(frappe.ValidationError):
            schema.assert_referenced_names_survive(
                "PROJ-A",
                "task_type",
                {"Task", "Bug"},
                {"Task", "Defect"},
                "task type",
            )


class TestWorkflowShape(FrappeTestCase):
    def test_duplicate_state_names_are_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            schema.unique_named_rows(
                [{"name": "To Do"}, {"name": "To Do"}], "workflow state"
            )

    @patch.object(schema, "_finish")
    @patch.object(schema.frappe.db, "set_value")
    @patch.object(schema.frappe.db, "get_value", return_value=3)
    @patch.object(schema, "assert_referenced_names_survive")
    @patch.object(schema.frappe, "get_cached_doc")
    @patch.object(schema, "require_admin")
    def test_unknown_transition_target_is_rejected_before_write(
        self, require_admin, get_project, survive, get_value, set_value, finish
    ):
        project = MagicMock()
        project.get_workflow_states.return_value = [{"name": "To Do"}]
        get_project.return_value = project

        with self.assertRaises(frappe.ValidationError):
            schema.update_project_workflow(
                "PROJ-A",
                [
                    {"name": "To Do", "allowed_to": ["Missing"]},
                    {"name": "Done", "category": "completed"},
                ],
            )

        set_value.assert_not_called()
        finish.assert_not_called()


class TestLabelIdentityGuard(FrappeTestCase):
    @patch.object(schema, "_finish")
    @patch.object(schema.frappe.db, "set_value")
    @patch.object(schema, "active_task_labels", return_value={"Urgent"})
    @patch.object(schema.frappe.db, "get_value")
    @patch.object(schema, "require_admin")
    def test_used_label_cannot_be_renamed_under_same_id(
        self, require_admin, get_value, used, set_value, finish
    ):
        get_value.return_value = '[{"id":"lbl_1","label":"Urgent","color":"#f00"}]'

        with self.assertRaises(frappe.ValidationError):
            schema.update_project_labels(
                "PROJ-A",
                [{"id": "lbl_1", "label": "Critical", "color": "#f00"}],
            )

        set_value.assert_not_called()
        finish.assert_not_called()

    @patch.object(schema, "_finish")
    @patch.object(schema.frappe.db, "set_value")
    @patch.object(schema, "active_task_labels", return_value={"Urgent"})
    @patch.object(schema.frappe.db, "get_value")
    @patch.object(schema, "require_admin")
    def test_color_change_preserves_used_label_identity(
        self, require_admin, get_value, used, set_value, finish
    ):
        get_value.return_value = '[{"id":"lbl_1","label":"Urgent","color":"#f00"}]'

        rows = schema.update_project_labels(
            "PROJ-A",
            [{"id": "lbl_1", "label": "Urgent", "color": "#0f0"}],
        )

        self.assertEqual(rows[0]["id"], "lbl_1")
        self.assertEqual(rows[0]["label"], "Urgent")
        set_value.assert_called_once()
        finish.assert_called_once_with("PROJ-A")


if __name__ == "__main__":
    import unittest
    unittest.main()
