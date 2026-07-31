"""Wrap every existing BP Automation Rule's single action_type/
action_config pair into the new ordered `actions` list ([{type, config}]),
and stamp scope="project" (the only scope that existed pre-v2). Old fields
are left populated (now hidden/read-only) for one release, for rollback —
this patch only ADDS the new shape, it never clears the legacy one."""

import frappe
import json


def execute():
    rows = frappe.get_all(
        "BP Automation Rule",
        filters={"actions": ["in", ["", "[]", None]]},
        fields=["name", "action_type", "action_config", "project", "scope"],
    )
    migrated = 0
    for r in rows:
        if not r.get("action_type"):
            continue
        try:
            cfg = json.loads(r.action_config) if isinstance(r.action_config, str) and r.action_config else (r.action_config or {})
        except (json.JSONDecodeError, TypeError):
            cfg = {}
        actions = json.dumps([{"type": r.action_type, "config": cfg}])
        updates = {"actions": actions}
        if not r.get("scope"):
            updates["scope"] = "project"
        frappe.db.set_value("BP Automation Rule", r.name, updates)
        migrated += 1
    frappe.db.commit()
    print(f"  Migrated {migrated} automation rule(s) to the v2 actions shape")
