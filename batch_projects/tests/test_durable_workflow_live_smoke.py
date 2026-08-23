"""Live, test1-only smoke coverage for the durable Gateway workflow contract.

This is intentionally run explicitly against the development Gateway.  It uses
the normal BP Task event hook and replay through ``events.emit``; it never
calls the durable coordinator APIs directly.

Because the assertions only pass when a real bp-gateway is reachable and
processing the event stream, this file is opt-in: it runs only when
``BP_LIVE_GATEWAY_SMOKE`` is set in the environment.  A generic full-suite
invocation (``bench run-tests --app batch_projects``, including the CI gate)
skips it, so the standard suite stays deterministic and self-contained.
"""

import json
import os
import time
import unittest
import uuid
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string


@unittest.skipUnless(
    os.environ.get("BP_LIVE_GATEWAY_SMOKE"),
    "requires a live bp-gateway; not run in standard CI. Set BP_LIVE_GATEWAY_SMOKE=1 to run.",
)
class TestDurableWorkflowLiveSmoke(FrappeTestCase):
    def _wait_for(self, predicate, message, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            frappe.db.commit()
            if predicate():
                return
            time.sleep(0.25)
        self.fail(message)

    def test_task_status_event_admits_once_and_replay_is_effect_free(self):
        suffix = random_string(8)
        marker = f"durable-smoke-{suffix}"
        event_id = str(uuid.uuid4())
        other_event_id = str(uuid.uuid4())

        project = frappe.get_doc({
            "doctype": "BP Project",
            "project_name": f"Durable workflow smoke {suffix}",
            "key": f"D{suffix[:5].upper()}",
            "status": "Active",
            "visibility": "workspace",
        }).insert(ignore_permissions=True)
        frappe.db.commit()

        workflow = frappe.get_doc({
            "doctype": "BP Workflow",
            "title": f"Durable workflow smoke {suffix}",
            "scope": "project",
            "project": project.name,
            "is_active": 1,
            "nodes": json.dumps([
                {
                    "id": "trigger",
                    "type": "trigger.task_event",
                    "config": {"event": "task.status_changed"},
                },
                {
                    "id": "comment",
                    "type": "action.add_comment",
                    "config": {"comment": marker},
                },
            ]),
            "edges": json.dumps([{"source": "trigger", "target": "comment"}]),
        }).insert(ignore_permissions=True)
        frappe.db.commit()

        task = frappe.get_doc({
            "doctype": "BP Task",
            "title": f"Durable workflow smoke task {suffix}",
            "project": project.name,
            "status": "To Do",
        }).insert(ignore_permissions=True)
        frappe.db.commit()

        # The status-change hook calls events.emit() itself.  Stabilize only
        # the generated IDs so this smoke can prove exact propagation; the
        # event still travels through bridge.publish_event -> Gateway Streams.
        with patch("batch_projects.events.uuid.uuid4", side_effect=[
            uuid.UUID(event_id), uuid.UUID(other_event_id),
        ]):
            task.status = "In Progress"
            task.save(ignore_permissions=True)
        frappe.db.commit()

        def execution_rows():
            return frappe.get_all(
                "BP Workflow Execution",
                filters={"workflow": workflow.name, "event_id": event_id},
                fields=["name", "event_id", "status", "started_at", "finished_at"],
            )

        self._wait_for(
            lambda: len(execution_rows()) == 1 and execution_rows()[0].status == "succeeded",
            "durable execution did not reach succeeded through the live Gateway path",
        )
        execution = execution_rows()[0]
        self.assertEqual(execution.event_id, event_id)
        self.assertTrue(execution.started_at)
        self.assertTrue(execution.finished_at)

        steps = frappe.get_all(
            "BP Workflow Step",
            filters={"execution": execution.name, "node_id": "comment"},
            fields=["name", "status", "effect_kind"],
        )
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].status, "succeeded")
        self.assertEqual(steps[0].effect_kind, "frappe_atomic")

        def run_rows():
            return frappe.get_all(
                "BP Workflow Run",
                filters={"execution": execution.name, "node_id": "comment"},
                fields=["name", "run_id", "execution", "correlation_id", "source", "status"],
            )

        self._wait_for(lambda: len(run_rows()) == 1, "workflow run observability row was not recorded")
        runs = run_rows()
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run.execution, execution.name)
        self.assertEqual(run.correlation_id, event_id)
        self.assertEqual(run.source, "event")
        self.assertEqual(run.status, "Success")
        self.assertTrue(run.run_id)
        self.assertNotEqual(run.run_id, execution.name)

        def comment_count():
            return frappe.db.count(
                "BP Activity",
                {"task": task.name, "action_type": "Comment", "comment_text": marker},
            )

        self._wait_for(lambda: comment_count() == 1, "local atomic comment was not created")

        # Simulate duplicate delivery at the publication boundary, preserving
        # the same event identity.  This deliberately does not invoke admit()
        # or any durable API directly.
        from batch_projects.events import TASK_STATUS_CHANGED, emit
        emit(TASK_STATUS_CHANGED, {
            "event_id": event_id,
            "project": project.name,
            "task": task.name,
            "task_key": task.task_key,
            "from_status": "To Do",
            "to_status": "In Progress",
        })
        frappe.db.commit()
        time.sleep(1)
        frappe.db.commit()

        self.assertEqual(len(execution_rows()), 1)
        self.assertEqual(comment_count(), 1)
        self.assertEqual(len(run_rows()), 1)
        self.assertEqual(
            frappe.db.count("BP Workflow Step", {"execution": execution.name, "node_id": "comment"}),
            1,
        )
