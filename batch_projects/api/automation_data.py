"""Final business-data adapter for bp-gateway automation.

This module is intentionally NOT a workflow engine.  It accepts only already-
resolved, already-validated business intent from the proprietary gateway and
commits that intent transactionally through Frappe/ERPNext domain documents.

It must never receive or interpret workflow ids, node types, rule configs,
conditions, branches, retries, waits, schedules, provider responses, or other
runtime state.  Those belong exclusively to bp-gateway.
"""

import json

import frappe


_ERPNEXT_UPDATE_DOCTYPES = {"Sales Invoice", "Sales Order", "Timesheet", "ToDo"}
_TASK_UPDATE_FIELDS = {"status", "priority", "due_date"}
_ALLOWED_KEYS = {
    "operation", "idempotency_key", "task", "project", "fields", "users", "labels",
    "comment", "target_doctype", "target_name", "recipients", "subject", "message",
    "title", "task_type", "status", "priority", "assignees", "link_to_task",
    "link_to_task_key",
}
_FORBIDDEN_RUNTIME_KEYS = {
    "workflow", "workflow_id", "workflow_revision", "node", "node_id", "node_type",
    "rule", "rule_name", "config", "conditions", "branch", "retry", "attempt",
    "wait", "execution_state", "ready_queue", "outputs", "provider_response",
}


def _assert_gateway_service_caller():
    """Require API-token service authentication, not an interactive session.

    This endpoint exposes only ordinary final data mutations, not premium
    orchestration logic, so the monetization boundary does not depend on Python
    authorization.  Still, browser sessions must not be able to drive this
    privileged adapter accidentally.
    """
    auth = frappe.get_request_header("Authorization") or ""
    if not auth.lower().startswith("token "):
        frappe.throw("Gateway service token authentication required", frappe.PermissionError)
    user = frappe.session.user
    if user == "Administrator":
        return
    if "System Manager" not in frappe.get_roles(user):
        frappe.throw("Gateway service account requires System Manager", frappe.PermissionError)


def _as_dict(value):
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
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    if len(out) > limit:
        frappe.throw(f"Too many values (maximum {limit})")
    return out


def _validate_envelope(mutation):
    unknown = set(mutation) - _ALLOWED_KEYS
    if unknown:
        frappe.throw("Final mutation contains unsupported field(s): " + ", ".join(sorted(unknown)))
    leaked = set(mutation) & _FORBIDDEN_RUNTIME_KEYS
    if leaked:
        frappe.throw("Workflow runtime data is forbidden in final mutations: " + ", ".join(sorted(leaked)))
    key = mutation.get("idempotency_key")
    if not isinstance(key, str) or not key.strip() or len(key) > 160:
        frappe.throw("A bounded idempotency_key is required")
    operation = mutation.get("operation")
    if operation not in {
        "task.update", "task.set_assignees", "task.set_labels", "task.create",
        "comment.add", "erp.update", "notification.send", "email.send",
    }:
        frappe.throw(f"Unsupported final mutation operation {operation!r}")


def _duplicate_result(key):
    name = frappe.db.exists("BP Gateway Mutation Receipt", {"idempotency_key": key})
    if not name:
        return None
    raw = frappe.db.get_value("BP Gateway Mutation Receipt", name, "result_json") or "{}"
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        frappe.throw("Existing gateway mutation receipt is corrupt")
    return {"status": "duplicate", "result": result}


def _new_receipt(mutation):
    return frappe.get_doc({
        "doctype": "BP Gateway Mutation Receipt",
        "idempotency_key": mutation["idempotency_key"],
        "operation": mutation["operation"],
        "target_doctype": mutation.get("target_doctype") or ("BP Task" if mutation.get("task") else ""),
        "target_name": mutation.get("target_name") or mutation.get("task") or "",
    }).insert(ignore_permissions=True)


def _task(name):
    if not name or not frappe.db.exists("BP Task", name):
        frappe.throw(f"BP Task {name!r} not found")
    return frappe.get_doc("BP Task", name)


def _apply_task_update(mutation):
    task = _task(mutation.get("task"))
    fields = mutation.get("fields")
    if not isinstance(fields, dict) or not fields:
        frappe.throw("task.update requires final fields")
    unknown = set(fields) - _TASK_UPDATE_FIELDS
    if unknown:
        frappe.throw("task.update cannot write: " + ", ".join(sorted(unknown)))
    changed = [field for field, value in fields.items() if task.get(field) != value]
    if not changed:
        return "unchanged", {"doctype": "BP Task", "name": task.name, "changed": []}
    for field in changed:
        task.set(field, fields[field])
    if "status" in changed:
        # Gateway already made the automation decision. This bypasses the
        # manual board transition graph while retaining BP Task validation,
        # hooks, activity and emitted business events.
        task.flags.ignore_transition_check = True
    task.save(ignore_permissions=True)
    return "applied", {"doctype": "BP Task", "name": task.name, "changed": changed}


def _apply_task_assignees(mutation):
    task = _task(mutation.get("task"))
    users = _clean_strings(mutation.get("users") or [])
    existing = sorted({row.user for row in (task.assignees or []) if row.user})
    if existing == sorted(users):
        return "unchanged", {"doctype": "BP Task", "name": task.name, "assignees": existing}
    task.set("assignees", [])
    for user in users:
        full_name = frappe.db.get_value("User", user, "full_name") or user
        task.append("assignees", {"user": user, "full_name": full_name})
    task.save(ignore_permissions=True)
    return "applied", {"doctype": "BP Task", "name": task.name, "assignees": users}


def _parse_labels(raw):
    if isinstance(raw, list):
        return _clean_strings(raw)
    if isinstance(raw, str) and raw:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            decoded = []
        return _clean_strings(decoded if isinstance(decoded, list) else [])
    return []


def _apply_task_labels(mutation):
    task = _task(mutation.get("task"))
    labels = _clean_strings(mutation.get("labels") or [])
    existing = _parse_labels(task.labels)
    if sorted(existing) == sorted(labels):
        return "unchanged", {"doctype": "BP Task", "name": task.name, "labels": existing}
    task.labels = json.dumps(labels)
    task.save(ignore_permissions=True)
    return "applied", {"doctype": "BP Task", "name": task.name, "labels": labels}


def _apply_comment(mutation):
    task = _task(mutation.get("task"))
    comment = mutation.get("comment")
    if not isinstance(comment, str) or not comment.strip() or len(comment) > 100000:
        frappe.throw("comment.add requires bounded final comment text")
    doc = frappe.get_doc({
        "doctype": "BP Activity",
        "task": task.name,
        "action_type": "Comment",
        "comment_text": comment.strip(),
        "user": frappe.session.user,
    }).insert(ignore_permissions=True)
    return "applied", {"doctype": "BP Activity", "name": doc.name, "task": task.name}


def _apply_task_create(mutation):
    project = mutation.get("project")
    title = mutation.get("title")
    status = mutation.get("status")
    if not project or not frappe.db.exists("BP Project", project):
        frappe.throw("task.create requires an existing final project")
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        frappe.throw("task.create requires a bounded final title")
    if not isinstance(status, str) or not status:
        # No Python-side project-default lookup. The gateway must resolve it.
        frappe.throw("task.create requires final status")
    assignees = _clean_strings(mutation.get("assignees") or [])
    doc = frappe.get_doc({
        "doctype": "BP Task",
        "project": project,
        "title": title.strip(),
        "task_type": mutation.get("task_type") or "Task",
        "status": status,
        "priority": mutation.get("priority") or "Medium",
        "assignees": [{"user": user, "full_name": frappe.db.get_value("User", user, "full_name") or user} for user in assignees],
    }).insert(ignore_permissions=True)
    link_to_task = mutation.get("link_to_task")
    if link_to_task:
        if not frappe.db.exists("BP Task", link_to_task):
            frappe.throw("task.create link_to_task does not exist")
        doc.append("links", {
            "link_type": "relates to",
            "linked_task": link_to_task,
            "linked_task_key": mutation.get("link_to_task_key") or frappe.db.get_value("BP Task", link_to_task, "task_key"),
        })
        doc.save(ignore_permissions=True)
    return "applied", {"doctype": "BP Task", "name": doc.name, "task_key": doc.get("task_key")}


def _apply_erp_update(mutation):
    doctype = mutation.get("target_doctype")
    name = mutation.get("target_name")
    fields = mutation.get("fields")
    if doctype not in _ERPNEXT_UPDATE_DOCTYPES:
        frappe.throw(f"erp.update doctype {doctype!r} is not allowed")
    if not name or not frappe.db.exists(doctype, name):
        frappe.throw(f"{doctype} {name!r} not found")
    if not isinstance(fields, dict) or not fields or len(fields) > 100:
        frappe.throw("erp.update requires final fields")
    protected = {"name", "doctype", "owner", "creation", "modified", "modified_by", "docstatus"}
    doc = frappe.get_doc(doctype, name)
    if int(doc.docstatus or 0) != 0:
        frappe.throw("erp.update target must be a draft document")
    changed = []
    for field, value in fields.items():
        if field in protected:
            frappe.throw(f"erp.update cannot write protected field {field!r}")
        df = doc.meta.get_field(field)
        if not df:
            frappe.throw(f"erp.update field {field!r} does not exist on {doctype}")
        if df.fieldtype in ("Table", "Table MultiSelect"):
            frappe.throw(f"erp.update cannot write child-table field {field!r}")
        if doc.get(field) != value:
            doc.set(field, value)
            changed.append(field)
    if not changed:
        return "unchanged", {"doctype": doctype, "name": name, "changed": []}
    doc.save(ignore_permissions=True)
    return "applied", {"doctype": doctype, "name": name, "changed": changed}


def _apply_notification(mutation):
    recipients = _clean_strings(mutation.get("recipients") or [])
    message = mutation.get("message")
    if not recipients or not isinstance(message, str) or not message.strip():
        frappe.throw("notification.send requires final recipients and message")
    from batch_projects.events import _create_notification
    names = []
    for recipient in recipients:
        before = frappe.db.get_value("BP Notification", {"recipient": recipient}, "name", order_by="creation desc")
        _create_notification(
            recipient=recipient,
            notification_type="Automation",
            task=mutation.get("task"),
            project=mutation.get("project"),
            actor=frappe.session.user,
            message=message,
        )
        after = frappe.db.get_value("BP Notification", {"recipient": recipient}, "name", order_by="creation desc")
        if after and after != before:
            names.append(after)
    return "applied", {"notifications": names, "recipients": recipients}


def _apply_email(mutation):
    recipients = _clean_strings(mutation.get("recipients") or [])
    subject = mutation.get("subject") or "Automation notification"
    message = mutation.get("message")
    if not recipients or not isinstance(message, str) or not message.strip():
        frappe.throw("email.send requires final recipients and message")
    if not isinstance(subject, str) or len(subject) > 500 or len(message) > 1000000:
        frappe.throw("email.send payload exceeds limits")
    frappe.sendmail(recipients=recipients, subject=subject, message=message)
    return "applied", {"recipients": recipients, "subject": subject}


def _dispatch_final_mutation(mutation):
    operation = mutation["operation"]
    if operation == "task.update":
        return _apply_task_update(mutation)
    if operation == "task.set_assignees":
        return _apply_task_assignees(mutation)
    if operation == "task.set_labels":
        return _apply_task_labels(mutation)
    if operation == "task.create":
        return _apply_task_create(mutation)
    if operation == "comment.add":
        return _apply_comment(mutation)
    if operation == "erp.update":
        return _apply_erp_update(mutation)
    if operation == "notification.send":
        return _apply_notification(mutation)
    if operation == "email.send":
        return _apply_email(mutation)
    frappe.throw(f"Unsupported final mutation operation {operation!r}")


@frappe.whitelist()
def apply_mutation(mutation=None, **_):
    """Commit one already-resolved gateway business mutation atomically.

    The idempotency receipt and the business mutation live in the same Frappe
    transaction. If the response is lost after commit, a retry returns the
    committed result instead of duplicating the side effect. If the mutation
    raises, the receipt rolls back with it.
    """
    _assert_gateway_service_caller()
    mutation = _as_dict(mutation)
    _validate_envelope(mutation)

    duplicate = _duplicate_result(mutation["idempotency_key"])
    if duplicate:
        return duplicate

    try:
        receipt = _new_receipt(mutation)
    except frappe.DuplicateEntryError:
        duplicate = _duplicate_result(mutation["idempotency_key"])
        if duplicate:
            return duplicate
        raise

    status, result = _dispatch_final_mutation(mutation)
    receipt.operation = mutation["operation"]
    receipt.target_doctype = result.get("doctype") or mutation.get("target_doctype") or receipt.target_doctype
    receipt.target_name = result.get("name") or mutation.get("target_name") or mutation.get("task") or receipt.target_name
    receipt.result_json = json.dumps(result, separators=(",", ":"), sort_keys=True, default=str)
    receipt.applied_at = frappe.utils.now_datetime()
    receipt.save(ignore_permissions=True)
    return {"status": status, "result": result}
