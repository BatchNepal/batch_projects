"""Regression coverage for soft-trash/restore event semantics.

Split out of a larger source file that also covered automation_surface.py's
automation-builder trigger list — that module isn't part of this PR (it's a
thin delegation layer being added as a follow-up commit to PR #60 instead).
"""

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import task_lifecycle


class TestLifecycleRoutes(FrappeTestCase):
    def test_lifecycle_routes_are_overridden(self):
        overrides = hooks.override_whitelisted_methods
        self.assertEqual(
            overrides["batch_projects.api.board.delete_task"],
            "batch_projects.task_lifecycle.delete_task",
        )
        self.assertEqual(
            overrides["batch_projects.api.board.restore_task"],
            "batch_projects.task_lifecycle.restore_task",
        )


class TestLifecycleDispatch(FrappeTestCase):
    @patch("batch_projects.bridge.publish_rebac_event")
    @patch("batch_projects.events._queue_notifications")
    @patch("batch_projects.events._evaluate_automations")
    @patch("batch_projects.events._broadcast")
    @patch("batch_projects.events._invalidate_cache")
    @patch("batch_projects.events._enrich", side_effect=lambda event, payload: {**payload, "event": event})
    def test_trash_restore_dispatch_runs_committed_event_pipeline(
        self, enrich, invalidate, broadcast, automation, notifications, rebac
    ):
        payload = {
            "project": "PROJ-1",
            "task": "TASK-1",
            "task_key": "PRJ-1",
            "title": "Task",
            "users": ["alice@example.com"],
        }

        task_lifecycle._dispatch_after_commit(task_lifecycle.TASK_TRASHED, payload)

        enrich.assert_called_once_with(task_lifecycle.TASK_TRASHED, payload)
        invalidate.assert_called_once()
        broadcast.assert_called_once()
        self.assertFalse(broadcast.call_args.kwargs["after_commit"])
        automation.assert_called_once()
        notifications.assert_called_once()
        rebac.assert_called_once()
        sent = rebac.call_args.args[0]
        self.assertEqual(sent["event"], "task.trashed")
        self.assertEqual(sent["users"], ["alice@example.com"])


if __name__ == "__main__":
    import unittest
    unittest.main()
