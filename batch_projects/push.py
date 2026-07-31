"""batch_projects → desktop push, via the erpdesktop notification pipeline.

batch_projects OWNS the durable side of a notification (the BP Notification
record + email). This module is the desktop channel. Rather than build a new
transport, it REUSES erpdesktop's existing rich client — Socket.IO
``agent:notification:new`` → Rust dispatcher → native OS toast + SQLite offline
store + reconnect catch-up + tray badge + action buttons — by calling
erpdesktop_agent's in-process producer, which creates the durable ERPDesktop
Notification Event AND publishes the realtime event the desktop already consumes.

Decoupled & safe
────────────────
The producer import is guarded: if erpdesktop_agent isn't installed, dispatch()
is a silent no-op and the in-app record + email remain the durable floor
("pushes regardless of apps"). It runs off the request hot-path (enqueued after
commit) and never raises into the caller.

Why not the gateway SSE plane? A separate ``/v1/push/*`` plane exists in
bp-gateway for FUTURE browser/mobile push that have no native client. The
desktop channel is served by erpdesktop's own client, so it does not use it.

OS action buttons are a FIXED catalogue (macOS requires categories registered at
startup — see erpdesktop categories.rs / erpdesktop_agent payload_builder.py), so
each notification type maps to an EXISTING action_type_id rather than inventing
per-notification buttons.
"""

import frappe

# ntype → (category, reason, action_type_id, priority). category/reason are
# constrained Selects on the ERPDesktop Notification Event; action_type_id must
# match a registered OS action category.
_MAP = {
    "Assignment":    ("assignment", "assignment", "assignment", "normal"),
    "Unassigned":    ("info",       "subscribed", "info",       "normal"),
    "Mention":       ("mention",    "mention",    "mention",    "high"),
    "Comment":       ("info",       "watcher",    "info",       "normal"),
    "Status Change": ("info",       "watcher",    "info",       "normal"),
    "Update":        ("info",       "watcher",    "info",       "low"),
    "Due Soon":      ("reminder",   "reminder",   "reminder",   "high"),
    "Overdue":       ("alert",      "reminder",   "alert",      "critical"),
    "Sprint":        ("info",       "subscribed", "info",       "normal"),
}


def dispatch(*, recipient, ntype, actor, title, body, task=None, task_key=None,
             project=None, deep_link=None):
    """Queue a desktop push for one recipient, off the request hot-path.

    Enqueued after commit so it only fires once the BP Notification record is
    durable, and so a slow/absent desktop pipeline never blocks the save.
    """
    try:
        frappe.enqueue(
            "batch_projects.push._deliver",
            queue="short",
            enqueue_after_commit=True,
            recipient=recipient, ntype=ntype, actor=actor, title=title, body=body,
            task=task, task_key=task_key, project=project, deep_link=deep_link,
        )
    except Exception:
        frappe.logger("bp.push").debug("desktop push enqueue skipped")


def _deliver(*, recipient, ntype, actor, title, body, task, task_key, project, deep_link):
    """Worker side: hand the notification to erpdesktop_agent's producer, which
    creates the durable Event + publishes agent:notification:new. Silent no-op if
    the agent app isn't installed; never raises."""
    try:
        from erpdesktop_agent.dispatch.fanout import push_notification
    except ImportError:
        return

    category, reason, action_type_id, priority = _MAP.get(
        ntype, ("info", "system", "info", "normal"))

    # Reuse the registered button set; route the foreground "view" to the SPA.
    actions = [{"id": "view", "label": "View", "foreground": True, "url": deep_link}] if deep_link else None

    # Sender avatar as the toast thumbnail (absolute URL so the desktop can fetch
    # it); the desktop falls back to the site logo when this is empty/unreachable.
    image = None
    avatar = frappe.db.get_value("User", actor, "user_image") if actor else None
    if avatar:
        image = frappe.utils.get_url(avatar) if avatar.startswith("/") else avatar

    try:
        push_notification(
            recipient,
            title=title,
            body=body,
            category=category,
            reason=reason,
            priority=priority,
            action_type_id=action_type_id,
            target_doctype="BP Task" if task else None,
            target_name=task,
            actions=actions,
            actor=actor,
            image=image,
            source_event=f"bp:{ntype}",
            dedup_key=f"bp:{task or project or ntype}:{ntype}:{recipient}",
            dedup_ttl_seconds=45,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "bp desktop push failed")
