"""Final recurrence state write for bp-gateway.

No recurrence decision lives here. The gateway supplies the exact final values;
this adapter writes them without invoking BPTask.on_update(), so Python cannot
cancel/re-register timers or otherwise reinterpret the gateway's decision.
"""

import json

import frappe

from batch_projects.api.automation_data import (
    _assert_gateway_service_caller,
    _duplicate_result,
    _new_receipt,
)


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


@frappe.whitelist()
def apply_recurrence_state(mutation=None, **_):
    _assert_gateway_service_caller()
    mutation = _as_dict(mutation)
    unknown = set(mutation) - {"idempotency_key", "task", "is_recurring", "bridge_job_id"}
    if unknown:
        frappe.throw("Recurrence state contains unsupported field(s): " + ", ".join(sorted(unknown)))
    key = mutation.get("idempotency_key")
    task = mutation.get("task")
    if not isinstance(key, str) or not key.strip() or len(key) > 128:
        frappe.throw("A bounded idempotency_key is required")
    if not isinstance(task, str) or not task or not frappe.db.exists("BP Task", task):
        frappe.throw("Recurrence state requires an existing task")
    if not isinstance(mutation.get("is_recurring"), bool):
        frappe.throw("is_recurring must be a final boolean")
    bridge_job_id = mutation.get("bridge_job_id")
    if bridge_job_id is not None and not isinstance(bridge_job_id, str):
        frappe.throw("bridge_job_id must be a final string or null")

    duplicate = _duplicate_result(key)
    if duplicate:
        return duplicate
    receipt_payload = {
        "idempotency_key": key,
        "operation": "task.recurrence_state",
        "target_doctype": "BP Task",
        "target_name": task,
    }
    try:
        receipt = _new_receipt(receipt_payload)
    except frappe.DuplicateEntryError:
        duplicate = _duplicate_result(key)
        if duplicate:
            return duplicate
        raise

    current = frappe.db.get_value("BP Task", task, ["is_recurring", "bridge_job_id"], as_dict=True)
    final_recurring = 1 if mutation["is_recurring"] else 0
    changed = []
    if int(current.is_recurring or 0) != final_recurring:
        changed.append("is_recurring")
    if (current.bridge_job_id or None) != (bridge_job_id or None):
        changed.append("bridge_job_id")

    if changed:
        frappe.db.set_value(
            "BP Task", task,
            {"is_recurring": final_recurring, "bridge_job_id": bridge_job_id},
            update_modified=False,
        )
        status = "applied"
    else:
        status = "unchanged"

    result = {
        "doctype": "BP Task",
        "name": task,
        "is_recurring": bool(final_recurring),
        "bridge_job_id": bridge_job_id,
        "changed": changed,
    }
    receipt.result_json = json.dumps(result, separators=(",", ":"), sort_keys=True, default=str)
    receipt.applied_at = frappe.utils.now_datetime()
    receipt.save(ignore_permissions=True)
    return {"status": status, "result": result}
