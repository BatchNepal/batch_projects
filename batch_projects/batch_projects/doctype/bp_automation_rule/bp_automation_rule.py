"""
BP Automation Rule
──────────────────
A "When → If → Then" rule — the recipe/trigger-action shape enterprise
automation tools converge on — v2: workspace scope + ordered
multi-action list + richer triggers.

    WHEN  a trigger event fires                    (trigger_event + trigger_config)
    IF    the conditions match the task             (conditions)
    THEN  run the actions, IN ORDER                  (actions = [{type, config}, ...])

Scope:
    project    (default) — fires only for its own `project`. Project-Admin bar.
    workspace  — fires for every project, or the ones listed in `project_filter`
                 (empty = all). Workspace-admin only. `project_filter` is
                 checked BEFORE condition evaluation (cheap reject) — both here
                 and in the Go gateway engine.

The engine entry point is `run_for_event(event_name, payload)`, called from
`batch_projects.events.emit()` for every mutation. Rules never break the
mutation that triggered them — every rule runs in its own try/except, and
every ACTION within a rule runs in ITS OWN try/except too (`_run_actions`):
one failing action logs its own `BP Automation Run` row (with `action_index`)
and the loop continues — it never aborts the rest of the rule.

─── conditions JSON ──────────────────────────────────────────────────────────
Either a bare list (all clauses ANDed):

    [ {"field": "priority", "op": "eq", "value": "Highest"} ]

…or an object with "all" / "any" groups:

    {"all": [ ... ], "any": [ ... ]}

A clause is {"field", "op", "value"}. Resolvable fields are any BP Task field
(status, priority, task_type, story_points, due_date, billable …) plus the
synthetic fields: to_status, from_status (status_changed events) and event.
The "labels" and "assignees" fields resolve to lists; "cf:<id>" reads a
custom field value.

Operators: eq ne in nin gt gte lt lte contains changed is_set is_not_set
  - changed: true when the field is in this event's changed-set (value ignored)
  - contains: substring (strings) or membership (lists)

THIS MATCHER (`_match` / `_match_clause` / `_resolve`) IS FINISHED — v2 adds
NO new op and no new resolvable synthetic field. The two new trigger types
below (`task.field_changed`, `task.moved_sprint`) are NOT new bus events; they
compile to a pre-check read directly off the event payload's own `changes`
list (`_compiled_trigger_matches`, using the exact same "is this field in the
changed-set" / "does it equal this value" building blocks as the `changed`/
`eq` ops — just evaluated ahead of, not inside, `_match_clause`, since a
"from" comparison for an arbitrary field has no home in `_resolve` today).
The rule's own (user-authored) `conditions` still apply on top, unchanged.

─── trigger_config JSON (only for task.field_changed / schedule.relative) ────
task.field_changed : {"field": "priority", "from": "Low", "to": "High"}
                     ("from"/"to" optional — bare "field" alone fires on ANY
                     change to that field, mirroring the "changed" op)
schedule.relative  : {"field": "due_date", "offset_days": 3, "direction":
                     "before"|"after"} — generalizes task.due_soon to any
                     date field. Registered as a fixed daily poll on the
                     bridge scheduler (interval_seconds auto-set to 86400);
                     when its own timer fires, `_run_relative_schedule` scans
                     for tasks whose `field` lands on today ± offset_days
                     across the rule's project (or project_filter/workspace).

─── actions JSON ─────────────────────────────────────────────────────────────
Ordered list: [{"type": <Action Type>, "config": {...}}, ...], run in sequence.
Same action bodies as before, just addressed by `action["type"]`/
`action["config"]` instead of the old single `rule.action_type`/
`rule.action_config` pair (kept, hidden+read-only, for one release —
`_get_actions` falls back to them for any not-yet-migrated row):

Change Status : {"status": "Done"}
Assign Issue  : {"assignees": ["a@x.com", ...], "mode": "set"|"add"}  (default set)
Notify        : {"to": "assignees"|"watchers"|"reporter", "users": [...],
                 "message": "..."}
Create Issue  : {"title": "...", "task_type": "Task", "status": "...",
                 "priority": "Medium", "assignees": [...],
                 "link_to_trigger": true}   (link type "relates to")
Update ERPNext Document : {"doctype": "Sales Invoice"|"Sales Order"|"Timesheet"|"ToDo",
                 "name_from": "fixed"|"task_field"|"cf:<id>", "name": "...",
                 "field": <task fieldname, when name_from="task_field">,
                 "fields": {fieldname: value, ...}}
                 Gateway-engine only — see _ERPNEXT_DOCTYPE_WHITELIST.
"""

import frappe
import json
import re
from frappe.model.document import Document


# Max chained automations (rule → save → event → rule …) before we stop,
# so a self-referential rule can never loop forever.
_MAX_DEPTH = 5

# "Update ERPNext Document" may only touch these — a rule builder must never
# become a way to write arbitrary doctypes (e.g. User, BP Project) via config.
_ERPNEXT_DOCTYPE_WHITELIST = ("Sales Invoice", "Sales Order", "Timesheet", "ToDo")

_KNOWN_ACTION_TYPES = {
    "Change Status", "Assign Issue", "Set Priority", "Set Due Date",
    "Add Label", "Add Comment", "Notify", "Create Issue", "Update ERPNext Document",
    "Send Email",
}

# Bus events (events.emit() names) that ALSO carry compiled-trigger rules.
# task.updated already fires with a generic {field, from, to} `changes` list
# for every tracked field (see bp_task.py::on_update) — task.field_changed and
# task.moved_sprint are both refinements of that same event, resolved by
# _compiled_trigger_matches() rather than being distinct bus events.
_COMPILED_TRIGGERS_FOR_BUS_EVENT = {
    "task.updated": ("task.field_changed", "task.moved_sprint"),
}


class BPAutomationRule(Document):

    def validate(self):
        self._validate_json("conditions")
        self._validate_json("action_config")
        self._validate_json("actions")
        self._validate_json("project_filter")
        self._validate_json("trigger_config")

        if self.scope not in ("project", "workspace"):
            frappe.throw("Scope must be 'project' or 'workspace'.")
        if self.scope == "project" and not self.project:
            frappe.throw("Project-scope rules require a Project.")
        if self.scope == "workspace":
            # Workspace rules never carry a project of their own — project_filter
            # (or nothing, meaning "every project") is the only scoping knob.
            self.project = None

        actions = _parse(self.actions)
        if not isinstance(actions, list):
            frappe.throw("Actions must be an ordered list.")
        for action in actions:
            if not isinstance(action, dict):
                frappe.throw("Each action must be an object with 'type' and 'config'.")
            _validate_action(action)
        if not actions and self.action_type:
            # Legacy single-action row (pre-migration, or a caller that still
            # only sets the old fields) — same per-type checks, no silent gap.
            _validate_action({"type": self.action_type, "config": _parse(self.action_config)})

        if self.trigger_event == "task.field_changed":
            if not (_parse(self.trigger_config) or {}).get("field"):
                frappe.throw("'When a field changes' rules need a Field configured.")
        if self.trigger_event == "schedule.relative":
            if not (_parse(self.trigger_config) or {}).get("field"):
                frappe.throw("'Relative to a date' rules need a Field configured.")
            if not self.interval_seconds:
                # Fixed daily poll cadence — the builder doesn't expose an
                # interval control for this trigger, unlike schedule.recurring.
                self.interval_seconds = 86400

        if self._is_scheduled() and int(self.interval_seconds or 0) <= 0:
            frappe.throw("Recurring rules require a positive Interval (seconds).")

    def _validate_json(self, fieldname):
        raw = self.get(fieldname)
        if not raw:
            return
        try:
            json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            frappe.throw(f"{fieldname} must be valid JSON.")

    # ── Bridge scheduler registration ─────────────────────────────────────────
    # Scheduled rules (trigger_event "schedule.*") run on the Go agent's durable
    # timer, not in Frappe. We register the job on save and cancel it on delete
    # or deactivation. Registration is best-effort: a down/unconfigured bridge
    # must never block editing the rule.

    def _is_scheduled(self) -> bool:
        return (self.trigger_event or "").startswith("schedule.")

    def on_update(self):
        # Skip the bridge entirely for plain event rules with nothing registered.
        if not self._is_scheduled() and not self.bridge_job_id:
            return
        self._sync_schedule()

    def on_trash(self):
        if self.bridge_job_id:
            from batch_projects import bridge
            bridge.cancel_scheduled_job(self.bridge_job_id)

    def _sync_schedule(self):
        from batch_projects import bridge
        from frappe.utils import get_datetime

        # Always clear the old registration first — covers edits, interval
        # changes, and deactivation. Idempotent: re-register below if still due.
        if self.bridge_job_id:
            bridge.cancel_scheduled_job(self.bridge_job_id)
            self.db_set("bridge_job_id", None, update_modified=False)

        if not (self._is_scheduled() and self.is_active):
            return

        interval = int(self.interval_seconds or 0)
        run_at, delay = None, None
        if self.first_run:
            run_at = int(get_datetime(self.first_run).timestamp())
        else:
            delay = interval or 60  # first fire one interval from now

        job_id = bridge.register_scheduled_job(
            kind="automation.scheduled",
            event=self.trigger_event,
            payload={"rule": self.name, "project": self.project},
            run_at=run_at,
            delay_seconds=delay,
            interval_seconds=interval,
        )
        if job_id:
            self.db_set("bridge_job_id", job_id, update_modified=False)
        elif bridge.is_configured():
            frappe.msgprint(
                "Could not register this recurring rule with the automation agent. "
                "It will not fire until re-saved.",
                indicator="orange", alert=True,
            )


def _validate_action(action: dict):
    a_type = action.get("type")
    cfg = action.get("config") or {}

    if a_type == "Change Status":
        if not cfg.get("status"):
            frappe.throw("Change Status actions require a 'status' in Config.")
    elif a_type == "Send Email":
        if not cfg.get("to"):
            frappe.throw("Send Email actions require at least one recipient in Config.")
        if not (cfg.get("message") or "").strip():
            frappe.throw("Send Email actions require a message body in Config.")
    elif a_type == "Create Issue":
        if not cfg.get("title"):
            frappe.throw("Create Issue actions require a 'title' in Config.")
    elif a_type == "Update ERPNext Document":
        # Only meaningful when the Go gateway decides *when* to fire — the
        # open Python engine must never be a path to this action.
        engine = (frappe.conf.get("bp_automation_engine") or "python").lower()
        if engine != "gateway":
            frappe.throw("Update ERPNext Document requires the gateway automation engine.")
        if cfg.get("doctype") not in _ERPNEXT_DOCTYPE_WHITELIST:
            frappe.throw(
                "Update ERPNext Document only supports: "
                + ", ".join(_ERPNEXT_DOCTYPE_WHITELIST) + "."
            )
        if not cfg.get("fields"):
            frappe.throw("Update ERPNext Document actions require at least one field to set.")
        name_from = cfg.get("name_from") or "fixed"
        if name_from == "fixed" and not cfg.get("name"):
            frappe.throw("Update ERPNext Document actions need a document name (or a different Name source).")
        if name_from == "task_field" and not cfg.get("field"):
            frappe.throw("Update ERPNext Document actions using 'Task field' need a Field configured.")
    elif a_type not in _KNOWN_ACTION_TYPES:
        frappe.throw(f"Unknown action type '{a_type}'.")


# ─── ENGINE ────────────────────────────────────────────────────────────────

_RULE_FIELDS = [
    "name", "rule_name", "scope", "project", "project_filter",
    "trigger_event", "trigger_config", "conditions",
    "actions", "action_type", "action_config",
]


def run_for_event(event_name: str, payload: dict):
    """
    Evaluate and execute every active rule (project-scope for this project,
    plus workspace-scope rules whose project_filter matches) whose trigger
    matches this event — directly, or via a compiled trigger (see module
    docstring). Called from events.emit(). Must never raise — a failing rule
    is logged, not propagated to the user's save.

    `project` may be None — genuinely workspace-wide events with no single
    owning project (external.webhook is the first of these: a third-party
    system POSTing to a workspace-level hook isn't "about" any one project).
    Project-scope rules are skipped entirely in that case (nothing to scope
    them to); only workspace-scope rules with an EMPTY project_filter apply
    (a workspace rule deliberately narrowed to specific projects has nothing
    to match against with no project in the event).
    """
    project = payload.get("project")

    # Monetization gate: automations run only on Team tier and above. One
    # flag for the whole surface — workspace scope rides the same gate.
    from batch_projects.entitlements import is_feature_enabled
    if not is_feature_enabled("automations"):
        return

    depth = frappe.flags.get("bp_automation_depth", 0)
    if depth >= _MAX_DEPTH:
        return  # runaway / deep chain — stop quietly

    trigger_events = [event_name, *_COMPILED_TRIGGERS_FOR_BUS_EVENT.get(event_name, ())]

    project_rules = []
    if project:
        project_rules = frappe.get_all(
            "BP Automation Rule",
            filters={
                "scope": "project", "project": project, "is_active": 1,
                "trigger_event": ["in", trigger_events],
            },
            fields=_RULE_FIELDS,
        )
    workspace_rules = frappe.get_all(
        "BP Automation Rule",
        filters={"scope": "workspace", "is_active": 1, "trigger_event": ["in", trigger_events]},
        fields=_RULE_FIELDS,
    )
    if project:
        workspace_rules = [r for r in workspace_rules if _project_filter_matches(r, project)]
    else:
        workspace_rules = [r for r in workspace_rules if not _parse(r.get("project_filter"))]

    rules = project_rules + workspace_rules
    if not rules:
        return

    ctx = _build_context(payload)

    frappe.flags.bp_automation_depth = depth + 1
    try:
        for rule in rules:
            try:
                if rule.trigger_event != event_name and not _compiled_trigger_matches(rule, payload):
                    continue
                if not _match(_parse(rule.conditions), ctx, payload):
                    continue  # conditions not met — not logged (would flood)
                results = _run_actions(rule, ctx, payload)
                status, _ = _aggregate_status(results)
                _update_rule_last_run(rule.name, status)
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"BP Automation rule failed: {rule.name} ({rule.rule_name})",
                )
                _log_run(rule, payload, "Failed", _short_error())
                _update_rule_last_run(rule.name, "Failed")
    finally:
        frappe.flags.bp_automation_depth = depth


def run_scheduled(rule_name: str, payload: dict):
    """Execute one scheduled rule by name — the agent's callback entry point.

    Unlike run_for_event (event-driven, fans across matching rules), this fires
    a single known rule whose timing the agent owns. Returns (status, message);
    never raises (the agent only needs the 2xx/non-2xx).

    schedule.relative is the one exception: its timer carries no specific task
    (the registration payload is just {rule, project}), so firing it means
    scanning for whichever tasks currently qualify — see
    _run_relative_schedule.
    """
    from batch_projects.entitlements import is_feature_enabled
    if not is_feature_enabled("automations"):
        return "Skipped", "automations not enabled for this tenant"
    if not frappe.db.exists("BP Automation Rule", rule_name):
        return "Skipped", f"rule {rule_name} not found"

    rule = frappe.get_doc("BP Automation Rule", rule_name)
    if not rule.is_active:
        return "Skipped", "rule inactive"

    if rule.trigger_event == "schedule.relative" and not (payload or {}).get("task"):
        return _run_relative_schedule(rule)

    payload = dict(payload or {})
    payload.setdefault("project", rule.project)

    ctx = _build_context(payload)
    depth = frappe.flags.get("bp_automation_depth", 0)
    frappe.flags.bp_automation_depth = depth + 1
    try:
        if not _match(_parse(rule.conditions), ctx, payload):
            _log_run(rule, payload, "Skipped", "conditions not met")
            _update_rule_last_run(rule_name, "Skipped")
            return "Skipped", "conditions not met"
        results = _run_actions(rule, ctx, payload)
        status, message = _aggregate_status(results)
        _update_rule_last_run(rule_name, status)
        return status, message
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"BP scheduled rule failed: {rule_name}")
        msg = _short_error()
        _log_run(rule, payload, "Failed", msg)
        _update_rule_last_run(rule_name, "Failed")
        return "Failed", msg
    finally:
        frappe.flags.bp_automation_depth = depth


def _run_relative_schedule(rule):
    """schedule.relative's own daily timer fired with no task attached — scan
    for tasks whose configured date field lands on today ± offset_days across
    the rule's scope (one project, or project_filter / every project for a
    workspace rule), firing the rule's actions once per matching task.
    De-duplicated per (rule, task) so a task fires this rule at most once per
    day, mirroring run_due_soon_automations()'s existing dedup pattern."""
    cfg = _parse(rule.trigger_config) or {}
    field = cfg.get("field")
    if not field:
        return "Skipped", "No date field configured"
    try:
        offset = int(cfg.get("offset_days") or 0)
    except (TypeError, ValueError):
        offset = 0
    direction = cfg.get("direction") or "before"

    today = frappe.utils.getdate()
    # direction="before": fire `offset` days before the date, i.e. the date
    # field's value is `offset` days in the future of today. "after": the
    # date field's value is `offset` days in the past.
    target = frappe.utils.add_days(today, offset if direction == "before" else -offset)

    projects = _projects_in_scope(rule)
    if not projects:
        return "Skipped", "No projects in scope"

    dedup_after = frappe.utils.add_days(today, -1)
    fired = 0
    any_failed = False
    for project in projects:
        try:
            completed = set(frappe.get_cached_doc("BP Project", project).get_completed_statuses())
        except Exception:
            completed = set()
        tasks = frappe.get_all(
            "BP Task", filters={"project": project, field: str(target)},
            fields=["name", "task_key", "status"],
        )
        for t in tasks:
            if t.status in completed:
                continue
            if frappe.db.exists("BP Automation Run", {
                "rule": rule.name, "task": t.name, "run_at": [">", dedup_after],
            }):
                continue
            payload = {
                "event": "schedule.relative", "project": project,
                "task": t.name, "task_key": t.task_key,
            }
            ctx = _build_context(payload)
            try:
                if not _match(_parse(rule.conditions), ctx, payload):
                    continue
                results = _run_actions(rule, ctx, payload)
                if _aggregate_status(results)[0] == "Failed":
                    any_failed = True
                fired += 1
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"BP schedule.relative failed: {rule.name}/{t.name}",
                )
                any_failed = True
    frappe.db.commit()
    if fired:
        status = "Failed" if any_failed else "Success"
        _update_rule_last_run(rule.name, status)
        return status, f"Fired for {fired} task(s)" + (", some failed" if any_failed else "")
    _update_rule_last_run(rule.name, "Skipped")
    return "Skipped", "No matching tasks"


def _projects_in_scope(rule) -> list:
    if rule.scope == "workspace":
        pf = _parse(rule.project_filter) or []
        if pf:
            return [p for p in pf if frappe.db.exists("BP Project", p)]
        return frappe.get_all("BP Project", pluck="name")
    return [rule.project] if rule.project else []


def _project_filter_matches(rule, project) -> bool:
    pf = _parse(rule.get("project_filter"))
    if not pf:
        return True  # empty filter = every project
    return project in pf


def _compiled_trigger_matches(rule, payload) -> bool:
    """Pre-filter for trigger types that don't correspond 1:1 to a bus event
    name. Reads payload["changes"] directly — does NOT touch _match /
    _match_clause / _resolve, so the finished matcher's contract with Go's
    evaluator_test.go stays exactly as documented. Only called when the
    rule's own trigger_event differs from the firing bus event (i.e. this
    rule was fetched via _COMPILED_TRIGGERS_FOR_BUS_EVENT, not a direct
    equality match)."""
    trig = rule.get("trigger_event")
    changes = payload.get("changes") or []

    if trig == "task.field_changed":
        cfg = _parse(rule.get("trigger_config")) or {}
        field = cfg.get("field")
        if not field:
            return False
        change = next((c for c in changes if c.get("field") == field), None)
        if not change:
            return False
        to_val = cfg.get("to")
        if to_val not in (None, "") and str(change.get("to")) != str(to_val):
            return False
        from_val = cfg.get("from")
        if from_val not in (None, "") and str(change.get("from")) != str(from_val):
            return False
        return True

    if trig == "task.moved_sprint":
        return any(c.get("field") == "sprint" for c in changes)

    return False


def _short_error():
    e = frappe.get_traceback().strip().splitlines()
    return (e[-1] if e else "error")[:200]


def _get_actions(rule) -> list:
    """The ordered action list for this rule — dict-like (frappe.get_all row)
    or Document, both support .get(). Falls back to the pre-v2 single
    action_type/action_config pair for any row the migration patch hasn't
    touched (or a caller still writing the legacy shape)."""
    actions = _parse(rule.get("actions"))
    if isinstance(actions, list) and actions:
        return actions
    action_type = rule.get("action_type")
    if action_type:
        return [{"type": action_type, "config": _parse(rule.get("action_config"))}]
    return []


def _run_actions(rule, ctx, payload) -> list:
    """Run every action in order. Per-action isolation: one failing action
    logs its own BP Automation Run row (with action_index) and the loop
    continues — it never aborts the rest of the rule, matching events.py's
    own isolation doctrine."""
    actions = _get_actions(rule)
    results = []
    for idx, action in enumerate(actions):
        try:
            status, message = _execute(action, ctx, payload)
        except frappe.TimestampMismatchError:
            # Deliberately NOT swallowed by the generic handler below.
            # TimestampMismatchError subclasses Exception, so catching it here
            # made api/automation.py::apply_action's conflict-retry loop
            # structurally unreachable — it retries on exactly this error, but
            # never saw one, because this per-action isolation converted it to
            # a ("Failed", …) tuple first. Net effect: every gateway-dispatched
            # rule that raced a concurrent write (the drag = move_task +
            # reorder_tasks case that retry was written for) failed permanently
            # instead of retrying. Re-running the whole action list on retry is
            # safe — every task-saving action is check-and-skip idempotent.
            # The Python-engine path is unaffected: run_for_event's own
            # per-rule `except Exception` still catches this and logs the same
            # Failed run row it always did.
            raise
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"BP Automation action failed: {rule.get('name')} #{idx}",
            )
            status, message = "Failed", _short_error()
        _log_run(rule, payload, status, message, action_index=idx, action_type=action.get("type"))
        results.append((status, message))
    return results


def _update_rule_last_run(rule_name, status):
    """Stamp BP Automation Rule.last_run_at/last_run_status — the same
    pattern report_workflow_run already keeps for BP Workflow, applied here
    so AutomationRules.vue's existing `r.last_run_status` failing-run badge
    (previously permanently dead — the field didn't exist) actually lights
    up. Best-effort: this must never break the automation it's reporting on.

    Also the single choke point for failure notification (every rule-
    execution path funnels through here) — edge-triggered on the PREVIOUS
    status so a rule stuck failing on every event notifies its owner once,
    not once per event."""
    try:
        prev = frappe.db.get_value("BP Automation Rule", rule_name, "last_run_status")
        frappe.db.set_value("BP Automation Rule", rule_name, {
            "last_run_at": frappe.utils.now_datetime(),
            "last_run_status": status,
        })
        if status == "Failed" and prev != "Failed":
            _notify_rule_failure(rule_name)
    except Exception:
        pass


def _notify_rule_failure(rule_name):
    """Tell the rule's owner it just started failing — the gap the audit
    found: nothing EVER notified anyone when a rule silently stopped
    running, so a broken automation was only ever discovered by someone
    manually opening Run History. Best-effort, never raises."""
    try:
        rule = frappe.db.get_value(
            "BP Automation Rule", rule_name, ["rule_name", "project", "owner"], as_dict=True)
        if not rule or not rule.owner:
            return
        from batch_projects.events import _create_notification
        _create_notification(
            # actor="Administrator" (never None — _create_notification's own
            # actor_name lookup assumes a real user) stands in for "the
            # system/automation engine", not a person who caused the failure.
            recipient=rule.owner, notification_type="Automation Failed",
            task=None, project=rule.project, actor="Administrator",
            message=f'Automation "{rule.rule_name or rule_name}" just failed. Check its run history.',
        )
    except Exception:
        pass


def _aggregate_status(results: list):
    """Collapse a multi-action run into one (status, message) pair for
    callers that only want a single verdict (the scheduler agent, apply_action's
    HTTP response) — the per-action detail already lives in the run log."""
    if not results:
        return "Skipped", "No actions configured"
    statuses = [s for s, _ in results]
    if "Failed" in statuses:
        failed_msg = next(m for s, m in results if s == "Failed")
        return "Failed", failed_msg
    if "Success" in statuses:
        return "Success", f"{statuses.count('Success')} action(s) applied"
    return "Skipped", results[-1][1]


def _log_run(rule, payload, status, message, action_index=None, action_type=None):
    """Record a single action execution for the run-history view. Best-effort —
    logging must never break the automation itself."""
    try:
        frappe.get_doc({
            "doctype": "BP Automation Run",
            "rule": rule.get("name"),
            "rule_name": rule.get("rule_name"),
            "project": payload.get("project"),
            "task": payload.get("task"),
            "task_key": payload.get("task_key"),
            "trigger_event": payload.get("event") or rule.get("trigger_event"),
            "action_type": action_type or "",
            "action_index": action_index if action_index is not None else 0,
            "status": status,
            "message": (message or "")[:500],
            "run_at": frappe.utils.now_datetime(),
        }).insert(ignore_permissions=True)
    except Exception:
        pass


def _build_context(payload: dict) -> dict:
    """Field-resolution context: the task doc (if any) + synthetic payload fields."""
    ctx = {
        "event": payload.get("event"),
        "to_status": payload.get("to_status"),
        "from_status": payload.get("from_status"),
        "changed_fields": {c.get("field") for c in (payload.get("changes") or [])},
        "_task": None,
        # erp.* events carry no task; _resolve falls back to this
        # raw payload so conditions can read amount/outstanding/currency/etc.
        "_payload": payload,
    }
    task_name = payload.get("task")
    if task_name and frappe.db.exists("BP Task", task_name):
        ctx["_task"] = frappe.get_doc("BP Task", task_name)
    return ctx


# ─── CONDITION MATCHING (finished — see module docstring; no new ops) ───────

def _match(conditions, ctx, payload) -> bool:
    if not conditions:
        return True  # no conditions → always fire

    if isinstance(conditions, list):
        return all(_match_clause(c, ctx) for c in conditions)

    if isinstance(conditions, dict):
        all_ok = all(_match_clause(c, ctx) for c in conditions.get("all", []))
        any_clauses = conditions.get("any", [])
        any_ok = any(_match_clause(c, ctx) for c in any_clauses) if any_clauses else True
        return all_ok and any_ok

    return True


def _match_clause(clause: dict, ctx: dict) -> bool:
    field = clause.get("field")
    op = clause.get("op", "eq")
    expected = clause.get("value")

    if op == "changed":
        return field in ctx["changed_fields"]

    actual = _resolve(field, ctx)

    if op == "is_set":
        return actual not in (None, "", [], 0)
    if op == "is_not_set":
        return actual in (None, "", [], 0)
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return actual in (expected or [])
    if op == "nin":
        return actual not in (expected or [])
    if op == "contains":
        if isinstance(actual, (list, tuple, set)):
            return expected in actual
        # NOT `actual or ""` — that collapses falsy-but-real values (0,
        # False, "") the same as a genuinely missing field, so e.g.
        # story_points==0 could never substring-match "0". Only None means
        # "nothing to search"; mirrors Go's pyStr() (evaluator.go).
        if expected is None:
            return False
        return str(expected) in (str(actual) if actual is not None else "")
    if op in ("gt", "gte", "lt", "lte"):
        try:
            a, e = float(actual), float(expected)
        except (TypeError, ValueError):
            return False
        return {"gt": a > e, "gte": a >= e, "lt": a < e, "lte": a <= e}[op]

    return False


def _resolve(field, ctx):
    """Resolve a clause field from synthetic ctx, the task doc, or (Phase
    21B, task-less events like erp.*) the raw event payload directly."""
    if field in ("event", "to_status", "from_status"):
        return ctx.get(field)

    # external.webhook's third-party body — a dotted `body.<key>` namespace
    # (WORKPLAN-PHASE25 B3) so an arbitrary third party's field names can't
    # collide with reserved words above. Checked before the task/payload
    # split below since it applies regardless (a webhook event never has a
    # task, but this stays a dedicated branch to mirror Go's resolve()
    # exactly rather than relying on that always being true).
    if field.startswith("body."):
        return ((ctx.get("_payload") or {}).get("body") or {}).get(field[len("body."):])

    task = ctx.get("_task")
    if not task:
        return (ctx.get("_payload") or {}).get(field)

    if field == "labels":
        return _parse(task.labels) or []
    if field == "assignees":
        return [r.user for r in (task.assignees or [])]
    if field and field.startswith("cf:"):  # custom field by id → cf:<id>
        return (_parse(task.custom_field_values) or {}).get(field[3:])

    return task.get(field)


# ─── ACTIONS ───────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def _render_tokens(text, ctx, payload):
    """Renders {{...}} tokens in action config text (WORKPLAN-PHASE25 C2) —
    built once, used by Add Comment/Notify/Send Email. Deliberately NOT
    Jinja (no loops/conditionals/arbitrary eval) — a simple lookup-and-
    substitute, same reasoning bp-gateway's own resolveTemplate() already
    uses for message_template fields: this text is user-authored automation
    config, not developer-authored code.

    `task.<field>` reads the triggering task — rendered as "" when the field
    is a REAL field left blank (the author explicitly referenced it, an
    empty value is a legitimate render), but left VERBATIM when the field
    doesn't exist on the doctype at all (task.meta.has_field — a plain
    `task.get()` returns None for both cases, which would otherwise silently
    swallow a typo'd token instead of surfacing it). Anything else is looked
    up in the raw event payload. A token that can't be resolved at all
    (task.* with no task in context, or a payload key that doesn't exist) is
    also left verbatim — so a rule saved before this existed, or one that
    happens to contain literal `{{` text unrelated to this feature, renders
    exactly as before. Fast no-op for the vast majority of existing saved
    text (no "{{" substring at all).
    """
    if not text or "{{" not in text:
        return text

    task = ctx.get("_task")

    def repl(m):
        token = m.group(1)
        if token.startswith("task."):
            if not task:
                return m.group(0)
            fieldname = token[len("task."):]
            if not task.meta.has_field(fieldname) and fieldname not in ("name", "owner", "creation", "modified"):
                return m.group(0)
            val = task.get(fieldname)
            return "" if val is None else str(val)
        val = (payload or {}).get(token)
        return m.group(0) if val is None else str(val)

    return _TOKEN_RE.sub(repl, text)


def _send_email(cfg, ctx, payload):
    """Send Email action (WORKPLAN-PHASE25 C2) — `to` is a flat list mixing
    real member emails (options_source: members) and free-typed addresses
    (allow_custom: True in the registry); Frappe usernames in this app ARE
    email addresses (confirmed via get_automation_options's own members
    list), so no user->email resolution step is needed."""
    recipients = [r for r in (cfg.get("to") or []) if r]
    if not recipients:
        return "Skipped", "No recipients configured"

    subject = _render_tokens(cfg.get("subject") or "", ctx, payload).strip() or "Automation notification"
    message = _render_tokens(cfg.get("message") or "", ctx, payload)
    if not message.strip():
        return "Skipped", "No message configured"

    try:
        frappe.sendmail(recipients=recipients, subject=subject, message=message)
    except Exception:
        return "Failed", _short_error()
    return "Success", f"Emailed {len(recipients)} recipient(s)"


def _execute(action: dict, ctx, payload):
    """Run one action. Returns (status, message) for the run log:
    'Success' (something changed), 'Skipped' (no-op / not applicable)."""
    action_type = action.get("type")
    cfg = action.get("config") or {}
    task = ctx.get("_task")
    actor = frappe.session.user

    if action_type == "Change Status":
        if not task:
            return "Skipped", "No task in context"
        if not cfg.get("status"):
            return "Skipped", "No target status configured"
        if task.status == cfg["status"]:
            return "Skipped", f"Already '{cfg['status']}'"
        task.status = cfg["status"]
        # Automations are admin-configured actions, not a user dragging a card —
        # they bypass the same transition-graph restriction a manual move enforces.
        task.flags.ignore_transition_check = True
        task.save(ignore_permissions=True)  # logs activity + re-emits
        return "Success", f"Status → {cfg['status']}"

    if action_type == "Assign Issue":
        if not task:
            return "Skipped", "No task in context"
        return _apply_assignees(task, cfg.get("assignees") or [], cfg.get("mode", "set"))

    if action_type == "Set Priority":
        if not task:
            return "Skipped", "No task in context"
        pri = cfg.get("priority")
        if not pri or task.priority == pri:
            return "Skipped", "Priority unchanged"
        task.priority = pri
        task.save(ignore_permissions=True)
        return "Success", f"Priority → {pri}"

    if action_type == "Set Due Date":
        return _set_due_date(task, cfg)

    if action_type == "Add Label":
        return _add_labels(task, cfg.get("labels") or [])

    if action_type == "Add Comment":
        return _add_comment(task, _render_tokens(cfg.get("comment") or "", ctx, payload), actor)

    if action_type == "Notify":
        cfg = {**cfg, "message": _render_tokens(cfg.get("message") or "", ctx, payload)}
        n = _notify(cfg, task, payload, actor)
        return ("Success", f"Notified {n} recipient(s)") if n else ("Skipped", "No recipients")

    if action_type == "Send Email":
        return _send_email(cfg, ctx, payload)

    if action_type == "Create Issue":
        key = _create_linked_issue(cfg, payload, task)
        return ("Success", f"Created task {key}") if key else ("Skipped", "Not created")

    if action_type == "Update ERPNext Document":
        return _update_erpnext_document(cfg, task)

    return "Skipped", f"Unknown action '{action_type}'"


def _apply_assignees(task, users, mode):
    existing = [r.user for r in (task.assignees or [])]
    target = list(dict.fromkeys((existing if mode == "add" else []) + list(users)))
    if set(target) == set(existing):
        return "Skipped", "Assignees unchanged"
    task.set("assignees", [])
    for u in target:
        if not u:
            continue
        full_name = frappe.db.get_value("User", u, "full_name") or u
        task.append("assignees", {"user": u, "full_name": full_name})
    task.save(ignore_permissions=True)
    return "Success", f"Assignees → {', '.join(target) or 'none'}"


def _set_due_date(task, cfg):
    if not task:
        return "Skipped", "No task in context"
    from datetime import timedelta
    mode = cfg.get("mode") or ("on_date" if cfg.get("date") else "in_days")
    if mode == "on_date":
        new_due = cfg.get("date")
    else:
        try:
            days = int(cfg.get("days") or 0)
        except (TypeError, ValueError):
            days = 0
        new_due = str((frappe.utils.getdate() + timedelta(days=days)))
    if not new_due:
        return "Skipped", "No due date configured"
    if str(task.due_date or "") == str(new_due):
        return "Skipped", "Due date unchanged"
    task.due_date = new_due
    task.save(ignore_permissions=True)
    return "Success", f"Due date → {new_due}"


def _add_labels(task, labels):
    if not task:
        return "Skipped", "No task in context"
    labels = [l for l in labels if l]
    if not labels:
        return "Skipped", "No labels configured"
    current = _parse(task.labels) or []
    if not isinstance(current, list):
        current = []
    merged = list(dict.fromkeys(current + labels))
    if set(merged) == set(current):
        return "Skipped", "Labels already present"
    task.labels = json.dumps(merged)
    task.save(ignore_permissions=True)
    return "Success", f"Added label(s): {', '.join(labels)}"


def _add_comment(task, comment, actor):
    if not task:
        return "Skipped", "No task in context"
    comment = (comment or "").strip()
    if not comment:
        return "Skipped", "No comment text configured"
    frappe.get_doc({
        "doctype": "BP Activity",
        "task": task.name,
        "action_type": "Comment",
        "comment_text": comment,
        "user": actor,
    }).insert(ignore_permissions=True)
    return "Success", "Comment added"


def _notify(cfg, task, payload, actor):
    from batch_projects.events import _create_notification, _get_watchers

    recipients = set(cfg.get("users") or [])
    to = cfg.get("to")
    if task:
        if to == "assignees":
            recipients |= {r.user for r in (task.assignees or [])}
        elif to == "watchers":
            recipients |= set(_get_watchers(task.name))
        elif to == "reporter" and task.reporter:
            user_id = frappe.db.get_value("Employee", task.reporter, "user_id")
            if user_id:
                recipients.add(user_id)

    message = cfg.get("message") or "An automation updated this task."
    sent = 0
    for r in recipients:
        if r:
            _create_notification(
                recipient=r, notification_type="Automation",
                task=payload.get("task"), project=payload.get("project"),
                actor=actor, message=message,
            )
            sent += 1
    return sent


def _create_linked_issue(cfg, payload, trigger_task):
    project = payload.get("project")
    # Default the new task's status to the project's first workflow state when
    # none is configured (inserting with status=None can fail validation).
    status = cfg.get("status")
    if not status and project:
        try:
            from batch_projects.api.board import _normalize_workflow_states
            states = _normalize_workflow_states(
                frappe.get_cached_doc("BP Project", project).get_workflow_states())
            status = states[0].get("name") if states else None
        except Exception:
            status = None

    doc = frappe.get_doc({
        "doctype": "BP Task",
        "project": project,
        "title": cfg.get("title"),
        "task_type": cfg.get("task_type") or "Task",
        "status": status,
        "priority": cfg.get("priority") or "Medium",
        "assignees": [{"user": u} for u in (cfg.get("assignees") or []) if u],
    })
    doc.insert(ignore_permissions=True)

    if cfg.get("link_to_trigger") and payload.get("task"):
        doc.append("links", {
            "link_type": "relates to",
            "linked_task": payload["task"],
            "linked_task_key": payload.get("task_key"),
        })
        doc.save(ignore_permissions=True)
    return doc.get("task_key") or doc.name


def _resolve_erpnext_target_name(cfg, task):
    name_from = cfg.get("name_from") or "fixed"
    if name_from == "fixed":
        return cfg.get("name")
    if not task:
        return None
    if name_from == "task_field":
        fieldname = cfg.get("field")
        return task.get(fieldname) if fieldname else None
    if name_from.startswith("cf:"):
        return (_parse(task.custom_field_values) or {}).get(name_from[3:])
    return None


def _update_erpnext_document(cfg, task):
    """'Update ERPNext Document' action body — gateway engine only (validated
    at rule-save time). Never db.set_value: goes through get_doc().save() so
    ERPNext's own hooks (GL entries, validation, etc.) fire normally."""
    doctype = cfg.get("doctype")
    if doctype not in _ERPNEXT_DOCTYPE_WHITELIST:
        return "Skipped", f"Doctype '{doctype}' not allowed"

    name = _resolve_erpnext_target_name(cfg, task)
    if not name:
        return "Skipped", "No target document resolved"
    if not frappe.db.exists(doctype, name):
        return "Skipped", f"{doctype} {name} not found"

    fields = cfg.get("fields") or {}
    if not fields:
        return "Skipped", "No fields configured"

    doc = frappe.get_doc(doctype, name)
    if doc.get("docstatus") == 1:
        # v1: submitted docs are read-only to this action. Amending or using
        # allow-on-submit fields is a deliberate follow-up, not a silent guess.
        return "Skipped", "target is submitted"

    changed = [f for f, v in fields.items() if doc.get(f) != v]
    if not changed:
        return "Skipped", "Fields already set"
    for f in changed:
        doc.set(f, fields[f])
    doc.save(ignore_permissions=True)
    return "Success", f"Updated {doctype} {name}: {', '.join(changed)}"


# ─── HELPERS ───────────────────────────────────────────────────────────────

def _parse(raw):
    if not raw:
        return [] if isinstance(raw, list) else {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
