"""Regression coverage for scheduled-job live-task filtering.

Recovered gaps (BatchProjects git-audit, P1 #1-#3): the daily/weekly
scheduled jobs that generate reminders, digests, and due-soon/overdue
automation triggers queried BP Task with no is_deleted filter at all, so a
trashed task could still nag its former assignees/watchers or fire an
automation rule.

Items 4-5 (deriving recipients from current live assignments, revalidating
authorization immediately before sending) are proven already satisfied by
existing code rather than reimplemented — see
TestCreateNotificationAlreadyRevalidatesBeforeDispatch: every one of these
jobs routes through events._create_notification, which already calls
notification_delivery.is_notification_visible before the push/email
channels fire (independent of and prior to this recovery work). Once the
is_deleted filters below keep a trashed task from reaching that point at
all, "current live assignments" and "revalidate before sending" both hold.

Run with:
    bench run-tests --module batch_projects.tests.test_scheduled_side_effect_live_task_invariants
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from batch_projects import events


def _task_call_filters(get_all_mock):
    """The filters kwarg of the (first) frappe.get_all("BP Task", ...) call."""
    for call in get_all_mock.call_args_list:
        args = call.args
        kwargs = call.kwargs
        doctype = args[0] if args else kwargs.get("doctype")
        if doctype == "BP Task":
            return kwargs.get("filters")
    return None


class TestReminderAndDigestExcludeDeletedTasks(FrappeTestCase):
    def test_due_date_reminders_query_excludes_deleted_tasks(self):
        with patch.object(frappe, "get_all", return_value=[]) as get_all:
            events.send_due_date_reminders()
        filters = _task_call_filters(get_all)
        self.assertEqual(filters.get("is_deleted"), 0)

    def test_daily_digest_query_excludes_deleted_tasks(self):
        with (
            patch.object(events, "_has_outgoing_email", return_value=True),
            patch.object(frappe, "get_all") as get_all,
            patch.object(frappe.db, "get_value") as get_value,
        ):
            def get_all_effect(doctype, *a, **kw):
                if doctype == "BP Task Assignee":
                    return ["alice@example.com"] if not kw.get("filters") else ["TASK-1"]
                return []
            get_all.side_effect = get_all_effect

            def get_value_effect(doctype, *a, **kw):
                if doctype == "User":
                    return 1  # enabled
                return None  # no BP Notification Preference row -> defaults apply
            get_value.side_effect = get_value_effect

            events.send_daily_digest()
        filters = _task_call_filters(get_all)
        self.assertEqual(filters.get("is_deleted"), 0)

    def test_weekly_project_summary_query_excludes_deleted_tasks(self):
        with (
            patch.object(events, "_has_outgoing_email", return_value=True),
            patch.object(frappe, "get_all") as get_all,
        ):
            def side_effect(doctype, *a, **kw):
                if doctype == "BP Project":
                    return [frappe._dict(name="PROJ-A", project_name="Proj A", key="PA", lead=None)]
                return []
            get_all.side_effect = side_effect
            events.send_weekly_project_summary()
        filters = _task_call_filters(get_all)
        self.assertEqual(filters.get("is_deleted"), 0)


class TestScheduledAutomationsExcludeDeletedTasks(FrappeTestCase):
    def test_due_soon_automations_query_excludes_deleted_tasks(self):
        with (
            patch(
                "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._projects_in_scope",
                return_value={"PROJ-A"},
            ),
            patch.object(frappe, "get_all") as get_all,
            patch.object(frappe, "get_cached_doc") as get_cached_doc,
            patch.object(frappe.db, "commit"),
        ):
            def side_effect(doctype, *a, **kw):
                if doctype == "BP Automation Rule":
                    return [{"name": "R-1", "scope": "project", "project": "PROJ-A", "project_filter": None}]
                return []
            get_all.side_effect = side_effect
            get_cached_doc.return_value.get_completed_statuses.return_value = []
            events.run_due_soon_automations()
        filters = _task_call_filters(get_all)
        self.assertEqual(filters.get("is_deleted"), 0)

    def test_overdue_automations_query_excludes_deleted_tasks(self):
        with (
            patch(
                "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._projects_in_scope",
                return_value={"PROJ-A"},
            ),
            patch.object(frappe, "get_all") as get_all,
            patch.object(frappe, "get_cached_doc") as get_cached_doc,
            patch.object(frappe.db, "commit"),
        ):
            def side_effect(doctype, *a, **kw):
                if doctype == "BP Automation Rule":
                    return [{"name": "R-1", "scope": "project", "project": "PROJ-A", "project_filter": None}]
                return []
            get_all.side_effect = side_effect
            get_cached_doc.return_value.get_completed_statuses.return_value = []
            events.run_overdue_automations()
        filters = _task_call_filters(get_all)
        self.assertEqual(filters.get("is_deleted"), 0)


class TestCreateNotificationAlreadyRevalidatesBeforeDispatch(FrappeTestCase):
    """Pins the pre-existing behavior items 4-5 rely on: _create_notification
    (used by every job above) already re-checks authorization immediately
    before the push/email channels fire, independent of this PR."""

    def test_push_and_email_are_skipped_when_visibility_check_fails(self):
        with (
            patch.object(frappe, "get_doc") as get_doc,
            patch.object(frappe.db, "get_value", return_value="Task Title"),
            patch("batch_projects.notification_delivery.is_notification_visible", return_value=False) as visible,
            patch("batch_projects.push.dispatch") as push_dispatch,
            patch.object(events, "_send_notification_email") as send_email,
            patch.object(events, "_is_muted", return_value=False),
            patch.object(events, "_get_pref", return_value=None),
        ):
            events._create_notification("outsider@example.com", "Due Soon", "TASK-1", "PROJ-A", None, "msg")

        visible.assert_called_once()
        push_dispatch.assert_not_called()
        send_email.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
