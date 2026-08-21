"""Authorization side effects of project membership changes.

A BP Task Watcher row is a delivery subscription, never an access grant. If a
user loses project membership, a stale watcher must not continue routing task
notifications unless another authorization edge (task assignment or instance
admin) still lets that user see the task.
"""

from __future__ import annotations

import frappe


# Mirrors task_invariants.py's _user_row / _user_can_view_task (not yet landed
# on develop-15 as of this PR — inlined here rather than taking on a
# dependency this fix doesn't otherwise need). Reconcile into a single shared
# definition once task_invariants.py merges.
def _user_row(user: str):
    if not user:
        return None
    return frappe.db.get_value(
        "User", user, ["name", "full_name", "enabled", "user_type"], as_dict=True
    )


def _user_can_view_task(project: str, task: str | None, user: str) -> bool:
    """Whether ``user`` already has authority to see this task."""
    from batch_projects import access

    row = _user_row(user)
    if not row or not row.enabled or row.user_type != "System User":
        return False
    if access.is_instance_admin(user):
        return True
    if access.has_at_least(project, "Viewer", user):
        return True
    return bool(task and access.is_task_assignee(task, user))


def prune_stale_watchers(project: str, users=None) -> list[str]:
    """Delete watcher rows whose user can no longer view their live task."""
    filters = {"project": project}
    if users is not None:
        users = {u for u in users if u}
        if not users:
            return []
        filters["user"] = ["in", sorted(users)]

    rows = frappe.get_all(
        "BP Task Watcher",
        filters=filters,
        fields=["name", "task", "user"],
    )
    if not rows:
        return []

    removed = []
    for row in rows:
        task = frappe.db.get_value(
            "BP Task", row.task, ["name", "project", "is_deleted"], as_dict=True
        )
        if not task:
            frappe.db.delete("BP Task Watcher", {"name": row.name})
            removed.append(row.name)
            continue

        # Preserve subscriptions across soft trash so restore returns the task
        # to the same followers. Revocation is evaluated against the live task
        # only; task_lifecycle owns trash/restore visibility.
        if task.is_deleted:
            continue

        if task.project != project or not _user_can_view_task(task.project, task.name, row.user):
            frappe.db.delete("BP Task Watcher", {"name": row.name})
            removed.append(row.name)
    return removed


@frappe.whitelist()
def update_project_members(project, members):
    """Preserve the existing API while applying revocation side effects.

    The real mutation's own authority check (Admin-only, api/board.py's
    update_project_members) is unchanged and still authoritative — this
    adapter only adds watcher cleanup around it, not a second authority gate.
    """
    before = set(
        frappe.get_all("BP Project Member", filters={"parent": project}, pluck="user")
    )

    # Direct Python call intentionally bypasses override_whitelisted_methods and
    # invokes the legacy implementation once. It remains authoritative for the
    # membership mutation itself; this adapter owns only access-revocation
    # cleanup around it.
    from batch_projects.api import board
    result = board.update_project_members(project, members)

    after = set(
        frappe.get_all("BP Project Member", filters={"parent": project}, pluck="user")
    )
    removed_users = before - after
    if removed_users:
        prune_stale_watchers(project, removed_users)
        frappe.db.commit()
    return result


def after_project_member_delete(doc, method=None):
    """Catch ORM/REST child-row deletion outside update_project_members.

    ``after_delete`` runs after the membership DELETE has been issued but before
    the surrounding transaction commits. The access check therefore sees the
    new membership graph immediately, and watcher cleanup commits atomically
    with the revocation instead of opening a nested post-commit transaction.
    """
    try:
        prune_stale_watchers(doc.parent, {doc.user})
    except Exception:
        # Do not silently commit a revocation while leaving a known stale
        # delivery subscription behind. Propagate after logging so the caller's
        # transaction rolls back and the graph remains internally consistent.
        frappe.log_error(
            frappe.get_traceback(),
            "bp watcher revocation cleanup failed",
        )
        raise
