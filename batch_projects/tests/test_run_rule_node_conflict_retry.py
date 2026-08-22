"""Regression coverage for run_rule_node's conflict retry and the
get_or_create_node_step/finish_node_step ledger it shares with
run_workflow_node (see test_run_workflow_node_idempotency.py for that side).

Found live (2026-08-22): run_rule_node's conflict-retry loop called a plain
frappe.db.rollback() on TimestampMismatchError. That's safe in apply_action
(the legacy path this retry loop was copied from) only because nothing was
staged before its retry loop began. Here, get_or_create_node_step's 'claimed'
row is staged earlier in the SAME transaction — a plain rollback discarded it
too, so finish_node_step's later UPDATE matched zero rows, threw uncaught,
and Frappe's own request handler rolled back the ENTIRE transaction on the
way out — including the retry's by-then-successful mutation. The gateway
then recorded a PERMANENT failure (a well-formed non-2xx reply is never
retried) for an automation that had actually already happened.

The fix commits the 'claimed' row before the retry loop (durable, immune to
any later rollback) and uses a plain rollback inside it (not a savepoint —
MariaDB's REPEATABLE READ means a savepoint-scoped rollback never refreshes
the transaction's read snapshot, so every retry would keep re-reading the
same pre-race data and the retry could never actually recover; only a plain
rollback's begin() opens a fresh snapshot).
"""

import json
import threading
from unittest.mock import patch

import frappe
from frappe.exceptions import TimestampMismatchError
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string


class TestRunRuleNodeConflictRetry(FrappeTestCase):
    def setUp(self):
        self._project = None
        self._task = None
        self._rule = None

    def tearDown(self):
        if self._rule:
            frappe.db.delete("BP Workflow Step", {"node_id": f"rule:{self._rule}:action-1"})
        if self._rule and frappe.db.exists("BP Automation Rule", self._rule):
            frappe.delete_doc("BP Automation Rule", self._rule, ignore_permissions=True, force=True)
        if self._task and frappe.db.exists("BP Task", self._task):
            frappe.delete_doc("BP Task", self._task, ignore_permissions=True, force=True)
        if self._project and frappe.db.exists("BP Project", self._project):
            frappe.delete_doc("BP Project", self._project, ignore_permissions=True, force=True)
        frappe.db.commit()

    def _make_project(self):
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Project", "project_name": f"Retry Test {uid}",
            "key": uid.upper(), "status": "Active", "visibility": "workspace",
        }).insert(ignore_permissions=True)
        self._project = doc.name
        return doc.name

    def _make_task(self, project, status="To Do"):
        doc = frappe.get_doc({
            "doctype": "BP Task", "title": f"Retry Task {random_string(4)}",
            "project": project, "status": status, "priority": "Low",
        }).insert(ignore_permissions=True)
        self._task = doc.name
        return doc.name

    def _make_rule(self, project, actions=None):
        doc = frappe.get_doc({
            "doctype": "BP Automation Rule", "rule_name": f"Retry Rule {random_string(6)}",
            "scope": "project", "project": project,
            "trigger_event": "task.field_changed",
            "trigger_config": json.dumps({"field": "priority"}),
            "actions": json.dumps(actions or [{"type": "Change Status", "config": {"status": "Done"}}]),
            "is_active": 1,
        }).insert(ignore_permissions=True)
        self._rule = doc.name
        return doc

    def _comment_count(self, task):
        return frappe.db.count("BP Activity", {"task": task, "action_type": "Comment"})

    def _payload(self, project, task):
        return {
            "event": "task.updated", "project": project, "task": task, "task_key": task,
            "depth": 0, "changes": [{"field": "priority", "from": "Low", "to": "High"}],
        }

    def test_conflict_retry_recovers_without_losing_step_ledger_or_mutation(self):
        from batch_projects.api import automation
        from batch_projects.batch_projects.doctype.bp_automation_rule import bp_automation_rule

        project = self._make_project()
        task = self._make_task(project)
        rule = self._make_rule(project)

        real_execute = bp_automation_rule._execute
        call_count = {"n": 0}

        def flaky_execute(action, ctx, payload):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise TimestampMismatchError("simulated concurrent writer")
            return real_execute(action, ctx, payload)

        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch("batch_projects.entitlements.is_feature_enabled", return_value=True),
            patch.object(bp_automation_rule, "_execute", side_effect=flaky_execute),
        ):
            result = automation.run_rule_node(
                rule=rule.name, node="action-1", payload=self._payload(project, task),
                idempotency_key="bpn_test_conflict_retry_1",
                workflow_revision_id=f"rule:{rule.automation_revision}:{rule.automation_definition_hash}",
            )

        # The retry actually recovered — this is the whole point of the fix,
        # not just "failed cleanly instead of crashing".
        self.assertEqual(result["status"], "Success")
        self.assertEqual(call_count["n"], 2)
        self.assertEqual(frappe.db.get_value("BP Task", task, "status"), "Done")

        step = frappe.db.get_value(
            "BP Workflow Step", {"node_id": f"rule:{rule.name}:action-1"},
            ["status", "result_json"], as_dict=True,
        )
        self.assertIsNotNone(step, "step ledger row must survive the retry, not vanish with it")
        self.assertEqual(step.status, "succeeded")
        self.assertEqual(json.loads(step.result_json)["status"], "Success")

    def test_exhausted_retries_fail_cleanly_without_orphaning_the_step(self):
        """A race that never resolves within _CONFLICT_RETRIES must still end
        in a clean, correctly-logged failure — not a crash, and not a step
        stuck forever in 'claimed' (which would make every future redelivery
        of this exact idempotency_key re-execute the mutation)."""
        from batch_projects.api import automation
        from batch_projects.batch_projects.doctype.bp_automation_rule import bp_automation_rule

        project = self._make_project()
        task = self._make_task(project)
        rule = self._make_rule(project)

        def always_races(action, ctx, payload):
            raise TimestampMismatchError("simulated concurrent writer, never resolves")

        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch("batch_projects.entitlements.is_feature_enabled", return_value=True),
            patch.object(bp_automation_rule, "_execute", side_effect=always_races),
        ):
            result = automation.run_rule_node(
                rule=rule.name, node="action-1", payload=self._payload(project, task),
                idempotency_key="bpn_test_conflict_retry_exhausted",
                workflow_revision_id=f"rule:{rule.automation_revision}:{rule.automation_definition_hash}",
            )

        self.assertEqual(result["status"], "Failed")
        self.assertEqual(result["json"]["error_code"], "TimestampMismatchError")
        self.assertEqual(frappe.db.get_value("BP Task", task, "status"), "To Do")

        step = frappe.db.get_value(
            "BP Workflow Step", {"node_id": f"rule:{rule.name}:action-1"}, "status",
        )
        self.assertEqual(step, "failed")

    def test_finish_node_step_identical_redelivery_succeeds(self):
        from batch_projects.workflow_execution import finish_node_step, get_or_create_node_step

        step = get_or_create_node_step("bpn_test_redelivery_key", None, "rule:FAKE:action-1")
        result = {"status": "Success", "json": {"message": "Status -> Done"}}
        first = finish_node_step(step["step_id"], "succeeded", result=result)
        self.assertEqual(first["status"], "succeeded")

        # A redelivered finish for the exact same outcome — the caller's own
        # retry after a lost response — must succeed, not reject a
        # redelivery that was actually fine.
        second = finish_node_step(step["step_id"], "succeeded", result=result)
        self.assertEqual(second["status"], "succeeded")
        frappe.db.delete("BP Workflow Step", {"name": step["step_id"]})
        frappe.db.commit()

    def test_finish_node_step_conflicting_transition_is_rejected(self):
        from batch_projects.workflow_execution import finish_node_step, get_or_create_node_step

        step = get_or_create_node_step("bpn_test_conflict_key", None, "rule:FAKE:action-1")
        finish_node_step(step["step_id"], "succeeded", result={"status": "Success", "json": {}})

        # A second transition with a genuinely DIFFERENT outcome for the same
        # step must still be rejected — silently accepting it could mask a
        # real double-execution.
        with self.assertRaises(frappe.ValidationError):
            finish_node_step(step["step_id"], "failed", result={"status": "Failed", "json": {}})

        frappe.db.delete("BP Workflow Step", {"name": step["step_id"]})
        frappe.db.commit()

    def test_sequential_redelivery_of_nonidempotent_action_executes_once(self):
        """Change Status masks a double-execution (it self-skips once the
        task is already in the target state), so the primary regression test
        above can't prove the action itself only ran once — only that the
        NET result looked right. Add Comment has no such natural dedup: a
        real second call really would post a second comment. This is the
        run_rule_node-level counterpart to
        test_run_workflow_node_idempotency.py's same-key test."""
        from batch_projects.api import automation

        project = self._make_project()
        task = self._make_task(project)
        rule = self._make_rule(project, actions=[
            {"type": "Add Comment", "config": {"comment": "hi from automation"}},
        ])

        with (
            patch("batch_projects.api.automation._assert_service_caller"),
            patch("batch_projects.entitlements.is_feature_enabled", return_value=True),
        ):
            revision_id = f"rule:{rule.automation_revision}:{rule.automation_definition_hash}"
            first = automation.run_rule_node(
                rule=rule.name, node="action-1", payload=self._payload(project, task),
                idempotency_key="bpn_test_sequential_redelivery",
                workflow_revision_id=revision_id,
            )
            second = automation.run_rule_node(
                rule=rule.name, node="action-1", payload=self._payload(project, task),
                idempotency_key="bpn_test_sequential_redelivery",
                workflow_revision_id=revision_id,
            )

        self.assertEqual(first["status"], "Success")
        self.assertEqual(first, second)
        self.assertEqual(self._comment_count(task), 1)

    def test_concurrent_redelivery_executes_mutation_exactly_once(self):
        """Two genuinely concurrent run_rule_node calls (real threads, real
        separate DB connections, a barrier so both race) with the SAME
        idempotency_key — what two actual overlapping gateway retries of the
        same node attempt look like. Add Comment (not Change Status) so a
        real double-execution would be visible even if the second attempt
        happened to run after the mutation already looked "done" — this is
        the regression test for committing the 'claimed' row early: that
        commit releases the row-lock a second worker used to block on for
        the whole request, so only the advisory GET_LOCK below now prevents
        both workers from actually calling _execute at the same time."""
        project = self._make_project()
        task = self._make_task(project)
        rule = self._make_rule(project, actions=[
            {"type": "Add Comment", "config": {"comment": "hi from automation"}},
        ])
        frappe.db.commit()

        site = frappe.local.site
        payload = self._payload(project, task)
        idempotency_key = "bpn_test_concurrent_redelivery"
        revision_id = f"rule:{rule.automation_revision}:{rule.automation_definition_hash}"
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def call_once():
            try:
                frappe.init(site=site)
                frappe.connect()
                from batch_projects.api import automation
                with (
                    patch("batch_projects.api.automation._assert_service_caller"),
                    patch("batch_projects.entitlements.is_feature_enabled", return_value=True),
                ):
                    barrier.wait(timeout=5)
                    result = automation.run_rule_node(
                        rule=rule.name, node="action-1", payload=dict(payload),
                        idempotency_key=idempotency_key, workflow_revision_id=revision_id,
                    )
                frappe.db.commit()
                results.append(result)
            except Exception as exc:  # noqa: BLE001 — collected, not raised, cross-thread
                errors.append(exc)
            finally:
                frappe.destroy()

        threads = [threading.Thread(target=call_once) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors, f"unexpected exceptions in worker threads: {errors}")
        self.assertEqual(len(results), 2)
        # The real proof: the non-idempotent side effect happened exactly
        # once, not "the ledger has one row" (which Change Status could
        # satisfy even with two real executions, since the second would
        # harmlessly no-op on an already-correct value).
        self.assertEqual(self._comment_count(task), 1)
        steps = frappe.db.get_all(
            "BP Workflow Step",
            filters={"node_id": f"rule:{rule.name}:action-1"},
            fields=["status"],
        )
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].status, "succeeded")

    def test_concurrent_telemetry_write_creates_exactly_one_row(self):
        """_upsert_run_log's old get_value()-then-insert check was itself a
        TOCTOU race: two concurrent writers for the SAME (execution, node,
        attempt) can both see "not found" and both insert, duplicating a
        telemetry row ExecutionsView.vue/AutomationRules.vue then render
        twice for one real node run. telemetry_key's own DocType-level
        unique index makes the database the arbiter regardless of what two
        real threads actually observe."""
        from batch_projects.api import automation

        project = self._make_project()
        rule = self._make_rule(project)
        frappe.db.commit()

        site = frappe.local.site
        execution_id = "bpx_test_concurrent_telemetry"
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def write_once():
            try:
                frappe.init(site=site)
                frappe.connect()
                with patch("batch_projects.api.automation._assert_service_caller"):
                    barrier.wait(timeout=5)
                    result = automation.log_rule_run(
                        rule=rule.name, node="action-1", status="Success",
                        message="Status -> Done", execution_id=execution_id, attempt=1,
                    )
                frappe.db.commit()
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                frappe.destroy()

        threads = [threading.Thread(target=write_once) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors, f"unexpected exceptions in worker threads: {errors}")
        self.assertEqual(len(results), 2)
        rows = frappe.get_all(
            "BP Automation Run",
            filters={"execution_id": execution_id, "action_index": 0, "attempt": 1},
            fields=["name"],
        )
        self.assertEqual(len(rows), 1, f"expected exactly one telemetry row, got {rows}")
        frappe.db.delete("BP Automation Run", {"execution_id": execution_id})
        frappe.db.commit()

    def test_concurrent_out_of_order_report_never_regresses_status(self):
        """_update_last_run_if_newer's old read-then-write was the same
        class of race: two concurrent reports can both read the same
        "current" last_run_at, both decide they're newer, and whichever
        WRITES last wins regardless of whose `at` was actually newer. Fires
        the older-timestamped report and the newer one at the same instant
        (barrier-synchronized, real threads/connections) — the conditional
        UPDATE's WHERE clause must make the outcome depend on the timestamps
        themselves, not on scheduling luck."""
        from batch_projects.api import automation

        project = self._make_project()
        rule = self._make_rule(project)
        frappe.db.commit()

        site = frappe.local.site
        older_at = "2026-01-01 00:00:00"
        newer_at = "2026-01-02 00:00:00"
        errors = []
        barrier = threading.Barrier(2)

        def report_once(status, at):
            try:
                frappe.init(site=site)
                frappe.connect()
                with patch("batch_projects.api.automation._assert_service_caller"):
                    barrier.wait(timeout=5)
                    automation.report_rule_run(rule=rule.name, status=status, at=at)
                frappe.db.commit()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                frappe.destroy()

        threads = [
            threading.Thread(target=report_once, args=("Failed", older_at)),
            threading.Thread(target=report_once, args=("Success", newer_at)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors, f"unexpected exceptions in worker threads: {errors}")
        final = frappe.db.get_value(
            "BP Automation Rule", rule.name, ["last_run_status", "last_run_at"], as_dict=True,
        )
        # Regardless of which thread's UPDATE statement physically executed
        # last, the newer-timestamped report must be what's stored.
        self.assertEqual(final.last_run_status, "Success")
        self.assertEqual(str(final.last_run_at), newer_at)

    def test_lock_timeout_on_stuck_worker_is_retryable_not_permanent(self):
        """A caller that never releases the advisory lock (crashed, or a
        genuinely very slow action) must not make a concurrent redelivery's
        call permanently fail while the original worker goes on to succeed.
        frappe_mutation.go's client only classifies specific HTTP statuses as
        RetryTransient (408/409/429/5xx) — a well-formed 200 "Failed" body is
        ALWAYS RetryPermanent there regardless of error_code. This must
        surface as frappe.DuplicateEntryError (-> HTTP 409), not a plain
        Failed result, so the gateway actually retries it."""
        import hashlib

        from batch_projects.api import automation

        project = self._make_project()
        task = self._make_task(project)
        rule = self._make_rule(project)
        frappe.db.commit()

        idempotency_key = "bpn_test_lock_timeout"
        lock_name = "bp_rule_node:" + hashlib.sha256(idempotency_key.encode()).hexdigest()

        # Pre-claim the step exactly as run_rule_node itself would — the
        # test's "stuck worker" holds the advisory lock without ever
        # finishing it, so it stays 'claimed' for the whole test.
        from batch_projects.workflow_execution import get_or_create_node_step

        get_or_create_node_step(idempotency_key, None, f"rule:{rule.name}:action-1")
        frappe.db.commit()

        site = frappe.local.site
        lock_held = threading.Event()
        release_lock = threading.Event()

        def hold_lock():
            frappe.init(site=site)
            frappe.connect()
            try:
                frappe.db.sql("SELECT GET_LOCK(%s, 5)", (lock_name,))
                lock_held.set()
                release_lock.wait(timeout=10)
            finally:
                frappe.db.sql("SELECT RELEASE_LOCK(%s)", (lock_name,))
                frappe.destroy()

        holder = threading.Thread(target=hold_lock)
        holder.start()
        self.assertTrue(lock_held.wait(timeout=5), "holder thread never acquired the lock")

        try:
            with (
                patch("batch_projects.api.automation._assert_service_caller"),
                patch("batch_projects.entitlements.is_feature_enabled", return_value=True),
                patch("batch_projects.api.automation._RULE_NODE_LOCK_TIMEOUT_SECONDS", 1),
            ):
                with self.assertRaises(frappe.DuplicateEntryError):
                    automation.run_rule_node(
                        rule=rule.name, node="action-1", payload=self._payload(project, task),
                        idempotency_key=idempotency_key,
                        workflow_revision_id=f"rule:{rule.automation_revision}:{rule.automation_definition_hash}",
                    )
        finally:
            release_lock.set()
            holder.join(timeout=10)

        # The step must still be exactly where the (still-alive, just slow)
        # original worker left it — 'claimed' — not corrupted by the timed-
        # out caller into some other state.
        step_status = frappe.db.get_value(
            "BP Workflow Step", {"node_id": f"rule:{rule.name}:action-1"}, "status",
        )
        self.assertEqual(step_status, "claimed")
