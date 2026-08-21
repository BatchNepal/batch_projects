"""Task trash/restore and ReBAC rebuild regression coverage."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import rebac_state
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
            overrides["batch_projects.api.board.sync_rebac_state"],
            "batch_projects.rebac_state.sync_rebac_state",
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
    @patch.object(task_lifecycle, "_assignees", return_value=["alice@example.com"])
    @patch.object(task_lifecycle.frappe.db, "set_value")
    @patch.object(task_lifecycle.frappe, "get_all", return_value=[])
    @patch.object(task_lifecycle.frappe, "get_doc")
    def test_trash_uses_one_explicit_cascade_stamp(
        self, get_doc, get_all, set_value, assignees, schedule
    ):
        get_doc.return_value = SimpleNamespace(
            name="TASK-1", project="PROJ-A", task_key="PRJ-1",
            title="Parent", is_deleted=0,
        )
        stamp = "2026-08-21 06:00:00"
        changed = task_lifecycle._trash_tree("TASK-1", stamp, "actor@example.com")
        self.assertEqual(changed, ["TASK-1"])
        values = set_value.call_args.args[2]
        self.assertEqual(values["deleted_on"], stamp)
        self.assertEqual(values["deleted_by"], "actor@example.com")
        self.assertEqual(schedule.call_args.args[0], "task.trashed")
        self.assertEqual(schedule.call_args.args[2], ["alice@example.com"])


class TestRebacRebuildTrashFilter(FrappeTestCase):
    @patch("batch_projects.api.board._assert_service_caller")
    @patch.object(rebac_state.frappe, "get_all")
    def test_task_rebuild_only_exports_live_tasks(self, get_all, service):
        get_all.return_value = [frappe._dict(task="TASK-1", project="PROJ-A")]
        result = rebac_state.sync_rebac_state("tasks", offset=0, limit=50)
        self.assertEqual(result["items"][0].task, "TASK-1")
        filters = get_all.call_args.kwargs["filters"]
        self.assertEqual(filters, {"is_deleted": 0})

    @patch("batch_projects.api.board._assert_service_caller")
    @patch.object(rebac_state.frappe.db, "sql")
    def test_assignee_rebuild_joins_only_live_parent_tasks(self, sql, service):
        sql.return_value = []
        rebac_state.sync_rebac_state("task_assignees", offset=0, limit=50)
        query = sql.call_args.args[0]
        self.assertIn("COALESCE(t.is_deleted, 0) = 0", query)
        self.assertIn("INNER JOIN `tabBP Task`", query)


if __name__ == "__main__":
    import unittest
    unittest.main()
