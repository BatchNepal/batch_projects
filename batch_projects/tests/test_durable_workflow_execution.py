"""Focused durable graph-execution regression coverage."""

import json
import threading

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string


class TestDurableWorkflowExecution(FrappeTestCase):
    def setUp(self):
        self.workflow = None
        self.executions = []

    def tearDown(self):
        for execution in self.executions:
            frappe.db.delete("BP Workflow Step", {"execution": execution})
            frappe.db.delete("BP Workflow Execution", execution)
        if self.workflow:
            frappe.db.delete("BP Workflow", self.workflow)
        frappe.db.commit()

    def _workflow(self):
        workflow = frappe.get_doc({
            "doctype": "BP Workflow", "title": f"Durable execution {random_string(6)}",
            "scope": "workspace", "is_active": 1,
            "nodes": json.dumps([{
                "id": "trigger", "type": "trigger.task_event",
                "config": {"event": "task.created"},
            }, {"id": "action", "type": "action.add_comment", "config": {"comment": "x"}}]),
            "edges": json.dumps([{"source": "trigger", "target": "action"}]),
        }).insert(ignore_permissions=True)
        self.workflow = workflow.name
        return workflow

    def _admit(self, event_id="evt-1"):
        from batch_projects.workflow_execution import admit
        workflow = frappe.get_doc("BP Workflow", self.workflow)
        out = admit(workflow.name, event_id, {
            "event": "task.created", "event_id": event_id, "source": "event",
        }, workflow.automation_revision, workflow.automation_definition_hash)
        if out["execution_id"] not in self.executions:
            self.executions.append(out["execution_id"])
        return out

    def test_duplicate_admission_and_step_creation_are_stable(self):
        self._workflow()
        first = self._admit()
        second = self._admit()
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["execution_id"], second["execution_id"])

        from batch_projects.workflow_execution import claim_lease, get_or_create_step
        lease = claim_lease(first["execution_id"], "gateway-r1", 60)
        self.assertTrue(lease["claimed"])
        step_one = get_or_create_step(first["execution_id"], "action", "frappe_atomic", "gateway-r1", lease["lease_generation"])
        step_two = get_or_create_step(first["execution_id"], "action", "frappe_atomic", "gateway-r1", lease["lease_generation"])
        self.assertTrue(step_one["created"])
        self.assertFalse(step_two["created"])
        self.assertEqual(step_one["step_id"], step_two["step_id"])

    def test_generation_fences_stale_step_writer(self):
        self._workflow()
        execution = self._admit()
        from batch_projects.workflow_execution import claim_lease, finish_step, get_or_create_step
        lease = claim_lease(execution["execution_id"], "gateway-r1", 60)
        step = get_or_create_step(execution["execution_id"], "action", "frappe_atomic", "gateway-r1", lease["lease_generation"])
        with self.assertRaises(frappe.ValidationError):
            finish_step(execution["execution_id"], step["step_id"], "gateway-r1", lease["lease_generation"] - 1, "succeeded", {})

    def test_lease_renewal_requires_current_generation(self):
        self._workflow()
        execution = self._admit()
        from batch_projects.workflow_execution import claim_lease, renew_lease
        lease = claim_lease(execution["execution_id"], "gateway-r1", 60)
        renewed = renew_lease(execution["execution_id"], "gateway-r1", lease["lease_generation"], 60)
        self.assertTrue(renewed["renewed"])
        stale = renew_lease(execution["execution_id"], "gateway-r1", lease["lease_generation"] - 1, 60)
        self.assertFalse(stale["renewed"])

    def test_local_success_is_reused_after_a_lost_response(self):
        self._workflow()
        execution = self._admit()
        from batch_projects.workflow_execution import claim_lease, finish_step, get_or_create_step
        lease = claim_lease(execution["execution_id"], "gateway-r1", 60)
        step = get_or_create_step(execution["execution_id"], "action", "frappe_atomic", "gateway-r1", lease["lease_generation"])
        finish_step(execution["execution_id"], step["step_id"], "gateway-r1", lease["lease_generation"], "succeeded", {"status": "Success", "json": {"message": "done"}})
        replay = get_or_create_step(execution["execution_id"], "action", "frappe_atomic", "gateway-r1", lease["lease_generation"])
        self.assertEqual(replay["status"], "succeeded")
        self.assertEqual(replay["result"]["json"]["message"], "done")

    def test_node_step_has_no_execution_or_lease_dependency(self):
        """get_or_create_node_step/finish_node_step back run_workflow_node's
        idempotency, which has no BP Workflow Execution of its own — Runtime
        V2 owns execution/lease state on the gateway side. Unlike
        get_or_create_step, there must be no _require_live_lease call here:
        this must work with no admit()/claim_lease() ever having run."""
        workflow = self._workflow()
        from batch_projects.workflow_execution import get_or_create_node_step, finish_node_step
        step_one = get_or_create_node_step("bpn_test_key_1", workflow.name, "action")
        step_two = get_or_create_node_step("bpn_test_key_1", workflow.name, "action")
        self.assertTrue(step_one["created"])
        self.assertFalse(step_two["created"])
        self.assertEqual(step_one["step_id"], step_two["step_id"])
        self.assertEqual(step_one["status"], "claimed")

        finish_node_step(step_one["step_id"], "succeeded", {"status": "Success", "json": {"message": "done"}})
        replay = get_or_create_node_step("bpn_test_key_1", workflow.name, "action")
        self.assertEqual(replay["status"], "succeeded")
        self.assertEqual(replay["result"]["json"]["message"], "done")

        frappe.db.delete("BP Workflow Step", step_one["step_id"])

    def test_node_step_key_is_scoped_per_key_not_per_node(self):
        """A different gateway-generated key (a distinct execution/node/run
        attempt) must be a genuinely separate ledger row, even for the same
        workflow/node — this is what lets two real, distinct dispatches of
        the same node (not a retry of one) both actually run."""
        workflow = self._workflow()
        from batch_projects.workflow_execution import get_or_create_node_step
        first = get_or_create_node_step("bpn_test_key_a", workflow.name, "action")
        second = get_or_create_node_step("bpn_test_key_b", workflow.name, "action")
        self.assertTrue(first["created"])
        self.assertTrue(second["created"])
        self.assertNotEqual(first["step_id"], second["step_id"])
        frappe.db.delete("BP Workflow Step", first["step_id"])
        frappe.db.delete("BP Workflow Step", second["step_id"])

    def test_concurrent_duplicate_admission_has_one_execution(self):
        workflow = self._workflow()
        frappe.db.commit()
        site = frappe.local.site
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def admit_once():
            try:
                frappe.init(site=site)
                frappe.connect()
                from batch_projects.workflow_execution import admit
                barrier.wait(timeout=5)
                out = admit(workflow.name, "evt-concurrent", {
                    "event": "task.created", "event_id": "evt-concurrent",
                }, workflow.automation_revision, workflow.automation_definition_hash)
                frappe.db.commit()
                results.append(out)
            except Exception as exc:
                errors.append(exc)
            finally:
                frappe.destroy()

        threads = [threading.Thread(target=admit_once), threading.Thread(target=admit_once)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(errors)
        self.assertEqual(len(results), 2)
        self.assertEqual(len({row["execution_id"] for row in results}), 1)
        self.assertEqual(sum(1 for row in results if row["created"]), 1)
        self.executions.append(results[0]["execution_id"])

    def test_concurrent_duplicate_node_step_creation_has_one_step(self):
        """The run_workflow_node idempotency path's own version of
        test_concurrent_duplicate_step_creation_has_one_step — two genuinely
        concurrent connections (real threads, real separate DB connections,
        a barrier so both race the same INSERT), not two sequential calls in
        one thread. This is what two actual overlapping gateway retries of
        the same node attempt look like."""
        workflow = self._workflow()
        frappe.db.commit()
        site = frappe.local.site
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def create_node_step_once():
            try:
                frappe.init(site=site)
                frappe.connect()
                from batch_projects.workflow_execution import get_or_create_node_step
                barrier.wait(timeout=5)
                result = get_or_create_node_step("bpn_concurrent_key", workflow.name, "action")
                frappe.db.commit()
                results.append(result)
            except Exception as exc:
                errors.append(exc)
            finally:
                frappe.destroy()

        threads = [threading.Thread(target=create_node_step_once) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors)
        self.assertEqual(len(results), 2)
        self.assertEqual(len({row["step_id"] for row in results}), 1)
        self.assertEqual(sum(1 for row in results if row["created"]), 1)
        frappe.db.delete("BP Workflow Step", results[0]["step_id"])

    def test_concurrent_duplicate_step_creation_has_one_step(self):
        self._workflow()
        execution = self._admit("evt-concurrent-step")
        from batch_projects.workflow_execution import claim_lease
        lease = claim_lease(execution["execution_id"], "gateway-r1", 60)
        frappe.db.commit()

        site = frappe.local.site
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def create_step_once():
            try:
                frappe.init(site=site)
                frappe.connect()
                from batch_projects.workflow_execution import get_or_create_step
                barrier.wait(timeout=5)
                result = get_or_create_step(
                    execution["execution_id"], "action", "frappe_atomic",
                    "gateway-r1", lease["lease_generation"],
                )
                frappe.db.commit()
                results.append(result)
            except Exception as exc:
                errors.append(exc)
            finally:
                frappe.destroy()

        threads = [threading.Thread(target=create_step_once) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors)
        self.assertEqual(len(results), 2)
        self.assertEqual(len({row["step_id"] for row in results}), 1)
        self.assertEqual(sum(1 for row in results if row["created"]), 1)

    def test_external_dispatch_is_one_way_to_review_after_uncertainty(self):
        self._workflow()
        execution = self._admit()
        from batch_projects.workflow_execution import begin_external_step, claim_lease, finish_step
        lease = claim_lease(execution["execution_id"], "gateway-r1", 60)
        started = begin_external_step(execution["execution_id"], "action", "gateway-r1", lease["lease_generation"])
        self.assertEqual(started["status"], "dispatching")
        self.assertTrue(started["dispatch_confirmed"])
        resumed = begin_external_step(execution["execution_id"], "action", "gateway-r1", lease["lease_generation"])
        self.assertFalse(resumed["dispatch_confirmed"])
        finished = finish_step(execution["execution_id"], started["step_id"], "gateway-r1", lease["lease_generation"], "needs_review", error_code="transport_lost")
        self.assertEqual(finished["status"], "needs_review")

    def test_definition_change_blocks_recovery(self):
        workflow = self._workflow()
        execution = self._admit()
        workflow.nodes = json.dumps([{
            "id": "trigger", "type": "trigger.task_event", "config": {"event": "task.created"},
        }])
        workflow.edges = "[]"
        workflow.save(ignore_permissions=True)
        from batch_projects.workflow_execution import recoverable_executions
        self.assertEqual(recoverable_executions(), [])
        self.assertEqual(frappe.db.get_value("BP Workflow Execution", execution["execution_id"], "status"), "needs_review")
