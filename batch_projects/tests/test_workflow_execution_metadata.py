"""Regression coverage for the graph-workflow run callback contract."""

import frappe
import json
from frappe.tests.utils import FrappeTestCase


class TestWorkflowExecutionMetadata(FrappeTestCase):
    def setUp(self):
        self.workflow = None
        self.run = None

    def tearDown(self):
        if self.run:
            frappe.db.delete("BP Workflow Run", self.run)
        if self.workflow:
            frappe.db.delete("BP Workflow", self.workflow)
        frappe.db.commit()

    def test_graph_nodes_do_not_advertise_automatic_retry(self):
        from batch_projects.api.automation import get_node_registry

        registry = get_node_registry()
        self.assertFalse(registry["action.send_email"]["supports_retry"])
        self.assertTrue(registry["action.send_email"]["supports_failure_policy"])
        self.assertFalse(registry["integration.http_request"]["supports_retry"])
        self.assertTrue(registry["integration.http_request"]["supports_failure_policy"])

    def test_gateway_rfc3339_timestamps_are_normalized_for_mariadb(self):
        from batch_projects.api.automation import _workflow_run_datetime

        value = _workflow_run_datetime("2026-08-15T20:53:18.007191+00:00")
        self.assertIsNone(value.tzinfo)
        self.assertEqual(str(value), "2026-08-15 20:53:18.007191")

    def test_callback_persists_trace_context_and_attempt(self):
        workflow = frappe.get_doc({
            "doctype": "BP Workflow",
            "title": "Workflow execution metadata test",
            "scope": "workspace",
            "is_active": 1,
            "nodes": json.dumps([{
                "id": "trigger-1",
                "type": "trigger.task_event",
                "config": {"event": "task.created"},
            }]),
            "edges": "[]",
        }).insert(ignore_permissions=True)
        self.workflow = workflow.name

        from batch_projects.api.automation import log_workflow_run

        result = log_workflow_run(
            workflow=workflow.name,
            run_id="workflow-test-run-1",
            node_id="action-1",
            node_type="action.change_status",
            status="Failed",
            message="Task no longer exists",
            correlation_id="evt-workflow-test-1",
            source="webhook",
            attempt=2,
            started_at="2026-08-15 10:00:00",
            finished_at="2026-08-15 10:00:00.250000",
            error_code="DoesNotExistError",
        )
        self.assertEqual(result["status"], "logged")

        row = frappe.get_all(
            "BP Workflow Run",
            filters={"workflow": workflow.name, "run_id": "workflow-test-run-1"},
            fields=[
                "name", "correlation_id", "source", "attempt", "started_at",
                "finished_at", "duration_ms", "error_code",
            ],
            limit=1,
        )[0]
        self.run = row.name
        self.assertEqual(row.correlation_id, "evt-workflow-test-1")
        self.assertEqual(row.source, "webhook")
        self.assertEqual(row.attempt, 2)
        self.assertEqual(row.duration_ms, 250)
        self.assertEqual(row.error_code, "DoesNotExistError")
