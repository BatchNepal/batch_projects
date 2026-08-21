"""Task mutation invariants enforced at the durable DocType boundary.

The SPA, REST API, imports, automations and direct ORM writes can all mutate
BP Task. High-blast-radius rules therefore live here rather than in one UI
or endpoint so equivalent task states always produce equivalent validation
and authorization side effects.
"""

from __future__ import annotations

import re

import frappe


_RESERVED_ASSIGNEES = {"Guest", "Administrator"}
_MENTION_RE = re.compile(r"@\[[^\]]+\]\(([^)]+)\)")
_PROJECT_RELATIONS = {
    "epic": ("BP Epic", "project", "Epic"),
    "milestone": ("BP Milestone", "project", "Milestone"),
}


def _user_row(user: str):
    if not user:
        return None
    return frappe.db.get_value(
        "User", user, ["name", "full_name", "enabled", "user_type"], as_dict=True
    )


def _assert_assignable_user(user: str):
    """Return the User row or fail closed when ``user`` cannot own task work."""
    row = _user_row(user)
    if (
        not row
        or user in _RESERVED_ASSIGNEES
        or not row.enabled
        or row.user_type != "System User"
    ):
        frappe.throw(
            f"{user or 'This user'} cannot be assigned this task. "
            "Assignees must be enabled System Users.",
            frappe.ValidationError,
            title="User is not assignable",
        )
    return row


def _assignee_users(doc) -> list[str]:
    if not doc:
        return []
    return [row.user for row in (doc.get("assignees") or []) if row.user]


def _mention_users(text) -> set[str]:
    if not text:
        return set()
    return {uid.strip() for uid in _MENTION_RE.findall(str(text)) if uid.strip()}


def _user_can_view_task(project: str, task: str | None, user: str, pending_assignees=()) -> bool:
    """Whether ``user`` already has authority to see this task.

    Mentioning somebody is not an access-grant operation. A target qualifies
    through normal project Viewer access, an already-durable task-assignee
    edge, or an assignee edge being created in the same task save.
    """
    from batch_projects import access

    row = _user_row(user)
    if not row or not row.enabled or row.user_type != "System User":
        return False
    if access.is_instance_admin(user):
        return True
    if access.has_at_least(project, "Viewer", user):
        return True
    if user in set(pending_assignees or ()):
        return True
    return bool(task and access.is_task_assignee(task, user))


def _assert_new_mentions_authorized(
    *, project: str, task: str | None, before, after, pending_assignees=()
) -> None:
    new_mentions = _mention_users(after) - _mention_users(before)
    for user in sorted(new_mentions):
        if not _user_can_view_task(project, task, user, pending_assignees):
            frappe.throw(
                f"{user} cannot be mentioned on this task because they do not "
                "currently have access to it. Assign them or add them to the "
                "project first.",
                frappe.PermissionError,
                title="Mention recipient has no task access",
            )


def before_task_insert(doc, method=None):
    """Reserved insertion boundary for the default-assignee cutover.

    The legacy task.created notification still treats BP Project.default_assignee
    as if it were a real assignment. Materializing it here before that handler
    is removed would double-notify the user, so the cutover is intentionally
    performed later as one atomic event-layer change.
    """
    return None


def validate_task_assignees(doc, method=None):
    """Enforce assignment, relationship, mention and ReBAC move invariants."""
    old = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
    new_users = _assignee_users(doc)
    old_users = _assignee_users(old)

    # Legacy unchanged rows are grandfathered: editing a title must not fail
    # because a years-old assignment points at a now-disabled account. Any
    # newly-created edge is strict, and the final set may never duplicate.
    if new_users != old_users or not old:
        if len(new_users) != len(set(new_users)):
            duplicate = next(user for user in new_users if new_users.count(user) > 1)
            frappe.throw(
                f"{duplicate} is assigned more than once.",
                frappe.ValidationError,
                title="Duplicate assignee",
            )
        old_set = set(old_users)
        for assignee in doc.get("assignees") or []:
            user = assignee.user
            if user in old_set:
                continue
            row = _assert_assignable_user(user)
            assignee.full_name = row.full_name or user

    _validate_project_relations(doc)

    _assert_new_mentions_authorized(
        project=doc.project,
        task=doc.name if not doc.is_new() else None,
        before=(old.description if old else ""),
        after=doc.description,
        pending_assignees=new_users,
    )

    # Project moves are permission-graph mutations. Queue the sync only after
    # the DB transaction commits; a validation/save failure must never mutate
    # OpenFGA ahead of MariaDB, which remains the durable authority.
    if old and old.project and old.project != doc.project:
        old_project = old.project
        new_project = doc.project
        task = doc.name

        def _sync_project_move():
            try:
                from batch_projects import bridge

                bridge.publish_rebac_event({
                    "event": "task.project_changed",
                    "task": task,
                    "old_project": old_project,
                    "project": new_project,
                    "timestamp": frappe.utils.now(),
                })
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(), "bp rebac task project-change sync failed"
                )

        frappe.db.after_commit.add(_sync_project_move)


def _validate_project_relations(doc) -> None:
    """Fail closed on project-local links that point across project boundaries."""
    for field, (doctype, project_field, label) in _PROJECT_RELATIONS.items():
        value = doc.get(field)
        if not value:
            continue
        target_project = frappe.db.get_value(doctype, value, project_field)
        if not target_project:
            frappe.throw(
                f"{label} '{value}' does not exist.",
                frappe.ValidationError,
                title=f"Invalid {label.lower()}",
            )
        if target_project != doc.project:
            frappe.throw(
                f"{label} '{value}' belongs to another project.",
                frappe.ValidationError,
                title=f"Cross-project {label.lower()} not allowed",
            )

    if doc.parent_task:
        if doc.name and doc.parent_task == doc.name:
            frappe.throw("A task cannot be its own parent.", frappe.ValidationError)
        parent = frappe.db.get_value(
            "BP Task", doc.parent_task, ["project", "parent_task", "is_deleted"], as_dict=True
        )
        if not parent or parent.is_deleted:
            frappe.throw("Parent task does not exist or is in trash.", frappe.ValidationError)
        if parent.project != doc.project:
            frappe.throw("Parent task belongs to another project.", frappe.ValidationError)

        # Walk upward to prevent A -> B -> A (and longer) cycles. Bound the
        # traversal so corrupted legacy data cannot make validation hang.
        ancestor = parent.parent_task
        seen = {doc.parent_task}
        for _ in range(1000):
            if not ancestor:
                break
            if ancestor == doc.name or ancestor in seen:
                frappe.throw("Task hierarchy cannot contain a cycle.", frappe.ValidationError)
            seen.add(ancestor)
            ancestor = frappe.db.get_value("BP Task", ancestor, "parent_task")
        else:
            frappe.throw("Task hierarchy is too deep to validate safely.", frappe.ValidationError)

    if doc.sprint:
        sprint = frappe.db.get_value(
            "BP Sprint", doc.sprint, ["project", "team", "sprint_type"], as_dict=True
        )
        if not sprint:
            frappe.throw("Sprint does not exist.", frappe.ValidationError)
        if sprint.project:
            if sprint.project != doc.project:
                frappe.throw("Sprint belongs to another project.", frappe.ValidationError)
        else:
            project_team = frappe.db.get_value("BP Project", doc.project, "team")
            if not sprint.team or sprint.team != project_team:
                frappe.throw(
                    "Team sprint does not belong to this project's team.",
                    frappe.ValidationError,
                )


def validate_comment_mentions(activity) -> None:
    """Validate newly-added @mentions in a BP Activity Comment."""
    if activity.action_type != "Comment" or not activity.task:
        return
    task = frappe.db.get_value("BP Task", activity.task, ["project", "name"], as_dict=True)
    if not task:
        frappe.throw("Comment task no longer exists.", frappe.ValidationError)
    old = activity.get_doc_before_save() if hasattr(activity, "get_doc_before_save") else None
    _assert_new_mentions_authorized(
        project=task.project,
        task=task.name,
        before=(old.comment_text if old else ""),
        after=activity.comment_text,
    )


def after_task_insert(doc, method=None):
    """Emit normal assignment lifecycle events for assignees present at birth."""
    if not doc.get("assignees"):
        return

    from batch_projects.events import TASK_ASSIGNED, emit

    actor_name = (
        frappe.db.get_value("User", frappe.session.user, "full_name")
        or frappe.session.user
    )

    for assignee in doc.assignees:
        full_name = assignee.full_name or assignee.user
        frappe.get_doc(
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
        emit(
            TASK_ASSIGNED,
            {
                "project": doc.project,
                "task": doc.name,
                "task_key": doc.task_key,
                "assignee": assignee.user,
                "full_name": full_name,
                "title": doc.title,
                "actor_name": actor_name,
                "initial_assignment": True,
            },
        )
