# Copyright (c) 2026, BatchNepal and contributors
# Regression coverage for dashboard_security.py / dashboard_task_reads.py.
# No dedicated test file existed for either module on the source branch —
# written fresh here rather than shipping 585 lines of ERP-dashboard
# authorization logic untested.
# Run: bench --site <site> run-tests --app batch_projects

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import dashboard_security, dashboard_task_reads, hooks


class TestDashboardSecurityWiring(FrappeTestCase):
    def test_all_seven_routes_are_overridden(self):
        overrides = hooks.override_whitelisted_methods
        expected = {
            "batch_projects.api.dashboards.get_column_widget_data":
                "batch_projects.dashboard_task_reads.get_column_widget_data",
            "batch_projects.api.dashboards.get_widget_source_fields":
                "batch_projects.dashboard_security.get_widget_source_fields",
            "batch_projects.api.dashboards.get_widget_source_field_options":
                "batch_projects.dashboard_security.get_widget_source_field_options",
            "batch_projects.api.dashboards.get_multi_source_count":
                "batch_projects.dashboard_security.get_multi_source_count",
            "batch_projects.api.dashboards.get_doctype_group_data":
                "batch_projects.dashboard_security.get_doctype_group_data",
            "batch_projects.api.dashboards.get_doctype_column_data":
                "batch_projects.dashboard_security.get_doctype_column_data",
            "batch_projects.api.dashboards.update_widget_source_field":
                "batch_projects.dashboard_security.update_widget_source_field",
            "batch_projects.api.dashboards.get_widget_source_doc_quickview":
                "batch_projects.dashboard_security.get_widget_source_doc_quickview",
        }
        for source, target in expected.items():
            self.assertEqual(overrides.get(source), target)


class TestAssertFilterFields(FrappeTestCase):
    def test_unpermitted_filter_field_rejected(self):
        with patch.object(
            dashboard_security, "_field_rows",
            return_value=[{"fieldname": "status"}],
        ):
            with self.assertRaises(frappe.PermissionError):
                dashboard_security._assert_filter_fields(
                    "Sales Invoice", [{"fieldname": "grand_total"}]
                )

    def test_bp_task_assignee_filter_always_allowed(self):
        with patch.object(dashboard_security, "_field_rows", return_value=[]):
            # Must not raise even though "assignee" isn't in the field-row list.
            dashboard_security._assert_filter_fields(
                "BP Task", [{"fieldname": "assignee"}]
            )

    def test_permitted_filter_field_allowed(self):
        with patch.object(
            dashboard_security, "_field_rows",
            return_value=[{"fieldname": "status"}],
        ):
            dashboard_security._assert_filter_fields(
                "Sales Invoice", [{"fieldname": "status"}]
            )


class TestWidgetSourceFields(FrappeTestCase):
    @patch.object(dashboard_security, "_guard")
    @patch.object(dashboard_security, "_entry", return_value={})
    def test_bp_task_strips_internal_and_money_fields(self, entry, guard):
        d = MagicMock()
        d._readable_field_rows.return_value = [
            {"fieldname": "title", "fieldtype": "Data"},
            {"fieldname": "sequence_no", "fieldtype": "Int"},
            {"fieldname": "billable", "fieldtype": "Check"},
        ]
        d._synthetic_fields.return_value = []
        with (
            patch.object(dashboard_security, "_dashboard_module", return_value=d),
            patch.object(dashboard_security.frappe, "get_meta", return_value=MagicMock(image_field=None)),
        ):
            rows = dashboard_security.get_widget_source_fields("BP Task")
        names = {row["fieldname"] for row in rows}
        self.assertEqual(names, {"title"})


class TestWidgetSourceFieldOptions(FrappeTestCase):
    @patch.object(dashboard_security, "_guard")
    @patch.object(dashboard_security, "_entry", return_value={})
    def test_non_select_or_link_field_rejected(self, entry, guard):
        with patch.object(
            dashboard_security, "_field_rows",
            return_value=[{"fieldname": "grand_total", "fieldtype": "Currency"}],
        ):
            with self.assertRaises(frappe.PermissionError):
                dashboard_security.get_widget_source_field_options(
                    "Sales Invoice", "grand_total"
                )

    @patch.object(dashboard_security, "_guard")
    @patch.object(dashboard_security, "_entry", return_value={})
    def test_link_field_without_target_read_permission_returns_empty(self, entry, guard):
        with (
            patch.object(
                dashboard_security, "_field_rows",
                return_value=[{"fieldname": "customer", "fieldtype": "Link", "options": "Customer"}],
            ),
            patch.object(dashboard_security.frappe, "has_permission", return_value=False),
        ):
            result = dashboard_security.get_widget_source_field_options(
                "Sales Invoice", "customer"
            )
        self.assertEqual(result, [])


class TestDoctypeGroupData(FrappeTestCase):
    @patch.object(dashboard_security, "_guard")
    def test_bp_task_must_use_dedicated_endpoint(self, guard):
        with self.assertRaises(frappe.ValidationError):
            dashboard_security.get_doctype_group_data("BP Task", "status")

    @patch.object(dashboard_security, "_guard")
    @patch.object(dashboard_security, "_entry", return_value={})
    def test_ungroupable_field_type_rejected(self, entry, guard):
        with patch.object(
            dashboard_security, "_field_rows",
            return_value=[{"fieldname": "grand_total", "fieldtype": "Currency"}],
        ):
            with self.assertRaises(frappe.PermissionError):
                dashboard_security.get_doctype_group_data("Sales Invoice", "grand_total")


class TestUpdateWidgetSourceField(FrappeTestCase):
    @patch.object(dashboard_security, "_guard")
    def test_bp_task_rejected(self, guard):
        with self.assertRaises(frappe.ValidationError):
            dashboard_security.update_widget_source_field("BP Task", "T-1", "status", "Done")

    @patch.object(dashboard_security, "_guard")
    @patch.object(dashboard_security, "_entry", return_value={})
    def test_unpermitted_write_field_rejected(self, entry, guard):
        with patch.object(dashboard_security, "_permitted_names", return_value=set()):
            with self.assertRaises(frappe.PermissionError):
                dashboard_security.update_widget_source_field(
                    "Sales Invoice", "SINV-1", "grand_total", 500
                )

    @patch.object(dashboard_security, "_guard")
    @patch.object(dashboard_security, "_entry", return_value={})
    def test_no_document_level_write_permission_rejected(self, entry, guard):
        with (
            patch.object(dashboard_security, "_permitted_names", return_value={"status"}),
            patch.object(dashboard_security.frappe, "has_permission", return_value=False),
        ):
            with self.assertRaises(frappe.PermissionError):
                dashboard_security.update_widget_source_field(
                    "Sales Invoice", "SINV-1", "status", "Closed"
                )

    @patch.object(dashboard_security, "_guard")
    @patch.object(dashboard_security, "_entry", return_value={})
    def test_submitted_document_rejected(self, entry, guard):
        doc = MagicMock()
        doc.get.side_effect = lambda k: {"docstatus": 1}.get(k)
        with (
            patch.object(dashboard_security, "_permitted_names", return_value={"status"}),
            patch.object(dashboard_security.frappe, "has_permission", return_value=True),
            patch.object(dashboard_security.frappe, "get_doc", return_value=doc),
        ):
            with self.assertRaises(frappe.ValidationError):
                dashboard_security.update_widget_source_field(
                    "Sales Invoice", "SINV-1", "status", "Closed"
                )


class TestWidgetSourceDocQuickview(FrappeTestCase):
    @patch.object(dashboard_security, "_guard")
    @patch.object(dashboard_security, "_entry", return_value={})
    def test_no_read_permission_raises_does_not_exist_not_permission_denied(self, entry, guard):
        # Deliberately DoesNotExistError, not PermissionError — avoids an
        # existence oracle (same pattern used in notification_reads.py).
        with patch.object(dashboard_security.frappe, "has_permission", return_value=False):
            with self.assertRaises(frappe.DoesNotExistError):
                dashboard_security.get_widget_source_doc_quickview("Sales Invoice", "SINV-1")


class TestMultiSourceCount(FrappeTestCase):
    @patch.object(dashboard_security, "_guard")
    @patch.object(dashboard_security, "_entry", return_value={"label": "Tasks"})
    @patch.object(dashboard_security, "_filters", return_value=[])
    def test_bp_task_source_applies_scope_and_trash_filter(self, filters, entry, guard):
        d = MagicMock()
        d._parse_json.return_value = [{"doctype": "BP Task"}]
        d._resolve_scope.return_value = ({"project": "PROJ-1"}, "PROJ-1", None)
        with (
            patch.object(dashboard_security, "_dashboard_module", return_value=d),
            patch("batch_projects.dashboard_task_reads.assert_dashboard_task_fields"),
            patch.object(dashboard_security.frappe.db, "count", return_value=3) as count,
        ):
            result = dashboard_security.get_multi_source_count(
                '[{"doctype": "BP Task"}]', scope="all"
            )
        self.assertEqual(result["total"], 3)
        called_filters = count.call_args.kwargs["filters"]
        self.assertIn(["is_deleted", "=", 0], called_filters)


class TestFieldAllowed(FrappeTestCase):
    def test_internal_field_always_denied(self):
        self.assertFalse(dashboard_task_reads._field_allowed("bridge_job_id", ["PROJ-1"]))

    def test_assignee_always_allowed(self):
        self.assertTrue(dashboard_task_reads._field_allowed("assignee", []))

    def test_money_field_requires_view_money_on_every_scoped_project(self):
        with patch(
            "batch_projects.access.has_capability",
            side_effect=lambda project, cap: project == "PROJ-1",
        ):
            self.assertFalse(
                dashboard_task_reads._field_allowed("billable", ["PROJ-1", "PROJ-2"])
            )
            self.assertTrue(
                dashboard_task_reads._field_allowed("billable", ["PROJ-1"])
            )

    def test_ordinary_field_allowed(self):
        self.assertTrue(dashboard_task_reads._field_allowed("title", ["PROJ-1"]))


class TestAssertDashboardTaskFields(FrappeTestCase):
    def test_denied_field_in_filters_rejected(self):
        with patch.object(dashboard_task_reads, "_scope_projects", return_value=["PROJ-1"]):
            with self.assertRaises(frappe.PermissionError):
                dashboard_task_reads.assert_dashboard_task_fields(
                    filters=[{"fieldname": "bridge_job_id"}]
                )

    def test_denied_field_in_group_by_rejected(self):
        with patch.object(dashboard_task_reads, "_scope_projects", return_value=["PROJ-1"]):
            with self.assertRaises(frappe.PermissionError):
                dashboard_task_reads.assert_dashboard_task_fields(group_by="bridge_job_id")

    def test_permitted_fields_pass(self):
        with patch.object(dashboard_task_reads, "_scope_projects", return_value=["PROJ-1"]):
            dashboard_task_reads.assert_dashboard_task_fields(
                filters=[{"fieldname": "status"}], extra_fields=["title"]
            )


class TestColumnWidgetDataVisibilityFilter(FrappeTestCase):
    def test_invisible_task_is_dropped_from_result(self):
        base_result = {
            "buckets": [{"key": "today", "tasks": [
                {"name": "TASK-VISIBLE", "billable": 1},
                {"name": "TASK-HIDDEN", "billable": 1},
            ]}],
            "total": 2,
        }
        with (
            patch.object(dashboard_task_reads, "assert_dashboard_task_fields"),
            patch("batch_projects.api.dashboards.get_column_widget_data", return_value=base_result),
            patch.object(
                dashboard_task_reads.frappe, "get_all",
                side_effect=[
                    ["TASK-VISIBLE", "TASK-HIDDEN"],  # live-task filter
                    [
                        frappe._dict(name="TASK-VISIBLE", project="PROJ-1"),
                        frappe._dict(name="TASK-HIDDEN", project="PROJ-1"),
                    ],
                ],
            ),
            patch(
                "batch_projects.task_invariants._user_can_view_task",
                side_effect=lambda project, task, user: task == "TASK-VISIBLE",
            ),
        ):
            result = dashboard_task_reads.get_column_widget_data()
        names = {row["name"] for b in result["buckets"] for row in b["tasks"]}
        self.assertEqual(names, {"TASK-VISIBLE"})
        self.assertEqual(result["total"], 1)


class TestMultiSourceCountDelegation(FrappeTestCase):
    def test_delegates_to_authoritative_dashboard_security_version(self):
        with patch(
            "batch_projects.dashboard_security.get_multi_source_count",
            return_value={"total": 5},
        ) as secure:
            result = dashboard_task_reads.get_multi_source_count("[]", scope="all")
        secure.assert_called_once_with("[]", scope="all")
        self.assertEqual(result["total"], 5)
