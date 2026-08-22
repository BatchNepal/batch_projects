"""Backfill BP Automation Run / BP Workflow Run telemetry_key for existing
rows before the DocType's own unique index is enforced by migration.

log_workflow_run/log_rule_run wrote rows via a get_value()-then-insert check
— a race under concurrency, since two redelivered/concurrent callers can both
see "not found" and both insert. telemetry_key (sha256 of the same identity
tuple _upsert_run_log now keys on) makes the database itself the arbiter via
its own unique constraint; this patch computes that key for rows written
before this migration, and — since a duplicate telemetry_key can now only
mean two rows genuinely describing the same (execution, node, attempt), i.e.
exactly the race this fix closes — keeps the most recently modified one and
removes the rest so the unique index below can actually be created.

Rows are processed newest-first (order_by="modified desc"): the first time a
key is seen it's necessarily the newest row with that key, so it's the one
kept; every later encounter of the same key is, by construction, an older
duplicate.
"""

import hashlib

import frappe


def _telemetry_key(*parts):
    return hashlib.sha256("\0".join(str(p or "") for p in parts).encode()).hexdigest()


def execute():
    _backfill_workflow_run()
    _backfill_automation_run()


def _backfill_workflow_run():
    rows = frappe.get_all(
        "BP Workflow Run",
        fields=["name", "execution", "run_id", "node_id", "attempt"],
        order_by="modified desc",
    )
    seen = set()
    for row in rows:
        key = _telemetry_key(row.execution or row.run_id, row.node_id, row.attempt)
        if key in seen:
            frappe.delete_doc("BP Workflow Run", row.name, ignore_permissions=True, delete_permanently=True)
            continue
        seen.add(key)
        frappe.db.set_value("BP Workflow Run", row.name, "telemetry_key", key, update_modified=False)
    frappe.db.commit()


def _backfill_automation_run():
    rows = frappe.get_all(
        "BP Automation Run",
        fields=["name", "execution_id", "action_index", "attempt"],
        order_by="modified desc",
    )
    seen = set()
    for row in rows:
        key = _telemetry_key(row.execution_id, row.action_index, row.attempt)
        if key in seen:
            frappe.delete_doc("BP Automation Run", row.name, ignore_permissions=True, delete_permanently=True)
            continue
        seen.add(key)
        frappe.db.set_value("BP Automation Run", row.name, "telemetry_key", key, update_modified=False)
    frappe.db.commit()
