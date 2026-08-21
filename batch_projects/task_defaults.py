"""Project default-assignee materialization.

Historically ``BP Project.default_assignee`` only caused a task.created
notification. The task itself remained unassigned, so authorization, My Tasks,
automation matching, watchers and ReBAC all disagreed with what the notification
claimed. This module turns the configured default into a real BP Task Assignee
edge before insert.

The legacy task.created notification is deliberately retained for this cutover.
For the one auto-materialized edge we therefore dispatch the real task.assigned
lifecycle *without* its built-in notification; that gives us assignment
activity, automation, realtime, watcher and ReBAC semantics with exactly one
human notification instead of two.
"""

from __future__ import annotations

import frappe

from batch_projects import task_invariants

_FLAG = "bp_default_assignee_materialized"


def _flag_value(doc):
    flags = getattr(doc, "flags", None)
    if not flags:
        return None
    return flags.get(_FLAG)


def before_task_insert(doc, method=None):
    """Materialize the project default only when the caller supplied no assignee."""
    if task_invariants._assignee_users(doc):
        return

    default_user = frappe.db.get_value("BP Project", doc.project, "default_assignee")
    if not default_user:
        return

    user = task_invariants._assert_assignable_user(default_user)
    doc.append(
        "assignees",
        {"user": default_user, "full_name": user.full_name or default_user},
    )
    doc.flags[_FLAG] = default_user


def validate_materialized_default(doc) -> bool:
    """Validate the one policy-created assignment edge.

    Returns True when this is the exact before_insert edge this module created,
    allowing task_validation to skip only the ordinary actor assignment-authority
    check. Every other task invariant still runs. The marker cannot be used as a
    generic bypass: the configured project default and complete assignee set must
    match it exactly.
    """
    default_user = _flag_value(doc)
    if not default_user:
        return False
    if not doc.is_new():
        frappe.throw("Default-assignee materialization is insert-only.", frappe.ValidationError)

    configured = frappe.db.get_value("BP Project", doc.project, "default_assignee")
    users = task_invariants._assignee_users(doc)
    if configured != default_user or users != [default_user]:
        frappe.throw(
            "The materialized default assignment no longer matches the project configuration.",
            frappe.ValidationError,
            title="Invalid default assignment",
        )

    row = task_invariants._assert_assignable_user(default_user)
    doc.assignees[0].full_name = row.full_name or default_user

    # Equivalent to validate_task_assignees() for an insert except for its
    # actor-authority check. The grant is authorized by the project's durable
    # Admin/Manager configuration, not by whichever Member happened to create
    # this particular task.
    task_invariants._validate_task_type(doc, None)
    task_invariants._validate_project_relations(doc, None)
    task_invariants._validate_task_links(doc, None)
    task_invariants._validate_pending_approver(doc, None, users)
    task_invariants._assert_new_mentions_authorized(
        project=doc.project,
        task=None,
        before="",
        after=doc.description,
        pending_assignees=users,
    )
    return True


def _assignment_activity(doc, assignee, full_name):
    return frappe.get_doc(
        {
            "doctype": "BP Activity",
            "task": doc.name,
            "project": doc.project,
            "task_key": doc.task_key,
            "action_type": "Assignment",
            "field_name": "",
            "old_value": "",
            "new_value": full_name,
            "user": frappe.session.user,
        }
    ).insert(ignore_permissions=True)


def _dispatch_without_builtin_notification(event_name: str, payload: dict):
    """Run the normal durable event pipeline except built-in notification fanout."""
    from batch_projects import events

    payload = events._enrich(event_name, payload)
    events._invalidate_cache(event_name, payload)
    events._broadcast(event_name, payload)
    events._evaluate_automations(event_name, payload)
    events._sync_rebac(event_name, payload)


def after_task_insert(doc, method=None):
    default_user = _flag_value(doc)
    if not default_user:
        # Explicit initial assignees keep the ordinary lifecycle, including the
        # ordinary assignment notification for each assignee.
        return task_invariants.after_task_insert(doc, method=method)

    users = task_invariants._assignee_users(doc)
    configured = frappe.db.get_value("BP Project", doc.project, "default_assignee")
    if configured != default_user or users != [default_user]:
        # Validation should make this unreachable; fail closed rather than emit
        # a permission edge for a state we did not prove.
        frappe.throw("Default assignment changed before insert completed.", frappe.ValidationError)

    assignee = doc.assignees[0]
    full_name = assignee.full_name or default_user
    _assignment_activity(doc, default_user, full_name)

    from batch_projects import events
    events.add_watcher(doc.name, default_user, reason="assigned")

    actor_name = (
        frappe.db.get_value("User", frappe.session.user, "full_name")
        or frappe.session.user
    )
    _dispatch_without_builtin_notification(
        events.TASK_ASSIGNED,
        {
            "project": doc.project,
            "task": doc.name,
            "task_key": doc.task_key,
            "assignee": default_user,
            "full_name": full_name,
            "title": doc.title,
            "actor_name": actor_name,
            "initial_assignment": True,
            "default_assignment": True,
        },
    )
