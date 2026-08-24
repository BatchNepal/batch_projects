"""Regression coverage for comment edit/delete realtime events and the
task.trashed/task.restored automation trigger metadata.

Recovered gaps (BatchProjects git-audit, P2 #2-#4):
  - edit_comment only ever emitted COMMENT_ADDED, and only when the edit
    added a new @mention; a plain text edit (the common case) broadcast
    nothing at all. delete_comment emitted nothing, ever.
  - task.trashed/task.restored are real, already-emitted runtime events
    (task_lifecycle.py) that were never offered as selectable triggers in
    the automation builder's trigger.task_event node.

Corrections (per independent validation):
  - task.trashed/task.restored were added to the workflow-canvas node
    registry only. The product has a SECOND, older automation surface —
    board.get_automation_options()'s _AUTOMATION_TRIGGERS (consumed by
    AutomationRules.vue/AutomationRuleEditor.vue) and BP Automation Rule.
    trigger_event's own DocType Select options — neither of which
    included the two new values, so a rule using them could be built in
    the workflow canvas but not the rule-builder, and would be REJECTED
    outright by Frappe's own Select-field validation on save. Both are
    now covered; see TestTrashRestoreAutomationTriggerMetadata below.
  - emit(COMMENT_EDITED)/emit(COMMENT_DELETED) were called AFTER an
    explicit frappe.db.commit() — _broadcast registers its realtime
    publish on frappe.db.after_commit, so it must be called before the
    commit for "no event on rollback, event published once durable" to
    be the actual guarantee rather than coincidental. See
    TestCommentEventTransactionOrdering.

Run with:
    bench run-tests --module batch_projects.tests.test_comment_realtime_and_trash_trigger_recovery
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects.api import board


class TestCommentEditEmitsRealtimeEvent(FrappeTestCase):
    def _activity(self, comment_text="old text"):
        doc = MagicMock()
        doc.action_type = "Comment"
        doc.task = "TASK-1"
        doc.user = frappe.session.user  # current test-session user -> skips the manager-permission branch
        doc.name = "ACT-1"
        doc.comment_text = comment_text
        return doc

    def test_plain_text_edit_still_emits_comment_edited(self):
        """The gap: previously nothing broadcast at all unless the edit
        happened to add a new mention."""
        activity = self._activity()
        task = frappe._dict(project="PROJ-A", task_key="BP-1")
        with (
            patch.object(frappe, "get_doc", side_effect=[activity, task]),
            patch("batch_projects.api.board.emit") as emit,
            patch.object(frappe.db, "commit"),
        ):
            board.edit_comment("ACT-1", "new text, no mentions")

        events_emitted = [c.args[0] for c in emit.call_args_list]
        self.assertIn("comment.edited", events_emitted)
        # No new mention -> the mentions_only COMMENT_ADDED must NOT also fire.
        self.assertNotIn("comment.added", events_emitted)

    def test_edit_adding_a_mention_emits_both_events(self):
        activity = self._activity()
        task = frappe._dict(project="PROJ-A", task_key="BP-1")
        with (
            patch.object(frappe, "get_doc", side_effect=[activity, task]),
            patch("batch_projects.api.board.emit") as emit,
            patch.object(frappe.db, "commit"),
        ):
            board.edit_comment("ACT-1", "hey @[Bob](test35+info@batchnepal.com)")

        events_emitted = [c.args[0] for c in emit.call_args_list]
        self.assertIn("comment.edited", events_emitted)
        self.assertIn("comment.added", events_emitted)


class TestCommentDeleteEmitsRealtimeEvent(FrappeTestCase):
    def test_delete_emits_comment_deleted_with_the_activity_name(self):
        activity = MagicMock()
        activity.action_type = "Comment"
        activity.task = "TASK-1"
        activity.user = frappe.session.user
        activity.name = "ACT-1"
        task = frappe._dict(project="PROJ-A", task_key="BP-1")
        with (
            patch.object(frappe, "get_doc", side_effect=[activity, task]),
            patch("batch_projects.api.board.emit") as emit,
            patch.object(frappe, "delete_doc"),
            patch.object(frappe.db, "commit"),
        ):
            board.delete_comment("ACT-1")

        emit.assert_called_once()
        event_name, payload = emit.call_args.args
        self.assertEqual(event_name, "comment.deleted")
        self.assertEqual(payload["activity"], "ACT-1")
        self.assertEqual(payload["task"], "TASK-1")


class TestCommentEventTransactionOrdering(FrappeTestCase):
    """emit()'s realtime broadcast is registered via frappe.db.after_commit
    (events._broadcast, after_commit=True) — calling it AFTER an explicit
    commit defers the registration to whatever the NEXT commit happens to
    be, rather than "this mutation's own commit", breaking the intended
    "no event on rollback, event on durability" guarantee outside the
    lucky case where a request-teardown commit happens to save it."""

    def test_edit_comment_calls_emit_before_commit(self):
        activity = MagicMock()
        activity.action_type = "Comment"
        activity.task = "TASK-1"
        activity.user = frappe.session.user
        activity.name = "ACT-1"
        activity.comment_text = "old"
        task = frappe._dict(project="PROJ-A", task_key="BP-1")

        order = []
        with (
            patch.object(frappe, "get_doc", side_effect=[activity, task]),
            patch("batch_projects.api.board.emit", side_effect=lambda *a, **kw: order.append("emit")),
            patch.object(frappe.db, "commit", side_effect=lambda: order.append("commit")),
        ):
            board.edit_comment("ACT-1", "new text")

        self.assertEqual(order[0], "emit")
        self.assertEqual(order[-1], "commit")

    def test_delete_comment_calls_emit_before_commit(self):
        activity = MagicMock()
        activity.action_type = "Comment"
        activity.task = "TASK-1"
        activity.user = frappe.session.user
        activity.name = "ACT-1"
        task = frappe._dict(project="PROJ-A", task_key="BP-1")

        order = []
        with (
            patch.object(frappe, "get_doc", side_effect=[activity, task]),
            patch("batch_projects.api.board.emit", side_effect=lambda *a, **kw: order.append("emit")),
            patch.object(frappe, "delete_doc"),
            patch.object(frappe.db, "commit", side_effect=lambda: order.append("commit")),
        ):
            board.delete_comment("ACT-1")

        self.assertEqual(order, ["emit", "commit"])


class TestTrashRestoreAutomationTriggerMetadata(FrappeTestCase):
    def test_trashed_and_restored_are_selectable_task_event_triggers(self):
        from batch_projects.api.automation import _NODE_REGISTRY

        options = {
            o["value"]
            for o in _NODE_REGISTRY["trigger.task_event"]["config_schema"][0]["options"]
        }
        self.assertIn("task.trashed", options)
        self.assertIn("task.restored", options)

    def test_get_automation_options_returns_both_events(self):
        """The second, older rule-builder surface — board.get_automation_
        options()'s _AUTOMATION_TRIGGERS, consumed by AutomationRules.vue/
        AutomationRuleEditor.vue — is a DIFFERENT catalog from the workflow
        canvas's _NODE_REGISTRY above; the workflow canvas having both
        values does not mean the rule builder does."""
        result = board.get_automation_options()
        trigger_values = {t["value"] for t in result["triggers"]}
        self.assertIn("task.trashed", trigger_values)
        self.assertIn("task.restored", trigger_values)

    def test_trigger_event_doctype_select_options_include_both(self):
        """BP Automation Rule.trigger_event is a required Select field —
        Frappe rejects any value outside its own `options` list at save
        time, independent of whatever the frontend offers. Requires
        bench migrate to have synced this DocType JSON change."""
        options = frappe.get_meta("BP Automation Rule").get_field("trigger_event").options
        values = set(options.split("\n"))
        self.assertIn("task.trashed", values)
        self.assertIn("task.restored", values)


class TestTrashRestoreRuleDocumentPersistence(FrappeTestCase):
    """Real DB round-trip: this is the thing that was actually broken —
    Frappe's own Select-field validation rejected trigger_event=task.trashed
    outright before the DocType JSON was corrected, regardless of what any
    frontend dropdown offered. automation_rule_definition_hash (part of
    validate(), feeding the Runtime V2 revision/definition the gateway
    syncs) also runs cleanly over both new values here."""

    def setUp(self):
        self._rules = []

    def tearDown(self):
        for name in reversed(self._rules):
            try:
                if frappe.db.exists("BP Automation Rule", name):
                    frappe.delete_doc("BP Automation Rule", name, ignore_permissions=True, force=True)
            except Exception:
                pass
        frappe.db.commit()

    def _make_rule(self, trigger_event):
        doc = frappe.get_doc({
            "doctype": "BP Automation Rule",
            "rule_name": f"test-{trigger_event}",
            "scope": "workspace",
            "trigger_event": trigger_event,
            "is_active": 0,
            "actions": "[]",
            # action_type otherwise picks up the DocType's own default
            # (a legacy single-action field predating `actions`), which
            # falls into a validate() branch requiring action-specific
            # config unrelated to what this test is actually checking.
            "action_type": "",
        })
        doc.insert(ignore_permissions=True)
        self._rules.append(doc.name)
        frappe.db.commit()
        return doc

    def test_a_rule_using_task_trashed_validates_and_saves(self):
        doc = self._make_rule("task.trashed")
        reloaded = frappe.get_doc("BP Automation Rule", doc.name)
        self.assertEqual(reloaded.trigger_event, "task.trashed")

    def test_a_rule_using_task_restored_validates_and_saves(self):
        doc = self._make_rule("task.restored")
        reloaded = frappe.get_doc("BP Automation Rule", doc.name)
        self.assertEqual(reloaded.trigger_event, "task.restored")

    def test_a_saved_task_trashed_rule_is_found_by_the_same_query_the_matcher_uses(self):
        """run_for_event/the_gateway matcher select active rules by a plain
        trigger_event equality filter — no special-casing per event name
        anywhere in that path (confirmed by code review, not new logic
        this correction had to add). This proves the row is actually
        findable that way once persistence allows it to exist at all."""
        doc = self._make_rule("task.trashed")
        frappe.db.set_value("BP Automation Rule", doc.name, "is_active", 1)
        frappe.db.commit()
        found = frappe.get_all(
            "BP Automation Rule",
            filters={"trigger_event": "task.trashed", "is_active": 1, "scope": "workspace"},
            pluck="name",
        )
        self.assertIn(doc.name, found)


if __name__ == "__main__":
    import unittest
    unittest.main()
