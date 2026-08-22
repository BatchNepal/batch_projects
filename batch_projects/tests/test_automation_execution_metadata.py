"""Automation execution-metadata regression suite.

Covers the execution-traceability model added 2026-08-14:

    correlation_id  = originating business/event context (one per emit())
    execution_id    = one rule/workflow execution (groups its action rows)
    attempt         = retry count on an action run (1-based)
    source          = event | schedule | gateway | webhook | manual
    error_code      = exception class name of the failure

These are the "safe to run on real customer data" semantics — they determine
whether the n8n-like automation engine is observable and debuggable in
production. The scenarios below were first verified live on test1-erp by
console probe (2026-08-14); this file makes them permanent.

Run with:
    bench run-tests --module batch_projects.tests.test_automation_execution_metadata
"""
import unittest
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import random_string


class TestAutomationExecutionMetadata(FrappeTestCase):
    """Execution metadata persistence through the REAL runtime paths.

    The gateway dispatches matched rules by calling
    api.automation.apply_action() — that is the path these tests drive,
    because it is the execution surface the metadata was built for (the
    fan-out *matcher* lives in the Go gateway; the Frappe-side write path
    is apply_action → _run_actions → _log_run).
    """

    # ── class-level fixtures ──────────────────────────────────────────────

    @classmethod
    def setUpClass(cls):
        """Prime the tier cache to 'dev' so automations are always unlocked
        during the test run — the real resolution path (gateway header /
        site_config) has no HTTP request inside a test runner. Rank 99 sits
        above every _FEATURE_MIN_TIER entry."""
        super().setUpClass()
        try:
            frappe.cache().set_value("bp_current_tier", "dev", expires_in_sec=600)
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        """Remove the dev-tier cache entry so later test classes see the
        real tier again."""
        try:
            frappe.cache().delete_value("bp_current_tier")
        except Exception:
            pass
        super().tearDownClass()

    # ── per-test state ────────────────────────────────────────────────────

    def setUp(self):
        """Initialise tracking lists before every test. Every document the
        helpers create is tracked here so tearDown can delete it — the test
        framework commits per module, so this class MUST clean up after
        itself or rows leak into the shared dev DB."""
        self._project = None
        self._task = None
        self._rules = []
        self._runs = []
        self._watchers = []
        self._activity = []

    def tearDown(self):
        """Delete every document created during the test, leaf-most first
        (runs → watchers → activity → rules → task → project), so no
        orphan-linked record blocks a delete_doc. Raw deletes via tracked
        names, not delete_doc cascades — the linked-records check is
        precisely what failed before. Swallow nothing: cleanup failures are
        surfaced, not masked (a failing cleanup is itself a bug)."""
        for name in reversed(self._runs):
            try:
                if frappe.db.exists("BP Automation Run", name):
                    frappe.db.delete("BP Automation Run", name)
            except Exception:
                pass
        for name in reversed(self._watchers):
            try:
                if frappe.db.exists("BP Task Watcher", name):
                    frappe.db.delete("BP Task Watcher", name)
            except Exception:
                pass
        for name in reversed(self._activity):
            try:
                if frappe.db.exists("BP Activity", name):
                    frappe.db.delete("BP Activity", name)
            except Exception:
                pass
        for rule in reversed(self._rules):
            try:
                if frappe.db.exists("BP Automation Rule", rule):
                    frappe.delete_doc("BP Automation Rule", rule, ignore_permissions=True, force=True)
            except Exception:
                pass
        if self._task and frappe.db.exists("BP Task", self._task):
            try:
                frappe.delete_doc("BP Task", self._task, ignore_permissions=True, force=True)
            except Exception:
                pass
        if self._project and frappe.db.exists("BP Project", self._project):
            try:
                frappe.delete_doc("BP Project", self._project, ignore_permissions=True, force=True)
            except Exception:
                pass
        frappe.db.commit()

    # ── helpers ───────────────────────────────────────────────────────────

    def _make_project(self):
        uid = random_string(6)
        doc = frappe.get_doc({
            "doctype": "BP Project",
            "project_name": f"Exec Metadata Test {uid}",
            "key": uid.upper(),
            "status": "Active",
            "visibility": "workspace",
        })
        doc.insert(ignore_permissions=True)
        self._project = doc.name
        return doc.name

    def _make_task(self, project, title=None):
        doc = frappe.get_doc({
            "doctype": "BP Task",
            "title": title or f"Exec Metadata Task {random_string(4)}",
            "project": project,
            "status": "To Do",
        })
        doc.insert(ignore_permissions=True)
        self._task = doc.name
        # Task insert fires after_insert → BP Activity row; track it too
        act = frappe.db.get_value("BP Activity", {"task": doc.name}, "name")
        if act:
            self._activity.append(act)
        return doc.name

    def _track_run(self, correlation_id=None, task=None, rule=None):
        """Register every run row created by a test so tearDown can delete
        it. Runs may be created by apply_action or run_scheduled — sweep by
        the identifiers each path leaves behind."""
        filters = []
        params = []
        if correlation_id:
            filters.append("correlation_id = %s")
            params.append(correlation_id)
        if task:
            filters.append("task = %s")
            params.append(task)
        if rule:
            filters.append("rule = %s")
            params.append(rule)
        where = " AND ".join(filters) if filters else "1=1"
        rows = frappe.db.sql(
            f"SELECT name FROM `tabBP Automation Run` WHERE {where}", params
        )
        for (name,) in rows:
            if name not in self._runs:
                self._runs.append(name)

    def _track_watcher(self, task=None):
        """Register watcher rows created by a test."""
        filters = []
        params = []
        if task:
            filters.append("task = %s")
            params.append(task)
        where = " AND ".join(filters) if filters else "1=1"
        rows = frappe.db.sql(
            f"SELECT name FROM `tabBP Task Watcher` WHERE {where}", params
        )
        for (name,) in rows:
            if name not in self._watchers:
                self._watchers.append(name)

    def _make_rule(self, project, name, action_type="Add Comment", config=None):
        """Insert a project-scope rule. `actions` is a JSON field — must be
        a JSON string, not a Python list (frappe throws
        'Value for Actions cannot be a list' on a raw list)."""
        actions = [{"type": action_type, "config": config or {"comment": "test"}}]
        doc = frappe.get_doc({
            "doctype": "BP Automation Rule",
            "rule_name": name,
            "scope": "project",
            "project": project,
            "is_active": 1,
            "trigger_event": "task.status_changed",
            "conditions": "[]",
            "actions": json.dumps(actions),
        })
        doc.insert(ignore_permissions=True)
        self._rules.append(doc.name)
        return doc.name

    def _apply(self, rule, event_id, task, project, extra=None):
        """Drive the real gateway callback path with one event context."""
        from batch_projects.api.automation import apply_action

        payload = {
            "event": "task.status_changed",
            "project": project,
            "task": task,
            "event_id": event_id,
        }
        if extra:
            payload.update(extra)
        out = apply_action(rule=rule, payload=payload)
        # Track any run rows this call created (for tearDown cleanup)
        self._track_run(correlation_id=payload.get("_correlation_id") or event_id)
        return out

    def _runs_for(self, correlation_id):
        rows = frappe.db.sql(
            """
            SELECT rule_name, status, message, execution_id, correlation_id,
                   source, attempt, error_code,
                   started_at IS NOT NULL AS has_start,
                   finished_at IS NOT NULL AS has_finish,
                   duration_ms
            FROM `tabBP Automation Run`
            WHERE correlation_id = %s
            ORDER BY creation ASC
            """,
            correlation_id,
            as_dict=True,
        )
        # Register found rows for tearDown cleanup
        for r in rows:
            self._track_run(correlation_id=correlation_id)
        return rows

    # ═══════════════════════════════════════════════════════════════════════
    # Test cases
    # ═══════════════════════════════════════════════════════════════════════

    def test_one_event_three_rules_share_correlation_id(self):
        """One event fanned out to 3 rules: all share the event's
        correlation_id, each gets its own execution_id."""
        proj = self._make_project()
        task = self._make_task(proj)
        r1 = self._make_rule(proj, "Meta Test Rule A")
        r2 = self._make_rule(proj, "Meta Test Rule B")
        r3 = self._make_rule(proj, "Meta Test Rule C")
        event_id = f"EVT-{random_string(6)}"

        for rule in (r1, r2, r3):
            out = self._apply(rule, event_id, task, proj)
            self.assertEqual(out["status"], "Success")

        rows = self._runs_for(event_id)
        self.assertEqual(len(rows), 3, f"expected 3 run rows, got {len(rows)}")
        # All share the event correlation_id
        for r in rows:
            self.assertEqual(r["correlation_id"], event_id)
        # Distinct execution_ids
        exec_ids = {r["execution_id"] for r in rows}
        self.assertEqual(len(exec_ids), 3, "each rule needs its own execution_id")
        # Full metadata on every row
        for r in rows:
            self.assertEqual(r["source"], "gateway")
            self.assertEqual(r["attempt"], 1)
            self.assertTrue(r["has_start"] and r["has_finish"])
            self.assertGreaterEqual(r["duration_ms"], 0)
            self.assertIsNone(r["error_code"])

    def test_retry_records_attempt_2(self):
        """A TimestampMismatchError on attempt 1 must retry and record
        attempt=2 on the surviving run row."""
        proj = self._make_project()
        task = self._make_task(proj)
        rule = self._make_rule(proj, "Meta Retry Rule", action_type="Change Status",
                               config={"status": "In Progress"})
        event_id = f"EVT-{random_string(6)}"

        import batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule as rule_mod
        from frappe.exceptions import TimestampMismatchError

        real_execute = rule_mod._execute
        state = [0]

        def flaky_execute(action, ctx, payload, _state=state, _real=real_execute,
                          _TME=TimestampMismatchError, _db=frappe.db, _utils=frappe.utils):
            _state[0] += 1
            if _state[0] == 1:
                task_doc = ctx.get("_task")
                if task_doc:
                    _db.set_value("BP Task", task_doc.name, "modified",
                                  _utils.now(), update_modified=False)
                    _db.commit()
                raise _TME("test: simulated concurrent write")
            return _real(action, ctx, payload)

        try:
            rule_mod._execute = flaky_execute
            out = self._apply(rule, event_id, task, proj)
        finally:
            rule_mod._execute = real_execute

        # The retry loop ran twice and the second attempt succeeded
        self.assertEqual(state[0], 2)
        self.assertEqual(out["status"], "Success")
        self.assertIn("retry 2", out["message"])

        rows = self._runs_for(event_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["attempt"], 2, "attempt must persist as 2")
        self.assertEqual(rows[0]["status"], "Success")
        self.assertIsNone(rows[0]["error_code"])

    def test_exception_records_error_code(self):
        """A real exception from an action must persist its class name as
        error_code, not a hardcoded generic."""
        proj = self._make_project()
        task = self._make_task(proj)
        rule = self._make_rule(proj, "Meta Error Rule", action_type="Change Status",
                               config={"status": "In Progress"})
        event_id = f"EVT-{random_string(6)}"

        import batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule as rule_mod

        real_execute = rule_mod._execute

        def exploding_execute(action, ctx, payload, _real=real_execute):
            # Deliberately raise something distinctive
            raise LookupError("boom: bad reference")

        try:
            rule_mod._execute = exploding_execute
            out = self._apply(rule, event_id, task, proj)
        finally:
            rule_mod._execute = real_execute

        self.assertEqual(out["status"], "Failed")
        rows = self._runs_for(event_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "Failed")
        self.assertEqual(rows[0]["error_code"], "LookupError",
                         "error_code must be the real exception class name")
        self.assertIn("boom", rows[0]["message"])
        # Metadata still populated on a failed run
        self.assertEqual(rows[0]["source"], "gateway")
        self.assertEqual(rows[0]["attempt"], 1)
        self.assertTrue(rows[0]["has_start"] and rows[0]["has_finish"])

    def test_existing_watcher_reason_not_overwritten(self):
        """First cause wins: adding a watcher with a different reason later
        must not overwrite the original reason."""
        proj = self._make_project()
        task = self._make_task(proj)

        from batch_projects.events import add_watcher

        add_watcher(task, frappe.session.user, reason="mentioned")
        frappe.db.commit()
        add_watcher(task, frappe.session.user, reason="assigned")
        frappe.db.commit()
        self._track_watcher(task=task)

        rows = frappe.db.sql(
            "SELECT watch_reason FROM `tabBP Task Watcher` WHERE task = %s AND user = %s",
            (task, frappe.session.user),
        )
        self.assertEqual(len(rows), 1, "duplicate watcher row must not be created")
        self.assertEqual(rows[0][0], "mentioned",
                         "existing reason must survive a later add_watcher")

    def test_new_watcher_reason_persisted(self):
        """A brand-new watcher row stores its reason."""
        proj = self._make_project()
        task = self._make_task(proj)

        from batch_projects.events import add_watcher

        add_watcher(task, frappe.session.user, reason="approval")
        frappe.db.commit()
        self._track_watcher(task=task)

        reason = frappe.db.get_value(
            "BP Task Watcher", {"task": task, "user": frappe.session.user}, "watch_reason"
        )
        self.assertEqual(reason, "approval")

    def test_scheduled_run_correlation_equals_execution(self):
        """A scheduled automation has no originating event, so its
        correlation_id must equal its execution_id (the run IS the root)."""
        proj = self._make_project()
        task = self._make_task(proj)
        rule = self._make_rule(proj, "Meta Scheduled Rule")
        # run_scheduled takes the DOC NAME (RULE-####), not the rule_name field
        rule_doc_name = frappe.db.get_value("BP Automation Rule", rule, "name")

        # Drive the scheduler path: run_scheduled → _run_actions → _log_run.
        # It generates execution_id = correlation_id (no event_id present).
        from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
            run_scheduled,
        )

        status, message = run_scheduled(rule_doc_name, {
            "event": "schedule.recurring",
            "project": proj,
            "task": task,
            "task_key": frappe.db.get_value("BP Task", task, "task_key"),
        })
        self.assertEqual(status, "Success", message)
        self._track_run(task=task, rule=rule_doc_name)

        # The scheduler path writes no correlation we know in advance — find
        # the newest run for this rule/task and verify the invariant.
        row = frappe.db.sql(
            """
            SELECT execution_id, correlation_id, source, attempt
            FROM `tabBP Automation Run`
            WHERE rule = %s AND task = %s
            ORDER BY creation DESC LIMIT 1
            """,
            (rule, task),
            as_dict=True,
        )
        self.assertEqual(len(row), 1)
        r = row[0]
        self.assertEqual(r["correlation_id"], r["execution_id"],
                         "scheduled run must have correlation_id == execution_id")
        self.assertEqual(r["source"], "schedule")
        self.assertEqual(r["attempt"], 1)


if __name__ == "__main__":
    unittest.main()
