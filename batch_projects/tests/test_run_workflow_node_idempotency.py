"""Idempotency regression coverage for run_workflow_node.

bp-gateway's Runtime V2 retries a transient failure (or a lost-but-actually-
successful response) by calling run_workflow_node again with the SAME
gateway-generated idempotency_key. Notify/Email/Add Comment/Create Issue have
no natural dedup of their own (unlike Update ERPNext Document, which only
writes fields that differ), so without a ledger a retry repeats the side
effect. These tests drive the real whitelisted entry point end to end (real
BP Workflow/BP Task/BP Workflow Step rows, real _execute), not a mocked
workflow document, since the ledger's own frappe.get_doc/frappe.db calls need
a real DB underneath them.
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string


class TestRunWorkflowNodeIdempotency(FrappeTestCase):
    def setUp(self):
        self._project = None
        self._task = None
        self._workflow = None

    def tearDown(self):
        # Scoped by this test's own (randomly-named) workflow rather than a
        # list of tracked step names — a node_id like "n2" is reused across
        # every test in this file, so relying on "the one step I remembered
        # to track" leaked an orphaned row into the shared test1-erp database
        # the first time a test created more than one step for the same
        # node_id (a real bug this class hit and is a regression guard for).
        if self._workflow:
            frappe.db.delete("BP Workflow Step", {"workflow": self._workflow})
        if self._workflow and frappe.db.exists("BP Workflow", self._workflow):
            frappe.delete_doc("BP Workflow", self._workflow, ignore_permissions=True, force=True)
        if self._task and frappe.db.exists("BP Task", self._task):
            frappe.delete_doc("BP Task", self._task, ignore_permissions=True, force=True)
        if self._project and frappe.db.exists("BP Project", self._project):
            frappe.delete_doc("BP Project", self._project, ignore_permissions=True, force=True)
        frappe.db.commit()

    def _make_project(self):
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Project", "project_name": f"Idempotency Test {uid}",
            "key": uid.upper(), "status": "Active", "visibility": "workspace",
        }).insert(ignore_permissions=True)
        self._project = doc.name
        return doc.name

    def _make_task(self, project):
        doc = frappe.get_doc({
            "doctype": "BP Task", "title": f"Idempotency Task {random_string(4)}",
            "project": project, "status": "To Do",
        }).insert(ignore_permissions=True)
        self._task = doc.name
        return doc.name

    def _make_workflow(self, project):
        doc = frappe.get_doc({
            "doctype": "BP Workflow", "title": f"Idempotency Workflow {random_string(6)}",
            "scope": "project", "project": project, "is_active": 1,
            "nodes": json.dumps([
                {"id": "trigger", "type": "trigger.task_event", "config": {"event": "task.updated"}},
                {"id": "n2", "type": "action.add_comment", "config": {"comment": "hi from automation"}},
            ]),
            "edges": json.dumps([{"source": "trigger", "target": "n2"}]),
        }).insert(ignore_permissions=True)
        self._workflow = doc.name
        return doc.name

    def _comment_count(self, task):
        return frappe.db.count("BP Activity", {"task": task, "action_type": "Comment"})

    def test_same_idempotency_key_executes_the_side_effect_exactly_once(self):
        from batch_projects.api import automation

        project = self._make_project()
        task = self._make_task(project)
        workflow = self._make_workflow(project)

        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch("batch_projects.entitlements.is_feature_enabled", return_value=True),
        ):
            first = automation.run_workflow_node(
                workflow=workflow, node="n2", payload={"task": task},
                idempotency_key="bpn_test_dedup_key_1",
            )
            second = automation.run_workflow_node(
                workflow=workflow, node="n2", payload={"task": task},
                idempotency_key="bpn_test_dedup_key_1",
            )

        self.assertEqual(first["status"], "Success")
        self.assertEqual(first, second)
        self.assertEqual(self._comment_count(task), 1)

    def test_different_idempotency_key_is_a_genuinely_new_attempt(self):
        from batch_projects.api import automation

        project = self._make_project()
        task = self._make_task(project)
        workflow = self._make_workflow(project)

        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch("batch_projects.entitlements.is_feature_enabled", return_value=True),
        ):
            automation.run_workflow_node(
                workflow=workflow, node="n2", payload={"task": task},
                idempotency_key="bpn_test_dedup_key_a",
            )
            automation.run_workflow_node(
                workflow=workflow, node="n2", payload={"task": task},
                idempotency_key="bpn_test_dedup_key_b",
            )

        # Two distinct gateway attempts (e.g. two separate node runs, not a
        # retry of the same one) must not be silently collapsed into one.
        self.assertEqual(self._comment_count(task), 2)

    def test_failed_attempt_is_replayed_not_retried(self):
        from batch_projects.api import automation
        from batch_projects.batch_projects.doctype.bp_automation_rule import bp_automation_rule

        project = self._make_project()
        task = self._make_task(project)
        workflow = self._make_workflow(project)

        call_count = {"n": 0}

        def failing_execute(action, ctx, payload):
            call_count["n"] += 1
            raise RuntimeError("simulated action failure")

        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch("batch_projects.entitlements.is_feature_enabled", return_value=True),
            patch.object(bp_automation_rule, "_execute", side_effect=failing_execute),
        ):
            first = automation.run_workflow_node(
                workflow=workflow, node="n2", payload={"task": task},
                idempotency_key="bpn_test_dedup_key_fail",
            )
            second = automation.run_workflow_node(
                workflow=workflow, node="n2", payload={"task": task},
                idempotency_key="bpn_test_dedup_key_fail",
            )

        self.assertEqual(first["status"], "Failed")
        self.assertEqual(first, second)
        # The real action must only ever have been attempted once — the
        # second call replays the recorded failure instead of calling it again.
        self.assertEqual(call_count["n"], 1)
        self.assertEqual(self._comment_count(task), 0)

    def test_call_without_idempotency_key_is_unaffected(self):
        """Backward compatibility: a caller with no key (there should be
        none left, but the parameter is optional) still executes normally,
        with no ledger row created at all."""
        from batch_projects.api import automation

        project = self._make_project()
        task = self._make_task(project)
        workflow = self._make_workflow(project)

        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch("batch_projects.entitlements.is_feature_enabled", return_value=True),
        ):
            result = automation.run_workflow_node(workflow=workflow, node="n2", payload={"task": task})

        self.assertEqual(result["status"], "Success")
        self.assertEqual(self._comment_count(task), 1)
        self.assertEqual(
            frappe.db.count("BP Workflow Step", {"workflow": workflow, "node_id": "n2"}), 0,
        )
