# Copyright (c) 2026, BatchNepal and contributors
# Tests for task CRUD plus the milestone/risk lifecycle surfaced on
# ProjectSummary. Run: bench --site <site> run-tests --app batch_projects

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.api.board import (
    create_milestone,
    create_risk,
    create_task,
    delete_task,
    get_milestones,
    get_risks,
    get_task,
    update_milestone,
    update_risk,
    update_task,
    update_task_status,
)
from batch_projects.batch_projects.doctype.bp_project.test_bp_project import (
    delete_project_fixture,
    make_project,
)

TEST_KEY = "TBTSK"


class TestBPTask(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        delete_project_fixture(TEST_KEY)
        self.project = make_project(key=TEST_KEY)["name"]

    def tearDown(self):
        delete_project_fixture(TEST_KEY)

    def _task(self, title="Test task", **kwargs):
        return create_task(self.project, title, **kwargs)

    def test_create_task_defaults(self):
        task = self._task()
        self.assertEqual(task["project"], self.project)
        self.assertEqual(task["title"], "Test task")
        # First workflow state of the project is the default status
        self.assertEqual(task["status"], "To Do")
        self.assertTrue(task["task_key"].startswith(TEST_KEY))

    def test_task_keys_are_sequential(self):
        first = self._task("First")
        second = self._task("Second")
        n1 = int(first["task_key"].rsplit("-", 1)[1])
        n2 = int(second["task_key"].rsplit("-", 1)[1])
        self.assertEqual(n2, n1 + 1)

    def test_update_task_fields(self):
        task = self._task()
        update_task(task["name"], {"title": "Renamed", "priority": "High"})
        fetched = get_task(task["name"])
        self.assertEqual(fetched["title"], "Renamed")
        self.assertEqual(fetched["priority"], "High")

    def test_update_task_status(self):
        task = self._task()
        res = update_task_status(task["name"], "In Progress")
        self.assertFalse(res.get("blocked"))
        self.assertEqual(
            frappe.db.get_value("BP Task", task["name"], "status"),
            "In Progress",
        )

    def test_delete_task(self):
        task = self._task()
        delete_task(task["name"])
        self.assertFalse(frappe.db.exists("BP Task", task["name"]))

    # ── Milestones & risks (project-scoped, as shown on ProjectSummary) ──────

    def test_milestone_lifecycle(self):
        doc = create_milestone(self.project, "Beta launch", due_date="2026-12-01")
        self.assertEqual(doc["status"], "Open")

        rows = get_milestones(self.project)
        self.assertIn("Beta launch", [m["title"] for m in rows])

        update_milestone(doc["name"], {"status": "Completed"})
        self.assertEqual(
            frappe.db.get_value("BP Milestone", doc["name"], "status"),
            "Completed",
        )

    def test_risk_lifecycle(self):
        doc = create_risk(self.project, "Vendor delay", severity="high")
        self.assertEqual(doc["status"], "Open")

        rows = get_risks(self.project)
        self.assertIn("Vendor delay", [r["title"] for r in rows])

        # get_risks only returns open risks — mitigated ones must drop out
        update_risk(doc["name"], {"status": "Mitigated"})
        rows = get_risks(self.project)
        self.assertNotIn("Vendor delay", [r["title"] for r in rows])
