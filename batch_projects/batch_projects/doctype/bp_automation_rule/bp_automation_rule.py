"""BP Automation Rule configuration model.

This public module intentionally contains NO automation runtime. It validates
and stores a user's When/If/Then configuration and registers durable schedule
metadata with bp-gateway. Trigger matching, condition evaluation, action
semantics, retries, branching, schedule interpretation and execution all live
in the proprietary gateway runtime.
"""

import json

import frappe
from frappe.model.document import Document


# Shared configuration vocabulary used by the rule editor/node registry. These
# are data-schema constants, not runtime implementations.
_ERPNEXT_DOCTYPE_WHITELIST = ("Sales Invoice", "Sales Order", "Timesheet", "ToDo")

_KNOWN_ACTION_TYPES = {
    "Change Status",
    "Assign Issue",
    "Set Priority",
    "Set Due Date",
    "Add Label",
    "Add Comment",
    "Notify",
    "Create Issue",
    "Update ERPNext Document",
    "Send Email",
}


def _parse(value, default=None):
    """Decode Text/JSON configuration without interpreting its semantics."""
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if not isinstance(value, str):
        return default
    current = value
    for _ in range(4):
        if not isinstance(current, str):
            return current
        if not current:
            return default
        try:
            current = json.loads(current)
        except (json.JSONDecodeError, TypeError):
            return default
    return current


def _get_actions(rule):
    """Return ordered action configuration, including the one-release legacy row."""
    actions = _parse(rule.get("actions"), [])
    if isinstance(actions, list) and actions:
        return actions
    action_type = rule.get("action_type")
    if action_type:
        config = _parse(rule.get("action_config"), {})
        return [{"type": action_type, "config": config if isinstance(config, dict) else {}}]
    return []


# Temporary import-compatibility names for older public modules while their old
# callback endpoints are removed. They contain deliberately no matcher/action
# logic and must never become a fallback execution path.
def run_for_event(*_args, **_kwargs):
    return None


def run_scheduled(*_args, **_kwargs):
    return "Skipped", "Python automation runtime has been removed; bp-gateway owns execution"


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
            self.project = None

        project_filter = _parse(self.project_filter, [])
        if not isinstance(project_filter, list):
            frappe.throw("Project Filter must be a JSON list.")

        conditions = _parse(self.conditions, [])
        if not isinstance(conditions, (list, dict)):
            frappe.throw("Conditions must be a JSON list or {all, any} object.")

        actions = _parse(self.actions, [])
        if not isinstance(actions, list):
            frappe.throw("Actions must be an ordered list.")
        for action in actions:
            if not isinstance(action, dict):
                frappe.throw("Each action must be an object with 'type' and 'config'.")
            _validate_action(action)
        if not actions and self.action_type:
            _validate_action({"type": self.action_type, "config": _parse(self.action_config, {})})

        trigger_config = _parse(self.trigger_config, {})
        if trigger_config is None:
            trigger_config = {}
        if not isinstance(trigger_config, dict):
            frappe.throw("Trigger Config must be a JSON object.")
        if self.trigger_event == "task.field_changed" and not trigger_config.get("field"):
            frappe.throw("'When a field changes' rules need a Field configured.")
        if self.trigger_event == "schedule.relative":
            if not trigger_config.get("field"):
                frappe.throw("'Relative to a date' rules need a Field configured.")
            direction = trigger_config.get("direction") or "before"
            if direction not in ("before", "after"):
                frappe.throw("Relative schedule direction must be 'before' or 'after'.")
            try:
                offset = int(trigger_config.get("offset_days") or 0)
            except (TypeError, ValueError):
                frappe.throw("Relative schedule offset_days must be an integer.")
            if abs(offset) > 3650:
                frappe.throw("Relative schedule offset cannot exceed 3650 days.")
            if not self.interval_seconds:
                self.interval_seconds = 86400

        if self._is_scheduled() and int(self.interval_seconds or 0) <= 0:
            frappe.throw("Recurring rules require a positive Interval (seconds).")

    def _validate_json(self, fieldname):
        raw = self.get(fieldname)
        if not raw:
            return
        if isinstance(raw, (dict, list)):
            return
        if not isinstance(raw, str):
            frappe.throw(f"{fieldname} must be valid JSON.")
        try:
            json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            frappe.throw(f"{fieldname} must be valid JSON.")

    def _is_scheduled(self):
        return (self.trigger_event or "").startswith("schedule.")

    def on_update(self):
        if not self._is_scheduled() and not self.bridge_job_id:
            return
        self._sync_schedule()

    def on_trash(self):
        if self.bridge_job_id:
            from batch_projects import bridge
            bridge.cancel_scheduled_job(self.bridge_job_id)

    def _sync_schedule(self):
        """Register/cancel timer DATA; scheduler semantics stay in bp-gateway."""
        from batch_projects import bridge
        from frappe.utils import get_datetime

        if self.bridge_job_id:
            bridge.cancel_scheduled_job(self.bridge_job_id)
            self.db_set("bridge_job_id", None, update_modified=False)

        if not (self._is_scheduled() and self.is_active):
            return

        interval = int(self.interval_seconds or 0)
        run_at = None
        delay = None
        if self.first_run:
            run_at = int(get_datetime(self.first_run).timestamp())
        else:
            delay = interval or 60

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
                "Could not register this scheduled automation with the gateway. "
                "It will not fire until re-saved.",
                indicator="orange",
                alert=True,
            )


def _validate_action(action):
    a_type = action.get("type")
    cfg = action.get("config") or {}
    if a_type not in _KNOWN_ACTION_TYPES:
        frappe.throw(f"Unknown action type '{a_type}'.")
    if not isinstance(cfg, dict):
        frappe.throw(f"Config for '{a_type}' must be an object.")

    if a_type == "Change Status":
        if not cfg.get("status"):
            frappe.throw("Change Status actions require a 'status' in Config.")
    elif a_type == "Assign Issue":
        if not isinstance(cfg.get("assignees") or [], list):
            frappe.throw("Assign Issue assignees must be a list.")
        if (cfg.get("mode") or "set") not in ("set", "add"):
            frappe.throw("Assign Issue mode must be 'set' or 'add'.")
    elif a_type == "Set Priority":
        if not cfg.get("priority"):
            frappe.throw("Set Priority actions require a priority.")
    elif a_type == "Set Due Date":
        mode = cfg.get("mode") or ("on_date" if cfg.get("date") else "in_days")
        if mode not in ("on_date", "in_days"):
            frappe.throw("Set Due Date mode must be 'on_date' or 'in_days'.")
        if mode == "on_date" and not cfg.get("date"):
            frappe.throw("Set Due Date requires a date for on_date mode.")
        if mode == "in_days":
            try:
                days = int(cfg.get("days") or 0)
            except (TypeError, ValueError):
                frappe.throw("Set Due Date days must be an integer.")
            if abs(days) > 3650:
                frappe.throw("Set Due Date offset cannot exceed 3650 days.")
    elif a_type == "Add Label":
        if not isinstance(cfg.get("labels") or [], list) or not cfg.get("labels"):
            frappe.throw("Add Label actions require at least one label.")
    elif a_type == "Add Comment":
        if not str(cfg.get("comment") or "").strip():
            frappe.throw("Add Comment actions require comment text.")
    elif a_type == "Notify":
        if not str(cfg.get("message") or "").strip():
            frappe.throw("Notify actions require a message.")
        if not isinstance(cfg.get("users") or [], list):
            frappe.throw("Notify users must be a list.")
    elif a_type == "Create Issue":
        if not str(cfg.get("title") or "").strip():
            frappe.throw("Create Issue actions require a title.")
    elif a_type == "Update ERPNext Document":
        if cfg.get("doctype") not in _ERPNEXT_DOCTYPE_WHITELIST:
            frappe.throw(
                "Update ERPNext Document only supports: "
                + ", ".join(_ERPNEXT_DOCTYPE_WHITELIST)
                + "."
            )
        fields = cfg.get("fields")
        if not isinstance(fields, dict) or not fields:
            frappe.throw("Update ERPNext Document actions require at least one field to set.")
        name_from = cfg.get("name_from") or "fixed"
        if name_from == "fixed" and not cfg.get("name"):
            frappe.throw("Update ERPNext Document needs a document name (or a different Name source).")
        if name_from == "task_field" and not cfg.get("field"):
            frappe.throw("Update ERPNext Document using 'Task field' needs a Field configured.")
        if name_from != "fixed" and name_from != "task_field" and not str(name_from).startswith("cf:"):
            frappe.throw("Unsupported ERPNext document Name source.")
    elif a_type == "Send Email":
        if not isinstance(cfg.get("to") or [], list) or not cfg.get("to"):
            frappe.throw("Send Email actions require at least one recipient.")
        if not str(cfg.get("message") or "").strip():
            frappe.throw("Send Email actions require a message body.")
