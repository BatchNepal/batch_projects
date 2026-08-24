"""Task trash/restore regression coverage.

Split out of a larger source file that also covered rebac_state.py's
ReBAC-rebuild sync — that module belongs to a separate PR (project security
model), not this one.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import task_lifecycle
from batch_projects import task_validation


class TestLifecycleRouting(FrappeTestCase):
    def test_soft_delete_methods_use_authoritative_lifecycle(self):
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
            overrides["batch_projects.api.board.bulk_delete_tasks"],
            "batch_projects.task_lifecycle.bulk_delete_tasks",
        )
        self.assertEqual(
            overrides["batch_projects.api.board.get_export_data"],
            "batch_projects.task_reads.get_export_data",
        )


class TestTrashFlagInvariant(FrappeTestCase):
    def test_direct_soft_delete_flag_change_is_rejected(self):
        old = frappe._dict(is_deleted=0)
        doc = frappe._dict(is_deleted=1)
        with self.assertRaises(frappe.ValidationError):
            task_validation.validate_trash_state(doc, old)

    def test_unchanged_trash_flag_is_allowed(self):
        old = frappe._dict(is_deleted=0)
        task_validation.validate_trash_state(frappe._dict(is_deleted=0), old)


class TestActiveTimerTrashInvariant(FrappeTestCase):
    @patch("batch_projects.api.timers._append_time_log")
    @patch.object(task_lifecycle.frappe, "delete_doc")
    @patch.object(task_lifecycle.frappe, "get_all")
    def test_trash_stops_timer_at_exact_delete_timestamp(
        self, get_all, delete_doc, append_time_log
    ):
        get_all.return_value = [
            frappe._dict(
                name="TIMER-1",
                user="test31+info@batchnepal.com",
                started_at="2026-08-21 07:30:00",
            )
        ]
        doc = SimpleNamespace(
            name="TASK-1",
            task_key="PRJ-1",
            title="Task",
            project="PROJ-A",
        )

        stopped = task_lifecycle._stop_active_timers(
            doc, "2026-08-21 08:00:00"
        )

        self.assertEqual(stopped, ["TIMER-1"])
        delete_doc.assert_called_once_with(
            "BP Active Timer", "TIMER-1", ignore_permissions=True
        )
        args = append_time_log.call_args.args
        self.assertIs(args[0], doc)
        self.assertEqual(args[1], "test31+info@batchnepal.com")
        self.assertEqual(args[4], 0.5)
        self.assertIn("moved to Trash", append_time_log.call_args.kwargs["description"])

    @patch(
        "batch_projects.api.timers._append_time_log",
        side_effect=frappe.ValidationError("cannot persist time"),
    )
    @patch.object(task_lifecycle.frappe, "delete_doc")
    @patch.object(task_lifecycle.frappe, "get_all")
    def test_trash_fails_if_active_time_cannot_be_preserved(
        self, get_all, delete_doc, append_time_log
    ):
        get_all.return_value = [
            frappe._dict(
                name="TIMER-1",
                user="test31+info@batchnepal.com",
                started_at="2026-08-21 07:30:00",
            )
        ]
        doc = SimpleNamespace(
            name="TASK-1",
            task_key="PRJ-1",
            title="Task",
            project="PROJ-A",
        )

        with self.assertRaises(frappe.ValidationError):
            task_lifecycle._stop_active_timers(doc, "2026-08-21 08:00:00")

        # The outer delete_task transaction owns rollback. The important
        # invariant here is that a failed time-log write is not swallowed and
        # allowed to commit a trashed task with lost working time.
        append_time_log.assert_called_once()


class TestRestoreCascadeProvenance(FrappeTestCase):
    @patch.object(task_lifecycle, "_schedule_lifecycle")
    @patch.object(task_lifecycle, "_assignees", return_value=[])
    @patch.object(task_lifecycle.frappe.db, "set_value")
    @patch.object(task_lifecycle.frappe, "get_all", return_value=[])
    @patch.object(task_lifecycle.frappe, "get_doc")
    def test_restore_queries_only_same_delete_stamp(
        self, get_doc, get_all, set_value, assignees, schedule
    ):
        stamp = "2026-08-21 06:00:00"
        get_doc.return_value = SimpleNamespace(
            name="TASK-1", project="PROJ-A", task_key="PRJ-1",
            title="Parent", is_deleted=1, deleted_on=stamp,
        )

        changed = task_lifecycle._restore_tree("TASK-1", stamp)

        self.assertEqual(changed, ["TASK-1"])
        filters = get_all.call_args.kwargs["filters"]
        self.assertEqual(filters["parent_task"], "TASK-1")
        self.assertEqual(filters["is_deleted"], 1)
        self.assertEqual(filters["deleted_on"], stamp)
        schedule.assert_called_once()
        self.assertEqual(schedule.call_args.args[0], "task.restored")

    @patch.object(task_lifecycle, "_schedule_lifecycle")
    @patch.object(task_lifecycle, "_assignees", return_value=["test31+info@batchnepal.com"])
    @patch.object(task_lifecycle, "_stop_active_timers", return_value=[])
    @patch.object(task_lifecycle.frappe.db, "set_value")
    @patch.object(task_lifecycle.frappe, "get_all", return_value=[])
    @patch.object(task_lifecycle.frappe, "get_doc")
    def test_trash_uses_one_explicit_cascade_stamp(
        self, get_doc, get_all, set_value, stop_timers, assignees, schedule
    ):
        get_doc.return_value = SimpleNamespace(
            name="TASK-1", project="PROJ-A", task_key="PRJ-1",
            title="Parent", is_deleted=0,
        )
        stamp = "2026-08-21 06:00:00"
        changed = task_lifecycle._trash_tree("TASK-1", stamp, "test30+info@batchnepal.com")
        self.assertEqual(changed, ["TASK-1"])
        stop_timers.assert_called_once_with(get_doc.return_value, stamp)
        values = set_value.call_args.args[2]
        self.assertEqual(values["deleted_on"], stamp)
        self.assertEqual(values["deleted_by"], "test30+info@batchnepal.com")
        self.assertEqual(schedule.call_args.args[0], "task.trashed")
        self.assertEqual(schedule.call_args.args[2], ["test31+info@batchnepal.com"])


if __name__ == "__main__":
    import unittest
    unittest.main()
