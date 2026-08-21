"""Regression contracts for enterprise authorization boundaries.

These tests deliberately target helpers below the SPA endpoints: route-specific
checks are not sufficient when REST, imports, automation and ORM writes can all
reach the same documents.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import custom_field_security
from batch_projects import hooks
from batch_projects import task_field_security
from batch_projects import task_reads
from batch_projects import workflow_security


class TestPermissionSecurityRouting(FrappeTestCase):
    def test_custom_field_security_routes_are_authoritative(self):
        overrides = hooks.override_whitelisted_methods
        self.assertEqual(
            overrides["batch_projects.api.custom_fields.create_field"],
            "batch_projects.custom_field_security.create_field",
        )
        self.assertEqual(
            overrides["batch_projects.api.custom_fields.update_field"],
            "batch_projects.custom_field_security.update_field",
        )
        self.assertEqual(
            overrides["batch_projects.api.custom_fields.search_field_link_options"],
            "batch_projects.custom_field_security.search_field_link_options",
        )

    def test_workflow_security_routes_are_authoritative(self):
        overrides = hooks.override_whitelisted_methods
        self.assertEqual(
            overrides["batch_projects.api.workflows.list_workflows"],
            "batch_projects.workflow_security.list_workflows",
        )
        self.assertEqual(
            overrides["batch_projects.api.workflows.test_workflow"],
            "batch_projects.workflow_security.test_workflow",
        )


class TestCustomFieldPolicy(FrappeTestCase):
    def test_edit_role_cannot_be_lower_than_view_role(self):
        with self.assertRaises(frappe.ValidationError):
            custom_field_security._validate_role_order("Manager", "Member")

    def test_edit_role_may_equal_or_exceed_view_role(self):
        custom_field_security._validate_role_order("Viewer", "Member")
        custom_field_security._validate_role_order("Manager", "Manager")

    @patch("batch_projects.task_field_security.access.has_at_least")
    @patch.object(task_field_security.frappe.db, "get_value")
    def test_hidden_custom_field_cannot_be_written(self, get_value, has_at_least):
        get_value.return_value = frappe._dict(
            field_label="Secret",
            view_role="Manager",
            edit_role="Member",
            field_type="text",
            options_json="{}",
        )
        # Caller meets legacy edit role but not view role.
        has_at_least.side_effect = [False]
        with self.assertRaises(frappe.PermissionError):
            task_field_security._custom_field_policy("PROJ", "CF-SECRET")

    @patch.object(task_field_security.frappe, "has_permission", return_value=False)
    def test_link_value_requires_real_erp_document_read(self, has_permission):
        row = frappe._dict(
            field_label="Invoice",
            field_type="link",
            options_json='{"link_doctype":"Sales Invoice"}',
        )
        with self.assertRaises(frappe.PermissionError):
            task_field_security._validate_link_target_readability(
                "PROJ", "CF-INVOICE", {"name": "SINV-0001"}, row=row
            )
        has_permission.assert_called_once()
        self.assertEqual(has_permission.call_args.args[:2], ("Sales Invoice", "read"))


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
    @patch("batch_projects.task_reads.access.has_at_least", create=True)
    def test_custom_field_output_is_allowlist_not_denylist(self, has_role, attached):
        # Patch import-time target through batch_projects.access instead; helper
        # imports it locally, so the create=True alias here is not relied on.
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


class TestWorkflowScopeSecurity(FrappeTestCase):
    @patch("batch_projects.api.board._check_permission")
    @patch.object(workflow_security, "_guard")
    @patch.object(workflow_security.frappe, "get_all")
    def test_project_list_uses_two_exact_queries_not_unsafe_or_filters(
        self, get_all, guard, check_permission
    ):
        get_all.side_effect = [
            [frappe._dict(name="WF-P", modified="2026-08-21 01:00:00")],
            [frappe._dict(name="WF-W", modified="2026-08-21 02:00:00")],
        ]
        rows = workflow_security.list_workflows("PROJ-A")
        self.assertEqual({row.name for row in rows}, {"WF-P", "WF-W"})
        first = get_all.call_args_list[0].kwargs
        second = get_all.call_args_list[1].kwargs
        self.assertEqual(
            first["filters"],
            {"is_active": 1, "scope": "project", "project": "PROJ-A"},
        )
        self.assertEqual(second["filters"], {"is_active": 1, "scope": "workspace"})
        self.assertNotIn("or_filters", first)
        self.assertNotIn("or_filters", second)

    @patch("batch_projects.api.workflows._require_workflow_admin")
    @patch.object(workflow_security, "_guard")
    @patch.object(workflow_security.frappe, "get_doc")
    @patch.object(workflow_security.frappe.db, "exists", return_value=True)
    @patch.object(workflow_security.frappe.db, "get_value")
    def test_project_workflow_rejects_task_from_other_project(
        self, get_value, exists, get_doc, guard, require_admin
    ):
        get_doc.return_value = frappe._dict(
            name="WF-1", scope="project", project="PROJ-A"
        )
        get_value.return_value = frappe._dict(
            name="TASK-1", project="PROJ-B", is_deleted=0
        )
        with self.assertRaises(frappe.PermissionError):
            workflow_security.test_workflow("WF-1", task="TASK-1")


if __name__ == "__main__":
    import unittest
    unittest.main()
