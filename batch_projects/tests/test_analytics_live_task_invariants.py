"""Regression coverage for analytics live-task filtering.

Recovered gap (BatchProjects git-audit, P2 #1): burndown, velocity, burnup,
cycle-time and sprint-health all queried BP Task with no is_deleted filter,
so a trashed task could still inflate/distort a project's metrics.

Run with:
    bench run-tests --module batch_projects.tests.test_analytics_live_task_invariants
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import analytics


def _task_call_filters(get_all_mock):
    for call in get_all_mock.call_args_list:
        args = call.args
        kwargs = call.kwargs
        doctype = args[0] if args else kwargs.get("doctype")
        if doctype == "BP Task":
            return kwargs.get("filters")
    return None


def _sprint_doc(**overrides):
    row = frappe._dict(
        name="SPRINT-1", sprint_name="Sprint 1", project="PROJ-A",
        start_date="2026-01-01", end_date="2026-01-03", status="Active", goal="",
    )
    row.update(overrides)
    return row


class TestBurndownAndBurnupExcludeDeletedTasks(FrappeTestCase):
    def test_burndown_query_excludes_deleted_tasks(self):
        with (
            patch.object(frappe, "get_doc", return_value=_sprint_doc()),
            patch.object(analytics, "_get_done_statuses", return_value=set()),
            patch.object(frappe, "get_all", return_value=[]) as get_all,
        ):
            analytics.compute_burndown("SPRINT-1")
        self.assertEqual(_task_call_filters(get_all).get("is_deleted"), 0)

    def test_burnup_query_excludes_deleted_tasks(self):
        with (
            patch.object(frappe, "get_doc", return_value=_sprint_doc()),
            patch.object(analytics, "_get_done_statuses", return_value=set()),
            patch.object(frappe, "get_all", return_value=[]) as get_all,
        ):
            analytics.compute_burnup("SPRINT-1")
        self.assertEqual(_task_call_filters(get_all).get("is_deleted"), 0)

    def test_sprint_health_status_counts_query_excludes_deleted_tasks(self):
        with (
            patch.object(frappe, "get_doc", return_value=_sprint_doc()),
            patch.object(analytics, "_get_done_statuses", return_value=set()),
            patch.object(frappe, "get_all", return_value=[]) as get_all,
            patch.object(analytics, "compute_velocity", return_value={}),
            patch.object(analytics, "compute_cycle_time", return_value={}),
        ):
            analytics.compute_sprint_health("SPRINT-1")
        self.assertEqual(_task_call_filters(get_all).get("is_deleted"), 0)


class TestVelocityAndCycleTimeExcludeDeletedTasks(FrappeTestCase):
    def test_velocity_query_excludes_deleted_tasks(self):
        with (
            patch.object(analytics, "_get_done_statuses", return_value=set()),
            patch.object(frappe, "get_all") as get_all,
        ):
            def side_effect(doctype, *a, **kw):
                if doctype == "BP Sprint":
                    return [frappe._dict(name="SPRINT-1", sprint_name="Sprint 1", start_date="2026-01-01", end_date="2026-01-03")]
                return []
            get_all.side_effect = side_effect
            analytics.compute_velocity("PROJ-A")
        self.assertEqual(_task_call_filters(get_all).get("is_deleted"), 0)

    def test_cycle_time_query_excludes_deleted_tasks(self):
        with patch.object(frappe, "get_all", return_value=[]) as get_all:
            analytics.compute_cycle_time("PROJ-A")
        self.assertEqual(_task_call_filters(get_all).get("is_deleted"), 0)


if __name__ == "__main__":
    import unittest
    unittest.main()
