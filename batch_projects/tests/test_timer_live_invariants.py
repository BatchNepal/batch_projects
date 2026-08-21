"""Regression coverage for timer behavior around soft-deleted tasks."""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import timer_invariants as timers


class TestTimerRouting(FrappeTestCase):
    def test_timer_endpoints_use_live_task_adapter(self):
        overrides = hooks.override_whitelisted_methods
        expected = {
            "batch_projects.api.timers.get_active_timer":
                "batch_projects.timer_invariants.get_active_timer",
            "batch_projects.api.timers.start_timer":
                "batch_projects.timer_invariants.start_timer",
            "batch_projects.api.timers.stop_timer":
                "batch_projects.timer_invariants.stop_timer",
            "batch_projects.api.timers.log_time":
                "batch_projects.timer_invariants.log_time",
        }
        for method, target in expected.items():
            self.assertEqual(overrides[method], target)

        self.assertIn(
            "batch_projects.timer_invariants.send_timer_reminders",
            hooks.scheduler_events["hourly"],
        )
        self.assertNotIn(
            "batch_projects.api.timers.send_timer_reminders",
            hooks.scheduler_events["hourly"],
        )


class TestLiveTaskTimerGuard(FrappeTestCase):
    @patch.object(timers, "_task_state")
    def test_trash_rejects_new_time(self, task_state):
        task_state.return_value = frappe._dict(
            name="TASK-1",
            task_key="PRJ-1",
            project="PROJ",
            is_deleted=1,
            deleted_on="2026-08-21 08:00:00",
        )
        with self.assertRaises(frappe.ValidationError):
            timers._require_live_task("TASK-1")

    @patch("batch_projects.api.timers._require_system_user")
    @patch("batch_projects.api.timers.require_feature")
    @patch("batch_projects.api.timers.start_timer")
    @patch.object(timers, "_require_live_task")
    def test_start_timer_checks_auth_then_live_state_before_legacy_api(
        self, require_live, original_start, require_feature, require_user
    ):
        require_live.side_effect = frappe.ValidationError("in trash")
        with self.assertRaises(frappe.ValidationError):
            timers.start_timer("TASK-1")
        require_user.assert_called_once()
        require_feature.assert_called_once_with("time_tracking")
        require_live.assert_called_once_with("TASK-1")
        original_start.assert_not_called()

    @patch("batch_projects.api.timers._require_system_user")
    @patch("batch_projects.api.timers.require_feature")
    @patch("batch_projects.api.timers.log_time")
    @patch.object(timers, "_require_live_task")
    def test_manual_time_checks_auth_then_live_state_before_legacy_api(
        self, require_live, original_log, require_feature, require_user
    ):
        require_live.side_effect = frappe.ValidationError("in trash")
        with self.assertRaises(frappe.ValidationError):
            timers.log_time("TASK-1", 1.0)
        require_user.assert_called_once()
        require_feature.assert_called_once_with("time_tracking")
        require_live.assert_called_once_with("TASK-1")
        original_log.assert_not_called()


class TestGhostTimerRepair(FrappeTestCase):
    @patch("batch_projects.api.timers._append_time_log")
    @patch.object(timers.frappe, "get_doc")
    @patch.object(timers.frappe, "delete_doc")
    def test_deleted_timer_is_capped_at_deleted_on(
        self, delete_doc, get_doc, append_time_log
    ):
        active = frappe._dict(
            name="TIMER-1",
            user="alice@example.com",
            task="TASK-1",
            started_at="2026-08-21 07:15:00",
        )
        state = frappe._dict(
            name="TASK-1",
            task_key="PRJ-1",
            title="Task",
            project="PROJ",
            is_deleted=1,
            deleted_on="2026-08-21 08:00:00",
        )
        task_doc = MagicMock()
        get_doc.return_value = task_doc
        append_time_log.return_value = {"elapsed_hours": 0.75}

        result = timers._close_deleted_timer(active, state)

        delete_doc.assert_called_once_with(
            "BP Active Timer", "TIMER-1", ignore_permissions=True
        )
        args = append_time_log.call_args.args
        self.assertIs(args[0], task_doc)
        self.assertEqual(args[1], "alice@example.com")
        self.assertEqual(args[4], 0.75)
        self.assertEqual(result, {"elapsed_hours": 0.75})

    def test_missing_deleted_on_never_falls_back_to_now(self):
        active = frappe._dict(
            name="TIMER-1",
            user="alice@example.com",
            task="TASK-1",
            started_at="2026-08-21 07:15:00",
        )
        state = frappe._dict(
            name="TASK-1",
            task_key="PRJ-1",
            project="PROJ",
            is_deleted=1,
            deleted_on=None,
        )
        with self.assertRaises(frappe.ValidationError):
            timers._close_deleted_timer(active, state)

    @patch.object(timers.frappe.db, "commit")
    @patch.object(timers, "_close_deleted_timer")
    @patch.object(timers, "_task_state")
    @patch.object(timers, "_active_timer_for_user")
    @patch("batch_projects.api.timers._require_system_user")
    def test_active_timer_read_repairs_soft_deleted_task(
        self, require_user, active_timer, task_state, close_timer, commit
    ):
        active_timer.return_value = frappe._dict(
            name="TIMER-1",
            task="TASK-1",
            user="alice@example.com",
            started_at="2026-08-21 07:00:00",
        )
        task_state.return_value = frappe._dict(
            name="TASK-1",
            task_key="PRJ-1",
            title="Task",
            project="PROJ",
            is_deleted=1,
            deleted_on="2026-08-21 08:00:00",
        )

        self.assertIsNone(timers.get_active_timer())

        close_timer.assert_called_once()
        commit.assert_called_once()


class TestTimerReminderLiveBoundary(FrappeTestCase):
    @patch("batch_projects.events._push_notification_badge")
    @patch("batch_projects.events._create_notification")
    @patch("batch_projects.events._reminder_sent_today", return_value=False)
    @patch.object(timers, "_close_deleted_timer")
    @patch.object(timers, "_task_state")
    @patch.object(timers.frappe, "get_all")
    @patch.object(timers.frappe.db, "commit")
    def test_hourly_job_repairs_deleted_timer_instead_of_notifying(
        self,
        commit,
        get_all,
        task_state,
        close_timer,
        reminder_sent,
        create_notification,
        push_badge,
    ):
        active = frappe._dict(
            name="TIMER-1",
            user="alice@example.com",
            task="TASK-1",
            started_at="2026-08-20 23:00:00",
        )
        get_all.return_value = [active]
        task_state.return_value = frappe._dict(
            name="TASK-1",
            task_key="PRJ-1",
            title="Task",
            project="PROJ",
            is_deleted=1,
            deleted_on="2026-08-21 00:00:00",
        )

        timers.send_timer_reminders()

        close_timer.assert_called_once()
        create_notification.assert_not_called()
        push_badge.assert_not_called()
        commit.assert_called_once()
