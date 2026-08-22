"""Whitelisted endpoints the bp-gateway agent calls back into.

The agent never holds transactional DB logic — it decides *when* (durable
timers, SLA windows, external webhooks, or — when `bp_automation_engine` is
"gateway" — matched event-driven rules too) and then forwards here, where the
actual write happens atomically inside Frappe with full ORM + permissions.

Endpoints:
    run_scheduled_event  ← the scheduler plane (recurring / SLA / deferred jobs)
    list_active_rules    ← gateway engine: per-project rule cache refresh
    apply_action          gateway engine: execute one matched rule's action
    run_external_event   ← the external-webhook plane (internal/premium/premium.go's
                            POST /v1/hooks/{token} — HMAC-verified, replay-guarded,
                            license-gated entirely on the gateway side before this
                            is ever called)
    create_webhook_token,
    list_webhook_tokens,
    revoke_webhook_token ← admin-facing: mint/inspect/revoke the tokens
                            run_external_event resolves

These are server-to-server. The agent authenticates with the service account
(api_key:api_secret) which must map to a System Manager; we re-assert that here
so a stray browser session can't drive automations.
"""

import json
import time
import uuid
from datetime import timezone

import frappe

# Attempts for the optimistic-lock retry in apply_action — a dispatched action
# racing the SPA's drag writes (move_task + reorder_tasks) needs a beat or two.
_CONFLICT_RETRIES = 3

from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
    run_scheduled,
)
from batch_projects.api.board import _ERP_DOC_EVENT_DOCTYPES


def _assert_service_caller():
    """Only the bridge service account (System Manager / Administrator) may call."""
    user = frappe.session.user
    if user == "Administrator":
        return
    if "System Manager" in frappe.get_roles(user):
        return
    frappe.throw("Not permitted", frappe.PermissionError)


def _as_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


@frappe.whitelist()
def run_scheduled_event(job_id=None, tenant=None, kind=None, event=None, payload=None, **_):
    """Called by the agent when a scheduled job fires.

    Body (from the agent's dispatch): {job_id, tenant, kind, event, payload}.
    ``payload`` is whatever Frappe registered for the job — for automation
    rules it carries {"rule": <name>, "project": <name>}.
    """
    _assert_service_caller()
    payload = _as_dict(payload)

    if kind == "task.recurring":
        task = payload.get("task")
        if not task:
            return {"status": "skipped", "reason": "no task in payload"}
        from batch_projects.batch_projects.doctype.bp_task.bp_task import spawn_recurring_occurrence
        status, message = spawn_recurring_occurrence(task)
        return {"status": status, "message": message}

    if kind in ("automation.scheduled", "automation.sla", "automation.deferred"):
        rule = payload.get("rule")
        if not rule:
            return {"status": "skipped", "reason": "no rule in payload"}
        status, message = run_scheduled(rule, {**payload, "event": event or kind, "job_id": job_id})
        return {"status": status, "message": message}

    return {"status": "skipped", "reason": f"unknown kind {kind!r}"}


_WORKSPACE_BUCKET = "__workspace__"

_RULE_CACHE_FIELDS = [
    "name", "rule_name", "trigger_event", "trigger_config", "conditions",
    "actions", "action_type", "action_config", "scope", "project_filter", "project",
]


@frappe.whitelist()
def list_active_rules(project=None, **_):
    """Called by the gateway automation worker to (re)build its rule cache —
    one call per bucket. `project=<name>` returns that project's own
    project-scope rules; `project="__workspace__"` returns every active
    workspace-scope rule (unfiltered — the gateway itself checks each rule's
    project_filter against the firing event's project, before condition
    evaluation). Excludes `schedule.*` rules —
    those stay on the existing scheduler path (run_scheduled_event above)
    regardless of engine.
    """
    _assert_service_caller()
    if not project:
        return []
    if project == _WORKSPACE_BUCKET:
        return frappe.get_all(
            "BP Automation Rule",
            filters={"scope": "workspace", "is_active": 1, "trigger_event": ["not like", "schedule.%"]},
            fields=_RULE_CACHE_FIELDS,
        )
    return frappe.get_all(
        "BP Automation Rule",
        filters={
            "scope": "project", "project": project, "is_active": 1,
            "trigger_event": ["not like", "schedule.%"],
        },
        fields=_RULE_CACHE_FIELDS,
    )


@frappe.whitelist()
def apply_action(rule=None, payload=None, **_):
    """Called by the gateway automation worker after it matched a rule against
    a published event. Runs the rule's FULL ordered action list via the
    EXISTING multi-action executor (bp_automation_rule `_run_actions` /
    `_build_context`) so status defaulting, per-action isolation, run
    logging, and depth tracking happen exactly the same way as the Python
    engine — this endpoint reuses those, it does not reimplement them. The
    gateway only decided WHICH rule matched; every action in it fires from
    this one call.
    """
    _assert_service_caller()
    payload = _as_dict(payload)
    if not rule or not frappe.db.exists("BP Automation Rule", rule):
        return {"status": "skipped", "message": f"rule {rule!r} not found"}

    from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
        _build_context,
        _run_actions,
        _aggregate_status,
        _log_run,
        _short_error,
        _update_rule_last_run,
    )

    rule_doc = frappe.get_doc("BP Automation Rule", rule)
    if not rule_doc.is_active:
        return {"status": "skipped", "message": "rule inactive"}

    # Execution traceability — one execution_id per gateway-dispatched fire,
    # correlation_id links back to the originating event across BP Activity
    # and BP Audit Log. Prefer the event_id emit() stamped on the payload
    # (the gateway's envelope carries it through, so several rules fired by
    # ONE event share a single correlation); fall back to a generated ID so
    # every run row is traceable even for a manually-dispatched action.
    payload["_execution_id"] = payload.get("_execution_id") or str(uuid.uuid4())
    payload["_correlation_id"] = (
        payload.get("_correlation_id") or payload.get("event_id") or payload["_execution_id"]
    )
    payload["_source"] = "gateway"

    depth = int(payload.get("depth", 0))
    frappe.flags.bp_automation_depth = depth + 1
    try:
        # Conflict retry: the engine is asynchronous now, so an action can race
        # the SPA's own follow-up writes (a drag = move_task then reorder_tasks
        # within ~200ms) and lose Frappe's optimistic lock. Every task-saving
        # action is check-and-skip idempotent, so re-running the action list
        # against a freshly loaded doc is safe.
        from frappe.exceptions import TimestampMismatchError

        status = message = None
        for attempt in range(1, _CONFLICT_RETRIES + 1):
            try:
                # Thread the attempt number into the payload so _run_actions →
                # _log_run records it on every run row — without this, a run
                # that "succeeded on retry 2/3" would write attempt=1 in the DB.
                payload["_attempt"] = attempt
                ctx = _build_context(payload)  # fresh task doc every attempt
                results = _run_actions(rule_doc, ctx, payload)
                status, message = _aggregate_status(results)
                if attempt > 1:
                    # Retry-attempt visibility (previously only the final
                    # attempt's outcome was ever recorded anywhere) — a run
                    # that needed 2 tries now reads that way in Run History
                    # instead of looking identical to one that succeeded
                    # first try.
                    message = f"{message} (succeeded on retry {attempt}/{_CONFLICT_RETRIES})"
                break
            except TimestampMismatchError:
                frappe.db.rollback()
                # frappe.throw() queues its red message into the request's
                # message_log before raising — that queued entry survives this
                # except block and would otherwise leak into _server_messages
                # on the eventual successful response. Discard just that one.
                frappe.clear_last_message()
                if attempt == _CONFLICT_RETRIES:
                    raise
                time.sleep(0.15 * attempt)
        _update_rule_last_run(rule, status)
        return {"status": status, "message": message}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"BP gateway-dispatched action failed: {rule}")
        msg = _short_error()
        if "TimestampMismatchError" in frappe.get_traceback():
            msg = f"{msg} (failed after {_CONFLICT_RETRIES} attempts — conflict retry exhausted)"
        _log_run(rule_doc, payload, "Failed", msg,
                 execution_id=payload.get("_execution_id"),
                 correlation_id=payload.get("_correlation_id"),
                 source="gateway",
                 attempt=payload.get("_attempt") or 1,
                 error_code=type(e).__name__)
        _update_rule_last_run(rule, "Failed")
        return {"status": "Failed", "message": msg}
    finally:
        frappe.flags.bp_automation_depth = depth


# ─── EXTERNAL WEBHOOKS (the piece bp-gateway's /v1/hooks/{token} calls) ─────

@frappe.whitelist()
def run_external_event(token=None, event=None, body=None, **_):
    """Landing point for bp-gateway's verified external webhook ingress.

    By the time this is called, the gateway (internal/premium/premium.go)
    has already: checked the tenant is licensed for "webhooks", verified the
    HMAC-SHA256 body signature, and de-duplicated by delivery id. This
    function's only job is authenticating the SERVICE CALLER (not the
    original third party — that trust boundary is the gateway's) and turning
    a (token, event, body) triple into a normal automation-engine dispatch,
    through the EXACT SAME path every other trigger uses
    (events._evaluate_automations — respects bp_automation_engine, so an
    external event still goes through the Go evaluator when that's enabled,
    never bypasses it).
    """
    _assert_service_caller()

    if not token or not frappe.db.exists("BP Webhook Token", {"token": token}):
        return {"status": "rejected", "message": "unknown token"}

    tok = frappe.get_doc("BP Webhook Token", {"token": token})
    if not tok.is_active:
        return {"status": "rejected", "message": "token revoked"}

    body_dict = _as_dict(body)
    # WORKPLAN-PHASE25 B3: cap what a third party's JSON body can inject into
    # the envelope — dict-only (_as_dict already guarantees that) and 32KB,
    # applied uniformly to BOTH the flattened top-level merge below and the
    # dedicated `body` key events.py._event_envelope threads through to Go —
    # a body this large has no business becoming per-condition/per-log data.
    if len(json.dumps(body_dict)) > 32 * 1024:
        frappe.log_error(f"webhook body exceeds 32KB, dropped (token={token})", "run_external_event")
        body_dict = {}

    # Best-effort usage tracking — must never block dispatch of the actual event.
    try:
        tok.db_set("call_count", (tok.call_count or 0) + 1, update_modified=False)
        tok.db_set("last_used", frappe.utils.now_datetime(), update_modified=False)
        tok.db_set("last_event", (event or "")[:140], update_modified=False)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "webhook token usage tracking failed")

    from batch_projects.entitlements import is_feature_enabled
    if not is_feature_enabled("automations"):
        return {"status": "skipped", "message": "automations not enabled for this tenant"}

    # Flatten the webhook body's top-level keys into the payload so rule
    # conditions can reference them directly (field: "amount", "status", ...)
    # via _resolve's existing _payload fallback — same convention erp.* events
    # already use for their task-less payloads.
    payload = {
        **{k: v for k, v in body_dict.items() if k not in ("event", "project")},
        "event": event,          # the third party's own event name/type
        "project": tok.project,  # None for scope="workspace"
        "_source": "webhook",    # traceability: this fire came from an external webhook
        # Dedicated nested copy — see events.py._event_envelope's own
        # "body" key comment. The flat spread above is kept too (pre-dates
        # this, and an existing rule/workflow may already reference a
        # top-level field name) — this ADDS the `body.<key>` convention
        # rather than replacing the flat one.
        "body": body_dict,
    }

    # Full emit(), not just the automation-evaluation step — matches every
    # other erp.* trigger in erp_triggers.py (cache invalidation/broadcast/
    # notifications all safely no-op on project=None, same as they already
    # do for any event with no project).
    from batch_projects.events import emit
    emit("external.webhook", payload)
    return {"status": "accepted"}


def _require_workspace_admin_for_tokens():
    """Token management is an admin action — reuses the same workspace-admin
    check the rest of the app's admin-only endpoints use."""
    from batch_projects import access
    if frappe.session.user == "Administrator":
        return
    if not access.is_workspace_admin():
        frappe.throw("You need workspace admin access for this.", frappe.PermissionError)


def _require_webhooks_feature():
    """`webhooks` is catalogued in _FEATURE_MIN_TIER (Team) but nothing ever
    called require_feature() for it — these 3 functions were only gated
    incidentally, via this module's blanket "automations" prefix in
    bp-gateway's urlToFeature table (both features happen to be Team tier
    today, so there's no actual under-charging bug). Making it explicit here so the catalog entry
    means something instead of being dead weight, and so a future tier split
    between "webhooks" and "automations" doesn't silently do nothing."""
    from batch_projects.entitlements import require_feature
    require_feature("webhooks")


@frappe.whitelist()
def create_webhook_token(label, scope="project", project=None):
    """Mint a new webhook token. Returns the token value ONCE (it's not a
    secret bp-gateway needs to keep private the way an API key is — it's an
    unguessable routing key — but there's still no reason to keep re-serving
    it after creation, so callers should copy it from this response)."""
    _require_workspace_admin_for_tokens()
    _require_webhooks_feature()
    if scope not in ("workspace", "project"):
        frappe.throw("scope must be 'workspace' or 'project'.")
    if scope == "project" and not project:
        frappe.throw("project is required when scope is 'project'.")

    doc = frappe.get_doc({
        "doctype": "BP Webhook Token",
        "label": label,
        "scope": scope,
        "project": project if scope == "project" else None,
        "is_active": 1,
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    return {
        "name": doc.name, "token": doc.token, "label": doc.label,
        "scope": doc.scope, "project": doc.project,
        "webhook_path": f"/v1/hooks/{doc.token}",
    }


@frappe.whitelist()
def list_webhook_tokens(project=None):
    """`project=<name>` (WORKPLAN-PHASE25 B3, new — the canvas's trigger.webhook
    dialog is this endpoint's first caller) scopes to that project's own
    tokens plus workspace-scope ones (project="") — same
    `["in", [project, ""]]` shape list_credentials already uses; Frappe Link
    fields store "" for "unset", not SQL NULL, so this matches correctly.
    No project given returns everything (unchanged from the original
    signature — no other caller exists yet)."""
    _require_workspace_admin_for_tokens()
    _require_webhooks_feature()
    filters = {"project": ["in", [project, ""]]} if project else {}
    return frappe.get_all(
        "BP Webhook Token",
        filters=filters,
        fields=["name", "label", "token", "scope", "project", "is_active",
                "call_count", "last_used", "last_event", "creation"],
        order_by="creation desc",
    )


@frappe.whitelist()
def revoke_webhook_token(name):
    _require_workspace_admin_for_tokens()
    _require_webhooks_feature()
    if not frappe.db.exists("BP Webhook Token", name):
        frappe.throw("Token not found.")
    frappe.db.set_value("BP Webhook Token", name, "is_active", 0)
    frappe.db.commit()
    return {"status": "revoked"}


# ─── NODE REGISTRY (WORKPLAN-PHASE24 02-NODE-LIBRARY.md) ───────────────────
#
# Single source of truth for the automation canvas's node palette AND the Go
# engine's node dispatch — both fetch/cache this instead of hand-maintaining
# their own copy (the same drift risk as entitlements.py vs bp-gateway's
# license.go — two independent copies of the same catalog silently diverging).
#
# Trigger/action entries deliberately reference the SAME strings already
# governing the underlying doctype (BP Automation Rule.trigger_event's Select
# options, _KNOWN_ACTION_TYPES) rather than re-declaring a parallel list —
# see _assert_registry_matches_doctype below, which is exercised by a probe,
# not just a comment promising it stays true.

from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
    _KNOWN_ACTION_TYPES,
)

_ACTION_TYPE_TO_NODE_TYPE = {
    "Change Status": "action.change_status",
    "Assign Issue": "action.assign_issue",
    "Set Priority": "action.set_priority",
    "Set Due Date": "action.set_due_date",
    "Add Label": "action.add_label",
    "Add Comment": "action.add_comment",
    "Notify": "action.notify",
    "Create Issue": "action.create_issue",
    "Update ERPNext Document": "action.update_erpnext_document",
    "Send Email": "action.send_email",
}

# Same labels board.py's _AUTOMATION_ACTIONS already uses, same icons
# AutomationRuleEditor's actionIcon() already uses — one vocabulary, not a
# second copy that could drift from the flat-rule builder's.
_ACTION_LABELS = {
    "Change Status": "Change the status", "Assign Issue": "Assign the task",
    "Set Priority": "Set the priority", "Set Due Date": "Set the due date",
    "Add Label": "Add label(s)", "Add Comment": "Post a comment",
    "Notify": "Send a notification", "Create Issue": "Create a new task",
    "Update ERPNext Document": "Update an ERPNext document",
    "Send Email": "Send an email",
}
_ACTION_ICONS = {
    "Change Status": "ArrowRightCircle", "Assign Issue": "UserPlus",
    "Set Priority": "Flag", "Set Due Date": "CalendarClock",
    "Add Label": "Tag", "Add Comment": "MessageSquare", "Notify": "Bell",
    "Create Issue": "FilePlus", "Update ERPNext Document": "FilePenLine",
    "Send Email": "Mail",
}

# ── Config schemas per action type (WORKPLAN-PHASE25 A2/C1) ─────────────────
# Field names/shapes below are NOT invented — each one is exactly what
# bp_automation_rule.py::_execute (and its _apply_assignees/_set_due_date/
# _add_labels/_notify/_create_linked_issue/_update_erpnext_document helpers)
# reads from `cfg`. Changing a field name here without changing the reader
# breaks the action silently — grep _execute before touching either side.
#
# `options_source` is a key straight into get_automation_options(project)'s
# response (board.py) — statuses/task_types/members/labels/priorities/
# erpnext_update_doctypes — so there is exactly one place that data is
# computed, not a second copy here. `show_if: {field, eq}` is UI-only (all
# fields still round-trip in `config`; unrelated ones are simply left at
# their default when hidden).
_ACTION_CONFIG_SCHEMAS = {
    "Change Status": [
        {"name": "status", "label": "Move task to", "type": "select",
         "options_source": "statuses", "allow_custom": True, "required": True,
         "description": "Pick an existing status, or type one — workspace-scope workflows "
                         "show no list here since different projects can define different ones."},
    ],
    "Assign Issue": [
        {"name": "assignees", "label": "Assign to", "type": "member", "multi": True,
         "options_source": "members", "required": True},
        {"name": "mode", "label": "Mode", "type": "select", "default": "set",
         "options": [{"value": "set", "label": "Replace existing assignees"},
                     {"value": "add", "label": "Add to existing assignees"}]},
    ],
    "Set Priority": [
        {"name": "priority", "label": "Set priority to", "type": "select",
         "options_source": "priorities", "required": True},
    ],
    "Set Due Date": [
        {"name": "mode", "label": "When", "type": "select", "default": "in_days",
         "options": [{"value": "in_days", "label": "N days from now"},
                     {"value": "on_date", "label": "A fixed date"}]},
        {"name": "days", "label": "Days from now", "type": "int",
         "show_if": {"field": "mode", "eq": "in_days"}},
        {"name": "date", "label": "Date", "type": "date",
         "show_if": {"field": "mode", "eq": "on_date"}},
    ],
    "Add Label": [
        {"name": "labels", "label": "Labels to add", "type": "select", "multi": True,
         "options_source": "labels", "allow_custom": True, "required": True,
         "description": "Pick existing labels or type a new one."},
    ],
    "Add Comment": [
        {"name": "comment", "label": "Comment text", "type": "template", "required": True},
    ],
    "Notify": [
        {"name": "to", "label": "Notify", "type": "select", "default": "assignees",
         "options": [{"value": "assignees", "label": "Assignees"},
                     {"value": "watchers", "label": "Watchers"},
                     {"value": "reporter", "label": "Reporter"},
                     {"value": "", "label": "Nobody by role"}]},
        {"name": "users", "label": "Also notify", "type": "member", "multi": True,
         "options_source": "members", "required": False,
         "description": "Specific people to notify in addition to the role above."},
        {"name": "message", "label": "Message", "type": "template", "required": True},
    ],
    "Create Issue": [
        {"name": "title", "label": "Task title", "type": "template", "required": True},
        {"name": "task_type", "label": "Type", "type": "select", "options_source": "task_types",
         "allow_custom": True},
        {"name": "priority", "label": "Priority", "type": "select",
         "options_source": "priorities", "default": "Medium"},
        {"name": "assignees", "label": "Assign to", "type": "member", "multi": True,
         "options_source": "members"},
        {"name": "link_to_trigger", "label": "Link to the triggering task", "type": "boolean",
         "default": True},
    ],
    "Update ERPNext Document": [
        {"name": "doctype", "label": "Document type", "type": "select",
         "options_source": "erpnext_update_doctypes", "required": True},
        {"name": "name_from", "label": "Find the document by", "type": "select",
         "default": "fixed",
         "options": [{"value": "fixed", "label": "A fixed document name"},
                     {"value": "task_field", "label": "A field on the triggering task"}]},
        {"name": "name", "label": "Document name", "type": "erp_link_search",
         "doctype_field": "doctype",
         "show_if": {"field": "name_from", "eq": "fixed"}},
        {"name": "field", "label": "Task field name", "type": "text",
         "show_if": {"field": "name_from", "eq": "task_field"},
         "description": "e.g. a custom field on BP Task holding the document's name."},
        {"name": "fields", "label": "Fields to update", "type": "keyvalue", "required": True,
         "keyvalue_doctype_field": "doctype",
         "description": "Field name → new value, e.g. status → Closed."},
    ],
    # WORKPLAN-PHASE25 C2 — reads _render_tokens()'s {{task.<field>}} syntax
    # (bp_automation_rule.py); "to" is a flat list of email strings, mixing
    # real member emails (options_source) and free-typed ones (allow_custom)
    # — see _send_email's own docstring for why no separate role/user split
    # like Notify's is needed here.
    "Send Email": [
        {"name": "to", "label": "To", "type": "member", "multi": True,
         "options_source": "members", "allow_custom": True, "required": True,
         "description": "Pick members, or type any email address."},
        {"name": "subject", "label": "Subject", "type": "template", "required": True},
        {"name": "message", "label": "Body", "type": "template", "required": True,
         "description": "Supports {{task.<field>}}, e.g. {{task.title}} or {{task.task_key}}."},
    ],
}

_NODE_REGISTRY = {
    # ── Triggers (exactly one per workflow) ──────────────────────────────
    "trigger.task_event": {
        "category": "trigger", "label": "Task event", "icon": "Zap",
        "maps_to_trigger_event": None,  # config.event picks the specific task.* value
        # task.due_soon / task.overdue deliberately NOT offered here: the
        # daily scheduled jobs that publish them
        # (events.py::run_due_soon_automations/run_overdue_automations) gate
        # entirely on "does an active BP Automation Rule with this
        # trigger_event exist" BEFORE scanning any tasks. A BP Workflow using
        # this event would never fire: the scanning job wouldn't even know
        # to look. Fixing that scan to also consider BP Workflow triggers is
        # real, separate work, not done here — offering the option in this
        # dropdown today would be a trigger that silently never fires, which
        # is worse than omitting it.
        "config_schema": [
            {"name": "event", "label": "When a task", "type": "select", "required": True,
             "options": [
                 {"value": "task.created", "label": "is created"},
                 {"value": "task.status_changed", "label": "changes status"},
                 {"value": "task.assigned", "label": "is assigned"},
                 {"value": "task.unassigned", "label": "is unassigned"},
                 {"value": "task.updated", "label": "is updated (any field)"},
                 {"value": "task.field_changed", "label": "has a specific field changed"},
                 {"value": "task.moved_sprint", "label": "is moved to another sprint"},
                 {"value": "task.deleted", "label": "is deleted"},
             ]},
            {"name": "from_status", "label": "From status", "type": "select",
             "options_source": "statuses", "allow_custom": True,
             "show_if": {"field": "event", "eq": "task.status_changed"}},
            {"name": "to_status", "label": "To status", "type": "select",
             "options_source": "statuses", "allow_custom": True,
             "show_if": {"field": "event", "eq": "task.status_changed"}},
            {"name": "field", "label": "Field", "type": "select",
             "options_source": "field_changed_fields",
             "show_if": {"field": "event", "eq": "task.field_changed"}},
            {"name": "conditions", "type": "conditions", "required": False},
        ],
    },
    "trigger.comment_added": {
        "category": "trigger", "label": "Comment added", "icon": "MessageSquare",
        "maps_to_trigger_event": "comment.added",
        "config_schema": [{"name": "conditions", "type": "conditions", "required": False}],
    },
    "trigger.schedule": {
        "category": "trigger", "label": "Schedule", "icon": "Clock",
        "maps_to_trigger_event": None,  # never envelope-matched (see workflowTriggerEvent) — polled via the bridge scheduler instead
        # WORKPLAN-PHASE25 B5 (SHOULD): recurring-interval only. schedule.
        # relative's semantics (BP Automation Rule's own
        # _run_relative_schedule — a daily scan across tasks for a due-date
        # proximity match) has no workflow-graph equivalent built yet;
        # offering it here would be the same "trigger that silently never
        # fires" trap B1/B2 already refused elsewhere in this registry —
        # add it back the day that scan exists for workflows too.
        "config_schema": [
            {"name": "every", "label": "Every", "type": "int", "required": True, "default": 1},
            {"name": "unit", "label": "Unit", "type": "select", "required": True, "default": "hours",
             "options": ["minutes", "hours", "days", "weeks"]},
        ],
    },
    "trigger.doc_event": {
        "category": "trigger", "label": "ERP doc event", "icon": "Calendar",
        "maps_to_trigger_event": "erp.doc_event",
        "config_schema": [
            {"name": "doctype", "label": "Document type", "type": "select", "required": True,
             "allow_custom": True,
             # A curated shortlist, not an exhaustive whitelist — the wildcard
             # hook (erp_triggers.on_any_doctype_event) genuinely covers every
             # Frappe doctype, so "allow_custom" lets someone type any other
             # one; this list just saves a search for the common cases.
             # Hoisted to board._ERP_DOC_EVENT_DOCTYPES so get_erp_doctype_fields_readonly
             # can whitelist against this exact set — no second hand-copy.
             "options": _ERP_DOC_EVENT_DOCTYPES,
             "description": "Any Frappe doctype — not limited to this list."},
            {"name": "erp_event", "label": "When the document is", "type": "select", "required": True,
             "options": [{"value": "after_insert", "label": "created"},
                         {"value": "on_update", "label": "saved"},
                         {"value": "on_submit", "label": "submitted"},
                         {"value": "on_cancel", "label": "cancelled"},
                         {"value": "on_trash", "label": "deleted"}]},
            {"name": "conditions", "type": "conditions", "required": False,
             # No static preset list (the fields differ per doctype) — the
             # frontend resolves real field metadata live from
             # get_erp_doctype_fields_readonly(config[doctype_field]) instead,
             # keyed off this pointer to the sibling "doctype" field above.
             "condition_fields_dynamic_doctype_field": "doctype",
             "description": "Field options load once you pick a document type above — real "
                             "Frappe fieldnames for that doctype, e.g. customer, grand_total."},
        ],
    },
    "trigger.webhook": {
        "category": "trigger", "label": "Webhook", "icon": "Webhook",
        "maps_to_trigger_event": "external.webhook",
        "config_schema": [
            {"name": "webhook_token", "type": "webhook_lifecycle", "required": True},
            {"name": "response_mode", "type": "select", "required": False, "default": "immediate",
             "options": [{"value": "immediate", "label": "Respond immediately (recommended)"}],
             "description": "\"Wait for the workflow to finish\" is deferred — a held-open HTTP "
                             "response needs mid-run state this engine doesn't persist yet."},
            {"name": "conditions", "type": "conditions", "required": False,
             "condition_fields_source": "webhook_condition_fields",
             "description": "The posted JSON body's own fields are available as body.<key>, "
                             "e.g. body.amount > 100 — see the URL panel above for a live example."},
        ],
    },

    # ── New event triggers (WORKPLAN-PHASE25 B2) — cheap, real events ───────
    #    already on the bus (events.py), config.event picks the specific one
    #    (same "one dropdown field" shape as trigger.task_event) rather than
    #    a node type per event.
    "trigger.project_event": {
        "category": "trigger", "label": "Project event", "icon": "Layers",
        "maps_to_trigger_event": None,
        "config_schema": [
            {"name": "event", "label": "When a project is", "type": "select", "required": True,
             "options": [{"value": "project.created", "label": "created"}]},
             # project.updated (events.PROJECT_UPDATED) is a DEAD event —
             # declared in events.py but never actually emit()'d anywhere.
             # Omitted for the same reason as task.due_soon/overdue/deleted
             # above: offering a trigger that can never fire is worse than
             # not offering it. Add it here the same day someone wires the emit.
            {"name": "conditions", "type": "conditions", "required": False,
             "condition_fields_source": "project_event_condition_fields"},
        ],
    },
    "trigger.sprint_event": {
        "category": "trigger", "label": "Sprint event", "icon": "Rows3",
        "maps_to_trigger_event": None,
        "config_schema": [
            {"name": "event", "label": "When a sprint is", "type": "select", "required": True,
             "options": [{"value": "sprint.started", "label": "started"},
                         {"value": "sprint.completed", "label": "completed"}]},
            {"name": "conditions", "type": "conditions", "required": False,
             "condition_fields_source": "sprint_event_condition_fields"},
        ],
    },
    "trigger.erp_finance": {
        "category": "trigger", "label": "ERP finance event", "icon": "CircleDollarSign",
        "maps_to_trigger_event": None,
        "config_schema": [
            {"name": "event", "label": "When", "type": "select", "required": True,
             "options": [{"value": "erp.invoice_submitted", "label": "a Sales Invoice is submitted"},
                         {"value": "erp.payment_received", "label": "a payment is received against an invoice"},
                         {"value": "erp.so_confirmed", "label": "a Sales Order is confirmed"}]},
            {"name": "conditions", "type": "conditions", "required": False,
             "condition_fields_source": "erp_finance_condition_fields",
             "description": "These events carry no task — condition fields are the event's own "
                             "payload: invoice / sales_order, customer, amount, outstanding "
                             "(invoice/payment only), currency, payment_entry (payment only)."},
        ],
    },
    "trigger.manual": {
        "category": "trigger", "label": "Run manually only", "icon": "MousePointerClick",
        "maps_to_trigger_event": "manual.run",
        # No config — Go's workflowTriggerEvent hardcodes the "manual.run"
        # literal for this node type; it never matches real bus traffic, only
        # a forced Test workflow run (WORKPLAN-PHASE25 A3, not yet built).
        "config_schema": [],
    },

    # ── Logic (new — the actual "graph" part; no Python execution today, ───
    #    Go-side only once 04 is built) ────────────────────────────────────
    "logic.if": {
        "category": "logic", "label": "If / Else", "icon": "GitBranch",
        "config_schema": [{"name": "conditions", "type": "conditions", "required": True}],
        "output_ports": [{"id": "true", "label": "true"}, {"id": "false", "label": "false"}],
    },
    "logic.filter": {
        "category": "logic", "label": "Filter", "icon": "Filter",
        "config_schema": [{"name": "conditions", "type": "conditions", "required": True}],
    },
    "logic.merge": {
        "category": "logic", "label": "Merge", "icon": "GitBranch",
        # "wait_all" (real branch-join semantics) used to be offered here
        # alongside "first" but the Go engine (graph.go::runLogicNode)
        # never read the mode at all — every merge behaved as "first"
        # regardless of what a user picked, silently. No config left to
        # offer honestly: a merge node just joins as soon as any wired
        # branch arrives, full stop, until real wait_all bookkeeping exists.
        "config_schema": [],
    },
    "logic.switch": {
        "category": "logic", "label": "Switch", "icon": "GitBranch",
        # output_ports is DELIBERATELY absent here — unlike logic.if's fixed
        # true/false, a switch's port count depends on how many `cases` the
        # user has configured (WORKPLAN-PHASE25 C5, cap 5 + 1 default). The
        # frontend derives ports from config.cases at node-create/save time
        # (switchOutputPorts() in automation-node-registry.js) rather than
        # from a static registry list — see that file before assuming this
        # entry needs one.
        "config_schema": [
            {"name": "field", "label": "Switch on", "type": "select", "required": True,
             "options_source": "condition_fields", "allow_custom": True,
             "description": "A trigger/task field, or a free entry like body.<key> for webhook payloads."},
            {"name": "cases", "label": "Cases", "type": "case_list", "required": True},
        ],
    },

    # ── Actions (existing 9 types, made node-addressable — see ─────────────
    #    02-NODE-LIBRARY.md §2). WORKPLAN-PHASE25 A2/C1: config_schema is now
    #    exploded per-field (_ACTION_CONFIG_SCHEMAS above), matching exactly
    #    what _execute() reads — no raw JSON in the default dialog view.
    #    Labels/icons match AutomationRuleEditor's own choices (actionIcon())
    #    so the two builders read as one product, not two.
    **{
        _ACTION_TYPE_TO_NODE_TYPE[action_type]: {
            "category": "action",
            "label": _ACTION_LABELS.get(action_type, action_type),
            "icon": _ACTION_ICONS.get(action_type, "CheckCircle2"),
            "maps_to_action_type": action_type,
            "config_schema": _ACTION_CONFIG_SCHEMAS.get(action_type, []),
        }
        for action_type in _KNOWN_ACTION_TYPES
    },

    # ── Integrations (Go-gateway-ONLY execution — see 02-NODE-LIBRARY.md §2, ─
    #    NO Python handler exists or should ever exist for any of these) ──────
    "integration.http_request": {
        "category": "integration", "label": "HTTP Request", "icon": "Globe",
        "gateway_only": True,
        "config_schema": [
            {"name": "method", "type": "select", "required": True,
             "options": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
            {"name": "url", "type": "text", "required": True},
            {"name": "headers", "type": "json", "required": False},
            {"name": "body_template", "type": "text", "required": False,
             "description": "Supports {{node_id.field}} referencing an upstream node's output."},
            {"name": "auth", "type": "credential", "required": False,
             "description": "{type: 'credential', credential: '<BP Integration Credential name>'} or {type: 'none'}. NEVER a raw secret — see 01-DATA-MODEL.md §1b."},
        ],
        "sub_ports": [{"id": "cred", "label": "Credential"}],
    },
    "integration.webhook_response": {
        "category": "integration", "label": "Webhook Response", "icon": "Webhook",
        "gateway_only": True,
        # WORKPLAN-PHASE25 B3 point 5: "wait_for_workflow" (a held-open HTTP
        # response) is explicitly deferred, not built half-way — this node
        # type has no meaning without it. hidden=True keeps it OUT of the
        # palette (see paletteGroups() in automation-node-registry.js) so a
        # user can't place a node that would never actually run, while
        # leaving the registry entry itself intact for any workflow saved
        # before this decision (get_node_registry still resolves its
        # label/icon rather than falling back to the generic placeholder).
        "hidden": True,
        "config_schema": [
            {"name": "status_code", "type": "int", "required": False, "default": 200},
            {"name": "body_template", "type": "text", "required": False},
        ],
    },

    # ── Messaging presets (WORKPLAN-PHASE25 C4) — each a tiny request-builder
    #    on top of graph.go's shared postJSON helper, not a copy of it. The
    #    `credential` field is a FLAT string (the credential's name) — unlike
    #    integration.http_request's `auth` (a {type,credential} union that
    #    also allows "none"), these three always require a credential, so
    #    there's no union to represent. `credential_label` is a companion
    #    "hidden" field: never rendered, but round-tripped through the config
    #    form so the sub-node chip's display label survives an Apply that
    #    didn't touch the credential (NodeConfigPanel only persists fields
    #    that are actually IN the schema — see its `visibleFields`/seed
    #    watcher before assuming an undeclared config key like this would
    #    survive on its own).
    "integration.slack": {
        "category": "integration", "label": "Slack message", "icon": "MessageSquare",
        "gateway_only": True,
        "config_schema": [
            {"name": "credential", "label": "Webhook", "type": "credential", "required": True,
             "description": "A 'webhook_url' credential — attach via the chip below this node."},
            {"name": "credential_label", "type": "hidden"},
            {"name": "message_template", "label": "Message", "type": "template", "required": True},
        ],
        "sub_ports": [{"id": "cred", "label": "Webhook", "field": "credential"}],
    },
    "integration.discord": {
        "category": "integration", "label": "Discord message", "icon": "MessageCircle",
        "gateway_only": True,
        "config_schema": [
            {"name": "credential", "label": "Webhook", "type": "credential", "required": True,
             "description": "A 'webhook_url' credential — attach via the chip below this node."},
            {"name": "credential_label", "type": "hidden"},
            {"name": "message_template", "label": "Message", "type": "template", "required": True},
        ],
        "sub_ports": [{"id": "cred", "label": "Webhook", "field": "credential"}],
    },
    "integration.telegram": {
        "category": "integration", "label": "Telegram message", "icon": "Send",
        "gateway_only": True,
        "config_schema": [
            {"name": "credential", "label": "Bot token", "type": "credential", "required": True,
             "description": "A 'bot_token' credential — attach via the chip below this node."},
            {"name": "credential_label", "type": "hidden"},
            {"name": "chat_id", "label": "Chat ID", "type": "text", "required": True},
            {"name": "message_template", "label": "Message", "type": "template", "required": True},
        ],
        "sub_ports": [{"id": "cred", "label": "Bot token", "field": "credential"}],
    },
    # C4 SHOULD tier — same shape as Slack (webhook_url credential, {"text": ...}
    # body), so they ride the same Go case rather than earning their own.
    "integration.teams": {
        "category": "integration", "label": "Microsoft Teams message", "icon": "Users",
        "gateway_only": True,
        "config_schema": [
            {"name": "credential", "label": "Webhook", "type": "credential", "required": True,
             "description": "A 'webhook_url' credential — attach via the chip below this node."},
            {"name": "credential_label", "type": "hidden"},
            {"name": "message_template", "label": "Message", "type": "template", "required": True},
        ],
        "sub_ports": [{"id": "cred", "label": "Webhook", "field": "credential"}],
    },
    "integration.googlechat": {
        "category": "integration", "label": "Google Chat message", "icon": "MessagesSquare",
        "gateway_only": True,
        "config_schema": [
            {"name": "credential", "label": "Webhook", "type": "credential", "required": True,
             "description": "A 'webhook_url' credential — attach via the chip below this node."},
            {"name": "credential_label", "type": "hidden"},
            {"name": "message_template", "label": "Message", "type": "template", "required": True},
        ],
        "sub_ports": [{"id": "cred", "label": "Webhook", "field": "credential"}],
    },
}

# Graph nodes can create externally visible effects. Retrying after a timeout
# or transport error can duplicate an effect that actually completed, so the
# current contract exposes failure routing but not automatic replay. Durable
# retries require a provider-aware idempotency key/claim model.
for _node_type, _entry in _NODE_REGISTRY.items():
    _entry["supports_retry"] = False
    _entry["supports_failure_policy"] = _entry["category"] in ("action", "integration")


def _assert_registry_matches_doctype():
    """Every action.* node type must correspond to a real, currently-known
    action type, and vice versa — run by test/probe, not trusted from the
    comment above alone."""
    registry_action_types = {
        v["maps_to_action_type"] for v in _NODE_REGISTRY.values() if v.get("maps_to_action_type")
    }
    if registry_action_types != _KNOWN_ACTION_TYPES:
        missing = _KNOWN_ACTION_TYPES - registry_action_types
        extra = registry_action_types - _KNOWN_ACTION_TYPES
        frappe.throw(f"Node registry drifted from _KNOWN_ACTION_TYPES: missing={missing} extra={extra}")


@frappe.whitelist()
def get_node_registry():
    """Fetched by the canvas UI (palette + config-form rendering) and cached
    by the Go engine the same way it already caches rules (60s TTL, see
    internal/automation/engine.go) — both read this, neither hand-maintains
    a separate copy."""
    _assert_registry_matches_doctype()
    return {node_type: {**meta, "type": node_type} for node_type, meta in _NODE_REGISTRY.items()}


# ─── GRAPH ENGINE CALLBACKS (WORKPLAN-PHASE24 04-GO-EXECUTION-ENGINE.md) ────
#
# The BP Workflow analogue of list_active_rules/apply_action above — a
# parallel set of endpoints for bp-gateway's graph.go, never touching
# BP Automation Rule's own tables.

_NODE_TYPE_TO_ACTION_TYPE = {v: k for k, v in _ACTION_TYPE_TO_NODE_TYPE.items()}


def _resolve_workflow_node_action(workflow_doc, node_id):
    """The one place run_workflow_node/run_local_workflow_step may learn what
    a node does. Both used to accept node_type/config as caller-supplied
    parameters and execute them directly — meaning whatever authority check
    ran against workflow_doc's OWN stored graph (workflow_security.py) could
    pass while a caller executed something else entirely under the same
    workflow/node names. Resolving here, from workflow_doc.nodes by node_id,
    makes validation and execution look at the same data by construction:
    there is no longer a second copy of the config for them to disagree
    about. Returns (action_type, config) or (None, None) if node_id doesn't
    name a real action node in this workflow's current, stored graph.
    """
    nodes = workflow_doc.get("nodes")
    if isinstance(nodes, str):
        try:
            nodes = json.loads(nodes) if nodes else []
        except (json.JSONDecodeError, TypeError):
            nodes = []
    if not isinstance(nodes, list):
        return None, None
    for node in nodes:
        if not isinstance(node, dict) or node.get("id") != node_id:
            continue
        action_type = _NODE_TYPE_TO_ACTION_TYPE.get(node.get("type"))
        if not action_type:
            return None, None
        config = node.get("config")
        return action_type, (config if isinstance(config, dict) else {})
    return None, None


_WORKFLOW_CACHE_FIELDS = [
    "name", "title", "scope", "project", "project_filter", "nodes", "edges",
    "automation_revision", "automation_definition_hash",
]


@frappe.whitelist()
def admit_workflow_execution(workflow=None, event_id=None, envelope=None,
                             workflow_revision=None, definition_hash=None, **_):
    _assert_service_caller()
    from batch_projects.workflow_execution import admit
    return admit(
        workflow, event_id, _as_dict(envelope),
        expected_revision=workflow_revision, expected_hash=definition_hash,
    )


@frappe.whitelist()
def claim_workflow_execution_lease(execution_id=None, owner=None, lease_seconds=60, **_):
    _assert_service_caller()
    if not execution_id or not owner:
        return {"claimed": False, "reason": "missing_execution_or_owner"}
    from batch_projects.workflow_execution import claim_lease
    return claim_lease(execution_id, owner, lease_seconds)


@frappe.whitelist()
def renew_workflow_execution_lease(execution_id=None, owner=None, lease_generation=None,
                                   lease_seconds=60, **_):
    _assert_service_caller()
    if not execution_id or not owner or lease_generation is None:
        return {"renewed": False, "reason": "missing_lease_context"}
    from batch_projects.workflow_execution import renew_lease
    return renew_lease(execution_id, owner, lease_generation, lease_seconds)


@frappe.whitelist()
def list_recoverable_workflow_executions(limit=100, **_):
    _assert_service_caller()
    from batch_projects.workflow_execution import recoverable_executions
    return recoverable_executions(limit)


@frappe.whitelist()
def begin_external_workflow_step(execution_id=None, node_id=None, owner=None,
                                 lease_generation=None, **_):
    _assert_service_caller()
    if not all((execution_id, node_id, owner)) or lease_generation is None:
        frappe.throw("Missing workflow execution step context")
    from batch_projects.workflow_execution import begin_external_step
    return begin_external_step(execution_id, node_id, owner, lease_generation)


@frappe.whitelist()
def finish_workflow_step(execution_id=None, step_id=None, owner=None, lease_generation=None,
                         status=None, result=None, error_code=None, error_message=None, **_):
    _assert_service_caller()
    if not all((execution_id, step_id, owner, status)) or lease_generation is None:
        frappe.throw("Missing workflow step completion context")
    from batch_projects.workflow_execution import finish_step
    return finish_step(
        execution_id, step_id, owner, lease_generation, status, _as_dict(result),
        error_code=error_code, error_message=error_message,
    )


@frappe.whitelist()
def finish_workflow_execution(execution_id=None, owner=None, lease_generation=None,
                              status=None, reason=None, **_):
    _assert_service_caller()
    if not all((execution_id, owner, status)) or lease_generation is None:
        frappe.throw("Missing workflow execution completion context")
    from batch_projects.workflow_execution import finish_execution
    return finish_execution(execution_id, owner, lease_generation, status, reason)


@frappe.whitelist()
def list_active_workflows(project=None, **_):
    """Called by the gateway's workflow cache refresh — one call per bucket,
    same shape as list_active_rules. No schedule-trigger exclusion here:
    unlike BP Automation Rule, a workflow's trigger type lives inside its
    trigger node, not a doctype-level trigger_event field, so a
    schedule-only workflow is simply never matched by processWorkflows
    (workflowTriggerEvent returns "" for trigger.schedule — see graph.go)."""
    _assert_service_caller()
    if not project:
        return []
    if project == _WORKSPACE_BUCKET:
        return frappe.get_all(
            "BP Workflow",
            filters={"scope": "workspace", "is_active": 1},
            fields=_WORKFLOW_CACHE_FIELDS,
        )
    return frappe.get_all(
        "BP Workflow",
        filters={"scope": "project", "project": project, "is_active": 1},
        fields=_WORKFLOW_CACHE_FIELDS,
    )


@frappe.whitelist()
def run_workflow_node(workflow=None, node=None, payload=None, **_):
    """Called by the gateway for every action.* node it walks. Reuses
    bp_automation_rule._execute() UNCHANGED (02-NODE-LIBRARY.md §2) — the
    node's own `config` becomes an action dict of the exact same shape a
    BP Automation Rule action already carries, so every existing action type
    (Change Status, Assign Issue, ...) works here with zero new code. Never
    writes to BP Automation Run — the gateway logs this call's outcome into
    BP Workflow Run via a SEPARATE log_workflow_run call, so this endpoint
    only executes and returns.

    Identifies the node to run by (workflow, node) only — node_type/config
    are never accepted as parameters. The gateway decides WHICH node fires;
    what that node actually does is resolved here, from workflow's own
    currently-stored graph, every time. A caller that could supply its own
    node_type/config could execute anything under any workflow's name,
    regardless of what workflow_security.py validated for that workflow —
    validation and execution must read the same data, not two copies of it.
    """
    _assert_service_caller()
    from batch_projects.entitlements import is_feature_enabled
    if not is_feature_enabled("automations"):
        # Defense in depth — the gateway already gates the whole workflow run
        # on this same "automations"/team-tier check before it ever calls
        # here (processWorkflows in graph.go), same as run_for_event's own
        # re-check. integration.* nodes deliberately reuse this one gate
        # rather than a separate tier.
        return {"status": "Skipped", "json": {"message": "automations not enabled for this tenant"}}

    if not workflow or not frappe.db.exists("BP Workflow", workflow):
        return {"status": "Failed", "json": {
            "message": f"workflow {workflow!r} not found",
            "error_code": "workflow_not_found",
        }}
    workflow_doc = frappe.get_doc("BP Workflow", workflow)
    action_type, config = _resolve_workflow_node_action(workflow_doc, node)
    if not action_type:
        return {"status": "Failed", "json": {
            "message": f"node {node!r} is not a known action node in workflow {workflow!r}",
            "error_code": "unknown_action_node",
        }}

    payload = _as_dict(payload)

    from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
        _build_context,
        _execute,
        _short_error,
    )

    depth = int(payload.get("depth", 0))
    frappe.flags.bp_automation_depth = depth + 1
    try:
        ctx = _build_context(payload)
        status, message = _execute({"type": action_type, "config": config}, ctx, payload)
        return {"status": status, "json": {"message": message}}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"BP workflow node failed: {workflow}/{node}")
        return {"status": "Failed", "json": {
            "message": _short_error(),
            "error_code": type(e).__name__,
        }}
    finally:
        frappe.flags.bp_automation_depth = depth


_LOCAL_WORKFLOW_ACTIONS = {
    "Change Status", "Assign Issue", "Set Priority", "Set Due Date",
    "Add Label", "Add Comment", "Create Issue", "Update ERPNext Document",
}


@frappe.whitelist()
def run_local_workflow_step(execution_id=None, node_id=None, payload=None, owner=None,
                            lease_generation=None, **_):
    """Execute a Frappe-only node and mark its durable step in one request TX.

    Do not catch action exceptions here.  A Frappe POST rolls the whole request
    back, including the business mutation, step write, and after-commit event
    callbacks.  That makes a lost response safely repeatable.

    Identified by (execution_id, node_id) only, same reasoning as
    run_workflow_node: node_type/config are resolved from the workflow's own
    currently-stored graph, never accepted from the caller. The workflow is
    itself resolved from execution_id (BP Workflow Execution.workflow) rather
    than trusted as a separate parameter, so there's nothing here a caller
    could point at a workflow/node pairing that doesn't actually exist.
    """
    _assert_service_caller()
    if not all((execution_id, node_id, owner)) or lease_generation is None:
        frappe.throw("Missing local workflow step context")

    workflow_name = frappe.db.get_value("BP Workflow Execution", execution_id, "workflow")
    if not workflow_name or not frappe.db.exists("BP Workflow", workflow_name):
        frappe.throw("Workflow execution has no resolvable workflow.", frappe.PermissionError)
    workflow_doc = frappe.get_doc("BP Workflow", workflow_name)
    action_type, config = _resolve_workflow_node_action(workflow_doc, node_id)
    if action_type not in _LOCAL_WORKFLOW_ACTIONS:
        frappe.throw("Workflow action is not local-atomic")

    payload = _as_dict(payload)

    from batch_projects.workflow_execution import finish_step, get_or_create_step
    from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import (
        _build_context,
        _execute,
    )

    step = get_or_create_step(execution_id, node_id, "frappe_atomic", owner, lease_generation)
    if step["effect_kind"] != "frappe_atomic":
        frappe.throw("Workflow step effect kind changed")
    if step["status"] == "succeeded":
        return step["result"]
    if step["status"] in ("failed", "needs_review", "dispatching"):
        return {
            "status": "Failed", "json": {"message": step["error_message"] or step["status"],
                                           "error_code": step["error_code"] or step["status"]},
        }

    depth = int(payload.get("depth", 0))
    previous_defer = getattr(frappe.flags, "bp_defer_workflow_events", False)
    frappe.flags.bp_automation_depth = depth + 1
    frappe.flags.bp_defer_workflow_events = True
    try:
        ctx = _build_context(payload)
        status, message = _execute({"type": action_type, "config": config}, ctx, payload)
        result = {"status": status, "json": {"message": message}}
        terminal = "failed" if status == "Failed" else "succeeded"
        return finish_step(
            execution_id, step["step_id"], owner, lease_generation, terminal,
            result=result,
            error_code="local_action_failed" if terminal == "failed" else None,
            error_message=message if terminal == "failed" else None,
        )["result"]
    finally:
        frappe.flags.bp_automation_depth = depth
        frappe.flags.bp_defer_workflow_events = previous_defer


_WORKFLOW_RUN_SOURCES = {"event", "schedule", "gateway", "webhook", "manual"}


def _workflow_run_datetime(value):
    if not value:
        return None
    try:
        parsed = frappe.utils.get_datetime(value)
        # Gateway timestamps use RFC3339 UTC.  Frappe preserves their tzinfo,
        # while MariaDB DATETIME rejects an offset suffix, so persist the
        # equivalent naive UTC datetime.
        if getattr(parsed, "tzinfo", None):
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


@frappe.whitelist()
def log_workflow_run(workflow=None, run_id=None, node_id=None, node_type=None, status=None,
                     message=None, correlation_id=None, source=None, attempt=1,
                     started_at=None, finished_at=None, error_code=None, execution_id=None, **_):
    """Best-effort per-node run log (mirrors bp_automation_rule._log_run's
    swallow-everything discipline — logging must never break the graph
    walk). Per-node only — the run's overall status is a SEPARATE call, see
    report_workflow_run below."""
    _assert_service_caller()
    try:
        started = _workflow_run_datetime(started_at)
        finished = _workflow_run_datetime(finished_at)
        duration_ms = None
        if started and finished:
            duration_ms = max(0, int((finished - started).total_seconds() * 1000))
        try:
            attempt = max(1, int(attempt or 1))
        except (TypeError, ValueError):
            attempt = 1
        frappe.get_doc({
            "doctype": "BP Workflow Run",
            "workflow": workflow,
            "run_id": run_id,
            "execution": execution_id or None,
            "node_id": node_id,
            "node_type": node_type,
            "status": status,
            "message": (message or "")[:500],
            "run_at": frappe.utils.now_datetime(),
            "correlation_id": correlation_id or None,
            "source": source if source in _WORKFLOW_RUN_SOURCES else None,
            "attempt": attempt,
            "started_at": started,
            "finished_at": finished,
            "duration_ms": duration_ms,
            "error_code": (error_code or "")[:140] or None,
        }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"log_workflow_run failed: {workflow}/{run_id}")
    return {"status": "logged"}


@frappe.whitelist()
def report_workflow_run(workflow=None, run_id=None, status=None, **_):
    """Called exactly once per graph walk, after runWorkflow finishes
    (graph.go's reportWorkflowRun, deferred so it fires on every return path
    — cycle, missing trigger, or a normal walk). Updates
    BP Workflow.last_run_at/last_run_status — previously nothing wrote these
    fields at all."""
    _assert_service_caller()
    if not workflow or not status:
        return {"status": "skipped", "reason": "missing workflow or status"}
    try:
        # Edge-triggered notify, same posture as
        # bp_automation_rule._update_rule_last_run: alert once when a
        # workflow starts failing, not once per run while it stays broken.
        prev = frappe.db.get_value("BP Workflow", workflow, "last_run_status")
        frappe.db.set_value("BP Workflow", workflow, {
            "last_run_at": frappe.utils.now_datetime(),
            "last_run_status": status,
        })
        if status == "Failed" and prev != "Failed":
            _notify_workflow_failure(workflow)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"report_workflow_run failed: {workflow}/{run_id}")
    return {"status": "recorded"}


def _notify_workflow_failure(workflow):
    """Same gap as bp_automation_rule._notify_rule_failure, for the Go-
    gateway-executed graph workflows — nothing ever told anyone when one
    started failing. Best-effort, never raises."""
    try:
        wf = frappe.db.get_value("BP Workflow", workflow, ["title", "project", "owner"], as_dict=True)
        if not wf or not wf.owner:
            return
        from batch_projects.events import _create_notification
        _create_notification(
            recipient=wf.owner, notification_type="Automation Failed",
            task=None, project=wf.project, actor="Administrator",
            message=f'Workflow "{wf.title or workflow}" just failed. Check its Executions tab.',
        )
    except Exception:
        pass
