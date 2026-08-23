"""Raw schedule data + final recurrence mutation adapter for bp-gateway.

This module contains no timer, recurrence, trigger, matcher, condition, or
workflow semantics. The proprietary gateway computes all of those. Python only
returns current business rows and commits an already-resolved task occurrence.
"""

import json
import re

import frappe

from batch_projects.api.automation_data import (
    _assert_gateway_service_caller,
    _duplicate_result,
    _new_receipt,
)

_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_PROJECTS = 500
_MAX_RESULT_ROWS = 5000


def _clean_projects(values):
    if not isinstance(values, list):
        frappe.throw("projects must be a list")
    out = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            frappe.throw("project names must be strings")
        value = value.strip()
        if value and value not in seen:
            out.append(value)
            seen.add(value)
    if len(out) > _MAX_PROJECTS:
        frappe.throw(f"Too many projects (maximum {_MAX_PROJECTS})")
    return out


def _task_snapshot(task):
    return {
        "status": task.status,
        "priority": task.priority,
        "task_type": task.task_type,
        "story_points": task.story_points,
        "due_date": str(task.due_date) if task.due_date else None,
        "planned_start": str(task.planned_start) if task.planned_start else None,
        "planned_end": str(task.planned_end) if task.planned_end else None,
        "billable": task.billable,
        "reporter": task.reporter,
        "blocked_reason": task.blocked_reason or None,
        "blocked_since": str(task.blocked_since) if task.blocked_since else None,
        "blocked_by": task.blocked_by or None,
        "labels": _safe_json(task.labels, []),
        "assignees": [row.user for row in (task.assignees or []) if row.user],
        "custom_field_values": _safe_json(task.custom_field_values, {}),
    }


def _safe_json(raw, default):
    if not raw:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        decoded = json.loads(raw)
        return decoded
    except (json.JSONDecodeError, TypeError):
        return default


@frappe.whitelist()
def get_project_facts(projects=None, **_):
    """Return ordered workflow-state data for raw project names."""
    _assert_gateway_service_caller()
    projects = _clean_projects(projects if isinstance(projects, list) else _safe_json(projects, []))
    out = []
    for project in projects:
        if not frappe.db.exists("BP Project", project):
            continue
        doc = frappe.get_cached_doc("BP Project", project)
        out.append({
            "project": project,
            "workflow_states": [
                {"name": state.get("name"), "category": state.get("category") or "unstarted"}
                for state in doc.get_workflow_states()
                if isinstance(state, dict) and state.get("name")
            ],
        })
    return out


@frappe.whitelist()
def list_projects(**_):
    """Return raw project identities. Scope/filter decisions happen in Go."""
    _assert_gateway_service_caller()
    return frappe.get_all("BP Project", pluck="name", order_by="name asc", limit_page_length=_MAX_RESULT_ROWS)


@frappe.whitelist()
def query_tasks_by_date(projects=None, field=None, date=None, **_):
    """Return task rows whose raw Date/Datetime field intersects one date.

    The requested date is already computed by the gateway. This endpoint does
    not know why that date was requested or which automation will consume it.
    """
    _assert_gateway_service_caller()
    projects = _clean_projects(projects if isinstance(projects, list) else _safe_json(projects, []))
    if not projects:
        return []
    if not isinstance(field, str) or not _FIELD_RE.match(field):
        frappe.throw("Invalid BP Task date field")
    meta = frappe.get_meta("BP Task")
    df = meta.get_field(field)
    if not df or df.fieldtype not in ("Date", "Datetime"):
        frappe.throw("Requested BP Task field is not Date/Datetime")
    try:
        target = frappe.utils.getdate(date)
    except Exception:
        frappe.throw("date must be YYYY-MM-DD")

    value_filter = str(target)
    if df.fieldtype == "Datetime":
        value_filter = ["between", [f"{target} 00:00:00", f"{target} 23:59:59"]]
    names = frappe.get_all(
        "BP Task",
        filters={"project": ["in", projects], field: value_filter, "is_deleted": 0},
        pluck="name",
        order_by="name asc",
        limit_page_length=_MAX_RESULT_ROWS,
    )
    out = []
    for name in names:
        task = frappe.get_doc("BP Task", name)
        out.append({
            "name": task.name,
            "task_key": task.task_key,
            "project": task.project,
            "snapshot": _task_snapshot(task),
        })
    return out


@frappe.whitelist()
def get_recurring_task(task=None, **_):
    """Return the current recurrence template row without interpreting it."""
    _assert_gateway_service_caller()
    if not task or not frappe.db.exists("BP Task", task):
        return None
    doc = frappe.get_doc("BP Task", task)
    # A trashed or no-longer-recurring task must not serve as a recurrence
    # template — the scheduler would otherwise admit new occurrences from it.
    if doc.is_deleted or not doc.is_recurring:
        return None
    return {
        "name": doc.name,
        "project": doc.project,
        "title": doc.title,
        "priority": doc.priority,
        "task_type": doc.task_type,
        "epic": doc.epic,
        "description": doc.description,
        "estimated_hours": doc.estimated_hours,
        "billable": doc.billable,
        "labels": _safe_json(doc.labels, []),
        "custom_field_values": _safe_json(doc.custom_field_values, {}),
        "assignees": [row.user for row in (doc.assignees or []) if row.user],
        "due_date": str(doc.due_date) if doc.due_date else None,
        "is_recurring": bool(doc.is_recurring),
        "recurrence_frequency": doc.recurrence_frequency,
        "recurrence_end_date": str(doc.recurrence_end_date) if doc.recurrence_end_date else None,
        "bridge_job_id": doc.bridge_job_id,
    }


def _parse_mutation(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _clean_strings(values, limit=100):
    if not isinstance(values, list):
        frappe.throw("Expected a list")
    out = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            frappe.throw("List values must be strings")
        value = value.strip()
        if value and value not in seen:
            out.append(value)
            seen.add(value)
    if len(out) > limit:
        frappe.throw(f"Too many values (maximum {limit})")
    return out


@frappe.whitelist()
def apply_task_occurrence(mutation=None, **_):
    """Commit one fully-resolved recurring task occurrence.

    No recurrence frequency/end-date/date-shift logic exists here. All values
    below are final values supplied by the gateway. The receipt and inserted
    BP Task share one transaction, so retry after a lost response is idempotent.
    """
    _assert_gateway_service_caller()
    mutation = _parse_mutation(mutation)
    allowed = {
        "idempotency_key", "project", "title", "priority", "task_type", "status",
        "epic", "description", "estimated_hours", "billable", "labels",
        "custom_field_values", "assignees", "due_date", "recurrence_source",
    }
    unknown = set(mutation) - allowed
    if unknown:
        frappe.throw("Recurring occurrence contains unsupported field(s): " + ", ".join(sorted(unknown)))
    key = mutation.get("idempotency_key")
    if not isinstance(key, str) or not key.strip() or len(key) > 128:
        frappe.throw("A bounded idempotency_key is required")
    for required in ("project", "title", "priority", "task_type", "status", "recurrence_source"):
        if not mutation.get(required):
            frappe.throw(f"Recurring occurrence requires final {required}")
    if not frappe.db.exists("BP Project", mutation["project"]):
        frappe.throw("Recurring occurrence project does not exist")
    if not frappe.db.exists("BP Task", mutation["recurrence_source"]):
        frappe.throw("Recurring occurrence source task does not exist")

    duplicate = _duplicate_result(key)
    if duplicate:
        return duplicate
    receipt_payload = {
        "idempotency_key": key,
        "operation": "task.recurring.create",
        "target_doctype": "BP Task",
        "target_name": "",
    }
    try:
        receipt = _new_receipt(receipt_payload)
    except frappe.DuplicateEntryError:
        duplicate = _duplicate_result(key)
        if duplicate:
            return duplicate
        raise

    assignees = _clean_strings(mutation.get("assignees") or [])
    labels = _clean_strings(mutation.get("labels") or [])
    custom = mutation.get("custom_field_values") or {}
    if not isinstance(custom, dict):
        frappe.throw("custom_field_values must be an object")
    due_date = mutation.get("due_date")
    if due_date:
        try:
            due_date = str(frappe.utils.getdate(due_date))
        except Exception:
            frappe.throw("due_date must be YYYY-MM-DD")

    doc = frappe.get_doc({
        "doctype": "BP Task",
        "project": mutation["project"],
        "title": mutation["title"],
        "priority": mutation["priority"],
        "task_type": mutation["task_type"],
        "status": mutation["status"],
        "epic": mutation.get("epic"),
        "description": mutation.get("description"),
        "estimated_hours": mutation.get("estimated_hours"),
        "billable": mutation.get("billable"),
        "labels": json.dumps(labels),
        "custom_field_values": json.dumps(custom, separators=(",", ":"), sort_keys=True, default=str),
        "recurrence_source": mutation["recurrence_source"],
        "due_date": due_date,
        "assignees": [
            {"user": user, "full_name": frappe.db.get_value("User", user, "full_name") or user}
            for user in assignees
        ],
    })

    # Lock and re-validate the recurrence source inside the same transaction
    # as the occurrence insert: live, still recurring, same project.
    source = frappe.db.sql(
        """SELECT name, is_deleted, is_recurring, project
           FROM `tabBP Task` WHERE name = %s FOR UPDATE""",
        mutation["recurrence_source"],
        as_dict=True,
    )
    if not source:
        frappe.throw("Recurrence source task no longer exists")
    source = source[0]
    if source.is_deleted:
        frappe.throw("Recurrence source task has been trashed")
    if not source.is_recurring:
        frappe.throw("Recurrence source task is no longer recurring")
    if source.project != mutation["project"]:
        frappe.throw("Recurrence source project mismatch")

    doc.insert(ignore_permissions=True)

    result = {"doctype": "BP Task", "name": doc.name, "task_key": doc.task_key}
    receipt.target_name = doc.name
    receipt.result_json = json.dumps(result, separators=(",", ":"), sort_keys=True, default=str)
    receipt.applied_at = frappe.utils.now_datetime()
    receipt.save(ignore_permissions=True)
    return {"status": "applied", "result": result}
