"""
BP Workflow
───────────
The graph automation surface — additive alongside `BP Automation
Rule` (that doctype's simple flat-list rules are untouched; see
WORKPLAN-PHASE24-AUTOMATION-CANVAS/00-README.md Ground Rule 6).

`nodes`/`edges` are a flat array pair (Vue Flow's own native shape), not
a nested connections-by-node-name map — see 01-DATA-MODEL.md §2 for why.
Validation here is the SERVER-SIDE gate; the canvas UI should also validate
client-side for UX, but this is the one that actually matters.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document


class BPWorkflow(Document):
    def validate(self):
        self._validate_json("nodes")
        self._validate_json("edges")
        self._validate_json("project_filter")
        self._validate_json("canvas_meta")

        if self.scope == "project" and not self.project:
            frappe.throw(_("Project is required when scope is 'project'."))
        if self.scope == "workspace":
            self.project = None

        nodes = _parse(self.nodes)
        edges = _parse(self.edges)
        if not isinstance(nodes, list) or not isinstance(edges, list):
            frappe.throw(_("Nodes and edges must be JSON arrays."))

        node_ids = self._validate_node_ids(nodes)
        self._validate_edges(edges, node_ids)
        self._validate_trigger_count(nodes)
        self._validate_doc_event_scope(nodes)
        self._validate_error_branches(nodes, edges)
        self._validate_no_cycles(node_ids, edges)
        self._set_automation_definition_identity(nodes, edges)

    def _set_automation_definition_identity(self, nodes, edges):
        definition_hash = workflow_definition_hash(self, nodes, edges)
        previous = self.get_doc_before_save()
        previous_hash = previous.get("automation_definition_hash") if previous else None
        previous_revision = int(previous.get("automation_revision") or 0) if previous else 0
        if not previous:
            self.automation_revision = max(1, int(self.automation_revision or 0))
        elif previous_hash != definition_hash:
            self.automation_revision = max(1, previous_revision + 1)
        else:
            self.automation_revision = max(1, previous_revision)
        self.automation_definition_hash = definition_hash

    def _validate_json(self, fieldname):
        raw = self.get(fieldname)
        if not raw:
            return
        try:
            json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            frappe.throw(_("{0} must be valid JSON.").format(fieldname))

    def _validate_node_ids(self, nodes) -> set:
        ids = []
        for n in nodes:
            if not isinstance(n, dict) or not n.get("id"):
                frappe.throw(_("Every node needs an id."))
            ids.append(n["id"])
        if len(ids) != len(set(ids)):
            dupes = {i for i in ids if ids.count(i) > 1}
            frappe.throw(_("Duplicate node id(s): {0}").format(", ".join(sorted(dupes))))
        return set(ids)

    def _validate_edges(self, edges, node_ids: set):
        for e in edges:
            if not isinstance(e, dict):
                frappe.throw(_("Every edge must be an object."))
            src, tgt = e.get("source"), e.get("target")
            if src not in node_ids:
                frappe.throw(_("Edge {0} references unknown source node '{1}'.").format(e.get("id", "?"), src))
            if tgt not in node_ids:
                frappe.throw(_("Edge {0} references unknown target node '{1}'.").format(e.get("id", "?"), tgt))

    def _validate_trigger_count(self, nodes):
        triggers = [n for n in nodes if isinstance(n.get("type"), str) and n["type"].startswith("trigger.")]
        if len(nodes) == 0:
            return  # an empty in-progress workflow is fine to save as a draft
        if len(triggers) == 0:
            frappe.throw(_("Workflow needs exactly one trigger node (none found)."))
        if len(triggers) > 1:
            frappe.throw(_("Workflow needs exactly one trigger node (found {0}: {1}) — multi-trigger workflows aren't supported yet.").format(
                len(triggers), ", ".join(t["id"] for t in triggers)))

    def _validate_doc_event_scope(self, nodes):
        """erp.doc_event carries no project — erp_triggers.py's wildcard
        doctype hook can't generically resolve one for an arbitrary
        doctype, unlike the 4 hand-wired ERPNext triggers. A project-scope
        workflow using this trigger would therefore never fire (the gateway
        only matches it against unfiltered workspace-scope workflows) —
        reject at save time instead of shipping a silently-dead workflow."""
        has_doc_event_trigger = any(n.get("type") == "trigger.doc_event" for n in nodes)
        if has_doc_event_trigger and self.scope != "workspace":
            frappe.throw(_("An 'ERP doc event' trigger only fires for workspace-scope workflows — it carries no project to scope to."))

    def _validate_error_branches(self, nodes, edges):
        """A node with on_error='error_branch' must have a real edge whose
        sourceHandle is 'error' — otherwise the Go engine would hit an
        unreachable combination at run time (see 04-GO-EXECUTION-ENGINE.md
        §2). Catch it at save time instead."""
        by_node_error_edges = set()
        for e in edges:
            if e.get("sourceHandle") == "error":
                by_node_error_edges.add(e.get("source"))
        for n in nodes:
            if n.get("on_error") == "error_branch" and n["id"] not in by_node_error_edges:
                frappe.throw(_("Node '{0}' has on_error='error_branch' but no edge routes its 'error' output anywhere.").format(n["id"]))

    def _validate_no_cycles(self, node_ids: set, edges):
        """Kahn's algorithm. A cycle means the graph can never finish
        executing — reject at save time, not discovered by the Go engine
        mid-run (which re-checks this defensively too, per 04 §2, in case a
        row is ever edited directly in the DB)."""
        indegree = {nid: 0 for nid in node_ids}
        adjacency = {nid: [] for nid in node_ids}
        for e in edges:
            src, tgt = e.get("source"), e.get("target")
            adjacency[src].append(tgt)
            indegree[tgt] += 1

        queue = [nid for nid, deg in indegree.items() if deg == 0]
        visited = 0
        while queue:
            nid = queue.pop()
            visited += 1
            for nxt in adjacency[nid]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)

        if visited != len(node_ids):
            stuck = sorted(nid for nid, deg in indegree.items() if deg > 0)
            frappe.throw(_("Workflow has a cycle involving node(s): {0}").format(", ".join(stuck)))

    # ── Bridge scheduler registration (WORKPLAN-PHASE25 B5) ─────────────────
    # A workflow with a trigger.schedule node runs on the Go agent's durable
    # timer, not in Frappe — mirrors BP Automation Rule's own
    # on_update/on_trash/_sync_schedule EXACTLY (register on save, cancel on
    # delete/deactivation/re-save). The one real difference: kind is
    # "workflow.scheduled", not "automation.scheduled" — the gateway
    # dispatches that kind by running the workflow DIRECTLY in Go
    # (scheduler.WorkflowRunner -> automation.Engine.RunScheduledWorkflow),
    # never calling back into Frappe's rule path (see graph.go). Recurring-
    # interval only for now — schedule.relative's per-task date-proximity
    # scan (BP Automation Rule's _run_relative_schedule) has no
    # workflow-graph equivalent yet, so that kind is deliberately not
    # offered in the trigger.schedule config_schema (automation.py) at all.
    def on_update(self):
        nodes = _parse(self.nodes)
        if not _find_schedule_node(nodes) and not self.bridge_job_id:
            return
        self._sync_schedule(nodes)

    def on_trash(self):
        if self.bridge_job_id:
            from batch_projects import bridge
            bridge.cancel_scheduled_job(self.bridge_job_id)

    def _sync_schedule(self, nodes):
        from batch_projects import bridge

        # Always clear the old registration first — covers edits (interval
        # change, trigger swapped for a different type) and deactivation.
        if self.bridge_job_id:
            bridge.cancel_scheduled_job(self.bridge_job_id)
            self.db_set("bridge_job_id", None, update_modified=False)

        node = _find_schedule_node(nodes)
        if not (node and self.is_active):
            return

        cfg = node.get("config") or {}
        every = int(cfg.get("every") or 1)
        unit = cfg.get("unit") or "hours"
        interval = every * _SECONDS_PER_UNIT.get(unit, 3600)

        job_id = bridge.register_scheduled_job(
            kind="workflow.scheduled",
            event="schedule.tick",
            payload={"workflow": self.name, "scope": self.scope, "project": self.project},
            delay_seconds=interval,  # first fire one interval out — no first_run concept for workflows (unlike rules)
            interval_seconds=interval,
        )
        if job_id:
            self.db_set("bridge_job_id", job_id, update_modified=False)
        elif bridge.is_configured():
            frappe.msgprint(
                _("Could not register this scheduled workflow with the automation agent. "
                  "It will not fire until re-saved."),
                indicator="orange", alert=True,
            )


_SECONDS_PER_UNIT = {"minutes": 60, "hours": 3600, "days": 86400, "weeks": 604800}


def _find_schedule_node(nodes):
    return next((n for n in nodes if n.get("type") == "trigger.schedule"), None)


def _parse(raw):
    if not raw:
        return []
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def workflow_definition_hash(workflow, nodes=None, edges=None):
    """Hash only data that changes graph execution semantics."""
    nodes = nodes if nodes is not None else _parse(workflow.nodes)
    edges = edges if edges is not None else _parse(workflow.edges)
    canonical = {
        "is_active": bool(workflow.get("is_active")),
        "scope": workflow.get("scope"),
        "project": workflow.get("project"),
        "project_filter": _parse(workflow.get("project_filter")),
        "nodes": sorted((_canonical_node(node) for node in nodes), key=lambda node: node["id"]),
        "edges": sorted((_canonical_edge(edge) for edge in edges), key=lambda edge: (
            edge["source"], edge["target"], edge["source_handle"],
        )),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _canonical_node(node):
    return {
        "id": node.get("id"),
        "type": node.get("type"),
        "config": node.get("config") or {},
        "disabled": bool(node.get("disabled")),
        "retry": node.get("retry") or None,
        "on_error": node.get("on_error") or "stop",
    }


def _canonical_edge(edge):
    return {
        "source": edge.get("source"),
        "target": edge.get("target"),
        "source_handle": edge.get("sourceHandle") or "",
    }
