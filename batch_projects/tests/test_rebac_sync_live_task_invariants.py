"""Regression coverage for sync_rebac_state's live-task filtering.

Recovered gap (BatchProjects git-audit, P0 #2): a full ReBAC rebuild dumped
every BP Task / BP Task Assignee row unfiltered, so a rebuild could recreate
OpenFGA tuples for soft-deleted tasks and their assignees — access a trash
action already revoked.

Run with:
    bench run-tests --module batch_projects.tests.test_rebac_sync_live_task_invariants
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.api import board


class TestRebacSyncLiveTaskFiltering(FrappeTestCase):
    def test_tasks_resource_excludes_soft_deleted_tasks(self):
        with (
            patch("batch_projects.api.board._assert_service_caller"),
            patch.object(frappe, "get_all", return_value=[]) as get_all,
        ):
            board.sync_rebac_state("tasks")

        self.assertEqual(get_all.call_args.args[0], "BP Task")
        self.assertEqual(get_all.call_args.kwargs["filters"], {"is_deleted": 0})

    def test_task_assignees_resource_joins_against_live_tasks_only(self):
        with (
            patch("batch_projects.api.board._assert_service_caller"),
            patch.object(frappe.db, "sql", return_value=[]) as sql,
        ):
            board.sync_rebac_state("task_assignees", offset=10, limit=50)

        query = sql.call_args.args[0]
        params = sql.call_args.args[1]
        self.assertIn("tabBP Task Assignee", query)
        self.assertIn("t.is_deleted = 0", query)
        self.assertEqual(params, {"limit": 50, "offset": 10})

    def test_projects_resource_is_unaffected(self):
        """Only tasks/task_assignees gained the live-task filter — projects
        and project_members keep their prior, unfiltered behavior."""
        with (
            patch("batch_projects.api.board._assert_service_caller"),
            patch.object(frappe, "get_all", return_value=[]) as get_all,
        ):
            board.sync_rebac_state("projects")

        self.assertEqual(get_all.call_args.args[0], "BP Project")
        self.assertNotIn("filters", get_all.call_args.kwargs)


if __name__ == "__main__":
    import unittest
    unittest.main()
