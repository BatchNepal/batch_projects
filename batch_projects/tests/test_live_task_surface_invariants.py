"""Regression coverage for live-task-only read and sprint surfaces."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import task_aggregates
from batch_projects import task_surfaces


class TestLiveTaskRoutes(FrappeTestCase):
    def test_legacy_task_surfaces_are_overridden(self):
        overrides = hooks.override_whitelisted_methods
        expected = {
            "batch_projects.api.board.get_milestone_report":
                "batch_projects.task_aggregates.get_milestone_report",
            "batch_projects.api.board.get_sprint_capacity":
                "batch_projects.task_aggregates.get_sprint_capacity",
            "batch_projects.api.board.get_reports":
                "batch_projects.task_aggregates.get_reports",
            "batch_projects.api.board.complete_sprint":
                "batch_projects.task_surfaces.complete_sprint",
            "batch_projects.api.board.get_project_files":
                "batch_projects.task_surfaces.get_project_files",
            "batch_projects.api.board.get_automation_options":
                "batch_projects.automation_surface.get_automation_options",
            "batch_projects.api.dashboards.get_column_widget_data":
                "batch_projects.dashboard_task_reads.get_column_widget_data",
            "batch_projects.api.dashboards.get_multi_source_count":
                "batch_projects.dashboard_task_reads.get_multi_source_count",
        }
        for source, target in expected.items():
            self.assertEqual(overrides.get(source), target)


class TestAggregateFilters(FrappeTestCase):
    @patch.object(task_aggregates.frappe, "get_all", return_value=[])
    @patch.object(task_aggregates.frappe, "get_doc")
    @patch.object(task_aggregates, "_check")
    def test_milestone_report_reads_only_live_tasks(self, check, get_doc, get_all):
        milestone = SimpleNamespace(
            project="PROJ-1", title="M1", due_date=None, status="Open"
        )
        project = MagicMock()
        project.get_completed_statuses.return_value = ["Done"]
        project.project_name = "Project"
        project.hourly_rate = 0
        project.budget_amount = 0
        project.currency = "USD"
        get_doc.side_effect = [milestone, project]

        task_aggregates.get_milestone_report("MILESTONE-1")

        _, kwargs = get_all.call_args
        self.assertEqual(kwargs["filters"]["is_deleted"], 0)
        self.assertEqual(kwargs["filters"]["project"], "PROJ-1")

    @patch("batch_projects.api.board._get_member_capacities", return_value={})
    @patch.object(task_aggregates.frappe, "get_all", return_value=[])
    @patch.object(task_aggregates.frappe, "get_doc")
    @patch.object(task_aggregates, "_check")
    def test_sprint_capacity_reads_only_live_tasks(self, check, get_doc, get_all, capacities):
        get_doc.return_value = SimpleNamespace(project="PROJ-1", sprint_name="Sprint 1")

        task_aggregates.get_sprint_capacity("SPRINT-1")

        first_call = get_all.call_args_list[0]
        self.assertEqual(first_call.kwargs["filters"]["is_deleted"], 0)
        self.assertEqual(first_call.kwargs["filters"]["sprint"], "SPRINT-1")

    @patch.object(task_aggregates.frappe, "get_all", return_value=[])
    @patch.object(task_aggregates, "_resolve_report_projects", return_value=["PROJ-1"])
    @patch.object(task_aggregates.frappe, "get_cached_doc")
    def test_delivery_report_task_snapshot_is_live_only(self, get_project, resolve, get_all):
        project = MagicMock()
        project.get_workflow_states.return_value = [
            {"name": "Todo", "category": "unstarted"},
            {"name": "Done", "category": "completed"},
        ]
        project.get_completed_statuses.return_value = ["Done"]
        get_project.return_value = project

        task_aggregates.get_reports("PROJ-1")

        task_query = next(
            call for call in get_all.call_args_list
            if call.args and call.args[0] == "BP Task"
        )
        self.assertEqual(task_query.kwargs["filters"]["is_deleted"], 0)


class TestSprintAndFilesFilters(FrappeTestCase):
    @patch("batch_projects.api.board._invalidate_sprint_cache")
    @patch("batch_projects.api.board._get_completed_statuses_by_project", return_value=["Done"])
    @patch("batch_projects.api.board._check_permission")
    @patch.object(task_surfaces.frappe.db, "count", return_value=0)
    @patch.object(task_surfaces.frappe, "get_all", return_value=[])
    @patch.object(task_surfaces.frappe, "get_doc")
    @patch("batch_projects.events.emit")
    def test_complete_sprint_ignores_trash_in_move_and_count(
        self, emit, get_doc, get_all, count, check, completed, invalidate
    ):
        sprint = MagicMock()
        sprint.project = "PROJ-1"
        sprint.status = "Active"
        sprint.name = "SPRINT-1"
        sprint.sprint_name = "Sprint 1"
        sprint.as_dict.return_value = {"name": "SPRINT-1"}
        get_doc.return_value = sprint

        task_surfaces.complete_sprint("SPRINT-1")

        self.assertEqual(get_all.call_args.kwargs["filters"]["is_deleted"], 0)
        self.assertEqual(count.call_args.args[1]["is_deleted"], 0)

    @patch("batch_projects.api.board._check_permission")
    @patch("batch_projects.access.has_capability", return_value=True)
    @patch.object(task_surfaces.frappe.db, "sql", return_value=[])
    def test_project_files_sql_excludes_trashed_task_attachments(self, sql, capability, check):
        task_surfaces.get_project_files("PROJ-1")
        query = sql.call_args.args[0]
        self.assertIn("t.is_deleted = 0", query)

    @patch("batch_projects.api.board._check_permission")
    @patch("batch_projects.access.has_capability", return_value=False)
    @patch.object(task_surfaces.frappe.db, "sql")
    def test_project_files_respect_view_files_capability(self, sql, capability, check):
        self.assertEqual(task_surfaces.get_project_files("PROJ-1"), [])
        sql.assert_not_called()
