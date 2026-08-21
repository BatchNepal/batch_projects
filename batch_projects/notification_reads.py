"""Authorization-aware reads for the in-app notification center.

A notification can be perfectly valid when created and become sensitive later:
a user may be removed from a private project, unassigned from their only task
access, or the task may move to another project. Persisted notification rows
therefore cannot be treated as permanently readable just because
``recipient == session.user``.

All notification-center pagination and badge counts are computed from the
currently-authorized set so hidden stale rows cannot leak through metadata such
as a larger unread count or create short/empty pages after post-filtering.
"""

from __future__ import annotations

import frappe

from batch_projects.notification_delivery import is_notification_visible

_DISPLAY_FIELDS = [
    "name", "notification_type", "task", "task_key", "task_title",
    "project", "actor", "actor_name", "message", "is_read", "read_at",
    "creation",
]


def _require_system_user() -> None:
    # Reuse the existing gateway + System User request boundary without
    # importing it at module import time (board.py is large and imports events).
    from batch_projects.api.board import _require_system_user as require
    require()


def _is_visible(row, user: str) -> bool:
    """Current read authority for one persisted notification row."""
    return is_notification_visible(row, user)


def _candidate_rows(user: str, *, unread_only=False, on_date=None):
    filters = {"recipient": user}
    if frappe.utils.cint(unread_only):
        filters["is_read"] = 0
    if on_date:
        day = frappe.utils.getdate(on_date)
        filters["creation"] = [
            "between",
            [f"{day} 00:00:00", f"{day} 23:59:59"],
        ]
    return frappe.get_all(
        "BP Notification",
        filters=filters,
        fields=["name", "notification_type", "task", "project", "is_read", "creation"],
        order_by="creation desc",
        limit_page_length=0,
    )


def _visible_rows(user: str, *, unread_only=False, on_date=None):
    """Return candidate metadata filtered against current authorization.

    Cache one decision per (task, project) inside this pass: a noisy task can
    have dozens of notifications but requires only one access evaluation.
    """
    decisions = {}
    out = []
    for row in _candidate_rows(user, unread_only=unread_only, on_date=on_date):
        task = row.get("task")
        if task:
            key = ("task", task, row.get("project"))
        elif row.get("notification_type") == "Task Deleted" and row.get("project"):
            key = ("deleted", row.get("project"))
        else:
            key = ("other", row.name)

        if key not in decisions:
            try:
                decisions[key] = _is_visible(row, user)
            except Exception:
                # Access subsystem trouble must hide task metadata, never expose
                # it. Task-less unrelated notifications remain governed by their
                # own contracts and _is_visible returns True without DB access.
                frappe.log_error(
                    frappe.get_traceback(),
                    "bp notification read authorization failed",
                )
                decisions[key] = False
        if decisions[key]:
            out.append(row)
    return out


def _visible_unread_count(user: str) -> int:
    return len(_visible_rows(user, unread_only=True))


def visible_unread_count(user: str) -> int:
    """Public scheduler-safe unread count using current notification access.

    Scheduled emails are generated outside a browser session, so they cannot
    call the whitelisted ``get_notification_count`` endpoint. Keep one public
    server-side primitive instead of letting schedulers fall back to a raw
    ``frappe.db.count`` that includes notifications the user can no longer read.
    """
    if not user:
        return 0
    return _visible_unread_count(user)


def _visible_notification(notification: str, user: str):
    row = frappe.db.get_value(
        "BP Notification",
        {"name": notification, "recipient": user},
        ["name", "notification_type", "task", "project", "is_read"],
        as_dict=True,
    )
    if not row:
        frappe.throw("Notification not found.", frappe.DoesNotExistError)
    if not _is_visible(row, user):
        # Do not distinguish "exists but revoked" from "not yours" at this
        # boundary; callers should not gain a notification-existence oracle.
        frappe.throw("Notification not found.", frappe.DoesNotExistError)
    return row


@frappe.whitelist()
def get_notifications(limit=30, offset=0, unread_only=False, on_date=None):
    """Current user's currently-authorized notifications, newest first."""
    _require_system_user()
    if not frappe.db.table_exists("BP Notification"):
        return {"notifications": [], "unread_count": 0, "total": 0}

    user = frappe.session.user
    visible = _visible_rows(user, unread_only=unread_only, on_date=on_date)
    total = len(visible)
    start = max(frappe.utils.cint(offset), 0)
    size = max(frappe.utils.cint(limit) or 30, 1)
    page = visible[start:start + size]
    names = [row.name for row in page]

    notifications = []
    if names:
        fetched = frappe.get_all(
            "BP Notification",
            filters={"name": ["in", names], "recipient": user},
            fields=_DISPLAY_FIELDS,
            limit_page_length=0,
        )
        by_name = {row.name: row for row in fetched}
        notifications = [by_name[name] for name in names if name in by_name]

    return {
        "notifications": notifications,
        "unread_count": _visible_unread_count(user),
        "total": total,
    }


@frappe.whitelist()
def get_notification_count():
    """Sidebar badge count with the same revocation semantics as the list."""
    _require_system_user()
    if not frappe.db.table_exists("BP Notification"):
        return {"unread_count": 0}
    return {"unread_count": _visible_unread_count(frappe.session.user)}


@frappe.whitelist()
def mark_notification_read(notification):
    _require_system_user()
    if not frappe.db.table_exists("BP Notification"):
        return {"ok": True, "unread_count": 0}
    user = frappe.session.user
    row = _visible_notification(notification, user)
    if not frappe.utils.cint(row.is_read):
        frappe.db.set_value(
            "BP Notification",
            row.name,
            {"is_read": 1, "read_at": frappe.utils.now()},
            update_modified=False,
        )
        frappe.db.commit()
    return {"ok": True, "unread_count": _visible_unread_count(user)}


@frappe.whitelist()
def mark_notification_unread(notification):
    _require_system_user()
    if not frappe.db.table_exists("BP Notification"):
        return {"ok": True, "unread_count": 0}
    user = frappe.session.user
    row = _visible_notification(notification, user)
    if frappe.utils.cint(row.is_read):
        frappe.db.set_value(
            "BP Notification",
            row.name,
            {"is_read": 0, "read_at": None},
            update_modified=False,
        )
        frappe.db.commit()
    return {"ok": True, "unread_count": _visible_unread_count(user)}


@frappe.whitelist()
def mark_all_notifications_read():
    """Mark only notifications the user is currently authorized to read."""
    _require_system_user()
    if not frappe.db.table_exists("BP Notification"):
        return {"ok": True, "unread_count": 0}
    user = frappe.session.user
    rows = _visible_rows(user, unread_only=True)
    for row in rows:
        frappe.db.set_value(
            "BP Notification",
            row.name,
            {"is_read": 1, "read_at": frappe.utils.now()},
            update_modified=False,
        )
    if rows:
        frappe.db.commit()
    return {"ok": True, "unread_count": 0}
