"""Live-task scheduled jobs.

Schedulers are a separate read surface from the board/list APIs. They run as a
system user and use ``frappe.get_all`` directly, so permission query conditions
do not hide soft-deleted tasks for them. Every operational scheduled job that
acts on current work must therefore apply ``is_deleted = 0`` itself.

This module is intentionally a narrow adapter around the established event/
email/automation helpers. It fixes the live-task contract without rewriting the
large events.py module or changing user-facing email/automation semantics.
"""

from __future__ import annotations

import frappe

from batch_projects.notification_delivery import (
    can_receive_project_delivery,
    can_receive_task_delivery,
    resolve_system_user,
)
from batch_projects.notification_reads import visible_unread_count


def _live_filters(base=None):
    filters = dict(base or {})
    filters.setdefault("is_deleted", 0)
    return filters


def _current_task_for_user(user: str, task) -> bool:
    """Fail closed if the assignment/access changed while a digest is built."""
    try:
        return can_receive_task_delivery(user, task.name, task.project)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"BP scheduled task visibility check failed: {task.name}",
        )
        return False


def send_due_date_reminders():
    """Daily due/overdue reminders for live, incomplete tasks only."""
    from batch_projects.events import (
        _completed_statuses,
        _create_notification,
        _get_watchers,
        _reminder_sent_today,
    )

    today = frappe.utils.getdate()
    soon_cutoff = frappe.utils.add_days(today, 2)
    tasks = frappe.get_all(
        "BP Task",
        filters=_live_filters({"due_date": ["<=", soon_cutoff]}),
        fields=["name", "task_key", "title", "project", "status", "due_date"],
    )
    completed_cache = {}

    for task in tasks:
        if not task.due_date:
            continue
        completed = completed_cache.get(task.project)
        if completed is None:
            completed = set(_completed_statuses(task.project))
            completed_cache[task.project] = completed
        if task.status in completed:
            continue

        due = frappe.utils.getdate(task.due_date)
        if due < today:
            ntype = "Overdue"
            message = f"{task.task_key} is overdue (due {due}): {task.title}"
        elif due <= soon_cutoff:
            ntype = "Due Soon"
            message = f"{task.task_key} is due {due}: {task.title}"
        else:
            continue

        recipients = set(
            frappe.get_all(
                "BP Task Assignee", filters={"parent": task.name}, pluck="user"
            )
        )
        recipients |= set(_get_watchers(task.name))
        for user in recipients:
            if _reminder_sent_today(user, task.name, ntype):
                continue
            _create_notification(
                user, ntype, task.name, task.project, None, message
            )


def send_daily_digest():
    """One daily email per user, containing only live tasks they can still open."""
    from batch_projects.events import (
        _build_digest_html,
        _completed_statuses,
        _has_outgoing_email,
    )

    if not _has_outgoing_email():
        return

    today = frappe.utils.getdate()
    # Derive candidates from live assignments at the database boundary. A
    # soft-deleted task retains child assignee rows for restore/audit, so a
    # bare scan of BP Task Assignee grows forever with trash history and keeps
    # waking users who no longer have any current work.
    candidates = set(
        frappe.db.sql_list(
            """
            select distinct a.user
            from `tabBP Task Assignee` a
            inner join `tabBP Task` t on t.name = a.parent
            where a.parenttype = 'BP Task'
              and t.is_deleted = 0
            """
        )
    )
    completed_cache = {}

    for candidate in candidates:
        user = resolve_system_user(candidate)
        if not user or user == "Administrator":
            continue

        preference = frappe.db.get_value(
            "BP Notification Preference",
            user,
            ["email_enabled", "email_digest"],
            as_dict=True,
        )
        if preference and (
            not preference.email_enabled or not preference.email_digest
        ):
            continue

        user_row = frappe.db.get_value(
            "User", user, ["email", "full_name"], as_dict=True
        )
        if not user_row or not user_row.email or "@" not in user_row.email:
            continue

        task_names = frappe.get_all(
            "BP Task Assignee", filters={"user": user}, pluck="parent"
        )
        if not task_names:
            continue

        tasks = frappe.get_all(
            "BP Task",
            filters=_live_filters({"name": ["in", task_names]}),
            fields=[
                "name", "task_key", "title", "status", "project",
                "due_date", "priority",
            ],
        )

        due_today = []
        overdue = []
        open_tasks = []
        for task in tasks:
            # Assignment can disappear or a task can move while this scheduler
            # is building a multi-task message. Revalidate from durable state
            # before task metadata enters the email body.
            if not _current_task_for_user(user, task):
                continue

            completed = completed_cache.get(task.project)
            if completed is None:
                completed = set(_completed_statuses(task.project))
                completed_cache[task.project] = completed
            if task.status in completed:
                continue

            open_tasks.append(task)
            if task.due_date:
                due = frappe.utils.getdate(task.due_date)
                if due < today:
                    overdue.append(task)
                elif due == today:
                    due_today.append(task)

        if not open_tasks:
            continue

        # Do not leak stale task-notification existence through the digest badge.
        unread = visible_unread_count(user)
        user_full_name = user_row.full_name or user.split("@")[0].title()
        html = _build_digest_html(
            due_today, overdue, open_tasks, unread, user_full_name
        )

        parts = []
        if overdue:
            parts.append(f"{len(overdue)} overdue")
        if due_today:
            parts.append(f"{len(due_today)} due today")
        if not parts:
            parts.append(f"{len(open_tasks)} open")
        subject = f"batch_projects — {', '.join(parts)}"

        try:
            frappe.sendmail(
                recipients=[user_row.email],
                subject=subject,
                message=html,
                delayed=True,
                retry=1,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "bp daily digest failed")


def send_weekly_project_summary():
    """Weekly project summary using live tasks and current recipient access."""
    from batch_projects.events import (
        _build_weekly_html,
        _completed_statuses,
        _has_outgoing_email,
        _send_notification_email,
    )

    if not _has_outgoing_email():
        return

    today = frappe.utils.getdate()
    week_ago = frappe.utils.add_days(today, -7)
    projects = frappe.get_all(
        "BP Project",
        filters={"status": "Active"},
        fields=["name", "project_name", "key", "lead"],
    )

    for project in projects:
        completed = set(_completed_statuses(project.name))
        tasks = frappe.get_all(
            "BP Task",
            filters=_live_filters({"project": project.name}),
            fields=["status", "due_date", "creation", "completed_on"],
        )
        if not tasks:
            continue

        open_count = sum(1 for task in tasks if task.status not in completed)
        overdue = sum(
            1
            for task in tasks
            if task.status not in completed
            and task.due_date
            and frappe.utils.getdate(task.due_date) < today
        )
        created_week = sum(
            1 for task in tasks if frappe.utils.getdate(task.creation) >= week_ago
        )
        completed_week = sum(
            1
            for task in tasks
            if task.completed_on
            and frappe.utils.getdate(task.completed_on) >= week_ago
        )
        if not (open_count or created_week or completed_week):
            continue

        recipients = set()
        if project.lead:
            recipients.add(project.lead)
        recipients |= set(
            frappe.get_all(
                "BP Project Member",
                filters={
                    "parent": project.name,
                    "role": ["in", ["Admin", "Manager"]],
                },
                pluck="user",
            )
        )

        summary_line = (
            f"{project.project_name}: {completed_week} completed, "
            f"{open_count} open, {overdue} overdue"
        )
        html = _build_weekly_html(
            project.project_name,
            completed_week,
            created_week,
            open_count,
            overdue,
        )

        for candidate in recipients:
            user = resolve_system_user(candidate)
            if not user or user == "Administrator":
                continue
            if not can_receive_project_delivery(user, project.name, "Viewer"):
                continue

            preference = frappe.db.get_value(
                "BP Notification Preference",
                user,
                ["email_enabled", "email_weekly_summary"],
                as_dict=True,
            )
            if preference and (
                not preference.email_enabled
                or not preference.email_weekly_summary
            ):
                continue

            _send_notification_email(
                recipient=user,
                notification_type="Summary",
                task=None,
                task_key=None,
                task_title=None,
                project=project.name,
                actor_name=None,
                message=summary_line,
                message_html=html,
                cta_label="Open project",
            )


def _automation_projects(trigger_event: str):
    from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
        _projects_in_scope,
    )

    rules = frappe.get_all(
        "BP Automation Rule",
        filters={"is_active": 1, "trigger_event": trigger_event},
        fields=["name", "scope", "project", "project_filter"],
    )
    projects = set()
    for rule in rules:
        projects.update(_projects_in_scope(rule))
    return projects


def run_due_soon_automations():
    """Fire due-soon rules only for live tasks."""
    from batch_projects.events import _evaluate_automations

    projects = _automation_projects("task.due_soon")
    if not projects:
        return

    today = frappe.utils.getdate()
    horizon = frappe.utils.add_days(today, 3)
    dedup_after = frappe.utils.add_days(today, -4)

    for project in projects:
        try:
            completed = set(
                frappe.get_cached_doc("BP Project", project).get_completed_statuses()
            )
        except Exception:
            completed = set()

        tasks = frappe.get_all(
            "BP Task",
            filters=_live_filters(
                {
                    "project": project,
                    "due_date": ["between", [str(today), str(horizon)]],
                }
            ),
            fields=["name", "task_key", "status"],
        )
        for task in tasks:
            if task.status in completed:
                continue
            if frappe.db.exists(
                "BP Automation Run",
                {
                    "task": task.name,
                    "trigger_event": "task.due_soon",
                    "run_at": [">", dedup_after],
                },
            ):
                continue
            # Re-check the soft-delete bit immediately before the automation
            # event in case trash raced the initial scheduler query.
            if frappe.db.get_value("BP Task", task.name, "is_deleted"):
                continue
            try:
                _evaluate_automations(
                    "task.due_soon",
                    {
                        "event": "task.due_soon",
                        "project": project,
                        "task": task.name,
                        "task_key": task.task_key,
                    },
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"due_soon automation failed: {task.name}",
                )
    frappe.db.commit()


def run_overdue_automations():
    """Fire overdue rules only for live tasks."""
    from batch_projects.events import _evaluate_automations

    projects = _automation_projects("task.overdue")
    if not projects:
        return

    today = frappe.utils.getdate()
    dedup_after = frappe.utils.add_days(today, -1)

    for project in projects:
        try:
            completed = set(
                frappe.get_cached_doc("BP Project", project).get_completed_statuses()
            )
        except Exception:
            completed = set()

        tasks = frappe.get_all(
            "BP Task",
            filters=_live_filters(
                {"project": project, "due_date": ["<", str(today)]}
            ),
            fields=["name", "task_key", "status"],
        )
        for task in tasks:
            if task.status in completed:
                continue
            if frappe.db.exists(
                "BP Automation Run",
                {
                    "task": task.name,
                    "trigger_event": "task.overdue",
                    "run_at": [">", dedup_after],
                },
            ):
                continue
            if frappe.db.get_value("BP Task", task.name, "is_deleted"):
                continue
            try:
                _evaluate_automations(
                    "task.overdue",
                    {
                        "event": "task.overdue",
                        "project": project,
                        "task": task.name,
                        "task_key": task.task_key,
                    },
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"overdue automation failed: {task.name}",
                )
    frappe.db.commit()
