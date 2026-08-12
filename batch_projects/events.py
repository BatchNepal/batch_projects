"""
batch_projects/events.py
─────────────────────────
Formal event bus. Every mutation in board.py calls emit().
Automation rules, notifications, and realtime all listen here.

Usage:
    from batch_projects.events import emit
    emit("task.updated", {"task": doc.name, "project": doc.project, ...})
"""

import frappe
import json


# ─── EVENT NAMES (constants) ─────────────────────────────────────────────────
# Use these instead of raw strings everywhere.

TASK_CREATED        = "task.created"
TASK_UPDATED        = "task.updated"
TASK_DELETED        = "task.deleted"
TASK_STATUS_CHANGED  = "task.status_changed"
TASK_MOVED          = "task.moved"
TASK_ASSIGNED       = "task.assigned"
TASK_UNASSIGNED     = "task.unassigned"
COMMENT_ADDED       = "comment.added"
PROJECT_CREATED     = "project.created"
PROJECT_UPDATED     = "project.updated"
PROJECT_ROLE_CHANGED = "project.role_changed"
SPRINT_STARTED      = "sprint.started"
SPRINT_COMPLETED    = "sprint.completed"
TASK_APPROVAL_REQUESTED = "task.approval_requested"
TASK_APPROVAL_DECIDED   = "task.approval_decided"
ERP_INVOICE_SUBMITTED = "erp.invoice_submitted"
ERP_PAYMENT_RECEIVED  = "erp.payment_received"
ERP_SO_CONFIRMED      = "erp.so_confirmed"
# Ephemeral (broadcast_only, never persisted) — see api/drawings.py.
DRAWING_CHANGED   = "drawing.changed"
DRAWING_PRESENCE  = "drawing.presence"


# ─── PAYLOAD SHAPES ──────────────────────────────────────────────────────────
# Every event payload must include these base fields:
#
# {
#   "event":    str   — event name constant above
#   "project":  str   — BP Project name
#   "user":     str   — frappe.session.user
#   "timestamp": str  — frappe.utils.now()
#   ...event-specific fields
# }
#
# task.created / task.updated:
#   "task":   str — BP Task name
#   "task_key":  str
#   "title":  str
#   "changes": list[dict] — [{"field": str, "from": any, "to": any}]
#
# task.status_changed (subset of task.updated, fired separately for clarity):
#   "task":       str
#   "task_key":   str
#   "from_status": str
#   "to_status":   str
#
# task.moved (board.move_task, the drag-and-drop endpoint): fired for
# EVERY successful drag, including a pure same-column reorder
# (task.status_changed only fires when status actually changes — a
# same-column reorder has none, and was previously invisible to every
# other connected client until their next full refresh). Realtime-only:
# no notification/automation listens on this, it exists purely so
# stores/project.js can reposition the exact card in place instead of
# refetching the whole board.
#   "task":        str
#   "task_key":    str
#   "old_status":  str
#   "new_status":  str
#   "board_rank":  str — the new fractional rank; the SPA inserts the card
#                  at the position this sorts into, string-comparable
#                  since rank.py's ranks are fixed-width zero-padded
#
# task.assigned / task.unassigned:
#   "task":     str
#   "employee": str
#   "full_name": str
#
# project.role_changed (ReBAC sync, see _sync_rebac below):
#   "user":      str — the member whose role changed
#   "old_role":  str | None — None means "just added"
#   "new_role":  str | None — None means "removed from the project"
#
# comment.added:
#   "task":         str — BP Task name (every real emit(COMMENT_ADDED, ...)
#                    call site — board.py, sharing.py — uses "task", not
#                    "issue"; keep this consistent or stores/project.js
#                    destructures a key that doesn't exist).
#   "comment_text": str
#   "activity":     str — BP Activity name
#
# erp.invoice_submitted / erp.payment_received / erp.so_confirmed (these
# carry NO "task", by design; see erp_triggers.py):
#   "invoice"/"sales_order": str — the ERPNext doc name
#   "payment_entry": str — erp.payment_received only
#   "customer": str
#   "amount":   float
#   "outstanding": float — erp.invoice_submitted / erp.payment_received only;
#                  a condition of {"field":"outstanding","op":"eq","value":0}
#                  is how a rule expresses "this invoice is now fully paid"
#   "currency": str


# ─── CORE EMIT ───────────────────────────────────────────────────────────────

def emit(event_name: str, payload: dict):
    """
    Central event dispatcher. Call this from every mutating API.

    1. Enriches payload with base fields if missing.
    2. Invalidates Redis cache for the affected project — ensures fresh data
       on next load for any client not connected via socket.
    3. Publishes realtime to connected clients (board/list auto-refresh).
    4. Evaluates automation rules (isolated — failures never break the caller).
    5. Queues notifications.
    6. Syncs relationship-change edges to the gateway's ReBAC cache (only
       for the handful of events that are actual permission edges).
    """

    payload = _enrich(event_name, payload)

    # 1. Cache invalidation — BEFORE broadcast so any client that refetches
    #    after receiving the socket event gets fresh data from DB, not stale cache.
    _invalidate_cache(event_name, payload)

    # 2. Realtime broadcast — board/list auto-refresh
    _broadcast(event_name, payload)

    # 3. Automation rules
    _evaluate_automations(event_name, payload)

    # 4. Notifications
    _queue_notifications(event_name, payload)

    # 5. ReBAC relationship sync — always, independent of bp_automation_engine
    _sync_rebac(event_name, payload)


# ─── ENRICHMENT ──────────────────────────────────────────────────────────────

def _enrich(event_name: str, payload: dict) -> dict:
    from frappe.utils import now
    payload.setdefault("event", event_name)
    payload.setdefault("user", frappe.session.user)
    payload.setdefault("timestamp", now())
    return payload


# ─── CACHE INVALIDATION ──────────────────────────────────────────────────────

def _invalidate_cache(event_name: str, payload: dict):
    """
    Invalidate Redis cache for the affected project on every mutation.

    Called BEFORE broadcast so that:
    - A client receiving the socket event and immediately calling refreshBoard()
      gets fresh DB data, not the old cached version.
    - A client opening a fresh tab after any mutation always sees current data.

    We invalidate ALL views for the project (board + backlog + sprints) on any
    event except comment.added, which doesn't affect issue lists.

    Additionally, if the mutated task belongs to a sprint, we invalidate sprint
    analytics (burndown, velocity, cycle-time, CFD) so the sprint detail page
    always shows fresh data after a drag/status change/reorder.
    """
    if event_name == "comment.added":
        return  # Comments don't affect board/backlog/sprint views

    project = payload.get("project")
    if not project:
        return

    try:
        from batch_projects.cache import invalidate_project
        invalidate_project(project)

        # Sprint analytics invalidation: if the task belongs to a sprint,
        # bust the finer-grained analytics cache too.
        task = payload.get("task")
        sprint = payload.get("sprint")
        if task and not sprint:
            # sprint may not be in the payload but we can look it up
            sprint = frappe.db.get_value("BP Task", task, "sprint") if task else None
        if sprint:
            from batch_projects.api.sprint_analytics import invalidate_sprint_cache
            invalidate_sprint_cache(sprint, project)
    except Exception:
        # Never let cache failure break a mutation
        frappe.log_error(frappe.get_traceback(), "bp_cache invalidation failed in emit")

def _broadcast(event_name: str, payload: dict, after_commit: bool = True):
    """
    Publish once to the gateway's realtime plane (bridge.publish_realtime_event
    -> POST /v1/realtime/publish -> internal/realtime.Handler.Publish), which
    fans the event out over SSE to every connected client. Per-user scoping
    happens on the GATEWAY side, not here: each open SSE connection filters
    the shared per-tenant stream by that user's own visible-project set
    (api.board.get_member_projects, resolved via membership.sees() —
    System Managers/Administrator see "all": true), the mirror image of what
    the old per-recipient frappe.publish_realtime() loop did in-process.

    Was frappe.publish_realtime() looped over _get_broadcast_recipients(project)
    — Frappe's own native socket.io/pub-sub, which bp-gateway's SSE Subscribe()
    never consumed (two disconnected systems, confirmed live 2026-08-05: a
    publish_realtime() broadcast never reached a connected SSE client with a
    valid token, correct CORS, and a genuinely open stream). Removed that
    recipient cache (_get_broadcast_recipients/invalidate_recipients) along
    with this change — a single tenant-wide publish plus gateway-side
    filtering makes the Frappe-side recipient list dead weight.

    after_commit=True (the default, used by every mutation-driven event)
    defers the publish until the DB transaction commits, so latency stays off
    the save hot-path.
    """
    from batch_projects.entitlements import is_feature_enabled
    if not is_feature_enabled("realtime"):
        return
    project = payload.get("project")
    if not project:
        return

    try:
        from batch_projects import bridge
        if after_commit:
            frappe.db.after_commit.add(
                lambda: bridge.publish_realtime_event(event_name, project, payload)
            )
        else:
            bridge.publish_realtime_event(event_name, project, payload)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "bp_event broadcast failed")


def broadcast_only(event_name: str, payload: dict, after_commit: bool = False):
    """Enrichment + realtime broadcast, deliberately skipping the rest of
    emit()'s pipeline (cache invalidation, automation rules, notifications,
    ReBAC sync) — for ephemeral, high-frequency, non-durable signals where
    those side effects would be actively wrong, not just wasted work: a live
    collaborative-drawing scene push (batch_projects.api.drawings.
    broadcast_drawing_change) can fire every few hundred ms per active
    editor, and running full automation-rule evaluation or busting the
    project cache on every keystroke-level update would be both a real
    performance cost and a correctness risk (an automation rule matching a
    transient mid-drag payload that was never actually saved).
    after_commit defaults to False here (unlike _broadcast's True) — these
    callers typically write nothing to the DB, so there's no save-latency
    reason to defer, and the whole point is minimizing live-sync latency."""
    payload = _enrich(event_name, payload)
    _broadcast(event_name, payload, after_commit=after_commit)


# ─── AUTOMATION RULES ────────────────────────────────────────────────────────

def _evaluate_automations(event_name: str, payload: dict):
    """
    Run every active BP Automation Rule whose trigger matches this event.

    Dispatched to whichever engine site_config `bp_automation_engine` selects:
    "python" (default) evaluates + executes rules in-process as before;
    "gateway" publishes the event to the bp-gateway automation engine instead
    and returns immediately — Go decides what fires and calls back into
    api/automation.py::apply_action. Never both. Failures are isolated here
    and never propagate to the mutation that triggered the event.
    """
    try:
        engine = (frappe.conf.get("bp_automation_engine") or "python").lower()
        if engine == "gateway":
            from batch_projects import bridge
            bridge.publish_event(_event_envelope(event_name, payload))
        else:
            from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
                run_for_event,
            )
            run_for_event(event_name, payload)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "bp automation dispatch failed")


def _event_envelope(event_name: str, payload: dict) -> dict:
    """Build the event the gateway automation engine consumes.

    Carries a snapshot of the task's field subset (loaded once here) so Go
    never re-derives Frappe field semantics — the snapshot is the drift
    protection between the two engines.
    """
    envelope = {
        "event": event_name,
        "project": payload.get("project"),
        "task": payload.get("task"),
        "task_key": payload.get("task_key"),
        "to_status": payload.get("to_status"),
        "from_status": payload.get("from_status"),
        "changes": payload.get("changes"),
        "depth": frappe.flags.get("bp_automation_depth", 0),
        "snapshot": None,
        # erp.doc_event carries no project (erp_triggers.py's wildcard hook
        # can't generically resolve one) and no task — these three are its
        # actual identity. Must stay populated: processEvent on the Go side
        # rejects an empty project, so dropping these here would silently
        # stop every erp.doc_event workflow/rule from firing through the
        # gateway engine at all.
        "doctype": payload.get("doctype"),
        "docname": payload.get("docname"),
        "erp_event": payload.get("erp_event"),
        # Generic passthrough — mirrors _resolve()'s own "if not task: return
        # payload.get(field)" fallback (bp_automation_rule.py) EXACTLY, so a
        # condition on a task-less event's own field (erp.invoice_submitted's
        # "amount"/"customer"/"outstanding", sprint.*'s "sprint_name", etc.)
        # resolves the same way through the Go gateway as it already does
        # through the Python engine. Previously this whole dict was silently
        # dropped before reaching Go — any Team-tier workspace on
        # bp_automation_engine="gateway" (the default) had these fields
        # unconditionally unresolvable (WORKPLAN-PHASE25 B2 finding).
        "payload": payload,
        # external.webhook's third-party JSON body — a SEPARATE, explicit key
        # (not just riding inside "payload") because it gets its own dotted
        # resolve()/resolveTemplate() lookup convention (`body.<key>`,
        # `{{trigger.body.<key>}}`) to keep an arbitrary third party's field
        # names from colliding with reserved envelope words. Always {} unless
        # the caller is run_external_event (WORKPLAN-PHASE25 B3).
        "body": payload.get("body") or {},
    }

    task_name = payload.get("task")
    if task_name and frappe.db.exists("BP Task", task_name):
        task = frappe.get_doc("BP Task", task_name)
        envelope["snapshot"] = {
            "status": task.status,
            "priority": task.priority,
            "task_type": task.task_type,
            "story_points": task.story_points,
            "due_date": str(task.due_date) if task.due_date else None,
            "billable": task.billable,
            "reporter": task.reporter,
            "labels": _safe_json(task.labels, []),
            "assignees": [r.user for r in (task.assignees or [])],
            "custom_field_values": _safe_json(task.custom_field_values, {}),
        }
    return envelope


def _safe_json(raw, default):
    if not raw:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


# ─── REBAC RELATIONSHIP SYNC ─────────────────────────────────────────────────
#
# The gateway runs a Zanzibar-lite ReBAC engine (OpenFGA) as the authorization
# authority; Frappe/MariaDB remains the durable source of truth OpenFGA's
# relation tuples are a materialized index of. This is the write-side half —
# every edge-changing event also gets a small, purpose-built envelope
# published to the gateway, independent of bp_automation_engine (that flag
# only selects which engine EXECUTES automation RULES; ReBAC sync is a
# separate, always-on concern) and via a separate endpoint from the
# automation ingest (see bridge.publish_rebac_event — the automation ingest
# license-gates on the "automations" paid feature, which permission-sync
# correctness must never depend on).
#
# TASK_CREATED / PROJECT_CREATED carry the STRUCTURAL edges (task's
# parent_project link, project's org link) — without them a role or
# assignee tuple has nothing to inherit through; the other three carry the
# actual grants.

_REBAC_SYNC_EVENTS = {
    TASK_ASSIGNED, TASK_UNASSIGNED, PROJECT_ROLE_CHANGED,
    TASK_CREATED, PROJECT_CREATED,
}


def _rebac_envelope(event_name: str, payload: dict) -> dict:
    """Minimal envelope for a relationship-sync edge — deliberately NOT
    _event_envelope() above (that one is automation-specific: condition
    snapshot, recursion-depth guard, generic payload passthrough for rule
    matching). A ReBAC edge only ever carries the identity of what changed."""
    envelope = {
        "event": event_name,
        "project": payload.get("project"),
        "timestamp": payload.get("timestamp"),
    }
    if event_name in (TASK_ASSIGNED, TASK_UNASSIGNED):
        envelope["task"] = payload.get("task")
        envelope["user"] = payload.get("assignee")
    elif event_name == PROJECT_ROLE_CHANGED:
        envelope["user"] = payload.get("user")
        envelope["old_role"] = payload.get("old_role")
        envelope["new_role"] = payload.get("new_role")
    elif event_name == TASK_CREATED:
        envelope["task"] = payload.get("task")
    # PROJECT_CREATED needs nothing beyond the base "project" field already
    # set above — the gateway links every project to the single org:main.
    return envelope


def _sync_rebac(event_name: str, payload: dict):
    """Publish a relationship-change edge to the gateway, if this event is
    one of the ones that actually changes a permission edge. Isolated like
    every other emit() step — a failure here never breaks the caller's
    save. Fail-CLOSED is the gateway's job (a stale/unreachable cache must
    deny, not silently allow) — this function failing quietly is a
    sync-lag risk to monitor, not itself a security hole, since the
    gateway is the one deciding what "cache miss" means."""
    if event_name not in _REBAC_SYNC_EVENTS:
        return
    try:
        from batch_projects import bridge
        bridge.publish_rebac_event(_rebac_envelope(event_name, payload))
    except Exception:
        frappe.log_error(frappe.get_traceback(), "bp rebac sync failed")


# ─── NOTIFICATIONS ───────────────────────────────────────────────────────────

def _queue_notifications(event_name: str, payload: dict):
    """
    Create BP Notification records for the relevant users.

    Rules:
    - comment.added       → notify all assignees + reporter (not the commenter)
    - task.assigned       → notify the newly assigned user
    - task.status_changed → notify reporter and assignees (not the actor)
    - task.created        → notify default_assignee if set (not the creator)
    - task.approval_requested → notify the designated approver
    - task.approval_decided   → notify assignees/reporter/watchers
    - project.role_changed    → notify the user whose role changed

    Precedence: custom BP Notification Rules are evaluated FIRST, before the
    built-ins above — a mute rule needs to suppress the built-in entirely,
    which is only possible if it's checked first. Non-mute matching rules
    then ADD their own recipients on top of whatever the built-in (or the
    mute-skip) produced.
    """
    # Each of the three phases below (rule matching, built-in dispatch, rule
    # dispatch) gets its OWN try/except — a failure in the built-in path
    # (pre-existing data issue, e.g.) must not silently prevent rules from
    # firing, and a bad rule must not silently break the built-in; matches
    # emit()'s "isolated — failures never break the caller" promise.
    actor = payload.get("user") or frappe.session.user
    task_name = payload.get("task") or payload.get("issue")
    project = payload.get("project")

    matching_rules = []
    try:
        from batch_projects.entitlements import is_feature_enabled
        # Gated at execution time too, not just in the CRUD API — a
        # workspace that downgrades below Team simply stops evaluating its
        # existing rules rather than erroring.
        if is_feature_enabled("notification_rules"):
            matching_rules = _matching_notification_rules(event_name, project, task_name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "bp_notification_rule evaluation failed")

    muted_by_rule = any(r.mute for r in matching_rules)

    if not muted_by_rule:
        try:
            if event_name == COMMENT_ADDED:
                _notify_comment(payload, actor, task_name, project)
            elif event_name == TASK_ASSIGNED:
                _notify_assignment(payload, actor, task_name, project)
            elif event_name == TASK_UNASSIGNED:
                _notify_task_unassigned(payload, actor, task_name, project)
            elif event_name == TASK_STATUS_CHANGED:
                _notify_status_change(payload, actor, task_name, project)
            elif event_name == TASK_UPDATED:
                _notify_task_updated(payload, actor, task_name, project)
            elif event_name == TASK_CREATED:
                _notify_task_created(payload, actor, task_name, project)
            elif event_name in (SPRINT_STARTED, SPRINT_COMPLETED):
                _notify_sprint(event_name, payload, actor, project)
            elif event_name == TASK_APPROVAL_REQUESTED:
                _notify_approval_requested(payload, actor, task_name, project)
            elif event_name == TASK_APPROVAL_DECIDED:
                _notify_approval_decided(payload, actor, task_name, project)
            elif event_name == PROJECT_ROLE_CHANGED:
                _notify_role_changed(payload, actor, project)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "bp_notification queue failed")

    for rule in matching_rules:
        if rule.mute:
            continue
        try:
            channels = set(_safe_json(rule.channels_json, ["in_app", "email", "desktop"]))
            recipients = _resolve_rule_recipients(rule, task_name, project)
            message = f"Routed by rule: {rule.rule_name}"
            for recipient in recipients:
                _create_rule_notification(recipient, rule, task_name, project, actor, message, channels)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"bp_notification_rule dispatch failed ({rule.name})")


# ─── PHASE 16 — CUSTOM NOTIFICATION RULES (routing only) ─────────────────────
# Rules key on the events.py bus name (task.created, task.updated, ...) — a
# different vocabulary from notification_type above (BP Notification
# Template keys on that one). See docs/PLAN-phase16-notifications.md for why
# two vocabularies exist: templates vary at the email-content granularity,
# rules filter at the point where the full task+project doc is available.

_RULE_OP_FUNCS = {
    "=":        lambda a, b: a == b,
    "!=":       lambda a, b: a != b,
    "in":       lambda a, b: a in (b if isinstance(b, list) else [b]),
    "not in":   lambda a, b: a not in (b if isinstance(b, list) else [b]),
    "contains": lambda a, b: str(b) in str(a or ""),
}


def _rule_context(task_name, project) -> dict:
    """Merged task + project field dict for condition evaluation — project
    fields first so task fields win on any name collision (there shouldn't
    be one)."""
    ctx = {}
    if project:
        proj = frappe.db.get_value("BP Project", project, "*", as_dict=True)
        if proj:
            ctx.update(proj)
    if task_name:
        task = frappe.db.get_value("BP Task", task_name, "*", as_dict=True)
        if task:
            ctx.update(task)
    return ctx


def _rule_matches(rule, ctx: dict) -> bool:
    for cond in _safe_json(rule.conditions_json, []):
        field, op, value = cond.get("field"), cond.get("op"), cond.get("value")
        if not field or op not in _RULE_OP_FUNCS:
            continue
        if not _RULE_OP_FUNCS[op](ctx.get(field), value):
            return False
    return True


def _matching_notification_rules(event_name: str, project, task_name) -> list:
    rules = frappe.get_all(
        "BP Notification Rule",
        filters={"event": event_name, "enabled": 1},
        fields=["name", "rule_name", "event", "project", "mute",
                "conditions_json", "recipients_json", "channels_json"],
    )
    rules = [r for r in rules if not r.project or r.project == project]
    if not rules:
        return []
    ctx = _rule_context(task_name, project)
    return [r for r in rules if _rule_matches(r, ctx)]


def _resolve_rule_recipients(rule, task_name, project) -> set:
    recipients = set()
    for r in _safe_json(rule.recipients_json, []):
        rtype, rvalue = r.get("type"), r.get("value")
        if rtype == "assignee" and task_name:
            recipients.update(frappe.get_all("BP Task Assignee", filters={"parent": task_name}, pluck="user"))
        elif rtype == "watchers" and task_name:
            recipients.update(_get_watchers(task_name))
        elif rtype == "project_role" and rvalue and project:
            recipients.update(frappe.get_all(
                "BP Project Member", filters={"parent": project, "role": rvalue}, pluck="user"
            ))
        elif rtype == "user" and rvalue:
            recipients.add(rvalue)
    return recipients


def _create_rule_notification(recipient, rule, task_name, project, actor, message, channels):
    """Rule-triggered fan-out — mirrors _create_notification's 3 channels,
    but CHANNEL SELECTION comes from the rule (an explicit admin routing
    decision — "urgent task always emails the manager" would be pointless if
    the recipient's personal per-notification-type email toggle could
    silently swallow it), not the recipient's per-notification-type
    preference. The recipient's own task/project MUTE still applies —
    muting a task should still mean silence, rule or no rule."""
    if recipient == actor:
        return
    if _is_muted(recipient, task_name, project):
        return

    notification_type = "Rule"
    actor_name = frappe.db.get_value("User", actor, "full_name") or actor or "Automation"
    task_key = frappe.db.get_value("BP Task", task_name, "task_key") if task_name else None
    task_title = frappe.db.get_value("BP Task", task_name, "title") if task_name else None

    if "in_app" in channels:
        frappe.get_doc({
            "doctype": "BP Notification",
            "recipient": recipient,
            "notification_type": notification_type,
            "task": task_name,
            "task_key": task_key,
            "task_title": task_title,
            "project": project,
            "actor": actor,
            "actor_name": actor_name,
            "message": message,
            "is_read": 0,
        }).insert(ignore_permissions=True)

    if "desktop" in channels:
        try:
            from batch_projects import push
            deep_link = _task_url(project, task_key) if task_key else _project_url(project)
            push.dispatch(
                recipient=recipient, ntype=notification_type, actor=actor,
                title=task_title or task_key or "batch_projects",
                body=_desktop_body(notification_type, actor_name, task_title, {}),
                task=task_name, task_key=task_key, project=project, deep_link=deep_link,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "bp push dispatch failed (rule)")

    if "email" in channels:
        _send_notification_email(
            recipient=recipient, notification_type=notification_type,
            task=task_name, task_key=task_key, task_title=task_title,
            project=project, actor_name=actor_name, message=message,
        )


def _create_notification(recipient, notification_type, task, project, actor, message,
                         email_extras=None):
    """Create a notification, honoring the recipient's mute + channel preferences.

    email_extras is an optional dict of extra keyword arguments forwarded to
    _send_notification_email (e.g. comment_text, changes, priority, due_date,
    from_status, to_status). It is ignored for the in-app record.
    """
    if recipient == actor:
        return
    # Per-user mute: silence this issue/project entirely (both channels)
    if _is_muted(recipient, task, project):
        return

    pref = _get_pref(recipient)
    actor_name = frappe.db.get_value("User", actor, "full_name") or actor
    task_key = frappe.db.get_value("BP Task", task, "task_key") if task else None
    task_title = frappe.db.get_value("BP Task", task, "title") if task else None

    # In-app channel — created unless the user turned in-app off (default on)
    notif_name = None
    if not pref or pref.get("inapp_enabled", 1):
        notif_doc = frappe.get_doc({
            "doctype": "BP Notification",
            "recipient": recipient,
            "notification_type": notification_type,
            "task": task,
            "task_key": task_key,
            "task_title": task_title,
            "project": project,
            "actor": actor,
            "actor_name": actor_name,
            "message": message,
            "is_read": 0,
        }).insert(ignore_permissions=True)
        notif_name = notif_doc.name

    # Desktop push channel — native OS toast via erpdesktop's existing client
    # (Socket.IO agent:notification:new → dispatcher). Fire-and-forget and fully
    # decoupled: a silent no-op when erpdesktop_agent isn't installed, so the
    # in-app record + email above remain the durable floor regardless of any app.
    if _desktop_pref_allows(pref):
        try:
            from batch_projects import push
            deep_link = _task_url(project, task_key) if task_key else _project_url(project)
            push.dispatch(
                recipient=recipient,
                ntype=notification_type,
                actor=actor,
                title=task_title or task_key or "batch_projects",
                body=_desktop_body(notification_type, actor_name, task_title, email_extras),
                task=task,
                task_key=task_key,
                project=project,
                deep_link=deep_link,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "bp push dispatch failed")

    # Email channel — fire-and-forget; gated by per-user email preferences
    if _email_pref_allows(notification_type, pref):
        _send_notification_email(
            recipient=recipient,
            notification_type=notification_type,
            task=task,
            task_key=task_key,
            task_title=task_title,
            project=project,
            actor_name=actor_name,
            message=message,
            **(email_extras or {}),
        )


# ─── PREFERENCES & MUTE ──────────────────────────────────────────────────────

# notification_type → the email preference field that gates it
_EMAIL_PREF_FIELD = {
    "Assignment":    "email_assignment",
    "Unassigned":    "email_assignment",    # same channel as assignment
    "Comment":       "email_comment",
    "Mention":       "email_mention",
    "Status Change": "email_status_change",
    "Update":        "email_status_change", # field changes gate on same pref as status
    "Due Soon":      "email_due_reminder",
    "Overdue":       "email_due_reminder",
    "Approval Requested": "email_assignment",  # a new responsibility, same channel as assignment
    "Approval Decided":   "email_status_change",
    "Role Changed":        "email_assignment",  # new access is an assignment-shaped event
    "Timer Reminder":      "email_due_reminder", # same "nag" channel as Due Soon/Overdue
}

# Fields on a task whose change is worth notifying watchers about.
_NOTIF_WORTHY_FIELDS = {
    "priority", "due_date", "title", "task_type",
    "description", "labels", "story_points",
}

_FIELD_LABEL = {
    "priority":     "priority",
    "due_date":     "due date",
    "title":        "title",
    "task_type":    "type",
    "labels":       "labels",
    "story_points": "story points",
    "description":  "description",
}

_PREF_FIELDS = [
    "email_enabled", "email_assignment", "email_comment", "email_mention",
    "email_status_change", "email_due_reminder", "email_digest",
    "email_weekly_summary", "inapp_enabled", "desktop_enabled",
]


def _get_pref(user: str):
    """Per-request cached preference record for a user (None = no record → all on)."""
    cache = getattr(frappe.local, "_bp_pref_cache", None)
    if cache is None:
        cache = {}
        frappe.local._bp_pref_cache = cache
    if user not in cache:
        cache[user] = frappe.db.get_value(
            "BP Notification Preference", user, _PREF_FIELDS, as_dict=True
        )
    return cache[user]


def _email_pref_allows(notification_type: str, pref) -> bool:
    """True if the user's email preferences permit this notification type."""
    if not pref:
        return True  # no explicit prefs → default everything on
    if not pref.get("email_enabled", 1):
        return False
    field = _EMAIL_PREF_FIELD.get(notification_type)
    if field and not pref.get(field, 1):
        return False
    return True


def _desktop_pref_allows(pref) -> bool:
    """True if the user permits native desktop push (default on)."""
    return not pref or bool(pref.get("desktop_enabled", 1))


# notification_type → concise desktop toast body (richer than the in-app line)
def _desktop_body(notification_type: str, actor_name: str, task_title: str, extras: dict) -> str:
    extras = extras or {}
    preview = (extras.get("comment_text") or "").strip()
    if notification_type == "Assignment":
        return f"{actor_name} assigned this to you"
    if notification_type == "Unassigned":
        return f"{actor_name} unassigned you"
    if notification_type == "Mention":
        return f"{actor_name} mentioned you" + (f" — “{preview}”" if preview else "")
    if notification_type == "Comment":
        return f"{actor_name} commented" + (f" — “{preview}”" if preview else "")
    if notification_type == "Status Change":
        f, t = extras.get("from_status"), extras.get("to_status")
        return f"{actor_name}: {f} → {t}" if f and t else f"{actor_name} changed the status"
    if notification_type == "Update":
        return f"{actor_name} updated this task"
    if notification_type == "Due Soon":
        due = extras.get("due_date")
        return f"Due {due}" if due else "Due soon"
    if notification_type == "Overdue":
        return "This task is overdue"
    return f"{actor_name}"


def _is_muted(user: str, task: str, project: str) -> bool:
    """True if the user muted this specific task or its whole project."""
    if task and frappe.db.exists("BP Notification Mute", {"user": user, "task": task}):
        return True
    if project and frappe.db.exists(
        "BP Notification Mute", {"user": user, "project": project, "task": ["in", ["", None]]}
    ):
        return True
    return False


# ─── EMAIL CHANNEL ───────────────────────────────────────────────────────────


def _has_outgoing_email() -> bool:
    """True if the site has a usable outgoing email account (cached per request)."""
    cached = getattr(frappe.local, "_bp_has_outgoing_email", None)
    if cached is None:
        cached = bool(
            frappe.db.get_value("Email Account", {"enable_outgoing": 1, "default_outgoing": 1})
            or frappe.conf.get("mail_server")
        )
        frappe.local._bp_has_outgoing_email = cached
    return cached


def _project_url(project: str, view: str = "board") -> str:
    key = frappe.db.get_value("BP Project", project, "key") if project else None
    base = frappe.utils.get_url()
    return f"{base}/workspace/{key}/{view}" if key else f"{base}/workspace"


def _task_url(project: str, task_key: str) -> str:
    """Deep link to the task on its project board (opens the detail panel)."""
    key = frappe.db.get_value("BP Project", project, "key") if project else None
    base = frappe.utils.get_url()
    if key and task_key:
        return f"{base}/workspace/{key}/board?task={task_key}"
    return _project_url(project)


# ─── PHASE 16 — CUSTOM TEMPLATE OVERRIDE ─────────────────────────────────────

def _render_custom_template(notification_type, ctx):
    """An enabled BP Notification Template overriding this notification_type.
    Returns (subject, body_html) or None (no usable override);
    NEVER raises — a missing row, enabled=0, or any render error all fall
    through to the code default in the caller. `ctx` is a plain dict of
    already-safe scalar values (the same ones build_notification_email
    already receives) — the whitelisted variable context, nothing from
    frappe.local or any doc object."""
    try:
        if not frappe.db.exists("BP Notification Template", notification_type):
            return None
        tpl = frappe.get_cached_doc("BP Notification Template", notification_type)
        if not tpl.enabled or not tpl.subject or not tpl.body:
            return None
        subject = frappe.render_template(tpl.subject, ctx)
        body = frappe.render_template(tpl.body, ctx)
        if not subject or not body:
            return None
        return subject, body
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"bp_notification_template render failed ({notification_type})")
        return None


def _send_notification_email(
    recipient, notification_type, task, task_key, task_title,
    project, actor_name, message,
    # legacy parameters (kept for callers that pass them explicitly)
    cta_url=None, cta_label=None, message_html=None,
    # rich context forwarded via email_extras
    comment_text=None, changes=None,
    from_status=None, to_status=None,
    priority=None, due_date=None,
):
    """Queue a premium HTML notification email.

    When ``message_html`` is provided (digest / weekly summary / report) it is
    used verbatim — those callers build their own templates. For all event-driven
    notifications we render via email_templates.build_notification_email so every
    inbox-landing email has the same dark-header, coloured-accent card design.
    """
    try:
        user_row = frappe.db.get_value(
            "User", recipient, ["email", "enabled", "user_type"], as_dict=True
        )
        if not user_row:
            return
        email = user_row.email or recipient
        if not email or "@" not in email or recipient == "Guest" or not user_row.enabled:
            return
        if not _has_outgoing_email():
            return

        manage_url = frappe.utils.get_url("/workspace/account")

        if message_html:
            # Caller-supplied HTML (digest, weekly summary, report) — use as-is.
            html    = message_html
            key     = task_key or (
                frappe.db.get_value("BP Project", project, "project_name") if project else None
            ) or "batch_projects"
            subject = (f"[{key}] " + frappe.utils.strip_html(message)[:70]) if not cta_label \
                      else f"[{key}] {cta_label}"
        else:
            # Premium template for all event-driven notifications.
            from batch_projects.email_templates import (
                build_notification_email, notification_subject, build_custom_notification_email,
            )
            url = cta_url or (_task_url(project, task_key) if task_key else _project_url(project))

            # An enabled BP Notification Template overrides the
            # message content (not the shell/footer chrome) for this
            # notification_type. Any failure at all falls straight through
            # to the code default below — never a broken email.
            custom = _render_custom_template(notification_type, {
                "actor_name": actor_name or "", "task_key": task_key or "",
                "task_title": task_title or "", "message": message or "",
                "url": url, "comment_text": comment_text or "",
                "priority": priority or "", "due_date": str(due_date) if due_date else "",
                "from_status": from_status or "", "to_status": to_status or "",
            })
            if custom:
                custom_subject, custom_body = custom
                html = build_custom_notification_email(notification_type, task_key or "", custom_body, manage_url)
                subject = custom_subject
            else:
                html = build_notification_email(
                    ntype=notification_type,
                    actor_name=actor_name or "",
                    task_key=task_key or "",
                    task_title=task_title or "",
                    message=message or "",
                    url=url,
                    manage_url=manage_url,
                    comment_text=comment_text,
                    changes=changes,
                    priority=priority,
                    due_date=due_date,
                    from_status=from_status,
                    to_status=to_status,
                )
                subject = notification_subject(
                    notification_type,
                    actor_name or "",
                    task_key or "",
                    task_title or "",
                    from_status=from_status,
                    to_status=to_status,
                )

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=html,
            reference_doctype="BP Task" if task else None,
            reference_name=task or None,
            delayed=True,
            retry=1,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "bp_notification email failed")


import re as _re
_MENTION_TOKEN = _re.compile(r"@\[([^\]]+)\]\([^)]+\)")


def _strip_mentions(text: str) -> str:
    """Turn @[Name](userid) tokens into plain @Name for previews/emails."""
    if not text:
        return ""
    return _MENTION_TOKEN.sub(lambda m: "@" + m.group(1), text)


def _get_task_recipients(task_name: str, exclude_user: str) -> list:
    """Return assignees + reporter + watchers for a task, excluding the actor."""
    recipients = set()

    # Assignees
    for row in frappe.get_all("BP Task Assignee", filters={"parent": task_name}, pluck="user"):
        if row != exclude_user:
            recipients.add(row)

    # Reporter
    reporter = frappe.db.get_value("BP Task", task_name, "reporter")
    if reporter and reporter != exclude_user:
        recipients.add(reporter)

    # Watchers (explicit follows)
    for w in _get_watchers(task_name):
        if w != exclude_user:
            recipients.add(w)

    return list(recipients)


def _get_watchers(task_name: str) -> list:
    """Users explicitly watching a task."""
    if not task_name:
        return []
    return frappe.get_all("BP Task Watcher", filters={"task": task_name}, pluck="user")


def add_watcher(task_name: str, user: str):
    """Idempotently make a user watch a task (used by auto-watch + the API)."""
    if not task_name or not user or user == "Guest":
        return
    if frappe.db.exists("BP Task Watcher", {"task": task_name, "user": user}):
        return
    frappe.get_doc({
        "doctype": "BP Task Watcher",
        "task": task_name,
        "user": user,
        "project": frappe.db.get_value("BP Task", task_name, "project"),
    }).insert(ignore_permissions=True)


def _notify_comment(payload, actor, task_name, project):
    if not task_name:
        return
    comment_text = payload.get("comment_text", "")
    # Strip mention tokens + HTML for the preview text
    preview = _strip_mentions(comment_text)[:100].strip() if comment_text else ""
    actor_name = frappe.db.get_value("User", actor, "full_name") or actor

    task_key = frappe.db.get_value("BP Task", task_name, "task_key") or task_name

    # Commenting auto-subscribes user to the issue
    add_watcher(task_name, actor)

    # Mentioned users get a dedicated "Mention" (takes priority over a plain comment notif)
    mentioned = set(payload.get("mentions") or [])
    mentioned.discard(actor)
    for user in mentioned:
        add_watcher(task_name, user)  # mentioning someone makes them a watcher too
        _create_notification(
            user, "Mention", task_name, project, actor,
            f"{actor_name} mentioned you on {task_key}: {preview}",
            email_extras={"comment_text": preview},
        )

    # On edits we only ping the newly-mentioned; on a new comment everyone involved is notified
    if payload.get("mentions_only"):
        _push_notification_badge(mentioned, project)
        return

    message = f"{actor_name} commented on {task_key}: {preview}"
    recipients = set(_get_task_recipients(task_name, actor)) - mentioned
    for recipient in recipients:
        _create_notification(
            recipient, "Comment", task_name, project, actor, message,
            email_extras={"comment_text": preview},
        )

    _push_notification_badge(recipients | mentioned, project)


def _notify_assignment(payload, actor, task_name, project):
    assigned_user = payload.get("employee") or payload.get("assignee")
    if not assigned_user or not task_name:
        return
    actor_name = frappe.db.get_value("User", actor, "full_name") or actor
    task_data = frappe.db.get_value(
        "BP Task", task_name, ["task_key", "title", "priority", "due_date"], as_dict=True
    ) or {}
    task_key   = task_data.get("task_key") or task_name
    task_title = task_data.get("title")    or task_name
    message = f"{actor_name} assigned you to {task_key}: {task_title}"
    add_watcher(task_name, assigned_user)  # auto-watch on assignment
    _create_notification(
        assigned_user, "Assignment", task_name, project, actor, message,
        email_extras={
            "priority": task_data.get("priority"),
            "due_date": task_data.get("due_date"),
        },
    )
    _push_notification_badge({assigned_user}, project)


def _notify_status_change(payload, actor, task_name, project):
    if not task_name:
        return
    from_status = payload.get("from_status", "")
    to_status   = payload.get("to_status", "")
    actor_name  = frappe.db.get_value("User", actor, "full_name") or actor
    task_key    = frappe.db.get_value("BP Task", task_name, "task_key") or task_name
    message = f"{actor_name} changed status of {task_key} from {from_status} to {to_status}"

    recipients = set(_get_task_recipients(task_name, actor))
    for recipient in recipients:
        _create_notification(
            recipient, "Status Change", task_name, project, actor, message,
            email_extras={"from_status": from_status, "to_status": to_status},
        )
    _push_notification_badge(recipients, project)


def _notify_task_created(payload, actor, task_name, project):
    if not task_name or not project:
        return
    # Notify default assignee if different from creator
    default_assignee = frappe.db.get_value("BP Project", project, "default_assignee")
    if default_assignee and default_assignee != actor:
        actor_name = frappe.db.get_value("User", actor, "full_name") or actor
        task_key = frappe.db.get_value("BP Task", task_name, "task_key") or task_name
        task_title = frappe.db.get_value("BP Task", task_name, "title") or task_name
        message = f"{actor_name} created {task_key}: {task_title}"
        _create_notification(default_assignee, "Assignment", task_name, project, actor, message)
        _push_notification_badge({default_assignee}, project)


def _notify_task_updated(payload, actor, task_name, project):
    """Notify watchers when notable fields change on a task (the P0 gap)."""
    if not task_name:
        return
    changes = payload.get("changes") or []
    notable = [c for c in changes if c.get("field") in _NOTIF_WORTHY_FIELDS]
    if not notable:
        return

    actor_name = frappe.db.get_value("User", actor, "full_name") or actor
    task_key   = payload.get("task_key") or frappe.db.get_value("BP Task", task_name, "task_key") or task_name
    task_title = payload.get("title")    or frappe.db.get_value("BP Task", task_name, "title")    or task_name

    if len(notable) == 1:
        label   = _FIELD_LABEL.get(notable[0].get("field", ""), "a field")
        message = f"{actor_name} updated {label} on {task_key}: {task_title}"
    else:
        labels  = ", ".join(
            _FIELD_LABEL.get(c.get("field", ""), c.get("field", ""))
            for c in notable[:3]
        )
        message = f"{actor_name} updated {labels} on {task_key}: {task_title}"

    recipients = set(_get_task_recipients(task_name, actor))
    for recipient in recipients:
        _create_notification(
            recipient, "Update", task_name, project, actor, message,
            email_extras={"changes": notable},
        )
    _push_notification_badge(recipients, project)


def _notify_task_unassigned(payload, actor, task_name, project):
    """Notify the removed assignee (the other P0 gap)."""
    removed_user = payload.get("assignee")
    if not removed_user or not task_name:
        return
    actor_name = frappe.db.get_value("User", actor, "full_name") or actor
    task_key   = payload.get("task_key") or frappe.db.get_value("BP Task", task_name, "task_key") or task_name
    task_title = frappe.db.get_value("BP Task", task_name, "title") or task_name
    message    = f"{actor_name} unassigned you from {task_key}: {task_title}"
    _create_notification(removed_user, "Unassigned", task_name, project, actor, message)
    _push_notification_badge({removed_user}, project)


def _notify_approval_requested(payload, actor, task_name, project):
    """The designated approver was never told anything — request_approval()
    just flipped a field and returned. Notify them (audit 01 §A1)."""
    approver = payload.get("approver")
    if not approver or not task_name:
        return
    actor_name = frappe.db.get_value("User", actor, "full_name") or actor
    task_key   = frappe.db.get_value("BP Task", task_name, "task_key") or task_name
    task_title = frappe.db.get_value("BP Task", task_name, "title") or task_name
    message = f"{actor_name} requested your approval on {task_key}: {task_title}"
    add_watcher(task_name, approver)  # so they see the eventual decision too
    _create_notification(approver, "Approval Requested", task_name, project, actor, message)
    _push_notification_badge({approver}, project)


def _notify_approval_decided(payload, actor, task_name, project):
    """approve_task/reject_task also notified no one — the requester never
    learned the outcome. There's no persisted "who requested this", so
    notify the same recipient set every other task event does (assignees +
    reporter + watchers), which the requester is virtually always in
    (request_approval only fires from someone already looking at the task)."""
    if not task_name:
        return
    decision = payload.get("decision") or "decided"
    actor_name = frappe.db.get_value("User", actor, "full_name") or actor
    task_key   = frappe.db.get_value("BP Task", task_name, "task_key") or task_name
    task_title = frappe.db.get_value("BP Task", task_name, "title") or task_name
    message = f"{actor_name} {decision.lower()} {task_key}: {task_title}"

    recipients = set(_get_task_recipients(task_name, actor))
    for recipient in recipients:
        _create_notification(
            recipient, "Approval Decided", task_name, project, actor, message,
            email_extras={"from_status": "Pending", "to_status": decision},
        )
    _push_notification_badge(recipients, project)


def _notify_role_changed(payload, actor, project):
    """project.role_changed reaches only ReBAC sync today — nobody added to
    (or re-roled on) a project is ever told (audit 01 §B, the most damaging
    gap: for a partner-led product, the first experience is an agency adding
    a client user, and that user hears nothing)."""
    user = payload.get("user")
    if not user or not project:
        return
    old_role = payload.get("old_role")
    new_role = payload.get("new_role")
    actor_name   = frappe.db.get_value("User", actor, "full_name") or actor
    project_name = frappe.db.get_value("BP Project", project, "project_name") or project
    if old_role:
        message = f"{actor_name} changed your role on {project_name} to {new_role}"
    else:
        message = f"{actor_name} added you to {project_name} as {new_role}"
    _create_notification(
        user, "Role Changed", None, project, actor, message,
        email_extras={"from_status": old_role, "to_status": new_role},
    )
    _push_notification_badge({user}, project)


def send_due_date_reminders():
    """Daily scheduled job: remind assignees + watchers about due-soon / overdue tasks.

    - "Due Soon"  : open task due within the next 2 days
    - "Overdue"   : open task whose due date has passed
    De-duplicated to at most one reminder per (user, task, type) per day.
    """
    today = frappe.utils.getdate()
    soon_cutoff = frappe.utils.add_days(today, 2)

    # Bounded in SQL: any task overdue (due_date < today, unbounded into the
    # past) or due within the window is a candidate; NULL due_date fails the
    # comparison and is excluded automatically. Previously this pulled every
    # task that has EVER had a due_date set — including years-future ones —
    # into memory nightly and filtered in Python; that degrades linearly with
    # total task count forever.
    tasks = frappe.get_all(
        "BP Task",
        filters={"due_date": ["<=", soon_cutoff]},
        fields=["name", "task_key", "title", "project", "status", "due_date"],
    )
    completed_cache = {}

    for t in tasks:
        if not t.due_date:
            continue
        comp = completed_cache.get(t.project)
        if comp is None:
            comp = set(_completed_statuses(t.project))
            completed_cache[t.project] = comp
        if t.status in comp:
            continue  # done → no reminder

        due = frappe.utils.getdate(t.due_date)
        if due < today:
            ntype, msg = "Overdue", f"{t.task_key} is overdue (due {due}): {t.title}"
        elif due <= soon_cutoff:
            ntype, msg = "Due Soon", f"{t.task_key} is due {due}: {t.title}"
        else:
            continue

        recipients = set(frappe.get_all("BP Task Assignee", filters={"parent": t.name}, pluck="user"))
        recipients |= set(_get_watchers(t.name))
        for user in recipients:
            if _reminder_sent_today(user, t.name, ntype):
                continue
            # actor=None → system reminder; still honors mute + email_due_reminder pref
            _create_notification(user, ntype, t.name, t.project, None, msg)


def send_daily_digest():
    """Daily scheduled job: one summary email per user with their day's work."""
    if not _has_outgoing_email():
        return

    today = frappe.utils.getdate()
    # Candidate users = anyone with at least one open assigned task
    candidates = set(frappe.get_all("BP Task Assignee", pluck="user"))
    completed_cache = {}

    for user in candidates:
        if user in ("Guest", "Administrator"):
            continue
        pref = frappe.db.get_value(
            "BP Notification Preference", user, ["email_enabled", "email_digest"], as_dict=True
        )
        if pref and (not pref.email_enabled or not pref.email_digest):
            continue
        if not (frappe.db.get_value("User", user, "enabled") and "@" in user):
            continue

        task_names = frappe.get_all("BP Task Assignee", filters={"user": user}, pluck="parent")
        if not task_names:
            continue
        tasks = frappe.get_all(
            "BP Task",
            filters={"name": ["in", task_names]},
            fields=["name", "task_key", "title", "status", "project", "due_date", "priority"],
        )
        due_today, overdue, open_tasks = [], [], []
        for t in tasks:
            comp = completed_cache.get(t.project)
            if comp is None:
                comp = set(_completed_statuses(t.project))
                completed_cache[t.project] = comp
            if t.status in comp:
                continue
            open_tasks.append(t)
            if t.due_date:
                due = frappe.utils.getdate(t.due_date)
                if due < today:
                    overdue.append(t)
                elif due == today:
                    due_today.append(t)

        if not open_tasks:
            continue  # nothing to report → don't send an empty digest

        unread = frappe.db.count("BP Notification", {"recipient": user, "is_read": 0})
        user_full_name = frappe.db.get_value("User", user, "full_name") or user.split("@")[0].title()
        html = _build_digest_html(due_today, overdue, open_tasks, unread, user_full_name)
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
                recipients=[user],
                subject=subject,
                message=html,
                delayed=True,
                retry=1,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "bp daily digest failed")


def _build_digest_html(due_today, overdue, open_tasks, unread, user_name=""):
    from batch_projects.email_templates import build_digest_email
    return build_digest_email(
        user_name or "",
        [frappe._dict(t) for t in due_today],
        [frappe._dict(t) for t in overdue],
        [frappe._dict(t) for t in open_tasks],
        unread,
        frappe.utils.get_url(),
    )


def send_weekly_project_summary():
    """Weekly scheduled job: email project leads + managers a summary of their project."""
    if not _has_outgoing_email():
        return
    today = frappe.utils.getdate()
    week_ago = frappe.utils.add_days(today, -7)

    projects = frappe.get_all(
        "BP Project", filters={"status": "Active"},
        fields=["name", "project_name", "key", "lead"],
    )
    for p in projects:
        comp = set(_completed_statuses(p.name))
        tasks = frappe.get_all(
            "BP Task", filters={"project": p.name},
            fields=["status", "due_date", "creation", "completed_on"],
        )
        if not tasks:
            continue
        open_count = sum(1 for t in tasks if t.status not in comp)
        overdue = sum(1 for t in tasks if t.status not in comp and t.due_date and frappe.utils.getdate(t.due_date) < today)
        created_week = sum(1 for t in tasks if frappe.utils.getdate(t.creation) >= week_ago)
        completed_week = sum(
            1 for t in tasks
            if t.completed_on and frappe.utils.getdate(t.completed_on) >= week_ago
        )
        if not (open_count or created_week or completed_week):
            continue  # dormant project → skip

        # Recipients: lead + admins/managers
        recipients = set()
        if p.lead:
            recipients.add(p.lead)
        for m in frappe.get_all(
            "BP Project Member",
            filters={"parent": p.name, "role": ["in", ["Admin", "Manager"]]},
            pluck="user",
        ):
            recipients.add(m)

        summary_line = f"{p.project_name}: {completed_week} completed, {open_count} open, {overdue} overdue"
        html = _build_weekly_html(p.project_name, completed_week, created_week, open_count, overdue)

        for user in recipients:
            if user in ("Guest", "Administrator"):
                continue
            pref = frappe.db.get_value(
                "BP Notification Preference", user, ["email_enabled", "email_weekly_summary"], as_dict=True
            )
            if pref and (not pref.email_enabled or not pref.email_weekly_summary):
                continue
            if not (frappe.db.get_value("User", user, "enabled") and "@" in user):
                continue
            _send_notification_email(
                recipient=user, notification_type="Summary", task=None, task_key=None,
                task_title=None, project=p.name, actor_name=None, message=summary_line,
                message_html=html, cta_label="Open project",
            )


def run_due_soon_automations():
    """Daily job: fire `task.due_soon` automation rules for tasks whose due date
    is within the next 3 days and that aren't completed. De-duplicated so each
    task triggers the rule only once per due-soon window (not every day)."""
    from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import _projects_in_scope

    rules = frappe.get_all(
        "BP Automation Rule",
        filters={"is_active": 1, "trigger_event": "task.due_soon"},
        fields=["name", "scope", "project", "project_filter"],
    )
    # Must use _projects_in_scope, not a bare `{r["project"] for r in rules
    # if r.get("project")}` — the latter silently drops every workspace-
    # scope rule (project is blank by design for those), so a workspace-
    # wide "nag on due-soon" automation would never fire. _projects_in_scope
    # resolves both project- and workspace-scope rules the same way
    # run_overdue_automations already does below.
    projects = set()
    for r in rules:
        projects.update(_projects_in_scope(r))
    if not projects:
        return

    today = frappe.utils.getdate()
    horizon = frappe.utils.add_days(today, 3)
    dedup_after = frappe.utils.add_days(today, -4)  # one fire per due-soon window

    for project in projects:
        try:
            completed = set(frappe.get_cached_doc("BP Project", project).get_completed_statuses())
        except Exception:
            completed = set()
        tasks = frappe.get_all(
            "BP Task",
            filters={"project": project, "due_date": ["between", [str(today), str(horizon)]]},
            fields=["name", "task_key", "status"],
        )
        for t in tasks:
            if t.status in completed:
                continue
            if frappe.db.exists("BP Automation Run", {
                "task": t.name, "trigger_event": "task.due_soon",
                "run_at": [">", dedup_after],
            }):
                continue
            try:
                # Must go through _evaluate_automations, not a direct
                # run_for_event() call — the latter always evaluates
                # in-process regardless of site_config bp_automation_engine,
                # so a tenant running "gateway" mode would have its
                # scheduled/due-soon rules silently double-run in Python too
                # (or, worse, never routed through Go's engine at all).
                # _evaluate_automations is the one dispatch point everything
                # else in this file already goes through.
                _evaluate_automations("task.due_soon", {
                    "event": "task.due_soon", "project": project,
                    "task": t.name, "task_key": t.task_key,
                })
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"due_soon automation failed: {t.name}")
    frappe.db.commit()


def run_overdue_automations():
    """Daily job: fire `task.overdue` automation rules for tasks whose due date
    has already passed and that aren't completed. De-duplicated per-project
    (one fire per overdue window per project) exactly like due_soon — this
    scans every project holding an active task.overdue rule, project-scope or
    workspace-scope (project blank), the latter expanded to its project_filter
    or every project when empty."""
    from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
        _projects_in_scope,
    )

    rules = frappe.get_all(
        "BP Automation Rule",
        filters={"is_active": 1, "trigger_event": "task.overdue"},
        fields=["name", "scope", "project", "project_filter"],
    )
    if not rules:
        return

    projects = set()
    for r in rules:
        projects.update(_projects_in_scope(r))
    if not projects:
        return

    today = frappe.utils.getdate()
    dedup_after = frappe.utils.add_days(today, -1)

    for project in projects:
        try:
            completed = set(frappe.get_cached_doc("BP Project", project).get_completed_statuses())
        except Exception:
            completed = set()
        tasks = frappe.get_all(
            "BP Task",
            filters={"project": project, "due_date": ["<", str(today)]},
            fields=["name", "task_key", "status"],
        )
        for t in tasks:
            if t.status in completed:
                continue
            if frappe.db.exists("BP Automation Run", {
                "task": t.name, "trigger_event": "task.overdue",
                "run_at": [">", dedup_after],
            }):
                continue
            try:
                # Same bypass risk as due_soon above — route through the
                # shared dispatch point so bp_automation_engine ("gateway"
                # vs "python") is respected.
                _evaluate_automations("task.overdue", {
                    "event": "task.overdue", "project": project,
                    "task": t.name, "task_key": t.task_key,
                })
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"overdue automation failed: {t.name}")
    frappe.db.commit()


def send_scheduled_reports():
    """Hourly job: email saved reports that are scheduled to go out this hour.

    A report fires when the current site hour matches `schedule_hour` and the
    frequency window matches (Daily = every day, Weekly = matching weekday,
    Monthly = the 1st). `last_sent` guards against double-sends within the day.
    """
    if not _has_outgoing_email():
        return

    now = frappe.utils.now_datetime()
    cur_hour = now.hour
    cur_weekday = now.strftime("%A")
    is_month_start = now.day == 1

    reports = frappe.get_all(
        "BP Report",
        filters={"schedule_enabled": 1},
        fields=["name", "report_name", "project", "period", "schedule_frequency",
                "schedule_day", "schedule_hour", "schedule_recipients", "last_sent"],
    )
    for r in reports:
        if (r.schedule_hour or 0) != cur_hour:
            continue
        freq = r.schedule_frequency or "Weekly"
        if freq == "Weekly" and (r.schedule_day or "Monday") != cur_weekday:
            continue
        if freq == "Monthly" and not is_month_start:
            continue
        # Already sent in the last ~20h? skip (scheduler may run more than once).
        if r.last_sent and (now - frappe.utils.get_datetime(r.last_sent)).total_seconds() < 20 * 3600:
            continue

        # Revalidate at send time, not just at save_report — a recipient who
        # had access when the schedule was created but lost it since (left
        # the project, was disabled) must not keep receiving it (audit 07 G1).
        from batch_projects.api.board import resolve_report_recipients
        recipients, dropped = resolve_report_recipients(r.schedule_recipients or "", r.project)
        if dropped:
            frappe.logger("bp_reports").warning(
                f"Scheduled report {r.name} ({r.report_name}): dropped {len(dropped)} "
                f"unauthorized/unresolvable recipient(s) at send time: {dropped}"
            )
        if not recipients:
            continue

        try:
            html = _build_report_email_html(r)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"BP scheduled report failed: {r.name}")
            continue

        try:
            frappe.sendmail(
                recipients=recipients,
                subject=f"📊 {r.report_name} — scheduled report",
                message=html,
                reference_doctype="BP Report",
                reference_name=r.name,
            )
            frappe.db.set_value("BP Report", r.name, "last_sent", now, update_modified=False)
            # The only trace of a scheduled report send anywhere (audit 04
            # §E5 — no export/report events reach BP Audit Log at all).
            frappe.logger("bp_reports").info(
                f"Scheduled report {r.name} ({r.report_name}) sent to "
                f"{len(recipients)} recipient(s): {recipients}"
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"BP scheduled report email failed: {r.name}")
    frappe.db.commit()


def _build_report_email_html(r):
    """Build the scheduled report email via the premium email_templates module."""
    from batch_projects.api.board import get_reports
    from batch_projects.email_templates import build_report_email

    data      = get_reports(r.project or "all", r.period or "last_30_days")
    sb        = [s for s in (data.get("status_breakdown") or []) if s.get("count")]
    total     = data.get("total_tasks", 0)
    tp        = data.get("throughput") or []
    created   = sum(x.get("created", 0) for x in tp)
    completed = sum(x.get("completed", 0) for x in tp)
    url       = frappe.utils.get_url(f"/workspace/reports/{r.name}")
    scope     = "All projects" if not r.project else (
        frappe.db.get_value("BP Project", r.project, "project_name") or r.project)

    return build_report_email(
        r.report_name, scope, r.period or "last_30_days",
        sb, total, created, completed, url,
    )


def _build_weekly_html(project_name, done, created, open_count, overdue):
    from batch_projects.email_templates import build_weekly_email
    return build_weekly_email(project_name, done, created, open_count, overdue)


def send_view_subscriptions_daily():
    """Scheduled daily: process Daily view-subscriptions (and Weekly ones on Mondays)."""
    _send_view_subscriptions("Daily")
    if frappe.utils.getdate().weekday() == 0:  # Monday
        _send_view_subscriptions("Weekly")


_VIEW_FILTER_MAP = {
    "filterPriority": "priority", "filterType": "task_type",
    "filterAssignee": "assignee", "filterLabel": "labels",
}

def _digest_task_rows(tasks: list, limit: int = 15) -> str:
    """Build a simple HTML table of tasks for digest / summary emails."""
    rows = []
    for t in tasks[:limit]:
        key = frappe.utils.escape_html(t.get("task_key") or "")
        title = frappe.utils.escape_html(t.get("title") or "")
        url = _task_url(t.get("project"), t.get("task_key"))
        rows.append(f'<tr><td><a href="{url}">{key}</a></td><td>{title}</td></tr>')
    if len(tasks) > limit:
        rows.append(f'<tr><td colspan="2" style="text-align:center">…and {len(tasks) - limit} more</td></tr>')
    return f'<table style="width:100%;border-collapse:collapse;">{"".join(rows)}</table>'


def _send_view_subscriptions(frequency: str):
    if not _has_outgoing_email():
        return
    views = frappe.get_all(
        "BP View",
        filters={"subscribed": 1, "subscription_frequency": frequency},
        fields=["name", "view_name", "project", "filters", "owner"],
    )
    if not views:
        return
    from batch_projects.api.board import query_tasks  # local import avoids circular dep

    for v in views:
        owner = v.owner
        if owner in ("Guest", "Administrator"):
            continue
        if not (frappe.db.get_value("User", owner, "enabled") and "@" in owner):
            continue
        pref = frappe.db.get_value("BP Notification Preference", owner, "email_enabled")
        if pref == 0:
            continue

        try:
            config = json.loads(v.filters) if isinstance(v.filters, str) else (v.filters or {})
        except Exception:
            config = {}
        raw = config.get("filters") or {}
        qf = {}
        for src, dest in _VIEW_FILTER_MAP.items():
            if raw.get(src):
                qf[dest] = [raw[src]]
        if raw.get("search"):
            qf["search"] = raw["search"]

        try:
            res = query_tasks(project=v.project, filters=qf)
        except Exception:
            continue
        issues = res.get("issues", []) if isinstance(res, dict) else []
        if not issues:
            continue  # nothing matches → skip

        rows = _digest_task_rows(
            [frappe._dict(i) for i in issues], limit=15
        )
        html = (f'<div style="font-size:15px;font-weight:600;margin-bottom:10px">'
                f'{frappe.utils.escape_html(v.view_name)} — {len(issues)} matching</div>{rows}')
        summary = f"Saved view '{v.view_name}': {len(issues)} matching task(s)"
        key = frappe.db.get_value("BP Project", v.project, "key") or ""
        _send_notification_email(
            recipient=owner, notification_type="Summary", task=None, task_key=None,
            task_title=None, project=v.project, actor_name=None, message=summary,
            message_html=html, cta_label="Open view",
            cta_url=f"{frappe.utils.get_url()}/workspace/{key}/list" if key else None,
        )


def _completed_statuses(project: str) -> list:
    states = frappe.db.get_value("BP Project", project, "workflow_states")
    try:
        parsed = json.loads(states) if isinstance(states, str) else (states or [])
    except Exception:
        parsed = []
    return [s.get("name") for s in parsed if isinstance(s, dict) and s.get("category") == "completed"]


def _reminder_sent_today(user: str, task: str, ntype: str) -> bool:
    start = frappe.utils.get_datetime(frappe.utils.today())
    return bool(frappe.db.exists("BP Notification", {
        "recipient": user, "task": task,
        "notification_type": ntype, "creation": [">=", start],
    }))


def _get_project_members(project: str) -> list:
    """Users who are members of a project (for project-level notifications)."""
    if not project:
        return []
    return frappe.get_all("BP Project Member", filters={"parent": project}, pluck="user")


def _notify_sprint(event_name, payload, actor, project):
    if not project:
        return
    sprint_name = payload.get("sprint_name") or "Sprint"
    if event_name == SPRINT_STARTED:
        total = payload.get("total_issues") or 0
        message = f"Sprint “{sprint_name}” has started" + (f" — {total} issue(s) committed" if total else "")
    else:
        done = payload.get("completed_count") or 0
        carried = payload.get("incomplete_count") or 0
        message = f"Sprint “{sprint_name}” completed — {done} done"
        if carried:
            message += f", {carried} carried over"

    recipients = set(_get_project_members(project))
    recipients.discard(actor)
    for user in recipients:
        # task=None → project-level notification; honors mute (project) + email pref
        _create_notification(user, "Sprint", None, project, actor, message)
    _push_notification_badge(recipients, project)


def _push_notification_badge(recipients: set, project: str = None):
    """Push a realtime unread-count update to each recipient via bp-gateway's
    realtime plane. Was frappe.publish_realtime(event="bp_notification_count",
    user=user, ...) — dead for the identical reason _broadcast() was (see its
    docstring): this SPA has no socket.io connection, only bp-gateway's SSE
    plane, which never listened on Frappe's own native realtime. Sidebar.vue's
    matching window.frappe.realtime.on('bp_notification_count', ...) listener
    was equally dead (window.frappe.realtime doesn't exist here) — both sides
    replaced together, 2026-08-06.

    Routed per-recipient rather than a single project-wide publish because
    unread_count is personal; the gateway fans this out to every connected
    client who can see `project` (same as any other event), and the
    frontend listener discards anything whose "recipient" isn't itself —
    the same coarse-server/fine-client filtering pattern DrawCanvas.vue's
    presence and drawing-change listeners already use."""
    if not project:
        return
    from batch_projects import bridge
    for user in recipients:
        try:
            unread = frappe.db.count("BP Notification", {"recipient": user, "is_read": 0})
            bridge.publish_realtime_event("notification.badge", project, {
                "event": "notification.badge",
                "project": project,
                "recipient": user,
                "unread_count": unread,
            })
        except Exception:
            pass


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def build_changes(old_doc, new_doc, fields: list) -> list:
    """
    Compare old and new doc for a list of field names.
    Returns list of { field, from, to } for changed fields only.

    Usage:
        changes = build_changes(old, doc, ["status", "priority", "task_type"])
        if changes:
            emit(TASK_UPDATED, {"task": doc.name, ..., "changes": changes})
    """
    changes = []
    for field in fields:
        old_val = getattr(old_doc, field, None)
        new_val = getattr(new_doc, field, None)
        if old_val != new_val:
            changes.append({"field": field, "from": old_val, "to": new_val})
    return changes


def build_custom_field_changes(old_cfv: dict, new_cfv: dict) -> list:
    """
    Diff two custom_field_values dicts.
    Returns list of { field, from, to } using cf: prefix convention.
    """
    changes = []
    # Underscore-prefixed keys (e.g. "_checklist") are internal storage
    # piggybacking on this same JSON blob, not user-facing custom fields —
    # logging their raw values as "Field Edit" activity would just dump
    # checklist JSON into the task's activity feed on every edit.
    all_keys = {k for k in (set(old_cfv.keys()) | set(new_cfv.keys())) if not k.startswith("_")}
    for key in all_keys:
        old_val = old_cfv.get(key)
        new_val = new_cfv.get(key)
        if old_val != new_val:
            changes.append({
                "field": f"cf:{key}",
                "from": old_val,
                "to": new_val,
            })
    return changes