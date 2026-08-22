"""Durable coordination primitives for Gateway graph workflows."""

import hashlib
import json

import frappe


TERMINAL_EXECUTION_STATES = {"succeeded", "failed", "needs_review"}
TERMINAL_STEP_STATES = {"succeeded", "failed", "needs_review"}
EFFECT_KINDS = {"frappe_atomic", "external"}


def _key(*parts):
    return hashlib.sha256("\0".join(str(part or "") for part in parts).encode()).hexdigest()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _as_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}
    return {}


def sanitize_envelope(envelope):
    """Persist only the event fields the graph evaluator can use on recovery."""
    envelope = _as_dict(envelope)
    allowed = (
        "event", "event_id", "source", "project", "task", "task_key",
        "to_status", "from_status", "changes", "depth", "snapshot",
        "doctype", "docname", "erp_event", "payload", "body",
    )
    cleaned = {key: envelope.get(key) for key in allowed if key in envelope}
    encoded = _json(cleaned)
    if len(encoded.encode()) > 256 << 10:
        frappe.throw("Workflow recovery envelope exceeds 256 KiB")
    return cleaned


def admit(workflow_name, event_id, envelope, expected_revision=None, expected_hash=None):
    """Create or return the single execution for one workflow/event pair."""
    if not workflow_name or not event_id:
        frappe.throw("workflow and event_id are required")
    workflow = frappe.get_doc("BP Workflow", workflow_name)
    revision = int(workflow.automation_revision or 0)
    definition_hash = workflow.automation_definition_hash or ""
    if not revision or not definition_hash:
        frappe.throw("Workflow definition identity is not initialized")
    if ((expected_revision is not None and int(expected_revision) != revision)
            or (expected_hash and expected_hash != definition_hash)):
        return {"status": "needs_review", "reason": "definition_changed"}

    execution_key = _key("workflow-execution", workflow.name, event_id)
    frappe.db.savepoint("bp_workflow_admit")
    try:
        execution = frappe.get_doc({
            "doctype": "BP Workflow Execution",
            "execution_key": execution_key,
            "workflow": workflow.name,
            "event_id": event_id,
            "recovery_envelope": _json(sanitize_envelope(envelope)),
            "workflow_revision": revision,
            "definition_hash": definition_hash,
            "status": "pending",
        }).insert(ignore_permissions=True)
        return _execution_payload(execution, created=True)
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback(save_point="bp_workflow_admit")
        rows = frappe.db.sql(
            """SELECT name, event_id, workflow, status, workflow_revision, definition_hash
               FROM `tabBP Workflow Execution` WHERE execution_key = %(key)s FOR UPDATE""",
            {"key": execution_key},
            as_dict=True,
        )
        if not rows:
            frappe.throw("Concurrent workflow execution admission did not resolve")
        execution = rows[0]
        if (int(execution.workflow_revision or 0) != revision
                or execution.definition_hash != definition_hash):
            # Never mutate an active holder from a duplicate delivery.  A
            # future recovery pass will terminally mark an expired execution;
            # this caller simply must not start a graph with a new definition.
            return {"execution_id": execution.name, "event_id": execution.event_id,
                    "workflow": execution.workflow, "status": "needs_review",
                    "reason": "definition_changed", "created": False}
        return _execution_row_payload(execution, created=False)


def claim_lease(execution_id, owner, lease_seconds):
    """Atomically claim a pending/expired execution, using MariaDB time."""
    seconds = max(10, min(int(lease_seconds or 60), 300))
    frappe.db.sql("""
        UPDATE `tabBP Workflow Execution`
        SET lease_owner = %(owner)s,
            lease_generation = COALESCE(lease_generation, 0) + 1,
            lease_expires_at = DATE_ADD(UTC_TIMESTAMP(6), INTERVAL %(seconds)s SECOND),
            status = 'running',
            started_at = COALESCE(started_at, UTC_TIMESTAMP(6))
        WHERE name = %(execution)s
          AND (status = 'pending'
               OR (status = 'running' AND (lease_expires_at IS NULL OR lease_expires_at < UTC_TIMESTAMP(6))))
    """, {"execution": execution_id, "owner": owner, "seconds": seconds})
    if _row_count():
        return _lease_payload(execution_id, owner)
    return _claim_failure(execution_id)


def renew_lease(execution_id, owner, generation, lease_seconds):
    """Renew only an unexpired lease held by this exact graph-walk attempt."""
    seconds = max(10, min(int(lease_seconds or 60), 300))
    frappe.db.sql("""
        UPDATE `tabBP Workflow Execution`
        SET lease_expires_at = DATE_ADD(UTC_TIMESTAMP(6), INTERVAL %(seconds)s SECOND)
        WHERE name = %(execution)s AND status = 'running'
          AND lease_owner = %(owner)s AND lease_generation = %(generation)s
          AND lease_expires_at >= UTC_TIMESTAMP(6)
    """, {"execution": execution_id, "owner": owner, "generation": int(generation), "seconds": seconds})
    if _row_count():
        payload = _lease_payload(execution_id, owner)
        payload["renewed"] = payload.pop("claimed", False)
        return payload
    return {"renewed": False, "reason": "lease_lost"}


def recoverable_executions(limit=100):
    """Return pending work and expired runs; Gateway claims each separately."""
    limit = max(1, min(int(limit or 100), 250))
    rows = frappe.db.sql("""
        SELECT name, workflow, event_id, recovery_envelope, workflow_revision, definition_hash,
               status, lease_expires_at
        FROM `tabBP Workflow Execution`
        WHERE status = 'pending'
           OR (status = 'running' AND (lease_expires_at IS NULL OR lease_expires_at < UTC_TIMESTAMP(6)))
        ORDER BY creation ASC
        LIMIT %(limit)s
    """, {"limit": limit}, as_dict=True)
    result = []
    for row in rows:
        workflow = frappe.db.get_value(
            "BP Workflow", row.workflow,
            ["automation_revision", "automation_definition_hash"], as_dict=True,
        )
        if not workflow or int(workflow.automation_revision or 0) != int(row.workflow_revision or 0) \
                or workflow.automation_definition_hash != row.definition_hash:
            frappe.db.set_value("BP Workflow Execution", row.name, {
                "status": "needs_review", "terminal_reason": "definition_changed",
            }, update_modified=False)
            continue
        result.append({
            "execution_id": row.name,
            "workflow": row.workflow,
            "event_id": row.event_id,
            "envelope": _as_dict(row.recovery_envelope),
            "workflow_revision": row.workflow_revision,
            "definition_hash": row.definition_hash,
            "status": row.status,
        })
    return result


def get_or_create_step(execution_id, node_id, effect_kind, owner, generation):
    if effect_kind not in EFFECT_KINDS:
        frappe.throw("Unknown workflow effect kind")
    _require_live_lease(execution_id, owner, generation, for_update=True)
    step_key = _key("workflow-step", execution_id, node_id)
    name = frappe.db.get_value("BP Workflow Step", {"step_key": step_key}, "name")
    if name:
        step = frappe.get_doc("BP Workflow Step", name)
        if step.effect_kind != effect_kind:
            frappe.throw("Workflow step effect kind changed")
        return _step_payload(step, created=False)
    try:
        frappe.db.savepoint("bp_workflow_step")
        step = frappe.get_doc({
            "doctype": "BP Workflow Step", "step_key": step_key,
            "execution": execution_id, "node_id": node_id,
            "effect_kind": effect_kind, "status": "claimed",
        }).insert(ignore_permissions=True)
        return _step_payload(step, created=True)
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback(save_point="bp_workflow_step")
        rows = frappe.db.sql(
            """SELECT name, status, effect_kind, result_json, error_code, error_message
               FROM `tabBP Workflow Step` WHERE step_key = %(key)s FOR UPDATE""",
            {"key": step_key},
            as_dict=True,
        )
        if not rows:
            frappe.throw("Concurrent workflow step creation did not resolve")
        return _step_row_payload(rows[0], created=False)


def get_or_create_node_step(idempotency_key, workflow, node_id):
    """Idempotency ledger entry for one run_workflow_node call, keyed by the
    GATEWAY's own idempotency_key (already a stable hash of that gateway's
    execution/node/run-attempt identity — see bp-gateway's
    runtimeNodeIdempotencyKey) rather than a BP Workflow Execution row.

    run_workflow_node has no BP Workflow Execution/lease of its own: Runtime
    V2 owns execution/retry/lease state entirely on the gateway side (its own
    SQLite-backed store), so unlike get_or_create_step there is no
    _require_live_lease precondition here — that would require a Frappe-side
    execution admission Runtime V2 does not (and should not) perform. This
    reuses BP Workflow Step's schema and the same insert-or-fetch-existing
    concurrency pattern as get_or_create_step, just without the lease
    dependency, so a real duplicate-key race still resolves to exactly one
    winner (the unique step_key constraint) instead of two.
    """
    if not idempotency_key:
        frappe.throw("idempotency_key is required")
    step_key = _key("workflow-node-step", idempotency_key)
    name = frappe.db.get_value("BP Workflow Step", {"step_key": step_key}, "name")
    if name:
        step = frappe.get_doc("BP Workflow Step", name)
        return _step_payload(step, created=False)
    try:
        frappe.db.savepoint("bp_workflow_node_step")
        step = frappe.get_doc({
            "doctype": "BP Workflow Step", "step_key": step_key,
            "workflow": workflow or None, "node_id": node_id or "",
            "effect_kind": "gateway_node", "status": "claimed",
        }).insert(ignore_permissions=True)
        return _step_payload(step, created=True)
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback(save_point="bp_workflow_node_step")
        rows = frappe.db.sql(
            """SELECT name, status, effect_kind, result_json, error_code, error_message
               FROM `tabBP Workflow Step` WHERE step_key = %(key)s FOR UPDATE""",
            {"key": step_key},
            as_dict=True,
        )
        if not rows:
            frappe.throw("Concurrent workflow node step creation did not resolve")
        return _step_row_payload(rows[0], created=False)


def finish_node_step(step_id, status, result=None, error_code=None, error_message=None):
    """Terminal transition for get_or_create_node_step's row. No lease/owner
    fencing to check — see get_or_create_node_step's docstring for why."""
    if status not in TERMINAL_STEP_STATES:
        frappe.throw("Illegal terminal workflow step status")
    frappe.db.sql("""
        UPDATE `tabBP Workflow Step`
        SET status = %(status)s, result_json = %(result)s,
            error_code = %(error_code)s, error_message = %(error_message)s
        WHERE name = %(step)s AND status = 'claimed'
    """, {
        "step": step_id,
        "status": status, "result": _json(result) if result is not None else None,
        "error_code": (error_code or "")[:140] or None,
        "error_message": (error_message or "")[:500] or None,
    })
    if not _row_count():
        frappe.throw("Workflow node step transition rejected")
    return _step_payload(frappe.get_doc("BP Workflow Step", step_id), created=False)


def begin_external_step(execution_id, node_id, owner, generation):
    """Durably mark dispatching before Gateway may send an external request."""
    step = get_or_create_step(execution_id, node_id, "external", owner, generation)
    if step["status"] in TERMINAL_STEP_STATES:
        return step

    # Global workflow row-lock order is Execution -> Step. The execution lease
    # is the authority for this graph-walk attempt, so lock and validate it
    # first; then mutate only the step row. A joined UPDATE lets MariaDB choose
    # Step -> Execution and can deadlock against get_or_create_step().
    _require_live_lease(execution_id, owner, generation, for_update=True)
    frappe.db.sql("""
        UPDATE `tabBP Workflow Step`
        SET status = 'dispatching', dispatch_started_at = UTC_TIMESTAMP(6)
        WHERE name = %(step)s AND execution = %(execution)s
          AND status = 'claimed'
    """, {"step": step["step_id"], "execution": execution_id})
    dispatch_confirmed = bool(_row_count())
    payload = _step_payload(frappe.get_doc("BP Workflow Step", step["step_id"]), created=step["created"])
    payload["dispatch_confirmed"] = dispatch_confirmed
    return payload


def finish_step(execution_id, step_id, owner, generation, status, result=None,
                error_code=None, error_message=None):
    if status not in TERMINAL_STEP_STATES:
        frappe.throw("Illegal terminal workflow step status")

    # Preserve generation/expiry fencing while keeping the deterministic
    # Execution -> Step order. Holding the execution row lock prevents a new
    # lease holder from being admitted while this step transition completes.
    _require_live_lease(execution_id, owner, generation, for_update=True)
    frappe.db.sql("""
        UPDATE `tabBP Workflow Step`
        SET status = %(status)s, result_json = %(result)s,
            error_code = %(error_code)s, error_message = %(error_message)s
        WHERE name = %(step)s AND execution = %(execution)s
          AND status IN ('claimed', 'dispatching')
    """, {
        "step": step_id, "execution": execution_id,
        "status": status, "result": _json(result) if result is not None else None,
        "error_code": (error_code or "")[:140] or None,
        "error_message": (error_message or "")[:500] or None,
    })
    if not _row_count():
        frappe.throw("Workflow step transition rejected")
    return _step_payload(frappe.get_doc("BP Workflow Step", step_id), created=False)


def finish_execution(execution_id, owner, generation, status, reason=None):
    if status not in TERMINAL_EXECUTION_STATES:
        frappe.throw("Illegal terminal workflow execution status")
    frappe.db.sql("""
        UPDATE `tabBP Workflow Execution`
        SET status = %(status)s, terminal_reason = %(reason)s,
            finished_at = UTC_TIMESTAMP(6), lease_expires_at = UTC_TIMESTAMP(6)
        WHERE name = %(execution)s AND status = 'running'
          AND lease_owner = %(owner)s AND lease_generation = %(generation)s
          AND lease_expires_at >= UTC_TIMESTAMP(6)
    """, {"execution": execution_id, "owner": owner, "generation": int(generation),
            "status": status, "reason": (reason or "")[:140] or None})
    if not _row_count():
        return {"finished": False, "reason": "lease_lost"}
    return {"finished": True, "status": status}


def definition_is_current(execution_id):
    execution = frappe.get_doc("BP Workflow Execution", execution_id)
    workflow = frappe.get_doc("BP Workflow", execution.workflow)
    return (int(execution.workflow_revision or 0) == int(workflow.automation_revision or 0)
            and execution.definition_hash == (workflow.automation_definition_hash or ""))


def _require_live_lease(execution_id, owner, generation, for_update=False):
    suffix = " FOR UPDATE" if for_update else ""
    rows = frappe.db.sql(f"""
        SELECT name FROM `tabBP Workflow Execution`
        WHERE name = %(execution)s AND status = 'running'
          AND lease_owner = %(owner)s AND lease_generation = %(generation)s
          AND lease_expires_at >= UTC_TIMESTAMP(6){suffix}
    """, {"execution": execution_id, "owner": owner, "generation": int(generation)}, as_dict=True)
    if not rows:
        frappe.throw("Workflow execution lease is no longer valid")


def _execution_payload(execution, created=False):
    return {
        "execution_id": execution.name, "event_id": execution.event_id,
        "workflow": execution.workflow, "status": execution.status,
        "workflow_revision": execution.workflow_revision,
        "definition_hash": execution.definition_hash, "created": created,
    }


def _execution_row_payload(row, created=False):
    return {
        "execution_id": row.name, "event_id": row.event_id,
        "workflow": row.workflow, "status": row.status,
        "workflow_revision": row.workflow_revision,
        "definition_hash": row.definition_hash, "created": created,
    }


def _step_payload(step, created=False):
    return {
        "step_id": step.name, "status": step.status, "effect_kind": step.effect_kind,
        "result": _as_dict(step.result_json), "error_code": step.error_code,
        "error_message": step.error_message, "created": created,
    }


def _step_row_payload(row, created=False):
    return {
        "step_id": row.name, "status": row.status, "effect_kind": row.effect_kind,
        "result": _as_dict(row.result_json), "error_code": row.error_code,
        "error_message": row.error_message, "created": created,
    }


def _lease_payload(execution_id, owner):
    row = frappe.db.get_value(
        "BP Workflow Execution", execution_id,
        ["name", "lease_owner", "lease_generation", "lease_expires_at", "status"], as_dict=True,
    )
    if not row or row.lease_owner != owner:
        return {"claimed": False, "reason": "lease_lost"}
    return {"claimed": True, "execution_id": row.name, "lease_generation": row.lease_generation,
            "lease_expires_at": row.lease_expires_at, "status": row.status}


def _claim_failure(execution_id):
    row = frappe.db.get_value(
        "BP Workflow Execution", execution_id,
        ["status", "terminal_reason"], as_dict=True,
    )
    if not row:
        return {"claimed": False, "reason": "execution_not_found"}
    return {"claimed": False, "reason": row.terminal_reason or row.status or "lease_held"}


def _row_count():
    return int(frappe.db.sql("SELECT ROW_COUNT()")[0][0])
