"""Regression coverage for project schema mutation invariants.

Recovered gaps (BatchProjects git-audit, P1 #1-#3): update_project_workflow/
_issue_types/_labels replaced their whole JSON schema wholesale with no check
for whether a removed/renamed entry, or a workflow state's lifecycle
category, was still referenced by live tasks — orphaning existing task state.

Run with:
    bench run-tests --module batch_projects.tests.test_project_schema_invariants
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.api import board


def _states(*rows):
    return json.dumps(list(rows))


def _get_value_returning(schema_json):
    """frappe.db.get_value("BP Project", project, field) — the schema field
    (workflow_states/issue_types/labels) needs the fixture JSON, but
    update_project_workflow also reads schema_version separately (expects an
    int), so a single blanket return_value breaks the increment."""
    def _side_effect(doctype, name, field, *a, **kw):
        if field == "schema_version":
            return 0
        return schema_json
    return _side_effect


class TestWorkflowStateInvariants(FrappeTestCase):
    def test_removing_an_in_use_state_is_rejected(self):
        existing = _states({"name": "To Do", "category": "unstarted"}, {"name": "In Progress", "category": "started"})
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", return_value=existing),
            patch.object(frappe, "get_all", return_value=["In Progress"]),
            patch.object(frappe.db, "set_value"),
            patch.object(frappe.db, "commit"),
            patch("batch_projects.cache.invalidate_project"),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_workflow("PROJ-A", _states({"name": "To Do", "category": "unstarted"}))

    def test_removing_an_unused_state_is_allowed(self):
        existing = _states({"name": "To Do", "category": "unstarted"}, {"name": "Unused", "category": "started"})
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", side_effect=_get_value_returning(existing)),
            patch.object(frappe, "get_all", return_value=["To Do"]),
            patch.object(frappe.db, "set_value") as set_value,
            patch.object(frappe.db, "commit"),
            patch("batch_projects.cache.invalidate_project"),
        ):
            board.update_project_workflow("PROJ-A", _states({"name": "To Do", "category": "unstarted"}))
        set_value.assert_called_once()

    def test_duplicate_state_names_are_rejected(self):
        with (
            patch.object(board, "_check_permission"),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_workflow(
                "PROJ-A",
                _states({"name": "To Do", "category": "unstarted"}, {"name": "To Do", "category": "started"}),
            )

    def test_changing_category_of_an_in_use_state_is_rejected(self):
        existing = _states({"name": "In Progress", "category": "started"})
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", return_value=existing),
            patch.object(frappe, "get_all", return_value=["In Progress"]),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_workflow("PROJ-A", _states({"name": "In Progress", "category": "completed"}))

    def test_changing_category_of_an_unused_state_is_allowed(self):
        existing = _states({"name": "In Progress", "category": "started"})
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", side_effect=_get_value_returning(existing)),
            patch.object(frappe, "get_all", return_value=[]),
            patch.object(frappe.db, "set_value") as set_value,
            patch.object(frappe.db, "commit"),
            patch("batch_projects.cache.invalidate_project"),
        ):
            board.update_project_workflow("PROJ-A", _states({"name": "In Progress", "category": "completed"}))
        set_value.assert_called_once()


class TestTaskTypeInvariants(FrappeTestCase):
    def test_removing_an_in_use_task_type_is_rejected(self):
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", return_value=json.dumps([{"name": "Bug"}, {"name": "Task"}])),
            patch.object(frappe, "get_all", return_value=["Bug"]),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_issue_types("PROJ-A", json.dumps([{"name": "Task"}]))

    def test_duplicate_task_type_names_are_rejected(self):
        with (
            patch.object(board, "_check_permission"),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_issue_types("PROJ-A", json.dumps([{"name": "Bug"}, {"name": "Bug"}]))


def _label_catalog(*rows):
    """Real BP Project.labels shape — a list of {id, label, color} objects,
    NOT plain strings (BP Task.labels stores plain label-name strings; the
    two are different shapes — see _normalize_project_labels)."""
    return json.dumps(list(rows))


class TestLabelInvariants(FrappeTestCase):
    """Uses the real {id, label, color} catalog shape throughout — the
    original version of these tests used plain strings (['urgent',
    'backend']), which is not the production schema and let a real bug
    (comparing str({id,label,color}) against task label names, which can
    never match) pass while the actual behavior stayed broken."""

    def test_deleting_an_in_use_label_is_rejected(self):
        existing = _label_catalog(
            {"id": "lbl_urgent", "label": "urgent", "color": "#ef4444"},
            {"id": "lbl_backend", "label": "backend", "color": "#3b82f6"},
        )
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", return_value=existing),
            patch.object(frappe, "get_all", return_value=[{"name": "T-1", "labels": json.dumps(["urgent"])}]),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_labels(
                "PROJ-A",
                _label_catalog({"id": "lbl_backend", "label": "backend", "color": "#3b82f6"}),
            )

    def test_renaming_an_in_use_id_is_rejected(self):
        existing = _label_catalog({"id": "lbl_urgent", "label": "urgent", "color": "#ef4444"})
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", return_value=existing),
            patch.object(frappe, "get_all", return_value=[{"name": "T-1", "labels": json.dumps(["urgent"])}]),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_labels(
                "PROJ-A",
                _label_catalog({"id": "lbl_urgent", "label": "urgent-renamed", "color": "#ef4444"}),
            )

    def test_color_only_edit_with_same_id_and_name_succeeds(self):
        existing = _label_catalog({"id": "lbl_urgent", "label": "urgent", "color": "#ef4444"})
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", side_effect=_get_value_returning(existing)),
            patch.object(frappe, "get_all", return_value=[{"name": "T-1", "labels": json.dumps(["urgent"])}]),
            patch.object(frappe.db, "set_value") as set_value,
            patch.object(frappe.db, "commit"),
        ):
            result = board.update_project_labels(
                "PROJ-A",
                _label_catalog({"id": "lbl_urgent", "label": "urgent", "color": "#00FF00"}),
            )
        set_value.assert_called_once()
        self.assertEqual(result[0]["color"], "#00FF00")

    def test_deleting_an_unused_label_succeeds(self):
        existing = _label_catalog(
            {"id": "lbl_urgent", "label": "urgent", "color": "#ef4444"},
            {"id": "lbl_unused", "label": "unused", "color": "#000000"},
        )
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", side_effect=_get_value_returning(existing)),
            patch.object(frappe, "get_all", return_value=[{"name": "T-1", "labels": json.dumps(["urgent"])}]),
            patch.object(frappe.db, "set_value") as set_value,
            patch.object(frappe.db, "commit"),
        ):
            board.update_project_labels(
                "PROJ-A",
                _label_catalog({"id": "lbl_urgent", "label": "urgent", "color": "#ef4444"}),
            )
        set_value.assert_called_once()

    def test_duplicate_label_names_are_rejected(self):
        with (
            patch.object(board, "_check_permission"),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_labels(
                "PROJ-A",
                _label_catalog(
                    {"id": "lbl_1", "label": "urgent", "color": "#111111"},
                    {"id": "lbl_2", "label": "urgent", "color": "#222222"},
                ),
            )

    def test_duplicate_label_ids_are_rejected(self):
        with (
            patch.object(board, "_check_permission"),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_labels(
                "PROJ-A",
                _label_catalog(
                    {"id": "lbl_same", "label": "urgent", "color": "#111111"},
                    {"id": "lbl_same", "label": "backend", "color": "#222222"},
                ),
            )

    def test_legacy_no_id_in_use_label_cannot_disappear(self):
        """Catalog rows saved before label IDs existed are name-addressed —
        losing the name (delete or rename) while in use is still blocked."""
        existing = _label_catalog({"label": "legacy-label", "color": "#999999"})
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", return_value=existing),
            patch.object(frappe, "get_all", return_value=[{"name": "T-1", "labels": json.dumps(["legacy-label"])}]),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_labels("PROJ-A", _label_catalog())

    def test_malformed_current_catalog_fails_closed(self):
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", return_value=json.dumps(["not", "objects"])),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_labels(
                "PROJ-A",
                _label_catalog({"id": "lbl_1", "label": "urgent", "color": "#111111"}),
            )

    def test_malformed_task_label_json_fails_closed(self):
        existing = _label_catalog({"id": "lbl_urgent", "label": "urgent", "color": "#ef4444"})
        with (
            patch.object(board, "_check_permission"),
            patch.object(frappe.db, "get_value", return_value=existing),
            patch.object(frappe, "get_all", return_value=[{"name": "T-1", "labels": "{not valid json"}]),
            self.assertRaises(frappe.ValidationError),
        ):
            board.update_project_labels(
                "PROJ-A",
                _label_catalog({"id": "lbl_urgent", "label": "urgent", "color": "#ef4444"}),
            )


if __name__ == "__main__":
    import unittest
    unittest.main()
