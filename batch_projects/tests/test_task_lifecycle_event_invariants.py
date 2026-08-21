"""Regression coverage for soft-trash/restore event semantics."""

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import task_lifecycle
from batch_projects import automation_surface


class TestLifecycleRoutes(FrappeTestCase):
    def test_lifecycle_and_builder_routes_are_overridden(self):
        overrides = hooks.override_whitelisted_methods
        self.assertEqual(
            overrides["batch_projects.api.board.delete_task"],
            "batch_projects.task_lifecycle.delete_task",
        )
        self.assertEqual(
            overrides["batch_projects.api.board.restore_task"],
            "batch_projects.task_lifecycle.restore_task",
        )
        self.assertEqual(
            overrides["batch_projects.api.board.get_automation_options"],
            "batch_projects.automation_surface.get_automation_options",
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


class TestLifecycleAutomationSurface(FrappeTestCase):
    @patch("batch_projects.api.board.get_automation_options")
    def test_builder_exposes_trash_and_restore_triggers(self, base_options):
        base_options.return_value = {
            "triggers": [{"value": "task.created", "label": "Created"}],
            "actions": [],
        }

        result = automation_surface.get_automation_options("PROJ-1")
        values = {row["value"] for row in result["triggers"]}
        self.assertIn("task.trashed", values)
        self.assertIn("task.restored", values)
        self.assertIn("task.created", values)

    @patch("batch_projects.api.board.get_automation_options")
    def test_builder_does_not_duplicate_existing_lifecycle_trigger(self, base_options):
        base_options.return_value = {
            "triggers": [{"value": "task.trashed", "label": "Existing"}],
        }
        result = automation_surface.get_automation_options("PROJ-1")
        values = [row["value"] for row in result["triggers"]]
        self.assertEqual(values.count("task.trashed"), 1)
