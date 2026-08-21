"""Regression coverage for sprint analytics trash semantics."""

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from batch_projects import analytics_live
from batch_projects.api import sprint_analytics


class TestSprintAnalyticsRouting(FrappeTestCase):
    def test_api_imports_live_engine(self):
        self.assertIs(sprint_analytics.analytics, analytics_live)


class TestLiveAnalyticsQueries(FrappeTestCase):
    @patch.object(analytics_live.base, "_get_project_labels", return_value={
        "cycle_label": "Sprint", "effort_label": "Points", "effort_label_abbr": "pts"
    })
    @patch.object(analytics_live.frappe, "get_all", return_value=[])
    @patch.object(analytics_live.frappe, "get_doc")
    def test_burndown_task_query_excludes_trash(self, get_doc, get_all, labels):
        sprint = MagicMock()
        sprint.project = "PROJ-1"
        sprint.name = "SPRINT-1"
        sprint.sprint_name = "Sprint 1"
        sprint.start_date = "2026-08-01"
        sprint.end_date = "2026-08-07"
        sprint.status = "Active"
        get_doc.return_value = sprint

        analytics_live.compute_burndown("SPRINT-1")

        task_query = next(call for call in get_all.call_args_list if call.args[0] == "BP Task")
        self.assertEqual(task_query.kwargs["filters"]["is_deleted"], 0)

    @patch.object(analytics_live.base, "_get_done_statuses", return_value={"done"})
    @patch.object(analytics_live.base, "_get_project_labels", return_value={
        "cycle_label": "Sprint", "effort_label": "Points", "effort_label_abbr": "pts"
    })
    @patch.object(analytics_live.frappe, "get_all")
    def test_velocity_task_queries_exclude_trash(self, get_all, labels, done):
        sprint = MagicMock()
        sprint.name = "SPRINT-1"
        sprint.sprint_name = "Sprint 1"
        sprint.start_date = "2026-08-01"
        sprint.end_date = "2026-08-07"
        get_all.side_effect = [[sprint], []]

        analytics_live.compute_velocity("PROJ-1")

        task_query = get_all.call_args_list[1]
        self.assertEqual(task_query.kwargs["filters"]["is_deleted"], 0)

    @patch.object(analytics_live.base, "_get_project_labels", return_value={
        "cycle_label": "Sprint", "effort_label": "Points", "effort_label_abbr": "pts"
    })
    @patch.object(analytics_live.frappe, "get_all", return_value=[])
    def test_cycle_time_query_excludes_trash(self, get_all, labels):
        analytics_live.compute_cycle_time("PROJ-1", days=60)
        self.assertEqual(get_all.call_args.kwargs["filters"]["is_deleted"], 0)

    @patch.object(analytics_live, "compute_cycle_time", return_value={})
    @patch.object(analytics_live, "compute_velocity", return_value={})
    @patch.object(analytics_live, "compute_burnup", return_value={})
    @patch.object(analytics_live, "compute_burndown", return_value={})
    @patch.object(analytics_live.frappe, "get_all", return_value=[])
    @patch.object(analytics_live.frappe, "get_doc")
    def test_health_status_count_excludes_trash(
        self, get_doc, get_all, burndown, burnup, velocity, cycle
    ):
        sprint = MagicMock()
        sprint.name = "SPRINT-1"
        sprint.sprint_name = "Sprint 1"
        sprint.project = "PROJ-1"
        sprint.status = "Active"
        sprint.start_date = None
        sprint.end_date = None
        sprint.goal = ""
        get_doc.return_value = sprint

        analytics_live.compute_sprint_health("SPRINT-1")

        self.assertEqual(get_all.call_args.kwargs["filters"]["is_deleted"], 0)
