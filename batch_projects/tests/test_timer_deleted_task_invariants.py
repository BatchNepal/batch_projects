"""Regression coverage for timer operations against soft-deleted tasks.

Recovered gaps (BatchProjects git-audit, P1 #4-#5): start/log/lookup/reminder
timer paths only ever checked whether a task existed at all, not whether it
had been soft-deleted (is_deleted=1 — the row is still there, only hidden
from list/permission-query views) — so a timer could be started, logged, or
kept nagging its user against a trashed task, and a legacy timer still
running when its task got trashed kept accruing loggable time forever
instead of being capped at the moment the task was deleted.

Run with:
    bench run-tests --module batch_projects.tests.test_timer_deleted_task_invariants
"""

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from batch_projects.api import timers


class TestStartAndLogRejectDeletedTasks(FrappeTestCase):
    def test_start_timer_rejects_a_deleted_task(self):
        task_doc = frappe._dict(project="PROJ-A", is_deleted=1)
        with (
            patch.object(timers, "_require_system_user"),
            patch("batch_projects.entitlements.require_feature"),
            patch.object(frappe, "get_doc", return_value=task_doc),
            patch.object(timers, "_check_task_permission"),
            self.assertRaises(frappe.ValidationError),
        ):
            timers.start_timer("TASK-1")

    def test_log_time_rejects_a_deleted_task(self):
        task_doc = frappe._dict(project="PROJ-A", is_deleted=1)
        with (
            patch.object(timers, "_require_system_user"),
            patch("batch_projects.entitlements.require_feature"),
            patch.object(frappe, "get_doc", return_value=task_doc),
            patch.object(timers, "_check_task_permission"),
            self.assertRaises(frappe.ValidationError),
        ):
            timers.log_time("TASK-1", 1.0)


class TestStopCapsDurationAtDeletion(FrappeTestCase):
    def test_legacy_timer_on_a_deleted_task_is_capped_at_deleted_on(self):
        started_at = now_datetime() - timedelta(hours=5)
        deleted_on = now_datetime() - timedelta(hours=2)
        active_timer = frappe._dict(user="u@example.com", task="TASK-1", started_at=started_at)

        with (
            patch.object(frappe, "get_doc") as get_doc,
            patch.object(frappe, "delete_doc"),
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(is_deleted=1, deleted_on=deleted_on),
            ),
            patch.object(timers, "_append_time_log", return_value={"ok": True}) as append_log,
        ):
            get_doc.return_value = active_timer
            timers._stop("AT-1")

        append_log.assert_called_once()
        logged_to_time = append_log.call_args.args[3]
        logged_hours = append_log.call_args.args[4]
        self.assertEqual(logged_to_time, deleted_on)
        # 5h started -> 2h before deletion = 3h capped, not the full 5h to now().
        self.assertAlmostEqual(logged_hours, 3.0, places=1)

    def test_timer_on_a_hard_deleted_task_logs_nothing(self):
        active_timer = frappe._dict(user="u@example.com", task="TASK-GONE", started_at=now_datetime())
        with (
            patch.object(frappe, "get_doc", return_value=active_timer),
            patch.object(frappe, "delete_doc"),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(timers, "_append_time_log") as append_log,
        ):
            result = timers._stop("AT-1")

        self.assertIsNone(result)
        append_log.assert_not_called()

    def test_timer_on_a_live_task_is_uncapped(self):
        started_at = now_datetime() - timedelta(hours=1)
        active_timer = frappe._dict(user="u@example.com", task="TASK-1", started_at=started_at)
        with (
            patch.object(frappe, "get_doc", return_value=active_timer),
            patch.object(frappe, "delete_doc"),
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(is_deleted=0, deleted_on=None),
            ),
            patch.object(timers, "_append_time_log", return_value={"ok": True}) as append_log,
        ):
            timers._stop("AT-1")

        append_log.assert_called_once()
        self.assertAlmostEqual(append_log.call_args.args[4], 1.0, places=1)


class TestGetActiveTimerSelfHealsTrashedTask(FrappeTestCase):
    def test_lookup_resolves_and_clears_a_timer_on_a_trashed_task(self):
        row = frappe._dict(name="AT-1", task="TASK-1", started_at=now_datetime())
        with (
            patch.object(timers, "_require_system_user"),
            patch.object(
                frappe.db, "get_value",
                side_effect=[row, frappe._dict(
                    name="TASK-1", task_key="BP-1", title="t", project="PROJ-A", is_deleted=1,
                )],
            ),
            patch.object(timers, "_stop", return_value=None) as stop,
            patch.object(frappe.db, "commit"),
        ):
            result = timers.get_active_timer()

        self.assertIsNone(result)
        stop.assert_called_once_with("AT-1")


class TestTimerRemindersSkipDeletedTasks(FrappeTestCase):
    def test_no_reminder_is_sent_for_a_deleted_tasks_timer(self):
        rows = [frappe._dict(name="AT-1", user="u@example.com", task="TASK-1", started_at=now_datetime() - timedelta(hours=9))]
        with (
            patch.object(frappe, "get_all", return_value=rows),
            patch("batch_projects.events._reminder_sent_today", return_value=False),
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(task_key="BP-1", title="t", project="PROJ-A", is_deleted=1),
            ),
            patch("batch_projects.events._create_notification") as create_notification,
        ):
            timers.send_timer_reminders()

        create_notification.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
