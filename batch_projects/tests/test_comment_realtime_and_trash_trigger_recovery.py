"""Regression coverage for comment edit/delete realtime events and the
task.trashed/task.restored automation trigger metadata.

Recovered gaps (BatchProjects git-audit, P2 #2-#4):
  - edit_comment only ever emitted COMMENT_ADDED, and only when the edit
    added a new @mention; a plain text edit (the common case) broadcast
    nothing at all. delete_comment emitted nothing, ever.
  - task.trashed/task.restored are real, already-emitted runtime events
    (task_lifecycle.py) that were never offered as selectable triggers in
    the automation builder's trigger.task_event node.

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
            board.edit_comment("ACT-1", "hey @[Bob](bob@example.com)")

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


class TestTrashRestoreAutomationTriggerMetadata(FrappeTestCase):
    def test_trashed_and_restored_are_selectable_task_event_triggers(self):
        from batch_projects.api.automation import _NODE_REGISTRY

        options = {
            o["value"]
            for o in _NODE_REGISTRY["trigger.task_event"]["config_schema"][0]["options"]
        }
        self.assertIn("task.trashed", options)
        self.assertIn("task.restored", options)


if __name__ == "__main__":
    import unittest
    unittest.main()
