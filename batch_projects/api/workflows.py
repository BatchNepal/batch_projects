"""
BP Workflow — frontend-facing CRUD for the automation canvas (WORKPLAN-PHASE24
01-DATA-MODEL.md). Gateway-facing endpoints (list_active_workflows,
log_workflow_run, run_workflow_node) are a separate, not-yet-built piece —
see 04-GO-EXECUTION-ENGINE.md; this file is save/load only, same tier gate
("automations", Team+) the flat-list rule engine already uses.
"""

import json

import frappe
from frappe import _

from batch_projects.entitlements import require_feature


def _require_workflow_admin(scope, project):
    """Same authorization board.py's BP Automation Rule already uses
    (`_require_automation_admin`) — reused, not reimplemented, so the two
    automation surfaces (flat-list rules and graph workflows) share one
    access model. Workflows are System-Manager-only at the raw Frappe
    DocType-permission level (see bp_workflow.json — same restrictive
    backstop BP Automation Rule's own JSON uses); real authorization happens
    here, then callers use ignore_permissions=True past that backstop."""
    from batch_projects.api.board import _require_automation_admin
    _require_automation_admin(scope, project)


def _as_dict_or_list(value, default):
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


@frappe.whitelist()
def list_workflows(project=None):
    """Workflows visible to the caller: their project's own + every
    workspace-scope one. Mirrors the same bucket logic BP Automation Rule's
    `get_automation_rules` already uses — open to viewers on the
    project-scoped call, workspace admin only for the unscoped call."""
    require_feature("automations")
    # This file was the one automation surface with no gateway check at all
    # (board.py's own helpers — _check_permission/_require_system_user —
    # bake it in; workflows.py's ad-hoc access.is_workspace_admin() checks on
    # the workspace-scope path don't). require_feature() alone isn't enough:
    # a direct-to-Frappe caller could still inherit a CACHED tier value from
    # a prior legitimate gateway request (current_tier()'s 3rd fallback).
    # This is the hard rejection — no valid gateway signature, no access,
    # regardless of what tier resolves.
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    from batch_projects import access
    if project:
        from batch_projects.api.board import _check_permission
        _check_permission(project, "BP Viewer")
    elif not access.is_workspace_admin():
        frappe.throw(_("You need workspace admin access for workspace-scope automations."), frappe.PermissionError)

    filters = [["is_active", "=", 1]]
    or_filters = [["scope", "=", "workspace"]]
    if project:
        or_filters.append(["scope", "=", "project"])
        or_filters.append(["project", "=", project])
    return frappe.get_all(
        "BP Workflow",
        filters=filters if not project else None,
        or_filters=or_filters if project else None,
        fields=["name", "title", "scope", "project", "is_active", "last_run_at", "last_run_status", "modified"],
        order_by="modified desc",
        ignore_permissions=True,
    )


@frappe.whitelist()
def get_workflow(name):
    require_feature("automations")
    # This file was the one automation surface with no gateway check at all
    # (board.py's own helpers — _check_permission/_require_system_user —
    # bake it in; workflows.py's ad-hoc access.is_workspace_admin() checks on
    # the workspace-scope path don't). require_feature() alone isn't enough:
    # a direct-to-Frappe caller could still inherit a CACHED tier value from
    # a prior legitimate gateway request (current_tier()'s 3rd fallback).
    # This is the hard rejection — no valid gateway signature, no access,
    # regardless of what tier resolves.
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    if not frappe.db.exists("BP Workflow", name):
        frappe.throw(_("Workflow not found."))
    doc = frappe.get_doc("BP Workflow", name)
    from batch_projects import access
    if doc.scope == "project":
        from batch_projects.api.board import _check_permission
        _check_permission(doc.project, "BP Viewer")
    elif not access.is_workspace_admin():
        frappe.throw(_("You need workspace admin access for workspace-scope automations."), frappe.PermissionError)
    return {
        "name": doc.name,
        "title": doc.title,
        "scope": doc.scope,
        "project": doc.project,
        "project_filter": _as_dict_or_list(doc.project_filter, []),
        "is_active": doc.is_active,
        "nodes": _as_dict_or_list(doc.nodes, []),
        "edges": _as_dict_or_list(doc.edges, []),
        "canvas_meta": _as_dict_or_list(doc.canvas_meta, {}),
        "last_run_at": doc.last_run_at,
        "last_run_status": doc.last_run_status,
    }


@frappe.whitelist()
def save_workflow(name=None, title=None, scope="workspace", project=None,
                   project_filter=None, nodes=None, edges=None, canvas_meta=None, is_active=1):
    """Create (name=None) or update (name=<existing>) a workflow in one call
    — the canvas has no reason to distinguish create-vs-update client-side,
    the doctype's own autoname:hash already handles both."""
    require_feature("automations")
    # This file was the one automation surface with no gateway check at all
    # (board.py's own helpers — _check_permission/_require_system_user —
    # bake it in; workflows.py's ad-hoc access.is_workspace_admin() checks on
    # the workspace-scope path don't). require_feature() alone isn't enough:
    # a direct-to-Frappe caller could still inherit a CACHED tier value from
    # a prior legitimate gateway request (current_tier()'s 3rd fallback).
    # This is the hard rejection — no valid gateway signature, no access,
    # regardless of what tier resolves.
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    _require_workflow_admin(scope or "workspace", project)

    payload = {
        "title": title or "Untitled workflow",
        "scope": scope,
        "project": project if scope == "project" else None,
        "project_filter": json.dumps(_as_dict_or_list(project_filter, [])),
        "nodes": json.dumps(_as_dict_or_list(nodes, [])),
        "edges": json.dumps(_as_dict_or_list(edges, [])),
        "canvas_meta": json.dumps(_as_dict_or_list(canvas_meta, {})),
        "is_active": 1 if int(is_active or 0) else 0,
    }

    if name and frappe.db.exists("BP Workflow", name):
        doc = frappe.get_doc("BP Workflow", name)
        # Re-check against the EXISTING doc's own scope/project too — a
        # caller who is admin of the NEW scope shouldn't be able to use that
        # to silently take over a workflow they don't actually administer.
        _require_workflow_admin(doc.scope, doc.project)
        doc.update(payload)
    else:
        doc = frappe.get_doc({"doctype": "BP Workflow", **payload})

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "title": doc.title}


def _trigger_event_for_node(node):
    """Resolves a trigger NODE to the bus event name it listens for — the
    Python-side twin of Go's workflowTriggerEvent (graph.go), reading the
    SAME registry (_NODE_REGISTRY) that function's own docstring points back
    to, rather than a third hand-maintained copy. Returns None for
    trigger.schedule (polled, not envelope-driven — can't be "test fired")
    or an unrecognized node type."""
    from batch_projects.api.automation import _NODE_REGISTRY
    meta = _NODE_REGISTRY.get(node.get("type"))
    if not meta:
        return None
    fixed = meta.get("maps_to_trigger_event")
    if fixed:
        return fixed
    if node.get("type") in ("trigger.task_event", "trigger.project_event", "trigger.sprint_event", "trigger.erp_finance"):
        return (node.get("config") or {}).get("event") or None
    return None


@frappe.whitelist()
def test_workflow(name, task=None):
    """Fires the workflow's own trigger through the REAL gateway pipeline
    (WORKPLAN-PHASE25 A3) — not a dry-run. Whatever the workflow's action
    nodes do, they really happen, exactly like a genuine event firing (same
    posture bp_automation_rule's rules already have — there is no sandboxed
    execution mode anywhere in this engine, this doesn't invent one).

    Task-centric by design (mirrors the spec's own framing): builds the
    envelope from the given task, or the most recently updated task in
    scope. A non-task trigger (webhook/doc_event/project/sprint/finance)
    still fires — forced event name, project riding along — just without
    the task-shaped fields such a trigger's OWN conditions might reference;
    those trigger types are honestly under-served by "test with a task"
    and a real fixture (curl/console) remains the precise way to test them.
    """
    require_feature("automations")
    # This file was the one automation surface with no gateway check at all
    # (board.py's own helpers — _check_permission/_require_system_user —
    # bake it in; workflows.py's ad-hoc access.is_workspace_admin() checks on
    # the workspace-scope path don't). require_feature() alone isn't enough:
    # a direct-to-Frappe caller could still inherit a CACHED tier value from
    # a prior legitimate gateway request (current_tier()'s 3rd fallback).
    # This is the hard rejection — no valid gateway signature, no access,
    # regardless of what tier resolves.
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    if not frappe.db.exists("BP Workflow", name):
        frappe.throw(_("Workflow not found."))
    doc = frappe.get_doc("BP Workflow", name)
    _require_workflow_admin(doc.scope, doc.project)

    if (frappe.conf.get("bp_automation_engine") or "python").lower() != "gateway":
        frappe.throw(_("Test workflow requires the gateway engine."))
    if not doc.is_active:
        # Not just a courtesy: list_active_workflows filters is_active=1, so
        # the gateway's own project/workspace bucket cache wouldn't even
        # CONTAIN a paused workflow — firing its trigger would publish an
        # envelope that reaches processEvent and then matches nothing,
        # silently looking like "it worked" while doing nothing at all.
        frappe.throw(_("Activate the workflow before testing it — paused workflows aren't loaded by the automation engine."))

    nodes = _as_dict_or_list(doc.nodes, [])
    trigger = next((n for n in nodes if str(n.get("type", "")).startswith("trigger.")), None)
    if not trigger:
        frappe.throw(_("This workflow has no trigger node."))

    event_name = _trigger_event_for_node(trigger)
    if not event_name:
        frappe.throw(_("This trigger type can't be tested manually yet."))

    task_doc = None
    if task:
        if not frappe.db.exists("BP Task", task):
            frappe.throw(_("Task not found."))
        task_doc = frappe.get_doc("BP Task", task)
    else:
        filters = {"project": doc.project} if doc.scope == "project" and doc.project else {}
        recent = frappe.db.get_value("BP Task", filters, "name", order_by="modified desc")
        if recent:
            task_doc = frappe.get_doc("BP Task", recent)

    payload = {"project": doc.project}
    if task_doc:
        # to_status == from_status: a test run asks "does this task, AS IT
        # STANDS RIGHT NOW, look like it just satisfied this trigger" rather
        # than fabricating a fake transition — the honest reading of
        # "test with this task" when there's no real prior state to diff.
        payload.update({
            "task": task_doc.name, "project": task_doc.project,
            "to_status": task_doc.status, "from_status": task_doc.status,
            "changes": [],
        })

    from batch_projects.events import _event_envelope
    from batch_projects import bridge
    envelope = _event_envelope(event_name, payload)
    envelope["__bp_test__"] = True  # metadata only — no code branches on this today

    if not bridge.publish_event(envelope):
        frappe.throw(_("Could not reach the automation engine — check the bridge connection."))

    return {
        "status": "fired", "event": event_name,
        "task": task_doc.name if task_doc else None,
        "fired_at": frappe.utils.now_datetime(),
    }


@frappe.whitelist()
def get_workflow_runs(workflow, since=None, limit=20):
    """Runs grouped by run_id, newest group first (WORKPLAN-PHASE25 A3/A4) —
    the Test workflow poll and the Executions view read the same shape.
    `since` (a datetime string) scopes to runs at/after that moment — how
    the Test workflow poll isolates ITS OWN run without trying to predict
    Go's nanosecond-timestamp run_id ahead of time (that ID doesn't exist
    until runWorkflow generates it server-side, well after this call
    returns "fired"). Viewer-gated like get_workflow, not admin-only —
    anyone who can see the workflow can see its run history."""
    require_feature("automations")
    # This file was the one automation surface with no gateway check at all
    # (board.py's own helpers — _check_permission/_require_system_user —
    # bake it in; workflows.py's ad-hoc access.is_workspace_admin() checks on
    # the workspace-scope path don't). require_feature() alone isn't enough:
    # a direct-to-Frappe caller could still inherit a CACHED tier value from
    # a prior legitimate gateway request (current_tier()'s 3rd fallback).
    # This is the hard rejection — no valid gateway signature, no access,
    # regardless of what tier resolves.
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    if not frappe.db.exists("BP Workflow", workflow):
        frappe.throw(_("Workflow not found."))
    doc = frappe.get_doc("BP Workflow", workflow)
    from batch_projects import access
    if doc.scope == "project":
        from batch_projects.api.board import _check_permission
        _check_permission(doc.project, "BP Viewer")
    elif not access.is_workspace_admin():
        frappe.throw(_("You need workspace admin access for workspace-scope automations."), frappe.PermissionError)

    filters = {"workflow": workflow}
    if since:
        filters["run_at"] = [">=", since]
    rows = frappe.get_all(
        "BP Workflow Run", filters=filters,
        fields=["run_id", "node_id", "node_type", "status", "message", "run_at"],
        order_by="run_at asc",
    )

    groups = {}
    order = []
    for r in rows:
        if r.run_id not in groups:
            groups[r.run_id] = {"run_id": r.run_id, "started_at": r.run_at, "nodes": []}
            order.append(r.run_id)
        groups[r.run_id]["nodes"].append({
            "node_id": r.node_id, "node_type": r.node_type,
            "status": r.status, "message": r.message, "run_at": r.run_at,
        })

    result = []
    for run_id in reversed(order):  # newest run first; each group's own nodes stay chronological
        g = groups[run_id]
        g["status"] = "Failed" if any(n["status"] == "Failed" for n in g["nodes"]) else "Success"
        result.append(g)
    return result[: int(limit or 20)]


@frappe.whitelist()
def delete_workflow(name):
    require_feature("automations")
    # This file was the one automation surface with no gateway check at all
    # (board.py's own helpers — _check_permission/_require_system_user —
    # bake it in; workflows.py's ad-hoc access.is_workspace_admin() checks on
    # the workspace-scope path don't). require_feature() alone isn't enough:
    # a direct-to-Frappe caller could still inherit a CACHED tier value from
    # a prior legitimate gateway request (current_tier()'s 3rd fallback).
    # This is the hard rejection — no valid gateway signature, no access,
    # regardless of what tier resolves.
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    if not frappe.db.exists("BP Workflow", name):
        frappe.throw(_("Workflow not found."))
    doc = frappe.get_doc("BP Workflow", name)
    _require_workflow_admin(doc.scope, doc.project)
    frappe.delete_doc("BP Workflow", name, ignore_permissions=True)
    frappe.db.commit()
    return {"status": "deleted"}


# ─── RULE → WORKFLOW CONVERSION (WORKPLAN-PHASE25 A5) ───────────────────────
#
# BP Automation Rule (flat trigger/conditions/actions) and BP Workflow
# (nodes/edges graph) are different schemas — this is a deterministic,
# LOSSLESS conversion, not a view toggle. The source rule is left completely
# untouched and still running; the two coexist until a human pauses the rule.

# task.due_soon/task.overdue are excluded from trigger.task_event's OWN
# palette dropdown (see automation.py's _NODE_REGISTRY comment) because the
# daily scan jobs that publish them only look for BP Automation Rules, never
# BP Workflows — a converted workflow using either would silently never
# fire. Same reasoning, applied here: refuse the conversion rather than hand
# back a workflow that looks fine but is structurally dead.
_UNCONVERTIBLE_TASK_EVENTS = {"task.due_soon", "task.overdue"}


def _extract_doc_event_fields(conditions):
    """erp.doc_event rules scope via conditions clauses on "doctype"/
    "erp_event" (see bp_automation_rule.json's own field description) —
    trigger.doc_event's node has THOSE as dedicated config fields instead.
    Pulls the two clauses out (eq only — anything else is left as a real
    condition, not silently dropped) and returns (doctype, erp_event,
    remaining_conditions)."""
    doctype = erp_event = None
    remaining = []
    for c in conditions:
        if not isinstance(c, dict):
            remaining.append(c)
            continue
        if c.get("field") == "doctype" and c.get("op", "eq") == "eq":
            doctype = c.get("value")
        elif c.get("field") == "erp_event" and c.get("op", "eq") == "eq":
            erp_event = c.get("value")
        else:
            remaining.append(c)
    return doctype, erp_event, remaining


def _rule_trigger_to_node(rule_doc):
    """Maps the rule's flat trigger_event/trigger_config/conditions onto ONE
    BP Workflow trigger node. Mirrors _NODE_REGISTRY's maps_to_trigger_event
    contract in reverse (registry: node type -> event name; here: event name
    -> node type + config) — see automation.py, not re-declared here."""
    event = rule_doc.trigger_event
    conditions = _as_dict_or_list(rule_doc.conditions, [])
    if not isinstance(conditions, list):
        conditions = []  # {all:/any:} shape: rare on hand-authored rules — not attempted here, kept as [] rather than guessed
    trigger_config = _as_dict_or_list(rule_doc.trigger_config, {})

    if event.startswith("schedule."):
        frappe.throw(_("Schedule rules can't be converted to a workflow yet."))
    if event in _UNCONVERTIBLE_TASK_EVENTS:
        frappe.throw(_(f"{event!r} rules can't be converted — the scheduled scan that fires them doesn't look at workflows yet."))

    base = {"id": "n1", "position": {"x": 40, "y": 160}}

    if event.startswith("task."):
        cfg = {"event": event, "conditions": conditions}
        if event == "task.field_changed":
            cfg["field"] = trigger_config.get("field")
            # Read by Go's CompiledTriggerMatches / Python's
            # _compiled_trigger_matches directly (cfg["from"]/cfg["to"]) —
            # NOT part of `conditions`, a separate matching mechanism
            # entirely (see bp_automation_rule.py's own module docstring).
            if trigger_config.get("from") not in (None, ""):
                cfg["from"] = trigger_config["from"]
            if trigger_config.get("to") not in (None, ""):
                cfg["to"] = trigger_config["to"]
        return {**base, "type": "trigger.task_event", "label": "Trigger", "config": cfg}

    if event == "comment.added":
        return {**base, "type": "trigger.comment_added", "label": "Comment added", "config": {"conditions": conditions}}

    if event == "erp.doc_event":
        doctype, erp_event, remaining = _extract_doc_event_fields(conditions)
        cfg = {"doctype": doctype, "erp_event": erp_event, "conditions": remaining}
        return {**base, "type": "trigger.doc_event", "label": "ERP doc event", "config": cfg}

    if event in ("erp.invoice_submitted", "erp.payment_received", "erp.so_confirmed"):
        cfg = {"event": event, "conditions": conditions}
        return {**base, "type": "trigger.erp_finance", "label": "ERP finance event", "config": cfg}

    if event == "external.webhook":
        # No webhook_token on BP Automation Rule at all — the flat engine
        # never scoped external.webhook rules to one token, matching ANY
        # active token's delivery (conditions are the only filter), and
        # trigger.webhook's OWN matching mirrors that (webhook_token is
        # display/URL-copy only, never checked in workflowTriggerMatches —
        # see graph.go). Left unset; the converted draft's Webhook node
        # dialog (WORKPLAN-PHASE25 B3) is exactly where a human picks one.
        cfg = {"webhook_token": None, "response_mode": "immediate", "conditions": conditions}
        return {**base, "type": "trigger.webhook", "label": "Webhook", "config": cfg}

    frappe.throw(_(f"Trigger {event!r} isn't supported by the workflow converter yet."))


@frappe.whitelist()
def convert_rule_to_workflow(rule):
    require_feature("automations")
    # This file was the one automation surface with no gateway check at all
    # (board.py's own helpers — _check_permission/_require_system_user —
    # bake it in; workflows.py's ad-hoc access.is_workspace_admin() checks on
    # the workspace-scope path don't). require_feature() alone isn't enough:
    # a direct-to-Frappe caller could still inherit a CACHED tier value from
    # a prior legitimate gateway request (current_tier()'s 3rd fallback).
    # This is the hard rejection — no valid gateway signature, no access,
    # regardless of what tier resolves.
    from batch_projects.gateway_guard import verify_gateway_request
    verify_gateway_request()
    if not frappe.db.exists("BP Automation Rule", rule):
        frappe.throw(_("Rule not found."))
    rule_doc = frappe.get_doc("BP Automation Rule", rule)

    from batch_projects.api.board import _require_automation_admin
    _require_automation_admin(rule_doc.scope, rule_doc.project)

    trigger_node = _rule_trigger_to_node(rule_doc)

    from batch_projects.api.automation import _ACTION_TYPE_TO_NODE_TYPE
    from batch_projects.batch_projects.doctype.bp_automation_rule.bp_automation_rule import _get_actions

    nodes = [trigger_node]
    edges = []
    prev_id = trigger_node["id"]
    for i, action in enumerate(_get_actions(rule_doc)):
        node_type = _ACTION_TYPE_TO_NODE_TYPE.get(action.get("type"))
        if not node_type:
            frappe.throw(_(f"Action type {action.get('type')!r} isn't supported by the workflow converter yet."))
        node_id = f"a{i + 1}"
        nodes.append({
            "id": node_id, "type": node_type, "label": action.get("type"),
            "position": {"x": 40 + 300 * (i + 1), "y": 160},
            "config": action.get("config") or {},
        })
        edges.append({"id": f"e{i}", "source": prev_id, "target": node_id})
        prev_id = node_id

    res = save_workflow(
        title=f"{rule_doc.rule_name} (workflow)",
        scope=rule_doc.scope, project=rule_doc.project,
        project_filter=_as_dict_or_list(rule_doc.project_filter, []),
        nodes=nodes, edges=edges, is_active=0,  # draft — rule keeps running until a human activates this
    )
    return {"name": res["name"], "title": res["title"]}
