"""Regression contracts for task field-write authority and read minimization.

Split out of a larger cross-cutting file (test_enterprise_permission_invariants.py
on the source branch) — that file also covered custom_field_security.py and
workflow_security.py, which belong to separate PRs. This file keeps only the
task_field_security.py / task_reads.py coverage relevant here.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import task_field_security
from batch_projects import task_reads


class TestTaskOnlyFieldAuthority(FrappeTestCase):
    @staticmethod
    def _doc(**values):
        return frappe._dict(values)

    @patch("batch_projects.task_field_security.access.is_task_assignee", return_value=True)
    @patch("batch_projects.task_field_security.access.get_effective_role", return_value=None)
    @patch("batch_projects.task_field_security.access.is_instance_admin", return_value=False)
    def test_task_only_assignee_cannot_change_planning_field(
        self, is_admin, effective_role, is_assignee
    ):
        old = self._doc(name="TASK-1", project="PROJ", sprint=None)
        doc = self._doc(name="TASK-1", project="PROJ", sprint="SPRINT-1")
        with self.assertRaises(frappe.PermissionError):
            task_field_security._validate_task_only_scope(
                doc, old, {"sprint"}
            )

    @patch("batch_projects.task_field_security.access.is_task_assignee", return_value=True)
    @patch("batch_projects.task_field_security.access.get_effective_role", return_value=None)
    @patch("batch_projects.task_field_security.access.is_instance_admin", return_value=False)
    def test_task_only_assignee_can_edit_core_content(
        self, is_admin, effective_role, is_assignee
    ):
        old = self._doc(name="TASK-1", project="PROJ", description="old")
        doc = self._doc(name="TASK-1", project="PROJ", description="new")
        task_field_security._validate_task_only_scope(doc, old, {"description"})

    @patch("batch_projects.task_field_security.access.is_task_assignee", return_value=True)
    @patch("batch_projects.task_field_security.access.get_effective_role", return_value=None)
    @patch("batch_projects.task_field_security.access.is_instance_admin", return_value=False)
    def test_status_controller_derived_fields_do_not_expand_task_only_denial(
        self, is_admin, effective_role, is_assignee
    ):
        old = self._doc(name="TASK-1", project="PROJ", status="Open")
        doc = self._doc(name="TASK-1", project="PROJ", status="Done")
        task_field_security._validate_task_only_scope(
            doc,
            old,
            {"status", "completed_on", "completed_by", "resolution"},
        )


class TestTaskReadMinimization(FrappeTestCase):
    @patch("batch_projects.api.custom_fields._attached_fields")
    def test_custom_field_output_is_allowlist_not_denylist(self, attached):
        # task_reads imports access locally inside the function, not at module
        # level, so the patch target is batch_projects.access itself.
        cf = frappe._dict(name="CF-VISIBLE", view_role="Viewer")
        attached.return_value = [(frappe._dict(), cf)]
        with patch("batch_projects.access.has_at_least", return_value=True):
            values = task_reads._visible_custom_values(
                "PROJ",
                {
                    "CF-VISIBLE": "ok",
                    "CF-DETACHED": "must disappear",
                    "_checklist": [{"text": "internal"}],
                },
            )
        self.assertEqual(values, {"CF-VISIBLE": "ok"})

    @patch("batch_projects.access.has_capability", return_value=False)
    def test_task_detail_strips_internal_and_money_fields(self, has_capability):
        data = {
            "project": "PROJ",
            "title": "Visible",
            "sequence_no": 99,
            "bridge_job_id": "secret-job",
            "billable": 1,
            "sales_order": "SO-1",
            "references": [],
            "custom_field_values": {},
        }
        with patch.object(task_reads, "_visible_custom_values", return_value={}):
            out = task_reads._sanitize_task_fields(data)
        self.assertNotIn("sequence_no", out)
        self.assertNotIn("bridge_job_id", out)
        self.assertNotIn("billable", out)
        self.assertNotIn("sales_order", out)
        self.assertEqual(out["title"], "Visible")

    @patch.object(task_reads.frappe, "has_permission", return_value=False)
    def test_erp_reference_requires_document_read(self, has_permission):
        self.assertFalse(
            task_reads._can_read_reference(
                {"ref_doctype": "Sales Invoice", "ref_name": "SINV-1"}
            )
        )


if __name__ == "__main__":
    import unittest
    unittest.main()
