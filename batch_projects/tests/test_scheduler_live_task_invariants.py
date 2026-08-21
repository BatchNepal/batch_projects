"""Regression coverage for live-task scheduler semantics."""

import inspect
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import hooks
from batch_projects import scheduler_live as scheduler


class TestSchedulerRouting(FrappeTestCase):
    def test_task_schedulers_use_live_adapter(self):
        daily = set(hooks.scheduler_events["daily"])
        daily_long = set(hooks.scheduler_events["daily_long"])
        weekly_long = set(hooks.scheduler_events["weekly_long"])

        self.assertIn("batch_projects.scheduler_live.send_due_date_reminders", daily)
        self.assertIn("batch_projects.scheduler_live.run_due_soon_automations", daily)
        self.assertIn("batch_projects.scheduler_live.run_overdue_automations", daily)
        self.assertIn("batch_projects.scheduler_live.send_daily_digest", daily_long)
        self.assertIn("batch_projects.scheduler_live.send_weekly_project_summary", weekly_long)

        self.assertNotIn("batch_projects.events.send_due_date_reminders", daily)
        self.assertNotIn("batch_projects.events.run_due_soon_automations", daily)
        self.assertNotIn("batch_projects.events.run_overdue_automations", daily)
        self.assertNotIn("batch_projects.events.send_daily_digest", daily_long)
        self.assertNotIn("batch_projects.events.send_weekly_project_summary", weekly_long)

    def test_live_filter_defaults_to_not_deleted(self):
        self.assertEqual(scheduler._live_filters({"project": "PROJ-1"}), {
            "project": "PROJ-1",
            "is_deleted": 0,
        })
        self.assertEqual(
            scheduler._live_filters({"project": "PROJ-1", "is_deleted": 1}),
            {"project": "PROJ-1", "is_deleted": 1},
        )

    def test_scheduler_never_uses_raw_notification_unread_count(self):
        source = inspect.getsource(scheduler)
        self.assertNotIn('frappe.db.count("BP Notification"', source)
        self.assertIn("visible_unread_count(user)", source)


class TestDailyDigestLiveTasks(FrappeTestCase):
    @patch("batch_projects.events._has_outgoing_email", return_value=True)
    @patch("batch_projects.events._completed_statuses", return_value=[])
    @patch("batch_projects.events._build_digest_html", return_value="<html>digest</html>")
    @patch.object(scheduler, "resolve_system_user", return_value="user@example.com")
    @patch.object(scheduler, "_current_task_for_user", return_value=True)
    @patch.object(scheduler, "visible_unread_count", return_value=4)
    @patch.object(scheduler.frappe, "sendmail")
    @patch.object(scheduler.frappe, "get_all")
    @patch.object(scheduler.frappe.db, "get_value")
    @patch.object(scheduler.frappe.db, "sql_list", return_value=["user@example.com"])
    def test_digest_uses_live_assignments_and_authorized_unread_count(
        self,
        sql_list,
        get_value,
        get_all,
        sendmail,
        visible_unread,
        current_access,
        resolve_user,
        build_html,
        completed_statuses,
        outgoing,
    ):
        def get_value_side_effect(doctype, name, fieldname, *args, **kwargs):
            if doctype == "BP Notification Preference":
                return None
            if doctype == "User":
                return frappe._dict(
                    email="user@example.com",
                    full_name="Digest User",
                )
            return None

        task_filters = []

        def get_all_side_effect(doctype, *args, **kwargs):
            if doctype == "BP Task Assignee":
                self.assertEqual(kwargs.get("filters"), {"user": "user@example.com"})
                return ["TASK-1"]
            if doctype == "BP Task":
                task_filters.append(kwargs.get("filters"))
                return [
                    frappe._dict(
                        name="TASK-1",
                        task_key="PROJ-1",
                        title="Live work",
                        status="Open",
                        project="PROJ",
                        due_date=None,
                        priority="Medium",
                    )
                ]
            return []

        get_value.side_effect = get_value_side_effect
        get_all.side_effect = get_all_side_effect

        scheduler.send_daily_digest()

        query = sql_list.call_args.args[0]
        self.assertIn("inner join `tabBP Task`", query)
        self.assertIn("t.is_deleted = 0", query)
        self.assertEqual(task_filters, [{"name": ["in", ["TASK-1"]], "is_deleted": 0}])
        current_access.assert_called_once()
        visible_unread.assert_called_once_with("user@example.com")
        build_html.assert_called_once()
        self.assertEqual(build_html.call_args.args[3], 4)
        sendmail.assert_called_once()
        self.assertEqual(sendmail.call_args.kwargs["recipients"], ["user@example.com"])
        self.assertFalse(sendmail.call_args.kwargs["delayed"])

    @patch("batch_projects.events._has_outgoing_email", return_value=True)
    @patch.object(scheduler, "resolve_system_user", return_value=None)
    @patch.object(scheduler.frappe, "sendmail")
    @patch.object(scheduler.frappe.db, "sql_list", return_value=["legacy-web-user"])
    def test_digest_skips_non_system_or_disabled_users(
        self, sql_list, sendmail, resolve_user, outgoing
    ):
        scheduler.send_daily_digest()
        resolve_user.assert_called_once_with("legacy-web-user")
        sendmail.assert_not_called()

    @patch("batch_projects.events._has_outgoing_email", return_value=True)
    @patch("batch_projects.events._completed_statuses", return_value=[])
    @patch("batch_projects.events._build_digest_html")
    @patch.object(scheduler, "resolve_system_user", return_value="user@example.com")
    @patch.object(scheduler, "_current_task_for_user", return_value=False)
    @patch.object(scheduler.frappe, "sendmail")
    @patch.object(scheduler.frappe, "get_all")
    @patch.object(scheduler.frappe.db, "get_value")
    @patch.object(scheduler.frappe.db, "sql_list", return_value=["user@example.com"])
    def test_digest_drops_task_when_current_access_is_gone(
        self,
        sql_list,
        get_value,
        get_all,
        sendmail,
        current_access,
        resolve_user,
        build_html,
        completed_statuses,
        outgoing,
    ):
        def get_value_side_effect(doctype, name, fieldname, *args, **kwargs):
            if doctype == "BP Notification Preference":
                return None
            if doctype == "User":
                return frappe._dict(email="user@example.com", full_name="User")
            return None

        def get_all_side_effect(doctype, *args, **kwargs):
            if doctype == "BP Task Assignee":
                return ["TASK-1"]
            if doctype == "BP Task":
                return [
                    frappe._dict(
                        name="TASK-1",
                        task_key="PROJ-1",
                        title="Formerly visible",
                        status="Open",
                        project="PROJ",
                        due_date=None,
                        priority="Medium",
                    )
                ]
            return []

        get_value.side_effect = get_value_side_effect
        get_all.side_effect = get_all_side_effect

        scheduler.send_daily_digest()

        current_access.assert_called_once()
        build_html.assert_not_called()
        sendmail.assert_not_called()


class TestOtherScheduledLiveTaskSurfaces(FrappeTestCase):
    @patch("batch_projects.events._completed_statuses", return_value=[])
    @patch.object(scheduler.frappe, "get_all", return_value=[])
    def test_due_date_reminder_query_excludes_trash(self, get_all, completed):
        scheduler.send_due_date_reminders()
        filters = get_all.call_args.kwargs["filters"]
        self.assertEqual(filters["is_deleted"], 0)

    @patch("batch_projects.events._has_outgoing_email", return_value=True)
    @patch("batch_projects.events._completed_statuses", return_value=[])
    @patch.object(scheduler.frappe, "get_all")
    def test_weekly_summary_task_query_excludes_trash(self, get_all, completed, outgoing):
        def side_effect(doctype, *args, **kwargs):
            if doctype == "BP Project":
                return [
                    frappe._dict(
                        name="PROJ", project_name="Project", key="P", lead=None
                    )
                ]
            if doctype == "BP Task":
                self.assertEqual(kwargs["filters"]["is_deleted"], 0)
                return []
            return []

        get_all.side_effect = side_effect
        scheduler.send_weekly_project_summary()

    @patch.object(scheduler, "_automation_projects", return_value={"PROJ"})
    @patch.object(scheduler.frappe, "get_cached_doc")
    @patch.object(scheduler.frappe, "get_all", return_value=[])
    def test_due_soon_automation_query_excludes_trash(
        self, get_all, get_cached_doc, automation_projects
    ):
        project = MagicMock()
        project.get_completed_statuses.return_value = []
        get_cached_doc.return_value = project

        scheduler.run_due_soon_automations()

        self.assertEqual(get_all.call_args.kwargs["filters"]["is_deleted"], 0)

    @patch.object(scheduler, "_automation_projects", return_value={"PROJ"})
    @patch.object(scheduler.frappe, "get_cached_doc")
    @patch.object(scheduler.frappe, "get_all", return_value=[])
    def test_overdue_automation_query_excludes_trash(
        self, get_all, get_cached_doc, automation_projects
    ):
        project = MagicMock()
        project.get_completed_statuses.return_value = []
        get_cached_doc.return_value = project

        scheduler.run_overdue_automations()

        self.assertEqual(get_all.call_args.kwargs["filters"]["is_deleted"], 0)
