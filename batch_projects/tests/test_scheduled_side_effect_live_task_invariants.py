"""Regression coverage for scheduled-job live-task filtering and per-path
delivery revalidation.

Recovered gaps (BatchProjects git-audit, P1 #1-#3): the daily/weekly
scheduled jobs that generate reminders, digests, and due-soon/overdue
automation triggers queried BP Task with no is_deleted filter at all, so a
trashed task could still nag its former assignees/watchers or fire an
automation rule.

Correction (per independent validation): the original version of this
module claimed items 4-5 ("derive recipients from current live
assignments", "revalidate authorization immediately before sending") were
already satisfied because every job here routes through
events._create_notification. That is true only for send_due_date_reminders
— send_daily_digest calls frappe.sendmail directly, send_weekly_project_
summary calls _send_notification_email directly, and run_due_soon_
automations/run_overdue_automations call _evaluate_automations directly.
None of those three paths ever reached _create_notification, so none of
them got its is_notification_visible recheck. Each is now revalidated
directly at its own dispatch point instead; see TestDailyDigestRevalidates,
TestWeeklySummaryRevalidates and TestScheduledAutomationsRevalidate below,
plus the (still valid, for send_due_date_reminders specifically)
TestCreateNotificationAlreadyRevalidatesBeforeDispatch.

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


def _digest_task(name, project="PROJ-A", status="Open", due_date=None):
    return frappe._dict(name=name, task_key=name, title=name, status=status, project=project, due_date=due_date, priority="Medium")


class TestDailyDigestRevalidates(FrappeTestCase):
    """send_daily_digest calls frappe.sendmail directly — it never reached
    _create_notification's is_notification_visible gate. Each task is now
    rechecked via notification_delivery.can_receive_task_delivery at the
    point the digest actually includes it, and again immediately before
    frappe.sendmail."""

    def test_excludes_a_task_whose_access_was_revoked_after_candidate_query(self):
        tasks = [_digest_task("TASK-1")]
        with (
            patch.object(events, "_has_outgoing_email", return_value=True),
            patch.object(frappe.db, "sql_list", return_value=["alice@example.com"]),
            patch("batch_projects.notification_delivery.resolve_system_user", side_effect=lambda u: u),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(frappe, "get_all", return_value=tasks),
            patch("batch_projects.notification_delivery.can_receive_task_delivery", return_value=False),
            patch("batch_projects.notification_reads.visible_unread_count") as unread_mock,
            patch.object(events, "_build_digest_html", return_value="<html></html>"),
            patch.object(frappe, "sendmail") as sendmail,
        ):
            events.send_daily_digest()
        sendmail.assert_not_called()
        unread_mock.assert_not_called()  # never got far enough to build a digest at all

    def test_excludes_a_task_trashed_after_candidate_query(self):
        """Mechanically identical to a revoked-access recheck failure —
        can_receive_task_delivery re-reads BP Task.is_deleted fresh at call
        time, so a task trashed after the initial query is caught the same
        way a permission change would be."""
        tasks = [_digest_task("TASK-1")]
        with (
            patch.object(events, "_has_outgoing_email", return_value=True),
            patch.object(frappe.db, "sql_list", return_value=["alice@example.com"]),
            patch("batch_projects.notification_delivery.resolve_system_user", side_effect=lambda u: u),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(frappe, "get_all", return_value=tasks),
            patch("batch_projects.notification_delivery.can_receive_task_delivery", return_value=False),
            patch.object(frappe, "sendmail") as sendmail,
        ):
            events.send_daily_digest()
        sendmail.assert_not_called()

    def test_uses_visible_unread_count_not_a_raw_notification_count(self):
        tasks = [_digest_task("TASK-1")]
        with (
            patch.object(events, "_has_outgoing_email", return_value=True),
            patch.object(frappe.db, "sql_list", return_value=["alice@example.com"]),
            patch("batch_projects.notification_delivery.resolve_system_user", side_effect=lambda u: u),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(frappe.db, "count") as raw_count,
            patch.object(frappe, "get_all", return_value=tasks),
            patch("batch_projects.notification_delivery.can_receive_task_delivery", return_value=True),
            patch("batch_projects.notification_reads.visible_unread_count", return_value=7) as unread_mock,
            patch.object(events, "_build_digest_html", return_value="<html></html>") as build_html,
            patch.object(frappe, "sendmail"),
        ):
            events.send_daily_digest()
        unread_mock.assert_called_once_with("alice@example.com")
        raw_count.assert_not_called()
        self.assertEqual(build_html.call_args.args[3], 7)

    def test_sends_immediately_not_delayed_and_skips_when_final_allowed_set_is_empty(self):
        tasks = [_digest_task("TASK-1")]
        # First call (assembly loop) allows the task; second call (final
        # recheck immediately before send) denies it — proves the second
        # recheck is a real, independent gate, not just re-running the same
        # cached decision.
        with (
            patch.object(events, "_has_outgoing_email", return_value=True),
            patch.object(frappe.db, "sql_list", return_value=["alice@example.com"]),
            patch("batch_projects.notification_delivery.resolve_system_user", side_effect=lambda u: u),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(frappe, "get_all", return_value=tasks),
            patch(
                "batch_projects.notification_delivery.can_receive_task_delivery",
                side_effect=[True, False],
            ),
            patch("batch_projects.notification_reads.visible_unread_count", return_value=0),
            patch.object(events, "_build_digest_html", return_value="<html></html>"),
            patch.object(frappe, "sendmail") as sendmail,
        ):
            events.send_daily_digest()
        sendmail.assert_not_called()

    def test_sendmail_called_with_delayed_false(self):
        tasks = [_digest_task("TASK-1")]
        with (
            patch.object(events, "_has_outgoing_email", return_value=True),
            patch.object(frappe.db, "sql_list", return_value=["alice@example.com"]),
            patch("batch_projects.notification_delivery.resolve_system_user", side_effect=lambda u: u),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(frappe, "get_all", return_value=tasks),
            patch("batch_projects.notification_delivery.can_receive_task_delivery", return_value=True),
            patch("batch_projects.notification_reads.visible_unread_count", return_value=0),
            patch.object(events, "_build_digest_html", return_value="<html></html>"),
            patch.object(frappe, "sendmail") as sendmail,
        ):
            events.send_daily_digest()
        sendmail.assert_called_once()
        self.assertEqual(sendmail.call_args.kwargs.get("delayed"), False)


class TestWeeklySummaryRevalidates(FrappeTestCase):
    def test_skips_a_manager_who_loses_project_access_after_candidate_query(self):
        project_row = frappe._dict(name="PROJ-A", project_name="Proj A", key="PA", lead="lead@example.com")
        with (
            patch.object(events, "_has_outgoing_email", return_value=True),
            patch.object(frappe, "get_all") as get_all,
            patch.object(events, "_completed_statuses", return_value=[]),
            patch("batch_projects.notification_delivery.resolve_system_user", side_effect=lambda u: u),
            patch("batch_projects.notification_delivery.can_receive_project_delivery", return_value=False) as can_deliver,
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(events, "_send_notification_email") as send_email,
        ):
            def side_effect(doctype, *a, **kw):
                if doctype == "BP Project":
                    return [project_row]
                if doctype == "BP Task":
                    return [frappe._dict(status="Open", due_date=None, creation=frappe.utils.now(), completed_on=None)]
                return []
            get_all.side_effect = side_effect
            events.send_weekly_project_summary()
        can_deliver.assert_called_once_with("lead@example.com", "PROJ-A", "Viewer")
        send_email.assert_not_called()

    def test_authorization_exception_fails_closed(self):
        project_row = frappe._dict(name="PROJ-A", project_name="Proj A", key="PA", lead="lead@example.com")
        with (
            patch.object(events, "_has_outgoing_email", return_value=True),
            patch.object(frappe, "get_all") as get_all,
            patch.object(events, "_completed_statuses", return_value=[]),
            patch("batch_projects.notification_delivery.resolve_system_user", side_effect=lambda u: u),
            patch(
                "batch_projects.notification_delivery.can_receive_project_delivery",
                side_effect=RuntimeError("boom"),
            ),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(frappe, "log_error") as log_error,
            patch.object(events, "_send_notification_email") as send_email,
        ):
            def side_effect(doctype, *a, **kw):
                if doctype == "BP Project":
                    return [project_row]
                if doctype == "BP Task":
                    return [frappe._dict(status="Open", due_date=None, creation=frappe.utils.now(), completed_on=None)]
                return []
            get_all.side_effect = side_effect
            events.send_weekly_project_summary()
        log_error.assert_called_once()
        send_email.assert_not_called()


class TestScheduledAutomationsRevalidate(FrappeTestCase):
    def test_due_soon_skips_a_task_trashed_between_query_and_dispatch(self):
        with (
            patch(
                "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._projects_in_scope",
                return_value={"PROJ-A"},
            ),
            patch.object(frappe, "get_all") as get_all,
            patch.object(frappe, "get_cached_doc") as get_cached_doc,
            patch.object(frappe.db, "exists", return_value=False),
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(is_deleted=1, project="PROJ-A"),
            ),
            patch.object(events, "_evaluate_automations") as evaluate,
            patch.object(frappe.db, "commit"),
        ):
            def side_effect(doctype, *a, **kw):
                if doctype == "BP Automation Rule":
                    return [frappe._dict(name="R-1", scope="project", project="PROJ-A", project_filter=None)]
                if doctype == "BP Task":
                    return [frappe._dict(name="TASK-1", task_key="BP-1", status="Open")]
                return []
            get_all.side_effect = side_effect
            get_cached_doc.return_value.get_completed_statuses.return_value = []
            events.run_due_soon_automations()
        evaluate.assert_not_called()

    def test_overdue_skips_a_task_trashed_between_query_and_dispatch(self):
        with (
            patch(
                "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._projects_in_scope",
                return_value={"PROJ-A"},
            ),
            patch.object(frappe, "get_all") as get_all,
            patch.object(frappe, "get_cached_doc") as get_cached_doc,
            patch.object(frappe.db, "exists", return_value=False),
            patch.object(
                frappe.db, "get_value",
                return_value=frappe._dict(is_deleted=1, project="PROJ-A"),
            ),
            patch.object(events, "_evaluate_automations") as evaluate,
            patch.object(frappe.db, "commit"),
        ):
            def side_effect(doctype, *a, **kw):
                if doctype == "BP Automation Rule":
                    return [frappe._dict(name="R-1", scope="project", project="PROJ-A", project_filter=None)]
                if doctype == "BP Task":
                    return [frappe._dict(name="TASK-1", task_key="BP-1", status="Open")]
                return []
            get_all.side_effect = side_effect
            get_cached_doc.return_value.get_completed_statuses.return_value = []
            events.run_overdue_automations()
        evaluate.assert_not_called()

    def test_due_soon_skips_a_task_moved_to_another_project(self):
        with (
            patch(
                "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._projects_in_scope",
                return_value={"PROJ-A"},
            ),
            patch.object(frappe, "get_all") as get_all,
            patch.object(frappe, "get_cached_doc") as get_cached_doc,
            patch.object(frappe.db, "exists", return_value=False),
            patch.object(
                frappe.db, "get_value",
                # Moved to a different project than the one this scan is for.
                return_value=frappe._dict(is_deleted=0, project="PROJ-B"),
            ),
            patch.object(events, "_evaluate_automations") as evaluate,
            patch.object(frappe.db, "commit"),
        ):
            def side_effect(doctype, *a, **kw):
                if doctype == "BP Automation Rule":
                    return [frappe._dict(name="R-1", scope="project", project="PROJ-A", project_filter=None)]
                if doctype == "BP Task":
                    return [frappe._dict(name="TASK-1", task_key="BP-1", status="Open")]
                return []
            get_all.side_effect = side_effect
            get_cached_doc.return_value.get_completed_statuses.return_value = []
            events.run_due_soon_automations()
        evaluate.assert_not_called()

    def test_due_soon_skips_a_task_that_no_longer_exists(self):
        with (
            patch(
                "batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule._projects_in_scope",
                return_value={"PROJ-A"},
            ),
            patch.object(frappe, "get_all") as get_all,
            patch.object(frappe, "get_cached_doc") as get_cached_doc,
            patch.object(frappe.db, "exists", return_value=False),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(events, "_evaluate_automations") as evaluate,
            patch.object(frappe.db, "commit"),
        ):
            def side_effect(doctype, *a, **kw):
                if doctype == "BP Automation Rule":
                    return [frappe._dict(name="R-1", scope="project", project="PROJ-A", project_filter=None)]
                if doctype == "BP Task":
                    return [frappe._dict(name="TASK-1", task_key="BP-1", status="Open")]
                return []
            get_all.side_effect = side_effect
            get_cached_doc.return_value.get_completed_statuses.return_value = []
            events.run_due_soon_automations()
        evaluate.assert_not_called()


class TestCreateNotificationAlreadyRevalidatesBeforeDispatch(FrappeTestCase):
    """Pins the pre-existing behavior send_due_date_reminders (specifically
    — not the other jobs above, see the module docstring) relies on:
    _create_notification already re-checks authorization immediately
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
            # The idempotency guard queries the DB via frappe.db.exists, which
            # internally uses the get_value patch above — pin it to "not seen"
            # so this test exercises the visibility gate, not the dedup gate.
            patch.object(events, "_dedup_seen", return_value=False),
        ):
            events._create_notification("outsider@example.com", "Due Soon", "TASK-1", "PROJ-A", None, "msg")

        visible.assert_called_once()
        push_dispatch.assert_not_called()
        send_email.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
