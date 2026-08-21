"""Regression coverage for project default-assignee materialization."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import task_defaults


class _Task:
    def __init__(self, assignees=None):
        self.project = "PROJ-1"
        self.name = "TASK-1"
        self.task_key = "PRJ-1"
        self.title = "Default assignment test"
        self.description = ""
        self.task_type = "Task"
        self.epic = None
        self.milestone = None
        self.parent_task = None
        self.sprint = None
        self.approval_status = "Approval Not Required"
        self.approver = None
        self.assignees = list(assignees or [])
        self.flags = frappe._dict()

    def get(self, field):
        return getattr(self, field, None)

    def append(self, field, values):
        row = SimpleNamespace(**values)
        getattr(self, field).append(row)
        return row

    def is_new(self):
        return True


class TestDefaultAssigneeHooks(FrappeTestCase):
    def test_task_hooks_route_through_default_adapter(self):
        task_hooks = hooks.doc_events["BP Task"]
        self.assertEqual(task_hooks["before_insert"], "batch_projects.task_defaults.before_task_insert")
        self.assertEqual(task_hooks["after_insert"], "batch_projects.task_defaults.after_task_insert")
        self.assertEqual(task_hooks["validate"], "batch_projects.task_validation.validate_task")


class TestDefaultMaterialization(FrappeTestCase):
    @patch.object(task_defaults.task_invariants, "_assert_assignable_user")
    @patch.object(task_defaults.frappe.db, "get_value")
    def test_project_default_becomes_real_assignee_when_none_explicit(self, get_value, assignable):
        get_value.return_value = "default@example.com"
        assignable.return_value = frappe._dict(full_name="Default User")
        task = _Task()

        task_defaults.before_task_insert(task)

        self.assertEqual([row.user for row in task.assignees], ["default@example.com"])
        self.assertEqual(task.assignees[0].full_name, "Default User")
        self.assertEqual(task.flags.bp_default_assignee_materialized, "default@example.com")

    @patch.object(task_defaults.frappe.db, "get_value")
    def test_explicit_assignee_wins_over_project_default(self, get_value):
        task = _Task([SimpleNamespace(user="explicit@example.com", full_name="Explicit")])
        task_defaults.before_task_insert(task)
        get_value.assert_not_called()
        self.assertEqual([row.user for row in task.assignees], ["explicit@example.com"])
        self.assertFalse(task.flags.get("bp_default_assignee_materialized"))

    @patch.object(task_defaults.task_invariants, "_assert_new_mentions_authorized")
    @patch.object(task_defaults.task_invariants, "_validate_pending_approver")
    @patch.object(task_defaults.task_invariants, "_validate_task_links")
    @patch.object(task_defaults.task_invariants, "_validate_project_relations")
    @patch.object(task_defaults.task_invariants, "_validate_task_type")
    @patch.object(task_defaults.task_invariants, "_assert_assignable_user")
    @patch.object(task_defaults.frappe.db, "get_value")
    def test_materialized_edge_must_match_current_project_default(
        self, get_value, assignable, *_validators
    ):
        task = _Task([SimpleNamespace(user="default@example.com", full_name="")])
        task.flags.bp_default_assignee_materialized = "default@example.com"
        get_value.return_value = "someone-else@example.com"

        with self.assertRaises(frappe.ValidationError):
            task_defaults.validate_materialized_default(task)
        assignable.assert_not_called()

    @patch.object(task_defaults.task_invariants, "_assert_new_mentions_authorized")
    @patch.object(task_defaults.task_invariants, "_validate_pending_approver")
    @patch.object(task_defaults.task_invariants, "_validate_task_links")
    @patch.object(task_defaults.task_invariants, "_validate_project_relations")
    @patch.object(task_defaults.task_invariants, "_validate_task_type")
    @patch.object(task_defaults.task_invariants, "_assert_assignable_user")
    @patch.object(task_defaults.frappe.db, "get_value")
    def test_exact_materialized_edge_runs_all_non_authority_invariants(
        self, get_value, assignable, task_type, relations, links, approver, mentions
    ):
        task = _Task([SimpleNamespace(user="default@example.com", full_name="")])
        task.flags.bp_default_assignee_materialized = "default@example.com"
        get_value.return_value = "default@example.com"
        assignable.return_value = frappe._dict(full_name="Default User")

        self.assertTrue(task_defaults.validate_materialized_default(task))
        self.assertEqual(task.assignees[0].full_name, "Default User")
        task_type.assert_called_once()
        relations.assert_called_once()
        links.assert_called_once()
        approver.assert_called_once()
        mentions.assert_called_once()


class TestDefaultAssignmentLifecycle(FrappeTestCase):
    @patch("batch_projects.events._sync_rebac")
    @patch("batch_projects.events._evaluate_automations")
    @patch("batch_projects.events._broadcast")
    @patch("batch_projects.events._invalidate_cache")
    @patch("batch_projects.events._enrich", side_effect=lambda event, payload: {**payload, "event": event})
    @patch("batch_projects.events.add_watcher")
    @patch.object(task_defaults.frappe, "get_doc")
    @patch.object(task_defaults.frappe.db, "get_value")
    def test_default_assignment_dispatches_real_edge_without_second_notification(
        self, get_value, get_doc, add_watcher, enrich, invalidate, broadcast, automation, rebac
    ):
        task = _Task([SimpleNamespace(user="default@example.com", full_name="Default User")])
        task.flags.bp_default_assignee_materialized = "default@example.com"

        def value_side_effect(doctype, *args, **kwargs):
            if doctype == "BP Project":
                return "default@example.com"
            if doctype == "User":
                return "Actor Name"
            return None
        get_value.side_effect = value_side_effect

        activity = MagicMock()
        get_doc.return_value = activity

        task_defaults.after_task_insert(task)

        activity.insert.assert_called_once_with(ignore_permissions=True)
        add_watcher.assert_called_once_with("TASK-1", "default@example.com", reason="assigned")
        enrich.assert_called_once()
        invalidate.assert_called_once()
        broadcast.assert_called_once()
        automation.assert_called_once()
        rebac.assert_called_once()

        # The adapter intentionally never calls events._queue_notifications;
        # the earlier task.created event supplies the one legacy notification.
        event_name, payload = enrich.call_args.args
        self.assertEqual(event_name, "task.assigned")
        self.assertTrue(payload["default_assignment"])
        self.assertEqual(payload["assignee"], "default@example.com")

    @patch.object(task_defaults.task_invariants, "after_task_insert")
    def test_explicit_initial_assignees_keep_normal_event_path(self, normal_after_insert):
        task = _Task([SimpleNamespace(user="explicit@example.com", full_name="Explicit")])
        task_defaults.after_task_insert(task)
        normal_after_insert.assert_called_once_with(task, method=None)
